# filename: src/core/translation_worker.py
import logging
import time
import threading

from PyQt5.QtCore import QObject, pyqtSignal

# --- Import engine(s) using absolute paths from src ---
try:
    from src.translation_engines.base_engine import TranslationEngine, TranslationError
    from src.translation_engines.google_cloud_v3_engine import GoogleCloudV3Engine
    from src.translation_engines.googletrans_engine import GoogletransEngine
    from src.translation_engines.deepl_free_engine import DeepLFreeEngine
except ImportError as e:
    logging.critical(f"TranslationWorker: Failed to import engine classes: {e}")
    TranslationEngine = object; TranslationError = Exception
    GoogleCloudV3Engine = None; GoogletransEngine = None; DeepLFreeEngine = None

# Import config using absolute path from src
from src import config

class TranslationWorker(QObject):
    """
    Worker thread for performing only translation on existing text.
    Runs in a separate QThread.
    """
    # Emits (original_text, translated_text)
    finished = pyqtSignal(str, str)
    # Emits error message string
    error = pyqtSignal(str)

    def __init__(self, text_to_translate, target_language_code,
                 selected_trans_engine_key, google_credentials_path=None, deepl_api_key=None):
        """
        Initializes the Translation Worker.
        Args:
            text_to_translate (str): The text to be translated.
            target_language_code (str): ISO code for translation target.
            selected_trans_engine_key (str): Key for the chosen translation engine.
            google_credentials_path (str, optional): Path to Google Cloud credentials JSON.
            deepl_api_key (str, optional): API key for DeepL translation.
        """
        super().__init__()
        self.text_to_translate = text_to_translate
        self.target_language_code = target_language_code
        self.selected_trans_engine_key = selected_trans_engine_key
        self.google_credentials_path = google_credentials_path
        self.deepl_api_key = deepl_api_key

        # --- Translation Engine ---
        self.translation_engine = None
        self._initialize_translation_engine()

    def _initialize_translation_engine(self):
        """Initializes the translation engine based on the selected_trans_engine_key."""
        engine_key = self.selected_trans_engine_key
        logging.info(f"TranslationWorker: Initializing engine: '{engine_key}'")
        engine_config = {
            'credentials_path': self.google_credentials_path,
            'deepl_api_key': self.deepl_api_key
        }
        self.translation_engine = None
        try:
            if engine_key == "google_cloud_v3":
                 if GoogleCloudV3Engine: self.translation_engine = GoogleCloudV3Engine(config=engine_config)
                 else: logging.error("Cannot init Google Cloud V3 Translate: Class not loaded.")
            elif engine_key == "googletrans":
                 if GoogletransEngine: self.translation_engine = GoogletransEngine(config=engine_config)
                 else: logging.error("Cannot init googletrans: Class not loaded.")
            elif engine_key == "deepl_free":
                 if DeepLFreeEngine: self.translation_engine = DeepLFreeEngine(config=engine_config)
                 else: logging.error("Cannot init DeepL: Class not loaded.")
            else:
                 logging.error(f"Unknown translation engine key: '{engine_key}'")

            if self.translation_engine:
                if not self.translation_engine.is_available():
                     logging.error(f"Engine '{engine_key}' initialized but unavailable.")
                     self.translation_engine = None
                else:
                     logging.info(f"Translation engine '{engine_key}' initialized and available.")
            else:
                 logging.warning(f"Translation engine '{engine_key}' could not be initialized.")
        except Exception as e:
             logging.exception(f"Error initializing translation engine '{engine_key}':")
             self.translation_engine = None

    def run(self):
        """Performs the translation task."""
        start_time = time.time()
        thread_name = threading.current_thread().name
        logging.debug(f"TranslationWorker run() started in thread '{thread_name}'. Target: {self.target_language_code}")

        translated_text = ""

        try:
            if not self.text_to_translate:
                logging.info("TranslationWorker: No text provided to translate.")
                translated_text = ""
            elif not self.translation_engine:
                engine_display_name = config.AVAILABLE_ENGINES.get(self.selected_trans_engine_key, self.selected_trans_engine_key)
                logging.warning(f"TranslationWorker: No translation engine available ('{engine_display_name}').")
                raise TranslationError(f"{engine_display_name} Engine Unavailable")
            else:
                engine_name = type(self.translation_engine).__name__
                logging.debug(f"TranslationWorker: Calling {engine_name}.translate() for target '{self.target_language_code}'.")
                try:
                    translated_text = self.translation_engine.translate(
                        text=self.text_to_translate,
                        target_language_code=self.target_language_code
                        # Assuming source language auto-detection or not needed
                    )
                    logging.debug(f"TranslationWorker: Result received from {engine_name}.")
                except TranslationError as te:
                    logging.error(f"TranslationWorker: Translation failed using {engine_name}: {te}")
                    # Emit specific error signal instead of raising exception here
                    self.error.emit(f"Re-translate Error [{engine_name}]: {te}")
                    return # Stop processing on error
                except Exception as e:
                    logging.exception(f"TranslationWorker: Unexpected error calling {engine_name}.translate():")
                    self.error.emit(f"Re-translate Error: Unexpected {type(e).__name__}")
                    return # Stop processing on error

            # Emit Results
            # Pass original text back so the receiver knows what was translated
            self.finished.emit(self.text_to_translate, str(translated_text if translated_text is not None else ""))
            logging.debug("TranslationWorker: Finished signal emitted.")

        except Exception as e:
            logging.exception("TranslationWorker: Unhandled error in run loop:")
            self.error.emit(f"Worker Error: {e}")
        finally:
            end_time = time.time()
            logging.debug(f"TranslationWorker run() finished. Duration: {end_time - start_time:.3f}s")