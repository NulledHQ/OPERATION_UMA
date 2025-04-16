# src/config.py
# (Content is the same as the config.py you provided earlier)
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
    ("English", "en"),         # DeepL: EN-US/EN-GB, Google: en
    ("Spanish", "es"),         # DeepL: ES, Google: es
    ("French", "fr"),          # DeepL: FR, Google: fr
    ("German", "de"),          # DeepL: DE, Google: de
    ("Japanese", "ja"),        # DeepL: JA, Google: ja
    ("Korean", "ko"),          # DeepL: KO, Google: ko
    ("Chinese (Simplified)", "zh-CN"), # DeepL: ZH, Google: zh-CN/zh-Hans
    # ("Chinese (Traditional)", "zh-TW"), # DeepL: ZH, Google: zh-TW/zh-Hant (less common target)
    ("Italian", "it"),         # DeepL: IT, Google: it
    ("Portuguese", "pt"),      # DeepL: PT-PT/PT-BR, Google: pt
    ("Russian", "ru"),         # DeepL: RU, Google: ru
]

# --- Logging ---
LOG_LEVEL = "DEBUG" # Or "INFO", "WARNING", "ERROR"
LOG_FORMAT = '[%(asctime)s] %(levelname)s [%(threadName)s] in %(module)s.%(funcName)s: %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# --- QSettings Keys ---
SETTINGS_ORG = "MyCompanyOrName" # Change as needed
SETTINGS_APP = "ScreenOCRTranslator"
SETTINGS_CREDENTIALS_PATH_KEY = "googleCredentialsPath"
SETTINGS_DEEPL_API_KEY = "deeplApiKey"
SETTINGS_GEOMETRY_KEY = "windowGeometry"
SETTINGS_TARGET_LANG_KEY = "targetLanguage"
SETTINGS_FONT_KEY = "displayFont"
SETTINGS_WINDOW_LOCKED_KEY = "windowLocked"
SETTINGS_OCR_INTERVAL_KEY = "ocrInterval"
SETTINGS_BG_COLOR_KEY = "backgroundColor"
SETTINGS_TRANSLATION_ENGINE_KEY = "translationEngine"

# --- Translation Engines ---
AVAILABLE_ENGINES = {
    "google_cloud_v3": "Google Cloud API v3",
    "googletrans": "Google Translate (Unofficial)",
    "deepl_free": "DeepL Free/Pro",
}
DEFAULT_TRANSLATION_ENGINE = "google_cloud_v3"

# --- UI Tooltips ---
TOOLTIP_GOOGLE_CREDENTIALS = ("Select Google Cloud service account JSON key file.\n"
                            "Required for OCR (all engines) and Google Cloud translation.")
TOOLTIP_DEEPL_KEY = ("Enter your DeepL API Authentication Key (Free or Pro).\n"
                   "Required only if DeepL engine is selected.\n"
                   "Get a key from deepl.com.")
TOOLTIP_ENGINE_SELECT = "Select the translation service to use."