"""
Test script to debug the nurture date picker on MAF.
Opens browser visible so we can see what's happening.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# Force visible browser
os.environ["SELENIUM_HEADLESS"] = "false"

from app.referral_scrapers.my_agent_finder.my_agent_finder_service import MyAgentFinderService
from app.referral_scrapers.utils.driver_service import DriverService
from selenium.webdriver.common.by import By
from datetime import datetime, timedelta

def test_nurture_date():
    """Test the nurture date picker"""
    print("Starting test...")

    driver_service = DriverService()
    service = MyAgentFinderService(
        organization_id=None,
        driver_service=driver_service,
        nurture_days_offset=180
    )

    try:
        # Login
        print("\n[1] Logging in...")
        if not service.login():
            print("Login failed!")
            return

        print("Login successful!")
        time.sleep(2)

        # Go to active referrals
        print("\n[2] Going to active referrals...")
        driver_service.get_page("https://app.myagentfinder.com/referral/active/allactive")
        time.sleep(3)

        # Search for a nurture lead - pick one from the overdue list
        # Using "Cody Samora" as test
        test_name = "Cody Samora"
        first_name = test_name.split()[0]

        print(f"\n[3] Searching for '{first_name}'...")

        search_selectors = [
            'input[placeholder*="Search" i]',
            'input[type="search"]',
            'input[name*="search" i]',
        ]

        search_box = None
        for selector in search_selectors:
            try:
                search_box = driver_service.driver.find_element(By.CSS_SELECTOR, selector)
                if search_box:
                    print(f"Found search: {selector}")
                    break
            except:
                continue

        if search_box:
            from app.referral_scrapers.utils.web_interaction_simulator import WebInteractionSimulator
            wis = WebInteractionSimulator()
            search_box.clear()
            wis.simulated_typing(search_box, first_name)
            time.sleep(3)

        # Click on the lead NAME (link) to open detail page
        print(f"\n[4] Looking for '{test_name}' in results...")

        # The name appears as text in a table cell - find it directly
        # Look for elements containing the full name or first name
        lead_found = False

        # Try to find the name as a clickable element
        name_selectors = [
            f"//td[contains(text(), '{first_name}')]",  # td with name
            f"//a[contains(text(), '{first_name}')]",   # link with name
            f"//*[contains(text(), '{test_name}')]",    # any element with full name
        ]

        for selector in name_selectors:
            try:
                elements = driver_service.driver.find_elements(By.XPATH, selector)
                for elem in elements:
                    # Skip if it's part of the search box or header
                    if elem.tag_name in ['input', 'th']:
                        continue
                    text = elem.text.strip()
                    # Make sure we're clicking on the actual name, not something else
                    if first_name in text and len(text) < 200:  # Name cell shouldn't be too long
                        print(f"Found name element: {elem.tag_name} - '{text[:50]}...'")
                        elem.click()
                        lead_found = True
                        break
                if lead_found:
                    break
            except Exception as e:
                print(f"Selector '{selector}' failed: {e}")
                continue

        if not lead_found:
            # Fallback: find the row and click on it
            print("Trying fallback: clicking on table row...")
            rows = driver_service.driver.find_elements(By.CSS_SELECTOR, "tbody tr")
            for row in rows:
                if first_name.lower() in row.text.lower():
                    print(f"Found row with '{first_name}', clicking...")
                    # Click the row itself
                    row.click()
                    lead_found = True
                    break

        if not lead_found:
            print("Could not find lead to click!")
        else:
            print("Clicked on lead, waiting for detail page...")
            time.sleep(4)

        # Take screenshot to see the detail page
        driver_service.driver.save_screenshot("lead_detail_page.png")
        print("Screenshot saved: lead_detail_page.png")

        # Now we should be on the lead detail page with the Update Status form
        print("\n[5] Looking for page content...")
        page_text = driver_service.driver.find_element(By.TAG_NAME, "body").text
        print(f"Page contains 'Status': {'Status' in page_text}")
        print(f"Page contains 'Nurture': {'Nurture' in page_text}")
        print(f"Page contains 'Next Status Update Date': {'Next Status Update Date' in page_text}")
        print(f"Page contains 'Update': {'Update' in page_text}")

        # Look for the status dropdown
        print("\n[6] Looking for Status dropdown...")
        dropdown = None
        try:
            dropdown = driver_service.driver.find_element(By.CSS_SELECTOR, 'input.MuiAutocomplete-input[role="combobox"]')
            if dropdown:
                print("Found dropdown, clicking...")
                dropdown.click()
                time.sleep(2)

                # Look for Nurture option
                print("\n[7] Looking for Nurture option...")
                options = driver_service.driver.find_elements(By.CSS_SELECTOR, 'li[role="option"]')
                for opt in options:
                    if 'nurture' in opt.text.lower() and 'long term' in opt.text.lower():
                        print(f"Found Nurture option: {opt.text}")
                        opt.click()
                        time.sleep(2)
                        break
        except Exception as e:
            print(f"Could not find dropdown: {e}")

        # Now look for the date picker
        print("\n[7] Looking for date picker elements...")

        # Take screenshot
        driver_service.driver.save_screenshot("nurture_date_debug.png")
        print("Screenshot saved: nurture_date_debug.png")

        # Find all inputs on the page
        all_inputs = driver_service.driver.find_elements(By.TAG_NAME, "input")
        print(f"\nFound {len(all_inputs)} input elements:")
        for i, inp in enumerate(all_inputs):
            try:
                inp_type = inp.get_attribute("type")
                inp_name = inp.get_attribute("name")
                inp_id = inp.get_attribute("id")
                inp_placeholder = inp.get_attribute("placeholder")
                inp_class = inp.get_attribute("class")
                inp_value = inp.get_attribute("value")
                visible = inp.is_displayed()

                if visible:
                    print(f"\n  Input {i}:")
                    print(f"    type: {inp_type}")
                    print(f"    name: {inp_name}")
                    print(f"    id: {inp_id}")
                    print(f"    placeholder: {inp_placeholder}")
                    print(f"    class: {inp_class[:50] if inp_class else None}...")
                    print(f"    value: {inp_value}")
            except Exception as e:
                print(f"  Input {i}: Error - {e}")

        # Look for any date-related elements
        print("\n[8] Looking for date-related elements...")

        # Try different approaches to find date picker
        date_selectors = [
            'input[type="date"]',
            '[class*="date" i]',
            '[class*="Date" i]',
            '[aria-label*="date" i]',
            '[placeholder*="date" i]',
            '.MuiDatePicker-root input',
            '.MuiPickersDay-root',
        ]

        for selector in date_selectors:
            try:
                elements = driver_service.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    print(f"\n  Found {len(elements)} elements for '{selector}':")
                    for elem in elements:
                        print(f"    - {elem.tag_name}: {elem.text[:50] if elem.text else elem.get_attribute('value') or elem.get_attribute('class')[:50]}")
            except Exception as e:
                print(f"  Selector '{selector}' failed: {e}")

        # Look for labels containing "date"
        print("\n[9] Looking for date-related labels...")
        all_text = driver_service.driver.find_elements(By.XPATH, "//*[contains(text(), 'date') or contains(text(), 'Date')]")
        for elem in all_text:
            try:
                print(f"  Found text element: {elem.tag_name} - '{elem.text[:100]}'")
            except:
                pass

        print("\n\n=== PAUSING - Check browser to see date picker ===")
        print("Look for 'Next Status Update Date' field")
        print("Press Enter when ready to continue...")
        input()

        # Try to take another screenshot after user has had a chance to look
        driver_service.driver.save_screenshot("nurture_date_debug_2.png")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\nClosing browser in 5 seconds...")
        time.sleep(5)
        service.logout()

if __name__ == "__main__":
    test_nurture_date()
