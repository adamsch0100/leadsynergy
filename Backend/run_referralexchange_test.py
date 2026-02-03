"""
Quick test script to verify ReferralExchange sync works.
Processes just 1 lead to verify the flow.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

os.environ["SELENIUM_HEADLESS"] = "true"

print("=" * 60)
print("REFERRALEXCHANGE QUICK TEST (1 LEAD)")
print("=" * 60)

from app.service.lead_service import LeadServiceSingleton
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
from app.referral_scrapers.referral_exchange.referral_exchange_service import ReferralExchangeService

USER_ID = "87fecfda-3123-459b-8d95-62d4f943e60f"
SOURCE_NAME = "Referral Exchange"

lead_service = LeadServiceSingleton.get_instance()
source_service = LeadSourceSettingsSingleton.get_instance()

source_settings = source_service.get_by_source_name(SOURCE_NAME)
leads = lead_service.get_by_source_and_user(SOURCE_NAME, USER_ID, limit=5, offset=0)
print(f"Found {len(leads)} leads")

# Build leads_data for first lead with mapping
leads_data = []
for lead in leads:
    mapped_stage = source_settings.get_mapped_stage(lead.status)
    if mapped_stage:
        if isinstance(mapped_stage, str):
            if "::" in mapped_stage:
                main, sub = [part.strip() for part in mapped_stage.split("::", 1)]
                status_for_service = [main, sub]
            else:
                status_for_service = [mapped_stage, ""]
        else:
            status_for_service = list(mapped_stage) if len(mapped_stage) >= 2 else [str(mapped_stage), ""]
        leads_data.append((lead, status_for_service))
        print(f"Test lead: {lead.first_name} {lead.last_name} -> {status_for_service}")
        break

if not leads_data:
    print("No leads with mapping found")
    sys.exit(1)

print("\nCreating service...")
template_lead, template_status = leads_data[0]

service = ReferralExchangeService(
    lead=template_lead,
    status=template_status,
    organization_id=template_lead.organization_id,
    min_sync_interval_hours=0  # No skip interval for testing
)

print(f"Driver initialized: {service.driver_service.driver is not None}")
print(f"Credentials: email={service.email[:3] if service.email else None}***, password={'***' if service.password else None}")

print("\nStarting test...")
results = service.update_multiple_leads(leads_data)

print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)
print(f"Successful: {results['successful']}")
print(f"Failed: {results['failed']}")
print(f"Skipped: {results['skipped']}")

if results['details']:
    for d in results['details']:
        print(f"  {d['name']}: {d['status']} - {d.get('error') or d.get('reason') or 'OK'}")

# Close driver
try:
    service.driver_service.close()
except:
    pass

print("=" * 60)
print("Test complete")
