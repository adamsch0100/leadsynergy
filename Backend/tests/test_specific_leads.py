"""
Test script for testing specific HomeLight leads by name
Usage:
    python test_specific_leads.py "Name1" "Name2" "Name3"
    OR
    python test_specific_leads.py  # Will use names from TEST_LEAD_NAMES list below
"""
import sys
from dotenv import load_dotenv

load_dotenv()

from app.service.lead_service import LeadServiceSingleton
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
from app.referral_scrapers.homelight.homelight_service import HomelightService
from app.referral_scrapers.utils.driver_service import DriverService

# List of specific lead names to test (if no command line args provided)
TEST_LEAD_NAMES = [
    "Michael Wimberley",      # Had double-typing issue
    "Benjamin Atchison",     # Multiple results (buyer/seller)
    "Robert Adams",           # Multiple matches
    "Mark Sims",              # Status update failed
    "Stacey Allen",           # Status update failed
    "Karen Parish",           # Status update failed
    "Charles Ward",           # Status update failed
    "Kristina Peterson",      # Status update failed
    "Rex Freburg",           # Status update failed
    "Chaim Bennell",         # Multiple matches
]

def find_lead_by_name(name: str):
    """Find a lead by full name or partial name"""
    lead_service = LeadServiceSingleton.get_instance()
    leads = lead_service.get_by_source('HomeLight', limit=1000, offset=0)
    
    name_lower = name.lower()
    matches = []
    
    for lead in leads:
        full_name = f"{lead.first_name} {lead.last_name}".lower()
        if name_lower in full_name or full_name in name_lower:
            matches.append(lead)
    
    return matches

def main():
    # Get names from command line args or use default list
    if len(sys.argv) > 1:
        test_names = sys.argv[1:]
        print(f"Using names from command line: {test_names}")
    else:
        test_names = TEST_LEAD_NAMES
    
    if not test_names:
        print("No test lead names specified.")
        print("\nUsage:")
        print('  python test_specific_leads.py "Name1" "Name2" "Name3"')
        print("\nOR add names to TEST_LEAD_NAMES list in the script.")
        return
    
    # Get settings
    settings_service = LeadSourceSettingsSingleton.get_instance()
    settings = settings_service.get_by_source_name('HomeLight')
    
    if not settings:
        print("Error: HomeLight settings not found")
        return
    
    # Get min_sync_interval from metadata
    min_sync_interval = 24  # Default
    if settings.metadata and isinstance(settings.metadata, dict):
        min_sync_interval = settings.metadata.get("min_sync_interval_hours", 24)
    elif hasattr(settings, 'metadata') and isinstance(settings.metadata, str):
        try:
            import json
            metadata = json.loads(settings.metadata)
            min_sync_interval = metadata.get("min_sync_interval_hours", 24)
        except:
            pass
    
    print("="*80)
    print("TESTING SPECIFIC HOMELIGHT LEADS")
    print("="*80)
    print(f"Testing {len(test_names)} lead(s)")
    print(f"Min sync interval: {min_sync_interval} hours")
    print("="*80 + "\n")
    
    driver_service = None
    results = []
    
    try:
        driver_service = DriverService()
        driver_service.initialize_driver()
        
        for i, lead_name in enumerate(test_names, 1):
            print("\n" + "="*80)
            print(f"LEAD {i}/{len(test_names)}: {lead_name}")
            print("="*80)
            
            # Find the lead
            matches = find_lead_by_name(lead_name)
            
            if not matches:
                print(f"[ERROR] No lead found matching '{lead_name}'")
                results.append({
                    "name": lead_name,
                    "status": "not_found",
                    "error": "Lead not found in database"
                })
                continue
            
            if len(matches) > 1:
                print(f"[WARNING] Found {len(matches)} leads matching '{lead_name}':")
                for j, match in enumerate(matches, 1):
                    print(f"  {j}. {match.first_name} {match.last_name} (FUB ID: {match.fub_person_id}, Status: {match.status})")
                print(f"Using first match: {matches[0].first_name} {matches[0].last_name}")
            
            lead = matches[0]
            
            # Get mapped status
            mapped_stage = None
            if settings and hasattr(lead, 'status'):
                mapped_stage = settings.get_mapped_stage(lead.status)
            
            if not mapped_stage:
                print(f"[SKIP] No mapped stage for FUB status: {lead.status}")
                results.append({
                    "name": lead_name,
                    "status": "skipped",
                    "reason": f"No mapped stage for FUB status: {lead.status}"
                })
                continue
            
            print(f"Lead: {lead.first_name} {lead.last_name}")
            print(f"FUB Status: {lead.status}")
            print(f"Target HomeLight Stage: {mapped_stage}")
            print()
            
            # Create service and test
            try:
                service = HomelightService(
                    lead=lead,
                    status=mapped_stage,
                    driver_service=driver_service,
                    organization_id=lead.organization_id,
                    min_sync_interval_hours=min_sync_interval
                )
                
                # Login if needed
                try:
                    service.login()
                except Exception as login_error:
                    print(f"[ERROR] Login failed: {login_error}")
                    results.append({
                        "name": lead_name,
                        "status": "failed",
                        "error": f"Login failed: {login_error}"
                    })
                    continue
                
                # Test update
                success = service.update_single_lead()
                
                if success:
                    print(f"\n[SUCCESS] {lead_name}")
                    results.append({
                        "name": lead_name,
                        "status": "success"
                    })
                else:
                    print(f"\n[FAILED] {lead_name}")
                    results.append({
                        "name": lead_name,
                        "status": "failed",
                        "error": "Update returned False"
                    })
                
            except Exception as e:
                print(f"\n[ERROR] Exception for {lead_name}: {e}")
                import traceback
                traceback.print_exc()
                results.append({
                    "name": lead_name,
                    "status": "error",
                    "error": str(e)
                })
            
            # Wait between leads
            if i < len(test_names):
                print("\nWaiting 3 seconds before next lead...")
                import time
                time.sleep(3)
        
    finally:
        if driver_service:
            try:
                driver_service.close()
            except:
                pass
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    success_count = sum(1 for r in results if r.get("status") == "success")
    failed_count = sum(1 for r in results if r.get("status") in ["failed", "error"])
    skipped_count = sum(1 for r in results if r.get("status") == "skipped")
    not_found_count = sum(1 for r in results if r.get("status") == "not_found")
    
    print(f"Total tested: {len(results)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {failed_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Not found: {not_found_count}")
    print("\nDetailed results:")
    for result in results:
        status = result.get("status", "unknown")
        name = result.get("name", "Unknown")
        if status == "success":
            print(f"  ✓ {name}")
        elif status == "skipped":
            print(f"  ⊘ {name} - {result.get('reason', 'Skipped')}")
        elif status == "not_found":
            print(f"  ✗ {name} - Not found")
        else:
            error = result.get("error", "Unknown error")
            print(f"  ✗ {name} - {error}")

if __name__ == "__main__":
    main()

