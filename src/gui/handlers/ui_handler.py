# filename: src/gui/handlers/ui_handler.py
import logging
from PyQt5.QtWidgets import (QWidget, QPushButton, QTextEdit, QStyle, QCheckBox,
                             QMessageBox, QDialog)
from PyQt5.QtCore import Qt, QPoint, QRect, QTimer, QThread, QSettings, pyqtSignal, QByteArray, QStandardPaths, QObject, QSize, pyqtSlot, QRectF
from PyQt5.QtGui import QColor, QPainter, QBrush, QFont, QIcon, QCursor, QTextOption, QPainterPath, QFontMetrics

try:
    from src import config
    # from .settings_state_handler import SettingsStateHandler # For type hint
except ImportError:
    logging.critical("UIManager: Failed to import config.")
    class ConfigFallback: DEFAULT_BG_COLOR = QColor(0, 0, 0, 150); MIN_WINDOW_WIDTH = 100; MIN_WINDOW_HEIGHT = 100; RESIZE_MARGIN = 10
    config = ConfigFallback()


class UIManager(QObject):
    """Handles UI widget creation, styling, layout, and painting for MainWindow."""

    def __init__(self, window: QWidget, settings_state_handler): # Added settings_state_handler
        super().__init__(window)
        self.window = window
        self.settings_state_handler = settings_state_handler # Store handler
        self.widgets = {}
        # (Styles remain the same)
        self._close_style = "QPushButton { background-color: transparent; border: none; border-radius: 4px; padding: 4px; } QPushButton:hover { background-color: rgba(255, 0, 0, 180); } QPushButton:pressed { background-color: rgba(200, 0, 0, 200); }"
        self._options_style = "QPushButton { background-color: transparent; border: none; border-radius: 4px; font-size: 16px; padding: 4px; } QPushButton:hover { background-color: rgba(100, 100, 255, 150); } QPushButton:pressed { background-color: rgba(80, 80, 200, 180); }"
        self._grab_style = "QPushButton { background-color: rgba(200, 200, 200, 100); border: none; border-radius: 4px; font-size: 11px; padding: 4px 8px; color: #333; } QPushButton:hover { background-color: rgba(180, 210, 255, 150); } QPushButton:pressed { background-color: rgba(150, 190, 230, 180); } QPushButton:disabled { background-color: rgba(220, 220, 220, 80); color: #999; }"
        self._checkbox_style_base = "font-size: 11px; color: #333; margin-left: 5px;"
        self._checkbox_style_indicator = "QCheckBox::indicator { width: 13px; height: 13px; }"
        self._checkbox_style_disabled = "QCheckBox:disabled { color: #999; }"

    def setup_window_properties(self):
        self.window.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.window.setAttribute(Qt.WA_TranslucentBackground)
        self.window.setMinimumSize(config.MIN_WINDOW_WIDTH, config.MIN_WINDOW_HEIGHT)
        self.window.setMouseTracking(True)

    def setup_ui(self):
        """Initializes the user interface widgets."""
        logging.debug("UIManager initializing UI widgets.")

        # Close Button
        close_button = QPushButton(self.window); close_icon = self.window.style().standardIcon(QStyle.SP_TitleBarCloseButton)
        close_button.setIcon(close_icon); close_button.setIconSize(QSize(16, 16)); close_button.setFlat(True); close_button.clicked.connect(self.window.close)
        close_button.setToolTip("Close"); close_button.setStyleSheet(self._close_style); self.widgets['close_button'] = close_button

        # Options Button
        options_button = QPushButton('⚙️', self.window); options_button.setFlat(True); options_button.clicked.connect(self.window.open_settings_dialog)
        options_button.setToolTip("Settings"); options_button.setStyleSheet(self._options_style); self.widgets['options_button'] = options_button

        # Grab Button
        grab_button = QPushButton('Grab Text', self.window); grab_button.setFlat(True); grab_button.setStyleSheet(self._grab_style); self.widgets['grab_button'] = grab_button
        # Connection happens in MainWindow after UI setup

        # Live Mode Checkbox
        live_mode_checkbox = QCheckBox("Live", self.window); live_mode_checkbox.setToolTip("Enable/Disable periodic OCR mode")
        live_mode_checkbox.setStyleSheet(f"QCheckBox {{ {self._checkbox_style_base} }} {self._checkbox_style_indicator} {self._checkbox_style_disabled}")
        live_mode_checkbox.stateChanged.connect(self.window.on_live_mode_checkbox_changed); self.widgets['live_mode_checkbox'] = live_mode_checkbox

        # Text Display Area
        text_display = QTextEdit(self.window); text_display.setReadOnly(True); text_display.setWordWrapMode(QTextOption.WrapAnywhere)
        text_display.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded); text_display.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.widgets['text_display'] = text_display

        self.update_text_display_style() # Initial style update based on state handler

    def update_text_display_style(self):
        """Updates the QTextEdit style using settings from SettingsStateHandler."""
        text_display = self.widgets.get('text_display')
        if not text_display or not self.settings_state_handler: return

        # Get state from the SettingsStateHandler
        current_font = self.settings_state_handler.get_value('display_font', QFont())
        bg_color = self.settings_state_handler.get_value('bg_color', QColor(config.DEFAULT_BG_COLOR))
        current_alpha = bg_color.alpha() # Get alpha from the stored color object

        text_display.setFont(current_font)

        bg_r, bg_g, bg_b = 255, 255, 255
        alpha_float = max(0.0, min(1.0, current_alpha / 255.0))
        text_bg_color_str = f"rgba({bg_r}, {bg_g}, {bg_b}, {alpha_float:.3f})"
        text_color_str = "#000000"

        style = ( f"QTextEdit {{ background-color: {text_bg_color_str}; color: {text_color_str}; border-radius: 5px; padding: 5px; }}" )
        text_display.setStyleSheet(style)
        logging.debug(f"UIManager updated text_display style with alpha {current_alpha} -> {alpha_float:.3f}")

    def handle_resize_event(self, event):
        # (Layout logic remains the same)
        btn_sz, btn_m, txt_m = 28, 5, 8; top_h = btn_sz + (btn_m * 2); grab_w = 70
        live_cb = self.widgets.get('live_mode_checkbox'); checkbox_w = 0
        if live_cb: fm = QFontMetrics(live_cb.font()); checkbox_w = fm.horizontalAdvance(live_cb.text()) + 25
        else: checkbox_w = 55
        checkbox_m = 5; window_w = self.window.width(); window_h = self.window.height()
        close_btn = self.widgets.get('close_button'); options_btn = self.widgets.get('options_button')
        grab_btn = self.widgets.get('grab_button'); text_dsp = self.widgets.get('text_display')
        if close_btn: close_btn.setGeometry(window_w - btn_sz - btn_m, btn_m, btn_sz, btn_sz)
        if options_btn and close_btn: options_btn.setGeometry(close_btn.x() - btn_sz - btn_m, btn_m, btn_sz, btn_sz)
        grab_x = btn_m
        if grab_btn: grab_btn.setGeometry(grab_x, btn_m, grab_w, btn_sz)
        if live_cb and grab_btn: live_cb.setGeometry(grab_btn.x() + grab_btn.width() + checkbox_m, btn_m, checkbox_w, btn_sz)
        if text_dsp:
            txt_w = max(config.MIN_WINDOW_WIDTH - (txt_m * 2), window_w - (txt_m * 2))
            txt_h = max(config.MIN_WINDOW_HEIGHT - top_h - txt_m, window_h - top_h - txt_m)
            text_dsp.setGeometry(txt_m, top_h, txt_w, txt_h)

    def handle_paint_event(self, event):
        """Paints the main window's background using color from state handler."""
        painter = QPainter(self.window); painter.setRenderHint(QPainter.Antialiasing)

        # Get base frame color (fixed alpha black) - Maybe this should come from state too? For now, keep it simple.
        frame_color = QColor(0, 0, 0, 255) # Use fixed black frame for now
        # bg_color_setting = self.settings_state_handler.get_value('bg_color', QColor(config.DEFAULT_BG_COLOR))
        # frame_color = QColor(bg_color_setting.red(), bg_color_setting.green(), bg_color_setting.blue(), 255) # Use setting RGB, fixed Alpha

        text_display = self.widgets.get('text_display')
        text_area_rect = text_display.geometry() if text_display else QRect()
        window_rect = self.window.rect(); border_radius = 7.0
        full_window_path = QPainterPath(); full_window_path.addRoundedRect(QRectF(window_rect), border_radius, border_radius)
        text_area_path = QPainterPath();
        if text_area_rect.isValid(): text_area_path.addRect(QRectF(text_area_rect))
        background_path = full_window_path
        if text_area_rect.isValid(): background_path = full_window_path.subtracted(text_area_path)
        painter.setPen(Qt.NoPen); painter.setBrush(QBrush(frame_color)); painter.drawPath(background_path); painter.end()

    # --- UI Update Helper Methods (remain the same) ---
    def get_widget(self, name: str): return self.widgets.get(name)
    def set_grab_button_state(self, enabled: bool, text: str = None, tooltip: str = None):
        grab_button = self.widgets.get('grab_button')
        if grab_button: grab_button.setEnabled(enabled);
        if text is not None: grab_button.setText(text)
        if tooltip is not None: grab_button.setToolTip(tooltip)
    def set_live_mode_checkbox_state(self, checked: bool, enabled: bool, is_active: bool):
        live_cb = self.widgets.get('live_mode_checkbox')
        if live_cb:
            live_cb.blockSignals(True); live_cb.setChecked(checked); live_cb.setEnabled(enabled)
            if is_active:
                live_cb.setText("Live ●"); active_style = "font-weight: bold; color: #007A00;"
                live_cb.setStyleSheet(f"QCheckBox {{ {self._checkbox_style_base} {active_style} }} {self._checkbox_style_indicator} {self._checkbox_style_disabled}")
            else:
                live_cb.setText("Live"); live_cb.setStyleSheet(f"QCheckBox {{ {self._checkbox_style_base} }} {self._checkbox_style_indicator} {self._checkbox_style_disabled}")
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