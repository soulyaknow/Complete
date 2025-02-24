import tkinter as tk
from tkinter import PhotoImage
import subprocess
import psutil
import os

# Initialize the main application
root = tk.Tk()
root.title("AI Broker")
root.geometry("400x300")  # Adjusted width to accommodate the sidebar

# Variable to store the subprocess
script_process = None

# Function to start a Python script based on user selection
def start_script(script_path):
    global script_process
    if script_process is None or script_process.poll() is not None:  # Ensure no duplicate script runs
        try:
            python_executable = r"C:\Users\Hello World!\AppData\Local\Programs\Python\Python312\pythonw.exe"
            script_process = subprocess.Popen(
                [python_executable, script_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW  # Hide command window
            )
            status_label.config(text="Script is running...", fg="green")
        except Exception as e:
            status_label.config(text=f"Error: {e}", fg="red")
    else:
        status_label.config(text="Script is already running!", fg="orange")

# Function to stop the script
def stop_app():
    global script_process
    if script_process and script_process.poll() is None:  # Check if the script is running
        try:
            # Use psutil to terminate the process properly
            parent_pid = script_process.pid
            parent_proc = psutil.Process(parent_pid)
            
            # Terminate child processes
            for child in parent_proc.children(recursive=True):
                child.terminate()
            parent_proc.terminate()
            
            script_process = None  # Reset process variable
            status_label.config(text="Script stopped.", fg="red")
        except Exception as e:
            status_label.config(text=f"Error stopping script: {e}", fg="red")
    else:
        status_label.config(text="No script is running.", fg="red")

# Sidebar frame
sidebar = tk.Frame(root, width=100, bg="lightgray")
sidebar.pack(side=tk.LEFT, fill=tk.Y)

# Buttons in the sidebar for each RPA
tk.Button(sidebar, text="Start AI Broker", command=lambda: start_script(r"C:\Users\Hello World!\Desktop\COMPLETE\SELENIUM-RPA\app.py"), bg="green", fg="white").pack(fill=tk.X, padx=5, pady=5)
tk.Button(sidebar, text="Start SFG AI Broker", command=lambda: start_script(r"C:\Users\Hello World!\Desktop\COMPLETE\SELENIUM\app.py"), bg="green", fg="white").pack(fill=tk.X, padx=5, pady=5)
tk.Button(sidebar, text="Stop", command=stop_app, bg="red", fg="white").pack(fill=tk.X, padx=5, pady=5)

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
