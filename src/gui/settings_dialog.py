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
    Dynamically shows/hides API key/credential fields based on provider/engine selection.
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
            'ocr_provider': self.current_settings.get('ocr_provider', config.DEFAULT_OCR_PROVIDER),
            'google_credentials_path': self.current_settings.get('google_credentials_path'),
            'ocrspace_api_key': self.current_settings.get('ocrspace_api_key'),
            'ocr_language_code': self.current_settings.get('ocr_language_code', config.DEFAULT_OCR_LANGUAGE), # <<< OCR LANG
            'deepl_api_key': self.current_settings.get('deepl_api_key'),
            'target_language_code': self.current_settings.get('target_language_code', config.DEFAULT_TARGET_LANGUAGE_CODE), # Target for Translation
            'translation_engine': self.current_settings.get('translation_engine', config.DEFAULT_TRANSLATION_ENGINE),
            'display_font': self.current_settings.get('display_font', QFont()),
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
        self._update_provider_specific_visibility() # Show/hide fields based on initial provider/engine

        logging.debug("SettingsDialog initialized.")

    def _setup_widgets(self):
        """Create all the widgets for the dialog."""
        # --- OCR Provider Section ---
        self.ocr_provider_label = QLabel("OCR Provider:")
        self.ocr_provider_combo = QComboBox(self); self.ocr_provider_combo.setToolTip(config.TOOLTIP_OCR_PROVIDER_SELECT)
        for key, display_name in config.AVAILABLE_OCR_PROVIDERS.items(): self.ocr_provider_combo.addItem(display_name, key)

        # OCR Language Selection (Specific to OCR.space)
        self.ocr_language_label = QLabel("OCR Language:") # <<< NEW
        self.ocr_language_combo = QComboBox(self) # <<< NEW
        self.ocr_language_combo.setToolTip(config.TOOLTIP_OCR_LANGUAGE_SELECT)
        # Populate with OCR.space languages {code: name}
        for code, display_name in sorted(config.OCR_SPACE_LANGUAGES.items(), key=lambda item: item[1]): # Sort by name
            self.ocr_language_combo.addItem(display_name, code) # Display name, store code

        # Google Credentials Widget (for Google Vision)
        self.google_credentials_widget = QWidget()
        google_cred_layout = QHBoxLayout(self.google_credentials_widget); google_cred_layout.setContentsMargins(0,0,0,0)
        self.google_credentials_path_edit = QLineEdit(self); self.google_credentials_path_edit.setReadOnly(True)
        self.google_credentials_browse_button = QPushButton("Browse...")
        self.google_credentials_browse_button.setToolTip(config.TOOLTIP_GOOGLE_CREDENTIALS)
        google_cred_layout.addWidget(self.google_credentials_path_edit, 1)
        google_cred_layout.addWidget(self.google_credentials_browse_button)
        self.google_credentials_label = QLabel("Google Credentials:") # Label associated with this widget

        # OCR.space API Key Widget
        self.ocrspace_key_widget = QWidget()
        ocrspace_inner = QHBoxLayout(self.ocrspace_key_widget); ocrspace_inner.setContentsMargins(0,0,0,0)
        self.ocrspace_key_edit = QLineEdit(self); self.ocrspace_key_edit.setEchoMode(QLineEdit.Password)
        self.ocrspace_key_edit.setPlaceholderText("Enter OCR.space API Key...")
        self.ocrspace_key_edit.setToolTip(config.TOOLTIP_OCRSPACE_KEY)
        self.ocrspace_show_key_button = QPushButton("Show"); self.ocrspace_show_key_button.setCheckable(True); self.ocrspace_show_key_button.setFixedWidth(50)
        ocrspace_inner.addWidget(self.ocrspace_key_edit, 1)
        ocrspace_inner.addWidget(self.ocrspace_show_key_button)
        self.ocrspace_key_label = QLabel("OCR.space API Key:") # Label associated with this widget

        # --- Translation Engine Section ---
        self.engine_label = QLabel("Translation Engine:")
        self.engine_combo = QComboBox(self); self.engine_combo.setToolTip(config.TOOLTIP_ENGINE_SELECT)
        for key, display_name in config.AVAILABLE_ENGINES.items(): self.engine_combo.addItem(display_name, key)

        # DeepL API Key Widget (for DeepL Translation)
        self.deepl_key_widget = QWidget()
        deepl_inner = QHBoxLayout(self.deepl_key_widget); deepl_inner.setContentsMargins(0,0,0,0)
        self.deepl_key_edit = QLineEdit(self); self.deepl_key_edit.setEchoMode(QLineEdit.Password)
        self.deepl_key_edit.setPlaceholderText("Enter DeepL API Key...")
        self.deepl_key_edit.setToolTip(config.TOOLTIP_DEEPL_KEY)
        self.deepl_show_key_button = QPushButton("Show"); self.deepl_show_key_button.setCheckable(True); self.deepl_show_key_button.setFixedWidth(50)
        deepl_inner.addWidget(self.deepl_key_edit, 1)
        deepl_inner.addWidget(self.deepl_show_key_button)
        self.deepl_key_label = QLabel("DeepL API Key:") # Label associated with this widget

        # --- Common Settings ---
        # Target Language Section (for Translation)
        self.language_label = QLabel("Translate To:") # Changed label for clarity
        self.language_combo = QComboBox(self); self.language_combo.setToolTip(config.TOOLTIP_TARGET_LANGUAGE_SELECT) # Updated tooltip
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

        # --- OCR Provider Rows ---
        form_layout.addRow(self.ocr_provider_label, self.ocr_provider_combo)
        form_layout.addRow(self.ocr_language_label, self.ocr_language_combo) # <<< ADD OCR LANG ROW
        form_layout.addRow(self.google_credentials_label, self.google_credentials_widget) # Google Credentials Row
        form_layout.addRow(self.ocrspace_key_label, self.ocrspace_key_widget) # OCR.space Key Row

        # --- Translation Rows ---
        form_layout.addRow(self.engine_label, self.engine_combo) # Engine Row
        form_layout.addRow(self.deepl_key_label, self.deepl_key_widget) # DeepL Key Row
        form_layout.addRow(self.language_label, self.language_combo) # TRANSLATE TO Language Row

        # --- Common Rows ---
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

        # OCR Provider Signals
        self.ocr_provider_combo.currentIndexChanged.connect(self._update_ocr_provider)
        self.ocr_provider_combo.currentIndexChanged.connect(self._update_provider_specific_visibility) # Visibility update
        self.ocr_language_combo.currentIndexChanged.connect(self._update_ocr_language) # <<< CONNECT OCR LANG
        self.google_credentials_browse_button.clicked.connect(self._browse_google_credentials)
        self.ocrspace_key_edit.textChanged.connect(self._update_ocrspace_key)
        self.ocrspace_show_key_button.toggled.connect(self._toggle_ocrspace_key_visibility)

        # Translation Engine Signals
        self.engine_combo.currentIndexChanged.connect(self._update_translation_engine)
        self.engine_combo.currentIndexChanged.connect(self._update_provider_specific_visibility) # Visibility update
        self.deepl_key_edit.textChanged.connect(self._update_deepl_key)
        self.deepl_show_key_button.toggled.connect(self._toggle_deepl_key_visibility)

        # Common Signals
        self.language_combo.currentIndexChanged.connect(self._update_language) # Updates TRANSLATION target lang
        self.font_button.clicked.connect(self._change_font)
        self.bg_alpha_slider.valueChanged.connect(self._update_alpha)
        self.interval_spinbox.valueChanged.connect(self._update_interval)
        self.lock_checkbox.stateChanged.connect(self._update_lock_status)

        # Connect history buttons to parent window methods (if available)
        if self.parent_window:
            can_export = hasattr(self.parent_window, 'export_history') and callable(self.parent_window.export_history)
            if can_export: self.history_export_button.clicked.connect(self.parent_window.export_history)
            else: self.history_export_button.setEnabled(False); logging.warning("Parent has no 'export_history' method.")

            can_clear = hasattr(self.parent_window, 'clear_history') and callable(self.parent_window.clear_history)
            if can_clear: self.history_clear_button.clicked.connect(self._confirm_clear_history)
            else: self.history_clear_button.setEnabled(False); logging.warning("Parent has no 'clear_history' method.")
        else:
             self.history_export_button.setEnabled(False)
             self.history_clear_button.setEnabled(False)


    def _load_initial_settings(self):
        """Populate widgets with values from self.new_settings."""
        # OCR Provider
        current_ocr_provider = self.new_settings.get('ocr_provider', config.DEFAULT_OCR_PROVIDER)
        ocr_index = self.ocr_provider_combo.findData(current_ocr_provider)
        self.ocr_provider_combo.setCurrentIndex(ocr_index if ocr_index != -1 else 0)
        self.new_settings['ocr_provider'] = self.ocr_provider_combo.currentData() # Ensure actual selected key

        # OCR Language
        current_ocr_lang_code = self.new_settings.get('ocr_language_code', config.DEFAULT_OCR_LANGUAGE) # <<< LOAD OCR LANG
        ocr_lang_index = self.ocr_language_combo.findData(current_ocr_lang_code)
        self.ocr_language_combo.setCurrentIndex(ocr_lang_index if ocr_lang_index != -1 else 0)
        self.new_settings['ocr_language_code'] = self.ocr_language_combo.currentData()

        # Google Credentials Path
        cred_path = self.new_settings.get('google_credentials_path', '')
        self.google_credentials_path_edit.setText(os.path.basename(cred_path) if cred_path else "")
        self.google_credentials_path_edit.setToolTip(cred_path if cred_path else "No Google credentials file selected.")

        # OCR.space API Key
        ocrspace_key = self.new_settings.get('ocrspace_api_key', '')
        self.ocrspace_key_edit.setText(ocrspace_key)

        # DeepL API Key
        deepl_key = self.new_settings.get('deepl_api_key', '')
        self.deepl_key_edit.setText(deepl_key)

        # Translation Engine
        current_engine_key = self.new_settings.get('translation_engine', config.DEFAULT_TRANSLATION_ENGINE)
        engine_index = self.engine_combo.findData(current_engine_key)
        self.engine_combo.setCurrentIndex(engine_index if engine_index != -1 else 0)
        self.new_settings['translation_engine'] = self.engine_combo.currentData()

        # Target Language (Translation)
        current_target_lang_code = self.new_settings.get('target_language_code', config.DEFAULT_TARGET_LANGUAGE_CODE)
        target_lang_index = self.language_combo.findData(current_target_lang_code)
        self.language_combo.setCurrentIndex(target_lang_index if target_lang_index != -1 else 0)
        self.new_settings['target_language_code'] = self.language_combo.currentData()

        # Display Font
        current_font = self.new_settings.get('display_font', QFont())
        if not isinstance(current_font, QFont): current_font = QFont() # Reset if invalid
        self.new_settings['display_font'] = current_font # Ensure working copy has valid font
        self.current_font_label.setText(f"{current_font.family()} {current_font.pointSize()}pt")
        self.current_font_label.setFont(current_font)

        # Background Alpha
        current_alpha = self.new_settings.get('bg_alpha', QColor(config.DEFAULT_BG_COLOR).alpha())
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
        # Update visibility based on loaded settings
        self._update_provider_specific_visibility()


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

    def _browse_google_credentials(self):
        """Open file dialog to select Google credentials file."""
        current_path = self.new_settings.get('google_credentials_path', '')
        directory = os.path.dirname(current_path) if current_path else ''
        filePath, _ = QFileDialog.getOpenFileName(self, "Select Google Cloud Credentials", directory, "JSON files (*.json)")
        if filePath:
            self.new_settings['google_credentials_path'] = filePath
            self.google_credentials_path_edit.setText(os.path.basename(filePath))
            self.google_credentials_path_edit.setToolTip(filePath)
            logging.info(f"Google credentials path selected in dialog: {filePath}")

    def _update_ocr_provider(self, index):
        """Update selected OCR provider key in new_settings."""
        selected_key = self.ocr_provider_combo.itemData(index)
        if selected_key: self.new_settings['ocr_provider'] = selected_key
        # Visibility handled by _update_provider_specific_visibility connected to same signal

    def _update_ocr_language(self, index): # <<< NEW SLOT
        """Update selected OCR language code in new_settings."""
        selected_code = self.ocr_language_combo.itemData(index)
        if selected_code:
            self.new_settings['ocr_language_code'] = selected_code

    def _update_ocrspace_key(self, text):
        """Update OCR.space API key in new_settings."""
        self.new_settings['ocrspace_api_key'] = text

    def _toggle_ocrspace_key_visibility(self, checked):
        """Toggle visibility of the OCR.space API key characters."""
        self.ocrspace_key_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        self.ocrspace_show_key_button.setText("Hide" if checked else "Show")

    def _update_translation_engine(self, index):
        """Update selected translation engine key in new_settings."""
        selected_key = self.engine_combo.itemData(index)
        if selected_key: self.new_settings['translation_engine'] = selected_key
        # Visibility handled by _update_provider_specific_visibility connected to same signal

    def _update_deepl_key(self, text):
        """Update DeepL API key in new_settings."""
        self.new_settings['deepl_api_key'] = text

    def _toggle_deepl_key_visibility(self, checked):
        """Toggle visibility of the DeepL API key characters."""
        self.deepl_key_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        self.deepl_show_key_button.setText("Hide" if checked else "Show")

    def _update_provider_specific_visibility(self):
        """Show/hide provider/engine-specific fields (Credentials, API keys, OCR Language)."""
        selected_ocr_key = self.ocr_provider_combo.currentData()
        selected_trans_key = self.engine_combo.currentData()

        # OCR Provider Visibility
        is_google_vision = (selected_ocr_key == "google_vision")
        is_ocr_space = (selected_ocr_key == "ocr_space")

        self.google_credentials_label.setVisible(is_google_vision)
        self.google_credentials_widget.setVisible(is_google_vision)

        self.ocrspace_key_label.setVisible(is_ocr_space)
        self.ocrspace_key_widget.setVisible(is_ocr_space)
        self.ocr_language_label.setVisible(is_ocr_space) # <<< Show/Hide OCR Lang
        self.ocr_language_combo.setVisible(is_ocr_space) # <<< Show/Hide OCR Lang Combo

        # Translation Engine Visibility
        is_deepl = (selected_trans_key == "deepl_free")
        is_google_cloud_trans = (selected_trans_key == "google_cloud_v3")
        self.deepl_key_label.setVisible(is_deepl)
        self.deepl_key_widget.setVisible(is_deepl)

        # Conditionally show Google Credentials label again if Google Cloud Translate is chosen
        # but Google Vision OCR is *not* chosen (since Translate still needs creds)
        # Make sure Google Credentials row is visible if EITHER is true
        google_needed = is_google_vision or is_google_cloud_trans
        self.google_credentials_label.setVisible(google_needed)
        self.google_credentials_widget.setVisible(google_needed)
        # Adjust label text based on why it's needed
        if is_google_vision and is_google_cloud_trans:
             self.google_credentials_label.setText("Google Credentials (OCR & Translate):")
        elif is_google_vision:
             self.google_credentials_label.setText("Google Credentials (for OCR):")
        elif is_google_cloud_trans:
              self.google_credentials_label.setText("Google Credentials (for Translate):")


    def _update_language(self, index): # <<< Renamed from _update_language to be specific
        """Update selected TRANSLATION target language code in new_settings."""
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
             self.parent_window.clear_history()
             self._update_history_button_states()


    # --- Get Final Settings ---
    def get_updated_settings(self):
        """Returns the modified settings dict gathered from the widgets."""
        logging.debug(f"Returning updated settings from dialog: {self.new_settings}")
        return self.new_settings

    def accept(self):
        """Validate settings before accepting the dialog."""
        # --- Validation ---
        selected_ocr = self.new_settings.get('ocr_provider')
        selected_trans = self.new_settings.get('translation_engine')
        google_cred_path = self.new_settings.get('google_credentials_path')

        # Validate Google Credentials Path (Warn if set but non-existent)
        # Required if Google Vision OCR or Google Cloud Translate is selected
        google_needed = selected_ocr == 'google_vision' or selected_trans == 'google_cloud_v3'
        if google_needed:
            if not google_cred_path:
                ocr_name = config.AVAILABLE_OCR_PROVIDERS.get(selected_ocr, selected_ocr)
                trans_name = config.AVAILABLE_ENGINES.get(selected_trans, selected_trans)
                reason = f"Google Cloud Vision OCR" if selected_ocr == 'google_vision' else f"Google Cloud Translate Engine"
                if selected_ocr == 'google_vision' and selected_trans == 'google_cloud_v3':
                     reason = "Google Cloud Vision OCR and Translate Engine"

                QMessageBox.warning(self, "Credentials Required", f"Google Credentials are required for {reason}.\nPlease select the JSON key file.")
                return # Block closing
            elif not os.path.exists(google_cred_path):
                 QMessageBox.warning(self, "Credentials Invalid", f"The selected Google credentials file does not exist:\n{google_cred_path}\nOCR/Translation may fail.")
                 # Don't block closing, but warn user.

        # Block closing if OCR.space selected and key is missing
        if selected_ocr == 'ocr_space' and not self.new_settings.get('ocrspace_api_key'):
            QMessageBox.warning(self, "API Key Required", "OCR.space requires an API Key. Please enter one or select a different OCR provider.")
            return # Keep dialog open

        # Block closing if DeepL selected and key is missing
        if selected_trans == 'deepl_free' and not self.new_settings.get('deepl_api_key'):
            QMessageBox.warning(self, "API Key Required", "DeepL engine requires an API Key. Please enter one or select a different translation engine.")
            return # Keep dialog open

        # --- End Validation ---
        super().accept() # Call parent accept if validation passes