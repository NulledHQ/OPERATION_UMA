# Modified src/gui/settings_dialog.py

import logging
import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton, QLineEdit,
    QComboBox, QSpinBox, QSlider, QCheckBox, QDialogButtonBox, QFileDialog,
    QFontDialog, QMessageBox, QLabel, QWidget, QGroupBox # Added QGroupBox
)
from PyQt5.QtCore import Qt, QStandardPaths, pyqtSignal # Added pyqtSignal here
from PyQt5.QtGui import QFont, QColor

# Use absolute import from src package root
# Need to handle potential ImportError if src/config isn't found during isolated execution
try:
    from src import config
    from src.gui.hotkey_edit import HotkeyEdit
except ImportError:
    logging.critical("SettingsDialog: Failed to import config or HotkeyEdit. Using placeholders.")
    # Create fallback config object for basic operation
    class ConfigFallback:
        DEFAULT_OCR_PROVIDER="google_vision"; AVAILABLE_OCR_PROVIDERS={"google_vision":"GV"}
        DEFAULT_OCR_LANGUAGE="eng"; OCR_SPACE_LANGUAGES={"eng":"English"}
        DEFAULT_OCR_SPACE_ENGINE_NUMBER=1; OCR_SPACE_ENGINES={1:"Eng1"}
        DEFAULT_OCR_SPACE_SCALE=False; DEFAULT_OCR_SPACE_DETECT_ORIENTATION=False
        DEFAULT_TESSERACT_CMD_PATH=None; TESSERACT_LANGUAGES={"eng":"English"}; DEFAULT_TESSERACT_LANGUAGE="eng"
        DEFAULT_TRANSLATION_ENGINE="google_cloud_v3"; AVAILABLE_ENGINES={"google_cloud_v3":"GCv3"}
        DEFAULT_TARGET_LANGUAGE_CODE="en"; DEFAULT_FONT_SIZE=18; DEFAULT_BG_COLOR=QColor(0,0,0,150)
        DEFAULT_OCR_INTERVAL_SECONDS=5; DEFAULT_HOTKEY='ctrl+shift+g'; DEFAULT_SAVE_OCR_IMAGES=False; DEFAULT_OCR_IMAGE_SAVE_PATH=None
        COMMON_LANGUAGES=[("English","en")]; TOOLTIP_OCR_PROVIDER_SELECT=""; TOOLTIP_GOOGLE_CREDENTIALS=""
        TOOLTIP_OCRSPACE_KEY=""; TOOLTIP_OCR_LANGUAGE_SELECT=""; TOOLTIP_OCR_SPACE_ENGINE_SELECT=""
        TOOLTIP_OCR_SPACE_SCALE=""; TOOLTIP_OCR_SPACE_DETECT_ORIENTATION=""; TOOLTIP_TESSERACT_CMD_PATH=""
        TOOLTIP_TESSERACT_LANGUAGE_SELECT=""; TOOLTIP_DEEPL_KEY=""; TOOLTIP_ENGINE_SELECT=""
        TOOLTIP_TARGET_LANGUAGE_SELECT=""; TOOLTIP_HOTKEY_INPUT=""; TOOLTIP_SAVE_OCR_IMAGES=""
        TOOLTIP_OCR_IMAGE_SAVE_PATH=""
    config = ConfigFallback()
    # Placeholder for HotkeyEdit if unavailable
    class HotkeyEdit(QLineEdit):
         hotkeyChanged = pyqtSignal(str)
         def __init__(self, parent=None): super().__init__(parent); self.setPlaceholderText("Hotkey Input Unavailable")
         def setHotkey(self, text): self.setText(text)
         def currentHotkey(self): return self.text()

