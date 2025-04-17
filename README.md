# Operation UMA Translator

A desktop application for Windows (and potentially other platforms with adjustments) that captures a selected screen region, performs Optical Character Recognition (OCR), and translates the recognized text using various translation engines.

## Features

* **Screen Region Capture:** Define a specific area on your screen for OCR.
* **OCR Engine Support:** Uses Google Cloud Vision API or OCR.space for text recognition (configurable).
* **Translation:** Supports multiple translation backends:
    * Google Cloud Translation API v3 (Requires API setup)
    * DeepL API (Free or Pro) (Requires API Key)
    * Google Translate (Unofficial via `googletrans` library - may be unstable)
* **Configurable:**
    * Select OCR provider and specific OCR language (for OCR.space).
    * Select target language for translation.
    * Choose the desired translation engine.
    * Adjust OCR refresh interval for "Live Mode".
    * Customize display font and background opacity.
    * Set a global hotkey for single captures.
    * Lock window position and size.
* **User Interface:**
    * Translucent, always-on-top window displaying OCR and translation results.
    * Resizable and movable window (unless locked).
    * Settings dialog for easy configuration.
    * Dedicated checkbox to enable/disable Live Mode.
* **History:** Stores recent OCR/translation pairs, allowing export to CSV and clearing.
* **Modular Design:** Core components have been refactored into separate handlers for improved structure and maintainability.

## Requirements

* Python 3.8+
* External Libraries (see `requirements.txt`)

## Setup & Installation

1.  **Clone or Download:** Get the project files.
2.  **Navigate to Project Root:** Open terminal/command prompt to the project folder.
3.  **Create Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # Activate (Windows): .\venv\Scripts\activate
    # Activate (macOS/Linux): source venv/bin/activate
    ```
4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
5.  **Google Cloud Credentials (Required for Google OCR/Translate):**
    * Need a GCP project with **Cloud Vision API** and/or **Cloud Translation API** enabled.
    * Create a Service Account and download its JSON key file.
6.  **OCR.space API Key (Optional - Required for OCR.space):**
    * Get a free or pro API key from [ocr.space/OCRAPI](https://ocr.space/OCRAPI).
7.  **DeepL API Key (Optional - Required for DeepL Engine):**
    * Get a Free or Pro API key from your account on [deepl.com](https://www.deepl.com/).

## Configuration

1.  **Run:** `python main.py`
2.  **Open Settings (⚙️):**
3.  **Credentials/API Keys:**
    * If using Google Cloud services, browse and select your JSON key file.
    * If using OCR.space, enter your API key.
    * If using DeepL, enter your API key.
4.  **OCR Provider:** Select Google Cloud Vision or OCR.space. If using OCR.space, select the appropriate OCR Language.
5.  **Translation Engine:** Select your preferred engine.
6.  **Target Language:** Choose the language for translation results.
7.  **Other Settings:** Adjust font, opacity, live interval, lock state, hotkey.
8.  **Click OK** to save.

## Usage

1.  **Start:** `python main.py`
2.  **Position/Resize:** Drag top bar to move, drag edges to resize (if not locked).
3.  **Single Capture:**
    * Press the global hotkey (default defined in `config.py`).
    * Alternatively, click the "Grab Text" button (ensure the "Live" checkbox is **unchecked**).
4.  **Live Mode:**
    * **Enable:** Check the "Live" checkbox next to the "Grab Text" button. Prerequisites (API keys/credentials) must be met.
    * **Start Capture:** Click the main action button (which should now read "Start Live"). The checkbox label will change (e.g., "Live ●") to indicate activity.
    * **Stop Capture:** Click the main action button again (which should read "Stop Live").
    * **Disable:** Uncheck the "Live" checkbox. This also stops active capture.
5.  **View History / Settings:** Use the Settings dialog (⚙️).

## Translation Engines Notes

* **Google Cloud API v3:** Reliable, requires Google Cloud setup/credentials.
* **DeepL Free/Pro:** High-quality, requires a DeepL API key.
* **Google Translate (Unofficial):** Uses `googletrans`, **can be unstable/break easily**. No API key needed.

## Troubleshooting

* **`googletrans` Errors:** Likely blocked by Google or API changes. Try later or switch engines.
* **API Key/Credential Errors:** Double-check keys/file paths in settings and ensure APIs are enabled in the respective cloud consoles. Check quotas.
* **Hotkey Not Working:** Ensure `keyboard` library installed, check for conflicts with other apps, potentially check permissions.
* **OCR Fails:** Check selected OCR provider's requirements (API Key for OCR.space, valid credentials/API enabled for Google Vision). Check network.
