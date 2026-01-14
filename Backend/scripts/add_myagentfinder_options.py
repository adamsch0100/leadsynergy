"""
Script to add My Agent Finder status options to the lead_source_settings table.
This enables the stage mapping UI to show My Agent Finder status options.

Note: My Agent Finder has different options for Buyer vs Seller referrals.
The service auto-detects the referral type at runtime and uses the correct status.
Options are organized by Buyer and Seller for clarity.
"""
import os
import sys
import json

# Add Backend directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.database.supabase_client import SupabaseClientSingleton

# My Agent Finder status options for stage mapping
# Organized by Buyer and Seller for clear separation
# Format: { "Category": ["status_key1", "status_key2", ...] }
# The frontend will display as "Category • status_key"

MYAGENTFINDER_OPTIONS = {
    # ===== BUYER OPTIONS =====
    "Buyer - Assigned": [
        "trying_to_reach",
    ],
    "Buyer - Prospect": [
        "communicating",
        "appointment",
        "lender",
    ],
    "Buyer - Client": [
        "showing",
        "offer",
        "mls_search",
    ],
    "Buyer - In Escrow": [
        "in_escrow",
    ],
    "Buyer - Closed": [
        "closed",
    ],
    "Buyer - Nurture": [
        "nurture",
        "nurture_mls",
    ],
    "Buyer - No Longer Engaged": [
        "another_agent",
        "unresponsive",
        "not_engaged",
        "other",
    ],

    # ===== SELLER OPTIONS =====
    "Seller - Assigned": [
        "trying_to_reach",
    ],
    "Seller - Prospect": [
        "communicating",
        "listing_appointment",
    ],
    "Seller - Listed": [
        "listing_agreement",
        "listed",
    ],
    "Seller - In Escrow": [
        "in_escrow",
    ],
    "Seller - Closed": [
        "closed",
    ],
    "Seller - Nurture": [
        "nurture",
        "nurture_mls",
    ],
    "Seller - No Longer Engaged": [
        "another_agent",
        "unresponsive",
        "not_engaged",
        "other",
    ],
}

# Flat format with descriptive labels (for metadata)
MYAGENTFINDER_OPTIONS_FLAT = [
    # Buyer options
    {"value": "trying_to_reach", "label": "Assigned - Trying to reach client"},
    {"value": "communicating", "label": "Prospect - Communicating with client"},
    {"value": "appointment", "label": "Prospect - Appointment to show (Buyer)"},
    {"value": "lender", "label": "Prospect - Connected to lender (Buyer)"},
    {"value": "showing", "label": "Client - Showing properties (Buyer)"},
    {"value": "offer", "label": "Client - Submitted offer (Buyer)"},
    {"value": "mls_search", "label": "Client - MLS search setup"},
    # Seller options
    {"value": "listing_appointment", "label": "Prospect - Listing appointment (Seller)"},
    {"value": "listing_agreement", "label": "Listed - Signed listing agreement (Seller)"},
    {"value": "listed", "label": "Listed - Property listed (Seller)"},
    # Common options
    {"value": "in_escrow", "label": "In Escrow"},
    {"value": "closed", "label": "Closed Escrow - Sold!"},
    {"value": "nurture", "label": "Nurture - Long term"},
    {"value": "nurture_mls", "label": "Nurture - MLS search setup"},
    {"value": "another_agent", "label": "No Longer Engaged - Has another agent"},
    {"value": "unresponsive", "label": "No Longer Engaged - Unresponsive"},
    {"value": "not_engaged", "label": "No Longer Engaged - Unable to attend"},
    {"value": "other", "label": "No Longer Engaged - Other"},
]


