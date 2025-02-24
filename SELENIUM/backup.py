import os
import time
import json
import requests
import mimetypes
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
    "drivers_license": ["license", "id", "driver"],
    "national_id": ["passport", "national", "citizen", "citizenship", "residency"],
    "utility_bill": ["bill", "utility"],
    "bank_statement": ["bank", "statement"],
    "application_form": ["application", "form"],
    "payslip": ["payslip", "salary", "payroll"],
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
    # Fetch existing applicants from APITable
    existing_applicants = get_existing_applicants(applicant_api_url, headers)
    
    # Filter out applicants that already exist
    new_applicants = []
    for applicant in applicant_details:
        is_existing = is_applicant_existing(applicant, existing_applicants)
        
        if not is_existing:
            new_applicants.append(applicant)
    
    # If there are new applicants, post their data
    if new_applicants:
        all_applicant_details = []
        for applicant_data in new_applicants:
            response_data = post_to_apitable(applicant_api_url, headers, applicant_data, "Applicant Hub")
            if response_data:
                all_applicant_details.extend(response_data)
        
        # Post lender data only once for the new applicants
        for lender_data in lender_details:
            response_data = post_to_apitable(lender_api_url, headers, lender_data, "Lender Hub")
        
        # Send data with files if new applicants were added
        if all_applicant_details:
            send_applicant_data_with_files(all_applicant_details)
        else:
            print("No valid applicant details to process.")
    else:
        print("No new applicants to process.")

def is_applicant_existing(applicant_data, existing_applicants):
    try:
        # Extract fields from applicant_data
        records = applicant_data.get("records", [])
        if not records:
            print("No records found in the applicant data.")
            return False
        
        applicant_fields = records[0].get("fields", {})
        applicant_first_name = applicant_fields.get("First Name")
        applicant_last_name = applicant_fields.get("Last Name")

        # Loop through existing applicants to find a match
        for record in existing_applicants:
            fields = record.get("fields", {})
            if (
                fields.get("First Name") == applicant_first_name
                and fields.get("Last Name") == applicant_last_name
            ):
                return True
        
        return False

    except KeyError as e:
        print(f"KeyError occurred: {str(e)}")
        return False

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

def get_file_metadata(file_path):
    file_name = os.path.basename(file_path)
    file_extension = os.path.splitext(file_name)[1]  # Get file extension
    mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"  # Guess MIME type
    return {"file_name": file_name, "file_extension": file_extension, "mime_type": mime_type}

def get_document_type(file_name):
    file_name_lower = file_name.lower()
    for doc_type, keywords in classified_documents.items():
        if any(keyword in file_name_lower for keyword in keywords):
            return doc_type
    return "unknown_document"

def prepare_headers_with_default_files(files):
    headers = {}

    # Initialize all document types with empty values
    for doc_type in classified_documents.keys():
        headers[f"{doc_type}"] = ""

    # Track document types and their corresponding files
    doc_files = {doc_type: [] for doc_type in classified_documents.keys()}

    # Assign actual file names if they exist
    for file_name in files:
        doc_type = get_document_type(file_name)
        if doc_type:
            doc_files[doc_type].append(file_name)

    # Update headers to store all found files under their document types
    for doc_type, files_in_type in doc_files.items():
        if files_in_type:
            headers[doc_type] = ", ".join(files_in_type)  # Store all files for that doc type

    return headers

