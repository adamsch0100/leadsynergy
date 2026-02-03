"""
Direct command-line script to run ReferralExchange bulk sync.
Bypasses the server and runs the sync directly.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# Set headless mode (change to "false" to see browser)
os.environ["SELENIUM_HEADLESS"] = "true"

print("=" * 60)
print("REFERRALEXCHANGE BULK SYNC - DIRECT COMMAND LINE")
print("=" * 60)

from app.service.lead_service import LeadServiceSingleton
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
from app.referral_scrapers.referral_exchange.referral_exchange_service import ReferralExchangeService

# Configuration
USER_ID = "87fecfda-3123-459b-8d95-62d4f943e60f"
SOURCE_NAME = "Referral Exchange"

# Get services
lead_service = LeadServiceSingleton.get_instance()
source_service = LeadSourceSettingsSingleton.get_instance()

# Get source settings
source_settings = source_service.get_by_source_name(SOURCE_NAME)
if not source_settings:
    print(f"ERROR: Source '{SOURCE_NAME}' not found")
    sys.exit(1)

print(f"Source: {source_settings.source_name}")
print(f"Active: {source_settings.is_active}")

# Get leads
print(f"\nFetching leads for user {USER_ID}...")
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
        leads_data.append((lead, status_for_service))
    else:
        skipped.append(f"{lead.first_name} {lead.last_name} - no mapping for status: {lead.status}")

print(f"\nLeads to process: {len(leads_data)}")
print(f"Skipped (no mapping): {len(skipped)}")

if skipped[:5]:
    print("\nSample skipped leads:")
    for s in skipped[:5]:
        print(f"  - {s}")

if not leads_data:
    print("No leads with stage mapping to process")
    sys.exit(0)

# Limit for testing (remove this for full run)
MAX_LEADS = int(input("\nHow many leads to process? (Enter number, or 0 for all): ") or "5")
if MAX_LEADS > 0:
    leads_data = leads_data[:MAX_LEADS]
    print(f"Processing {len(leads_data)} leads")

input("\nPress Enter to start sync (Selenium browser will launch)...")

# Create service
print("\n" + "-" * 60)
print("Creating ReferralExchangeService...")
template_lead = leads_data[0][0]
template_status = leads_data[0][1]

service = ReferralExchangeService(
    lead=template_lead,
    status=template_status,
    organization_id=template_lead.organization_id,
    min_sync_interval_hours=168
)

print(f"Service created:")
print(f"  Driver initialized: {service.driver_service.driver is not None}")
print(f"  Credentials loaded: email={service.email is not None}, password={service.password is not None}")

# Run bulk update
print("\n" + "-" * 60)
print("Starting bulk update...")
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

if results['details']:
    print("\nDetails (first 10):")
    for detail in results['details'][:10]:
        status = detail.get('status', 'unknown')
        name = detail.get('name', 'Unknown')
        if status == 'success':
            print(f"  ✓ {name}")
        elif status == 'skipped':
            print(f"  - {name} (skipped: {detail.get('reason', '?')})")
        else:
            print(f"  ✗ {name} (error: {detail.get('error', '?')})")

print("=" * 60)
