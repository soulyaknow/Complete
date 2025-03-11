import os
import time
import json
import requests
import mimetypes
import re
import tkinter as tk
import sys
import threading
import pythoncom
import ctypes
from tkinter import ttk, messagebox
from flask import Flask, request, jsonify
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from requests_toolbelt.multipart.encoder import MultipartEncoder


# Initialize Flask app
app = Flask(__name__)
CORS(app)

DOWNLOAD_PATH = r"C:\Users\Hello World!\Desktop\COMPLETE\SELENIUM\docs"

classified_documents = {
    "bank_statement": [
        "bank", "statement", "transaction", "account", "banking",
        "deposit", "withdrawal", "balance", "credit", "debit",
        "interest", "overdraft", "transfer", "statement period",
        "monthly statement", "checking", "savings", "financial summary",
        "ledger", "IBAN", "SWIFT", "sort code"
    ],
    "drivers_license": ["license", "driver", "driving", "licence", "id"],
    "passport_id": ["passport"],
    "national_id": ["national", "id", "identification", "citizen", "citizenship", "residency"],
    "utility_bill": ["bill", "utility", "electric", "water", "gas", "electricity", "utilities"],
    "application_form": ["application", "form", "forms"],
    "payslip": ["payslip", "salary", "wage", "payment", "payroll", "pay"],
    "insurance": ["insurance", "policy", "coverage", "premium"]
}

# Ensure the download directory exists
if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

chrome_options = webdriver.ChromeOptions()    
chrome_options.add_argument("user-data-dir=C:\\Automation\\RPA")
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option("useAutomationExtension", False)

prefs = {
    "download.default_directory": DOWNLOAD_PATH,  # Set download path
    "download.prompt_for_download": False,        # Disable prompt
    "download.directory_upgrade": True,          # Allow path updates
    "safebrowsing.enabled": True                 # Enable safe browsing
}
chrome_options.add_experimental_option("prefs", prefs)

def process_applicants(applicant_details, lender_details, applicant_api_url, lender_api_url, headers):
    existing_applicants = get_existing_applicants(applicant_api_url, headers)
    new_applicants = []
    all_applicant_details = []

    for applicant in applicant_details:
        matching_records, status_code = is_applicant_existing(applicant, existing_applicants)
        
        if status_code == 200:
            all_applicant_details.extend(matching_records)  # Include existing applicants
        else:
            new_applicants.append(applicant)

    # Process new applicants in APITable
    application_recordIDs = []  
    new_applicant_recordIDs = []
    if new_applicants:
        for applicant_data in new_applicants:
            response_data = post_to_apitable(applicant_api_url, headers, applicant_data, "Applicant Hub")
            if response_data:
                all_applicant_details.extend(response_data)
                # Extract and store recordIDs for new applicants
                for record in response_data:
                    if 'recordId' in record:
                        new_applicant_recordIDs.append(record['recordId'])
        
        # Process lender data
        for lender_data in lender_details:
            if lender_data:
                post_to_apitable(lender_api_url, headers, lender_data, "Lender Hub")

        application_hub_api = "https://ai-broker.korunaassist.com/fusion/v1/datasheets/dstLr3xUL37tbn2Sud/records"
        # Prepare the application data
        application_data = {
            "records": [
                {
                    "fields": {
                        "Applicants": new_applicant_recordIDs,
                        "Status": "New"
                    }
                }
            ],
            "fieldKey": "name"
        }
            
        # Post the application record
        app_response = requests.post(
            application_hub_api, 
            headers=headers, 
            json=application_data
        )
            
        if app_response.status_code in (200, 201):
            response_json = app_response.json()  # Convert response to JSON
            print("Application record created successfully")

            # Extract the recordId
            if "data" in response_json and "records" in response_json["data"]:
                application_recordIDs = [record["recordId"] for record in response_json["data"]["records"]]
                print("Extracted Record IDs:", application_recordIDs)
            else:
                print("⚠️ Warning: No records found in response.")

    # Add Application_ID to group applicants (for both existing and new ones)
    application_id = time.strftime("%Y%m%d%H%M%S")
    for applicant in all_applicant_details:
        applicant["Application_ID"] = application_id

    # **Always launch the Tkinter GUI**
    if all_applicant_details:  # Ensure there are applicants to process
        root = tk.Tk()
        app = FileSelectorApp(root, all_applicant_details, application_recordIDs)

        if sys.platform.startswith('win'):
            pythoncom.CoInitialize()
            root.mainloop()
        else:
            root.mainloop()

    return {
        "status": "success",
        "message": "Processing started",
        "applicant_count": len(all_applicant_details)
    }

