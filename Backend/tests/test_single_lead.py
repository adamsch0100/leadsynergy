"""
Test script for testing individual HomeLight lead updates
Usage:
    python test_single_lead.py [lead_name] [--status STATUS] [--skip-check]
    
Examples:
    python test_single_lead.py "John Doe"
    python test_single_lead.py "John Doe" --status "Connected"
    python test_single_lead.py "John Doe" --skip-check
"""
import sys
import argparse
from dotenv import load_dotenv

load_dotenv()

from app.service.lead_service import LeadServiceSingleton
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
from app.referral_scrapers.homelight.homelight_service import HomelightService
from app.referral_scrapers.utils.driver_service import DriverService

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
    parser = argparse.ArgumentParser(description='Test individual HomeLight lead update')
    parser.add_argument('lead_name', nargs='?', help='Lead name to test (partial or full)')
    parser.add_argument('--status', help='Override status to set (default: use mapped status from FUB)')
    parser.add_argument('--skip-check', action='store_true', help='Skip the min_sync_interval check')
    parser.add_argument('--list', action='store_true', help='List first 20 HomeLight leads')
    
    args = parser.parse_args()
    
    # Get settings
    settings_service = LeadSourceSettingsSingleton.get_instance()
    settings = settings_service.get_by_source_name('HomeLight')
    
    if not settings:
        print('ERROR: No HomeLight lead source configuration found.')
        sys.exit(1)
    
    if not getattr(settings, 'is_active', True):
        print('ERROR: HomeLight lead source is not active.')
        sys.exit(1)
    
    # List leads if requested
    if args.list:
        lead_service = LeadServiceSingleton.get_instance()
        leads = lead_service.get_by_source('HomeLight', limit=20, offset=0)
        print(f"\nFound {len(leads)} HomeLight leads (showing first 20):\n")
        for i, lead in enumerate(leads, 1):
            status = getattr(lead, 'status', 'N/A')
            print(f"{i}. {lead.first_name} {lead.last_name} (Status: {status})")
        print()
        sys.exit(0)
    
    # Find lead by name
    if not args.lead_name:
        print("ERROR: Please provide a lead name to test")
        print("Usage: python test_single_lead.py [lead_name] [--status STATUS] [--skip-check]")
        print("       python test_single_lead.py --list  (to see available leads)")
        sys.exit(1)
    
    matches = find_lead_by_name(args.lead_name)
    
    if not matches:
        print(f"ERROR: No lead found matching '{args.lead_name}'")
        print("Use --list to see available leads")
        sys.exit(1)
    
    if len(matches) > 1:
        print(f"Found {len(matches)} matching leads:")
        for i, lead in enumerate(matches, 1):
            status = getattr(lead, 'status', 'N/A')
            print(f"  {i}. {lead.first_name} {lead.last_name} (Status: {status})")
        print(f"\nUsing first match: {matches[0].first_name} {matches[0].last_name}\n")
    
    lead = matches[0]
    full_name = f"{lead.first_name} {lead.last_name}"
    
    print("="*70)
    print(f"TESTING HOMELIGHT UPDATE FOR: {full_name}")
    print("="*70)
    print(f"Lead ID: {lead.id}")
    print(f"FUB Person ID: {lead.fub_person_id}")
    print(f"Current FUB Status: {getattr(lead, 'status', 'N/A')}")
    
    # Get mapped status
    mapped_status = None
    if settings and hasattr(lead, 'status'):
        mapped_status = settings.get_mapped_stage(lead.status)
    
    # Use override status or mapped status
    target_status = args.status or mapped_status or 'Connected'
    print(f"Target HomeLight Status: {target_status}")
    
    # Check metadata
    if lead.metadata and isinstance(lead.metadata, dict):
        last_synced = lead.metadata.get("homelight_last_updated")
        if last_synced:
            print(f"Last Synced: {last_synced}")
    else:
        print("Last Synced: Never (no metadata)")
    
    print("="*70)
    
    # Get min_sync_interval
    min_sync_interval_hours = 24
    if settings.metadata and isinstance(settings.metadata, dict):
        min_sync_interval_hours = settings.metadata.get("min_sync_interval_hours", 24)
    elif hasattr(settings, 'metadata') and isinstance(settings.metadata, str):
        import json
        try:
            metadata = json.loads(settings.metadata)
            min_sync_interval_hours = metadata.get("min_sync_interval_hours", 24)
        except:
            pass
    
    if args.skip_check:
        print("NOTE: Skipping min_sync_interval check (--skip-check flag set)")
        min_sync_interval_hours = 0
    
    print(f"Min Sync Interval: {min_sync_interval_hours} hours")
    print("="*70)
    print()
    
    # Create service instance
    driver_service = DriverService()
    same_status_note = getattr(settings, 'same_status_note', None)
    
    service = HomelightService(
        lead=lead,
        status=target_status,
        driver_service=driver_service,
        organization_id=getattr(lead, 'organization_id', None),
        same_status_note=same_status_note,
        min_sync_interval_hours=min_sync_interval_hours if not args.skip_check else 0
    )
    
    print("\n[TEST] Starting HomeLight update process...")
    print("[TEST] Watch the browser - it should open and perform the following:")
    print("[TEST]   1. Login to HomeLight")
    print("[TEST]   2. Navigate to referrals page")
    print("[TEST]   3. Search for the lead")
    print("[TEST]   4. Click on the lead")
    print("[TEST]   5. Select the stage dropdown (NOT assigned agent)")
    print("[TEST]   6. Update stage and add note")
    print("[TEST]   7. Navigate back\n")
    
    try:
        # Login first
        print("[STEP 1] Logging in to HomeLight...")
        login_success = service.login_once()
        if not login_success:
            print("[ERROR] Login failed!")
            sys.exit(1)
        print("[SUCCESS] Login successful!\n")
        
        # Ensure on referrals page
        print("[STEP 2] Ensuring on referrals page...")
        service._ensure_on_referrals_page()
        print("[SUCCESS] On referrals page\n")
        
        # Search for customer
        print(f"[STEP 3] Searching for '{full_name}'...")
        customer_found = service.find_and_click_customer_by_name(full_name)
        if not customer_found:
            print("[ERROR] Could not find or click customer!")
            service.logout()
            sys.exit(1)
        print("[SUCCESS] Customer found and opened!\n")
        
        # Check skip logic
        print("[STEP 4] Checking if lead should be skipped...")
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=min_sync_interval_hours if not args.skip_check else 0)
        
        should_skip = False
        skip_reason = None
        
        # Check metadata
        if not args.skip_check and lead.metadata and isinstance(lead.metadata, dict):
            last_synced_str = lead.metadata.get("homelight_last_updated")
            if last_synced_str:
                try:
                    if isinstance(last_synced_str, str):
                        last_synced = datetime.fromisoformat(last_synced_str.replace('Z', '+00:00'))
                    else:
                        last_synced = last_synced_str
                    if last_synced.tzinfo is None:
                        last_synced = last_synced.replace(tzinfo=timezone.utc)
                    
                    if last_synced > cutoff_time:
                        hours_since = (now - last_synced).total_seconds() / 3600
                        should_skip = True
                        skip_reason = f"Synced {hours_since:.1f}h ago (metadata)"
                except Exception as e:
                    print(f"[WARNING] Error parsing metadata: {e}")
        
        # Check page activity if not skipped by metadata
        if not should_skip and not args.skip_check:
            try:
                should_skip = service._check_recent_activity_on_page(min_sync_interval_hours)
                if should_skip:
                    skip_reason = "Recent activity found on page"
            except Exception as e:
                print(f"[WARNING] Error checking activity: {e}")
        
        if should_skip:
            print(f"[SKIP] Lead would be skipped: {skip_reason}")
            print("[INFO] Use --skip-check to force update anyway")
            service.logout()
            sys.exit(0)
        else:
            print("[INFO] Lead will be updated (not skipped)\n")
        
        # Update customer
        print(f"[STEP 5] Updating stage to '{target_status}'...")
        print("[WATCH] Check that it clicks the STAGE dropdown (NOT assigned agent)")
        success = service.update_customers(target_status)
        
        if success:
            print("\n" + "="*70)
            print("[SUCCESS] UPDATE COMPLETED SUCCESSFULLY!")
            print("="*70)
            
            # Update metadata
            try:
                from datetime import datetime, timezone
                if not lead.metadata:
                    lead.metadata = {}
                lead.metadata["homelight_last_updated"] = datetime.now(timezone.utc).isoformat()
                lead_service.update(lead)
                print(f"[METADATA] Recorded sync time for {full_name}")
            except Exception as e:
                print(f"[WARNING] Could not update metadata: {e}")
        else:
            print("\n" + "="*70)
            print("[FAILED] UPDATE FAILED!")
            print("="*70)
        
        # Navigate back
        print("\n[STEP 6] Navigating back to referrals page...")
        service._navigate_back_to_referrals()
        print("[SUCCESS] Navigation complete")
        
    except KeyboardInterrupt:
        print("\n[INFO] Test interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] Exception during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n[INFO] Keeping browser open for 30 seconds for inspection...")
        import time
        time.sleep(30)
        print("[INFO] Closing browser...")
        service.logout()
        print("[INFO] Test complete")

if __name__ == "__main__":
    main()

