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
# from src import config # No longer need config here for default

# Flag and state variables
_hotkey_listener_started = False
_listener_thread = None
_registered_hotkey_func = None # Store the actual hotkey function object returned by keyboard lib
_current_hotkey_str = "" # Store the string used for registration

def _listen_for_hotkey(key_combination, callback_func):
    """Target function for the listener thread."""
    global _registered_hotkey_func, _hotkey_listener_started, _current_hotkey_str
    if keyboard is None: return

    logging.debug(f"Hotkey listener thread attempting to register '{key_combination}'...")
    try:
        # Ensure previous hotkeys are cleared before adding a new one in the thread
        # This might be necessary if the thread restarts or logic changes
        # Use unhook_all() cautiously if other apps might use keyboard lib hooks.
        # Using remove_hotkey(_registered_hotkey_func) before adding might be slightly safer
        # if _registered_hotkey_func:
        #     keyboard.remove_hotkey(_registered_hotkey_func)
        # But unhook_all is simpler if we assume this app controls all its hooks.
        keyboard.unhook_all()

        # Use a lambda with QTimer.singleShot to run callback in the main Qt thread
        # Store the actual function object returned by add_hotkey for later removal attempt
        _registered_hotkey_func = keyboard.add_hotkey(
            key_combination,
            lambda: QTimer.singleShot(0, callback_func),
            trigger_on_release=False # Trigger on press
        )
        _current_hotkey_str = key_combination # Store the string we registered
        logging.info(f"Global hotkey '{key_combination}' registered.")
        _hotkey_listener_started = True

        # keyboard.wait() blocks. This makes dynamic changes hard without restarting thread.
        keyboard.wait()

    except ValueError as ve: # keyboard lib raises ValueError for invalid hotkey strings
        logging.error(f"Hotkey listener: Invalid hotkey format '{key_combination}'. Error: {ve}")
        _hotkey_listener_started = False # Ensure flag is reset if registration fails
    except Exception as e:
        logging.exception("Error in hotkey listener thread:")
        _hotkey_listener_started = False # Ensure flag is reset on other errors
    finally:
        logging.debug("Hotkey listener thread finished.")
        _registered_hotkey_func = None
        _current_hotkey_str = ""
        # Set started flag to False ONLY if the thread is actually stopping.
        # If wait() returns due to unhook_all() called from outside,
        # the flag might be reset prematurely if a new thread is starting.
        # This logic might need refinement for robust dynamic changes.
        _hotkey_listener_started = False # Reset flag when thread stops


def setup_hotkey(hotkey_str, callback_func): # <<< ACCEPT HOTKEY STRING
    """Sets up the global hotkey listener in a separate thread."""
    global _hotkey_listener_started, _listener_thread, _current_hotkey_str
    if keyboard is None:
        logging.error("Cannot setup hotkey: 'keyboard' library not imported.")
        return
    if not hotkey_str:
        logging.error("Cannot setup hotkey: No hotkey string provided.")
        return

    # If listener already running, log warning (dynamic change not yet implemented)
    if _hotkey_listener_started:
        logging.warning(f"Hotkey listener setup called while already potentially running for '{_current_hotkey_str}'.")
        # If the requested hotkey is the same as current, do nothing
        if hotkey_str == _current_hotkey_str:
             logging.debug("Requested hotkey is the same as the currently registered one.")
             return
        else:
             # *** Dynamic change requires stopping the old thread cleanly ***
             # *** Deferring this complex implementation ***
             logging.error(f"Cannot change hotkey from '{_current_hotkey_str}' to '{hotkey_str}' while listener is running. Restart application to apply changes.")
             return # Exit without starting a new thread

    # Stop condition for the old thread if it exists and isn't alive (e.g., from previous error)
    if _listener_thread and not _listener_thread.is_alive():
         logging.debug("Cleaning up stale listener thread object.")
         _listener_thread = None # Clear stale thread object


    # Start a new listener thread
    logging.info(f"Starting hotkey listener thread for '{hotkey_str}'...")
    _listener_thread = threading.Thread(
        target=_listen_for_hotkey,
        args=(hotkey_str, callback_func), # Pass the hotkey string
        name="HotkeyListenerThread",
        daemon=True
    )
    _listener_thread.start()
    # Note: _hotkey_listener_started flag is set inside the thread upon successful registration


def unregister_hotkeys():
    """Unregisters all hotkeys managed by the keyboard library."""
    global _hotkey_listener_started, _registered_hotkey_func, _current_hotkey_str
    if keyboard is None:
        # Don't log error here, might be called during shutdown when lib is gone
        # logging.warning("Cannot unregister hotkeys: 'keyboard' library not imported.")
        return

    # Check if the listener was ever started or needs stopping
    # Avoid calling unhook_all if not necessary or if thread never started.
    # if not _hotkey_listener_started and not _registered_hotkey_func:
    #      logging.debug("No active hotkeys known to unregister.")
    #      return

    logging.debug("Attempting to unregister hotkeys via unhook_all()...")
    try:
        # This should cause keyboard.wait() in the listener thread to return.
        keyboard.unhook_all()
        _registered_hotkey_func = None # Clear the stored function object
        # Keep _current_hotkey_str until thread confirms exit? Or clear here? Clear here for now.
        # _current_hotkey_str = ""
        # The thread itself should reset _hotkey_listener_started in its finally block
        logging.info("Keyboard unhook_all() called.")

    except Exception as e:
         # Use broad exception during shutdown/cleanup
         logging.exception("Error occurred while calling keyboard.unhook_all():")

# --- Function for dynamic change (Deferred Implementation) ---
# def change_hotkey(new_hotkey_str, callback_func):
#     """ Safely stops the current listener, unregisters, and starts a new one. """
#     logging.info(f"Attempting to change hotkey to: {new_hotkey_str}")
#     unregister_hotkeys() # Unhook everything
#
#     # Need a reliable way to stop the listener thread here.
#     # keyboard.wait() makes this tricky. Might need signals or different thread structure.
#     # For now, this function is a placeholder.
#     if _listener_thread and _listener_thread.is_alive():
#          logging.warning("Waiting for listener thread to stop after unhook...")
#          # keyboard._listener.stop() # This might be internal/unstable API
#          # If thread doesn't stop naturally after unhook, join might hang
#          _listener_thread.join(timeout=0.5) # Wait briefly for thread to exit
#          if _listener_thread.is_alive():
#              logging.error("Listener thread did not stop cleanly. Cannot change hotkey dynamically.")
#              # Attempt to re-register the original if possible? Risky.
#              # setup_hotkey(_current_hotkey_str, callback_func) # Try to restore old one
#              return False # Indicate failure
#          else:
#              logging.info("Listener thread stopped.")
#              _listener_thread = None # Clear stopped thread
#
#     # If thread stopped or wasn't running, setup the new one
#     logging.debug("Setting up new hotkey listener...")
#     setup_hotkey(new_hotkey_str, callback_func)
#     return True # Indicate success (or at least attempt)