class Windows11Theme:
    """Windows 11 styling for Tkinter"""
    def __init__(self, root):
        self.style = ttk.Style(root)
        self.configure_styles()
        
    def configure_styles(self):
        # Windows 11 colors
        self.accent_color = "#0067C0"  # Windows 11 accent blue
        self.bg_color = "#F3F3F3"      # Light background
        self.text_color = "#202020"    # Dark text
        self.border_color = "#E1DFDE"  # Light border
        
        # Configure the root style
        self.style.configure('TFrame', background=self.bg_color)
        self.style.configure('TLabel', background=self.bg_color, foreground=self.text_color)
        self.style.configure('TLabelframe', background=self.bg_color, foreground=self.text_color)
        self.style.configure('TLabelframe.Label', background=self.bg_color, foreground=self.text_color, font=('Segoe UI', 9, 'bold'))
        
        # Configure button styles (Windows 11 has rounded buttons with subtle shadows)
        self.style.configure('TButton', 
                             background='white',
                             foreground=self.text_color,
                             font=('Segoe UI', 9),
                             relief=tk.FLAT,
                             borderwidth=1)
        
        # Accent button style (with white text)
        self.style.configure('Accent.TButton',
                             background=self.accent_color,
                             foreground='white',
                             font=('Segoe UI', 9, 'bold'),
                             relief=tk.FLAT,
                             borderwidth=0)
        
        # Accent button style (with black text)
        self.style.configure('AccentBlack.TButton',
                             background=self.accent_color,
                             foreground='black',
                             font=('Segoe UI', 9, 'bold'),
                             relief=tk.FLAT,
                             borderwidth=0)
        
        # Hover styles
        self.style.map('TButton',
                      background=[('active', '#F5F5F5'), ('pressed', '#E1E1E1')],
                      relief=[('pressed', 'flat')])
        
        self.style.map('Accent.TButton',
                      background=[('active', '#005FB3'), ('pressed', '#004E99')],
                      foreground=[('active', 'white'), ('pressed', 'white')])
                      
        self.style.map('AccentBlack.TButton',
                      background=[('active', '#005FB3'), ('pressed', '#004E99')],
                      foreground=[('active', 'black'), ('pressed', 'black')])
        
        # Configure combobox style
        self.style.configure('TCombobox', 
                            background='white',
                            fieldbackground='white',
                            foreground=self.text_color,
                            arrowcolor=self.text_color)
        
        # Configure progressbar style
        self.style.configure('TProgressbar', 
                            background=self.accent_color,
                            troughcolor='#E5E7EB',
                            borderwidth=0,
                            thickness=6)

