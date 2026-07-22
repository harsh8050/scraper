import time
import os
import urllib.request
import random
import pydub
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, StaleElementReferenceException
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

recaptcha_words = [
    "apple tree", "blue sky", "silver coin", "happy child", "gold star",
    "fast car", "river bank", "mountain peak", "red house", "sun flower",
    "deep ocean", "bright moon", "green grass", "snow fall", "strong wind",
    "dark night", "big city", "tall building", "small village", "soft pillow",
    "quiet room", "loud noise", "warm fire", "cold water", "heavy rain",
    "hot coffee", "empty street", "open door", "closed window", "white cloud",
    "yellow light", "long road", "short path", "new book", "old paper",
    "broken clock", "silent night", "early morning", "late evening", "clear sky",
    "dusty road", "sharp knife", "dull pencil", "lost key", "found wallet",
    "strong bridge", "weak signal", "fast train", "slow boat", "hidden message",
    "bright future", "dark past", "deep forest", "shallow lake", "frozen river",
    "burning candle", "flying bird", "running horse", "jumping fish", "falling leaf",
    "climbing tree", "rolling stone", "melting ice", "whispering wind", "shining star",
    "crying baby", "laughing child", "singing voice", "barking dog", "meowing cat",
    "chirping bird", "roaring lion", "galloping horse", "buzzing bee", "silent whisper",
    "drifting boat", "rushing water", "ticking clock", "clicking sound", "typing keyboard",
    "ringing bell", "blinking light", "floating balloon", "spinning wheel", "crashing waves",
    "boiling water", "freezing air", "burning wood", "echoing voice", "howling wind",
    "glowing candle", "rustling leaves", "dancing flame", "rattling chains", "splashing water",
    "twisting road", "swinging door", "glistening snow", "pouring rain", "shaking ground"
]

def voicereco(AUDIO_FILE):
    import speech_recognition as sr

    recognizer = sr.Recognizer()
    
    try:
        with sr.AudioFile(AUDIO_FILE) as source:
            logger.info("Processing audio file...")
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = recognizer.record(source)

            try:
                text = recognizer.recognize_google(audio)
                logger.info(f"Extracted Text: '{text}'")
                return text
            except sr.UnknownValueError:
                logger.warning("Could not understand audio.")
                return None
            except sr.RequestError as e:
                logger.error(f"Speech recognition request error: {e}")
                return None
    except Exception as e:
        logger.error(f"Error processing audio file: {e}")
        return None

