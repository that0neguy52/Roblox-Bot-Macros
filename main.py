"""
Unified Roblox Bot Launcher
Launches the unified bot GUI with bot selector
"""

import sys
from pathlib import Path

# Add unified_bot directory to path
unified_bot_dir = Path(__file__).parent / "unified_bot"
sys.path.insert(0, str(unified_bot_dir))

# Import and run the main GUI
from main import main

if __name__ == "__main__":
    main()