class FileSelectorApp:
    def __init__(self, root, applicant_details, application_id):
        self.root = root
        self.root.title("Document Assignment Tool")
        self.root.geometry("1000x700")
        self.root.configure(bg="#F3F3F3")  # Windows 11 background color
        
        # Apply Windows 11 theme
        self.theme = Windows11Theme(root)
        
        # Add icon to the window and taskbar - with improved icon finding
        self.find_and_set_icon()
        
        # Store applicant details and initialize assignments
        self.applicant_details = applicant_details
        self.application_id = application_id
        self.assignments = {}  # Dictionary to store file assignments
        self.processed_files = {}  # Dictionary to track processed files per applicant
        
        # Create main container with grid
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        # Left Frame: Available Files
        left_frame = ttk.LabelFrame(self.root, text=" Available Documents ", padding=(10, 5))
        left_frame.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")
        left_frame.grid_rowconfigure(1, weight=1)  # Ensure the file container expands
        left_frame.grid_columnconfigure(0, weight=1)
        
        # Add heading with icon (simulated with a label)
        doc_heading = ttk.Frame(left_frame)
        doc_heading.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        
        doc_heading_icon = ttk.Label(doc_heading, text="📄", font=("Segoe UI", 11))
        doc_heading_icon.pack(side=tk.LEFT, padx=(0, 5))
        
        doc_heading_text = ttk.Label(doc_heading, text="Select a document to assign", font=("Segoe UI", 10))
        doc_heading_text.pack(side=tk.LEFT)
        
        # File listbox with custom styling
        file_container = ttk.Frame(left_frame)
        file_container.grid(row=1, column=0, sticky="nsew")
        file_container.grid_rowconfigure(0, weight=1)
        file_container.grid_columnconfigure(0, weight=1)
        
        # Create a frame for the listbox with a border
        listbox_frame = tk.Frame(file_container, bg="white", highlightbackground="#E1DFDE", 
                                highlightthickness=1, bd=0)
        listbox_frame.grid(row=0, column=0, sticky="nsew")
        listbox_frame.grid_rowconfigure(0, weight=1)
        listbox_frame.grid_columnconfigure(0, weight=1)
        
        # File listbox with custom styling
        self.file_listbox = tk.Listbox(listbox_frame, 
                                     selectmode=tk.SINGLE,
                                     bg="white",
                                     fg="#202020",
                                     font=("Segoe UI", 9),
                                     bd=0,
                                     highlightthickness=0,
                                     activestyle="none",
                                     selectbackground="#CCE4F7",
                                     selectforeground="#202020")
        
        file_scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.file_listbox.yview)
        self.file_listbox.configure(yscrollcommand=file_scrollbar.set)
        
        self.file_listbox.grid(row=0, column=0, sticky="nsew")
        file_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Right Frame: Controls and Assigned Files
        right_frame = ttk.Frame(self.root, padding=(0, 0))
        right_frame.grid(row=0, column=1, padx=16, pady=16, sticky="nsew")
        right_frame.grid_columnconfigure(0, weight=1)
        
        # Applicant selection panel
        applicant_frame = ttk.LabelFrame(right_frame, text=" Applicant Selection ", padding=(10, 5))
        applicant_frame.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        
        # Add heading with icon
        app_heading = ttk.Frame(applicant_frame)
        app_heading.pack(fill=tk.X, pady=(0, 8))
        
        app_heading_icon = ttk.Label(app_heading, text="👤", font=("Segoe UI", 11))
        app_heading_icon.pack(side=tk.LEFT, padx=(0, 5))
        
        app_heading_text = ttk.Label(app_heading, text="Select an applicant", font=("Segoe UI", 10))
        app_heading_text.pack(side=tk.LEFT)
        
        # Applicant dropdown with Windows 11 styling
        dropdown_frame = ttk.Frame(applicant_frame)
        dropdown_frame.pack(fill=tk.X, pady=5)
        
        self.applicant_var = tk.StringVar()
        self.applicant_dropdown = ttk.Combobox(dropdown_frame, 
                                             textvariable=self.applicant_var,
                                             font=("Segoe UI", 9),
                                             state="readonly",
                                             height=5)
        self.applicant_dropdown.pack(fill=tk.X)
        
        # Assigned files frame
        assigned_frame = ttk.LabelFrame(right_frame, text=" Assigned Documents ", padding=(10, 5))
        assigned_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 16))
        assigned_frame.grid_rowconfigure(1, weight=1)  # Ensure the assigned container expands
        assigned_frame.grid_columnconfigure(0, weight=1)
        
        # Add heading with icon
        assigned_heading = ttk.Frame(assigned_frame)
        assigned_heading.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        
        assigned_heading_icon = ttk.Label(assigned_heading, text="📋", font=("Segoe UI", 11))
        assigned_heading_icon.pack(side=tk.LEFT, padx=(0, 5))
        
        assigned_heading_text = ttk.Label(assigned_heading, text="Documents assigned to this applicant", font=("Segoe UI", 10))
        assigned_heading_text.pack(side=tk.LEFT)
        
        # Assigned listbox with custom styling
        assigned_container = ttk.Frame(assigned_frame)
        assigned_container.grid(row=1, column=0, sticky="nsew")
        assigned_container.grid_rowconfigure(0, weight=1)
        assigned_container.grid_columnconfigure(0, weight=1)
        
        # Create a frame for the listbox with a border
        assigned_listbox_frame = tk.Frame(assigned_container, bg="white", highlightbackground="#E1DFDE", 
                                        highlightthickness=1, bd=0)
        assigned_listbox_frame.grid(row=0, column=0, sticky="nsew")
        assigned_listbox_frame.grid_rowconfigure(0, weight=1)
        assigned_listbox_frame.grid_columnconfigure(0, weight=1)
        
        self.assigned_listbox = tk.Listbox(assigned_listbox_frame,
                                         selectmode=tk.SINGLE,
                                         bg="white",
                                         fg="#202020",
                                         font=("Segoe UI", 9),
                                         bd=0,
                                         highlightthickness=0,
                                         activestyle="none",
                                         selectbackground="#CCE4F7",
                                         selectforeground="#202020")
        
        assigned_scrollbar = ttk.Scrollbar(assigned_listbox_frame, orient=tk.VERTICAL, command=self.assigned_listbox.yview)
        self.assigned_listbox.configure(yscrollcommand=assigned_scrollbar.set)
        
        self.assigned_listbox.grid(row=0, column=0, sticky="nsew")
        assigned_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Status frame
        status_frame = ttk.LabelFrame(right_frame, text=" Processing Status ", padding=(10, 5))
        status_frame.grid(row=2, column=0, sticky="ew")
        
        # Add heading with icon
        status_heading = ttk.Frame(status_frame)
        status_heading.pack(fill=tk.X, pady=(0, 8))
        
        status_heading_icon = ttk.Label(status_heading, text="🔄", font=("Segoe UI", 11))
        status_heading_icon.pack(side=tk.LEFT, padx=(0, 5))
        
        status_heading_text = ttk.Label(status_heading, text="Document processing status", font=("Segoe UI", 10))
        status_heading_text.pack(side=tk.LEFT)
        
        # Status text with Windows 11 styling
        status_text_frame = tk.Frame(status_frame, bg="white", highlightbackground="#E1DFDE", 
                                    highlightthickness=1, bd=0)
        status_text_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_text = tk.Text(status_text_frame, 
                                 height=4, 
                                 wrap=tk.WORD,
                                 bg="white",
                                 fg="#202020",
                                 font=("Segoe UI", 9),
                                 bd=0,
                                 highlightthickness=0,
                                 padx=8,
                                 pady=8)
        self.status_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        status_text_scrollbar = ttk.Scrollbar(status_text_frame, orient=tk.VERTICAL, command=self.status_text.yview)
        self.status_text.configure(yscrollcommand=status_text_scrollbar.set)
        status_text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add progress bar to status frame
        progress_frame = ttk.Frame(status_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 5))
        
        progress_label = ttk.Label(progress_frame, text="Progress:")
        progress_label.pack(side=tk.LEFT, padx=(0, 5))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame, 
            variable=self.progress_var,
            maximum=100,
            mode='determinate',
            length=100
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.progress_label = ttk.Label(progress_frame, text="0%", width=5)
        self.progress_label.pack(side=tk.RIGHT)
        
        # Action button frame (bottom of the window)
        button_frame = ttk.Frame(right_frame, padding=(0, 10))
        button_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        
        button_grid = ttk.Frame(button_frame)
        button_grid.pack(fill=tk.X)
        button_grid.grid_columnconfigure(0, weight=1)
        button_grid.grid_columnconfigure(1, weight=1)
        
        # Create assign button with icon
        assign_button_frame = ttk.Frame(button_grid)
        assign_button_frame.grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=5)
        assign_button_frame.grid_columnconfigure(0, weight=1)
        
        self.assign_button = ttk.Button(
            assign_button_frame, 
            text="Assign Document",
            command=self.assign_document,
            style="TButton",
            width=20
        )
        self.assign_button.grid(row=0, column=0, sticky="ew")
        
        # Create remove button with icon
        remove_button_frame = ttk.Frame(button_grid)
        remove_button_frame.grid(row=0, column=1, sticky="ew", padx=(5, 0), pady=5)
        remove_button_frame.grid_columnconfigure(0, weight=1)
        
        self.remove_button = ttk.Button(
            remove_button_frame, 
            text="Remove Assignment",
            command=self.remove_assignment,
            style="TButton",
            width=20
        )
        self.remove_button.grid(row=0, column=0, sticky="ew")
        
        # Create submit button with accent style and BLACK text
        submit_button_frame = ttk.Frame(button_grid)
        submit_button_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)
        submit_button_frame.grid_columnconfigure(0, weight=1)
        
        self.submit_button = ttk.Button(
            submit_button_frame, 
            text="Submit Documents",
            command=self.submit_to_textract,
            style="AccentBlack.TButton",  # Changed to AccentBlack.TButton for black text
            width=20
        )
        self.submit_button.grid(row=0, column=0, sticky="ew")
        
        # Create clear button
        clear_button_frame = ttk.Frame(button_grid)
        clear_button_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)
        clear_button_frame.grid_columnconfigure(0, weight=1)
        
        self.clear_button = ttk.Button(
            clear_button_frame, 
            text="Clear Status",
            command=self.clear_status,
            style="TButton",
            width=20
        )
        self.clear_button.grid(row=0, column=0, sticky="ew")
        
        # Initialize the interface
        self.load_applicants()
        self.load_files()
        
        # Bind events
        self.applicant_dropdown.bind('<<ComboboxSelected>>', self.on_applicant_selected)
        
        # Update status
        self.update_status("Ready to process documents.")
    
    def find_and_set_icon(self):
        """Find and set the icon by checking multiple possible locations"""
        # Look for icon in possible locations
        icon_paths = [
            "logo/ka.ico",  # Original path
            "ka.ico",       # Root directory
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "ka.ico"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo", "ka.ico"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "ka.ico"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "ka.ico")
        ]
        
        # Print the current directory and searched locations for debugging
        print(f"Current working directory: {os.getcwd()}")
        print("Searching for icon in the following locations:")
        for path in icon_paths:
            print(f"  - {path} (Exists: {os.path.exists(path)})")
        
        # Try each path
        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                try:
                    self.set_taskbar_icon(self.root, icon_path)
                    print(f"✅ Successfully loaded icon from: {icon_path}")
                    return
                except Exception as e:
                    print(f"❌ Error setting icon from {icon_path}: {str(e)}")
        
        # If we got here, no icons were found
        print("⚠️ No icon files found in any of the searched locations.")
        print("Make sure to place ka.ico in one of the following directories:")
        print("  - ./logo/")
        print("  - ./ (root directory)")
        print("  - ./assets/")
        print("  - ./icons/")
    
    def set_taskbar_icon(self, root, icon_path):
        """Set both window and taskbar icons for a Tkinter application."""
        import os
        import sys
        import ctypes
        
        # Set window icon using normal Tkinter approach
        root.iconbitmap(icon_path)
        
        # For Windows taskbar icon
        if sys.platform.startswith('win'):
            # Get absolute path to the icon
            abs_icon_path = os.path.abspath(icon_path)
            
            # Windows-specific method to set the taskbar icon
            myappid = f'mycompany.documentprocessor.{os.path.basename(icon_path)}'  # Arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            
            # Set the icon for the process
            if hasattr(ctypes.windll, 'user32'):
                # Apply icon for taskbar
                hwnd = ctypes.windll.user32.GetActiveWindow()
                if hwnd:
                    icon_handle = ctypes.windll.user32.LoadImageW(
                        None, 
                        abs_icon_path, 
                        1,  # IMAGE_ICON
                        0, 
                        0, 
                        0x00000010 | 0x00000040  # LR_LOADFROMFILE | LR_DEFAULTSIZE
                    )
                    if icon_handle:
                        ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, icon_handle)  # WM_SETICON, ICON_SMALL
                        ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, icon_handle)  # WM_SETICON, ICON_BIG
    
    def get_folder_path(self):
        """Get the folder path for the current applicant"""
        # Find the first applicant in the same application
        current_applicant = next(
            (app for app in self.applicant_details 
             if f"{app['First Name']} {app['Last Name']}" == self.applicant_var.get()),
            None
        )
        
        if not current_applicant:
            return None
            
        # Use the first applicant's name as the folder name
        first_applicant = self.applicant_details[0]  # Always use the first applicant's name for the folder
        folder_name = f"{first_applicant['First Name']} {first_applicant['Last Name']}"
        
        # Debug information
        print(f"First applicant: {first_applicant}")
        print(f"Folder name: {folder_name}")

        return os.path.join(DOWNLOAD_PATH, folder_name)
    
    def load_applicants(self):
        """Load applicants into the dropdown"""
        applicant_names = [
            f"{app['First Name']} {app['Last Name']}"
            for app in self.applicant_details
        ]
        self.applicant_dropdown['values'] = applicant_names
        if applicant_names:
            self.applicant_dropdown.set(applicant_names[0])
            print(f"Loaded applicants: {applicant_names}")
    
    def load_files(self):
        """Load available files for the selected applicant"""
        self.file_listbox.delete(0, tk.END)
        folder_path = self.get_folder_path()
        
        if not folder_path:
            print("No folder path found")
            return
            
        if os.path.exists(folder_path):
            print(f"Loading files from: {folder_path}")
            for file_name in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file_name)
                if os.path.isfile(file_path):
                    # Check if the file is not processed and not assigned
                    current_applicant = self.applicant_var.get()
                    if (file_name not in self.processed_files.get(current_applicant, set()) and 
                        file_name not in self.assignments.get(current_applicant, [])):
                        self.file_listbox.insert(tk.END, file_name)
                        print(f"Added file to listbox: {file_name}")
        else:
            print(f"Folder does not exist: {folder_path}")
    
    def update_status(self, message):
        """Update the status text with timestamp"""
        timestamp = time.strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.see(tk.END)
    
    def update_progress(self, percentage):
        """Update progress bar and percentage display"""
        self.progress_var.set(percentage)
        self.progress_label.config(text=f"{int(percentage)}%")
        self.root.update_idletasks()  # Force update of the UI
    
    def clear_status(self):
        """Clear the status text"""
        self.status_text.delete(1.0, tk.END)
        self.update_status("Status cleared.")
        # Reset progress bar
        self.update_progress(0)
    
    def on_applicant_selected(self, event):
        """Handle applicant selection change"""
        self.load_files()
        self.update_assigned_files()
        self.update_status(f"Selected applicant: {self.applicant_var.get()}")
    
    def assign_document(self):
        """Assign selected document to current applicant"""
        selected_indices = self.file_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Warning", "Please select a document to assign")
            return
        
        selected_file = self.file_listbox.get(selected_indices[0])
        selected_applicant = self.applicant_var.get()
        
        if selected_applicant not in self.assignments:
            self.assignments[selected_applicant] = []
        
        self.assignments[selected_applicant].append(selected_file)
        self.file_listbox.delete(selected_indices[0])
        self.update_assigned_files()
        self.update_status(f"Assigned '{selected_file}' to {selected_applicant}")
    
    def remove_assignment(self):
        """Remove document assignment"""
        selected_indices = self.assigned_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Warning", "Please select a document to remove")
            return
        
        selected_file = self.assigned_listbox.get(selected_indices[0])
        selected_applicant = self.applicant_var.get()
        
        self.assignments[selected_applicant].remove(selected_file)
        self.assigned_listbox.delete(selected_indices[0])
        self.file_listbox.insert(tk.END, selected_file)
        self.update_status(f"Removed '{selected_file}' from {selected_applicant}")
    
    def update_assigned_files(self):
        """Update the assigned files listbox"""
        self.assigned_listbox.delete(0, tk.END)
        selected_applicant = self.applicant_var.get()
        if selected_applicant in self.assignments:
            for file_name in self.assignments[selected_applicant]:
                self.assigned_listbox.insert(tk.END, file_name)
    
    def submit_to_textract(self):
        """Submit assigned documents to Textract"""
        if not any(self.assignments.values()):
            messagebox.showwarning("Warning", "No documents have been assigned")
            return
        
        # Start processing in a separate thread
        processing_thread = threading.Thread(target=self._process_documents)
        processing_thread.start()
    
    def _process_documents(self):
        """Process documents in background thread"""
        folder_path = self.get_folder_path()
        if not folder_path:
            self.root.after(0, self.update_status, "Error: Could not determine folder path")
            return
        
        # Calculate total files for progress tracking
        total_files = sum(len(files) for files in self.assignments.values())
        processed_count = 0
            
        for applicant_name, files in self.assignments.items():
            if not files:
                continue
            
            # Find applicant details
            applicant = next(
                (app for app in self.applicant_details 
                if f"{app['First Name']} {app['Last Name']}" == applicant_name),
                None
            )
            
            if applicant and files:
                files_to_upload = []
                
                for file_name in files:
                    file_path = os.path.join(folder_path, file_name)
                    if os.path.isfile(file_path):
                        metadata = get_file_metadata(file_path)
                        doc_type = get_document_type(file_name)  # Get document type
                        files_to_upload.append((file_name, open(file_path, "rb"), metadata["mime_type"], doc_type))
                
                if files_to_upload:
                    try:
                        self.root.after(0, self.update_status, f"Processing files for {applicant_name}...")
                        
                        # Update progress at the start of processing for this applicant
                        progress_percentage = (processed_count / total_files) * 100
                        self.root.after(0, self.update_progress, progress_percentage)
                        
                        # Create multipart form-data that properly handles multiple files
                        # Use self.application_id here instead of application_id
                        multipart_data = self._create_multipart_data(files_to_upload, applicant, self.application_id)
                        
                        # Send to Textract middleware
                        response = requests.post(
                            "https://textractor.korunaassist.com/upload",
                            data=multipart_data,
                            headers={"Content-Type": multipart_data.content_type},
                            timeout=30  # Increased timeout for multiple files
                        )
                        
                        if response.status_code in (200, 201):
                            # Parse the queue status from response
                            queue_info = ""
                            try:
                                resp_data = response.json()
                                if "queueStatus" in resp_data:
                                    status = resp_data["queueStatus"]
                                    queue_info = f" (Files in queue: {status.get('remainingInQueue', 0)})"
                                    
                                    # If we have files in queue, show a more detailed message
                                    if status.get('remainingInQueue', 0) > 0:
                                        queue_info = f" (Processing {status.get('totalFiles', 0)} files sequentially.)"
                            except Exception as e:
                                print(f"Error parsing queue status: {str(e)}")
                            
                            # Increment count for processed files
                            processed_count += len(files_to_upload)
                            
                            # Update progress after processing this applicant's files
                            progress_percentage = (processed_count / total_files) * 100
                            self.root.after(0, self.update_progress, progress_percentage)
                                    
                            # Mark files as processed for this applicant
                            if applicant_name not in self.processed_files:
                                self.processed_files[applicant_name] = set()
                                
                            for file_name, _, _, _ in files_to_upload:
                                self.processed_files[applicant_name].add(file_name)
                            
                            self.root.after(0, self.update_status,
                                f"✅ Files for {applicant_name} successfully queued and being processed{queue_info}")
                                
                        else:
                            self.root.after(0, self.update_status,
                                f"❌ Failed to process files for {applicant_name}: {response.text}")
                    
                    except Exception as e:
                        self.root.after(0, self.update_status,
                            f"Error processing files for {applicant_name}: {str(e)}")
                    
                    finally:
                        for _, file_obj, _, _ in files_to_upload:
                            file_obj.close()
        
        # Set progress to 100% when complete
        self.root.after(0, self.update_progress, 100)
        
        # Clear assignments after processing
        self.assignments = {}
        
        # Update UI in main thread
        self.root.after(0, self._after_processing)
    
    def _create_multipart_data(self, files_to_upload, applicant, application_id):
        """
        Create a properly structured multipart form-data that supports multiple files.
        
        Args:
            files_to_upload: List of tuples (file_name, file_obj, mime_type, doc_type)
            applicant: Applicant information dictionary
            application_id: The ID of the application
            
        Returns:
            MultipartEncoder object configured with all files
        """
        # Use requests_toolbelt's MultipartEncoder with a list of tuples
        # The key difference is we're not converting to a dict, which preserves multiple values for the same key
        fields = []
        
        # Add each file with the same field name 'files'
        for i, (file_name, file_obj, mime_type, doc_type) in enumerate(files_to_upload):
            # Keep the field name 'files' the same for all files
            fields.append(
                ('files', (file_name, file_obj, mime_type))
            )
            # Add document type for each file
            fields.append(
                (f'document_type_{file_name}', doc_type)
            )
        
        # Add applicant data
        fields.append(('applicant', json.dumps({
            "Applicant_ID": applicant["Applicant_ID"],
            "First Name": applicant["First Name"],
            "Last Name": applicant["Last Name"],
            "recordId": applicant["recordId"],
            "application_recordId": application_id
        })))
        
        # Print debug info
        print(f"Creating request with {len(files_to_upload)} files")
        for i, (file_name, _, _, doc_type) in enumerate(files_to_upload):
            print(f"  File {i+1}: {file_name} (Type: {doc_type})")
        
        # Return the MultipartEncoder with all fields
        return MultipartEncoder(fields=fields)
    
    def _after_processing(self):
        """Update UI after processing completes"""
        self.update_assigned_files()
        self.load_files()
        self.update_status("Processing complete. Ready for more documents.")
        messagebox.showinfo("Success", "Documents have been submitted for processing")
        
