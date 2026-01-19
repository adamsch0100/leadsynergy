"""Debug script for HomeLight urgent leads - tests the 4 urgent leads from the screenshot"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
load_dotenv()

# Force headless OFF for debugging
os.environ["SELENIUM_HEADLESS"] = "false"

import json
from app.database.supabase_client import SupabaseClientSingleton
from app.models.lead import Lead
from app.referral_scrapers.homelight.homelight_service import HomelightService
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton

# Configuration
MIN_SYNC_INTERVAL_HOURS = 168  # 1 week default

print("=" * 60)
print("HOMELIGHT URGENT LEADS DEBUG TEST")
print("=" * 60)

# The 4 urgent leads from your screenshot
URGENT_LEADS = [
    "Pat Kurtz",
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

print(f"\nMin sync interval: {MIN_SYNC_INTERVAL_HOURS} hours")
print("\nSearching for urgent leads in database...")

# Lists for categorizing leads
leads_to_process = []
leads_skipped = []
leads_no_mapping = []

now = datetime.now(timezone.utc)
cutoff_time = now - timedelta(hours=MIN_SYNC_INTERVAL_HOURS)

for name in URGENT_LEADS:
    parts = name.split()
    first_name = parts[0]
    last_name = parts[-1] if len(parts) > 1 else ""

    # Search by first name
    result = supabase.table('leads').select('*').eq('source', 'HomeLight').ilike('first_name', f'%{first_name}%').execute()

    for lead_data in result.data:
        if last_name.lower() in lead_data.get('last_name', '').lower():
            lead = Lead.from_dict(lead_data)

            # Extract lead type (buyer/seller) from tags
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

            # Check metadata for last sync
            metadata = lead_data.get('metadata') or {}
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}

            last_sync_str = metadata.get('homelight_last_updated') if isinstance(metadata, dict) else None
            last_sync_dt = None
            hours_since_sync = None

            if last_sync_str:
                try:
                    last_sync_dt = datetime.fromisoformat(last_sync_str.replace('Z', '+00:00'))
                    if last_sync_dt.tzinfo is None:
                        last_sync_dt = last_sync_dt.replace(tzinfo=timezone.utc)
                    hours_since_sync = (now - last_sync_dt).total_seconds() / 3600
                except:
                    pass

            lead_info = {
                'lead': lead,
                'mapped_stage': mapped_stage,
                'fub_status': lead.status,
                'lead_type': lead_type,
                'last_sync_dt': last_sync_dt,
                'hours_since_sync': hours_since_sync
            }

            # Categorize the lead
            if not mapped_stage:
                lead_info['skip_reason'] = f"No mapping for FUB status: {lead.status}"
                leads_no_mapping.append(lead_info)
            elif last_sync_dt and last_sync_dt > cutoff_time:
                lead_info['skip_reason'] = f"Recently synced ({hours_since_sync:.1f}h ago)"
                leads_skipped.append(lead_info)
            else:
                leads_to_process.append(lead_info)

            break

# Display summary
print(f"\n{'=' * 60}")
print("LEAD ANALYSIS SUMMARY")
print("=" * 60)

# Show skipped leads (recently synced)
if leads_skipped:
    print(f"\n[SKIPPED - RECENTLY SYNCED] ({len(leads_skipped)} leads)")
    print("-" * 40)
    for item in leads_skipped:
        lead = item['lead']
        print(f"  - {lead.first_name} {lead.last_name}")
        print(f"      FUB Status: {item['fub_status']}")
        print(f"      Reason: {item['skip_reason']}")

# Show leads with no mapping
if leads_no_mapping:
    print(f"\n[SKIPPED - NO MAPPING] ({len(leads_no_mapping)} leads)")
    print("-" * 40)
    for item in leads_no_mapping:
        lead = item['lead']
        print(f"  - {lead.first_name} {lead.last_name}")
        print(f"      FUB Status: {item['fub_status']}")
        print(f"      Reason: {item['skip_reason']}")

# Show leads to process
if leads_to_process:
    print(f"\n[WILL PROCESS] ({len(leads_to_process)} leads)")
    print("-" * 40)
    for item in leads_to_process:
        lead = item['lead']
        sync_info = f"Never synced" if not item['last_sync_dt'] else f"Last sync: {item['hours_since_sync']:.1f}h ago"
        print(f"  - {lead.first_name} {lead.last_name} [{item['lead_type'] or 'unknown'}]")
        print(f"      FUB: {item['fub_status']} -> HL: {item['mapped_stage']}")
        print(f"      {sync_info}")

print(f"\n{'=' * 60}")
print(f"TOTAL: {len(leads_to_process)} to process, {len(leads_skipped)} skipped (recent), {len(leads_no_mapping)} no mapping")
print("=" * 60)

if not leads_to_process:
    print("\nNo leads to process!")
    if leads_skipped:
        print(f"\nTo force processing skipped leads, set MIN_SYNC_INTERVAL_HOURS = 0 at the top of this script")
    sys.exit(0)

# Let user select which lead to test
print("\nSelect a lead to test:")
for i, item in enumerate(leads_to_process):
    lead = item['lead']
    print(f"  {i+1}. {lead.first_name} {lead.last_name} [{item['lead_type'] or 'unknown'}] -> {item['mapped_stage']}")

print(f"  {len(leads_to_process)+1}. Test ALL leads sequentially")
print("\nEnter number (or press Enter for #1): ", end="")
choice = input().strip()

leads_to_test = []
if choice and choice.isdigit():
    idx = int(choice) - 1
    if idx == len(leads_to_process):
        leads_to_test = leads_to_process
    elif 0 <= idx < len(leads_to_process):
        leads_to_test = [leads_to_process[idx]]
    else:
        leads_to_test = [leads_to_process[0]]
else:
    leads_to_test = [leads_to_process[0]]

print(f"\nWill test {len(leads_to_test)} lead(s)")
print("\n" + "=" * 60)
print("IMPORTANT DEBUG CHECKPOINTS:")
print("=" * 60)
print("1. Watch the browser login process")
print("2. Watch if it navigates to the Referrals page")
print("3. Watch if it types the lead name in the search box")
print("4. Watch if it finds and clicks the lead")
print("5. Watch if it opens the lead detail panel")
print("6. Watch if it changes the stage dropdown")
print("7. Watch if it clicks 'Update Stage' or 'Add Note' button")
print("=" * 60)
input("\nPress Enter to start (browser will open)...")

# Results tracking
results = {
    'successful': [],
    'failed': [],
    'skipped': []
}

# Process each lead
service = None
for i, item in enumerate(leads_to_test):
    lead = item['lead']
    mapped_stage = item['mapped_stage']

    print(f"\n{'#' * 60}")
    print(f"# TESTING LEAD {i+1}/{len(leads_to_test)}: {lead.first_name} {lead.last_name}")
    print(f"# FUB Status: {lead.status}")
    print(f"# Lead Type: {item['lead_type'] or 'unknown'}")
    print(f"# Target HomeLight Stage: {mapped_stage}")
    print(f"{'#' * 60}\n")

    if not mapped_stage:
        print(f"ERROR: No mapping for status '{lead.status}'!")
        results['failed'].append({'lead': lead, 'reason': 'No mapping'})
        continue

    # Create service (reuse browser if possible)
    if service is None:
        service = HomelightService(
            lead=lead,
            status=mapped_stage,
            organization_id=lead.organization_id,
            min_sync_interval_hours=0  # Disable skip for testing (we pre-filtered)
        )

        print("[STEP 1] Attempting login...")
        if not service.login_once():
            print("[FAILED] Login failed - check credentials")
            results['failed'].append({'lead': lead, 'reason': 'Login failed'})
            break
        print("[OK] Login successful")
    else:
        # Update service with new lead data
        service.update_active_lead(lead, mapped_stage)

    try:
        print("\n[STEP 2] Attempting to update lead...")
        result = service.update_single_lead()

        if result:
            print(f"\n[SUCCESS] Lead {lead.first_name} {lead.last_name} updated!")
            results['successful'].append({'lead': lead})
        else:
            print(f"\n[FAILED] Lead update returned False")
            print("Possible reasons:")
            print("  - Lead not found in HomeLight search")
            print("  - Recent activity caused skip")
            print("  - Update stage button not clicked")
            results['failed'].append({'lead': lead, 'reason': 'Update returned False'})

    except Exception as e:
        print(f"\n[ERROR] Exception during update: {e}")
        import traceback
        traceback.print_exc()
        results['failed'].append({'lead': lead, 'reason': str(e)})

# Cleanup
if service:
    service.logout()

# Final results
print("\n" + "=" * 60)
print("TEST COMPLETE - RESULTS")
print("=" * 60)
print(f"\nSuccessful: {len(results['successful'])}")
for item in results['successful']:
    print(f"  - {item['lead'].first_name} {item['lead'].last_name}")

print(f"\nFailed: {len(results['failed'])}")
for item in results['failed']:
    print(f"  - {item['lead'].first_name} {item['lead'].last_name}: {item.get('reason', 'Unknown')}")

print(f"\nSkipped (pre-filtered): {len(leads_skipped)}")
for item in leads_skipped:
    print(f"  - {item['lead'].first_name} {item['lead'].last_name}: {item['skip_reason']}")

print("\n" + "=" * 60)
input("\nPress Enter to close...")
