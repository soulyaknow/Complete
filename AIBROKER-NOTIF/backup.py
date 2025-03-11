import requests
import schedule
import time
import json
import os
import sys
from plyer import notification

# Set UTF-8 encoding for standard output and error
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# AITable API Details
API_URL = "https://ai-broker.korunaassist.com/fusion/v1/datasheets/dst1vag1MekDBbrzoS/records"
HEADERS = {"Authorization": "Bearer usk5YzjFkoAuRfYFNcPCM0j"}

BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
LAST_RECORD_FILE = os.path.join(BASE_DIR, "last_record.json")
ICON_PATH = os.path.join(BASE_DIR, "ka.ico") 

def get_current_record_count():
    try:
        response = requests.get(API_URL, headers=HEADERS)
        data = response.json()
        return data.get("data", {}).get("total", 0)
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return None

def save_last_record_count(count):
    try:
        with open(LAST_RECORD_FILE, "w") as f:
            json.dump({"last_count": count}, f)
    except Exception as e:
        print(f"❌ Error saving last record count: {e}")

def load_last_record_count():
    try:
        with open(LAST_RECORD_FILE, "r") as f:
            data = json.load(f)
            return data.get("last_count", 0)
    except FileNotFoundError:
        return 0  # If no file exists, assume no previous records
    except Exception as e:
        print(f"❌ Error loading last record count: {e}")
        return 0

def show_notification(new_records):
    try:
        notification.notify(
            title="AI Broker Notification",
            message=f"📢 New Data Entry!\n {new_records} new record added.",
            app_name="AI Broker",
            app_icon=ICON_PATH if os.path.exists(ICON_PATH) else None,
            timeout=10  
        )
    except Exception as e:
        print(f"❌ Notification error: {e}")

def check_new_records():
    print("🔄 Checking for new records...")
    last_count = load_last_record_count()
    current_count = get_current_record_count()

    if current_count is None:
        return 

    if current_count > last_count:
        new_records = current_count - last_count
        print(f"🆕 {new_records} new records added!")
        show_notification(new_records)

    # Save the updated record count
    save_last_record_count(current_count)

# Run every 10 seconds
schedule.every(10).seconds.do(check_new_records)

print(f"✅ Windows Notification System Started. Monitoring AITable for new records...\nJSON File Path: {LAST_RECORD_FILE}")

# Keep the script running
while True:
    schedule.run_pending()
    time.sleep(1)
