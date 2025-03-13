import tkinter as tk
from tkinter import ttk, PhotoImage
import subprocess
import psutil
import os
import threading
import sys
try:
    from PIL import Image, ImageTk
except ImportError:
    print("PIL not available, falling back to standard PhotoImage")
import ctypes

class Windows11Theme:
    """Windows 11 styling for Tkinter"""
    def __init__(self, root):
        self.style = ttk.Style(root)
        self.configure_styles()
        
    def configure_styles(self):
        # Windows 11 colors
        self.accent_color = "#0067C0"  # Windows 11 accent blue
        self.bg_color = "#F9F9F9"      # Light background
        self.text_color = "#202020"    # Dark text
        self.border_color = "#E1DFDE"  # Light border
        self.card_bg = "#FFFFFF"       # Card background
        
        # Configure the root style
        self.style.configure('TFrame', background=self.bg_color)
        self.style.configure('TLabel', background=self.bg_color, foreground=self.text_color)
        
        # Card frame style
        self.style.configure('Card.TFrame', 
                            background=self.card_bg,
                            relief='flat',
                            borderwidth=0)
        
        # Configure button styles with rounded corners effect
        self.style.configure('TButton', 
                             background='white',
                             foreground=self.text_color,
                             font=('Segoe UI Variable', 10),
                             relief=tk.FLAT,
                             borderwidth=0,
                             padding=(15, 8))
        
        # Green action button style
        self.style.configure('Success.TButton',
                             background='#13A10E',  # Windows 11 green
                             foreground='white',
                             font=('Segoe UI Variable', 10, 'bold'),
                             relief=tk.FLAT,
                             borderwidth=0,
                             padding=(15, 10))
        
        # Red action button style
        self.style.configure('Danger.TButton',
                             background='#E81123',  # Windows 11 red
                             foreground='white',
                             font=('Segoe UI Variable', 10, 'bold'),
                             relief=tk.FLAT,
                             borderwidth=0,
                             padding=(15, 10))
        
        # Hover styles
        self.style.map('TButton',
                      background=[('active', '#F5F5F5'), ('pressed', '#E5E5E5')],
                      relief=[('pressed', 'flat')])
        
        self.style.map('Success.TButton',
                      background=[('active', '#16C60C'), ('pressed', '#107C10')],
                      foreground=[('active', 'white'), ('pressed', 'white')])
        
        self.style.map('Danger.TButton',
                      background=[('active', '#FF4343'), ('pressed', '#C42B1C')],
                      foreground=[('active', 'white'), ('pressed', 'white')])
        
        # Content frame style
        self.style.configure('Content.TFrame', 
                            background=self.bg_color,
                            relief=tk.FLAT)
        
        # Status label styles
        self.style.configure('Status.TLabel',
                           font=('Segoe UI Variable', 12),
                           background=self.card_bg,
                           padding=10)
        
        self.style.configure('StatusIdle.TLabel',
                           foreground='#0078D7',
                           background=self.card_bg)
        
        self.style.configure('StatusRunning.TLabel',
                           foreground='#107C10',
                           background=self.card_bg)
        
        self.style.configure('StatusStopped.TLabel',
                           foreground='#E81123',
                           background=self.card_bg)
        
        # Title styles
        self.style.configure('Title.TLabel',
                           font=('Segoe UI Variable', 18, 'bold'),
                           background=self.bg_color,
                           padding=(0, 5, 0, 5))
        
        # Center aligned title style
        self.style.configure('CenterTitle.TLabel',
                           font=('Segoe UI Variable', 18, 'bold'),
                           background=self.bg_color,
                           padding=(0, 5, 0, 5),
                           anchor='center')
        
        # Separator style
        self.style.configure('TSeparator', 
                           background='#E0E0E0')

def set_taskbar_icon(root, icon_path=None):
    """Set both window and taskbar icons for a Tkinter application."""
    # For Windows taskbar icon
    if sys.platform.startswith('win'):
        try:
            # Windows-specific method to set the taskbar icon
            myappid = 'mycompany.aibroker.app'  # Arbitrary but unique string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            
            # If icon path is provided and exists, set it
            if icon_path and os.path.exists(icon_path):
                try:
                    root.iconbitmap(icon_path)
                except Exception as e:
                    print(f"Could not set window icon: {e}")
            
        except Exception as e:
            print(f"Error setting taskbar icon: {e}")

