import tkinter as tk
from tkinter import PhotoImage
import subprocess
import psutil  # To check running processes

# Initialize the main application
root = tk.Tk()
root.title("AI Broker")
root.geometry("300x300")

# Variable to store the subprocess
script_process = None

def start_aibroker_sfg():
    global script_process
    if script_process is None or script_process.poll() is not None:  # Ensure no duplicate script runs
        try:
            python_executable = r"C:\Users\VanessaResgonia\AppData\Local\Programs\Python\Python313\pythonw.exe"  # Using pythonw
            script_path = r"C:\Users\VanessaResgonia\AIBROKER\SELENIUM-RPA\app.py"
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

# Function to start the Python script
def start_sfg_aibroker():
    global script_process
    if script_process is None or script_process.poll() is not None:  # Ensure no duplicate script runs
        try:
            python_executable = r"C:\Users\VanessaResgonia\AppData\Local\Programs\Python\Python313\pythonw.exe"  # Using pythonw
            script_path = r"C:\Users\VanessaResgonia\AIBROKER\SELENIUM\app.py"
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

# Function to stop the application and terminate the process
def stop_app():
    global script_process
    if script_process and script_process.poll() is None:  # Check if the script is running
        try:
            # Use psutil to terminate the process properly
            parent_pid = script_process.pid
            parent_proc = psutil.Process(parent_pid)
            
            # Iterate over all child processes and terminate them
            for child in parent_proc.children(recursive=True):
                child.terminate()  # Terminate the child process
                print(f"Child process {child.pid} terminated")
            
            # Terminate the parent process (pythonw.exe)
            parent_proc.terminate()  # Terminate the parent process
            print(f"Process {parent_pid} terminated")
            
            script_process = None  # Reset process variable
            status_label.config(text="Script stopped.", fg="red")
        except Exception as e:
            status_label.config(text=f"Error stopping script: {e}", fg="red")
    else:
        status_label.config(text="No script is running.", fg="red")

# Load and display the logo image
try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(BASE_DIR, "robot.png")
    logo = PhotoImage(file=logo_path)
    logo = logo.subsample(3, 3)  # Scale down the image
    logo_label = tk.Label(root, image=logo)
    logo_label.pack(pady=10)
except Exception as e:
    print(f"Error loading logo: {e}")

# UI Elements
start_button = tk.Button(root, text="Start", command=start_sfg_aibroker, bg="green", fg="white", font=("Arial", 12))
start_button.pack(side=tk.LEFT, padx=30, pady=20)

stop_button = tk.Button(root, text="Stop", command=stop_app, bg="red", fg="white", font=("Arial", 12))
stop_button.pack(side=tk.RIGHT, padx=30, pady=20)

status_label = tk.Label(root, text="Idle", fg="blue", font=("Arial", 10))
status_label.pack(pady=10)

# Start the Tkinter event loop
root.mainloop()
