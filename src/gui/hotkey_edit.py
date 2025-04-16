# src/gui/hotkey_edit.py
import logging
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QKeyEvent

# Try importing keyboard library safely for key name conversion
try:
    import keyboard
except ImportError:
    keyboard = None
    logging.warning("HotkeyEdit: 'keyboard' library not found. Key name display might be limited.")

class HotkeyEdit(QPushButton):
    """
    A button-like widget to capture and display a keyboard hotkey combination.
    """
    hotkeyChanged = pyqtSignal(str) # Signal emitted when a new hotkey is set

    def __init__(self, initial_hotkey="", parent=None):
        super().__init__(parent)
        self._hotkey_str = initial_hotkey
        self._is_capturing = False
        self._pressed_keys = set() # To track modifiers
        self.setText(self._format_hotkey_display(self._hotkey_str))
        self.setToolTip(f"Current Hotkey: {self._hotkey_str}\nClick to change.")
        self.clicked.connect(self._start_capture)
        self.setFocusPolicy(Qt.StrongFocus) # Allow widget to receive key presses

    def _format_hotkey_display(self, hotkey_str):
        # Simple display formatting (can be improved)
        return hotkey_str.replace("+", " + ").title() if hotkey_str else "Click to Set Hotkey"

    def setHotkey(self, hotkey_str):
        """Programmatically sets the hotkey string."""
        self._hotkey_str = hotkey_str
        self.setText(self._format_hotkey_display(self._hotkey_str))
        self.setToolTip(f"Current Hotkey: {self._hotkey_str}\nClick to change.")
        self._is_capturing = False # Ensure capture mode is off

    def currentHotkey(self) -> str:
        """Returns the currently set hotkey string."""
        return self._hotkey_str

    def _start_capture(self):
        """Handles the button click to start capturing."""
        self._is_capturing = True
        self._pressed_keys = set()
        self.setText("Press new hotkey...")
        self.grabKeyboard() # Capture keyboard input exclusively for this widget

    def _stop_capture(self):
        """Stops capturing and releases the keyboard."""
        self._is_capturing = False
        self.releaseKeyboard()
        # Restore display text after capture attempt
        self.setText(self._format_hotkey_display(self._hotkey_str))

    def keyPressEvent(self, event: QKeyEvent):
        """Handles key press events when capturing."""
        if not self._is_capturing:
            super().keyPressEvent(event) # Default handling if not capturing
            return

        key = event.key()
        modifiers = event.modifiers()
        key_text = event.text() # Raw text if available

        # Ignore modifier-only presses initially
        if key in [Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta]:
            mod_name = self._qt_modifier_to_str(key)
            if mod_name:
                self._pressed_keys.add(mod_name)
            # Display current modifiers
            self.setText(" + ".join(sorted(list(self._pressed_keys))) + " + ...")
            return

        # --- A non-modifier key was pressed ---
        final_key_str = ""
        if keyboard:
            # Try to use keyboard library to get a canonical name
            try:
                # Note: Getting scan code might be platform dependent or need mapping
                # Using key name conversion from Qt might be more reliable here
                # For simplicity, we'll try a basic Qt conversion first
                qt_key_name = self._qt_key_to_str(key, key_text)
                if qt_key_name and qt_key_name.lower() not in ['ctrl', 'shift', 'alt', 'meta']:
                     final_key_str = qt_key_name.lower()
                # If Qt conversion fails, try keyboard lib (might be less reliable without scancodes)
                # This part using keyboard.scan_codes often doesn't work well with Qt events directly
                # scan_code = event.nativeScanCode()
                # key_name = keyboard.scan_codes.get(scan_code)
                # if key_name and key_name not in ['ctrl', 'shift', 'alt', 'meta', 'windows', 'cmd', 'option']:
                #     final_key_str = key_name.lower()

            except Exception as e:
                logging.warning(f"HotkeyEdit: Error getting key name: {e}")

        # Fallback if keyboard lib failed or key unknown
        if not final_key_str:
            qt_key_name = self._qt_key_to_str(key, key_text)
            if qt_key_name and qt_key_name.lower() not in ['ctrl', 'shift', 'alt', 'meta']:
                final_key_str = qt_key_name.lower()

        if final_key_str:
            # Combine modifiers and the final key
            parts = sorted(list(self._pressed_keys))
            parts.append(final_key_str)
            new_hotkey = "+".join(parts)

            self._hotkey_str = new_hotkey
            self.hotkeyChanged.emit(self._hotkey_str) # Emit the change
            logging.debug(f"Hotkey captured: {self._hotkey_str}")
            self._stop_capture() # Finish capturing
        else:
             # If we only got modifiers or an invalid key, maybe reset or wait
             logging.debug("HotkeyEdit: Ignoring modifier press or unrecognized key.")
             # Optionally, could reset capture after a timeout or specific key (like Esc)
             pass


    def keyReleaseEvent(self, event: QKeyEvent):
        """Handles key release events to track modifiers."""
        if self._is_capturing:
            mod_name = self._qt_modifier_to_str(event.key())
            if mod_name and mod_name in self._pressed_keys:
                self._pressed_keys.remove(mod_name)
                # Update display if only modifiers remain pressed
                if self._pressed_keys:
                   self.setText(" + ".join(sorted(list(self._pressed_keys))) + " + ...")
                elif not event.isAutoRepeat(): # Don't reset on auto-repeat release
                     self.setText("Press new hotkey...")

            # Allow Esc to cancel capture
            if event.key() == Qt.Key_Escape:
                 self._stop_capture()
                 self.setText(self._format_hotkey_display(self._hotkey_str)) # Restore previous
        else:
            super().keyReleaseEvent(event)

    def _qt_modifier_to_str(self, key_code):
        """Convert Qt modifier key code to string for keyboard lib."""
        # Using lowercase consistent with 'keyboard' library conventions
        return {
            Qt.Key_Control: 'ctrl',
            Qt.Key_Shift: 'shift',
            Qt.Key_Alt: 'alt',
            Qt.Key_Meta: 'win' # Or 'cmd'/'meta'. 'win' often works with 'keyboard' lib on windows
        }.get(key_code)

    def _qt_key_to_str(self, key_code, key_text):
        """Convert Qt key code to a string representation, preferring text."""
        # Prefer simple text for letters/numbers if available and valid
        if key_text and len(key_text) == 1 and ('a' <= key_text.lower() <= 'z' or '0' <= key_text <= '9'):
            return key_text.lower()

        # Map common non-alphanumeric keys using Qt.Key constants
        simple_map = {
            Qt.Key_Space: 'space', Qt.Key_Return: 'enter', Qt.Key_Enter: 'enter',
            Qt.Key_Backspace: 'backspace', Qt.Key_Delete: 'delete', Qt.Key_Tab: 'tab',
            Qt.Key_Escape: 'esc', Qt.Key_Home: 'home', Qt.Key_End: 'end',
            Qt.Key_Left: 'left', Qt.Key_Right: 'right', Qt.Key_Up: 'up', Qt.Key_Down: 'down',
            Qt.Key_PageUp: 'page up', Qt.Key_PageDown: 'page down',
            Qt.Key_Insert: 'insert', Qt.Key_Print: 'print screen', Qt.Key_ScrollLock: 'scroll lock',
            Qt.Key_Pause: 'pause',
            Qt.Key_F1: 'f1', Qt.Key_F2: 'f2', Qt.Key_F3: 'f3', Qt.Key_F4: 'f4',
            Qt.Key_F5: 'f5', Qt.Key_F6: 'f6', Qt.Key_F7: 'f7', Qt.Key_F8: 'f8',
            Qt.Key_F9: 'f9', Qt.Key_F10: 'f10', Qt.Key_F11: 'f11', Qt.Key_F12: 'f12',
            # Common symbols (check key_text first as it might be more accurate)
            Qt.Key_Plus: '+', Qt.Key_Minus: '-', Qt.Key_Equal: '=',
            Qt.Key_BracketLeft: '[', Qt.Key_BracketRight: ']',
            Qt.Key_Backslash: '\\', Qt.Key_Slash: '/',
            Qt.Key_Semicolon: ';', Qt.Key_Apostrophe: "'", Qt.Key_QuoteDbl: '"',
            Qt.Key_Comma: ',', Qt.Key_Period: '.',
            Qt.Key_QuoteLeft: '`', Qt.Key_AsciiTilde: '~',
            # Consider adding numpad keys if needed, e.g., Qt.Key_NumLock
        }
        return simple_map.get(key_code)