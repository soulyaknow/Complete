import tkinter as tk
import subprocess
import threading
import os
import signal
import psutil
import logging

class RpaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RPA Controller")
        self.root.geometry("500x300")
        
        self.script_processes = []
        
        # Set up logging
        self.log_file = "rpa_log.txt"
        logging.basicConfig(filename=self.log_file, level=logging.INFO, format='%(asctime)s - %(message)s')
        
        # Start Button
        self.start_button = tk.Button(root, text="Start RPA", command=self.start_rpa, font=("Arial", 16), width=20, height=2)
        self.start_button.pack(pady=20)
        
        # Stop Button
        self.stop_button = tk.Button(root, text="Stop RPA", command=self.stop_rpa, font=("Arial", 16), width=20, height=2)
        self.stop_button.pack(pady=20)
        
        # Status Label
        self.status_label = tk.Label(root, text="Status: Idle", font=("Arial", 14))
        self.status_label.pack(pady=10)
        
    def start_rpa(self):
        if not self.script_processes:  # Ensure scripts aren't already running
            try:
                python_executable = r"C:\Users\Hello World!\AppData\Local\Programs\Python\Python312\pythonw.exe"
                scripts = [
                    r"C:\Users\Hello World!\Desktop\COMPLETE\SELENIUM\rpa.py",
                ]
                
                def run_scripts():
                    for script_path in scripts:
                        # Open a file to capture stdout and stderr
                        with open(self.log_file, "a") as log_file:
                            process = subprocess.Popen(
                                [python_executable, script_path],
                                stdout=log_file,  # Redirect stdout to the log file
                                stderr=log_file,  # Redirect stderr to the log file
                                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
                            )
                            self.script_processes.append(process)
                    
                    self.update_status("AI assistant is now working", "running")
                
                threading.Thread(target=run_scripts, daemon=True).start()
                
            except Exception as e:
                self.update_status("Something went wrong", "error")
        else:
            self.update_status("AI assistant is already working", "running")
    
    def stop_rpa(self):
        if self.script_processes:
            for process in self.script_processes:
                try:
                    # Terminate the running processes
                    pid = process.pid
                    os.kill(pid, signal.SIGTERM)
                    self.update_status("RPA has been stopped", "stopped")
                except Exception as e:
                    self.update_status(f"Failed to stop process: {e}", "error")
            self.script_processes = []
        else:
            self.update_status("No RPA script is running", "idle")

    def update_status(self, message, status_type):
        # Update the status label with a simplified message
        self.status_label.config(text=f"Status: {message}")
        
# Create the Tkinter window
root = tk.Tk()
app = RpaApp(root)
root.mainloop()
