# src/core/hotkey_manager.py
import threading
import logging
import time # Keep time for potential debouncing if needed
from collections import defaultdict

try:
    import keyboard
    # Define constants based on the keyboard library's event types
    KEY_DOWN = keyboard.KEY_DOWN
    KEY_UP = keyboard.KEY_UP
except ImportError:
    logging.critical("Failed to import 'keyboard' library. Hotkeys will not work. Run 'pip install keyboard'")
    keyboard = None
    KEY_DOWN = 'down' # Dummy values if import fails
    KEY_UP = 'up'

from PyQt5.QtCore import QTimer

# --- Module State ---
_listener_thread = None
_stop_event = threading.Event() # Used to signal the listener thread to stop
_hook_active = False
_current_hotkey_str = ""
_main_callback = None # Store the main callback function (e.g., grab_text)
_pressed_keys = set() # Track currently pressed keys
_hotkey_keys = set() # Parsed keys from the _current_hotkey_str
_hotkey_lock = threading.Lock() # Lock for accessing shared state (_current_hotkey_str, _hotkey_keys)

def _parse_hotkey_string(hotkey_str):
    """Parses the hotkey string into a set of lower-case key names."""
    if not hotkey_str:
        return set()
    # Normalize and split, converting to lowercase
    return set(key.strip().lower() for key in hotkey_str.split('+'))

def _on_key_event(event):
    """Callback function for keyboard.hook(). Processes key events."""
    global _pressed_keys, _hotkey_keys, _current_hotkey_str, _main_callback
    if keyboard is None or not _main_callback:
        return

    try:
        # Get the canonical name, lowercased
        # Use event.name which is generally preferred
        key_name = event.name.lower() if event.name else None
        if not key_name: return # Ignore events without a name

        # Update the set of currently pressed keys
        if event.event_type == KEY_DOWN:
            _pressed_keys.add(key_name)
        elif event.event_type == KEY_UP:
            _pressed_keys.discard(key_name) # Use discard to avoid errors if key wasn't tracked

        # Check for hotkey match ONLY on key down events
        if event.event_type == KEY_DOWN:
            with _hotkey_lock:
                target_keys = _hotkey_keys

            # Check if the currently pressed keys EXACTLY match the target hotkey keys
            # Use issubset and check lengths for an exact match
            if target_keys and target_keys.issubset(_pressed_keys) and len(_pressed_keys) == len(target_keys):
                logging.debug(f"Hotkey '{_current_hotkey_str}' detected!")
                # Trigger the main callback in the Qt main thread
                QTimer.singleShot(0, _main_callback)
                # Optional: Consume the event to prevent it going further?
                # Be careful with consuming, might interfere elsewhere.
                # return False # If keyboard hook callback allows consumption

    except Exception as e:
        logging.exception(f"Error processing key event in hotkey manager: {e}")

def _run_hook_listener():
    """Target function for the listener thread that runs the hook."""
    global _hook_active
    if keyboard is None: return

    logging.debug("Hotkey listener thread starting keyboard.hook()...")
    hook_ref = None
    try:
        # Register the hook
        hook_ref = keyboard.hook(_on_key_event, suppress=False) # suppress=False lets events pass through
        _hook_active = True
        logging.info(f"Keyboard hook registered. Listening for hotkey '{_current_hotkey_str}'.")

        # Keep the thread alive while the stop event is not set
        _stop_event.wait() # Block until stop_event is set

    except Exception as e:
        logging.exception("Error setting up or running keyboard hook:")
    finally:
        _hook_active = False
        if keyboard and hook_ref:
            try:
                keyboard.unhook(hook_ref)
                logging.debug("Keyboard hook removed.")
            except Exception as e:
                logging.exception("Error removing keyboard hook:")
        # keyboard.unhook_all() # Alternative, potentially broader cleanup
        logging.debug("Hotkey listener thread finished.")

def start_hotkey_listener(hotkey_str, callback_func):
    """Starts the global hotkey listener using keyboard.hook in a thread."""
    global _listener_thread, _stop_event, _current_hotkey_str, _main_callback, _hotkey_keys
    if keyboard is None:
        logging.error("Cannot start hotkey listener: 'keyboard' library not imported.")
        return False
    if not hotkey_str:
        logging.error("Cannot start hotkey listener: No hotkey string provided.")
        return False
    if _hook_active or (_listener_thread and _listener_thread.is_alive()):
        logging.warning("Hotkey listener setup called while already running. Call stop first if needed.")
        # If the request is for the same hotkey and callback, consider it a no-op success
        if hotkey_str == _current_hotkey_str and callback_func == _main_callback:
            return True
        # Otherwise, changing requires stopping first (handled by update_active_hotkey or stop)
        logging.error("Cannot start a new listener while one is active. Use update_active_hotkey or stop first.")
        return False

    # Store callback and initial hotkey
    _main_callback = callback_func
    with _hotkey_lock:
        _current_hotkey_str = hotkey_str
        _hotkey_keys = _parse_hotkey_string(hotkey_str)

    # Reset stop event and start the listener thread
    _stop_event.clear()
    _pressed_keys.clear() # Clear pressed keys state
    logging.info(f"Starting hotkey listener thread for '{hotkey_str}'...")
    _listener_thread = threading.Thread(
        target=_run_hook_listener,
        name="HotkeyListenerThread",
        daemon=True
    )
    _listener_thread.start()
    # Give the thread a moment to potentially start the hook
    time.sleep(0.1)
    return _hook_active # Return status based on whether hook started

def stop_hotkey_listener():
    """Stops the hotkey listener thread."""
    global _listener_thread, _hook_active, _main_callback
    if not _listener_thread or not _listener_thread.is_alive():
        logging.debug("Hotkey listener thread already stopped or not started.")
        _hook_active = False # Ensure flag is correct
        return

    logging.debug("Attempting to stop hotkey listener thread...")
    _stop_event.set() # Signal the thread to exit its wait loop
    _listener_thread.join(timeout=1.0) # Wait for the thread to terminate

    if _listener_thread.is_alive():
        logging.error("Hotkey listener thread did not stop gracefully.")
        # Further action might be needed (though unhook should have happened in thread)
    else:
        logging.info("Hotkey listener thread stopped.")

    _listener_thread = None
    _hook_active = False
    _main_callback = None
    _pressed_keys.clear()

def update_active_hotkey(new_hotkey_str):
    """Dynamically updates the hotkey string the listener checks for."""
    global _current_hotkey_str, _hotkey_keys
    if keyboard is None: return False
    if not _hook_active:
        logging.warning("Cannot update hotkey: Listener is not active.")
        return False # Or should we just update the variable anyway?

    logging.info(f"Updating active hotkey to: '{new_hotkey_str}'")
    with _hotkey_lock:
        _current_hotkey_str = new_hotkey_str
        _hotkey_keys = _parse_hotkey_string(new_hotkey_str)
        # Clear potentially stale pressed keys when hotkey changes
        # This prevents accidental triggering if modifiers were held during change
        _pressed_keys.clear()
    logging.debug(f"Active hotkey keys set to: {_hotkey_keys}")
    return True