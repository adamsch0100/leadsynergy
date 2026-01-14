import time
import random
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def human_delay(min_time=1, max_time=3):
    """Pause for a random time between actions."""
    time.sleep(random.uniform(min_time, max_time))

def simulated_typing(element, text):
    """Simulate typing by sending one character at a time."""
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.1, 0.3))  # Simulate typing speed

def update_redfin_customers():
    # Redfin login credentials
    REDFIN_EMAIL = "adam@saahomes.com"
    REDFIN_PASSWORD = "Vitzer0100!"

    # Set up Selenium WebDriver
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Run headless for automation
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(options=options)

    try:
        print("Navigating to Redfin login page...")
        driver.get("https://www.redfin.com/tools/new/login")
        human_delay(2, 5)  # Random delay before starting login process

        print(f"Current URL: {driver.current_url}")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="login_email"]')))

        # Fill in login form
        email_field = driver.find_element(By.CSS_SELECTOR, 'input[name="login_email"]')
        password_field = driver.find_element(By.CSS_SELECTOR, 'input[name="login_password"]')
        login_button = driver.find_element(By.CSS_SELECTOR, 'button[data-rf-test-name="login_submit"]')

        print("Typing email...")
        simulated_typing(email_field, REDFIN_EMAIL)
        human_delay(1, 2)  # Random delay between typing actions

        print("Typing password...")
        simulated_typing(password_field, REDFIN_PASSWORD)
        human_delay(1, 2)

        print("Submitting login form...")
        login_button.click()
        human_delay(3, 5)

        # Wait for customers to load directly
        print("Waiting for customer elements to load...")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".edit-status-button")))
        edit_buttons = driver.find_elements(By.CSS_SELECTOR, ".edit-status-button")
        print(f"Found {len(edit_buttons)} customers to process.")

        # Process each customer
        for index, edit_button in enumerate(edit_buttons):
            try:
                print(f"Processing customer {index + 1}/{len(edit_buttons)}...")

                # Scroll element into view and wait for it to be clickable
                driver.execute_script("arguments[0].scrollIntoView(true);", edit_button)
                human_delay(2, 4)  # Wait for scroll to complete

                # Try to ensure the element is clickable
                WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".edit-status-button"))
                )

                # Try JavaScript click if regular click fails
                try:
                    edit_button.click()
                except:
                    driver.execute_script("arguments[0].click();", edit_button)

                human_delay(2, 4)  # Wait for the pop-up to appear

                # Locate and click the Save button
                save_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//span[text()='Save']"))
                )

                try:
                    save_button.click()
                except:
                    driver.execute_script("arguments[0].click();", save_button)

                human_delay(3, 5)  # Random delay after saving
                print(f"Customer {index + 1} updated successfully.")

            except Exception as e:
                print(f"Error processing customer {index + 1}: {e}")
                continue

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        driver.quit()
        print("Script completed.")

def calculate_next_run_time(min_delay_hours=72, max_delay_hours=220):
    """Calculate the next run time with a random delay."""
    now = datetime.now()
    random_delay = random.randint(min_delay_hours, max_delay_hours)
    next_run_time = now + timedelta(hours=random_delay)
    return next_run_time

if __name__ == "__main__":
    print("Running initial update...")
    update_redfin_customers()
    print("Initial update completed. Starting scheduled runs...")

    while True:
        next_run_time = calculate_next_run_time(min_delay_hours=6, max_delay_hours=24)
        print(f"Next run scheduled at: {next_run_time}")
        while datetime.now() < next_run_time:
            time.sleep(60)  # Check every minute
        print("Executing scheduled task...")
        update_redfin_customers()
        print("Task completed.")