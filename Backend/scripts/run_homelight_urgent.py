"""Quick script to run HomeLight urgent leads update"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

# Force headless OFF for debugging
os.environ["SELENIUM_HEADLESS"] = "false"

import json
from app.database.supabase_client import SupabaseClientSingleton
from app.models.lead import Lead
from app.referral_scrapers.homelight.homelight_service import HomelightService
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton

print("=" * 60)
print("HOMELIGHT URGENT LEADS UPDATE")
print("=" * 60)

# Remaining urgent leads to process
URGENT_LEADS = [
    "Tony Choi",
    "Augustine Rodriguez",
    "Mayra Villarreal"
]

supabase = SupabaseClientSingleton.get_instance()
settings_service = LeadSourceSettingsSingleton.get_instance()
source_settings = settings_service.get_by_source_name("HomeLight")

if not source_settings:
    print("ERROR: No HomeLight lead source settings found!")
    sys.exit(1)

leads_to_process = []

for name in URGENT_LEADS:
    parts = name.split()
    first_name = parts[0]
    last_name = parts[-1] if len(parts) > 1 else ""

    # Search by first name
    result = supabase.table('leads').select('*').eq('source', 'HomeLight').ilike('first_name', f'%{first_name}%').execute()

    for lead_data in result.data:
        if last_name.lower() in lead_data.get('last_name', '').lower():
            lead = Lead.from_dict(lead_data)

            # Extract lead type from tags
            tags = lead_data.get('tags', []) or []
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except:
                    tags = []
            lead_type = None
            for tag in tags:
                tag_lower = str(tag).lower()
                if 'seller' in tag_lower:
                    lead_type = 'seller'
                    break
                elif 'buyer' in tag_lower:
                    lead_type = 'buyer'
                    break

            # Get mapped stage
            mapped_stage = source_settings.get_mapped_stage(lead.status, lead_type)

            leads_to_process.append({
                'lead': lead,
                'mapped_stage': mapped_stage or "Connected",  # Default to Connected
                'fub_status': lead.status,
                'lead_type': lead_type
            })
            print(f"Found: {lead.first_name} {lead.last_name} - FUB: {lead.status} -> HL: {mapped_stage}")
            break

print(f"\nFound {len(leads_to_process)} leads to process")

if not leads_to_process:
    print("No leads found!")
    sys.exit(0)

# Process each lead
service = None
results = {'successful': [], 'failed': []}

for i, item in enumerate(leads_to_process):
    lead = item['lead']
    mapped_stage = item['mapped_stage']

    print(f"\n{'#' * 60}")
    print(f"# PROCESSING {i+1}/{len(leads_to_process)}: {lead.first_name} {lead.last_name}")
    print(f"# FUB Status: {lead.status}")
    print(f"# Target HomeLight Stage: {mapped_stage}")
    print(f"{'#' * 60}\n")

    if service is None:
        service = HomelightService(
            lead=lead,
            status=mapped_stage,
            organization_id=lead.organization_id,
            min_sync_interval_hours=0  # Disable skip
        )

        print("[STEP 1] Logging in...")
        if not service.login_once():
            print("[FAILED] Login failed!")
            results['failed'].append({'lead': lead, 'reason': 'Login failed'})
            break
        print("[OK] Login successful")
    else:
        service.update_active_lead(lead, mapped_stage)

    try:
        print("\n[STEP 2] Updating lead...")
        result = service.update_single_lead()

        if result:
            print(f"\n[SUCCESS] {lead.first_name} {lead.last_name} updated!")
            results['successful'].append({'lead': lead})
        else:
            print(f"\n[FAILED] Update returned False")
            results['failed'].append({'lead': lead, 'reason': 'Update failed'})

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        results['failed'].append({'lead': lead, 'reason': str(e)})

if service:
    service.logout()

print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)
print(f"Successful: {len(results['successful'])}")
for item in results['successful']:
    print(f"  - {item['lead'].first_name} {item['lead'].last_name}")

print(f"\nFailed: {len(results['failed'])}")
for item in results['failed']:
    print(f"  - {item['lead'].first_name} {item['lead'].last_name}: {item.get('reason', 'Unknown')}")
print("=" * 60)
