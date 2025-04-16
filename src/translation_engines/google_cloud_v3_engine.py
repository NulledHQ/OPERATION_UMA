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
    Requires Google Cloud credentials. Includes explicit language detection.
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
        """
        Translates text using Google Translate API v3.
        Detects source language automatically if not provided.
        """
        if not self.is_available():
             reason = "required libraries missing" if translate is None else "client initialization failed (check credentials?)"
             raise TranslationError(f"Google Cloud V3 Engine not available ({reason}).")
        if not target_language_code: raise ValueError("Target language code cannot be empty.")
        if not text: return "" # Nothing to translate

        detected_source_code = None # Variable to store detected language

        try:
            # --- Step 1: Detect Source Language (if not provided) ---
            if not source_language_code:
                logging.debug(f"Requesting Google V3 language detection for text: '{text[:50]}...'")
                detect_request = {
                    "parent": self.parent_path,
                    "content": text,
                    "mime_type": "text/plain" # Or "text/html" if applicable
                }
                detect_response = self.client.detect_language(request=detect_request)

                if detect_response.languages:
                    # Sort by confidence or take the first one (usually most confident)
                    detected_source_code = detect_response.languages[0].language_code
                    confidence = detect_response.languages[0].confidence
                    logging.debug(f"Google V3 detected source language: '{detected_source_code}' (Confidence: {confidence:.2f})")
                else:
                    logging.warning("Google V3 could not detect source language reliably.")
                    # Optionally, fallback to a default source or raise an error
                    # For now, we proceed and let translate_text try auto-detect
                    # raise TranslationError("Could not detect source language.")
            else:
                logging.debug(f"Using provided source language code: '{source_language_code}'")
                detected_source_code = source_language_code # Use the provided one

            # --- Step 2: Translate Text ---
            translate_request = {
                "parent": self.parent_path,
                "contents": [text],
                "mime_type": "text/plain", # Or "text/html"
                "target_language_code": target_language_code,
            }
            # Use the detected (or provided) source language code
            if detected_source_code:
                 translate_request["source_language_code"] = detected_source_code
                 log_src = detected_source_code
            else:
                 # Fallback to auto-detect if detection failed but we didn't raise error
                 log_src = 'auto'

            logging.debug(f"Requesting Google V3 translation: target='{target_language_code}', source='{log_src}'")
            translate_response = self.client.translate_text(request=translate_request)

            if not translate_response.translations:
                raise TranslationError("Translation failed: No result from Google V3 API.")

            result = translate_response.translations[0]
            translated = html.unescape(result.translated_text) # API might return HTML entities
            # Log the source language actually used by the translation step
            final_detected_src = result.detected_language_code or detected_source_code or 'unknown'
            logging.debug(f"Google V3 translated (Detected/Used Src: {final_detected_src}): '{text[:50]}...' -> '{translated[:50]}...'")
            return translated

        except google_exceptions.InvalidArgument as e:
             logging.error(f"Google Cloud V3 Engine: Invalid argument - {e}")
             # Check if it's a language code error
             if "language code" in str(e).lower():
                  invalid_code = target_language_code if target_language_code in str(e) else (detected_source_code or source_language_code or 'unknown')
                  raise TranslationError(f"Invalid language code ('{invalid_code}').") from e
             else:
                  raise TranslationError(f"Invalid argument: {e.message}") from e
        except google_exceptions.PermissionDenied as e:
            logging.error(f"Google Cloud V3 Engine: Permission denied - {e}")
            raise TranslationError("Permission denied. Check API key/credentials and API enablement.") from e
        except google_exceptions.NotFound as e:
            logging.error(f"Google Cloud V3 Engine: Not Found - {e}")
            raise TranslationError(f"API endpoint or resource not found: {e.message}") from e
        except google_exceptions.GoogleAPIError as e:
             # Catch-all for other Google API errors
             logging.exception(f"Google Cloud V3 Engine: API error during operation:")
             raise TranslationError(f"Google API Error: {e.message}") from e
        except Exception as e:
             # Catch unexpected non-Google errors
             logging.exception(f"Google Cloud V3 Engine: Unexpected error:")
             raise TranslationError(f"Unexpected Error: {type(e).__name__}") from e