def download_audio_file(src, mp3_path, wav_path):
    """Download audio file and convert to 16kHz 16-bit mono PCM WAV"""
    max_retries = 2
    for attempt in range(max_retries):
        try:
            logger.info(f"Downloading audio (attempt {attempt + 1}/{max_retries})...")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'audio/webm,audio/ogg,audio/wav,audio/*;q=0.9,application/ogg;q=0.7,video/*;q=0.6,*/*;q=0.5',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Range': 'bytes=0-',
                'Connection': 'keep-alive',
                'Referer': 'https://www.google.com/',
                'Sec-Fetch-Dest': 'audio',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Site': 'same-origin',
            }
            
            req = urllib.request.Request(src, headers=headers)
            
            with urllib.request.urlopen(req) as response:
                with open(mp3_path, 'wb') as f:
                    f.write(response.read())
            
            logger.info("Audio file downloaded.")
            
            file_size = os.path.getsize(mp3_path)
            logger.info(f"Audio file size: {file_size} bytes")
            
            if file_size < 1000:
                logger.error(f"File too small ({file_size} bytes), probably not audio")
                return False
            
            # Convert MP3/audio to 16kHz 16-bit Mono PCM WAV (prevents FLAC dependence)
            try:
                sound = pydub.AudioSegment.from_file(mp3_path)
                sound = sound.set_frame_rate(16000).set_channels(1).set_sample_width(2)
                sound.export(wav_path, format="wav")
                logger.info("Audio converted to 16kHz 16-bit Mono PCM WAV.")
                return True
            except Exception as e:
                logger.error(f"Audio conversion error: {e}")
                return False
                    
        except Exception as e:
            logger.error(f"Audio download error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                return False

def get_audio_source(driver):
    """Get the actual audio source URL from reCAPTCHA with multiple approaches"""
    try:
        time.sleep(2.5)
        
        logger.info("Looking for audio source using multiple methods...")
        
        # METHOD 0: Look for reCAPTCHA audio download link
        try:
            download_links = driver.find_elements(By.XPATH, "//a[contains(@class, 'rc-audio-challenge-download-link') or contains(@href, 'payload') or contains(@href, 'audio')]")
            for link in download_links:
                href = link.get_attribute("href") or ""
                if href and ("payload" in href or "audio" in href or ".mp3" in href):
                    logger.info(f"Found audio download link: {href[:80]}...")
                    return href
        except Exception as e:
            logger.debug(f"Download link search error: {e}")

        # METHOD 1: Look for audio element directly
        audio_elements = driver.find_elements(By.TAG_NAME, "audio")
        logger.info(f"Found {len(audio_elements)} audio elements")
        
        for i, audio in enumerate(audio_elements):
            try:
                src = audio.get_attribute("src") or ""
                id_attr = audio.get_attribute("id") or ""
                if src and not src.endswith('.js'):
                    logger.info(f"Found audio element {i}: id='{id_attr}', src='{src[:80]}...'")
                    return src
            except:
                continue
        
        # METHOD 2: Look for iframe within iframe (nested structure)
        logger.info("Checking for nested iframes...")
        nested_frames = driver.find_elements(By.TAG_NAME, "iframe")
        
        for frame_idx, frame in enumerate(nested_frames):
            try:
                driver.switch_to.frame(frame)
                logger.info(f"Switched to nested frame {frame_idx}")
                
                nested_links = driver.find_elements(By.XPATH, "//a[contains(@class, 'rc-audio-challenge-download-link') or contains(@href, 'payload') or contains(@href, 'audio')]")
                for link in nested_links:
                    href = link.get_attribute("href") or ""
                    if href:
                        logger.info(f"Found audio link in nested frame: {href[:80]}...")
                        driver.switch_to.parent_frame()
                        return href

                nested_audio = driver.find_elements(By.TAG_NAME, "audio")
                for audio in nested_audio:
                    src = audio.get_attribute("src") or ""
                    if src:
                        logger.info(f"Found audio in nested frame: {src[:80]}...")
                        driver.switch_to.parent_frame()
                        return src
                
                driver.switch_to.parent_frame()
            except Exception as e:
                logger.error(f"Error checking nested frame {frame_idx}: {e}")
                try:
                    driver.switch_to.default_content()
                except:
                    pass
        
        # METHOD 3: Use JavaScript to find all audio sources & links
        logger.info("Using JavaScript to find audio sources...")
        audio_sources = driver.execute_script("""
            var sources = [];
            var audios = document.getElementsByTagName('audio');
            for (var i = 0; i < audios.length; i++) {
                var src = audios[i].src;
                if (src && src.trim() !== '') {
                    sources.push({src: src});
                }
            }
            var sourceTags = document.querySelectorAll('audio source');
            for (var j = 0; j < sourceTags.length; j++) {
                var src = sourceTags[j].src;
                if (src && src.trim() !== '') {
                    sources.push({src: src});
                }
            }
            var links = document.querySelectorAll('a[href*="payload"], a[href*="audio"], a.rc-audio-challenge-download-link');
            for (var k = 0; k < links.length; k++) {
                var href = links[k].href;
                if (href && href.trim() !== '') {
                    sources.push({src: href});
                }
            }
            return sources;
        """)
        
        if audio_sources:
            logger.info(f"JavaScript found {len(audio_sources)} audio sources")
            for source in audio_sources:
                logger.info(f"JS Source: {source['src'][:100]}...")
                if source['src'] and not source['src'].endswith('.js'):
                    return source['src']
        
        # METHOD 4: Try to extract from page source
        logger.info("Checking page source for audio URLs...")
        page_source = driver.page_source
        
        import re
        patterns = [
            r'https://www[.]google[.]com/recaptcha/enterprise/payload[^\s"\'<>]*',
            r'https://www[.]google[.]com/recaptcha/api2/payload[^\s"\'<>]*',
            r'https://www[.]google[.]com/recaptcha/api2/[^\s"\'<>]*[.]mp3[^\s"\'<>]*',
            r'https://www[.]google[.]com/recaptcha/[^\s"\'<>]*(?:audio|payload)[^\s"\'<>]*',
            r'https://[^\s"\'<>]*recaptcha[^\s"\'<>]*(?:audio|payload|[.]mp3)[^\s"\'<>]*',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, page_source, re.IGNORECASE)
            if matches:
                for url in matches:
                    if 'recaptcha' in url.lower() and ('payload' in url.lower() or 'audio' in url.lower() or '.mp3' in url.lower()):
                        logger.info(f"Found audio URL in source: {url[:100]}...")
                        return url
        
        logger.error("No valid audio source found after all attempts")
        return None
        
    except Exception as e:
        logger.error(f"Error finding audio source: {e}")
        return None


def _find_recaptcha_anchor_frame(driver):
    """
    Find the reCAPTCHA checkbox/anchor iframe.

    Google Shopping embeds reCAPTCHA in an iframe whose:
      - src contains 'recaptcha' and 'anchor'
      - title is 'reCAPTCHA'
      - name contains 'a-' prefix (Google's naming)

    Falls back to any recaptcha/captcha frame.
    """
    try:
        driver.switch_to.default_content()
        frames = driver.find_elements(By.TAG_NAME, "iframe")
        logger.info(f"Total iframes on page: {len(frames)}")
        for i, frame in enumerate(frames):
            try:
                src   = (frame.get_attribute("src")   or "").lower()
                title = (frame.get_attribute("title") or "").lower()
                name  = (frame.get_attribute("name")  or "").lower()
                combined = src + " " + title + " " + name
                logger.info(f"  Frame {i}: title='{title[:60]}' src='{src[:60]}'")
                if "recaptcha" in combined and ("anchor" in combined or "checkbox" in combined or "i'm not a robot" in combined or "not a robot" in combined):
                    logger.info(f"Found reCAPTCHA anchor frame at index {i}")
                    return frame
            except StaleElementReferenceException:
                continue
        # Fallback: any recaptcha frame (title == 'recaptcha')
        for i, frame in enumerate(frames):
            try:
                src   = (frame.get_attribute("src")   or "").lower()
                title = (frame.get_attribute("title") or "").lower()
                name  = (frame.get_attribute("name")  or "").lower()
                combined = src + " " + title + " " + name
                if "recaptcha" in combined or "captcha" in combined:
                    logger.info(f"Found recaptcha-like frame at index {i} (fallback)")
                    return frame
            except StaleElementReferenceException:
                continue
        return None
    except Exception as e:
        logger.error(f"Error finding recaptcha anchor frame: {e}")
        return None


def _checkbox_is_checked(driver):
    """
    Return True if the reCAPTCHA checkbox aria-checked == 'true'.
    Must be called while inside the anchor iframe.
    """
    try:
        checkbox = driver.find_element(By.XPATH, "//*[@role='checkbox']")
        return (checkbox.get_attribute("aria-checked") or "").lower() == "true"
    except:
        return False


def _find_challenge_frame(driver):
    """
    Find the reCAPTCHA challenge/bframe iframe that appears after clicking the checkbox.
    Google challenge iframes have:
      - name starting with 'c-' (e.g. name="c-2u9w...")
      - src containing 'bframe', 'challenge', or 'recaptcha' (excluding 'anchor')
      - title containing 'recaptcha challenge' or 'challenge'
    """
    try:
        driver.switch_to.default_content()
        frames = driver.find_elements(By.TAG_NAME, "iframe")
        anchor = _find_recaptcha_anchor_frame(driver)

        for i, frame in enumerate(frames):
            try:
                src   = (frame.get_attribute("src")   or "").lower()
                title = (frame.get_attribute("title") or "").lower()
                name  = (frame.get_attribute("name")  or "").lower()
                combined = src + " " + title + " " + name
                
                # Exclude anchor frame
                if "anchor" not in combined:
                    if name.startswith("c-") or any(x in combined for x in ["bframe", "challenge", "recaptcha/api2/bframe", "recaptcha/enterprise/bframe", "recaptcha challenge"]):
                        logger.info(f"Found challenge frame at index {i}: name='{name}' title='{title[:40]}' src='{src[:60]}'")
                        return frame
            except StaleElementReferenceException:
                continue

        # Fallback: find any visible iframe that is not the anchor frame and has recaptcha in src/title
        for i, frame in enumerate(frames):
            try:
                if frame != anchor:
                    src   = (frame.get_attribute("src")   or "").lower()
                    title = (frame.get_attribute("title") or "").lower()
                    if ("recaptcha" in src or "recaptcha" in title) and frame.is_displayed():
                        logger.info(f"Found visible challenge frame (fallback) at index {i}: src='{src[:60]}'")
                        return frame
            except StaleElementReferenceException:
                continue

        return None
    except Exception as e:
        logger.error(f"Error finding challenge frame: {e}")
        return None


def solve_recaptcha_audio(driver):
    """
    Solve reCAPTCHA on Google Shopping pages.

    Flow:
      1. Find and switch into the reCAPTCHA anchor (checkbox) iframe.
      2. Click the checkbox.
      3. Poll up to 5 s for a challenge bframe.
         - If none appears and checkbox is now checked -> return 'solved'.
      4. If a challenge bframe appears:
         a. Switch into it, click the audio challenge button.
         b. Obtain audio URL, download, transcribe, submit.
      5. Return 'solved' or 'quit'.
    """
    try:
        logger.info("=== solve_recaptcha_audio: START ===")
        time.sleep(1.5)

        # ── Step 1: Find anchor frame ─────────────────────────────────────────
        anchor_frame = _find_recaptcha_anchor_frame(driver)
        if not anchor_frame:
            logger.info("No reCAPTCHA anchor frame found – treating as already solved.")
            return "solved"

        # ── Step 2: Switch in and click the checkbox ──────────────────────────
        try:
            driver.switch_to.frame(anchor_frame)
            logger.info("Switched into reCAPTCHA anchor frame.")
            time.sleep(1)
        except Exception as e:
            logger.error(f"Could not switch to anchor frame: {e}")
            driver.switch_to.default_content()
            return "quit"

        # If already checked, treat as solved
        if _checkbox_is_checked(driver):
            logger.info("Checkbox already checked – CAPTCHA may be pre-solved.")
            driver.switch_to.default_content()
            return "solved"

        # Locate checkbox element
        checkbox = None
        for sel in [
            ".recaptcha-checkbox-border",
            ".recaptcha-checkbox",
            "#recaptcha-anchor",
            "div.recaptcha-checkbox-border",
        ]:
            try:
                checkbox = driver.find_element(By.CSS_SELECTOR, sel)
                break
            except:
                continue
        if not checkbox:
            try:
                checkbox = driver.find_element(By.XPATH, "//*[@role='checkbox']")
            except:
                pass

        if not checkbox:
            logger.error("Cannot find checkbox element inside anchor frame.")
            driver.switch_to.default_content()
            return "quit"

        try:
            driver.execute_script("arguments[0].click();", checkbox)
            logger.info("Clicked reCAPTCHA checkbox.")
        except Exception as e:
            logger.error(f"Checkbox click failed: {e}")
            driver.switch_to.default_content()
            return "quit"

        # ── Step 3: Poll for challenge frame (max 5 s) ────────────────────────
        driver.switch_to.default_content()
        logger.info("Waiting up to 5 s for challenge frame to appear...")
        challenge_frame = None
        for _ in range(10):        # 10 x 0.5 s = 5 s
            time.sleep(0.5)
            challenge_frame = _find_challenge_frame(driver)
            if challenge_frame:
                logger.info("Challenge frame appeared.")
                break

        if not challenge_frame:
            # No audio challenge needed – verify checkbox state
            try:
                driver.switch_to.frame(anchor_frame)
                checked = _checkbox_is_checked(driver)
                driver.switch_to.default_content()
            except:
                driver.switch_to.default_content()
                checked = True  # Assume success if we can't read the state

            if checked:
                logger.info("Checkbox tick was sufficient – CAPTCHA solved!")
                return "solved"
            else:
                logger.warning("No challenge frame and checkbox not checked – possible failure.")
                return "quit"

        # ── Step 4: Switch into challenge frame ───────────────────────────────
        try:
            driver.switch_to.frame(challenge_frame)
            logger.info("Switched into challenge frame.")
            time.sleep(3)
        except Exception as e:
            logger.error(f"Failed to switch to challenge frame: {e}")
            driver.switch_to.default_content()
            return "quit"

        # ── Step 5: Click audio challenge button ──────────────────────────────
        audio_button = None
        audio_button_finders = [
            lambda: driver.find_element(By.ID, "recaptcha-audio-button"),
            lambda: driver.find_element(By.XPATH, "//button[contains(@title,'audio') or contains(@title,'Audio')]"),
            lambda: driver.find_element(By.CLASS_NAME, "rc-button-audio"),
            lambda: driver.find_element(By.XPATH, "//button[contains(.,'audio') or contains(.,'Audio')]"),
        ]
        for finder in audio_button_finders:
            try:
                audio_button = finder()
                if audio_button:
                    break
            except:
                continue

        if not audio_button:
            logger.error("Could not find audio challenge button.")
            driver.switch_to.default_content()
            return "quit"

        try:
            driver.execute_script("arguments[0].click();", audio_button)
            logger.info("Clicked audio challenge button.")
            time.sleep(5)
        except Exception as e:
            logger.error(f"Error clicking audio button: {e}")
            driver.switch_to.default_content()
            return "quit"

        # ── Step 6: Multi-Round Audio Solution Loop ────────────────────────────
        # Google reCAPTCHA frequently requires 2-4 consecutive correct audio solutions
        max_audio_rounds = 4
        for round_idx in range(1, max_audio_rounds + 1):
            logger.info(f"--- Audio Solve Round {round_idx}/{max_audio_rounds} ---")

            # Obtain audio source URL
            audio_src = get_audio_source(driver)

            if not audio_src:
                try:
                    reload_btn = driver.find_element(By.ID, "recaptcha-reload-button")
                    driver.execute_script("arguments[0].click();", reload_btn)
                    logger.info("Clicked reload, retrying audio source...")
                    time.sleep(4)
                    audio_src = get_audio_source(driver)
                except:
                    pass

            if not audio_src:
                logger.error("Could not obtain audio source URL.")
                driver.switch_to.default_content()
                return "quit"

            if audio_src.endswith('.js') or 'recaptcha__en.js' in audio_src:
                logger.error(f"Got JS file instead of audio: {audio_src[:100]}")
                driver.switch_to.default_content()
                return "quit"

            # Download & transcribe
            timestamp = int(time.time())
            mp3_path  = os.path.join(os.getcwd(), f"captcha_audio_{timestamp}_{round_idx}.mp3")
            wav_path  = os.path.join(os.getcwd(), f"captcha_audio_{timestamp}_{round_idx}.wav")

            logger.info(f"Downloading audio clip {round_idx}: {audio_src[:100]}...")
            if not download_audio_file(audio_src, mp3_path, wav_path):
                logger.error("Audio download failed.")
                driver.switch_to.default_content()
                return "quit"

            captcha_text = voicereco(wav_path)
            if not captcha_text:
                logger.warning("Audio recognition failed for this clip. Trying reload button for a new audio clip...")
                try:
                    reload_btn = driver.find_element(By.ID, "recaptcha-reload-button")
                    driver.execute_script("arguments[0].click();", reload_btn)
                    time.sleep(3)
                    audio_src = get_audio_source(driver)
                    if audio_src and download_audio_file(audio_src, mp3_path, wav_path):
                        captcha_text = voicereco(wav_path)
                except Exception as e:
                    logger.error(f"Error reloading audio clip: {e}")

            if not captcha_text:
                logger.error("Audio recognition failed after reload.")
                driver.switch_to.default_content()
                return "quit"

            # Type and submit response
            response_box = None
            for sel in [
                "#audio-response",
                "input[type='text']",
                "input[name='audio-response']",
                "input.audio-response",
            ]:
                try:
                    response_box = driver.find_element(By.CSS_SELECTOR, sel)
                    break
                except:
                    continue
            if not response_box:
                try:
                    response_box = driver.find_element(By.XPATH, "//input[@placeholder]")
                except:
                    pass

            if not response_box:
                logger.error("Could not find response input box.")
                driver.switch_to.default_content()
                return "quit"

            captcha_text = captcha_text.lower().strip()
            logger.info(f"Typing CAPTCHA response (round {round_idx}): '{captcha_text}'")
            response_box.clear()
            time.sleep(0.3)
            for ch in captcha_text:
                response_box.send_keys(ch)
                time.sleep(random.uniform(0.05, 0.15))
            response_box.send_keys(Keys.ENTER)
            logger.info(f"Submitted audio response for round {round_idx}.")
            time.sleep(4)

            # Check if CAPTCHA is now solved
            driver.switch_to.default_content()
            time.sleep(1)

            try:
                anchor = _find_recaptcha_anchor_frame(driver)
                if anchor:
                    driver.switch_to.frame(anchor)
                    if _checkbox_is_checked(driver):
                        logger.info("🎉 Checkbox is now checked! CAPTCHA fully solved!")
                        driver.switch_to.default_content()
                        return "solved"
                    driver.switch_to.default_content()
            except Exception:
                driver.switch_to.default_content()

            c_frame = _find_challenge_frame(driver)
            if not c_frame:
                logger.info("Challenge frame disappeared – CAPTCHA fully solved!")
                driver.switch_to.default_content()
                return "solved"

            # Challenge frame still present -> switch back in for next round
            try:
                driver.switch_to.frame(c_frame)
                logger.info("Challenge frame still present (multiple solutions required). Proceeding to next round...")
                time.sleep(2)
            except Exception:
                driver.switch_to.default_content()
                return "solved"

        driver.switch_to.default_content()
        logger.info("=== CAPTCHA solve attempt complete (max audio rounds reached) ===")
        return "solved"

    except Exception as e:
        logger.error(f"Unexpected error in solve_recaptcha_audio: {e}")
        import traceback
        traceback.print_exc()
        return "quit"
    finally:
        try:
            driver.switch_to.default_content()
        except:
            pass
        cleanup_audio_files()


def cleanup_audio_files():
    """Remove temporary audio files created during CAPTCHA solving."""
    import glob

    audio_files = glob.glob("captcha_audio_*")
    for file in audio_files:
        try:
            os.remove(file)
            logger.debug(f"Cleaned up: {file}")
        except:
            pass