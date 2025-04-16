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
from src.core.hotkey_manager import setup_hotkey, unregister_hotkeys
from src.gui.settings_dialog import SettingsDialog


class TranslucentBox(QWidget):
    """
    Main application window. Orchestrates UI, settings, history, and OCR.
    Delegates settings/history persistence to manager classes.
    """
    # ...(Initialization __init__, etc. need adjustments)...
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
        if 'setup_hotkey' in globals() and callable(setup_hotkey):
             setup_hotkey(self.grab_text)
        else: logging.error("Hotkey setup failed.")

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
        self.display_font = settings_dict.get('display_font', QFont())
        self.ocr_interval = settings_dict.get('ocr_interval', config.DEFAULT_OCR_INTERVAL_SECONDS)
        self.is_locked = settings_dict.get('is_locked', False)

        # --- Handle Colors ---
        loaded_bg_color = settings_dict.get('bg_color', QColor(config.DEFAULT_BG_COLOR))
        if not isinstance(loaded_bg_color, QColor) or not loaded_bg_color.isValid():
            logging.warning(f"Invalid bg_color loaded ('{loaded_bg_color}'). Using default.")
            loaded_bg_color = QColor(config.DEFAULT_BG_COLOR)

        # Set window background color with fixed alpha from config default
        default_win_alpha = config.DEFAULT_BG_COLOR.alpha()
        self.bg_color = QColor(0, 0, 0, 255)
        # Store the alpha from the loaded setting specifically for the text area
        self.textarea_alpha = loaded_bg_color.alpha()


        # Validation / Type Checking
        if self.ocr_provider not in config.AVAILABLE_OCR_PROVIDERS: self.ocr_provider = config.DEFAULT_OCR_PROVIDER
        if self.translation_engine_key not in config.AVAILABLE_ENGINES: self.translation_engine_key = config.DEFAULT_TRANSLATION_ENGINE
        if not isinstance(self.display_font, QFont): self.display_font = QFont()
        # bg_color and textarea_alpha already handled/validated above
        if not isinstance(self.ocr_interval, int) or self.ocr_interval <= 0: self.ocr_interval = config.DEFAULT_OCR_INTERVAL_SECONDS
        # Validate OCR language code only if OCR.space is selected
        if self.ocr_provider == 'ocr_space' and self.ocr_language_code not in config.OCR_SPACE_LANGUAGES:
             self.ocr_language_code = config.DEFAULT_OCR_LANGUAGE


        logging.debug("Applied loaded settings to TranslucentBox attributes.")

    # (_update_prerequisite_state_flags, load_settings, save_settings, load_history,
    #  save_history, clear_history, export_history, restore_geometry, apply_initial_lock_state,
    #  _setup_window_properties, initUI, _update_text_display_style remain the same)
    def _update_prerequisite_state_flags(self):
        """Updates internal flags based on current credentials/keys."""
        self._is_google_credentials_valid = bool(self.google_credentials_path and os.path.exists(self.google_credentials_path))
        self._is_ocrspace_key_set = bool(self.ocrspace_api_key)
        self._is_deepl_key_set = bool(self.deepl_api_key)

    def load_settings(self):
        if self.settings_manager:
            settings_dict = self.settings_manager.load_all_settings()
            self._apply_loaded_settings(settings_dict) # Apply loaded settings
            self._update_prerequisite_state_flags() # Update flags based on new settings
            self._update_text_display_style() # Apply style changes (font, text alpha)
            self._update_ocr_button_states() # Update button state/tooltip
            self.apply_initial_lock_state()
            self.update() # Redraw window (uses self.bg_color with fixed alpha)
        else: logging.error("SettingsManager not available.")

    def save_settings(self):
        if self.settings_manager:
            # Combine the base RGB from window color with the current text area alpha for saving
            base_rgb = self.bg_color.getRgb() # Get RGB from the (fixed alpha) window color
            saved_bg_color_for_settings = QColor(base_rgb[0], base_rgb[1], base_rgb[2], self.textarea_alpha)

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
            }
            current_geometry = self.saveGeometry()
            self.settings_manager.save_all_settings(current_settings_data, current_geometry)
        else: logging.error("SettingsManager not available.")

    def load_history(self):
        logging.warning("TranslucentBox.load_history() called, but init handles loading.")

    def save_history(self):
        if self.history_manager: self.history_manager.save_history()
        else: logging.error("HistoryManager not available.")

    def clear_history(self):
        if self.history_manager:
            self.history_manager.clear_history(parent_widget=self)
            if not self.history_manager.history_deque: self.text_display.clear()
        else: QMessageBox.warning(self, "Error", "History unavailable.")

    def export_history(self):
        if self.history_manager: self.history_manager.export_history(parent_widget=self)
        else: QMessageBox.warning(self, "Error", "History unavailable.")

    def restore_geometry(self, saved_geometry_bytes):
        restored = False
        if saved_geometry_bytes and isinstance(saved_geometry_bytes, QByteArray):
            restored = self.restoreGeometry(saved_geometry_bytes)
        if restored: logging.debug("Window geometry restored.")
        else: logging.debug("Using default geometry."); self.setGeometry(100, 100, 350, 250)

    def apply_initial_lock_state(self):
         opacity = 0.95 if self.is_locked else 1.0; self.setWindowOpacity(opacity)
         logging.info(f"Window lock state applied: {'Locked' if self.is_locked else 'Unlocked'}.")

    def _setup_window_properties(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground); self.setMinimumSize(config.MIN_WINDOW_WIDTH, config.MIN_WINDOW_HEIGHT)
        self.setMouseTracking(True)
        # Optional: Try enabling High DPI scaling explicitly if not default
        # QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        # QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)


    def initUI(self):
        logging.debug("Initializing UI widgets.")
        close_style = "QPushButton { background-color: transparent; border: none; border-radius: 4px; padding: 4px; } QPushButton:hover { background-color: rgba(255, 0, 0, 180); } QPushButton:pressed { background-color: rgba(200, 0, 0, 200); }"
        options_style = "QPushButton { background-color: transparent; border: none; border-radius: 4px; font-size: 16px; padding: 4px; } QPushButton:hover { background-color: rgba(100, 100, 255, 150); } QPushButton:pressed { background-color: rgba(80, 80, 200, 180); }"
        grab_style = "QPushButton { background-color: rgba(200, 200, 200, 100); border: none; border-radius: 4px; font-size: 11px; padding: 4px 8px; color: #333; } QPushButton:hover { background-color: rgba(180, 210, 255, 150); } QPushButton:pressed { background-color: rgba(150, 190, 230, 180); } QPushButton:disabled { background-color: rgba(220, 220, 220, 80); color: #999; }"
        self.close_button = QPushButton(self); btn_icon = self.style().standardIcon(QStyle.SP_TitleBarCloseButton)
        self.close_button.setIcon(btn_icon); self.close_button.setIconSize(QSize(16, 16)); self.close_button.setFlat(True)
        self.close_button.clicked.connect(self.close); self.close_button.setToolTip("Close"); self.close_button.setStyleSheet(close_style)
        self.options_button = QPushButton('⚙️', self); self.options_button.setFlat(True)
        self.options_button.clicked.connect(self.open_settings_dialog); self.options_button.setToolTip("Settings"); self.options_button.setStyleSheet(options_style)
        self.grab_button = QPushButton('Grab Text', self); self.grab_button.setFlat(True)
        self.grab_button.clicked.connect(self.grab_text); self.grab_button.setStyleSheet(grab_style)
        self.text_display = QTextEdit(self); self.text_display.setReadOnly(True); self.text_display.setWordWrapMode(QTextOption.WrapAnywhere)
        self.text_display.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded); self.text_display.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # Apply initial style (font and background alpha)
        self._update_text_display_style()

    def _update_text_display_style(self):
        """Updates the QTextEdit style including font and background alpha."""
        if not hasattr(self, 'text_display'): return # Avoid error during early init

        if not isinstance(self.display_font, QFont): self.display_font = QFont()
        self.text_display.setFont(self.display_font)

        # Ensure textarea_alpha is initialized if called early
        if not hasattr(self, 'textarea_alpha'):
             self.textarea_alpha = config.DEFAULT_BG_COLOR.alpha()

        # Use a white base for the text area background for readability
        bg_r, bg_g, bg_b = 255, 255, 255 # White
        # Apply the stored textarea_alpha (convert 0-255 to 0.0-1.0 for CSS)
        alpha_float = max(0.0, min(1.0, self.textarea_alpha / 255.0))
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
        logging.debug(f"Updated text_display style with alpha {self.textarea_alpha} -> {alpha_float:.3f}")


    # --------------------------------------------------------------------------
    # OCR / Worker Interaction (Methods starting with _)
    # --------------------------------------------------------------------------
    # <<< REMOVED hide_window_for_capture and show_window_after_capture slots >>>

    # (_update_ocr_button_states, check_ocr_prerequisites remain the same)
    def _update_ocr_button_states(self):
        """Update grab button enabled state and tooltip based on selected providers/settings."""
        can_run_ocr = False
        tooltip = f"Perform OCR/Translate ({config.HOTKEY})"
        self._update_prerequisite_state_flags() # Ensure flags are current

        ocr_provider_name = config.AVAILABLE_OCR_PROVIDERS.get(self.ocr_provider, self.ocr_provider)
        trans_engine_name = config.AVAILABLE_ENGINES.get(self.translation_engine_key, self.translation_engine_key)

        # Check OCR prerequisites
        ocr_ready = False
        if self.ocr_provider == "google_vision":
            if self._is_google_credentials_valid:
                ocr_ready = True
            else:
                tooltip = f"Set Google Credentials for '{ocr_provider_name}' in Settings (⚙️)"
        elif self.ocr_provider == "ocr_space":
            if self._is_ocrspace_key_set:
                # Check if OCR language is selected (it should have a default)
                if self.ocr_language_code:
                    ocr_ready = True
                else:
                     tooltip = f"Select OCR Language for '{ocr_provider_name}' in Settings (⚙️)" # Should not happen due to default
            else:
                tooltip = f"Set API Key for '{ocr_provider_name}' in Settings (⚙️)"
        else:
            ocr_ready = False # Unknown provider
            tooltip = f"Unknown OCR Provider '{self.ocr_provider}' selected."

        # Check Translation prerequisites (only if OCR is ready)
        translation_ready = False
        if ocr_ready:
            if self.translation_engine_key == "google_cloud_v3":
                if self._is_google_credentials_valid:
                    translation_ready = True
                    tooltip = f"{ocr_provider_name} & Google Cloud Translate ({config.HOTKEY})"
                else:
                    tooltip = f"Set Google Credentials for '{trans_engine_name}' in Settings (⚙️)"
            elif self.translation_engine_key == "deepl_free":
                if self._is_deepl_key_set:
                    translation_ready = True
                    tooltip = f"{ocr_provider_name} & DeepL Translate ({config.HOTKEY})"
                else:
                    tooltip = f"Set DeepL API Key for '{trans_engine_name}' in Settings (⚙️)"
            elif self.translation_engine_key == "googletrans":
                translation_ready = True # googletrans has no specific key prerequisite here
                tooltip = f"{ocr_provider_name} & Google Translate (Unofficial) ({config.HOTKEY})"
            else:
                translation_ready = False # Unknown engine
                tooltip = f"OCR with {ocr_provider_name}, Unknown translation engine '{trans_engine_name}' selected."

            can_run_ocr = ocr_ready and translation_ready

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

        # Check Translation Provider (only needs checking if different from OCR reqs)
        if self.translation_engine_key == "google_cloud_v3":
            # Check Google creds again only if NOT already checked for Google Vision OCR
            if not self.ocr_provider == "google_vision":
                if self._is_google_credentials_valid: trans_prereqs_met = True
                else: missing.append(f"Google Credentials (for {trans_engine_name})")
            else:
                trans_prereqs_met = self._is_google_credentials_valid # Reuse check result
        elif self.translation_engine_key == "deepl_free":
            if self._is_deepl_key_set: trans_prereqs_met = True
            else: missing.append(f"DeepL API Key (for {trans_engine_name})")
        elif self.translation_engine_key == "googletrans":
            trans_prereqs_met = True # No specific prerequisite to check here
        else:
             missing.append(f"Configuration for unknown Translation Engine '{self.translation_engine_key}'")

        # Combine checks - remove duplicates from missing list
        missing = list(dict.fromkeys(missing)) # Simple way to unique-ify while preserving order
        all_prereqs_met = ocr_prereqs_met and trans_prereqs_met

        if not all_prereqs_met and prompt_if_needed:
            logging.info(f"OCR/Translate prereqs missing for '{ocr_provider_name}'/'{trans_engine_name}'. Prompting.")
            msg = f"Required configuration missing:\n\n- {chr(10).join(missing)}\n\nConfigure in Settings (⚙️)."
            QMessageBox.warning(self, "Config Needed", msg)
            self.open_settings_dialog() # Open settings to allow user to fix
            # Re-check after dialog (user might have fixed it)
            return self.check_ocr_prerequisites(prompt_if_needed=False) # Re-run check without prompt

        self._update_ocr_button_states() # Update button based on check result
        return all_prereqs_met


    def grab_text(self):
        if not self.check_ocr_prerequisites(prompt_if_needed=True):
            logging.warning("OCR cancelled: Prerequisite check failed.")
            return
        if self.ocr_running:
            logging.warning("OCR already running.")
            return

        # *** Hide only the text display, like the old code ***
        self.text_display.hide()
        QApplication.processEvents() # Try to force repaint before capture

        self.ocr_running = True
        logging.debug("Starting OCR worker...")
        self.grab_button.setText("Working...")
        self.grab_button.setEnabled(False)

        try:
            # *** Use coordinate calculation from old gui.py ***
            geo = self.geometry() # Window's overall geometry
            content_rect = self.text_display.geometry() # Text display's geometry *relative to window*

            if not geo.isValid() or not content_rect.isValid():
                raise ValueError("Invalid window or text_display geometry.")

            monitor = {
                "top": geo.top() + content_rect.top(),       # Window top + text_display top
                "left": geo.left() + content_rect.left(),     # Window left + text_display left
                "width": content_rect.width(),                # text_display width
                "height": content_rect.height()               # text_display height
            }

            # Ensure width/height are valid
            if monitor["width"] <= 0 or monitor["height"] <= 0:
                 raise ValueError(f"Invalid calculated capture dimensions: w={monitor['width']},h={monitor['height']}")

            logging.debug(f"Calculated monitor region (based on text_display): {monitor}")

        except Exception as e:
            logging.exception("Error calculating capture region geometry:")
            self.on_ocr_error(f"Capture Region Error: {e}")
            self.text_display.show() # Ensure text display is shown again on error
            self.on_thread_finished() # Reset state even on geometry error
            return

        history_snapshot = self.history_manager.get_history_list() if self.history_manager else []

        # Pass all relevant settings to the worker
        self.thread = QThread(self)
        self.worker = OCRWorker(
            monitor=monitor, # Pass text_display based monitor dictionary
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

        # <<< REMOVED signal connections >>>

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_ocr_done)
        self.worker.error.connect(self.on_ocr_error)
        # Ensure thread quits and objects are deleted on finish/error
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.on_thread_finished) # Reset state *after* thread finishes

        self.thread.start()
        logging.debug("OCR worker thread started.")

    def on_ocr_done(self, ocr_text, translated_text):
        # *** Show text display again ***
        self.text_display.show()

        logging.info("OCR results received.")
        if self.history_manager: self.history_manager.add_item(ocr_text, translated_text)
        safe_ocr=html.escape(ocr_text or ""); safe_trans=html.escape(translated_text or "")
        lang=html.escape(self.target_language_code.upper()); ocr_fmt=safe_ocr.replace('\n','<br>'); trans_fmt=safe_trans.replace('\n','<br>')
        font_style=f"font-family:'{self.display_font.family()}'; font-size:{self.display_font.pointSize()}pt;" # Use font style consistently
        err_style="color:#A00;"; ok_style="color:#005;"; is_err=translated_text and translated_text.startswith("[") and "Error:" in translated_text
        ocr_provider_name = config.AVAILABLE_OCR_PROVIDERS.get(self.ocr_provider, self.ocr_provider)
        trans_engine_name = config.AVAILABLE_ENGINES.get(self.translation_engine_key, self.translation_engine_key)

        # Apply font style to both OCR and Translation sections
        html_out=f"""<div style="margin-bottom:10px;"><b style="color:#333;">--- OCR ({ocr_provider_name}) ---</b><br/><div style="color:#000; margin-left:5px; {font_style}">{ocr_fmt if ocr_fmt else '<i style="color:#777;">No text detected.</i>'}</div></div>""" \
                   f"""<div><b style="color:#333;">--- Translation ({trans_engine_name} / {lang}) ---</b><br/><div style="margin-left:5px; {font_style} {err_style if is_err else ok_style}">{trans_fmt if trans_fmt else ('<i style="color:#777;">N/A (No OCR text)</i>' if not ocr_fmt else '<i style="color:#777;">No translation.</i>')}</div></div>"""
        self.text_display.setAlignment(Qt.AlignLeft); self.text_display.setHtml(html_out)

    def on_ocr_error(self, error_msg):
        # *** Show text display again ***
        self.text_display.show()

        logging.error(f"Worker error signal received: {error_msg}")
        font_style=f"font-family:'{self.display_font.family()}'; font-size:{self.display_font.pointSize()}pt;"
        err_html=f"""<p style="color:#A00;font-weight:bold;">--- Error ---</p><p style="color:#A00; {font_style}">{html.escape(error_msg)}</p>"""
        self.text_display.setAlignment(Qt.AlignLeft); self.text_display.setHtml(err_html)
        # Note: on_thread_finished is connected to thread.finished signal,
        # so UI state reset will happen there automatically after error signal.

    def on_thread_finished(self):
        logging.debug("Worker thread finished signal received.")

        # <<< REMOVED signal disconnection logic >>>

        # Ensure text display is visible, in case error occurred before on_ocr_error showed it
        if hasattr(self, 'text_display') and not self.text_display.isVisible():
             logging.warning("Thread finished but text display was hidden. Showing.")
             self.text_display.show()

        self.ocr_running = False
        self._update_ocr_button_states() # Update button state and tooltip
        # Reset button text only if not in live mode
        if not self.is_live_mode and self.grab_button.isEnabled():
            self.grab_button.setText("Grab Text")
        elif self.is_live_mode: # If was live, keep "Live..." but maybe re-enable if possible now
             if self.grab_button.isEnabled(): # Check if it BECAME enabled after thread finished
                  self.grab_button.setText("Live...") # Keep live text
             # If still disabled, _update_ocr_button_states will handle tooltip

        self.thread = None
        self.worker = None


    # (open_settings_dialog, window interaction, lifecycle, live mode methods need update or are same)
    # --------------------------------------------------------------------------
    # Settings Dialog Interaction
    # --------------------------------------------------------------------------
    def open_settings_dialog(self):
        if 'SettingsDialog' not in globals() or not SettingsDialog: QMessageBox.critical(self, "Error", "SettingsDialog not loaded."); return
        logging.debug("Opening settings dialog...")

        # --- Prepare current data for dialog ---
        # Use the RGB from self.bg_color (which has fixed alpha) and combine with self.textarea_alpha
        current_base_rgb = self.bg_color.getRgb()
        current_color_for_dialog = QColor(current_base_rgb[0], current_base_rgb[1], current_base_rgb[2], self.textarea_alpha)

        current_data = {
            'ocr_provider': self.ocr_provider,
            'google_credentials_path': self.google_credentials_path,
            'ocrspace_api_key': self.ocrspace_api_key,
            'ocr_language_code': self.ocr_language_code, # <<< PASS OCR LANG
            'deepl_api_key': self.deepl_api_key,
            'target_language_code': self.target_language_code, # Target for translation
            'translation_engine': self.translation_engine_key,
            'display_font': self.display_font,
            'bg_color': current_color_for_dialog, # Pass color with text area alpha
            'ocr_interval': self.ocr_interval,
            'is_locked': self.is_locked,
        }
        dialog = SettingsDialog(self, current_data)

        if dialog.exec_() == QDialog.Accepted:
            logging.debug("Settings dialog accepted. Applying...")
            updated = dialog.get_updated_settings()

            # Update attributes from dialog result
            self.ocr_provider = updated.get('ocr_provider', self.ocr_provider)
            self.google_credentials_path=updated.get('google_credentials_path')
            self.ocrspace_api_key=updated.get('ocrspace_api_key')
            self.ocr_language_code = updated.get('ocr_language_code', self.ocr_language_code) # <<< GET OCR LANG
            self.deepl_api_key=updated.get('deepl_api_key')
            self.target_language_code=updated.get('target_language_code', self.target_language_code)
            self.translation_engine_key=updated.get('translation_engine', self.translation_engine_key)
            self.display_font=updated.get('display_font', self.display_font)
            self.ocr_interval=updated.get('ocr_interval', self.ocr_interval)
            self.is_locked=updated.get('is_locked', self.is_locked)

            # --- Handle background color alpha update ---
            # The dialog returns 'bg_alpha' which is the desired alpha for the text area
            new_alpha = updated.get('bg_alpha') # Get alpha value (0-255) from dialog settings
            if isinstance(new_alpha, int):
                self.textarea_alpha = new_alpha # Update the textarea alpha attribute
            else:
                 logging.warning("Invalid alpha value received from settings dialog.")
                 # Keep existing self.textarea_alpha

            # The main window background color (self.bg_color) keeps its fixed alpha
            # No need to update self.bg_color's alpha here

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
        # --- Layout Adjustments ---
        btn_sz, btn_m, txt_m = 28, 5, 8 # Button size, button margin, text margin
        top_h = btn_sz + (btn_m * 2) # Height of the top control area
        grab_w = 70 # Width of the grab button

        # Position buttons (right to left)
        self.close_button.setGeometry(self.width() - btn_sz - btn_m, btn_m, btn_sz, btn_sz)
        self.options_button.setGeometry(self.close_button.x() - btn_sz - btn_m, btn_m, btn_sz, btn_sz)
        # Position grab button (left)
        self.grab_button.setGeometry(btn_m, btn_m, grab_w, btn_sz)

        # Position text display area below buttons
        txt_w = max(0, self.width() - (txt_m * 2))
        txt_h = max(0, self.height() - top_h - txt_m)
        self.text_display.setGeometry(txt_m, top_h, txt_w, txt_h)

        # --- Call Superclass ---
        if event:
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
        text_area_rect = self.text_display.geometry() # Get the text area's geometry relative to the window
        border_radius = 7 # Keep the rounded corners consistent

        # --- Create Drawing Paths ---
        full_window_path = QPainterPath()
        # Convert QRect to QRectF and ensure radii are floats
        full_window_path.addRoundedRect(QRectF(window_rect), border_radius, border_radius) # <<< CORRECTED LINE
        
        # Path for the text area rectangle - QRectF might be safer here too
        text_area_path = QPainterPath()
        text_area_path.addRect(QRectF(text_area_rect)) # Convert this too for consistency

        # --- Calculate Background Path (Window MINUS Text Area) ---
        # Subtract the text area path from the full window path
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
        if self.is_locked: return
        if event.button()==Qt.LeftButton:
            self.drag_pos = None; self.resizing = False; pos = event.pos(); self.detect_resize_edges(pos)
            if any(self.resizing_edges.values()):
                self.resizing=True; self.resize_start_pos=event.globalPos(); self.original_geometry=self.geometry()
            else:
                title_h = 35 # Approximate title bar height for dragging
                drag_rect = QRect(0, 0, self.width(), title_h)
                # Corrected Indentation Starts Here
                on_widget = any(w.geometry().contains(pos) for w in [self.close_button, self.options_button, self.grab_button, self.text_display])
                if drag_rect.contains(pos) and not on_widget:
                    self.drag_pos=event.globalPos()-self.frameGeometry().topLeft()
                    self.setCursor(Qt.SizeAllCursor)
                else:
                    self.unsetCursor()
                # Corrected Indentation Ends Here


    def mouseMoveEvent(self, event):
        if self.is_locked: return
        dragging = self.drag_pos and event.buttons()==Qt.LeftButton; resizing = self.resizing and event.buttons()==Qt.LeftButton
        if not (dragging or resizing): self.set_resize_cursor(event.pos()) # Update cursor if idle
        if dragging: self.move(event.globalPos()-self.drag_pos)
        elif resizing: self.handle_resize(event.globalPos())

    def mouseReleaseEvent(self, event):
        if event.button()==Qt.LeftButton: self.drag_pos=None; self.resizing=False; self.resizing_edges={k:False for k in self.resizing_edges}; self.unsetCursor()

    def detect_resize_edges(self, pos):
        if self.is_locked: self.resizing_edges={k:False for k in self.resizing_edges}; return
        x,y,w,h,m = pos.x(),pos.y(),self.width(),self.height(),config.RESIZE_MARGIN
        self.resizing_edges['left']=(0<=x<m); self.resizing_edges['top']=(0<=y<m)
        self.resizing_edges['right']=(w-m<x<=w+m); self.resizing_edges['bottom']=(h-m<y<=h+m)

    def set_resize_cursor(self, pos):
        if self.is_locked or self.resizing or (self.drag_pos and QApplication.mouseButtons()==Qt.LeftButton): return
        self.detect_resize_edges(pos); edges=self.resizing_edges # Use full keys
        if (edges['left'] and edges['top']) or (edges['right'] and edges['bottom']): self.setCursor(Qt.SizeFDiagCursor)
        elif (edges['right'] and edges['top']) or (edges['left'] and edges['bottom']): self.setCursor(Qt.SizeBDiagCursor)
        elif edges['left'] or edges['right']: self.setCursor(Qt.SizeHorCursor)
        elif edges['top'] or edges['bottom']: self.setCursor(Qt.SizeVerCursor)
        else: self.unsetCursor()

    def handle_resize(self, global_pos):
        if not self.resizing: return
        delta=global_pos-self.resize_start_pos; rect=QRect(self.original_geometry); min_w,min_h=config.MIN_WINDOW_WIDTH,config.MIN_WINDOW_HEIGHT; geo=QRect(rect)
        if self.resizing_edges['right']: geo.setWidth(max(min_w, rect.width()+delta.x())) # Use max for min size
        if self.resizing_edges['bottom']: geo.setHeight(max(min_h, rect.height()+delta.y()))
        if self.resizing_edges['left']:
            new_l=rect.left()+delta.x(); new_w=rect.right()-new_l+1
            # Prevent shrinking below min width AND moving right edge left
            if new_w < min_w: new_l = rect.right() - min_w + 1
            geo.setLeft(new_l)
        if self.resizing_edges['top']:
            new_t=rect.top()+delta.y(); new_h=rect.bottom()-new_t+1
            if new_h < min_h: new_t = rect.bottom() - min_h + 1
            geo.setTop(new_t)
        # Final check to ensure min size (redundant with max checks above but safe)
        if geo.width()<min_w: geo.setWidth(min_w)
        if geo.height()<min_h: geo.setHeight(min_h)
        self.setGeometry(geo)


    # --------------------------------------------------------------------------
    # Application Lifecycle
    # --------------------------------------------------------------------------
    def closeEvent(self, event):
        logging.info("Close event received. Cleaning up..."); self.live_mode_timer.stop()
        if 'unregister_hotkeys' in globals() and callable(unregister_hotkeys):
             try: unregister_hotkeys()
             except: logging.exception("Hotkey unregister failed:")
        # Ensure thread finishes cleanly
        if self.thread and self.thread.isRunning():
            logging.warning("Worker active on close. Requesting quit...")
            # <<< REMOVED signal disconnection logic >>>
            self.thread.quit()
            if not self.thread.wait(1000): # Wait up to 1 second
                 logging.error("Worker thread did not finish cleanly on close. Forcing termination possibility.")
                 # self.thread.terminate() # Use terminate only as a last resort

        self.save_history(); self.save_settings(); logging.info("Cleanup finished."); event.accept(); QApplication.instance().quit()

    def toggle_live_mode(self):
        # Check prerequisites before starting
        if not self.is_live_mode:
             if not self.check_ocr_prerequisites(prompt_if_needed=False): # Don't prompt here, just check
                 ocr_provider_name = config.AVAILABLE_OCR_PROVIDERS.get(self.ocr_provider, self.ocr_provider)
                 trans_engine_name = config.AVAILABLE_ENGINES.get(self.translation_engine_key, self.translation_engine_key)
                 QMessageBox.warning(self, "Config Needed", f"Check prerequisites for '{ocr_provider_name}' and '{trans_engine_name}' in Settings (⚙️) to start Live Mode.")
                 return

        # Toggle state
        if self.is_live_mode:
             self.is_live_mode = False; self.live_mode_timer.stop(); logging.info("Live Mode stopped.")
             self._update_ocr_button_states(); # Update button state/tooltip
             # Reset text only if button is now enabled
             if self.grab_button.isEnabled(): self.grab_button.setText("Grab Text")
        else:
             self.is_live_mode = True; self.grab_button.setEnabled(False); self.grab_button.setText("Live...")
             # Ensure interval is valid before starting timer
             interval_ms = max(1000, self.ocr_interval * 1000) # Use at least 1 second
             self.live_mode_timer.start(interval_ms)
             logging.info(f"Live Mode started (Interval: {interval_ms / 1000.0}s).")
             self.grab_text() # Perform initial grab immediately