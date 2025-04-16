# src/gui/translucent_box.py
import logging
import sys
import os
import html

# PyQt5 Imports
from PyQt5.QtWidgets import (QWidget, QApplication, QPushButton, QTextEdit,
                             QMenu, QAction, QColorDialog, QInputDialog, QStyle,
                             QFileDialog, QMessageBox, QFontDialog, QDialog)
from PyQt5.QtCore import Qt, QPoint, QRect, QTimer, QThread, QSettings, pyqtSignal, QByteArray, QStandardPaths, QObject, QSize
from PyQt5.QtGui import QColor, QPainter, QBrush, QFont, QIcon, QCursor, QTextOption

# --- Import application modules using absolute paths from src ---
from src import config
from src.core.settings_manager import SettingsManager
from src.core.history_manager import HistoryManager
from src.core.ocr_worker import OCRWorker
from src.core.hotkey_manager import setup_hotkey, unregister_hotkeys
from src.gui.settings_dialog import SettingsDialog


class TranslucentBox(QWidget):
    """
    Main application window. Orchestrates UI, settings, history, and OCR.
    Delegates settings/history persistence to manager classes.
    """
    def __init__(self):
        super().__init__()

        # --- Initialize Managers ---
        self.settings_manager = SettingsManager() if SettingsManager else None
        if not self.settings_manager:
             try: QMessageBox.critical(None, "Init Error", "SettingsManager failed. App cannot continue.")
             except: print("CRITICAL: SettingsManager failed. App cannot continue.") # Fallback print
             sys.exit(1)

        initial_settings = self.settings_manager.load_all_settings()
        self._apply_loaded_settings(initial_settings)

        self.history_manager = HistoryManager(max_items=config.MAX_HISTORY_ITEMS) if HistoryManager else None
        if not self.history_manager:
             QMessageBox.warning(None, "Init Warning", "HistoryManager failed. History unavailable.")

        # --- Initialize State Variables ---
        self._update_prerequisite_state_flags()
        self.is_live_mode = False
        self.drag_pos = None
        self.resizing = False
        self.resizing_edges = {'left': False, 'top': False, 'right': False, 'bottom': False} # Full keys
        self.ocr_running = False
        self.thread = None
        self.worker = None

        # --- Timers ---
        self.live_mode_timer = QTimer(self); self.live_mode_timer.timeout.connect(self.grab_text)

        # --- UI Initialization ---
        self._setup_window_properties()
        self.initUI()
        self._update_ocr_button_states()
        self.restore_geometry(initial_settings.get('saved_geometry'))
        self.apply_initial_lock_state()

        # --- Hotkey Setup ---
        if 'setup_hotkey' in globals() and callable(setup_hotkey):
             setup_hotkey(self.grab_text)
        else: logging.error("Hotkey setup failed.")

        logging.info("Application window initialized.")


    def _apply_loaded_settings(self, settings_dict):
        """Applies settings from a dictionary to instance attributes."""
        self.credentials_path = settings_dict.get('credentials_path')
        self.deepl_api_key = settings_dict.get('deepl_api_key')
        self.target_language_code = settings_dict.get('target_language_code', config.DEFAULT_TARGET_LANGUAGE_CODE)
        self.translation_engine_key = settings_dict.get('translation_engine_key', config.DEFAULT_TRANSLATION_ENGINE)
        self.display_font = settings_dict.get('display_font', QFont())
        self.ocr_interval = settings_dict.get('ocr_interval', config.DEFAULT_OCR_INTERVAL_SECONDS)
        self.bg_color = settings_dict.get('bg_color', QColor(config.DEFAULT_BG_COLOR))
        self.is_locked = settings_dict.get('is_locked', False)
        if not isinstance(self.display_font, QFont): self.display_font = QFont()
        if not isinstance(self.bg_color, QColor): self.bg_color = QColor(config.DEFAULT_BG_COLOR)
        if not isinstance(self.ocr_interval, int) or self.ocr_interval <= 0: self.ocr_interval = config.DEFAULT_OCR_INTERVAL_SECONDS
        logging.debug("Applied loaded settings to TranslucentBox attributes.")

    def _update_prerequisite_state_flags(self):
        """Updates internal flags based on current credentials/keys."""
        self._is_google_credentials_valid = bool(self.credentials_path and os.path.exists(self.credentials_path))
        self._is_deepl_key_set = bool(self.deepl_api_key)

    # --------------------------------------------------------------------------
    # Settings and History Management (Delegated Methods)
    # --------------------------------------------------------------------------
    def load_settings(self):
        if self.settings_manager:
            settings_dict = self.settings_manager.load_all_settings()
            self._apply_loaded_settings(settings_dict); self._update_prerequisite_state_flags()
            self._update_text_display_style(); self._update_ocr_button_states()
            self.apply_initial_lock_state(); self.update()
        else: logging.error("SettingsManager not available.")

    def save_settings(self):
        if self.settings_manager:
            current_settings_data = {
                'credentials_path': self.credentials_path, 'deepl_api_key': self.deepl_api_key,
                'target_language_code': self.target_language_code, 'translation_engine_key': self.translation_engine_key,
                'display_font': self.display_font, 'ocr_interval': self.ocr_interval,
                'bg_color': self.bg_color, 'is_locked': self.is_locked,
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

    # --------------------------------------------------------------------------
    # Geometry and Window State
    # --------------------------------------------------------------------------
    def restore_geometry(self, saved_geometry_bytes):
        restored = False
        if saved_geometry_bytes and isinstance(saved_geometry_bytes, QByteArray):
            restored = self.restoreGeometry(saved_geometry_bytes)
        if restored: logging.debug("Window geometry restored.")
        else: logging.debug("Using default geometry."); self.setGeometry(100, 100, 350, 250)

    def apply_initial_lock_state(self):
         opacity = 0.95 if self.is_locked else 1.0; self.setWindowOpacity(opacity)
         logging.info(f"Window lock state applied: {'Locked' if self.is_locked else 'Unlocked'}.")

    # --------------------------------------------------------------------------
    # UI Initialization and Styling (Methods starting with _)
    # --------------------------------------------------------------------------
    def _setup_window_properties(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground); self.setMinimumSize(config.MIN_WINDOW_WIDTH, config.MIN_WINDOW_HEIGHT)
        self.setMouseTracking(True)

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
        self._update_text_display_style()

    def _update_text_display_style(self):
        if not isinstance(self.display_font, QFont): self.display_font = QFont()
        self.text_display.setFont(self.display_font)
        style = f"background-color: rgba(255, 255, 255, 220); color: #000; border-radius: 5px; padding: 5px;"
        self.text_display.setStyleSheet(style)

    # --------------------------------------------------------------------------
    # OCR / Worker Interaction (Methods starting with _)
    # --------------------------------------------------------------------------
    def _update_ocr_button_states(self):
        can_run_ocr = False; tooltip = f"Perform OCR/Translate ({config.HOTKEY})"
        self._update_prerequisite_state_flags()
        sel_engine = self.translation_engine_key; engine_name = config.AVAILABLE_ENGINES.get(sel_engine, sel_engine)
        if not self._is_google_credentials_valid: tooltip = "Set Google Credentials (for OCR) in Settings (⚙️)"
        else:
            if sel_engine == "google_cloud_v3": can_run_ocr = True; tooltip = f"OCR & Google Cloud Translate ({config.HOTKEY})"
            elif sel_engine == "deepl_free":
                if self._is_deepl_key_set: can_run_ocr = True; tooltip = f"OCR & DeepL Translate ({config.HOTKEY})"
                else: tooltip = f"Set DeepL API Key in Settings (⚙️)"
            elif sel_engine == "googletrans": can_run_ocr = True; tooltip = f"OCR & Google Translate (Unofficial) ({config.HOTKEY})"
            else: can_run_ocr = True; tooltip = f"OCR with unknown engine '{engine_name}' ({config.HOTKEY})"
        self.grab_button.setEnabled(can_run_ocr); self.grab_button.setToolTip(tooltip)
        if self.is_live_mode and not can_run_ocr: self.toggle_live_mode()

    def check_ocr_prerequisites(self, prompt_if_needed=False):
        sel_engine = self.translation_engine_key; engine_name = config.AVAILABLE_ENGINES.get(sel_engine, sel_engine)
        prereqs_met = True; missing = []
        self._update_prerequisite_state_flags()
        if not self._is_google_credentials_valid: prereqs_met = False; missing.append("Google Credentials (for OCR)")
        if sel_engine == "deepl_free" and not self._is_deepl_key_set: prereqs_met = False; missing.append("DeepL API Key")
        if not prereqs_met and prompt_if_needed:
            logging.info(f"OCR prereqs missing for '{engine_name}'. Prompting."); msg = f"Required for '{engine_name}':\n\n- {chr(10).join(missing)}\n\nConfigure in Settings (⚙️)."
            QMessageBox.warning(self, "Config Needed", msg); self.open_settings_dialog()
            self._update_prerequisite_state_flags()
            current_met = self._is_google_credentials_valid
            if sel_engine == "deepl_free": current_met = current_met and self._is_deepl_key_set
            self._update_ocr_button_states(); return current_met
        self._update_ocr_button_states(); return prereqs_met

    def grab_text(self):
        if not self.check_ocr_prerequisites(prompt_if_needed=True): logging.warning("OCR cancelled: Prereqs check failed."); return
        if self.ocr_running: logging.warning("OCR already running."); return
        self.ocr_running = True; logging.debug("Starting OCR worker..."); self.grab_button.setText("Working..."); self.grab_button.setEnabled(False)
        try: geo = self.geometry(); monitor = {"top": geo.top(), "left": geo.left(), "width": geo.width(), "height": geo.height()}
        except Exception as e: logging.exception("Capture region error:"); self.on_ocr_error(f"Capture Error: {e}"); self.on_thread_finished(); return
        history_snapshot = self.history_manager.get_history_list() if self.history_manager else []
        self.thread = QThread(self); self.worker = OCRWorker(monitor, self.credentials_path, self.target_language_code, history_snapshot, self.translation_engine_key, self.deepl_api_key)
        self.worker.moveToThread(self.thread); self.thread.started.connect(self.worker.run); self.worker.finished.connect(self.on_ocr_done)
        self.worker.error.connect(self.on_ocr_error); self.worker.finished.connect(self.thread.quit); self.worker.error.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater); self.worker.error.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater); self.thread.finished.connect(self.on_thread_finished)
        self.thread.start(); logging.debug("OCR worker thread started.")

    def on_ocr_done(self, ocr_text, translated_text):
        logging.info("OCR results received.")
        if self.history_manager: self.history_manager.add_item(ocr_text, translated_text)
        safe_ocr=html.escape(ocr_text or ""); safe_trans=html.escape(translated_text or "")
        lang=html.escape(self.target_language_code.upper()); ocr_fmt=safe_ocr.replace('\n','<br>'); trans_fmt=safe_trans.replace('\n','<br>')
        font=f"font-family:'{self.display_font.family()}'; font-size:{self.display_font.pointSize()}pt;"
        err="color:#A00;"; ok="color:#005;"; is_err=translated_text and translated_text.startswith("[") and "Error:" in translated_text
        html_out=f"""<div style="margin-bottom:10px;"><b style="color:#333;">--- OCR ---</b><br/><div style="color:#000; margin-left:5px; {font}">{ocr_fmt if ocr_fmt else '<i style="color:#777;">No text.</i>'}</div></div>""" \
                   f"""<div><b style="color:#333;">--- Translation ({lang}) ---</b><br/><div style="margin-left:5px; {font} {err if is_err else ok}">{trans_fmt if trans_fmt else ('<i style="color:#777;">N/A</i>' if not ocr_fmt else '<i style="color:#777;">No translation.</i>')}</div></div>"""
        self.text_display.setAlignment(Qt.AlignLeft); self.text_display.setHtml(html_out)

    def on_ocr_error(self, error_msg):
        logging.error(f"Worker error: {error_msg}")
        font=f"font-family:'{self.display_font.family()}'; font-size:{self.display_font.pointSize()}pt;"
        err_html=f"""<p style="color:#A00;font-weight:bold;">--- Error ---</p><p style="color:#A00; {font}">{html.escape(error_msg)}</p>"""
        self.text_display.setAlignment(Qt.AlignLeft); self.text_display.setHtml(err_html)

    def on_thread_finished(self):
        logging.debug("Worker thread finished signal received.")
        self.ocr_running = False; self._update_ocr_button_states()
        if not self.is_live_mode and self.grab_button.isEnabled(): self.grab_button.setText("Grab Text")
        self.thread = None; self.worker = None

    # --------------------------------------------------------------------------
    # Settings Dialog Interaction
    # --------------------------------------------------------------------------
    def open_settings_dialog(self):
        if 'SettingsDialog' not in globals() or not SettingsDialog: QMessageBox.critical(self, "Error", "SettingsDialog not loaded."); return
        logging.debug("Opening settings dialog...")
        current_data = {'credentials_path': self.credentials_path, 'deepl_api_key': self.deepl_api_key,'target_language_code': self.target_language_code, 'translation_engine': self.translation_engine_key,'display_font': self.display_font, 'bg_color': self.bg_color,'ocr_interval': self.ocr_interval, 'is_locked': self.is_locked,}
        dialog = SettingsDialog(self, current_data)
        if dialog.exec_() == QDialog.Accepted:
            logging.debug("Settings dialog accepted. Applying...")
            updated = dialog.get_updated_settings()
            self.credentials_path=updated.get('credentials_path'); self.deepl_api_key=updated.get('deepl_api_key')
            self.target_language_code=updated.get('target_language_code', self.target_language_code); self.translation_engine_key=updated.get('translation_engine', self.translation_engine_key)
            self.display_font=updated.get('display_font', self.display_font); self.ocr_interval=updated.get('ocr_interval', self.ocr_interval)
            self.is_locked=updated.get('is_locked', self.is_locked); new_alpha=updated.get('bg_alpha')
            if isinstance(new_alpha, int): self.bg_color.setAlpha(new_alpha)
            self._update_prerequisite_state_flags(); self._update_text_display_style(); self.apply_initial_lock_state()
            self.update(); self._update_ocr_button_states(); self.save_settings()
            logging.debug("Settings applied and saved.")
        else: logging.debug("Settings dialog cancelled.")

    # --------------------------------------------------------------------------
    # Window Interaction (Mouse, Paint) - Kept in main class
    # --------------------------------------------------------------------------
    def resizeEvent(self, event):
        btn_sz, btn_m, txt_m = 28, 5, 8; top_h = btn_sz+(btn_m*2); grab_w=70
        self.close_button.setGeometry(self.width()-btn_sz-btn_m, btn_m, btn_sz, btn_sz)
        self.options_button.setGeometry(self.close_button.x()-btn_sz-btn_m, btn_m, btn_sz, btn_sz)
        self.grab_button.setGeometry(btn_m, btn_m, grab_w, btn_sz)
        txt_w = max(0, self.width()-(txt_m*2)); txt_h = max(0, self.height()-top_h-txt_m)
        self.text_display.setGeometry(txt_m, top_h, txt_w, txt_h)
        if event: super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(self.bg_color)); painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 7, 7)

    def mousePressEvent(self, event):
        if self.is_locked: return
        if event.button()==Qt.LeftButton:
            self.drag_pos = None; self.resizing = False; pos = event.pos(); self.detect_resize_edges(pos)
            if any(self.resizing_edges.values()):
                self.resizing=True; self.resize_start_pos=event.globalPos(); self.original_geometry=self.geometry()
            else:
                # Check drag area (simplified) - Ensure correct indentation
                title_h = 35 # Approximate title bar height for dragging
                drag_rect = QRect(0, 0, self.width(), title_h)

                # --- Corrected Indentation Starts Here ---
                # This block should be indented under the 'else:' above
                on_widget = any(w.geometry().contains(pos) for w in [self.close_button, self.options_button, self.grab_button, self.text_display])
                if drag_rect.contains(pos) and not on_widget:
                    self.drag_pos=event.globalPos()-self.frameGeometry().topLeft()
                    self.setCursor(Qt.SizeAllCursor)
                else:
                    self.unsetCursor()
                # --- Corrected Indentation Ends Here ---


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
        if self.resizing_edges['right']: geo.setWidth(rect.width()+delta.x())
        if self.resizing_edges['bottom']: geo.setHeight(rect.height()+delta.y())
        if self.resizing_edges['left']: new_l=rect.left()+delta.x(); new_w=rect.right()-new_l+1; geo.setLeft(new_l if new_w>=min_w else rect.right()-min_w+1)
        if self.resizing_edges['top']: new_t=rect.top()+delta.y(); new_h=rect.bottom()-new_t+1; geo.setTop(new_t if new_h>=min_h else rect.bottom()-min_h+1)
        if geo.width()<min_w: geo.setWidth(min_w)
        if geo.height()<min_h: geo.setHeight(min_h)
        if self.resizing_edges['left'] and geo.width()==min_w: geo.setLeft(rect.right()-min_w+1)
        if self.resizing_edges['top'] and geo.height()==min_h: geo.setTop(rect.bottom()-min_h+1)
        self.setGeometry(geo)

    # --------------------------------------------------------------------------
    # Application Lifecycle
    # --------------------------------------------------------------------------
    def closeEvent(self, event):
        logging.info("Close event received. Cleaning up..."); self.live_mode_timer.stop()
        if 'unregister_hotkeys' in globals() and callable(unregister_hotkeys):
             try: unregister_hotkeys()
             except: logging.exception("Hotkey unregister failed:")
        if self.thread and self.thread.isRunning(): logging.warning("Worker active on close. Quitting..."); self.thread.quit(); self.thread.wait(500)
        self.save_history(); self.save_settings(); logging.info("Cleanup finished."); event.accept(); QApplication.instance().quit()

    # --------------------------------------------------------------------------
    # Live Mode
    # --------------------------------------------------------------------------
    def toggle_live_mode(self):
        if not self.is_live_mode:
             if not self.check_ocr_prerequisites(prompt_if_needed=False):
                 engine = config.AVAILABLE_ENGINES.get(self.translation_engine_key, self.translation_engine_key)
                 QMessageBox.warning(self, "Config Needed", f"Check prerequisites for '{engine}' in Settings (⚙️) to start Live Mode.")
                 return
        if self.is_live_mode:
             self.is_live_mode = False; self.live_mode_timer.stop(); logging.info("Live Mode stopped.")
             self._update_ocr_button_states();
             if self.grab_button.isEnabled(): self.grab_button.setText("Grab Text")
        else:
             self.is_live_mode = True; self.grab_button.setEnabled(False); self.grab_button.setText("Live...")
             self.live_mode_timer.start(self.ocr_interval * 1000); logging.info(f"Live Mode started (Interval: {self.ocr_interval}s).")
             self.grab_text()