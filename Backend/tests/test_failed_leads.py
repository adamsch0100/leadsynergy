"""
Test script to update only the failed leads so we can observe what's happening
"""
import json
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from app.service.lead_service import LeadServiceSingleton
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
from app.referral_scrapers.homelight.homelight_service import HomelightService
from app.referral_scrapers.utils.driver_service import DriverService

# Failed leads data
failed_leads = {
    "customer_not_found": [
        3143,  # Benjamin Atchison
        3027,  # Michael Wimberley
        3023,  # Bruce Brotemarkle
        2800,  # Linda Decker
        2781,  # Denise Alexander
        2775,  # Robert Karyadeva
        2709,  # Richard Bamrick
        2921,  # Enrique Jimenez
    ],
    "status_update_failed": [
        3056,  # Patricia Kurtz
        3028,  # Steve Eisler
        3158,  # Tony Choi
        3021,  # Daniel Najar
        3010,  # Glenna Vansickle
        3009,  # Sandra Nye
        2999,  # Kristine
        2989,  # Karon Sadhnani
        2982,  # Cesar Holguin
        2974,  # Nathan Brounce
        2949,  # Ashley Brimhall
        2944,  # Charles Closson
        2929,  # Eric Kisskalt
        2925,  # Tim Mincer
        2923,  # Garret Dirks
        2920,  # Leeann Dye
        2907,  # Augustine Rodriguez
        2877,  # Frank Fischetta
        2826,  # Li Hwa
        2811,  # Robert Adams
        2759,  # Mark Sims
        2757,  # Stacey Allen
        2738,  # Karen Parish
        2706,  # Ramon Ramirez
        2666,  # Willie H
        2627,  # Charles Ward
        2576,  # Kristina Peterson
        2571,  # Rex Freburg
        2566,  # Chaim Bennell
    ]
}

lead_service = LeadServiceSingleton.get_instance()
settings_service = LeadSourceSettingsSingleton.get_instance()
settings = settings_service.get_by_source_name('HomeLight')

if not settings:
    print('ERROR: No HomeLight lead source configuration found.')
    exit(1)

if not getattr(settings, 'is_active', True):
    print('ERROR: HomeLight lead source is not active.')
    exit(1)

# Get min_sync_interval
min_sync_interval_hours = 24
if settings.metadata and isinstance(settings.metadata, dict):
    min_sync_interval_hours = settings.metadata.get("min_sync_interval_hours", 24)

# Combine all failed leads
all_failed_ids = failed_leads["customer_not_found"] + failed_leads["status_update_failed"]
print(f"Total failed leads to test: {len(all_failed_ids)}")
print(f"  - Customer not found: {len(failed_leads['customer_not_found'])}")
print(f"  - Status update failed: {len(failed_leads['status_update_failed'])}")
print()

# Fetch all leads
leads_to_test = []
for fub_id in all_failed_ids:
    lead = lead_service.get_by_fub_person_id(str(fub_id))
    if lead:
        leads_to_test.append(lead)
        category = "CUSTOMER NOT FOUND" if fub_id in failed_leads["customer_not_found"] else "STATUS UPDATE FAILED"
        print(f"Found: {lead.first_name} {lead.last_name} (ID: {fub_id}) - {category}")
    else:
        print(f"WARNING: Lead with FUB ID {fub_id} not found in database")

if not leads_to_test:
    print("No leads found to test")
    exit(1)

print(f"\n{'='*80}")
print(f"Testing {len(leads_to_test)} failed leads")
print(f"{'='*80}\n")

# Create driver and service
driver_service = DriverService()
same_status_note = getattr(settings, 'same_status_note', None)

# Use first lead for initialization
main_service = HomelightService(
    lead=leads_to_test[0],
    status='Connected',  # Will be updated per lead
    driver_service=driver_service,
    organization_id=getattr(leads_to_test[0], 'organization_id', None),
    same_status_note=same_status_note,
    min_sync_interval_hours=min_sync_interval_hours  # Use actual interval from settings
)

