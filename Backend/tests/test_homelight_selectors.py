import json
import time
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from app.service.lead_service import LeadServiceSingleton
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
from app.referral_scrapers.homelight.homelight_service import HomelightService
from selenium.webdriver.common.by import By

lead_service = LeadServiceSingleton.get_instance()
settings_service = LeadSourceSettingsSingleton.get_instance()
settings = settings_service.get_by_source_name('HomeLight')

if not settings:
    print('ERROR: No HomeLight lead source configuration found.')
    raise SystemExit(1)

if not getattr(settings, 'is_active', True):
    print('ERROR: HomeLight lead source is not active.')
    raise SystemExit(1)

# Get just one lead to test
leads = lead_service.get_by_source('HomeLight', limit=1, offset=0)
if not leads:
    print('No leads found to test')
    raise SystemExit(1)

lead = leads[0]
print(f"Testing with lead: {lead.full_name}")

# Create service instance
service = HomelightService(
    lead=lead,
    status='Connected',
    organization_id=getattr(lead, 'organization_id', None)
)

try:
    # Login
    if service.login():
        print("Logged in successfully")

        # Find and click customer
        customer_found = service.find_and_click_customer_by_name(lead.full_name)
        if customer_found:
            print("Customer found and clicked")

            # Now let's inspect the page to see what elements are available
            print("\nInspecting stage dropdown...")

            # Found the correct stage dropdown selector
            stage_dropdown = service.driver_service.driver.find_element(By.CSS_SELECTOR, '[data-test="referralDetailsModal-stageUpdateOptions"]')
            print(f"Stage dropdown found: tag={stage_dropdown.tag_name}, text='{stage_dropdown.text}'")
            print(f"Attributes: {stage_dropdown.get_attribute('outerHTML')[:300]}...")

            # Click the dropdown to see options
            print("\nClicking stage dropdown...")
            stage_dropdown.click()
            service.wis.human_delay(2, 3)

            # Look for dropdown options
            print("\nLooking for dropdown options...")
            option_selectors = [
                "[role='option']",
                "[data-test*='option']",
                "li",
                ".option",
                "[data-value]"
            ]

            for selector in option_selectors:
                try:
                    elements = service.driver_service.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        print(f"Found {len(elements)} option elements with selector: {selector}")
                        for i, elem in enumerate(elements[:5]):  # Show first 5
                            print(f"  Option {i}: tag={elem.tag_name}, text='{elem.text}', attrs={elem.get_attribute('outerHTML')[:150]}...")
                except Exception as e:
                    print(f"Error with option selector {selector}: {e}")

            # Look for "Connected" option specifically
            try:
                connected_option = service.driver_service.driver.find_element(By.XPATH, "//*[contains(text(), 'Connected')]")
                print(f"\nFound 'Connected' option: {connected_option.get_attribute('outerHTML')[:200]}...")
            except Exception as e:
                print(f"Could not find 'Connected' option: {e}")

            # Now look for update/save buttons
            print("\nLooking for Update/Save buttons...")
            update_selectors = [
                "button",
                "[data-test*='update']",
                "[data-test*='save']",
                "button[type='submit']",
                ".update-button",
                ".save-button"
            ]

            for selector in update_selectors:
                try:
                    elements = service.driver_service.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        print(f"Found {len(elements)} button elements with selector: {selector}")
                        for i, elem in enumerate(elements):
                            if elem.is_displayed() and elem.text:
                                print(f"  Button {i}: text='{elem.text}', enabled={elem.is_enabled()}, attrs={elem.get_attribute('outerHTML')[:150]}...")
                except Exception as e:
                    print(f"Error with button selector {selector}: {e}")

            # Look for any text containing "Update" or "Save"
            try:
                update_elements = service.driver_service.driver.find_elements(By.XPATH, "//*[contains(text(), 'Update') or contains(text(), 'Save')]")
                print(f"\nFound {len(update_elements)} elements containing 'Update' or 'Save':")
                for i, elem in enumerate(update_elements):
                    print(f"  Element {i}: tag={elem.tag_name}, text='{elem.text}', enabled={elem.is_enabled() if hasattr(elem, 'is_enabled') else 'N/A'}")
            except Exception as e:
                print(f"Error looking for Update/Save text: {e}")

        else:
            print("Customer not found")

    else:
        print("Login failed")

finally:
    try:
        service.driver_service.close()
    except:
        pass
