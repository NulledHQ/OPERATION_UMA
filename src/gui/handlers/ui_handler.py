# filename: src/gui/handlers/ui_handler.py
import logging
from PyQt5.QtWidgets import (QWidget, QPushButton, QTextEdit, QStyle, QCheckBox,
                             QMessageBox, QDialog, QLabel, QComboBox)
from PyQt5.QtCore import Qt, QPoint, QRect, QTimer, QThread, QSettings, pyqtSignal, QByteArray, QStandardPaths, QObject, QSize, pyqtSlot, QRectF
from PyQt5.QtGui import (QColor, QPainter, QBrush, QFont, QIcon, QCursor,
                         QTextOption, QPainterPath, QFontMetrics, QPen)

try:
    from src import config
    # from .settings_state_handler import SettingsStateHandler # For type hint
except ImportError:
    logging.critical("UIManager: Failed to import config.")
    class ConfigFallback: DEFAULT_BG_COLOR = QColor(0, 0, 0, 150); MIN_WINDOW_WIDTH = 100; MIN_WINDOW_HEIGHT = 100; RESIZE_MARGIN = 10; COMMON_LANGUAGES = [("English","en")]
    config = ConfigFallback()


class UIManager(QObject):
    """Handles UI widget creation, styling, layout, and painting for MainWindow."""

    OCR_ACTIVE_BORDER_COLOR = QColor(100, 150, 255, 200)
    LOCKED_BORDER_COLOR = QColor(160, 160, 160, 220)

    def __init__(self, window: QWidget, settings_state_handler):
        super().__init__(window)
        self.window = window
        self.settings_state_handler = settings_state_handler
        self.widgets = {}
        # Styles...
        self._status_label_style = "QLabel { color: #DDD; padding: 0px 5px; background-color: transparent; font-size: 10px; }"
        self._status_clear_timer = QTimer(self); self._status_clear_timer.setSingleShot(True); self._status_clear_timer.timeout.connect(self.clear_status)
        self._draw_active_border = False; self._active_border_color = self.OCR_ACTIVE_BORDER_COLOR; self._is_window_locked = False
        self._close_style = "QPushButton { background-color: transparent; border: none; border-radius: 4px; padding: 4px; } QPushButton:hover { background-color: rgba(255, 0, 0, 180); } QPushButton:pressed { background-color: rgba(200, 0, 0, 200); }"
        self._options_style = "QPushButton { background-color: transparent; border: none; border-radius: 4px; font-size: 16px; padding: 4px; } QPushButton:hover { background-color: rgba(100, 100, 255, 150); } QPushButton:pressed { background-color: rgba(80, 80, 200, 180); }"
        self._grab_style = "QPushButton { background-color: rgba(200, 200, 200, 100); border: none; border-radius: 4px; font-size: 11px; padding: 4px 8px; color: #333; } QPushButton:hover { background-color: rgba(180, 210, 255, 150); } QPushButton:pressed { background-color: rgba(150, 190, 230, 180); } QPushButton:disabled { background-color: rgba(220, 220, 220, 80); color: #999; }"
        self._checkbox_style_base = "font-size: 11px; color: #333; margin-left: 5px;"
        self._checkbox_style_indicator = "QCheckBox::indicator { width: 13px; height: 13px; }"
        self._checkbox_style_disabled = "QCheckBox:disabled { color: #999; }"
        # --- Styles for Retranslate Controls (Updated) ---
        self._retranslate_combo_style = """
            QComboBox {
                font-size: 10px;
                min-height: 18px;
                border: 1px solid #555; /* Add border */
                border-radius: 3px; /* Slightly rounded corners */
                padding-left: 4px;
                background-color: #333; /* Darker background */
                color: #EEE; /* Lighter text */
            }
            QComboBox:disabled {
                 background-color: #555;
                 color: #AAA;
            }
            QComboBox QAbstractItemView { /* Dropdown list style */
                font-size: 10px;
                background-color: #444;
                color: #EEE;
                selection-background-color: #558; /* Highlight selection */
                border: 1px solid #666;
            }
            QComboBox::drop-down { /* Arrow button */
                border: none;
                background-color: transparent;
                width: 15px;
            }
            QComboBox::down-arrow {
                 image: url(:/qt-project.org/styles/commonstyle/images/downarraow-16.png); /* Use a standard arrow if available */
                 width: 10px; height: 10px; /* Adjust size */
            }
            /* Fallback if standard arrow not found */
            QComboBox::down-arrow:on { top: 1px; left: 1px; }
         """
        self._retranslate_button_style = """
            QPushButton {
                background-color: rgba(200, 200, 200, 100);
                border: none;
                border-radius: 4px;
                font-size: 10px;
                padding: 2px 6px; /* Adjust padding */
                color: #333;
                min-height: 18px; /* Match combo box height */
            }
            QPushButton:hover { background-color: rgba(180, 210, 255, 150); }
            QPushButton:pressed { background-color: rgba(150, 190, 230, 180); }
            QPushButton:disabled { background-color: rgba(220, 220, 220, 80); color: #999; }
         """
        # --- End Updated Styles ---


    def setup_window_properties(self):
        # (Remains the same)
        self.window.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.window.setAttribute(Qt.WA_TranslucentBackground)
        self.window.setMinimumSize(config.MIN_WINDOW_WIDTH, config.MIN_WINDOW_HEIGHT + 25) # Increase min height slightly for bottom bar
        self.window.setMouseTracking(True)

    def setup_ui(self):
        # (Remains the same)
        logging.debug("UIManager initializing UI widgets.")
        close_button = QPushButton(self.window); close_icon = self.window.style().standardIcon(QStyle.SP_TitleBarCloseButton)
        close_button.setIcon(close_icon); close_button.setIconSize(QSize(16, 16)); close_button.setFlat(True); close_button.clicked.connect(self.window.close)
        close_button.setToolTip("Close"); close_button.setStyleSheet(self._close_style); self.widgets['close_button'] = close_button
        options_button = QPushButton('⚙️', self.window); options_button.setFlat(True); options_button.clicked.connect(self.window.open_settings_dialog)
        options_button.setToolTip("Settings"); options_button.setStyleSheet(self._options_style); self.widgets['options_button'] = options_button
        grab_button = QPushButton('Grab Text', self.window); grab_button.setFlat(True); grab_button.setStyleSheet(self._grab_style); self.widgets['grab_button'] = grab_button
        live_mode_checkbox = QCheckBox("Live", self.window); live_mode_checkbox.setToolTip("Enable/Disable periodic OCR mode")
        live_mode_checkbox.setStyleSheet(f"QCheckBox {{ {self._checkbox_style_base} }} {self._checkbox_style_indicator} {self._checkbox_style_disabled}")
        live_mode_checkbox.stateChanged.connect(self.window.on_live_mode_checkbox_changed); self.widgets['live_mode_checkbox'] = live_mode_checkbox
        text_display = QTextEdit(self.window); text_display.setReadOnly(True); text_display.setWordWrapMode(QTextOption.WrapAnywhere)
        text_display.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded); text_display.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.widgets['text_display'] = text_display
        status_label = QLabel("", self.window); status_label.setStyleSheet(self._status_label_style); status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.widgets['status_label'] = status_label
        retranslate_lang_combo = QComboBox(self.window); retranslate_lang_combo.setStyleSheet(self._retranslate_combo_style); retranslate_lang_combo.setToolTip("Select language for re-translation")
        current_target_lang = self.settings_state_handler.get_value('target_language_code', config.DEFAULT_TARGET_LANGUAGE_CODE); selected_index = 0
        for index, (display_name, code) in enumerate(config.COMMON_LANGUAGES): retranslate_lang_combo.addItem(display_name, code);
        if code == current_target_lang: selected_index = index
        retranslate_lang_combo.setCurrentIndex(selected_index); self.widgets['retranslate_lang_combo'] = retranslate_lang_combo
        retranslate_button = QPushButton("Translate Again", self.window); retranslate_button.setStyleSheet(self._retranslate_button_style)
        retranslate_button.setToolTip("Translate last captured text into selected language"); retranslate_button.clicked.connect(self.window.on_retranslate_clicked)
        self.widgets['retranslate_button'] = retranslate_button
        self.update_text_display_style()

    def update_text_display_style(self):
        # (Remains the same)
        text_display = self.widgets.get('text_display')
        if not text_display or not self.settings_state_handler: return
        current_font = self.settings_state_handler.get_value('display_font', QFont()); bg_color = self.settings_state_handler.get_value('bg_color', QColor(config.DEFAULT_BG_COLOR))
        current_alpha = bg_color.alpha(); text_display.setFont(current_font)
        bg_r, bg_g, bg_b = 255, 255, 255; alpha_float = max(0.0, min(1.0, current_alpha / 255.0))
        text_bg_color_str = f"rgba({bg_r}, {bg_g}, {bg_b}, {alpha_float:.3f})"; text_color_str = "#000000"
        style = ( f"QTextEdit {{ background-color: {text_bg_color_str}; color: {text_color_str}; border-radius: 5px; padding: 5px; }}" )
        text_display.setStyleSheet(style)

    def handle_resize_event(self, event):
        """Handles window resize events to reposition widgets."""
        # --- Layout Adjustments ---
        btn_sz, btn_m, txt_m = 28, 5, 8
        top_h = btn_sz + (btn_m * 2)
        grab_w = 70
        live_cb = self.widgets.get('live_mode_checkbox'); checkbox_w = 0
        if live_cb: fm = QFontMetrics(live_cb.font()); checkbox_w = fm.horizontalAdvance(live_cb.text()) + 25
        else: checkbox_w = 55
        checkbox_m = 5
        # --- Define bottom bar dimensions ---
        status_h = 22 # Increased height slightly for padding
        bottom_margin_outer = 5 # Margin from window bottom edge
        bottom_margin_inner = 2 # Padding within the bottom area
        retrans_btn_w = 90; retrans_combo_w = 100; retrans_m = 5
        # --- End Bottom Bar Dimensions ---

        window_w = self.window.width()
        window_h = self.window.height()

        # Position top row widgets (same)
        close_btn = self.widgets.get('close_button'); options_btn = self.widgets.get('options_button'); grab_btn = self.widgets.get('grab_button')
        if close_btn: close_btn.setGeometry(window_w - btn_sz - btn_m, btn_m, btn_sz, btn_sz)
        if options_btn and close_btn: options_btn.setGeometry(close_btn.x() - btn_sz - btn_m, btn_m, btn_sz, btn_sz)
        grab_x = btn_m; 
        if grab_btn: grab_btn.setGeometry(grab_x, btn_m, grab_w, btn_sz)
        if live_cb and grab_btn: live_cb.setGeometry(grab_btn.x() + grab_btn.width() + checkbox_m, btn_m, checkbox_w, btn_sz)

        # Position bottom row widgets
        status_label = self.widgets.get('status_label')
        retrans_combo = self.widgets.get('retranslate_lang_combo')
        retrans_btn = self.widgets.get('retranslate_button')
        # Calculate Y position for bottom widgets (vertically centered within status_h)
        bottom_y = window_h - status_h - bottom_margin_outer + bottom_margin_inner

        current_x = window_w - txt_m # Start from right edge (with text margin)
        if retrans_btn:
            current_x -= retrans_btn_w
            # Adjust height slightly less than status_h for centering
            retrans_btn.setGeometry(current_x, bottom_y, retrans_btn_w, status_h - (bottom_margin_inner * 2))
        if retrans_combo:
             current_x -= (retrans_combo_w + retrans_m)
             # Adjust height slightly less than status_h for centering
             retrans_combo.setGeometry(current_x, bottom_y, retrans_combo_w, status_h - (bottom_margin_inner * 2))

        if status_label:
            status_w = max(0, current_x - txt_m - retrans_m)
            status_label.setGeometry(txt_m, bottom_y, status_w, status_h - (bottom_margin_inner * 2))

        # Position Text Display (Adjust available height)
        text_dsp = self.widgets.get('text_display')
        if text_dsp:
            txt_w = max(config.MIN_WINDOW_WIDTH - (txt_m * 2), window_w - (txt_m * 2))
            available_h = window_h - top_h - status_h - bottom_margin_outer - txt_m # Use outer margin
            txt_h = max(config.MIN_WINDOW_HEIGHT - top_h - status_h - bottom_margin_outer - txt_m, available_h)
            text_dsp.setGeometry(txt_m, top_h, txt_w, txt_h)

    def handle_paint_event(self, event):
        # (Remains the same)
        painter = QPainter(self.window); painter.setRenderHint(QPainter.Antialiasing)
        frame_color = QColor(0, 0, 0, 255); text_display = self.widgets.get('text_display')
        text_area_rect = text_display.geometry() if text_display else QRect(); window_rect = self.window.rect(); border_radius = 7.0
        full_window_path = QPainterPath(); full_window_path.addRoundedRect(QRectF(window_rect), border_radius, border_radius)
        text_area_path = QPainterPath();
        if text_area_rect.isValid(): text_area_path.addRect(QRectF(text_area_rect))
        background_path = full_window_path.subtracted(text_area_path) if text_area_rect.isValid() else full_window_path
        painter.setPen(Qt.NoPen); painter.setBrush(QBrush(frame_color)); painter.drawPath(background_path)
        border_pen = QPen(); border_pen.setWidth(2); draw_border = False
        if self._draw_active_border: border_pen.setColor(self._active_border_color); draw_border = True
        elif self._is_window_locked: border_pen.setColor(self.LOCKED_BORDER_COLOR); draw_border = True
        if draw_border: painter.setPen(border_pen); painter.setBrush(Qt.NoBrush); painter.drawPath(full_window_path)
        painter.end()

    # --- Status Methods ---
    def set_status(self, message: str, timeout: int = 0):
        status_label = self.widgets.get('status_label')
        if status_label: status_label.setText(message); logging.debug(f"Status set: {message}"); self._status_clear_timer.stop();
        if timeout > 0: self._status_clear_timer.start(timeout)

    def clear_status(self):
        status_label = self.widgets.get('status_label')
        if status_label: status_label.setText(""); logging.debug("Status cleared.")

    # --- OCR/Lock Feedback Methods ---
    def show_ocr_active_feedback(self, color=None):
        self._draw_active_border = True; self._active_border_color = color if color else self.OCR_ACTIVE_BORDER_COLOR; self.window.update()
    def hide_ocr_active_feedback(self):
        if self._draw_active_border: self._draw_active_border = False; self.window.update()
    def set_locked_indicator(self, is_locked: bool):
        if self._is_window_locked != is_locked: self._is_window_locked = is_locked; self.window.update()

    # --- Retranslate Control Methods ---
    def get_retranslate_language_code(self) -> str | None:
        combo = self.widgets.get('retranslate_lang_combo'); return combo.currentData() if combo else None
    def set_retranslate_controls_enabled(self, enabled: bool):
        combo = self.widgets.get('retranslate_lang_combo'); button = self.widgets.get('retranslate_button')
        if combo: combo.setEnabled(enabled)
        if button: button.setEnabled(enabled)

    # --- Other UI Update Helpers ---
    def get_widget(self, name: str): return self.widgets.get(name)
    def set_grab_button_state(self, enabled: bool, text: str = None, tooltip: str = None):
        grab_button = self.widgets.get('grab_button');
        if grab_button: grab_button.setEnabled(enabled);
        if text is not None: grab_button.setText(text)
        if tooltip is not None: grab_button.setToolTip(tooltip)
    def set_live_mode_checkbox_state(self, checked: bool, enabled: bool, is_active: bool):
        live_cb = self.widgets.get('live_mode_checkbox')
        if live_cb:
            live_cb.blockSignals(True); live_cb.setChecked(checked); live_cb.setEnabled(enabled)
            if is_active: live_cb.setText("Live ●"); active_style = "font-weight: bold; color: #007A00;" ; live_cb.setStyleSheet(f"QCheckBox {{ {self._checkbox_style_base} {active_style} }} {self._checkbox_style_indicator} {self._checkbox_style_disabled}")
            else: live_cb.setText("Live"); live_cb.setStyleSheet(f"QCheckBox {{ {self._checkbox_style_base} }} {self._checkbox_style_indicator} {self._checkbox_style_disabled}")
            live_cb.blockSignals(False)
    def update_text_display_content(self, html_content: str, alignment=Qt.AlignLeft):
        text_display = self.widgets.get('text_display')
        if text_display: text_display.setAlignment(alignment); text_display.setHtml(html_content)
    def set_text_display_visibility(self, visible: bool):
        text_display = self.widgets.get('text_display')
        if text_display: text_display.setVisible(visible)
    def get_text_display_geometry(self) -> QRect:
         text_display = self.widgets.get('text_display'); return text_display.geometry() if text_display else QRect()
    def get_button_geometry(self, name: str) -> QRect:
         button = self.widgets.get(name); return button.geometry() if button else QRect()