# Login once
print("="*80)
print("STEP 1: Logging into HomeLight...")
print("="*80)
login_success = main_service.login_once()
if not login_success:
    print("ERROR: Failed to login to HomeLight")
    exit(1)
print("Login successful!\n")

# Process each lead
results = {
    "total": len(leads_to_test),
    "successful": 0,
    "failed": 0,
    "skipped": 0,
    "customer_not_found": 0,
    "status_update_failed": 0,
    "details": []
}

start_time = time.time()

try:
    for idx, lead in enumerate(leads_to_test, 1):
        print("\n" + "="*80)
        print(f"LEAD {idx}/{len(leads_to_test)}: {lead.first_name} {lead.last_name}")
        print("="*80)
        print(f"FUB Person ID: {lead.fub_person_id}")
        print(f"FUB Status: {getattr(lead, 'status', 'N/A')}")
        
        # Get mapped stage
        mapped_stage = settings.get_mapped_stage(lead.status) if hasattr(settings, 'get_mapped_stage') else None
        if isinstance(mapped_stage, (list, tuple)):
            status_to_use = mapped_stage[0]
        elif mapped_stage:
            status_to_use = mapped_stage
        else:
            status_to_use = lead.status or 'Connected'
        
        print(f"Target HomeLight Stage: {status_to_use}")
        
        # Determine original failure category
        original_category = None
        if lead.fub_person_id in [str(id) for id in failed_leads["customer_not_found"]]:
            original_category = "customer_not_found"
        elif lead.fub_person_id in [str(id) for id in failed_leads["status_update_failed"]]:
            original_category = "status_update_failed"
        
        print(f"Original Failure Category: {original_category}")
        print("-"*80)
        
        # Update service with current lead
        main_service.update_active_lead(lead, status_to_use)
        
        # Try to update
        print(f"\nAttempting update...")
        success = main_service.update_single_lead()
        
        if success:
            results["successful"] += 1
            print(f"\n[SUCCESS] for {lead.first_name} {lead.last_name}")
            
            # Update metadata
            try:
                from datetime import datetime, timezone
                if not lead.metadata:
                    lead.metadata = {}
                lead.metadata["homelight_last_updated"] = datetime.now(timezone.utc).isoformat()
                lead_service.update(lead)
                print(f"  Metadata updated")
            except Exception as e:
                print(f"  Warning: Could not update metadata: {e}")
        else:
            results["failed"] += 1
            if original_category == "customer_not_found":
                results["customer_not_found"] += 1
            elif original_category == "status_update_failed":
                results["status_update_failed"] += 1
            print(f"\n[FAILED] for {lead.first_name} {lead.last_name}")
        
        results["details"].append({
            "lead_id": lead.fub_person_id,
            "name": f"{lead.first_name} {lead.last_name}",
            "status": lead.status,
            "target_stage": status_to_use,
            "original_category": original_category,
            "success": success
        })
        
        # Wait a bit between leads
        if idx < len(leads_to_test):
            print(f"\nWaiting 3 seconds before next lead...")
            time.sleep(3)

finally:
    # Logout
    print("\n" + "="*80)
    print("Logging out...")
    print("="*80)
    main_service.logout()

elapsed = time.time() - start_time

# Print summary
print("\n" + "="*80)
print("TEST SUMMARY")
print("="*80)
print(f"Total leads tested: {results['total']}")
print(f"Successful: {results['successful']}")
print(f"Failed: {results['failed']}")
print(f"  - Customer not found: {results['customer_not_found']}")
print(f"  - Status update failed: {results['status_update_failed']}")
print(f"Elapsed time: {elapsed:.1f}s")
print("="*80)

# Save detailed results
with open("failed_leads_test_results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
print(f"\nDetailed results saved to: failed_leads_test_results.json")

