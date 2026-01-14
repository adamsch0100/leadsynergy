import json
import time
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from app.service.lead_service import LeadServiceSingleton
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
from app.referral_scrapers.homelight.homelight_service import HomelightService
from app.referral_scrapers.utils.driver_service import DriverService

lead_service = LeadServiceSingleton.get_instance()
settings_service = LeadSourceSettingsSingleton.get_instance()
settings = settings_service.get_by_source_name('HomeLight')

if not settings:
    print('ERROR: No HomeLight lead source configuration found.')
    raise SystemExit(1)

if not getattr(settings, 'is_active', True):
    print('ERROR: HomeLight lead source is not active.')
    raise SystemExit(1)

# Debug: Print credentials
credentials = settings.metadata.get('credentials', {}) if settings.metadata else {}
email = credentials.get('email')
password = credentials.get('password')
print(f"HomeLight credentials from settings:")
print(f"  Email: {email or 'NOT SET'}")
print(f"  Password: {'*' * len(password) if password else 'NOT SET'}")

# Get all HomeLight leads first
page_size = 100  # Get more leads at once
offset = 0
all_leads = []

print("Fetching all HomeLight leads...")
while True:
    leads = lead_service.get_by_source('HomeLight', limit=page_size, offset=offset)
    if not leads:
        break
    all_leads.extend(leads)
    offset += page_size
    if len(leads) < page_size:
        break

print(f"Found {len(all_leads)} HomeLight leads to process")

if not all_leads:
    print("No leads to process")
    raise SystemExit(0)

total_processed = 0
success_count = 0
failures = []

start = time.time()
print(f"[{datetime.utcnow().isoformat()}] Starting HomeLight referral update for {len(all_leads)} leads")

# Create a single driver service and service instance for the entire session
driver_service = DriverService()
main_service = HomelightService(
    lead=all_leads[0],  # Dummy lead for initialization
    status='Connected',
    driver_service=driver_service
)

# Login once
print("Starting login process...")
login_success = main_service.login_once()
print(f"Login result: {login_success}")
if not login_success:
    print("ERROR: Failed to login to HomeLight")
    raise SystemExit(1)

print("Login successful, starting lead processing...")
try:
    # Process all leads with the same service instance
    for lead in all_leads:
        total_processed += 1
        mapped_stage = settings.get_mapped_stage(lead.status) if hasattr(settings, 'get_mapped_stage') else None

        if isinstance(mapped_stage, (list, tuple)):
            status_to_use = mapped_stage[0]
        elif mapped_stage:
            status_to_use = mapped_stage
        else:
            status_to_use = lead.status or 'Connected'

        # Update the service with the current lead and status
        main_service.update_active_lead(lead, status_to_use)

        lead_name = lead.full_name
        print(f"Processing {total_processed}: {lead_name} -> {status_to_use}")

        success = main_service.update_single_lead()

        if success:
            success_count += 1
            print(f"  ✓ Success for {lead_name}")
        else:
            failure_info = {
                'lead_id': lead.id,
                'fub_person_id': lead.fub_person_id,
                'name': lead_name,
                'status': status_to_use,
                'error': 'Update failed'
            }
            failures.append(failure_info)
            print(f"  ✗ Failed for {lead_name}")

finally:
    # Logout once at the end
    main_service.logout()

elapsed = time.time() - start
print('')
print('=== HomeLight Update Summary ===')
print(f'Total leads processed: {total_processed}')
print(f'Successful updates: {success_count}')
print(f'Failed updates: {len(failures)}')
print(f'Elapsed time: {elapsed:.1f}s')

if failures:
    print('Failure details:')
    print(json.dumps(failures, indent=2))
