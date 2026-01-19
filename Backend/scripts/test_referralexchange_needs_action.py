"""
Test script for ReferralExchange Needs Action sweep with FUB integration.

This script tests the Needs Action sweep functionality which:
1. Navigates to the Needs Action filter on ReferralExchange
2. For each lead in Needs Action:
   - Looks up the lead in the database by name
   - Uses FUB data to determine the best status (FUB mapping > last known > default)
   - Fetches recent FUB notes for the update comment
   - Updates the lead on ReferralExchange
   - Saves the status to metadata for future fallback

Usage:
    cd Backend
    python scripts/test_referralexchange_needs_action.py
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from dotenv import load_dotenv
load_dotenv()

# Force headless OFF for debugging
os.environ["SELENIUM_HEADLESS"] = "false"

print("=" * 60)
print("REFERRALEXCHANGE NEEDS ACTION SWEEP TEST")
print("=" * 60)

# Check what mode to run in
print("\nThis script tests the ReferralExchange Needs Action sweep.")
print("The sweep will:")
print("  1. Log into ReferralExchange")
print("  2. Navigate to the 'Needs Action' filter")
print("  3. For each lead found:")
print("     - Look up lead in database by name")
print("     - Use FUB mapped status if available")
print("     - Fall back to last known status from metadata")
print("     - Fall back to default 'We are in contact' if no match")
print("     - Add comment from recent FUB notes if available")
print("  4. Save successful status to metadata for future use")

print("\n" + "-" * 60)
print("OPTIONS:")
print("-" * 60)
print("1. Run the full Needs Action sweep")
print("2. Just check what leads are in Needs Action (no updates)")
print("3. Test FUB data lookup for a specific lead name")
print("\nEnter choice (1-3, or press Enter for #1): ", end="")
choice = input().strip()

if choice == "2":
    # Just check what's in Needs Action
    print("\n" + "=" * 60)
    print("CHECKING NEEDS ACTION LEADS (No updates)")
    print("=" * 60)

    from app.referral_scrapers.referral_exchange.referral_exchange_service import ReferralExchangeService
    from selenium.webdriver.common.by import By

    service = ReferralExchangeService()

    try:
        print("\nLogging in...")
        if not service.login():
            print("ERROR: Login failed!")
            sys.exit(1)
        print("Login successful!")

        # Navigate to referrals
        service._navigate_to_referrals()

        # Click Needs Action filter
        if not service._click_need_action_filter():
            print("Could not find Needs Action filter")
            sys.exit(1)

        import time
        time.sleep(3)

        # Get all leads
        lead_rows = service.driver_service.driver.find_elements(By.CSS_SELECTOR, ".leads-row")
        print(f"\nFound {len(lead_rows)} leads in Needs Action:")

        for i, row in enumerate(lead_rows):
            row_text = row.text.strip()
            row_lines = row_text.split('\n')
            display_name = row_lines[0].strip() if row_lines else row_text[:30]
            print(f"  {i+1}. {display_name}")

        print("\n" + "=" * 60)

    finally:
        service.logout()

elif choice == "3":
    # Test FUB lookup for a specific name
    print("\n" + "=" * 60)
    print("TEST FUB DATA LOOKUP")
    print("=" * 60)

    print("\nEnter lead display name to test (e.g., 'John S.'): ", end="")
    test_name = input().strip()

    if not test_name:
        print("No name entered, exiting.")
        sys.exit(0)

    from app.referral_scrapers.utils.fub_data_helper import get_fub_data_helper
    from app.service.lead_source_settings_service import LeadSourceSettingsSingleton

    fub_helper = get_fub_data_helper()
    settings_service = LeadSourceSettingsSingleton.get_instance()
    source_settings = settings_service.get_by_source_name("ReferralExchange")

    print(f"\nLooking up '{test_name}' in database...")
    db_lead = fub_helper.lookup_lead_by_name(test_name, "ReferralExchange")

    if not db_lead:
        print(f"  Lead NOT found in database for name: '{test_name}'")
        print("  Would use default status: ['We are in contact', 'is open to working with me']")
    else:
        print(f"  Found lead: {db_lead.first_name} {db_lead.last_name}")
        print(f"  Lead ID: {db_lead.id}")
        print(f"  FUB Status: {db_lead.status}")
        print(f"  FUB ID: {getattr(db_lead, 'fub_id', 'N/A')}")

        # Test status determination
        DEFAULT_STATUS = ["We are in contact", "is open to working with me"]
        fub_status, fub_comment = fub_helper.determine_status_for_lead(
            lead=db_lead,
            source_settings=source_settings,
            platform_name="referralexchange",
            default_status=DEFAULT_STATUS
        )

        print(f"\n  Determined status: {fub_status}")
        print(f"  Comment from FUB: {fub_comment[:100] + '...' if fub_comment and len(fub_comment) > 100 else fub_comment}")

        # Check metadata for last known status
        import json
        metadata = getattr(db_lead, 'metadata', {}) or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}

        last_status = metadata.get('referralexchange_last_status') if isinstance(metadata, dict) else None
        last_updated = metadata.get('referralexchange_last_updated') if isinstance(metadata, dict) else None

        print(f"\n  Metadata - Last status: {last_status}")
        print(f"  Metadata - Last updated: {last_updated}")

    print("\n" + "=" * 60)

else:
    # Run the full sweep
    print("\n" + "=" * 60)
    print("RUNNING FULL NEEDS ACTION SWEEP")
    print("=" * 60)

    print("\nIMPORTANT: Watch the browser to verify:")
    print("  1. Login process works")
    print("  2. Needs Action filter is clicked")
    print("  3. Each lead is updated with correct status")
    print("  4. Comments are added (if FUB notes available)")
    print("=" * 60)

    input("\nPress Enter to start (browser will open)...")

    from app.referral_scrapers.referral_exchange.referral_exchange_service import ReferralExchangeService

    service = ReferralExchangeService()

    try:
        results = service.run_standalone_need_action_sweep()

        print("\n" + "=" * 60)
        print("FINAL RESULTS")
        print("=" * 60)
        print(f"Total in Needs Action: {results['total_checked']}")
        print(f"Successfully updated: {results['updated']}")
        print(f"Used FUB data: {results.get('fub_used', 0)}")
        print(f"Used default: {results.get('default_used', 0)}")
        print(f"Errors: {results['errors']}")

        if results['updated_leads']:
            print(f"\nUpdated leads:")
            for name in results['updated_leads']:
                print(f"  - {name}")

        print("=" * 60)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

input("\nPress Enter to close...")