def get_file_metadata(file_path):
    """Get file metadata including MIME type"""
    file_name = os.path.basename(file_path)
    file_extension = os.path.splitext(file_name)[1]  # Get file extension
    mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"  # Guess MIME type
    return {"file_name": file_name, "file_extension": file_extension, "mime_type": mime_type}

def get_document_type(file_name):
    """Get document type based on file name"""
    normalized_file_name = re.sub(r'[^a-z0-9]', ' ', file_name.lower())
    
    # Check each document type's keywords
    for doc_type, keywords in classified_documents.items():
        for keyword in keywords:
            if keyword in normalized_file_name:
                print(f"Classified {file_name} as {doc_type}")
                return doc_type
    
    print(f"Could not classify {file_name}, marking as unknown_document")
    return "unknown_document"

def is_applicant_existing(applicant_data, existing_applicants):
    try:
        # Extract fields from applicant_data
        records = applicant_data.get("records", [])
        if not records:
            print("No records found in the applicant data.")
            return [], 404  # Returning empty list with status 404 if no record is found
        
        applicant_fields = records[0].get("fields", {})
        applicant_first_name = applicant_fields.get("First Name")
        applicant_last_name = applicant_fields.get("Last Name")

        # Loop through existing applicants to find a match
        matching_records = []
        for record in existing_applicants:
            fields = record.get("fields", {})
            if (
                fields.get("First Name") == applicant_first_name
                and fields.get("Last Name") == applicant_last_name
            ):
                matching_records.append({
                    "Applicant_ID": fields.get("Applicant_ID"),
                    "First Name": fields.get("First Name"),
                    "Last Name": fields.get("Last Name"),
                    "recordId": record.get("recordId")
                })
        
        if matching_records:
            return matching_records, 200  # Returning the matched records and status 200
        else:
            return [], 404  # No match, returning empty list and status 404

    except KeyError as e:
        print(f"KeyError occurred: {str(e)}")
        return [], 404

