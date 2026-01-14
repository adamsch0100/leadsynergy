import time
import random
from datetime import datetime, timedelta
from selenium import webdriver
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
import traceback
from app.referral_scrapers.utils.driver_service import DriverService
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementNotInteractableException,
)
from app.referral_scrapers.utils.web_interaction_simulator import (
    WebInteractionSimulator as wis,
)
from app.utils.constants import Credentials
from dotenv import load_dotenv

# Services and Utils
load_dotenv()
driver = DriverService()
driver.initialize_driver()
wis = wis()
CREDS = Credentials()
EMAIL = os.getenv("REFERRAL_EXCHANGE_EMAIL")
PASSWORD = os.getenv("REFERRAL_EXCHANGE_PASSWORD")


# Links
LOGIN_URL = "https://www.referralexchange.com/login/password"

# Other shit
status_mapping = {
    "No interaction yet": {"I am still trying to contact": "82"},
    "We are in contact": {
        "I have an appointment with": "83",
        "is open to working with me": "116",
        "does not want to work with me": "117",
    },
    "Listing / showing properties": {
        "I am also helping to sell": "132",
        "I am showing properties": "84",
    },
    "Transaction in progress": {
        "We are in escrow": "86",
        "We have closed escrow": "87",
    },
    "No longer working this referral": {
        "is no longer my client": "88",
        "is unresponsive": "89",
        "has another agent": "90",
        "I have prior relationship with": "107",
        "Other": "99",
    },
}


def main():
    print(f"EMAIL: {EMAIL}")
    print(f"PASSWORD: {PASSWORD}")
    try:
        lead_name = "Hannah Taylor"
        driver.get_page(LOGIN_URL)
        wis.human_delay(3, 5)
        email_field = driver.find_element(By.ID, "email")
        wis.human_delay(2, 4)
        wis.simulated_typing(email_field, CREDS.REFERRAL_EXCHANGE_EMAIL)

        password_field = driver.find_element(By.ID, "password")
        wis.human_delay(2, 4)
        print("I am handsome")
        wis.simulated_typing(password_field, CREDS.REFERRAL_EXCHANGE_PASSWORD)

        login_button = driver.find_element(By.ID, "submit")
        driver.safe_click(login_button)
        wis.human_delay(3, 5)

        search_field = driver.find_element(By.ID, "maching-search")
        wis.human_delay(2, 4)
        wis.simulated_typing(search_field, f"{lead_name}")
        search_field.send_keys(Keys.ENTER)
        wis.human_delay(2, 4)

        driver.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".leads-row"))
        )

        # Find lead's link and click it
        lead_link = driver.wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    f"//span[text()='{lead_name}' or contains(text(), 'Hannah Taylor')]/ancestor::a",
                )
            )
        )
        driver.safe_click(lead_link)
        wis.human_delay(2, 3)

        # Status
        status_button = driver.find_element(By.ID, "cta-status")
        status_button.click()
        wis.human_delay(1, 3)

        # Update
        try:
            driver.wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, f"//h1[contains(text(), 'Update Status')]")
                )
            )
            print("Found status update modal with header")
        except TimeoutException:
            print("Could not find modal by header, looking for other elements...")
            driver.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, ".action-options, .options-reason")
                )
            )
            print("Found status options container")
            
        try:
            try:
                status_option = driver.wait.until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            "//button[contains(@class, 'action-option-reason')]/span[text()='We are in contact']",
                        )
                    )
                )
                print("Found status option by specific class and text")
            except TimeoutException:
                try:
                    status_option = driver.wait.until(
                        EC.element_to_be_clickable(
                            (
                                By.XPATH,
                                "//span[text()='We are in contact']/parent::button",
                            )
                        )
                    )
                    print("Found status option by text and parent")
                except TimeoutException:
                    try:
                        status_option = driver.wait.until(
                            EC.element_to_be_clickable(
                                (By.XPATH, "//*[contains(text(), 'We are in contact')]")
                            )
                        )
                        print("Found status option by partial text match")
                    except TimeoutException:
                        # List all available options
                        options = driver.find_elements(
                            By.CSS_SELECTOR,
                            ".action-options button, .options-reason button",
                        )
                        print(f"Found {len(options)} total status options")
                        for i, option in enumerate(options):
                            try:
                                text = option.text.strip()
                                print(f"Option {i + 1}: '{text}'")
                                if "in contact" in text.lower():
                                    status_option = option
                                    print(f"Selected option: {i + 1}: '{text}'")
                                    break
                            except:
                                continue

                # Click JS
                driver.execute_script("arguments[0].click();", status_option)
                print("Clicked 'We are in contact' using JS")

        except Exception as e:
            print(f"Error selecting status option: {e}")
            print(traceback.format_exc())
        status_option.click()

        wis.human_delay(1, 2)

        ####################### Option choice: From DB #######################
        status_to_select = "We are in contact"
        sub_option_value = "83"
        try:
            print(f"Looking for radio button with value: {sub_option_value}")
            radio_button = driver.wait.until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        f"//button[@type='button' and contains(text(), 'I have an appointment with')]",
                    )
                )
            )

            # Try to click it with JavaScript first
            try:
                driver.execute_script("arguments[0].click();", radio_button)
                print(
                    f"Clicked radio button with value {sub_option_value} using JavaScript"
                )
            except Exception as js_error:
                print(f"JavaScript click failed: {js_error}")
                # Try regular click
                radio_button.click()
                print(
                    f"Clicked radio button with value {sub_option_value} using regular click"
                )
        except Exception as e:
            print(f"No sub-options found or could not select: {e}")
        wis.human_delay(2, 3)

        # Click update button
        driver.find_element(By.XPATH, "//button[text()='Update']").click()
        input("Press enter to quit")
    except Exception as e:
        print(f"There is an error: {e}  ")



if __name__ == "__main__":
    main()
