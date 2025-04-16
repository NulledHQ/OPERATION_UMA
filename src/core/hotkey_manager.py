# src/core/hotkey_manager.py
import threading
import logging
try:
    import keyboard
except ImportError:
    logging.critical("Failed to import 'keyboard' library. Hotkeys will not work. Run 'pip install keyboard'")
    keyboard = None # Define dummy to prevent NameErrors

from PyQt5.QtCore import QTimer

# Use absolute import from src package root
from src import config

# Flag to ensure listener starts only once
_hotkey_listener_started = False
_listener_thread = None
_registered_hotkey = None # Keep track of the registered hotkey function

def _listen_for_hotkey(key_combination, callback_func):
    """Target function for the listener thread."""
    if keyboard is None: return # Don't run if library failed import

    global _registered_hotkey
    logging.debug(f"Hotkey listener thread started. Waiting for '{key_combination}'...")
    try:
        # Use a lambda with QTimer.singleShot to ensure the callback runs in the main Qt thread
        # Store the hotkey function returned by add_hotkey for later removal
        _registered_hotkey = keyboard.add_hotkey(key_combination, lambda: QTimer.singleShot(0, callback_func))
        logging.info(f"Global hotkey '{key_combination}' registered.")
        # keyboard.wait() blocks until keyboard.unhook_all() or program exit
        # Using wait() might block application exit if not handled carefully.
        # Consider alternative non-blocking approaches if needed, but wait() is simple for now.
        keyboard.wait()
    except Exception as e:
        logging.exception("Error in hotkey listener thread:")
    finally:
        logging.debug("Hotkey listener thread finished.")
        _registered_hotkey = None

def setup_hotkey(callback_func):
    """Sets up the global hotkey listener in a separate thread."""
    if keyboard is None:
        logging.error("Cannot setup hotkey: 'keyboard' library not imported.")
        return

    global _hotkey_listener_started, _listener_thread
    if _hotkey_listener_started:
        logging.warning("Hotkey listener already started.")
        return

    key_combination = config.HOTKEY
    _listener_thread = threading.Thread(
        target=_listen_for_hotkey,
        args=(key_combination, callback_func),
        name="HotkeyListenerThread", # Give thread a name for logging
        daemon=True # Allows program to exit even if this thread is running
    )
    _listener_thread.start()
    _hotkey_listener_started = True


def unregister_hotkeys():
    """Unregisters all hotkeys managed by the keyboard library."""
    if keyboard is None:
        logging.error("Cannot unregister hotkeys: 'keyboard' library not imported.")
        return

    global _hotkey_listener_started, _registered_hotkey
    logging.debug("Attempting to unregister hotkeys...")
    try:
        # Specific removal might be better if library allows it, but unhook_all is robust
        # if _registered_hotkey:
        #     keyboard.remove_hotkey(_registered_hotkey)
        #     _registered_hotkey = None
        #     logging.info("Specific hotkey removed.")
        # else:
        #     keyboard.unhook_all() # Fallback
        #     logging.info("Unhooked all keyboard hotkeys.")

        # unhook_all is generally sufficient and simpler if this app manages all hotkeys
        keyboard.unhook_all()
        _hotkey_listener_started = False # Reset flag
        logging.info("All keyboard hotkeys unregistered.")
        # This should also cause keyboard.wait() in the listener thread to return.
    except Exception as e:
         logging.exception("Error occurred while unregistering hotkeys:")