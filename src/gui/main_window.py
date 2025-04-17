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
from .handlers.settings_state_handler import SettingsStateHandler


class MainWindow(QWidget):
    """
    Main application window. Orchestrates UI, settings, history, and OCR.
    Delegates state and specific logic to handler classes.
    """

    def __init__(self):
        super().__init__()

        # --- Initialize Core Managers ---
        self.settings_manager = SettingsManager();
        if not self.settings_manager: sys.exit(1)
        self.history_manager = HistoryManager(max_items=config.MAX_HISTORY_ITEMS)
        if not self.history_manager: QMessageBox.warning(None, "Init Warning", "HistoryManager failed.")

        # --- Load Initial Settings ---
        initial_settings_dict = self.settings_manager.load_all_settings()

        # --- Initialize Handlers ---
        self.settings_state_handler = SettingsStateHandler(initial_settings_dict)
        self.ui_manager = UIManager(self, self.settings_state_handler)
        self.interaction_handler = InteractionHandler(self, self.settings_state_handler)
        self.ocr_handler = OcrHandler(self, self.history_manager, self.settings_state_handler)
        self.live_mode_handler = LiveModeHandler(self, self.ocr_handler, self.ui_manager, self.settings_state_handler)

        # --- Connect Signals ---
        self.ocr_handler.ocrCompleted.connect(self.on_ocr_done)
        self.ocr_handler.ocrError.connect(self.on_ocr_error)
        self.ocr_handler.stateChanged.connect(self.on_ocr_state_changed)
        # Retranslate signals (NEW)
        self.ocr_handler.retranslationCompleted.connect(self.on_retranslation_done)
        self.ocr_handler.retranslationError.connect(self.on_retranslation_error)
        # Live Mode signals
        self.live_mode_handler.timerStarted.connect(self.on_live_mode_timer_state_changed)
        self.live_mode_handler.timerStopped.connect(self.on_live_mode_timer_state_changed)
        # Settings signals
        self.settings_state_handler.settingsChanged.connect(self.on_settings_changed)

        # --- UI Initialization via UIManager ---
        self.ui_manager.setup_window_properties()
        self.ui_manager.setup_ui() # Creates retranslate controls
        # Connect Grab Button signal
        grab_button = self.ui_manager.get_widget('grab_button')
        if grab_button:
            try: grab_button.clicked.disconnect()
            except TypeError: pass
            grab_button.clicked.connect(self.on_grab_button_clicked)
        else: logging.error("Could not find grab_button to connect signal.")
        # Retranslate button connection happens in setup_ui now

        # --- End UI Initialization ---

        # Initial UI setup based on loaded state
        self._update_ui_from_settings() # Updates styles, buttons, locks, retranslate state
        self.restore_geometry(initial_settings_dict.get('saved_geometry'))

        # --- Hotkey Setup ---
        current_hotkey = self.settings_state_handler.get_value('hotkey')
        logging.info(f"Attempting to start hotkey listener for: '{current_hotkey}'")
        if not hotkey_manager.start_hotkey_listener(current_hotkey, self.trigger_single_ocr):
             logging.error("Failed to start hotkey listener."); QMessageBox.warning(self, "Hotkey Error", f"Could not register global hotkey '{current_hotkey}'.")
        else: logging.info("Hotkey listener started successfully.")

        self.ui_manager.set_status("Ready", 3000)
        logging.info("Application window initialized.")

    # --- Settings Loading / Saving (remain the same) ---
    def load_settings(self):
        if self.settings_manager: logging.debug("Reloading settings..."); settings_dict = self.settings_manager.load_all_settings(); self.settings_state_handler.apply_settings(settings_dict); self.restore_geometry(settings_dict.get('saved_geometry')); self.ui_manager.set_status("Settings Reloaded", 3000)
        else: logging.error("SettingsManager not available.")

    def save_settings(self):
        if self.settings_manager and self.settings_state_handler: current_settings_data = self.settings_state_handler.get_all_settings(); current_geometry = self.saveGeometry(); self.settings_manager.save_all_settings(current_settings_data, current_geometry)
        else: logging.error("SettingsManager or SettingsStateHandler not available for saving.")

    # --- History Management (remain the same) ---
    def clear_history(self):
        if self.history_manager: cleared = self.history_manager.clear_history(parent_widget=self);
        if cleared: self.ui_manager.update_text_display_content(""); self.ui_manager.set_status("History Cleared", 3000); self._update_all_button_states() # Update retranslate state
        else: QMessageBox.warning(self, "Error", "History unavailable.")

    def export_history(self):
        if self.history_manager: exported = self.history_manager.export_history(parent_widget=self);
        if exported: self.ui_manager.set_status("History Exported", 3000)
        else: QMessageBox.warning(self, "Error", "History unavailable.")

    # --- Geometry / Lock State (remain the same) ---
    def restore_geometry(self, saved_geometry_bytes):
        restored = False
        if saved_geometry_bytes and isinstance(saved_geometry_bytes, QByteArray):
            try: restored = self.restoreGeometry(saved_geometry_bytes)
            except Exception as e: logging.error(f"Error restoring geometry: {e}"); restored = False
        if restored: logging.debug("Window geometry restored.")
        else: logging.debug("Using default geometry."); self.setGeometry(100, 100, 400, 300)

    def apply_lock_state(self, is_locked):
        self.ui_manager.set_locked_indicator(is_locked)
        logging.info(f"Window lock state applied: {'Locked' if is_locked else 'Unlocked'}.")

    # --- Settings Dialog Interaction (remain the same) ---
    def open_settings_dialog(self):
        if 'SettingsDialog' not in globals() or not SettingsDialog: QMessageBox.critical(self, "Error", "SettingsDialog component not loaded."); return
        if not self.settings_state_handler: QMessageBox.critical(self, "Error", "Settings state handler not available."); return
        logging.debug("Opening settings dialog..."); current_data = self.settings_state_handler.get_all_settings()
        current_data['translation_engine'] = current_data.get('translation_engine_key')
        dialog = SettingsDialog(self, current_data)
        if dialog.exec_() == QDialog.Accepted:
            logging.debug("Settings dialog accepted. Applying via state handler...")
            updated_settings = dialog.get_updated_settings(); self.settings_state_handler.apply_settings(updated_settings)
            self.save_settings(); self.ui_manager.set_status("Settings Applied", 3000); logging.debug("Settings applied and saved.")
        else: logging.debug("Settings dialog cancelled."); self.ui_manager.set_status("Settings Cancelled", 2000)

    # --- OCR / Button / Checkbox Logic ---
    def trigger_single_ocr(self):
        # (Remains the same)
        if self.live_mode_handler.is_active(): logging.debug("Single OCR trigger skipped, Live Mode active."); self.ui_manager.set_status("Cannot capture: Live Mode active", 2000); return
        if self.ocr_handler.ocr_running: logging.warning("Single OCR trigger skipped, OCR running."); self.ui_manager.set_status("Cannot capture: OCR already running", 2000); return
        if self.ocr_handler.check_prerequisites(prompt_if_needed=True): self.ocr_handler.trigger_ocr()
        else: logging.warning("Single OCR trigger skipped, prereqs not met."); self.ui_manager.set_status("Cannot capture: Check prerequisites", 3000)

    def on_grab_button_clicked(self):
        # (Remains the same)
        live_cb = self.ui_manager.get_widget('live_mode_checkbox'); is_live_potentially_enabled = live_cb.isChecked() if live_cb else False
        if is_live_potentially_enabled:
            if self.live_mode_handler.is_active(): logging.info("Grab btn: Stopping live timer."); self.live_mode_handler.stop_timer()
            else: logging.info("Grab btn: Starting live timer."); self.live_mode_handler.start_timer()
        else: logging.info("Grab btn: Triggering single OCR."); self.trigger_single_ocr()

    # --- Renamed _update_ocr_button_states for clarity ---
    def _update_all_button_states(self):
        """Update Grab button, Live checkbox, and Retranslate controls based on current state."""
        can_run_ocr = self.ocr_handler.check_prerequisites(prompt_if_needed=False)
        is_live_timer_active = self.live_mode_handler.is_active()
        is_ocr_running = self.ocr_handler.ocr_running # Includes OCR and potential re-translation via OcrHandler state? No, need separate flag maybe? Let's assume OCR state is sufficient for now.
        is_retranslation_possible = bool(self.ocr_handler.get_last_ocr_text())

        live_cb = self.ui_manager.get_widget('live_mode_checkbox')
        is_live_potentially_enabled = live_cb.isChecked() if live_cb else False

        # --- Update Grab Button ---
        grab_enabled = False; grab_text = "Grab Text"; grab_tooltip = ""
        current_hotkey = self.settings_state_handler.get_value('hotkey', '')
        hotkey_display = f"({current_hotkey.replace('+', ' + ').title()})" if current_hotkey else ""
        if is_ocr_running: grab_text = "Working..."; grab_tooltip = "OCR in progress..."; grab_enabled = False
        elif not can_run_ocr: grab_text = "Grab Text"; grab_tooltip = "Prerequisites not met (Configure ⚙️)"; grab_enabled = False
        elif is_live_potentially_enabled:
            if is_live_timer_active: grab_text = "Stop Live"; grab_tooltip = "Click to stop periodic capture"; grab_enabled = True
            else: grab_text = "Start Live"; grab_tooltip = "Click to start periodic capture"; grab_enabled = True
        else: grab_text = "Grab Text"; grab_tooltip = f"Click for single capture {hotkey_display}"; grab_enabled = True
        self.ui_manager.set_grab_button_state(enabled=grab_enabled, text=grab_text, tooltip=grab_tooltip)

        # --- Update Live Mode Checkbox ---
        checkbox_enabled = can_run_ocr and not is_ocr_running
        checkbox_checked = is_live_potentially_enabled
        self.ui_manager.set_live_mode_checkbox_state(checked=checkbox_checked, enabled=checkbox_enabled, is_active=is_live_timer_active)

        # --- Update Retranslate Controls (NEW) ---
        # Enable only if OCR is possible, not currently running, and there's text to translate
        retranslate_enabled = can_run_ocr and not is_ocr_running and not is_live_timer_active and is_retranslation_possible
        self.ui_manager.set_retranslate_controls_enabled(retranslate_enabled)

    # --- Slots for Handler Signals ---
    @pyqtSlot(dict)
    def on_settings_changed(self, changed_settings: dict):
        """Handles updates when settings state changes."""
        logging.debug(f"MainWindow received settings changed: {changed_settings.keys()}")
        needs_button_update = False; needs_repaint = True
        if any(k in changed_settings for k in ['display_font', 'bg_color']): self.ui_manager.update_text_display_style()
        if 'is_locked' in changed_settings: self.apply_lock_state(changed_settings['is_locked'])
        if 'hotkey' in changed_settings:
            new_hotkey = changed_settings['hotkey']; logging.info(f"Hotkey changed to '{new_hotkey}'.")
            if hotkey_manager.update_active_hotkey(new_hotkey): logging.info("Hotkey listener updated.")
            else: logging.error("Failed to update hotkey."); QMessageBox.warning(self, "Hotkey Error", f"Could not apply hotkey '{new_hotkey}'.")
            needs_button_update = True
        if any(k in changed_settings for k in ['ocr_provider', 'google_credentials_path', 'ocrspace_api_key', 'deepl_api_key', 'translation_engine_key', 'ocr_language_code']):
            needs_button_update = True
        if needs_button_update: self._update_all_button_states() # Use renamed method
        if needs_repaint: self.update()

    @pyqtSlot(str, str)
    def on_ocr_done(self, ocr_text, translated_text):
        # (Status update added, otherwise same)
        self.ui_manager.set_text_display_visibility(True); logging.info("OCR results received.")
        if self.history_manager and ocr_text: self.history_manager.add_item(ocr_text, translated_text) # Add only if OCR text exists
        # HTML formatting...
        safe_ocr = html.escape(ocr_text or ""); safe_trans = translated_text or ""
        target_lang_code = self.settings_state_handler.get_value('target_language_code', 'N/A'); display_font = self.settings_state_handler.get_value('display_font', QFont())
        ocr_provider = self.settings_state_handler.get_value('ocr_provider', '?'); trans_engine_key = self.settings_state_handler.get_value('translation_engine_key', '?')
        lang = html.escape(target_lang_code.upper()); ocr_fmt = safe_ocr.replace('\n', '<br/>'); trans_fmt = safe_trans
        is_error = isinstance(safe_trans, str) and safe_trans.startswith("[") and "Error:" in safe_trans
        if not is_error: trans_fmt = html.escape(safe_trans).replace('\n', '<br/>')
        font_style = f"font-family:'{display_font.family()}'; font-size:{display_font.pointSize()}pt;"; err_style = "color:#A00;"; ok_style = "color:#000;"
        ocr_provider_name = config.AVAILABLE_OCR_PROVIDERS.get(ocr_provider, ocr_provider); trans_engine_name = config.AVAILABLE_ENGINES.get(trans_engine_key, trans_engine_key)
        html_out = f"""<div style="margin-bottom:10px;"><b style="color:#333;">--- OCR ({ocr_provider_name}) ---</b><br/><div style="margin-left:5px; {font_style} color:#000;">{ocr_fmt if ocr_fmt else '<i style="color:#777;">No text detected.</i>'}</div></div><div><b style="color:#333;">--- Translation ({trans_engine_name} / {lang}) ---</b><br/><div style="margin-left:5px; {font_style} {err_style if is_error else ok_style}">{trans_fmt if trans_fmt else ('<i style="color:#777;">N/A</i>' if not ocr_fmt else '<i style="color:#777;">No translation.</i>')}</div></div>"""
        self.ui_manager.update_text_display_content(html_out, Qt.AlignLeft); self.ui_manager.set_status("OCR Complete", 3000)
        # Update buttons (enables retranslate if OCR was successful)
        self._update_all_button_states()

    @pyqtSlot(str)
    def on_ocr_error(self, error_msg):
        # (Status update added, otherwise same)
        self.ui_manager.set_text_display_visibility(True); logging.error(f"MainWindow received error signal: {error_msg}")
        display_font = self.settings_state_handler.get_value('display_font', QFont())
        font_style = f"font-family:'{display_font.family()}'; font-size:{display_font.pointSize()}pt;"; err_html = f"""<p style="color:#A00;font-weight:bold;">--- Error ---</p><p style="color:#A00; {font_style}">{html.escape(error_msg)}</p>"""
        self.ui_manager.update_text_display_content(err_html, Qt.AlignLeft); self.ui_manager.set_status(f"Error: {error_msg[:60]}...", 5000)
        # Update buttons (retranslate might become disabled if last OCR text was cleared)
        self._update_all_button_states()

    @pyqtSlot(bool)
    def on_ocr_state_changed(self, is_running):
        """Slot connected to OcrHandler.stateChanged signal."""
        logging.debug(f"MainWindow received OCR state change: {'Running' if is_running else 'Finished'}")
        if is_running: self.ui_manager.set_status("OCR Running..."); self.ui_manager.show_ocr_active_feedback()
        else: self.ui_manager.clear_status(); self.ui_manager.hide_ocr_active_feedback()
        self._update_all_button_states() # Use renamed method
        if not is_running: self.ui_manager.set_text_display_visibility(True)

    @pyqtSlot()
    def on_live_mode_timer_state_changed(self): # Renamed slot
        logging.debug("MainWindow received Live Mode timer state change signal.")
        if self.live_mode_handler.is_active(): self.ui_manager.set_status("Live Mode Active")
        else: self.ui_manager.set_status("Live Mode Stopped", 3000)
        self._update_all_button_states() # Use renamed method

    @pyqtSlot(int)
    def on_live_mode_checkbox_changed(self, state):
        # (Remains the same)
        is_checked = (state == Qt.Checked); self.live_mode_potentially_enabled = is_checked
        logging.info(f"Live mode potentially enabled set to: {is_checked}")
        if not is_checked:
            if self.live_mode_handler.is_active(): logging.info("Live mode checkbox unchecked, stopping timer..."); self.live_mode_handler.stop_timer()
            else: self._update_all_button_states()
        else: self._update_all_button_states()

    # --- Retranslate Slots (NEW) ---
    @pyqtSlot()
    def on_retranslate_clicked(self):
        """Handles clicks on the 'Translate Again' button."""
        last_text = self.ocr_handler.get_last_ocr_text()
        new_lang_code = self.ui_manager.get_retranslate_language_code()

        if not last_text:
             self.ui_manager.set_status("No previous text to re-translate", 3000)
             logging.warning("Re-translate clicked, but no text stored.")
             return
        if not new_lang_code:
             self.ui_manager.set_status("Please select a language to translate to", 3000)
             logging.warning("Re-translate clicked, but no language selected.")
             return

        # Disable controls and set status
        self.ui_manager.set_retranslate_controls_enabled(False)
        self.ui_manager.set_status(f"Re-translating to {new_lang_code}...")

        # Request retranslation via OcrHandler (which starts TranslationWorker)
        success = self.ocr_handler.request_retranslation(new_lang_code)
        if not success:
            # Re-enable controls if starting failed immediately
            self.ui_manager.set_retranslate_controls_enabled(True)
            self.ui_manager.set_status("Failed to start re-translation", 3000)


    @pyqtSlot(str, str)
    def on_retranslation_done(self, original_text, new_translated_text):
        """Handles successful result from TranslationWorker."""
        logging.info("Re-translation successful.")
        self.ui_manager.set_status("Re-translation Complete", 3000)

        # Update the text display area (similar format to on_ocr_done)
        safe_ocr = html.escape(original_text or "") # Use original text passed back
        safe_trans = new_translated_text or ""
        # Need the language code it was just translated *to*
        new_lang_code = self.ui_manager.get_retranslate_language_code() or "?"
        lang = html.escape(new_lang_code.upper())

        display_font = self.settings_state_handler.get_value('display_font', QFont())
        ocr_provider = self.settings_state_handler.get_value('ocr_provider', '?') # Keep original provider?
        trans_engine_key = self.settings_state_handler.get_value('translation_engine_key', '?')

        ocr_fmt = safe_ocr.replace('\n', '<br/>'); trans_fmt = safe_trans
        is_error = isinstance(safe_trans, str) and safe_trans.startswith("[") and "Error:" in safe_trans
        if not is_error: trans_fmt = html.escape(safe_trans).replace('\n', '<br/>')
        font_style = f"font-family:'{display_font.family()}'; font-size:{display_font.pointSize()}pt;"; err_style = "color:#A00;"; ok_style = "color:#000;"
        ocr_provider_name = config.AVAILABLE_OCR_PROVIDERS.get(ocr_provider, ocr_provider); trans_engine_name = config.AVAILABLE_ENGINES.get(trans_engine_key, trans_engine_key)

        html_out = f"""
           <div style="margin-bottom:10px;"><b style="color:#333;">--- Original OCR ({ocr_provider_name}) ---</b><br/><div style="margin-left:5px; {font_style} color:#000;">{ocr_fmt if ocr_fmt else '<i style="color:#777;">No text detected.</i>'}</div></div>
           <div><b style="color:#333;">--- Re-Translation ({trans_engine_name} / {lang}) ---</b><br/><div style="margin-left:5px; {font_style} {err_style if is_error else ok_style}">{trans_fmt if trans_fmt else ('<i style="color:#777;">N/A</i>' if not ocr_fmt else '<i style="color:#777;">No translation.</i>')}</div></div>"""
        self.ui_manager.update_text_display_content(html_out, Qt.AlignLeft)

        # Re-enable controls
        self._update_all_button_states() # This handles re-enabling based on state

    @pyqtSlot(str)
    def on_retranslation_error(self, error_msg):
        """Handles error result from TranslationWorker."""
        logging.error(f"Re-translation failed: {error_msg}")
        self.ui_manager.set_status(f"Re-translation Error: {error_msg[:50]}...", 5000)
        # Optionally update text display with error? For now, just status bar.
        # Re-enable controls
        self._update_all_button_states()
    # --- End Retranslate Slots ---

    def _update_ui_from_settings(self):
         """Update UI elements based on initial settings state"""
         logging.debug("Syncing UI from initial settings state...")
         self.apply_lock_state(self.settings_state_handler.get_value('is_locked', False))
         self.ui_manager.update_text_display_style()
         self._update_all_button_states() # Use renamed method
         self.update()

    # --- Window Interaction Events ---
    def resizeEvent(self, event): self.ui_manager.handle_resize_event(event); super().resizeEvent(event)
    def paintEvent(self, event): self.ui_manager.handle_paint_event(event)
    def mousePressEvent(self, event): self.interaction_handler.mousePressEvent(event)
    def mouseMoveEvent(self, event): self.interaction_handler.mouseMoveEvent(event)
    def mouseReleaseEvent(self, event): self.interaction_handler.mouseReleaseEvent(event)

    # --- Application Lifecycle ---
    def closeEvent(self, event):
        logging.info("Close event received. Cleaning up..."); self.live_mode_handler.stop(); self.ocr_handler.stop_processes()
        hotkey_manager.stop_hotkey_listener(); self.save_settings(); logging.info("Cleanup finished. Exiting application.")
        event.accept(); app_instance = QApplication.instance();
        if app_instance: app_instance.quit()