# Operation UMA Translator

A desktop application for Windows (and potentially other platforms with adjustments) that captures a selected screen region, performs Optical Character Recognition (OCR), and translates the recognized text using various translation engines.

## Features

* **Screen Region Capture:** Define a specific area on your screen for OCR by positioning the application window over it.
* **OCR:** Supports multiple OCR backends:
    * Google Cloud Vision API (Requires API setup) [cite: src/config.py, src/core/ocr_worker.py]
    * OCR.space API (Requires API Key) [cite: src/config.py, src/core/ocr_worker.py]
* **Translation:** Supports multiple translation backends:
    * Google Cloud Translation API v3 (Requires API setup) [cite: src/config.py, src/translation_engines/google_cloud_v3_engine.py]
    * DeepL API (Free or Pro) (Requires API Key) [cite: src/config.py, src/translation_engines/deepl_free_engine.py]
    * Google Translate (Unofficial via `googletrans` library - may be unstable) [cite: src/config.py, src/translation_engines/googletrans_engine.py]
* **Configurable:** [cite: src/gui/settings_dialog.py, src/config.py]
    * Select OCR provider (Google Cloud Vision or OCR.space).
    * Select OCR language (for OCR.space).
    * Select the desired translation engine.
    * Select target language for translation.
    * Adjust OCR refresh interval for "Live Mode".
    * Customize display font and text area background opacity.
    * Lock window position and size.
* **User Interface:** [cite: src/gui/translucent_box.py]
    * Translucent, always-on-top window displaying OCR and translation results.
    * Resizable and movable window (unless locked).
    * Settings dialog (⚙️) for easy configuration.
* **Global Hotkey:** Trigger OCR/Translate capture using a configurable hotkey (default: `Ctrl+Shift+G`) [cite: src/config.py, src/core/hotkey_manager.py].
* **Live Mode:** Toggle automatic periodic OCR/Translation via the Settings dialog [cite: src/gui/translucent_box.py, src/gui/settings_dialog.py].
* **History:** Stores recent OCR/translation pairs, allowing export to CSV and clearing via the Settings dialog [cite: src/core/history_manager.py, src/gui/settings_dialog.py].
* **Modular Design:** OCR providers and translation engines are separated for easier maintenance and extension.

## Requirements

* Python 3.8+
* The following libraries (see `requirements.txt` [cite: 1]):
    ```
    PyQt5==5.15.10
    mss==9.0.1
    Pillow==10.3.0
    keyboard==0.13.5
    google-cloud-vision==3.7.2
    google-cloud-translate==3.15.1
    google-auth==2.29.0
    googletrans==4.0.0rc1
    deepl==1.18.1
    ```

## Setup & Installation

1.  **Clone or Download:** Get the project files.
2.  **Navigate to Project Root:** Open a terminal/command prompt in the project folder.
3.  **Create Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # Windows: .\venv\Scripts\activate
    # macOS/Linux: source venv/bin/activate
    ```
4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt [cite: 1]
    ```
