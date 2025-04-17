# filename: src/gui/handlers/live_mode_handler.py
import logging
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, Qt
from PyQt5.QtWidgets import QMessageBox

try:
    from src import config
    # from .settings_state_handler import SettingsStateHandler # For type hint
except ImportError:
    logging.error("LiveModeHandler: Failed to import config.")
    class ConfigFallback: AVAILABLE_OCR_PROVIDERS = {}; AVAILABLE_ENGINES = {}
    config = ConfigFallback()


class LiveModeHandler(QObject):
    """Manages the state and timer for Live OCR mode."""

    timerStarted = pyqtSignal()
    timerStopped = pyqtSignal()

    def __init__(self, window, ocr_handler, ui_manager, settings_state_handler): # Added settings_state_handler
        super().__init__(window)
        self.window = window
        self.ocr_handler = ocr_handler
        self.ui_manager = ui_manager
        self.settings_state_handler = settings_state_handler # Store handler

        self._is_timer_active = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.ocr_handler.trigger_ocr)

    def is_active(self) -> bool:
        return self._is_timer_active

    def start_timer(self) -> bool:
        """Attempts to start the Live Mode timer. Returns True if successful."""
        if self._is_timer_active:
            logging.debug("LiveModeHandler: Timer start called but already active.")
            return True

        # Get interval from SettingsStateHandler
        try:
            interval_sec = self.settings_state_handler.get_value('ocr_interval', config.DEFAULT_OCR_INTERVAL_SECONDS)
        except Exception as e:
             logging.error(f"LiveModeHandler: Error getting interval from state handler: {e}")
             QMessageBox.critical(self.window, "Internal Error", f"Cannot start Live Mode timer: Missing interval setting.")
             return False

        # Check prerequisites via OcrHandler (which uses settings state handler)
        if not self.ocr_handler.check_prerequisites(prompt_if_needed=True): # Prompt if check fails here
             # Prerequisite message shown by OcrHandler
             return False

        # Start the timer
        interval_ms = max(1000, interval_sec * 1000)
        self._timer.setInterval(interval_ms)
        self._timer.start()
        self._is_timer_active = True
        logging.info(f"Live Mode timer started by handler (Interval: {interval_ms / 1000.0}s).")
        self.timerStarted.emit()
        # No initial OCR trigger
        return True

    def stop_timer(self):
        """Stops the Live Mode timer if it's active."""
        if not self._is_timer_active:
            logging.debug("LiveModeHandler: Timer stop called but not active.")
            return
        self._timer.stop()
        self._is_timer_active = False
        logging.info("Live Mode timer stopped by handler.")
        self.timerStopped.emit()

    def stop(self):
        """Ensures the timer is stopped (e.g., on application close)."""
        self.stop_timer()