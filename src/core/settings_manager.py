# src/core/settings_manager.py
import logging
import os
from PyQt5.QtCore import QSettings, QByteArray, QStandardPaths, QCoreApplication
from PyQt5.QtGui import QFont, QColor

# Use absolute import from src package root
from src import config

class SettingsManager:
    """Handles loading and saving application settings using QSettings."""

    def __init__(self):
        """Initializes QSettings."""
        self.settings = QSettings(config.SETTINGS_ORG, config.SETTINGS_APP)
        logging.debug(f"SettingsManager initialized. Using QSettings backend: {self.settings.fileName()}")

    def load_all_settings(self) -> dict:
        """Loads all relevant settings from QSettings into a dictionary."""
        logging.debug("Loading all settings via SettingsManager...")
        loaded_settings = {}

        # --- Load individual settings with defaults ---

        # OCR Provider Settings
        loaded_settings['ocr_provider'] = self.settings.value(
            config.SETTINGS_OCR_PROVIDER_KEY,
            config.DEFAULT_OCR_PROVIDER
        )
        if loaded_settings['ocr_provider'] not in config.AVAILABLE_OCR_PROVIDERS:
            logging.warning(f"Saved OCR provider '{loaded_settings['ocr_provider']}' not found. Reverting to default '{config.DEFAULT_OCR_PROVIDER}'.")
            loaded_settings['ocr_provider'] = config.DEFAULT_OCR_PROVIDER

        loaded_settings['google_credentials_path'] = self.settings.value(config.SETTINGS_GOOGLE_CREDENTIALS_PATH_KEY, None)
        loaded_settings['ocrspace_api_key'] = self.settings.value(config.SETTINGS_OCRSPACE_API_KEY, None)
        # Load OCR Language (New)
        loaded_settings['ocr_language_code'] = self.settings.value(
            config.SETTINGS_OCR_LANGUAGE_KEY,
            config.DEFAULT_OCR_LANGUAGE
        )
        # Basic validation if using OCR.space codes directly
        if loaded_settings['ocr_provider'] == 'ocr_space' and loaded_settings['ocr_language_code'] not in config.OCR_SPACE_LANGUAGES:
             logging.warning(f"Saved OCR language code '{loaded_settings['ocr_language_code']}' not found in config.OCR_SPACE_LANGUAGES. Reverting to default '{config.DEFAULT_OCR_LANGUAGE}'.")
             loaded_settings['ocr_language_code'] = config.DEFAULT_OCR_LANGUAGE


        # Translation Settings
        loaded_settings['deepl_api_key'] = self.settings.value(config.SETTINGS_DEEPL_API_KEY, None)
        loaded_settings['target_language_code'] = self.settings.value(config.SETTINGS_TARGET_LANG_KEY, config.DEFAULT_TARGET_LANGUAGE_CODE)

        # Load and validate translation engine key
        default_trans_engine = config.DEFAULT_TRANSLATION_ENGINE
        trans_engine_key = self.settings.value(config.SETTINGS_TRANSLATION_ENGINE_KEY, default_trans_engine)
        if trans_engine_key not in config.AVAILABLE_ENGINES:
            logging.warning(f"Saved translation engine key '{trans_engine_key}' not found. Reverting to default '{default_trans_engine}'.")
            trans_engine_key = default_trans_engine
        loaded_settings['translation_engine_key'] = trans_engine_key

        # UI / Behavior Settings
        # Load font safely
        font_str = self.settings.value(config.SETTINGS_FONT_KEY, None)
        display_font = QFont()
        if font_str and isinstance(font_str, str) and not display_font.fromString(font_str):
             logging.warning(f"Failed loading font from stored string: '{font_str}'. Using default.")
             display_font = QFont() # Reset
        elif not isinstance(font_str, str): # Handle case where it's not a string
             display_font = QFont() # Use default if stored value isn't a string
        loaded_settings['display_font'] = display_font


        # Load interval safely
        try:
            interval_val = self.settings.value(config.SETTINGS_OCR_INTERVAL_KEY, config.DEFAULT_OCR_INTERVAL_SECONDS)
            ocr_interval = int(interval_val)
            if ocr_interval <= 0: raise ValueError("Interval must be positive")
        except (ValueError, TypeError):
            logging.warning(f"Invalid OCR interval loaded ('{interval_val}'). Using default.")
            ocr_interval = config.DEFAULT_OCR_INTERVAL_SECONDS
        loaded_settings['ocr_interval'] = ocr_interval

        # Load color safely
        default_color_str = config.DEFAULT_BG_COLOR.name(QColor.HexArgb)
        bg_color_str = self.settings.value(config.SETTINGS_BG_COLOR_KEY, default_color_str)
        loaded_bg_color = QColor(bg_color_str)
        if not loaded_bg_color.isValid():
            logging.warning(f"Invalid background color '{bg_color_str}' loaded. Using default.")
            loaded_bg_color = QColor(config.DEFAULT_BG_COLOR)
        loaded_settings['bg_color'] = loaded_bg_color

        loaded_settings['saved_geometry'] = self.settings.value(config.SETTINGS_GEOMETRY_KEY, None)
        loaded_settings['is_locked'] = self.settings.value(config.SETTINGS_WINDOW_LOCKED_KEY, False, type=bool)

        # Load Hotkey <<< NEW >>>
        loaded_settings['hotkey'] = self.settings.value(
            config.SETTINGS_HOTKEY_KEY,
            config.DEFAULT_HOTKEY # Use the new default from config
        )

        logging.debug(f"Settings loaded by SettingsManager: {list(loaded_settings.keys())}")
        return loaded_settings

    def save_setting(self, key: str, value: any):
        """Saves a single setting, handling None to remove."""
        log_val = str(value)[:50] + "..." if value and len(str(value)) > 50 else str(value)
        # Avoid logging sensitive keys like API keys directly
        sensitive_keys = ["key", "credential", "token"]
        is_sensitive = any(k in key.lower() for k in sensitive_keys)
        if is_sensitive:
            log_val = "****" if value else "None"
        logging.debug(f"Saving setting via SettingsManager: {key} = {log_val}")

        if value is None:
            self.settings.remove(key)
            logging.debug(f"Removed setting: {key}")
        else:
            # Ensure value types are suitable for QSettings
            if isinstance(value, QColor):
                value_to_save = value.name(QColor.HexArgb)
            elif isinstance(value, QFont):
                value_to_save = value.toString()
            elif isinstance(value, QByteArray):
                 value_to_save = value # Already suitable
            elif isinstance(value, (str, int, float, bool, list, dict)):
                 value_to_save = value # Standard types
            else:
                 logging.warning(f"Attempting to save unsupported type for key '{key}': {type(value)}. Converting to string.")
                 value_to_save = str(value)
            self.settings.setValue(key, value_to_save)


    def save_all_settings(self, settings_dict: dict, current_geometry: QByteArray):
        """Saves all relevant settings from a dictionary and current geometry."""
        logging.debug("Saving all settings via SettingsManager...")

        # Save geometry first
        self.save_setting(config.SETTINGS_GEOMETRY_KEY, current_geometry)

        # Save OCR Provider settings
        self.save_setting(config.SETTINGS_OCR_PROVIDER_KEY, settings_dict.get('ocr_provider'))
        self.save_setting(config.SETTINGS_GOOGLE_CREDENTIALS_PATH_KEY, settings_dict.get('google_credentials_path'))
        self.save_setting(config.SETTINGS_OCRSPACE_API_KEY, settings_dict.get('ocrspace_api_key'))
        self.save_setting(config.SETTINGS_OCR_LANGUAGE_KEY, settings_dict.get('ocr_language_code')) # <<< SAVE OCR LANG

        # Save Translation settings
        self.save_setting(config.SETTINGS_DEEPL_API_KEY, settings_dict.get('deepl_api_key'))
        self.save_setting(config.SETTINGS_TARGET_LANG_KEY, settings_dict.get('target_language_code'))
        self.save_setting(config.SETTINGS_TRANSLATION_ENGINE_KEY, settings_dict.get('translation_engine_key'))

        # Save UI / Behavior settings
        self.save_setting(config.SETTINGS_FONT_KEY, settings_dict.get('display_font'))
        self.save_setting(config.SETTINGS_OCR_INTERVAL_KEY, settings_dict.get('ocr_interval'))
        self.save_setting(config.SETTINGS_BG_COLOR_KEY, settings_dict.get('bg_color'))
        self.save_setting(config.SETTINGS_WINDOW_LOCKED_KEY, settings_dict.get('is_locked', False))
        # Save Hotkey <<< NEW >>>
        self.save_setting(config.SETTINGS_HOTKEY_KEY, settings_dict.get('hotkey', config.DEFAULT_HOTKEY))


        # Sync once after saving all settings
        self.settings.sync()
        logging.debug("Settings synced by SettingsManager.")

    def get_value(self, key: str, default: any = None) -> any:
        """Retrieves a single setting value."""
        return self.settings.value(key, default)