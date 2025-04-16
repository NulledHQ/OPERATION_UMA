# src/translation_engines/google_cloud_v3_engine.py
import logging
import os
import html

# Import Google libraries safely
try:
    from google.cloud import translate_v3 as translate # Use v3 alias
    from google.oauth2 import service_account
    from google.api_core import exceptions as google_exceptions
except ImportError:
    logging.critical("Failed to import Google Cloud libraries (translate, oauth2, api_core). Google Cloud V3 engine unavailable. Run 'pip install google-cloud-translate google-auth google-api-core'")
    translate = None
    service_account = None
    google_exceptions = None

# Use absolute import from src package root
from src.translation_engines.base_engine import TranslationEngine, TranslationError

class GoogleCloudV3Engine(TranslationEngine):
    """
    Translation engine using the official Google Cloud Translation API v3.
    Requires Google Cloud credentials.
    """
    REQUIRED_CONFIG_KEYS = ['credentials_path']

    def __init__(self, config=None):
        """
        Initializes the Google Cloud V3 engine. See ocr_worker.py for Args details.
        """
        super().__init__(config)
        self.config = config or {}
        self.credentials_path = self.config.get('credentials_path')
        self.credentials = None
        self.client = None
        self.project_id = None
        self.parent_path = None # For API calls

        # Check if libraries were imported
        if translate is None or service_account is None or google_exceptions is None:
             logging.error("Google Cloud V3 Engine: Cannot initialize, required libraries missing.")
             return # Stop initialization

        if not self.credentials_path:
            logging.error("Google Cloud V3 Engine: 'credentials_path' missing in config.")
            return

        self._initialize_client()

    def _initialize_client(self):
        """Initialize Google Cloud client using credentials."""
        try:
            if not os.path.exists(self.credentials_path):
                 raise FileNotFoundError(f"Credentials file not found: {self.credentials_path}")

            self.credentials = service_account.Credentials.from_service_account_file(self.credentials_path)
            self.project_id = self.credentials.project_id
            if not self.project_id:
                 raise ValueError("Could not determine project ID from credentials file.")

            # location = "global" # Or specific region if needed, e.g., "us-central1"
            location = "global"
            self.client = translate.TranslationServiceClient(credentials=self.credentials)
            self.parent_path = f"projects/{self.project_id}/locations/{location}"
            logging.info(f"Google Cloud V3 Translation client initialized for project '{self.project_id}' (location: {location}).")

        except FileNotFoundError as e:
            logging.error(f"Google Cloud V3 Engine: {e}")
            self.client = None
        except ValueError as e:
             logging.error(f"Google Cloud V3 Engine: Error reading credentials - {e}")
             self.client = None
        except Exception as e:
            logging.exception("Google Cloud V3 Engine: Error initializing client:")
            self.client = None

    def is_available(self) -> bool:
        """Check if the client was initialized successfully and libraries loaded."""
        return (translate is not None and
                service_account is not None and
                google_exceptions is not None and
                self.client is not None and
                self.parent_path is not None)

    def translate(self, text: str, target_language_code: str, source_language_code: str = None) -> str:
        """Translates text using Google Translate API v3."""
        if not self.is_available():
             reason = "required libraries missing" if translate is None else "client initialization failed (check credentials?)"
             raise TranslationError(f"Google Cloud V3 Engine not available ({reason}).")
        if not target_language_code: raise ValueError("Target language code cannot be empty.")
        if not text: return "" # Nothing to translate

        try:
            request = {
                "parent": self.parent_path,
                "contents": [text],
                "mime_type": "text/plain", # Or "text/html"
                "target_language_code": target_language_code,
            }
            if source_language_code:
                 request["source_language_code"] = source_language_code
                 log_src = source_language_code
            else: log_src = 'auto' # For logging

            logging.debug(f"Requesting Google V3 translation: target='{target_language_code}', source='{log_src}'")
            response = self.client.translate_text(request=request)

            if not response.translations:
                raise TranslationError("Translation failed: No result from Google V3 API.")

            result = response.translations[0]
            translated = html.unescape(result.translated_text) # API might return HTML entities
            detected_src = result.detected_language_code or 'unknown'
            logging.debug(f"Google V3 translated (Detected: {detected_src}): '{text[:50]}...' -> '{translated[:50]}...'")
            return translated

        except google_exceptions.InvalidArgument as e:
             logging.error(f"Google Cloud V3 Engine: Invalid argument - {e}")
             # Check if it's a language code error
             if "language code" in str(e).lower():
                  raise TranslationError(f"Invalid language code ('{target_language_code}' or source '{source_language_code}').") from e
             else:
                  raise TranslationError(f"Invalid argument: {e.message}") from e
        except google_exceptions.PermissionDenied as e:
            logging.error(f"Google Cloud V3 Engine: Permission denied - {e}")
            raise TranslationError("Permission denied. Check API key/credentials and API enablement.") from e
        except google_exceptions.GoogleAPIError as e:
             logging.exception(f"Google Cloud V3 Engine: API error during translation:")
             raise TranslationError(f"Google API Error: {e.message}") from e
        except Exception as e:
             logging.exception(f"Google Cloud V3 Engine: Unexpected error during translation:")
             raise TranslationError(f"Unexpected Error: {type(e).__name__}") from e