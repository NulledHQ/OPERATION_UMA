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
        # Ensure Org/App names are set (typically done in main.py before this)
        # if not QCoreApplication.organizationName():
        #     QCoreApplication.setOrganizationName(config.SETTINGS_ORG)
        # if not QCoreApplication.applicationName():
        #     QCoreApplication.setApplicationName(config.SETTINGS_APP)

        self.settings = QSettings(config.SETTINGS_ORG, config.SETTINGS_APP)
        logging.debug(f"SettingsManager initialized. Using QSettings backend: {self.settings.fileName()}")

    def load_all_settings(self) -> dict:
        """Loads all relevant settings from QSettings into a dictionary."""
        logging.debug("Loading all settings via SettingsManager...")
        loaded_settings = {}

        # --- Load individual settings with defaults ---
        loaded_settings['credentials_path'] = self.settings.value(config.SETTINGS_CREDENTIALS_PATH_KEY, None)
        loaded_settings['deepl_api_key'] = self.settings.value(config.SETTINGS_DEEPL_API_KEY, None)
        loaded_settings['target_language_code'] = self.settings.value(config.SETTINGS_TARGET_LANG_KEY, config.DEFAULT_TARGET_LANGUAGE_CODE)

        # Load and validate engine key
        default_engine = config.DEFAULT_TRANSLATION_ENGINE
        engine_key = self.settings.value(config.SETTINGS_TRANSLATION_ENGINE_KEY, default_engine)
        if engine_key not in config.AVAILABLE_ENGINES:
            logging.warning(f"Saved engine key '{engine_key}' not found. Reverting to default '{default_engine}'.")
            engine_key = default_engine
        loaded_settings['translation_engine_key'] = engine_key

        # Load font safely
        font_str = self.settings.value(config.SETTINGS_FONT_KEY, None)
        display_font = QFont()
        if font_str and not display_font.fromString(font_str):
            logging.warning(f"Failed loading font from stored string: '{font_str}'. Using default.")
            display_font = QFont() # Reset
        loaded_settings['display_font'] = display_font

        # Load interval safely
        try:
            interval_val = self.settings.value(config.SETTINGS_OCR_INTERVAL_KEY, config.DEFAULT_OCR_INTERVAL_SECONDS)
            ocr_interval = int(interval_val)
            if ocr_interval <= 0: raise ValueError()
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

        logging.debug(f"Settings loaded by SettingsManager: {list(loaded_settings.keys())}")
        return loaded_settings

    def save_setting(self, key: str, value: any):
        """Saves a single setting, handling None to remove."""
        logging.debug(f"Saving setting via SettingsManager: {key} = {str(value)[:50]}...") # Log truncated value
        if value is None:
            self.settings.remove(key)
            logging.debug(f"Removed setting: {key}")
        else:
            self.settings.setValue(key, value)
        # Syncing after every single save might be slow, consider syncing once in save_all_settings
        # self.settings.sync()

    def save_all_settings(self, settings_dict: dict, current_geometry: QByteArray):
        """Saves all relevant settings from a dictionary and current geometry."""
        logging.debug("Saving all settings via SettingsManager...")

        # Save geometry first
        self.save_setting(config.SETTINGS_GEOMETRY_KEY, current_geometry)

        # Save other settings using keys from config.py
        self.save_setting(config.SETTINGS_CREDENTIALS_PATH_KEY, settings_dict.get('credentials_path'))
        self.save_setting(config.SETTINGS_DEEPL_API_KEY, settings_dict.get('deepl_api_key'))
        self.save_setting(config.SETTINGS_TARGET_LANG_KEY, settings_dict.get('target_language_code'))
        self.save_setting(config.SETTINGS_TRANSLATION_ENGINE_KEY, settings_dict.get('translation_engine_key'))

        font = settings_dict.get('display_font')
        self.save_setting(config.SETTINGS_FONT_KEY, font.toString() if isinstance(font, QFont) else None)

        self.save_setting(config.SETTINGS_OCR_INTERVAL_KEY, settings_dict.get('ocr_interval'))

        bg_color = settings_dict.get('bg_color')
        self.save_setting(config.SETTINGS_BG_COLOR_KEY, bg_color.name(QColor.HexArgb) if isinstance(bg_color, QColor) else None)

        self.save_setting(config.SETTINGS_WINDOW_LOCKED_KEY, settings_dict.get('is_locked', False))

        # Sync once after saving all settings
        self.settings.sync()
        logging.debug("Settings synced by SettingsManager.")

    def get_value(self, key: str, default: any = None) -> any:
        """Retrieves a single setting value."""
        return self.settings.value(key, default)