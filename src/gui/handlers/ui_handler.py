# src/gui/handlers/ui_handler.py

import logging
# Make sure QCheckBox is imported
from PyQt5.QtWidgets import (QWidget, QPushButton, QTextEdit, QStyle, QCheckBox,
                             QMessageBox, QDialog, QLabel, QComboBox)
from PyQt5.QtCore import Qt, QPoint, QRect, QTimer, QThread, QSettings, pyqtSignal, QByteArray, QStandardPaths, QObject, QSize, pyqtSlot, QRectF
from PyQt5.QtGui import (QColor, QPainter, QBrush, QFont, QIcon, QCursor,
                         QTextOption, QPainterPath, QFontMetrics, QPen)

try:
    from src import config
except ImportError:
    logging.critical("UIManager: Failed to import config.")
    # Basic fallback for essential attributes if config fails
    class ConfigFallback:
        DEFAULT_BG_COLOR = QColor(0, 0, 0, 150)
        MIN_WINDOW_WIDTH = 100
        MIN_WINDOW_HEIGHT = 100
        RESIZE_MARGIN = 10
        COMMON_LANGUAGES = [("English","en")]
        DEFAULT_TARGET_LANGUAGE_CODE="en"
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
        self._status_clear_timer = QTimer(self)
        self._status_clear_timer.setSingleShot(True)
        self._status_clear_timer.timeout.connect(self.clear_status)
        self._draw_active_border = False
        self._active_border_color = self.OCR_ACTIVE_BORDER_COLOR
        self._is_window_locked = False
        # --- Existing Styles ---
        self._close_style = "QPushButton { background-color: transparent; border: none; border-radius: 4px; padding: 4px; } QPushButton:hover { background-color: rgba(255, 0, 0, 180); } QPushButton:pressed { background-color: rgba(200, 0, 0, 200); }"
        self._options_style = "QPushButton { background-color: transparent; border: none; border-radius: 4px; font-size: 16px; padding: 4px; } QPushButton:hover { background-color: rgba(100, 100, 255, 150); } QPushButton:pressed { background-color: rgba(80, 80, 200, 180); }"
        self._grab_style = "QPushButton { background-color: rgba(200, 200, 200, 100); border: none; border-radius: 4px; font-size: 11px; padding: 4px 8px; color: #333; } QPushButton:hover { background-color: rgba(180, 210, 255, 150); } QPushButton:pressed { background-color: rgba(150, 190, 230, 180); } QPushButton:disabled { background-color: rgba(220, 220, 220, 80); color: #999; }"
        self._checkbox_style_base = "font-size: 11px; color: #333; margin-left: 5px;"
        self._checkbox_style_indicator = "QCheckBox::indicator { width: 13px; height: 13px; }"
        self._checkbox_style_disabled = "QCheckBox:disabled { color: #999; }"
        # --- New Styles ---
        self._minimize_style = "QPushButton { background-color: transparent; border: none; border-radius: 4px; padding: 4px; } QPushButton:hover { background-color: rgba(100, 100, 100, 150); } QPushButton:pressed { background-color: rgba(80, 80, 80, 180); }"
        self._always_on_top_checkbox_style = f"QCheckBox {{ font-size: 10px; color: #EEE; margin-left: 5px; }} {self._checkbox_style_indicator} {self._checkbox_style_disabled}"
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
                 /* Try to use standard arrow - may vary by platform/style */
                 image: url(:/qt-project.org/styles/commonstyle/images/downarraow-16.png);
                 width: 10px; height: 10px; /* Adjust size */
            }
            /* Fallback if standard arrow not found or for more control */
            /* QComboBox::down-arrow:on { top: 1px; left: 1px; } */
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

    def setup_window_properties(self):
        # Remove Qt.Tool flag to show in taskbar
        # Keep Qt.WindowStaysOnTopHint as the initial default
        self.window.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint )
        self.window.setAttribute(Qt.WA_TranslucentBackground)
        # Adjust minimum height if needed for new controls
        self.window.setMinimumSize(config.MIN_WINDOW_WIDTH, config.MIN_WINDOW_HEIGHT + 25)
        self.window.setMouseTracking(True)

    def setup_ui(self):
        logging.debug("UIManager initializing UI widgets.")
        # --- Close Button ---
        close_button = QPushButton(self.window)
        close_icon = self.window.style().standardIcon(QStyle.SP_TitleBarCloseButton)
        close_button.setIcon(close_icon)
        close_button.setIconSize(QSize(16, 16))
        close_button.setFlat(True)
        close_button.clicked.connect(self.window.close)
        close_button.setToolTip("Close")
        close_button.setStyleSheet(self._close_style)
        self.widgets['close_button'] = close_button

        # --- Minimize Button (New) ---
        minimize_button = QPushButton(self.window)
        minimize_icon = self.window.style().standardIcon(QStyle.SP_TitleBarMinButton)
        minimize_button.setIcon(minimize_icon)
        minimize_button.setIconSize(QSize(16, 16))
        minimize_button.setFlat(True)
        minimize_button.clicked.connect(self.window.showMinimized) # Connect directly
        minimize_button.setToolTip("Minimize")
        minimize_button.setStyleSheet(self._minimize_style)
        self.widgets['minimize_button'] = minimize_button

        # --- Options Button ---
        options_button = QPushButton('⚙️', self.window)
        options_button.setFlat(True)
        options_button.clicked.connect(self.window.open_settings_dialog)
        options_button.setToolTip("Settings")
        options_button.setStyleSheet(self._options_style)
        self.widgets['options_button'] = options_button

        # --- Grab Button ---
        grab_button = QPushButton('Grab Text', self.window)
        grab_button.setFlat(True)
        grab_button.setStyleSheet(self._grab_style)
        # grab_button connection is done in MainWindow.__init__
        self.widgets['grab_button'] = grab_button

        # --- Live Mode Checkbox ---
        live_mode_checkbox = QCheckBox("Live", self.window)
        live_mode_checkbox.setToolTip("Enable/Disable periodic OCR mode")
        live_mode_checkbox.setStyleSheet(f"QCheckBox {{ {self._checkbox_style_base} }} {self._checkbox_style_indicator} {self._checkbox_style_disabled}")
        live_mode_checkbox.stateChanged.connect(self.window.on_live_mode_checkbox_changed)
        self.widgets['live_mode_checkbox'] = live_mode_checkbox

        # --- Text Display ---
        text_display = QTextEdit(self.window)
        text_display.setReadOnly(True)
        text_display.setWordWrapMode(QTextOption.WrapAnywhere)
        text_display.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        text_display.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.widgets['text_display'] = text_display

        # --- Status Label ---
        status_label = QLabel("", self.window)
        status_label.setStyleSheet(self._status_label_style)
        status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.widgets['status_label'] = status_label

        # --- Always-on-Top Checkbox (New) ---
        always_on_top_checkbox = QCheckBox("Always on Top", self.window)
        always_on_top_checkbox.setToolTip("Toggle always-on-top behavior")
        always_on_top_checkbox.setStyleSheet(self._always_on_top_checkbox_style)
        # Check if the initial flags include WindowStaysOnTopHint
        initial_flags = self.window.windowFlags()
        always_on_top_checkbox.setChecked(bool(initial_flags & Qt.WindowStaysOnTopHint))
        # Connection needs to be done in MainWindow
        self.widgets['always_on_top_checkbox'] = always_on_top_checkbox

        # --- Retranslate Language Combo ---
        retranslate_lang_combo = QComboBox(self.window)
        retranslate_lang_combo.setStyleSheet(self._retranslate_combo_style)
        retranslate_lang_combo.setToolTip("Select language for re-translation")
        current_target_lang = self.settings_state_handler.get_value('target_language_code', config.DEFAULT_TARGET_LANGUAGE_CODE)
        selected_index = 0
        # Populate combo box
        for index, (display_name, code) in enumerate(config.COMMON_LANGUAGES):
            retranslate_lang_combo.addItem(display_name, code)
            if code == current_target_lang:
                selected_index = index
        retranslate_lang_combo.setCurrentIndex(selected_index)
        self.widgets['retranslate_lang_combo'] = retranslate_lang_combo

        # --- Retranslate Button ---
        retranslate_button = QPushButton("Translate Again", self.window)
        retranslate_button.setStyleSheet(self._retranslate_button_style)
        retranslate_button.setToolTip("Translate last captured text into selected language")
        retranslate_button.clicked.connect(self.window.on_retranslate_clicked)
        self.widgets['retranslate_button'] = retranslate_button

        self.update_text_display_style()

    def update_text_display_style(self):
        text_display = self.widgets.get('text_display')
        if not text_display or not self.settings_state_handler:
            return
        # Safely get settings
        current_font = self.settings_state_handler.get_value('display_font', QFont())
        if not isinstance(current_font, QFont): current_font = QFont() # Fallback if not QFont

        bg_color = self.settings_state_handler.get_value('bg_color', QColor(config.DEFAULT_BG_COLOR))
        if not isinstance(bg_color, QColor) or not bg_color.isValid(): bg_color = QColor(config.DEFAULT_BG_COLOR) # Fallback

        current_alpha = bg_color.alpha()
        text_display.setFont(current_font)

        # Use white base for text area, apply alpha
        bg_r, bg_g, bg_b = 255, 255, 255
        alpha_float = max(0.0, min(1.0, current_alpha / 255.0))
        text_bg_color_str = f"rgba({bg_r}, {bg_g}, {bg_b}, {alpha_float:.3f})"
        text_color_str = "#000000" # Black text

        style = (
            f"QTextEdit {{ "
            f"background-color: {text_bg_color_str}; "
            f"color: {text_color_str}; "
            f"border-radius: 5px; "
            f"padding: 5px; "
            f"}}"
        )
        text_display.setStyleSheet(style)

    def handle_resize_event(self, event):
        """Handles window resize events to reposition widgets."""
        # Define sizes and margins
        btn_sz, btn_m, txt_m = 28, 5, 8  # Standard button size, margin, text area margin
        top_h = btn_sz + (btn_m * 2)      # Height of the top control area
        grab_w = 70                       # Width of the grab button
        status_h = 22                     # Height of the bottom status bar area
        bottom_margin_outer = 5           # Margin below status bar
        bottom_margin_inner = 2           # Padding within status bar area
        retrans_btn_w = 90                # Width of retranslate button
        retrans_combo_w = 100             # Width of retranslate combo box
        retrans_m = 5                     # Margin between retranslate controls

        # Get widget dimensions dynamically
        live_cb = self.widgets.get('live_mode_checkbox')
        checkbox_w = 0
        if live_cb:
            fm = QFontMetrics(live_cb.font())
            checkbox_w = fm.horizontalAdvance(live_cb.text()) + 25 # Estimate width
        else:
            checkbox_w = 55 # Fallback width

        aot_cb = self.widgets.get('always_on_top_checkbox')
        aot_cb_w = 0
        if aot_cb:
            fm_aot = QFontMetrics(aot_cb.font())
            aot_cb_w = fm_aot.horizontalAdvance(aot_cb.text()) + 25 # Estimate width
        else:
            aot_cb_w = 110 # Fallback width

        checkbox_m = 5 # Margin for live checkbox
        aot_cb_m = 5   # Margin for always-on-top checkbox

        window_w = self.window.width()
        window_h = self.window.height()

        # --- Position Top Row Widgets (Right to Left) ---
        close_btn = self.widgets.get('close_button')
        minimize_btn = self.widgets.get('minimize_button')
        options_btn = self.widgets.get('options_button')

        current_top_x = window_w - btn_m # Start from right edge
        if close_btn:
            current_top_x -= btn_sz
            close_btn.setGeometry(current_top_x, btn_m, btn_sz, btn_sz)
        if minimize_btn:
            current_top_x -= (btn_sz + btn_m)
            minimize_btn.setGeometry(current_top_x, btn_m, btn_sz, btn_sz)
        if options_btn:
            current_top_x -= (btn_sz + btn_m)
            options_btn.setGeometry(current_top_x, btn_m, btn_sz, btn_sz)

        # --- Position Top Row Widgets (Left to Right) ---
        grab_btn = self.widgets.get('grab_button')
        if grab_btn:
            grab_btn.setGeometry(btn_m, btn_m, grab_w, btn_sz)
        if live_cb and grab_btn:
            live_cb.setGeometry(grab_btn.x() + grab_btn.width() + checkbox_m, btn_m, checkbox_w, btn_sz)


        # --- Position Bottom Row Widgets (Right to Left) ---
        status_label = self.widgets.get('status_label')
        retrans_combo = self.widgets.get('retranslate_lang_combo')
        retrans_btn = self.widgets.get('retranslate_button')

        bottom_y = window_h - status_h - bottom_margin_outer + bottom_margin_inner
        bottom_widget_h = status_h - (bottom_margin_inner * 2) # Effective height for widgets

        current_bottom_x = window_w - txt_m # Start from right edge (inside text margin)

        if retrans_btn:
            current_bottom_x -= retrans_btn_w
            retrans_btn.setGeometry(current_bottom_x, bottom_y, retrans_btn_w, bottom_widget_h)
        if retrans_combo:
            current_bottom_x -= (retrans_combo_w + retrans_m)
            retrans_combo.setGeometry(current_bottom_x, bottom_y, retrans_combo_w, bottom_widget_h)
        if aot_cb: # Position Always-on-Top checkbox to the left
             current_bottom_x -= (aot_cb_w + aot_cb_m)
             aot_cb.setGeometry(current_bottom_x, bottom_y, aot_cb_w, bottom_widget_h)

        # Status label takes remaining space on the left
        if status_label:
            # Calculate width from left text margin to start of rightmost bottom widget
            status_w = max(0, current_bottom_x - txt_m - retrans_m) # Subtract margin
            status_label.setGeometry(txt_m, bottom_y, status_w, bottom_widget_h)

        # --- Position Text Display Area ---
        text_dsp = self.widgets.get('text_display')
        if text_dsp:
            txt_x = txt_m
            txt_y = top_h
            txt_w = max(config.MIN_WINDOW_WIDTH - (txt_m * 2), window_w - (txt_m * 2))
            # Available height between top controls and bottom status bar area
            available_h = window_h - top_h - status_h - bottom_margin_outer - txt_m
            txt_h = max(config.MIN_WINDOW_HEIGHT - top_h - status_h - bottom_margin_outer - txt_m, available_h)
            text_dsp.setGeometry(txt_x, txt_y, txt_w, txt_h)

    def handle_paint_event(self, event):
        painter = QPainter(self.window)
        painter.setRenderHint(QPainter.Antialiasing)

        # Frame color (e.g., black, fully opaque)
        frame_color = QColor(0, 0, 0, 255)
        text_display = self.widgets.get('text_display')
        text_area_rect = text_display.geometry() if text_display else QRect()
        window_rect = self.window.rect()
        border_radius = 7.0

        # Create rounded rectangle path for the whole window
        full_window_path = QPainterPath()
        full_window_path.addRoundedRect(QRectF(window_rect), border_radius, border_radius)

        # Create rectangle path for the text area (where background should be transparent)
        text_area_path = QPainterPath()
        if text_area_rect.isValid():
            text_area_path.addRect(QRectF(text_area_rect))

        # Subtract text area from the full window to get the frame/background path
        background_path = full_window_path
        if text_area_rect.isValid():
            background_path = full_window_path.subtracted(text_area_path)

        # Draw the frame/background (excluding the text area)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(frame_color))
        painter.drawPath(background_path)

        # --- Draw Optional Border (OCR Active / Locked) ---
        border_pen = QPen()
        border_pen.setWidth(2)
        draw_border = False
        if self._draw_active_border:
            border_pen.setColor(self._active_border_color)
            draw_border = True
        elif self._is_window_locked:
            border_pen.setColor(self.LOCKED_BORDER_COLOR)
            draw_border = True

        # Draw border around the *entire* window if needed
        if draw_border:
            painter.setPen(border_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(full_window_path) # Draw the outline of the full window path

        painter.end()

    # --- Status Methods ---
    def set_status(self, message: str, timeout: int = 0):
        status_label = self.widgets.get('status_label')
        if status_label:
            status_label.setText(message)
            logging.debug(f"Status set: {message}")
            self._status_clear_timer.stop() # Stop previous timer if any
            if timeout > 0:
                self._status_clear_timer.start(timeout)

    def clear_status(self):
        status_label = self.widgets.get('status_label')
        if status_label:
            status_label.setText("")
            logging.debug("Status cleared.")

    # --- OCR/Lock Feedback Methods ---
    def show_ocr_active_feedback(self, color=None):
        self._draw_active_border = True
        self._active_border_color = color if color else self.OCR_ACTIVE_BORDER_COLOR
        self.window.update() # Trigger repaint

    def hide_ocr_active_feedback(self):
        if self._draw_active_border:
            self._draw_active_border = False
            self.window.update() # Trigger repaint

    def set_locked_indicator(self, is_locked: bool):
        if self._is_window_locked != is_locked:
            self._is_window_locked = is_locked
            self.window.update() # Trigger repaint

    # --- Retranslate Control Methods ---
    def get_retranslate_language_code(self) -> str | None:
        combo = self.widgets.get('retranslate_lang_combo')
        return combo.currentData() if combo else None

    def set_retranslate_controls_enabled(self, enabled: bool):
        combo = self.widgets.get('retranslate_lang_combo')
        button = self.widgets.get('retranslate_button')
        aot_checkbox = self.widgets.get('always_on_top_checkbox') # Include this checkbox

        if combo: combo.setEnabled(enabled)
        if button: button.setEnabled(enabled)

    # --- Other UI Update Helpers ---
    def get_widget(self, name: str):
        return self.widgets.get(name)

    def set_grab_button_state(self, enabled: bool, text: str = None, tooltip: str = None):
        grab_button = self.widgets.get('grab_button')
        if grab_button:
            grab_button.setEnabled(enabled)
            if text is not None:
                grab_button.setText(text)
            if tooltip is not None:
                grab_button.setToolTip(tooltip)

    def set_live_mode_checkbox_state(self, checked: bool, enabled: bool, is_active: bool):
        live_cb = self.widgets.get('live_mode_checkbox')
        if live_cb:
            live_cb.blockSignals(True) # Prevent stateChanged signal during update
            live_cb.setChecked(checked)
            live_cb.setEnabled(enabled)
            # Update text and style based on active state
            if is_active:
                live_cb.setText("Live ●")
                active_style = "font-weight: bold; color: #007A00;" # Green and bold when active
                live_cb.setStyleSheet(f"QCheckBox {{ {self._checkbox_style_base} {active_style} }} {self._checkbox_style_indicator} {self._checkbox_style_disabled}")
            else:
                live_cb.setText("Live")
                live_cb.setStyleSheet(f"QCheckBox {{ {self._checkbox_style_base} }} {self._checkbox_style_indicator} {self._checkbox_style_disabled}")
            live_cb.blockSignals(False) # Re-enable signals

    def update_text_display_content(self, html_content: str, alignment=Qt.AlignLeft):
        text_display = self.widgets.get('text_display')
        if text_display:
            text_display.setAlignment(alignment)
            text_display.setHtml(html_content)

    def set_text_display_visibility(self, visible: bool):
        text_display = self.widgets.get('text_display')
        if text_display:
            text_display.setVisible(visible)

    def get_text_display_geometry(self) -> QRect:
         text_display = self.widgets.get('text_display')
         return text_display.geometry() if text_display else QRect()

    def get_button_geometry(self, name: str) -> QRect:
         button = self.widgets.get(name)
         return button.geometry() if button else QRect()