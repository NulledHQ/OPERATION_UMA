# src/translation_engines/googletrans_engine.py
import logging
import html
try:
    # Try importing from the recommended version first
    from googletrans import Translator, LANGUAGES
except ImportError:
    # Fallback or log an error if the library isn't installed correctly
    logging.critical("Failed to import 'googletrans' library. Googletrans engine unavailable. Run 'pip install googletrans==4.0.0rc1'")
    Translator = None
    LANGUAGES = {}

# Use absolute import from src package root
from src.translation_engines.base_engine import TranslationEngine, TranslationError

class GoogletransEngine(TranslationEngine):
    """
    Translation engine using the unofficial googletrans library.
    Note: This library relies on web scraping Google Translate and might be unstable.
    """
    def __init__(self, config=None):
        """
        Initializes the Googletrans engine. See ocr_worker.py for Args details.
        """
        super().__init__(config)
        self.config = config or {}
        self.translator = None

        if Translator is None:
             logging.error("GoogletransEngine cannot initialize: Translator class not imported.")
             return

        try:
            self.translator = Translator()
            # Attempt a dummy translation to check connectivity/availability early
            self.translator.translate("test", dest="en")
            logging.info("Googletrans engine initialized successfully.")
        except Exception as e:
            logging.exception("GoogletransEngine: Error initializing Translator instance:")
            self.translator = None # Ensure it's None if init fails

    def is_available(self) -> bool:
        """Check if the translator instance was initialized successfully."""
        # Also check if library was loaded
        return Translator is not None and self.translator is not None

    def translate(self, text: str, target_language_code: str, source_language_code: str = None) -> str:
        """Translates text using the googletrans library."""
        if not self.is_available():
            reason = "library missing" if Translator is None else "initialization failed"
            raise TranslationError(f"Googletrans engine not available ({reason}).")
        if not target_language_code: raise ValueError("Target language code cannot be empty.")
        if not text: return ""

        src_lang = source_language_code.lower() if source_language_code else 'auto'
        target_lang_lower = target_language_code.lower()

        # --- Corrected Validation ---
        if LANGUAGES and target_lang_lower not in LANGUAGES and target_lang_lower not in ['zh-cn', 'zh-tw']:
             logging.error(f"GoogletransEngine: Invalid target language code '{target_language_code}'.")
             raise ValueError(f"Invalid target language code for googletrans: {target_language_code}")
        elif not LANGUAGES: logging.warning("GoogletransEngine: LANGUAGES dict not available for validation.")
        # --- End Corrected Validation ---

        try:
            logging.debug(f"Requesting googletrans translation: target='{target_lang_lower}', source='{src_lang}'")
            result = self.translator.translate(text, dest=target_lang_lower, src=src_lang)
            if result and result.text:
                translated = html.unescape(result.text)
                detected_src = result.src.lower() if result.src else 'unknown'
                logging.debug(f"Googletrans translated (Detected: {detected_src}): '{text[:50]}...' -> '{translated[:50]}...'")
                return translated
            else: raise TranslationError("No valid result from googletrans (blocked/API change?).")
        except AttributeError as ae:
             logging.exception(f"GoogletransEngine: Attribute error (translator not initialized?): {ae}")
             raise TranslationError("Googletrans engine not properly initialized.") from ae
        except Exception as e:
            logging.exception(f"GoogletransEngine: Error during translation: {e}")
            error_msg = str(e) if str(e) else f"Unexpected {type(e).__name__}"
            if "JSONDecodeError" in error_msg or "Networkerror" in error_msg or "'NoneType' object is not callable" in error_msg:
                 error_msg += " (Check network or if Google Translate API changed/blocked)"
            raise TranslationError(f"googletrans Error: {error_msg}") from e