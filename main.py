# main.py
import sys
import os
import logging
from PyQt5.QtWidgets import QApplication, QMessageBox

# Import necessary components from other modules
import config
try:
    from gui import TranslucentBox
except ImportError as e:
     logging.basicConfig(level="CRITICAL", format='%(levelname)s: %(message)s')
     logging.critical(f"Failed to import GUI: {e}. Make sure gui.py exists and PyQt5 is installed.")
     sys.exit(1)


def run_application():
    """Sets up logging, checks prerequisites, and runs the application."""
    # Setup Logging
    try:
         log_level_str = config.LOG_LEVEL.upper()
         log_level = getattr(logging, log_level_str, logging.INFO) # Default to INFO if invalid
    except AttributeError:
         log_level = logging.INFO # Fallback
         print(f"Warning: Invalid LOG_LEVEL '{config.LOG_LEVEL}' in config.py. Defaulting to INFO.")

    logging.basicConfig(level=log_level, format=config.LOG_FORMAT, datefmt='%Y-%m-%d %H:%M:%S')
    logging.info("Application starting...")

    app = QApplication(sys.argv)

    # --- Set App details for QSettings ---
    app.setOrganizationName(config.SETTINGS_ORG)
    app.setApplicationName(config.SETTINGS_APP)
    logging.debug(f"QSettings using Org='{config.SETTINGS_ORG}', App='{config.SETTINGS_APP}'")
    # --- End Set App details ---


    # --- Run Application ---
    try:
        window = TranslucentBox() # Window now handles credential check/prompt
        exit_code = app.exec_()
        logging.info(f"Application finished with exit code {exit_code}.")
        sys.exit(exit_code)
    except Exception as e:
        logging.exception("An unhandled exception occurred:")
        QMessageBox.critical(None, "Fatal Error", f"An unexpected error occurred:\n{e}\n\nCheck logs for details.")
        sys.exit(1)


if __name__ == '__main__':
    run_application()