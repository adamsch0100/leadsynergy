"""Test script to run ReferralExchange sync on a single lead - run from terminal to see browser"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# Verify headless is off
headless = os.getenv("SELENIUM_HEADLESS", "true")
print(f"SELENIUM_HEADLESS = {headless}")
if headless.lower() in ["true", "1", "yes"]:
    print("WARNING: Headless mode is ON. Set SELENIUM_HEADLESS=false in .env to see browser")
else:
    print("Headless mode is OFF - browser should be visible")

from app.database.supabase_client import SupabaseClientSingleton
from app.models.lead import Lead

# Get ReferralExchange leads
supabase = SupabaseClientSingleton.get_instance()

print("\n=== REFERRALEXCHANGE LEADS ===")
result = supabase.table('leads').select('*').eq('source', 'ReferralExchange').limit(30).execute()

if not result.data:
    print("No ReferralExchange leads found")
    sys.exit(1)

print(f"\nFound {len(result.data)} ReferralExchange leads:")
for i, lead_data in enumerate(result.data):
    metadata = lead_data.get('metadata') or {}
    if isinstance(metadata, str):
        import json
        try:
            metadata = json.loads(metadata)
        except:
            metadata = {}
    last_updated = metadata.get('referralexchange_last_updated', 'Never') if isinstance(metadata, dict) else 'Never'
    if isinstance(last_updated, str) and len(last_updated) > 20:
        last_updated = last_updated[:19]
    print(f"  {i+1}. {lead_data['first_name']} {lead_data['last_name']} - Status: {lead_data['status']} - Last sync: {last_updated}")

# Let user pick which lead to test
print("\nEnter the number of the lead to test (or press Enter for #1):")
choice = input().strip()
if choice and choice.isdigit():
    idx = int(choice) - 1
    if 0 <= idx < len(result.data):
        lead_data = result.data[idx]
    else:
        print("Invalid choice, using first lead")
        lead_data = result.data[0]
else:
    lead_data = result.data[0]

lead = Lead.from_dict(lead_data)
print(f"\nTesting with: {lead.first_name} {lead.last_name}")
print(f"FUB Status: {lead.status}")

# Get the mapped stage for ReferralExchange
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
settings_service = LeadSourceSettingsSingleton.get_instance()
source_settings = settings_service.get_by_source_name("ReferralExchange")
mapped_stage = source_settings.get_mapped_stage(lead.status)
print(f"Mapped ReferralExchange stage: {mapped_stage}")

if not mapped_stage:
    print("ERROR: No mapping found for this FUB status")
    sys.exit(1)

# Convert to list format
if isinstance(mapped_stage, str):
    if "::" in mapped_stage:
        main, sub = [part.strip() for part in mapped_stage.split("::", 1)]
        status_for_service = [main, sub]
    else:
        status_for_service = [mapped_stage, ""]
elif isinstance(mapped_stage, (list, tuple)) and len(mapped_stage) >= 2:
    status_for_service = [mapped_stage[0], mapped_stage[1]]
else:
    status_for_service = [str(mapped_stage), ""]

print(f"Status for service: {status_for_service}")

input("\nPress Enter to start the ReferralExchange sync (browser will open)...")

# Run the sync
from app.referral_scrapers.referral_exchange.referral_exchange_service import ReferralExchangeService

service = ReferralExchangeService(
    lead=lead,
    status=status_for_service,
    organization_id=lead.organization_id
)

print("\nStarting ReferralExchange sync...")
result = service.referral_exchange_run()

if result:
    print("\n=== RESULT: SUCCESS - Lead was updated ===")
else:
    print("\n=== RESULT: NOT UPDATED ===")
    print("This could mean:")
    print("  - Lead was not found on platform")
    print("  - Status update failed")
    print("  - Actual error occurred")
    print("Check the logs above to see which case applies.")

input("\nPress Enter to close...")
