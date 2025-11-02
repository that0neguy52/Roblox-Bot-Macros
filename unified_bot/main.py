import tkinter as tk
import threading
import logging
import sys
import time
import gui

# --- Imports for native Windows hotkeys ---
try:
    import ctypes
    from ctypes import wintypes
except ImportError:
    ctypes = None
    wintypes = None
    logging.error("ctypes library not found. Hotkeys will not work.")

# Set up logging to the console
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] (%(threadName)s) %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)

# --- Hotkey Thread using native Windows API ---
class HotkeyThread(threading.Thread):
    """
    A dedicated thread to register and listen for a global Windows hotkey.
    This avoids the 'keyboard' library and the need for admin rights.
    """
    def __init__(self, app_instance, hotkey_name, hotkey_code):
        super().__init__()
        self.app_instance = app_instance
        self.logger = logging.getLogger(__name__)
        self.stop_event = threading.Event()
        
        # Store dynamic hotkey info
        self.hotkey_name = hotkey_name
        self.hotkey_code = hotkey_code
        
        # Hotkey Constants
        self.MOD_NOMOD = 0x0000
        self.WM_HOTKEY = 0x0312
        self.HOTKEY_ID = 9001  # Arbitrary ID for our hotkey

    def run(self):
        if not ctypes or not wintypes:
            self.logger.warning("ctypes module not loaded. Hotkey thread exiting.")
            return

        user32 = None
        try:
            user32 = ctypes.windll.user32
            
            # Register the Hotkey
            if not user32.RegisterHotKey(None, self.HOTKEY_ID, self.MOD_NOMOD, self.hotkey_code):
                self.logger.error(f"Failed to register '{self.hotkey_name}' hotkey. Error code: {ctypes.GetLastError()}")
                return
            
            self.logger.info(f"'{self.hotkey_name}' hotkey registered. Press {self.hotkey_name} to start/stop the bot.")
            
            # Start the Windows Message Loop
            msg = wintypes.MSG()
            while not self.stop_event.is_set():
                # PeekMessageW with PM_REMOVE (1)
                if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                    if msg.message == self.WM_HOTKEY and msg.wParam == self.HOTKEY_ID:
                        self.logger.info(f"Hotkey '{self.hotkey_name}' pressed. Toggling bot state.")
                        # Safely call the GUI toggle function
                        try:
                            self.app_instance.root.after(0, self.app_instance.toggle_bot_state)
                        except:
                            # GUI might be closing, ignore errors
                            pass
                    
                    # Required for the message loop to function
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                
                # Sleep to prevent high CPU usage and allow stop_event to be checked
                time.sleep(0.01)

        except Exception as e:
            self.logger.error(f"Error in hotkey thread: {e}", exc_info=True)
        finally:
            # Unregister the Hotkey
            if user32:
                try:
                    self.logger.info("Unregistering hotkey...")
                    user32.UnregisterHotKey(None, self.HOTKEY_ID)
                except:
                    pass

    def stop(self):
        """Signals the thread to stop."""
        self.stop_event.set()

def main():
    """
    Main function to initialize and run the GUI.
    """
    root = tk.Tk()
    app = gui.UnifiedBotGUI(root)
    
    # Run the 'clear on start' check
    app.run_clear_on_start()
    
    # Set up the native hotkey thread
    hotkey_thread = None
    if sys.platform.startswith('win') and ctypes:
        hotkey_name = app.hotkey_name_var.get()
        hotkey_code = app.hotkey_code_var.get()
        hotkey_thread = HotkeyThread(app, hotkey_name, hotkey_code)
        hotkey_thread.daemon = True
        hotkey_thread.start()
    else:
        logging.warning("Hotkeys are only supported on Windows. F7 hotkey will be disabled.")

    # Custom closing function to stop the hotkey thread
    def on_app_closing():
        if hotkey_thread:
            hotkey_thread.stop()  # Signal the hotkey thread to stop
        app.on_closing()  # Call the GUI's original closing logic
        
        # Wait briefly for hotkey thread to finish
        if hotkey_thread and hotkey_thread.is_alive():
            hotkey_thread.join(timeout=0.5)

    # Set the on_closing protocol
    root.protocol("WM_DELETE_WINDOW", on_app_closing)
    
    # Run the main GUI loop
    try:
        root.mainloop()
    except KeyboardInterrupt:
        logging.info("Application interrupted. Shutting down...")
        if hotkey_thread:
            hotkey_thread.stop()
            hotkey_thread.join(timeout=0.5)
        app.on_closing()
    
    # Final cleanup after mainloop exits
    if hotkey_thread and hotkey_thread.is_alive():
        hotkey_thread.stop()
        hotkey_thread.join(timeout=0.5)

if __name__ == "__main__":
    if not sys.platform.startswith('win'):
        logging.warning("This bot is designed for Windows and may not function correctly on other OS.")
    main()