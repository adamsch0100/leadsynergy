"""Script to process ALL HomeLight urgent leads directly from the platform"""
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

print("=" * 60)
print("HOMELIGHT URGENT LEADS - DIRECT PLATFORM SWEEP")
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
    else:
        # Try alternative - look for filter with count
        filter_elements = service.driver_service.find_elements(By.XPATH, "//*[contains(text(), 'Urgent')]")
        print(f"Found {len(filter_elements)} elements with 'Urgent' text")
        for elem in filter_elements:
            print(f"  - {elem.tag_name}: {elem.text[:100]}")
except Exception as e:
    print(f"Error clicking urgent filter: {e}")

# Get all lead rows
print("\n[STEP 3] Getting urgent lead rows...")
time.sleep(2)
lead_rows = service.driver_service.find_elements(By.CSS_SELECTOR, "a[data-test='referralsList-row']")
print(f"Found {len(lead_rows)} leads")

results = {'successful': [], 'failed': [], 'skipped': []}

for i, row in enumerate(lead_rows):
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
        print(f"# LEAD {i+1}/{len(lead_rows)}: {lead_name}")
        print(f"# Type: {lead_type}")
        print(f"# Current Stage: {current_stage}")
        print(f"{'#' * 60}")

        # Click the lead to open detail
        service.driver_service.safe_click(row)
        time.sleep(3)

        # Try to find and click "Add Another Note" or similar to just update activity
        try:
            # First try to find the "Add Another Note" button
            add_note_btn = None
            for selector in [
                "//button[contains(text(), 'Add Another Note')]",
                "//button[contains(text(), 'Add Note')]",
                "//button[contains(@data-test, 'add-note')]"
            ]:
                try:
                    add_note_btn = service.driver_service.find_element(By.XPATH, selector)
                    if add_note_btn:
                        break
                except:
                    continue

            if add_note_btn:
                print("Found Add Note button, clicking...")
                service.driver_service.safe_click(add_note_btn)
                time.sleep(2)

            # Find the note textarea
            textarea = None
            for selector in [
                "textarea[data-test='referral-add-note-textarea']",
                "textarea[placeholder*='Add an optional note']",
                "textarea[placeholder*='note']",
                "textarea[data-test='connected-notes']"
            ]:
                try:
                    textarea = service.driver_service.find_element(By.CSS_SELECTOR, selector)
                    if textarea:
                        break
                except:
                    continue

            if textarea:
                note = f"Status update - Continuing to work with {lead_name}. Updated {datetime.now().strftime('%m/%d/%Y')}."
                textarea.clear()
                textarea.send_keys(note)
                print(f"Added note: {note[:50]}...")
                time.sleep(1)

                # Try to find and click Update/Submit button
                for btn_selector in [
                    "//button[contains(text(), 'Update Stage')]",
                    "//button[contains(text(), 'Submit')]",
                    "//button[contains(text(), 'Save')]",
                    "//button[contains(@data-test, 'submit')]"
                ]:
                    try:
                        btn = service.driver_service.find_element(By.XPATH, btn_selector)
                        if btn:
                            service.driver_service.safe_click(btn)
                            print(f"Clicked: {btn.text}")
                            time.sleep(2)
                            results['successful'].append({'name': lead_name})
                            break
                    except:
                        continue
            else:
                print("Could not find note textarea")
                results['skipped'].append({'name': lead_name, 'reason': 'No textarea found'})

        except Exception as e:
            print(f"Error updating lead: {e}")
            results['failed'].append({'name': lead_name, 'reason': str(e)})

        # Click Done to close
        try:
            done_btn = service.driver_service.find_element(By.XPATH, "//button[contains(text(), 'Done')]")
            if done_btn:
                done_btn.click()
                time.sleep(2)
        except:
            pass

        # Clear search and get fresh list
        time.sleep(2)

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