5.  **API Keys / Credentials:**
    * **Google Cloud (Conditional):**
        * If using Google Cloud Vision (OCR) OR Google Cloud Translate (Translation):
            * You need a Google Cloud Platform project with the **Cloud Vision API** and/or **Cloud Translation API** enabled.
            * Create a **Service Account** and download its **JSON key file**.
    * **OCR.space (Conditional):**
        * If using OCR.space (OCR): Get a free API key from [ocr.space/OCRAPI](https://ocr.space/OCRAPI).
    * **DeepL (Conditional):**
        * If using DeepL (Translation): Get an Authentication Key (Free or Pro) from your [deepl.com](https://www.deepl.com/) account.

## Configuration

1.  **Run the application:** `python main.py`
2.  **Open Settings:** Click the gear icon (⚙️).
3.  **Select OCR Provider:** Choose between Google Cloud Vision and OCR.space [cite: src/gui/settings_dialog.py].
4.  **Provide OCR Credentials/Key:**
    * If using **Google Cloud Vision**: Click "Browse..." next to "Google Credentials" and select your JSON key file [cite: src/gui/settings_dialog.py].
    * If using **OCR.space**: Enter your OCR.space API key in the corresponding field. Select the expected **OCR Language** from the dropdown [cite: src/gui/settings_dialog.py].
5.  **Select Translation Engine:** Choose your preferred engine [cite: src/gui/settings_dialog.py].
6.  **Provide Translation Credentials/Key:**
    * If using **Google Cloud Translate**: Ensure you have provided the Google Credentials JSON key file (Step 4a) [cite: src/gui/settings_dialog.py].
    * If using **DeepL**: Enter your DeepL API Key in the corresponding field [cite: src/gui/settings_dialog.py].
    * **Googletrans (Unofficial)** requires no key here.
7.  **Target Language:** Choose the language you want the text translated into [cite: src/gui/settings_dialog.py].
8.  **Other Settings:** Adjust font, text background opacity, live mode interval, and window lock as desired [cite: src/gui/settings_dialog.py].
9.  **Click OK** to save. Settings are stored using QSettings [cite: src/core/settings_manager.py].

## Usage

1.  **Start the Application:**
    ```bash
    python main.py
    ```
2.  **Position and Resize:** Drag the top area to move, drag edges to resize (if not locked) [cite: src/gui/translucent_box.py].
3.  **Capture Text:**
    * Press the global hotkey (`Ctrl+Shift+G` by default) [cite: src/gui/translucent_box.py].
    * Alternatively, click the "Grab Text" button [cite: src/gui/translucent_box.py].
    * The application captures the region under the text display area, performs OCR using the selected provider, and translates using the selected engine [cite: src/core/ocr_worker.py, src/gui/translucent_box.py].
4.  **Live Mode:**
    * Toggle via the Settings dialog (⚙️) [cite: src/gui/settings_dialog.py].
    * Automatically performs "Grab Text" at the configured interval [cite: src/gui/translucent_box.py].
5.  **View History / Settings:** Use the Settings dialog (⚙️) to Export/Clear history and change configuration [cite: src/gui/settings_dialog.py].

## Translation Engines Notes

* **Google Cloud API v3:** Reliable, requires Google Cloud setup. Uses the JSON credentials file for authentication. Recommended for stability [cite: src/translation_engines/google_cloud_v3_engine.py].
* **DeepL Free/Pro:** High-quality translation, requires a DeepL API key. Free tier has usage limits [cite: src/translation_engines/deepl_free_engine.py].
* **Google Translate (Unofficial):** Uses the `googletrans` library. **Can be unstable and break without notice** if Google changes their web interface. Does not require an API key [cite: src/translation_engines/googletrans_engine.py].

## Troubleshooting

* **`googletrans` Errors:** If the unofficial engine fails (e.g., `JSONDecodeError`, network errors), it might be temporarily blocked or broken. Try again later or switch engines. Ensure you installed `googletrans==4.0.0rc1` [cite: 1, src/translation_engines/googletrans_engine.py].
* **API Key/Credential Errors (Google Cloud/DeepL/OCR.space):** Double-check that the correct API key/credentials file is selected in settings and that the corresponding APIs (Vision, Translate) are enabled in your cloud project. Verify the service account has appropriate roles (e.g., Cloud Vision AI User, Cloud Translation API User). Check for quota limits [cite: src/gui/settings_dialog.py].
* **OCR Fails (Google Vision):** Ensure the Cloud Vision API is enabled and the credentials file is valid and selected correctly. Check network connection [cite: src/core/ocr_worker.py].
* **OCR Fails (OCR.space):** Ensure the API key is correct and you have selected an appropriate OCR language in settings. Check network connection and OCR.space service status [cite: src/core/ocr_worker.py].
* **Hotkey Not Working:** Ensure the `keyboard` library installed correctly. May require elevated permissions on some systems (run as administrator - use with caution). Check for conflicts with other global hotkeys [cite: src/core/hotkey_manager.py, 1].
