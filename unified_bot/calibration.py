import tkinter as tk

class CalibrationWindow:
    """
    Creates a full-screen, semi-transparent window to allow the user
    to select a screen region by clicking and dragging.
    """
    # --- MODIFIED: Added scale_x and scale_y ---
    def __init__(self, root, title, on_complete_callback, scale_x=1.0, scale_y=1.0):
        """
        Initializes the calibration window.
        :param root: The main Tkinter root window (to minimize/restore).
        :param title: The title/instruction to display.
        :param on_complete_callback: The function to call when selection is complete.
                                     This function will be passed the region rect.
        :param scale_x: The horizontal display scaling factor.
        :param scale_y: The vertical display scaling factor.
        """
        self.root = root
        self.on_complete_callback = on_complete_callback
        # --- NEW ---
        self.scale_x = scale_x
        self.scale_y = scale_y
        
        # Minimize the main window
        self.root.iconify()

        # Create the full-screen, borderless, transparent top-level window
        self.top = tk.Toplevel(root)
        self.top.overrideredirect(True) # Borderless
        
        screen_width = self.top.winfo_screenwidth()
        screen_height = self.top.winfo_screenheight()
        self.top.geometry(f"{screen_width}x{screen_height}+0+0")
        
        # Make it semi-transparent (e.g., 30% opaque)
        self.top.wait_visibility(self.top) # Wait for window to be mapped
        self.top.attributes('-alpha', 0.3)
        self.top.attributes('-topmost', True) # Stay on top

        # Create a canvas to draw on
        self.canvas = tk.Canvas(self.top, bg="black", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Add instruction label
        self.label = tk.Label(
            self.canvas, 
            text=f"Calibrating: {title}\nClick and DRAG to select the region. Press ESC to cancel.",
            fg="white", 
            bg="black",
            font=("Arial", 16)
        )
        self.label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Store coordinates
        self.start_x = None
        self.start_y = None
        self.rect = None

        # Bind mouse events
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.top.bind("<Escape>", self.on_cancel)
        
        self.top.focus_force()

    def on_press(self, event):
        """Called on mouse click."""
        self.label.place_forget() # Hide label
        self.start_x = event.x
        self.start_y = event.y
        
        # Create a rectangle (green, dashed)
        if not self.rect:
            self.rect = self.canvas.create_rectangle(
                self.start_x, self.start_y, self.start_x + 1, self.start_y + 1, 
                outline="green", width=2, dash=(5, 5)
            )

    def on_drag(self, event):
        """Called on mouse drag."""
        if not self.rect:
            return
            
        cur_x, cur_y = event.x, event.y
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_release(self, event):
        """Called on mouse release."""
        end_x, end_y = event.x, event.y
        
        # --- MODIFIED: Apply scaling factors to final coordinates ---
        start_x_scaled = self.start_x * self.scale_x
        start_y_scaled = self.start_y * self.scale_y
        end_x_scaled = end_x * self.scale_x
        end_y_scaled = end_y * self.scale_y

        x = min(start_x_scaled, end_x_scaled)
        y = min(start_y_scaled, end_y_scaled)
        w = abs(start_x_scaled - end_x_scaled)
        h = abs(start_y_scaled - end_y_scaled)
        
        # Ensure width and height are at least 1
        w = max(1, w)
        h = max(1, h)
        
        region_rect = [int(x), int(y), int(w), int(h)]
        # --- END MODIFICATION ---
        
        self.close()
        
        # Call the callback with the result
        if w > 0 and h > 0:
            self.on_complete_callback(region_rect)
        else:
            # Handle case where drag was too small or just a click
            self.on_complete_callback(None) # Signal cancellation

    def on_cancel(self, event=None):
        """Called on ESC press."""
        self.close()
        self.on_complete_callback(None) # Pass None to indicate cancellation

    def close(self):
        """Closes the calibration window and restores the main window."""
        self.top.destroy()
        self.root.deiconify() # Restore main window


class CalibrationClickWindow:
    """
    Creates a full-screen, semi-transparent window to allow the user
    to select a single point by clicking.
    """
    # --- MODIFIED: Added scale_x and scale_y ---
    def __init__(self, root, title, on_complete_callback, scale_x=1.0, scale_y=1.0):
        """
        Initializes the calibration window.
        :param root: The main Tkinter root window.
        :param title: The title/instruction to display.
        :param on_complete_callback: The function to call when selection is complete.
                                     This function will be passed the [x, y] point.
        :param scale_x: The horizontal display scaling factor.
        :param scale_y: The vertical display scaling factor.
        """
        self.root = root
        self.on_complete_callback = on_complete_callback
        # --- NEW ---
        self.scale_x = scale_x
        self.scale_y = scale_y
        
        # Minimize the main window
        self.root.iconify()

        # Create the full-screen, borderless, transparent top-level window
        self.top = tk.Toplevel(root)
        self.top.overrideredirect(True) # Borderless
        
        screen_width = self.top.winfo_screenwidth()
        screen_height = self.top.winfo_screenheight()
        self.top.geometry(f"{screen_width}x{screen_height}+0+0")
        
        # Make it semi-transparent (e.g., 30% opaque)
        self.top.wait_visibility(self.top) # Wait for window to be mapped
        self.top.attributes('-alpha', 0.3)
        self.top.attributes('-topmost', True) # Stay on top

        # Create a canvas to draw on
        self.canvas = tk.Canvas(self.top, bg="black", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Add instruction label
        self.label = tk.Label(
            self.canvas, 
            text=f"Calibrating: {title}\nCLICK the target location. Press ESC to cancel.",
            fg="white", 
            bg="black",
            font=("Arial", 16)
        )
        self.label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Bind mouse events
        self.canvas.bind("<ButtonPress-1>", self.on_click)
        self.top.bind("<Escape>", self.on_cancel)
        
        self.top.focus_force()

    def on_click(self, event):
        """Called on mouse click."""
        
        # --- MODIFIED: Apply scaling factors to the click coordinate ---
        x_scaled = event.x * self.scale_x
        y_scaled = event.y * self.scale_y
        point = [int(x_scaled), int(y_scaled)]
        # --- END MODIFICATION ---
        
        self.close()
        self.on_complete_callback(point)

    def on_cancel(self, event=None):
        """Called on ESC press."""
        self.close()
        self.on_complete_callback(None) # Pass None to indicate cancellation

    def close(self):
        """Closes the calibration window and restores the main window."""
        self.top.destroy()
        self.root.deiconify() # Restore main window

