# hotkey_manager.py
import threading
import logging
import keyboard
from PyQt5.QtCore import QTimer # Import QTimer here

import config # Import config for hotkey definition

# Flag to ensure listener starts only once
_hotkey_listener_started = False
_listener_thread = None

def _listen_for_hotkey(key_combination, callback_func):
    """Target function for the listener thread."""
    logging.debug(f"Hotkey listener thread started. Waiting for '{key_combination}'...")
    try:
        # Use QTimer.singleShot to ensure the callback runs in the main Qt thread
        keyboard.add_hotkey(key_combination, lambda: QTimer.singleShot(0, callback_func))
        keyboard.wait()  # Blocks this thread until keyboard.unhook_all() or program exit
    except Exception as e:
        logging.exception("Error in hotkey listener thread:")
    finally:
        logging.debug("Hotkey listener thread finished.")

def setup_hotkey(callback_func):
    """Sets up the global hotkey listener in a separate thread."""
    global _hotkey_listener_started, _listener_thread
    if _hotkey_listener_started:
        logging.warning("Hotkey listener already started.")
        return

    key_combination = config.HOTKEY
    _listener_thread = threading.Thread(
        target=_listen_for_hotkey,
        args=(key_combination, callback_func),
        daemon=True # Allows program to exit even if this thread is running
    )
    _listener_thread.start()
    _hotkey_listener_started = True
    logging.info(f"Global hotkey '{key_combination}' registered.")

def unregister_hotkeys():
    """Unregisters all hotkeys managed by the keyboard library."""
    logging.debug("Unregistering hotkeys...")
    try:
        keyboard.unhook_all() # This will also make keyboard.wait() return
    except Exception as e:
         logging.exception("Error unregistering hotkeys:")