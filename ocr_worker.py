# ocr_worker.py
import io
import html
import logging
import os # Needed for basename
import time # For timing cache check if needed

import mss
from PIL import Image
from PyQt5.QtCore import QObject, pyqtSignal
from google.cloud import vision, translate
from google.oauth2 import service_account

import config # Import configuration

class OCRWorker(QObject):
    finished = pyqtSignal(str, str)  # Emit both OCR text and translated text
    error = pyqtSignal(str)

    # Accept history_data in constructor
    def __init__(self, monitor, credentials_path, target_language_code, history_data):
        super().__init__()
        self.monitor = monitor
        self.credentials_path = credentials_path
        self.target_language_code = target_language_code # Store target language
        self.credentials = None
        self.vision_client = None
        self.translate_client = None
        self.project_id = None

        # --- History Cache ---
        # Create a lookup dictionary from the history (most recent entry wins for duplicates)
        # Assumes history_data is an iterable of (ocr_text, translated_text) tuples/lists
        try:
            self.history_lookup = {entry[0]: entry[1] for entry in history_data if isinstance(entry, (list, tuple)) and len(entry) == 2 and isinstance(entry[0], str) and isinstance(entry[1], str)}
            logging.debug(f"OCR Worker initialized with history lookup cache size: {len(self.history_lookup)}")
        except Exception as e:
            logging.error(f"Failed to create history lookup: {e}")
            self.history_lookup = {} # Ensure it's an empty dict on error
        # --- End History Cache ---


    def _initialize_clients(self):
        """Initialize Google Cloud clients using credentials."""
        try:
            # Check if path exists before trying to load
            if not self.credentials_path or not os.path.exists(self.credentials_path):
                 raise FileNotFoundError("Credentials path not set or file does not exist.")

            self.credentials = service_account.Credentials.from_service_account_file(self.credentials_path)
            self.project_id = self.credentials.project_id
            self.vision_client = vision.ImageAnnotatorClient(credentials=self.credentials)
            self.translate_client = translate.TranslationServiceClient(credentials=self.credentials)
            logging.debug("Google Cloud clients initialized successfully.")
            return True
        except FileNotFoundError:
            # Show only filename if path is set, otherwise generic message
            err_msg = f"Credentials file not found: {os.path.basename(self.credentials_path)}" if self.credentials_path else "Credentials file not set."
            logging.error(f"Credentials file error: {err_msg} (Path: {self.credentials_path})")
            self.error.emit(err_msg)
            return False
        except Exception as e:
            logging.exception("Error initializing Google Cloud clients:")
            self.error.emit(f"Client Initialization Error: {e}")
            return False

    def run(self):
        """Performs screen capture, OCR, checks history cache, and translates."""
        if not self._initialize_clients():
            # Error signal already emitted in _initialize_clients
            return

        try:
            # 1. Capture Screen Region
            logging.debug(f"Capturing screen region: {self.monitor}")
            with mss.mss() as sct:
                screenshot = sct.grab(self.monitor)
                # Check if capture was successful
                if not screenshot or screenshot.width <= 0 or screenshot.height <= 0:
                    raise mss.ScreenShotError(f"Failed to grab screen region or region was empty ({screenshot.width}x{screenshot.height}).")
                img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            content = buffer.getvalue()
            logging.debug("Screen capture successful.")

            # 2. OCR
            logging.debug("Sending image to Google Cloud Vision API...")
            image = vision.Image(content=content)
            response = self.vision_client.text_detection(image=image)

            if response.error.message:
                raise Exception(f"Vision API error: {response.error.message}")

            texts = response.text_annotations
            ocr_result = texts[0].description.strip() if texts else "No text detected."
            logging.debug(f"OCR result received (length: {len(ocr_result)}).")


            # 3. Translation (with Cache Check)
            translated_text = "[No translation performed]" # Default message
            cache_hit = False
            # Only attempt translation/cache lookup if OCR found text
            if ocr_result and ocr_result != "No text detected.":
                # --- Check History Cache ---
                # Use .get() for safer lookup in case key isn't string? Unlikely here.
                cached_translation = self.history_lookup.get(ocr_result)
                if cached_translation is not None:
                    translated_text = cached_translation
                    cache_hit = True
                    logging.info(f"Translation cache hit for target '{self.target_language_code}'. Using cached result.")
                # --- End Cache Check ---
                else:
                    # If not in cache, call the API
                    logging.debug(f"Translation cache miss. Calling Translate API for target '{self.target_language_code}'.")
                    translated_text = self.translate_text_v3(ocr_result, self.target_language_code)
                    logging.debug("Translation result received from API.")

            elif ocr_result == "No text detected.":
                 translated_text = "" # No text -> empty translation
            else:
                 # Handle empty ocr_result case explicitly
                 translated_text = "[OCR result was empty]"


            self.finished.emit(ocr_result, translated_text)

        except mss.ScreenShotError as e:
             logging.exception("Screen capture error:")
             self.error.emit(f"Screen Capture Error: {e}")
        except Exception as e:
            # Catch potential errors during image processing or API interaction
            logging.exception("OCR/Translation Worker error:")
            self.error.emit(f"Worker Error: {str(e)}")


    # Modified translate_text_v3 accepts target_language_code
    def translate_text_v3(self, text, target_language_code):
        """Translates text using Google Translate API v3, detecting source language."""
        if not text: # Should not happen if called after check, but safeguard
            return ""
        if not self.translate_client or not self.project_id:
             logging.error("Translate client or project ID not initialized.")
             return "[Translation Error: Client not ready]"

        parent = f"projects/{self.project_id}/locations/global"

        try:
            # Step 1: Detect source language
            detect_response = self.translate_client.detect_language(
                request={ "parent": parent, "content": text, "mime_type": "text/plain"}
            )

            detected_language = "und" # Default if detection fails
            if detect_response.languages:
                # Find the most confident detection
                best_guess = max(detect_response.languages, key=lambda lang: lang.confidence)
                detected_language = best_guess.language_code
                logging.debug(f"Detected source language: {detected_language} (Confidence: {best_guess.confidence:.2f})")
            else:
                 logging.warning("Could not detect source language.")

            # Step 2: Translate only if source is different from target
            # Also translate if source is undetermined ('und') - let Google handle it
            if detected_language == target_language_code and detected_language != "und":
                 logging.debug(f"Source language '{detected_language}' is the same as target. No translation needed.")
                 return text # Return original text

            translate_response = self.translate_client.translate_text(
                request={
                    "parent": parent,
                    "contents": [text],
                    "mime_type": "text/plain",
                    # Explicitly pass detected source OR None if undetermined
                    "source_language_code": detected_language if detected_language != "und" else None,
                    "target_language_code": target_language_code, # Use the passed target language
                }
            )

            if not translate_response.translations:
                logging.error("Translation API returned no translations.")
                return "[Translation Failed: No result from API]"

            # Return only the translated text
            translated_text = html.unescape(translate_response.translations[0].translated_text)
            return translated_text

        except Exception as e:
            logging.exception("Error during translation:")
            # Provide a slightly more user-friendly error format
            return f"[Translation Error: {type(e).__name__}]"