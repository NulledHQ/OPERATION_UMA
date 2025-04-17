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
DEFAULT_HOTKEY = 'ctrl+shift+g'
DEFAULT_WINDOW_GEOMETRY = None
MAX_HISTORY_ITEMS = 20
HISTORY_FILENAME = "ocr_translator_history.json"

# --- NEW: Training Data Saving Defaults ---
DEFAULT_SAVE_OCR_IMAGES = False
DEFAULT_OCR_IMAGE_SAVE_PATH = None # Default to None, prompt user if needed

# --- Logging ---
LOG_LEVEL = "INFO" # Or "INFO", "WARNING", "ERROR"
LOG_FORMAT = '[%(asctime)s] %(levelname)s [%(threadName)s] in %(module)s.%(funcName)s: %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# --- Common Language Codes for TRANSLATION Selection ---
COMMON_LANGUAGES = [
    ("English", "en"), ("Spanish", "es"), ("French", "fr"), ("German", "de"),
    ("Japanese", "ja"), ("Korean", "ko"), ("Chinese (Simplified)", "zh-CN"),
    ("Italian", "it"), ("Portuguese", "pt"), ("Russian", "ru"),
]

# --- Language Codes specifically for OCR.space API Selection ---
OCR_SPACE_LANGUAGES = {
    "ara": "Arabic", "bul": "Bulgarian", "chs": "Chinese (Simplified)",
    "cht": "Chinese (Traditional)", "hrv": "Croatian", "cze": "Czech",
    "dan": "Danish", "dut": "Dutch", "eng": "English", "fin": "Finnish",
    "fre": "French", "ger": "German", "gre": "Greek", "hun": "Hungarian",
    "kor": "Korean", "ita": "Italian", "jpn": "Japanese", "pol": "Polish",
    "por": "Portuguese", "rus": "Russian", "slv": "Slovenian",
    "spa": "Spanish", "swe": "Swedish", "tur": "Turkish"
}

# --- Tesseract Specific Languages ---
TESSERACT_LANGUAGES = {
    "eng": "English", "deu": "German", "fra": "French", "jpn": "Japanese",
    "kor": "Korean", "chi_sim": "Chinese Simplified", "spa": "Spanish",
    # Add more installed languages
}
DEFAULT_TESSERACT_LANGUAGE = "eng"

# --- OCR.space API Config ---
OCR_SPACE_API_URL = "https://api.ocr.space/parse/image"
OCR_SPACE_ENGINES = { 1: "Engine 1 (Fast, More Languages)", 2: "Engine 2 (Quality, Auto-Detect Latin)" }
DEFAULT_OCR_SPACE_ENGINE_NUMBER = 1
DEFAULT_OCR_SPACE_SCALE = False
DEFAULT_OCR_SPACE_DETECT_ORIENTATION = False

# --- OCR Providers ---
AVAILABLE_OCR_PROVIDERS = {
    "google_vision": "Google Cloud Vision",
    "ocr_space": "OCR.space",
    "tesseract": "Tesseract (Local)",
}
DEFAULT_OCR_PROVIDER = "google_vision"
DEFAULT_TESSERACT_CMD_PATH = None # For Tesseract

# --- Translation Engines ---
AVAILABLE_ENGINES = {
    "google_cloud_v3": "Google Cloud API v3",
    "googletrans": "Google Translate (Unofficial)",
    "deepl_free": "DeepL Free/Pro",
}
DEFAULT_TRANSLATION_ENGINE = "google_cloud_v3"

# --- QSettings Keys ---
SETTINGS_ORG = "NulledHQ" # Change as needed
SETTINGS_APP = "ScreenOCRTranslator"
SETTINGS_GEOMETRY_KEY = "windowGeometry"
SETTINGS_FONT_KEY = "displayFont"
SETTINGS_WINDOW_LOCKED_KEY = "windowLocked"
SETTINGS_OCR_INTERVAL_KEY = "ocrInterval"
SETTINGS_BG_COLOR_KEY = "backgroundColor"
SETTINGS_HOTKEY_KEY = "captureHotkey"
# OCR Provider Settings
SETTINGS_OCR_PROVIDER_KEY = "ocrProvider"
SETTINGS_GOOGLE_CREDENTIALS_PATH_KEY = "googleCredentialsPath"
SETTINGS_OCRSPACE_API_KEY = "ocrSpaceApiKey"
SETTINGS_OCR_LANGUAGE_KEY = "ocrLanguage" # OCR.space Eng1 lang
SETTINGS_OCR_SPACE_ENGINE_KEY = "ocrSpaceEngine"
SETTINGS_OCR_SPACE_SCALE_KEY = "ocrSpaceScale"
SETTINGS_OCR_SPACE_DETECT_ORIENTATION_KEY = "ocrSpaceDetectOrientation"
SETTINGS_TESSERACT_CMD_PATH_KEY = "tesseractCmdPath"
SETTINGS_TESSERACT_LANGUAGE_KEY = "tesseractLanguage"
# Translation Settings
SETTINGS_TRANSLATION_ENGINE_KEY = "translationEngine"
SETTINGS_TARGET_LANG_KEY = "targetLanguage"
SETTINGS_DEEPL_API_KEY = "deeplApiKey"
# Training Data Saving Keys
SETTINGS_SAVE_OCR_IMAGES_KEY = "saveOcrImages"
SETTINGS_OCR_IMAGE_SAVE_PATH_KEY = "ocrImageSavePath"

# --- UI Tooltips ---
TOOLTIP_GOOGLE_CREDENTIALS = "Select Google Cloud service account JSON key file.\nRequired if Google Cloud Vision/Translate is selected."
TOOLTIP_OCRSPACE_KEY = "Enter your OCR.space API Key.\nRequired only if OCR.space is selected."
TOOLTIP_OCR_PROVIDER_SELECT = "Select the service/engine for Optical Character Recognition (OCR)."
TOOLTIP_OCR_LANGUAGE_SELECT = "Select the language for OCR.space Engine 1."
TOOLTIP_OCR_SPACE_ENGINE_SELECT = "Select OCR.space engine.\nEngine 2 offers auto language detection (Latin)."
TOOLTIP_OCR_SPACE_SCALE = "Enable image upscaling (improves low-res OCR)."
TOOLTIP_OCR_SPACE_DETECT_ORIENTATION = "Enable automatic image rotation detection."
TOOLTIP_TESSERACT_CMD_PATH = "Optional: Full path to Tesseract executable.\nLeave blank to use system PATH."
TOOLTIP_TESSERACT_LANGUAGE_SELECT = "Select Tesseract language.\nRequires installed .traineddata file."
TOOLTIP_DEEPL_KEY = "Enter your DeepL API Key.\nRequired only if DeepL engine is selected."
TOOLTIP_ENGINE_SELECT = "Select the translation service."
TOOLTIP_TARGET_LANGUAGE_SELECT = "Select the language to translate the text INTO."
TOOLTIP_HOTKEY_INPUT = "Click to set global capture hotkey."
TOOLTIP_SAVE_OCR_IMAGES = "Save captured images automatically.\nUseful for creating Tesseract training data."
TOOLTIP_OCR_IMAGE_SAVE_PATH = "Select the folder where captured images will be saved."