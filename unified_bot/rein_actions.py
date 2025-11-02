import pydirectinput
import numpy as np
import logging
import time
import threading
import random

logger = logging.getLogger(__name__)

def move_and_click(target_x, target_y, config, stop_event):
    """
    Moves the mouse with proportional "ease-out" speed using pydirectinput.
    Snaps to the final position when it gets within 'mouse_snap_threshold'.
    
    This function is based on the user's provided 'safe_human_click'.
    """
    try:
        factor = config.get("mouse_speed_factor", 0.3)
        snap_distance = config.get("mouse_snap_threshold", 5) 
    except KeyError:
        factor = 0.3 
        snap_distance = 5 
        
    target_x, target_y = int(target_x), int(target_y)
    
    # 3. Start the "ease-out" loop
    while True:
        if stop_event.is_set(): 
            logger.debug("Mouse movement interrupted by stop event.")
            return

        current_x, current_y = pydirectinput.position()
        
        remaining_x = target_x - current_x
        remaining_y = target_y - current_y
        
        distance = max(abs(remaining_x), abs(remaining_y))
        
        # 4. The "Snap" Logic:
        if distance < snap_distance:
            break
            
        # 5. The "Ease-Out" Logic:
        move_x = np.round(remaining_x * factor)
        move_y = np.round(remaining_y * factor)
        
        if move_x == 0 and remaining_x != 0:
            move_x = 1 if remaining_x > 0 else -1
        if move_y == 0 and remaining_y != 0:
            move_y = 1 if remaining_y > 0 else -1
            
        pydirectinput.moveRel(int(move_x), int(move_y), relative=True)
        time.sleep(0.001)

    # 6. The Final "Snap":
    if stop_event.is_set():
        logger.debug("Mouse movement interrupted by stop event.")
        return

    final_x, final_y = pydirectinput.position()
    final_move_x = target_x - final_x
    final_move_y = target_y - final_y
    
    if final_move_x != 0 or final_move_y != 0: 
        pydirectinput.moveRel(final_move_x, final_move_y, relative=True)
        # --- FIX: Add sleep *after* final move to let it 'settle' ---
        time.sleep(0.05) 
    
    # --- FIX: Failsafe position check ---
    # Check if we are *exactly* on the target. If not, force it.
    final_pos = pydirectinput.position()
    if final_pos != (target_x, target_y):
        logger.warning(f"Final click position {final_pos} does not match target {target_x, target_y}. Forcing absolute move.")
        pydirectinput.moveTo(target_x, target_y)
        time.sleep(0.05) # Sleep after absolute move
    
    # Tiny pause before click
    time.sleep(0.01 + random.uniform(0.0, 0.01))
    
    # --- MODIFIED: Perform a double click for reliability ---
    pydirectinput.click()
    time.sleep(0.05 + random.uniform(0.0, 0.05)) # Pause for double click
    pydirectinput.click()


def click_button(button_key, config, stop_event, timeout=None):
    """
    Finds a calibrated button point and clicks it using human-like movement.
    """
    try:
        logger.debug(f"Attempting to click calibrated button '{button_key}'...")
        
        pos = config['calibrated_points'].get(button_key)
        
        if pos and len(pos) == 2:
            center_x, center_y = pos
            move_and_click(int(center_x), int(center_y), config, stop_event)
            logger.info(f"Clicked '{button_key}'.")
        else:
            logger.error(f"Calibration data for '{button_key}' is invalid or missing: {pos}")
            raise Exception(f"Invalid calibration data for {button_key}")
        
    except Exception as e:
        if not stop_event.is_set():
            logger.error(f"Failed to click button '{button_key}': {e}", exc_info=True)
        raise


