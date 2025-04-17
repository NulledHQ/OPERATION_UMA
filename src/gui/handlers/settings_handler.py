# src/gui/handlers/settings_handler.py
import logging
import os

# PyQt5 Imports
from PyQt5.QtCore import QObject, pyqtSignal, QByteArray
from PyQt5.QtWidgets import QMessageBox, QDialog
from PyQt5.QtGui import QFont, QColor

# Core and GUI components
from src import config # Assuming direct import works
from src.core.settings_manager import SettingsManager # Should exist
from src.core.history_manager import HistoryManager # Should exist
from src.gui.widgets.settings_dialog import SettingsDialog # Should exist
from src.core import hotkey_manager # Needed for hotkey update


class SettingsHandler(QObject):
    """Handles loading, applying, saving settings and settings dialog interaction."""

    # Signal emitted when settings have been changed and applied via the dialog
    # The dictionary contains the *updated* settings dictionary
    settingsApplied = pyqtSignal(dict)

    def __init__(self, window, settings_manager: SettingsManager, history_manager: HistoryManager):
        """
        Args:
            window: The main window instance (e.g., MainWindow).
            settings_manager: The core SettingsManager instance.
            history_manager: The core HistoryManager instance.
        """
        super().__init__()
        self.window = window
        self.settings_manager = settings_manager
        self.history_manager = history_manager # Store ref if settings dialog needs it

        # Store current settings state locally within the handler
        # Initialize with defaults, will be overwritten by apply_initial_settings
        self.current_settings = {
            'ocr_provider': config.DEFAULT_OCR_PROVIDER,
            'google_credentials_path': None,
            'ocrspace_api_key': None,
            'ocr_language_code': config.DEFAULT_OCR_LANGUAGE,
            'deepl_api_key': None,
            'target_language_code': config.DEFAULT_TARGET_LANGUAGE_CODE,
            'translation_engine_key': config.DEFAULT_TRANSLATION_ENGINE,
            'display_font': QFont(),
            'ocr_interval': config.DEFAULT_OCR_INTERVAL_SECONDS,
            'bg_color': QColor(config.DEFAULT_BG_COLOR), # Store the QColor object
            'is_locked': False,
            'hotkey': config.DEFAULT_HOTKEY,
        }

    def apply_initial_settings(self, initial_settings_dict: dict):
        """Applies the initially loaded settings to the window and stores them."""
        logging.debug("SettingsHandler applying initial settings...")
        self._apply_settings_to_window(initial_settings_dict)
        # Store the initial settings state
        self.current_settings = initial_settings_dict.copy() # Work with a copy

    def _apply_settings_to_window(self, settings_to_apply: dict):
        """Applies a dictionary of settings to the main window's attributes/styles."""
        logging.debug("Applying settings dictionary to window attributes...")
        changed_keys = {} # Track which keys actually changed

        # --- Apply UI / Behavior Settings ---
        old_font = self.current_settings.get('display_font')
        new_font = settings_to_apply.get('display_font', old_font)
        if isinstance(new_font, QFont) and new_font != old_font:
            self.window.display_font = new_font # Assuming MainWindow still holds these direct attrs
            changed_keys['display_font'] = new_font
            if hasattr(self.window, '_update_text_display_style'):
                 self.window._update_text_display_style() # Trigger style update

        old_interval = self.current_settings.get('ocr_interval')
        new_interval = settings_to_apply.get('ocr_interval', old_interval)
        if isinstance(new_interval, int) and new_interval > 0 and new_interval != old_interval:
            self.window.ocr_interval = new_interval
            changed_keys['ocr_interval'] = new_interval
            # Update live mode timer if it exists and is active
            if hasattr(self.window, 'is_live_mode') and self.window.is_live_mode and hasattr(self.window, 'live_mode_timer'):
                 self.window.live_mode_timer.setInterval(max(1000, new_interval * 1000))
                 logging.info(f"Live mode interval updated to {new_interval}s")

        old_color = self.current_settings.get('bg_color')
        new_color = settings_to_apply.get('bg_color', old_color) # This should be the QColor with correct alpha
        if isinstance(new_color, QColor) and new_color.isValid() and new_color != old_color:
            # Apply alpha to window's text area, keep frame color separate
            self.window.textarea_alpha = new_color.alpha()
            # Frame color (self.window.bg_color) might remain fixed (e.g., black)
            # Re-apply style which uses textarea_alpha
            if hasattr(self.window, '_update_text_display_style'):
                 self.window._update_text_display_style()
            self.window.update() # Trigger repaint for potential window bg change if applicable
            changed_keys['bg_color'] = new_color # Store the combined color

        old_locked = self.current_settings.get('is_locked', False)
        new_locked = settings_to_apply.get('is_locked', old_locked)
        if isinstance(new_locked, bool) and new_locked != old_locked:
            self.window.is_locked = new_locked
            changed_keys['is_locked'] = new_locked
            # Apply visual lock state (e.g., opacity)
            if hasattr(self.window, 'apply_initial_lock_state'): # Reuse this method
                 self.window.apply_initial_lock_state()

        # --- Apply OCR/Translation settings directly to window attributes ---
        # (MainWindow/OcrHandler will read these attributes)
        keys_to_update = [
            'ocr_provider', 'google_credentials_path', 'ocrspace_api_key',
            'ocr_language_code', 'deepl_api_key', 'target_language_code',
            'translation_engine_key', 'hotkey'
        ]
        for key in keys_to_update:
            old_value = self.current_settings.get(key)
            new_value = settings_to_apply.get(key, old_value) # Get new value or keep old if missing
            # Update if the value exists in the input dict and is different, or if it's None
            if key in settings_to_apply and new_value != old_value:
                 setattr(self.window, key, new_value) # Set attribute on MainWindow instance
                 changed_keys[key] = new_value
                 logging.debug(f"Applied setting '{key}' = {new_value}")

        # --- Update Prerequisite Flags ---
        # OcrHandler/MainWindow should call this after settings are applied
        if hasattr(self.window, '_update_prerequisite_state_flags'):
            self.window._update_prerequisite_state_flags()

        # --- Update Hotkey Listener ---
        if 'hotkey' in changed_keys:
            old_hotkey_val = self.current_settings.get('hotkey') # Get previous value before overwrite
            new_hotkey_val = changed_keys['hotkey']
            if new_hotkey_val != old_hotkey_val:
                 logging.info(f"Hotkey changed from '{old_hotkey_val}' to '{new_hotkey_val}'. Attempting dynamic update.")
                 if hotkey_manager.update_active_hotkey(new_hotkey_val):
                     logging.info("Hotkey updated successfully in listener.")
                 else:
                     logging.error("Failed to dynamically update hotkey in listener.")
                     QMessageBox.warning(self.window, "Hotkey Update Failed", f"Could not dynamically apply the new hotkey '{new_hotkey_val}'.")

        # Update internal state *after* applying changes and handling hotkey
        self.current_settings.update(changed_keys)

        # Emit signal with only the keys that actually changed and their new values
        if changed_keys:
            self.settingsApplied.emit(changed_keys)
            logging.debug(f"Emitted settingsApplied signal with changed keys: {list(changed_keys.keys())}")

    def open_settings_dialog(self):
        """Opens the settings configuration dialog."""
        if not SettingsDialog:
             QMessageBox.critical(self.window, "Error", "SettingsDialog component not loaded correctly.")
             return
        logging.debug("SettingsHandler opening settings dialog...")

        # Prepare current data FOR the dialog from internal state
        dialog_data = self.current_settings.copy()
        # Ensure complex types are correct for the dialog
        dialog_data['display_font'] = dialog_data.get('display_font', QFont())
        # Pass the color object directly (dialog handles alpha slider separately)
        dialog_data['bg_color'] = dialog_data.get('bg_color', QColor(config.DEFAULT_BG_COLOR))

        # Pass history manager reference or necessary methods if dialog needs them
        # For now, assume dialog uses parent methods which MainWindow still has
        dialog = SettingsDialog(self.window, dialog_data) # Parent to main window

        if dialog.exec_() == QDialog.Accepted:
            logging.debug("Settings dialog accepted. Applying changes...")
            updated_settings_from_dialog = dialog.get_updated_settings()

            # Prepare a dictionary suitable for _apply_settings_to_window
            settings_to_apply = {}
            # Copy most settings directly
            for key, value in updated_settings_from_dialog.items():
                 if key not in ['bg_alpha', 'bg_color']: # Exclude alpha/color initially
                      settings_to_apply[key] = value

            # Handle color/alpha separately
            new_alpha = updated_settings_from_dialog.get('bg_alpha')
            if isinstance(new_alpha, int):
                 # Combine base color RGB (e.g., black from window.bg_color) with new alpha
                 base_color = self.window.bg_color if hasattr(self.window, 'bg_color') else QColor(0,0,0)
                 color_to_apply = QColor(base_color.red(), base_color.green(), base_color.blue(), new_alpha)
                 settings_to_apply['bg_color'] = color_to_apply # Store the combined QColor

            # Apply the collected changes
            self._apply_settings_to_window(settings_to_apply)

            # Update button tooltips/states in main window *after* applying
            if hasattr(self.window, '_update_ocr_button_tooltip'):
                self.window._update_ocr_button_tooltip()
            # Let the stateChanged signal handle enable/disable state

            # Save settings immediately after dialog OK
            self.save_current_settings()
            logging.debug("Settings applied and saved by SettingsHandler.")
        else:
            logging.debug("Settings dialog cancelled.")

    def save_current_settings(self):
        """Saves the current application state via SettingsManager."""
        logging.debug("SettingsHandler saving current settings...")
        if not self.settings_manager:
            logging.error("Cannot save settings: SettingsManager not available.")
            return

        # Prepare data for saving (ensure types are correct for QSettings)
        settings_to_save = self.current_settings.copy()

        # Get geometry from window
        window_geometry = self.window.saveGeometry() if hasattr(self.window, 'saveGeometry') else None

        # Call the manager's save method
        self.settings_manager.save_all_settings(settings_to_save, window_geometry)

    def save_settings_on_exit(self):
        """Convenience method for saving settings during application close."""
        self.save_current_settings()

    def get_setting(self, key: str, default: any = None) -> any:
        """Retrieves a current setting value stored by the handler."""
        return self.current_settings.get(key, default)

    def is_locked(self) -> bool:
        """Returns the current lock state."""
        return self.get_setting('is_locked', False)