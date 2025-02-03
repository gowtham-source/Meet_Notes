from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
import pyautogui
import cv2
import numpy as np
import speech_recognition as sr
import time
import os
import json
import logging
from datetime import datetime
from config import CHROME_PROFILE_PATH, RECORDING_DIR, TRANSCRIPTION_DIR
import threading
from selenium.common.exceptions import TimeoutException
from PIL import ImageGrab  
from urllib3 import PoolManager
from urllib3.util import Retry
from selenium.webdriver.common.action_chains import ActionChains
import socket
import random
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.utils import ChromeType

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('meet_notes.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MeetingRecorder:
    def __init__(self):
        self.recording = False
        self.profile_path = CHROME_PROFILE_PATH
        logger.info(f"Initialized MeetingRecorder with profile path: {self.profile_path}")
        self.setup_browser()

    def verify_cookies(self):
        """Verify if Google cookies are present"""
        try:
            cookies = self.driver.get_cookies()
            google_cookies = [cookie for cookie in cookies if '.google.com' in cookie.get('domain', '')]
            
            if google_cookies:
                logger.info("Google cookies found in profile")
                # Save cookies for debugging
                cookie_file = os.path.join(self.profile_path, 'cookies_backup.json')
                with open(cookie_file, 'w') as f:
                    json.dump(google_cookies, f)
                return True
            else:
                logger.warning("No Google cookies found in profile")
                return False
        except Exception as e:
            logger.error(f"Error verifying cookies: {e}")
            return False

    def setup_browser(self):
        """Setup Chrome browser with custom profile"""
        try:
            logger.info("Setting up Chrome browser...")
            
            # Simplified UC-compatible configuration
            options = uc.ChromeOptions()
            options.add_argument(f"--user-data-dir={self.profile_path}")
            options.add_argument("--start-maximized")
            options.add_argument("--no-default-browser-check")
            options.add_argument("--log-level=3")
            options.binary_location = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
            
            # Use webdriver manager to get the appropriate chromedriver for version 114
            driver_path = ChromeDriverManager(
                version="114.0.5735.90",
                chrome_type=ChromeType.CHROMIUM
            ).install()
            
            self.driver = uc.Chrome(
                options=options,
                driver_executable_path=driver_path,
                headless=False
            )
            
            # Remove navigator.webdriver flag
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Set normal screen resolution
            self.driver.set_window_size(1920, 1080)
            self.driver.set_page_load_timeout(30)
            
            # Verify Google login status
            logger.info("Verifying Google login status...")
            self.verify_google_login()
            
        except Exception as e:
            logger.error(f"Error initializing undetected-chromedriver: {e}")
            raise
        
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise

    def verify_google_login(self):
        """Verify Google login status using multiple checks"""
        try:
            # First check: Try accessing Google Calendar
            self.driver.get('https://calendar.google.com')
            time.sleep(3)  # Wait for redirect if not logged in
            
            # Check if we're on the calendar page
            current_url = self.driver.current_url
            if 'calendar.google.com' in current_url and 'signin' not in current_url:
                logger.info("Successfully verified Google login - Calendar access confirmed")
                return self.verify_cookies()
            
            # Second check: Try accessing Google account page
            self.driver.get('https://myaccount.google.com')
            time.sleep(3)
            
            current_url = self.driver.current_url
            if 'myaccount.google.com' in current_url and 'signin' not in current_url:
                logger.info("Successfully verified Google login - Account access confirmed")
                return self.verify_cookies()
            
            # If both checks fail, try to find login elements
            try:
                # Check for common elements that appear when logged out
                login_elements = self.driver.find_elements(By.XPATH, 
                    "//*[contains(text(), 'Sign in') or contains(text(), 'Login') or contains(@id, 'identifierId')]")
                
                if login_elements:
                    logger.warning("Login elements found - User not logged in")
                    return False
                else:
                    logger.info("No login elements found - User appears to be logged in")
                    return True
                    
            except Exception as e:
                logger.error(f"Error checking login elements: {e}")
                # If we can't find login elements but got this far, user might be logged in
                return True
            
        except Exception as e:
            logger.error(f"Error verifying Google login: {e}")
            return False

    def verify_meeting_link(self, meet_link):
        """Verify if the meeting link is valid and accessible"""
        try:
            self.driver.get(meet_link)
            time.sleep(3)  # Wait for page to load
            
            # Check for error messages
            error_messages = [
                "You can't create a meeting yourself",
                "Meeting code not found",
                "Invalid meeting code",
                "You don't have access to this video call",
                "Check your meeting code"
            ]
            
            for message in error_messages:
                if message.lower() in self.driver.page_source.lower():
                    logger.error(f"Meeting access error: {message}")
                    return False
                    
            # Check if we're on a valid Meet page
            if "meet.google.com" not in self.driver.current_url:
                logger.error("Not a valid Google Meet URL")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error verifying meeting link: {e}")
            return False

    def wait_for_join_completion(self, timeout=30):
        """Wait for join completion using MutationObserver"""
        script = """
        return new Promise((resolve) => {
            const observer = new MutationObserver((mutations) => {
                // Check if the join button is removed
                const joinButton = document.querySelector('button.UywwFc-LgbsSe');
                if (!joinButton) {
                    observer.disconnect();
                    resolve(true);
                }
            });
            
            observer.observe(document.body, {
                childList: true,
                subtree: true,
                attributes: true
            });
            
            // Set timeout
            setTimeout(() => {
                observer.disconnect();
                resolve(false);
            }, """ + str(timeout * 1000) + """);
        });
        """
        return self.driver.execute_script(script)

    def join_meeting(self, meet_link):
        """Join a Google Meet meeting"""
        try:
            logger.info(f"Attempting to join meeting: {meet_link}")
            
            # Extract meeting code from the link
            meeting_code = meet_link.split('/')[-1].split('?')[0]
            
            # First go to Google Calendar to access the meeting (more natural approach)
            self.driver.get('https://calendar.google.com')
            time.sleep(3)
            
            # Then go to the meeting through the proper channel
            meet_url = f"https://meet.google.com/{meeting_code}?authuser=0"
            self.driver.get(meet_url)
            time.sleep(5)
            
            # Wait for the pre-meeting screen to load
            logger.info("Waiting for pre-meeting screen...")
            time.sleep(3)
            
            # Try to handle camera and microphone permissions naturally
            try:
                # Look for and click the dismiss button for any permissions popup
                dismiss_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Dismiss')]")
                for button in dismiss_buttons:
                    try:
                        button.click()
                        time.sleep(1)
                    except:
                        pass
            except:
                pass

            # Handle camera and microphone more naturally
            media_buttons = self.driver.find_elements(By.XPATH, "//button[contains(@class, 'U26fgb')]")
            for button in media_buttons:
                try:
                    aria_label = button.get_attribute("aria-label") or ""
                    if "camera" in aria_label.lower() or "microphone" in aria_label.lower():
                        if "on" in aria_label.lower():
                            button.click()
                            time.sleep(1)
                except:
                    continue

            # Look for the join button with multiple selectors
            join_button_selectors = [
                "//button[contains(@class, 'VfPpkd-LgbsSe')]//span[contains(text(), 'Join now')]/ancestor::button",
                "//button[contains(@class, 'UywwFc-LgbsSe')]//span[contains(text(), 'Join now')]/ancestor::button",
                "//button[contains(@class, 'Jyj1Td')]//span[contains(text(), 'Join now')]/ancestor::button",
                "//button[contains(@data-id, 'join-now')]",
                "//button[contains(@aria-label, 'Join now')]"
            ]
            
            join_button = None
            for selector in join_button_selectors:
                try:
                    join_button = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    if join_button.is_displayed() and join_button.is_enabled():
                        break
                except:
                    continue

            if join_button:
                logger.info("Found join button, attempting to click...")
                
                # Try multiple methods to click the button
                try:
                    join_button.click()
                except:
                    try:
                        self.driver.execute_script("arguments[0].click();", join_button)
                    except:
                        actions = ActionChains(self.driver)
                        actions.move_to_element(join_button).click().perform()

                logger.info("Clicked join button, waiting for meeting to load...")
                
                # Wait for meeting to load
                try:
                    WebDriverWait(self.driver, 30).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[role='main'], [data-meeting-title]"))
                    )
                    logger.info("Successfully joined the meeting")
                    return True
                except:
                    logger.error("Failed to detect meeting load after clicking join button")
                    return False
            else:
                logger.error("Could not find join button")
                return False

        except Exception as e:
            logger.error(f"Error joining meeting: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def check_if_meeting_ended(self):
        """Check if the meeting has ended"""
        try:
            meeting_ended = self.driver.execute_script("return window.meetingHasEnded === true;")
            return meeting_ended
        except Exception as e:
            logger.error(f"Error checking meeting end status: {e}")
            return False

    def get_chrome_window_rect(self):
        """Get Chrome window position and size"""
        try:
            import win32gui
            import win32con
            
            def callback(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if "Meet - " in title:  # Chrome window with Meet
                        rect = win32gui.GetWindowRect(hwnd)
                        windows.append({
                            'hwnd': hwnd,
                            'rect': rect
                        })
            
            windows = []
            win32gui.EnumWindows(callback, windows)
            
            if windows:
                # Bring window to front
                win32gui.SetForegroundWindow(windows[0]['hwnd'])
                time.sleep(0.5)  # Wait for window to be brought to front
                return windows[0]['rect']
            return None
            
        except Exception as e:
            logger.error(f"Error getting Chrome window: {e}")
            return None

    def start_recording(self, meeting_url):
        """Start recording the meeting"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.recording = True
            
            # Create meeting-specific directories
            meeting_dir = os.path.join(RECORDING_DIR, f"{meeting_url}_{timestamp}")
            os.makedirs(meeting_dir, exist_ok=True)
            
            # Get screen dimensions
            screen = ImageGrab.grab()
            screen_width, screen_height = screen.size

            # Initialize video writer with proper codec and FPS
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            video_path = os.path.join(meeting_dir, "screen_recording.avi")
            self.video_writer = cv2.VideoWriter(
                video_path, 
                fourcc, 
                20.0, 
                (screen_width, screen_height),
                isColor=True
            )
            
            # Initialize audio recording
            audio_path = os.path.join(meeting_dir, "audio.wav")
            self.audio_file = audio_path
            
            # Initialize transcription file
            self.transcription_file = os.path.join(meeting_dir, "transcription.txt")
            with open(self.transcription_file, 'w', encoding='utf-8') as f:
                f.write("=== Meeting Transcription ===\n\n")
            
            # Enable captions in Meet
            self.enable_captions()
            
            # Wait for the main content to load with a more reliable selector
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='main'], [data-meeting-title]"))
            )
            
            # Enable captions
            try:
                captions_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(@aria-label, 'captions')]"))
                )
                captions_button.click()
                logger.info("Enabled captions in Meet")
            except TimeoutException:
                logger.warning("Captions button not found - may already be enabled")
            
            # Add meeting end detection
            script = """
            const observer = new MutationObserver((mutations) => {
                for (const mutation of mutations) {
                    const leftMeeting = document.querySelector('.roSPhc');
                    if (leftMeeting && leftMeeting.textContent.includes('You left the meeting')) {
                        window.dispatchEvent(new CustomEvent('meetingEnded'));
                        observer.disconnect();
                    }
                }
            });
            
            observer.observe(document.body, {
                childList: true,
                subtree: true
            });
            """
            self.driver.execute_script(script)
            
            # Add event listener for meeting end
            self.driver.execute_script("""
            window.addEventListener('meetingEnded', () => {
                window.meetingHasEnded = true;
            });
            """)
            
            # Set up connection pool limits
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[500, 502, 503, 504]
            )
            
            # Create a new connection pool with higher max retries and pool size
            pool = PoolManager(
                maxsize=5,  # Increase pool size
                retries=retry_strategy,
                timeout=5.0
            )
            
            # Attach pool to driver session
            self.driver.command_executor._conn = pool
            
            # Start recording threads
            self.screen_thread = threading.Thread(target=self.record_screen, args=(0, 0, screen_width, screen_height))
            self.audio_thread = threading.Thread(target=self.record_audio)
            self.caption_thread = threading.Thread(target=self.capture_captions)
            
            # Set threads as daemon threads so they stop when main thread stops
            self.screen_thread.daemon = True
            self.audio_thread.daemon = True
            self.caption_thread.daemon = True
            
            self.screen_thread.start()
            self.audio_thread.start()
            self.caption_thread.start()
            
            # Start recording loop with timeout
            max_duration = 3 * 60 * 60  # 3 hours in seconds
            start_time = time.time()
            
            while True:
                # Check for timeout
                if time.time() - start_time > max_duration:
                    logger.info("Maximum recording duration reached (3 hours)")
                    break
                    
                try:
                    # Check if meeting has ended
                    meeting_ended = self.driver.execute_script("""
                        return window.meetingHasEnded === true || 
                               document.querySelector('.roSPhc')?.textContent?.includes('You left the meeting') || 
                               false;
                    """)
                    
                    if meeting_ended:
                        logger.info("Meeting has ended, stopping recording")
                        break
                        
                    time.sleep(1)  # Check every second instead of continuous loop
                    
                except Exception as e:
                    logger.error(f"Error checking meeting status: {e}")
                    break  # Break the loop if we can't check meeting status
                    
            # Ensure recording stops
            self.stop_recording()
            
        except Exception as e:
            logger.error(f"Error in recording: {str(e)}")
            self.stop_recording()
            raise

    def enable_captions(self):
        """Enable captions in Google Meet"""
        try:
            # Try multiple possible caption button selectors
            caption_button_xpaths = [
                "//button[contains(@aria-label, 'captions') or contains(@aria-label, 'subtitle')]",
                "//button[@jsname='r8qRAd']",
                "//button[contains(@data-tooltip, 'captions')]",
                "//div[@role='button'][contains(., 'captions')]"
            ]
            
            for xpath in caption_button_xpaths:
                try:
                    caption_button = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, xpath))
                    )
                    if caption_button.is_displayed() and caption_button.is_enabled():
                        caption_button.click()
                        logger.info("Enabled captions in Meet")
                        time.sleep(2)  # Wait for captions to initialize
                        return
                except:
                    continue
                
            logger.warning("Could not find caption button - captions may already be enabled")
            
        except Exception as e:
            logger.error(f"Error enabling captions: {e}")

    def capture_captions(self):
        """Capture live captions from Google Meet"""
        try:
            # Set up caption observer with improved selector and handling
            script = """
            window.captionHistory = [];
            window.lastProcessedText = '';
            
            function processCaptions() {
                // Look for captions container with multiple possible selectors
                const containers = document.querySelectorAll('.a4cQT, .zs7s8d, .VR3bTd');
                
                containers.forEach(container => {
                    let speakerName = '';
                    let captionText = '';
                    
                    // Try different speaker name selectors
                    const speakerElem = container.querySelector('.M4LFnf, .YTbUzc');
                    if (speakerElem) {
                        speakerName = speakerElem.textContent.trim();
                    }
                    
                    // Try different caption text selectors
                    const textElem = container.querySelector('.VR3bTd, .CNusmb, .Pf3Ezf');
                    if (textElem) {
                        captionText = textElem.textContent.trim();
                    }
                    
                    // Only process if we have both speaker and text
                    if (speakerName && captionText && captionText !== window.lastProcessedText) {
                        const timestamp = new Date().toISOString();
                        const captionData = {
                            timestamp: timestamp,
                            speaker: speakerName,
                            text: captionText
                        };
                        
                        window.captionHistory.push(captionData);
                        window.lastProcessedText = captionText;
                        
                        // Dispatch event for new caption
                        window.dispatchEvent(new CustomEvent('newCaption', {
                            detail: captionData
                        }));
                    }
                });
            }
            
            // Create mutation observer
            window.captionObserver = new MutationObserver((mutations) => {
                processCaptions();
            });
            
            // Start observing with broader scope
            window.captionObserver.observe(document.body, {
                childList: true,
                subtree: true,
                characterData: true,
                characterDataOldValue: true
            });
            
            // Also set up periodic checking as backup
            window.captionInterval = setInterval(processCaptions, 1000);
            """
            
            self.driver.execute_script(script)
            logger.info("Caption observer initialized")
            
            # Process captions
            while self.recording:
                try:
                    # Get latest caption data
                    caption_data = self.driver.execute_script("""
                        const history = window.captionHistory || [];
                        return history[history.length - 1];
                    """)
                    
                    if caption_data and caption_data.get('text'):
                        # Format caption with timestamp and speaker
                        formatted_caption = (
                            f"[{caption_data['timestamp']}] "
                            f"{caption_data['speaker']}: {caption_data['text']}\n"
                        )
                        
                        # Write to file with proper encoding
                        try:
                            with open(self.transcription_file, 'a', encoding='utf-8') as f:
                                f.write(formatted_caption)
                                f.flush()  # Ensure it's written immediately
                            logger.debug(f"Captured caption: {formatted_caption.strip()}")
                        except Exception as e:
                            logger.error(f"Error writing caption to file: {e}")
                    
                    time.sleep(0.5)  # Check every 500ms
                    
                except Exception as e:
                    logger.error(f"Error processing caption: {e}")
                    time.sleep(1)  # Wait longer on error
                
        except Exception as e:
            logger.error(f"Error in caption capture: {e}")
        finally:
            # Clean up interval if it exists
            try:
                self.driver.execute_script("""
                    if (window.captionInterval) {
                        clearInterval(window.captionInterval);
                    }
                """)
            except:
                pass

    def record_screen(self, left, top, width, height):
        """Record screen content"""
        try:
            while self.recording:
                # Capture the entire screen
                screenshot = ImageGrab.grab(bbox=(left, top, width, height))
                frame = np.array(screenshot)
                
                # Convert from RGB to BGR (OpenCV format)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                # Write frame
                if frame.size > 0:
                    self.video_writer.write(frame)
                
                time.sleep(0.05)  # 20 FPS
                
        except Exception as e:
            logger.error(f"Error in screen recording: {e}")
            self.recording = False

    def record_audio(self):
        """Record system audio using PyAudio"""
        try:
            import pyaudio
            import wave
            import numpy as np
            from contextlib import contextmanager

            CHUNK = 1024
            FORMAT = pyaudio.paInt16
            CHANNELS = 2
            RATE = 44100

            # Create a context manager for PyAudio to ensure proper cleanup
            @contextmanager
            def audio_manager():
                p = pyaudio.PyAudio()
                try:
                    yield p
                finally:
                    p.terminate()

            with audio_manager() as p:
                # Find the system audio input device
                device_index = None
                info = None
                
                # First try to find Stereo Mix
                for i in range(p.get_device_count()):
                    try:
                        info = p.get_device_info_by_index(i)
                        if info['maxInputChannels'] > 0:
                            if 'Stereo Mix' in info['name'] or 'What U Hear' in info['name']:
                                device_index = i
                                break
                    except Exception:
                        continue

                # If no Stereo Mix, try to find any working input device
                if device_index is None:
                    for i in range(p.get_device_count()):
                        try:
                            info = p.get_device_info_by_index(i)
                            if info['maxInputChannels'] > 0:
                                test_stream = p.open(
                                    format=FORMAT,
                                    channels=CHANNELS,
                                    rate=RATE,
                                    input=True,
                                    input_device_index=i,
                                    frames_per_buffer=CHUNK,
                                    start=False
                                )
                                test_stream.close()
                                device_index = i
                                break
                        except Exception:
                            continue

                if device_index is None:
                    raise Exception("No working audio input device found")

                logger.info(f"Using audio device: {info['name']} (index: {device_index})")

                # Configure audio stream with larger buffer
                stream = p.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=CHUNK * 4,  # Increased buffer size
                    stream_callback=None
                )
            
            # Open wave file for writing
                with wave.open(self.audio_file, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(p.get_sample_size(FORMAT))
                    wf.setframerate(RATE)

                    logger.info("Started audio recording")
                    stream.start_stream()

            while self.recording:
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    if data:  # Only write if we got data
                        wf.writeframes(data)
                except IOError as e:
                    if e.errno == -9981:  # Buffer overflow
                        logger.warning("Audio buffer overflow - adjusting...")
                        time.sleep(0.1)  # Give the buffer time to clear
                        continue
                    else:
                        logger.error(f"Audio recording error: {e}")
                        break
                except Exception as e:
                    logger.error(f"Error reading audio chunk: {e}")
                    break

                    # Clean up stream
                    try:
                        stream.stop_stream()
                        stream.close()
                    except Exception as e:
                        logger.error(f"Error closing audio stream: {e}")

                logger.info("Audio recording completed")

        except Exception as e:
            logger.error(f"Error in audio recording: {e}")
            self.recording = False

    def stop_recording(self):
        """Stop all recording activities"""
        try:
            # Set recording flag to False first
            self.recording = False
            logger.info("Stopping recording - flag set to False")
            
            # Stop caption observer first
            try:
                if self.driver:
                    self.driver.execute_script("""
                        if (window.captionObserver) {
                            window.captionObserver.disconnect();
                            window.captionObserver = null;
                        }
                    """)
                    logger.info("Caption observer stopped")
            except Exception as e:
                logger.error(f"Error stopping caption observer: {e}")

            # Wait for threads with timeout
            threads = []
            if hasattr(self, 'screen_thread') and self.screen_thread:
                threads.append(('screen', self.screen_thread))
            if hasattr(self, 'audio_thread') and self.audio_thread:
                threads.append(('audio', self.audio_thread))
            if hasattr(self, 'caption_thread') and self.caption_thread:
                threads.append(('caption', self.caption_thread))

            # Join threads with timeout
            for name, thread in threads:
                try:
                    thread.join(timeout=5)  # 5 second timeout for each thread
                    if thread.is_alive():
                        logger.warning(f"{name} thread did not stop gracefully")
                except Exception as e:
                    logger.error(f"Error stopping {name} thread: {e}")

            # Release video writer
            try:
                if hasattr(self, 'video_writer') and self.video_writer:
                    self.video_writer.release()
                    logger.info("Video writer released")
            except Exception as e:
                logger.error(f"Error releasing video writer: {e}")

            # Close browser last
            try:
                if hasattr(self, 'driver') and self.driver:
                    self.driver.quit()
                    logger.info("Browser closed")
            except Exception as e:
                logger.error(f"Error closing browser: {e}")

        except Exception as e:
            logger.error(f"Error in stop_recording: {str(e)}")
        finally:
            # Reset all attributes
            self.recording = False
            self.video_writer = None
            self.driver = None
            self.screen_thread = None
            self.audio_thread = None
            self.caption_thread = None
            logger.info("Recording stopped and resources cleaned up")

    def leave_meeting(self):
        """Leave the current meeting"""
        try:
            self.stop_recording()
            self.driver.quit()
        except Exception as e:
            logger.error(f"Error leaving meeting: {e}")

    def __del__(self):
        """Cleanup resources"""
        if hasattr(self, 'driver'):
            self.driver.quit() 
