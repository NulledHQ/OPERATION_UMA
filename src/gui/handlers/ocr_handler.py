# filename: src/gui/handlers/ocr_handler.py
import logging
import html
import os

from PyQt5.QtCore import QObject, pyqtSignal, QThread, pyqtSlot, QRect
from PyQt5.QtWidgets import QApplication, QMessageBox

# Core components
from src.core.ocr_worker import OCRWorker
from src.core.translation_worker import TranslationWorker # Import new worker
try:
    from src import config
    # from .settings_state_handler import SettingsStateHandler # For type hint
except ImportError:
    logging.error("OcrHandler: Failed to import config directly.")
    class ConfigFallback: AVAILABLE_OCR_PROVIDERS = {}; AVAILABLE_ENGINES = {}
    config = ConfigFallback()


class OcrHandler(QObject):
    """Handles the OCR/Translation workflow, worker thread management, and state."""

    # Original OCR signals
    ocrCompleted = pyqtSignal(str, str) # ocr_text, translated_text
    ocrError = pyqtSignal(str)         # error_message
    stateChanged = pyqtSignal(bool)    # True if OCR started, False if finished/error

    # New signals for re-translation
    retranslationCompleted = pyqtSignal(str, str) # original_text, new_translation
    retranslationError = pyqtSignal(str)        # error_message

    def __init__(self, window, history_manager, settings_state_handler):
        super().__init__(window)
        self.window = window
        self.history_manager = history_manager
        self.settings_state_handler = settings_state_handler
        self.ui_manager = getattr(window, 'ui_manager', None)
        if not self.ui_manager: logging.error("OcrHandler: Could not get ui_manager from window.")

        self.ocr_running = False
        self.thread = None # For OCRWorker
        self.worker = None # For OCRWorker

        self.translation_thread = None # For TranslationWorker
        self.translation_worker = None # For TranslationWorker

        self.last_ocr_text = "" # Store last successful OCR text

    def trigger_ocr(self):
        # (Method remains the same as previous version)
        if self.ocr_running: logging.warning("OCR already running."); return
        if not self.check_prerequisites(prompt_if_needed=True): logging.warning("OCR cancelled: Prerequisite check failed."); return
        self.ocr_running = True; self.stateChanged.emit(True); logging.debug("OcrHandler starting OCR worker...")
        if not self.ui_manager: logging.error("OcrHandler: ui_manager not found."); self._reset_state_and_emit(False); self.ocrError.emit("Internal Error: UI Manager missing."); return
        self.ui_manager.set_text_display_visibility(False); QApplication.processEvents()
        try:
            geo = self.window.geometry(); content_rect = self.ui_manager.get_text_display_geometry()
            if not geo.isValid() or not content_rect.isValid(): raise ValueError("Invalid geometry.")
            monitor = {"top": geo.top()+content_rect.top(), "left": geo.left()+content_rect.left(), "width": content_rect.width(), "height": content_rect.height()}
            if monitor["width"] <= 0 or monitor["height"] <= 0: raise ValueError(f"Invalid capture dimensions: w={monitor['width']},h={monitor['height']}")
            logging.debug(f"OcrHandler calculated monitor region: {monitor}")
        except Exception as e: logging.exception("OcrHandler error calculating region:"); self._handle_internal_error(f"Capture Region Error: {e}"); return
        history_snapshot = self.history_manager.get_history_list() if self.history_manager else []
        try: # Get settings
            ocr_provider = self.settings_state_handler.get_value('ocr_provider'); google_cred = self.settings_state_handler.get_value('google_credentials_path')
            ocrspace_key = self.settings_state_handler.get_value('ocrspace_api_key'); ocr_lang = self.settings_state_handler.get_value('ocr_language_code')
            target_lang = self.settings_state_handler.get_value('target_language_code'); trans_engine = self.settings_state_handler.get_value('translation_engine_key')
            deepl_key = self.settings_state_handler.get_value('deepl_api_key')
            if not all([ocr_provider, ocr_lang, target_lang, trans_engine]): raise ValueError("Essential settings missing.")
        except Exception as e: logging.error(f"OcrHandler: Error getting settings: {e}"); self._handle_internal_error(f"Config Error: {e}"); return
        self.thread = QThread(self.window); self.worker = OCRWorker( monitor=monitor, selected_ocr_provider=ocr_provider, google_credentials_path=google_cred, ocrspace_api_key=ocrspace_key, ocr_language_code=ocr_lang, target_language_code=target_lang, history_data=history_snapshot, selected_trans_engine_key=trans_engine, deepl_api_key=deepl_key )
        self.worker.moveToThread(self.thread); self.thread.started.connect(self.worker.run); self.worker.finished.connect(self._on_worker_done); self.worker.error.connect(self._on_worker_error)
        self.worker.finished.connect(self.thread.quit); self.worker.error.connect(self.thread.quit); self.worker.finished.connect(self.worker.deleteLater); self.worker.error.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater); self.thread.finished.connect(self._on_thread_finished)
        self.thread.start(); logging.debug("OCR worker thread started by OcrHandler.")


    @pyqtSlot(str, str)
    def _on_worker_done(self, ocr_text, translated_text):
        logging.debug("OcrHandler received finished signal from OCR worker.")
        # Store the successful OCR text before emitting
        if ocr_text:
            self.last_ocr_text = ocr_text
            logging.debug(f"Stored last OCR text (length: {len(self.last_ocr_text)}).")
        else:
             # Don't clear last_ocr_text if current OCR failed, keep previous one
             logging.debug("Current OCR empty, retaining previous last_ocr_text.")
             pass
        self.ocrCompleted.emit(ocr_text, translated_text)

    @pyqtSlot(str)
    def _on_worker_error(self, error_msg):
        logging.debug(f"OcrHandler received error signal from OCR worker: {error_msg}")
        # Don't clear last_ocr_text on error
        self.ocrError.emit(error_msg)

    @pyqtSlot()
    def _on_thread_finished(self):
        logging.debug("OcrHandler notified OCR worker thread finished.")
        self._reset_state_and_emit(False)

    # --- Retranslation Methods (NEW) ---

    def get_last_ocr_text(self) -> str:
        """Returns the last successfully captured non-empty OCR text."""
        return self.last_ocr_text

    def request_retranslation(self, new_target_language_code: str):
        """Starts a TranslationWorker to re-translate the last OCR text."""
        if not self.last_ocr_text:
            logging.warning("Re-translation requested but no previous OCR text available.")
            self.retranslationError.emit("No text captured previously to re-translate.")
            return False # Indicate failure to start

        if self.translation_thread and self.translation_thread.isRunning():
             logging.warning("Re-translation requested but another translation is already running.")
             self.retranslationError.emit("Another translation is already in progress.")
             return False

        logging.info(f"Requesting re-translation of last OCR text to '{new_target_language_code}'.")

        # Get current engine config
        try:
            trans_engine = self.settings_state_handler.get_value('translation_engine_key')
            google_cred = self.settings_state_handler.get_value('google_credentials_path')
            deepl_key = self.settings_state_handler.get_value('deepl_api_key')
            if not trans_engine: raise ValueError("Translation engine key missing.")
        except Exception as e:
             logging.error(f"OcrHandler: Error getting settings for re-translation: {e}")
             self.retranslationError.emit(f"Config Error for re-translation: {e}")
             return False

        # Setup and start the TranslationWorker thread
        self.translation_thread = QThread(self.window)
        self.translation_worker = TranslationWorker(
            text_to_translate=self.last_ocr_text,
            target_language_code=new_target_language_code,
            selected_trans_engine_key=trans_engine,
            google_credentials_path=google_cred,
            deepl_api_key=deepl_key
        )
        self.translation_worker.moveToThread(self.translation_thread)

        # Connect signals specific to re-translation
        self.translation_thread.started.connect(self.translation_worker.run)
        # Connect worker signals to OcrHandler's internal slots or directly to new signals
        self.translation_worker.finished.connect(self._on_translation_worker_done)
        self.translation_worker.error.connect(self._on_translation_worker_error)
        # Cleanup
        self.translation_worker.finished.connect(self.translation_thread.quit)
        self.translation_worker.error.connect(self.translation_thread.quit)
        self.translation_worker.finished.connect(self.translation_worker.deleteLater)
        self.translation_worker.error.connect(self.translation_worker.deleteLater)
        self.translation_thread.finished.connect(self.translation_thread.deleteLater)
        # Optional: Connect thread finish to a cleanup method if needed
        self.translation_thread.finished.connect(self._on_translation_thread_finished)

        self.translation_thread.start()
        logging.debug("Translation worker thread started by OcrHandler.")
        return True # Indicate started successfully


    @pyqtSlot(str, str)
    def _on_translation_worker_done(self, original_text, new_translation):
        """Handles successful results from TranslationWorker."""
        logging.debug("OcrHandler received finished signal from TranslationWorker.")
        self.retranslationCompleted.emit(original_text, new_translation)

    @pyqtSlot(str)
    def _on_translation_worker_error(self, error_msg):
        """Handles errors from TranslationWorker."""
        logging.debug(f"OcrHandler received error signal from TranslationWorker: {error_msg}")
        self.retranslationError.emit(error_msg)

    @pyqtSlot()
    def _on_translation_thread_finished(self):
         """Cleans up translation thread/worker references."""
         logging.debug("OcrHandler notified translation worker thread finished.")
         self.translation_thread = None
         self.translation_worker = None
    # --- End Retranslation Methods ---

    # --- Other methods (check_prerequisites, stop_processes, etc.) ---
    def _reset_state_and_emit(self, is_running: bool):
        self.ocr_running = is_running; self.thread = None; self.worker = None
        if self.ui_manager: self.ui_manager.set_text_display_visibility(True)
        self.stateChanged.emit(is_running)

    def _handle_internal_error(self, error_msg):
         logging.error(f"OcrHandler internal error: {error_msg}"); self.ocrError.emit(error_msg)
         self._reset_state_and_emit(False)

    def check_prerequisites(self, prompt_if_needed=False):
        # (Remains the same, uses settings_state_handler)
        if not self.settings_state_handler: logging.error("Cannot check prereqs: SettingsStateHandler missing."); return False
        try:
            ocr_provider = self.settings_state_handler.get_value('ocr_provider'); trans_engine_key = self.settings_state_handler.get_value('translation_engine_key')
            ocr_lang_code = self.settings_state_handler.get_value('ocr_language_code'); is_google_valid = self.settings_state_handler.is_google_credentials_valid()
            is_ocrspace_set = self.settings_state_handler.is_ocrspace_key_set(); is_deepl_set = self.settings_state_handler.is_deepl_key_set()
        except Exception as e: logging.error(f"Error getting settings/flags: {e}"); return False
        ocr_prereqs_met = False; trans_prereqs_met = False; missing = []
        ocr_provider_name = config.AVAILABLE_OCR_PROVIDERS.get(ocr_provider, ocr_provider); trans_engine_name = config.AVAILABLE_ENGINES.get(trans_engine_key, trans_engine_key)
        if ocr_provider == "google_vision":
            if is_google_valid: ocr_prereqs_met = True
            else: missing.append(f"Google Credentials (for {ocr_provider_name})")
        elif ocr_provider == "ocr_space":
            if is_ocrspace_set and ocr_lang_code: ocr_prereqs_met = True
            if not is_ocrspace_set: missing.append(f"API Key (for {ocr_provider_name})")
            if not ocr_lang_code: missing.append(f"OCR Language (for {ocr_provider_name})")
        else: missing.append(f"Config for unknown OCR Provider '{ocr_provider}'")
        if trans_engine_key == "google_cloud_v3":
            if is_google_valid: trans_prereqs_met = True
            elif not any("Google Credentials" in item for item in missing): missing.append(f"Google Credentials (for {trans_engine_name})")
        elif trans_engine_key == "deepl_free":
            if is_deepl_set: trans_prereqs_met = True
            else: missing.append(f"DeepL API Key (for {trans_engine_name})")
        elif trans_engine_key == "googletrans": trans_prereqs_met = True
        else: missing.append(f"Config for unknown Translation Engine '{trans_engine_key}'")
        all_prereqs_met = ocr_prereqs_met and trans_prereqs_met
        if not all_prereqs_met and prompt_if_needed:
            missing_str = "\n- ".join(missing) if missing else "Unknown reason"; logging.info(f"Prereqs missing for '{ocr_provider_name}'/'{trans_engine_name}'. Prompting.")
            msg = f"Required config missing:\n\n- {missing_str}\n\nConfigure in Settings (⚙️)."; QMessageBox.warning(self.window, "Config Needed", msg)
            return False
        return all_prereqs_met

    def stop_processes(self):
        """Requests worker threads (OCR and Translation) to stop."""
        if self.thread and self.thread.isRunning():
            logging.warning("OcrHandler: Requesting OCR worker thread quit...")
            self.thread.quit()
            if not self.thread.wait(500): logging.error("OcrHandler: OCR Worker thread did not finish cleanly.")
            else: logging.debug("OcrHandler: OCR Worker thread finished after quit request.")
        self.ocr_running = False; self.thread = None; self.worker = None

        if self.translation_thread and self.translation_thread.isRunning():
            logging.warning("OcrHandler: Requesting Translation worker thread quit...")
            self.translation_thread.quit()
            if not self.translation_thread.wait(500): logging.error("OcrHandler: Translation Worker thread did not finish cleanly.")
            else: logging.debug("OcrHandler: Translation Worker thread finished after quit request.")
        self.translation_thread = None; self.translation_worker = None