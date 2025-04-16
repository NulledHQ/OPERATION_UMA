# Screen OCR Translator

A desktop application for Windows (and potentially other platforms with adjustments) that captures a selected screen region, performs Optical Character Recognition (OCR) using Google Cloud Vision, and translates the recognized text using various translation engines.

## Features

* **Screen Region Capture:** Define a specific area on your screen for OCR.
* **OCR:** Uses Google Cloud Vision API for accurate text recognition.
* **Translation:** Supports multiple translation backends:
    * Google Cloud Translation API v3 (Requires API setup)
    * DeepL API (Free or Pro) (Requires API Key)
    * Google Translate (Unofficial via `googletrans` library - may be unstable)
* **Configurable:**
    * Select target language for translation.
    * Choose the desired translation engine.
    * Adjust OCR refresh interval for "Live Mode".
    * Customize display font and background opacity.
    * Lock window position and size.
* **User Interface:**
    * Translucent, always-on-top window displaying OCR and translation results.
    * Resizable and movable window (unless locked).
    * Settings dialog for easy configuration.
* **Global Hotkey:** Trigger OCR capture using a configurable hotkey (default: `Ctrl+Shift+G`).
* **History:** Stores recent OCR/translation pairs, allowing export to CSV and clearing.
* **Modular Design:** Translation engines and core components are separated for easier maintenance and extension.

## Requirements

* Python 3.8+
* External Libraries (see `requirements.txt`)

## Setup & Installation

1.  **Clone or Download:** Get the project files onto your local machine.
2.  **Navigate to Project Root:** Open your terminal or command prompt and change directory to the project folder (`ScreenOCRTranslator/`).
3.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # On Windows:
    .\venv\Scripts\activate
    # On macOS/Linux:
    # source venv/bin/activate
    ```
4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
5.  **Google Cloud Credentials (Required for OCR):**
    * You need a Google Cloud Platform project with the **Cloud Vision API** enabled.
    * Create a **Service Account** for this project.
    * Download the **JSON key file** for the service account.
    * Keep this file safe!
6.  **DeepL API Key (Optional - Required for DeepL Engine):**
    * Sign up for a DeepL account (Free or Pro) at [deepl.com](https://www.deepl.com/).
    * Go to your Account settings and find your **Authentication Key for DeepL API**.
    * Copy this key.

## Configuration

1.  **Run the application:** `python main.py`
2.  **Open Settings:** Click the gear icon (⚙️) in the application window.
3.  **Google Credentials:**
    * Click "Browse..." next to "Google Credentials".
    * Select the JSON key file you downloaded in the setup steps. (This is **required** for OCR to function with *any* translation engine).
4.  **Translation Engine:**
    * Select your preferred translation engine from the dropdown.
5.  **DeepL API Key:**
    * If you selected "DeepL Free/Pro", the API Key field will appear.
    * Paste your DeepL API Key into the field.
6.  **Target Language:** Choose the language you want the OCR text translated into.
7.  **Other Settings:** Adjust font, background opacity, live mode interval, and window lock as desired.
8.  **Click OK** to save the settings.

## Usage

1.  **Start the Application:**
    ```bash
    python main.py
    ```
2.  **Position and Resize:** Click and drag the top area (not buttons or text area) to move the window. Click and drag near the window edges to resize it (unless locked).
3.  **Capture Text:**
    * Press the global hotkey (`Ctrl+Shift+G` by default).
    * Alternatively, click the "Grab Text" button on the window.
    * The application will capture the region underneath its window, perform OCR, and translate the text using the selected engine.
4.  **Live Mode (Optional):**
    * Live mode can be toggled via a context menu (Right-click, if implemented) or potentially a button in settings (Currently toggled via `toggle_live_mode` function - needs UI integration).
    * When active, it automatically performs "Grab Text" at the interval specified in the settings.
5.  **View History / Settings:** Use the Settings dialog (⚙️) to access history options (Export, Clear) and change configuration.

## Translation Engines Notes

* **Google Cloud API v3:** Most reliable, requires Google Cloud setup and enabled billing (though Vision/Translate have free tiers). Uses the credentials file.
* **DeepL Free/Pro:** High-quality translation, requires a DeepL API key. Free tier has usage limits.
* **Google Translate (Unofficial):** Uses the `googletrans` library which scrapes Google Translate. **This can be unstable and may break without notice** if Google changes their internal API. It does not require an API key.

## Troubleshooting

* **`googletrans` Errors:** If the unofficial engine fails (e.g., `JSONDecodeError`, network errors), it might be temporarily blocked by Google or the underlying API might have changed. Try again later or switch engines. Ensure you installed `googletrans==4.0.0rc1`.
* **API Key Errors (DeepL/Google Cloud):** Double-check that the correct API key/credentials file is selected in settings and that the corresponding APIs (Vision, Translate) are enabled in your cloud project. Check for quota limits.
* **Hotkey Not Working:** Ensure the `keyboard` library installed correctly and that the application has necessary permissions (sometimes requires running as administrator, though use with caution). Conflicts with other global hotkeys are possible.
* **OCR Fails:** Ensure the Google Cloud Vision API is enabled and the credentials file is valid and selected correctly. Check network connection.

## License

MIT License

Copyright (c) 2025 NULLEDHQ

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
