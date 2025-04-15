# Screen OCR Translator Tool

A desktop overlay application using PyQt5 that performs Optical Character Recognition (OCR) on a selected screen region and translates the recognized text into English using Google Cloud APIs.

## Features

* Translucent, always-on-top overlay window.
* Movable and resizable window.
* Manual OCR trigger via "Grab Text" button.
* Global hotkey (`Ctrl+Shift+G` by default) to trigger OCR.
* "Live Mode" for periodic automatic OCR.
* Uses Google Cloud Vision for OCR and Google Cloud Translate (v3) for translation (auto-detects source language).
* Customizable:
    * Font size and color for displayed text.
    * Window background color and transparency.
    * Window locking (prevents moving/resizing).
    * Live mode OCR interval.

## Setup

1.  **Prerequisites:**
    * Python 3.6+
    * Pip (Python package installer)

2.  **Google Cloud Setup:**
    * You need a Google Cloud Platform (GCP) project.
    * Enable the **Cloud Vision API** and **Cloud Translation API** for your project.
    * Create a **Service Account** within your GCP project.
    * Download the **JSON key file** for this service account.

3.  **Credentials File:**
    * Rename the downloaded JSON key file to `your-credentials-file.json` (or update the `CREDENTIALS_FILENAME` variable in `config.py` to match your file's name).
    * **Place this JSON key file in the same directory** as the Python scripts (`main.py`, `config.py`, etc.).

4.  **Install Dependencies:**
    Open a terminal or command prompt in the project directory (`ocr_translator_app/`) and run:
    ```bash
    pip install -r requirements.txt
    ```
    *Note: You might need administrator privileges for the `keyboard` library on some systems.*

## Running the Application

Navigate to the project directory in your terminal and run:

```bash
python main.py