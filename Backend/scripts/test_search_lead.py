"""
Simple test to search for a lead on MyAgentFinder
Opens visible browser so you can watch what happens
"""
import os
import sys
import time

# Force visible browser
os.environ["SELENIUM_HEADLESS"] = "false"

# Add Backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.referral_scrapers.utils.driver_service import DriverService
from app.referral_scrapers.utils.web_interaction_simulator import WebInteractionSimulator
from selenium.webdriver.common.by import By

EMAIL = os.getenv("MY_AGENT_FINDER_EMAIL")
PASSWORD = os.getenv("MY_AGENT_FINDER_PASSWORD")
LOGIN_URL = "https://app.myagentfinder.com/login"
REFERRALS_URL = "https://app.myagentfinder.com/referral/active/allactive"

# Lead to search for - change this to test different leads
LEAD_NAME = "Victor Medina"

def main():
    print("="*60)
    print(f"Testing MyAgentFinder Search for: {LEAD_NAME}")
    print("="*60)

    driver = DriverService()
    wis = WebInteractionSimulator()

    try:
        print("\n[1] Initializing browser (should be visible)...")
        driver.initialize_driver()

        print(f"\n[2] Navigating to login: {LOGIN_URL}")
        driver.get_page(LOGIN_URL)
        time.sleep(3)

        print("\n[3] Entering credentials...")
        email_field = driver.find_element(By.CSS_SELECTOR, 'input[type="email"]')
        password_field = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')

        if email_field and password_field:
            wis.simulated_typing(email_field, EMAIL)
            time.sleep(1)
            wis.simulated_typing(password_field, PASSWORD)
            time.sleep(1)

            # Find and click login button
            buttons = driver.driver.find_elements(By.TAG_NAME, 'button')
            for btn in buttons:
                if btn.is_displayed():
                    driver.driver.execute_script("arguments[0].click();", btn)
                    print("    Clicked login button")
                    break

        print("\n[4] Waiting for login to complete...")
        time.sleep(6)

        current_url = driver.get_current_url()
        print(f"    Current URL: {current_url}")

        print(f"\n[5] Navigating to All Active: {REFERRALS_URL}")
        driver.get_page(REFERRALS_URL)
        time.sleep(4)

        print(f"\n[6] Looking for search box...")
        search_selectors = [
            'input[type="search"]',
            'input[placeholder*="search" i]',
            'input[name="search"]',
        ]

        search_box = None
        for selector in search_selectors:
            try:
                search_box = driver.find_element(By.CSS_SELECTOR, selector)
                if search_box:
                    print(f"    Found search box: {selector}")
                    break
            except:
                continue

        if search_box:
            # Only search by first name - MAF search breaks with spaces
            search_term = LEAD_NAME.split()[0] if ' ' in LEAD_NAME else LEAD_NAME
            print(f"\n[7] Searching for '{search_term}' (first name only - MAF bug with spaces)...")
            search_box.clear()
            wis.simulated_typing(search_box, search_term)
            time.sleep(3)

            # Take screenshot after search
            driver.driver.save_screenshot("maf_search_result.png")
            print("    Screenshot saved: maf_search_result.png")

            # Look for the lead in results
            print("\n[8] Looking for lead in results...")
            page_text = driver.driver.find_element(By.TAG_NAME, 'body').text

            if LEAD_NAME.lower() in page_text.lower():
                print(f"    SUCCESS: Found '{LEAD_NAME}' on page!")

                # Try to find and click on the lead
                rows = driver.driver.find_elements(By.CSS_SELECTOR, 'tr, [role="row"]')
                for row in rows:
                    if LEAD_NAME.lower() in row.text.lower():
                        print(f"    Found lead in row, clicking...")
                        links = row.find_elements(By.TAG_NAME, 'a')
                        if links:
                            driver.driver.execute_script("arguments[0].click();", links[0])
                            print("    Clicked on lead!")
                            time.sleep(3)
                        break
            else:
                print(f"    NOT FOUND: '{LEAD_NAME}' not visible on page")
                print(f"    Page text preview: {page_text[:500]}")
        else:
            print("    ERROR: Could not find search box!")

        print("\n" + "="*60)
        print("Browser will stay open for 60 seconds - explore manually!")
        print("="*60)
        time.sleep(60)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        time.sleep(30)

    finally:
        print("\nClosing browser...")
        driver.close()

if __name__ == "__main__":
    main()
