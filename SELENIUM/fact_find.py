import os
import time
import requests
import logging
import re
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
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager
from requests_toolbelt.multipart.encoder import MultipartEncoder
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, NoSuchElementException
from dotenv import load_dotenv


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

load_dotenv()

def get_select_text(root, xpath):
    try:
        element = root.find_element(By.XPATH, xpath)
        select = Select(element)
        return select.first_selected_option.text
    except NoSuchElementException:
        return None
    except Exception:
        return None

def get_input_value(root, xpath):
    try:
        element = root.find_element(By.XPATH, xpath)
        return element.get_attribute("value")
    except NoSuchElementException:
        return None
    except Exception:
        return None

def get_radio_value(driver,group_xpath):
    group = driver.find_element(By.XPATH, group_xpath)
    selected = group.find_element(By.XPATH, ".//md-radio-button[@aria-checked='true']")
    return selected.find_element(By.XPATH, ".//span").text.strip()

def get_element_text(root, xpath):
    try:
        element = root.find_element(By.XPATH, xpath)
        return element.text.strip()
    except NoSuchElementException:
        return None
    except Exception:
        return None

def get_select_text_with_index(root, xpath, index):
    try:
        elements = root.find_elements(By.XPATH, xpath)
        if index < len(elements):
            select = Select(elements[index])
            return select.first_selected_option.text
        return None
    except Exception:
        return None

def get_input_value_with_index(root, xpath, index):
    try:
        elements = root.find_elements(By.XPATH, xpath)
        if index < len(elements):
            return elements[index].get_attribute("value")
        return None
    except Exception:
        return None

def get_household_expense_by_label(active_driver, label_text):
    try:
        # Find the label element
        label_xpath = f"//label[contains(text(), '{label_text}')]"
        label_elem = active_driver.find_element(By.XPATH, label_xpath)

        # Get the nearest repeating parent div
        parent = label_elem.find_element(By.XPATH, "./ancestor::div[contains(@class, 'layout-gt-sm-row')]")

        # Now use the parent as the root for input/select lookups
        amount = get_input_value(parent, ".//input[@ng-model='householdExpense.value']")
        frequency = get_select_text(parent, ".//select[@ng-model='householdExpense.frequency']")

        # Monthly value (disabled input)
        try:
            monthly_value = get_input_value(parent, ".//input[@disabled and contains(@value,'$')]")
        except NoSuchElementException:
            monthly_value = None

        return {
            "Amount": amount,
            "Frequency": frequency,
            "Monthly Value": monthly_value
        }

    except Exception as e:
        logging.error(f"Failed to get household expense for label '{label_text}': {e}")
        return {
            "Amount": None,
            "Frequency": None,
            "Monthly Value": None
        }

def safe_get_element_value(element, selector, selector_type=By.CSS_SELECTOR, get_attribute="value"):
    """Safely get element value with better error handling"""
    try:
        found_element = element.find_element(selector_type, selector)
        return found_element.get_attribute(get_attribute)
    except Exception as e:
        logger.debug(f"Failed to get element value for selector {selector}: {str(e)}")
        return None

def safe_get_select_value(element, selector, selector_type=By.CSS_SELECTOR):
    """Safely get select element value with better error handling"""
    try:
        select_element = Select(element.find_element(selector_type, selector))
        return select_element.first_selected_option.text
    except Exception as e:
        logger.debug(f"Failed to get select value for selector {selector}: {str(e)}")
        return None

def extract_income_data(block):
    """Extract income data from a block with safe element access"""
    try:
        linked_contact = safe_get_select_value(block, 'select[ng-model="$ctrl.income.idContact"]')
        
        return {
            "Applicant Income": {
                "Gross Salary": safe_get_element_value(block, 'input[ng-model="$ctrl.income.payg.grossSalary"]'),
                "Gross Salary Freq": safe_get_select_value(block, 'select[ng-model="$ctrl.income.payg.grossSalaryFrequency"]'),
                "Allowance": safe_get_element_value(block, 'input[ng-model="$ctrl.income.payg.allowance"]'),
                "Allowance Freq": safe_get_select_value(block, 'select[ng-model="$ctrl.income.payg.allowanceFrequency"]'),
                "Bonus": safe_get_element_value(block, 'input[ng-model="$ctrl.income.payg.bonus"]'),
                "Bonus Freq": safe_get_select_value(block, 'select[ng-model="$ctrl.income.payg.bonusFrequency"]'),
                "Commission": safe_get_element_value(block, 'input[ng-model="$ctrl.income.payg.commission"]'),
                "Commission Freq": safe_get_select_value(block, 'select[ng-model="$ctrl.income.payg.commissionFrequency"]'),
                "Overtime Essential": safe_get_element_value(block, 'input[ng-model="$ctrl.income.payg.overtimeEssential"]'),
                "Overtime Essential Freq": safe_get_select_value(block, 'select[ng-model="$ctrl.income.payg.overtimeEssentialFrequency"]'),
                "Overtime Non Essential": safe_get_element_value(block, 'input[ng-model="$ctrl.income.payg.overtimeNonEssential"]'),
                "Overtime Non Essential Freq": safe_get_select_value(block, 'select[ng-model="$ctrl.income.payg.overtimeNonEssentialFrequency"]'),
                "Linked Contact": linked_contact,
                "Linked Employer": safe_get_element_value(block, 'span[ng-bind="employment.getEmployerName() || \'N/A\'"]', get_attribute="textContent"),
            },
            "Existing Rental Income": [],
            "Annual Income Summary": [],
            "Annual Net Income": []
        }
    except Exception as e:
        logger.error(f"Error extracting income data: {str(e)}")
        return None

def extract_rental_data(block):
    """Extract rental data from a block with safe element access"""
    try:
        return {
            "Client": safe_get_element_value(block, './/span[small[text()="Client:"]]/span[@class="ng-binding"]', By.XPATH, "textContent"),
            "Percent": safe_get_element_value(block, './/span[small[text()="Percent:"]]/span[@class="ng-binding"]', By.XPATH, "textContent"),
            "Monthly Rental Income": safe_get_element_value(block, './/span[small[contains(text(),"Monthly rental income")]]/span[@class="ng-binding"]', By.XPATH, "textContent")
        }
    except Exception as e:
        logger.error(f"Error extracting rental data: {str(e)}")
        return None

def get_ownership(block):
    ownership_data = []
    try:
        owner_items = block.find_elements(By.XPATH, ".//content-item")
        for owner in owner_items:
            try:
                name = owner.find_element(By.XPATH, ".//span[1]").text.strip()
                percent = owner.find_element(By.XPATH, ".//span[2]").text.strip()
                ownership_data.append({"Name": name, "Percentage": percent})
            except:
                continue
    except:
        pass
    return ownership_data

def clean_currency(value):
    if not value:
        return 0
    # Remove $ and commas
    cleaned = re.sub(r'[^\d.]', '', value)
    try:
        return float(cleaned)
    except ValueError:
        return 0

