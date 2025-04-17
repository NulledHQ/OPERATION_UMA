# src/core/ocr_worker.py
import io
import html
import logging
import os
import time # Needed for timestamp in filename
import threading
import base64
import requests
import json
import random # Added for unique filename

# Import external libraries safely
try: import mss
except ImportError: logging.critical("Failed to import 'mss'. Screen capture won't work."); mss = None
try: from PIL import Image
except ImportError: logging.critical("Failed to import 'Pillow'. Image processing won't work."); Image = None
try: import pytesseract
except ImportError: logging.warning("Failed to import 'pytesseract'. Tesseract OCR unavailable."); pytesseract = None

from PyQt5.QtCore import QObject, pyqtSignal

# Vision API import
try: from google.cloud import vision; from google.oauth2 import service_account; from google.api_core import exceptions as google_exceptions
except ImportError: logging.warning("Google Cloud libs not found."); vision = None; service_account = None; google_exceptions = None

# --- Import engine(s) ---
try: from src.translation_engines.base_engine import TranslationEngine, TranslationError; from src.translation_engines.google_cloud_v3_engine import GoogleCloudV3Engine; from src.translation_engines.googletrans_engine import GoogletransEngine; from src.translation_engines.deepl_free_engine import DeepLFreeEngine
except ImportError as e: logging.critical(f"Failed to import translation engines: {e}."); TranslationEngine = object; TranslationError = Exception; GoogleCloudV3Engine = None; GoogletransEngine = None; DeepLFreeEngine = None

from src import config

