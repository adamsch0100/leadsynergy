"""
Fix stage mappings to include required sub-options for ReferralExchange.
The mappings currently only have main categories but need full main::sub format.
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.supabase_client import SupabaseClientSingleton

# Default sub-options for each main category
DEFAULT_SUB_OPTIONS = {
    "No interaction yet": "I am still trying to contact",
    "We are in contact": "is open to working with me",
    "Listing / showing properties": "I am showing properties",  # For buyers
    "Transaction in progress": "We are in escrow",
    "No longer working this referral": "is unresponsive"
}


def fix_stage_mappings(user_email: str = "adam@saahomes.com", dry_run: bool = True):
    """
    Fix stage mappings for ReferralExchange to include sub-options.
    """
    print("=" * 70)
    print("FIX STAGE MAPPINGS FOR REFERRAL EXCHANGE")
    if dry_run:
        print("(DRY RUN - no changes will be made)")
    print("=" * 70)

    supabase = SupabaseClientSingleton.get_instance()

    # Get user ID
    user_result = supabase.from_("users").select("id").eq("email", user_email).execute()
    if not user_result.data:
        print(f"User not found: {user_email}")
        return

    user_id = user_result.data[0]["id"]
    print(f"User: {user_email} ({user_id})")

    # Get ReferralExchange sources
    sources = supabase.table("lead_source_settings").select("*").eq("user_id", user_id).or_(
        "source_name.eq.Referral Exchange,source_name.eq.ReferralExchange"
    ).execute()

    if not sources.data:
        print("No ReferralExchange sources found")
        return

    print(f"\nFound {len(sources.data)} ReferralExchange source(s)")

    for source in sources.data:
        source_id = source["id"]
        source_name = source["source_name"]

        print(f"\n--- {source_name} (ID: {source_id}) ---")

        # Get current mapping
        current_mapping = source.get("fub_stage_mapping")
        if current_mapping:
            if isinstance(current_mapping, str):
                try:
                    current_mapping = json.loads(current_mapping)
                except:
                    print(f"  Error parsing mapping: {current_mapping}")
                    continue

        if not current_mapping:
            print("  No current mapping")
            continue

        print(f"  Current mapping:")
        for fub_stage, platform_status in current_mapping.items():
            print(f"    {fub_stage} -> {platform_status}")

        # Fix mappings
        new_mapping = {}
        changes = []

        for fub_stage, platform_status in current_mapping.items():
            if "::" in platform_status:
                # Already has sub-option
                new_mapping[fub_stage] = platform_status
            else:
                # Need to add sub-option
                main_category = platform_status
                if main_category in DEFAULT_SUB_OPTIONS:
                    sub_option = DEFAULT_SUB_OPTIONS[main_category]
                    new_value = f"{main_category}::{sub_option}"
                    new_mapping[fub_stage] = new_value
                    changes.append(f"  {fub_stage}: '{platform_status}' -> '{new_value}'")
                else:
                    # Keep as-is if we don't have a default
                    new_mapping[fub_stage] = platform_status
                    print(f"  WARNING: No default sub-option for '{main_category}'")

        if changes:
            print(f"\n  Changes to be made:")
            for change in changes:
                print(change)

            if not dry_run:
                # Update the database
                update_result = supabase.table("lead_source_settings").update({
                    "fub_stage_mapping": json.dumps(new_mapping)
                }).eq("id", source_id).execute()

                if update_result.data:
                    print(f"\n  [SUCCESS] Updated mapping")
                else:
                    print(f"\n  [ERROR] Failed to update mapping")
            else:
                print(f"\n  [DRY RUN] Would update mapping")
        else:
            print(f"\n  No changes needed")

    print("\n" + "=" * 70)
    if dry_run:
        print("This was a DRY RUN. Run with --apply to make changes.")
    print("=" * 70)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fix stage mappings for ReferralExchange")
    parser.add_argument("--user-email", type=str, default="adam@saahomes.com", help="User email")
    parser.add_argument("--apply", action="store_true", help="Actually apply changes")

    args = parser.parse_args()

    fix_stage_mappings(user_email=args.user_email, dry_run=not args.apply)
