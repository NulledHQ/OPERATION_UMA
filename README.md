# Screen OCR Translator Tool

A desktop overlay application using PyQt5 that performs Optical Character Recognition (OCR) on a selected screen region and translates the recognized text into English using Google Cloud APIs.

## Features

* Translucent, always-on-top overlay window.
* Movable and resizable window.
* Manual OCR trigger via:
    - "Grab Text" button in the GUI.
    - Global hotkey (`Ctrl+Shift+G` by default).
* "Live Mode" for periodic automatic OCR at configurable intervals.
* Uses Google Cloud Vision for OCR and Google Cloud Translate (v3) for translation (auto-detects source language).
* Customizable:
    - Font size and color for displayed text.
    - Window background color and transparency.
    - Window locking (prevents moving/resizing).
    - Live mode OCR interval.
    - Target translation language.
* OCR history management:
    - View, clear, or export history to a CSV file.
* Error handling with detailed logs.

## Setup

1.  **Prerequisites:**
    - Python 3.6+
    - Pip (Python package installer)

2.  **Google Cloud Setup:**
    - You need a Google Cloud Platform (GCP) project.
    - Enable the **Cloud Vision API** and **Cloud Translation API** for your project.
    - Create a **Service Account** within your GCP project.
    - Download the **JSON key file** for this service account.

3.  **Credentials File:**
    - Set credentials file.

4.  **Install Dependencies:**
    Open a terminal or command prompt in the project directory and run:
    ```bash
    pip install -r requirements.txt
    ```
    *Note: You might need administrator privileges for the `keyboard` library on some systems.*

## Running the Application

Navigate to the project directory in your terminal and run:

```bash
python main.py
```

## Usage

1. Launch the application. The translucent overlay window will appear.
2. Resize or move the window to cover the region of the screen you want to capture.
3. Press the "Grab Text" button or the hotkey (`Ctrl+Shift+G`) to perform OCR and translation.
4. Enable "Live Mode" from the options menu to periodically perform OCR.
5. Customize the appearance and settings via the options menu:
    - Set credentials file.
    - Change the target translation language.
    - Adjust font and background transparency.
6. View, clear, or export OCR history from the options menu.

## Logs and Debugging

Logs are stored in the console or terminal where the application is run. You can configure the log level in `config.py` by setting the `LOG_LEVEL` variable (e.g., `DEBUG`, `INFO`, `WARNING`, `ERROR`).