# Function for APITable
def post_to_apitable(api_url, headers, data, data_type):
    try:
        response = requests.post(api_url, headers=headers, json=data)

        if response.status_code in (200, 201):
            if data_type != "Lender Hub":
                print(f"{data_type} data successfully posted.")
            
            response_data = response.json()

            # Parse the response to extract IDs and applicant details (name, etc.)
            if response_data.get("success") and "records" in response_data["data"] and data_type != "Lender Hub":
                records = response_data["data"]["records"]
                processed_records = []
                

                for record in records:
                    record_id = record.get("recordId")
                    applicant_id = record["fields"].get("Applicant_ID")
                    first_name = record["fields"].get("First Name")
                    last_name = record["fields"].get("Last Name")

                    if record_id and applicant_id and first_name and last_name:
                        processed_records.append({
                            "Applicant_ID": applicant_id,
                            "recordId": record_id,
                            "First Name": first_name,
                            "Last Name": last_name
                        })

                return processed_records  # Return processed records for the current applicant
            elif data_type != "Lender Hub":
                print(f"No valid records found in {data_type} response.")
                return []
        else:
            if data_type != "Lender Hub":
                print(f"Failed to post {data_type} data. Status: {response.status_code}, Response: {response.text}")
            return []
    except requests.exceptions.RequestException as e:
        if data_type != "Lender Hub":
            print(f"Network error while posting {data_type} data: {str(e)}")
        return []

