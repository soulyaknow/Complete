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
        # Ensure the request content-type is JSON
        if request.content_type != "application/json":
            return jsonify({"error": "Unsupported Media Type. Use 'application/json'"}), 415

        data = request.json

        # Extract applicationData and brokerData from the request
        application_data = data.get("applicationData", {})
        broker_data = data.get("brokerData", {})

        print("Received application data:", application_data)
        print("Received broker data:", broker_data)

        # Set up Selenium WebDriver without headless mode
        chrome_options = webdriver.ChromeOptions()
        
        chrome_options.add_argument("user-data-dir=C:\\Automation\\RPA")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # Install and set up the ChromeDriver
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
        
        try:
            # Navigate to the URL
            url = "https://sfg.salestrekker.com/authenticate"
            print(f"Navigating to {url}")
            driver.get(url)

            # Wait for specific elements to load (example: <a> tag)
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.TAG_NAME, "a"))
            )

            print("Login page is loaded. Pausing for user to input credentials...")

            # Pause and allow the user to input credentials
            time.sleep(30)

            print("Waiting for user to log in...")

            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "header-actions"))
            )

            print("Login successful. Continuing automation...")

            # click this 
            add_new_button = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//strong[contains(text(), 'Add new')]"))
            )

            print("'Add New' button is found. Clicking it...")

            add_new_button.click()

            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "st-ticket-contact-edit"))
            )

            print("Form loaded successfully. Filling out the fields...")

            # Fill out fields dynamically
            # driver.find_element(By.XPATH, "//*[@ng-model='$mdAutocompleteCtrl.scope.searchText' and @aria-label='First name']").send_keys(application_data.get("fields", {}).get("Housing Expense", ""))
            # driver.find_element(By.XPATH, "//*[@ng-model='$ctrl.contact.familyName']").send_keys(application_data.get("fields", {}).get("Household Income", ""))
            # driver.find_element(By.XPATH, "//*[@ng-model='$ctrl.contact.phone']").send_keys("Loan Type", "")
            # driver.find_element(By.XPATH, "//*[@ng-model='$ctrl.contact.email']").send_keys(application_data.get("fields", {}).get("App ID", ""))

            # Dynamically fill out the fields
            driver.find_element(By.XPATH, "//*[@ng-model='$mdAutocompleteCtrl.scope.searchText' and @aria-label='First name']").send_keys(
                application_data.get("fields", {}).get("Housing Expense", "")
            )

            driver.find_element(By.XPATH, "//*[@ng-model='$ctrl.contact.familyName']").send_keys(
                application_data.get("fields", {}).get("Household Income", "")
            )

            driver.find_element(By.XPATH, "//*[@ng-model='$ctrl.contact.phone']").send_keys(
                application_data.get("fields", {}).get("Loan Type", "")
            )

            driver.find_element(By.XPATH, "//*[@ng-model='$ctrl.contact.email']").send_keys(
                application_data.get("fields", {}).get("App ID", "")
            )


            # Locate and click the 'Next' button
            # next_button = driver.find_element(By.XPATH, "//button[@type='button' and contains(@ng-click, 'next(Model.activeSection)')]")
            # ActionChains(driver).move_to_element(next_button).perform()
            # next_button.click()
            next_button = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//button[@type='button' and contains(@ng-click, 'next(Model.activeSection)')]"))
            )

            print("Next button located. Clicking it...")

            next_button.click()

            # add_security_button = driver.find_element(By.XPATH, '//button[@type="button" and @ng-click="$ctrl.ticketLoanSecuritySplitAdd($event)"]')
            # ActionChains(driver).move_to_element(add_security_button).perform()
            # add_security_button.click()

            add_security_button = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, '//button[@type="button" and @ng-click="$ctrl.ticketLoanSecuritySplitAdd($event)"]'))
            )
            
            print("'Add Security' button located. Clicking it...")

            add_security_button.click()

            # driver.find_element(By.XPATH, "//*[@ng-model='$mdAutocompleteCtrl.scope.searchText']").send_keys(broker_data.get("recordId", ""))

            broker_field = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//*[@ng-model='$mdAutocompleteCtrl.scope.searchText']"))
            )

            broker_field.send_keys(broker_data.get("recordId", ""))

            print("Broker information entered successfully.")

        finally:
            # Additional actions if needed
            print("Form filled and submitted successfully.")
            return jsonify({"message": "Selenium automation executed successfully","success": True}), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Check for updates on start
    check_for_updates()

    # Start the Flask web service
    app.run(host="0.0.0.0", port=5213, debug=True)
