"""Script to process ALL MyAgentFinder overdue leads"""
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
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

print("=" * 60)
print("MYAGENTFINDER OVERDUE LEADS - DIRECT PLATFORM SWEEP")
print("=" * 60)

from app.referral_scrapers.my_agent_finder.my_agent_finder_service import (
    MyAgentFinderService,
    STATUS_CATEGORIES,
    BUYER_STATUS_OPTIONS,
    SELLER_STATUS_OPTIONS
)
from app.database.supabase_client import SupabaseClientSingleton
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
from app.referral_scrapers.utils.fub_data_helper import get_fub_data_helper
from app.models.lead import Lead

supabase = SupabaseClientSingleton.get_instance()
settings_service = LeadSourceSettingsSingleton.get_instance()
source_settings = settings_service.get_by_source_name("MyAgentFinder")
fub_helper = get_fub_data_helper()

# Default status for overdue leads if no FUB mapping
DEFAULT_STATUS_BUYER = "Prospect - I'm communicating with this Client"
DEFAULT_STATUS_SELLER = "Prospect - I'm communicating with this Seller"

# Initialize service
service = MyAgentFinderService(
    lead=None,
    status=None,
    organization_id="cfde8fec-3b87-4558-b20f-5fe25fdcf149",
    min_sync_interval_hours=0
)

print("\n[STEP 1] Logging in to MyAgentFinder...")
if not service.login():
    print("[FAILED] Login failed!")
    sys.exit(1)
print("[OK] Login successful")
service.is_logged_in = True

# Navigate to overdue URL
overdue_url = STATUS_CATEGORIES["overdue"]
print(f"\n[STEP 2] Navigating to overdue leads: {overdue_url}")
service.driver_service.get_page(overdue_url)
time.sleep(3)

# Get all lead cards
print("\n[STEP 3] Getting overdue lead cards...")
lead_cards = []

# MyAgentFinder uses cards for each lead
card_selectors = [
    "div[class*='card']",
    "div[class*='referral']",
    "a[href*='/referral/']"
]

for selector in card_selectors:
    try:
        cards = service.driver_service.find_elements(By.CSS_SELECTOR, selector)
        if cards and len(cards) > 0:
            lead_cards = cards
            print(f"Found {len(cards)} cards with selector: {selector}")
            break
    except:
        continue

# If no cards found, try looking for text
if not lead_cards:
    page_text = service.driver_service.driver.find_element(By.TAG_NAME, "body").text
    print(f"Page text preview: {page_text[:500]}")

    # Check for "No referrals" message
    if "no referrals" in page_text.lower() or "no overdue" in page_text.lower():
        print("\n[OK] No overdue leads found!")
        service.logout()
        sys.exit(0)

results = {'successful': [], 'failed': [], 'skipped': []}

# If we found lead cards, process them
for i, card in enumerate(lead_cards):
    try:
        card_text = card.text.strip()
        if not card_text:
            continue

        lines = card_text.split('\n')
        lead_name = lines[0] if lines else "Unknown"

        # Skip non-lead cards
        if lead_name in ['MyAgentFinder', 'Dashboard', 'Referrals', ''] or len(lead_name) < 3:
            continue

        print(f"\n{'#' * 60}")
        print(f"# LEAD {i+1}: {lead_name}")
        print(f"# Card text: {card_text[:100]}...")
        print(f"{'#' * 60}")

        # Determine if buyer or seller from card text
        is_seller = "seller" in card_text.lower() or "listing" in card_text.lower()
        lead_type = "seller" if is_seller else "buyer"
        default_status = DEFAULT_STATUS_SELLER if is_seller else DEFAULT_STATUS_BUYER

        # Try to find lead in database
        db_lead = fub_helper.lookup_lead_by_name(lead_name, "MyAgentFinder")

        target_status = default_status
        if db_lead:
            print(f"Found in database: {db_lead.first_name} {db_lead.last_name}, FUB status: {db_lead.status}")
            # Try to get mapped status
            if source_settings and db_lead.status:
                mapped_status = source_settings.get_mapped_stage(db_lead.status, lead_type)
                if mapped_status:
                    target_status = mapped_status
                    print(f"Using mapped status: {mapped_status}")
        else:
            print(f"Not found in database, using default: {default_status}")

        # Click the card to open lead details
        service.driver_service.safe_click(card)
        time.sleep(3)

        # Try to update the status
        try:
            success = service.find_and_update_lead(lead_name, target_status)
            if success:
                results['successful'].append({'name': lead_name})
                print(f"[SUCCESS] Updated {lead_name}")
            else:
                results['failed'].append({'name': lead_name, 'reason': 'Update failed'})
                print(f"[FAILED] Could not update {lead_name}")
        except Exception as e:
            print(f"Error updating: {e}")
            results['failed'].append({'name': lead_name, 'reason': str(e)})

        # Navigate back to overdue list
        service.driver_service.get_page(overdue_url)
        time.sleep(2)

        # Re-get cards (page refreshed)
        for selector in card_selectors:
            try:
                lead_cards = service.driver_service.find_elements(By.CSS_SELECTOR, selector)
                if lead_cards:
                    break
            except:
                continue

    except Exception as e:
        print(f"Error processing card {i}: {e}")
        results['failed'].append({'name': f"Card {i}", 'reason': str(e)})

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