class SettingsDialog(QDialog):
    """Dialog for configuring application settings."""

    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.parent_window = parent
        self.current_settings = current_settings if current_settings else {}

        # Initialize working copy of settings
        self.new_settings = {
            'ocr_provider': self.current_settings.get('ocr_provider', config.DEFAULT_OCR_PROVIDER),
            'google_credentials_path': self.current_settings.get('google_credentials_path'),
            'ocrspace_api_key': self.current_settings.get('ocrspace_api_key'),
            'ocr_language_code': self.current_settings.get('ocr_language_code', config.DEFAULT_OCR_LANGUAGE),
            'ocr_space_engine': self.current_settings.get('ocr_space_engine', config.DEFAULT_OCR_SPACE_ENGINE_NUMBER),
            'ocr_space_scale': self.current_settings.get('ocr_space_scale', config.DEFAULT_OCR_SPACE_SCALE),
            'ocr_space_detect_orientation': self.current_settings.get('ocr_space_detect_orientation', config.DEFAULT_OCR_SPACE_DETECT_ORIENTATION),
            'tesseract_cmd_path': self.current_settings.get('tesseract_cmd_path', config.DEFAULT_TESSERACT_CMD_PATH),
            'tesseract_language_code': self.current_settings.get('tesseract_language_code', config.DEFAULT_TESSERACT_LANGUAGE),
            'deepl_api_key': self.current_settings.get('deepl_api_key'),
            'target_language_code': self.current_settings.get('target_language_code', config.DEFAULT_TARGET_LANGUAGE_CODE),
            'translation_engine_key': self.current_settings.get('translation_engine_key', config.DEFAULT_TRANSLATION_ENGINE),
            'display_font': self.current_settings.get('display_font', QFont()),
            'bg_alpha': self.current_settings.get('bg_color', QColor(config.DEFAULT_BG_COLOR)).alpha(),
            'ocr_interval': self.current_settings.get('ocr_interval', config.DEFAULT_OCR_INTERVAL_SECONDS),
            'is_locked': self.current_settings.get('is_locked', False),
            'hotkey': self.current_settings.get('hotkey', config.DEFAULT_HOTKEY),
            # --- Commented out training data settings ---
            # 'save_ocr_images': self.current_settings.get('save_ocr_images', config.DEFAULT_SAVE_OCR_IMAGES),
            # 'ocr_image_save_path': self.current_settings.get('ocr_image_save_path', config.DEFAULT_OCR_IMAGE_SAVE_PATH),
            # --- End comment out ---
        }
        self.original_bg_color = self.current_settings.get('bg_color', QColor(config.DEFAULT_BG_COLOR))

        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)

        self._setup_widgets()
        self._setup_layout()
        self._connect_signals()
        self._load_initial_settings()
        self._update_provider_specific_visibility()

        logging.debug("SettingsDialog initialized.")

    def _setup_widgets(self):
        # OCR Provider Section
        self.ocr_provider_label = QLabel("OCR Provider:")
        self.ocr_provider_combo = QComboBox(self); self.ocr_provider_combo.setToolTip(config.TOOLTIP_OCR_PROVIDER_SELECT)
        for key, display_name in config.AVAILABLE_OCR_PROVIDERS.items(): self.ocr_provider_combo.addItem(display_name, key)

        # Google Credentials
        self.google_credentials_widget = QWidget(); google_cred_layout = QHBoxLayout(self.google_credentials_widget); google_cred_layout.setContentsMargins(0,0,0,0)
        self.google_credentials_path_edit = QLineEdit(self); self.google_credentials_path_edit.setReadOnly(True); self.google_credentials_browse_button = QPushButton("Browse...")
        self.google_credentials_browse_button.setToolTip(config.TOOLTIP_GOOGLE_CREDENTIALS); google_cred_layout.addWidget(self.google_credentials_path_edit, 1); google_cred_layout.addWidget(self.google_credentials_browse_button)
        self.google_credentials_label = QLabel("Google Credentials:")

        # OCR.space Specific
        self.ocrspace_key_widget = QWidget(); ocrspace_inner = QHBoxLayout(self.ocrspace_key_widget); ocrspace_inner.setContentsMargins(0,0,0,0)
        self.ocrspace_key_edit = QLineEdit(self); self.ocrspace_key_edit.setEchoMode(QLineEdit.Password); self.ocrspace_key_edit.setPlaceholderText("Enter OCR.space API Key..."); self.ocrspace_key_edit.setToolTip(config.TOOLTIP_OCRSPACE_KEY)
        self.ocrspace_show_key_button = QPushButton("Show"); self.ocrspace_show_key_button.setCheckable(True); self.ocrspace_show_key_button.setFixedWidth(50); ocrspace_inner.addWidget(self.ocrspace_key_edit, 1); ocrspace_inner.addWidget(self.ocrspace_show_key_button)
        self.ocrspace_key_label = QLabel("OCR.space API Key:")
        self.ocr_language_label = QLabel("OCR Language (Eng1):"); self.ocr_language_combo = QComboBox(self); self.ocr_language_combo.setToolTip(config.TOOLTIP_OCR_LANGUAGE_SELECT)
        for code, display_name in sorted(config.OCR_SPACE_LANGUAGES.items(), key=lambda item: item[1]): self.ocr_language_combo.addItem(display_name, code)
        self.ocr_space_engine_label = QLabel("OCR.space Engine:"); self.ocr_space_engine_combo = QComboBox(self); self.ocr_space_engine_combo.setToolTip(config.TOOLTIP_OCR_SPACE_ENGINE_SELECT)
        for engine_num, display_name in config.OCR_SPACE_ENGINES.items(): self.ocr_space_engine_combo.addItem(display_name, engine_num)
        self.ocr_space_scale_checkbox = QCheckBox("Enable Upscaling"); self.ocr_space_scale_checkbox.setToolTip(config.TOOLTIP_OCR_SPACE_SCALE)
        self.ocr_space_detect_orientation_checkbox = QCheckBox("Auto-Detect Orientation"); self.ocr_space_detect_orientation_checkbox.setToolTip(config.TOOLTIP_OCR_SPACE_DETECT_ORIENTATION)

        # Tesseract Specific
        self.tesseract_cmd_label = QLabel("Tesseract Path:"); self.tesseract_cmd_widget = QWidget(); tess_cmd_layout = QHBoxLayout(self.tesseract_cmd_widget); tess_cmd_layout.setContentsMargins(0,0,0,0)
        self.tesseract_cmd_path_edit = QLineEdit(self); self.tesseract_cmd_path_edit.setPlaceholderText("Leave blank to use system PATH")
        self.tesseract_cmd_browse_button = QPushButton("Browse..."); self.tesseract_cmd_browse_button.setToolTip(config.TOOLTIP_TESSERACT_CMD_PATH); tess_cmd_layout.addWidget(self.tesseract_cmd_path_edit, 1); tess_cmd_layout.addWidget(self.tesseract_cmd_browse_button)
        self.tesseract_language_label = QLabel("Tesseract Language:"); self.tesseract_language_combo = QComboBox(self); self.tesseract_language_combo.setToolTip(config.TOOLTIP_TESSERACT_LANGUAGE_SELECT)
        for code, display_name in sorted(config.TESSERACT_LANGUAGES.items(), key=lambda item: item[1]): self.tesseract_language_combo.addItem(display_name, code)

        # Translation Engine Section
        self.engine_label = QLabel("Translation Engine:"); self.engine_combo = QComboBox(self); self.engine_combo.setToolTip(config.TOOLTIP_ENGINE_SELECT)
        for key, display_name in config.AVAILABLE_ENGINES.items(): self.engine_combo.addItem(display_name, key)
        self.deepl_key_widget = QWidget(); deepl_inner = QHBoxLayout(self.deepl_key_widget); deepl_inner.setContentsMargins(0,0,0,0)
        self.deepl_key_edit = QLineEdit(self); self.deepl_key_edit.setEchoMode(QLineEdit.Password); self.deepl_key_edit.setPlaceholderText("Enter DeepL API Key..."); self.deepl_key_edit.setToolTip(config.TOOLTIP_DEEPL_KEY)
        self.deepl_show_key_button = QPushButton("Show"); self.deepl_show_key_button.setCheckable(True); self.deepl_show_key_button.setFixedWidth(50); deepl_inner.addWidget(self.deepl_key_edit, 1); deepl_inner.addWidget(self.deepl_show_key_button)
        self.deepl_key_label = QLabel("DeepL API Key:")
        self.language_label = QLabel("Translate To:"); self.language_combo = QComboBox(self); self.language_combo.setToolTip(config.TOOLTIP_TARGET_LANGUAGE_SELECT)
        for display_name, code in config.COMMON_LANGUAGES: self.language_combo.addItem(display_name, code)

        # Common Settings
        self.font_label = QLabel("Display Font:"); self.current_font_label = QLabel("..."); self.current_font_label.setToolTip("Current display font.")
        self.font_button = QPushButton("Change Font..."); self.font_button.setToolTip("Select display font.")
        self.bg_alpha_label = QLabel("Background Opacity:"); self.bg_alpha_slider = QSlider(Qt.Horizontal); self.bg_alpha_slider.setRange(0, 255); self.bg_alpha_slider.setToolTip("Adjust background opacity (0=Transparent, 255=Opaque).")
        self.bg_alpha_value_label = QLabel("..."); self.bg_alpha_value_label.setMinimumWidth(35)
        self.interval_label = QLabel("Live OCR Interval:"); self.interval_spinbox = QSpinBox(self); self.interval_spinbox.setRange(1, 300); self.interval_spinbox.setSuffix(" s"); self.interval_spinbox.setToolTip("Set refresh interval (seconds) for Live Mode.")
        self.hotkey_label = QLabel("Capture Hotkey:"); self.hotkey_edit = HotkeyEdit(parent=self); self.hotkey_edit.setToolTip(config.TOOLTIP_HOTKEY_INPUT)
        self.lock_checkbox = QCheckBox("Lock Window Position/Size"); self.lock_checkbox.setToolTip("Prevent moving or resizing.")

        # --- Commented out training data widget creation ---
        # self.save_images_groupbox = QGroupBox("Save Images for Training"); self.save_images_groupbox.setCheckable(True); self.save_images_groupbox.setToolTip(config.TOOLTIP_SAVE_OCR_IMAGES)
        # save_images_layout = QFormLayout(self.save_images_groupbox)
        # self.save_path_widget = QWidget(); save_path_hbox = QHBoxLayout(self.save_path_widget); save_path_hbox.setContentsMargins(0,0,0,0)
        # self.save_path_edit = QLineEdit(); self.save_path_edit.setPlaceholderText("Select directory..."); self.save_path_edit.setReadOnly(True)
        # self.save_path_browse_button = QPushButton("Browse..."); self.save_path_browse_button.setToolTip(config.TOOLTIP_OCR_IMAGE_SAVE_PATH)
        # save_path_hbox.addWidget(self.save_path_edit, 1); save_path_hbox.addWidget(self.save_path_browse_button)
        # save_images_layout.addRow(QLabel("Save Location:"), self.save_path_widget)
        # --- End comment out ---

        # History Buttons
        self.history_export_button = QPushButton("Export History..."); self.history_export_button.setToolTip("Save history to CSV.")
        self.history_clear_button = QPushButton("Clear History..."); self.history_clear_button.setToolTip("Delete all history.")
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

    def _setup_layout(self):
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setRowWrapPolicy(QFormLayout.WrapLongRows)
        form_layout.setLabelAlignment(Qt.AlignRight)

        # Add rows in logical order
        form_layout.addRow(self.ocr_provider_label, self.ocr_provider_combo)
        form_layout.addRow(self.google_credentials_label, self.google_credentials_widget)
        form_layout.addRow(self.ocrspace_key_label, self.ocrspace_key_widget)
        form_layout.addRow(self.ocr_space_engine_label, self.ocr_space_engine_combo)
        form_layout.addRow(self.ocr_language_label, self.ocr_language_combo)
        form_layout.addRow("", self.ocr_space_scale_checkbox) # No label for checkboxes
        form_layout.addRow("", self.ocr_space_detect_orientation_checkbox)
        form_layout.addRow(self.tesseract_cmd_label, self.tesseract_cmd_widget)
        form_layout.addRow(self.tesseract_language_label, self.tesseract_language_combo)

        form_layout.addRow(self.engine_label, self.engine_combo)
        form_layout.addRow(self.deepl_key_label, self.deepl_key_widget)
        form_layout.addRow(self.language_label, self.language_combo)

        font_layout = QHBoxLayout(); font_layout.addWidget(self.current_font_label, 1); font_layout.addWidget(self.font_button)
        form_layout.addRow(self.font_label, font_layout)
        alpha_layout = QHBoxLayout(); alpha_layout.addWidget(self.bg_alpha_slider); alpha_layout.addWidget(self.bg_alpha_value_label)
        form_layout.addRow(self.bg_alpha_label, alpha_layout)
        form_layout.addRow(self.interval_label, self.interval_spinbox)
        form_layout.addRow(self.hotkey_label, self.hotkey_edit)

        main_layout.addLayout(form_layout)
        main_layout.addSpacing(10)
        main_layout.addWidget(self.lock_checkbox)
        main_layout.addSpacing(10)
        # --- Commented out adding training groupbox ---
        # main_layout.addWidget(self.save_images_groupbox) # Add training groupbox
        # main_layout.addSpacing(15)
        # --- End comment out ---

        history_layout = QHBoxLayout(); history_layout.addStretch(); history_layout.addWidget(self.history_export_button); history_layout.addWidget(self.history_clear_button)
        main_layout.addLayout(history_layout)
        main_layout.addStretch(1)
        main_layout.addWidget(self.button_box)

    def _connect_signals(self):
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        # OCR Providers
        self.ocr_provider_combo.currentIndexChanged.connect(self._update_ocr_provider)
        self.ocr_provider_combo.currentIndexChanged.connect(self._update_provider_specific_visibility)
        self.google_credentials_browse_button.clicked.connect(self._browse_google_credentials)
        self.ocrspace_key_edit.textChanged.connect(self._update_ocrspace_key)
        self.ocrspace_show_key_button.toggled.connect(self._toggle_ocrspace_key_visibility)
        self.ocr_space_engine_combo.currentIndexChanged.connect(self._update_ocr_space_engine)
        self.ocr_language_combo.currentIndexChanged.connect(self._update_ocr_language)
        self.ocr_space_scale_checkbox.stateChanged.connect(self._update_ocr_space_scale)
        self.ocr_space_detect_orientation_checkbox.stateChanged.connect(self._update_ocr_space_detect_orientation)
        self.tesseract_cmd_browse_button.clicked.connect(self._browse_tesseract_cmd)
        self.tesseract_cmd_path_edit.textChanged.connect(self._update_tesseract_cmd_path)
        self.tesseract_language_combo.currentIndexChanged.connect(self._update_tesseract_language)
        # Translation Engines
        self.engine_combo.currentIndexChanged.connect(self._update_translation_engine)
        self.engine_combo.currentIndexChanged.connect(self._update_provider_specific_visibility)
        self.deepl_key_edit.textChanged.connect(self._update_deepl_key)
        self.deepl_show_key_button.toggled.connect(self._toggle_deepl_key_visibility)
        self.language_combo.currentIndexChanged.connect(self._update_target_language) # Renamed slot
        # Common
        self.font_button.clicked.connect(self._change_font)
        self.bg_alpha_slider.valueChanged.connect(self._update_alpha)
        self.interval_spinbox.valueChanged.connect(self._update_interval)
        self.hotkey_edit.hotkeyChanged.connect(self._update_hotkey)
        self.lock_checkbox.stateChanged.connect(self._update_lock_status)
        # --- Commented out training data signal connections ---
        # if hasattr(self, 'save_images_groupbox'): # Check if attribute exists before connecting
        #     self.save_images_groupbox.toggled.connect(self._update_save_images_flag)
        #     self.save_path_browse_button.clicked.connect(self._browse_save_path)
        # --- End comment out ---
        # History
        if self.parent_window:
            if hasattr(self.parent_window, 'export_history'): self.history_export_button.clicked.connect(self.parent_window.export_history)
            else: self.history_export_button.setEnabled(False)
            if hasattr(self.parent_window, 'clear_history'): self.history_clear_button.clicked.connect(self._confirm_clear_history)
            else: self.history_clear_button.setEnabled(False)
        else: self.history_export_button.setEnabled(False); self.history_clear_button.setEnabled(False)

    def _load_initial_settings(self):
        # OCR Provider
        current_ocr_provider = self.new_settings.get('ocr_provider')
        idx = self.ocr_provider_combo.findData(current_ocr_provider)
        self.ocr_provider_combo.setCurrentIndex(idx if idx != -1 else 0)
        self.new_settings['ocr_provider'] = self.ocr_provider_combo.currentData()

        # Google Credentials
        cred_path = self.new_settings.get('google_credentials_path', '')
        self.google_credentials_path_edit.setText(os.path.basename(cred_path) if cred_path else "")
        self.google_credentials_path_edit.setToolTip(cred_path or "No file selected.")

        # OCR.space
        self.ocrspace_key_edit.setText(self.new_settings.get('ocrspace_api_key', ''))
        idx = self.ocr_space_engine_combo.findData(self.new_settings.get('ocr_space_engine'))
        self.ocr_space_engine_combo.setCurrentIndex(idx if idx != -1 else 0)
        self.new_settings['ocr_space_engine'] = self.ocr_space_engine_combo.currentData()
        idx = self.ocr_language_combo.findData(self.new_settings.get('ocr_language_code'))
        self.ocr_language_combo.setCurrentIndex(idx if idx != -1 else 0)
        self.new_settings['ocr_language_code'] = self.ocr_language_combo.currentData()
        self.ocr_space_scale_checkbox.setChecked(self.new_settings.get('ocr_space_scale', False))
        self.ocr_space_detect_orientation_checkbox.setChecked(self.new_settings.get('ocr_space_detect_orientation', False))

        # Tesseract
        tess_cmd_path = self.new_settings.get('tesseract_cmd_path')
        self.tesseract_cmd_path_edit.setText(tess_cmd_path or "")
        self.tesseract_cmd_path_edit.setToolTip(tess_cmd_path or config.TOOLTIP_TESSERACT_CMD_PATH)
        idx = self.tesseract_language_combo.findData(self.new_settings.get('tesseract_language_code'))
        self.tesseract_language_combo.setCurrentIndex(idx if idx != -1 else 0)
        self.new_settings['tesseract_language_code'] = self.tesseract_language_combo.currentData()

        # Translation
        self.deepl_key_edit.setText(self.new_settings.get('deepl_api_key', ''))
        idx = self.engine_combo.findData(self.new_settings.get('translation_engine_key'))
        self.engine_combo.setCurrentIndex(idx if idx != -1 else 0)
        self.new_settings['translation_engine_key'] = self.engine_combo.currentData() # Ensure key is stored
        idx = self.language_combo.findData(self.new_settings.get('target_language_code'))
        self.language_combo.setCurrentIndex(idx if idx != -1 else 0)
        self.new_settings['target_language_code'] = self.language_combo.currentData()

        # Common UI
        current_font = self.new_settings.get('display_font', QFont())
        self.new_settings['display_font'] = current_font if isinstance(current_font, QFont) else QFont()
        self.current_font_label.setText(f"{current_font.family()} {current_font.pointSize()}pt")
        self.current_font_label.setFont(current_font)

        current_alpha = self.new_settings.get('bg_alpha', 150)
        self.bg_alpha_slider.setValue(current_alpha if isinstance(current_alpha, int) else 150)
        self.bg_alpha_value_label.setText(str(self.bg_alpha_slider.value()))

        current_interval = self.new_settings.get('ocr_interval', 5)
        self.interval_spinbox.setValue(current_interval if isinstance(current_interval, int) else 5)

        self.lock_checkbox.setChecked(self.new_settings.get('is_locked', False))

        current_hotkey = self.new_settings.get('hotkey', config.DEFAULT_HOTKEY)
        self.hotkey_edit.setHotkey(current_hotkey if isinstance(current_hotkey, str) else config.DEFAULT_HOTKEY)

        # --- Commented out training data loading ---
        # if hasattr(self, 'save_images_groupbox'): # Check if attribute exists
        #     save_enabled = self.new_settings.get('save_ocr_images', False)
        #     self.save_images_groupbox.setChecked(save_enabled)
        #     save_path = self.new_settings.get('ocr_image_save_path')
        #     self.save_path_edit.setText(save_path or "")
        #     self.save_path_edit.setToolTip(save_path or "No directory selected.")
        #     self.save_path_widget.setEnabled(save_enabled) # Enable/disable path selector
        # --- End comment out ---

        self._update_history_button_states()
        self._update_provider_specific_visibility() # Call last

    def _update_history_button_states(self):
        """Enable/disable history buttons based on parent's history."""
        history_exists = bool(self.parent_window and hasattr(self.parent_window, 'history_manager') and self.parent_window.history_manager.history_deque)
        can_export = hasattr(self.parent_window, 'export_history')
        can_clear = hasattr(self.parent_window, 'clear_history')
        self.history_export_button.setEnabled(can_export and history_exists)
        self.history_clear_button.setEnabled(can_clear and history_exists)

    # --- Action Methods / Slots ---
    def _browse_google_credentials(self):
        current_path = self.new_settings.get('google_credentials_path', '')
        directory = os.path.dirname(current_path) if current_path else QStandardPaths.writableLocation(QStandardPaths.HomeLocation)
        filePath, _ = QFileDialog.getOpenFileName(self, "Select Google Cloud Credentials", directory, "JSON files (*.json)")
        if filePath: self.new_settings['google_credentials_path'] = filePath; self.google_credentials_path_edit.setText(os.path.basename(filePath)); self.google_credentials_path_edit.setToolTip(filePath)

    def _update_ocr_provider(self, index): self.new_settings['ocr_provider'] = self.ocr_provider_combo.itemData(index)
    def _update_ocrspace_key(self, text): self.new_settings['ocrspace_api_key'] = text
    def _toggle_ocrspace_key_visibility(self, checked): self.ocrspace_key_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password); self.ocrspace_show_key_button.setText("Hide" if checked else "Show")
    def _update_ocr_space_engine(self, index): self.new_settings['ocr_space_engine'] = self.ocr_space_engine_combo.itemData(index)
    def _update_ocr_language(self, index): self.new_settings['ocr_language_code'] = self.ocr_language_combo.itemData(index)
    def _update_ocr_space_scale(self, state): self.new_settings['ocr_space_scale'] = (state == Qt.Checked)
    def _update_ocr_space_detect_orientation(self, state): self.new_settings['ocr_space_detect_orientation'] = (state == Qt.Checked)

    def _browse_tesseract_cmd(self):
        current_path = self.new_settings.get('tesseract_cmd_path', '')
        directory = os.path.dirname(current_path) if current_path else QStandardPaths.writableLocation(QStandardPaths.HomeLocation)
        filters = "Executables (*.exe)" if os.name == 'nt' else "All Files (*)"
        filePath, _ = QFileDialog.getOpenFileName(self, "Select Tesseract Executable", directory, filters)
        if filePath: self.new_settings['tesseract_cmd_path'] = filePath; self.tesseract_cmd_path_edit.setText(filePath); self.tesseract_cmd_path_edit.setToolTip(filePath)
    def _update_tesseract_cmd_path(self, text): self.new_settings['tesseract_cmd_path'] = text if text else None
    def _update_tesseract_language(self, index): self.new_settings['tesseract_language_code'] = self.tesseract_language_combo.itemData(index)

    def _update_translation_engine(self, index): self.new_settings['translation_engine_key'] = self.engine_combo.itemData(index)
    def _update_deepl_key(self, text): self.new_settings['deepl_api_key'] = text
    def _toggle_deepl_key_visibility(self, checked): self.deepl_key_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password); self.deepl_show_key_button.setText("Hide" if checked else "Show")
    def _update_target_language(self, index): self.new_settings['target_language_code'] = self.language_combo.itemData(index) # Renamed slot

    def _change_font(self):
        current_font = self.new_settings.get('display_font', QFont())
        font, ok = QFontDialog.getFont(current_font if isinstance(current_font, QFont) else QFont(), self, "Select Font")
        if ok: self.new_settings['display_font'] = font; self.current_font_label.setText(f"{font.family()} {font.pointSize()}pt"); self.current_font_label.setFont(font)
    def _update_alpha(self, value): self.new_settings['bg_alpha'] = value; self.bg_alpha_value_label.setText(str(value))
    def _update_interval(self, value): self.new_settings['ocr_interval'] = value
    def _update_hotkey(self, hotkey_str): self.new_settings['hotkey'] = hotkey_str; logging.debug(f"Hotkey updated in dialog: {hotkey_str}")
    def _update_lock_status(self, state): self.new_settings['is_locked'] = (state == Qt.Checked)

    # --- Commented out training data update/browse methods ---
    # def _update_save_images_flag(self, checked):
    #     self.new_settings['save_ocr_images'] = checked
    #     self.save_path_widget.setEnabled(checked)
    #     if checked and not self.new_settings.get('ocr_image_save_path'):
    #         self._browse_save_path() # Prompt for path if enabling and path is empty
    # def _browse_save_path(self):
    #     current_path = self.new_settings.get('ocr_image_save_path')
    #     start_dir = current_path if current_path and os.path.isdir(current_path) else QStandardPaths.writableLocation(QStandardPaths.PicturesLocation)
    #     dir_path = QFileDialog.getExistingDirectory(self, "Select Directory to Save Images", start_dir)
    #     if dir_path:
    #         self.new_settings['ocr_image_save_path'] = dir_path
    #         self.save_path_edit.setText(dir_path)
    #         self.save_path_edit.setToolTip(dir_path)
    #         if not self.save_images_groupbox.isChecked(): # Auto-check if path selected
    #             self.save_images_groupbox.setChecked(True)
    # --- End comment out ---

    def _confirm_clear_history(self):
        if self.parent_window and hasattr(self.parent_window, 'clear_history'):
             self.parent_window.clear_history()
             self._update_history_button_states()

    def _update_provider_specific_visibility(self):
        selected_ocr_key = self.ocr_provider_combo.currentData()
        selected_trans_key = self.engine_combo.currentData()
        is_google_vision = (selected_ocr_key == "google_vision")
        is_ocr_space = (selected_ocr_key == "ocr_space")
        is_tesseract = (selected_ocr_key == "tesseract")
        is_deepl = (selected_trans_key == "deepl_free")
        is_google_cloud_trans = (selected_trans_key == "google_cloud_v3")

        # Default hide all specific sections
        for w in [self.google_credentials_label, self.google_credentials_widget,
                  self.ocrspace_key_label, self.ocrspace_key_widget,
                  self.ocr_space_engine_label, self.ocr_space_engine_combo,
                  self.ocr_language_label, self.ocr_language_combo,
                  self.ocr_space_scale_checkbox, self.ocr_space_detect_orientation_checkbox,
                  self.tesseract_cmd_label, self.tesseract_cmd_widget,
                  self.tesseract_language_label, self.tesseract_language_combo,
                  self.deepl_key_label, self.deepl_key_widget]:
            w.setVisible(False)

        # Set tooltips and visibility based on OCR provider
        if is_google_vision:
            self.ocr_provider_combo.setToolTip(config.TOOLTIP_OCR_PROVIDER_SELECT + "\nRequires Google Credentials.")
            self.google_credentials_label.setVisible(True); self.google_credentials_widget.setVisible(True)
        elif is_ocr_space:
            self.ocr_provider_combo.setToolTip("OCR.space: Cloud OCR. Configure API key, language, engine.")
            self.ocrspace_key_label.setVisible(True); self.ocrspace_key_widget.setVisible(True)
            self.ocr_space_engine_label.setVisible(True); self.ocr_space_engine_combo.setVisible(True)
            self.ocr_language_label.setVisible(True); self.ocr_language_combo.setVisible(True)
            self.ocr_space_scale_checkbox.setVisible(True); self.ocr_space_detect_orientation_checkbox.setVisible(True)
        elif is_tesseract:
            self.ocr_provider_combo.setToolTip("Tesseract: Local OCR. Configure path (optional) & language.")
            self.tesseract_cmd_label.setVisible(True); self.tesseract_cmd_widget.setVisible(True)
            self.tesseract_language_label.setVisible(True); self.tesseract_language_combo.setVisible(True)
        else:
            self.ocr_provider_combo.setToolTip(config.TOOLTIP_OCR_PROVIDER_SELECT)

        # Set visibility based on Translation engine
        if is_deepl:
            self.deepl_key_label.setVisible(True); self.deepl_key_widget.setVisible(True)
        elif is_google_cloud_trans:
            self.google_credentials_label.setVisible(True); self.google_credentials_widget.setVisible(True) # Ensure visible

        # Adjust Google label if needed by both
        google_needed_for_ocr = is_google_vision; google_needed_for_trans = is_google_cloud_trans
        if google_needed_for_ocr and google_needed_for_trans: self.google_credentials_label.setText("Google Credentials (OCR & Translate):")
        elif google_needed_for_ocr: self.google_credentials_label.setText("Google Credentials (for OCR):")
        elif google_needed_for_trans: self.google_credentials_label.setText("Google Credentials (for Translate):")

    def get_updated_settings(self):
        """Returns the modified settings dict gathered from the widgets."""
        # Ensure correct types before returning
        self.new_settings['ocr_space_scale'] = bool(self.ocr_space_scale_checkbox.isChecked())
        self.new_settings['ocr_space_detect_orientation'] = bool(self.ocr_space_detect_orientation_checkbox.isChecked())
        selected_engine_data = self.ocr_space_engine_combo.currentData()
        self.new_settings['ocr_space_engine'] = int(selected_engine_data) if selected_engine_data is not None else config.DEFAULT_OCR_SPACE_ENGINE_NUMBER
        self.new_settings['is_locked'] = bool(self.lock_checkbox.isChecked())
        if self.new_settings.get('tesseract_cmd_path') == "": self.new_settings['tesseract_cmd_path'] = None

        # --- Commented out retrieving training data settings ---
        # self.new_settings['save_ocr_images'] = bool(self.save_images_groupbox.isChecked())
        # self.new_settings['ocr_image_save_path'] = self.save_path_edit.text() if self.new_settings.get('save_ocr_images') and self.save_path_edit.text() else None
        # --- End comment out ---

        # Map translation engine key consistently
        if 'translation_engine' in self.new_settings: # Remove temporary key if it exists
            self.new_settings.pop('translation_engine')

        # Ensure the correct key from the combo is stored
        self.new_settings['translation_engine_key'] = self.engine_combo.currentData()

        logging.debug(f"Returning updated settings from dialog: {self.new_settings}")
        return self.new_settings

    def accept(self):
        """Validate settings before accepting the dialog."""
        selected_ocr = self.new_settings.get('ocr_provider')
        selected_trans = self.new_settings.get('translation_engine_key') # Use the correct key
        google_cred_path = self.new_settings.get('google_credentials_path')

        google_needed = selected_ocr == 'google_vision' or selected_trans == 'google_cloud_v3'
        if google_needed and not google_cred_path:
            QMessageBox.warning(self, "Credentials Required", "Google Credentials required."); return
        if google_needed and google_cred_path and not os.path.exists(google_cred_path):
            QMessageBox.warning(self, "Credentials Invalid", f"Google credentials file not found:\n{google_cred_path}") # Warn only

        if selected_ocr == 'ocr_space' and not self.new_settings.get('ocrspace_api_key'):
            QMessageBox.warning(self, "API Key Required", "OCR.space requires an API Key."); return

        if selected_ocr == 'tesseract':
             tess_path = self.new_settings.get('tesseract_cmd_path')
             if tess_path and not os.path.exists(tess_path):
                  QMessageBox.warning(self, "Tesseract Path Invalid", f"Tesseract path does not exist:\n{tess_path}") # Warn only

        if selected_trans == 'deepl_free' and not self.new_settings.get('deepl_api_key'):
            QMessageBox.warning(self, "API Key Required", "DeepL engine requires an API Key."); return

        if not self.new_settings.get('hotkey'):
            QMessageBox.warning(self, "Hotkey Required", "Please set a capture hotkey."); return

        # --- Commented out training data path validation ---
        # if self.new_settings.get('save_ocr_images'):
        #     save_path = self.new_settings.get('ocr_image_save_path')
        #     if not save_path:
        #         QMessageBox.warning(self, "Save Path Required", "Please select a directory to save images, or disable image saving."); return
        #     if not os.path.isdir(save_path):
        #         try: # Attempt to create directory
        #             os.makedirs(save_path, exist_ok=True)
        #             logging.info(f"Created image save directory: {save_path}")
        #         except OSError as e:
        #             QMessageBox.warning(self, "Save Path Invalid", f"Could not create save directory:\n{save_path}\nError: {e}"); return
        # --- End comment out ---

        super().accept()