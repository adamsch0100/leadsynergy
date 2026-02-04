#!/usr/bin/env python3
"""
Force sync all leads for all active lead sources
Bypasses the minimum sync interval to update all leads immediately
"""
import sys
import os
import time
from datetime import datetime

# Add the Backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
from app.service.lead_service import LeadServiceSingleton
from app.service.sync_status_tracker import get_tracker
import uuid

def main():
    print("="*80)
    print("FORCE SYNC ALL LEADS - Bypassing 7-day minimum interval")
    print("="*80)
    print()

    # Get service instances
    lead_source_service = LeadSourceSettingsSingleton.get_instance()
    lead_service = LeadServiceSingleton.get_instance()
    tracker = get_tracker()

    # Get all active lead sources
    print("Fetching all active lead sources...")
    all_sources = lead_source_service.get_all()

    if not all_sources:
        print("ERROR No lead sources found")
        return

    # Handle both dict and object sources
    active_sources = []
    for s in all_sources:
        is_active = s.get('is_active') if isinstance(s, dict) else s.is_active
        if is_active:
            active_sources.append(s)

    print(f"OK Found {len(active_sources)} active lead sources:")
    for source in active_sources:
        source_name = source.get('source_name') if isinstance(source, dict) else source.source_name
        source_id = source.get('id') if isinstance(source, dict) else source.id
        print(f"  - {source_name} (ID: {source_id})")
    print()

    # Track overall results
    total_synced = 0
    total_failed = 0
    total_skipped = 0
    source_results = []

    # Sync all supported platforms
    SUPPORTED_PLATFORMS = [
        'Referral Exchange',
        'ReferralExchange',
        'HomeLight',
        'Redfin',
        'Agent Pronto',
        'MyAgentFinder'
    ]

    # Sync each source
    for idx, source in enumerate(active_sources, 1):
        source_name = source.get('source_name') if isinstance(source, dict) else source.source_name
        source_id = source.get('id') if isinstance(source, dict) else source.id

        # Skip unsupported platforms
        if source_name not in SUPPORTED_PLATFORMS:
            print(f"\n{'='*80}")
            print(f"[{idx}/{len(active_sources)}] Skipping: {source_name} (unsupported)")
            print(f"{'='*80}")
            continue

        print(f"\n{'='*80}")
        print(f"[{idx}/{len(active_sources)}] Syncing: {source_name}")
        print(f"{'='*80}")

        # Get all leads for this source
        leads = lead_service.get_by_source(source_name, limit=10000, offset=0)

        if not leads:
            print(f"WARNING  No leads found for {source_name}")
            source_results.append({
                "source": source_name,
                "total": 0,
                "successful": 0,
                "failed": 0,
                "skipped": 0,
                "status": "no_leads"
            })
            continue

        print(f"Found {len(leads)} leads for {source_name}")

        # Get user_id from first lead (assuming all leads belong to same user)
        user_id = leads[0].user_id if hasattr(leads[0], 'user_id') else None
        if not user_id and hasattr(leads[0], 'organization_id'):
            # Try to get user from organization
            print(f"WARNING  No user_id found, using organization_id: {leads[0].organization_id}")
            user_id = str(leads[0].organization_id)

        if not user_id:
            print(f"ERROR Cannot sync {source_name} - no user_id found")
            source_results.append({
                "source": source_name,
                "total": len(leads),
                "successful": 0,
                "failed": len(leads),
                "skipped": 0,
                "status": "no_user_id"
            })
            continue

        # Generate sync ID
        sync_id = str(uuid.uuid4())

        # Start sync with tracker
        print(f"Starting sync with ID: {sync_id}")
        print(f"User ID: {user_id}")
        print(f"Force sync: ENABLED (bypassing 168h minimum interval)")
        print()

        try:
            # Call the sync function with force_sync=True
            lead_source_service.sync_all_sources_bulk_with_tracker(
                sync_id=sync_id,
                source_name=source_name,
                leads=leads,
                user_id=user_id,
                tracker=tracker,
                force_sync=True  # BYPASS MINIMUM INTERVAL
            )

            # Wait for sync to complete (poll tracker)
            max_wait = 120  # 2 minutes max per check
            start_time = time.time()
            last_status = None
            no_change_count = 0
            last_change_time = start_time
            got_first_status = False

            while time.time() - start_time < max_wait:
                status = tracker.get_status(sync_id)

                if status:
                    got_first_status = True
                    # Check if status actually changed
                    if status != last_status:
                        last_change_time = time.time()
                        no_change_count = 0
                    else:
                        no_change_count += 1

                    # If no changes for 30 seconds (15 polls), consider it stuck
                    if no_change_count > 15 and (time.time() - last_change_time) > 30:
                        print(f"WARNING  No status changes for 30s, assuming sync stuck/complete")
                        # Mark as completed with what we have
                        break
                else:
                    # If we haven't gotten ANY status after 30 seconds, platform is hung
                    if not got_first_status and (time.time() - start_time) > 30:
                        print(f"ERROR Platform not responding after 30s - skipping {source_name}")
                        source_results.append({
                            "source": source_name,
                            "total": len(leads),
                            "successful": 0,
                            "failed": 0,
                            "skipped": 0,
                            "status": "timeout"
                        })
                        break

                    # Only print if status changed
                    if status != last_status:
                        if status.get("current_lead"):
                            print(f"  Processing: {status['current_lead']} ({status.get('processed', 0)}/{status.get('total_leads', 0)})")
                        elif status.get("messages") and len(status["messages"]) > 0:
                            latest_msg = status["messages"][-1].get("message", "")
                            if latest_msg and (not last_status or latest_msg not in str(last_status)):
                                print(f"  {latest_msg}")
                        last_status = status.copy()

                    # Check if complete
                    if status.get("status") in ["completed", "failed", "cancelled"]:
                        print()
                        print(f"OK Sync {status['status']}")
                        print(f"  Successful: {status.get('successful', 0)}")
                        print(f"  Failed: {status.get('failed', 0)}")
                        print(f"  Skipped: {status.get('skipped', 0)}")

                        total_synced += status.get('successful', 0)
                        total_failed += status.get('failed', 0)
                        total_skipped += status.get('skipped', 0)

                        source_results.append({
                            "source": source_name,
                            "total": len(leads),
                            "successful": status.get('successful', 0),
                            "failed": status.get('failed', 0),
                            "skipped": status.get('skipped', 0),
                            "status": status['status']
                        })
                        break

                time.sleep(2)  # Poll every 2 seconds
            else:
                print(f"WARNING  Sync timed out after {max_wait} seconds")
                source_results.append({
                    "source": source_name,
                    "total": len(leads),
                    "successful": 0,
                    "failed": 0,
                    "skipped": 0,
                    "status": "timeout"
                })

        except Exception as e:
            print(f"ERROR Error syncing {source_name}: {str(e)}")
            import traceback
            traceback.print_exc()
            source_results.append({
                "source": source_name,
                "total": len(leads),
                "successful": 0,
                "failed": len(leads),
                "skipped": 0,
                "status": "error",
                "error": str(e)
            })

    # Print summary
    print()
    print("="*80)
    print("SYNC COMPLETE - SUMMARY")
    print("="*80)
    print()
    print(f"Total sources synced: {len(source_results)}")
    print(f"Total leads updated: {total_synced}")
    print(f"Total leads failed: {total_failed}")
    print(f"Total leads skipped: {total_skipped}")
    print()

    # Detailed results
    print("Results by source:")
    print("-" * 80)
    for result in source_results:
        status_emoji = "OK" if result["status"] == "completed" else "WARNING" if result["status"] in ["no_leads", "timeout"] else "ERROR"
        print(f"{status_emoji} {result['source']:<25} | Total: {result['total']:>4} | Updated: {result['successful']:>4} | Failed: {result['failed']:>4} | Skipped: {result['skipped']:>4}")
    print()

    if total_failed > 0:
        print(f"WARNING  {total_failed} leads failed to sync. Check the logs for details.")
    else:
        print("OK All leads synced successfully!")

    print()
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

if __name__ == "__main__":
    main()
