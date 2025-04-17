# filename: src/gui/handlers/ocr_handler.py
import logging
import html
import os

from PyQt5.QtCore import QObject, pyqtSignal, QThread, pyqtSlot, QRect
from PyQt5.QtWidgets import QApplication, QMessageBox

# Core components
from src.core.ocr_worker import OCRWorker
from src.core.translation_worker import TranslationWorker
try:
    from src import config
except ImportError:
    logging.error("OcrHandler: Failed to import config.")
    class Cfg: # Define fallback class
        AVAILABLE_OCR_PROVIDERS={}
        AVAILABLE_ENGINES={}
    config = Cfg() # Assign instance


class OcrHandler(QObject):
    """Handles the OCR/Translation workflow, worker thread management, and state."""
    ocrCompleted = pyqtSignal(str, str) # ocr_text, translated_text
    ocrError = pyqtSignal(str)         # error_message
    stateChanged = pyqtSignal(bool)    # True if OCR started, False if finished/error
    retranslationCompleted = pyqtSignal(str, str) # original_text, new_translation
    retranslationError = pyqtSignal(str)        # error_message

    def __init__(self, window, history_manager, settings_state_handler):
        super().__init__(window)
        self.window = window
        self.history_manager = history_manager
        self.settings_state_handler = settings_state_handler
        self.ui_manager = getattr(window, 'ui_manager', None)
        if not self.ui_manager:
            logging.error("OcrHandler: Could not get ui_manager from window.")
        self.ocr_running = False
        self.thread = None
        self.worker = None
        self.translation_thread = None
        self.translation_worker = None
        self.last_ocr_text = ""

    def trigger_ocr(self):
        """Checks prerequisites and starts the OCRWorker thread."""
        if self.ocr_running:
            logging.warning("OCR already running.")
            return
        if not self.check_prerequisites(prompt_if_needed=True):
            logging.warning("OCR cancelled: Prerequisite check failed.")
            return

        self.ocr_running = True
        self.stateChanged.emit(True)
        logging.debug("OcrHandler starting OCR worker...")

        if not self.ui_manager:
            self._handle_internal_error("Internal Error: UI Manager missing.")
            return

        # Hide text display for capture
        self.ui_manager.set_text_display_visibility(False)
        QApplication.processEvents()

        try: # Calculate capture region
            geo = self.window.geometry()
            content_rect = self.ui_manager.get_text_display_geometry()
            if not geo.isValid() or not content_rect.isValid():
                raise ValueError("Invalid geometry.")
            monitor = {
                "top": geo.top()+content_rect.top(),
                "left": geo.left()+content_rect.left(),
                "width": content_rect.width(),
                "height": content_rect.height()
            }
            if monitor["width"] <= 0 or monitor["height"] <= 0:
                raise ValueError(f"Invalid capture dimensions: {monitor}")
            logging.debug(f"OcrHandler calculated monitor region: {monitor}")
        except Exception as e:
            self._handle_internal_error(f"Capture Region Error: {e}")
            return

        # Get current settings for the worker
        history_snapshot = self.history_manager.get_history_list() if self.history_manager else []
        try:
            ocr_provider = self.settings_state_handler.get_value('ocr_provider')
            google_cred = self.settings_state_handler.get_value('google_credentials_path')
            ocrspace_key = self.settings_state_handler.get_value('ocrspace_api_key')
            ocr_lang = self.settings_state_handler.get_value('ocr_language_code') # OCR.space lang
            target_lang = self.settings_state_handler.get_value('target_language_code')
            trans_engine = self.settings_state_handler.get_value('translation_engine_key')
            deepl_key = self.settings_state_handler.get_value('deepl_api_key')
            ocr_space_engine = self.settings_state_handler.get_value('ocr_space_engine')
            ocr_space_scale = self.settings_state_handler.get_value('ocr_space_scale')
            ocr_space_detect_orientation = self.settings_state_handler.get_value('ocr_space_detect_orientation')
            tesseract_cmd_path = self.settings_state_handler.get_value('tesseract_cmd_path')
            tesseract_language_code = self.settings_state_handler.get_value('tesseract_language_code')
            save_ocr_images = self.settings_state_handler.get_value('save_ocr_images')
            ocr_image_save_path = self.settings_state_handler.get_value('ocr_image_save_path')

            if not all([ocr_provider, target_lang, trans_engine]): # Removed ocr_lang check as Tesseract doesn't always need it upfront
                raise ValueError("Essential settings missing (provider, target lang, trans engine).")
        except Exception as e:
            self._handle_internal_error(f"Config Error: {e}")
            return

        # Setup and start worker thread
        self.thread = QThread(self.window)
        self.worker = OCRWorker(
            monitor=monitor,
            selected_ocr_provider=ocr_provider,
            google_credentials_path=google_cred,
            ocrspace_api_key=ocrspace_key,
            ocr_language_code=ocr_lang,
            target_language_code=target_lang,
            history_data=history_snapshot,
            selected_trans_engine_key=trans_engine,
            deepl_api_key=deepl_key,
            ocr_space_engine=ocr_space_engine,
            ocr_space_scale=ocr_space_scale,
            ocr_space_detect_orientation=ocr_space_detect_orientation,
            tesseract_cmd_path=tesseract_cmd_path,
            tesseract_language_code=tesseract_language_code,
            save_ocr_images=save_ocr_images,
            ocr_image_save_path=ocr_image_save_path,
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_worker_done)
        self.worker.error.connect(self._on_worker_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self._on_thread_finished)
        self.thread.start()
        logging.debug("OCR worker thread started by OcrHandler.")


    @pyqtSlot(str, str)
    def _on_worker_done(self, ocr_text, translated_text):
        """Handles successful OCR result from the worker."""
        logging.debug("OcrHandler received finished signal from OCR worker.")
        if ocr_text:
            self.last_ocr_text = ocr_text
            logging.debug(f"Stored last OCR text len: {len(self.last_ocr_text)}.")
        else:
            logging.debug("Current OCR empty, retaining previous last_ocr_text.")
        self.ocrCompleted.emit(ocr_text, translated_text)

    @pyqtSlot(str)
    def _on_worker_error(self, error_msg):
        """Handles error signal from the worker."""
        logging.debug(f"OcrHandler received error signal from OCR worker: {error_msg}")
        self.ocrError.emit(error_msg)

    @pyqtSlot()
    def _on_thread_finished(self):
        """Cleans up OCR worker thread references and updates state."""
        logging.debug("OcrHandler notified OCR worker thread finished.")
        self._reset_state_and_emit(False)

    # --- Retranslation Methods ---
    def get_last_ocr_text(self) -> str:
        return self.last_ocr_text

    def request_retranslation(self, new_target_language_code: str) -> bool:
        """Starts a TranslationWorker to re-translate the last OCR text."""
        if not self.last_ocr_text:
            self.retranslationError.emit("No text captured previously.")
            return False
        if self.translation_thread and self.translation_thread.isRunning():
            self.retranslationError.emit("Translation already in progress.")
            return False
        logging.info(f"Requesting re-translation to '{new_target_language_code}'.")
        try:
            trans_engine = self.settings_state_handler.get_value('translation_engine_key')
            google_cred = self.settings_state_handler.get_value('google_credentials_path')
            deepl_key = self.settings_state_handler.get_value('deepl_api_key')
            if not trans_engine:
                raise ValueError("Translation engine key missing.")
        except Exception as e:
            self.retranslationError.emit(f"Config Error: {e}")
            return False

        self.translation_thread = QThread(self.window)
        self.translation_worker = TranslationWorker(
            text_to_translate=self.last_ocr_text,
            target_language_code=new_target_language_code,
            selected_trans_engine_key=trans_engine,
            google_credentials_path=google_cred,
            deepl_api_key=deepl_key
        )
        self.translation_worker.moveToThread(self.translation_thread)
        self.translation_thread.started.connect(self.translation_worker.run)
        self.translation_worker.finished.connect(self._on_translation_worker_done)
        self.translation_worker.error.connect(self._on_translation_worker_error)
        self.translation_worker.finished.connect(self.translation_thread.quit)
        self.translation_worker.error.connect(self.translation_thread.quit)
        self.translation_worker.finished.connect(self.translation_worker.deleteLater)
        self.translation_worker.error.connect(self.translation_worker.deleteLater)
        self.translation_thread.finished.connect(self.translation_thread.deleteLater)
        self.translation_thread.finished.connect(self._on_translation_thread_finished)
        self.translation_thread.start()
        logging.debug("Translation worker thread started.")
        return True


    @pyqtSlot(str, str)
    def _on_translation_worker_done(self, original_text, new_translation):
        logging.debug("OcrHandler received finished signal from TranslationWorker.")
        self.retranslationCompleted.emit(original_text, new_translation)

    @pyqtSlot(str)
    def _on_translation_worker_error(self, error_msg):
        logging.debug(f"OcrHandler received error signal from TranslationWorker: {error_msg}")
        self.retranslationError.emit(error_msg)

    @pyqtSlot()
    def _on_translation_thread_finished(self):
        logging.debug("OcrHandler notified translation worker thread finished.")
        self.translation_thread = None
        self.translation_worker = None

    # --- Other methods ---
    def _reset_state_and_emit(self, is_running: bool):
        """Resets worker/thread references and emits state change."""
        self.ocr_running = is_running
        self.thread = None
        self.worker = None
        # Don't manage UI visibility here, let the main window do it
        self.stateChanged.emit(is_running)

    def _handle_internal_error(self, error_msg):
         """Handles internal errors, emits signal, resets state."""
         logging.error(f"OcrHandler internal error: {error_msg}")
         self.ocrError.emit(error_msg)
         self._reset_state_and_emit(False)

    def check_prerequisites(self, prompt_if_needed=False) -> bool:
        """Checks if prerequisites for selected OCR and Translation are met."""
        if not self.settings_state_handler:
            logging.error("Cannot check prereqs: SettingsStateHandler missing.")
            return False
        try: # Get settings/flags
            ocr_provider=self.settings_state_handler.get_value('ocr_provider')
            trans_engine_key=self.settings_state_handler.get_value('translation_engine_key')
            is_google_valid=self.settings_state_handler.is_google_credentials_valid()
            is_ocrspace_set=self.settings_state_handler.is_ocrspace_key_set()
            is_deepl_set=self.settings_state_handler.is_deepl_key_set()
        except Exception as e:
            logging.error(f"Error getting settings/flags: {e}")
            return False

        ocr_prereqs_met = False
        trans_prereqs_met = False
        missing = []
        ocr_provider_name = config.AVAILABLE_OCR_PROVIDERS.get(ocr_provider, ocr_provider)
        trans_engine_name = config.AVAILABLE_ENGINES.get(trans_engine_key, trans_engine_key)

        # Check OCR Prereqs
        if ocr_provider == "google_vision":
            if is_google_valid:
                ocr_prereqs_met = True
            else:
                missing.append(f"Google Credentials ({ocr_provider_name})")
        elif ocr_provider == "ocr_space":
            if is_ocrspace_set: # Language is handled by worker default if not set
                ocr_prereqs_met = True
            else:
                missing.append(f"API Key ({ocr_provider_name})")
        elif ocr_provider == "tesseract":
            # Assume Tesseract is installed if selected; rely on worker errors if not found.
            # A stricter check could involve trying to run `tesseract --version`
            ocr_prereqs_met = True
        else:
            missing.append(f"Unknown OCR Provider '{ocr_provider}'")

        # Check Translation Prereqs
        if trans_engine_key == "google_cloud_v3":
            if is_google_valid:
                trans_prereqs_met = True
            elif not any("Google Credentials" in item for item in missing):
                missing.append(f"Google Credentials ({trans_engine_name})")
        elif trans_engine_key == "deepl_free":
            if is_deepl_set:
                trans_prereqs_met = True
            else:
                missing.append(f"DeepL API Key ({trans_engine_name})")
        elif trans_engine_key == "googletrans":
            trans_prereqs_met = True # No API key needed
        else:
            missing.append(f"Unknown Translation Engine '{trans_engine_key}'")

        all_prereqs_met = ocr_prereqs_met and trans_prereqs_met
        if not all_prereqs_met and prompt_if_needed:
            missing_str = "\n- ".join(missing) if missing else "Unknown reason"
            logging.info(f"Prereqs missing for '{ocr_provider_name}'/'{trans_engine_name}'. Prompting.")
            msg = f"Required configuration missing or invalid:\n\n- {missing_str}\n\nConfigure in Settings (⚙️)."
            QMessageBox.warning(self.window, "Config Needed", msg)
            return False
        return all_prereqs_met

    def stop_processes(self):
        """Requests worker threads (OCR and Translation) to stop."""
        if self.thread and self.thread.isRunning():
            logging.warning("OcrHandler: Requesting OCR worker quit...")
            self.thread.quit()
            if not self.thread.wait(500):
                logging.error("OcrHandler: OCR Worker thread timeout.")
            else:
                logging.debug("OcrHandler: OCR Worker thread finished.")
        self.ocr_running = False
        self.thread = None
        self.worker = None

        if self.translation_thread and self.translation_thread.isRunning():
            logging.warning("OcrHandler: Requesting Translation worker quit...")
            self.translation_thread.quit()
            if not self.translation_thread.wait(500):
                logging.error("OcrHandler: Translation Worker thread timeout.")
            else:
                logging.debug("OcrHandler: Translation Worker thread finished.")
        self.translation_thread = None
        self.translation_worker = None