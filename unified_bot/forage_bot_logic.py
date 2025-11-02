import time
import logging
import threading
import numpy as np
import pyautogui
import pydirectinput
import cv2
from pynput import mouse
import settings_manager

logger = logging.getLogger(__name__)

# Global state
STRIKE_COUNTS = {}
BLACKLIST = {}


def is_on_blacklist(button_pos_rel, area_blacklist, radius):
    """Check if a position is on the blacklist."""
    for blacklisted_coord in area_blacklist:
        dist = np.sqrt((int(button_pos_rel[0]) - int(blacklisted_coord[0]))**2 + 
                      (int(button_pos_rel[1]) - int(blacklisted_coord[1]))**2)
        if dist < radius:
            return True
    return False


def preprocess_template_edges(image_gray):
    """Preprocess template image for edge detection."""
    if image_gray is None:
        return None
    blurred = cv2.GaussianBlur(image_gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    return edges


def preprocess_haystack_edges(image_gray, g_min, g_max):
    """Preprocess haystack image for edge detection with grayscale filtering."""
    if image_gray is None:
        return None
    mask = cv2.inRange(image_gray, g_min, g_max)
    blurred = cv2.GaussianBlur(mask, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    return edges


def load_template_pyramid(template_path, settings):
    """Load and create a pyramid of scaled templates for matching."""
    canny_templates = []
    scales = np.linspace(settings['scale_min'], settings['scale_max'], settings['scale_steps'])
    
    logger.info(f"Loading template from {template_path}...")
    template_gray = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
    
    if template_gray is None:
        logger.error(f"Could not load template from {template_path}")
        return []

    for scale in scales:
        width = int(template_gray.shape[1] * scale)
        height = int(template_gray.shape[0] * scale)
        if width < 5 or height < 5:
            continue
        
        resized_gray = cv2.resize(template_gray, (width, height), interpolation=cv2.INTER_AREA)
        template_edges = preprocess_template_edges(resized_gray)
        
        canny_templates.append({
            'name': 'template.png',
            'edges': template_edges,
            'width': width,
            'height': height
        })

    logger.info(f"Created pyramid of {len(canny_templates)} scaled templates")
    return canny_templates


def non_max_suppression(boxes, scores, threshold):
    """Apply non-maximum suppression to remove overlapping detections."""
    if len(boxes) == 0:
        return []
    
    x1, y1, x2, y2 = boxes[:,0], boxes[:,1], boxes[:,2], boxes[:,3]
    areas = (x2-x1+1)*(y2-y1+1)
    order = scores.argsort()[::-1]
    keep = []
    
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1, yy1 = np.maximum(x1[i], x1[order[1:]]), np.maximum(y1[i], y1[order[1:]])
        xx2, yy2 = np.minimum(x2[i], x2[order[1:]]), np.minimum(y2[i], y2[order[1:]])
        w, h = np.maximum(0.0, xx2-xx1+1), np.maximum(0.0, yy2-yy1+1)
        inter = w*h
        iou = inter/(areas[i] + areas[order[1:]] - inter)
        inds = np.where(iou <= threshold)[0]
        order = order[inds+1]
    
    return keep


def find_buttons_advanced(canny_templates, region, settings):
    """Find buttons in a region using template matching."""
    try:
        screenshot_pil = pyautogui.screenshot(region=region)
        screenshot_bgr = cv2.cvtColor(np.array(screenshot_pil), cv2.COLOR_RGB2BGR)
        screenshot_gray = cv2.cvtColor(screenshot_bgr, cv2.COLOR_BGR2GRAY)
        
        haystack_edges = preprocess_haystack_edges(screenshot_gray, 
                                                   settings['grayscale_min'], 
                                                   settings['grayscale_max'])
        
        if haystack_edges is None:
            return []

        detections = []
        for template in canny_templates:
            t_w, t_h = template['width'], template['height']
            if t_w > haystack_edges.shape[1] or t_h > haystack_edges.shape[0]:
                continue
            if template['edges'] is None:
                continue

            res = cv2.matchTemplate(haystack_edges, template['edges'], cv2.TM_CCOEFF_NORMED)
            
            loc = np.where(res >= settings['detection_threshold'])
            for pt in zip(*loc[::-1]):
                score = res[pt[1], pt[0]]
                box = (pt[0], pt[1], pt[0] + t_w, pt[1] + t_h)
                detections.append({'box': box, 'score': score})
        
        if not detections:
            return []

        boxes = np.array([d['box'] for d in detections])
        scores = np.array([d['score'] for d in detections])
        indices_to_keep = non_max_suppression(boxes, scores, settings['nms_threshold'])
        
        final_buttons = []
        for i in indices_to_keep:
            box = boxes[i]
            center_x_rel = box[0] + (box[2] - box[0]) // 2
            center_y_rel = box[1] + (box[3] - box[1]) // 2
            center_x_abs = region[0] + center_x_rel
            center_y_abs = region[1] + center_y_rel
            
            final_buttons.append({
                'pos': (center_x_abs, center_y_abs),
                'center_rel': (center_x_rel, center_y_rel),
                'score': scores[i],
                'box_rel': box
            })
        
        return final_buttons
        
    except Exception as e:
        logger.error(f"Error in find_buttons_advanced: {e}")
        return []


def safe_human_click(pos, settings, stop_event):
    """Move mouse and click with human-like movement."""
    try:
        factor = settings['mouse_speed_factor']
        snap_distance = settings['mouse_snap_distance']
    except KeyError:
        factor = 0.3
        snap_distance = 5
        
    target_x, target_y = int(pos[0]), int(pos[1])
    
    while True:
        if stop_event.is_set():
            return
        
        current_x, current_y = pydirectinput.position()
        
        remaining_x = target_x - current_x
        remaining_y = target_y - current_y
        
        distance = max(abs(remaining_x), abs(remaining_y))
        
        if distance < snap_distance:
            break
            
        move_x = np.round(remaining_x * factor)
        move_y = np.round(remaining_y * factor)
        
        if move_x == 0 and remaining_x != 0:
            move_x = 1 if remaining_x > 0 else -1
        if move_y == 0 and remaining_y != 0:
            move_y = 1 if remaining_y > 0 else -1
            
        pydirectinput.moveRel(int(move_x), int(move_y), relative=True)
        time.sleep(0.001)

    final_x, final_y = pydirectinput.position()
    final_move_x = target_x - final_x
    final_move_y = target_y - final_y
    if final_move_x != 0 or final_move_y != 0:
        pydirectinput.moveRel(final_move_x, final_move_y, relative=True)
        
    pydirectinput.click()


def go_to_start_position(left_arrow_pos, total_areas, load_delay, settings, stop_event):
    """Navigate to the starting position (Area 1)."""
    logger.info("Moving to starting position (Area 1)...")
    for i in range(total_areas):
        if stop_event.is_set():
            return False
        logger.debug(f"Going left... ({i+1}/{total_areas})")
        safe_human_click(left_arrow_pos, settings, stop_event)
        time.sleep(load_delay)
    logger.info("Reached starting position")
    return True


def save_learning_data(settings_file):
    """Save strike counts and blacklist to settings file."""
    global STRIKE_COUNTS, BLACKLIST
    try:
        settings = settings_manager.load_settings(settings_file, 
                                                  settings_manager.get_forage_default_settings())
        settings['strike_counts'] = STRIKE_COUNTS
        settings['blacklist'] = BLACKLIST
        settings_manager.save_settings(settings_file, settings)
    except Exception as e:
        logger.error(f"Could not save learning data: {e}")


def forage_bot_loop(config, stop_event, template_path):
    """
    Main forage bot loop.
    
    :param config: Dictionary of settings
    :param stop_event: threading.Event() to signal when to stop
    :param template_path: Path to the template image
    """
    global STRIKE_COUNTS, BLACKLIST
    
    logger.info("Forage bot loop starting...")
    
    # Load learning data from settings
    STRIKE_COUNTS = config.get('strike_counts', {})
    BLACKLIST = config.get('blacklist', {})
    
    try:
        game_region = tuple(config['search_region'])
        left_arrow_pos = tuple(config['left_arrow_pos'])
        right_arrow_pos = tuple(config['right_arrow_pos'])
        all_templates = load_template_pyramid(template_path, config)
    except Exception as e:
        logger.error(f"Failed to load calibrated settings: {e}")
        return

    current_area = 1
    movement_direction = 'right'
    recent_clicks = []
    first_run = True

    while not stop_event.is_set():
        try:
            now = time.time()
            recent_clicks = [c for c in recent_clicks if now - c[2] < config['click_cooldown_seconds']]
            
            if first_run:
                if not go_to_start_position(left_arrow_pos, config['total_areas'], 
                                          config['area_load_delay'], config, stop_event):
                    time.sleep(0.1)
                    continue
                current_area = 1
                movement_direction = 'right'
                first_run = False
            
            try:
                area_key = str(current_area)
                area_blacklist = BLACKLIST.get(area_key, [])
                radius = config['blacklist_radius']
                
                all_found_buttons = find_buttons_advanced(all_templates, game_region, config)
                
                found_buttons = []
                for btn in all_found_buttons:
                    if not is_on_blacklist(btn['center_rel'], area_blacklist, radius):
                        found_buttons.append(btn)
                
                buttons_to_click = []
                if found_buttons:
                    for button in found_buttons:
                        is_on_cooldown = False
                        (x, y) = button['center_rel']
                        for (cx, cy, timestamp) in recent_clicks:
                            distance = np.sqrt((x - cx)**2 + (y - cy)**2)
                            if distance < 30:
                                is_on_cooldown = True
                                break
                        if not is_on_cooldown:
                            buttons_to_click.append(button)
                
                action_taken = False
                
                if buttons_to_click:
                    action_taken = True
                    logger.info(f"Found {len(buttons_to_click)} new targets. Optimizing click path...")
                    
                    current_mouse_pos = pydirectinput.position()
                    remaining_buttons = list(buttons_to_click)
                    
                    learning_data_changed = False
                    
                    while remaining_buttons and not stop_event.is_set():
                        def get_sq_distance(p1, p2):
                            return (int(p1[0]) - int(p2[0]))**2 + (int(p1[1]) - int(p2[1]))**2
                        
                        remaining_buttons.sort(key=lambda b: get_sq_distance(current_mouse_pos, b['pos']))
                        
                        button = remaining_buttons.pop(0)
                        
                        clean_pos = (int(button['pos'][0]), int(button['pos'][1]))
                        logger.info(f"Clicking button at {clean_pos} (Confidence: {button['score']:.2f})")
                        
                        safe_human_click(button['pos'], config, stop_event)
                        
                        current_mouse_pos = button['pos']
                        
                        recent_clicks.append((button['center_rel'][0], button['center_rel'][1], time.time()))
                        time.sleep(config['post_click_delay'])
                        
                        if stop_event.is_set():
                            break
                        
                        box = button['box_rel']
                        padding = 10
                        
                        box_left_rel = int(box[0]) - padding
                        box_top_rel = int(box[1]) - padding
                        box_width = (int(box[2]) - int(box[0])) + padding * 2
                        box_height = (int(box[3]) - int(box[1])) + padding * 2

                        r_left = int(max(game_region[0], game_region[0] + box_left_rel))
                        r_top = int(max(game_region[1], game_region[1] + box_top_rel))
                        r_width = int(box_width)
                        r_height = int(box_height)
                        
                        rescan_box_abs = (r_left, r_top, r_width, r_height)
                        
                        rescan_matches = find_buttons_advanced(all_templates, rescan_box_abs, config)
                        
                        if len(rescan_matches) > 0:
                            learning_data_changed = True

                            clean_rel_pos = (int(button['center_rel'][0]), int(button['center_rel'][1]))
                            
                            coord_key = f"{clean_rel_pos[0]},{clean_rel_pos[1]}"
                            
                            area_strikes = STRIKE_COUNTS.get(area_key, {})
                            
                            current_strikes = area_strikes.get(coord_key, 0) + 1
                            area_strikes[coord_key] = current_strikes
                            STRIKE_COUNTS[area_key] = area_strikes
                            
                            logger.warning(f"False positive at {clean_pos}. Strike {current_strikes}/{config['strike_limit']}")
                            
                            if current_strikes >= config['strike_limit']:
                                logger.info(f"Blacklisting spot {clean_rel_pos} for Area {area_key}")
                                area_blacklist.append(clean_rel_pos)
                                BLACKLIST[area_key] = area_blacklist

                    if learning_data_changed:
                        save_learning_data(settings_manager.FORAGE_SETTINGS_FILE)
                
                if action_taken:
                    logger.debug("Action taken. Re-scanning area")
                    continue

                logger.info(f"Area {current_area} clear. Moving...")
                recent_clicks = []
                
                if current_area >= config['total_areas'] and movement_direction == 'right':
                    movement_direction = 'left'
                    logger.debug("Reached rightmost area. Swapping to LEFT")
                elif current_area <= 1 and movement_direction == 'left':
                    movement_direction = 'right'
                    logger.debug("Reached leftmost area. Swapping to RIGHT")

                if movement_direction == 'right':
                    logger.debug(f"Moving RIGHT to Area {current_area + 1}")
                    safe_human_click(right_arrow_pos, config, stop_event)
                    current_area += 1
                else:
                    logger.debug(f"Moving LEFT to Area {current_area - 1}")
                    safe_human_click(left_arrow_pos, config, stop_event)
                    current_area -= 1
                
                logger.debug("Waiting for new area to load...")
                time.sleep(config['area_load_delay'])
            
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(5)
            
            time.sleep(config['scan_interval'])
            
        except Exception as e:
            logger.error(f"Critical thread error: {e}")
            time.sleep(5)
            
    logger.info("Forage bot loop stopped")