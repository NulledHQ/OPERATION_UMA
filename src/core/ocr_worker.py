# src/core/ocr_worker.py
import io
import html
import logging
import os
import time # Keep for potential timing later
import threading # To get thread name for logging

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

from PyQt5.QtCore import QObject, pyqtSignal

# Vision API import
try:
    from google.cloud import vision
    from google.oauth2 import service_account
    from google.api_core import exceptions as google_exceptions
except ImportError:
    logging.critical("Failed to import Google Cloud libraries (vision, oauth2, api_core). OCR/Google Translate will not work.")
    vision = None
    service_account = None
    google_exceptions = None


# --- Import engine(s) using absolute paths from src ---
try:
    # Import base class first
    from src.translation_engines.base_engine import TranslationEngine, TranslationError
    # Import specific engine classes
    from src.translation_engines.google_cloud_v3_engine import GoogleCloudV3Engine
    from src.translation_engines.googletrans_engine import GoogletransEngine
    from src.translation_engines.deepl_free_engine import DeepLFreeEngine
except ImportError as e:
    logging.critical(f"Failed to import translation engine classes: {e}. Translation will not work.")
    # Define dummies to prevent NameErrors later
    TranslationEngine = object
    TranslationError = Exception
    GoogleCloudV3Engine = None
    GoogletransEngine = None
    DeepLFreeEngine = None


# Import config using absolute path from src
from src import config

