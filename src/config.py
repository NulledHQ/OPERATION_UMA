# src/config.py
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
DEFAULT_TARGET_LANGUAGE_CODE = "en" # Default target language for TRANSLATION
DEFAULT_OCR_LANGUAGE = "eng" # Default language for OCR (using OCR.space codes)
DEFAULT_HOTKEY = 'ctrl+shift+g' # <<< Define default hotkey here
DEFAULT_WINDOW_GEOMETRY = None # Default to None, let Qt decide initially
MAX_HISTORY_ITEMS = 20 # How many OCR results to store in history
HISTORY_FILENAME = "ocr_translator_history.json" # Filename for history persistence

# --- Hotkey ---
# HOTKEY = 'ctrl+shift+g' # <<< Remove this old hardcoded value

# --- Common Language Codes for TRANSLATION Selection ---
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
# --- Language Codes specifically for OCR.space API Selection ---
# Dictionary: {OCR.space Code: Display Name}
# https://ocr.space/OCRAPI#ocrengine1 (Check documentation for Engine 2/3 languages)
OCR_SPACE_LANGUAGES = {
    "ara": "Arabic",
    "bul": "Bulgarian",
    "chs": "Chinese (Simplified)",
    "cht": "Chinese (Traditional)",
    "hrv": "Croatian",
    "cze": "Czech",
    "dan": "Danish",
    "dut": "Dutch",
    "eng": "English", # Default
    "fin": "Finnish",
    "fre": "French",
    "ger": "German",
    "gre": "Greek",
    "hun": "Hungarian",
    "kor": "Korean", # Engine 1/3
    "ita": "Italian",
    "jpn": "Japanese", # Engine 1/3
    "pol": "Polish",
    "por": "Portuguese",
    "rus": "Russian", # Engine 1/3
    "slv": "Slovenian",
    "spa": "Spanish",
    "swe": "Swedish",
    "tur": "Turkish"
    # Add more from OCR.space documentation if needed (e.g., Hindi 'hin', etc.)
}


# --- Logging ---
LOG_LEVEL = "DEBUG" # Or "INFO", "WARNING", "ERROR"
LOG_FORMAT = '[%(asctime)s] %(levelname)s [%(threadName)s] in %(module)s.%(funcName)s: %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# --- QSettings Keys ---
SETTINGS_ORG = "MyCompanyOrName" # Change as needed
SETTINGS_APP = "ScreenOCRTranslator"
SETTINGS_GEOMETRY_KEY = "windowGeometry"
SETTINGS_FONT_KEY = "displayFont"
SETTINGS_WINDOW_LOCKED_KEY = "windowLocked"
SETTINGS_OCR_INTERVAL_KEY = "ocrInterval"
SETTINGS_BG_COLOR_KEY = "backgroundColor"
SETTINGS_HOTKEY_KEY = "captureHotkey" # <<< ADD THIS KEY
# OCR Provider Settings
SETTINGS_OCR_PROVIDER_KEY = "ocrProvider"
SETTINGS_GOOGLE_CREDENTIALS_PATH_KEY = "googleCredentialsPath"
SETTINGS_OCRSPACE_API_KEY = "ocrSpaceApiKey"
SETTINGS_OCR_LANGUAGE_KEY = "ocrLanguage" # <<< NEW KEY for selected OCR language
# Translation Settings
SETTINGS_TRANSLATION_ENGINE_KEY = "translationEngine"
SETTINGS_TARGET_LANG_KEY = "targetLanguage" # Target for translation
SETTINGS_DEEPL_API_KEY = "deeplApiKey"

# --- OCR Providers ---
AVAILABLE_OCR_PROVIDERS = {
    "google_vision": "Google Cloud Vision",
    "ocr_space": "OCR.space",
}
DEFAULT_OCR_PROVIDER = "google_vision" # Default OCR provider

# --- Translation Engines ---
AVAILABLE_ENGINES = {
    "google_cloud_v3": "Google Cloud API v3",
    "googletrans": "Google Translate (Unofficial)",
    "deepl_free": "DeepL Free/Pro",
}
DEFAULT_TRANSLATION_ENGINE = "google_cloud_v3"

# --- UI Tooltips ---
TOOLTIP_GOOGLE_CREDENTIALS = ("Select Google Cloud service account JSON key file.\n"
                            "Required only if Google Cloud Vision is selected as OCR provider\n"
                            "OR if Google Cloud Translate is the selected Translation Engine.")
TOOLTIP_OCRSPACE_KEY = ("Enter your OCR.space API Key.\n"
                      "Required only if OCR.space is selected as OCR provider.\n"
                      "Get a free key from ocr.space/OCRAPI.")
TOOLTIP_OCR_PROVIDER_SELECT = "Select the service to use for Optical Character Recognition (OCR)."
TOOLTIP_OCR_LANGUAGE_SELECT = ("Select the language the OCR engine should detect.\n"
                               "Only used when OCR.space provider is selected.") # <<< NEW TOOLTIP
TOOLTIP_DEEPL_KEY = ("Enter your DeepL API Authentication Key (Free or Pro).\n"
                   "Required only if DeepL engine is selected for translation.\n"
                   "Get a key from deepl.com.")
TOOLTIP_ENGINE_SELECT = "Select the translation service to use."
TOOLTIP_TARGET_LANGUAGE_SELECT = "Select the language to translate the recognized text INTO."
TOOLTIP_HOTKEY_INPUT = ("Click here, then press the desired key combination (e.g., Ctrl+Shift+X).\n"
                      "Uses 'keyboard' library format. Mouse buttons not supported.") # <<< ADD THIS TOOLTIP


# --- OCR.space API ---
OCR_SPACE_API_URL = "https://api.ocr.space/parse/image"
OCR_SPACE_DEFAULT_ENGINE = 1 # Can be 1 or 2 or 3 (Engine 3 often better for CJK)