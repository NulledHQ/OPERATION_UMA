# main.py
import sys
import os
import logging
from PyQt5.QtWidgets import QApplication, QMessageBox, QStyleFactory
from PyQt5.QtCore import QCoreApplication

# --- Set application details early for QSettings ---
# Import config from the 'src' package first to get settings keys
try:
    from src import config
    QCoreApplication.setOrganizationName(config.SETTINGS_ORG)
    QCoreApplication.setApplicationName(config.SETTINGS_APP)
except ImportError as e:
    # Basic logging if src/config fails very early
    logging.basicConfig(level="CRITICAL", format='%(levelname)s: %(message)s')
    logging.critical(f"Failed to import config from src: {e}. Application cannot start correctly.")
    # Cannot show QMessageBox easily without QApplication instance yet
    print(f"ERROR: Failed to import config from src: {e}. Application cannot start correctly.")
    sys.exit(1)
except Exception as e:
    logging.basicConfig(level="CRITICAL", format='%(levelname)s: %(message)s')
    logging.critical(f"Unexpected error setting application details: {e}")
    print(f"ERROR: Unexpected error setting application details: {e}")
    sys.exit(1)


# --- Import GUI component after setting app details ---
try:
    # Import the main window class from its new location
    from src.gui.translucent_box import TranslucentBox
except ImportError as e:
     logging.basicConfig(level="CRITICAL", format='%(levelname)s: %(message)s')
     logging.critical(f"Failed to import GUI component (TranslucentBox): {e}. Make sure src/gui/translucent_box.py exists.")
     # Try to show a message box if QApplication can be instantiated
     try:
         app = QApplication(sys.argv)
         QMessageBox.critical(None, "Initialization Error", f"Failed to load GUI component:\n{e}\n\nApplication cannot start.")
     except Exception:
         print(f"ERROR: Failed to load GUI component:\n{e}\n\nApplication cannot start.")
     sys.exit(1)


def setup_logging():
    """Configures logging for the application."""
    try:
        log_level_str = config.LOG_LEVEL.upper()
        log_level = getattr(logging, log_level_str, logging.INFO)
        if not isinstance(log_level, int): # Check if getattr succeeded
            print(f"Warning: Invalid LOG_LEVEL '{config.LOG_LEVEL}' in config.py. Defaulting to INFO.")
            log_level = logging.INFO
    except AttributeError:
        log_level = logging.INFO
        print("Warning: LOG_LEVEL not found in config.py. Defaulting to INFO.")

    # Use configured format and date format
    logging.basicConfig(level=log_level, format=config.LOG_FORMAT, datefmt=config.DATE_FORMAT)
    logging.info("Logging configured.")
    logging.debug(f"Logging level set to {logging.getLevelName(log_level)}")


def run_application():
    """Initializes QApplication and runs the main window."""
    setup_logging() # Configure logging first

    logging.info("Application starting...")

    # --- Initialize QApplication ---
    # Pass sys.argv for command-line arguments Qt might use
    app = QApplication(sys.argv)

    # Optional: Set a specific style if desired (e.g., 'Fusion')
    # app.setStyle(QStyleFactory.create('Fusion'))

    # --- Run Application Window ---
    try:
        # Create the main window instance
        # Initialization within TranslucentBox handles loading managers, settings, etc.
        window = TranslucentBox()
        window.show() # Ensure window is shown (might be redundant if show() is in __init__)

        # Enter the Qt event loop
        exit_code = app.exec_()
        logging.info(f"Application event loop finished with exit code {exit_code}.")
        sys.exit(exit_code) # Exit process with the code from app.exec_()

    except Exception as e:
        # Catch any unhandled exceptions during initialization or runtime
        logging.exception("An unhandled exception occurred during application execution:")
        QMessageBox.critical(None, "Fatal Error", f"An unexpected error occurred:\n{e}\n\nCheck logs for details. Application will exit.")
        sys.exit(1) # Exit with error code


if __name__ == '__main__':
    # Ensure the application runs only when script is executed directly
    run_application()