def get_existing_applicants(applicant_api_url, headers):
    try:
        # Send a GET request to the API
        response = requests.get(applicant_api_url, headers=headers) 
        if response.status_code == 200:
            data = response.json()
            return data.get("data", {}).get("records", [])
        else:
            print(f"Failed to fetch existing applicants. Status Code: {response.status_code}")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching existing applicants: {str(e)}")
        return []

def scroll_down_until_bottom(driver):
    try:
        ticket_content = driver.find_element(By.TAG_NAME, "ticket-content")
        last_scroll_position = -1

        while True:
            # Scroll down
            driver.execute_script("arguments[0].scrollBy(0, 500);", ticket_content)
            time.sleep(2)  # Wait for new elements to load

            # Get new scroll position
            current_scroll_position = driver.execute_script("return arguments[0].scrollTop;", ticket_content)

            # If the scroll position hasn't changed, we've reached the bottom
            if current_scroll_position == last_scroll_position:
                print("Reached the bottom of the timeline.")
                break
            else:
                last_scroll_position = current_scroll_position

    except Exception as e:
        print(f"Error while scrolling down: {e}")

@app.route('/', methods=['GET'])
def home():
    print('service is running')
    return "Service is running"

@app.route('/process-url', methods=['POST'])
def process_url():
    # Parse request data
    data = request.json
    print(data)
    login_url = data.get('loginUrl')
    target_url = data.get('targetUrl')

    if not login_url or not target_url:
        return jsonify({"error": "Missing required parameters"}), 400

    # Set up Chrome WebDriver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    try:
        # Step 1: Log in
        driver.get(login_url)

        # Wait for specific elements to load (example: <a> tag)
        WebDriverWait(driver, 10000).until(
            EC.presence_of_element_located((By.TAG_NAME, "a"))
        )

        print("Login page is loaded. Pausing for user to input credentials...")

        # Pause and allow the user to input credentials
        time.sleep(30)

        print("Waiting for user to log in...")

        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "img"))
        )

        print("Login successful. Continuing automation...")

        # Step 2: Navigate to provided URL
        driver.get(target_url)

        # Wait for content to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "ticket-contacts"))
        )

        time.sleep(10)

        applicants = []
        seen_names = set()
        ticket_contacts = driver.find_elements(By.TAG_NAME, "ticket-contacts")
        folder_created = False
        applicant_folder = ""

        for contact in ticket_contacts:
            try:
                # Extract name
                name = contact.find_element(By.XPATH, ".//strong[@ng-bind='::client.getName()']").text
                if name and name not in seen_names:
                    seen_names.add(name)

                    # Create or use the folder for the first applicant
                    if not folder_created:
                        applicant_folder = os.path.join(DOWNLOAD_PATH, name)

                        # Check if the folder exists
                        if not os.path.exists(applicant_folder):
                            os.makedirs(applicant_folder)
                            print(f"Folder created for the first applicant: {name}")
                        else:
                            print(f"Using existing folder: {applicant_folder}")

                        # Update download directory dynamically for the first applicant
                        driver.execute_cdp_cmd(
                            "Page.setDownloadBehavior",
                            {
                                "behavior": "allow",
                                "downloadPath": applicant_folder,
                            },
                        )

                        folder_created = True

                    # Attempt to extract phone number, fallback to None if not found
                    try:
                        phone = contact.find_element(By.XPATH, ".//span[@ng-bind='::client.getPhone()']").text
                    except Exception:
                        phone = None

                    # Attempt to extract email, fallback to None if not found
                    try:
                        email = contact.find_element(By.XPATH, ".//span[@ng-bind='::client.getEmail()']").text
                    except Exception:
                        email = None

                    # Append extracted data to the applicants list
                    applicants.append({
                        "applicant_name": name,
                        "contact_number": phone,
                        "email": email
                    })

                    # Break the loop if required number of names are extracted
                    if len(seen_names) == 2:
                        break

            except Exception as e:
                print(f"Error processing contact: {str(e)}")
                continue

        # Wait for content to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "ticket-basic-info-value"))
        )

        time.sleep(5)


        lender = None
        try:
            lender_element = driver.find_element(By.XPATH, "//span[@ng-bind=\"::Model.currentLender.getName()\"]")
            lender = lender_element.get_attribute("innerText").strip()
        except Exception as e:
            print(f"Error getting lender data: {str(e)}")

        # Get loan security addresses
        loan_security_addresses = None  # Initialize as None
        try:
            address_elements = driver.find_elements(By.XPATH, 
                "//ticket-basic-info-value//span[@ng-repeat='security in Model.currentHomeLoan.securityDetails.securitySplits']")
            addresses = []  # Temporary list to hold the addresses
            for address_elem in address_elements:
                address_text = address_elem.get_attribute("innerText").strip()
                if address_text:
                    addresses.append(address_text)
            
            # Join addresses into a single string separated by commas (or any other delimiter)
            if addresses:
                loan_security_addresses = ", ".join(addresses)
        except Exception as e:
            print(f"Error getting addresses: {str(e)}")

        
        deal_value = None
        try:
            deal_value_element = driver.find_element(By.XPATH, 
                "//ticket-basic-info-value[@ng-bind='Model.currentTicket.values.onceOff.formatWithCurrency(CurrentCurrency(), 0)']")
            deal_value = deal_value_element.get_attribute("innerText").strip()

            # Clean and convert the deal value to a float
            if deal_value:
                # Remove the dollar sign and commas, then convert to float
                deal_value = float(deal_value.replace("$", "").replace(",", ""))
        except Exception as e:
            print(f"Error getting deal value data: {str(e)}")


        total_loan_amount = None
        try:
            total_loan_amount_element = driver.find_element(By.XPATH, 
                "//ticket-basic-info-value[@ng-bind='Model.preferredProductTotalLoanAmount.formatWithCurrency(CurrentCurrency())']")
            total_loan_amount = total_loan_amount_element.get_attribute("innerText").strip()
        except Exception as e:
            print(f"Error getting total loan amount data: {str(e)}")

        estimated_settlement_date = None
        try:
            settlement_element = driver.find_element(By.XPATH, 
                "//span[@ng-bind='Model.currentTicket.getDueDate(CurrentTimeZone(), CurrentOrganizationDateTimeLocale())']")
            estimated_settlement_date = settlement_element.get_attribute("innerText").strip()
        except Exception as e:
            print(f"Error getting settlement date data: {str(e)}")

        deal_owner = None
        try:
            deal_owner_element = driver.find_element(By.XPATH, 
                "//span[@ng-bind=\"getAccount(Model.currentTicket.idOwner).getName()\"]")
            deal_owner = deal_owner_element.get_attribute("innerText").strip()
        except Exception as e:
            print(f"Error getting deal owner data: {str(e)}")
        
        try:
            # Locate the scrollable container for forcing the scroll
            scrollable_container = driver.find_element(By.CSS_SELECTOR, "md-content[md-scroll-y]")

            # Force the scroll to the bottom to trigger new event loading
            print("🔽 Scrolling down to trigger loading of new timeline events...")
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", scrollable_container)
            time.sleep(5)  # Wait for new items to load

            # Get all timeline-event elements after scrolling
            timeline_events = driver.find_elements(By.TAG_NAME, "timeline-event")
            print(f"📋 Found {len(timeline_events)} timeline events.")

            # Process the events
            for index, event in enumerate(timeline_events):
                try:
                    # Check if the element contains <span>Labels</span>
                    labels_span = event.find_elements(By.XPATH, ".//span[text()='Labels']")
                    if labels_span:
                        print(f"🎯 Found labels in timeline-event #{index + 1}, processing...")

                        # Locate and click the download button
                        download_button = event.find_element(By.XPATH, ".//md-icon[text()='cloud_download']")
                        if download_button:
                            ActionChains(driver).move_to_element(download_button).perform()
                            download_button.click()
                            print(f"✅ Download button clicked for timeline-event #{index + 1}.")
                            time.sleep(2)  # Optional: Wait between downloads

                except Exception as e:
                    print(f"⚠️ Error processing timeline-event #{index + 1}: {e}")

            print("✅ All events processed. Stopping process.")
            
        except Exception as e:
            print(f"Error during process: {e}")

        # POST the data to the apitable endpoint
        applicant_api_url = "https://ai-broker.korunaassist.com/fusion/v1/datasheets/dst1vag1MekDBbrzoS/records"
        lender_api_url = "https://ai-broker.korunaassist.com/fusion/v1/datasheets/dstGYdtqYD60Hk58UV/records"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer usk5YzjFkoAuRfYFNcPCM0j"
        }

        applicant_details = []
        lender_details = []

        # Loop over each applicant
        for applicant in applicants:
            # Create JSON structure for each applicant
            applicant_data = {
                "records": [
                    {
                        "fields": {
                            "Application Hub": None,
                            "Title": None,
                            "First Name": applicant["applicant_name"].split()[0] if applicant.get("applicant_name") else None,
                            "Last Name": applicant["applicant_name"].split()[-1] if applicant.get("applicant_name") else None,
                            "Date of Birth": None,
                            "Residential Address": loan_security_addresses if loan_security_addresses else None,
                            "Primary Contact Number": applicant.get("contact_number") if applicant.get("contact_number") else None,
                            "Secondary Contact Number": None,
                            "Email Address": applicant.get("email") if applicant.get("email") else None,
                            "Marital Status": None,
                            "Savings": None,
                            "Income": None,
                            "Housing Loans": None,
                            "Vehicle Loans": None,
                            "Personal Loans": None,
                            "Total Liabilities": None,
                            "Employment Status": None,
                            "Employer": None
                        }
                    }
                ],
                "fieldKey": "name"
            }

            applicant_details.append(applicant_data)

            lender_data = {}
            # Post lender data only once
            if lender:
                lender_data = {
                    "records": [
                        {
                            "fields": {
                                "Company Name": lender,
                                "Contact": None,
                                "Website": None,
                                "Phone Number": None,
                            }
                        }
                    ],
                    "fieldKey": "name"
                }
            
            lender_details.append(lender_data)

        process_applicants(applicant_details, lender_details, applicant_api_url, lender_api_url, headers)

        return jsonify({"message": "URL processed successfully!"}), 200

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return jsonify({"message": "URL processed unsuccessfully!"}), 500

    finally:
        driver.quit()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=2500, debug=True)
