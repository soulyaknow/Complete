import tkinter as tk
import sys
import json
import os

def main():
    if len(sys.argv) != 2:
        print("Usage: temp_gui_launcher.py <data_file>")
        sys.exit(1)
    
    with open(sys.argv[1], 'r') as f:
        data = json.load(f)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(script_dir)
    from rpa import FileSelectorApp
    
    root = tk.Tk()
    app = FileSelectorApp(root, data['applicant_details'], data['application_recordIDs'])
    root.mainloop()

if __name__ == "__main__":
    main()