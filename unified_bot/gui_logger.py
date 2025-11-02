import logging
import queue
from logging.handlers import RotatingFileHandler
import os             # <-- ADD
from pathlib import Path  # <-- ADD

# --- Store the queue_handler in the module so we can access it ---
queue_handler = None

class QueueHandler(logging.Handler):
    """
    A custom logging handler that puts log messages into a queue.
    This is used to safely pass log messages from the bot thread to the GUI thread.
    """
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        """
        Puts the raw log record (object) into the queue.
        """
        self.log_queue.put(record)

def set_gui_log_level(level_str):
    """
    Sets the logging level for the GUI queue handler based on a string.
    """
    global queue_handler
    if queue_handler:
        if level_str == "User":
            queue_handler.setLevel(logging.INFO)
        elif level_str == "Developer":
            queue_handler.setLevel(logging.DEBUG)
        
        # Log the change itself (this will always appear)
        logging.getLogger().info(f"GUI log level set to: {level_str}")

# gui_logger.py (Replace the whole setup_logging function)

def setup_logging(log_queue):
    """
    Configures the root logger to use the QueueHandler
    and a RotatingFileHandler, saving the file logs to the user's Documents folder.
    """
    global queue_handler
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    
    # --- FIND LOG PATH IN DOCUMENTS FOLDER ---
    try:
        # Get the path to the user's Documents folder (Windows, Linux, macOS compatible)
        documents_path = Path.home() / 'Documents'
        log_dir = documents_path / 'Choice of Immortals Bot Logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file_path = log_dir / 'bot_activity.log'
    except Exception:
        # Fallback to the current directory if finding Documents fails
        log_file_path = 'bot_activity.log'
        
    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG) # Set to lowest level

    # Clear existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    # 1. Console/GUI Handler (via Queue)
    queue_handler = QueueHandler(log_queue)
    queue_handler.setFormatter(logging.Formatter(log_format))
    queue_handler.setLevel(logging.DEBUG) 
    logger.addHandler(queue_handler)

    # 2. File Handler (for all-time logs)
    file_handler = RotatingFileHandler(
        log_file_path,  # <-- USE THE NEW PATH
        mode='a', 
        maxBytes=5*1024*1024, 
        backupCount=2
    )
    file_handler.setFormatter(logging.Formatter(log_format))
    file_handler.setLevel(logging.INFO) # Keep file logs at INFO
    logger.addHandler(file_handler)
    
    # Silence overly verbose libraries
    logging.getLogger('PIL').setLevel(logging.WARNING)
    logging.getLogger('pyautogui').setLevel(logging.WARNING)
