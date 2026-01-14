"""
Script to add Agent Pronto status options to the lead_source_settings table.
This enables the stage mapping UI to show Agent Pronto status options.
"""
import os
import sys
import json

# Add Backend directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.supabase_client import SupabaseClientSingleton

# Agent Pronto status options for stage mapping
# These match the actual options on the Agent Pronto status update page
AGENT_PRONTO_OPTIONS = {
    "Active": [
        "Communicating with referral",
        "Showing properties in person",
        "Offer accepted"
    ],
    "Lost/Archived": [
        "I was never able to contact this referral",
        "They're no longer buying / selling a property",
        "They already have an agent",
        "They became unresponsive",
        "They don't have the means to buy",
        "The listing expired or was cancelled",
        "Other"
    ]
}

# Alternative flat format for simpler mapping
AGENT_PRONTO_OPTIONS_FLAT = [
    {"value": "Communicating with referral", "label": "Active - Communicating with referral"},
    {"value": "Showing properties in person", "label": "Active - Showing properties in person"},
    {"value": "Offer accepted", "label": "Active - Offer accepted"},
    {"value": "agent_did_not_make_contact", "label": "Lost - Never able to contact"},
    {"value": "no_longer_buying_or_selling", "label": "Lost - No longer buying/selling"},
    {"value": "already_has_agent", "label": "Lost - Already has an agent"},
    {"value": "unresponsive", "label": "Lost - Became unresponsive"},
    {"value": "denied_loan_approval", "label": "Lost - Can't afford to buy"},
    {"value": "listing_expired_or_cancelled", "label": "Lost - Listing expired/cancelled"},
    {"value": "other", "label": "Lost - Other reason"}
]


def add_agent_pronto_options():
    """Add Agent Pronto status options to the database"""
    print("=" * 60)
    print("Adding Agent Pronto Status Options")
    print("=" * 60)

    supabase = SupabaseClientSingleton.get_instance()

    # Find Agent Pronto lead sources
    result = supabase.table("lead_source_settings").select("*").or_(
        "source_name.eq.AgentPronto,source_name.eq.Agent Pronto"
    ).execute()

    if not result.data:
        print("\n[WARNING] No Agent Pronto lead sources found in the database.")
        print("You may need to create an Agent Pronto lead source first.")
        print("\nWould you like to create a template entry? (This won't be active)")

        create_template = input("Create template? (y/n): ").strip().lower()
        if create_template == 'y':
            # Create a template entry
            template_data = {
                "source_name": "AgentPronto",
                "is_active": False,
                "options": json.dumps(AGENT_PRONTO_OPTIONS),
                "metadata": json.dumps({
                    "status_options": AGENT_PRONTO_OPTIONS_FLAT,
                    "description": "Agent Pronto referral platform",
                    "requires_magic_link": True
                }),
                "fub_stage_mapping": json.dumps({})
            }

            try:
                insert_result = supabase.table("lead_source_settings").insert(template_data).execute()
                if insert_result.data:
                    print(f"\n[SUCCESS] Created Agent Pronto template with ID: {insert_result.data[0]['id']}")
                    print("You can now configure it in the admin dashboard.")
            except Exception as e:
                print(f"\n[ERROR] Failed to create template: {e}")

        return

    print(f"\nFound {len(result.data)} Agent Pronto lead source(s)")

    for source in result.data:
        source_id = source['id']
        source_name = source['source_name']
        current_options = source.get('options')

        print(f"\n--- Processing: {source_name} (ID: {source_id}) ---")

        # Parse current options if they exist
        if current_options:
            if isinstance(current_options, str):
                try:
                    current_options = json.loads(current_options)
                except:
                    current_options = None
            print(f"Current options: {json.dumps(current_options, indent=2)[:200]}...")
        else:
            print("Current options: None")

        # Update with new options
        update_data = {
            "options": json.dumps(AGENT_PRONTO_OPTIONS)
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

        current_metadata["status_options"] = AGENT_PRONTO_OPTIONS_FLAT
        current_metadata["description"] = current_metadata.get("description", "Agent Pronto referral platform")
        current_metadata["requires_magic_link"] = True

        update_data["metadata"] = json.dumps(current_metadata)

        # Update the database
        try:
            update_result = supabase.table("lead_source_settings").update(
                update_data
            ).eq("id", source_id).execute()

            if update_result.data:
                print(f"[SUCCESS] Updated options for {source_name}")
            else:
                print(f"[WARNING] No data returned for update on {source_name}")

        except Exception as e:
            print(f"[ERROR] Failed to update {source_name}: {e}")

    print("\n" + "=" * 60)
    print("AGENT PRONTO OPTIONS SUMMARY")
    print("=" * 60)
    print("\nActive Statuses (keeps deal in progress):")
    for status in AGENT_PRONTO_OPTIONS["Active"]:
        print(f"  - {status}")

    print("\nLost/Archived Statuses (archives the deal):")
    for status in AGENT_PRONTO_OPTIONS["Lost/Archived"]:
        print(f"  - {status}")

    print("\n" + "=" * 60)
    print("Done! You can now map FUB stages to Agent Pronto statuses")
    print("in the Admin > Stage Mapping page.")
    print("=" * 60)


def show_current_options():
    """Show current Agent Pronto options in database"""
    print("=" * 60)
    print("Current Agent Pronto Configuration")
    print("=" * 60)

    supabase = SupabaseClientSingleton.get_instance()

    result = supabase.table("lead_source_settings").select("*").or_(
        "source_name.eq.AgentPronto,source_name.eq.Agent Pronto"
    ).execute()

    if not result.data:
        print("\nNo Agent Pronto lead sources found in the database.")
        return

    for source in result.data:
        print(f"\n--- {source['source_name']} (ID: {source['id']}) ---")
        print(f"Active: {source.get('is_active', False)}")

        options = source.get('options')
        if options:
            if isinstance(options, str):
                try:
                    options = json.loads(options)
                except:
                    pass
            print(f"Options: {json.dumps(options, indent=2)}")
        else:
            print("Options: None")

        metadata = source.get('metadata')
        if metadata:
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except:
                    pass
            print(f"Metadata: {json.dumps(metadata, indent=2)}")

        fub_mapping = source.get('fub_stage_mapping')
        if fub_mapping:
            if isinstance(fub_mapping, str):
                try:
                    fub_mapping = json.loads(fub_mapping)
                except:
                    pass
            print(f"FUB Stage Mapping: {json.dumps(fub_mapping, indent=2)}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage Agent Pronto options in database")
    parser.add_argument("--show", action="store_true", help="Show current configuration")
    parser.add_argument("--add", action="store_true", help="Add/update Agent Pronto options")

    args = parser.parse_args()

    if args.show:
        show_current_options()
    elif args.add:
        add_agent_pronto_options()
    else:
        # Default: show then add
        show_current_options()
        print("\n" + "=" * 60 + "\n")

        proceed = input("Update Agent Pronto options? (y/n): ").strip().lower()
        if proceed == 'y':
            add_agent_pronto_options()
