"""Test script to run HomeLight sync on a single lead - run from terminal to see browser"""
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
from app.referral_scrapers.homelight.homelight_service import HomelightService

# Get a HomeLight lead that needs updating
supabase = SupabaseClientSingleton.get_instance()

# First, show the urgent leads that exist in the database
print("\n=== URGENT LEADS (from HomeLight screenshot) ===")
urgent_names = ['Benjamin Atchison', 'Judy Digiacomo']
for name in urgent_names:
    parts = name.split()
    first = parts[0]
    res = supabase.table('leads').select('first_name,last_name,status').eq('source', 'HomeLight').ilike('first_name', f'%{first}%').execute()
    for l in res.data:
        if parts[-1].lower() in l.get('last_name', '').lower():
            print(f"  - {l['first_name']} {l['last_name']}: FUB Status = {l['status']}")

print("\n=== ALL HOMELIGHT LEADS ===")
result = supabase.table('leads').select('*').eq('source', 'HomeLight').limit(20).execute()

if not result.data:
    print("No HomeLight leads found")
    sys.exit(1)

print(f"\nFound {len(result.data)} HomeLight leads:")
for i, lead_data in enumerate(result.data):
    metadata = lead_data.get('metadata') or {}
    if isinstance(metadata, str):
        import json
        try:
            metadata = json.loads(metadata)
        except:
            metadata = {}
    last_updated = metadata.get('homelight_last_updated', 'Never') if isinstance(metadata, dict) else 'Never'
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

# Get the mapped stage for HomeLight
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
settings_service = LeadSourceSettingsSingleton.get_instance()
source_settings = settings_service.get_by_source_name("HomeLight")
mapped_stage = source_settings.get_mapped_stage(lead.status)
print(f"Mapped HomeLight stage: {mapped_stage}")

if not mapped_stage:
    print("ERROR: No mapping found for this FUB status")
    sys.exit(1)

input("\nPress Enter to start the HomeLight sync (browser will open)...")

# Run the sync
service = HomelightService(
    lead=lead,
    status=mapped_stage,
    organization_id=lead.organization_id
)

print("\nStarting HomeLight sync...")
print("(Note: If skipped due to recent activity, it returns False but is NOT a failure)")
result = service.homelight_run()

if result:
    print("\n=== RESULT: SUCCESS - Lead was updated ===")
else:
    print("\n=== RESULT: NOT UPDATED ===")
    print("This could mean:")
    print("  - Lead was skipped (recent activity found) - this is OK")
    print("  - Lead was not found on platform")
    print("  - Actual error occurred")
    print("Check the logs above to see which case applies.")

input("\nPress Enter to close...")
