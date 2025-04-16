# src/core/history_manager.py
import logging
import os
import sys # Needed for sys.executable fallback
import json
import csv
import collections
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtCore import QStandardPaths

# Use absolute import from src package root
from src import config

class HistoryManager:
    """Manages loading, saving, clearing, and exporting OCR history."""

    def __init__(self, max_items=config.MAX_HISTORY_ITEMS):
        """
        Initializes the History Manager.

        Args:
            max_items (int): Maximum number of history items to keep.
        """
        self.max_items = max(max_items, 0) # Ensure non-negative
        self.history_deque = collections.deque(maxlen=self.max_items)
        self.history_file_path = self._determine_history_path()
        self.load_history() # Load initial history

    def _determine_history_path(self) -> str:
        """Determines the platform-appropriate path for the history file."""
        # Use QStandardPaths for AppDataLocation
        data_path = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)

        if not data_path:
             # Fallback logic if AppDataLocation is not available
             logging.warning("AppDataLocation not found by Qt, using application directory for history.")
             if getattr(sys, 'frozen', False): # Check if running as packaged app (e.g., PyInstaller)
                 data_path = os.path.dirname(sys.executable)
             else: # Running as a script
                  # Use the directory containing this script file's package (src/core)
                  # Go up two levels to get the project root (where main.py likely is)
                  # This assumes a standard execution context.
                  script_dir = os.path.dirname(os.path.abspath(__file__))
                  project_root = os.path.dirname(os.path.dirname(script_dir))
                  data_path = os.path.join(project_root, "data") # Store in a 'data' subfolder relative to main.py

        # Ensure the chosen data_path directory exists
        try:
            os.makedirs(data_path, exist_ok=True)
        except OSError as e:
            logging.error(f"Could not create data directory: {data_path}, Error: {e}. Falling back.")
            # Define a robust fallback path in user's home directory
            fallback_path = os.path.join(os.path.expanduser("~"), f".{config.SETTINGS_APP}_data")
            try:
                os.makedirs(fallback_path, exist_ok=True)
                data_path = fallback_path
                logging.warning(f"Using fallback data directory: {data_path}")
            except OSError as e2:
                 logging.error(f"Could not create fallback directory: {fallback_path}, Error: {e2}. History might not save.")
                 # If even fallback fails, history path might be invalid, but proceed.
                 data_path = "." # Last resort: current working directory

        file_path = os.path.join(data_path, config.HISTORY_FILENAME)
        logging.info(f"History file path set to: {file_path}")
        return file_path

    def load_history(self):
        """Loads OCR/Translation history from the JSON file into the deque."""
        if not self.max_items or not self.history_file_path:
             logging.debug("History loading skipped (maxlen=0 or no path).")
             return
        self.history_deque.clear() # Clear existing deque before loading
        try:
            if os.path.exists(self.history_file_path):
                with open(self.history_file_path, 'r', encoding='utf-8') as f:
                    history_list = json.load(f)
                    valid_items = []
                    # Validate each item before adding
                    for item in history_list:
                        if isinstance(item, (list, tuple)) and len(item) == 2 and all(isinstance(s, str) for s in item):
                             valid_items.append(tuple(item)) # Ensure it's a tuple
                        else:
                             logging.warning(f"Skipping invalid history item format: {item}")
                    # Populate the deque efficiently from the end, respecting maxlen
                    self.history_deque.extend(valid_items[-self.max_items:])
                    count = len(self.history_deque)
                    logging.info(f"Loaded {count} valid items from history file.")
            else:
                logging.info("History file not found, starting with empty history.")
        except json.JSONDecodeError:
            logging.exception(f"Error decoding history JSON file: {self.history_file_path}. Clearing history.")
            # Optionally backup corrupted file here
        except Exception as e:
            logging.exception(f"Unexpected error loading history file: {e}")


    def save_history(self):
        """Saves the current content of the history deque to the JSON file."""
        if not self.max_items or not self.history_file_path:
            logging.debug("History saving skipped (maxlen=0 or no path).")
            return

        history_list = list(self.history_deque)
        history_dir = os.path.dirname(self.history_file_path)

        try:
             # Ensure the target directory exists before attempting to write
             if not os.path.exists(history_dir):
                 os.makedirs(history_dir, exist_ok=True)

             # Write the history list if it's not empty
             if history_list:
                 with open(self.history_file_path, 'w', encoding='utf-8') as f:
                     json.dump(history_list, f, ensure_ascii=False, indent=2)
                 logging.info(f"Saved {len(history_list)} items to history file.")
             # If history is empty, remove the history file if it exists
             elif os.path.exists(self.history_file_path):
                  os.remove(self.history_file_path)
                  logging.info(f"History is empty. Removed history file: {self.history_file_path}")

        except OSError as e:
             logging.error(f"OSError saving history file '{self.history_file_path}': {e}")
             # Inform user? Only if critical.
        except Exception as e:
             logging.exception(f"Unexpected error saving history file: {e}")

    def add_item(self, ocr_text: str, translated_text: str):
        """Adds a new item to the history deque, avoiding consecutive duplicates."""
        if not self.max_items: return # Don't add if history is disabled

        result_entry = (str(ocr_text or ""), str(translated_text or ""))
        # Avoid adding duplicate consecutive entries
        if not self.history_deque or self.history_deque[-1] != result_entry:
            self.history_deque.append(result_entry)
            logging.debug(f"Result added to history. New size: {len(self.history_deque)}")
            # Consider saving immediately or batching saves
            # self.save_history() # Uncomment to save after every addition
        else:
            logging.debug("Skipped adding duplicate consecutive entry to history.")

    def get_history_list(self) -> list:
        """Returns the current history as a list."""
        return list(self.history_deque)

    def get_last_item(self) -> tuple | None:
        """Returns the most recent history item, or None if empty."""
        return self.history_deque[-1] if self.history_deque else None

    def clear_history(self, parent_widget=None):
        """
        Clears the in-memory history deque and attempts to delete the saved file.
        Requires confirmation from the user.

        Args:
            parent_widget: The parent widget for displaying the confirmation dialog.
        """
        if not self.history_deque:
            logging.debug("Clear history called, but history was already empty.")
            if parent_widget:
                QMessageBox.information(parent_widget, "History", "History is already empty.")
            return

        # Confirm with the user
        reply = QMessageBox.question(parent_widget, "Confirm Clear History",
                                     "Are you sure you want to permanently delete all OCR/Translation history?\n(This action cannot be undone)",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            logging.info("User confirmed history clear.")
            # Clear the in-memory deque
            self.history_deque.clear()
            logging.info("In-memory history deque cleared.")

            # Attempt to delete the history file
            try:
                if os.path.exists(self.history_file_path):
                    os.remove(self.history_file_path)
                    logging.info(f"History file deleted: {self.history_file_path}")
                # Inform user of success (optional, can be annoying)
                # if parent_widget:
                #     QMessageBox.information(parent_widget, "History Cleared", "OCR/Translation history has been cleared.")
            except OSError as e:
                logging.error(f"Could not delete history file '{self.history_file_path}': {e}")
                if parent_widget:
                    QMessageBox.warning(parent_widget, "File Error", "History cleared from memory, but could not delete the history file.\nPlease check file permissions.")
        else:
            logging.info("User cancelled history clear.")


    def export_history(self, parent_widget=None):
        """
        Exports the current history deque to a user-selected CSV file.

        Args:
            parent_widget: The parent widget for displaying dialogs.
        """
        if not self.history_deque:
             if parent_widget:
                  QMessageBox.information(parent_widget, "Export History", "History is empty. Nothing to export.")
             return

        # Suggest a default filename
        try:
             docs_location = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
             default_dir = docs_location if docs_location else "."
             default_filename = os.path.join(default_dir, "ocr_translator_history.csv")
        except Exception:
             default_filename = "ocr_translator_history.csv" # Basic fallback

        # Open "Save File" dialog
        filePath, _ = QFileDialog.getSaveFileName(
            parent_widget, # Use parent for dialog
            "Export History As",
            default_filename,
            "CSV Files (*.csv);;All Files (*)" # Filter for CSV files
        )

        # Proceed only if a file path was selected
        if filePath:
            try:
                with open(filePath, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(["OCR Text", "Translated Text"]) # Header row
                    # Write data rows from deque
                    for ocr_text, translated_text in self.history_deque:
                        writer.writerow([ocr_text, translated_text])
                logging.info(f"History exported successfully to: {filePath}")
                if parent_widget:
                    QMessageBox.information(parent_widget, "Export Successful", f"History exported to:\n{filePath}")
            except Exception as e:
                logging.exception(f"Error occurred while exporting history to '{filePath}':")
                if parent_widget:
                    QMessageBox.critical(parent_widget, "Export Error", f"Could not export history:\n{e}")