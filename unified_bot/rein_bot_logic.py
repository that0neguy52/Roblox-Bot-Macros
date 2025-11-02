import logging
import time
import unified_bot.rein_actions as actions
import unified_bot.rein_vision as vision
import re
import pydirectinput # For sending input
import pyautogui # For reading pixels
import unified_bot.settings_manager as settings_manager # To access history file paths

def responsive_sleep(duration, stop_event, step=0.1):
    """
    Sleeps for 'duration' in 'step' increments, checking stop_event.
    Returns True if interrupted, False if completed.
    """
    end_time = time.time() + duration
    while time.time() < end_time:
        if stop_event.is_set():
            return True # Interrupted
        
        sleep_time = min(step, end_time - time.time())
        if sleep_time > 0:
            time.sleep(sleep_time)
            
    return False # Completed

def wait_for_game_load(config, stop_event):
    """
    Waits for the game UI to load using a 2-stage pixel check.
    1. Waits for the main game load screen (22, 26, 55) to appear.
    2. Waits for the main game load screen (22, 26, 55) to disappear.
    """
    logger = logging.getLogger(__name__)
    # --- MODIFIED: Re-classified to DEBUG ---
    logger.debug("Waiting for game UI to load (checking stats_button pixel)...")
    
    try:
        stats_x, stats_y = config['calibrated_points']['stats_button']
        stats_x, stats_y = int(stats_x), int(stats_y)
    except Exception as e:
        logger.error(f"Could not get stats_button for pixel check: {e}. Falling back to 10s sleep.")
        responsive_sleep(10.0, stop_event)
        return

    GAME_LOAD_COLOR = (22, 26, 55) # <-- Updated color
    CHECK_INTERVAL = 0.5 # Check every 0.5 seconds as requested
    STAGE_1_TIMEOUT = 60.0 # Max 60s to *find* the main load screen
    STAGE_2_TIMEOUT = 30.0 # Max 30s for the main load screen to *disappear*

    try:
        current_color = pyautogui.pixel(stats_x, stats_y) # <-- FIXED
    except Exception as e:
        logger.warning(f"Could not read pixel color at ({stats_x}, {stats_y}): {e}")
        current_color = GAME_LOAD_COLOR # Assume loading if pixel read fails

    # --- CASE A: Bot is started and already in-game ---
    if current_color != GAME_LOAD_COLOR:
        if responsive_sleep(CHECK_INTERVAL, stop_event): return
        
        try:
            current_color = pyautogui.pixel(stats_x, stats_y) # <-- FIXED
        except Exception:
            pass # Ignore read error
            
        if current_color != GAME_LOAD_COLOR:
            logger.debug(f"Pre-loading screen detected (Color: {current_color}). Waiting for main load screen ({GAME_LOAD_COLOR})...")
        else:
            logger.debug("Main game loading screen detected. Waiting for it to disappear...")

    # --- STAGE 1: Wait for the main game load screen (22, 26, 55) to appear ---
    if current_color != GAME_LOAD_COLOR:
        start_time_1 = time.time()
        while current_color != GAME_LOAD_COLOR:
            if stop_event.is_set(): return
            
            if time.time() - start_time_1 > STAGE_1_TIMEOUT:
                logger.warning(f"Stage 1 Timeout: Main game load screen ({GAME_LOAD_COLOR}) never appeared. Proceeding anyway.")
                return # Timed out, but proceed

            if responsive_sleep(CHECK_INTERVAL, stop_event): return # Interrupted
            
            try:
                current_color = pyautogui.pixel(stats_x, stats_y) # <-- FIXED
            except Exception:
                pass # Ignore pixel read errors during loop
        
        logger.debug(f"Main game loading screen ({GAME_LOAD_COLOR}) detected. Waiting for it to disappear...")

    # --- STAGE 2: Wait for the main game load screen (22, 26, 55) to disappear ---
    start_time_2 = time.time()
    while current_color == GAME_LOAD_COLOR:
        if stop_event.is_set(): return
        
        if time.time() - start_time_2 > STAGE_2_TIMEOUT:
            logger.warning(f"Stage 2 Timeout: Main game load screen ({GAME_LOAD_COLOR}) did not disappear. Proceeding anyway.")
            return # Timed out, but proceed

        if responsive_sleep(CHECK_INTERVAL, stop_event): return # Interrupted

        try:
            current_color = pyautogui.pixel(stats_x, stats_y) # <-- FIXED
        except Exception:
            pass # Ignore pixel read errors
            
    logger.debug(f"Game UI detected (Pixel {current_color} != {GAME_LOAD_COLOR}). Continuing loop.")
    return


