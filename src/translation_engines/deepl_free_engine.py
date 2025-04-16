# src/translation_engines/deepl_free_engine.py
import logging
import os
import html
try:
    import deepl # Official DeepL library
except ImportError:
     logging.critical("Failed to import 'deepl' library. DeepL engine unavailable. Run 'pip install deepl'")
     deepl = None

# Use absolute import from src package root
from src.translation_engines.base_engine import TranslationEngine, TranslationError

class DeepLFreeEngine(TranslationEngine):
    """
    Translation engine using the official DeepL API (Free or Pro).
    Requires an API key.
    """
    REQUIRED_CONFIG_KEYS = ['deepl_api_key'] # Define required key

    def __init__(self, config=None):
        """
        Initializes the DeepL engine. See ocr_worker.py for Args details.
        """
        super().__init__(config)
        self.config = config or {}
        self.api_key = self.config.get('deepl_api_key')
        self.translator = None

        # Check if library imported successfully
        if deepl is None:
             logging.error("DeepL Engine: Cannot initialize, library not imported.")
             return # Stop initialization

        if not self.api_key:
            logging.error("DeepL Engine: 'deepl_api_key' missing in config.")
            return

        self._initialize_client()

    def _initialize_client(self):
        """Initialize DeepL client using the API key."""
        try:
            self.translator = deepl.Translator(self.api_key)
            usage = self.translator.get_usage() # Verify authentication
            if usage.character and usage.character.limit_reached:
                 logging.warning("DeepL API character usage limit reached.")
            logging.info("DeepL Translator client initialized successfully.")
        except deepl.AuthorizationException as e:
             logging.error(f"DeepL Engine: Authorization Error (invalid API key?): {e}")
             self.translator = None
        except deepl.DeepLException as e:
             logging.error(f"DeepL Engine: Error initializing client: {e}")
             self.translator = None
        except Exception as e:
            logging.exception("DeepL Engine: Unexpected error initializing client:")
            self.translator = None

    def is_available(self) -> bool:
        """Check if the translator was initialized successfully."""
        # Also check if library was loaded
        return deepl is not None and self.translator is not None

    def translate(self, text: str, target_language_code: str, source_language_code: str = None) -> str:
        """Translates text using the DeepL API."""
        if not self.is_available():
            reason = "library missing" if deepl is None else "initialization failed (check API key?)"
            raise TranslationError(f"DeepL Engine not available ({reason}).")
        if not target_language_code: raise ValueError("Target language code cannot be empty.")
        if not text: return "" # Nothing to translate

        # --- DeepL Language Code Handling ---
        target_dl = target_language_code.upper(); source_dl = source_language_code.upper() if source_language_code else None
        if target_dl == 'EN': target_dl = 'EN-US'
        if target_dl == 'PT': target_dl = 'PT-PT'
        if target_dl in ['ZH-CN', 'ZH-TW']: target_dl = 'ZH'
        if source_dl == 'EN': source_dl = 'EN'
        if source_dl == 'PT': source_dl = 'PT'
        if source_dl in ['ZH-CN', 'ZH-TW']: source_dl = 'ZH'
        # --- End Language Code Handling ---

        try:
            logging.debug(f"Requesting DeepL translation: target='{target_dl}', source='{source_dl or 'auto'}'")
            result = self.translator.translate_text(text, source_lang=source_dl, target_lang=target_dl)
            if result and result.text:
                translated = html.unescape(result.text)
                detected_src = str(result.detected_source_lang or 'unknown')
                logging.debug(f"DeepL translated (Detected: {detected_src}): '{text[:50]}...' -> '{translated[:50]}...'")
                return translated
            else: raise TranslationError("No text result from DeepL API.")
        except deepl.QuotaExceededException as e: raise TranslationError("DeepL API quota exceeded.") from e
        except deepl.AuthorizationException as e: raise TranslationError("DeepL API authorization failed.") from e
        except deepl.ConnectionException as e: raise TranslationError("Network error connecting to DeepL.") from e
        except deepl.DeepLException as e:
             err_str = str(e)
             if "Target language not supported" in err_str: raise TranslationError(f"DeepL unsupported target: {target_dl}") from e
             elif "Source language not supported" in err_str: raise TranslationError(f"DeepL unsupported source: {source_dl}") from e
             raise TranslationError(f"DeepL API Error: {e}") from e
        except Exception as e:
             logging.exception(f"DeepL Engine: Unexpected error during translation:")
             raise TranslationError(f"Unexpected Error: {type(e).__name__}") from e