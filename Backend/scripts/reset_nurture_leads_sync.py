"""
One-time script to reset sync timestamp for MAF leads
so they can be re-synced with the correct future date for Nurture status.

Run this script, then trigger a sync to fix the dates.
"""
import os
import sys

# Add the parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.database.supabase_client import SupabaseClientSingleton

def reset_all_synced_leads():
    """Reset sync timestamp for all recently synced MAF leads"""
    supabase = SupabaseClientSingleton.get_instance()

    print("Finding MyAgentFinder leads to reset...")

    response = supabase.table("leads").select("*").eq("source", "MyAgentFinder").execute()

    if not response.data:
        print("No MyAgentFinder leads found")
        return

    leads = response.data
    print(f"Found {len(leads)} MyAgentFinder leads total")

    # Filter to leads that have sync timestamp
    leads_to_reset = []
    for lead in leads:
        metadata = lead.get("metadata", {})
        if isinstance(metadata, str):
            import json
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}

        if metadata and metadata.get("myagentfinder_last_updated"):
            lead['_metadata'] = metadata
            leads_to_reset.append(lead)

    if not leads_to_reset:
        print("\nNo synced leads found to reset")
        return

    print(f"\n{len(leads_to_reset)} leads will be reset:")
    for lead in leads_to_reset:
        print(f"  - {lead.get('name')} (status: {lead.get('status')})")

    # Reset all of them
    print(f"\nResetting {len(leads_to_reset)} leads...")

    reset_count = 0
    for lead in leads_to_reset:
        lead_id = lead.get("id")
        metadata = lead.get("_metadata", {}).copy()

        # Remove the sync timestamp
        if "myagentfinder_last_updated" in metadata:
            del metadata["myagentfinder_last_updated"]

        # Update the lead
        try:
            supabase.table("leads").update({"metadata": metadata}).eq("id", lead_id).execute()
            print(f"  Reset: {lead.get('name')}")
            reset_count += 1
        except Exception as e:
            print(f"  Error resetting {lead.get('name')}: {e}")

    print(f"\nDone! {reset_count} leads reset.")
    print("Now run a sync from the frontend to re-update them with the correct 6-month date.")

if __name__ == "__main__":
    reset_all_synced_leads()