class RoundedButton(tk.Canvas):
    """Custom rounded button widget for Windows 11 look"""
    def __init__(self, parent, text, command=None, radius=10, bg="#0067C0", fg="white", 
                 hoverbg="#0078D4", pressbg="#005A9E", width=110, height=40, **kwargs):
        # Use a fixed background color that matches parent's theme instead of
        # trying to access parent's background property
        parent_bg = "#F9F9F9"  # Default to Windows 11 light background
        
        # Try to get background from ttk style if it's a ttk widget
        if isinstance(parent, ttk.Frame) or isinstance(parent, ttk.LabelFrame):
            try:
                style_name = parent.winfo_class()
                if style_name:
                    parent_bg = ttk.Style().lookup(style_name, 'background') or parent_bg
            except:
                pass  # Fall back to default if lookup fails
        
        super().__init__(parent, width=width, height=height, bg=parent_bg,
                        highlightthickness=0, **kwargs)
        
        self.radius = radius
        self.bg = bg
        self.fg = fg
        self.hoverbg = hoverbg
        self.pressbg = pressbg
        self.current_bg = bg
        self.width = width
        self.height = height
        self.command = command
        self.text = text
        
        # Draw initial button
        self.draw_button()
        
        # Bind events
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<ButtonRelease-1>", self.on_release)
    
    def draw_button(self):
        self.delete("all")
        
        # Draw rounded rectangle
        self.create_rounded_rect(0, 0, self.width, self.height, self.radius, 
                                fill=self.current_bg, outline="")
        
        # Draw text
        self.create_text(self.width/2, self.height/2, text=self.text,
                       fill=self.fg, font=("Segoe UI Variable", 10, "bold"))
    
    def create_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        # Create rounded rectangle shape
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1
        ]
        return self.create_polygon(points, **kwargs, smooth=True)
    
    def on_enter(self, event):
        self.current_bg = self.hoverbg
        self.draw_button()
    
    def on_leave(self, event):
        self.current_bg = self.bg
        self.draw_button()
    
    def on_press(self, event):
        self.current_bg = self.pressbg
        self.draw_button()
    
    def on_release(self, event):
        self.current_bg = self.hoverbg
        self.draw_button()
        if self.command:
            self.command()

class StatusCard(ttk.Frame):
    """A Windows 11 style card for displaying status information"""
    def __init__(self, parent, initial_status="Idle", **kwargs):
        super().__init__(parent, style="Card.TFrame", **kwargs)
        
        # Card content with padding
        padding_frame = ttk.Frame(self, style="Card.TFrame")
        padding_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=12)
        
        # Status
        self.status_frame = ttk.Frame(padding_frame, style="Card.TFrame")
        self.status_frame.pack(fill=tk.X, pady=5)
        
        # Status indicators
        self.status_indicator = tk.Canvas(self.status_frame, width=20, height=20, 
                                       bg="#FFFFFF", highlightthickness=0)
        self.status_indicator.pack(side=tk.LEFT, padx=(0, 10))
        self.draw_status_indicator("idle")
        
        self.status_label = ttk.Label(self.status_frame, text=initial_status, 
                                     style="Status.TLabel StatusIdle.TLabel")
        self.status_label.pack(side=tk.LEFT, fill=tk.X)
    
    def draw_status_indicator(self, status):
        self.status_indicator.delete("all")
        if status == "idle":
            color = "#0078D7"  # Blue
        elif status == "running":
            color = "#13A10E"  # Green
        elif status == "error":
            color = "#E81123"  # Red
        else:
            color = "#767676"  # Gray
            
        # Draw a circle
        self.status_indicator.create_oval(4, 4, 16, 16, fill=color, outline="")
    
    def update_status(self, text, status):
        self.status_label.config(text=text)
        
        # Update indicator
        self.draw_status_indicator(status)
        
        # Update label style
        if status == "idle":
            self.status_label.configure(style="Status.TLabel StatusIdle.TLabel")
        elif status == "running":
            self.status_label.configure(style="Status.TLabel StatusRunning.TLabel")
        elif status == "error":
            self.status_label.configure(style="Status.TLabel StatusStopped.TLabel")

class AIBrokerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Broker")
        self.root.geometry("380x370")  # Increased height from 350 to 370 for version visibility
        self.root.configure(bg="#F9F9F9")  # Windows 11 background color
        self.root.resizable(False, False)  # Lock window size
        
        # Apply Windows 11 theming
        self.theme = Windows11Theme(self.root)
        
        # Try to load and set the icon 
        self.try_set_icon()
        
        # Variables to store script processes
        self.script_processes = []
        
        # Create the main layout
        self.setup_layout()
    
    def try_set_icon(self):
        # Look for icon in possible locations
        icon_paths = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "ka.ico"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo", "ka.ico"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "ka.ico"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "ka.ico")
        ]
        
        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                set_taskbar_icon(self.root, icon_path)
                return
        
        # If no icon found, still set app ID for taskbar
        set_taskbar_icon(self.root)
    
    def try_load_image(self, image_name, fallback_text="AI Broker", max_size=(100, 100)):
        """Try to load an image from various possible locations with better sizing"""
        # List of possible paths
        possible_paths = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), image_name),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo", image_name),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", image_name),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "images", image_name)
        ]
        
        # Try different file extensions if not specified
        if "." not in image_name:
            extensions = [".png", ".jpg", ".jpeg", ".gif", ".ico"]
            extended_paths = []
            for path in possible_paths:
                for ext in extensions:
                    extended_paths.append(path + ext)
            possible_paths.extend(extended_paths)
        
        # Try each path
        for path in possible_paths:
            if os.path.exists(path):
                try:
                    # Try using PIL for better image support
                    if 'PIL' in sys.modules:
                        pil_img = Image.open(path)
                        
                        # Resize if the image is too large
                        orig_width, orig_height = pil_img.size
                        max_width, max_height = max_size
                        
                        # Calculate resize ratio to maintain aspect ratio
                        if orig_width > max_width or orig_height > max_height:
                            ratio = min(max_width/orig_width, max_height/orig_height)
                            new_width = int(orig_width * ratio)
                            new_height = int(orig_height * ratio)
                            pil_img = pil_img.resize((new_width, new_height), Image.LANCZOS)
                        
                        img = ImageTk.PhotoImage(pil_img)
                        return img, None
                    else:
                        # Fall back to standard PhotoImage
                        img = PhotoImage(file=path)
                        return img, None
                except Exception as e:
                    print(f"Error loading image {path}: {e}")
        
        # Return a text label as fallback
        return None, fallback_text
    
    def setup_layout(self):
        # Configure the grid
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=0)
        self.root.grid_rowconfigure(2, weight=0)
        self.root.grid_rowconfigure(3, weight=0)
        self.root.grid_rowconfigure(4, weight=0)
        
        # Create a main frame with padding
        main_frame = ttk.Frame(self.root, style='Content.TFrame')
        main_frame.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        main_frame.grid_columnconfigure(0, weight=1)  # Center all children
        
        # Title with app name - properly centered
        title_container = ttk.Frame(main_frame, style='Content.TFrame')
        title_container.grid(row=0, column=0, sticky="ew")
        title_container.grid_columnconfigure(0, weight=1)  # This enables center alignment
        
        app_title = ttk.Label(title_container, 
                            text="AI Broker Control Panel", 
                            style='CenterTitle.TLabel')
        app_title.grid(row=0, column=0)
        
        # App logo with controlled size in its own frame
        logo_frame = ttk.Frame(main_frame, style='Content.TFrame', height=110)
        logo_frame.grid(row=1, column=0, sticky="ew", pady=10)
        logo_frame.grid_columnconfigure(0, weight=1)  # Enable centering
        logo_frame.grid_propagate(False)  # Maintain fixed height
        
        # Load image with larger size limit
        logo_img, fallback_text = self.try_load_image("ka", max_size=(100, 100))
        if logo_img:
            logo_label = ttk.Label(logo_frame, image=logo_img)
            logo_label.image = logo_img  # Keep a reference
            logo_label.grid(row=0, column=0)
        else:
            logo_label = ttk.Label(logo_frame, text=fallback_text, 
                                font=("Segoe UI Variable", 16, "bold"))
            logo_label.grid(row=0, column=0)
        
        # Status card
        self.status_card = StatusCard(
            main_frame, 
            "System is ready"
        )
        self.status_card.grid(row=2, column=0, sticky="ew", pady=10)
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame, style='Content.TFrame')
        button_frame.grid(row=3, column=0, sticky="ew", pady=10)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        
        # Start button - using new RoundedButton
        self.start_btn = RoundedButton(
            button_frame,
            text="Start",
            command=self.start_multiple_rpa,
            bg="#13A10E",  # Windows 11 green
            hoverbg="#16C60C",
            pressbg="#107C10",
            width=110,
            height=40
        )
        self.start_btn.grid(row=0, column=0, padx=(20, 10), pady=5)
        
        # Stop button - using new RoundedButton
        self.stop_btn = RoundedButton(
            button_frame,
            text="Stop",
            command=self.stop_all_rpa,
            bg="#E81123",  # Windows 11 red
            hoverbg="#FF4343",
            pressbg="#C42B1C",
            width=110,
            height=40
        )
        self.stop_btn.grid(row=0, column=1, padx=(10, 20), pady=5)
        
        # Add a footer with version info
        footer_frame = ttk.Frame(main_frame, style='Content.TFrame')
        footer_frame.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        footer_frame.grid_columnconfigure(0, weight=1)  # To push the footer to the right
        
        footer = ttk.Label(footer_frame, 
                        text="AI Broker v1.0.5", 
                        font=("Segoe UI Variable", 8),
                        foreground="#767676")
        footer.grid(row=0, column=0, sticky="e")
    
    def start_multiple_rpa(self):
        if not self.script_processes:  # Ensure scripts aren't already running
            try:
                # Define the scripts to run
                python_executable = r"C:\Users\Hello World!\AppData\Local\Programs\Python\Python312\pythonw.exe"
                scripts = [
                    r"C:\Users\Hello World!\Desktop\COMPLETE\SELENIUM-RPA\rpa.py",
                    r"C:\Users\Hello World!\Desktop\COMPLETE\SELENIUM\test.py",
                    r"C:\Users\Hello World!\Desktop\COMPLETE\AIBROKER-NOTIF\aitable_notifier.py"
                ]
                
                # Run in a separate thread
                def run_scripts():
                    for script_path in scripts:
                        process = subprocess.Popen(
                            [python_executable, script_path],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
                        )
                        self.script_processes.append(process)
                    
                    # Update status in a user-friendly way for elderly users
                    self.status_card.update_status("AI assistant is now working", "running")
                
                # Start the script-running in a new thread
                threading.Thread(target=run_scripts, daemon=True).start()
            
            except Exception as e:
                # Update status to error with simplified message
                self.status_card.update_status("Something went wrong", "error")
        else:
            # Update status to indicate scripts are already running
            self.status_card.update_status("AI assistant is already working", "running")
    
    def stop_all_rpa(self):
        if self.script_processes:  # Check if scripts are running
            try:
                for process in self.script_processes:
                    if process.poll() is None:  # Check if the script is running
                        parent_proc = psutil.Process(process.pid)
                        
                        # Terminate child processes
                        for child in parent_proc.children(recursive=True):
                            child.terminate()
                        parent_proc.terminate()
                
                self.script_processes.clear()  # Clear the list of processes
                
                # Update status with user-friendly message
                self.status_card.update_status("AI assistant has been stopped", "error")
            except Exception as e:
                # Update status with error
                self.status_card.update_status("Could not stop the AI assistant", "error")
        else:
            # Update status to indicate no scripts are running
            self.status_card.update_status("AI assistant is not running", "idle")

# Initialize the application
if __name__ == "__main__":
    # Check if PIL is available and import it if so
    try:
        from PIL import Image, ImageTk
    except ImportError:
        print("PIL not available, falling back to standard PhotoImage")
    
    root = tk.Tk()
    app = AIBrokerApp(root)
    root.mainloop()