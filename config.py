# config.py
import os
from PyQt5.QtGui import QColor

# --- Application Defaults ---
DEFAULT_OCR_INTERVAL_SECONDS = 5
DEFAULT_FONT_SIZE = 18 # Used only if font loading fails
DEFAULT_FONT_COLOR = QColor(0, 0, 0)  # Used only if font loading fails
DEFAULT_BG_COLOR = QColor(0, 0, 0, 150) # Semi-transparent black
MIN_WINDOW_WIDTH = 100
MIN_WINDOW_HEIGHT = 100
RESIZE_MARGIN = 10
DEFAULT_TARGET_LANGUAGE_CODE = "en" # Default target language
DEFAULT_WINDOW_GEOMETRY = None # Default to None, let Qt decide initially
MAX_HISTORY_ITEMS = 20 # How many OCR results to store in history
HISTORY_FILENAME = "ocr_translator_history.json" # Filename for history persistence

# --- Hotkey ---
HOTKEY = 'ctrl+shift+g'

# --- Common Language Codes for Selection ---
# List of tuples: (Display Name, ISO 639-1 Code)
COMMON_LANGUAGES = [
    ("English", "en"),
    ("Spanish", "es"),
    ("French", "fr"),
    ("German", "de"),
    ("Japanese", "ja"),
    ("Korean", "ko"),
    ("Chinese (Simplified)", "zh-CN"),
    ("Chinese (Traditional)", "zh-TW"),
    ("Italian", "it"),
    ("Portuguese", "pt"),
    ("Russian", "ru"),
    # Add more as needed
]

# --- Logging ---
LOG_LEVEL = "DEBUG" # Or "INFO", "WARNING", "ERROR"
LOG_FORMAT = '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'

# --- QSettings Keys ---
SETTINGS_ORG = "MyCompanyOrName" # Change as needed
SETTINGS_APP = "ScreenOCRTranslator"
SETTINGS_CREDENTIALS_PATH_KEY = "googleCredentialsPath"
SETTINGS_GEOMETRY_KEY = "windowGeometry" # Key for saving window size/pos
SETTINGS_TARGET_LANG_KEY = "targetLanguage" # Key for saving target language
SETTINGS_FONT_KEY = "displayFont" # Key for saving display font
# History path not stored in QSettings, using fixed filename relative to app/script