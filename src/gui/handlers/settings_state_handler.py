# filename: src/gui/handlers/settings_state_handler.py
import logging
import os
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QFont, QColor

try:
    from src import config
except ImportError:
    logging.critical("SettingsStateHandler: Failed to import config.")
    # Define fallback config if necessary
    class ConfigFallback:
        DEFAULT_OCR_PROVIDER="google_vision"; AVAILABLE_OCR_PROVIDERS={}
        DEFAULT_OCR_LANGUAGE="eng"; OCR_SPACE_LANGUAGES={}
        DEFAULT_TRANSLATION_ENGINE="google_cloud_v3"; AVAILABLE_ENGINES={}
        DEFAULT_TARGET_LANGUAGE_CODE="en"
        DEFAULT_FONT_SIZE=18; DEFAULT_BG_COLOR=QColor(0,0,0,150)
        DEFAULT_OCR_INTERVAL_SECONDS=5; DEFAULT_HOTKEY='ctrl+shift+g'
    config = ConfigFallback()


class SettingsStateHandler(QObject):
    """Holds and manages the application's current settings state."""

    # Signal emitted when settings are changed via apply_settings.
    # The dictionary contains only the keys/values that were changed.
    settingsChanged = pyqtSignal(dict)

    def __init__(self, initial_settings: dict):
        super().__init__()
        self._settings = {}
        self._is_google_credentials_valid = False
        self._is_ocrspace_key_set = False
        self._is_deepl_key_set = False

        # Initialize with provided settings, applying defaults and validation
        self._initialize_settings(initial_settings)
        self.update_prerequisite_flags() # Calculate initial flags

    def _initialize_settings(self, settings_dict):
        """Sets initial settings, applying defaults and validation."""
        # Use get_value for applying defaults during init
        self._settings['ocr_provider'] = settings_dict.get('ocr_provider', config.DEFAULT_OCR_PROVIDER)
        if self._settings['ocr_provider'] not in config.AVAILABLE_OCR_PROVIDERS:
            self._settings['ocr_provider'] = config.DEFAULT_OCR_PROVIDER

        self._settings['google_credentials_path'] = settings_dict.get('google_credentials_path')
        self._settings['ocrspace_api_key'] = settings_dict.get('ocrspace_api_key')
        self._settings['ocr_language_code'] = settings_dict.get('ocr_language_code', config.DEFAULT_OCR_LANGUAGE)
        # Basic validation
        if self.get_value('ocr_provider') == 'ocr_space' and self.get_value('ocr_language_code') not in config.OCR_SPACE_LANGUAGES:
             self._settings['ocr_language_code'] = config.DEFAULT_OCR_LANGUAGE

        self._settings['deepl_api_key'] = settings_dict.get('deepl_api_key')
        self._settings['target_language_code'] = settings_dict.get('target_language_code', config.DEFAULT_TARGET_LANGUAGE_CODE)
        self._settings['translation_engine_key'] = settings_dict.get('translation_engine_key', config.DEFAULT_TRANSLATION_ENGINE)
        if self._settings['translation_engine_key'] not in config.AVAILABLE_ENGINES:
            self._settings['translation_engine_key'] = config.DEFAULT_TRANSLATION_ENGINE

        # UI / Behavior
        loaded_font = settings_dict.get('display_font')
        self._settings['display_font'] = loaded_font if isinstance(loaded_font, QFont) else QFont()

        loaded_interval = settings_dict.get('ocr_interval', config.DEFAULT_OCR_INTERVAL_SECONDS)
        self._settings['ocr_interval'] = loaded_interval if isinstance(loaded_interval, int) and loaded_interval > 0 else config.DEFAULT_OCR_INTERVAL_SECONDS

        self._settings['is_locked'] = settings_dict.get('is_locked', False)
        loaded_hotkey = settings_dict.get('hotkey', config.DEFAULT_HOTKEY)
        self._settings['hotkey'] = loaded_hotkey if isinstance(loaded_hotkey, str) and loaded_hotkey else config.DEFAULT_HOTKEY

        loaded_bg_color = settings_dict.get('bg_color', QColor(config.DEFAULT_BG_COLOR))
        if not isinstance(loaded_bg_color, QColor) or not loaded_bg_color.isValid():
            loaded_bg_color = QColor(config.DEFAULT_BG_COLOR)
        # Store the combined color object
        self._settings['bg_color'] = loaded_bg_color

        logging.debug("SettingsStateHandler initialized with settings.")

    def get_value(self, key: str, default: any = None) -> any:
        """Gets the current value of a setting."""
        return self._settings.get(key, default)

    def get_all_settings(self) -> dict:
        """Returns a copy of the current settings dictionary."""
        return self._settings.copy()

    def apply_settings(self, updated_settings: dict):
        """
        Applies updates to the settings state and emits a signal with changes.
        Performs validation before applying.
        """
        changed_values = {}
        keys_to_update_flags = []

        for key, new_value in updated_settings.items():
            # Basic type/value validation could happen here if desired
            # e.g., ensure interval is int > 0

            # Special handling for complex types if needed (e.g., QFont, QColor)
            if key == 'bg_alpha': # Handle alpha specifically if passed separately
                current_color = self.get_value('bg_color', QColor(config.DEFAULT_BG_COLOR))
                if isinstance(new_value, int) and 0 <= new_value <= 255:
                    new_color = QColor(current_color.red(), current_color.green(), current_color.blue(), new_value)
                    # Update the actual 'bg_color' setting
                    key_to_set = 'bg_color'
                    value_to_set = new_color
                else:
                    logging.warning(f"Invalid bg_alpha value received: {new_value}. Skipping.")
                    continue # Skip this key
            else:
                 key_to_set = key
                 value_to_set = new_value

            # Check if value actually changed
            current_value = self._settings.get(key_to_set)
            if current_value != value_to_set:
                self._settings[key_to_set] = value_to_set
                changed_values[key_to_set] = value_to_set
                logging.debug(f"Setting '{key_to_set}' changed to: {value_to_set}")
                # Track keys that require prerequisite flag updates
                if key_to_set in ['google_credentials_path', 'ocrspace_api_key', 'deepl_api_key']:
                    keys_to_update_flags.append(key_to_set)

        # Update prerequisite flags if relevant keys changed
        if keys_to_update_flags:
            logging.debug(f"Prerequisite-related keys changed ({keys_to_update_flags}), updating flags...")
            self.update_prerequisite_flags()
            # Add flags themselves to changed_values if their state changes? Optional.

        # Emit signal only if something actually changed
        if changed_values:
            logging.info(f"Settings changed: {list(changed_values.keys())}")
            self.settingsChanged.emit(changed_values)

    def update_prerequisite_flags(self):
        """Updates internal flags based on current credentials/keys."""
        gc_path = self.get_value('google_credentials_path')
        ocr_key = self.get_value('ocrspace_api_key')
        dl_key = self.get_value('deepl_api_key')

        old_google = self._is_google_credentials_valid
        old_ocr = self._is_ocrspace_key_set
        old_deepl = self._is_deepl_key_set

        self._is_google_credentials_valid = bool(isinstance(gc_path, str) and gc_path and os.path.exists(gc_path))
        self._is_ocrspace_key_set = bool(isinstance(ocr_key, str) and ocr_key)
        self._is_deepl_key_set = bool(isinstance(dl_key, str) and dl_key)

        # Log if flags changed
        if old_google != self._is_google_credentials_valid: logging.info(f"Google credentials valid state changed: {self._is_google_credentials_valid}")
        if old_ocr != self._is_ocrspace_key_set: logging.info(f"OCR.space key set state changed: {self._is_ocrspace_key_set}")
        if old_deepl != self._is_deepl_key_set: logging.info(f"DeepL key set state changed: {self._is_deepl_key_set}")

    # --- Prerequisite Flag Getters ---
    def is_google_credentials_valid(self) -> bool:
        return self._is_google_credentials_valid

    def is_ocrspace_key_set(self) -> bool:
        return self._is_ocrspace_key_set

    def is_deepl_key_set(self) -> bool:
        return self._is_deepl_key_set