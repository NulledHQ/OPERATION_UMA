# filename: src/gui/handlers/ocr_handler.py
import logging
import html
import os

from PyQt5.QtCore import QObject, pyqtSignal, QThread, pyqtSlot, QRect
from PyQt5.QtWidgets import QApplication, QMessageBox

# Core components
from src.core.ocr_worker import OCRWorker
try:
    from src import config
    # from .settings_state_handler import SettingsStateHandler # For type hint
except ImportError:
    logging.error("OcrHandler: Failed to import config directly.")
    class ConfigFallback: AVAILABLE_OCR_PROVIDERS = {}; AVAILABLE_ENGINES = {}
    config = ConfigFallback()


class OcrHandler(QObject):
    """Handles the OCR/Translation workflow, worker thread management, and state."""

    ocrCompleted = pyqtSignal(str, str) # ocr_text, translated_text
    ocrError = pyqtSignal(str)         # error_message
    stateChanged = pyqtSignal(bool)    # True if OCR started, False if finished/error

    def __init__(self, window, history_manager, settings_state_handler): # Added settings_state_handler
        """
        Args:
            window: The main window instance (e.g., MainWindow). Used for parenting/context.
            history_manager: The history manager instance.
            settings_state_handler: The handler managing current settings state.
        """
        super().__init__(window) # Parent to window
        self.window = window
        self.history_manager = history_manager
        self.settings_state_handler = settings_state_handler # Store handler

        # Access UIManager via window (needed for geometry)
        self.ui_manager = getattr(window, 'ui_manager', None)
        if not self.ui_manager:
             logging.error("OcrHandler: Could not get ui_manager from window.")

        self.ocr_running = False
        self.thread = None
        self.worker = None

    def trigger_ocr(self):
        """Initiates the screen capture, OCR, and translation process."""
        # This method now assumes prerequisites were checked by the caller
        # (e.g., trigger_single_ocr or LiveModeHandler.start_timer)
        if self.ocr_running:
            logging.warning("OCR already running.")
            return

        # --- Start OCR Process ---
        self.ocr_running = True
        self.stateChanged.emit(True) # Signal OCR started
        logging.debug("OcrHandler starting OCR worker...")

        if not self.ui_manager:
             logging.error("OcrHandler: Cannot trigger OCR, ui_manager not found.")
             self._reset_state_and_emit(False)
             self.ocrError.emit("Internal Error: UI Manager not found.") # Send specific error
             return

        # Hide the text display area
        self.ui_manager.set_text_display_visibility(False)
        QApplication.processEvents()

        try:
            geo = self.window.geometry()
            content_rect = self.ui_manager.get_text_display_geometry()
            if not geo.isValid() or not content_rect.isValid(): raise ValueError("Invalid window/text geometry.")
            monitor = {"top": geo.top()+content_rect.top(), "left": geo.left()+content_rect.left(), "width": content_rect.width(), "height": content_rect.height()}
            if monitor["width"] <= 0 or monitor["height"] <= 0: raise ValueError(f"Invalid capture dimensions: w={monitor['width']},h={monitor['height']}")
            logging.debug(f"OcrHandler calculated monitor region: {monitor}")
        except Exception as e:
            logging.exception("OcrHandler error calculating capture region:")
            self._handle_internal_error(f"Capture Region Error: {e}")
            return

        # Prepare data for the worker
        history_snapshot = self.history_manager.get_history_list() if self.history_manager else []

        # Get current settings via SettingsStateHandler
        try:
            ocr_provider = self.settings_state_handler.get_value('ocr_provider')
            google_cred = self.settings_state_handler.get_value('google_credentials_path')
            ocrspace_key = self.settings_state_handler.get_value('ocrspace_api_key')
            ocr_lang = self.settings_state_handler.get_value('ocr_language_code')
            target_lang = self.settings_state_handler.get_value('target_language_code')
            trans_engine = self.settings_state_handler.get_value('translation_engine_key')
            deepl_key = self.settings_state_handler.get_value('deepl_api_key')
            # Check if any essential setting is None/missing if needed, though defaults should exist
            if not all([ocr_provider, ocr_lang, target_lang, trans_engine]):
                 raise ValueError("One or more essential settings missing from state handler.")
        except Exception as e:
             logging.error(f"OcrHandler: Error retrieving settings from state handler: {e}")
             self._handle_internal_error(f"Configuration Error: {e}")
             return

        # Setup and start the worker thread
        self.thread = QThread(self.window)
        self.worker = OCRWorker( monitor=monitor, selected_ocr_provider=ocr_provider, google_credentials_path=google_cred, ocrspace_api_key=ocrspace_key, ocr_language_code=ocr_lang, target_language_code=target_lang, history_data=history_snapshot, selected_trans_engine_key=trans_engine, deepl_api_key=deepl_key )
        self.worker.moveToThread(self.thread)
        # Connect signals...
        self.thread.started.connect(self.worker.run); self.worker.finished.connect(self._on_worker_done); self.worker.error.connect(self._on_worker_error)
        self.worker.finished.connect(self.thread.quit); self.worker.error.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater); self.worker.error.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater); self.thread.finished.connect(self._on_thread_finished)
        self.thread.start()
        logging.debug("OCR worker thread started by OcrHandler.")

    @pyqtSlot(str, str)
    def _on_worker_done(self, ocr_text, translated_text):
        logging.debug("OcrHandler received finished signal.")
        self.ocrCompleted.emit(ocr_text, translated_text)

    @pyqtSlot(str)
    def _on_worker_error(self, error_msg):
        logging.debug(f"OcrHandler received error signal: {error_msg}")
        self.ocrError.emit(error_msg)

    @pyqtSlot()
    def _on_thread_finished(self):
        logging.debug("OcrHandler notified worker thread finished.")
        self._reset_state_and_emit(False)

    def _reset_state_and_emit(self, is_running: bool):
        """Helper to reset internal state and emit stateChanged."""
        self.ocr_running = is_running
        self.thread = None
        self.worker = None
        if self.ui_manager: self.ui_manager.set_text_display_visibility(True)
        self.stateChanged.emit(is_running)

    def _handle_internal_error(self, error_msg):
         logging.error(f"OcrHandler internal error: {error_msg}")
         self.ocrError.emit(error_msg)
         self._reset_state_and_emit(False)

    def check_prerequisites(self, prompt_if_needed=False):
        """Checks prerequisites using SettingsStateHandler."""
        if not self.settings_state_handler:
            logging.error("Cannot check prerequisites: SettingsStateHandler not available.")
            if prompt_if_needed: QMessageBox.critical(self.window, "Internal Error", "Settings state handler missing.")
            return False

        # Get settings and flags from the state handler
        try:
            ocr_provider = self.settings_state_handler.get_value('ocr_provider')
            trans_engine_key = self.settings_state_handler.get_value('translation_engine_key')
            ocr_lang_code = self.settings_state_handler.get_value('ocr_language_code')
            is_google_valid = self.settings_state_handler.is_google_credentials_valid()
            is_ocrspace_set = self.settings_state_handler.is_ocrspace_key_set()
            is_deepl_set = self.settings_state_handler.is_deepl_key_set()
        except Exception as e:
            logging.error(f"Error getting settings/flags from state handler: {e}")
            if prompt_if_needed: QMessageBox.critical(self.window, "Internal Error", "Could not read settings state.")
            return False

        ocr_prereqs_met = False
        trans_prereqs_met = False
        missing = []
        ocr_provider_name = config.AVAILABLE_OCR_PROVIDERS.get(ocr_provider, ocr_provider)
        trans_engine_name = config.AVAILABLE_ENGINES.get(trans_engine_key, trans_engine_key)

        # Check OCR
        if ocr_provider == "google_vision":
            if is_google_valid: ocr_prereqs_met = True
            else: missing.append(f"Google Credentials (for {ocr_provider_name})")
        elif ocr_provider == "ocr_space":
            if is_ocrspace_set and ocr_lang_code: ocr_prereqs_met = True
            if not is_ocrspace_set: missing.append(f"API Key (for {ocr_provider_name})")
            if not ocr_lang_code: missing.append(f"OCR Language (for {ocr_provider_name})")
        else: missing.append(f"Config for unknown OCR Provider '{ocr_provider}'")

        # Check Translation
        if trans_engine_key == "google_cloud_v3":
            if is_google_valid: trans_prereqs_met = True
            elif not any("Google Credentials" in item for item in missing):
                 missing.append(f"Google Credentials (for {trans_engine_name})")
        elif trans_engine_key == "deepl_free":
            if is_deepl_set: trans_prereqs_met = True
            else: missing.append(f"DeepL API Key (for {trans_engine_name})")
        elif trans_engine_key == "googletrans":
            trans_prereqs_met = True
        else: missing.append(f"Config for unknown Translation Engine '{trans_engine_key}'")

        all_prereqs_met = ocr_prereqs_met and trans_prereqs_met

        if not all_prereqs_met and prompt_if_needed:
            missing_str = "\n- ".join(missing) if missing else "Unknown reason"
            logging.info(f"OCR/Translate prereqs missing for '{ocr_provider_name}'/'{trans_engine_name}'. Prompting.")
            msg = f"Required configuration missing:\n\n- {missing_str}\n\nConfigure in Settings (⚙️)."
            QMessageBox.warning(self.window, "Config Needed", msg)
            # Do not open dialog here, let MainWindow handle it if needed
            return False

        return all_prereqs_met

    def stop_processes(self):
        """Requests the worker thread (if running) to stop."""
        if self.thread and self.thread.isRunning():
            logging.warning("OcrHandler: Requesting worker thread quit...")
            self.thread.quit()
            if not self.thread.wait(1000): logging.error("OcrHandler: Worker thread did not finish cleanly.")
            else: logging.debug("OcrHandler: Worker thread finished after quit request.")
        self.ocr_running = False; self.thread = None; self.worker = None