"""
Check aliases/mappings for a user
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.supabase_client import SupabaseClientSingleton


def check_aliases(email: str = "adam@saahomes.com"):
    supabase = SupabaseClientSingleton.get_instance()

    # Get user ID
    user_result = supabase.from_("users").select("id").eq("email", email).execute()
    if not user_result.data:
        print(f"User not found: {email}")
        return

    user_id = user_result.data[0]["id"]
    print(f"User: {email} ({user_id})")
    print("=" * 60)

    # Get aliases
    aliases = supabase.table("lead_source_aliases").select("*").eq("user_id", user_id).execute()

    if not aliases.data:
        print("\nNo aliases found (no sources have been merged)")
        return

    print(f"\nFound {len(aliases.data)} alias(es):\n")

    for alias in aliases.data:
        # Get canonical source name
        canonical_id = alias["canonical_source_id"]
        canonical = supabase.table("lead_source_settings").select("source_name").eq("id", canonical_id).execute()
        canonical_name = canonical.data[0]["source_name"] if canonical.data else "Unknown"

        print(f"  '{alias['alias_name']}' -> '{canonical_name}'")
        print(f"    Alias ID: {alias['id']}")
        print(f"    Canonical Source ID: {canonical_id}")
        print()


if __name__ == "__main__":
    check_aliases()
