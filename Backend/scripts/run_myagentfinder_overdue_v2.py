"""
Script to process ALL MyAgentFinder overdue leads with proper date setting.
This version properly handles the table-based overdue list and sets nurture dates 6 months out.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
load_dotenv()

# Force headless OFF for debugging
os.environ["SELENIUM_HEADLESS"] = "false"

import json
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

print("=" * 60)
print("MYAGENTFINDER OVERDUE LEADS - TABLE-BASED SWEEP V2")
print("=" * 60)

from app.referral_scrapers.my_agent_finder.my_agent_finder_service import (
    MyAgentFinderService,
    STATUS_CATEGORIES,
)
from app.referral_scrapers.utils.driver_service import DriverService
from app.referral_scrapers.utils.web_interaction_simulator import WebInteractionSimulator

# Configuration
NURTURE_DAYS_OFFSET = 180  # 6 months
ORGANIZATION_ID = "cfde8fec-3b87-4558-b20f-5fe25fdcf149"
OVERDUE_URL = "https://app.myagentfinder.com/referral/active/overdue"

# Initialize
driver_service = DriverService()
wis = WebInteractionSimulator()

service = MyAgentFinderService(
    lead=None,
    status=None,
    organization_id=ORGANIZATION_ID,
    driver_service=driver_service,
    min_sync_interval_hours=0,
    nurture_days_offset=NURTURE_DAYS_OFFSET
)

results = {'successful': 0, 'failed': 0, 'details': []}

def get_future_date_str(days_offset=NURTURE_DAYS_OFFSET):
    """Get date string in MM/DD/YYYY format for X days from now"""
    future_date = datetime.now() + timedelta(days=days_offset)
    return future_date.strftime("%m/%d/%Y")

def set_date_via_keyboard(driver, date_str):
    """Set date by clearing field and typing new date"""
    try:
        # Find the date input - look for inputs that might be date fields
        # MAF uses input with type="text" but displays as date
        date_inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="text"]')
        visible_inputs = [inp for inp in date_inputs if inp.is_displayed()]

        # Find the one that has a date-like value or is near "Next Status Update Date" text
        date_input = None
        for inp in visible_inputs:
            value = inp.get_attribute("value") or ""
            # Look for date-like patterns (MM/DD/YYYY or similar)
            if ('/' in value and len(value) >= 8 and len(value) <= 12) or \
               (inp.get_attribute("placeholder") or "").lower().find("date") >= 0:
                # Skip search box
                if "search" not in (inp.get_attribute("placeholder") or "").lower():
                    date_input = inp
                    print(f"  Found date input with current value: {value}")
                    break

        if not date_input:
            # Try to find by label
            labels = driver.find_elements(By.XPATH, "//*[contains(text(), 'Next Status Update')]")
            for label in labels:
                # Look for input in parent containers
                parent = label
                for _ in range(5):
                    try:
                        parent = parent.find_element(By.XPATH, "..")
                        inputs = parent.find_elements(By.TAG_NAME, "input")
                        for inp in inputs:
                            if inp.is_displayed():
                                role = inp.get_attribute("role") or ""
                                if role != "combobox":  # Skip status dropdown
                                    date_input = inp
                                    print(f"  Found date input near label")
                                    break
                        if date_input:
                            break
                    except:
                        break
                if date_input:
                    break

        if date_input:
            # Clear and set new date
            date_input.click()
            time.sleep(0.3)

            # Select all and delete
            date_input.send_keys(Keys.CONTROL + "a")
            time.sleep(0.1)
            date_input.send_keys(Keys.DELETE)
            time.sleep(0.1)

            # Type new date
            date_input.send_keys(date_str)
            time.sleep(0.3)

            # Press Tab to commit
            date_input.send_keys(Keys.TAB)
            time.sleep(0.5)

            print(f"  Set date to: {date_str}")
            return True
        else:
            print("  WARNING: Could not find date input")
            return False

    except Exception as e:
        print(f"  ERROR setting date: {e}")
        return False

def click_update_button(driver):
    """Find and click the Update button"""
    try:
        # Try XPath first (handles MUI buttons with nested span)
        update_xpaths = [
            "//button[.//text()[contains(., 'Update')]]",
            "//button[contains(text(), 'Update')]",
            "//button[.//span[contains(text(), 'Update')]]",
        ]

        for xpath in update_xpaths:
            btns = driver.find_elements(By.XPATH, xpath)
            for btn in btns:
                if btn.is_displayed():
                    btn_text = btn.text.strip()
                    if 'update' in btn_text.lower():
                        driver.execute_script("arguments[0].click();", btn)
                        print(f"  Clicked Update button")
                        return True

        # Try CSS selectors
        css_selectors = [
            "button.MuiButton-containedPrimary",
            "button.MuiButton-contained",
        ]
        for sel in css_selectors:
            btns = driver.find_elements(By.CSS_SELECTOR, sel)
            for btn in btns:
                if btn.is_displayed() and 'update' in btn.text.lower():
                    driver.execute_script("arguments[0].click();", btn)
                    print(f"  Clicked Update button (CSS)")
                    return True

        print("  WARNING: Could not find Update button")
        return False

    except Exception as e:
        print(f"  ERROR clicking Update: {e}")
        return False

def process_overdue_leads():
    """Process all overdue leads from the table"""
    global results

    print("\n[STEP 1] Logging in to MyAgentFinder...")
    if not service.login():
        print("[FAILED] Login failed!")
        return
    print("[OK] Login successful")

    print(f"\n[STEP 2] Navigating to overdue page: {OVERDUE_URL}")
    driver_service.get_page(OVERDUE_URL)
    time.sleep(4)

    # Calculate target date
    target_date = get_future_date_str(NURTURE_DAYS_OFFSET)
    print(f"\n[INFO] Will set nurture dates to: {target_date} ({NURTURE_DAYS_OFFSET} days from now)")

    # Take screenshot
    driver_service.driver.save_screenshot("maf_overdue_page.png")
    print("[DEBUG] Screenshot saved: maf_overdue_page.png")

    # Get count of overdue leads first
    print("\n[STEP 3] Counting overdue leads...")
    max_leads = 50
    lead_count = 0

    while lead_count < max_leads:
        # Refresh the page to get current state (leads may have been removed from overdue)
        if lead_count > 0:
            driver_service.get_page(OVERDUE_URL)
            time.sleep(3)

        # Find all edit buttons in the table
        edit_buttons = driver_service.driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='edit' i], a[href*='/opp/'], td a, tbody tr a")

        # Also try finding rows directly
        rows = driver_service.driver.find_elements(By.CSS_SELECTOR, "tbody tr")

        if not rows or len(rows) == 0:
            # Check if page shows "No referrals found" or similar
            page_text = driver_service.driver.find_element(By.TAG_NAME, "body").text.lower()
            if "no referrals" in page_text or "no overdue" in page_text or len(rows) == 0:
                print(f"\n[DONE] No more overdue leads found! Processed {lead_count} leads total.")
                break

        # Get the first row's lead name
        try:
            first_row = rows[0]
            row_text = first_row.text.strip()
            lines = row_text.split('\n')
            lead_name = lines[0] if lines else "Unknown"

            # Skip header row
            if lead_name.lower() in ['action', 'contact info', 'details', 'location', 'status']:
                if len(rows) > 1:
                    first_row = rows[1]
                    row_text = first_row.text.strip()
                    lines = row_text.split('\n')
                    lead_name = lines[0] if lines else "Unknown"
                else:
                    print("\n[DONE] Only header row found - no overdue leads!")
                    break

            print(f"\n{'='*60}")
            print(f"LEAD {lead_count + 1}: {lead_name}")
            print(f"{'='*60}")

            # Find clickable element in this row (edit button or name link)
            clickable = None

            # Try to find edit button (pencil icon) in row
            try:
                edit_btn = first_row.find_element(By.CSS_SELECTOR, "button, svg, [class*='edit']")
                if edit_btn:
                    clickable = edit_btn
                    print(f"  Found edit button")
            except:
                pass

            # Try to find link in row
            if not clickable:
                try:
                    links = first_row.find_elements(By.TAG_NAME, "a")
                    for link in links:
                        href = link.get_attribute("href") or ""
                        if "/opp/" in href:
                            clickable = link
                            print(f"  Found link: {href}")
                            break
                except:
                    pass

            # Fall back to clicking the row itself
            if not clickable:
                clickable = first_row
                print(f"  Will click on row directly")

            # Click to open lead detail page
            try:
                # Try direct click first
                if hasattr(clickable, 'click'):
                    clickable.click()
                else:
                    driver_service.driver.execute_script("arguments[0].click();", clickable)
            except Exception as click_err:
                print(f"  Click error: {click_err}")
                # Try to find and click the first link in the row
                try:
                    first_link = first_row.find_element(By.TAG_NAME, "a")
                    first_link.click()
                except:
                    try:
                        first_row.click()
                    except:
                        print(f"  WARNING: Could not click on row")

            time.sleep(3)

            # Take screenshot of detail page
            driver_service.driver.save_screenshot(f"maf_lead_{lead_count+1}.png")

            # Check current URL - should be on detail page now
            current_url = driver_service.driver.get_current_url()
            print(f"  Current URL: {current_url}")

            if "/opp/" not in current_url:
                print(f"  WARNING: May not have navigated to detail page")
                # Try clicking on name text directly
                try:
                    name_elem = driver_service.driver.find_element(By.XPATH, f"//*[contains(text(), '{lead_name.split()[0]}')]")
                    name_elem.click()
                    time.sleep(3)
                except:
                    pass

            # Now we should be on the detail page - look for status dropdown and date input
            # Scroll down to the "Keep Us Informed" section
            try:
                keep_informed = driver_service.driver.find_element(By.XPATH, "//*[contains(text(), 'Keep Us Informed')]")
                driver_service.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", keep_informed)
                time.sleep(1)
            except:
                # Scroll down by 300px
                driver_service.driver.execute_script("window.scrollBy(0, 300);")
                time.sleep(1)

            # Set the date to 6 months from now
            date_set = set_date_via_keyboard(driver_service.driver, target_date)

            # Click Update button
            update_clicked = click_update_button(driver_service.driver)

            if update_clicked:
                time.sleep(3)
                results['successful'] += 1
                results['details'].append({'name': lead_name, 'status': 'success', 'date': target_date})
                print(f"  [SUCCESS] Updated {lead_name}")
            else:
                results['failed'] += 1
                results['details'].append({'name': lead_name, 'status': 'failed', 'reason': 'Could not click Update'})
                print(f"  [FAILED] Could not update {lead_name}")

            lead_count += 1

        except Exception as e:
            print(f"  ERROR processing lead: {e}")
            results['failed'] += 1
            results['details'].append({'name': 'Unknown', 'status': 'failed', 'reason': str(e)})
            lead_count += 1
            import traceback
            traceback.print_exc()

    # Done
    service.logout()

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Successful: {results['successful']}")
    print(f"Failed: {results['failed']}")
    print("=" * 60)

    for detail in results['details']:
        status = detail.get('status', 'unknown')
        name = detail.get('name', 'Unknown')
        if status == 'success':
            print(f"  [OK] {name} -> date set to {detail.get('date', 'N/A')}")
        else:
            print(f"  [FAIL] {name}: {detail.get('reason', 'Unknown error')}")

if __name__ == "__main__":
    try:
        process_overdue_leads()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            service.logout()
        except:
            pass
