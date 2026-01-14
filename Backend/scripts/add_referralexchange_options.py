"""
Script to add ReferralExchange status options to the lead_source_settings table.
This enables the stage mapping UI to show ReferralExchange status options.

Note: ReferralExchange uses a two-tier status system:
  - Main option (e.g., "We are in contact")
  - Sub option (e.g., "is open to working with me")

The format stored is: "Main Option::Sub Option"
"""
import os
import sys
import json

# Add Backend directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.database.supabase_client import SupabaseClientSingleton

# ReferralExchange status options for stage mapping
# These match the actual dropdown options on ReferralExchange's status update modal
# Format: Main Option -> List of Sub Options
REFERRALEXCHANGE_OPTIONS = {
    "No interaction yet": [
        "I am still trying to contact",
    ],
    "We are in contact": [
        "I have an appointment with",
        "is open to working with me",
        "does not want to work with me",
    ],
    "Listing / showing properties": [
        "I am also helping to sell",
        "I am showing properties",
    ],
    "Transaction in progress": [
        "We are in escrow",
        "We have closed escrow",
    ],
    "No longer working this referral": [
        "is no longer my client",
        "is unresponsive",
        "has another agent",
        "I have prior relationship with",
        "Other",
    ],
}

# Flat format for mapping - uses "Main::Sub" format
REFERRALEXCHANGE_OPTIONS_FLAT = [
    # No interaction yet
    {"value": "No interaction yet::I am still trying to contact", "label": "No interaction yet - I am still trying to contact"},

    # We are in contact
    {"value": "We are in contact::I have an appointment with", "label": "We are in contact - I have an appointment with"},
    {"value": "We are in contact::is open to working with me", "label": "We are in contact - is open to working with me"},
    {"value": "We are in contact::does not want to work with me", "label": "We are in contact - does not want to work with me"},

    # Listing / showing properties
    {"value": "Listing / showing properties::I am also helping to sell", "label": "Listing/showing - I am also helping to sell"},
    {"value": "Listing / showing properties::I am showing properties", "label": "Listing/showing - I am showing properties"},

    # Transaction in progress
    {"value": "Transaction in progress::We are in escrow", "label": "Transaction - We are in escrow"},
    {"value": "Transaction in progress::We have closed escrow", "label": "Transaction - We have closed escrow"},

    # No longer working this referral
    {"value": "No longer working this referral::is no longer my client", "label": "No longer working - is no longer my client"},
    {"value": "No longer working this referral::is unresponsive", "label": "No longer working - is unresponsive"},
    {"value": "No longer working this referral::has another agent", "label": "No longer working - has another agent"},
    {"value": "No longer working this referral::I have prior relationship with", "label": "No longer working - I have prior relationship with"},
    {"value": "No longer working this referral::Other", "label": "No longer working - Other"},
]


def add_referralexchange_options(auto_create: bool = False):
    """Add ReferralExchange status options to the database"""
    print("=" * 60)
    print("Adding ReferralExchange Status Options")
    print("=" * 60)

    supabase = SupabaseClientSingleton.get_instance()

    # Find ReferralExchange lead sources
    result = supabase.table("lead_source_settings").select("*").or_(
        "source_name.eq.ReferralExchange,source_name.eq.Referral Exchange,source_name.ilike.%referralexchange%,source_name.ilike.%referral exchange%"
    ).execute()

    if not result.data:
        print("\n[WARNING] No ReferralExchange lead sources found in the database.")
        print("Creating a new ReferralExchange lead source...")

        template_data = {
            "source_name": "ReferralExchange",
            "is_active": False,
            "options": json.dumps(REFERRALEXCHANGE_OPTIONS),
            "metadata": json.dumps({
                "status_options": REFERRALEXCHANGE_OPTIONS_FLAT,
                "description": "ReferralExchange referral platform",
                "login_type": "password",
                "two_tier_status": True,
                "status_format": "main::sub"
            }),
            "fub_stage_mapping": json.dumps({})
        }

        try:
            insert_result = supabase.table("lead_source_settings").insert(template_data).execute()
            if insert_result.data:
                print(f"\n[SUCCESS] Created ReferralExchange lead source with ID: {insert_result.data[0]['id']}")
                print("You can now configure it in the admin dashboard.")
        except Exception as e:
            print(f"\n[ERROR] Failed to create lead source: {e}")

        return

    print(f"\nFound {len(result.data)} ReferralExchange lead source(s)")

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
            "options": json.dumps(REFERRALEXCHANGE_OPTIONS)
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

        current_metadata["status_options"] = REFERRALEXCHANGE_OPTIONS_FLAT
        current_metadata["description"] = current_metadata.get("description", "ReferralExchange referral platform")
        current_metadata["login_type"] = "password"
        current_metadata["two_tier_status"] = True
        current_metadata["status_format"] = "main::sub"

        update_data["metadata"] = json.dumps(current_metadata)

        # Update the database
        try:
            supabase.table("lead_source_settings").update(update_data).eq("id", source_id).execute()
            print(f"[SUCCESS] Updated options for {source_name}")

        except Exception as e:
            print(f"[ERROR] Failed to update {source_name}: {e}")

    print("\n" + "=" * 60)
    print("REFERRALEXCHANGE OPTIONS SUMMARY")
    print("=" * 60)
    print("\nFormat: Main Option -> Sub Options")
    print("Status stored as: 'Main Option::Sub Option'")
    print("-" * 40)
    for main_option, sub_options in REFERRALEXCHANGE_OPTIONS.items():
        print(f"\n{main_option}:")
        for sub in sub_options:
            print(f"  - {sub}")

    print("\n" + "=" * 60)
    print("Done! You can now map FUB stages to ReferralExchange statuses")
    print("in the Admin > Stage Mapping page.")
    print("=" * 60)


def show_current_options():
    """Show current ReferralExchange options in database"""
    print("=" * 60)
    print("Current ReferralExchange Options in Database")
    print("=" * 60)

    supabase = SupabaseClientSingleton.get_instance()
    result = supabase.table("lead_source_settings").select("*").or_(
        "source_name.eq.ReferralExchange,source_name.eq.Referral Exchange,source_name.ilike.%referralexchange%"
    ).execute()

    if not result.data:
        print("\nNo ReferralExchange lead sources found.")
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

    parser = argparse.ArgumentParser(description="Add ReferralExchange status options to database")
    parser.add_argument("--add", action="store_true", help="Add/update options in database")
    parser.add_argument("--show", action="store_true", help="Show current options in database")

    args = parser.parse_args()

    if args.show:
        show_current_options()
    elif args.add:
        add_referralexchange_options()
    else:
        print("Usage: python add_referralexchange_options.py [--add | --show]")
        print("\nAvailable ReferralExchange options:")
        print("\nFormat: Main Option -> Sub Options")
        for main_option, sub_options in REFERRALEXCHANGE_OPTIONS.items():
            print(f"\n{main_option}:")
            for sub in sub_options:
                print(f"  - {sub}")
