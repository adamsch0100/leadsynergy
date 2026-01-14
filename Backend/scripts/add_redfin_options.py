"""
Script to add Redfin status options to the lead_source_settings table.
This enables the stage mapping UI to show Redfin status options.
"""
import os
import sys
import json

# Add Backend directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.database.supabase_client import SupabaseClientSingleton

# Redfin status options for stage mapping
# These match the actual dropdown options on Redfin's partner portal
REDFIN_OPTIONS = {
    "Initial Contact": [
        "Active",
        "Attempted Contact",
    ],
    "In Progress": [
        "In Communication",
        "Showing",
    ],
    "Transaction": [
        "Under Contract",
        "Closed",
    ],
    "Other": [
        "Create Deal",  # Note: This triggers deal creation flow
    ],
}

# Flat format for mapping
REDFIN_OPTIONS_FLAT = [
    {"value": "active", "label": "Active"},
    {"value": "attempted_contact", "label": "Attempted Contact"},
    {"value": "in_communication", "label": "In Communication"},
    {"value": "showing", "label": "Showing"},
    {"value": "under_contract", "label": "Under Contract"},
    {"value": "closed", "label": "Closed"},
    {"value": "create_deal", "label": "Create Deal"},
]


def add_redfin_options(auto_create: bool = False):
    """Add Redfin status options to the database"""
    print("=" * 60)
    print("Adding Redfin Status Options")
    print("=" * 60)

    supabase = SupabaseClientSingleton.get_instance()

    # Find Redfin lead sources
    result = supabase.table("lead_source_settings").select("*").or_(
        "source_name.eq.Redfin,source_name.ilike.%redfin%"
    ).execute()

    if not result.data:
        print("\n[WARNING] No Redfin lead sources found in the database.")
        print("Creating a new Redfin lead source...")

        template_data = {
            "source_name": "Redfin",
            "is_active": False,
            "options": json.dumps(REDFIN_OPTIONS),
            "metadata": json.dumps({
                "status_options": REDFIN_OPTIONS_FLAT,
                "description": "Redfin partner referral platform",
                "login_type": "password_2fa",
                "requires_2fa": True
            }),
            "fub_stage_mapping": json.dumps({})
        }

        try:
            insert_result = supabase.table("lead_source_settings").insert(template_data).execute()
            if insert_result.data:
                print(f"\n[SUCCESS] Created Redfin lead source with ID: {insert_result.data[0]['id']}")
                print("You can now configure it in the admin dashboard.")
        except Exception as e:
            print(f"\n[ERROR] Failed to create lead source: {e}")

        return

    print(f"\nFound {len(result.data)} Redfin lead source(s)")

    for source in result.data:
        source_id = source['id']
        source_name = source['source_name']
        current_options = source.get('options')

        print(f"\n--- Processing: {source_name} (ID: {source_id}) ---")

        if current_options:
            if isinstance(current_options, str):
                try:
                    current_options = json.loads(current_options)
                except:
                    current_options = None
            print(f"Current options: {json.dumps(current_options, indent=2)[:200] if current_options else 'None'}...")
        else:
            print("Current options: None")

        # Update with new options
        update_data = {
            "options": json.dumps(REDFIN_OPTIONS)
        }

        # Also update metadata with flat options
        current_metadata = source.get('metadata')
        if current_metadata:
            if isinstance(current_metadata, str):
                try:
                    current_metadata = json.loads(current_metadata)
                except:
                    current_metadata = {}
        else:
            current_metadata = {}

        current_metadata["status_options"] = REDFIN_OPTIONS_FLAT
        current_metadata["description"] = current_metadata.get("description", "Redfin partner referral platform")
        current_metadata["login_type"] = "password_2fa"
        current_metadata["requires_2fa"] = True

        update_data["metadata"] = json.dumps(current_metadata)

        # Update the database
        try:
            supabase.table("lead_source_settings").update(update_data).eq("id", source_id).execute()
            print(f"[SUCCESS] Updated options for {source_name}")

        except Exception as e:
            print(f"[ERROR] Failed to update {source_name}: {e}")

    print("\n" + "=" * 60)
    print("REDFIN OPTIONS SUMMARY")
    print("=" * 60)
    for category, statuses in REDFIN_OPTIONS.items():
        print(f"\n{category}:")
        for status in statuses:
            print(f"  - {status}")

    print("\n" + "=" * 60)
    print("Done! You can now map FUB stages to Redfin statuses")
    print("in the Admin > Stage Mapping page.")
    print("NOTE: 'Create Deal' requires manual handling (not automated).")
    print("=" * 60)


def show_current_options():
    """Show current Redfin options in database"""
    print("=" * 60)
    print("Current Redfin Options in Database")
    print("=" * 60)

    supabase = SupabaseClientSingleton.get_instance()
    result = supabase.table("lead_source_settings").select("*").or_(
        "source_name.eq.Redfin,source_name.ilike.%redfin%"
    ).execute()

    if not result.data:
        print("\nNo Redfin lead sources found.")
        return

    for source in result.data:
        print(f"\n--- {source['source_name']} (ID: {source['id']}) ---")
        options = source.get('options')
        if options:
            if isinstance(options, str):
                options = json.loads(options)
            print(json.dumps(options, indent=2))
        else:
            print("No options configured")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Add Redfin status options to database")
    parser.add_argument("--add", action="store_true", help="Add/update options in database")
    parser.add_argument("--show", action="store_true", help="Show current options in database")

    args = parser.parse_args()

    if args.show:
        show_current_options()
    elif args.add:
        add_redfin_options()
    else:
        print("Usage: python add_redfin_options.py [--add | --show]")
        print("\nAvailable Redfin options:")
        for category, statuses in REDFIN_OPTIONS.items():
            print(f"\n{category}:")
            for status in statuses:
                print(f"  - {status}")