def send_applicant_data_with_files(applicant_details):
    folder_created = False
    folder_path = ""
    combined_applicant_data = {}
    files_to_upload = []
    file_metadata = {}
    headers = {}

    # Combine applicant details into a single object
    if len(applicant_details) == 1:
        combined_applicant_data = {
            "Applicant1": {
                "Applicant_ID": applicant_details[0]["Applicant_ID"],
                "First Name": applicant_details[0]["First Name"],
                "Last Name": applicant_details[0]["Last Name"],
                "recordId": applicant_details[0]["recordId"],
            }
        }
    elif len(applicant_details) == 2:
        combined_applicant_data = {
            "Applicant1": {
                "Applicant_ID": applicant_details[0]["Applicant_ID"],
                "First Name": applicant_details[0]["First Name"],
                "Last Name": applicant_details[0]["Last Name"],
                "recordId": applicant_details[0]["recordId"],
            },
            "Applicant2": {
                "Applicant_ID": applicant_details[1]["Applicant_ID"],
                "First Name": applicant_details[1]["First Name"],
                "Last Name": applicant_details[1]["Last Name"],
                "recordId": applicant_details[1]["recordId"],
            }
        }
    else:
        print(f"Error: Expected 1 or 2 applicants but got {len(applicant_details)}.")
        return 

    # Full name of the first applicant
    full_name = f"{applicant_details[0]['First Name']} {applicant_details[0]['Last Name']}"

    # Check if folder exists
    folder_path = os.path.join(DOWNLOAD_PATH, full_name)
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        folder_created = True
        print(f"Using existing folder: {folder_path}")
    else:
        print(f"Folder not found for {full_name}.")
        return  

    # Collect files
    found_files = []
    if folder_created:
        for index, file_name in enumerate(os.listdir(folder_path)):
            file_path = os.path.join(folder_path, file_name)
            if os.path.isfile(file_path):
                metadata = get_file_metadata(file_path)
                file_metadata[f"file{index}"] = metadata
                
                # Get document type
                doc_type = get_document_type(file_name)

                # Store file for upload
                files_to_upload.append((file_name, open(file_path, "rb"), metadata["mime_type"], doc_type))

                found_files.append(file_name)  # Track found files

    # Ensure **all document types are included** in headers
    headers.update(prepare_headers_with_default_files(found_files))

    # Check if there are files
    if not files_to_upload:
        print("No files found for the applicants.")
        return  

    # Prepare multipart form-data payload
    fields = {
        "applicants": json.dumps(combined_applicant_data),
        "file_metadata": json.dumps(file_metadata)
    }

    # Add files to form-data
    for index, (file_name, file_obj, mime_type, _) in enumerate(files_to_upload):
        fields[f"files_{index}"] = (file_name, file_obj, mime_type)

    # Create multipart encoder
    multipart_data = MultipartEncoder(fields=fields)

    # Add Content-Type header
    headers["Content-Type"] = multipart_data.content_type

    # Define the endpoint
    n8n_endpoint = "https://integration.korunaassist.com/webhook-test/67944059-2667-4476-87e0-1b6ec63ea6ef"

    try:
        # Send POST request with custom headers
        response = requests.post(url=n8n_endpoint, data=multipart_data, headers=headers)

        # Close all file handles
        for _, file_obj, _, _ in files_to_upload:
            file_obj.close()

        # Handle response
        if response.status_code in (200, 201):
            print(f"✅ Successfully sent data for applicants!")
        else:
            print(f"❌ Failed to send data. Response Code: {response.status_code}")
            print("Response:", response.text)
    except requests.exceptions.RequestException as e:
        print(f"Error while sending data: {str(e)}")
    finally:
        # Ensure all file handles are closed
        for _, file_obj, _, _ in files_to_upload:
            file_obj.close()

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
            # Find all 'timeline-event' elements
            timeline_events = driver.find_elements(By.TAG_NAME, "timeline-event")

            for index, event in enumerate(timeline_events):
                try:
                    # Check if the element contains <span>Labels</span>
                    labels_span = event.find_elements(By.XPATH, ".//span[text()='Labels']")
                    if labels_span:
                        # Scroll the timeline-event into view
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", event)
                        time.sleep(1)  # Allow some time for smooth scrolling
                        
                        # Locate the download button
                        download_button = event.find_element(By.XPATH, ".//md-icon[text()='cloud_download']")
                        if download_button:
                            # Scroll into view and click the download button
                            ActionChains(driver).move_to_element(download_button).perform()
                            download_button.click()
                            print(f"Download button clicked for timeline-event #{index + 1}.")
                            time.sleep(2)  # Optional: Wait between downloads
                except Exception as inner_e:
                    print(f"Error processing timeline-event #{index + 1}: {inner_e}")
                    continue

        except Exception as e:
            print(f"An error occurred: {e}")


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

                # post_to_apitable(lender_url, headers, lender_data, "Lender Hub")
            
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
