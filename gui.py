# gui.py
import logging
import sys
import os
import collections # For history deque
import html # For escaping text in HTML output
import json # For history persistence
import csv # For history export

# PyQt5 Imports
from PyQt5.QtWidgets import (QWidget, QApplication, QPushButton, QTextEdit, QMenu, QAction, QColorDialog, QInputDialog, QStyle, QFileDialog, QMessageBox, QFontDialog)
from PyQt5.QtCore import Qt, QPoint, QRect, QTimer, QThread, QSettings, pyqtSignal, QByteArray, QStandardPaths
from PyQt5.QtGui import QColor, QPainter, QBrush, QFont


# Import other modules from the application
import config
try:
    from ocr_worker import OCRWorker
except ImportError:
    logging.error("Failed to import OCRWorker. Make sure ocr_worker.py is present.")
    # Define a dummy class to prevent further NameErrors if worker is missing
    # --- CORRECTED INDENTATION STARTS HERE ---
    class OCRWorker(QObject):
        # Define signals as class attributes
        error = pyqtSignal(str)
        finished = pyqtSignal(str, str)

        # Dummy __init__ to match expected signature (accepts any arguments)
        def __init__(self, *args, **kwargs):
            super().__init__()
            logging.debug("Using dummy OCRWorker because import failed.")

        # Dummy run method that emits an error
        def run(self):
            logging.debug("Dummy OCRWorker run called.")
            self.error.emit("OCR Worker module (ocr_worker.py) could not be imported.")
    # --- CORRECTED INDENTATION ENDS HERE ---
try:
    from hotkey_manager import setup_hotkey, unregister_hotkeys
except ImportError:
    logging.warning("hotkey_manager not found. Hotkey functionality disabled.")
    def setup_hotkey(callback): pass
    def unregister_hotkeys(): pass


