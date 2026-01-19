"""
Reset sync timestamp for specific failed MAF leads so they can be re-synced.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.database.supabase_client import SupabaseClientSingleton

# Failed leads from the last sync + overdue leads from MAF
FAILED_LEADS = [
    # Failed in sync
    "Bill Sasso",
    "Brendan Klover",
    "Crystal Mullins",
    "Serenity Hidalgo",
    "Mark Pelletier",
    "Roberto Godoy",
    "Jade Wilson",
    "Ginger Young",
    # Overdue on MAF (dates not updated)
    "Kim Myers",
    "Steven VanDeventer",
    "Aayan Malik",
    "Joseph Negley",
]

def reset_failed_leads():
    """Reset sync timestamp for failed leads"""
    supabase = SupabaseClientSingleton.get_instance()

    print("Finding failed leads to reset...")

    response = supabase.table("leads").select("*").eq("source", "MyAgentFinder").execute()

    if not response.data:
        print("No MyAgentFinder leads found")
        return

    leads = response.data
    print(f"Found {len(leads)} MyAgentFinder leads total")

    reset_count = 0
    for lead in leads:
        name = lead.get("name") or f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()

        # Check if this is one of our failed leads
        if any(failed_name.lower() in name.lower() for failed_name in FAILED_LEADS):
            lead_id = lead.get("id")
            metadata = lead.get("metadata", {})
            if isinstance(metadata, str):
                import json
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}

            # Clear the sync timestamp
            if metadata and "myagentfinder_last_updated" in metadata:
                del metadata["myagentfinder_last_updated"]

                try:
                    supabase.table("leads").update({"metadata": metadata}).eq("id", lead_id).execute()
                    print(f"  Reset: {name}")
                    reset_count += 1
                except Exception as e:
                    print(f"  Error resetting {name}: {e}")
            else:
                print(f"  {name} - no sync timestamp to clear")

    print(f"\nDone! {reset_count} leads reset.")
    print("Now run a sync from the frontend to re-update them.")

if __name__ == "__main__":
    reset_failed_leads()