def extract_fact_find(active_driver):
    try:
        logger.info("Starting fact find extraction")
        
        wait = WebDriverWait(active_driver, 10)
        personal_buttons = wait.until(EC.presence_of_all_elements_located(
            (By.XPATH, "//div[@class='group-items']//button//span[@ng-bind='contact.getName()']")
        ))
        logger.info(f"Found {len(personal_buttons)} applicants to process")

        personal_data = []
        
        # Extract Personal Details
        for i, button in enumerate(personal_buttons):
            logger.info(f"Processing applicant {i + 1} of {len(personal_buttons)}")
            
            wait.until(EC.element_to_be_clickable((By.XPATH, f"(//div[@class='group-items']//button//span[@ng-bind='contact.getName()'])[{i + 1}]")))
            button.click()
            time.sleep(2)  # Allow content to load
            
            try:
                num_dependents_element = wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//select[@ng-model='$ctrl.contact.person.information.numberOfDependents']")
                ))
                num_dependents = int(Select(num_dependents_element).first_selected_option.text)
            except Exception:
                num_dependents = 0

            # Get dependents information
            dependents = []
            age_containers = active_driver.find_elements(By.XPATH, "//md-input-container[label[contains(text(), 'Age of dependant')]]")

            for d_idx in range(num_dependents):
                name_xpath = f"(//input[@ng-model='dependent.name'])[{d_idx + 1}]"
                dob_xpath = f"(//md-datepicker[contains(@ng-model, 'getSetDependentDateOfBirth')]/div[@class='md-datepicker-input-container']//input[contains(@class, 'md-datepicker-input')])[{d_idx + 1}]"

                name = get_input_value(active_driver, name_xpath)
                dob = get_input_value(active_driver, dob_xpath)

                try:
                    age_input = age_containers[d_idx].find_element(By.TAG_NAME, "input")
                    age = age_input.get_attribute("value")

                    dependents.append({
                        "Name": name,
                        "Date of Birth": dob,
                        "Age": age
                    })
                except Exception:
                    continue

            # Get employment information
            current_employer = []
            previous_employer = []
            employment_containers = active_driver.find_elements(By.XPATH, "//div[contains(@ng-repeat, 'employment in $ctrl.contact.person.employments')]")
            
            for employment in employment_containers:
                try:
                    status_element = employment.find_element(By.XPATH, ".//em[@ng-bind=\"$ctrl.employment.isCurrent ? 'Current employer' : 'Previous employer'\"]")
                    status_value = status_element.text.strip()
                    is_current = status_value.lower() == "current employer"

                    employer_info = {
                        "Employment Status": get_select_text(active_driver, "//select[@ng-model='$ctrl.employment.isCurrent']"),
                        "Employment Type": get_select_text(active_driver, "//select[@ng-model='$ctrl.employment.type']"),
                        "Employment Priority": get_select_text(active_driver, "//select[@ng-model='$ctrl.employment.status']"),
                        "Employment Basis": get_select_text(active_driver, "//select[@ng-model='$ctrl.employment.basis']"),
                        "Occupation": get_input_value(active_driver, "//input[@ng-model='$ctrl.employment.role']"),
                        "Employer Name": get_input_value(active_driver, "//input[@aria-label='Employer name']"),
                        "Title": get_select_text(active_driver, "//select[@ng-model='$ctrl.employment.employerContactTitle']"),
                        "Employer Contact First Name": get_input_value(active_driver, "//input[@ng-model='$ctrl.employment.employerContactFirstName']"),
                        "Employer Contact Surname": get_input_value(active_driver, "//input[@ng-model='$ctrl.employment.employerContactSurname']"),
                        "Prefix": get_input_value(active_driver, "//input[@ng-model='$ctrl.employment.employerPhoneCode']"),
                        "Employer Phone": get_input_value(active_driver, "//input[@ng-model='$ctrl.employment.employerPhone']"),
                        "Employer Type": get_select_text(active_driver, "//select[@ng-model='$ctrl.employment.employerType']"),
                        "Employer ABN": get_input_value(active_driver, "//input[@aria-label='Employer ABN']"),
                        "Employer ACN": get_input_value(active_driver, "//input[@aria-label='Employer ACN']"),
                        "ABS Occupation Code": get_input_value(active_driver, "//input[@aria-label='ABS occupation code']"),
                        "ANZSCO Industry Code": get_input_value(active_driver, "//input[@aria-label='ANZSCO industry code']"),
                        "Employer Address": {
                            "Search Employer Address": get_input_value(employment, ".//input[@aria-label='Search employer address']"),
                            "Unit Number": get_input_value(employment, ".//input[@ng-model='$ctrl.address.suiteNumber']"),
                            "Street Number": get_input_value(employment, ".//input[@ng-model='$ctrl.address.streetNumber']"),
                            "Street Name": get_input_value(employment, ".//input[@ng-model='$ctrl.address.street']"),
                            "Street Type": get_input_value(employment, ".//input[@aria-label='Street type']"),
                            "Country": get_select_text(employment, ".//select[@ng-model='$ctrl.address.country']"),
                            "Town": get_input_value(employment, ".//input[@ng-model='$ctrl.address.suburb']"),
                            "State": get_select_text(employment, ".//select[@ng-model='$ctrl.address.state']"),
                            "Postal Code": get_input_value(employment, ".//input[@ng-model='$ctrl.address.postCode']")
                        }
                    }

                    if is_current:
                        current_employer.append(employer_info)
                    else:
                        previous_employer.append(employer_info)
                except Exception:
                    continue

            # Get personal details
            personal_details = {
                "Personal Details": {
                    "Title": get_select_text(active_driver, "//select[@ng-model='$ctrl.contact.person.information.title']"),
                    "First Name": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.information.firstName']"),
                    "Middle Name": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.information.middleName']"),
                    "Sur Name": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.information.familyName']"),
                    "Preferred Name": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.information.preferredName']"),
                    "Previous Name": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.information.previousName']"),
                    "Gender": get_select_text(active_driver, "//select[@ng-model='$ctrl.contact.person.information.gender']"),
                    "Date of Birth": get_input_value(active_driver, "//input[@placeholder='DD/MM/YYYY']")
                },
                "Contact Details": {
                    "Prefix 1": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.contact.primaryCode']"),
                    "Mobile Number": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.contact.primary']"),
                    "Prefix 2": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.contact.homeCode']"),
                    "Home Number": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.contact.home']"),
                    "Prefix 3": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.contact.workCode']"),
                    "Work Number": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.contact.work']"),
                    "Email 1": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.contact.email']"),
                    "Email 2": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.contact.secondaryEmail']"),
                    "Website": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.contact.website']")
                },
                "Current Address": {
                    "Search Current Address": get_input_value(active_driver, "//input[@aria-label='Search current address']"),
                    "Unit Number": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.suiteNumber']"),
                    "Street Number": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.streetNumber']"),
                    "Street Name": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.street']"),
                    "Street Type": get_input_value(active_driver, "//input[@aria-label='Street type']"),
                    "Country": get_select_text(active_driver, "//select[@ng-model='$ctrl.address.country']"),
                    "Town": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.suburb']"),
                    "State": get_select_text(active_driver, "//select[@ng-model='$ctrl.address.state']"),
                    "Postal Code": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.postCode']"),
                    "Residential Status": get_select_text(active_driver, "//select[@ng-model='$ctrl.contact.person.contact.housing']")
                },
                "Previous Address": {
                    "Search Previous Address": get_input_value(active_driver, "//input[@aria-label='Search previous address']"),
                    "Unit Number": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.suiteNumber']"),
                    "Street Number": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.streetNumber']"),
                    "Street Name": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.street']"),
                    "Street Type": get_input_value_with_index(active_driver, "//input[@aria-label='Street type']", 1),
                    "Country": get_select_text_with_index(active_driver, "//select[@ng-model='$ctrl.address.country']", 1),
                    "Town": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.suburb']"),
                    "State": get_select_text_with_index(active_driver, "//select[@ng-model='$ctrl.address.state']", 1),
                    "Postal Code": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.postCode']"),
                    "Residential Status": get_select_text(active_driver, "//select[@ng-model='$ctrl.contact.person.contact.previousHousing']")
                },
                "Mailing Address": {
                    "Search Mailing Address": get_input_value(active_driver, "//input[@aria-label='Search mailing address']"),
                    "Unit Number": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.suiteNumber']"),
                    "Street Number": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.streetNumber']"),
                    "Street Name": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.street']"),
                    "Street Type": get_input_value_with_index(active_driver, "//input[@aria-label='Street type']", 0),
                    "Country": get_select_text_with_index(active_driver, "//select[@ng-model='$ctrl.address.country']", 0),
                    "Town": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.suburb']"),
                    "State": get_select_text_with_index(active_driver, "//select[@ng-model='$ctrl.address.state']", 0),
                    "Postal Code": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.postCode']")
                },
                "Post Settlement Address": {
                    "Search Post Settlement Address": get_input_value(active_driver, "//input[@aria-label='Search post settlement address']"),
                    "Unit Number": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.suiteNumber']"),
                    "Street Number": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.streetNumber']"),
                    "Street Name": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.street']"),
                    "Street Type": get_input_value_with_index(active_driver, "//input[@aria-label='Street type']", 1),
                    "Country": get_select_text_with_index(active_driver, "//select[@ng-model='$ctrl.address.country']", 1),
                    "Town": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.suburb']"),
                    "State": get_select_text_with_index(active_driver, "//select[@ng-model='$ctrl.address.state']", 1),
                    "Postal Code": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.postCode']"),
                    "Residential Status": get_select_text(active_driver, "//select[@ng-model='$ctrl.contact.person.contact.settlementHousing']")
                },
                "Identification": {
                    "Country of Residency": get_select_text(active_driver, "//select[@ng-model='$ctrl.contact.person.information.countryOfResidency']"),
                    "Country of Tax Residence": get_select_text(active_driver, "//select[@ng-model='$ctrl.contact.person.information.countryOfTaxResidence']"),
                    "Citizenship": get_select_text(active_driver, "//select[@ng-model='$ctrl.contact.person.information.citizenship']"),
                    "Residency Status": get_select_text(active_driver, "//select[@ng-model='$ctrl.contact.person.information.residentialStatus']"),
                    "Country of Birth": get_select_text(active_driver, "//select[@ng-model='$ctrl.contact.person.information.countryOfBirth']"),
                    "City of Birth": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.information.cityOfBirth']"),
                    "Driver License Details": {
                        "Driver License Type": get_select_text(active_driver, "//select[@ng-model='$ctrl.contact.person.information.driversLicenseType']"),
                        "Driver License Number": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.information.driversLicenseNumber']"),
                        "Driver License Card Number": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.information.driversLicenseCardNumber']"),
                        "Driver License Name on Document": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.information.driversLicenseNameOnDocument']"),
                        "Driver License State of Issue": get_select_text(active_driver, "//select[@ng-model='$ctrl.contact.person.information.driversLicenseStateOfIssue']")
                    },
                    "Passport Details": {
                        "Passport Number": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.information.passportNumber']"),
                        "Passport Name on Document": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.information.passportNameOnDocument']"),
                        "Passport Issue Country": get_select_text(active_driver, "//select[@ng-model='$ctrl.contact.person.information.passportIssueCountry']")
                    },
                    "Medicare Details": {
                        "Medicare Number": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.information.medicareNumber']"),
                        "Medicare Reference Number": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.information.medicareReferenceNumber']"),
                        "Medicare Name on Card": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.information.medicareNameOnCard']"),
                        "Medicare Card Color": get_select_text(active_driver, "//select[@ng-model='$ctrl.contact.person.information.medicareCardColor']")
                    }
                },
                "Family Relations": {
                    "Mother's Maiden Name": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.information.mothersMaidenName']"),
                    "Marital Status": get_select_text(active_driver, "//select[@ng-model='$ctrl.contact.person.information.maritalStatus']"),
                    "Spouse Name": {
                        "First Name": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.name']"),
                        "Surname": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.familyName']")
                    },
                    "Number of Dependents": str(num_dependents)
                },
                "Dependents": dependents,
                "Next of Kin": {
                    "Full Name": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.information.nextOfKinFullName']"),
                    "Relationship": get_select_text(active_driver, "//select[@ng-model='$ctrl.contact.person.information.nextOfKinRelationship']"),
                    "Phone Prefix": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.information.nextOfKinPhoneCode']"),
                    "Phone Number": get_input_value(active_driver, "//input[@ng-model='$ctrl.contact.person.information.nextOfKinPhone']")
                },
                "Next of Kin Address": {
                    "Search Address": get_input_value(active_driver, "//input[@aria-label='Search next of kin address']"),
                    "Unit Number": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.suiteNumber']"),
                    "Street Number": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.streetNumber']"),
                    "Street Name": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.street']"),
                    "Street Type": get_input_value(active_driver, "//input[@aria-label='Street type']"),
                    "Country": get_select_text(active_driver, "//select[@ng-model='$ctrl.address.country']"),
                    "Town": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.suburb']"),
                    "State": get_select_text(active_driver, "//select[@ng-model='$ctrl.address.state']"),
                    "Postal Code": get_input_value(active_driver, "//input[@ng-model='$ctrl.address.postCode']")
                },
                "Current Employer": current_employer,
                "Previous Employer": previous_employer,
                "SoW": {
                    "Source of Wealth": get_select_text(active_driver, "//select[@ng-model='$ctrl.contact.person.information.sourceOfWealth']"),
                    "Source of Funds for This Application": get_select_text(active_driver, "//select[@ng-model='$ctrl.contact.person.information.sourceOfFunds']")
                }
            }
            personal_data.append(personal_details)

        # Extract Income Data
        try:
            income_button = active_driver.find_element(By.XPATH, "//button[contains(@ng-click, 'income')]")
            income_button.click()

            wait.until(
                EC.presence_of_all_elements_located((By.XPATH, '//st-block[@ng-if="$ctrl.isReady && $ctrl.income.length"]'))
            )
       
            income_blocks = active_driver.find_elements(By.XPATH,'//st-block[@ng-repeat="income in $ctrl.income | orderBy:\'incomeType.weight\'"]')
            rental_blocks = active_driver.find_elements(By.XPATH, '//div[@class="inside-block ma1 layout-column"]//summary')
            annual_summary_blocks = active_driver.find_elements(By.XPATH, '//div[@ng-repeat="contact in $ctrl.contacts"]')
            net_income_blocks = active_driver.find_elements(By.XPATH, '//div[@ng-repeat="contact in $ctrl.contacts"]')

            income = []
            rental = []
            annual_income_summary = []
            annual_net_income = []

            # Extract rental data
            for block in rental_blocks:
                rental_data = extract_rental_data(block)
                if rental_data:
                    rental.append(rental_data)

            # Extract net income data
            net_income_label_map = {
                "Net income": "Net Income"
            }
            temp_net_income = {}
            for block in net_income_blocks:
                try:
                    name = safe_get_element_value(block, './/strong[@ng-bind="contact.getName()"]', By.XPATH, "textContent")
                    summary = {"Name": name}
                    
                    for container in block.find_elements(By.TAG_NAME, 'md-input-container'):
                        try:
                            label = safe_get_element_value(container, 'label', By.TAG_NAME, "innerText").strip()
                            if label in net_income_label_map:
                                value = safe_get_element_value(container, 'input', By.TAG_NAME)
                                summary[net_income_label_map[label]] = value
                        except Exception:
                            continue

                    if name:
                        temp_net_income[name] = summary
                except Exception:
                    continue
            
            annual_net_income = list(temp_net_income.values())

            # Extract annual income summary
            annual_income_label_map = {
                "Total PAYG income": "Total PAYG Income",
                "Total rental income": "Total Rental Income",
                "Total other taxable income": "Total Other Taxable Income",
                "Total non taxable income": "Total Non Taxable Income"
            }
            temp_annual_income = {}
            for block in annual_summary_blocks:
                try:
                    name = safe_get_element_value(block, './/strong[@ng-bind="contact.getName()"]', By.XPATH, "textContent")
                    summary = {"Name": name}

                    for container in block.find_elements(By.TAG_NAME, 'md-input-container'):
                        try:
                            label = safe_get_element_value(container, 'label', By.TAG_NAME, "innerText").strip()
                            if label in annual_income_label_map:
                                value = safe_get_element_value(container, 'input', By.TAG_NAME)
                                summary[annual_income_label_map[label]] = value
                        except Exception:
                            continue

                    if len(summary) > 1 and name:
                        temp_annual_income[name] = summary
                except Exception:
                    continue
            
            annual_income_summary = list(temp_annual_income.values())

            # Extract income blocks
            for block in income_blocks:
                income_data = extract_income_data(block)
                if income_data:
                    linked_contact = income_data["Applicant Income"]["Linked Contact"]
                    
                    # Add related rental income
                    
                    for rent in rental:
                        if rent["Client"] == linked_contact:
                            income_data["Existing Rental Income"].append(rent)
                    
                    # Add related annual income summary
                    for ais in annual_income_summary:
                        if ais["Name"] == linked_contact:
                            income_data["Annual Income Summary"].append(ais)

                    # Add related net income
                    for ani in annual_net_income:
                        if ani["Name"] == linked_contact:
                            income_data["Annual Net Income"].append(ani)

                    income.append(income_data)

        except Exception as e:
            logger.error(f"Error extracting income data: {str(e)}")
            income = []

        # Extract Expenses Data
        try:
            expenses_button = active_driver.find_element(By.XPATH, "//button[contains(@ng-click, 'expenses')]")
            expenses_button.click()

            wait.until(
                EC.visibility_of_element_located((By.XPATH, "//label[.//em[text()='Expenses']]"))
            )

            select_element = active_driver.find_element(By.XPATH, '//md-select[@aria-label="Contact(s)"]')
            contact_names = select_element.find_elements(By.XPATH, './/span[@ng-bind="contact.getName()"]')
            contacts = [name.text.strip() for name in contact_names if name.text.strip()]

            expense = {
                "Contact": contacts,
                "Food & Supermarket": get_household_expense_by_label(active_driver,"Food & supermarket"),
                "Coffee Lunches Takeaway": get_household_expense_by_label(active_driver,"Coffees, lunches takeaway"),
                "Cigarette & Alcohol": get_household_expense_by_label(active_driver,"Cigarettes & alcohol"),
                "Total Monthly Food Expenses": get_input_value(active_driver,"//label[contains(text(), 'Total monthly food expenses')]/following-sibling::input[@disabled]"),
                "Entertainment": get_household_expense_by_label(active_driver,"Entertainment"),
                "Domestic Holidays": get_household_expense_by_label(active_driver,"Domestic holidays"),
                "Clothing, Shoes & Accessories": get_household_expense_by_label(active_driver,"Clothing, shoes & accessories"),
                "Hairdressing & Gromming": get_household_expense_by_label(active_driver,"Hairdressing & grooming"),
                "Phone, Internet & Pay TV": get_household_expense_by_label(active_driver,"Phone, Internet & pay TV"),
                "Media Streaming & Subscription": get_household_expense_by_label(active_driver,"Media streaming & subscription services"),
                "Gift & Celebrations": get_household_expense_by_label(active_driver,"Gifts & celebrations"),
                "Other Discretionary Expenses": get_household_expense_by_label(active_driver,"Other discretionary expenses"),
                "Pets": get_household_expense_by_label(active_driver,"Pets"),
                "Total Monthly Discretionary Expenses": get_input_value(active_driver,"//label[contains(text(), 'Total monthly discretionary expenses')]/following-sibling::input[@disabled]"),
                "Public Education Costs": get_household_expense_by_label(active_driver,"Public education costs"),
                "Private Education Costs": get_household_expense_by_label(active_driver,"Private education costs"),
                "Tertiary & Vocational Education": get_household_expense_by_label(active_driver,"Tertiary & vocational education"),
                "Childcare": get_household_expense_by_label(active_driver,"Childcare"),
                "Total Monthly Children And Education": get_input_value(active_driver,"//label[contains(text(), 'Total monthly children and education expenses')]/following-sibling::input[@disabled]"),
                "Gym Fees, Sport, Other Health & Wellness": get_household_expense_by_label(active_driver,"Gym fees, sport, other health & wellness"),
                "Private Health Insurance": get_household_expense_by_label(active_driver,"Private health insurance"),
                "Doctor, Dentist, Pharmacy Glassess": get_household_expense_by_label(active_driver,"Doctor, dentist, pharmacy, glasses"),
                "Life, Trauma, Income Insurance": get_household_expense_by_label(active_driver,"Life, trauma, income insurance"),
                "Total Monthly Health & Insurance": get_input_value(active_driver,"//label[contains(text(), 'Total monthly health & wellness expenses')]/following-sibling::input[@disabled]"),
                "Recreational Vehicle Running Costs": get_household_expense_by_label(active_driver,"Recreational vehicle running costs"),
                "Essential Vehicle Running Costs": get_household_expense_by_label(active_driver,"Essential vehicle running cost"),
                "Public Transport, Taxis & Ride Share, Commuting Airfares": get_household_expense_by_label(active_driver,"Public transport, taxis & ride share, commuting airfares"),
                "Essential Vehicle Insurance": get_household_expense_by_label(active_driver,"Essential vehicle insurance"),
                "Total Monthly Transport Expenses": get_input_value(active_driver,"//label[contains(text(), 'Total monthly transport expenses')]/following-sibling::input[@disabled]"),
                "Primary Residence Running Costs": get_household_expense_by_label(active_driver,"Primary residence running costs"),
                "Primary Residence Land Tax": get_household_expense_by_label(active_driver,"Primary residence land tax"),
                "Secondary Residence Running Costs": get_household_expense_by_label(active_driver,"Secondary residence running costs"),
                "Secondary Residence Body Corp": get_household_expense_by_label(active_driver,"Secondary residence body corp"),
                "Investment Property Running Costs": get_household_expense_by_label(active_driver,"Investment property running costs"),
                "Investment Property Body Corp": get_household_expense_by_label(active_driver,"Investment property body corp"),
                "Total Monthly Property Expenses": get_input_value(active_driver,"//label[contains(text(), 'Total monthly property expenses')]/following-sibling::input[@disabled]"),
                "Child or Spousal Maintenance": get_household_expense_by_label(active_driver,"Child or spousal maintenance"),
                "Current Rent Expense": get_household_expense_by_label(active_driver,"Current rent expense"),
                "Ongoing Board Expense": get_household_expense_by_label(active_driver,"Ongoing board expense"),
                "Total Monthly Other Commitments": get_input_value(active_driver,"//label[contains(text(), 'Total monthly other commitments')]/following-sibling::input[@disabled]"),
                "Totals": {
                    "Expenses":  get_input_value(active_driver,"//label[contains(text(), 'Expenses')]/following-sibling::input[@disabled]"),
                    "Living Expenses (in HEM)": get_input_value(active_driver,"//label[contains(text(), 'Living expenses (in HEM)')]/following-sibling::input[@disabled]"),
                    "Living Expenses (not in HEM)": get_input_value(active_driver,"//label[contains(text(), 'Living expenses (not in HEM)')]/following-sibling::input[@disabled]"),
                    "Other Commitments (not in HEM)": get_input_value(active_driver,"//label[contains(text(), 'Other commitments (not in HEM)')]/following-sibling::input[@disabled]"),
                }
            }

        except Exception as e:
            logger.error(f"Error extracting expenses data: {str(e)}")
            expense = []
        
        # Extract Assets Data
        try:    
            assets_button = active_driver.find_element(By.XPATH, "//button[contains(@ng-click, 'showSection') and contains(@ng-click, 'assets')]")
            assets_button.click()

            wait.until(
                EC.visibility_of_element_located((By.XPATH, "//st-block-form-header[label/em[text()='Assets']]"))
            )

            assets = []
            asset_blocks = active_driver.find_elements(By.XPATH, "//st-block[contains(@ng-repeat, 'asset in')]")
            total_vehicle_value = 0
            total_home_content_value = 0

            for block in asset_blocks:
                try:
                    label = block.find_element(By.XPATH, ".//em").text.strip()

                    if label in ["Owner occupier property address", "Investment property address"]:
                        asset_data = {
                            "Label": label,
                            "Address": get_input_value(block, ".//input[@aria-label='Owner occupier property address']"),
                            "Unit Number": get_input_value(block, ".//input[@ng-model='$ctrl.address.suiteNumber']"),
                            "Street Number": get_input_value(block, ".//input[@ng-model='$ctrl.address.streetNumber']"),
                            "Street Name": get_input_value(block, ".//input[@ng-model='$ctrl.address.street']"),
                            "Street Type": get_input_value(block, ".//input[contains(@aria-label, 'Street type')]"),
                            "Country": get_select_text(block, ".//select[@ng-model='$ctrl.address.country']"),
                            "Town": get_input_value(block, ".//input[@ng-model='$ctrl.address.suburb']"),
                            "State": get_select_text(block, ".//select[@ng-model='$ctrl.address.state']"),
                            "Postal Code": get_input_value(block, ".//input[@ng-model='$ctrl.address.postCode']"),
                            "Value": get_input_value(block, ".//input[@ng-model='$ctrl.asset.value']"),
                            "Property Type": get_select_text(block, ".//select[@ng-model='$ctrl.asset.propertyType']"),
                            "Zoning": get_select_text(block, ".//select[@ng-model='$ctrl.asset.zoning']"),
                            "Valuation": get_select_text(block, ".//select[@ng-model='$ctrl.asset.valuation']"),
                            "Ownership": get_ownership(block)
                        }
                        assets.append(asset_data)

                    elif label == "Vehicle make and model":
                        value = get_input_value(block, ".//input[@ng-model='$ctrl.asset.value']")
                        total_vehicle_value += clean_currency(value)
                    
                    elif label == "Bank accounts":
                        bank_data = {
                            "Label": label,
                            "Bank": get_select_text(block, ".//md-select[@ng-model='$ctrl.asset.name']"),
                            "Bank Account Type": get_select_text(block, ".//select[@ng-model='$ctrl.asset.bankAccountType']"),
                            "BSB": get_input_value(block, ".//input[@ng-model='$ctrl.asset.bankBsb']"),
                            "Account Number": get_input_value(block, ".//input[@ng-model='$ctrl.asset.bankAccountNumber']"),
                            "Value": get_input_value(block, ".//input[@ng-model='$ctrl.asset.value']"),
                            "Ownership": get_ownership(block)
                        }
                        assets.append(bank_data)
                    
                    elif label == "Home contents":
                        value = get_input_value(block, ".//input[@ng-model='$ctrl.asset.value']")
                        total_home_content_value += clean_currency(value)
                    
                    elif label == "Super fund institution":
                        super_data = {
                            "Label": label,
                            "Institution": get_input_value(block, ".//input[@ng-model='$ctrl.asset.name']"),
                            "Membership Number": get_input_value(block, ".//input[@ng-model='$ctrl.asset.membershipNumber']"),
                            "Value": get_input_value(block, ".//input[@ng-model='$ctrl.asset.value']"),
                            "Ownership": get_ownership(block)
                        }
                        assets.append(super_data)

                    elif label == "Shares":
                        shares_data = {
                            "Label": label,
                            "Shares": get_input_value(block, ".//input[@ng-model='$ctrl.asset.name']"),
                            "Value": get_input_value(block, ".//input[@ng-model='$ctrl.asset.value']"),
                            "Ownership": get_ownership(block)
                        }
                        assets.append(shares_data)

                    elif label == "Other":
                        other_data = {
                            "Label": label,
                            "Other": get_input_value(block, ".//input[@ng-model='$ctrl.asset.name']"),
                            "Value": get_input_value(block, ".//input[@ng-model='$ctrl.asset.value']"),
                            "Ownership": get_ownership(block)
                        }
                        assets.append(other_data)

                    elif label == "Balance sheet":
                        balance_sheet_data = {
                            "Label": label,
                            "Item": get_input_value(block, ".//input[@ng-model='$ctrl.asset.name']"),
                            "As At Date": get_input_value(block, ".//input[contains(@class, 'md-datepicker-input')]"),
                            "Value": get_input_value(block, ".//input[@ng-model='$ctrl.asset.value']"),
                            "Ownership": get_ownership(block)
                        }
                        assets.append(balance_sheet_data)
                except Exception as e:
                    print(f"Error processing asset block: {e}")

            # Append the total values
            if total_vehicle_value > 0:
                assets.append({
                    "Label": "Vehicle make and model",
                    "Total Value": f"${total_vehicle_value:,.2f}"
                })

            if total_home_content_value > 0:
                assets.append({
                    "Label": "Home content",
                    "Total Value": f"${total_home_content_value:,.2f}"
                })

            try:
                total_assets_block = active_driver.find_element(By.XPATH, "//em[text()='Total assets']/ancestor::st-block")
                contact_blocks = total_assets_block.find_elements(By.XPATH, ".//div[@ng-repeat='contact in $ctrl.contacts']")
                for contact_block in contact_blocks:
                    try:
                        name = contact_block.find_element(By.XPATH, ".//strong").text.strip()
                        value = contact_block.find_element(By.XPATH, ".//input").get_attribute("value") or ""

                        assets.append({
                            "Label": "Total assets",
                            "Contact": name,
                            "Value": value.strip()
                        })
                    except Exception as e:
                        print(f"Error processing total assets for contact: {e}")
            except Exception as e:
                print(f"Couldn't find total assets block: {e}")

        except Exception as e:
            logger.error(f"Error extracting assets data: {str(e)}")
            assets = []

        # Extract Liabilities Data
        try:
            liabilities_button = active_driver.find_element(By.XPATH, "//button[contains(@class, 'md-button') and .//span[text()='Liabilities']]")
            liabilities_button.click()

            wait.until(
                EC.visibility_of_element_located((By.XPATH, "//st-block-form-header[.//em[text()='Liabilities']]"))
            )

            liabilities = []
            liabilities_blocks = active_driver.find_elements(By.XPATH, "//st-block[contains(@ng-repeat, 'liability in')]")

            for block in liabilities_blocks:
                try:
                    label = block.find_element(By.XPATH, ".//em").text.strip()

                    if label == "Mortgage loan":
                        mortage_data = {
                            "Label": label,
                            "Lender": get_select_text(block, ".//md-select[@ng-model='$ctrl.liability.name']"),
                            "BSB": get_input_value(block, ".//input[@ng-model='$ctrl.liability.bsb']"),
                            "Account Number": get_input_value(block, ".//input[@ng-model='$ctrl.liability.accountNumber']"),
                            "Interest Rate": get_input_value(block, ".//input[@ng-model='$ctrl.liability.interestRate']"),
                            "Mortgage Type": get_select_text(block, ".//select[@ng-model='$ctrl.liability.mortgageType']"),
                            "Limit": get_input_value(block, ".//input[@ng-model='$ctrl.liability.limit']"),
                            "Balance": get_input_value(block, ".//input[@ng-model='$ctrl.liability.balance']"),
                            "Repayment Monthly": get_input_value(block, ".//input[@ng-model='$ctrl.liability.repayment']"),
                            "Loan Term Expiry Date": get_input_value(block, ".//input[@placeholder='MM/YYYY']"),
                            "Repayment Type": get_select_text(block, ".//select[@ng-model='$ctrl.liability.repaymentType']"),
                            "Linked Asset": get_select_text(block, ".//select[@ng-model='$ctrl.liability.idAsset']"),
                            "Fixed Expiry Date": get_input_value(block, ".//input[@placeholder='DD/MM/YYYY']"),
                            "Ownership": get_ownership(block) 
                        }
                        liabilities.append(mortage_data)
                    
                    elif label == "Credit card":
                        credit_data = {
                            "Label": label,
                            "Lender": get_select_text(block, ".//md-select[@ng-model='$ctrl.liability.name']"),
                            "Credit Card Type": get_select_text(block, ".//select[@ng-model='$ctrl.liability.creditCardType']"),
                            "Credit Card Number": get_input_value(block, ".//input[@ng-model='$ctrl.liability.creditCardNumber']"),
                            "Limit": get_input_value(block, ".//input[@ng-model='$ctrl.liability.limit']"),
                            "Balance": get_input_value(block, ".//input[@ng-model='$ctrl.liability.balance']"),
                            "Ownership": get_ownership(block)
                        }
                        liabilities.append(credit_data)

                    elif label == "Vehicle loan":
                        vehicle_data = {
                            "Label": label,
                            "Lender": get_select_text(block, ".//md-select[@ng-model='$ctrl.liability.name']"),
                            "BSB": get_input_value(block, ".//input[@ng-model='$ctrl.liability.bsb']"),
                            "Account Number": get_input_value(block, ".//input[@ng-model='$ctrl.liability.accountNumber']"),
                            "Interest Rate": get_input_value(block, ".//input[@ng-model='$ctrl.liability.interestRate']"),
                            "Net Amount Financed": get_input_value(block, ".//input[@ng-model='$ctrl.liability.limit']"),
                            "Balance": get_input_value(block, ".//input[@ng-model='$ctrl.liability.balance']"),
                            "Repayment Monthly": get_input_value(block, ".//input[@ng-model='$ctrl.liability.repayment']"),
                            "Loan Term Expiry Date": get_input_value(block, ".//input[contains(@placeholder, 'MM/YYYY')]"),
                            "Linked Asset": get_select_text(block, ".//select[@ng-model='$ctrl.liability.idAsset']"),
                            "Ownership": get_ownership(block)
                        }
                        liabilities.append(vehicle_data)

                    elif label in ["Personal loan", "Other"]:
                        personal_loan_data = {
                            "Label": label,
                            "Lender": get_select_text(block, ".//md-select[@ng-model='$ctrl.liability.name']"),
                            "BSB": get_input_value(block, ".//input[@ng-model='$ctrl.liability.bsb']"),
                            "Account Number": get_input_value(block, ".//input[@ng-model='$ctrl.liability.accountNumber']"),
                            "Interest Rate": get_input_value(block, ".//input[@ng-model='$ctrl.liability.interestRate']"),
                            "Net Amount Financed": get_input_value(block, ".//input[@ng-model='$ctrl.liability.limit']"),
                            "Balance": get_input_value(block, ".//input[@ng-model='$ctrl.liability.balance']"),
                            "Repayment Monthly": get_input_value(block, ".//input[@ng-model='$ctrl.liability.repayment']"),
                            "Loan Term Expiry Date": get_input_value(block, ".//input[contains(@placeholder, 'MM/YYYY')]"),
                            "Ownership": get_ownership(block)
                        }
                        liabilities.append(personal_loan_data)
                    
                    elif label == "SMSF loan":
                        smsf_loan_data = {
                            "Label": label,
                            "Lender": get_select_text(block, ".//md-select[@ng-model='$ctrl.liability.name']"),
                            "BSB": get_input_value(block, ".//input[@ng-model='$ctrl.liability.bsb']"),
                            "Account Number": get_input_value(block, ".//input[@ng-model='$ctrl.liability.accountNumber']"),
                            "Interest Rate": get_input_value(block, ".//input[@ng-model='$ctrl.liability.interestRate']"),
                            "Net Amount Financed": get_input_value(block, ".//input[@ng-model='$ctrl.liability.limit']"),
                            "Balance": get_input_value(block, ".//input[@ng-model='$ctrl.liability.balance']"),
                            "Repayment Monthly": get_input_value(block, ".//input[@ng-model='$ctrl.liability.repayment']"),
                            "Loan Term Expiry Date": get_input_value(block, ".//input[@placeholder='MM/YYYY']"),
                            "Repayment Type": get_select_text(block, ".//select[@ng-model='$ctrl.liability.repaymentType']"),
                            "Linked Asset": get_select_text(block, ".//select[@ng-model='$ctrl.liability.idAsset']"),
                            "Fixed Expiry Date": get_input_value(block, ".//input[@placeholder='DD/MM/YYYY']"),
                            "Ownership": get_ownership(block)
                        }
                        liabilities.append(smsf_loan_data)

                    elif label == "Student loan":
                        student_loan_data = {
                            "Label": label,
                            "Details": get_input_value(block, ".//input[@ng-model='$ctrl.liability.name']"),
                            "Balance": get_input_value(block, ".//input[@ng-model='$ctrl.liability.balance']"),
                            "Repayment Monthly": get_input_value(block, ".//input[@ng-model='$ctrl.liability.repayment']"),
                            "Ownership": get_ownership(block)
                        }
                        liabilities.append(student_loan_data)

                    elif label == "Balance sheet":
                        balance_sheet_data = {
                            "Label": label,
                            "Name": get_input_value(block, ".//input[@ng-model='$ctrl.liability.name']"),
                            "Balance": get_input_value(block, ".//input[@ng-model='$ctrl.liability.balance']"),
                            "Repayment Monthly": get_input_value(block, ".//input[@ng-model='$ctrl.liability.repayment']"),
                            "As At Date": get_input_value(block, ".//input[contains(@class, 'md-datepicker-input')]"),
                            "Ownership": get_ownership(block)
                        }
                        liabilities.append(balance_sheet_data)
                except Exception as e:
                    print(f"Error processing liabilities block: {e}")

            try:
                total_liabilities_block = active_driver.find_element(By.XPATH, "//em[text()='Total liability']/ancestor::st-block")
                contact_blocks = total_liabilities_block.find_elements(By.XPATH, ".//div[@ng-repeat='contact in $ctrl.contacts']")
                for contact_block in contact_blocks:
                    try:
                        name = contact_block.find_element(By.XPATH, ".//strong").text.strip()
                        balance = contact_block.find_element(By.XPATH, ".//label[contains(text(), 'Total balance')]/following-sibling::input").get_attribute("value") or ""
                        repayment = contact_block.find_element(By.XPATH, ".//label[contains(text(), 'Total repayment monthly')]/following-sibling::input").get_attribute("value") or ""

                        liabilities.append({
                            "Label": "Total liability",
                            "Contact": name,
                            "Total Balance": balance.strip(),
                            "Total Repayment Monthly": repayment.strip()
                        })
                    except Exception as e:
                        print(f"Error processing total liability for contact {name}: {e}")
            except Exception as e:
                print(f"Error locating total liability block: {e}")

        except Exception as e:
            logger.error(f"Error extracting liabilities data: {str(e)}")
            liabilities = []
        
        # Extract Needs and Objectives
        try:
            needs_button = active_driver.find_element(By.XPATH, "//button[.//span[contains(., 'Needs and objectives')]]")
            needs_button.click()

            time.sleep(15)

            wait.until(
                EC.visibility_of_element_located((By.XPATH, "//label[./em[text()='Needs and objectives']]"))
            )

            needs = []
            try:
                needs_data = {
                    "Purchase_property": get_input_value(active_driver,"//input[@ng-model='$ctrl.objectives.requirementsAndObjectives.purposeDetails.purchasePropertyAmount']"),
                    "Construction": get_input_value(active_driver,"//input[@ng-model='$ctrl.objectives.requirementsAndObjectives.purposeDetails.constructionAmount']"),
                    "Renovations": get_input_value(active_driver,"//input[@ng-model='$ctrl.objectives.requirementsAndObjectives.purposeDetails.renovationsAmount']"),
                    "Investment_purposes": get_input_value(active_driver,"//input[@ng-model='$ctrl.objectives.requirementsAndObjectives.purposeDetails.investmentPurposesAmount']"),
                    "Purchase_vehicle": get_input_value(active_driver,"//input[@ng-model='$ctrl.objectives.requirementsAndObjectives.purposeDetails.purchaseAssetAmount']"),
                    "Refinance": get_input_value(active_driver,"//input[@ng-model='$ctrl.objectives.requirementsAndObjectives.purposeDetails.refinanceAmount']"),
                    "Debt_consolidation": get_input_value(active_driver,"//input[@ng-model='$ctrl.objectives.requirementsAndObjectives.purposeDetails.debtConsolidationAmount']"),
                    "Other_purposes": get_input_value(active_driver,"//input[@ng-model='$ctrl.objectives.requirementsAndObjectives.purposeDetails.otherAmount']"),
                    "Total": get_input_value(active_driver,"//input[@ng-model='$ctrl.objectives.requirementsAndObjectives.purposeDetails.totalAmount']")
                }
                needs.append(needs_data)

            except Exception as e:
                print(f"Error locating needs: {e}")
                needs = []

        except Exception as e:
            logger.error(f"Error extracting needs data: {str(e)}")
            needs = []

        # Extract Product requirements
        try:
            # Click the product requirements button
            products_button = active_driver.find_element(By.XPATH, "//button[.//span[contains(., 'Product requirements')]]")
            products_button.click()

            # Wait for the required element to be visible
            wait.until(EC.visibility_of_element_located((By.XPATH, "//label[./em[normalize-space() = 'BID process steps']]")))

            product_requirements = []
            try:
                # Extract values for various radio groups
                rate_type_value = get_radio_value(active_driver, "//md-radio-group")
                variable_value = get_radio_value(active_driver, "//md-radio-group[contains(@ng-model, 'rateType.variable')]")
                fixed_variable_value = get_radio_value(active_driver, "//md-radio-group[contains(@ng-model, '$ctrl.objectives.rateType.fixedAndVariable.type')]")
                repayment_value = get_radio_value(active_driver, "//md-radio-group[contains(@ng-model, '$ctrl.objectives.repaymentType.principalAndInterest.type')]")
                repayment_frequency_value = get_radio_value(active_driver, "//md-radio-group[contains(@ng-model, '$ctrl.objectives.repaymentType.principalAndInterest.preferredPaymentFrequency')]")
                product_type_value = get_radio_value(active_driver, "//md-radio-group[contains(@ng-model, '$ctrl.objectives.productType.offsetAccount.type')]")
                redraw_value = get_radio_value(active_driver, "//md-radio-group[contains(@ng-model, '$ctrl.objectives.productType.redraw.type')]")
                
                # Extract dropdown values using the provided helper function
                term_of_credit_years = get_select_text(active_driver, "//select[contains(@ng-model, 'termOfCreditSought.years')]")
                term_of_credit_months = get_select_text(active_driver, ".//select[@ng-model='$ctrl.objectives.termOfCreditSought.months']")
                
                # Extract input field values using the provided helper function
                preferred_lenders = get_input_value(active_driver, "ng-model='$ctrl.objectives.termOfCreditSought.preferredLenders'")
                any_lenders = get_input_value(active_driver, ".//input[@ng-model='$ctrl.objectives.termOfCreditSought.notLenders']")

                # Prepare the data
                requirements_data = {
                    "Rate Type": rate_type_value,
                    "Variable Rate": variable_value,
                    "Fixed and Variable Rate": fixed_variable_value,
                    "Repayment Type": repayment_value,
                    "Repayment Frequency": repayment_frequency_value,
                    "Product Type": product_type_value,
                    "Redraw": redraw_value,
                    "Term of credit sought": {
                        "Years": term_of_credit_years,
                        "Month": term_of_credit_months,
                        "Preferred Lenders": preferred_lenders,
                        "Any Lenders": any_lenders
                    }
                }

                product_requirements.append(requirements_data)

            except Exception as e:
                print(f"Error locating product requirements: {e}")
                product_requirements = []

        except Exception as e:
            logger.error(f"Error extracting product requirements data: {str(e)}")
            product_requirements = []

        # Extract Security Details
        try:
            security_button = active_driver.find_element(By.XPATH, "//button[contains(@class, 'md-button') and .//span[text()='Security details']]")
            security_button.click()

            wait.until(EC.visibility_of_element_located((By.XPATH, "//label[.//em[normalize-space(text())='Security details']]")))

            security = []

            # Extract security blocks
            security_blocks = active_driver.find_elements(By.XPATH, "//st-block[contains(@ng-if, '$ctrl.securityDetails.securitySplits')]")
            for block in security_blocks:
                try:
                    security_details = []
                    contact_details = []
                    title_details = []
                    other_details = []

                    label_element = block.find_element(By.XPATH, ".//em[contains(text(), 'Security')]")
                    label = label_element.text.strip()

                    if label and "Security" in label:
                        security_data = {
                            "street_number": get_input_value(block, ".//input[@ng-model='$ctrl.address.streetNumber']"),
                            "street_name": get_input_value(block, ".//input[@ng-model='$ctrl.address.street']"),
                            "street_type": get_input_value(block, ".//input[@aria-label='Street type']"),
                            "country": get_select_text(block, ".//select[@ng-model='$ctrl.address.country']"),
                            "town": get_input_value(block, ".//input[@ng-model='$ctrl.address.suburb']"),
                            "state": get_select_text(block, ".//select[@ng-model='$ctrl.address.state']"),
                            "postal_code": get_input_value(block, ".//input[@ng-model='$ctrl.address.postCode']"),
                            "security_value": get_input_value(block, ".//input[@ng-model='security.value']"),
                            "property_value": get_select_text(block, ".//select[@ng-model='security.propertyType']"),
                            "zoning": get_select_text(block, ".//select[@ng-model='security.zoning']"),
                            "valuation": get_select_text(block, ".//select[@ng-model='security.valuation']"),
                            "owner_type": get_select_text(block, ".//select[@ng-model='security.ownershipType']"),
                            "ownership": get_ownership(block)
                        }
                        security_details.append(security_data)

                    # Extract Contact for valuation blocks
                    contact_blocks = active_driver.find_elements(By.XPATH, "//st-block[contains(@ng-if, '$ctrl.securityDetails.contactsForValuation')]")
                    for contact_block in contact_blocks:
                        contact_data = {
                            "loan_party": get_select_text(contact_block, ".//select[@ng-model='contact.loanParty']"),
                            "unit_number": get_input_value(contact_block, ".//input[@ng-model='$ctrl.address.suiteNumber']"),
                            "street_number": get_input_value(contact_block, ".//input[@ng-model='$ctrl.address.streetNumber']"),
                            "street_name": get_input_value(contact_block, ".//input[@ng-model='$ctrl.address.street']"),
                            "street_type": get_input_value(contact_block, ".//input[@ng-model='$mdAutocompleteCtrl.scope.searchText']"),
                            "country": get_select_text(contact_block, ".//select[@ng-model='$ctrl.address.country']")
                        }
                        contact_details.append(contact_data)

                    # Extract Title details blocks
                    title_blocks = active_driver.find_elements(By.XPATH, "//st-block[contains(@ng-if, '$ctrl.securityDetails.titleDetails')]")
                    for title_block in title_blocks:
                        title_data = {
                            "title_type": get_select_text(title_block, ".//select[@ng-model='title.titleType']"),
                            "title": get_select_text(title_block, ".//select[@ng-model='title.title']"),
                            "lot": get_input_value(title_block, ".//input[@ng-model='title.lot']"),
                            "plan": get_input_value(title_block, ".//input[@ng-model='title.plan']"),
                            "volume": get_input_value(title_block, ".//input[@ng-model='title.volume']"),
                            "folio": get_input_value(title_block, ".//input[@ng-model='title.folio']")
                        }
                        title_details.append(title_data)

                    # Extract Other mortgages blocks
                    other_blocks = active_driver.find_elements(By.XPATH, "//st-block[contains(@ng-if, '$ctrl.securityDetails.otherMortgages')]")
                    for other_block in other_blocks:
                        other_data = {
                            "lender": None,
                            "balance": get_input_value(other_block, ".//input[@ng-model='mortgage.balance']"),
                            "limit": get_input_value(other_block, ".//input[@ng-model='mortgage.limit']"),
                            "monthly_repayment": get_input_value(other_block, ".//input[@ng-model='mortgage.repayment']"),
                            "bsb": get_input_value(other_block, ".//input[@ng-model='mortgage.bsb']"),
                            "account_number": get_input_value(other_block, ".//input[@ng-model='mortgage.accountNumber']"),
                            "interest_rate": get_input_value(other_block, ".//input[@ng-model='mortgage.interestRate']"),
                            "repayment_type": get_select_text(other_block, ".//select[@ng-model='mortgage.repaymentType']"),
                            "ownership": get_ownership(other_block)
                        }
                        try:
                            lender_element = other_block.find_element(By.XPATH, ".//md-select-value/span[1]")
                            lender_text = lender_element.text.strip() if lender_element else None
                            if lender_text == "" or lender_text == "\u00a0":  # non-breaking space
                                lender_text = None
                            other_data["lender"] = lender_text
                        except:
                            other_data["lender"] = None

                        # Optional: skip empty blocks if no lender and no balance
                        if any(v for k, v in other_data.items() if k != "ownership" and v):
                            other_details.append(other_data)

                    datas = {
                        "Security": security_details,
                        "Contact": contact_details,
                        "Title": title_details,
                        "Other": other_details
                    }
                    security.append(datas)

                except Exception as e:
                    print(f"Error processing security block: {e}")

        except Exception as e:
            logger.error(f"Error extracting security data: {str(e)}")
            security = []

        # Extract Funding Details
        try:
            funding_button = active_driver.find_element(By.XPATH, "//button[contains(@class, 'md-button') and .//span[text()='Funding worksheet']]")
            funding_button.click()

            wait.until(EC.visibility_of_element_located((By.XPATH, "//label[.//em[normalize-space()='Funding worksheet']]")))

            time.sleep(15)

            funding = []

            # For Funds Required (A)
            funding_required_a_block = active_driver.find_element(By.XPATH, "//st-block-form-header[label/em[text()='Funds required (A)']]")
            label_a = funding_required_a_block.find_element(By.XPATH, ".//em").text.strip()
            if label_a == "Funds required (A)":
                funding_data_a = {
                    "Security_address": get_input_value(funding_required_a_block, ".//blank-input[starts-with(@ng-bind, '$ctrl.getSecurity')]"),
                    "Security_value": get_input_value(funding_required_a_block, ".//input[@ng-model='fundRequired.purposeFunds']"),
                    "Transaction_type": get_select_text(funding_required_a_block, ".//select[@ng-model='fundRequired.transactionType']"),
                    "Ownership_type": get_select_text(funding_required_a_block, ".//select[@ng-model='fundRequired.ownershipType']"),
                    "Property_status": get_select_text(funding_required_a_block, ".//select[@ng-model='fundRequired.propertyStatus']"),
                    "Existing_loan_balance": get_input_value(funding_required_a_block, ".//input[@ng-model='fundRequired.existingLoanBalance']"),
                    "Exit_fee": get_input_value(funding_required_a_block, ".//input[@ng-model='fundRequired.exitFee']"),
                    "LMI_premium_already_paid": get_input_value(funding_required_a_block, ".//input[@ng-model='fundRequired.lmiPremiumAlreadyPaid']"),
                    "Mortgage_discharge_costs": get_input_value(funding_required_a_block, ".//input[@ng-model='fundRequired.mortgageDischargeCosts']"),
                    "Mortgage_registration_fees": get_input_value(funding_required_a_block, ".//input[@ng-model='fundRequired.mortgageRegistrationFees']"),
                    "Lender_fees": get_input_value(funding_required_a_block, ".//input[@ng-model='fundRequired.lenderFees']"),
                    "Other_fees/Costs": get_input_value(funding_required_a_block, ".//input[@ng-model='fundRequired.otherFees']")
                }
                funding.append(funding_data_a)

            # For Funds Available (B)
            funding_available_b_block = active_driver.find_element(By.XPATH, "//st-block-form-header[label/em[text()='Funds available (B)']]")
            label_b = funding_available_b_block.find_element(By.XPATH, ".//em").text.strip()
            if label_b == "Funds available (B)":
                funding_data_b = {
                    "Proposed_loan_amount": get_input_value(funding_available_b_block, ".//input[@ng-model='fundAvailable.proposedLoanAmount']"),
                    "First_home_owners_grant_(FHOG)": get_input_value(funding_available_b_block, ".//input[@ng-model='fundAvailable.firstHomeOwnersGrant']"),
                    "Sale_proceed_funds": get_input_value(funding_available_b_block, "//input[@ng-model='fundAvailable.saleProceedFunds']"),
                    "Savings": get_input_value(funding_available_b_block, "//input[@ng-model='fundAvailable.savings']"),
                    "Equity_from_property": get_input_value(funding_available_b_block, "//input[@ng-model='fundAvailable.equityFromProperty']"),
                    "Deposit_paid": get_input_value(funding_available_b_block, "//input[@ng-model='fundAvailable.depositPaid']"),
                    "Gift": get_input_value(funding_available_b_block, "//input[@ng-model='fundAvailable.gift']"),
                    "Other_funds_available": get_input_value(funding_available_b_block, "//input[@ng-model='fundAvailable.otherFundsAvailable']"),
                    "Base_LVR": get_input_value(funding_available_b_block, "//input[@ng-model='fundAvailable.baseLvr']"),
                    "Lender_mortgage_insurance_(LMI)": {
                        "Value": get_input_value(funding_available_b_block, "//input[@ng-model='fundAvailable.lmi']"),
                        "Bank": funding_available_b_block.find_element(By.XPATH, "//md-select-value[@class='md-select-value']").text.strip()
                    },
                    "Total_LVR": get_input_value(funding_available_b_block, "//input[@ng-model='fundAvailable.totalLvr']"),
                    "Total_proposed_loan_amount": get_input_value(funding_available_b_block, "//input[@ng-model='fundAvailable.totalProposedLoanAmount']")
                }
                funding.append(funding_data_b)

            # For Total Funds
            total_funds_block = active_driver.find_element(By.XPATH, "//st-block-form-header[label/em[text()='Total funds']]")
            total_funds_data = {
                "total_funds_a": get_input_value(total_funds_block, "//input[@ng-model='$ctrl.fundingWorksheets.fundsTotal.required']"),
                "total_funds_b": get_input_value(total_funds_block, "//input[@ng-model='$ctrl.fundingWorksheets.fundsTotal.available']"),
                "funds_surplus_a_b": get_input_value(total_funds_block, "//input[@ng-model='$ctrl.fundingWorksheets.fundsTotal.difference']")
            }
            funding.append(total_funds_data)

        except Exception as e:
            logger.error(f"Error extracting funding data: {str(e)}")
            funding = []

        # Extract Maximum Borrowing

        # Extract Search Loan Products
        try:
            loan_button = active_driver.find_element(By.XPATH, "//button[@ng-click=\"showSection('searchLoanProducts')\" and .//span[text()='Search loan products']]")
            loan_button.click()

            wait.until(EC.visibility_of_element_located((By.XPATH, "//label[.//em[text()='Search loan products']]")))

            loan = []
            
            blocks = active_driver.find_element(By.XPATH, "//st-block[@ng-if='$ctrl.isReady']//st-block-form-header")
            
            loan_data = {
                "selected_lender": active_driver.find_element(By.XPATH, "//md-select-value//span[@class='ng-binding']").text,
                "loan_ammount": get_input_value(blocks, "//input[@ng-model='$ctrl.searchFields.loanAmount']"),
                "lvr": get_input_value(blocks, "//input[@ng-model='$ctrl.searchFields.lvr']"),
                "loan_term": get_select_text(blocks, "//select[@ng-model='$ctrl.searchFields.loanTerm']"),
                "loan_type": get_select_text(blocks, "//select[@ng-model='$ctrl.searchFields.loanType']"),
                "repayment_type": get_select_text(blocks, "//select[@ng-model='$ctrl.searchFields.repaymentType']"),
                "rate_type": get_select_text(blocks, "//select[@ng-model='$ctrl.searchFields.rateType']"),
                "property_use": get_select_text(blocks, "//select[@ng-model='$ctrl.searchFields.propertyUse']"),
                "construction": get_select_text(blocks, "//select[@ng-model='$ctrl.searchFields.construction']"),
                "redraw_facility": get_select_text(blocks, "//select[@ng-model='$ctrl.searchFields.redrawFacility']"),
                "offset": get_select_text(blocks, "//select[@ng-model='$ctrl.searchFields.offset']"),
                "line_of_credit": get_select_text(blocks, "//select[@ng-model='$ctrl.searchFields.lineOfCredit']"),
                "smsf": get_select_text(blocks, "//select[@ng-model='$ctrl.searchFields.smsf']"),
                "additional_repayment": get_select_text(blocks, "//select[@ng-model='$ctrl.searchFields.additionalRepayments']"),
                "ability_loan_split": get_select_text(blocks, "//select[@ng-model='$ctrl.searchFields.abilityToSplitLoan']"),
                "lmi_capitalization": get_select_text(blocks, "//select[@ng-model='$ctrl.searchFields.lmiCapitalization']"),
                "rewards": get_select_text(blocks, "//select[@ng-model='$ctrl.searchFields.rewards']")
            }
            loan.append(loan_data)

        except Exception as e:
            logger.error(f"Error extracting loan data: {str(e)}")
            loan = []

        # Extract Review loan products
        try:
            loan_product_button = active_driver.find_element(By.XPATH, "//button[@ng-click=\"showSection('reviewLoanProducts')\"]/span[contains(text(), 'Review loan products')]")
            loan_product_button.click()

            wait.until(EC.visibility_of_element_located((By.XPATH, "//label[./em[text()='Review loan products']]")))

            time.sleep(15)

            loan_product = []
            blocks = active_driver.find_elements(By.XPATH, "//st-block[@ng-repeat='reviewProduct in $ctrl.reviewProducts track by reviewProduct.id']")

            for block in blocks:
                product_data = {
                    "lender_name": block.find_element(By.XPATH, ".//span[@class='truncate ng-binding']").text,
                    "product_name": block.find_element(By.XPATH, ".//span[@class='truncate ng-binding' and @ng-bind='::productSplit.productName']").text,
                    "loan_amount": get_input_value(block, ".//input[@ng-model='productSplit.totalLoanAmount']"),
                    "lmi": get_input_value(block, ".//input[@ng-model='productSplit.lmi']"),
                    "total_loan_amount": get_input_value(block, ".//input[@ng-model='productSplit.totalLoanAmountWithLmi']"),
                    "maximum_borrowing": get_input_value(block, ".//input[@ng-model='productSplit.maximumBorrowing']"),
                    "interest_rate": get_input_value(block, ".//input[@ng-model='productSplit.interestRate']"),
                    "interest_rate_discount": get_input_value(block, ".//input[@ng-model='productSplit.interestRateDiscount']"),
                    "interest_rate_product": get_input_value(block, ".//input[@ng-model='productSplit.interestRateOfProduct']"),
                    "revert_rate": get_input_value(block, ".//input[@ng-model='productSplit.revertRate']"),
                    "revert_rate_discount": get_input_value(block, ".//input[@ng-model='productSplit.revertRateDiscount']"),
                    "revert_rate_product": get_input_value(block, ".//input[@ng-model='productSplit.revertRateOfProduct']"),
                    "loan_term_years": get_select_text(block, ".//select[@ng-model='productSplit.loanTerm']"),
                    "initial_offset_balance": get_input_value(block, ".//input[@ng-model='productSplit.offsetBalance']"),
                    "monthly_offset_contribution": get_input_value(block, ".//input[@ng-model='productSplit.monthlyOffsetContribution']"),
                    "cashback_discount": get_input_value(block, ".//input[@ng-model='productSplit.cashback']"),
                    "abs_lending_purpose_code": block.find_element(By.XPATH, ".//md-select[@ng-model='productSplit.absLendingPurposeCode']").text
                }
                loan_product.append(product_data)

        except Exception as e:
            logger.error(f"Error extracting loan data: {str(e)}")
            loan_product = []

        # Extract Compare loan products
        try:
            compare_product_button = active_driver.find_element(By.XPATH, "//button[@ng-click=\"showSection('compareLoanProducts')\"]/span[contains(text(), 'Compare loan products')]")
            compare_product_button.click()

            wait.until(EC.visibility_of_element_located((By.XPATH, "//label[./em[text()='Compare loan products']]")))

            time.sleep(10)

            product_details_button = active_driver.find_element(By.XPATH, "//button[@ng-click='showProductDetails$index = !showProductDetails$index' and @aria-label='Show Fees']")
            product_details_button.click()

            time.sleep(10)

            compare_product = []
            blocks = active_driver.find_elements(By.XPATH, "//st-block[@ng-repeat='compare in $ctrl.compareProducts']")

            for block in blocks:
                try:
                    compare_product_data = {
                        "lender": get_element_text(block, ".//span[@class='truncate ng-binding']"),
                        "product_details": {
                            "product_name": get_element_text(block, ".//span[@ng-bind='productSplit.productName']"),
                            "loan_amount": clean_currency(get_element_text(block, ".//span[@ng-bind='productSplit.totalLoanAmount.formatWithCurrency($ctrl.currentCurrency)']")),
                            "total_loan_amount": clean_currency(get_element_text(block, ".//span[@ng-bind='$ctrl.getTotalLoanAmountWithLmi({ id: compare.id }).formatWithCurrency($ctrl.currentCurrency)']")),
                            "loan_term": get_element_text(block, ".//span[contains(@ng-bind, 'productSplit.loanTerm')]"),
                            "interest_rate": get_element_text(block, ".//span[@ng-bind='productSplit.interestRate.toFixed(2) + \"%\"']"),
                            "revert_rate": get_element_text(block, ".//span[@ng-bind='productSplit.revertRate.toFixed(2) + \"%\"']"),
                            "comparison_rate": get_element_text(block, ".//span[@ng-bind='productSplit.comparisonRate.toFixed(2) + \"%\"']"),
                            "abs_lending_purpose_code": get_element_text(block, ".//span[@ng-bind='productSplit.absLendingPurposeCode.id || \"N/A\"']"),
                            "repayment": clean_currency(get_element_text(block, ".//span[@ng-bind='productSplit.repayment1.formatWithCurrency($ctrl.currentCurrency)']"))
                        },
                        "monthly_cost": {
                            "initial_monthly_repayment": clean_currency(get_element_text(block, ".//span[@ng-bind='compare.repayments.initialMonthlyRepayment.formatWithCurrency($ctrl.currentCurrency)']")),
                            "ongoing_monthly_repayment": clean_currency(get_element_text(block, ".//span[@ng-bind='compare.repayments.ongoingMonthlyRepayment.formatWithCurrency($ctrl.currentCurrency)']")),
                            "upfront_fees": clean_currency(get_element_text(block, ".//span[@ng-bind='compare.repayments.upfrontFees.formatWithCurrency($ctrl.currentCurrency)']")),
                            "monthly_fees": clean_currency(get_element_text(block, ".//span[@ng-bind='compare.repayments.monthlyFees.formatWithCurrency($ctrl.currentCurrency)']")),
                            "annual_fees": clean_currency(get_element_text(block, ".//span[@ng-bind='compare.repayments.annualFees.formatWithCurrency($ctrl.currentCurrency)']"))
                        },
                        "servicing": {
                            "maximum_borrowing": clean_currency(get_element_text(block, ".//span[@ng-bind='compare.productSplits[0].maximumBorrowing ? compare.productSplits[0].maximumBorrowing.formatWithCurrency($ctrl.currentCurrency) : (0).formatWithCurrency($ctrl.currentCurrency)']"))
                        },
                        "Total_cost_(short_term_3_years)": {
                            "total_costs": clean_currency(get_element_text(block, ".//span[@ng-bind='compare.shortTotalCosts ? compare.shortTotalCosts.formatWithCurrency($ctrl.currentCurrency) : (0).formatWithCurrency($ctrl.currentCurrency)']"))
                        },
                        "Total_cost_(full_term_28_years)": {
                            "total_principal_a": clean_currency(get_element_text(block, ".//span[@ng-bind='compare.costs.principal.formatWithCurrency($ctrl.currentCurrency)']")),
                            "total_interest_b": clean_currency(get_element_text(block, ".//span[@ng-bind='compare.costs.interest.formatWithCurrency($ctrl.currentCurrency)']")),
                            "total_fees_c": clean_currency(get_element_text(block, ".//span[@ng-bind='compare.costs.fees.formatWithCurrency($ctrl.currentCurrency)']")),
                            "interest_offset_savings_d": clean_currency(get_element_text(block, ".//span[@ng-bind='compare.costs.interestOffsetSavings.formatWithCurrency($ctrl.currentCurrency)']")),
                            "total_cashback_e": clean_currency(get_element_text(block, ".//span[@ng-bind='compare.costs.cashback.formatWithCurrency($ctrl.currentCurrency)']")),
                            "total_cost": clean_currency(get_element_text(block, ".//span[@ng-bind='compare.costs.total.formatWithCurrency($ctrl.currentCurrency)']"))
                        },
                        "Total": {
                            "maximum_upfront": clean_currency(get_element_text(block, ".//span[@ng-bind='compare.commissionsPayable.upfront.formatWithCurrency($ctrl.currentCurrency)']")),
                            "maximum_monthly_trail": clean_currency(get_element_text(block, ".//span[@ng-bind='compare.commissionsPayable.trail.formatWithCurrency($ctrl.currentCurrency)']"))
                        }
                    }

                    compare_product.append(compare_product_data)

                except Exception as e:
                    logger.error(f"Error extracting data for block: {str(e)}")

        except Exception as e:
            logger.error(f"Error extracting loan data: {str(e)}")
            compare_product = []

        # Extract Compliance comments
        try:
            compliance_button = active_driver.find_element(By.XPATH, "//button[contains(., 'Compliance comments and documents')]")
            compliance_button.click()

            wait.until(EC.visibility_of_element_located((By.XPATH, "//label[./em[text()='Compliance comments and documents']]")))

            compliance = []
            blocks = active_driver.find_elements(By.XPATH, "//st-block[@ng-if=\"$ctrl.isReady && $ctrl.compliance\"]")
            for block in blocks:
                try:
                    monthly_financial_position_data = {
                        "net_income": {
                            "current_position": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.netIncome.currentPosition']"),
                            "proposed_position": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.netIncome.proposedPosition']"),
                            "proposed_position_buffer": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.netIncome.proposedPositionAtBufferRate']"),
                        },
                        "less_total_current_repayment": {
                            "current_position": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.lessTotalCurrentRepayment.currentPosition']"),
                            "proposed_position": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.lessTotalCurrentRepayment.proposedPosition']"),
                            "proposed_position_buffer": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.lessTotalCurrentRepayment.proposedPositionAtBufferRate']"),
                        },
                        "less_total_proposed_repayment": {
                            "current_position": get_input_value(block, "//md-input-container[label[text()='Current position']]/input"),
                            "proposed_position": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.lessTotalProposedRepayment.proposedPosition']"),
                            "proposed_position_buffer": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.lessTotalProposedRepayment.proposedPositionAtBufferRate']"),
                        },
                        "less_total_current_expenses": {
                            "current_position": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.lessTotalCurrentExpenses.currentPosition']"),
                            "proposed_position": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.lessTotalCurrentExpenses.proposedPosition']"),
                            "proposed_position_buffer": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.lessTotalCurrentExpenses.proposedPositionAtBufferRate']"),
                        },
                        "add_debt_commitments_ceasing": {
                            "current_position": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.foreseeableFinancialChanges.debtCommitmentsCeasing.currentPosition']"),
                            "proposed_position": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.foreseeableFinancialChanges.debtCommitmentsCeasing.proposedPosition']"),
                            "proposed_position_buffer": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.foreseeableFinancialChanges.debtCommitmentsCeasing.proposedPositionAtBufferRate']"),
                        },
                        "add_income_increasing": {
                            "current_position": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.foreseeableFinancialChanges.debtCommitmentsCeasing.currentPosition']"),
                            "proposed_position": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.foreseeableFinancialChanges.debtCommitmentsCeasing.proposedPosition']"),
                            "proposed_position_buffer": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.foreseeableFinancialChanges.debtCommitmentsCeasing.proposedPositionAtBufferRate']"),
                        },
                        "add_expense_decreasing": {
                            "current_position": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.foreseeableFinancialChanges.expenseDecreasing.currentPosition']"),
                            "proposed_position": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.foreseeableFinancialChanges.expenseDecreasing.proposedPosition']"),
                            "proposed_position_buffer": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.foreseeableFinancialChanges.expenseDecreasing.proposedPositionAtBufferRate']"),
                        },
                        "new_debt_commitments": {
                            "current_position": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.foreseeableFinancialChanges.newDebtCommitments.currentPosition']"),
                            "proposed_position": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.foreseeableFinancialChanges.newDebtCommitments.proposedPosition']"),
                            "proposed_position_buffer": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.foreseeableFinancialChanges.newDebtCommitments.proposedPositionAtBufferRate']"),
                        },
                        "income_decreasing": {
                            "current_position": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.foreseeableFinancialChanges.incomeDecreasing.currentPosition']"),
                            "proposed_position": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.foreseeableFinancialChanges.incomeDecreasing.proposedPosition']"),
                            "proposed_position_buffer": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.foreseeableFinancialChanges.incomeDecreasing.proposedPositionAtBufferRate']"),
                        },
                        "expense_increasing": {
                            "current_position": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.foreseeableFinancialChanges.expenseIncreasing.currentPosition']"),
                            "proposed_position": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.foreseeableFinancialChanges.expenseIncreasing.proposedPosition']"),
                            "proposed_position_buffer": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.foreseeableFinancialChanges.expenseIncreasing.proposedPositionAtBufferRate']"),
                        },
                        "surplus_deficit": {
                            "current_position": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.surplusDeficit.currentPosition']"),
                            "proposed_position": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.surplusDeficit.proposedPosition']"),
                            "proposed_position_buffer": get_input_value(block, "//input[@ng-model='$ctrl.compliance.monthlyFinancialPosition.surplusDeficit.proposedPositionAtBufferRate']"),
                        }
                    }
                    compliance.append(monthly_financial_position_data)
                except Exception as e:
                    logger.error(f"Error extracting data for block: {str(e)}")

        except Exception as e:
            logger.error(f"Error extracting loan data: {str(e)}")
            compliance = []

        logger.info(f"Extracted funding data: {product_requirements}")

        fact_find_data = {
            "Personal Data": personal_data,
            "Income": income,
            "Expenses": expense,
            "Assets": assets,
            "Liabilities": liabilities,
            "Needs": needs,
            "Product Requirements": product_requirements,
            "Security": security,
            "Funding": funding,
            "Search Loan": loan,
            "Review Loan Product": loan_product,
            "Compare Loan Product": compare_product,
            "Compliance": compliance
        }

        logger.info("Successfully extracted fact find data")

        return fact_find_data

    except Exception as e:
        logger.error(f"Error during extraction: {str(e)}")
        return {
            "Personal Data": [],
            "Income": [],
            "Expenses": [],
            "Assets": [],
            "Liabilities": [],
            "Needs": [],
            "Product Requirements": [],
            "Security": [],
            "Funding": [],
            "Search Loan": [],
            "Review Loan Product": [],
            "Compare Loan Product": [],
            "Compliance": []
        }