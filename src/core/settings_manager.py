# src/core/settings_manager.py
import logging
import os
from PyQt5.QtCore import QSettings, QByteArray, QStandardPaths, QCoreApplication
from PyQt5.QtGui import QFont, QColor

from src import config

class SettingsManager:
    """Handles loading and saving application settings using QSettings."""

    def __init__(self):
        """Initializes QSettings."""
        if not QCoreApplication.organizationName():
            QCoreApplication.setOrganizationName(config.SETTINGS_ORG)
        if not QCoreApplication.applicationName():
            QCoreApplication.setApplicationName(config.SETTINGS_APP)
        self.settings = QSettings(config.SETTINGS_ORG, config.SETTINGS_APP)
        logging.debug(f"SettingsManager initialized. Backend: {self.settings.fileName()}")

    def load_all_settings(self) -> dict:
        """Loads all relevant settings from QSettings into a dictionary."""
        logging.debug("Loading all settings via SettingsManager...")
        loaded_settings = {}

        # OCR Provider Settings
        loaded_settings['ocr_provider'] = self.settings.value(config.SETTINGS_OCR_PROVIDER_KEY, config.DEFAULT_OCR_PROVIDER)
        if loaded_settings['ocr_provider'] not in config.AVAILABLE_OCR_PROVIDERS:
            logging.warning(f"Saved OCR provider '{loaded_settings['ocr_provider']}' not found. Reverting.")
            loaded_settings['ocr_provider'] = config.DEFAULT_OCR_PROVIDER

        loaded_settings['google_credentials_path'] = self.settings.value(config.SETTINGS_GOOGLE_CREDENTIALS_PATH_KEY, None)
        loaded_settings['ocrspace_api_key'] = self.settings.value(config.SETTINGS_OCRSPACE_API_KEY, None)
        loaded_settings['ocr_language_code'] = self.settings.value(config.SETTINGS_OCR_LANGUAGE_KEY, config.DEFAULT_OCR_LANGUAGE)
        if loaded_settings['ocr_provider'] == 'ocr_space' and loaded_settings['ocr_language_code'] not in config.OCR_SPACE_LANGUAGES:
            loaded_settings['ocr_language_code'] = config.DEFAULT_OCR_LANGUAGE

        # OCR.space Specific
        loaded_settings['ocr_space_engine'] = self.settings.value(config.SETTINGS_OCR_SPACE_ENGINE_KEY, config.DEFAULT_OCR_SPACE_ENGINE_NUMBER, type=int)
        if loaded_settings['ocr_space_engine'] not in config.OCR_SPACE_ENGINES:
            loaded_settings['ocr_space_engine'] = config.DEFAULT_OCR_SPACE_ENGINE_NUMBER
        loaded_settings['ocr_space_scale'] = self.settings.value(config.SETTINGS_OCR_SPACE_SCALE_KEY, config.DEFAULT_OCR_SPACE_SCALE, type=bool)
        loaded_settings['ocr_space_detect_orientation'] = self.settings.value(config.SETTINGS_OCR_SPACE_DETECT_ORIENTATION_KEY, config.DEFAULT_OCR_SPACE_DETECT_ORIENTATION, type=bool)

        # Tesseract Specific
        loaded_settings['tesseract_cmd_path'] = self.settings.value(config.SETTINGS_TESSERACT_CMD_PATH_KEY, config.DEFAULT_TESSERACT_CMD_PATH)
        if loaded_settings['tesseract_cmd_path'] == "": loaded_settings['tesseract_cmd_path'] = None
        loaded_settings['tesseract_language_code'] = self.settings.value(config.SETTINGS_TESSERACT_LANGUAGE_KEY, config.DEFAULT_TESSERACT_LANGUAGE)
        if loaded_settings['tesseract_language_code'] not in config.TESSERACT_LANGUAGES:
            loaded_settings['tesseract_language_code'] = config.DEFAULT_TESSERACT_LANGUAGE

        # Translation Settings
        loaded_settings['deepl_api_key'] = self.settings.value(config.SETTINGS_DEEPL_API_KEY, None)
        loaded_settings['target_language_code'] = self.settings.value(config.SETTINGS_TARGET_LANG_KEY, config.DEFAULT_TARGET_LANGUAGE_CODE)
        default_trans_engine = config.DEFAULT_TRANSLATION_ENGINE
        trans_engine_key = self.settings.value(config.SETTINGS_TRANSLATION_ENGINE_KEY, default_trans_engine)
        if trans_engine_key not in config.AVAILABLE_ENGINES: trans_engine_key = default_trans_engine
        loaded_settings['translation_engine_key'] = trans_engine_key

        # UI / Behavior Settings
        font_str = self.settings.value(config.SETTINGS_FONT_KEY, None)
        display_font = QFont()
        font_ok = isinstance(font_str, str) and display_font.fromString(font_str)
        if not font_ok: display_font = QFont()
        loaded_settings['display_font'] = display_font

        try:
            interval_val = self.settings.value(config.SETTINGS_OCR_INTERVAL_KEY, config.DEFAULT_OCR_INTERVAL_SECONDS)
            ocr_interval = int(interval_val)
            if ocr_interval <= 0: raise ValueError("Interval must be positive")
        except (ValueError, TypeError):
            ocr_interval = config.DEFAULT_OCR_INTERVAL_SECONDS
        loaded_settings['ocr_interval'] = ocr_interval

        default_color_str = config.DEFAULT_BG_COLOR.name(QColor.HexArgb)
        bg_color_str = self.settings.value(config.SETTINGS_BG_COLOR_KEY, default_color_str)
        loaded_bg_color = QColor(bg_color_str)
        if not loaded_bg_color.isValid(): loaded_bg_color = QColor(config.DEFAULT_BG_COLOR)
        loaded_settings['bg_color'] = loaded_bg_color

        loaded_settings['saved_geometry'] = self.settings.value(config.SETTINGS_GEOMETRY_KEY, None, type=QByteArray)
        loaded_settings['is_locked'] = self.settings.value(config.SETTINGS_WINDOW_LOCKED_KEY, False, type=bool)
        loaded_settings['hotkey'] = self.settings.value(config.SETTINGS_HOTKEY_KEY, config.DEFAULT_HOTKEY)

        # Training Data Saving Settings
        loaded_settings['save_ocr_images'] = self.settings.value(config.SETTINGS_SAVE_OCR_IMAGES_KEY, config.DEFAULT_SAVE_OCR_IMAGES, type=bool)
        loaded_settings['ocr_image_save_path'] = self.settings.value(config.SETTINGS_OCR_IMAGE_SAVE_PATH_KEY, config.DEFAULT_OCR_IMAGE_SAVE_PATH)
        if loaded_settings['ocr_image_save_path'] == "": loaded_settings['ocr_image_save_path'] = None

        logging.debug(f"Settings loaded by SettingsManager: {list(loaded_settings.keys())}")
        return loaded_settings

    def save_setting(self, key: str, value: any):
        """Saves a single setting, handling None to remove."""
        log_val = str(value)[:50] + "..." if isinstance(value, str) and len(value) > 50 else str(value)
        sensitive_keys = ["key", "credential", "token"]
        is_sensitive = any(k in key.lower() for k in sensitive_keys)
        if is_sensitive:
            log_val = "****" if value else "None"
        logging.debug(f"Saving setting: {key} = {log_val}")

        if value is None:
            self.settings.remove(key)
        else:
            if isinstance(value, QColor): value_to_save = value.name(QColor.HexArgb)
            elif isinstance(value, QFont): value_to_save = value.toString()
            elif isinstance(value, QByteArray): value_to_save = value
            elif isinstance(value, (str, int, float, bool, list, dict)): value_to_save = value
            else: value_to_save = str(value); logging.warning(f"Saving unsupported type for '{key}' as string.")
            self.settings.setValue(key, value_to_save)

    def save_all_settings(self, settings_dict: dict, current_geometry: QByteArray):
        """Saves all relevant settings from a dictionary and current geometry."""
        logging.debug("Saving all settings via SettingsManager...")
        self.save_setting(config.SETTINGS_GEOMETRY_KEY, current_geometry)

        # OCR Provider settings
        self.save_setting(config.SETTINGS_OCR_PROVIDER_KEY, settings_dict.get('ocr_provider'))
        self.save_setting(config.SETTINGS_GOOGLE_CREDENTIALS_PATH_KEY, settings_dict.get('google_credentials_path'))
        self.save_setting(config.SETTINGS_OCRSPACE_API_KEY, settings_dict.get('ocrspace_api_key'))
        self.save_setting(config.SETTINGS_OCR_LANGUAGE_KEY, settings_dict.get('ocr_language_code'))
        self.save_setting(config.SETTINGS_OCR_SPACE_ENGINE_KEY, settings_dict.get('ocr_space_engine'))
        self.save_setting(config.SETTINGS_OCR_SPACE_SCALE_KEY, settings_dict.get('ocr_space_scale'))
        self.save_setting(config.SETTINGS_OCR_SPACE_DETECT_ORIENTATION_KEY, settings_dict.get('ocr_space_detect_orientation'))
        self.save_setting(config.SETTINGS_TESSERACT_CMD_PATH_KEY, settings_dict.get('tesseract_cmd_path'))
        self.save_setting(config.SETTINGS_TESSERACT_LANGUAGE_KEY, settings_dict.get('tesseract_language_code'))

        # Translation settings
        self.save_setting(config.SETTINGS_DEEPL_API_KEY, settings_dict.get('deepl_api_key'))
        self.save_setting(config.SETTINGS_TARGET_LANG_KEY, settings_dict.get('target_language_code'))
        self.save_setting(config.SETTINGS_TRANSLATION_ENGINE_KEY, settings_dict.get('translation_engine_key'))

        # UI / Behavior settings
        self.save_setting(config.SETTINGS_FONT_KEY, settings_dict.get('display_font'))
        self.save_setting(config.SETTINGS_OCR_INTERVAL_KEY, settings_dict.get('ocr_interval'))
        self.save_setting(config.SETTINGS_BG_COLOR_KEY, settings_dict.get('bg_color'))
        self.save_setting(config.SETTINGS_WINDOW_LOCKED_KEY, settings_dict.get('is_locked', False))
        self.save_setting(config.SETTINGS_HOTKEY_KEY, settings_dict.get('hotkey', config.DEFAULT_HOTKEY))

        # Training Data Saving Settings
        self.save_setting(config.SETTINGS_SAVE_OCR_IMAGES_KEY, settings_dict.get('save_ocr_images', config.DEFAULT_SAVE_OCR_IMAGES))
        self.save_setting(config.SETTINGS_OCR_IMAGE_SAVE_PATH_KEY, settings_dict.get('ocr_image_save_path'))

        self.settings.sync()
        logging.debug("Settings synced by SettingsManager.")

    def get_value(self, key: str, default: any = None) -> any:
        """Retrieves a single setting value."""
        return self.settings.value(key, default)