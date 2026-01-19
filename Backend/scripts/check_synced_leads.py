"""
Check which MAF leads have sync timestamps and their status.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.database.supabase_client import SupabaseClientSingleton

def check_synced_leads():
    """Check which leads have sync timestamps"""
    supabase = SupabaseClientSingleton.get_instance()

    response = supabase.table("leads").select("*").eq("source", "MyAgentFinder").execute()

    if not response.data:
        print("No MyAgentFinder leads found")
        return

    leads = response.data
    print(f"Found {len(leads)} MyAgentFinder leads total\n")

    synced = []
    not_synced = []

    for lead in leads:
        name = lead.get("name") or f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
        status = lead.get("status", "Unknown")
        metadata = lead.get("metadata", {})
        if isinstance(metadata, str):
            import json
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}

        last_synced = metadata.get("myagentfinder_last_updated") if metadata else None

        if last_synced:
            synced.append((name, status, last_synced))
        else:
            not_synced.append((name, status))

    print(f"=== SYNCED ({len(synced)}) ===")
    for name, status, ts in synced:
        print(f"  {name} - {status} (synced: {ts[:19]})")

    print(f"\n=== NOT SYNCED ({len(not_synced)}) ===")
    for name, status in not_synced:
        print(f"  {name} - {status}")

if __name__ == "__main__":
    check_synced_leads()
