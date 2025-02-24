import os
import json
import subprocess
from flask import Flask, request, jsonify
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:5123"}}, supports_credentials=True)

@app.route('/', methods=['GET'])
def home():
    print('service is running')
    return "Service is running"

@app.before_request
def handle_options_requests():
    if request.method == "OPTIONS":
        response = app.make_response("")
        response.headers["Access-Control-Allow-Origin"] = "http://localhost:5123"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

# Function to check for updates (optional)
def check_for_updates():
    try:
        import requests
        headers = {"PRIVATE-TOKEN": "YOUR_GITLAB_PERSONAL_ACCESS_TOKEN"}
        GITLAB_API_URL = "https://gitlab.com/api/v4/projects/YOUR_PROJECT_ID/repository/commits"
        response = requests.get(f"{GITLAB_API_URL}?ref_name=main", headers=headers)
        if response.status_code != 200:
            raise Exception("GitLab repository not reachable.")

        data = response.json()
        latest_commit = data[0]["id"] if data else None

        latest_commit_file = "latest_commit.txt"
        if os.path.exists(latest_commit_file):
            with open(latest_commit_file, "r") as f:
                stored_commit = f.read().strip()
        else:
            stored_commit = None

        if not stored_commit or latest_commit != stored_commit:
            print("New update found, pulling changes...")
            subprocess.run(["git", "pull", "origin", "main"], check=True)
            with open(latest_commit_file, "w") as f:
                f.write(latest_commit)
        else:
            print("No updates found, starting application normally.")
    except Exception as e:
        print(f"Error checking for updates: {e}")
        print("Starting application normally...")

# Endpoint to execute Selenium automation
@app.route("/execute-selenium-script", methods=["POST", "OPTIONS"])
def execute_selenium_script():
    try:
        if request.content_type != "application/json":
            return jsonify({"error": "Unsupported Media Type. Use 'application/json'"}), 415

        # Parse JSON data
        data = request.json
        applicants_data = data.get("applicantRecords", [])
        application_data = data.get("applicationData", {})
        broker_data = data.get("brokerData", {})

        if not applicants_data:
            return jsonify({"error": "No applicant records provided"}), 400

        num_applicants = len(applicants_data)
        print(f"Number of applicants: {num_applicants}")

        # Set up Selenium WebDriver
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("user-data-dir=C:\\Automation\\RPA")  
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)

        try:
            url = "https://sfg.salestrekker.com/authenticate"
            print(f"Navigating to {url}")
            driver.get(url)

            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "a")))
            print("Login page is loaded. Pausing for user to input credentials...")
            time.sleep(30)

            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "img")))
            print("Login successful. Continuing automation...")

            driver.get("https://sfg.salestrekker.com/board/6e1f0fea-42df-4592-85b8-59fd49f78468")
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "header-actions")))
            print("Board page loaded. Ready to add new applications.")

            add_new_button = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//strong[contains(text(), 'Add new')]"))
            )
            add_new_button.click()

            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "st-ticket-contact-edit")))
            print("Form loaded successfully.")

            # If there are 2 applicants, click "Add another contact" first
            if num_applicants > 1:
                try:
                    add_another_contact_button = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//strong[contains(text(), 'Add another contact')]"))
                    )
                    add_another_contact_button.click()
                    print("Clicked 'Add another contact' button.")
                    
                    # Click the "Person" button to open modal for second applicant
                    person_button = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//button[@type='button' and contains(@ng-click, 'contactAdd(false)')]"))
                    )
                    person_button.click()
                    print("Clicked 'Person' button to add second applicant.")
                    
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//st-ticket-contact-edit"))
                    )
                except:
                    print("No 'Add another contact' or 'Person' button found, proceeding...")

            # Find all `st-ticket-contact-edit` elements
            contact_forms = driver.find_elements(By.XPATH, "//st-ticket-contact-edit")
            print(f"Found {len(contact_forms)} contact forms on the page.")

            # Loop through each applicant and fill the forms
            for idx, (contact_form, applicant) in enumerate(zip(contact_forms, applicants_data), start=1):
                fields = applicant.get("fields", {})
                first_name = fields.get("First Name", "")
                last_name = fields.get("Last Name", "")
                primary_contact = fields.get("Primary Contact Number", "")
                email_address = fields.get("Email Address", "")

                # Fill in the contact details
                contact_form.find_element(By.XPATH, ".//*[@ng-model='$mdAutocompleteCtrl.scope.searchText' and @aria-label='First name']").send_keys(first_name)
                contact_form.find_element(By.XPATH, ".//*[@ng-model='$ctrl.contact.familyName']").send_keys(last_name)
                contact_form.find_element(By.XPATH, ".//*[@ng-model='$ctrl.contact.phone']").send_keys(primary_contact)
                contact_form.find_element(By.XPATH, ".//*[@ng-model='$ctrl.contact.email']").send_keys(email_address)

                print(f"Entered Applicant {idx}: {first_name} {last_name}, Phone: {primary_contact}, Email: {email_address}")

            time.sleep(10)

            next_button = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//button[@type='button' and contains(@ng-click, 'next(Model.activeSection)')]"))
            )
            next_button.click()
            print("Clicked 'Next' button to proceed.")

            # Locate this tag name
            st_address_elements = driver.find_elements(By.XPATH, "//st-address")
            if st_address_elements:
                print(f"Found {len(st_address_elements)} 'st-address' elements.")

                # Loop through each <st-address> and find the input box inside
                for idx, (st_address, applicant) in enumerate(zip(st_address_elements, applicants_data), start=1):
                    fields = applicant.get("fields", {})
                    residential_address = fields.get("Residential Address", "")

                    try:
                        # Locate the input field
                        security_address_input = st_address.find_element(By.XPATH, ".//md-input-container//input[@type='text']")
                        
                        security_address_input.click()

                        security_address_input.send_keys(residential_address)

                        print(f"Entered address: {residential_address} for st-address {idx}")

                    except Exception as e:
                        print(f"Error interacting with st-address {idx}: {e}")
            else:
                print("No 'st-address' elements found.")

            # Locate the parent div
            parent_divs = driver.find_elements(By.XPATH, "//div[@layout-gt-sm='row' and @layout='column' and @layout-wrap]")

            if parent_divs:
                try:
                    # Locate the "Security value" label
                    security_label = driver.find_element(By.XPATH, "//span[contains(text(), 'Security value')]")
                    
                    # Find the input field next to the label
                    security_input = security_label.find_element(By.XPATH, ".//following::input[1]")

                    # Get the loan value from the applicant data
                    loan_value = applicant.get("fields", {}).get("Personal Loans", "")

                    # Clear existing input and type the new value
                    security_input.clear()
                    security_input.send_keys(loan_value)

                    print(f"Entered Security Value: {loan_value}")

                except Exception as e:
                    print(f"Error locating 'Security value' input field: {e}")

            else:
                print("No security sections found.")

        except Exception as e:
            print(f"An error occurred: {e}")
            return jsonify({"message": "RPA automation failed", "success": False, "error": str(e)}), 500

        finally:
            print("RPA process successfully.")
            return jsonify({"message": "RPA automation executed successfully", "success": True}), 200
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Check for updates on start
    check_for_updates()

    # Start the Flask web service
    app.run(host="0.0.0.0", port=5213, debug=True)
