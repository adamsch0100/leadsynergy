"""Script to process ALL HomeLight urgent leads directly from the platform - V2 with proper note saving"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

# Force headless OFF for debugging
os.environ["SELENIUM_HEADLESS"] = "false"

import json
import time
from app.database.supabase_client import SupabaseClientSingleton
from app.models.lead import Lead
from app.referral_scrapers.homelight.homelight_service import HomelightService
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

print("=" * 60)
print("HOMELIGHT URGENT LEADS - DIRECT PLATFORM SWEEP V2")
print("=" * 60)

supabase = SupabaseClientSingleton.get_instance()
settings_service = LeadSourceSettingsSingleton.get_instance()
source_settings = settings_service.get_by_source_name("HomeLight")

# Initialize service with a dummy lead (we'll update later)
service = HomelightService(
    lead=None,
    status=None,
    organization_id="cfde8fec-3b87-4558-b20f-5fe25fdcf149",
    min_sync_interval_hours=0
)

print("\n[STEP 1] Logging in to HomeLight...")
if not service.login_once():
    print("[FAILED] Login failed!")
    sys.exit(1)
print("[OK] Login successful")

# Navigate to urgent filter
print("\n[STEP 2] Clicking Urgent filter...")
service.wis.human_delay(2, 3)

# Look for Urgent button
try:
    urgent_buttons = service.driver_service.find_elements(
        By.XPATH,
        "//button[contains(text(), 'Urgent')] | //span[contains(text(), 'Urgent')]/parent::button | //button[contains(@class, 'urgent')]"
    )
    if urgent_buttons:
        print(f"Found {len(urgent_buttons)} urgent button candidates")
        urgent_buttons[0].click()
        time.sleep(3)
        print("[OK] Clicked Urgent filter")
except Exception as e:
    print(f"Error clicking urgent filter: {e}")

# Get all lead rows
print("\n[STEP 3] Getting urgent lead rows...")
time.sleep(2)
lead_rows = service.driver_service.find_elements(By.CSS_SELECTOR, "a[data-test='referralsList-row']")
total_leads = len(lead_rows)
print(f"Found {total_leads} urgent leads")

results = {'successful': [], 'failed': [], 'skipped': []}

for i in range(total_leads):
    # Re-get lead rows since page might have changed
    time.sleep(2)
    lead_rows = service.driver_service.find_elements(By.CSS_SELECTOR, "a[data-test='referralsList-row']")

    if i >= len(lead_rows):
        print(f"No more leads found at index {i}")
        break

    row = lead_rows[i]

    try:
        row_text = row.text.strip()
        lines = row_text.split('\n')
        lead_name = lines[0] if lines else "Unknown"
        lead_type = "seller" if "Seller" in row_text else "buyer" if "Buyer" in row_text else None
        current_stage = None
        for line in lines:
            if any(stage in line for stage in ['Connected', 'Met', 'Listing', 'Escrow', 'Voicemail', 'Meeting']):
                current_stage = line.strip()
                break

        print(f"\n{'#' * 60}")
        print(f"# LEAD {i+1}/{total_leads}: {lead_name}")
        print(f"# Type: {lead_type}")
        print(f"# Current Stage: {current_stage}")
        print(f"{'#' * 60}")

        # Click the lead to open detail
        service.driver_service.safe_click(row)
        time.sleep(3)

        success = False
        try:
            # First try to find "Add Another Note" button and click it
            add_note_btn = None
            for selector in [
                "//button[contains(text(), 'Add Another Note')]",
                "//button[contains(text(), 'Add Note')]"
            ]:
                try:
                    add_note_btn = service.driver_service.find_element(By.XPATH, selector)
                    if add_note_btn:
                        print(f"Found: {add_note_btn.text}")
                        break
                except:
                    continue

            if add_note_btn:
                print("Clicking Add Note button to open note form...")
                service.driver_service.safe_click(add_note_btn)
                time.sleep(2)

                # Find the note textarea
                textarea = None
                for selector in [
                    "textarea[data-test='referral-add-note-textarea']",
                    "textarea[placeholder*='Add an optional note']",
                    "textarea[placeholder*='note']"
                ]:
                    try:
                        textarea = service.driver_service.find_element(By.CSS_SELECTOR, selector)
                        if textarea:
                            break
                    except:
                        continue

                if textarea:
                    note = f"Continuing to work with {lead_name}. Updated {datetime.now().strftime('%m/%d/%Y')}."
                    textarea.clear()
                    textarea.send_keys(note)
                    print(f"Entered note: {note}")
                    time.sleep(1)

                    # Now click "Add Another Note" button AGAIN to save
                    print("Looking for button to save the note...")
                    save_btn = None
                    for selector in [
                        "//button[contains(text(), 'Add Another Note')]",
                        "//button[contains(text(), 'Add Note')]",
                        "//button[contains(text(), 'Add note')]",
                        "button[data-test='referral-add-note-btn']"
                    ]:
                        try:
                            if selector.startswith("//"):
                                save_btn = service.driver_service.find_element(By.XPATH, selector)
                            else:
                                save_btn = service.driver_service.find_element(By.CSS_SELECTOR, selector)
                            if save_btn:
                                print(f"Found save button: {save_btn.text if hasattr(save_btn, 'text') else selector}")
                                break
                        except:
                            continue

                    if save_btn:
                        print("Clicking to save note...")
                        service.driver_service.safe_click(save_btn)
                        time.sleep(2)
                        results['successful'].append({'name': lead_name})
                        success = True
                        print(f"[SUCCESS] Note saved for {lead_name}")
                    else:
                        print("Could not find save button")
                        results['failed'].append({'name': lead_name, 'reason': 'No save button'})
                else:
                    print("Could not find note textarea")
                    results['skipped'].append({'name': lead_name, 'reason': 'No textarea found'})
            else:
                print("Could not find Add Note button")
                results['skipped'].append({'name': lead_name, 'reason': 'No Add Note button'})

        except Exception as e:
            print(f"Error updating lead: {e}")
            results['failed'].append({'name': lead_name, 'reason': str(e)})

        # Click Done to close the modal
        try:
            done_btn = service.driver_service.find_element(By.XPATH, "//button[contains(text(), 'Done')]")
            if done_btn:
                done_btn.click()
                print("Clicked Done")
                time.sleep(2)
        except Exception as e:
            print(f"Could not click Done: {e}")
            # Try pressing Escape to close
            try:
                from selenium.webdriver.common.keys import Keys
                service.driver_service.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                time.sleep(1)
            except:
                pass

    except Exception as e:
        print(f"Error processing lead {i+1}: {e}")
        results['failed'].append({'name': f"Lead {i+1}", 'reason': str(e)})

service.logout()

print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)
print(f"Successful: {len(results['successful'])}")
for item in results['successful']:
    print(f"  - {item['name']}")

print(f"\nFailed: {len(results['failed'])}")
for item in results['failed']:
    print(f"  - {item['name']}: {item.get('reason', 'Unknown')}")

print(f"\nSkipped: {len(results['skipped'])}")
for item in results['skipped']:
    print(f"  - {item['name']}: {item.get('reason', 'Unknown')}")
print("=" * 60)
