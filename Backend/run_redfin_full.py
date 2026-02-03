"""
Non-interactive script to run FULL Redfin bulk sync.
Processes ALL leads with stage mappings.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# Set headless mode
os.environ["SELENIUM_HEADLESS"] = "true"

print("=" * 60)
print("REDFIN FULL SYNC - ALL LEADS")
print("=" * 60)

from app.service.lead_service import LeadServiceSingleton
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
from app.referral_scrapers.redfin.redfin_service import RedfinService
from app.models.lead import Lead

# Configuration
USER_ID = "87fecfda-3123-459b-8d95-62d4f943e60f"
SOURCE_NAME = "Redfin"

# Get services
lead_service = LeadServiceSingleton.get_instance()
source_service = LeadSourceSettingsSingleton.get_instance()

# Get source settings
source_settings = source_service.get_by_source_name(SOURCE_NAME)
if not source_settings:
    print(f"ERROR: Source '{SOURCE_NAME}' not found")
    sys.exit(1)

print(f"Source: {source_settings.source_name}")

# Get leads
print(f"\nFetching leads...")
leads = lead_service.get_by_source_and_user(SOURCE_NAME, USER_ID, limit=10000, offset=0)
print(f"Found {len(leads)} leads")

if not leads:
    print("No leads to sync")
    sys.exit(0)

# Build leads_data with mapped stages
leads_data = []
skipped = []

for lead in leads:
    mapped_stage = source_settings.get_mapped_stage(lead.status)
    if mapped_stage:
        # Redfin uses just a simple status string (not array like ReferralExchange)
        if isinstance(mapped_stage, str):
            if "::" in mapped_stage:
                # Take the main status part
                status_for_service = mapped_stage.split("::")[0].strip()
            else:
                status_for_service = mapped_stage
        elif isinstance(mapped_stage, (list, tuple)) and len(mapped_stage) >= 1:
            status_for_service = mapped_stage[0]
        else:
            status_for_service = str(mapped_stage)
        leads_data.append((lead, status_for_service))
    else:
        skipped.append(f"{lead.first_name} {lead.last_name} - status: {lead.status}")

print(f"\nLeads to process: {len(leads_data)}")
print(f"Skipped (no mapping): {len(skipped)}")

if not leads_data:
    print("No leads with stage mapping to process")
    sys.exit(0)

# Create a dummy lead for initialization
dummy_lead = Lead()
dummy_lead.first_name = "Init"
dummy_lead.last_name = "User"

# Create service
print("\n" + "-" * 60)
print("Creating RedfinService...")

service = RedfinService(
    lead=dummy_lead,
    status="Active",
    organization_id="cfde8fec-3b87-4558-b20f-5fe25fdcf149",
    user_id=USER_ID,
    min_sync_interval_hours=168  # Skip if synced in last 7 days
)

print(f"Service created")
print(f"  Email: {service.email[:5] if service.email else 'NOT SET'}***")
print(f"  2FA configured: {bool(service.twofa_email and service.twofa_app_password)}")

# Run bulk update
print("\n" + "-" * 60)
print(f"Starting bulk update of {len(leads_data)} leads...")
print("-" * 60)

results = service.update_multiple_leads(leads_data)

# Show results
print("\n" + "=" * 60)
print("SYNC RESULTS")
print("=" * 60)
print(f"Total leads: {results['total_leads']}")
print(f"Successful: {results['successful']}")
print(f"Failed: {results['failed']}")
print(f"Skipped: {results['skipped']}")

success_rate = (results['successful'] / results['total_leads'] * 100) if results['total_leads'] > 0 else 0
print(f"\nSuccess rate: {success_rate:.1f}%")

# Show failures
failures = [d for d in results.get('details', []) if d.get('status') == 'failed']
if failures:
    print(f"\nFailed leads ({len(failures)}):")
    for f in failures[:20]:
        print(f"  - {f.get('name', '?')}: {f.get('error', 'unknown error')}")

print("=" * 60)
print("Sync complete")
