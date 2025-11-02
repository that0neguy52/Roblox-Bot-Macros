import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, font
import threading
import queue
import logging
import json
import os
import webbrowser
import re
import pyautogui
from unified_bot.calibration import CalibrationWindow, CalibrationClickWindow
import unified_bot.gui_logger as gui_logger
import unified_bot.rein_bot_logic as rein_bot_logic
import unified_bot.forage_bot_logic as forage_bot_logic
import unified_bot.settings_manager as settings_manager
from pathlib import Path
from pynput import mouse
import cv2
import numpy as np

# --- TOOLTIP CLASS ---
class ToolTip:
    """Simple tooltip class for tkinter widgets."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)
    
    def show_tooltip(self, event=None):
        if self.tooltip_window or not self.text:
            return
        x, y, _, _ = self.widget.bbox("insert") if hasattr(self.widget, 'bbox') else (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                        background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                        font=("TkDefaultFont", 9))
        label.pack(ipadx=1)
    
    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

# --- DEFAULT BLOODLINE DATA (Fallback) ---
DEFAULT_BLOODLINES_DATA = [
    ("Celestial Dragon", "20x Qi"), ("Buddha", "10x Qi"),
    ("The Sealed Demon", "5x Qi"), ("Heaven Devourer", "5x Qi"),
    ("Unbounded Astral Body", "4x Qi"), ("Primordial Phoenix", "4x Qi"),
    ("Bounded Astral Body", "3.5x Qi"), ("Martial Emperor", "3.45x Qi"),
    ("Golden Kirin", "3x Qi"), ("Eclipse Serpent", "3x Qi"),
    ("Celestial", "3x Qi"), ("Silver Wolf", "3x Qi"),
    ("Abyssal Monarch", "2.5x Qi"), ("Vengeful Ghost", "2.5x Qi"),
    ("Demon Sovereign", "2.5x Qi"), ("Azure Dragon", "2x Qi"),
    ("Chaos Fiend", "2x Qi"), ("Red Tiger", "2x Qi"),
    ("Spirit Fox", "2x Qi"), ("Demon King", "1.5x Qi"),
    ("Crimson Demon", "1.5x Qi"), ("Fallen Saint", "1.25x Qi"),
    ("Martial King", "1.2x Qi"), ("Hero", "1.2x Qi"),
    ("Frost Wyvern", "No Qi"), ("Heavenly Tiger", "No Qi"),
    ("Invincible Vajra", "No Qi"), ("High-tier Demon", "No Qi"),
    ("Middle-tier Demon", "No Qi"), ("Low-tier Demon", "No Qi"),
    ("High-tier Saint", "No Qi"), ("Middle-tier Saint", "No Qi"),
    ("Low-tier Saint", "No Qi"), ("Ancient Mortal", "No Qi"),
    ("Mortal", "No Qi"), ("Default Body", "No Qi")
]


class UnifiedBotGUI:
    """
    The main GUI class for the unified bot, built with Tkinter.
    Supports both Reincarnation and Forage bots with dynamic tab switching.
    """
    def __init__(self, root):
        self.root = root
        self.root.title("Unified Bot Control")
        self.root.configure(bg="#2E2E2E")
        self.root.geometry("700x900")

        self.log_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.bot_thread = None
        self.bot_thread_stopped_logged = True
        
        # Bot selection
        self.selected_bot = tk.StringVar(value="reincarnation")
        
        gui_logger.setup_logging(self.log_queue)
        self.logger = logging.getLogger(__name__)
        self.log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # Reincarnation bot data
        self.ranked_bloodlines_data = []
        self.ranked_bloodlines = []
        self.combobox_values = []
        self.ranked_bloodlines_lower = []
        self.load_bloodlines()

        # Settings variables (shared)
        self.ui_mode_var = tk.StringVar(value="dark")
        self.font_name_var = tk.StringVar(value="TkDefaultFont")
        self.font_size_var = tk.IntVar(value=10)
        self.log_level_var = tk.StringVar(value="User")
        self.clear_on_start_var = tk.BooleanVar(value=False)
        self.hotkey_name_var = tk.StringVar(value="F7")
        self.hotkey_code_var = tk.IntVar(value=118)
        self.history_sort_newest_first = tk.BooleanVar(value=True)
        
        # Reincarnation bot settings
        self.qi_region = None
        self.bloodline_region = None
        self.calibrated_points = {}
        self.stop_on_bloodline_var = tk.BooleanVar(value=True)
        self.stop_on_qi_var = tk.BooleanVar(value=False)
        self.qi_stop_var = tk.DoubleVar(value=200.0)
        self.stop_on_new_var = tk.BooleanVar(value=True)
        self.show_success_popup_var = tk.BooleanVar(value=True)
        self.speed_factor_var = tk.DoubleVar(value=0.15)
        self.snap_threshold_var = tk.IntVar(value=25)
        self.variability_var = tk.IntVar(value=3)
        self.after_click_delay_var = tk.DoubleVar(value=1.5)
        
        # Forage bot settings
        self.forage_search_region = None
        self.forage_left_arrow = None
        self.forage_right_arrow = None
        self.forage_detection_method = tk.StringVar(value="Template Matching")
        self.forage_detection_threshold = tk.DoubleVar(value=0.25)
        self.forage_mouse_speed = tk.DoubleVar(value=0.3)
        self.forage_total_areas = tk.IntVar(value=6)
        self.forage_post_click_delay = tk.DoubleVar(value=1.8)
        
        # RGB Detection Settings
        self.forage_rgb_target_r = tk.IntVar(value=255)
        self.forage_rgb_target_g = tk.IntVar(value=255)
        self.forage_rgb_target_b = tk.IntVar(value=255)
        self.forage_rgb_tolerance = tk.IntVar(value=1)
        self.forage_rgb_min_cluster = tk.IntVar(value=10)
        self.forage_rgb_max_cluster = tk.IntVar(value=1000)
        
        # False Positive Learning Settings
        self.forage_strike_limit = tk.IntVar(value=5)
        self.forage_blacklist_radius = tk.IntVar(value=5)
        
        # Detection Settings
        self.forage_nms_threshold = tk.DoubleVar(value=0.3)
        self.forage_grayscale_min = tk.IntVar(value=245)
        self.forage_grayscale_max = tk.IntVar(value=255)
        self.forage_scale_min = tk.DoubleVar(value=0.8)
        self.forage_scale_max = tk.DoubleVar(value=1.2)
        self.forage_scale_steps = tk.IntVar(value=20)
        
        # Timing Settings
        self.forage_scan_interval = tk.DoubleVar(value=0.01)
        self.forage_area_load_delay = tk.DoubleVar(value=1.0)
        self.forage_click_cooldown = tk.DoubleVar(value=5.0)
        self.forage_startup_delay = tk.IntVar(value=3)
        
        # Mouse Settings (additional)
        self.forage_snap_distance = tk.IntVar(value=15)
        self.forage_variability = tk.IntVar(value=3)

        self.scale_x = 1.0
        self.scale_y = 1.0
        self.calculate_display_scaling()

        self.style = ttk.Style()
        
        self.load_settings()
        
        gui_logger.set_gui_log_level(self.log_level_var.get())
        
        self.create_styles()
        self.create_widgets()
        self.apply_font_settings(log_errors=False)
        
        self.update_calibration_labels()
        self.update_bloodline_combobox()
        
        self.update_status("Idle", "#FAFAFA")
        
        self.root.after(100, self.check_log_queue)
        self.logger.info("GUI Initialized. Ready to start.")
        self.logger.info(f"Settings and logs are being saved to: {settings_manager.LOG_DIR}")
        
    def run_clear_on_start(self):
        """Called by main.py before root.mainloop()"""
        if self.clear_on_start_var.get():
            self.logger.info("Clearing history logs on startup...")
            try:
                with open(str(settings_manager.QI_HISTORY_FILE), 'w', encoding='utf-8') as f:
                    pass
                with open(str(settings_manager.BLOODLINE_HISTORY_FILE), 'w', encoding='utf-8') as f:
                    pass
                with open(str(settings_manager.FORAGE_HISTORY_FILE), 'w', encoding='utf-8') as f:
                    pass
                self.logger.info("History logs cleared.")
            except Exception as e:
                self.logger.error(f"Failed to clear history logs: {e}")

    def calculate_display_scaling(self):
        try:
            physical_width, physical_height = pyautogui.size()
            tk_width, tk_height = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            
            if physical_width != tk_width or physical_height != tk_height:
                self.scale_x = physical_width / tk_width
                self.scale_y = physical_height / tk_height
                if self.scale_x != 1.0 or self.scale_y != 1.0:
                    self.logger.info(f"Display scaling: X={self.scale_x}, Y={self.scale_y}")
                else:
                    self.logger.info("Display scaling: X=1.0, Y=1.0")
            else:
                self.logger.info("Display scaling: X=1.0, Y=1.0")
        except Exception as e:
            self.logger.error(f"Could not calculate display scaling: {e}")
            self.scale_x = 1.0
            self.scale_y = 1.0

    def create_styles(self):
        self.style.theme_use('clam')
        dark_bg = "#2E2E2E"
        light_text = "#FAFAFA"
        widget_bg = "#3E3E3E"
        border_color = "#555555"
        select_bg = "#5E5E5E"
        
        font_name = self.font_name_var.get()
        font_size = self.font_size_var.get()
        
        self.style.configure(".", background=dark_bg, foreground=light_text, fieldbackground=widget_bg, bordercolor=border_color, font=(font_name, font_size))
        self.style.configure("TLabel", background=dark_bg, foreground=light_text)
        self.style.configure("TFrame", background=dark_bg)
        self.style.configure("TButton", background=widget_bg, foreground=light_text, borderwidth=1)
        self.style.map("TButton", background=[('active', select_bg)], foreground=[('active', light_text)])
        self.style.configure("TEntry", fieldbackground=widget_bg, foreground=light_text, insertcolor=light_text)
        self.style.configure("TSpinbox", fieldbackground=widget_bg, foreground=light_text)
        self.style.configure("TCombobox", fieldbackground=widget_bg, foreground=light_text)
        self.style.configure("Vertical.TScrollbar", background=widget_bg, troughcolor=dark_bg)
        self.style.map("TCombobox", fieldbackground=[('readonly', widget_bg)], foreground=[('readonly', light_text)])
        self.style.configure("TCheckbutton", background=dark_bg, foreground=light_text, indicatorcolor=widget_bg)
        self.style.map("TCheckbutton", indicatorcolor=[('active', select_bg)])
        self.style.configure("TRadiobutton", background=dark_bg, foreground=light_text, indicatorcolor=widget_bg)
        self.style.map("TRadiobutton", indicatorcolor=[('active', select_bg)])
        self.style.configure("TNotebook", background=dark_bg, borderwidth=0)
        self.style.configure("TNotebook.Tab", background=widget_bg, foreground=light_text, borderwidth=0, padding=[10, 5])
        self.style.map("TNotebook.Tab", background=[("selected", select_bg), ("active", select_bg)])
        self.style.configure("Link.TLabel", foreground="#6e9ceb", background=dark_bg)
        self.style.configure("Status.TFrame", background=widget_bg)
        self.style.configure("Status.TLabel", background=widget_bg)

    def create_widgets(self):
        """Creates and lays out all widgets in the window."""
        
        # Main frame for Notebook and Log
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Bot selector at the top
        selector_frame = ttk.Frame(main_frame, padding=10)
        selector_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(selector_frame, text="Select Bot:", font=(self.font_name_var.get(), 12, 'bold')).pack(side=tk.LEFT, padx=5)
        
        ttk.Radiobutton(selector_frame, text="Reincarnation Bot", variable=self.selected_bot, 
                       value="reincarnation", command=self.on_bot_selection_changed).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(selector_frame, text="Forage Bot", variable=self.selected_bot, 
                       value="forage", command=self.on_bot_selection_changed).pack(side=tk.LEFT, padx=10)

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.main_settings_tab = ttk.Frame(self.notebook, padding=10)
        self.calibration_tab = ttk.Frame(self.notebook, padding=10)
        self.bloodline_editor_tab = ttk.Frame(self.notebook, padding=10)
        self.history_tab = ttk.Frame(self.notebook, padding=10)
        self.appearance_tab = ttk.Frame(self.notebook, padding=10)
        
        self.notebook.add(self.main_settings_tab, text="Bot Settings")
        self.notebook.add(self.calibration_tab, text="Calibration")
        self.notebook.add(self.bloodline_editor_tab, text="Bloodline Editor")
        self.notebook.add(self.history_tab, text="History")
        self.notebook.add(self.appearance_tab, text="Appearance")

        self.create_main_settings_widgets(self.main_settings_tab)
        self.create_calibration_widgets(self.calibration_tab)
        self.create_bloodline_editor_widgets(self.bloodline_editor_tab)
        self.create_history_widgets(self.history_tab)
        self.create_appearance_widgets(self.appearance_tab)

        log_frame = ttk.Labelframe(main_frame, text="Logs", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, state=tk.DISABLED, bg="#3E3E3E", fg="#FAFAFA", border=1, relief="solid")
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=5)
        self.log_text.config(font=(self.font_name_var.get(), self.font_size_var.get()))
        # Fix Issue 1: Stop log widget scroll from propagating to settings canvas
        self.log_text.bind("<MouseWheel>", lambda e: "break")

        # Status Bar
        status_bar_frame = ttk.Frame(self.root, style="Status.TFrame", height=25)
        status_bar_frame.pack(fill=tk.X, side=tk.BOTTOM, ipady=2)
        
        self.status_label = ttk.Label(
            status_bar_frame,
            text="Status: Initializing...",
            style="Status.TLabel",
            padding=(5, 0)
        )
        self.status_label.pack(side=tk.LEFT, fill=tk.X)
        
        # Update tab visibility based on initial selection
        self.on_bot_selection_changed()

    def on_bot_selection_changed(self):
        """Called when bot selection changes - shows/hides appropriate tabs."""
        selected = self.selected_bot.get()
        
        # Clear the current tab content (only if widgets have been created)
        if hasattr(self, 'main_settings_tab'):
            for widget in self.main_settings_tab.winfo_children():
                widget.destroy()
        if hasattr(self, 'calibration_tab'):
            for widget in self.calibration_tab.winfo_children():
                widget.destroy()
            
        if selected == "reincarnation":
            # Show bloodline editor tab
            try:
                self.notebook.tab(2, state=tk.NORMAL)
            except:
                pass
            self.create_rein_settings_widgets(self.main_settings_tab)
            self.create_rein_calibration_widgets(self.calibration_tab)
        else:  # forage
            # Hide bloodline editor tab
            try:
                self.notebook.tab(2, state=tk.HIDDEN)
            except:
                pass
            self.create_forage_settings_widgets(self.main_settings_tab)
            self.create_forage_calibration_widgets(self.calibration_tab)
        
        # Update history combo options based on selected bot
        if hasattr(self, 'history_combo'):
            filtered_options = self.get_filtered_history_options()
            self.history_combo.config(values=filtered_options)
            if filtered_options:
                self.history_combo.current(0)

    def create_main_settings_widgets(self, parent):
        """Placeholder - will be replaced by bot-specific widgets."""
        pass

    def create_rein_settings_widgets(self, parent):
        """Create reincarnation bot settings widgets."""
        # Fix Issue 2: Reincarnation bot doesn't need scrollbar - removed canvas/scrollbar
        scrollable_frame = ttk.Frame(parent)
        scrollable_frame.pack(fill=tk.BOTH, expand=True)
        
        controls_frame = ttk.Frame(scrollable_frame)
        controls_frame.pack(fill=tk.X, pady=5)
        controls_frame.columnconfigure(0, weight=1)
        controls_frame.columnconfigure(1, weight=1)
        
        hotkey_name = self.hotkey_name_var.get()
        self.start_button = ttk.Button(controls_frame, text=f"Start Bot ({hotkey_name})", command=self.start_bot)
        self.start_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.stop_button = ttk.Button(controls_frame, text=f"Stop Bot ({hotkey_name})", command=self.stop_bot, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # Settings management buttons for Reincarnation bot (moved under Start/Stop)
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill=tk.X, pady=5)
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        button_frame.columnconfigure(2, weight=1)
        
        ttk.Button(button_frame, text="Save Settings", command=self.manual_save_settings).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ttk.Button(button_frame, text="Reset to Default", command=self.reset_to_defaults).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(button_frame, text="Save as New Default", command=self.save_as_default).grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        
        stop_frame = ttk.Labelframe(scrollable_frame, text="Stop Conditions", padding=10)
        stop_frame.pack(fill=tk.X, pady=5)
        stop_frame.columnconfigure(1, weight=1)

        self.stop_on_bloodline_check = ttk.Checkbutton(
            stop_frame, text="Enable", variable=self.stop_on_bloodline_var, onvalue=True, offvalue=False
        )
        self.stop_on_bloodline_check.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        ttk.Label(stop_frame, text="Stop at this bloodline (or better):").grid(row=0, column=1, padx=5, pady=(5,0), sticky="nw")
        self.bloodline_stop_combo = ttk.Combobox(
            stop_frame,
            values=self.combobox_values,
            state="readonly",
            width=30
        )
        self.bloodline_stop_combo.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        
        self.stop_on_qi_check = ttk.Checkbutton(
            stop_frame, text="Enable", variable=self.stop_on_qi_var, onvalue=True, offvalue=False
        )
        self.stop_on_qi_check.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        
        ttk.Label(stop_frame, text="Stop Qi Multi (>=):").grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.qi_stop_entry = ttk.Spinbox(
            stop_frame, from_=1.0, to=1000.0, increment=0.1, textvariable=self.qi_stop_var
        )
        self.qi_stop_entry.grid(row=1, column=2, padx=5, pady=5, sticky="ew")
        # Fix Issue 3: Stop spinbox scroll from propagating
        self.qi_stop_entry.bind("<MouseWheel>", lambda e: "break")

        self.stop_on_new_check = ttk.Checkbutton(
            stop_frame, text="Stop if a new/unlisted bloodline is found",
            variable=self.stop_on_new_var, onvalue=True, offvalue=False
        )
        self.stop_on_new_check.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="w")
        
        self.show_success_popup_check = ttk.Checkbutton(
            stop_frame, text="Show popup window on success",
            variable=self.show_success_popup_var, onvalue=True, offvalue=False
        )
        self.show_success_popup_check.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky="w")
        
        mouse_frame = ttk.Labelframe(scrollable_frame, text="Mouse Settings", padding=10)
        mouse_frame.pack(fill=tk.X, pady=5)
        mouse_frame.columnconfigure(1, weight=1)
        
        ttk.Label(mouse_frame, text="Speed Factor (0.1-0.5):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.speed_factor_entry = ttk.Spinbox(mouse_frame, from_=0.1, to=0.5, increment=0.05, textvariable=self.speed_factor_var, format="%.2f")
        self.speed_factor_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.speed_factor_entry.bind("<MouseWheel>", lambda e: "break")
        
        ttk.Label(mouse_frame, text="Snap Threshold (px):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.snap_dist_entry = ttk.Spinbox(mouse_frame, from_=1, to=50, increment=1, textvariable=self.snap_threshold_var)
        self.snap_dist_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.snap_dist_entry.bind("<MouseWheel>", lambda e: "break")
        
        ttk.Label(mouse_frame, text="Variability (px):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.variability_entry = ttk.Spinbox(mouse_frame, from_=0, to=10, increment=1, textvariable=self.variability_var)
        self.variability_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        self.variability_entry.bind("<MouseWheel>", lambda e: "break")
        
        ttk.Label(mouse_frame, text="Delay After Click (s):").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.after_click_delay_entry = ttk.Spinbox(mouse_frame, from_=0.1, to=5.0, increment=0.1, textvariable=self.after_click_delay_var, format="%.1f")
        self.after_click_delay_entry.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        self.after_click_delay_entry.bind("<MouseWheel>", lambda e: "break")

    def create_forage_settings_widgets(self, parent):
        """Create forage bot settings widgets."""
        # Create canvas and scrollbar for scrollable content
        canvas = tk.Canvas(parent, bg="#2E2E2E", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Enable mousewheel scrolling with safety check
        def _on_mousewheel(event):
            """Handle mousewheel scrolling"""
            # Check if canvas exists and is valid
            if canvas.winfo_exists():
                try:
                    canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                except tk.TclError:
                    pass  # Canvas no longer exists, ignore
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        controls_frame = ttk.Frame(scrollable_frame)
        controls_frame.pack(fill=tk.X, pady=5)
        controls_frame.columnconfigure(0, weight=1)
        controls_frame.columnconfigure(1, weight=1)
        
        hotkey_name = self.hotkey_name_var.get()
        self.start_button = ttk.Button(controls_frame, text=f"Start Bot ({hotkey_name})", command=self.start_bot)
        self.start_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.stop_button = ttk.Button(controls_frame, text=f"Stop Bot ({hotkey_name})", command=self.stop_bot, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # Settings management buttons for Forage bot (moved under Start/Stop)
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill=tk.X, pady=5)
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        button_frame.columnconfigure(2, weight=1)
        
        ttk.Button(button_frame, text="Save Settings", command=self.manual_save_settings).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ttk.Button(button_frame, text="Reset to Default", command=self.reset_to_defaults).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(button_frame, text="Save as New Default", command=self.save_as_default).grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        
        # Detection Method Selection
        method_frame = ttk.Labelframe(scrollable_frame, text="Detection Method", padding=10)
        method_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Radiobutton(method_frame, text="Template Matching",
                        variable=self.forage_detection_method,
                        value="Template Matching",
                        command=self.on_detection_method_changed).pack(side="left", padx=10)
        ttk.Radiobutton(method_frame, text="RGB Color Detection",
                        variable=self.forage_detection_method,
                        value="RGB Color Detection",
                        command=self.on_detection_method_changed).pack(side="left", padx=10)
        
        # Mouse Settings (shared between both methods)
        mouse_frame = ttk.Labelframe(scrollable_frame, text="Mouse Settings", padding=10)
        mouse_frame.pack(fill=tk.X, pady=5)
        mouse_frame.columnconfigure(1, weight=1)
        
        ttk.Label(mouse_frame, text="Mouse Speed (0.1-1.0):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        mouse_speed_spin = ttk.Spinbox(mouse_frame, from_=0.1, to=1.0, increment=0.05, textvariable=self.forage_mouse_speed, format="%.2f")
        mouse_speed_spin.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        mouse_speed_spin.bind("<MouseWheel>", lambda e: "break")
        
        ttk.Label(mouse_frame, text="Snap Distance (px):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        snap_dist_spin = ttk.Spinbox(mouse_frame, from_=1, to=50, increment=1, textvariable=self.forage_snap_distance)
        snap_dist_spin.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        snap_dist_spin.bind("<MouseWheel>", lambda e: "break")
        
        ToolTip(mouse_speed_spin, "Controls how fast the mouse moves (0.1=slow, 1.0=fast)")
        ttk.Label(mouse_frame, text="Variability (px):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        variability_spin = ttk.Spinbox(mouse_frame, from_=0, to=10, increment=1, textvariable=self.forage_variability)
        variability_spin.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        variability_spin.bind("<MouseWheel>", lambda e: "break")
        ToolTip(snap_dist_spin, "Pixels within which mouse snaps directly to target")
        ToolTip(variability_spin, "Random offset added to clicks for human-like behavior")
        
        # Template Matching Settings Frame
        self.template_settings_frame = ttk.Labelframe(scrollable_frame, text="Template Matching Settings", padding=10)
        self.template_settings_frame.columnconfigure(1, weight=1)
        
        ttk.Label(self.template_settings_frame, text="Detection Threshold (0.0-1.0):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        det_thresh_spin = ttk.Spinbox(self.template_settings_frame, from_=0.0, to=1.0, increment=0.05, textvariable=self.forage_detection_threshold, format="%.2f")
        det_thresh_spin.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        det_thresh_spin.bind("<MouseWheel>", lambda e: "break")
        ToolTip(det_thresh_spin, "Minimum confidence for template matching (lower=more sensitive)")
        
        ttk.Label(self.template_settings_frame, text="NMS Threshold (0.0-1.0):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        nms_spin = ttk.Spinbox(self.template_settings_frame, from_=0.0, to=1.0, increment=0.05, textvariable=self.forage_nms_threshold, format="%.2f")
        nms_spin.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        nms_spin.bind("<MouseWheel>", lambda e: "break")
        ToolTip(nms_spin, "Non-maximum suppression threshold for overlapping detections")
        
        ttk.Label(self.template_settings_frame, text="Grayscale Min (0-255):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        gray_min_spin = ttk.Spinbox(self.template_settings_frame, from_=0, to=255, increment=5, textvariable=self.forage_grayscale_min)
        gray_min_spin.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        gray_min_spin.bind("<MouseWheel>", lambda e: "break")
        ToolTip(gray_min_spin, "Minimum grayscale value to filter targets (0=black, 255=white)")
        
        ttk.Label(self.template_settings_frame, text="Grayscale Max (0-255):").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        gray_max_spin = ttk.Spinbox(self.template_settings_frame, from_=0, to=255, increment=5, textvariable=self.forage_grayscale_max)
        gray_max_spin.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        gray_max_spin.bind("<MouseWheel>", lambda e: "break")
        ToolTip(gray_max_spin, "Maximum grayscale value to filter targets (0=black, 255=white)")
        
        ttk.Label(self.template_settings_frame, text="Scale Min (0.5-1.5):").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        scale_min_spin = ttk.Spinbox(self.template_settings_frame, from_=0.5, to=1.5, increment=0.1, textvariable=self.forage_scale_min, format="%.1f")
        scale_min_spin.grid(row=4, column=1, padx=5, pady=5, sticky="ew")
        scale_min_spin.bind("<MouseWheel>", lambda e: "break")
        ToolTip(scale_min_spin, "Minimum template scale for multi-scale detection")
        
        ttk.Label(self.template_settings_frame, text="Scale Max (0.5-1.5):").grid(row=5, column=0, padx=5, pady=5, sticky="w")
        scale_max_spin = ttk.Spinbox(self.template_settings_frame, from_=0.5, to=1.5, increment=0.1, textvariable=self.forage_scale_max, format="%.1f")
        scale_max_spin.grid(row=5, column=1, padx=5, pady=5, sticky="ew")
        scale_max_spin.bind("<MouseWheel>", lambda e: "break")
        ToolTip(scale_max_spin, "Maximum template scale for multi-scale detection")
        
        ttk.Label(self.template_settings_frame, text="Scale Steps (5-50):").grid(row=6, column=0, padx=5, pady=5, sticky="w")
        scale_steps_spin = ttk.Spinbox(self.template_settings_frame, from_=5, to=50, increment=5, textvariable=self.forage_scale_steps)
        scale_steps_spin.grid(row=6, column=1, padx=5, pady=5, sticky="ew")
        scale_steps_spin.bind("<MouseWheel>", lambda e: "break")
        ToolTip(scale_steps_spin, "Number of scale steps between min and max (more=slower but more accurate)")
        
        # RGB Detection Settings Frame
        self.rgb_settings_frame = ttk.Labelframe(scrollable_frame, text="RGB Color Detection Settings", padding=10)
        self.rgb_settings_frame.columnconfigure(1, weight=1)
        
        ttk.Label(self.rgb_settings_frame, text="Target RGB Color:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        rgb_color_frame = ttk.Frame(self.rgb_settings_frame)
        rgb_color_frame.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(rgb_color_frame, text="R:").pack(side="left", padx=2)
        rgb_r_spin = ttk.Spinbox(rgb_color_frame, from_=0, to=255, increment=1, textvariable=self.forage_rgb_target_r, width=5)
        rgb_r_spin.pack(side="left", padx=2)
        rgb_r_spin.bind("<MouseWheel>", lambda e: "break")
        
        ttk.Label(rgb_color_frame, text="G:").pack(side="left", padx=2)
        rgb_g_spin = ttk.Spinbox(rgb_color_frame, from_=0, to=255, increment=1, textvariable=self.forage_rgb_target_g, width=5)
        rgb_g_spin.pack(side="left", padx=2)
        rgb_g_spin.bind("<MouseWheel>", lambda e: "break")
        
        ttk.Label(rgb_color_frame, text="B:").pack(side="left", padx=2)
        rgb_b_spin = ttk.Spinbox(rgb_color_frame, from_=0, to=255, increment=1, textvariable=self.forage_rgb_target_b, width=5)
        rgb_b_spin.pack(side="left", padx=2)
        rgb_b_spin.bind("<MouseWheel>", lambda e: "break")
        ToolTip(rgb_color_frame, "Target RGB color to detect (default: 255,255,255 = white)")
        
        ttk.Label(self.rgb_settings_frame, text="RGB Tolerance (0-50):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        rgb_tol_spin = ttk.Spinbox(self.rgb_settings_frame, from_=0, to=50, increment=1, textvariable=self.forage_rgb_tolerance)
        rgb_tol_spin.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        rgb_tol_spin.bind("<MouseWheel>", lambda e: "break")
        ToolTip(rgb_tol_spin, "How close pixels must be to target color (lower=more strict)")
        
        ttk.Label(self.rgb_settings_frame, text="Min Cluster Size (px):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        rgb_min_spin = ttk.Spinbox(self.rgb_settings_frame, from_=1, to=500, increment=5, textvariable=self.forage_rgb_min_cluster)
        rgb_min_spin.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        rgb_min_spin.bind("<MouseWheel>", lambda e: "break")
        ToolTip(rgb_min_spin, "Minimum pixels in a cluster to be considered a detection")
        
        ttk.Label(self.rgb_settings_frame, text="Max Cluster Size (px):").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        rgb_max_spin = ttk.Spinbox(self.rgb_settings_frame, from_=10, to=5000, increment=50, textvariable=self.forage_rgb_max_cluster)
        rgb_max_spin.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        rgb_max_spin.bind("<MouseWheel>", lambda e: "break")
        ToolTip(rgb_max_spin, "Maximum pixels in a cluster to be considered a detection")
        
        # Patrol Areas (shared setting)
        patrol_frame = ttk.Labelframe(scrollable_frame, text="Patrol Areas", padding=10)
        patrol_frame.pack(fill=tk.X, padx=5, pady=5)
        patrol_frame.columnconfigure(1, weight=1)
        
        ttk.Label(patrol_frame, text="Total Patrol Areas:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        patrol_spin = ttk.Spinbox(patrol_frame, from_=1, to=20, increment=1, textvariable=self.forage_total_areas)
        patrol_spin.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        patrol_spin.bind("<MouseWheel>", lambda e: "break")
        ToolTip(patrol_spin, "Number of game areas to patrol for resources")
        
        # Timing Settings
        timing_frame = ttk.Labelframe(scrollable_frame, text="Timing Settings", padding=10)
        timing_frame.pack(fill=tk.X, pady=5)
        timing_frame.columnconfigure(1, weight=1)
        
        ttk.Label(timing_frame, text="Scan Interval (s):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        scan_spin = ttk.Spinbox(timing_frame, from_=0.001, to=1.0, increment=0.01, textvariable=self.forage_scan_interval, format="%.3f")
        scan_spin.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        scan_spin.bind("<MouseWheel>", lambda e: "break")
        
        ttk.Label(timing_frame, text="Area Load Delay (s):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        area_delay_spin = ttk.Spinbox(timing_frame, from_=0.1, to=10.0, increment=0.1, textvariable=self.forage_area_load_delay, format="%.1f")
        area_delay_spin.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        area_delay_spin.bind("<MouseWheel>", lambda e: "break")
        
        ttk.Label(timing_frame, text="Click Cooldown (s):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        cooldown_spin = ttk.Spinbox(timing_frame, from_=0.1, to=30.0, increment=0.5, textvariable=self.forage_click_cooldown, format="%.1f")
        cooldown_spin.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        cooldown_spin.bind("<MouseWheel>", lambda e: "break")
        
        ttk.Label(timing_frame, text="Post-Click Delay (s):").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        post_click_spin = ttk.Spinbox(timing_frame, from_=0.1, to=5.0, increment=0.1, textvariable=self.forage_post_click_delay, format="%.1f")
        post_click_spin.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        post_click_spin.bind("<MouseWheel>", lambda e: "break")
        
        ttk.Label(timing_frame, text="Startup Delay (s):").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        startup_spin = ttk.Spinbox(timing_frame, from_=0, to=30, increment=1, textvariable=self.forage_startup_delay)
        startup_spin.grid(row=4, column=1, padx=5, pady=5, sticky="ew")
        startup_spin.bind("<MouseWheel>", lambda e: "break")
        
        # False Positive Learning Settings (moved to bottom)
        learning_frame = ttk.Labelframe(scrollable_frame, text="False Positive Learning", padding=10)
        learning_frame.pack(fill=tk.X, pady=5)
        learning_frame.columnconfigure(1, weight=1)
        
        ttk.Label(learning_frame, text="Strike Limit (clicks before blacklist):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        strike_spin = ttk.Spinbox(learning_frame, from_=1, to=20, increment=1, textvariable=self.forage_strike_limit)
        strike_spin.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        strike_spin.bind("<MouseWheel>", lambda e: "break")
        
        ttk.Label(learning_frame, text="Blacklist Radius (pixels):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        blacklist_spin = ttk.Spinbox(learning_frame, from_=1, to=50, increment=1, textvariable=self.forage_blacklist_radius)
        blacklist_spin.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        blacklist_spin.bind("<MouseWheel>", lambda e: "break")
        
        ttk.Button(learning_frame, text="Clear Blacklist", command=self.clear_forage_blacklist).grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        
        # Initialize visibility based on detection method
        self.on_detection_method_changed()
    
    def on_detection_method_changed(self):
        """Show/hide settings based on selected detection method"""
        method = self.forage_detection_method.get()
        
        if method == "Template Matching":
            # Show template-specific settings
            self.template_settings_frame.pack(fill=tk.X, padx=5, pady=5)
            self.rgb_settings_frame.pack_forget()
        else:  # RGB Color Detection
            # Show RGB-specific settings
            self.template_settings_frame.pack_forget()
            self.rgb_settings_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.save_settings()

    def create_calibration_widgets(self, parent):
        """Placeholder - will be replaced by bot-specific widgets."""
        pass

    def create_rein_calibration_widgets(self, parent):
        """Create reincarnation bot calibration widgets."""
        parent.columnconfigure(1, weight=1)
        
        ocr_frame = ttk.Labelframe(parent, text="OCR Regions", padding=10)
        ocr_frame.pack(fill=tk.X, pady=5)
        ocr_frame.columnconfigure(1, weight=1)
        
        ttk.Label(ocr_frame, text="Qi Region:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.qi_region_label = ttk.Label(ocr_frame, text="Not Set", width=20)
        self.qi_region_label.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.calib_qi_button = ttk.Button(ocr_frame, text="Calibrate Qi", command=self.calibrate_qi)
        self.calib_qi_button.grid(row=0, column=2, padx=5, pady=5, sticky="e")
        
        ttk.Label(ocr_frame, text="Bloodline Region:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.bloodline_region_label = ttk.Label(ocr_frame, text="Not Set", width=20)
        self.bloodline_region_label.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.calib_bloodline_button = ttk.Button(ocr_frame, text="Calibrate Bloodline", command=self.calibrate_bloodline)
        self.calib_bloodline_button.grid(row=1, column=2, padx=5, pady=5, sticky="e")

        click_frame = ttk.Labelframe(parent, text="Click Positions", padding=10)
        click_frame.pack(fill=tk.X, pady=5)
        click_frame.columnconfigure(1, weight=1)

        self.calibration_widgets = {}
        buttons_to_calibrate = [
            ("stats_button", "Stats Button"),
            ("options_button", "Options Button"),
            ("reincarnate_button", "Reincarnate Button"),
            ("yes_confirm_button", "Yes (Confirm) Button"),
            ("skip_animation_button", "Skip Animation Button"),
            ("reincarnate_final_button", "Reincarnate (Final) Button"),
        ]

        for i, (key, text) in enumerate(buttons_to_calibrate):
            label = ttk.Label(click_frame, text=f"{text}:")
            label.grid(row=i, column=0, padx=5, pady=5, sticky="w")
            
            status_label = ttk.Label(click_frame, text="Not Set", width=20)
            status_label.grid(row=i, column=1, padx=5, pady=5, sticky="ew")
            
            calib_button = ttk.Button(
                click_frame,
                text=f"Calibrate {text}",
                command=lambda k=key, t=text: self.calibrate_click(k, t)
            )
            calib_button.grid(row=i, column=2, padx=5, pady=5, sticky="e")
            
            self.calibration_widgets[key] = {
                "label": status_label,
                "button": calib_button
            }
            
        # Hotkey capture UI
        hotkey_frame = ttk.Labelframe(parent, text="Hotkey Setting", padding=10)
        hotkey_frame.pack(fill=tk.X, pady=5, expand=True)
        hotkey_frame.columnconfigure(0, weight=1)
        
        self.hotkey_button = ttk.Button(
            hotkey_frame,
            textvariable=self.hotkey_name_var,
            command=self.start_hotkey_capture
        )
        self.hotkey_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        
        ttk.Label(hotkey_frame, text="(Requires application restart to take effect)").grid(row=1, column=0, padx=5, pady=2, sticky="w")

    def create_forage_calibration_widgets(self, parent):
        """Create forage bot calibration widgets."""
        parent.columnconfigure(1, weight=1)
        
        region_frame = ttk.Labelframe(parent, text="Scan Region", padding=10)
        region_frame.pack(fill=tk.X, pady=5)
        region_frame.columnconfigure(1, weight=1)
        
        ttk.Label(region_frame, text="Search Region:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.forage_region_label = ttk.Label(region_frame, text="Not Set", width=20)
        self.forage_region_label.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(region_frame, text="Calibrate Region", command=self.calibrate_forage_region).grid(row=0, column=2, padx=5, pady=5, sticky="e")
        
        arrow_frame = ttk.Labelframe(parent, text="Navigation Arrows", padding=10)
        arrow_frame.pack(fill=tk.X, pady=5)
        arrow_frame.columnconfigure(1, weight=1)
        
        ttk.Label(arrow_frame, text="Left Arrow:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.forage_left_label = ttk.Label(arrow_frame, text="Not Set", width=20)
        self.forage_left_label.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(arrow_frame, text="Calibrate Left", command=self.calibrate_forage_left).grid(row=0, column=2, padx=5, pady=5, sticky="e")
        
        ttk.Label(arrow_frame, text="Right Arrow:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.forage_right_label = ttk.Label(arrow_frame, text="Not Set", width=20)
        self.forage_right_label.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(arrow_frame, text="Calibrate Right", command=self.calibrate_forage_right).grid(row=1, column=2, padx=5, pady=5, sticky="e")
        
        # Hotkey frame (shared between both bots)
        hotkey_frame = ttk.Labelframe(parent, text="Hotkey Setting", padding=10)
        hotkey_frame.pack(fill=tk.X, pady=5, expand=True)
        hotkey_frame.columnconfigure(0, weight=1)
        
        self.hotkey_button = ttk.Button(
            hotkey_frame,
            textvariable=self.hotkey_name_var,
            command=self.start_hotkey_capture
        )
        self.hotkey_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        
        ttk.Label(hotkey_frame, text="(Requires application restart to take effect)").grid(row=1, column=0, padx=5, pady=2, sticky="w")

    def manual_save_settings(self):
        """Manually save current settings."""
        self.save_settings()
        messagebox.showinfo("Settings Saved", "Current settings have been saved successfully.")
        self.logger.info("Settings manually saved by user.")
    
    def reset_to_defaults(self):
        """Reset all settings to hardcoded defaults."""
        if not messagebox.askyesno("Reset to Defaults",
                                   "Are you sure you want to reset all settings to their default values?\n\n"
                                   "This will overwrite your current settings."):
            return
        
        selected = self.selected_bot.get()
        
        if selected == "reincarnation":
            # Reset reincarnation bot settings to defaults
            self.speed_factor_var.set(0.15)
            self.snap_threshold_var.set(25)
            self.variability_var.set(3)
            self.after_click_delay_var.set(1.5)
            self.stop_on_bloodline_var.set(True)
            self.stop_on_qi_var.set(False)
            self.qi_stop_var.set(200.0)
            self.stop_on_new_var.set(True)
            self.show_success_popup_var.set(True)
        else:  # forage
            # Reset forage bot settings to defaults
            self.forage_detection_threshold.set(0.25)
            self.forage_mouse_speed.set(0.3)
            self.forage_total_areas.set(6)
            self.forage_post_click_delay.set(1.8)
            self.forage_strike_limit.set(5)
            self.forage_blacklist_radius.set(5)
            self.forage_nms_threshold.set(0.3)
            self.forage_grayscale_min.set(245)
            self.forage_grayscale_max.set(255)
            self.forage_scale_min.set(0.8)
            self.forage_scale_max.set(1.2)
            self.forage_scale_steps.set(20)
            self.forage_scan_interval.set(0.01)
            self.forage_area_load_delay.set(1.0)
            self.forage_click_cooldown.set(5.0)
            self.forage_startup_delay.set(3)
            self.forage_snap_distance.set(15)
            self.forage_variability.set(3)
        
        self.save_settings()
        messagebox.showinfo("Reset Complete", f"{selected.capitalize()} bot settings have been reset to defaults.")
        self.logger.info(f"{selected.capitalize()} bot settings reset to defaults by user.")
    
    def save_as_default(self):
        """Save current settings as new default."""
        if not messagebox.askyesno("Save as Default",
                                   "Save current settings as the new default?\n\n"
                                   "This will create a default_settings.json file."):
            return
        
        try:
            selected = self.selected_bot.get()
            default_file = settings_manager.LOG_DIR / f"default_{selected}_settings.json"
            
            if selected == "reincarnation":
                default_settings = {
                    'speed_factor': self.speed_factor_var.get(),
                    'snap_threshold': self.snap_threshold_var.get(),
                    'variability': self.variability_var.get(),
                    'after_click_delay': self.after_click_delay_var.get(),
                    'stop_on_bloodline': self.stop_on_bloodline_var.get(),
                    'stop_on_qi': self.stop_on_qi_var.get(),
                    'qi_stop': self.qi_stop_var.get(),
                    'stop_on_new': self.stop_on_new_var.get(),
                    'show_success_popup': self.show_success_popup_var.get()
                }
            else:  # forage
                default_settings = {
                    'detection_threshold': self.forage_detection_threshold.get(),
                    'mouse_speed': self.forage_mouse_speed.get(),
                    'total_areas': self.forage_total_areas.get(),
                    'post_click_delay': self.forage_post_click_delay.get(),
                    'strike_limit': self.forage_strike_limit.get(),
                    'blacklist_radius': self.forage_blacklist_radius.get(),
                    'nms_threshold': self.forage_nms_threshold.get(),
                    'grayscale_min': self.forage_grayscale_min.get(),
                    'grayscale_max': self.forage_grayscale_max.get(),
                    'scale_min': self.forage_scale_min.get(),
                    'scale_max': self.forage_scale_max.get(),
                    'scale_steps': self.forage_scale_steps.get(),
                    'scan_interval': self.forage_scan_interval.get(),
                    'area_load_delay': self.forage_area_load_delay.get(),
                    'click_cooldown': self.forage_click_cooldown.get(),
                    'startup_delay': self.forage_startup_delay.get(),
                    'snap_distance': self.forage_snap_distance.get(),
                    'variability': self.forage_variability.get()
                }
            
            with open(str(default_file), 'w') as f:
                json.dump(default_settings, f, indent=4)
            
            messagebox.showinfo("Success", f"Current {selected} settings saved as default to:\n{default_file}")
            self.logger.info(f"Default {selected} settings saved to {default_file}")
        except Exception as e:
            self.logger.error(f"Failed to save default settings: {e}")
            messagebox.showerror("Error", f"Failed to save default settings:\n{e}")
    
    def clear_forage_blacklist(self):
        """Clear the forage bot's blacklist."""
        if messagebox.askyesno("Clear Blacklist", "Are you sure you want to clear the forage bot's blacklist?"):
            self.logger.info("Forage bot blacklist cleared by user.")
            messagebox.showinfo("Success", "Blacklist cleared. This will take effect on the next bot start.")
    
    def calibrate_forage_region(self):
        """Calibrate the forage search region."""
        self.logger.info("Starting Forage search region calibration...")
        CalibrationWindow(self.root, "Forage Search Region", self.on_forage_region_calibrated, self.scale_x, self.scale_y)
    
    def on_forage_region_calibrated(self, region_rect):
        """Callback for forage region calibration."""
        if region_rect:
            self.forage_search_region = region_rect
            self.forage_region_label.config(text=str(region_rect))
            self.logger.debug(f"[CALIBRATION DEBUG] Before save - forage_search_region: {self.forage_search_region}")
            self.logger.debug(f"[CALIBRATION DEBUG] Current bot selection: {self.selected_bot.get()}")
            self.save_settings()
            self.logger.info(f"New Forage search region saved: {region_rect}")
        else:
            self.logger.info("Forage region calibration cancelled.")
    
    def calibrate_forage_left(self):
        """Calibrate the left arrow position."""
        self.logger.info("Starting Left Arrow calibration...")
        CalibrationClickWindow(self.root, "Left Arrow", self.on_forage_left_calibrated, self.scale_x, self.scale_y)
    
    def on_forage_left_calibrated(self, point):
        """Callback for left arrow calibration."""
        if point:
            self.forage_left_arrow = point
            self.forage_left_label.config(text=str(point))
            self.logger.debug(f"[CALIBRATION DEBUG] Before save - forage_left_arrow: {self.forage_left_arrow}")
            self.logger.debug(f"[CALIBRATION DEBUG] Current bot selection: {self.selected_bot.get()}")
            self.save_settings()
            self.logger.info(f"New Left Arrow position saved: {point}")
        else:
            self.logger.info("Left Arrow calibration cancelled.")
    
    def calibrate_forage_right(self):
        """Calibrate the right arrow position."""
        self.logger.info("Starting Right Arrow calibration...")
        CalibrationClickWindow(self.root, "Right Arrow", self.on_forage_right_calibrated, self.scale_x, self.scale_y)
    
    def on_forage_right_calibrated(self, point):
        """Callback for right arrow calibration."""
        if point:
            self.forage_right_arrow = point
            self.forage_right_label.config(text=str(point))
            self.logger.debug(f"[CALIBRATION DEBUG] Before save - forage_right_arrow: {self.forage_right_arrow}")
            self.logger.debug(f"[CALIBRATION DEBUG] Current bot selection: {self.selected_bot.get()}")
            self.save_settings()
            self.logger.info(f"New Right Arrow position saved: {point}")
        else:
            self.logger.info("Right Arrow calibration cancelled.")

    def create_bloodline_editor_widgets(self, parent):
        """Create bloodline editor tab widgets."""
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.bloodline_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            height=15,
            bg="#3E3E3E",
            fg="#FAFAFA",
            selectbackground="#5E5E5E",
            borderwidth=1,
            relief="solid",
            exportselection=False,
            font=(self.font_name_var.get(), self.font_size_var.get())
        )
        scrollbar.config(command=self.bloodline_listbox.yview)
        
        self.bloodline_listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        move_button_frame = ttk.Frame(list_frame)
        move_button_frame.grid(row=0, column=2, sticky="ns", padx=5)
        
        ttk.Button(move_button_frame, text="Move Up", command=self.move_bloodline_up).pack(padx=5, pady=5, fill=tk.X)
        ttk.Button(move_button_frame, text="Move Down", command=self.move_bloodline_down).pack(padx=5, pady=5, fill=tk.X)

        edit_frame = ttk.Labelframe(parent, text="Add / Edit", padding=10)
        edit_frame.pack(fill=tk.X, pady=5)
        edit_frame.columnconfigure(1, weight=1)

        ttk.Label(edit_frame, text="Bloodline Name:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.bloodline_name_entry = ttk.Entry(edit_frame)
        self.bloodline_name_entry.grid(row=0, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        
        ttk.Label(edit_frame, text="Qi String (e.g., 5x Qi):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.bloodline_qi_entry = ttk.Entry(edit_frame)
        self.bloodline_qi_entry.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        ttk.Button(edit_frame, text="Add as New", command=self.add_bloodline).grid(row=2, column=0, padx=5, pady=5, sticky="ew")
        ttk.Button(edit_frame, text="Update Selected", command=self.update_bloodline).grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(edit_frame, text="Delete Selected", command=self.delete_bloodline).grid(row=2, column=2, padx=5, pady=5, sticky="ew")

        ttk.Button(parent, text="Save All Changes to bloodlines.json", command=self.save_bloodlines).pack(fill=tk.X, padx=5, pady=10)

        self.bloodline_listbox.bind("<<ListboxSelect>>", self.on_bloodline_select)
        
        self.refresh_bloodline_listbox()

    def on_bloodline_select(self, event=None):
        """Handle bloodline selection in listbox."""
        try:
            selected_index = self.bloodline_listbox.curselection()[0]
            name, qi = self.ranked_bloodlines_data[selected_index]
            self.bloodline_name_entry.delete(0, tk.END)
            self.bloodline_name_entry.insert(0, name)
            self.bloodline_qi_entry.delete(0, tk.END)
            self.bloodline_qi_entry.insert(0, qi)
        except IndexError:
            pass

    def add_bloodline(self):
        """Add a new bloodline to the list."""
        name = self.bloodline_name_entry.get().strip()
        qi = self.bloodline_qi_entry.get().strip()
        
        if not name or not qi:
            messagebox.showwarning("Missing Info", "Please enter both a name and a Qi string.")
            return
            
        self.ranked_bloodlines_data.append((name, qi))
        self.refresh_bloodline_listbox()
        self.bloodline_listbox.select_set(tk.END)
        self.bloodline_listbox.see(tk.END)

    def update_bloodline(self):
        """Update the selected bloodline."""
        try:
            idx = self.bloodline_listbox.curselection()[0]
            name = self.bloodline_name_entry.get().strip()
            qi = self.bloodline_qi_entry.get().strip()
            
            if not name or not qi:
                messagebox.showwarning("Missing Info", "Please enter both a name and a Qi string.")
                return
            
            self.ranked_bloodlines_data[idx] = (name, qi)
            self.refresh_bloodline_listbox()
            self.bloodline_listbox.select_set(idx)
        except IndexError:
            messagebox.showwarning("No Selection", "Please select a bloodline to update.")

    def delete_bloodline(self):
        """Delete the selected bloodline."""
        try:
            idx = self.bloodline_listbox.curselection()[0]
            name, qi = self.ranked_bloodlines_data[idx]
            
            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{name} - {qi}'?"):
                self.ranked_bloodlines_data.pop(idx)
                self.refresh_bloodline_listbox()
                self.bloodline_name_entry.delete(0, tk.END)
                self.bloodline_qi_entry.delete(0, tk.END)
        except IndexError:
            messagebox.showwarning("No Selection", "Please select a bloodline to delete.")

    def move_bloodline_up(self):
        """Move selected bloodline up in the list."""
        try:
            idx = self.bloodline_listbox.curselection()[0]
            if idx == 0:
                return
            
            item = self.ranked_bloodlines_data.pop(idx)
            self.ranked_bloodlines_data.insert(idx - 1, item)
            
            self.refresh_bloodline_listbox()
            self.bloodline_listbox.select_set(idx - 1)
            self.bloodline_listbox.see(idx - 1)
        except IndexError:
            pass

    def move_bloodline_down(self):
        """Move selected bloodline down in the list."""
        try:
            idx = self.bloodline_listbox.curselection()[0]
            if idx == self.bloodline_listbox.size() - 1:
                return
            
            item = self.ranked_bloodlines_data.pop(idx)
            self.ranked_bloodlines_data.insert(idx + 1, item)
            
            self.refresh_bloodline_listbox()
            self.bloodline_listbox.select_set(idx + 1)
            self.bloodline_listbox.see(idx + 1)
        except IndexError:
            pass

    def refresh_bloodline_listbox(self):
        """Refresh the bloodline listbox display."""
        self.bloodline_listbox.delete(0, tk.END)
        for name, qi in self.ranked_bloodlines_data:
            self.bloodline_listbox.insert(tk.END, f"{qi} - {name}")

    def create_history_widgets(self, parent):
        """Create history tab widgets."""
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)

        history_controls_frame = ttk.Frame(parent)
        history_controls_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=5)
        history_controls_frame.columnconfigure(1, weight=1)
        
        ttk.Label(history_controls_frame, text="View Log:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        self.history_combo = ttk.Combobox(
            history_controls_frame,
            values=self.get_filtered_history_options(),
            state="readonly"
        )
        self.history_combo.current(0)
        self.history_combo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        self.history_sort_button = ttk.Button(
            history_controls_frame,
            text="Sort: Newest First" if self.history_sort_newest_first.get() else "Sort: Oldest First",
            command=self.toggle_history_sort
        )
        self.history_sort_button.grid(row=0, column=2, padx=5, pady=5, sticky="e")
        
        self.history_load_button = ttk.Button(
            history_controls_frame,
            text="Load / Refresh",
            command=self.load_history_file
        )
        self.history_load_button.grid(row=0, column=3, padx=5, pady=5, sticky="e")
        
        self.history_clear_button = ttk.Button(
            history_controls_frame,
            text="Clear This Log",
            command=self.clear_history_file
        )
        self.history_clear_button.grid(row=0, column=4, padx=5, pady=5, sticky="e")

        self.history_text = scrolledtext.ScrolledText(
            parent,
            state=tk.DISABLED,
            bg="#3E3E3E",
            fg="#FAFAFA",
            border=1,
            relief="solid",
            wrap=tk.WORD
        )
        self.history_text.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=5)
        self.history_text.config(font=(self.font_name_var.get(), self.font_size_var.get()))
        
        self.clear_on_start_check = ttk.Checkbutton(
            parent,
            text="Clear all history logs on app start",
            variable=self.clear_on_start_var,
            onvalue=True,
            offvalue=False,
            command=self.save_settings
        )
        self.clear_on_start_check.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="w")

    def get_filtered_history_options(self):
        """Get history options filtered by active bot."""
        selected_bot = self.selected_bot.get()
        
        if selected_bot == "forage":
            return ["Forage History"]
        else:  # reincarnation
            return ["Bloodline History", "Qi History"]
    
    def toggle_history_sort(self):
        """Toggle the history sort order."""
        self.history_sort_newest_first.set(not self.history_sort_newest_first.get())
        if hasattr(self, 'history_sort_button'):
            self.history_sort_button.config(
                text="Sort: Newest First" if self.history_sort_newest_first.get() else "Sort: Oldest First"
            )
        self.load_history_file()
    
    def load_history_file(self):
        """Load and display the selected history file."""
        selected = self.history_combo.get()
        
        if selected == "Bloodline History":
            filename = str(settings_manager.BLOODLINE_HISTORY_FILE)
        elif selected == "Qi History":
            filename = str(settings_manager.QI_HISTORY_FILE)
        elif selected == "Forage History":
            filename = str(settings_manager.FORAGE_HISTORY_FILE)
        else:
            return

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Apply sort order if content exists
            if content and self.history_sort_newest_first.get():
                lines = content.strip().split('\n')
                lines.reverse()
                content = '\n'.join(lines)
                
            self.history_text.config(state=tk.NORMAL)
            self.history_text.delete('1.0', tk.END)
            if content:
                self.history_text.insert(tk.END, content)
            else:
                self.history_text.insert(tk.END, f"{filename} is empty.")
            
            # Scroll to appropriate position based on sort order
            if self.history_sort_newest_first.get():
                self.history_text.see('1.0')
            else:
                self.history_text.see(tk.END)
            self.history_text.config(state=tk.DISABLED)
            
        except FileNotFoundError:
            self.history_text.config(state=tk.NORMAL)
            self.history_text.delete('1.0', tk.END)
            self.history_text.insert(tk.END, f"Error: {filename} not found.")
            self.history_text.config(state=tk.DISABLED)
        except Exception as e:
            self.history_text.config(state=tk.NORMAL)
            self.history_text.delete('1.0', tk.END)
            self.history_text.insert(tk.END, f"An error occurred: {e}")
            self.history_text.config(state=tk.DISABLED)
            self.logger.error(f"Failed to load history file {filename}: {e}")

    def clear_history_file(self):
        """Clear the selected history file."""
        selected = self.history_combo.get()
        
        if selected == "Bloodline History":
            filename = str(settings_manager.BLOODLINE_HISTORY_FILE)
        elif selected == "Qi History":
            filename = str(settings_manager.QI_HISTORY_FILE)
        elif selected == "Forage History":
            filename = str(settings_manager.FORAGE_HISTORY_FILE)
        else:
            return

        if not messagebox.askyesno("Confirm Clear", f"Are you sure you want to permanently delete all data from {filename}?"):
            return
            
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                pass
            self.logger.info(f"User cleared history file: {filename}")
            self.load_history_file()
        except Exception as e:
            self.logger.error(f"Failed to clear history file {filename}: {e}")
            messagebox.showerror("Error", f"Could not clear file: {e}")

    def create_appearance_widgets(self, parent):
        """Create appearance tab widgets."""
        parent.columnconfigure(1, weight=1)

        font_frame = ttk.Labelframe(parent, text="Font Settings", padding=10)
        font_frame.pack(fill=tk.X, pady=5)
        font_frame.columnconfigure(1, weight=1)
        
        ttk.Label(font_frame, text="Font Family:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        system_fonts = sorted(list(font.families()))
        tk_default_fonts = ["TkDefaultFont", "TkTextFont", "TkFixedFont"]
        display_fonts = tk_default_fonts + system_fonts
        
        self.font_combo = ttk.Combobox(
            font_frame,
            textvariable=self.font_name_var,
            values=display_fonts,
            state="readonly"
        )
        self.font_combo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(font_frame, text="Font Size:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.font_size_spinbox = ttk.Spinbox(
            font_frame,
            from_=8, to=16,
            increment=1,
            textvariable=self.font_size_var,
            width=5
        )
        self.font_size_spinbox.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        self.apply_font_button = ttk.Button(font_frame, text="Apply Font", command=self.on_apply_font_clicked)
        self.apply_font_button.grid(row=2, column=0, columnspan=2, padx=5, pady=10, sticky="ew")
        
        log_level_frame = ttk.Labelframe(parent, text="Log Verbosity", padding=10)
        log_level_frame.pack(fill=tk.X, pady=5)
        log_level_frame.columnconfigure(1, weight=1)
        
        ttk.Label(log_level_frame, text="GUI Log Level:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        self.log_level_combo = ttk.Combobox(
            log_level_frame,
            textvariable=self.log_level_var,
            values=["User", "Developer"],
            state="readonly"
        )
        self.log_level_combo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.log_level_combo.bind("<<ComboboxSelected>>", self.on_log_level_changed)

        ttk.Label(log_level_frame, text="'User' = Only shows major events & errors.\n'Developer' = Shows all messages (verbose).", justify=tk.LEFT).grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="w")
        
        link_frame = ttk.Labelframe(parent, text="Get More Fonts", padding=10)
        link_frame.pack(fill=tk.X, pady=5)
        link_frame.columnconfigure(1, weight=1)

        ttk.Label(link_frame, text="Find and install new fonts at:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        google_font_link = ttk.Label(link_frame, text="https://fonts.google.com/", style="Link.TLabel", cursor="hand2")
        google_font_link.grid(row=0, column=1, padx=0, pady=2, sticky="w")
        google_font_link.bind("<Button-1>", lambda e: webbrowser.open_new("https://fonts.google.com/"))
        ttk.Label(link_frame, text="(Requires app restart after install)").grid(row=1, column=0, columnspan=2, padx=5, pady=2, sticky="w")

    def on_log_level_changed(self, event=None):
        """Handle log level change."""
        new_level = self.log_level_var.get()
        gui_logger.set_gui_log_level(new_level)
        self.save_settings()

    def on_apply_font_clicked(self):
        """Handle font apply button click."""
        self.save_settings()
        self.apply_font_settings(log_errors=True)

    def apply_font_settings(self, log_errors=True):
        """Apply font settings to all widgets."""
        font_name = self.font_name_var.get()
        font_size = self.font_size_var.get()
        
        try:
            self.logger.debug(f"Applying font: {font_name}, Size: {font_size}")
            
            self.style.configure(".", font=(font_name, font_size))
            
            if hasattr(self, 'log_text'):
                self.log_text.config(font=(font_name, font_size))
            
            if hasattr(self, 'bloodline_listbox'):
                self.bloodline_listbox.config(font=(font_name, font_size))
                
            if hasattr(self, 'history_text'):
                self.history_text.config(font=(font_name, font_size))
            
        except Exception as e:
            self.logger.error(f"Failed to apply font: {e}")
            if log_errors:
                messagebox.showerror("Font Error", f"Could not apply font '{font_name}'. It may not be installed correctly.")

    def load_bloodlines(self):
        """Load bloodlines from JSON file."""
        try:
            if os.path.exists(str(settings_manager.BLOODLINES_FILE)):
                with open(str(settings_manager.BLOODLINES_FILE), 'r') as f:
                    self.ranked_bloodlines_data = json.load(f)
                self.logger.info(f"Loaded {len(self.ranked_bloodlines_data)} bloodlines from {settings_manager.BLOODLINES_FILE}")
            else:
                self.logger.info(f"{settings_manager.BLOODLINES_FILE} not found, creating from default list.")
                self.ranked_bloodlines_data = DEFAULT_BLOODLINES_DATA
                try:
                    with open(str(settings_manager.BLOODLINES_FILE), 'w') as f:
                        json.dump(self.ranked_bloodlines_data, f, indent=4)
                    self.logger.info(f"Created default {settings_manager.BLOODLINES_FILE}.")
                except Exception as e:
                    self.logger.error(f"Could not create default {settings_manager.BLOODLINES_FILE}: {e}")
                    messagebox.showerror("Fatal Error", f"Could not create {settings_manager.BLOODLINES_FILE}: {e}")
            
            self.rebuild_bloodline_helpers()

        except Exception as e:
            self.logger.error(f"Error loading {settings_manager.BLOODLINES_FILE}: {e}")
            messagebox.showerror("Bloodline Error", f"Could not load {settings_manager.BLOODLINES_FILE}. Using default list.")
            self.ranked_bloodlines_data = DEFAULT_BLOODLINES_DATA
            self.rebuild_bloodline_helpers()

    def save_bloodlines(self, log_success=True):
        """Save bloodlines to JSON file."""
        try:
            self.ranked_bloodlines_data = []
            for i in range(self.bloodline_listbox.size()):
                display_text = self.bloodline_listbox.get(i)
                qi, name = display_text.split(" - ", 1)
                self.ranked_bloodlines_data.append((name, qi))

            with open(str(settings_manager.BLOODLINES_FILE), 'w') as f:
                json.dump(self.ranked_bloodlines_data, f, indent=4)
            
            if log_success:
                self.logger.info(f"Saved {len(self.ranked_bloodlines_data)} bloodlines to {settings_manager.BLOODLINES_FILE}")
                messagebox.showinfo("Success", "Bloodline list saved.")
            
            self.rebuild_bloodline_helpers()
            self.update_bloodline_combobox()

        except Exception as e:
            self.logger.error(f"Error saving {settings_manager.BLOODLINES_FILE}: {e}")
            messagebox.showerror("Save Error", f"Could not save bloodlines: {e}")

    def rebuild_bloodline_helpers(self):
        """Rebuild helper lists for bloodline matching."""
        self.ranked_bloodlines = [item[0] for item in self.ranked_bloodlines_data]
        self.combobox_values = [f"{item[1]} - {item[0]}" for item in self.ranked_bloodlines_data]
        self.ranked_bloodlines_lower = []
        for name, qi in self.ranked_bloodlines_data:
            cleaned_name = re.sub(r'[^\w\s-]', '', name).strip().lower()
            self.ranked_bloodlines_lower.append(cleaned_name)

    def update_bloodline_combobox(self):
        """Update bloodline combobox values."""
        if hasattr(self, 'bloodline_stop_combo'):
            self.bloodline_stop_combo.config(values=self.combobox_values)
            loaded_index = getattr(self, '_loaded_target_index', 0)
            
            if self.combobox_values:
                valid_index = min(loaded_index, len(self.combobox_values) - 1)
                self.bloodline_stop_combo.current(valid_index)

    def calibrate_qi(self):
        """Start Qi region calibration."""
        self.logger.info("Starting Qi region calibration...")
        CalibrationWindow(self.root, "Qi Multi Region", self.on_qi_calibrated, self.scale_x, self.scale_y)

    def on_qi_calibrated(self, region_rect):
        """Handle Qi calibration completion."""
        if region_rect:
            self.qi_region = region_rect
            self.qi_region_label.config(text=str(region_rect))
            self.logger.debug(f"[CALIBRATION DEBUG] Before save - qi_region: {self.qi_region}")
            self.logger.debug(f"[CALIBRATION DEBUG] Current bot selection: {self.selected_bot.get()}")
            self.save_settings()
            self.logger.info(f"New Qi region saved: {region_rect}")
        else:
            self.logger.info("Qi calibration cancelled.")

    def calibrate_bloodline(self):
        """Start bloodline region calibration."""
        self.logger.info("Starting Bloodline region calibration...")
        CalibrationWindow(self.root, "Bloodline Region", self.on_bloodline_calibrated, self.scale_x, self.scale_y)

    def on_bloodline_calibrated(self, region_rect):
        """Handle bloodline calibration completion."""
        if region_rect:
            self.bloodline_region = region_rect
            self.bloodline_region_label.config(text=str(self.bloodline_region))
            self.logger.debug(f"[CALIBRATION DEBUG] Before save - bloodline_region: {self.bloodline_region}")
            self.logger.debug(f"[CALIBRATION DEBUG] Current bot selection: {self.selected_bot.get()}")
            self.save_settings()
            self.logger.info(f"New Bloodline region saved: {region_rect}")
        else:
            self.logger.info("Bloodline calibration cancelled.")

    def calibrate_click(self, button_key, title):
        """Start click position calibration."""
        self.logger.info(f"Starting calibration for: {button_key}")
        CalibrationClickWindow(self.root, title, lambda p, k=button_key: self.on_click_calibrated(p, k), self.scale_x, self.scale_y)

    def on_click_calibrated(self, point, button_key):
        """Handle click calibration completion."""
        if point:
            self.calibrated_points[button_key] = point
            self.calibration_widgets[button_key]['label'].config(text=str(point))
            self.logger.debug(f"[CALIBRATION DEBUG] Before save - calibrated_points[{button_key}]: {point}")
            self.logger.debug(f"[CALIBRATION DEBUG] Current bot selection: {self.selected_bot.get()}")
            self.save_settings()
            self.logger.info(f"New point for {button_key} saved: {point}")
        else:
            self.logger.info(f"Calibration for {button_key} cancelled.")

    def start_hotkey_capture(self):
        """Start hotkey capture mode."""
        self.logger.debug("Starting hotkey capture...")
        self.hotkey_button.config(text="Press any key...", textvariable="")
        
        self.hotkey_button.bind("<KeyPress>", self.on_hotkey_captured)
        self.hotkey_button.bind("<FocusOut>", self.cancel_hotkey_capture)
        self.hotkey_button.focus_set()

    def on_hotkey_captured(self, event):
        """Handle hotkey capture."""
        self.cancel_hotkey_capture(event)
        
        key_name = event.keysym
        key_code = event.keycode
        
        ignored_keys = ["Control_L", "Control_R", "Alt_L", "Alt_R", "Shift_L", "Shift_R", "Escape", "Tab", "Caps_Lock"]
        if key_name in ignored_keys:
            self.logger.warning(f"Ignored invalid hotkey: {key_name}")
            self.hotkey_button.config(text=self.hotkey_name_var.get())
            return

        self.logger.info(f"New hotkey captured: Name={key_name}, Code={key_code}")
        
        self.hotkey_name_var.set(key_name)
        self.hotkey_code_var.set(key_code)
        
        self.hotkey_button.config(text=key_name)
        
        if hasattr(self, 'start_button'):
            self.start_button.config(text=f"Start Bot ({key_name})")
            self.stop_button.config(text=f"Stop Bot ({key_name})")
        
        self.save_settings()

    def cancel_hotkey_capture(self, event):
        """Cancel hotkey capture mode."""
        self.logger.debug("Cleaning up hotkey capture bindings.")
        self.hotkey_button.unbind("<KeyPress>")
        self.hotkey_button.unbind("<FocusOut>")
        self.hotkey_button.config(textvariable=self.hotkey_name_var)
        self.hotkey_name_var.set(self.hotkey_name_var.get())

    def update_calibration_labels(self):
        """Update calibration labels with current values."""
        # Only update if widgets have been created
        if hasattr(self, 'qi_region_label') and self.qi_region:
            self.qi_region_label.config(text=str(self.qi_region))
        if hasattr(self, 'bloodline_region_label') and self.bloodline_region:
            self.bloodline_region_label.config(text=str(self.bloodline_region))
        
        # Update calibration widgets if they exist
        if hasattr(self, 'calibration_widgets'):
            for key, point in self.calibrated_points.items():
                if key in self.calibration_widgets:
                    self.calibration_widgets[key]['label'].config(text=str(point))
        
        # Update forage calibration labels if they exist
        if hasattr(self, 'forage_region_label') and self.forage_search_region:
            self.forage_region_label.config(text=str(self.forage_search_region))
        if hasattr(self, 'forage_left_label') and self.forage_left_arrow:
            self.forage_left_label.config(text=str(self.forage_left_arrow))
        if hasattr(self, 'forage_right_label') and self.forage_right_arrow:
            self.forage_right_label.config(text=str(self.forage_right_arrow))

    def load_settings(self):
        """Load settings from JSON files - loads from both bot-specific files."""
        try:
            # Load reincarnation bot settings
            if os.path.exists(str(settings_manager.REIN_SETTINGS_FILE)):
                with open(str(settings_manager.REIN_SETTINGS_FILE), 'r') as f:
                    rein_settings = json.load(f)
                    
                    # Reincarnation bot settings
                    self.qi_region = rein_settings.get('qi_region')
                    self.bloodline_region = rein_settings.get('bloodline_region')
                    self.calibrated_points = rein_settings.get('calibrated_points', {})
                    
                    self.ui_mode_var.set(rein_settings.get('ui_mode', 'dark'))
                    
                    self.speed_factor_var.set(rein_settings.get('mouse_speed_factor', 0.15))
                    self.snap_threshold_var.set(rein_settings.get('mouse_snap_threshold', 25))
                    self.variability_var.set(rein_settings.get('mouse_variability', 3))
                    self.after_click_delay_var.set(rein_settings.get('after_click_delay', 1.5))
                    
                    self.stop_on_bloodline_var.set(rein_settings.get('stop_on_bloodline', True))
                    self.stop_on_qi_var.set(rein_settings.get('stop_on_qi', False))
                    self.qi_stop_var.set(rein_settings.get('target_qi_multi', 200.0))
                    self.stop_on_new_var.set(rein_settings.get('stop_on_new', True))
                    self.show_success_popup_var.set(rein_settings.get('show_success_popup', True))
                    
                    target_index = rein_settings.get('target_bloodline_index', 0)
                    self._loaded_target_index = target_index
                    
                    # Shared settings (from rein file)
                    self.font_name_var.set(rein_settings.get('font_name', 'TkDefaultFont'))
                    self.font_size_var.set(rein_settings.get('font_size', 10))
                    self.clear_on_start_var.set(rein_settings.get('clear_on_start', False))
                    self.log_level_var.set(rein_settings.get('log_level', 'User'))
                    self.hotkey_name_var.set(rein_settings.get('hotkey_name', 'F7'))
                    self.hotkey_code_var.set(rein_settings.get('hotkey_code', 118))
                    
                    self.logger.info(f"Reincarnation settings loaded from {settings_manager.REIN_SETTINGS_FILE}")
            else:
                self.logger.info(f"No {settings_manager.REIN_SETTINGS_FILE} found, using defaults for reincarnation bot.")
                self._loaded_target_index = 0
            
            # Load forage bot settings
            if os.path.exists(str(settings_manager.FORAGE_SETTINGS_FILE)):
                with open(str(settings_manager.FORAGE_SETTINGS_FILE), 'r') as f:
                    forage_settings = json.load(f)
                    
                    # Forage bot settings
                    self.forage_search_region = forage_settings.get('forage_search_region')
                    self.forage_left_arrow = forage_settings.get('forage_left_arrow')
                    self.forage_right_arrow = forage_settings.get('forage_right_arrow')
                    self.forage_detection_method.set(forage_settings.get('forage_detection_method', 'Template Matching'))
                    self.forage_detection_threshold.set(forage_settings.get('forage_detection_threshold', 0.25))
                    self.forage_mouse_speed.set(forage_settings.get('forage_mouse_speed', 0.3))
                    self.forage_total_areas.set(forage_settings.get('forage_total_areas', 6))
                    self.forage_post_click_delay.set(forage_settings.get('forage_post_click_delay', 1.8))
                    
                    # RGB Detection Settings
                    self.forage_rgb_target_r.set(forage_settings.get('forage_rgb_target_r', 255))
                    self.forage_rgb_target_g.set(forage_settings.get('forage_rgb_target_g', 255))
                    self.forage_rgb_target_b.set(forage_settings.get('forage_rgb_target_b', 255))
                    self.forage_rgb_tolerance.set(forage_settings.get('forage_rgb_tolerance', 5))
                    self.forage_rgb_min_cluster.set(forage_settings.get('forage_rgb_min_cluster', 10))
                    self.forage_rgb_max_cluster.set(forage_settings.get('forage_rgb_max_cluster', 1000))
                    
                    # False Positive Learning Settings
                    self.forage_strike_limit.set(forage_settings.get('forage_strike_limit', 5))
                    self.forage_blacklist_radius.set(forage_settings.get('forage_blacklist_radius', 5))
                    
                    # Detection Settings
                    self.forage_nms_threshold.set(forage_settings.get('forage_nms_threshold', 0.3))
                    self.forage_grayscale_min.set(forage_settings.get('forage_grayscale_min', 245))
                    self.forage_grayscale_max.set(forage_settings.get('forage_grayscale_max', 255))
                    self.forage_scale_min.set(forage_settings.get('forage_scale_min', 0.8))
                    self.forage_scale_max.set(forage_settings.get('forage_scale_max', 1.2))
                    self.forage_scale_steps.set(forage_settings.get('forage_scale_steps', 20))
                    
                    # Timing Settings
                    self.forage_scan_interval.set(forage_settings.get('forage_scan_interval', 0.01))
                    self.forage_area_load_delay.set(forage_settings.get('forage_area_load_delay', 1.0))
                    self.forage_click_cooldown.set(forage_settings.get('forage_click_cooldown', 5.0))
                    self.forage_startup_delay.set(forage_settings.get('forage_startup_delay', 3))
                    
                    # Mouse Settings
                    self.forage_snap_distance.set(forage_settings.get('forage_snap_distance', 15))
                    self.forage_variability.set(forage_settings.get('forage_variability', 3))
                    
                    self.logger.info(f"Forage settings loaded from {settings_manager.FORAGE_SETTINGS_FILE}")
            else:
                self.logger.info(f"No {settings_manager.FORAGE_SETTINGS_FILE} found, using defaults for forage bot.")
            
            # Load last selected bot from either settings file (prefer rein file)
            last_bot = None
            if os.path.exists(str(settings_manager.REIN_SETTINGS_FILE)):
                try:
                    with open(str(settings_manager.REIN_SETTINGS_FILE), 'r') as f:
                        rein_settings = json.load(f)
                        last_bot = rein_settings.get('last_selected_bot')
                except:
                    pass
            
            if last_bot:
                self.selected_bot.set(last_bot)
                self.on_bot_selection_changed()
                self.logger.info(f"Restored last selected bot: {last_bot}")
                
        except Exception as e:
            self.logger.error(f"Error loading settings: {e}")
            self._loaded_target_index = 0

    def save_settings(self):
        """Save settings to JSON files - saves bot-specific settings to their respective files."""
        try:
            target_index = self.bloodline_stop_combo.current() if hasattr(self, 'bloodline_stop_combo') else 0
        except Exception:
            target_index = getattr(self, '_loaded_target_index', 0)

        self.logger.debug(f"[SAVE DEBUG] Saving settings for both bots")
        self.logger.debug(f"[SAVE DEBUG] Current bot: {self.selected_bot.get()}")
        self.logger.debug(f"[SAVE DEBUG] qi_region: {self.qi_region}")
        self.logger.debug(f"[SAVE DEBUG] bloodline_region: {self.bloodline_region}")
        self.logger.debug(f"[SAVE DEBUG] forage_search_region: {self.forage_search_region}")
        self.logger.debug(f"[SAVE DEBUG] forage_left_arrow: {self.forage_left_arrow}")
        self.logger.debug(f"[SAVE DEBUG] forage_right_arrow: {self.forage_right_arrow}")

        # Shared settings (saved to both files)
        shared_settings = {
            'font_name': self.font_name_var.get(),
            'font_size': self.font_size_var.get(),
            'clear_on_start': self.clear_on_start_var.get(),
            'log_level': self.log_level_var.get(),
            'hotkey_name': self.hotkey_name_var.get(),
            'hotkey_code': self.hotkey_code_var.get(),
            'last_selected_bot': self.selected_bot.get()
        }

        # Reincarnation bot settings
        rein_settings = {
            'qi_region': self.qi_region,
            'bloodline_region': self.bloodline_region,
            'calibrated_points': self.calibrated_points,
            'ui_mode': self.ui_mode_var.get(),
            'mouse_speed_factor': self.speed_factor_var.get(),
            'mouse_snap_threshold': self.snap_threshold_var.get(),
            'mouse_variability': self.variability_var.get(),
            'after_click_delay': self.after_click_delay_var.get(),
            'stop_on_bloodline': self.stop_on_bloodline_var.get(),
            'stop_on_qi': self.stop_on_qi_var.get(),
            'target_bloodline_index': target_index,
            'target_qi_multi': self.qi_stop_var.get(),
            'stop_on_new': self.stop_on_new_var.get(),
            'show_success_popup': self.show_success_popup_var.get(),
        }
        rein_settings.update(shared_settings)
        
        # Forage bot settings
        forage_settings = {
            'forage_search_region': self.forage_search_region,
            'forage_left_arrow': self.forage_left_arrow,
            'forage_right_arrow': self.forage_right_arrow,
            'forage_detection_method': self.forage_detection_method.get(),
            'forage_detection_threshold': self.forage_detection_threshold.get(),
            'forage_mouse_speed': self.forage_mouse_speed.get(),
            'forage_total_areas': self.forage_total_areas.get(),
            'forage_post_click_delay': self.forage_post_click_delay.get(),
            
            # RGB Detection Settings
            'forage_rgb_target_r': self.forage_rgb_target_r.get(),
            'forage_rgb_target_g': self.forage_rgb_target_g.get(),
            'forage_rgb_target_b': self.forage_rgb_target_b.get(),
            'forage_rgb_tolerance': self.forage_rgb_tolerance.get(),
            'forage_rgb_min_cluster': self.forage_rgb_min_cluster.get(),
            'forage_rgb_max_cluster': self.forage_rgb_max_cluster.get(),
            
            # False Positive Learning Settings
            'forage_strike_limit': self.forage_strike_limit.get(),
            'forage_blacklist_radius': self.forage_blacklist_radius.get(),
            
            # Detection Settings
            'forage_nms_threshold': self.forage_nms_threshold.get(),
            'forage_grayscale_min': self.forage_grayscale_min.get(),
            'forage_grayscale_max': self.forage_grayscale_max.get(),
            'forage_scale_min': self.forage_scale_min.get(),
            'forage_scale_max': self.forage_scale_max.get(),
            'forage_scale_steps': self.forage_scale_steps.get(),
            
            # Timing Settings
            'forage_scan_interval': self.forage_scan_interval.get(),
            'forage_area_load_delay': self.forage_area_load_delay.get(),
            'forage_click_cooldown': self.forage_click_cooldown.get(),
            'forage_startup_delay': self.forage_startup_delay.get(),
            
            # Mouse Settings
            'forage_snap_distance': self.forage_snap_distance.get(),
            'forage_variability': self.forage_variability.get(),
        }
        forage_settings.update(shared_settings)
        
        # Save reincarnation settings
        try:
            with open(str(settings_manager.REIN_SETTINGS_FILE), 'w') as f:
                json.dump(rein_settings, f, indent=4)
            self.logger.debug(f"[SAVE DEBUG] Saved reincarnation settings to {settings_manager.REIN_SETTINGS_FILE}")
        except Exception as e:
            self.logger.error(f"Error saving reincarnation settings to {settings_manager.REIN_SETTINGS_FILE}: {e}")
        
        # Save forage settings
        try:
            with open(str(settings_manager.FORAGE_SETTINGS_FILE), 'w') as f:
                json.dump(forage_settings, f, indent=4)
            self.logger.debug(f"[SAVE DEBUG] Saved forage settings to {settings_manager.FORAGE_SETTINGS_FILE}")
        except Exception as e:
            self.logger.error(f"Error saving forage settings to {settings_manager.FORAGE_SETTINGS_FILE}: {e}")

    def update_status(self, text, color):
        """Update the bottom status bar label."""
        if hasattr(self, 'status_label'):
            self.status_label.config(text=f"Status: {text}")
            self.style.configure("Status.TLabel", foreground=color)

    def start_bot(self):
        """Start the selected bot."""
        if self.start_button['state'] == tk.DISABLED:
            return
        
        selected = self.selected_bot.get()
        
        if selected == "reincarnation":
            # Validate reincarnation bot calibration
            all_calibrated = True
            if not self.qi_region or not self.bloodline_region:
                all_calibrated = False
            for key in self.calibration_widgets:
                if key not in self.calibrated_points:
                    all_calibrated = False
                    break
                    
            if not all_calibrated:
                messagebox.showerror("Error", "Please calibrate all regions and click points in the 'Calibration' tab before starting.")
                self.logger.warning("Reincarnation bot start failed: Not all items calibrated.")
                return
            
            # Start reincarnation bot
            self.stop_event.clear()
            self.bot_thread_stopped_logged = False
            self.set_controls_enabled(False)
            self.save_settings()
            
            config = {
                "ui_mode": self.ui_mode_var.get(),
                "regions": {
                    "qi": self.qi_region,
                    "bloodline": self.bloodline_region
                },
                "calibrated_points": self.calibrated_points,
                "stop_conditions": {
                    "stop_on_bloodline": self.stop_on_bloodline_var.get(),
                    "stop_on_qi": self.stop_on_qi_var.get(),
                    "target_bloodline_index": self.bloodline_stop_combo.current(),
                    "target_qi_multi": self.qi_stop_var.get(),
                    "stop_on_new": self.stop_on_new_var.get(),
                    "show_success_popup": self.show_success_popup_var.get()
                },
                "ranked_bloodlines": self.ranked_bloodlines,
                "ranked_bloodlines_lower": self.ranked_bloodlines_lower,
                "wait_times": {
                    "page_load_delay": 0.5,
                    "reincarnation_load_delay": 15.0,
                    "after_click_delay": self.after_click_delay_var.get(),
                    "button_timeout": 10.0
                },
                "confidence": 0.9,
                "mouse_speed_factor": self.speed_factor_var.get(),
                "mouse_snap_threshold": self.snap_threshold_var.get(),
                "mouse_variability": self.variability_var.get(),
                "mouse_pause": 0.001
            }
            
            self.logger.info("Starting Reincarnation bot thread...")
            self.bot_thread = threading.Thread(
                target=rein_bot_logic.bot_loop,
                args=(config, self.stop_event),
                name="ReinBotThread",
                daemon=True
            )
            self.bot_thread.start()
            
        else:  # forage
            # Validate forage bot calibration
            if not self.forage_search_region or not self.forage_left_arrow or not self.forage_right_arrow:
                messagebox.showerror("Error", "Please calibrate the search region and both arrow positions in the 'Calibration' tab before starting.")
                self.logger.warning("Forage bot start failed: Not all items calibrated.")
                return
            
            # Start forage bot
            self.stop_event.clear()
            self.bot_thread_stopped_logged = False
            self.set_controls_enabled(False)
            self.save_settings()
            
            # Build complete config with all required parameters
            config = {
                # Calibrated positions
                "search_region": self.forage_search_region,
                "left_arrow_pos": self.forage_left_arrow,
                "right_arrow_pos": self.forage_right_arrow,
                
                # Detection method
                "detection_method": self.forage_detection_method.get(),
                
                # Template matching settings
                "detection_threshold": self.forage_detection_threshold.get(),
                "nms_threshold": self.forage_nms_threshold.get(),
                "grayscale_min": self.forage_grayscale_min.get(),
                "grayscale_max": self.forage_grayscale_max.get(),
                "scale_min": self.forage_scale_min.get(),
                "scale_max": self.forage_scale_max.get(),
                "scale_steps": self.forage_scale_steps.get(),
                
                # RGB detection settings
                "rgb_target_r": self.forage_rgb_target_r.get(),
                "rgb_target_g": self.forage_rgb_target_g.get(),
                "rgb_target_b": self.forage_rgb_target_b.get(),
                "rgb_tolerance": self.forage_rgb_tolerance.get(),
                "rgb_min_cluster": self.forage_rgb_min_cluster.get(),
                "rgb_max_cluster": self.forage_rgb_max_cluster.get(),
                
                # Timing settings
                "post_click_delay": self.forage_post_click_delay.get(),
                "scan_interval": self.forage_scan_interval.get(),
                "area_load_delay": self.forage_area_load_delay.get(),
                "click_cooldown_seconds": self.forage_click_cooldown.get(),
                
                # Area settings
                "total_areas": self.forage_total_areas.get(),
                "startup_delay": self.forage_startup_delay.get(),
                
                # Mouse settings
                "mouse_speed_factor": self.forage_mouse_speed.get(),
                "mouse_snap_distance": self.forage_snap_distance.get(),
                "mouse_variability": self.forage_variability.get(),
                
                # Learning settings
                "strike_limit": self.forage_strike_limit.get(),
                "blacklist_radius": self.forage_blacklist_radius.get(),
                "strike_counts": {},
                "blacklist": {}
            }
            
            # Template path
            import os
            template_path = os.path.join(os.path.dirname(__file__), "template.png")
            
            self.logger.info("Starting Forage bot thread...")
            self.logger.debug(f"Template path: {template_path}")
            
            try:
                self.bot_thread = threading.Thread(
                    target=forage_bot_logic.forage_bot_loop,
                    args=(config, self.stop_event, template_path),
                    name="ForageBotThread",
                    daemon=True
                )
                self.bot_thread.start()
                self.logger.info("Forage bot thread started successfully")
            except Exception as e:
                self.logger.error(f"Failed to start forage bot thread: {e}")
                self.set_controls_enabled(True)

    def stop_bot(self):
        """Stop the bot."""
        if self.stop_button['state'] == tk.DISABLED:
            return
        self.logger.info("Stop signal sent to bot thread...")
        self.update_status("Stopping...", "#ffca28")
        self.stop_event.set()

    def set_controls_enabled(self, enabled):
        """Enable or disable all settings widgets."""
        state = tk.NORMAL if enabled else tk.DISABLED
        readonly_state = "readonly" if enabled else tk.DISABLED
        
        # Disable all tabs except the first one when running
        for i in range(self.notebook.index("end")):
            if enabled:
                self.notebook.tab(i, state=tk.NORMAL)
            else:
                self.notebook.tab(i, state=tk.DISABLED)

        if not enabled:
            self.notebook.tab(0, state=tk.NORMAL)
            self.notebook.select(0)

        # Update button states
        if enabled:
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.update_status("Idle", "#FAFAFA")
        else:
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.update_status("Running...", "#66bb6a")

    def toggle_bot_state(self):
        """Toggle bot state (for hotkey)."""
        if self.bot_thread and self.bot_thread.is_alive():
            self.logger.info(f"Hotkey '{self.hotkey_name_var.get()}' pressed: Stopping bot.")
            self.stop_bot()
        else:
            self.logger.info(f"Hotkey '{self.hotkey_name_var.get()}' pressed: Starting bot.")
            self.start_bot()

    def check_log_queue(self):
        """Check for log messages and update GUI."""
        while True:
            try:
                record = self.log_queue.get_nowait()
                
                if record.levelno >= logging.ERROR:
                    self.update_status("Error! Check log.", "#ef5350")

                if hasattr(record, 'msg') and record.msg.startswith("SUCCESS_POPUP:"):
                    message = record.msg.split(":", 1)[1].strip()
                    messagebox.showinfo("Target Found!", message)
                    self.log_to_widget(self.log_formatter.format(record))
                else:
                    message = self.log_formatter.format(record)
                    self.log_to_widget(message)
                    
            except queue.Empty:
                break
        
        if self.bot_thread and not self.bot_thread.is_alive():
            if not self.bot_thread_stopped_logged:
                self.logger.info("Bot thread has finished.")
                self.set_controls_enabled(True)
                self.bot_thread_stopped_logged = True
            
        self.root.after(100, self.check_log_queue)

    def log_to_widget(self, message):
        """Add a message to the log widget."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + '\n')
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def on_closing(self):
        """Handle window close event."""
        self.logger.info("Window closing. Sending stop signal...")
        self.save_settings()
        
        # Stop the bot if running
        if self.bot_thread and self.bot_thread.is_alive():
            self.stop_event.set()
        
        # Give the thread a short time to stop (max 2 seconds)
        if self.bot_thread and self.bot_thread.is_alive():
            self.bot_thread.join(timeout=2.0)
            
            # If still alive after timeout, log warning and force close
            if self.bot_thread.is_alive():
                self.logger.warning("Bot thread did not stop in time. Force closing...")
        
        # Destroy the window
        self.root.destroy()