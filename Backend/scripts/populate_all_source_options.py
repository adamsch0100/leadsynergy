"""
Script to populate status options for all supported lead source platforms.
This restores the options that are needed for the stage mapping UI.
"""
import os
import sys
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.supabase_client import SupabaseClientSingleton

# =============================================================================
# PLATFORM OPTIONS DEFINITIONS
# =============================================================================

# ReferralExchange options - format: "Main Category::Sub Option"
# The lead name gets substituted at runtime
# Includes both Buyer and Seller specific options
REFERRAL_EXCHANGE_OPTIONS = {
    "No interaction yet": [
        "I am still trying to contact"
    ],
    "We are in contact": [
        "I have an appointment with",
        "is open to working with me",
        "does not want to work with me"
    ],
    "Listing / showing properties": [
        # Buyer options
        "I am also helping to sell",
        "I am showing properties",
        # Seller options
        "I am also helping to buy",
        "I have property listed"
    ],
    "Transaction in progress": [
        "We are in escrow",
        "We have closed escrow"
    ],
    "No longer working this referral": [
        "is no longer my client",
        "is unresponsive",
        "has another agent",
        "I have a prior relationship with",
        "Other"
    ]
}

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

# MyAgentFinder options (approximation - may need verification)
MY_AGENT_FINDER_OPTIONS = {
    "In Progress": [
        "Contacting Lead",
        "Showing Properties",
        "Writing Offer",
        "In Escrow"
    ],
    "Closed": [
        "Deal Closed",
        "Lost - Unresponsive",
        "Lost - Chose Another Agent",
        "Lost - Not Ready",
        "Lost - Other"
    ]
}

# Redfin options (approximation - may need verification)
REDFIN_OPTIONS = {
    "Active": [
        "Initial Contact",
        "Showing Properties",
        "Writing Offer",
        "In Escrow"
    ],
    "Inactive": [
        "Closed",
        "Lost",
        "On Hold"
    ]
}

# Platform name variations to match
PLATFORM_MAPPINGS = {
    "referralexchange": {
        "names": ["ReferralExchange", "Referral Exchange", "referralexchange", "referral exchange"],
        "options": REFERRAL_EXCHANGE_OPTIONS,
        "platform_name": "ReferralExchange"
    },
    "agentpronto": {
        "names": ["AgentPronto", "Agent Pronto", "agentpronto", "agent pronto"],
        "options": AGENT_PRONTO_OPTIONS,
        "platform_name": "AgentPronto"
    },
    "myagentfinder": {
        "names": ["MyAgentFinder", "myagentfinder", "MAF", "MyAgentFinder.com", "myagentfinder.com"],
        "options": MY_AGENT_FINDER_OPTIONS,
        "platform_name": "MyAgentFinder"
    },
    "redfin": {
        "names": ["Redfin", "redfin"],
        "options": REDFIN_OPTIONS,
        "platform_name": "Redfin"
    }
}


def get_platform_for_source(source_name: str) -> dict:
    """Find matching platform config for a source name"""
    source_lower = source_name.lower().replace(" ", "")

    for platform_key, config in PLATFORM_MAPPINGS.items():
        for name in config["names"]:
            if name.lower().replace(" ", "") == source_lower:
                return config

    return None


def populate_source_options(user_id: str = None, dry_run: bool = True, force: bool = False):
    """
    Populate options for all lead sources.

    Args:
        user_id: Optional - only update sources for this user
        dry_run: If True, only show what would be updated
        force: If True, overwrite existing options
    """
    print("=" * 70)
    print("POPULATE LEAD SOURCE OPTIONS")
    if force:
        print("(FORCE MODE - will overwrite existing options)")
    print("=" * 70)

    supabase = SupabaseClientSingleton.get_instance()

    # Get lead sources
    query = supabase.table("lead_source_settings").select("*")
    if user_id:
        query = query.eq("user_id", user_id)

    result = query.execute()

    if not result.data:
        print("No lead sources found")
        return

    print(f"\nFound {len(result.data)} lead source(s)")

    updated = 0
    skipped = 0

    for source in result.data:
        source_id = source['id']
        source_name = source['source_name']
        current_options = source.get('options')

        # Find matching platform
        platform_config = get_platform_for_source(source_name)

        if not platform_config:
            print(f"\n  [{source_name}] - No platform match, skipping")
            skipped += 1
            continue

        print(f"\n  [{source_name}] - Matched platform: {platform_config['platform_name']}")

        # Check if already has options (skip if not forcing)
        if current_options and not force:
            if isinstance(current_options, str):
                try:
                    current_options = json.loads(current_options)
                except:
                    current_options = None

            if current_options:
                print(f"    Already has options: {str(current_options)[:100]}...")
                skipped += 1
                continue
        elif current_options and force:
            print(f"    Overwriting existing options (force mode)")

        # Prepare update
        new_options = platform_config['options']

        # Parse existing metadata
        current_metadata = source.get('metadata')
        if current_metadata:
            if isinstance(current_metadata, str):
                try:
                    current_metadata = json.loads(current_metadata)
                except:
                    current_metadata = {}
        else:
            current_metadata = {}

        # Add platform name to metadata
        current_metadata['platform_name'] = platform_config['platform_name']

        if dry_run:
            print(f"    [DRY RUN] Would update with options:")
            print(f"    {json.dumps(new_options, indent=2)[:200]}...")
        else:
            # Update the database
            try:
                update_data = {
                    "options": json.dumps(new_options),
                    "metadata": json.dumps(current_metadata)
                }

                update_result = supabase.table("lead_source_settings").update(
                    update_data
                ).eq("id", source_id).execute()

                if update_result.data:
                    print(f"    [SUCCESS] Updated options")
                    updated += 1
                else:
                    print(f"    [WARNING] No data returned from update")

            except Exception as e:
                print(f"    [ERROR] Failed to update: {e}")

    print("\n" + "=" * 70)
    print(f"SUMMARY: Updated={updated}, Skipped={skipped}")
    if dry_run:
        print("\nThis was a DRY RUN. Run with --apply to actually update the database.")
    print("=" * 70)


def show_all_options():
    """Display all available platform options"""
    print("=" * 70)
    print("AVAILABLE PLATFORM OPTIONS")
    print("=" * 70)

    for platform_key, config in PLATFORM_MAPPINGS.items():
        print(f"\n{config['platform_name']}")
        print("-" * 40)
        print(f"Matches: {', '.join(config['names'])}")
        print(f"Options:")
        print(json.dumps(config['options'], indent=2))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Populate lead source options")
    parser.add_argument("--user", type=str, help="Only update sources for this user ID")
    parser.add_argument("--user-email", type=str, help="Only update sources for this user email")
    parser.add_argument("--apply", action="store_true", help="Actually apply changes (default is dry run)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing options")
    parser.add_argument("--show-options", action="store_true", help="Show all available platform options")

    args = parser.parse_args()

    if args.show_options:
        show_all_options()
        sys.exit(0)

    user_id = args.user

    # If user email provided, look up user ID
    if args.user_email:
        supabase = SupabaseClientSingleton.get_instance()
        user_result = supabase.from_("users").select("id").eq("email", args.user_email).execute()
        if user_result.data:
            user_id = user_result.data[0]["id"]
            print(f"Found user ID: {user_id} for email: {args.user_email}")
        else:
            print(f"User not found: {args.user_email}")
            sys.exit(1)

    dry_run = not args.apply

    populate_source_options(user_id=user_id, dry_run=dry_run, force=args.force)
