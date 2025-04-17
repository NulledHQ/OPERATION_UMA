# filename: src/gui/main_window.py
import logging
import sys
import os
import html

from PyQt5.QtWidgets import (QWidget, QApplication, QMessageBox, QDialog, QStyle)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QByteArray, QRect, pyqtSlot
from PyQt5.QtGui import QColor, QFont

# --- Import application modules ---
from src import config
from src.core.settings_manager import SettingsManager
from src.core.history_manager import HistoryManager
from src.core import hotkey_manager
from src.gui.settings_dialog import SettingsDialog

# --- Import Handlers ---
from .handlers.interaction_handler import InteractionHandler
from .handlers.ocr_handler import OcrHandler
from .handlers.ui_handler import UIManager
from .handlers.live_mode_handler import LiveModeHandler
from .handlers.settings_state_handler import SettingsStateHandler # <<< Import


class MainWindow(QWidget):
    """
    Main application window. Orchestrates UI, settings, history, and OCR.
    Delegates state and specific logic to handler classes.
    """

    def __init__(self):
        super().__init__()

        # --- Initialize Core Managers (Persistence/History) ---
        self.settings_manager = SettingsManager()
        if not self.settings_manager: sys.exit(1)

        self.history_manager = HistoryManager(max_items=config.MAX_HISTORY_ITEMS)
        if not self.history_manager: QMessageBox.warning(None, "Init Warning", "HistoryManager failed.")

        # --- Load Initial Settings ---
        # SettingsManager loads the raw dictionary
        initial_settings_dict = self.settings_manager.load_all_settings()

        # --- Initialize State Handler FIRST ---
        # SettingsStateHandler takes the raw dict and manages the actual state
        self.settings_state_handler = SettingsStateHandler(initial_settings_dict)

        # --- Initialize Other Handlers (pass state handler if needed) ---
        self.ui_manager = UIManager(self, self.settings_state_handler) # Pass state handler
        self.interaction_handler = InteractionHandler(self, self.settings_state_handler) # Pass state handler
        self.ocr_handler = OcrHandler(self, self.history_manager, self.settings_state_handler) # Pass state handler
        self.live_mode_handler = LiveModeHandler(self, self.ocr_handler, self.ui_manager, self.settings_state_handler) # Pass state handler

        # --- Connect Signals ---
        self.ocr_handler.ocrCompleted.connect(self.on_ocr_done)
        self.ocr_handler.ocrError.connect(self.on_ocr_error)
        self.ocr_handler.stateChanged.connect(self.on_ocr_state_changed)
        self.live_mode_handler.timerStarted.connect(self.on_live_mode_timer_state_changed)
        self.live_mode_handler.timerStopped.connect(self.on_live_mode_timer_state_changed)
        # Connect change signal from state handler to update methods
        self.settings_state_handler.settingsChanged.connect(self.on_settings_changed)

        # --- UI Initialization via UIManager ---
        self.ui_manager.setup_window_properties()
        self.ui_manager.setup_ui()
        # Connect Grab Button after UI setup
        grab_button = self.ui_manager.get_widget('grab_button')
        if grab_button:
            try: grab_button.clicked.disconnect()
            except TypeError: pass
            grab_button.clicked.connect(self.on_grab_button_clicked)
        else: logging.error("Could not find grab_button to connect signal.")
        # --- End UI Initialization ---

        # Initial UI setup based on loaded state
        self._update_ui_from_settings() # Initial sync based on state handler
        self.restore_geometry(initial_settings_dict.get('saved_geometry')) # Use raw dict for geometry

        # --- Hotkey Setup ---
        current_hotkey = self.settings_state_handler.get_value('hotkey')
        logging.info(f"Attempting to start hotkey listener for: '{current_hotkey}'")
        if not hotkey_manager.start_hotkey_listener(current_hotkey, self.trigger_single_ocr):
             logging.error("Failed to start hotkey listener.")
             QMessageBox.warning(self, "Hotkey Error", f"Could not register global hotkey '{current_hotkey}'.")
        else:
             logging.info("Hotkey listener started successfully.")

        logging.info("Application window initialized.")

    # --- REMOVED _apply_loaded_settings ---
    # --- REMOVED _update_prerequisite_state_flags ---
    # --- REMOVED direct settings attributes (self.ocr_provider, etc.) ---

    # --------------------------------------------------------------------------
    # Settings Loading / Saving
    # --------------------------------------------------------------------------
    def load_settings(self):
        """Reloads settings from storage and applies them via the state handler."""
        if self.settings_manager:
            logging.debug("Reloading settings...")
            settings_dict = self.settings_manager.load_all_settings()
            # Apply settings via handler, which will emit signals for updates
            self.settings_state_handler.apply_settings(settings_dict)
            # Geometry needs separate handling if stored/loaded
            self.restore_geometry(settings_dict.get('saved_geometry'))
        else:
            logging.error("SettingsManager not available.")

    def save_settings(self):
        """Saves current application state (from state handler) to settings."""
        if self.settings_manager and self.settings_state_handler:
            current_settings_data = self.settings_state_handler.get_all_settings()
            current_geometry = self.saveGeometry()
            self.settings_manager.save_all_settings(current_settings_data, current_geometry)
        else: logging.error("SettingsManager or SettingsStateHandler not available for saving.")

    # --- History Management ---
    def clear_history(self):
        # (Remains the same)
        if self.history_manager:
            self.history_manager.clear_history(parent_widget=self)
            if not self.history_manager.history_deque: self.ui_manager.update_text_display_content("")
        else: QMessageBox.warning(self, "Error", "History unavailable.")

    def export_history(self):
        # (Remains the same)
        if self.history_manager: self.history_manager.export_history(parent_widget=self)
        else: QMessageBox.warning(self, "Error", "History unavailable.")

    # --- Geometry / Lock State ---
    def restore_geometry(self, saved_geometry_bytes):
        # (Remains the same)
        restored = False
        if saved_geometry_bytes and isinstance(saved_geometry_bytes, QByteArray):
            try: restored = self.restoreGeometry(saved_geometry_bytes)
            except Exception as e: logging.error(f"Error restoring geometry: {e}"); restored = False
        if restored: logging.debug("Window geometry restored.")
        else: logging.debug("Using default geometry."); self.setGeometry(100, 100, 400, 300)

    def apply_lock_state(self, is_locked):
        """Applies lock state (opacity) based on setting value."""
        opacity = 0.95 if is_locked else 1.0
        self.setWindowOpacity(opacity)
        logging.info(f"Window lock state applied: {'Locked' if is_locked else 'Unlocked'}.")

    # --------------------------------------------------------------------------
    # Settings Dialog Interaction
    # --------------------------------------------------------------------------
    def open_settings_dialog(self):
        """Opens the settings configuration dialog."""
        if 'SettingsDialog' not in globals() or not SettingsDialog:
             QMessageBox.critical(self, "Error", "SettingsDialog component not loaded.")
             return
        if not self.settings_state_handler:
             QMessageBox.critical(self, "Error", "Settings state handler not available.")
             return

        logging.debug("Opening settings dialog...")
        # Prepare current data for dialog using state handler
        current_data = self.settings_state_handler.get_all_settings()
        # SettingsDialog expects 'translation_engine', map key if necessary
        current_data['translation_engine'] = current_data.get('translation_engine_key')

        dialog = SettingsDialog(self, current_data)

        if dialog.exec_() == QDialog.Accepted:
            logging.debug("Settings dialog accepted. Applying via state handler...")
            updated_settings = dialog.get_updated_settings()
            # Apply changes through the state handler
            # This will trigger the on_settings_changed slot for updates
            self.settings_state_handler.apply_settings(updated_settings)
            self.save_settings() # Save immediately after dialog OK
            logging.debug("Settings applied and saved.")
        else:
            logging.debug("Settings dialog cancelled.")

    # --------------------------------------------------------------------------
    # OCR / Button / Checkbox Logic
    # --------------------------------------------------------------------------
    def trigger_single_ocr(self):
        """Triggers a single OCR capture if conditions allow."""
        if self.live_mode_handler.is_active():
            logging.debug("Single OCR trigger skipped, Live Mode timer is active.")
            return
        if self.ocr_handler.ocr_running:
            logging.warning("Single OCR trigger skipped, OCR already running.")
            return
        # Check prerequisites via OcrHandler (which uses SettingsStateHandler)
        if self.ocr_handler.check_prerequisites(prompt_if_needed=True):
            self.ocr_handler.trigger_ocr()
        else:
            logging.warning("Single OCR trigger skipped, prerequisites not met.")


    def on_grab_button_clicked(self):
        """Handles clicks on the main action button."""
        # Get checkbox state directly from widget via UIManager
        live_cb = self.ui_manager.get_widget('live_mode_checkbox')
        is_live_potentially_enabled = live_cb.isChecked() if live_cb else False

        if is_live_potentially_enabled:
            if self.live_mode_handler.is_active():
                logging.info("Grab button clicked while live timer active: Stopping timer.")
                self.live_mode_handler.stop_timer()
            else:
                logging.info("Grab button clicked while live enabled but timer inactive: Starting timer.")
                # Start timer will check prereqs via ocr_handler
                self.live_mode_handler.start_timer()
        else:
            logging.info("Grab button clicked while live disabled: Triggering single OCR.")
            self.trigger_single_ocr()
        # UI state updates happen via signals from LiveModeHandler or OcrHandler

    def _update_ocr_button_states(self):
        """Update grab button and live mode checkbox based on current state."""
        # Get prerequisite state from SettingsStateHandler
        can_run_ocr = self.ocr_handler.check_prerequisites(prompt_if_needed=False)

        # Get operational states
        is_live_timer_active = self.live_mode_handler.is_active()
        is_ocr_running = self.ocr_handler.ocr_running
        # Get checkbox state directly from widget for consistency check
        live_cb = self.ui_manager.get_widget('live_mode_checkbox')
        is_live_potentially_enabled = live_cb.isChecked() if live_cb else False


        # --- Update Grab Button ---
        grab_enabled = False
        grab_text = "Grab Text"
        grab_tooltip = ""
        current_hotkey = self.settings_state_handler.get_value('hotkey', '')
        hotkey_display = f"({current_hotkey.replace('+', ' + ').title()})" if current_hotkey else ""

        if is_ocr_running:
            grab_text = "Working..."
            grab_tooltip = "OCR in progress..."
            grab_enabled = False
        elif not can_run_ocr:
            grab_text = "Grab Text"
            grab_tooltip = "Prerequisites not met (Configure ⚙️)"
            grab_enabled = False
        elif is_live_potentially_enabled: # Checkbox is checked
            if is_live_timer_active:
                grab_text = "Stop Live"
                grab_tooltip = "Click to stop periodic capture"
                grab_enabled = True
            else: # Checkbox checked, timer inactive
                grab_text = "Start Live"
                grab_tooltip = "Click to start periodic capture"
                grab_enabled = True
        else: # Checkbox unchecked, OCR ready, OCR not running
            grab_text = "Grab Text"
            grab_tooltip = f"Click for single capture {hotkey_display}"
            grab_enabled = True

        self.ui_manager.set_grab_button_state(enabled=grab_enabled, text=grab_text, tooltip=grab_tooltip)

        # --- Update Live Mode Checkbox ---
        checkbox_enabled = can_run_ocr and not is_ocr_running
        checkbox_checked = is_live_potentially_enabled

        self.ui_manager.set_live_mode_checkbox_state(
            checked=checkbox_checked,
            enabled=checkbox_enabled,
            is_active=is_live_timer_active # Pass timer status for indicator
        )

    # --- Slots for Handler Signals ---
    @pyqtSlot(dict)
    def on_settings_changed(self, changed_settings: dict):
        """Handles updates when settings state changes."""
        logging.debug(f"MainWindow received settings changed: {changed_settings.keys()}")

        # Update components based on changed keys
        needs_button_update = False
        if any(k in changed_settings for k in ['display_font', 'bg_color']):
            self.ui_manager.update_text_display_style()
        if 'is_locked' in changed_settings:
            self.apply_lock_state(changed_settings['is_locked'])
        if 'hotkey' in changed_settings:
            new_hotkey = changed_settings['hotkey']
            logging.info(f"Hotkey changed to '{new_hotkey}' via settings handler.")
            if hotkey_manager.update_active_hotkey(new_hotkey):
                logging.info("Hotkey listener updated successfully.")
                needs_button_update = True
            else:
                logging.error("Failed to update hotkey listener.")
                QMessageBox.warning(self, "Hotkey Update Failed", f"Could not apply new hotkey '{new_hotkey}'.")
        # If provider/keys changed, prerequisite flags were updated in handler,
        # we just need to update the UI state reflecting those flags.
        if any(k in changed_settings for k in [
            'ocr_provider', 'google_credentials_path', 'ocrspace_api_key',
            'deepl_api_key', 'translation_engine_key', 'ocr_language_code'
            ]):
            needs_button_update = True

        if needs_button_update:
            self._update_ocr_button_states()

        # Potentially update LiveModeHandler interval if it changes?
        # Currently interval is read when timer starts. If changed while running,
        # the timer needs to be restarted. Or LiveModeHandler could listen too.
        # For simplicity, interval change only affects next Live Mode start.
        if 'ocr_interval' in changed_settings:
            # No action needed here currently
            pass

        self.update() # Trigger repaint if color/alpha might have changed


    @pyqtSlot(str, str)
    def on_ocr_done(self, ocr_text, translated_text):
        self.ui_manager.set_text_display_visibility(True)
        logging.info("OCR results received by MainWindow.")
        if self.history_manager: self.history_manager.add_item(ocr_text, translated_text)
        # HTML formatting...
        safe_ocr = html.escape(ocr_text or ""); safe_trans = translated_text or ""
        target_lang_code = self.settings_state_handler.get_value('target_language_code', 'N/A')
        display_font = self.settings_state_handler.get_value('display_font', QFont())
        ocr_provider = self.settings_state_handler.get_value('ocr_provider', '?')
        trans_engine_key = self.settings_state_handler.get_value('translation_engine_key', '?')

        lang = html.escape(target_lang_code.upper()); ocr_fmt = safe_ocr.replace('\n', '<br/>'); trans_fmt = safe_trans
        is_error = isinstance(safe_trans, str) and safe_trans.startswith("[") and "Error:" in safe_trans
        if not is_error: trans_fmt = html.escape(safe_trans).replace('\n', '<br/>')
        font_style = f"font-family:'{display_font.family()}'; font-size:{display_font.pointSize()}pt;"; err_style = "color:#A00;"; ok_style = "color:#000;"
        ocr_provider_name = config.AVAILABLE_OCR_PROVIDERS.get(ocr_provider, ocr_provider); trans_engine_name = config.AVAILABLE_ENGINES.get(trans_engine_key, trans_engine_key)
        html_out = f"""<div style="margin-bottom:10px;"><b style="color:#333;">--- OCR ({ocr_provider_name}) ---</b><br/><div style="margin-left:5px; {font_style} color:#000;">{ocr_fmt if ocr_fmt else '<i style="color:#777;">No text detected.</i>'}</div></div><div><b style="color:#333;">--- Translation ({trans_engine_name} / {lang}) ---</b><br/><div style="margin-left:5px; {font_style} {err_style if is_error else ok_style}">{trans_fmt if trans_fmt else ('<i style="color:#777;">N/A</i>' if not ocr_fmt else '<i style="color:#777;">No translation.</i>')}</div></div>"""
        self.ui_manager.update_text_display_content(html_out, Qt.AlignLeft)

    @pyqtSlot(str)
    def on_ocr_error(self, error_msg):
        self.ui_manager.set_text_display_visibility(True)
        logging.error(f"MainWindow received error signal: {error_msg}")
        # HTML formatting...
        display_font = self.settings_state_handler.get_value('display_font', QFont())
        font_style = f"font-family:'{display_font.family()}'; font-size:{display_font.pointSize()}pt;"; err_html = f"""<p style="color:#A00;font-weight:bold;">--- Error ---</p><p style="color:#A00; {font_style}">{html.escape(error_msg)}</p>"""
        self.ui_manager.update_text_display_content(err_html, Qt.AlignLeft)

    @pyqtSlot(bool)
    def on_ocr_state_changed(self, is_running):
        """Slot connected to OcrHandler.stateChanged signal."""
        logging.debug(f"MainWindow received OCR state change: {'Running' if is_running else 'Finished'}")
        self._update_ocr_button_states()
        if not is_running:
            self.ui_manager.set_text_display_visibility(True)

    @pyqtSlot()
    def on_live_mode_timer_state_changed(self): # Renamed slot
        """Slot connected to LiveModeHandler timerStarted/timerStopped signals."""
        logging.debug("MainWindow received Live Mode timer state change signal.")
        self._update_ocr_button_states()

    @pyqtSlot(int)
    def on_live_mode_checkbox_changed(self, state):
        """Slot connected to the Live Mode checkbox stateChanged signal."""
        is_checked = (state == Qt.Checked)
        # Update the internal flag tracking user's *intent*
        self.live_mode_potentially_enabled = is_checked
        logging.info(f"Live mode potentially enabled set to: {is_checked}")

        if not is_checked:
            # If user unchecks the box, ensure the timer stops
            if self.live_mode_handler.is_active():
                logging.info("Live mode checkbox unchecked by user, stopping timer...")
                self.live_mode_handler.stop_timer()
            else:
                # Update UI state immediately even if timer wasn't active
                self._update_ocr_button_states()
        else:
            # Checking the box only enables the potential, update UI state
            self._update_ocr_button_states()

    def _update_ui_from_settings(self):
         """Update UI elements based on initial settings state"""
         logging.debug("Syncing UI from initial settings state...")
         self.apply_lock_state(self.settings_state_handler.get_value('is_locked', False))
         self.ui_manager.update_text_display_style()
         # Update buttons/checkbox state based on all current states
         self._update_ocr_button_states()
         self.update() # Trigger repaint


    # --- Window Interaction Events (Delegated) ---
    def resizeEvent(self, event): self.ui_manager.handle_resize_event(event); super().resizeEvent(event)
    def paintEvent(self, event): self.ui_manager.handle_paint_event(event)
    def mousePressEvent(self, event): self.interaction_handler.mousePressEvent(event)
    def mouseMoveEvent(self, event): self.interaction_handler.mouseMoveEvent(event)
    def mouseReleaseEvent(self, event): self.interaction_handler.mouseReleaseEvent(event)

    # --- Application Lifecycle ---
    def closeEvent(self, event):
        """Handles the window close event for cleanup."""
        logging.info("Close event received. Cleaning up...")
        self.live_mode_handler.stop()
        self.ocr_handler.stop_processes()
        hotkey_manager.stop_hotkey_listener()
        self.save_settings()
        logging.info("Cleanup finished. Exiting application.")
        event.accept()
        app_instance = QApplication.instance()
        if app_instance: app_instance.quit()