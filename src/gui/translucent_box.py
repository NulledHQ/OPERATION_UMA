# src/gui/translucent_box.py
import logging
import sys
import os
import html
# import time # No longer needed here

# PyQt5 Imports
from PyQt5.QtWidgets import (QWidget, QApplication, QPushButton, QTextEdit,
                             QMenu, QAction, QColorDialog, QInputDialog, QStyle,
                             QFileDialog, QMessageBox, QFontDialog, QDialog)
# Use QApplication for processEvents if needed
from PyQt5.QtCore import Qt, QPoint, QRect, QTimer, QThread, QSettings, pyqtSignal, QByteArray, QStandardPaths, QObject, QSize, pyqtSlot, QRectF
from PyQt5.QtGui import QColor, QPainter, QBrush, QFont, QIcon, QCursor, QTextOption, QPainterPath


# --- Import application modules using absolute paths from src ---
from src import config
from src.core.settings_manager import SettingsManager
from src.core.history_manager import HistoryManager
from src.core.ocr_worker import OCRWorker # Worker no longer has capture signals
# Import specific functions from hotkey_manager
from src.core.hotkey_manager import setup_hotkey, unregister_hotkeys #, change_hotkey # Keep change commented out
from src.gui.settings_dialog import SettingsDialog


class TranslucentBox(QWidget):
    """
    Main application window. Orchestrates UI, settings, history, and OCR.
    Delegates settings/history persistence to manager classes.
    Handles hotkey setup based on saved settings.
    """
    # ... (Initialization __init__ start) ...
    def __init__(self):
        super().__init__()

        # --- Initialize Managers ---
        self.settings_manager = SettingsManager() if SettingsManager else None
        if not self.settings_manager:
             try: QMessageBox.critical(None, "Init Error", "SettingsManager failed. App cannot continue.")
             except: print("CRITICAL: SettingsManager failed. App cannot continue.") # Fallback print
             sys.exit(1)

        # --- Initialize State Variables ---
        # Initialize defaults before loading to prevent attribute errors
        self.bg_color = QColor(config.DEFAULT_BG_COLOR) # Will be updated by load
        self.textarea_alpha = config.DEFAULT_BG_COLOR.alpha() # Default alpha for text area
        self.display_font = QFont() # Default font
        self.ocr_interval = config.DEFAULT_OCR_INTERVAL_SECONDS
        self.hotkey = config.DEFAULT_HOTKEY # Initialize with default
        self.is_locked = False
        # --- Load settings ---
        initial_settings = self.settings_manager.load_all_settings()
        self._apply_loaded_settings(initial_settings) # Load settings into attributes

        self.history_manager = HistoryManager(max_items=config.MAX_HISTORY_ITEMS) if HistoryManager else None
        if not self.history_manager:
             QMessageBox.warning(None, "Init Warning", "HistoryManager failed. History unavailable.")

        # --- Initialize MORE State Variables ---
        self._update_prerequisite_state_flags() # Update flags based on loaded settings
        self.is_live_mode = False
        self.drag_pos = None
        self.resizing = False
        self.resizing_edges = {'left': False, 'top': False, 'right': False, 'bottom': False} # Full keys
        self.ocr_running = False
        self.thread = None
        self.worker = None # Ensure worker is initialized to None

        # --- Timers ---
        self.live_mode_timer = QTimer(self); self.live_mode_timer.timeout.connect(self.grab_text)

        # --- UI Initialization ---
        self._setup_window_properties()
        self.initUI() # This now calls _update_text_display_style internally
        self._update_ocr_button_states() # Update button state based on loaded settings
        self.restore_geometry(initial_settings.get('saved_geometry'))
        self.apply_initial_lock_state()

        # --- Hotkey Setup ---
        # Pass the loaded hotkey string to the setup function
        if 'setup_hotkey' in globals() and callable(setup_hotkey):
             # <<< PASS LOADED HOTKEY HERE >>>
             logging.info(f"Attempting to set up hotkey: '{self.hotkey}'")
             setup_hotkey(self.hotkey, self.grab_text)
        else: logging.error("Hotkey setup function not available.")

        logging.info("Application window initialized.")


    def _apply_loaded_settings(self, settings_dict):
        """Applies settings from a dictionary to instance attributes."""
        # OCR Settings
        self.ocr_provider = settings_dict.get('ocr_provider', config.DEFAULT_OCR_PROVIDER)
        self.google_credentials_path = settings_dict.get('google_credentials_path')
        self.ocrspace_api_key = settings_dict.get('ocrspace_api_key')
        self.ocr_language_code = settings_dict.get('ocr_language_code', config.DEFAULT_OCR_LANGUAGE) # <<< LOAD OCR LANG

        # Translation Settings
        self.deepl_api_key = settings_dict.get('deepl_api_key')
        self.target_language_code = settings_dict.get('target_language_code', config.DEFAULT_TARGET_LANGUAGE_CODE) # Target for Translation
        self.translation_engine_key = settings_dict.get('translation_engine_key', config.DEFAULT_TRANSLATION_ENGINE)

        # UI / Behavior Settings
        # Safely handle font loading
        loaded_font = settings_dict.get('display_font')
        self.display_font = loaded_font if isinstance(loaded_font, QFont) else QFont()

        # Safely handle interval loading
        loaded_interval = settings_dict.get('ocr_interval', config.DEFAULT_OCR_INTERVAL_SECONDS)
        self.ocr_interval = loaded_interval if isinstance(loaded_interval, int) and loaded_interval > 0 else config.DEFAULT_OCR_INTERVAL_SECONDS

        self.is_locked = settings_dict.get('is_locked', False)

        # Safely handle hotkey loading <<< NEW >>>
        loaded_hotkey = settings_dict.get('hotkey', config.DEFAULT_HOTKEY)
        self.hotkey = loaded_hotkey if isinstance(loaded_hotkey, str) and loaded_hotkey else config.DEFAULT_HOTKEY


        # --- Handle Colors ---
        loaded_bg_color = settings_dict.get('bg_color', QColor(config.DEFAULT_BG_COLOR))
        if not isinstance(loaded_bg_color, QColor) or not loaded_bg_color.isValid():
            logging.warning(f"Invalid bg_color loaded ('{loaded_bg_color}'). Using default.")
            loaded_bg_color = QColor(config.DEFAULT_BG_COLOR)

        # Set window background color with fixed alpha from config default
        default_win_alpha = config.DEFAULT_BG_COLOR.alpha() # Base alpha for window frame/decor
        # Use the RGB from the loaded color for the frame, but keep fixed alpha
        self.bg_color = QColor(0, 0, 0, 255)
        # Store the alpha from the loaded setting specifically for the text area
        self.textarea_alpha = loaded_bg_color.alpha()


        # Validation / Type Checking (redundant for interval/font/hotkey due to safe loading above, but good practice)
        if self.ocr_provider not in config.AVAILABLE_OCR_PROVIDERS: self.ocr_provider = config.DEFAULT_OCR_PROVIDER
        if self.translation_engine_key not in config.AVAILABLE_ENGINES: self.translation_engine_key = config.DEFAULT_TRANSLATION_ENGINE
        # bg_color and textarea_alpha already handled/validated above
        # Validate OCR language code only if OCR.space is selected
        if self.ocr_provider == 'ocr_space' and self.ocr_language_code not in config.OCR_SPACE_LANGUAGES:
             self.ocr_language_code = config.DEFAULT_OCR_LANGUAGE


        logging.debug("Applied loaded settings to TranslucentBox attributes.")

    def _update_prerequisite_state_flags(self):
        """Updates internal flags based on current credentials/keys."""
        # Ensure paths/keys are strings before checking existence/truthiness
        gc_path = self.google_credentials_path
        ocr_key = self.ocrspace_api_key
        dl_key = self.deepl_api_key

        self._is_google_credentials_valid = bool(isinstance(gc_path, str) and gc_path and os.path.exists(gc_path))
        self._is_ocrspace_key_set = bool(isinstance(ocr_key, str) and ocr_key)
        self._is_deepl_key_set = bool(isinstance(dl_key, str) and dl_key)


    def load_settings(self):
        """Reloads settings from storage and applies them."""
        if self.settings_manager:
            logging.debug("Reloading settings...")
            settings_dict = self.settings_manager.load_all_settings()
            old_hotkey = self.hotkey # Store before applying loaded settings

            self._apply_loaded_settings(settings_dict) # Apply loaded settings
            self._update_prerequisite_state_flags() # Update flags based on new settings
            self._update_text_display_style() # Apply style changes (font, text alpha)
            self._update_ocr_button_states() # Update button state/tooltip
            self.apply_initial_lock_state()
            self.update() # Redraw window

            # Handle potential hotkey change on reload (unlikely use case, but for completeness)
            if self.hotkey != old_hotkey:
                 logging.warning(f"Hotkey changed during settings reload from '{old_hotkey}' to '{self.hotkey}'. Restart required.")
                 # Cannot dynamically change hotkey here easily.
        else:
            logging.error("SettingsManager not available.")


    def save_settings(self):
        """Saves current application state to settings."""
        if self.settings_manager:
            # Combine the base RGB from window color with the current text area alpha for saving
            base_rgb = self.bg_color.getRgb() # Get RGB from the (fixed alpha) window color
            # Ensure textarea_alpha is valid before creating color
            alpha_to_save = self.textarea_alpha if isinstance(self.textarea_alpha, int) else QColor(config.DEFAULT_BG_COLOR).alpha()
            saved_bg_color_for_settings = QColor(base_rgb[0], base_rgb[1], base_rgb[2], alpha_to_save)

            current_settings_data = {
                'ocr_provider': self.ocr_provider,
                'google_credentials_path': self.google_credentials_path,
                'ocrspace_api_key': self.ocrspace_api_key,
                'ocr_language_code': self.ocr_language_code, # <<< SAVE OCR LANG
                'deepl_api_key': self.deepl_api_key,
                'target_language_code': self.target_language_code,
                'translation_engine_key': self.translation_engine_key,
                'display_font': self.display_font,
                'ocr_interval': self.ocr_interval,
                'bg_color': saved_bg_color_for_settings, # Save color combining base RGB and textarea alpha
                'is_locked': self.is_locked,
                'hotkey': self.hotkey, # <<< SAVE HOTKEY
            }
            current_geometry = self.saveGeometry()
            self.settings_manager.save_all_settings(current_settings_data, current_geometry)
        else: logging.error("SettingsManager not available.")

    # ... (load_history, save_history, clear_history, export_history remain same) ...
    def load_history(self):
        logging.warning("TranslucentBox.load_history() called, but init handles loading.")

    def save_history(self):
        if self.history_manager: self.history_manager.save_history()
        else: logging.error("HistoryManager not available.")

    def clear_history(self):
        if self.history_manager:
            self.history_manager.clear_history(parent_widget=self)
            if not self.history_manager.history_deque: self.text_display.clear()
            # Update settings dialog button states if it were open (complex)
        else: QMessageBox.warning(self, "Error", "History unavailable.")

    def export_history(self):
        if self.history_manager: self.history_manager.export_history(parent_widget=self)
        else: QMessageBox.warning(self, "Error", "History unavailable.")


    def restore_geometry(self, saved_geometry_bytes):
        """Restores window geometry from saved QByteArray."""
        restored = False
        if saved_geometry_bytes and isinstance(saved_geometry_bytes, QByteArray):
            try:
                restored = self.restoreGeometry(saved_geometry_bytes)
                if restored:
                     # Double check if geometry is reasonable (e.g., on screen)
                     # screen_geo = QApplication.desktop().availableGeometry(self)
                     # if not screen_geo.intersects(self.geometry()):
                     #     logging.warning("Restored geometry seems off-screen. Resetting.")
                     #     restored = False # Force default if off-screen
                     pass # Basic check passed
            except Exception as e:
                 logging.error(f"Error restoring geometry: {e}")
                 restored = False
        if restored: logging.debug("Window geometry restored.")
        else:
             logging.debug("Using default geometry (or restore failed).")
             # Set a sensible default size/position
             self.setGeometry(100, 100, 400, 300) # Adjust default size if needed

    def apply_initial_lock_state(self):
        """Applies lock state (currently just affects window opacity)."""
        # Example: Slightly change opacity or visual cue when locked
        opacity = 0.95 if self.is_locked else 1.0 # Subtle visual cue
        self.setWindowOpacity(opacity)
        # Actual move/resize prevention is handled in mouse events
        logging.info(f"Window lock state applied: {'Locked' if self.is_locked else 'Unlocked'}.")

    def _setup_window_properties(self):
        """Sets window flags and attributes."""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(config.MIN_WINDOW_WIDTH, config.MIN_WINDOW_HEIGHT)
        self.setMouseTracking(True) # Needed for hover resize cursors


    def initUI(self):
        """Initializes the user interface widgets."""
        logging.debug("Initializing UI widgets.")
        # Basic styles - consider moving to a dedicated style module
        close_style = "QPushButton { background-color: transparent; border: none; border-radius: 4px; padding: 4px; } QPushButton:hover { background-color: rgba(255, 0, 0, 180); } QPushButton:pressed { background-color: rgba(200, 0, 0, 200); }"
        options_style = "QPushButton { background-color: transparent; border: none; border-radius: 4px; font-size: 16px; padding: 4px; } QPushButton:hover { background-color: rgba(100, 100, 255, 150); } QPushButton:pressed { background-color: rgba(80, 80, 200, 180); }"
        grab_style = "QPushButton { background-color: rgba(200, 200, 200, 100); border: none; border-radius: 4px; font-size: 11px; padding: 4px 8px; color: #333; } QPushButton:hover { background-color: rgba(180, 210, 255, 150); } QPushButton:pressed { background-color: rgba(150, 190, 230, 180); } QPushButton:disabled { background-color: rgba(220, 220, 220, 80); color: #999; }"

        # Close Button
        self.close_button = QPushButton(self)
        close_icon = self.style().standardIcon(QStyle.SP_TitleBarCloseButton)
        self.close_button.setIcon(close_icon)
        self.close_button.setIconSize(QSize(16, 16))
        self.close_button.setFlat(True)
        self.close_button.clicked.connect(self.close)
        self.close_button.setToolTip("Close")
        self.close_button.setStyleSheet(close_style)

        # Options Button
        self.options_button = QPushButton('⚙️', self)
        self.options_button.setFlat(True)
        self.options_button.clicked.connect(self.open_settings_dialog)
        self.options_button.setToolTip("Settings")
        self.options_button.setStyleSheet(options_style)

        # Grab Button
        self.grab_button = QPushButton('Grab Text', self)
        self.grab_button.setFlat(True)
        self.grab_button.clicked.connect(self.grab_text)
        self.grab_button.setStyleSheet(grab_style)

        # Text Display Area
        self.text_display = QTextEdit(self)
        self.text_display.setReadOnly(True)
        self.text_display.setWordWrapMode(QTextOption.WrapAnywhere)
        self.text_display.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.text_display.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # Apply initial style (font and background alpha)
        self._update_text_display_style()


    def _update_text_display_style(self):
        """Updates the QTextEdit style including font and background alpha."""
        if not hasattr(self, 'text_display'): return # Avoid error during early init

        # Ensure display_font is a valid QFont object
        current_font = self.display_font if isinstance(self.display_font, QFont) else QFont()
        self.text_display.setFont(current_font)

        # Ensure textarea_alpha is valid
        current_alpha = self.textarea_alpha if isinstance(self.textarea_alpha, int) else QColor(config.DEFAULT_BG_COLOR).alpha()

        # Use a white base for the text area background for readability
        bg_r, bg_g, bg_b = 255, 255, 255 # White
        # Apply the stored textarea_alpha (convert 0-255 to 0.0-1.0 for CSS)
        alpha_float = max(0.0, min(1.0, current_alpha / 255.0))
        text_bg_color_str = f"rgba({bg_r}, {bg_g}, {bg_b}, {alpha_float:.3f})"

        # Use black text color for contrast
        text_color_str = "#000000"

        # Set the stylesheet
        style = (
            f"QTextEdit {{ "
            f"background-color: {text_bg_color_str}; "
            f"color: {text_color_str}; "
            f"border-radius: 5px; "
            f"padding: 5px; "
            f"}}"
        )
        self.text_display.setStyleSheet(style)
        logging.debug(f"Updated text_display style with alpha {current_alpha} -> {alpha_float:.3f}")


    # --------------------------------------------------------------------------
    # OCR / Worker Interaction
    # --------------------------------------------------------------------------

    def _update_ocr_button_states(self):
        """Update grab button enabled state and tooltip based on selected providers/settings."""
        can_run_ocr = False
        # Use the currently loaded hotkey string for the tooltip <<< UPDATED >>>
        hotkey_display = self.hotkey.replace('+', ' + ').title() if self.hotkey else "N/A"
        base_tooltip = f"Perform OCR/Translate ({hotkey_display})"
        tooltip = base_tooltip # Default tooltip

        self._update_prerequisite_state_flags() # Ensure flags are current

        # Get display names, fall back to keys if not found
        ocr_provider_name = config.AVAILABLE_OCR_PROVIDERS.get(self.ocr_provider, self.ocr_provider)
        trans_engine_name = config.AVAILABLE_ENGINES.get(self.translation_engine_key, self.translation_engine_key)

        # Check OCR prerequisites
        ocr_ready = False
        ocr_tooltip_reason = ""
        if self.ocr_provider == "google_vision":
            if self._is_google_credentials_valid:
                ocr_ready = True
            else:
                ocr_tooltip_reason = f"Set Google Credentials for '{ocr_provider_name}' in Settings (⚙️)"
        elif self.ocr_provider == "ocr_space":
            if self._is_ocrspace_key_set:
                # Check if OCR language is selected (it should have a default)
                if self.ocr_language_code:
                    ocr_ready = True
                else:
                     # Should not happen due to default, but handle just in case
                     ocr_tooltip_reason = f"Select OCR Language for '{ocr_provider_name}' in Settings (⚙️)"
            else:
                ocr_tooltip_reason = f"Set API Key for '{ocr_provider_name}' in Settings (⚙️)"
        else:
            ocr_ready = False # Unknown provider
            ocr_tooltip_reason = f"Unknown OCR Provider '{self.ocr_provider}' selected."

        # Check Translation prerequisites (only if OCR is ready)
        translation_ready = False
        trans_tooltip_reason = ""
        if ocr_ready:
            if self.translation_engine_key == "google_cloud_v3":
                if self._is_google_credentials_valid:
                    translation_ready = True
                else:
                    # If Google OCR was ready, credentials must be valid, this shouldn't be hit unless logic changes
                    trans_tooltip_reason = f"Set Google Credentials for '{trans_engine_name}' in Settings (⚙️)"
            elif self.translation_engine_key == "deepl_free":
                if self._is_deepl_key_set:
                    translation_ready = True
                else:
                    trans_tooltip_reason = f"Set DeepL API Key for '{trans_engine_name}' in Settings (⚙️)"
            elif self.translation_engine_key == "googletrans":
                translation_ready = True # googletrans has no specific key prerequisite here
            else:
                translation_ready = False # Unknown engine
                trans_tooltip_reason = f"Unknown translation engine '{self.translation_engine_key}' selected."

            # Construct final tooltip
            if ocr_ready and translation_ready:
                tooltip = f"{ocr_provider_name} & {trans_engine_name} ({hotkey_display})"
            elif not ocr_ready:
                 tooltip = ocr_tooltip_reason # OCR reason takes priority if it failed
            else: # OCR ready, but translation failed
                 tooltip = trans_tooltip_reason

            can_run_ocr = ocr_ready and translation_ready
        else:
            # If OCR not ready, use the OCR reason for the tooltip
             tooltip = ocr_tooltip_reason

        self.grab_button.setEnabled(can_run_ocr)
        self.grab_button.setToolTip(tooltip)

        # If live mode is on but we can no longer run, stop it
        if self.is_live_mode and not can_run_ocr:
            self.toggle_live_mode() # This will stop the timer and update button text


    def check_ocr_prerequisites(self, prompt_if_needed=False):
        """Check if prerequisites for the *currently selected* OCR and Translation providers are met."""
        ocr_prereqs_met = False
        trans_prereqs_met = False
        missing = []
        self._update_prerequisite_state_flags() # Ensure flags are current

        ocr_provider_name = config.AVAILABLE_OCR_PROVIDERS.get(self.ocr_provider, self.ocr_provider)
        trans_engine_name = config.AVAILABLE_ENGINES.get(self.translation_engine_key, self.translation_engine_key)

        # Check OCR Provider
        if self.ocr_provider == "google_vision":
            if self._is_google_credentials_valid: ocr_prereqs_met = True
            else: missing.append(f"Google Credentials (for {ocr_provider_name})")
        elif self.ocr_provider == "ocr_space":
            # OCR.space needs API key and selected language (should always have a default)
            if self._is_ocrspace_key_set and self.ocr_language_code: ocr_prereqs_met = True
            if not self._is_ocrspace_key_set: missing.append(f"API Key (for {ocr_provider_name})")
            # if not self.ocr_language_code: missing.append(f"OCR Language Selection (for {ocr_provider_name})") # Unlikely due to default
        else:
             missing.append(f"Configuration for unknown OCR Provider '{self.ocr_provider}'")

        # Check Translation Provider
        if self.translation_engine_key == "google_cloud_v3":
            if self._is_google_credentials_valid: trans_prereqs_met = True
            # Add to missing list only if Google credentials weren't already marked as missing by OCR check
            elif not any("Google Credentials" in item for item in missing):
                 missing.append(f"Google Credentials (for {trans_engine_name})")

        elif self.translation_engine_key == "deepl_free":
            if self._is_deepl_key_set: trans_prereqs_met = True
            else: missing.append(f"DeepL API Key (for {trans_engine_name})")
        elif self.translation_engine_key == "googletrans":
            trans_prereqs_met = True # No specific prerequisite to check here
        else:
             missing.append(f"Configuration for unknown Translation Engine '{self.translation_engine_key}'")

        # Final check based on individual flags
        all_prereqs_met = ocr_prereqs_met and trans_prereqs_met

        if not all_prereqs_met and prompt_if_needed:
            # Use the unique list of missing items generated above
            missing_str = "\n- ".join(missing) if missing else "Unknown reason"
            logging.info(f"OCR/Translate prereqs missing for '{ocr_provider_name}'/'{trans_engine_name}'. Prompting.")
            msg = f"Required configuration missing:\n\n- {missing_str}\n\nConfigure in Settings (⚙️)."
            QMessageBox.warning(self, "Config Needed", msg)
            self.open_settings_dialog() # Open settings to allow user to fix
            # Re-check after dialog (user might have fixed it)
            return self.check_ocr_prerequisites(prompt_if_needed=False) # Re-run check without prompt

        self._update_ocr_button_states() # Update button based on check result
        return all_prereqs_met


    def grab_text(self):
        """Initiates the screen capture, OCR, and translation process."""
        # Prevent running if already running
        if self.ocr_running:
            logging.warning("OCR already running.")
            # Optionally provide user feedback, e.g., status bar message
            return

        # Check prerequisites before starting
        if not self.check_ocr_prerequisites(prompt_if_needed=True):
            logging.warning("OCR cancelled: Prerequisite check failed.")
            return

        # --- Start OCR Process ---
        self.ocr_running = True
        logging.debug("Starting OCR worker...")
        self.grab_button.setText("Working...")
        self.grab_button.setEnabled(False) # Disable button immediately

        # Hide the text display area to capture underneath it
        # (Ensure this happens before geometry calculation if based on display)
        self.text_display.hide()
        QApplication.processEvents() # Try to force repaint before capture

        try:
            # Calculate the screen region to capture based on text display geometry
            geo = self.geometry() # Window's overall geometry
            content_rect = self.text_display.geometry() # Text display's geometry *relative to window*

            if not geo.isValid() or not content_rect.isValid():
                raise ValueError("Invalid window or text_display geometry.")

            # Calculate absolute screen coordinates for capture
            monitor = {
                "top": geo.top() + content_rect.top(),       # Window top + text_display top
                "left": geo.left() + content_rect.left(),     # Window left + text_display left
                "width": content_rect.width(),                # text_display width
                "height": content_rect.height()               # text_display height
            }

            # Ensure calculated width/height are valid
            if monitor["width"] <= 0 or monitor["height"] <= 0:
                 raise ValueError(f"Invalid calculated capture dimensions: w={monitor['width']},h={monitor['height']}")

            logging.debug(f"Calculated monitor region (based on text_display): {monitor}")

        except Exception as e:
            logging.exception("Error calculating capture region geometry:")
            # Ensure UI is reset even if geometry calculation fails
            self.on_ocr_error(f"Capture Region Error: {e}") # Show error
            self.text_display.show() # Ensure text display is shown again on error
            # Manually reset state if thread never started
            self.ocr_running = False
            self._update_ocr_button_states()
            if not self.is_live_mode: self.grab_button.setText("Grab Text")
            return # Stop execution

        # Prepare data for the worker
        history_snapshot = self.history_manager.get_history_list() if self.history_manager else []

        # Setup and start the worker thread
        self.thread = QThread(self)
        self.worker = OCRWorker(
            monitor=monitor, # Pass calculated monitor dictionary
            selected_ocr_provider=self.ocr_provider,
            google_credentials_path=self.google_credentials_path,
            ocrspace_api_key=self.ocrspace_api_key,
            ocr_language_code=self.ocr_language_code,
            target_language_code=self.target_language_code,
            history_data=history_snapshot,
            selected_trans_engine_key=self.translation_engine_key,
            deepl_api_key=self.deepl_api_key
        )

        self.worker.moveToThread(self.thread)

        # Connect signals from worker to slots in this (GUI) thread
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_ocr_done)
        self.worker.error.connect(self.on_ocr_error)
        # Ensure thread quits and objects are deleted on finish/error
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit) # Ensure quit on error too
        # Use deleteLater for safer cleanup
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        # Connect thread finished signal to our final cleanup slot
        self.thread.finished.connect(self.on_thread_finished)

        self.thread.start()
        logging.debug("OCR worker thread started.")

    @pyqtSlot(str, str)
    def on_ocr_done(self, ocr_text, translated_text):
        """Handles successful OCR and translation results from the worker."""
        # Ensure text display is visible before updating
        self.text_display.show()

        logging.info("OCR results received.")
        # Add to history (manager handles duplicates)
        if self.history_manager: self.history_manager.add_item(ocr_text, translated_text)

        # Prepare text for display (HTML escaping for safety)
        safe_ocr = html.escape(ocr_text or "")
        safe_trans = translated_text or "" # Translation might contain error messages, don't escape fully yet
        lang = html.escape(self.target_language_code.upper())
        ocr_fmt = safe_ocr.replace('\n', '<br/>') # Basic formatting
        trans_fmt = safe_trans # Keep potential error format

        # Determine if translation was an error message
        is_error = isinstance(safe_trans, str) and safe_trans.startswith("[") and "Error:" in safe_trans
        if not is_error:
             trans_fmt = html.escape(safe_trans).replace('\n', '<br/>') # Escape if not error

        # Apply font style consistently
        font_style = f"font-family:'{self.display_font.family()}'; font-size:{self.display_font.pointSize()}pt;"
        err_style = "color:#A00;"
        ok_style = "color:#005;" # Or use default text color

        # Get provider/engine names for display
        ocr_provider_name = config.AVAILABLE_OCR_PROVIDERS.get(self.ocr_provider, self.ocr_provider)
        trans_engine_name = config.AVAILABLE_ENGINES.get(self.translation_engine_key, self.translation_engine_key)

        # Construct HTML output
        html_out = f"""
           <div style="margin-bottom:10px;">
               <b style="color:#333;">--- OCR ({ocr_provider_name}) ---</b><br/>
               <div style="color:#000; margin-left:5px; {font_style}">
                   {ocr_fmt if ocr_fmt else '<i style="color:#777;">No text detected.</i>'}
               </div>
           </div>
           <div>
               <b style="color:#333;">--- Translation ({trans_engine_name} / {lang}) ---</b><br/>
               <div style="margin-left:5px; {font_style} {err_style if is_error else ok_style}">
                   {trans_fmt if trans_fmt else ('<i style="color:#777;">N/A (No OCR text)</i>' if not ocr_fmt else '<i style="color:#777;">No translation result.</i>')}
               </div>
           </div>
           """
        self.text_display.setAlignment(Qt.AlignLeft)
        self.text_display.setHtml(html_out)
        # Note: on_thread_finished will handle resetting button state later

    @pyqtSlot(str)
    def on_ocr_error(self, error_msg):
        """Handles error messages from the worker thread."""
        # Ensure text display is visible
        self.text_display.show()

        logging.error(f"Worker error signal received: {error_msg}")
        # Apply font style to error message
        font_style = f"font-family:'{self.display_font.family()}'; font-size:{self.display_font.pointSize()}pt;"
        err_html = f"""
           <p style="color:#A00;font-weight:bold;">--- Error ---</p>
           <p style="color:#A00; {font_style}">{html.escape(error_msg)}</p>
           """
        self.text_display.setAlignment(Qt.AlignLeft)
        self.text_display.setHtml(err_html)
        # Note: on_thread_finished is connected to thread.finished signal,
        # so UI state reset will happen there automatically after error signal.

    @pyqtSlot()
    def on_thread_finished(self):
        """Cleans up after the worker thread finishes (success or error)."""
        logging.debug("Worker thread finished signal received. Resetting UI state.")

        # Ensure text display is visible, just in case
        if hasattr(self, 'text_display') and not self.text_display.isVisible():
             logging.warning("Thread finished but text display was hidden. Showing.")
             self.text_display.show()

        # Reset OCR running flag
        self.ocr_running = False

        # Update grab button state and text (based on whether live mode is active)
        self._update_ocr_button_states() # Updates enabled state and tooltip first
        if self.grab_button.isEnabled(): # Only change text if it's enabled
             if self.is_live_mode:
                  self.grab_button.setText("Live...") # Keep live text if still live
             else:
                  self.grab_button.setText("Grab Text") # Reset to default

        # Worker and thread objects are set to deleteLater, no need to nullify here explicitly
        # self.thread = None
        # self.worker = None


    # --------------------------------------------------------------------------
    # Settings Dialog Interaction
    # --------------------------------------------------------------------------
    def open_settings_dialog(self):
        """Opens the settings configuration dialog."""
        if 'SettingsDialog' not in globals() or not SettingsDialog:
             QMessageBox.critical(self, "Error", "SettingsDialog component not loaded correctly.")
             return
        logging.debug("Opening settings dialog...")

        # --- Prepare current data for dialog ---
        # Use the RGB from self.bg_color (which has fixed alpha) and combine with self.textarea_alpha
        current_base_rgb = self.bg_color.getRgb()
        current_alpha = self.textarea_alpha if isinstance(self.textarea_alpha, int) else QColor(config.DEFAULT_BG_COLOR).alpha()
        current_color_for_dialog = QColor(current_base_rgb[0], current_base_rgb[1], current_base_rgb[2], current_alpha)
        current_font = self.display_font if isinstance(self.display_font, QFont) else QFont()
        current_hotkey = self.hotkey if isinstance(self.hotkey, str) else config.DEFAULT_HOTKEY

        current_data = {
            'ocr_provider': self.ocr_provider,
            'google_credentials_path': self.google_credentials_path,
            'ocrspace_api_key': self.ocrspace_api_key,
            'ocr_language_code': self.ocr_language_code, # <<< PASS OCR LANG
            'deepl_api_key': self.deepl_api_key,
            'target_language_code': self.target_language_code, # Target for translation
            'translation_engine': self.translation_engine_key,
            'display_font': current_font,
            'bg_color': current_color_for_dialog, # Pass color with text area alpha
            'ocr_interval': self.ocr_interval,
            'is_locked': self.is_locked,
            'hotkey': current_hotkey, # <<< PASS CURRENT HOTKEY
        }
        dialog = SettingsDialog(self, current_data)

        if dialog.exec_() == QDialog.Accepted:
            logging.debug("Settings dialog accepted. Applying...")
            updated = dialog.get_updated_settings()
            old_hotkey = self.hotkey # Store old hotkey for comparison

            # Update attributes from dialog result
            self.ocr_provider = updated.get('ocr_provider', self.ocr_provider)
            self.google_credentials_path=updated.get('google_credentials_path')
            self.ocrspace_api_key=updated.get('ocrspace_api_key')
            self.ocr_language_code = updated.get('ocr_language_code', self.ocr_language_code) # <<< GET OCR LANG
            self.deepl_api_key=updated.get('deepl_api_key')
            self.target_language_code=updated.get('target_language_code', self.target_language_code)
            self.translation_engine_key=updated.get('translation_engine', self.translation_engine_key)

            # Safely update font
            new_font = updated.get('display_font')
            self.display_font = new_font if isinstance(new_font, QFont) else self.display_font

            # Safely update interval
            new_interval = updated.get('ocr_interval')
            self.ocr_interval = new_interval if isinstance(new_interval, int) and new_interval > 0 else self.ocr_interval

            self.is_locked=updated.get('is_locked', self.is_locked)

            # Safely update hotkey <<< NEW >>>
            new_hotkey = updated.get('hotkey')
            self.hotkey = new_hotkey if isinstance(new_hotkey, str) and new_hotkey else self.hotkey


            # --- Handle background color alpha update ---
            # The dialog returns 'bg_alpha' which is the desired alpha for the text area
            new_alpha = updated.get('bg_alpha') # Get alpha value (0-255) from dialog settings
            if isinstance(new_alpha, int):
                self.textarea_alpha = max(0, min(255, new_alpha)) # Clamp alpha value
            else:
                 logging.warning("Invalid alpha value received from settings dialog. Keeping old value.")
                 # Keep existing self.textarea_alpha

            # The main window background color (self.bg_color) keeps its fixed alpha
            # No need to update self.bg_color's alpha here

            # --- Handle Hotkey Change --- <<< MODIFIED >>>
            if self.hotkey != old_hotkey:
                logging.info(f"Hotkey changed from '{old_hotkey}' to '{self.hotkey}'. Restart required to apply.")
                QMessageBox.information(self, "Hotkey Changed",
                                        f"The hotkey has been changed to '{self.hotkey}'.\n\n"
                                        "Please restart the application for the change to take effect.")
                # Dynamic change is complex and not implemented. User must restart.

            # Apply other settings visually
            self._update_prerequisite_state_flags() # Update flags based on new settings
            self._update_text_display_style()   # Re-apply style with potentially new alpha/font for text area
            self.apply_initial_lock_state()      # Apply lock state / window opacity
            self.update()                        # Trigger repaint for main window (uses self.bg_color with fixed alpha)
            self._update_ocr_button_states()      # Update button state/tooltip
            self.save_settings()                 # Save the applied settings (save_settings handles combining color correctly)
            logging.debug("Settings applied and saved.")
        else:
            logging.debug("Settings dialog cancelled.")


    # --------------------------------------------------------------------------
    # Window Interaction (Mouse, Paint) - Kept in main class
    # --------------------------------------------------------------------------
    def resizeEvent(self, event):
        """Handles window resize events to reposition widgets."""
        # --- Layout Adjustments ---
        btn_sz, btn_m, txt_m = 28, 5, 8 # Button size, button margin, text margin
        top_h = btn_sz + (btn_m * 2) # Height of the top control area
        grab_w = 70 # Width of the grab button

        # Check if widgets exist before geometry calls
        if hasattr(self, 'close_button'): self.close_button.setGeometry(self.width() - btn_sz - btn_m, btn_m, btn_sz, btn_sz)
        if hasattr(self, 'options_button'): self.options_button.setGeometry(self.close_button.x() - btn_sz - btn_m, btn_m, btn_sz, btn_sz)
        if hasattr(self, 'grab_button'): self.grab_button.setGeometry(btn_m, btn_m, grab_w, btn_sz)

        # Position text display area below buttons
        if hasattr(self, 'text_display'):
            txt_w = max(config.MIN_WINDOW_WIDTH - (txt_m * 2), self.width() - (txt_m * 2)) # Ensure min width respected
            txt_h = max(config.MIN_WINDOW_HEIGHT - top_h - txt_m, self.height() - top_h - txt_m) # Ensure min height respected
            self.text_display.setGeometry(txt_m, top_h, txt_w, txt_h)

        # --- Call Superclass ---
        super().resizeEvent(event) # Important for proper widget resizing


    def paintEvent(self, event):
        """Paints the main window's background, excluding the text area."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # --- Define Colors ---
        # Use the configured background color for the frame/title bar
        frame_color = self.bg_color
        if not isinstance(frame_color, QColor) or not frame_color.isValid():
            logging.warning(f"Invalid self.bg_color detected during paintEvent: {self.bg_color}. Using default.")
            frame_color = QColor(config.DEFAULT_BG_COLOR) # Use default config color

        # --- Define Geometry ---
        window_rect = self.rect()
        # Ensure text_display exists before getting geometry
        text_area_rect = self.text_display.geometry() if hasattr(self, 'text_display') else QRect()
        border_radius = 7 # Keep the rounded corners consistent

        # --- Create Drawing Paths ---
        full_window_path = QPainterPath()
        # Convert QRect to QRectF and ensure radii are floats
        full_window_path.addRoundedRect(QRectF(window_rect), float(border_radius), float(border_radius))

        # Path for the text area rectangle - QRectF might be safer here too
        text_area_path = QPainterPath()
        if text_area_rect.isValid(): # Only subtract if valid
             text_area_path.addRect(QRectF(text_area_rect)) # Convert this too for consistency

        # --- Calculate Background Path (Window MINUS Text Area) ---
        # Subtract the text area path from the full window path if text area is valid
        background_path = full_window_path
        if text_area_rect.isValid():
             background_path = full_window_path.subtracted(text_area_path)


        # --- Draw the Background ---
        painter.setPen(Qt.NoPen) # No border for the background fill
        painter.setBrush(QBrush(frame_color))
        # Draw only the calculated background path (excluding the text area)
        painter.drawPath(background_path)

        # Optional: Draw a border around the whole window if desired
        # border_pen = QPen(QColor(255, 255, 255, 50)) # Example: faint white border
        # border_pen.setWidth(1)
        # painter.setPen(border_pen)
        # painter.setBrush(Qt.NoBrush)
        # painter.drawPath(full_window_path) # Draw the outline


    def mousePressEvent(self, event):
        """Handles mouse button presses for dragging and resizing."""
        # Ignore if locked
        if self.is_locked: return

        if event.button() == Qt.LeftButton:
            self.drag_pos = None # Reset drag position
            self.resizing = False # Reset resizing flag
            pos = event.pos()
            self.detect_resize_edges(pos) # Check if cursor is near edge

            if any(self.resizing_edges.values()):
                self.resizing = True
                self.resize_start_pos = event.globalPos() # Store global start pos for resize calc
                self.original_geometry = self.geometry() # Store original geometry
                logging.debug("Starting resize.")
            else:
                # Check if click is in the 'title bar' area (excluding buttons/text area)
                title_h = 35 # Approximate title bar height for dragging
                # Define rectangles for interactive elements to exclude from drag
                close_rect = self.close_button.geometry() if hasattr(self, 'close_button') else QRect()
                opts_rect = self.options_button.geometry() if hasattr(self, 'options_button') else QRect()
                grab_rect_btn = self.grab_button.geometry() if hasattr(self, 'grab_button') else QRect()
                text_rect = self.text_display.geometry() if hasattr(self, 'text_display') else QRect()

                # Check if click is within title height but NOT on buttons or text area
                is_on_widget = (close_rect.contains(pos) or
                                opts_rect.contains(pos) or
                                grab_rect_btn.contains(pos) or
                                text_rect.contains(pos))

                if pos.y() < title_h and not is_on_widget:
                    # Start dragging
                    self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
                    self.setCursor(Qt.SizeAllCursor) # Provide visual feedback
                    logging.debug("Starting drag.")
                else:
                    # Click was on a widget or outside title bar, unset cursor
                    self.unsetCursor()


    def mouseMoveEvent(self, event):
        """Handles mouse movement for dragging and resizing."""
        # Ignore if locked
        if self.is_locked: return

        # Determine current state
        is_left_button_down = event.buttons() == Qt.LeftButton
        is_dragging = self.drag_pos is not None and is_left_button_down
        is_resizing = self.resizing and is_left_button_down

        if is_dragging:
            # Move window based on drag position
            self.move(event.globalPos() - self.drag_pos)
        elif is_resizing:
            # Handle resize logic
            self.handle_resize(event.globalPos())
        else:
            # Update resize cursor if mouse is just moving over edges (no button down)
            self.set_resize_cursor(event.pos())


    def mouseReleaseEvent(self, event):
        """Handles mouse button releases to stop dragging/resizing."""
        if event.button() == Qt.LeftButton:
            self.drag_pos = None
            self.resizing = False
            self.resizing_edges = {k: False for k in self.resizing_edges} # Reset edge flags
            self.unsetCursor() # Restore default cursor
            if self.is_locked: # Ensure locked state cursor (shouldn't be needed if move/press are blocked)
                 pass
            logging.debug("Mouse released, drag/resize finished.")


    def detect_resize_edges(self, pos):
        """Detects if the mouse position is within the resize margin of window edges."""
        if self.is_locked:
            self.resizing_edges = {k: False for k in self.resizing_edges}
            return

        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        margin = config.RESIZE_MARGIN

        self.resizing_edges['left'] = (0 <= x < margin)
        self.resizing_edges['top'] = (0 <= y < margin)
        # Adjust right/bottom check to include the margin fully
        self.resizing_edges['right'] = (w - margin < x <= w)
        self.resizing_edges['bottom'] = (h - margin < y <= h)


    def set_resize_cursor(self, pos):
        """Sets the appropriate resize cursor based on mouse position near edges."""
        # Don't change cursor if locked, currently resizing, or dragging
        if self.is_locked or self.resizing or (self.drag_pos and QApplication.mouseButtons() == Qt.LeftButton):
            return

        self.detect_resize_edges(pos)
        edges = self.resizing_edges # Use dictionary keys

        if (edges['left'] and edges['top']) or (edges['right'] and edges['bottom']):
            self.setCursor(Qt.SizeFDiagCursor) # Diagonal NW-SE / SW-NE
        elif (edges['right'] and edges['top']) or (edges['left'] and edges['bottom']):
            self.setCursor(Qt.SizeBDiagCursor) # Diagonal NE-SW / NW-SE
        elif edges['left'] or edges['right']:
            self.setCursor(Qt.SizeHorCursor) # Horizontal
        elif edges['top'] or edges['bottom']:
            self.setCursor(Qt.SizeVerCursor) # Vertical
        else:
            self.unsetCursor() # Default arrow cursor


    def handle_resize(self, global_pos):
        """Calculates and applies the new window geometry during resizing."""
        if not self.resizing: return

        delta = global_pos - self.resize_start_pos
        new_rect = QRect(self.original_geometry) # Start with original geometry

        min_w, min_h = config.MIN_WINDOW_WIDTH, config.MIN_WINDOW_HEIGHT

        # Adjust right edge
        if self.resizing_edges['right']:
             new_rect.setWidth(max(min_w, self.original_geometry.width() + delta.x()))

        # Adjust bottom edge
        if self.resizing_edges['bottom']:
             new_rect.setHeight(max(min_h, self.original_geometry.height() + delta.y()))

        # Adjust left edge (moves top-left corner and potentially width)
        if self.resizing_edges['left']:
             new_left = self.original_geometry.left() + delta.x()
             # Prevent shrinking beyond minimum width by adjusting left edge relative to right edge
             max_left = new_rect.right() - min_w + 1 # Calculate max allowed left pos
             new_left = min(new_left, max_left) # Ensure left doesn't go too far right
             new_rect.setLeft(new_left)

        # Adjust top edge (moves top-left corner and potentially height)
        if self.resizing_edges['top']:
             new_top = self.original_geometry.top() + delta.y()
             # Prevent shrinking beyond minimum height
             max_top = new_rect.bottom() - min_h + 1 # Calculate max allowed top pos
             new_top = min(new_top, max_top) # Ensure top doesn't go too far down
             new_rect.setTop(new_top)

        # Final geometry check (should be redundant if logic above is correct, but safe)
        if new_rect.width() < min_w: new_rect.setWidth(min_w)
        if new_rect.height() < min_h: new_rect.setHeight(min_h)

        self.setGeometry(new_rect)


    # --------------------------------------------------------------------------
    # Application Lifecycle & Live Mode
    # --------------------------------------------------------------------------
    def closeEvent(self, event):
        """Handles the window close event for cleanup."""
        logging.info("Close event received. Cleaning up...");
        # Stop timers
        self.live_mode_timer.stop()

        # --- Unregister Hotkeys --- <<< ENSURE THIS IS CALLED
        logging.debug("Calling unregister_hotkeys...")
        if 'unregister_hotkeys' in globals() and callable(unregister_hotkeys):
             try:
                 unregister_hotkeys()
             except Exception: # Use broad exception during cleanup
                  logging.exception("Hotkey unregister failed during close:")
        else:
             logging.warning("unregister_hotkeys function not found.")


        # Ensure worker thread finishes cleanly if running
        if self.thread and self.thread.isRunning():
            logging.warning("Worker thread active on close. Requesting quit...")
            self.thread.quit() # Ask thread's event loop to exit
            if not self.thread.wait(1000): # Wait up to 1 second
                 logging.error("Worker thread did not finish cleanly on close. Forcing termination possibility.")
                 # self.thread.terminate() # Use terminate only as a last resort, can cause issues
            else:
                 logging.debug("Worker thread finished.")

        # Save state
        self.save_history()
        self.save_settings()

        logging.info("Cleanup finished. Exiting application.")
        event.accept()
        QApplication.instance().quit() # Ensure application quits


    def toggle_live_mode(self):
        """Toggles the automatic OCR/translation mode."""
        # Check prerequisites before starting
        if not self.is_live_mode:
             if not self.check_ocr_prerequisites(prompt_if_needed=False): # Don't prompt here, just check
                 ocr_provider_name = config.AVAILABLE_OCR_PROVIDERS.get(self.ocr_provider, self.ocr_provider)
                 trans_engine_name = config.AVAILABLE_ENGINES.get(self.translation_engine_key, self.translation_engine_key)
                 QMessageBox.warning(self, "Config Needed", f"Check prerequisites for '{ocr_provider_name}' and '{trans_engine_name}' in Settings (⚙️) to start Live Mode.")
                 return

        # Toggle state
        if self.is_live_mode:
             self.is_live_mode = False
             self.live_mode_timer.stop()
             logging.info("Live Mode stopped.")
             # Update button state/tooltip (will reset text if enabled)
             self._update_ocr_button_states()
        else:
             self.is_live_mode = True
             # Ensure interval is valid before starting timer
             interval_ms = max(1000, self.ocr_interval * 1000) # Use at least 1 second
             self.live_mode_timer.setInterval(interval_ms) # Set interval before starting
             self.live_mode_timer.start()
             logging.info(f"Live Mode started (Interval: {interval_ms / 1000.0}s).")
             # Update button immediately
             self.grab_button.setText("Live...")
             self.grab_button.setEnabled(False) # Disable manual grab while live is starting/running
             self.grab_text() # Perform initial grab immediately
             # Note: Button will re-enable/disable in on_thread_finished or _update_ocr_button_states