class OCRWorker(QObject):
    finished = pyqtSignal(str, str) # ocr_text, translated_text
    error = pyqtSignal(str)         # error_message

    def __init__(self, monitor, selected_ocr_provider, google_credentials_path,
                 ocrspace_api_key, ocr_language_code, target_language_code,
                 history_data, selected_trans_engine_key, deepl_api_key=None,
                 ocr_space_engine=config.DEFAULT_OCR_SPACE_ENGINE_NUMBER,
                 ocr_space_scale=config.DEFAULT_OCR_SPACE_SCALE,
                 ocr_space_detect_orientation=config.DEFAULT_OCR_SPACE_DETECT_ORIENTATION,
                 tesseract_cmd_path=config.DEFAULT_TESSERACT_CMD_PATH,
                 tesseract_language_code=config.DEFAULT_TESSERACT_LANGUAGE,
                 save_ocr_images=config.DEFAULT_SAVE_OCR_IMAGES,
                 ocr_image_save_path=config.DEFAULT_OCR_IMAGE_SAVE_PATH,
                 ):
        super().__init__()
        # Store configuration
        self.monitor = monitor
        self.selected_ocr_provider = selected_ocr_provider
        self.google_credentials_path = google_credentials_path
        self.ocrspace_api_key = ocrspace_api_key
        self.ocr_language_code = ocr_language_code
        self.target_language_code = target_language_code
        self.history_data = history_data
        self.selected_trans_engine_key = selected_trans_engine_key
        self.deepl_api_key = deepl_api_key
        # Store OCR.space specific
        self.ocr_space_engine = ocr_space_engine
        self.ocr_space_scale = ocr_space_scale
        self.ocr_space_detect_orientation = ocr_space_detect_orientation
        # Store Tesseract specific
        self.tesseract_cmd_path = tesseract_cmd_path
        self.tesseract_language_code = tesseract_language_code
        # Store Training Data Settings
        self.save_ocr_images = save_ocr_images
        self.ocr_image_save_path = ocr_image_save_path

        # OCR Client / Setup
        self.vision_client = None
        self._initialize_vision_client() # Call init method
        # Translation Engine
        self.translation_engine = None
        self._initialize_translation_engine() # Call init method
        # History Cache
        self.history_lookup = {}
        self._build_history_lookup() # Call init method

    def _build_history_lookup(self):
        try:
            self.history_lookup = {
                e[0]: e[1] for e in self.history_data
                if isinstance(e, (list, tuple)) and len(e) == 2 and isinstance(e[0], str) and isinstance(e[1], str)
            }
            logging.debug(f"History lookup cache size: {len(self.history_lookup)}")
        except Exception as e:
            logging.error(f"Failed to create history lookup: {e}")
            self.history_lookup = {}

    def _initialize_vision_client(self):
        if self.selected_ocr_provider != "google_vision":
            return # Don't init if not selected
        if vision is None or service_account is None:
            logging.error("Vision Client: Google Cloud libraries missing.")
            return
        if not self.google_credentials_path:
            logging.error("Vision Client: Credentials path not set.")
            return
        try:
            if not os.path.exists(self.google_credentials_path):
                raise FileNotFoundError(f"Vision credentials not found: {self.google_credentials_path}")
            creds = service_account.Credentials.from_service_account_file(self.google_credentials_path)
            self.vision_client = vision.ImageAnnotatorClient(credentials=creds)
            logging.info("Google Vision client initialized.")
        except Exception as e:
            logging.exception("Error initializing Google Vision client:")
            self.vision_client = None # Ensure client is None on failure

    def _initialize_translation_engine(self):
        engine_key = self.selected_trans_engine_key
        logging.info(f"Initializing translation engine: '{engine_key}'")
        cfg = { 'credentials_path': self.google_credentials_path, 'deepl_api_key': self.deepl_api_key }
        eng = None
        try:
            if engine_key == "google_cloud_v3": eng = GoogleCloudV3Engine(config=cfg) if GoogleCloudV3Engine else None
            elif engine_key == "googletrans": eng = GoogletransEngine(config=cfg) if GoogletransEngine else None
            elif engine_key == "deepl_free": eng = DeepLFreeEngine(config=cfg) if DeepLFreeEngine else None
            else: logging.error(f"Unknown translation engine key: '{engine_key}'")

            if eng and eng.is_available():
                self.translation_engine = eng
                logging.info(f"Translation engine '{engine_key}' available.")
            else:
                self.translation_engine = None # Ensure it's None if unavailable
                logging.warning(f"Translation engine '{engine_key}' could not be initialized or is unavailable.")
        except Exception as e:
            logging.exception(f"Error initializing translation engine '{engine_key}':")
            self.translation_engine = None


    def run(self):
        start_time = time.time()
        thread_name = threading.current_thread().name
        logging.debug(f"OCR Worker run() started. Provider: {self.selected_ocr_provider}")

        if mss is None or Image is None:
            self.error.emit("OCR Error: Required libraries missing.")
            return

        ocr_result = ""
        translated_text = ""
        img_buffer = None
        pil_image = None
        image_saved_path = None # Store path if image is saved

        try:
            # 1. Capture Screen Region
            logging.debug(f"Attempting capture: {self.monitor}")
            sct_img = None
            with mss.mss() as sct:
                sct_img = sct.grab(self.monitor)

            if not sct_img or sct_img.width <= 0 or sct_img.height <= 0:
                raise mss.ScreenShotError("Failed to grab screen region.")

            pil_image = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
            img_buffer = io.BytesIO()
            pil_image.save(img_buffer, format="PNG")
            img_content = img_buffer.getvalue()
            logging.debug(f"Screen capture successful ({sct_img.width}x{sct_img.height}).")

            # --- Save Image If Enabled ---
            # Generate filename here so it can be used for .gt.txt later
            image_base_filename = None
            if self.save_ocr_images and self.ocr_image_save_path and pil_image:
                try:
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    # Create base filename without extension
                    image_base_filename = f"ocr_capture_{timestamp}_{random.randint(100,999)}"
                    image_filename = f"{image_base_filename}.png"
                    save_full_path = os.path.join(self.ocr_image_save_path, image_filename)
                    os.makedirs(self.ocr_image_save_path, exist_ok=True)
                    pil_image.save(save_full_path, "PNG")
                    image_saved_path = save_full_path # Store the path
                    logging.info(f"Saved captured image to: {save_full_path}")
                except OSError as save_e:
                    logging.error(f"Failed to save image to '{self.ocr_image_save_path}': {save_e}")
                    image_base_filename = None # Reset if save failed
                    image_saved_path = None
                except Exception as e:
                    logging.exception("Unexpected error saving image:")
                    image_base_filename = None
                    image_saved_path = None
            # --- End Save Image ---

            # 2. OCR (Provider Specific)
            if self.selected_ocr_provider == "google_vision":
                if not self.vision_client:
                    raise Exception("Google Vision client not initialized.")
                logging.debug("Sending image to Google Cloud Vision API...")
                vision_image = vision.Image(content=img_content)
                response = self.vision_client.text_detection(image=vision_image)
                if response.error.message:
                    raise Exception(f"Vision API Error: {response.error.message}")
                texts = response.text_annotations
                ocr_result = texts[0].description.strip() if texts else ""
                logging.debug(f"Google Vision result len: {len(ocr_result)}.")

                # --- NEW: Save Google Vision output as .gt.txt if image was saved ---
                if image_base_filename and self.ocr_image_save_path:
                    try:
                        gt_filename = f"{image_base_filename}.gt.txt"
                        gt_full_path = os.path.join(self.ocr_image_save_path, gt_filename)
                        with open(gt_full_path, 'w', encoding='utf-8') as f:
                            f.write(ocr_result)
                        logging.info(f"Saved Google Vision OCR output to: {gt_full_path}")
                    except OSError as gt_save_e:
                        logging.error(f"Failed to save ground truth file '{gt_full_path}': {gt_save_e}")
                    except Exception as e:
                        logging.exception(f"Unexpected error saving ground truth file:")
                # --- End Save Google Vision output ---


            elif self.selected_ocr_provider == "ocr_space":
                # (Logic remains the same - doesn't save .gt.txt automatically)
                if not self.ocrspace_api_key: raise Exception("OCR.space API Key missing.")
                ocr_lang = self.ocr_language_code or 'eng'
                base64_image = base64.b64encode(img_content).decode('utf-8')
                payload = {'apikey': self.ocrspace_api_key, 'language': ocr_lang, 'isOverlayRequired': False, 'base64Image': f'data:image/png;base64,{base64_image}',
                           'OCREngine': self.ocr_space_engine, 'scale': str(self.ocr_space_scale).lower(), 'detectOrientation': str(self.ocr_space_detect_orientation).lower()}
                logging.debug(f"Sending to OCR.space (Lang:{ocr_lang}, Eng:{payload.get('OCREngine')}, Scale:{payload.get('scale')})...")
                try:
                    response = requests.post(config.OCR_SPACE_API_URL, data=payload, timeout=30); response.raise_for_status(); result = response.json()
                    if result.get("IsErroredOnProcessing"): raise Exception(f"OCR.space Error: {result.get('ErrorMessage', ['Unknown'])[0]}")
                    parsed_results = result.get("ParsedResults"); ocr_result = parsed_results[0].get("ParsedText", "").strip() if parsed_results else ""; logging.debug(f"OCR.space result len: {len(ocr_result)}.")
                except requests.exceptions.RequestException as e: raise Exception(f"Network Error: {e}") from e
                except json.JSONDecodeError as e: raise Exception("OCR Error: Invalid response format.") from e

            elif self.selected_ocr_provider == "tesseract":
                 # (Logic remains the same - doesn't save .gt.txt automatically)
                if pytesseract is None: raise Exception("Tesseract (pytesseract) library not available.")
                if not self.tesseract_language_code: raise Exception("Tesseract language not specified.")
                tess_lang = self.tesseract_language_code; logging.debug(f"Performing Tesseract OCR (Lang: {tess_lang})...")
                try:
                    if self.tesseract_cmd_path and os.path.exists(self.tesseract_cmd_path): pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd_path; logging.debug(f"Using Tesseract path: {self.tesseract_cmd_path}")
                    ocr_result = pytesseract.image_to_string(pil_image, lang=tess_lang).strip(); logging.debug(f"Tesseract result len: {len(ocr_result)}.")
                except pytesseract.TesseractNotFoundError: raise Exception("Tesseract Error: Executable not found.")
                except Exception as e: raise Exception(f"Tesseract Error: {e}") from e

            else:
                raise NotImplementedError(f"OCR provider '{self.selected_ocr_provider}' not implemented.")


            # 3. Translation (Conditional)
            if not ocr_result:
                logging.info("OCR: No text detected.")
                translated_text = ""
            else:
                cached = self.history_lookup.get(ocr_result)
                if cached is not None:
                    translated_text = cached
                    logging.info(f"Translation cache hit for '{self.target_language_code}'.")
                elif self.translation_engine:
                    engine_name = type(self.translation_engine).__name__
                    logging.debug(f"Cache miss. Calling {engine_name}.translate()...")
                    try:
                        translated_text = self.translation_engine.translate(text=ocr_result, target_language_code=self.target_language_code)
                    except TranslationError as e:
                        logging.error(f"Translation failed: {e}")
                        translated_text = f"[{engine_name} Error: {e}]"
                    except Exception as e:
                        logging.exception("Unexpected translation error:")
                        translated_text = "[Translation Error]"
                else:
                    engine_key = self.selected_trans_engine_key
                    translated_text = f"[{config.AVAILABLE_ENGINES.get(engine_key, engine_key)} Unavailable]"

            # 4. Emit Results
            self.finished.emit(str(ocr_result or ""), str(translated_text or ""))
            logging.debug("Finished signal emitted.")

        except mss.ScreenShotError as e:
            logging.error(f"Screen capture error: {e}")
            self.error.emit(f"Capture Error: {e}")
        except Exception as e:
            logging.exception("Unhandled error in OCR Worker:")
            error_msg = str(e)
            # Mask key if present
            if self.ocrspace_api_key and self.ocrspace_api_key in error_msg:
                error_msg = error_msg.replace(self.ocrspace_api_key, "****")
            self.error.emit(f"Worker Error: {error_msg}")
        finally:
            # Clean up resources
            if pil_image:
                pil_image.close()
            if img_buffer:
                img_buffer.close()
            end_time = time.time()
            logging.debug(f"OCR Worker run() finished. Duration: {end_time - start_time:.3f}s")