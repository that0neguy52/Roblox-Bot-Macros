import json
import os
from pathlib import Path

# --- Relocate ALL User-Generated Files to Documents Folder ---
try:
    documents_path = Path.home() / 'Documents'
    LOG_DIR = documents_path / 'Unified Bot Logs'
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Config Files
    FORAGE_SETTINGS_FILE = LOG_DIR / "forage_settings.json"
    REIN_SETTINGS_FILE = LOG_DIR / "rein_settings.json"
    BLOODLINES_FILE = LOG_DIR / "bloodlines.json"
    
    # Log Files
    QI_HISTORY_FILE = LOG_DIR / "qi_rates.log"
    BLOODLINE_HISTORY_FILE = LOG_DIR / "bloodlines.log"
    FORAGE_HISTORY_FILE = LOG_DIR / "forage_history.log"
except Exception:
    # Fallback to current directory if finding Documents fails
    FORAGE_SETTINGS_FILE = Path("forage_settings.json")
    REIN_SETTINGS_FILE = Path("rein_settings.json")
    BLOODLINES_FILE = Path("bloodlines.json")
    QI_HISTORY_FILE = Path("qi_rates.log")
    BLOODLINE_HISTORY_FILE = Path("bloodlines.log")
    FORAGE_HISTORY_FILE = Path("forage_history.log")


def load_settings(settings_file, default_settings):
    """
    Load settings from a JSON file, or create it with defaults if it doesn't exist.
    
    :param settings_file: Path to the settings file
    :param default_settings: Dictionary of default settings
    :return: Dictionary of settings
    """
    try:
        if os.path.exists(str(settings_file)):
            with open(str(settings_file), 'r') as f:
                return json.load(f)
        else:
            # Create default settings file
            with open(str(settings_file), 'w') as f:
                json.dump(default_settings, f, indent=4)
            return default_settings
    except Exception as e:
        print(f"Error loading settings from {settings_file}: {e}")
        return default_settings


def save_settings(settings_file, settings):
    """
    Save settings to a JSON file.
    
    :param settings_file: Path to the settings file
    :param settings: Dictionary of settings to save
    """
    try:
        with open(str(settings_file), 'w') as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        print(f"Error saving settings to {settings_file}: {e}")


def get_forage_default_settings():
    """Returns default settings for the forage bot."""
    return {
        "search_region": None,
        "left_arrow_pos": None,
        "right_arrow_pos": None,
        "detection_threshold": 0.25,
        "nms_threshold": 0.3,
        "grayscale_min": 245,
        "grayscale_max": 255,
        "scale_min": 0.8,
        "scale_max": 1.2,
        "scale_steps": 20,
        "post_click_delay": 1.8,
        "scan_interval": 0.01,
        "area_load_delay": 1.0,
        "click_cooldown_seconds": 5.0,
        "total_areas": 6,
        "startup_delay": 3,
        "mouse_speed_factor": 0.3,
        "mouse_snap_distance": 15,
        "strike_limit": 5,
        "blacklist_radius": 5,
        "strike_counts": {},
        "blacklist": {}
    }


def get_rein_default_settings():
    """Returns default settings for the reincarnation bot."""
    return {
        "qi_region": None,
        "bloodline_region": None,
        "calibrated_points": {},
        "ui_mode": "dark",
        "mouse_speed_factor": 0.15,
        "mouse_snap_threshold": 25,
        "mouse_variability": 3,
        "after_click_delay": 1.5,
        "stop_on_bloodline": True,
        "stop_on_qi": False,
        "target_bloodline_index": 0,
        "target_qi_multi": 200.0,
        "stop_on_new": True,
        "show_success_popup": True,
        "font_name": "TkDefaultFont",
        "font_size": 10,
        "clear_on_start": False,
        "log_level": "User",
        "hotkey_name": "F7",
        "hotkey_code": 118
    }