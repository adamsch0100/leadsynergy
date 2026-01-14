import json
import time
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from app.service.lead_service import LeadServiceSingleton
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
from app.referral_scrapers.homelight.homelight_service import HomelightService

lead_service = LeadServiceSingleton.get_instance()
settings_service = LeadSourceSettingsSingleton.get_instance()
settings = settings_service.get_by_source_name('HomeLight')

if not settings:
    print('ERROR: No HomeLight lead source configuration found.')
    raise SystemExit(1)

if not getattr(settings, 'is_active', True):
    print('ERROR: HomeLight lead source is not active.')
    raise SystemExit(1)

# Get first lead for testing
leads = lead_service.get_by_source('HomeLight', limit=1, offset=0)
if not leads:
    print('No HomeLight leads found for testing.')
    raise SystemExit(1)

lead = leads[0]
print(f"Testing with lead: {lead.full_name} (ID: {lead.id})")

# Get the mapped status based on the lead's current FUB stage
settings_service = LeadSourceSettingsSingleton.get_instance()
settings = settings_service.get_by_source_name('HomeLight')
mapped_status = None
if settings and hasattr(lead, 'status'):
    mapped_status = settings.get_mapped_stage(lead.status)

if not mapped_status:
    mapped_status = 'Connected'  # Default fallback

print(f"Lead current status: {lead.status}")
print(f"Mapped HomeLight status: {mapped_status}")

# Create service instance
service = HomelightService(
    lead=lead,
    status=mapped_status,
    organization_id=getattr(lead, 'organization_id', None)
)

print("Starting manual HomeLight test...")
print("Browser should open visibly. Follow these steps:")
print("1. Watch the login process")
print("2. Watch the search process")
print("3. Watch the status update process")
print("4. Tell me what you see at each step")

try:
    success = service.homelight_run()
    if success:
        print("SUCCESS: HomeLight update completed")
    else:
        print("FAILED: HomeLight update failed")
except Exception as e:
    print(f"ERROR: {e}")
finally:
    try:
        service.driver_service.close()
    except Exception:
        pass
