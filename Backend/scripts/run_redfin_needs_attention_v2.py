"""Script to process ALL Redfin 'Needs Attention' leads - V2 Simplified"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

# Force headless OFF for debugging
os.environ["SELENIUM_HEADLESS"] = "false"

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

print("=" * 60)
print("REDFIN NEEDS ATTENTION - BULK UPDATE V2")
print("=" * 60)

from app.referral_scrapers.redfin.redfin_service import RedfinService
from app.models.lead import Lead

# Create a dummy lead for initialization
dummy_lead = Lead()
dummy_lead.first_name = "Test"
dummy_lead.last_name = "User"

# Initialize service
service = RedfinService(
    lead=dummy_lead,
    status="Communicating",
    organization_id="cfde8fec-3b87-4558-b20f-5fe25fdcf149",
    min_sync_interval_hours=0
)

print("\n[STEP 1] Logging in via Google OAuth...")

try:
    if not service.login2():
        print("[FAILED] Login failed!")
        sys.exit(1)

    print("[OK] Login successful!")
    service.is_logged_in = True

    # Navigate to Needs Attention filter
    print("\n[STEP 2] Navigating to Needs Attention leads...")
    needs_attention_url = "https://www.redfin.com/tools/partnerCustomers?agentId=59062&settings=%7B%22queryId%22%3A%22needsAttention%22%7D"
    service.driver_service.get_page(needs_attention_url)
    time.sleep(5)

    results = {'successful': 0, 'failed': 0}
    max_leads = 150  # Safety limit

    print("\n[STEP 3] Processing leads...")

    for i in range(max_leads):
        # Find all edit status buttons
        edit_buttons = service.driver_service.find_elements(By.CSS_SELECTOR, ".edit-status-button")

        if not edit_buttons:
            print(f"\n[DONE] No more edit buttons found after processing {results['successful']} leads")
            break

        print(f"\n[{i+1}] Found {len(edit_buttons)} edit buttons, clicking first one...")

        try:
            button = edit_buttons[0]

            # Scroll into view and click
            service.driver_service.scroll_into_view(button)
            time.sleep(1)

            try:
                button.click()
            except:
                service.driver_service.safe_click(button)

            time.sleep(2)

            # Wait for the status form to appear
            try:
                WebDriverWait(service.driver_service.driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "UpdateStatusForm"))
                )

                # Find all status options
                status_options = service.driver_service.find_elements(By.CLASS_NAME, "ItemPicker__option")

                # Look for "Communicating" or any active status
                clicked_status = False
                for option in status_options:
                    try:
                        pill = option.find_element(By.CLASS_NAME, "Pill")
                        pill_text = pill.text.strip()
                        if pill_text in ["Communicating", "Showing", "Active"]:
                            option.click()
                            print(f"  Selected status: {pill_text}")
                            clicked_status = True
                            time.sleep(1)
                            break
                    except:
                        continue

                if not clicked_status:
                    # Just click the first non-empty option
                    for option in status_options:
                        try:
                            pill = option.find_element(By.CLASS_NAME, "Pill")
                            if pill.text.strip():
                                option.click()
                                print(f"  Selected status: {pill.text.strip()}")
                                break
                        except:
                            continue

                # Click Save button
                save_button = service.driver_service.find_element(
                    By.XPATH,
                    "//button[.//span[text()='Save']]"
                )
                if save_button:
                    save_button.click()
                    results['successful'] += 1
                    print(f"  [SUCCESS] Lead #{i+1} updated (Total: {results['successful']})")
                    time.sleep(2)
                else:
                    print("  [FAILED] Could not find Save button")
                    results['failed'] += 1

            except TimeoutException:
                print("  [FAILED] Timeout waiting for status form")
                results['failed'] += 1
                # Try to close any modal
                try:
                    service.driver_service.driver.find_element(By.TAG_NAME, "body").send_keys('\x1b')  # ESC
                except:
                    pass

        except Exception as e:
            print(f"  [ERROR] {str(e)[:100]}")
            results['failed'] += 1
            # Refresh page to recover
            service.driver_service.get_page(needs_attention_url)
            time.sleep(3)

        # Progress update every 10 leads
        if results['successful'] > 0 and results['successful'] % 10 == 0:
            print(f"\n=== PROGRESS: {results['successful']} successful, {results['failed']} failed ===\n")

except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()

finally:
    # Close browser
    try:
        service.driver_service.close()
    except:
        pass

print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)
print(f"Successful: {results['successful']}")
print(f"Failed: {results['failed']}")
print("=" * 60)
