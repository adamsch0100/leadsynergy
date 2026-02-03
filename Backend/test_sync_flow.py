"""Test script to simulate the sync flow"""
import os
os.environ['SELENIUM_HEADLESS'] = 'true'

print('Simulating sync flow...')

from app.service.lead_service import LeadServiceSingleton
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton

# Get leads and source settings like the sync does
lead_service = LeadServiceSingleton.get_instance()
source_service = LeadSourceSettingsSingleton.get_instance()

user_id = '87fecfda-3123-459b-8d95-62d4f943e60f'
source_name = 'Referral Exchange'

# Get source settings
source_settings = source_service.get_by_source_name(source_name)
print(f'Source settings found: {source_settings is not None}')

# Get leads
leads = lead_service.get_by_source_and_user(source_name, user_id, limit=5, offset=0)
print(f'Found {len(leads)} leads')

if not leads:
    print('No leads, exiting')
    exit(1)

# Build leads_data like the sync does
leads_data = []
for lead in leads:
    mapped_stage = source_settings.get_mapped_stage(lead.status)
    if mapped_stage:
        if isinstance(mapped_stage, str):
            if '::' in mapped_stage:
                main, sub = [part.strip() for part in mapped_stage.split('::', 1)]
                status_for_service = [main, sub]
            else:
                status_for_service = [mapped_stage, '']
        elif isinstance(mapped_stage, (list, tuple)) and len(mapped_stage) >= 2:
            status_for_service = [mapped_stage[0], mapped_stage[1]]
        else:
            status_for_service = [str(mapped_stage), '']
        leads_data.append((lead, status_for_service))
        print(f'Lead {lead.first_name} {lead.last_name}: {lead.status} -> {status_for_service}')

print(f'\nLeads to process: {len(leads_data)}')

if not leads_data:
    print('No leads with mapping, exiting')
    exit(1)

# Create service like the sync does
from app.referral_scrapers.referral_exchange.referral_exchange_service import ReferralExchangeService

template_lead = leads_data[0][0]
template_status = leads_data[0][1]

print(f'\nCreating ReferralExchangeService...')
print(f'  lead: {template_lead.first_name} {template_lead.last_name}')
print(f'  status: {template_status}')
print(f'  organization_id: {template_lead.organization_id}')

service = ReferralExchangeService(
    lead=template_lead,
    status=template_status,
    organization_id=template_lead.organization_id,
    min_sync_interval_hours=168
)

print(f'\nService created:')
print(f'  driver is None: {service.driver_service.driver is None}')
print(f'  email: {service.email[:3] if service.email else None}***')
print(f'  password: {"***" if service.password else None}')

# Try login
print('\nAttempting login...')
import time
start = time.time()
login_result = service.login()
elapsed = time.time() - start
print(f'Login result: {login_result} (took {elapsed:.1f}s)')

service.driver_service.close()
print('Done')
