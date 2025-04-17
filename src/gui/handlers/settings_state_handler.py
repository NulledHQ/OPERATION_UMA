# filename: src/gui/handlers/settings_state_handler.py
import logging
import os
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QFont, QColor

try:
    from src import config
except ImportError:
    logging.critical("SettingsStateHandler: Failed to import config.")
    class Cfg: # Define fallback config
        DEFAULT_OCR_PROVIDER="google_vision"; AVAILABLE_OCR_PROVIDERS={}
        DEFAULT_OCR_LANGUAGE="eng"; OCR_SPACE_LANGUAGES={}; DEFAULT_OCR_SPACE_ENGINE_NUMBER=1; OCR_SPACE_ENGINES={}
        DEFAULT_OCR_SPACE_SCALE=False; DEFAULT_OCR_SPACE_DETECT_ORIENTATION=False
        DEFAULT_TESSERACT_CMD_PATH=None; DEFAULT_TESSERACT_LANGUAGE="eng"; TESSERACT_LANGUAGES={}
        DEFAULT_TRANSLATION_ENGINE="google_cloud_v3"; AVAILABLE_ENGINES={}
        DEFAULT_TARGET_LANGUAGE_CODE="en"; DEFAULT_FONT_SIZE=18; DEFAULT_BG_COLOR=QColor(0,0,0,150)
        DEFAULT_OCR_INTERVAL_SECONDS=5; DEFAULT_HOTKEY='ctrl+shift+g'; DEFAULT_SAVE_OCR_IMAGES=False; DEFAULT_OCR_IMAGE_SAVE_PATH=None
    config = Cfg()


