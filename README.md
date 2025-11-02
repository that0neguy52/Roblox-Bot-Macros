# Unified Roblox Bot

A unified bot system that combines Forage Bot and Reincarnation Bot functionality into one application with a seamless bot selector interface.

## Features

- **Dual Bot System**: Switch between Forage Bot and Reincarnation Bot
- **Persistent Settings**: Remembers your last used bot and all calibration settings
- **Advanced Detection**: Template matching and RGB-based detection methods
- **Comprehensive Settings**: Full control over mouse behavior, detection, timing, and learning
- **History Tracking**: View and sort bot activity logs
- **User-Friendly GUI**: Dark theme, tooltips, and scrollable settings

## Installation

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd "Bot Hub"
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python main.py
   ```

## Usage

1. **Select Your Bot**: Choose between Forage Bot or Reincarnation Bot
2. **Calibrate**: Set up detection regions and click points
3. **Configure Settings**: Adjust detection, timing, and mouse settings
4. **Start Bot**: Press F7 or click the Start button
5. **Monitor**: View real-time logs and activity

## Bot Features

### Forage Bot
- Template-based button detection
- RGB color detection (for bugged buttons)
- Multi-area patrol system
- False positive learning
- Customizable detection parameters

### Reincarnation Bot
- OCR-based text detection
- Bloodline ranking system
- Stop conditions (Qi multiplier, bloodline rank)
- Automated reincarnation loop

## Settings Management

- **Save Settings**: Manually save current configuration
- **Reset to Default**: Restore factory defaults
- **Save as New Default**: Set current settings as your personal defaults

## Requirements

- Python 3.13+
- Windows OS
- See `requirements.txt` for Python packages

## Project Structure

```
Bot Hub/
├── unified_bot/           # Main application
│   ├── main.py           # Entry point
│   ├── gui.py            # GUI implementation
│   ├── settings_manager.py
│   ├── forage_bot_logic.py
│   ├── rein_bot_logic.py
│   └── ...
├── main.py               # Launcher
├── requirements.txt      # Dependencies
└── README.md            # This file
```

## License

This project is for educational purposes only.

## Contributing

Contributions are welcome! Please feel free to submit pull requests.