def add_myagentfinder_options(auto_create: bool = False):
    """Add My Agent Finder status options to the database"""
    print("=" * 60)
    print("Adding My Agent Finder Status Options")
    print("=" * 60)

    supabase = SupabaseClientSingleton.get_instance()

    # Find My Agent Finder lead sources
    result = supabase.table("lead_source_settings").select("*").or_(
        "source_name.eq.MyAgentFinder,source_name.eq.My Agent Finder,source_name.ilike.%myagentfinder%"
    ).execute()

    if not result.data:
        print("\n[WARNING] No My Agent Finder lead sources found in the database.")
        print("Creating a new My Agent Finder lead source...")

        template_data = {
            "source_name": "MyAgentFinder",
            "is_active": False,
            "options": json.dumps(MYAGENTFINDER_OPTIONS),
            "metadata": json.dumps({
                "status_options": MYAGENTFINDER_OPTIONS_FLAT,
                "description": "My Agent Finder referral platform",
                "login_type": "password",
                "supports_buyer_seller": True,
                "note": "Service auto-detects buyer/seller type and uses correct status strings"
            }),
            "fub_stage_mapping": json.dumps({})
        }

        try:
            insert_result = supabase.table("lead_source_settings").insert(template_data).execute()
            if insert_result.data:
                print(f"\n[SUCCESS] Created My Agent Finder lead source with ID: {insert_result.data[0]['id']}")
                print("You can now configure it in the admin dashboard.")
        except Exception as e:
            print(f"\n[ERROR] Failed to create lead source: {e}")

        return

    print(f"\nFound {len(result.data)} My Agent Finder lead source(s)")

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
            print(f"Current options type: {type(current_options).__name__}")

        # Update with new options (proper category format)
        update_data = {
            "options": json.dumps(MYAGENTFINDER_OPTIONS)
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

        current_metadata["status_options"] = MYAGENTFINDER_OPTIONS_FLAT
        current_metadata["description"] = current_metadata.get("description", "My Agent Finder referral platform")
        current_metadata["login_type"] = "password"
        current_metadata["supports_buyer_seller"] = True
        current_metadata["note"] = "Service auto-detects buyer/seller type and uses correct status strings"

        update_data["metadata"] = json.dumps(current_metadata)

        # Update the database
        try:
            supabase.table("lead_source_settings").update(update_data).eq("id", source_id).execute()
            print(f"[SUCCESS] Updated options for {source_name}")

        except Exception as e:
            print(f"[ERROR] Failed to update {source_name}: {e}")

    print("\n" + "=" * 60)
    print("MY AGENT FINDER OPTIONS SUMMARY")
    print("=" * 60)
    print("\nNote: The service auto-detects Buyer vs Seller referrals")
    print("and uses the appropriate status strings at runtime.")
    print("-" * 40)

    print("\n===== BUYER OPTIONS =====")
    for category, statuses in MYAGENTFINDER_OPTIONS.items():
        if category.startswith("Buyer"):
            print(f"\n{category}:")
            for status in statuses:
                label = next((o["label"] for o in MYAGENTFINDER_OPTIONS_FLAT if o["value"] == status), status)
                print(f"  - {status}: {label}")

    print("\n===== SELLER OPTIONS =====")
    for category, statuses in MYAGENTFINDER_OPTIONS.items():
        if category.startswith("Seller"):
            print(f"\n{category}:")
            for status in statuses:
                label = next((o["label"] for o in MYAGENTFINDER_OPTIONS_FLAT if o["value"] == status), status)
                print(f"  - {status}: {label}")

    print("\n" + "=" * 60)
    print("Done! You can now map FUB stages to My Agent Finder statuses")
    print("in the Admin > Stage Mapping page.")
    print("=" * 60)


def show_current_options():
    """Show current My Agent Finder options in database"""
    print("=" * 60)
    print("Current My Agent Finder Options in Database")
    print("=" * 60)

    supabase = SupabaseClientSingleton.get_instance()
    result = supabase.table("lead_source_settings").select("*").or_(
        "source_name.eq.MyAgentFinder,source_name.eq.My Agent Finder,source_name.ilike.%myagentfinder%"
    ).execute()

    if not result.data:
        print("\nNo My Agent Finder lead sources found.")
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

    parser = argparse.ArgumentParser(description="Add My Agent Finder status options to database")
    parser.add_argument("--add", action="store_true", help="Add/update options in database")
    parser.add_argument("--show", action="store_true", help="Show current options in database")

    args = parser.parse_args()

    if args.show:
        show_current_options()
    elif args.add:
        add_myagentfinder_options()
    else:
        print("Usage: python add_myagentfinder_options.py [--add | --show]")
        print("\nAvailable My Agent Finder options:")
        print("\n===== BUYER =====")
        for category, statuses in MYAGENTFINDER_OPTIONS.items():
            if category.startswith("Buyer"):
                print(f"\n{category}:")
                for status in statuses:
                    print(f"  - {status}")
        print("\n===== SELLER =====")
        for category, statuses in MYAGENTFINDER_OPTIONS.items():
            if category.startswith("Seller"):
                print(f"\n{category}:")
                for status in statuses:
                    print(f"  - {status}")
