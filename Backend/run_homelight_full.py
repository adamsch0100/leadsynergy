"""
Non-interactive script to run FULL HomeLight bulk sync.
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
print("HOMELIGHT FULL SYNC - ALL LEADS")
print("=" * 60)

from app.service.lead_service import LeadServiceSingleton
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
from app.referral_scrapers.homelight.homelight_service import HomelightService

# Configuration
USER_ID = "87fecfda-3123-459b-8d95-62d4f943e60f"
SOURCE_NAME = "HomeLight"

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
        # HomeLight uses "Main Status :: Sub Status" format
        if isinstance(mapped_stage, str):
            status_for_service = mapped_stage
        elif isinstance(mapped_stage, (list, tuple)):
            if len(mapped_stage) >= 2:
                status_for_service = f"{mapped_stage[0]} :: {mapped_stage[1]}"
            else:
                status_for_service = str(mapped_stage[0]) if mapped_stage else ""
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

# Create service
print("\n" + "-" * 60)
print("Creating HomelightService...")
template_lead = leads_data[0][0]
template_status = leads_data[0][1]

service = HomelightService(
    lead=template_lead,
    status=template_status,
    organization_id=template_lead.organization_id,
    min_sync_interval_hours=168,  # Skip if synced in last 7 days
    update_all_matches=True  # Update both buyer and seller referrals
)

print(f"Service created")
print(f"  Email: {service.email[:5] if service.email else 'NOT SET'}***")

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
