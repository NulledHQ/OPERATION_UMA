# src/core/ocr_worker.py
import io
import html
import logging
import os
import time
# Removed time import as sleep is removed
import threading
import base64
import requests
import json

# Import external libraries safely
try:
    import mss
except ImportError:
    logging.critical("Failed to import 'mss' library. Screen capture will not work. Run 'pip install mss'")
    mss = None
try:
    from PIL import Image
except ImportError:
    logging.critical("Failed to import 'Pillow' library. Image processing will not work. Run 'pip install Pillow'")
    Image = None

from PyQt5.QtCore import QObject, pyqtSignal # Keep pyqtSignal for existing signals

# Vision API import (Conditional)
try:
    from google.cloud import vision
    from google.oauth2 import service_account
    from google.api_core import exceptions as google_exceptions
except ImportError:
    logging.warning("Failed to import Google Cloud libraries (vision, oauth2, api_core). Google Cloud Vision OCR/Translate might be unavailable.")
    vision = None
    service_account = None
    google_exceptions = None


# --- Import engine(s) using absolute paths from src ---
try:
    from src.translation_engines.base_engine import TranslationEngine, TranslationError
    from src.translation_engines.google_cloud_v3_engine import GoogleCloudV3Engine
    from src.translation_engines.googletrans_engine import GoogletransEngine
    from src.translation_engines.deepl_free_engine import DeepLFreeEngine
except ImportError as e:
    logging.critical(f"Failed to import translation engine classes: {e}. Translation will not work.")
    TranslationEngine = object; TranslationError = Exception
    GoogleCloudV3Engine = None; GoogletransEngine = None; DeepLFreeEngine = None


# Import config using absolute path from src
from src import config