class OCRWorker(QObject):
    """
    Worker thread for performing screen capture, OCR, and translation.
    Uses a modular translation engine.
    Runs in a separate QThread.
    """
    finished = pyqtSignal(str, str) # Emits (ocr_text, translated_text)
    error = pyqtSignal(str)         # Emits error message string

    def __init__(self, monitor, credentials_path, target_language_code, history_data, selected_engine_key, deepl_api_key=None):
        """
        Initializes the OCR Worker. See gui.py for Args details.
        """
        super().__init__()
        # Store configuration passed from GUI thread
        self.monitor = monitor
        self.credentials_path = credentials_path # Google Cloud credentials (required for Vision OCR)
        self.target_language_code = target_language_code
        self.history_data = history_data # Snapshot of history for cache lookup
        self.selected_engine_key = selected_engine_key
        self.deepl_api_key = deepl_api_key # Store the DeepL key

        # --- Vision API Client ---
        self.vision_credentials = None
        self.vision_client = None
        self._initialize_vision_client() # Attempt initialization immediately

        # --- Translation Engine ---
        self.translation_engine = None
        self._initialize_translation_engine() # Attempt initialization immediately

        # --- History Cache ---
        self.history_lookup = {} # Initialize empty
        self._build_history_lookup()

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
            self.history_lookup = {} # Ensure it's an empty dict on error


    def _initialize_vision_client(self):
        """Initialize Google Cloud Vision client using the credentials path."""
        # Check if library was imported
        if vision is None or service_account is None:
             logging.error("Vision Client: Cannot initialize, Google Cloud libraries missing.")
             self.vision_client = None
             return

        if not self.credentials_path:
             logging.error("Vision Client: Google Credentials path not set. OCR will fail.")
             self.vision_client = None
             return

        try:
            if not os.path.exists(self.credentials_path):
                 raise FileNotFoundError(f"Vision credentials file not found: {self.credentials_path}")

            self.vision_credentials = service_account.Credentials.from_service_account_file(self.credentials_path)
            self.vision_client = vision.ImageAnnotatorClient(credentials=self.vision_credentials)
            logging.info("Google Cloud Vision client initialized successfully.")

        except FileNotFoundError as e:
            logging.error(f"Vision client initialization failed: {e}")
            self.vision_client = None
        except Exception as e:
            logging.exception("Unexpected error initializing Google Cloud Vision client:")
            self.vision_client = None


    def _initialize_translation_engine(self):
        """Initializes the translation engine based on the selected_engine_key."""
        engine_key = self.selected_engine_key
        logging.info(f"Attempting to initialize translation engine: '{engine_key}'")

        # Prepare configuration dictionary for the engine
        engine_config = {
            'credentials_path': self.credentials_path, # For Google Cloud engine
            'deepl_api_key': self.deepl_api_key        # For DeepL engine
        }

        self.translation_engine = None # Reset before trying

        try:
            # --- Engine Selection Logic ---
            if engine_key == "google_cloud_v3":
                 if GoogleCloudV3Engine is None: logging.error("Cannot init Google Cloud V3: Class not loaded.")
                 elif not self.credentials_path: logging.error("Google Cloud V3 engine requires credentials path.")
                 elif not self.vision_client: logging.error("Google Cloud V3 requires successful Vision client init.")
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
        """Performs the core OCR and translation task."""
        start_time = time.time()
        thread_name = threading.current_thread().name
        logging.debug(f"OCR Worker run() started in thread '{thread_name}'.")

        # --- Check Prerequisites ---
        if mss is None or Image is None:
             self.error.emit("OCR Error: Required libraries (mss, Pillow) missing.")
             return
        if vision is None:
            self.error.emit("OCR Error: Google Cloud Vision library missing.")
            return
        if not self.vision_client:
            self.error.emit("OCR Error: Vision client failed. Check Google credentials.")
            return

        ocr_result = ""
        translated_text = ""

        try:
            # 1. Capture Screen Region
            logging.debug(f"Capturing screen region: {self.monitor}")
            with mss.mss() as sct:
                monitor_mss = {k.lower(): v for k, v in self.monitor.items()}
                sct_img = sct.grab(monitor_mss)
                if not sct_img or sct_img.width <= 0 or sct_img.height <= 0:
                    if self.monitor.get('width',0)<=0 or self.monitor.get('height',0)<=0:
                         raise mss.ScreenShotError(f"Invalid capture dimensions: {self.monitor.get('width')}x{self.monitor.get('height')}")
                    else: raise mss.ScreenShotError("Failed to grab screen region (mss error).")

                img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
                logging.debug(f"Screen capture successful ({img.width}x{img.height}).")

            buffer = io.BytesIO()
            img.save(buffer, format="PNG"); content = buffer.getvalue()
            img.close(); buffer.close()

            # 2. OCR using Google Cloud Vision
            logging.debug("Sending image to Google Cloud Vision API...")
            vision_image = vision.Image(content=content)
            response = self.vision_client.text_detection(image=vision_image)

            if response.error.message:
                error_detail = f"Vision API Error: {response.error.message}"
                if "CREDENTIALS_MISSING" in error_detail or "PERMISSION_DENIED" in error_detail:
                    error_detail = "Vision API Error: Check Google Cloud credentials/permissions."
                raise Exception(error_detail)

            texts = response.text_annotations
            ocr_result = texts[0].description.strip() if texts else ""
            if not ocr_result: logging.info("OCR: No text detected.")
            else: logging.debug(f"OCR result received (Length: {len(ocr_result)}).")

            # 3. Translation (Conditional)
            if ocr_result:
                cached_translation = self.history_lookup.get(ocr_result)
                if cached_translation is not None:
                    translated_text = cached_translation
                    logging.info(f"Translation cache hit for target '{self.target_language_code}'.")
                elif self.translation_engine:
                    engine_name = type(self.translation_engine).__name__
                    logging.debug(f"Cache miss. Calling {engine_name}.translate() for target '{self.target_language_code}'.")
                    try:
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
                else: # Engine not available
                     engine_display_name = config.AVAILABLE_ENGINES.get(self.selected_engine_key, self.selected_engine_key)
                     logging.warning(f"No translation engine available ('{engine_display_name}'). Skipping translation.")
                     # Provide specific feedback if possible
                     if self.selected_engine_key == 'deepl_free' and not self.deepl_api_key: translated_text = f"[{engine_display_name} Error: API Key Missing]"
                     elif self.selected_engine_key == 'google_cloud_v3' and not self.credentials_path: translated_text = f"[{engine_display_name} Error: Credentials Missing]"
                     elif self.selected_engine_key == 'googletrans' and GoogletransEngine is None: translated_text = f"[{engine_display_name} Error: Library Missing]"
                     elif self.selected_engine_key == 'deepl_free' and DeepLFreeEngine is None: translated_text = f"[{engine_display_name} Error: Library Missing]"
                     else: translated_text = f"[{engine_display_name} Engine Unavailable]"

            # 4. Emit Results
            final_ocr = str(ocr_result if ocr_result is not None else "")
            final_trans = str(translated_text if translated_text is not None else "")
            self.finished.emit(final_ocr, final_trans)
            logging.debug("Finished signal emitted.")

        except mss.ScreenShotError as e:
             logging.error(f"Screen capture error: {e}")
             self.error.emit(f"Screen Capture Error: {e}")
        except Exception as e:
            logging.exception("Unhandled error in OCR Worker run loop:")
            self.error.emit(f"Worker Error: {str(e)}")
        finally:
            end_time = time.time()
            logging.debug(f"OCR Worker run() finished in thread '{thread_name}'. Duration: {end_time - start_time:.3f}s")