class TranslucentBox(QWidget):
    def __init__(self):
        super().__init__()

        # --- Determine History File Path ---
        # Try AppDataLocation first
        data_path = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        if not data_path: # If AppDataLocation is not available
             logging.warning("AppDataLocation not found, using application directory for history.")
             # Fallback to directory of the executable or script
             if getattr(sys, 'frozen', False): # Check if running as packaged app (PyInstaller)
                 data_path = os.path.dirname(sys.executable)
             else: # Running as script
                  data_path = os.path.dirname(__file__)
        else:
             # Ensure the directory exists if AppDataLocation was found
             if not os.path.exists(data_path):
                 try:
                     os.makedirs(data_path, exist_ok=True) # Use exist_ok=True
                 except OSError as e:
                      logging.error(f"Could not create AppData directory: {data_path}, Error: {e}")
                      # Fallback
                      if getattr(sys, 'frozen', False): data_path = os.path.dirname(sys.executable)
                      else: data_path = os.path.dirname(__file__)
                      logging.warning(f"Using script/executable directory as fallback for history: {data_path}")

        self.history_file_path = os.path.join(data_path, config.HISTORY_FILENAME)
        logging.info(f"History file path set to: {self.history_file_path}")
        # --- End History File Path ---


        self.settings = QSettings(config.SETTINGS_ORG, config.SETTINGS_APP)
        self.load_settings() # Load other settings

        # --- Load History ---
        history_size = max(config.MAX_HISTORY_ITEMS, 0)
        self.ocr_history = collections.deque(maxlen=history_size)
        self.load_history() # Populate deque from file
        # --- End Load History ---

        # State variables
        self._is_credentials_valid = False # Updated by ensure_credentials_path
        self.is_live_mode = False; self.drag_pos = None; self.resizing = False
        self.resizing_edges = {'left': False, 'top': False, 'right': False, 'bottom': False}
        self.is_locked = False; self.ocr_running = False; self.thread = None; self.worker = None

        # Timers
        self.live_mode_timer = QTimer(self)
        self.live_mode_timer.timeout.connect(self.grab_text)

        self._setup_window_properties()
        self.initUI()
        self.ensure_credentials_path(prompt_if_needed=True) # Check/prompt for credentials
        self.restore_geometry() # Restore size/pos

        setup_hotkey(self.grab_text) # Setup hotkey

        self.show()
        logging.info("Application window initialized and shown.")


    def load_settings(self):
        """Load saved settings."""
        logging.debug("Loading settings...")
        self.credentials_path = self.settings.value(config.SETTINGS_CREDENTIALS_PATH_KEY, None)
        self.target_language_code = self.settings.value(config.SETTINGS_TARGET_LANG_KEY, config.DEFAULT_TARGET_LANGUAGE_CODE)
        font_str = self.settings.value(config.SETTINGS_FONT_KEY, None)
        self.display_font = QFont() # Start with default
        if font_str:
            if not self.display_font.fromString(font_str):
                 logging.warning(f"Failed loading font: {font_str}. Using default.")
                 self.display_font = QFont() # Reset to default on error
        self.ocr_interval = self.settings.value("ocrInterval", config.DEFAULT_OCR_INTERVAL_SECONDS, type=int)
        bg_color_str = self.settings.value("backgroundColor", config.DEFAULT_BG_COLOR.name(QColor.HexArgb))
        loaded_bg_color = QColor(bg_color_str)
        self.bg_color = loaded_bg_color if loaded_bg_color.isValid() else config.DEFAULT_BG_COLOR
        self.saved_geometry = self.settings.value(config.SETTINGS_GEOMETRY_KEY, None)


    def save_settings(self):
        """Save current settings."""
        logging.debug("Saving settings...")
        self.settings.setValue(config.SETTINGS_GEOMETRY_KEY, self.saveGeometry())
        self.settings.setValue(config.SETTINGS_TARGET_LANG_KEY, self.target_language_code)
        self.settings.setValue(config.SETTINGS_FONT_KEY, self.display_font.toString())
        self.settings.setValue("ocrInterval", self.ocr_interval)
        self.settings.setValue("backgroundColor", self.bg_color.name(QColor.HexArgb))
        # Credentials path saved when selected via prompt_for_credentials
        self.settings.sync() # Force sync to ensure saving before exit
        logging.debug("Settings synced.")


    def load_history(self):
        """Loads OCR history from the JSON file."""
        if not self.ocr_history.maxlen or not self.history_file_path:
             logging.debug("History loading skipped (maxlen=0 or no path).")
             return
        try:
            if os.path.exists(self.history_file_path):
                with open(self.history_file_path, 'r', encoding='utf-8') as f:
                    history_list = json.load(f)
                    # Validate and populate deque
                    count = 0
                    temp_list = [] # Load into temp list first
                    for item in history_list:
                        if isinstance(item, (list, tuple)) and len(item) == 2 and all(isinstance(s, str) for s in item):
                             temp_list.append(tuple(item))
                        else:
                             logging.warning(f"Skipping invalid history item: {item}")

                    # Populate deque from the end of the valid list, respecting maxlen
                    self.ocr_history.extend(temp_list[-self.ocr_history.maxlen:])
                    count = len(self.ocr_history)
                    logging.info(f"Loaded {count} items from history file.")
            else:
                logging.info("History file not found, starting empty.")
        except json.JSONDecodeError:
            logging.exception(f"Error decoding history file: {self.history_file_path}")
            self.ocr_history.clear()
        except Exception as e:
            logging.exception(f"Error loading history file: {e}")
            self.ocr_history.clear()


    def save_history(self):
        """Saves the current OCR history to the JSON file."""
        if not self.ocr_history.maxlen or not self.history_file_path:
            logging.debug("History saving skipped (maxlen=0 or no path).")
            return

        history_list = list(self.ocr_history) # Convert deque to list

        if not history_list: # History is empty
             if os.path.exists(self.history_file_path):
                  try: os.remove(self.history_file_path); logging.debug("Removed empty history file.")
                  except OSError as e: logging.error(f"Could not remove empty history file: {e}")
             return

        try:
            # Ensure directory exists before writing
            history_dir = os.path.dirname(self.history_file_path)
            if not os.path.exists(history_dir):
                os.makedirs(history_dir, exist_ok=True)

            with open(self.history_file_path, 'w', encoding='utf-8') as f:
                json.dump(history_list, f, ensure_ascii=False, indent=2)
            logging.info(f"Saved {len(history_list)} items to history file.")
        except Exception as e:
            logging.exception(f"Error saving history file: {e}")


    def restore_geometry(self):
        """Restore window geometry."""
        # Ensure saved_geometry is loaded before calling this
        if hasattr(self, 'saved_geometry') and self.saved_geometry and isinstance(self.saved_geometry, QByteArray):
            if self.restoreGeometry(self.saved_geometry):
                 logging.debug("Window geometry restored.")
            else:
                 logging.warning("Failed to restore geometry."); self.setGeometry(100, 100, 350, 250)
        else:
            logging.debug("No saved geometry found."); self.setGeometry(100, 100, 350, 250)


    def _setup_window_properties(self):
        """Sets window flags and attributes."""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(config.MIN_WINDOW_WIDTH, config.MIN_WINDOW_HEIGHT)


    def initUI(self):
        """Initializes the UI elements."""
        logging.debug("Initializing UI elements.")

        # Close Button
        self.close_button = QPushButton(self); self.close_button.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton)); self.close_button.clicked.connect(self.close); self.close_button.setToolTip("Close"); self.close_button.setStyleSheet("QPushButton{background-color:rgba(255,255,255,100);border:none;border-radius:5px;}QPushButton:hover{background-color:rgba(255,50,50,150);}")
        # Options Button
        self.options_button = QPushButton('⚙️', self); self.options_button.clicked.connect(self.show_options_menu); self.options_button.setToolTip("Options"); self.options_button.setStyleSheet("QPushButton{background-color:rgba(255,255,255,100);border:none;font-size:16px;border-radius:5px;}QPushButton:hover{background-color:rgba(50,150,255,150);}")
        # Grab Button
        self.grab_button = QPushButton('Grab Text', self); self.grab_button.clicked.connect(self.grab_text); self.grab_button.setToolTip(f"Perform OCR/Translate ({config.HOTKEY})"); self.grab_button.setStyleSheet("QPushButton{background-color:rgba(255,255,255,100);border:none;font-size:12px;border-radius:5px;}QPushButton:hover{background-color:rgba(50,150,255,150);}QPushButton:disabled{background-color:rgba(200,200,200,80);color:#888;}")
        # Text Display
        self.text_display = QTextEdit(self); self.text_display.setReadOnly(True); self.text_display.setFont(self.display_font); self._update_text_display_style()

        self.resizeEvent(None) # Position elements


    def _update_text_display_style(self):
        """Applies background/border styles and ensures font is set."""
        self.text_display.setFont(self.display_font)
        style = (f"background-color: rgba(255, 255, 255, 180); border-radius: 5px;"); self.text_display.setStyleSheet(style)
        logging.debug(f"Text display style updated: Font={self.display_font.toString()}")


    def _update_ocr_button_states(self):
        """Enable/disable OCR buttons based on credentials validity."""
        enabled = self._is_credentials_valid
        self.grab_button.setEnabled(enabled)
        tooltip = f"Perform OCR/Translate ({config.HOTKEY})" if enabled else "Set Google Credentials file first (Options > Set Credentials File...)"
        self.grab_button.setToolTip(tooltip)


    def ensure_credentials_path(self, prompt_if_needed=False):
        """Checks credentials path validity, optionally prompts user."""
        # Check if path is set and exists
        if self.credentials_path and os.path.exists(self.credentials_path):
            if not self._is_credentials_valid: logging.info(f"Creds valid: {self.credentials_path}"); self._is_credentials_valid = True
        else: # Path not set or invalid
            if self.credentials_path: logging.warning(f"Stored creds path invalid: {self.credentials_path}"); self.credentials_path = None; self.settings.remove(config.SETTINGS_CREDENTIALS_PATH_KEY)
            if self._is_credentials_valid: logging.warning("Creds path became invalid."); self._is_credentials_valid = False
            # Prompt only if needed and still not valid
            if prompt_if_needed:
                logging.info("Creds path not set/invalid, prompting."); self.prompt_for_credentials() # Updates validity inside

        # Update UI state based on final validity
        self._update_ocr_button_states()
        return self._is_credentials_valid


    def prompt_for_credentials(self):
        """Opens file dialog for credentials, updates state and settings."""
        filePath, _ = QFileDialog.getOpenFileName(self, "Select Google Cloud Credentials File", "", "JSON files (*.json)")
        success = False
        if filePath:
            if os.path.exists(filePath):
                self.credentials_path = filePath; self.settings.setValue(config.SETTINGS_CREDENTIALS_PATH_KEY, self.credentials_path); logging.info(f"Creds path set: {self.credentials_path}"); self._is_credentials_valid = True; success = True
            else:
                logging.error(f"Selected file path does not exist: {filePath}"); QMessageBox.warning(self, "File Error", f"File not found:\n{filePath}"); self.credentials_path = None; self._is_credentials_valid = False
        else:
            logging.warning("User cancelled credentials selection.");
            if not self._is_credentials_valid: QMessageBox.warning(self, "Credentials Required", "Credentials file needed.");
            success = self._is_credentials_valid # Return current state if cancelled

        self._update_ocr_button_states(); return success


    def grab_text(self):
        """Initiates OCR, passing history snapshot for cache lookup."""
        if not self.ensure_credentials_path(prompt_if_needed=True): logging.warning("OCR cancelled: Credentials needed."); return
        if self.ocr_running: logging.warning("OCR already running."); return
        if not self._is_credentials_valid: logging.error("Cannot start OCR: Credentials invalid."); return

        self.ocr_running = True; logging.debug("Starting OCR process...")
        self.text_display.hide(); QApplication.processEvents() # Hide before capture
        self.grab_button.setText("Working..."); self.grab_button.setEnabled(False)

        # Calculate capture region
        try:
            geo = self.geometry(); content_rect = self.text_display.geometry()
            if not geo.isValid() or not content_rect.isValid(): raise ValueError("Invalid geometry.")
            monitor = {"top":geo.top()+content_rect.top(),"left":geo.left()+content_rect.left(),"width":content_rect.width(),"height":content_rect.height()}
            if monitor["width"]<=0 or monitor["height"]<=0: raise ValueError(f"Invalid capture dims: w={monitor['width']},h={monitor['height']}")
            logging.debug(f"Calculated monitor region: {monitor}")
        except Exception as e:
            logging.exception("Error calculating monitor region:"); self.on_ocr_error(f"Error preparing capture: {e}"); self.on_thread_finished(); return

        # Pass History snapshot to Worker
        history_snapshot = list(self.ocr_history)

        # Create and run worker
        self.thread = QThread(); self.worker = OCRWorker(monitor, self.credentials_path, self.target_language_code, history_snapshot); self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run); self.worker.finished.connect(self.on_ocr_done); self.worker.error.connect(self.on_ocr_error)
        self.worker.finished.connect(self.thread.quit); self.worker.error.connect(self.thread.quit); self.worker.finished.connect(self.worker.deleteLater); self.worker.error.connect(self.worker.deleteLater); self.thread.finished.connect(self.thread.deleteLater); self.thread.finished.connect(self.on_thread_finished)
        self.thread.start()


    # --- Event Handlers ---
    def resizeEvent(self, event):
        """Handles window resize to reposition UI elements."""
        button_size=30; button_margin=5; top_row_height=button_size+(button_margin*2)
        self.close_button.setGeometry(self.width()-button_size-button_margin,button_margin,button_size,button_size)
        self.options_button.setGeometry(self.close_button.x()-button_size-button_margin,button_margin,button_size,button_size)
        self.grab_button.setGeometry(button_margin,button_margin,80,button_size)
        text_margin=10; text_top=top_row_height
        self.text_display.setGeometry(text_margin,text_top,self.width()-(text_margin*2),self.height()-text_top-text_margin)
        if event: super().resizeEvent(event)

    def paintEvent(self, event):
        """Paints the translucent background."""
        painter=QPainter(self); painter.setRenderHint(QPainter.Antialiasing); brush=QBrush(self.bg_color); painter.setBrush(brush); painter.setPen(Qt.NoPen); painter.drawRoundedRect(self.rect(),7,7)

    def mousePressEvent(self, event):
        """Handles mouse press for dragging and resizing."""
        if self.is_locked: return
        if event.button() == Qt.LeftButton:
            pos=event.pos(); self.detect_resize_edges(pos)
            if any(self.resizing_edges.values()): self.resizing=True; self.drag_pos=None; self.resize_start_pos=event.globalPos(); self.original_geometry=self.geometry(); logging.debug("Resizing started."); return
            widgets_to_ignore=[self.close_button,self.options_button,self.grab_button,self.text_display]
            clicked_on_widget=any(widget.geometry().contains(pos) for widget in widgets_to_ignore)
            if not clicked_on_widget: self.resizing=False; self.drag_pos=event.globalPos()-self.frameGeometry().topLeft(); logging.debug("Dragging started.")
            else: self.drag_pos=None; logging.debug("Click on interactive widget.")


    def mouseMoveEvent(self, event):
        """Handles mouse move for dragging and resizing."""
        if self.is_locked: return
        if self.resizing: self.handle_resize(event.globalPos())
        elif self.drag_pos and event.buttons()==Qt.LeftButton: self.move(event.globalPos()-self.drag_pos)
        elif not self.resizing: self.set_resize_cursor(event.pos())

    def mouseReleaseEvent(self, event):
        """Handles mouse release to stop dragging/resizing."""
        if event.button()==Qt.LeftButton:
            if self.resizing: logging.debug("Resizing finished.")
            if self.drag_pos: logging.debug("Dragging finished.")
            self.drag_pos=None; self.resizing=False; self.resizing_edges={k:False for k in self.resizing_edges}; self.unsetCursor()


    def closeEvent(self, event):
        """Saves settings and history, cleans up resources on close."""
        logging.info("Close event triggered. Cleaning up...")
        self.save_history() # Save history first
        self.save_settings() # Then save other settings
        if self.live_mode_timer.isActive(): self.live_mode_timer.stop(); logging.debug("Live timer stopped.")
        try: unregister_hotkeys()
        except Exception as e: logging.exception("Error unregistering hotkeys:")
        if self.thread and self.thread.isRunning():
            logging.warning("Worker thread running. Quitting."); self.thread.quit()
            if not self.thread.wait(1000): logging.error("Worker thread didn't quit.")
        logging.info("Cleanup done. Quitting application."); event.accept(); QApplication.instance().quit()


    # --- Resizing Logic ---
    def detect_resize_edges(self, pos):
        """Detects if the mouse position is near an edge for resizing."""
        x,y,w,h=pos.x(),pos.y(),self.width(),self.height(); margin=config.RESIZE_MARGIN; self.resizing_edges={'left':x>=0 and x<margin,'top':y>=0 and y<margin,'right':x>w-margin and x<=w,'bottom':y>h-margin and y<=h}

    def set_resize_cursor(self, pos):
        """Sets the appropriate resize cursor based on mouse position."""
        if self.is_locked or self.drag_pos: self.unsetCursor(); return; self.detect_resize_edges(pos); edges=self.resizing_edges
        if(edges['left']and edges['top'])or(edges['right']and edges['bottom']): self.setCursor(Qt.SizeFDiagCursor)
        elif(edges['right']and edges['top'])or(edges['left']and edges['bottom']): self.setCursor(Qt.SizeBDiagCursor)
        elif edges['left']or edges['right']: self.setCursor(Qt.SizeHorCursor)
        elif edges['top']or edges['bottom']: self.setCursor(Qt.SizeVerCursor)
        else: self.unsetCursor()

    # In gui.py -> TranslucentBox class
    
    def handle_resize(self, global_pos):
        """Calculates and applies the new geometry during resizing."""
        # Guard clause: Do nothing if not actually resizing
        if not self.resizing:
            return
    
        # Calculate change in position
        delta = global_pos - self.resize_start_pos
    
        # --- FIX: Ensure 'rect' is initialized HERE ---
        # Create a QRect based on the geometry when resizing started
        rect = QRect(self.original_geometry)
        # --- End FIX ---
    
        # Get min dimensions from config
        min_w, min_h = config.MIN_WINDOW_WIDTH, config.MIN_WINDOW_HEIGHT
    
        # Adjust geometry based on which edge(s) are being dragged
        if self.resizing_edges['right']:
            rect.setWidth(self.original_geometry.width() + delta.x())
        if self.resizing_edges['bottom']:
            rect.setHeight(self.original_geometry.height() + delta.y())
        if self.resizing_edges['left']:
            new_left = self.original_geometry.left() + delta.x()
            # Prevent shrinking left edge past the right edge (respecting min width)
            new_width = self.original_geometry.right() - new_left
            if new_width >= min_w:
                rect.setLeft(new_left)
            else:
                # Pin left edge to maintain minimum width from the original right edge
                rect.setLeft(self.original_geometry.right() - min_w)
        if self.resizing_edges['top']:
            new_top = self.original_geometry.top() + delta.y()
            # Prevent shrinking top edge past the bottom edge (respecting min height)
            new_height = self.original_geometry.bottom() - new_top
            if new_height >= min_h:
                rect.setTop(new_top)
            else:
                # Pin top edge to maintain minimum height from the original bottom edge
                rect.setTop(self.original_geometry.bottom() - min_h)
    
        # Enforce minimum size strictly after adjustments
        if rect.width() < min_w:
            rect.setWidth(min_w)
        if rect.height() < min_h:
            rect.setHeight(min_h)
    
        # Apply the calculated geometry
        self.setGeometry(rect)


    # --- OCR and Translation Worker Slots ---
    def on_ocr_done(self, ocr_text, translated_text):
        """Handles successful OCR/translation, updates history and display."""
        logging.info("OCR/translation done.")
        # Add to History
        if hasattr(self, 'ocr_history') and self.ocr_history.maxlen > 0:
             if ocr_text or translated_text:
                  result_entry = (str(ocr_text or ""), str(translated_text or ""))
                  # Avoid duplicate consecutive entries
                  if not self.ocr_history or self.ocr_history[-1] != result_entry:
                       self.ocr_history.append(result_entry)
                       logging.debug(f"Result added to history. Size: {len(self.ocr_history)}")
                  else:
                       logging.debug("Skipped adding duplicate consecutive history entry.")

        # Format Output using HTML
        safe_ocr = html.escape(ocr_text if ocr_text else ""); safe_trans = html.escape(translated_text if translated_text else ""); target_lang_upper = html.escape(self.target_language_code.upper())
        html_output = f"""<p style="font-weight:bold;color:#333;">--- OCR ---</p><p style="color:#000;">{safe_ocr}</p><br/><p style="font-weight:bold;color:#333;">--- Translation ({target_lang_upper}) ---</p><p style="color:#005;">{safe_trans}</p>"""
        self.text_display.setAlignment(Qt.AlignLeft); self.text_display.setHtml(html_output)
        self.text_display.show() # Show display again (was hidden in grab_text)


    def on_ocr_error(self, error_msg):
        """Handles errors using QMessageBox and updates display."""
        logging.error(f"OCR/Translation error reported: {error_msg}")
        QMessageBox.warning(self, "OCR/Translation Error", f"An error occurred:\n\n{error_msg}")
        self.text_display.setAlignment(Qt.AlignLeft)
        self.text_display.setHtml('<p style="color: #A00;"><i>[Error occurred]</i></p>')
        self.text_display.show() # Ensure display is shown even after error


    def on_thread_finished(self):
        """Resets UI state after worker thread finishes."""
        self.ocr_running = False
        if hasattr(self, 'grab_button'):
            can_enable_grab = self._is_credentials_valid and not self.is_live_mode
            self.grab_button.setEnabled(can_enable_grab)
            self.grab_button.setText("Grab Text")
        self.thread = None; self.worker = None
        logging.debug("OCR worker thread finished.")


    # --- Options Menu and Actions ---
    def show_options_menu(self):
        """Displays the options context menu."""
        menu = QMenu(self)
        # Credentials and Language
        creds_action=QAction("Set Credentials File...",self); creds_action.triggered.connect(self.prompt_for_credentials); menu.addAction(creds_action)
        lang_action=QAction(f"Set Target Language ({self.target_language_code.upper()})...",self); lang_action.triggered.connect(self.select_target_language); menu.addAction(lang_action)
        menu.addSeparator()
        # Appearance
        font_action=QAction("Change Display Font...",self); font_action.triggered.connect(self.change_font); menu.addAction(font_action)
        alpha_action=QAction("Adjust Background Transparency...",self); alpha_action.triggered.connect(self.adjust_background_transparency); menu.addAction(alpha_action)
        menu.addSeparator()
        # History
        history_submenu=menu.addMenu("History"); show_last_action=history_submenu.addAction("Show Last Result"); show_last_action.triggered.connect(self.show_last_history_item); show_last_action.setEnabled(len(self.ocr_history)>0)
        export_action=history_submenu.addAction("Export History..."); export_action.triggered.connect(self.export_history); export_action.setEnabled(len(self.ocr_history)>0)
        clear_history_action=history_submenu.addAction("Clear History"); clear_history_action.triggered.connect(self.clear_history); clear_history_action.setEnabled(len(self.ocr_history)>0)
        menu.addSeparator()
        # Other Controls
        actions=[("Lock/Unlock Window",self.toggle_lock),("---",None),("Change OCR Interval",self.change_ocr_interval),("Toggle Live Mode",self.toggle_live_mode)]
        for text,callback in actions:
            if text=="---": menu.addSeparator()
            else:
                action=QAction(text,self); action.triggered.connect(callback); is_ocr_dep=text in ["Change OCR Interval","Toggle Live Mode"]
                if text=="Toggle Live Mode": action.setCheckable(True); action.setChecked(self.is_live_mode)
                if text=="Lock/Unlock Window": action.setCheckable(True); action.setChecked(self.is_locked)
                if is_ocr_dep and not self._is_credentials_valid: action.setEnabled(False); action.setToolTip("Set credentials file first")
                menu.addAction(action)
        button_pos=self.options_button.mapToGlobal(QPoint(0,self.options_button.height())); menu.exec_(button_pos)


    # --- New Action Methods ---
    def select_target_language(self):
        """Allows user to select the target translation language."""
        lang_display_names=[n for n,c in config.COMMON_LANGUAGES]; current_index=0
        try: current_index=[c for n,c in config.COMMON_LANGUAGES].index(self.target_language_code)
        except ValueError: logging.warning(f"Current target '{self.target_language_code}' not in common list.")
        lang_name,ok=QInputDialog.getItem(self,"Select Target Language","Translate to:",lang_display_names,current=current_index,editable=False)
        if ok and lang_name:
            new_code=next((c for n,c in config.COMMON_LANGUAGES if n==lang_name), None)
            if new_code and new_code!=self.target_language_code: self.target_language_code=new_code; self.settings.setValue(config.SETTINGS_TARGET_LANG_KEY,self.target_language_code); logging.info(f"Target lang set: {self.target_language_code}")
            elif not new_code: logging.error(f"Code not found for lang: {lang_name}")

    def adjust_background_transparency(self):
        """Allows user to set the background alpha channel (0-255)."""
        current_alpha=self.bg_color.alpha(); alpha,ok=QInputDialog.getInt(self,"Background Transparency","Alpha (0=Transparent, 255=Opaque):",current_alpha,0,255,5)
        if ok and alpha!=current_alpha: self.bg_color.setAlpha(alpha); self.settings.setValue("backgroundColor",self.bg_color.name(QColor.HexArgb)); self.update(); logging.info(f"BG alpha set: {alpha}")

    def change_font(self):
        """Opens QFontDialog to change display font."""
        font,ok=QFontDialog.getFont(self.display_font,self,"Select Display Font")
        if ok: self.display_font=font; self._update_text_display_style(); self.settings.setValue(config.SETTINGS_FONT_KEY,self.display_font.toString()); logging.info(f"Font set: {self.display_font.toString()}")

    def show_last_history_item(self):
        """Displays the most recent history item in the text area."""
        if self.ocr_history:
             last_ocr,last_trans=self.ocr_history[-1]; safe_ocr=html.escape(last_ocr or ""); safe_trans=html.escape(last_trans or ""); target_lang_upper=html.escape(self.target_language_code.upper())
             html_output=f"""<p style="color:#666;"><i>--- History (Last Result) ---</i></p><p style="font-weight:bold;color:#333;">--- OCR ---</p><p style="color:#000;">{safe_ocr}</p><br/><p style="font-weight:bold;color:#333;">--- Translation ({target_lang_upper}) ---</p><p style="color:#005;">{safe_trans}</p>"""
             self.text_display.setAlignment(Qt.AlignLeft); self.text_display.setHtml(html_output); logging.debug("Showed last history item.")
        else: logging.debug("No history."); QMessageBox.information(self,"History","No history available.")

    def clear_history(self):
        """Clears the OCR history deque and optionally the saved file."""
        if self.ocr_history:
            reply = QMessageBox.question(self, "Clear History", "Clear entire OCR/Translation history?\n(This action cannot be undone)", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                 self.ocr_history.clear(); self.text_display.clear(); logging.info("History deque cleared.")
                 try: # Attempt to delete file
                     if os.path.exists(self.history_file_path): os.remove(self.history_file_path); logging.info(f"History file deleted: {self.history_file_path}")
                 except OSError as e: logging.error(f"Could not delete history file: {e}"); QMessageBox.warning(self, "File Error", "History cleared from memory, but could not delete the history file.")
                 QMessageBox.information(self, "History", "History cleared.")
        else:
            logging.debug("No history to clear."); QMessageBox.information(self, "History", "History is already empty.")

    def export_history(self):
        """Exports the current history to a CSV file."""
        if not self.ocr_history: QMessageBox.information(self, "Export History", "History is empty."); return
        default_filename = os.path.join(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation), "ocr_translator_history.csv")
        filePath, _ = QFileDialog.getSaveFileName(self, "Export History As", default_filename, "CSV Files (*.csv)")
        if filePath:
            try:
                with open(filePath, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile); writer.writerow(["OCR Text", "Translated Text"]) # Header
                    for ocr_text, translated_text in self.ocr_history: writer.writerow([ocr_text, translated_text]) # Data
                logging.info(f"History exported to: {filePath}"); QMessageBox.information(self, "Export Successful", f"History exported to:\n{filePath}")
            except Exception as e: logging.exception(f"Error exporting history: {e}"); QMessageBox.critical(self, "Export Error", f"Could not export history:\n{e}")


    # --- Existing Action Methods ---
    def toggle_lock(self):
        """Toggles the window locked state."""
        self.is_locked=not self.is_locked; opacity=0.95 if self.is_locked else 1.0; self.setWindowOpacity(opacity); logging.info(f"Window {'locked' if self.is_locked else 'unlocked'}.");
        if self.is_locked: self.unsetCursor()

    def change_ocr_interval(self):
        """Opens dialog to change the live mode OCR interval."""
        interval,ok=QInputDialog.getInt(self,"Live OCR Interval","Enter interval (seconds):",self.ocr_interval,1,300,1)
        if ok and interval!=self.ocr_interval: self.ocr_interval=interval; self.settings.setValue("ocrInterval",self.ocr_interval); logging.info(f"OCR interval set: {self.ocr_interval}s.");
        if self.is_live_mode: self.live_mode_timer.start(self.ocr_interval*1000); logging.debug("Live timer restarted.")

    def toggle_live_mode(self):
        """Toggles the live OCR mode on/off."""
        if not self._is_credentials_valid: QMessageBox.warning(self,"Credentials Required","Set Credentials file first."); return
        if self.is_live_mode: self.is_live_mode=False; self.live_mode_timer.stop(); logging.info("Live Mode stopped."); self.grab_button.setEnabled(True) # Enable grab button if creds ok
        else: self.is_live_mode=True; self.live_mode_timer.start(self.ocr_interval*1000); logging.info(f"Live Mode started ({self.ocr_interval}s)."); self.grab_button.setEnabled(False); self.grab_text() # Initial grab