class SettingsStateHandler(QObject):
    """Holds and manages the application's current settings state."""
    settingsChanged = pyqtSignal(dict)

    def __init__(self, initial_settings: dict):
        super().__init__()
        self._settings = {}
        self._is_google_credentials_valid = False
        self._is_ocrspace_key_set = False
        self._is_deepl_key_set = False

        self._initialize_settings(initial_settings)
        self.update_prerequisite_flags()

    def _initialize_settings(self, settings_dict):
        """Sets initial settings, applying defaults and validation."""
        # OCR Provider
        self._settings['ocr_provider'] = settings_dict.get('ocr_provider', config.DEFAULT_OCR_PROVIDER)
        if self._settings['ocr_provider'] not in config.AVAILABLE_OCR_PROVIDERS:
            self._settings['ocr_provider'] = config.DEFAULT_OCR_PROVIDER

        self._settings['google_credentials_path'] = settings_dict.get('google_credentials_path')
        self._settings['ocrspace_api_key'] = settings_dict.get('ocrspace_api_key')
        self._settings['ocr_language_code'] = settings_dict.get('ocr_language_code', config.DEFAULT_OCR_LANGUAGE)
        if self.get_value('ocr_provider') == 'ocr_space' and self.get_value('ocr_language_code') not in config.OCR_SPACE_LANGUAGES:
            self._settings['ocr_language_code'] = config.DEFAULT_OCR_LANGUAGE

        # OCR.space specific
        self._settings['ocr_space_engine'] = settings_dict.get('ocr_space_engine', config.DEFAULT_OCR_SPACE_ENGINE_NUMBER)
        self._settings['ocr_space_scale'] = settings_dict.get('ocr_space_scale', config.DEFAULT_OCR_SPACE_SCALE)
        self._settings['ocr_space_detect_orientation'] = settings_dict.get('ocr_space_detect_orientation', config.DEFAULT_OCR_SPACE_DETECT_ORIENTATION)

        # Tesseract specific
        self._settings['tesseract_cmd_path'] = settings_dict.get('tesseract_cmd_path', config.DEFAULT_TESSERACT_CMD_PATH)
        self._settings['tesseract_language_code'] = settings_dict.get('tesseract_language_code', config.DEFAULT_TESSERACT_LANGUAGE)
        if self.get_value('ocr_provider') == 'tesseract' and self.get_value('tesseract_language_code') not in config.TESSERACT_LANGUAGES:
            self._settings['tesseract_language_code'] = config.DEFAULT_TESSERACT_LANGUAGE

        # Translation
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
        self._settings['bg_color'] = loaded_bg_color if isinstance(loaded_bg_color, QColor) and loaded_bg_color.isValid() else QColor(config.DEFAULT_BG_COLOR)

        # Training Data Saving Settings
        self._settings['save_ocr_images'] = settings_dict.get('save_ocr_images', config.DEFAULT_SAVE_OCR_IMAGES)
        self._settings['ocr_image_save_path'] = settings_dict.get('ocr_image_save_path', config.DEFAULT_OCR_IMAGE_SAVE_PATH)

        # --- Ensure correct types after loading ---
        bool_keys = ['ocr_space_scale', 'ocr_space_detect_orientation', 'is_locked', 'save_ocr_images']
        for key in bool_keys:
            value = self._settings.get(key)
            if isinstance(value, str): self._settings[key] = value.lower() == 'true'
            elif not isinstance(value, bool):
                default_value_key = f"DEFAULT_{key.upper()}"
                default_value = getattr(config, default_value_key, False)
                logging.warning(f"Invalid type for '{key}' ({type(value)}), using default: {default_value}")
                self._settings[key] = default_value

        engine_val = self._settings.get('ocr_space_engine')
        try:
            self._settings['ocr_space_engine'] = int(engine_val)
            if self._settings['ocr_space_engine'] not in config.OCR_SPACE_ENGINES:
                raise ValueError("Invalid engine number")
        except (ValueError, TypeError):
            logging.warning(f"Invalid ocr_space_engine: {engine_val}. Using default.")
            self._settings['ocr_space_engine'] = config.DEFAULT_OCR_SPACE_ENGINE_NUMBER

        path_keys = ['tesseract_cmd_path', 'ocr_image_save_path', 'google_credentials_path'] # Added google_credentials_path
        for key in path_keys:
            # Ensure None if empty or invalid type, but allow valid strings
            current_val = self._settings.get(key)
            if current_val == "":
                self._settings[key] = None
            elif not isinstance(current_val, (str, type(None))):
                 logging.warning(f"Invalid type for path '{key}' ({type(current_val)}), setting to None.")
                 self._settings[key] = None

        logging.debug("SettingsStateHandler initialized with settings.")

    def get_value(self, key: str, default: any = None) -> any:
        return self._settings.get(key, default)

    def get_all_settings(self) -> dict:
        return self._settings.copy()

    def apply_settings(self, updated_settings: dict):
        changed_values = {}
        keys_to_update_flags = []

        for key, new_value in updated_settings.items():
            key_to_set = key
            value_to_set = new_value

            # Handle specific key mappings or transformations
            if key == 'bg_alpha':
                current_color = self.get_value('bg_color', QColor(config.DEFAULT_BG_COLOR))
                if isinstance(new_value, int) and 0 <= new_value <= 255:
                    value_to_set = QColor(current_color.red(), current_color.green(), current_color.blue(), new_value)
                    key_to_set = 'bg_color'
                else:
                    logging.warning(f"Invalid bg_alpha: {new_value}. Skipping.")
                    continue
            elif key == 'translation_engine': # Map dialog key back to state key
                key_to_set = 'translation_engine_key'

            # Type validation/conversion for specific keys
            bool_keys = ['ocr_space_scale', 'ocr_space_detect_orientation', 'is_locked', 'save_ocr_images']
            if key_to_set in bool_keys:
                if not isinstance(value_to_set, bool):
                    logging.warning(f"Converting non-boolean for '{key_to_set}'")
                    value_to_set = bool(value_to_set)

            if key_to_set == 'ocr_space_engine':
                try:
                    value_to_set = int(value_to_set)
                    if value_to_set not in config.OCR_SPACE_ENGINES:
                        raise ValueError("Invalid engine number")
                except (ValueError, TypeError):
                    logging.warning(f"Invalid ocr_space_engine: {value_to_set}. Using default.")
                    value_to_set = config.DEFAULT_OCR_SPACE_ENGINE_NUMBER

            path_keys = ['tesseract_cmd_path', 'ocr_image_save_path', 'google_credentials_path']
            if key_to_set in path_keys and value_to_set == "":
                value_to_set = None # Empty path means None

            # Check if value actually changed
            current_value = self._settings.get(key_to_set)
            if current_value != value_to_set:
                self._settings[key_to_set] = value_to_set
                changed_values[key_to_set] = value_to_set
                logging.debug(f"Setting '{key_to_set}' changed to: {value_to_set}")
                if key_to_set in ['google_credentials_path', 'ocrspace_api_key', 'deepl_api_key', 'tesseract_cmd_path']:
                    keys_to_update_flags.append(key_to_set)

        if keys_to_update_flags:
            logging.debug(f"Prerequisite-related keys changed, updating flags...")
            self.update_prerequisite_flags()

        if changed_values:
            logging.info(f"Settings changed: {list(changed_values.keys())}")
            self.settingsChanged.emit(changed_values)

    def update_prerequisite_flags(self):
        gc_path = self.get_value('google_credentials_path')
        ocr_key = self.get_value('ocrspace_api_key')
        dl_key = self.get_value('deepl_api_key')

        old_google = self._is_google_credentials_valid
        old_ocr = self._is_ocrspace_key_set
        old_deepl = self._is_deepl_key_set

        self._is_google_credentials_valid = bool(isinstance(gc_path, str) and gc_path and os.path.exists(gc_path))
        self._is_ocrspace_key_set = bool(isinstance(ocr_key, str) and ocr_key)
        self._is_deepl_key_set = bool(isinstance(dl_key, str) and dl_key)

        if old_google != self._is_google_credentials_valid: logging.info(f"Google credentials valid: {self._is_google_credentials_valid}")
        if old_ocr != self._is_ocrspace_key_set: logging.info(f"OCR.space key set: {self._is_ocrspace_key_set}")
        if old_deepl != self._is_deepl_key_set: logging.info(f"DeepL key set: {self._is_deepl_key_set}")

    # --- Prerequisite Flag Getters ---
    def is_google_credentials_valid(self) -> bool: return self._is_google_credentials_valid
    def is_ocrspace_key_set(self) -> bool: return self._is_ocrspace_key_set
    def is_deepl_key_set(self) -> bool: return self._is_deepl_key_set