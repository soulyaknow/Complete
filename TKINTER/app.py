import tkinter as tk
from tkinter import PhotoImage
import subprocess
import psutil
import os

# Initialize the main application
root = tk.Tk()
root.title("AI Broker")
root.geometry("400x300")  # Adjusted width to accommodate the sidebar

# Variables to store subprocesses for both scripts
script_processes = []

# Function to start multiple RPA scripts
def start_multiple_rpa():
    global script_processes
    if not script_processes:  # Ensure scripts aren't already running
        try:
            # Define the scripts to run
            python_executable = r"C:\Users\Hello World!\AppData\Local\Programs\Python\Python312\pythonw.exe"
            scripts = [
                r"C:\Users\Hello World!\Desktop\COMPLETE\SELENIUM-RPA\rpa.py",
                r"C:\Users\Hello World!\Desktop\COMPLETE\SELENIUM\rpa.py"
            ]
            
            # Start both scripts
            for script_path in scripts:
                process = subprocess.Popen(
                    [python_executable, script_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW  # Hide command window
                )
                script_processes.append(process)
            
            status_label.config(text="Scripts are running...", fg="green")
        except Exception as e:
            status_label.config(text=f"Error: {e}", fg="red")
    else:
        status_label.config(text="Scripts are already running!", fg="orange")

# Function to stop the scripts
def stop_all_rpa():
    global script_processes
    if script_processes:  # Check if scripts are running
        try:
            for process in script_processes:
                if process.poll() is None:  # Check if the script is running
                    parent_proc = psutil.Process(process.pid)
                    
                    # Terminate child processes
                    for child in parent_proc.children(recursive=True):
                        child.terminate()
                    parent_proc.terminate()
            
            script_processes.clear()  # Clear the list of processes
            status_label.config(text="Scripts stopped.", fg="red")
        except Exception as e:
            status_label.config(text=f"Error stopping scripts: {e}", fg="red")
    else:
        status_label.config(text="No scripts are running.", fg="red")

# Sidebar frame
sidebar = tk.Frame(root, width=100, bg="lightgray")
sidebar.pack(side=tk.LEFT, fill=tk.Y)

# Buttons in the sidebar
tk.Button(sidebar, text="Start All RPAs", command=start_multiple_rpa, bg="green", fg="white").pack(fill=tk.X, padx=5, pady=5)
tk.Button(sidebar, text="Stop All RPAs", command=stop_all_rpa, bg="red", fg="white").pack(fill=tk.X, padx=5, pady=5)

# Main content area
content_frame = tk.Frame(root)
content_frame.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)

# Load and display the logo image
try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(BASE_DIR, "robot.png")
    logo = PhotoImage(file=logo_path)
    logo = logo.subsample(3, 3)  # Scale down the image
    logo_label = tk.Label(content_frame, image=logo)
    logo_label.pack(pady=10)
except Exception as e:
    print(f"Error loading logo: {e}")

# Status label
status_label = tk.Label(content_frame, text="Idle", fg="blue", font=("Arial", 10))
status_label.pack(pady=10)

# Start the Tkinter event loop
root.mainloop()