def bot_loop(config, stop_event):
    """
    The main logic loop for the bot, designed to run in a separate thread.
    
    :param config: Dictionary of settings from the GUI.
    :param stop_event: threading.Event() to signal when to stop.
    """
    logger = logging.getLogger(__name__)
    wait_times = config['wait_times']
    
    try:
        qi_region = config['regions']['qi']
        bloodline_region = config['regions']['bloodline']
        
        ranked_list_original = config['ranked_bloodlines']
        ranked_list_lower = config['ranked_bloodlines_lower']
        
        stop_cond = config['stop_conditions']
        stop_on_bloodline = stop_cond['stop_on_bloodline']
        stop_on_qi = stop_cond['stop_on_qi']
        target_index = stop_cond['target_bloodline_index']
        target_qi = stop_cond['target_qi_multi']
        stop_on_new = stop_cond['stop_on_new']
        show_success_popup = stop_cond.get('show_success_popup', True)
        
    except KeyError as e:
        logger.critical(f"Missing key in config: {e}. Halting bot.")
        return

    # --- NEW: Error Circuit Breaker ---
    consecutive_errors = 0
    MAX_CONSECUTIVE_ERRORS = 5

    try:
        # Use file paths from settings_manager (as strings)
        with open(str(settings_manager.QI_HISTORY_FILE), 'a', encoding='utf-8') as qi_log, \
             open(str(settings_manager.BLOODLINE_HISTORY_FILE), 'a', encoding='utf-8') as bloodline_log:
            
            logger.info("Bot loop started. Press F7 to stop.")
            
            is_first_loop = True 
            
            while not stop_event.is_set():
                # --- NEW: Flag for successful cycle ---
                successful_cycle = False
                try:
                    if not is_first_loop:
                        wait_for_game_load(config, stop_event)
                        if stop_event.is_set(): break
                    else:
                        logger.info("First loop, assuming in-game. Skipping load wait.")
                        is_first_loop = False 

                    # Step 1: Go to Stats page
                    logger.debug("Navigating to Stats page...")
                    actions.click_button('stats_button', config, stop_event)
                    
                    if responsive_sleep(wait_times['page_load_delay'], stop_event): break
                    if stop_event.is_set(): break 

                    # Step 2: Read QiMulti and Bloodline
                    logger.debug("Reading stats...")
                    qi_text = vision.read_stat(qi_region)
                    bloodline_text = vision.read_stat(bloodline_region)
                    
                    qi_val = 0.0
                    try:
                        matches = re.findall(r"[\d\.]+", qi_text)
                        if matches:
                            num_str = matches[0]
                            qi_val = float(num_str)
                            if 'k' in qi_text.lower():
                                qi_val *= 1000
                    except Exception as e:
                        logger.warning(f"Could not parse Qi value from '{qi_text}': {e}")
                        
                    bloodline_val = bloodline_text.strip()
                    if ':' in bloodline_val:
                        bloodline_val = bloodline_val.split(':')[-1].strip()
                        
                    cleaned_val = re.sub(r'[^\w\s-]', '', bloodline_val).strip()
                    bloodline_norm = cleaned_val.lower()
                        
                    logger.info(f"Read: Bloodline='{bloodline_val}', Qi={qi_val} (Raw: '{qi_text}')")

                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    qi_log.write(f"{timestamp} - {qi_val} (Raw: {qi_text})\n")
                    qi_log.flush()
                    bloodline_log.write(f"{timestamp} - {bloodline_val}\n")
                    bloodline_log.flush()

                    stop = False
                    found_index = -1
                    
                    try:
                        found_index = ranked_list_lower.index(bloodline_norm)
                    except ValueError:
                        if bloodline_norm and stop_on_new: 
                            logger.info(f"STOPPING: Found new or unlisted bloodline: '{bloodline_val}'")
                            if show_success_popup:
                                logger.critical(f"SUCCESS_POPUP: Found New Bloodline: {bloodline_val}")
                            stop = True
                        elif bloodline_norm and not stop_on_new:
                             logger.warning(f"Found unlisted bloodline: '{bloodline_val}'. 'Stop on New' is OFF. Continuing...")
                        else:
                            logger.warning("Could not read bloodline, will retry.")
                            raise Exception("Bloodline OCR returned empty or invalid string.")

                    if not stop and found_index != -1:
                        if stop_on_bloodline:
                            if found_index <= target_index:
                                target_name = ranked_list_original[target_index]
                                found_name = ranked_list_original[found_index]
                                logger.info(f"STOPPING: Found {found_name} (Rank {found_index}), which is >= target {target_name} (Rank {target_index}).")
                                if show_success_popup:
                                    logger.critical(f"SUCCESS_POPUP: Found Bloodline: {found_name} (Rank {found_index})")
                                stop = True
                            else:
                                logger.debug(f"Found {ranked_list_original[found_index]} (Rank {found_index}). Target rank is {target_index}. Continuing...")
                        
                        if not stop and stop_on_qi:
                            if qi_val >= target_qi:
                                logger.info(f"STOPPING: Found Qi Multi {qi_val}, which is >= target {target_qi}.")
                                if show_success_popup:
                                    logger.critical(f"SUCCESS_POPUP: Found Qi Multi: {qi_val}")
                                stop = True
                            else:
                                logger.debug(f"Found Qi Multi {qi_val}. Target is {target_qi}. Continuing...")

                    if stop:
                        break

                    if not stop_on_bloodline and not stop_on_qi:
                        logger.debug("No stop conditions enabled. Proceeding to reincarnate.")
                    else:
                        logger.debug("Conditions not met. Proceeding to reincarnate.")

                    # Step 3: Go to Options Page
                    logger.debug("Navigating to Options page...")
                    actions.click_button('options_button', config, stop_event)
                    if responsive_sleep(wait_times['page_load_delay'], stop_event): break

                    # Step 4: Find and Click Reincarnate Button
                    logger.debug("Clicking Reincarnate...")
                    actions.click_button('reincarnate_button', config, stop_event)
                    if responsive_sleep(wait_times['page_load_delay'], stop_event): break

                    # Step 5: Click Yes
                    logger.debug("Clicking Yes (Confirm)...")
                    actions.click_button('yes_confirm_button', config, stop_event)
                    if responsive_sleep(wait_times['after_click_delay'], stop_event): break
                    
                    # Step 6: Click Skip Animation (Optional)
                    try:
                        logger.debug("Attempting to skip animation...")
                        actions.click_button('skip_animation_button', config, stop_event, timeout=2.0)
                        if responsive_sleep(wait_times['after_click_delay'], stop_event): break
                    except Exception:
                        logger.warning("Could not find 'Skip Animation' button. Continuing...")

                    # Step 7: Click Final Reincarnate
                    logger.debug("Clicking final Reincarnate...")
                    actions.click_button('reincarnate_final_button', config, stop_event)
                    if responsive_sleep(wait_times['after_click_delay'], stop_event): break
                    
                    if not stop_event.is_set():
                        logger.info("Reincarnation finished. Starting next cycle.")
                    
                    # --- NEW: Mark cycle as successful ---
                    successful_cycle = True

                except Exception as e:
                    if stop_event.is_set():
                        logger.info("Error ignored during shutdown.")
                        break
                    
                    # --- NEW: Circuit Breaker Logic ---
                    if successful_cycle:
                        consecutive_errors = 0 # Reset on first error after success
                    
                    consecutive_errors += 1
                    logger.error(f"An error occurred in the bot loop: {e}")
                    
                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        logger.critical(f"STOPPING: Bot failed {consecutive_errors} times in a row. Halting to prevent issues.")
                        break # Exit the main while loop
                    else:
                        logger.info(f"Attempting to recover by waiting 10s (Error {consecutive_errors}/{MAX_CONSECUTIVE_ERRORS})...")
                        if responsive_sleep(10.0, stop_event): break

    except Exception as e:
        logger.critical(f"A critical error stopped the bot thread: {e}", exc_info=True)
    finally:
        logger.info("Bot loop stopped.")
