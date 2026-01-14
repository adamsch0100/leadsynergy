"""Test script to run ReferralExchange sync on failed/never-synced leads"""
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
import json

# Get ReferralExchange leads that were never synced
supabase = SupabaseClientSingleton.get_instance()

print("\n=== REFERRALEXCHANGE LEADS THAT NEVER SYNCED (47 failures) ===")
result = supabase.table('leads').select('*').eq('source', 'ReferralExchange').execute()

never_synced = []
for lead_data in result.data:
    metadata = lead_data.get('metadata') or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except:
            metadata = {}
    if not metadata.get('referralexchange_last_updated'):
        never_synced.append(lead_data)

print(f"\nFound {len(never_synced)} leads that never synced:")
for i, lead_data in enumerate(never_synced[:30]):
    print(f"  {i+1}. {lead_data['first_name']} {lead_data['last_name']} - FUB Status: {lead_data['status']}")

if len(never_synced) > 30:
    print(f"  ... and {len(never_synced) - 30} more")

if not never_synced:
    print("No failed leads found!")
    sys.exit(0)

# Let user pick which lead to test
print("\nEnter the number of the lead to test (or press Enter for #1):")
choice = input().strip()
if choice and choice.isdigit():
    idx = int(choice) - 1
    if 0 <= idx < len(never_synced):
        lead_data = never_synced[idx]
    else:
        print("Invalid choice, using first lead")
        lead_data = never_synced[0]
else:
    lead_data = never_synced[0]

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
    print("ERROR: No mapping found for this FUB status - THIS IS WHY IT FAILED!")
    print(f"You need to add a mapping for FUB status '{lead.status}' in the stage mapping settings.")
    input("\nPress Enter to exit...")
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
print("Watch the browser to see what happens during the search...")
result = service.referral_exchange_run()

if result:
    print("\n=== RESULT: SUCCESS - Lead was updated ===")
else:
    print("\n=== RESULT: FAILED ===")
    print("Possible reasons:")
    print("  1. Name not found in ReferralExchange (different spelling/format)")
    print("  2. Lead doesn't exist in ReferralExchange")
    print("  3. UI element not found")
    print("\nWatch the browser output above to see exactly what happened.")

input("\nPress Enter to close...")
