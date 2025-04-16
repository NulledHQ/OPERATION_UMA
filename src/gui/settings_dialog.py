# src/gui/settings_dialog.py
import logging
import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton, QLineEdit,
    QComboBox, QSpinBox, QSlider, QCheckBox, QDialogButtonBox, QFileDialog,
    QFontDialog, QMessageBox, QLabel, QWidget # Added QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

# Use absolute import from src package root
from src import config

class SettingsDialog(QDialog):
    """
    A dialog window for configuring application settings.
    Dynamically shows/hides API key fields based on engine selection.
    """
    def __init__(self, parent=None, current_settings=None):
        """
        Initializes the Settings Dialog.

        Args:
            parent: The parent widget (usually the main window).
            current_settings (dict): A dictionary containing the current values
                                     of the settings to populate the dialog.
        """
        super().__init__(parent)
        self.parent_window = parent # Keep reference to call history methods etc.
        self.current_settings = current_settings if current_settings else {}

        # Work with a copy so changes are only applied on OK
        # Initialize with defaults from config where appropriate
        self.new_settings = {
            'credentials_path': self.current_settings.get('credentials_path'),
            'deepl_api_key': self.current_settings.get('deepl_api_key'),
            'target_language_code': self.current_settings.get('target_language_code', config.DEFAULT_TARGET_LANGUAGE_CODE),
            'translation_engine': self.current_settings.get('translation_engine', config.DEFAULT_TRANSLATION_ENGINE),
            'display_font': self.current_settings.get('display_font', QFont()),
            # Note: bg_color is passed in, but we'll manage bg_alpha separately for the slider
            'bg_alpha': self.current_settings.get('bg_color', QColor(config.DEFAULT_BG_COLOR)).alpha(),
            'ocr_interval': self.current_settings.get('ocr_interval', config.DEFAULT_OCR_INTERVAL_SECONDS),
            'is_locked': self.current_settings.get('is_locked', False),
        }
        # Store the original bg_color object separately if needed for reference
        self.original_bg_color = self.current_settings.get('bg_color', QColor(config.DEFAULT_BG_COLOR))

        self.setWindowTitle("Settings")
        self.setMinimumWidth(450)

        # --- Setup UI Elements ---
        self._setup_widgets()
        self._setup_layout()
        self._connect_signals()
        self._load_initial_settings() # Load data into widgets from self.new_settings
        self._update_engine_specific_visibility() # Show/hide fields based on initial engine

        logging.debug("SettingsDialog initialized.")

    def _setup_widgets(self):
        """Create all the widgets for the dialog."""
        # Google Credentials Section
        self.credentials_label = QLabel("Google Credentials:")
        self.credentials_path_edit = QLineEdit(self); self.credentials_path_edit.setReadOnly(True)
        self.credentials_browse_button = QPushButton("Browse...")
        self.credentials_browse_button.setToolTip(config.TOOLTIP_GOOGLE_CREDENTIALS)

        # Translation Engine Selection
        self.engine_label = QLabel("Translation Engine:")
        self.engine_combo = QComboBox(self); self.engine_combo.setToolTip(config.TOOLTIP_ENGINE_SELECT)
        for key, display_name in config.AVAILABLE_ENGINES.items(): self.engine_combo.addItem(display_name, key)

        # DeepL API Key Section
        self.deepl_key_label = QLabel("DeepL API Key:")
        self.deepl_key_edit = QLineEdit(self); self.deepl_key_edit.setEchoMode(QLineEdit.Password)
        self.deepl_key_edit.setPlaceholderText("Enter DeepL API Key...")
        self.deepl_key_edit.setToolTip(config.TOOLTIP_DEEPL_KEY)
        self.deepl_show_key_button = QPushButton("Show"); self.deepl_show_key_button.setCheckable(True); self.deepl_show_key_button.setFixedWidth(50)

        # Target Language Section
        self.language_label = QLabel("Target Language:")
        self.language_combo = QComboBox(self); self.language_combo.setToolTip("Select translation target language.")
        for display_name, code in config.COMMON_LANGUAGES: self.language_combo.addItem(display_name, code)

        # Appearance Section
        self.font_label = QLabel("Display Font:")
        self.current_font_label = QLabel("..."); self.current_font_label.setToolTip("Current display font.")
        self.font_button = QPushButton("Change Font..."); self.font_button.setToolTip("Select display font.")

        self.bg_alpha_label = QLabel("Background Opacity:")
        self.bg_alpha_slider = QSlider(Qt.Horizontal); self.bg_alpha_slider.setRange(0, 255)
        self.bg_alpha_slider.setToolTip("Adjust background opacity (0=Transparent, 255=Opaque).")
        self.bg_alpha_value_label = QLabel("...") # Displays current alpha value

        # Behavior Section
        self.interval_label = QLabel("Live OCR Interval:")
        self.interval_spinbox = QSpinBox(self); self.interval_spinbox.setRange(1, 300); self.interval_spinbox.setSuffix(" s")
        self.interval_spinbox.setToolTip("Set refresh interval (seconds) for Live Mode.")

        self.lock_checkbox = QCheckBox("Lock Window Position/Size"); self.lock_checkbox.setToolTip("Prevent moving or resizing.")

        # History Section
        self.history_export_button = QPushButton("Export History..."); self.history_export_button.setToolTip("Save history to CSV.")
        self.history_clear_button = QPushButton("Clear History..."); self.history_clear_button.setToolTip("Delete all history.")

        # Dialog Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)


    def _setup_layout(self):
        """Arrange widgets in layouts."""
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout(); form_layout.setRowWrapPolicy(QFormLayout.WrapLongRows); form_layout.setLabelAlignment(Qt.AlignRight)

        # Google Credentials Row
        self.cred_layout = QHBoxLayout(); self.cred_layout.addWidget(self.credentials_path_edit, 1); self.cred_layout.addWidget(self.credentials_browse_button)
        form_layout.addRow(self.credentials_label, self.cred_layout)

        # Engine Row
        form_layout.addRow(self.engine_label, self.engine_combo)

        # DeepL Key Row (using container widget for visibility toggle)
        self.deepl_key_widget = QWidget()
        deepl_inner = QHBoxLayout(self.deepl_key_widget); deepl_inner.setContentsMargins(0,0,0,0); deepl_inner.addWidget(self.deepl_key_edit, 1); deepl_inner.addWidget(self.deepl_show_key_button)
        form_layout.addRow(self.deepl_key_label, self.deepl_key_widget)

        # Language Row
        form_layout.addRow(self.language_label, self.language_combo)

        # Font Row
        font_layout = QHBoxLayout(); font_layout.addWidget(self.current_font_label, 1); font_layout.addWidget(self.font_button)
        form_layout.addRow(self.font_label, font_layout)

        # Alpha Row
        alpha_layout = QHBoxLayout(); alpha_layout.addWidget(self.bg_alpha_slider); alpha_layout.addWidget(self.bg_alpha_value_label)
        self.bg_alpha_value_label.setMinimumWidth(35)
        form_layout.addRow(self.bg_alpha_label, alpha_layout)

        # Interval Row
        form_layout.addRow(self.interval_label, self.interval_spinbox)

        # Add Form and Checkbox
        main_layout.addLayout(form_layout)
        main_layout.addSpacing(15)
        main_layout.addWidget(self.lock_checkbox)
        main_layout.addSpacing(15)

        # History Buttons
        history_layout = QHBoxLayout(); history_layout.addStretch(); history_layout.addWidget(self.history_export_button); history_layout.addWidget(self.history_clear_button)
        main_layout.addLayout(history_layout)

        # Dialog Buttons
        main_layout.addStretch(1)
        main_layout.addWidget(self.button_box)


    def _connect_signals(self):
        """Connect widget signals to methods."""
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.credentials_browse_button.clicked.connect(self._browse_credentials)
        self.engine_combo.currentIndexChanged.connect(self._update_engine)
        self.engine_combo.currentIndexChanged.connect(self._update_engine_specific_visibility)
        self.deepl_key_edit.textChanged.connect(self._update_deepl_key)
        self.deepl_show_key_button.toggled.connect(self._toggle_deepl_key_visibility)
        self.language_combo.currentIndexChanged.connect(self._update_language)
        self.font_button.clicked.connect(self._change_font)
        self.bg_alpha_slider.valueChanged.connect(self._update_alpha)
        self.interval_spinbox.valueChanged.connect(self._update_interval)
        self.lock_checkbox.stateChanged.connect(self._update_lock_status)

        # Connect history buttons to parent window methods (if available)
        if self.parent_window:
            # Check for existence AND callability
            can_export = hasattr(self.parent_window, 'export_history') and callable(self.parent_window.export_history)
            if can_export: self.history_export_button.clicked.connect(self.parent_window.export_history)
            else: self.history_export_button.setEnabled(False); logging.warning("Parent has no 'export_history' method.")

            can_clear = hasattr(self.parent_window, 'clear_history') and callable(self.parent_window.clear_history)
            # We call _confirm_clear_history which then calls parent's clear_history
            if can_clear: self.history_clear_button.clicked.connect(self._confirm_clear_history)
            else: self.history_clear_button.setEnabled(False); logging.warning("Parent has no 'clear_history' method.")
        else: # Disable if no parent context
             self.history_export_button.setEnabled(False)
             self.history_clear_button.setEnabled(False)


    def _load_initial_settings(self):
        """Populate widgets with values from self.new_settings."""
        # Credentials Path
        cred_path = self.new_settings.get('credentials_path', '')
        self.credentials_path_edit.setText(os.path.basename(cred_path) if cred_path else "")
        self.credentials_path_edit.setToolTip(cred_path if cred_path else "No Google credentials file selected.")

        # DeepL API Key
        deepl_key = self.new_settings.get('deepl_api_key', '')
        self.deepl_key_edit.setText(deepl_key)

        # Translation Engine
        current_engine_key = self.new_settings.get('translation_engine', config.DEFAULT_TRANSLATION_ENGINE)
        index = self.engine_combo.findData(current_engine_key)
        self.engine_combo.setCurrentIndex(index if index != -1 else 0)
        # Ensure new_settings has the actual selected key if default was used
        self.new_settings['translation_engine'] = self.engine_combo.currentData()

        # Target Language
        current_lang_code = self.new_settings.get('target_language_code', config.DEFAULT_TARGET_LANGUAGE_CODE)
        index = self.language_combo.findData(current_lang_code)
        self.language_combo.setCurrentIndex(index if index != -1 else 0)
        self.new_settings['target_language_code'] = self.language_combo.currentData()

        # Display Font
        current_font = self.new_settings.get('display_font', QFont())
        if not isinstance(current_font, QFont): current_font = QFont() # Reset if invalid
        self.new_settings['display_font'] = current_font # Ensure working copy has valid font
        self.current_font_label.setText(f"{current_font.family()} {current_font.pointSize()}pt")
        self.current_font_label.setFont(current_font)

        # Background Alpha
        current_alpha = self.new_settings.get('bg_alpha', config.DEFAULT_BG_COLOR.alpha())
        self.bg_alpha_slider.setValue(current_alpha)
        self.bg_alpha_value_label.setText(str(current_alpha))

        # OCR Interval
        current_interval = self.new_settings.get('ocr_interval', config.DEFAULT_OCR_INTERVAL_SECONDS)
        self.interval_spinbox.setValue(current_interval)

        # Lock Status
        current_lock_status = self.new_settings.get('is_locked', False)
        self.lock_checkbox.setChecked(current_lock_status)

        # Update history button enabled state
        self._update_history_button_states()


    def _update_history_button_states(self):
        """Enable/disable history buttons based on history content in parent."""
        history_exists = False
        if (self.parent_window and
            hasattr(self.parent_window, 'history_manager') and
            self.parent_window.history_manager and
            self.parent_window.history_manager.history_deque):
            history_exists = True

        can_export = hasattr(self.parent_window, 'export_history') and callable(self.parent_window.export_history)
        self.history_export_button.setEnabled(can_export and history_exists)

        can_clear = hasattr(self.parent_window, 'clear_history') and callable(self.parent_window.clear_history)
        self.history_clear_button.setEnabled(can_clear and history_exists)


    # --- Widget Action Methods ---

    def _browse_credentials(self):
        """Open file dialog to select Google credentials file."""
        current_path = self.new_settings.get('credentials_path', '')
        directory = os.path.dirname(current_path) if current_path else ''
        filePath, _ = QFileDialog.getOpenFileName(self, "Select Google Cloud Credentials", directory, "JSON files (*.json)")
        if filePath:
            self.new_settings['credentials_path'] = filePath
            self.credentials_path_edit.setText(os.path.basename(filePath))
            self.credentials_path_edit.setToolTip(filePath)
            logging.info(f"Credentials path selected in dialog: {filePath}")

    def _update_engine(self, index):
        """Update selected engine key in new_settings."""
        selected_key = self.engine_combo.itemData(index)
        if selected_key: self.new_settings['translation_engine'] = selected_key
        # Visibility handled by _update_engine_specific_visibility connected to same signal

    def _update_engine_specific_visibility(self):
        """Show/hide engine-specific fields (DeepL key)."""
        selected_key = self.engine_combo.currentData()
        is_deepl = (selected_key == "deepl_free")
        self.deepl_key_label.setVisible(is_deepl)
        self.deepl_key_widget.setVisible(is_deepl) # Toggle container widget

        # Update Google Credentials label context
        if selected_key == "google_cloud_v3": self.credentials_label.setText("Google Credentials:")
        elif selected_key in ["deepl_free", "googletrans"]: self.credentials_label.setText("Google Credentials (for OCR):")
        else: self.credentials_label.setText("Google Credentials:")


    def _update_deepl_key(self, text):
        """Update DeepL API key in new_settings."""
        self.new_settings['deepl_api_key'] = text

    def _toggle_deepl_key_visibility(self, checked):
        """Toggle visibility of the DeepL API key characters."""
        self.deepl_key_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        self.deepl_show_key_button.setText("Hide" if checked else "Show")

    def _update_language(self, index):
        """Update selected language code in new_settings."""
        selected_code = self.language_combo.itemData(index)
        if selected_code: self.new_settings['target_language_code'] = selected_code

    def _change_font(self):
        """Open font dialog and update font settings."""
        current_font = self.new_settings.get('display_font', QFont())
        font, ok = QFontDialog.getFont(current_font, self, "Select Display Font")
        if ok:
             self.new_settings['display_font'] = font
             self.current_font_label.setText(f"{font.family()} {font.pointSize()}pt")
             self.current_font_label.setFont(font)

    def _update_alpha(self, value):
        """Update background alpha value in new_settings and label."""
        self.new_settings['bg_alpha'] = value
        self.bg_alpha_value_label.setText(str(value))

    def _update_interval(self, value):
        """Update OCR interval in new_settings."""
        self.new_settings['ocr_interval'] = value

    def _update_lock_status(self, state):
        """Update lock status in new_settings."""
        self.new_settings['is_locked'] = (state == Qt.Checked)

    def _confirm_clear_history(self):
        """Show confirmation dialog before calling parent's clear_history."""
        if self.parent_window and hasattr(self.parent_window, 'clear_history'):
             # Confirmation is now handled inside parent's clear_history method via HistoryManager
             self.parent_window.clear_history()
             # Update button states after attempting clear
             self._update_history_button_states()


    # --- Get Final Settings ---
    def get_updated_settings(self):
        """Returns the modified settings dict gathered from the widgets."""
        logging.debug(f"Returning updated settings from dialog: {self.new_settings}")
        # The dictionary self.new_settings holds the final state.
        return self.new_settings

    def accept(self):
        """Validate settings before accepting the dialog."""
        # --- Validation ---
        selected_engine = self.new_settings.get('translation_engine')
        cred_path = self.new_settings.get('credentials_path')

        # Validate Google Credentials Path (Warn if set but non-existent)
        if cred_path and not os.path.exists(cred_path):
            QMessageBox.warning(self, "Credentials Invalid", f"The selected Google credentials file does not exist:\n{cred_path}\nOCR/Translation may fail.")
            # Don't block closing, but warn user.

        # Block closing only if DeepL selected and key is missing
        if selected_engine == 'deepl_free' and not self.new_settings.get('deepl_api_key'):
            QMessageBox.warning(self, "API Key Required", "DeepL engine requires an API Key. Please enter one or select a different engine.")
            return # Keep dialog open

        # --- End Validation ---
        super().accept() # Call parent accept if validation passes