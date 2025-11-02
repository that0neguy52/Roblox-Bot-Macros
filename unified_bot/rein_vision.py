import pyautogui
import pytesseract
import logging
import os
import sys
import time
from PIL import Image, ImageGrab # <-- ImageGrab is new
import cv2                     # <-- NEW
import numpy as np             # <-- NEW

logger = logging.getLogger(__name__)

# --- Tesseract Path (for PyInstaller) ---
# This attempts to set the Tesseract command path.
# This is a fallback. The Inno Setup installer should add it to the system PATH.
if getattr(sys, 'frozen', False):
    # If running in a PyInstaller bundle
    bundle_dir = sys._MEIPASS
    # Look for tesseract in a bundled path (if you chose to bundle it, which we didn't)
    # or assume it's in the default Inno Setup install path.
    tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
    else:
        logger.warning("Tesseract not found at default install path. Assuming it's in system PATH.")
else:
    # If running as a normal script, check local dev path
    try:
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    except Exception:
        logger.warning("Could not set Tesseract path. Assuming it's in system PATH.")

def get_image_path(image_name, config):
    """
    Gets the full, absolute path to an image file.
    Handles running as a script and as a PyInstaller bundle.
    
    :param image_name: The filename of the image (e.g., "stats_button.png")
    :param config: The bot's config dict (for 'ui_mode')
    :return: Absolute path to the image
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running in a PyInstaller bundle
        base_path = os.path.join(sys._MEIPASS, 'images')
    else:
        # Running as a normal script
        base_path = os.path.join(os.path.abspath("."), 'images')

    image_path = os.path.join(base_path, config['ui_mode'], image_name)
    
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found at path: {image_path}")
        
    return image_path

def find_button(image_name, config, timeout=None):
    """
    Locates a button on the screen using OpenCV's masked template matching.
    
    :param image_name: The filename of the image.
    :param config: The bot's config dict.
    :param timeout: Max time in seconds to search. If None, uses default.
    :return: A pyautogui.Point(x, y) of the button's center.
    :raises: Exception if the button is not found within the timeout.
    """
    if timeout is None:
        timeout = config['wait_times']['button_timeout']
        
    image_path = get_image_path(image_name, config)
    # Get confidence from config (set in GUI)
    confidence = config['confidence']
    
    # Load the template image (with alpha channel for masking)
    try:
        template = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if template is None:
            raise FileNotFoundError(f"Could not load image file: {image_path}")
    except Exception as e:
        logger.error(f"Error loading template image '{image_name}': {e}")
        raise

    mask = None
    if template.shape[2] == 4:
        # Use the alpha channel as the mask
        mask = template[:, :, 3]
        template = template[:, :, :3] # Remove alpha channel from template
    else:
        logger.warning(f"Image '{image_name}' has no alpha channel. Masking will not be used. Results may be less reliable.")

    start_time = time.time()
    while True:
        try:
            # 1. Grab the screen
            # We use PIL's ImageGrab and convert to NumPy array for OpenCV
            screen_pil = ImageGrab.grab()
            screen_np = np.array(screen_pil)
            # Convert from RGB (PIL) to BGR (OpenCV)
            screen = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)

            # 2. Perform template matching
            if mask is not None:
                # Use the mask
                result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED, mask=mask)
            else:
                # Fallback for images without alpha
                result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
            
            # 3. Get the best match
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            match_confidence = max_val
            logger.debug(f"Matching '{image_name}': Best match confidence = {match_confidence:.2f}")

            if match_confidence >= confidence:
                # 4. Get dimensions and calculate center
                h, w = template.shape[:2]
                top_left = max_loc
                center_x = top_left[0] + w // 2
                center_y = top_left[1] + h // 2
                
                button_center = pyautogui.Point(center_x, center_y)
                logger.debug(f"Found '{image_name}' at {button_center} with confidence {match_confidence:.2f}")
                return button_center

        except Exception as e:
            logger.warning(f"Error during OpenCV image search for '{image_name}': {e}", exc_info=True)
            
        if time.time() - start_time > timeout:
            raise Exception(f"Button '{image_name}' not found after {timeout} seconds (Confidence threshold: {confidence})")
            
        time.sleep(0.2) # Wait a moment before retrying

def read_stat(region_rect):
    """
    Reads text from a specific screen region using Pytesseract.
    
    :param region_rect: A tuple [x, y, width, height]
    :return: The raw, cleaned text found in the region.
    """
    if not region_rect or len(region_rect) != 4:
        logger.error(f"Invalid OCR region provided: {region_rect}")
        return "ERROR_BAD_REGION"
        
    try:
        # 1. Take screenshot of the specified region
        img = pyautogui.screenshot(region=region_rect)
        
        # 2. Use Pytesseract to read the text
        #    --psm 6: Assume a single uniform block of text.
        #    --oem 3: Default, based on what's available.
        custom_config = r'--oem 3 --psm 6'
        raw_text = pytesseract.image_to_string(img, config=custom_config)
        
        if raw_text:
            cleaned_text = raw_text.strip().replace('\n', ' ').strip()
            return cleaned_text
        else:
            logger.warning(f"Tesseract read no text in region {region_rect}")
            return "UNKNOWN"
            
    except pytesseract.TesseractNotFoundError:
        logger.critical("TESSERACT NOT FOUND. Make sure it is installed and in your system's PATH.")
        raise
    except Exception as e:
        logger.error(f"Error during OCR read in region {region_rect}: {e}")
        return "ERROR"

