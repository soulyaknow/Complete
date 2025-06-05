import tkinter as tk
from tkinter import ttk, PhotoImage
import subprocess
import psutil
import os
import threading
import sys
import time
import logging
import queue
from datetime import datetime
import signal
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

class RoundedButton(tk.Canvas):
    """Custom rounded button widget for Windows 11 look"""
    def __init__(self, parent, text, command=None, radius=10, bg="#0067C0", fg="white", 
                 hoverbg="#0078D4", pressbg="#005A9E", width=110, height=40, **kwargs):
        parent_bg = "#F9F9F9"  # Default to Windows 11 light background
        
        if isinstance(parent, ttk.Frame) or isinstance(parent, ttk.LabelFrame):
            try:
                style_name = parent.winfo_class()
                if style_name:
                    parent_bg = ttk.Style().lookup(style_name, 'background') or parent_bg
            except:
                pass
        
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
        self.enabled = True
        
        self.draw_button()
        
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<ButtonRelease-1>", self.on_release)
    
    def draw_button(self):
        self.delete("all")
        self.create_rounded_rect(0, 0, self.width, self.height, self.radius, 
                                fill=self.current_bg if self.enabled else "#CCCCCC", outline="")
        self.create_text(self.width/2, self.height/2, text=self.text,
                       fill=self.fg if self.enabled else "#666666", 
                       font=("Segoe UI Variable", 10, "bold"))
    
    def create_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
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
    
    def enable(self):
        self.enabled = True
        self.draw_button()
    
    def disable(self):
        self.enabled = False
        self.draw_button()
    
    def on_enter(self, event):
        if self.enabled:
            self.current_bg = self.hoverbg
            self.draw_button()
    
    def on_leave(self, event):
        if self.enabled:
            self.current_bg = self.bg
            self.draw_button()
    
    def on_press(self, event):
        if self.enabled:
            self.current_bg = self.pressbg
            self.draw_button()
    
    def on_release(self, event):
        if self.enabled:
            self.current_bg = self.hoverbg
            self.draw_button()
            if self.command:
                self.command()

class ProcessManager:
    def __init__(self):
        self.processes = {}
        self.lock = threading.Lock()
        self.status_queue = queue.Queue()
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    
    def start_process(self, name, cmd, python_exe):
        with self.lock:
            try:
                if name not in self.processes:
                    # Set environment variables
                    env = os.environ.copy()
                    env['PYTHONUNBUFFERED'] = '1'
                    
                    # Set working directory to the script's directory
                    working_dir = os.path.dirname(os.path.abspath(cmd))
                    
                    # Create process with proper flags
                    process = subprocess.Popen(
                        [python_exe, cmd],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        cwd=working_dir,
                        env=env,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        text=True,
                        bufsize=1
                    )
                    
                    # Start output monitoring threads
                    threading.Thread(
                        target=self._monitor_output,
                        args=(process.stdout, f"{name}-stdout"),
                        daemon=True
                    ).start()
                    
                    threading.Thread(
                        target=self._monitor_output,
                        args=(process.stderr, f"{name}-stderr"),
                        daemon=True
                    ).start()
                    
                    self.processes[name] = {
                        'process': process,
                        'start_time': datetime.now(),
                        'status': 'running',
                        'restart_count': 0,
                        'working_dir': working_dir
                    }
                    logging.info(f"Started process: {name} in directory: {working_dir}")
                    return True
                return False
            except Exception as e:
                logging.error(f"Error starting process {name}: {e}")
                return False
    
    def _monitor_output(self, pipe, name):
        """Monitor process output streams."""
        try:
            for line in iter(pipe.readline, ''):
                if line:
                    logging.info(f"{name}: {line.strip()}")
            pipe.close()
        except Exception as e:
            logging.error(f"Error monitoring {name}: {e}")
    
    def stop_process(self, name):
        with self.lock:
            if name in self.processes:
                try:
                    process_info = self.processes[name]
                    process = process_info['process']
                    
                    if process.poll() is None:
                        try:
                            parent = psutil.Process(process.pid)
                            children = parent.children(recursive=True)
                            
                            # First try graceful termination
                            parent.terminate()
                            
                            # Wait for parent to terminate
                            try:
                                parent.wait(timeout=5)
                            except psutil.TimeoutExpired:
                                # Force kill if timeout
                                parent.kill()
                            
                            # Handle any remaining children
                            for child in children:
                                try:
                                    if child.is_running():
                                        child.terminate()
                                        try:
                                            child.wait(timeout=3)
                                        except psutil.TimeoutExpired:
                                            child.kill()
                                except (psutil.NoSuchProcess, psutil.AccessDenied):
                                    pass
                            
                            process_info['status'] = 'stopped'
                            logging.info(f"Stopped process: {name}")
                            
                        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                            logging.error(f"Error stopping process {name}: {e}")
                    
                    del self.processes[name]
                    return True
                except Exception as e:
                    logging.error(f"Error stopping process {name}: {e}")
                    return False
            return False
    
    def stop_all(self):
        with self.lock:
            for name in list(self.processes.keys()):
                self.stop_process(name)
    
    def is_running(self, name):
        with self.lock:
            if name in self.processes:
                process = self.processes[name]['process']
                try:
                    # Check if process is actually running
                    if process.poll() is None:
                        psutil.Process(process.pid)  # Will raise if process doesn't exist
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    return False
            return False
    
    def check_health(self):
        with self.lock:
            for name, info in list(self.processes.items()):
                process = info['process']
                try:
                    # Check if process is still running
                    if process.poll() is not None:
                        # Process has died, attempt to restart if not manually stopped
                        if info['status'] != 'stopped' and info['restart_count'] < 3:
                            logging.warning(f"Process {name} has died, attempting restart")
                            self.restart_process(name)
                        else:
                            logging.warning(f"Process {name} has died and exceeded restart attempts")
                            del self.processes[name]
                except Exception as e:
                    logging.error(f"Error checking process {name} health: {e}")

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
        self.draw_status_indicator(status)
        
        if status == "idle":
            self.status_label.configure(style="Status.TLabel StatusIdle.TLabel")
        elif status == "running":
            self.status_label.configure(style="Status.TLabel StatusRunning.TLabel")
        elif status == "error":
            self.status_label.configure(style="Status.TLabel StatusStopped.TLabel")

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

class AIBrokerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Broker")
        self.root.geometry("380x370")
        self.root.configure(bg="#F9F9F9")
        self.root.resizable(False, False)
        
        # Initialize process manager
        self.process_manager = ProcessManager()
        
        # Apply Windows 11 theming
        self.theme = Windows11Theme(self.root)
        
        # Variables to store script processes
        self.script_processes = {}
        
        self.try_set_icon()
        self.setup_layout()
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self.monitor_processes, daemon=True)
        self.monitor_thread.start()
    
    def try_set_icon(self):
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
        possible_paths = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), image_name),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo", image_name),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", image_name),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "images", image_name)
        ]
        
        if "." not in image_name:
            extensions = [".png", ".jpg", ".jpeg", ".gif", ".ico"]
            extended_paths = []
            for path in possible_paths:
                for ext in extensions:
                    extended_paths.append(path + ext)
            possible_paths.extend(extended_paths)
        
        for path in possible_paths:
            if os.path.exists(path):
                try:
                    if 'PIL' in sys.modules:
                        pil_img = Image.open(path)
                        orig_width, orig_height = pil_img.size
                        max_width, max_height = max_size
                        
                        if orig_width > max_width or orig_height > max_height:
                            ratio = min(max_width/orig_width, max_height/orig_height)
                            new_width = int(orig_width * ratio)
                            new_height = int(orig_height * ratio)
                            pil_img = pil_img.resize((new_width, new_height), Image.LANCZOS)
                        
                        img = ImageTk.PhotoImage(pil_img)
                        return img, None
                    else:
                        img = PhotoImage(file=path)
                        return img, None
                except Exception as e:
                    print(f"Error loading image {path}: {e}")
        
        return None, fallback_text
    
    def setup_layout(self):
        self.root.grid_columnconfigure(0, weight=1)
        
        main_frame = ttk.Frame(self.root, style='Content.TFrame')
        main_frame.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        main_frame.grid_columnconfigure(0, weight=1)
        
        title_container = ttk.Frame(main_frame, style='Content.TFrame')
        title_container.grid(row=0, column=0, sticky="ew")
        title_container.grid_columnconfigure(0, weight=1)
        
        app_title = ttk.Label(title_container, 
                            text="AI Broker Control Panel", 
                            style='CenterTitle.TLabel')
        app_title.grid(row=0, column=0)
        
        logo_frame = ttk.Frame(main_frame, style='Content.TFrame', height=110)
        logo_frame.grid(row=1, column=0, sticky="ew", pady=10)
        logo_frame.grid_columnconfigure(0, weight=1)
        logo_frame.grid_propagate(False)
        
        logo_img, fallback_text = self.try_load_image("ka", max_size=(100, 100))
        if logo_img:
            logo_label = ttk.Label(logo_frame, image=logo_img)
            logo_label.image = logo_img
            logo_label.grid(row=0, column=0)
        else:
            logo_label = ttk.Label(logo_frame, text=fallback_text, 
                                font=("Segoe UI Variable", 16, "bold"))
            logo_label.grid(row=0, column=0)
        
        self.status_card = StatusCard(
            main_frame, 
            "System is ready"
        )
        self.status_card.grid(row=2, column=0, sticky="ew", pady=10)
        
        button_frame = ttk.Frame(main_frame, style='Content.TFrame')
        button_frame.grid(row=3, column=0, sticky="ew", pady=10)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        
        self.start_btn = RoundedButton(
            button_frame,
            text="Start",
            command=self.start_multiple_rpa,
            bg="#13A10E",
            hoverbg="#16C60C",
            pressbg="#107C10",
            width=110,
            height=40
        )
        self.start_btn.grid(row=0, column=0, padx=(20, 10), pady=5)
        
        self.stop_btn = RoundedButton(
            button_frame,
            text="Stop",
            command=self.stop_all_rpa,
            bg="#E81123",
            hoverbg="#FF4343",
            pressbg="#C42B1C",
            width=110,
            height=40
        )
        self.stop_btn.grid(row=0, column=1, padx=(10, 20), pady=5)
        
        footer_frame = ttk.Frame(main_frame, style='Content.TFrame')
        footer_frame.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        footer_frame.grid_columnconfigure(0, weight=1)
        
        footer = ttk.Label(footer_frame, 
                        text="AI Broker v1.0.5", 
                        font=("Segoe UI Variable", 8),
                        foreground="#767676")
        footer.grid(row=0, column=0, sticky="e")
    
    def start_multiple_rpa(self):
        if not self.script_processes:
            try:
                python_executable = r"C:\Users\user\AppData\Local\Programs\Python\Python313\pythonw.exe"
                scripts = {
                    'rpa': r"C:\Users\user\Desktop\Complete\SELENIUM\test.py",
                    'notifier': r"C:\Users\user\Desktop\Complete\AIBROKER-NOTIF\aitable_notifier.py"
                }
                
                for name, script_path in scripts.items():
                    if os.path.exists(script_path):
                        if self.process_manager.start_process(name, script_path, python_executable):
                            self.script_processes[name] = True
                
                self.status_card.update_status("AI assistant is now working", "running")
                self.start_btn.disable()
                self.stop_btn.enable()
                
            except Exception as e:
                logging.error(f"Error starting RPA: {e}")
                self.status_card.update_status("Something went wrong", "error")
    
    def stop_all_rpa(self):
        if self.script_processes:
            try:
                for name in list(self.script_processes.keys()):
                    self.process_manager.stop_process(name)
                
                self.script_processes.clear()
                self.status_card.update_status("AI assistant has been stopped", "idle")
                self.start_btn.enable()
                self.stop_btn.disable()
                
            except Exception as e:
                logging.error(f"Error stopping RPA: {e}")
                self.status_card.update_status("Could not stop the AI assistant", "error")
        else:
            self.status_card.update_status("AI assistant is not running", "idle")
    
    def monitor_processes(self):
        """Monitor running processes and their children"""
        while True:
            try:
                for name, info in list(self.script_processes.items()):
                    if not self.process_manager.is_running(name):
                        self.script_processes.pop(name, None)
                        
                        # Update UI from main thread
                        if not self.script_processes:  # All processes stopped
                            self.root.after(0, lambda: (
                                self.status_card.update_status("AI assistant has been stopped", "idle"),
                                self.start_btn.enable(),
                                self.stop_btn.disable()
                            ))
                
                time.sleep(1)  # Check every second
                
            except Exception:
                continue  # Keep monitoring even if an error occurs
    
    def on_closing(self):
        self.stop_all_rpa()
        self.root.destroy()

if __name__ == "__main__":
    try:
        from PIL import Image, ImageTk
    except ImportError:
        print("PIL not available, falling back to standard PhotoImage")
    
    root = tk.Tk()
    app = AIBrokerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()