class OCRWorker(QObject):
    """
    Worker thread for performing screen capture, OCR, and translation.
    Uses a modular translation engine and now supports multiple OCR providers.
    Runs in a separate QThread.
    """
    finished = pyqtSignal(str, str) # Emits (ocr_text, translated_text)
    error = pyqtSignal(str)         # Emits error message string
    # <<< REMOVED aboutToCapture and captureFinished signals >>>

    # (__init__ remains the same as previous version, accepting ocr_language_code)
    def __init__(self, monitor, selected_ocr_provider, google_credentials_path, ocrspace_api_key,
                 ocr_language_code, target_language_code, # <<< Added ocr_language_code
                 history_data, selected_trans_engine_key, deepl_api_key=None):
        """
        Initializes the OCR Worker.
        Args:
            monitor (dict): Screen region details.
            selected_ocr_provider (str): Key for the chosen OCR provider.
            google_credentials_path (str): Path to Google Cloud credentials JSON.
            ocrspace_api_key (str): API key for OCR.space.
            ocr_language_code (str): Language code for OCR detection (e.g., 'eng', 'jpn'). <<< New
            target_language_code (str): ISO code for translation target.
            history_data (list): Snapshot of history for cache lookup.
            selected_trans_engine_key (str): Key for the chosen translation engine.
            deepl_api_key (str, optional): API key for DeepL translation.
        """
        super().__init__()
        # Store configuration passed from GUI thread
        self.monitor = monitor
        self.selected_ocr_provider = selected_ocr_provider
        self.google_credentials_path = google_credentials_path
        self.ocrspace_api_key = ocrspace_api_key
        self.ocr_language_code = ocr_language_code # <<< Store selected OCR language
        self.target_language_code = target_language_code # Target for translation
        self.history_data = history_data
        self.selected_trans_engine_key = selected_trans_engine_key
        self.deepl_api_key = deepl_api_key

        # --- OCR Client / Setup ---
        self.vision_credentials = None
        self.vision_client = None
        if self.selected_ocr_provider == "google_vision":
            self._initialize_vision_client()

        # --- Translation Engine ---
        self.translation_engine = None
        self._initialize_translation_engine()

        # --- History Cache ---
        self.history_lookup = {}
        self._build_history_lookup()

    # (_build_history_lookup, _initialize_vision_client, _initialize_translation_engine remain same)
    def _build_history_lookup(self):
        """Builds the history lookup dictionary from the snapshot data."""
        try:
            self.history_lookup = {
                entry[0]: entry[1] for entry in self.history_data
                if isinstance(entry, (list, tuple)) and len(entry) == 2 and
                   isinstance(entry[0], str) and isinstance(entry[1], str)
            }
            logging.debug(f"OCR Worker history lookup cache size: {len(self.history_lookup)}")
        except Exception as e:
            logging.error(f"Failed to create history lookup dictionary: {e}")
            self.history_lookup = {}

    def _initialize_vision_client(self):
        """Initialize Google Cloud Vision client."""
        # Check if library was imported
        if vision is None or service_account is None:
             logging.error("Vision Client: Cannot initialize, Google Cloud libraries missing.")
             self.vision_client = None
             return

        if not self.google_credentials_path:
             logging.error("Vision Client: Google Credentials path not set. OCR will fail.")
             self.vision_client = None
             return

        try:
            if not os.path.exists(self.google_credentials_path):
                 raise FileNotFoundError(f"Vision credentials file not found: {self.google_credentials_path}")

            self.vision_credentials = service_account.Credentials.from_service_account_file(self.google_credentials_path)
            self.vision_client = vision.ImageAnnotatorClient(credentials=self.vision_credentials)
            logging.info("Google Cloud Vision client initialized successfully.")

        except FileNotFoundError as e:
            logging.error(f"Vision client initialization failed: {e}")
            self.vision_client = None
        except Exception as e:
            logging.exception("Unexpected error initializing Google Cloud Vision client:")
            self.vision_client = None

    def _initialize_translation_engine(self):
        """Initializes the translation engine based on the selected_trans_engine_key."""
        engine_key = self.selected_trans_engine_key
        logging.info(f"Attempting to initialize translation engine: '{engine_key}'")

        # Prepare configuration dictionary for the engine
        engine_config = {
            'credentials_path': self.google_credentials_path, # Google Cloud V3 needs this
            'deepl_api_key': self.deepl_api_key
        }

        self.translation_engine = None # Reset before trying

        try:
            if engine_key == "google_cloud_v3":
                 if GoogleCloudV3Engine is None: logging.error("Cannot init Google Cloud V3 Translate: Class not loaded.")
                 elif not self.google_credentials_path: logging.error("Google Cloud V3 Translate engine requires credentials path.")
                 # Note: We don't strictly need vision_client for the *translation* engine itself
                 else: self.translation_engine = GoogleCloudV3Engine(config=engine_config)
            elif engine_key == "googletrans":
                 if GoogletransEngine is None: logging.error("Cannot init googletrans: Class not loaded.")
                 else: self.translation_engine = GoogletransEngine(config=engine_config)
            elif engine_key == "deepl_free":
                 if DeepLFreeEngine is None: logging.error("Cannot init DeepL: Class not loaded.")
                 elif not self.deepl_api_key: logging.error("DeepL engine requires an API Key.")
                 else: self.translation_engine = DeepLFreeEngine(config=engine_config)
            else:
                 logging.error(f"Unknown or unsupported translation engine key: '{engine_key}'")

            # --- Availability Check ---
            if self.translation_engine:
                if not self.translation_engine.is_available():
                     logging.error(f"Engine '{engine_key}' initialized but is_available() returned False.")
                     self.translation_engine = None # Mark as unavailable
                else:
                     logging.info(f"Translation engine '{engine_key}' initialized and available.")
            else:
                 logging.warning(f"Translation engine '{engine_key}' could not be initialized.")

        except Exception as e:
             logging.exception(f"Unexpected error initializing translation engine '{engine_key}':")
             self.translation_engine = None


    def run(self):
        """Performs the core screen capture, OCR, and translation task."""
        start_time = time.time()
        thread_name = threading.current_thread().name
        logging.debug(f"OCR Worker run() started in thread '{thread_name}'. Provider: {self.selected_ocr_provider}")

        # --- Check General Prerequisites ---
        if mss is None or Image is None:
             self.error.emit("OCR Error: Required libraries (mss, Pillow) missing.")
             return

        ocr_result = ""
        translated_text = ""
        img_buffer = None # To hold image data

        try:
            # 1. Capture Screen Region (Common step)
            # Uses the 'monitor' dictionary passed during __init__
            # This dictionary is now calculated in TranslucentBox.grab_text
            # to represent only the text_display area based on the old code.
            logging.debug(f"Attempting capture of region: {self.monitor}")

            # <<< REMOVED aboutToCapture signal and sleep >>>

            sct_img = None
            with mss.mss() as sct:
                # Use the pre-calculated monitor dictionary directly
                sct_img = sct.grab(self.monitor)

            # <<< REMOVED captureFinished signal >>>

            # Process the captured image
            if not sct_img or sct_img.width <= 0 or sct_img.height <= 0:
                # Check if the dimensions passed were invalid to begin with
                if self.monitor.get('width',0)<=0 or self.monitor.get('height',0)<=0:
                     raise mss.ScreenShotError(f"Invalid capture dimensions passed to worker: {self.monitor}")
                else:
                    raise mss.ScreenShotError("Failed to grab screen region (mss error).")

            # Keep image data in buffer for potential use by OCR providers
            img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
            img_buffer = io.BytesIO()
            img.save(img_buffer, format="PNG")
            img_content = img_buffer.getvalue() # Get bytes for Google Vision or requests
            img.close() # Close PIL image
            logging.debug(f"Screen capture successful ({sct_img.width}x{sct_img.height}).")

            # (Rest of OCR / Translation logic remains the same as previous version)
            # 2. OCR (Provider Specific)
            if self.selected_ocr_provider == "google_vision":
                # --- Google Cloud Vision OCR ---
                if vision is None:
                    raise Exception("Google Cloud Vision library not loaded.")
                if not self.vision_client:
                    raise Exception("Google Vision client not initialized. Check credentials.")

                logging.debug("Sending image to Google Cloud Vision API...")
                vision_image = vision.Image(content=img_content)
                response = self.vision_client.text_detection(image=vision_image)


                if response.error.message:
                    error_detail = f"Vision API Error: {response.error.message}"
                    if "CREDENTIALS_MISSING" in error_detail or "PERMISSION_DENIED" in error_detail:
                        error_detail = "Vision API Error: Check Google Cloud credentials/permissions."
                    raise Exception(error_detail)

                texts = response.text_annotations
                ocr_result = texts[0].description.strip() if texts else ""
                logging.debug(f"Google Vision OCR result received (Length: {len(ocr_result)}).")

            elif self.selected_ocr_provider == "ocr_space":
                # --- OCR.space OCR ---
                if not self.ocrspace_api_key:
                    raise Exception("OCR.space API Key not provided.")
                if not self.ocr_language_code:
                    logging.warning("OCR.space provider selected, but no OCR language chosen. Defaulting to 'eng'.")
                    ocr_lang = 'eng'
                else:
                     ocr_lang = self.ocr_language_code

                base64_image = base64.b64encode(img_content).decode('utf-8')

                payload = {
                    'apikey': self.ocrspace_api_key,
                    'language': ocr_lang,
                    'isOverlayRequired': False,
                    'base64Image': f'data:image/png;base64,{base64_image}',
                    'OCREngine': config.OCR_SPACE_DEFAULT_ENGINE
                }
                logging.debug(f"Sending image to OCR.space API (Lang: {ocr_lang}, Engine: {config.OCR_SPACE_DEFAULT_ENGINE})...")

                try:
                    response = requests.post(config.OCR_SPACE_API_URL, data=payload, timeout=30)
                    response.raise_for_status()
                    result = response.json()

                    if result.get("IsErroredOnProcessing"):
                         error_details = result.get("ErrorMessage", ["Unknown OCR.space Error"])[0]
                         raise Exception(f"OCR.space Error: {error_details}")

                    parsed_results = result.get("ParsedResults")
                    if parsed_results and len(parsed_results) > 0:
                         ocr_result = parsed_results[0].get("ParsedText", "").strip()
                    else:
                        if result.get("ErrorMessage"):
                             error_details = result.get("ErrorMessage", ["Unknown OCR.space issue"])[0]
                             logging.warning(f"OCR.space returned no results but message: {error_details}")
                             ocr_result = ""
                        else:
                             ocr_result = ""

                    logging.debug(f"OCR.space result received (Length: {len(ocr_result)}).")

                except requests.exceptions.RequestException as req_e:
                    logging.error(f"Network error contacting OCR.space: {req_e}")
                    raise Exception(f"Network Error: {req_e}") from req_e
                except json.JSONDecodeError as json_e:
                    logging.error(f"Error decoding OCR.space JSON response: {json_e}")
                    raise Exception("OCR Error: Invalid response format from OCR.space.") from json_e

            else:
                raise NotImplementedError(f"OCR provider '{self.selected_ocr_provider}' not implemented.")


            # 3. Translation (Conditional, common step)
            if not ocr_result:
                logging.info("OCR: No text detected.")
                translated_text = "" # Ensure empty if no OCR text
            else:
                cached_translation = self.history_lookup.get(ocr_result)
                if cached_translation is not None:
                    translated_text = cached_translation
                    logging.info(f"Translation cache hit for target '{self.target_language_code}'.")
                elif self.translation_engine:
                    engine_name = type(self.translation_engine).__name__
                    logging.debug(f"Cache miss. Calling {engine_name}.translate() for target '{self.target_language_code}'.")
                    try:
                        # Use the target language for translation
                        translated_text = self.translation_engine.translate(
                            text=ocr_result,
                            target_language_code=self.target_language_code
                        )
                        logging.debug(f"Translation result received from {engine_name}.")
                    except TranslationError as te:
                        logging.error(f"Translation failed using {engine_name}: {te}")
                        translated_text = f"[{engine_name} Error: {te}]" # Report specific error
                    except Exception as e:
                        logging.exception(f"Unexpected error calling {engine_name}.translate():")
                        translated_text = f"[Translation Error: Unexpected {type(e).__name__}]"
                else: # Translation engine not available/initialized
                     engine_display_name = config.AVAILABLE_ENGINES.get(self.selected_trans_engine_key, self.selected_trans_engine_key)
                     logging.warning(f"No translation engine available ('{engine_display_name}'). Skipping translation.")
                     if self.selected_trans_engine_key == 'deepl_free' and not self.deepl_api_key: translated_text = f"[{engine_display_name} Error: API Key Missing]"
                     elif self.selected_trans_engine_key == 'google_cloud_v3' and not self.google_credentials_path: translated_text = f"[{engine_display_name} Error: Credentials Missing]"
                     elif self.selected_trans_engine_key == 'googletrans' and GoogletransEngine is None: translated_text = f"[{engine_display_name} Error: Library Missing]"
                     elif self.selected_trans_engine_key == 'deepl_free' and DeepLFreeEngine is None: translated_text = f"[{engine_display_name} Error: Library Missing]"
                     else: translated_text = f"[{engine_display_name} Engine Unavailable]"

            # 4. Emit Results (Common step)
            final_ocr = str(ocr_result if ocr_result is not None else "")
            final_trans = str(translated_text if translated_text is not None else "")
            self.finished.emit(final_ocr, final_trans)
            logging.debug("Finished signal emitted.")

        except mss.ScreenShotError as e:
             # <<< REMOVED captureFinished.emit() >>>
             logging.error(f"Screen capture error: {e}")
             self.error.emit(f"Screen Capture Error: {e}")
        except Exception as e:
            # <<< REMOVED captureFinished.emit() >>>
            logging.exception("Unhandled error in OCR Worker run loop:")
            error_msg = str(e)
            if self.ocrspace_api_key and self.ocrspace_api_key in error_msg:
                error_msg = error_msg.replace(self.ocrspace_api_key, "****")
            self.error.emit(f"Worker Error: {error_msg}")
        finally:
            if img_buffer: img_buffer.close() # Clean up image buffer
            end_time = time.time()
            logging.debug(f"OCR Worker run() finished in thread '{thread_name}'. Duration: {end_time - start_time:.3f}s")