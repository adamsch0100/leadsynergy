#!/usr/bin/env python3
"""
Lookup stage mappings for a specific user and lead source.

Usage:
    python lookup_mappings.py

This script will:
1. Connect to Supabase using the existing SupabaseClientSingleton
2. Look up the user_id for email "adam@saahomes.com" from the users table
3. Get the lead_source_settings for "Referral Exchange" (or similar) for that user
4. Print the fub_stage_mapping field
"""
import sys
import os
import json

# Add the parent directory to the Python path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database.supabase_client import SupabaseClientSingleton


def main():
    email = "adam@saahomes.com"

    try:
        supabase = SupabaseClientSingleton.get_instance()
        print(f"Connected to Supabase successfully.\n")

        # Step 1: Look up the user by email
        print(f"Looking up user with email: {email}")
        user_result = supabase.table('users').select('*').eq('email', email).execute()

        if not user_result.data:
            print(f"ERROR: No user found with email '{email}'")
            return

        user = user_result.data[0]
        user_id = user['id']
        print(f"Found user:")
        print(f"  ID: {user_id}")
        print(f"  Email: {user.get('email', 'N/A')}")
        print(f"  Full Name: {user.get('full_name', 'N/A')}")
        print()

        # Step 2: Get lead_source_settings for this user
        print(f"Looking up lead_source_settings for user_id: {user_id}")

        # Try multiple variations of "Referral Exchange"
        source_names = ["Referral Exchange", "ReferralExchange", "referral exchange", "referralexchange"]

        settings_result = supabase.table('lead_source_settings').select('*').eq('user_id', user_id).execute()

        if not settings_result.data:
            print(f"No lead_source_settings found for user_id: {user_id}")
            return

        print(f"Found {len(settings_result.data)} lead source setting(s) for this user:\n")

        # Find Referral Exchange specifically
        referral_exchange_settings = None

        for settings in settings_result.data:
            source_name = settings.get('source_name', 'Unknown')
            is_active = settings.get('is_active', False)

            print(f"  Source: {source_name}")
            print(f"    ID: {settings.get('id', 'N/A')}")
            print(f"    Active: {is_active}")

            # Check if this is Referral Exchange
            if source_name.lower().replace(' ', '') == 'referralexchange':
                referral_exchange_settings = settings
                print(f"    << This is the Referral Exchange source >>")
            print()

        # Step 3: Print the fub_stage_mapping for Referral Exchange
        if referral_exchange_settings:
            print("=" * 60)
            print("REFERRAL EXCHANGE STAGE MAPPING")
            print("=" * 60)

            fub_stage_mapping = referral_exchange_settings.get('fub_stage_mapping', {})

            # Handle if it's stored as a string
            if isinstance(fub_stage_mapping, str):
                try:
                    fub_stage_mapping = json.loads(fub_stage_mapping)
                except json.JSONDecodeError:
                    print(f"fub_stage_mapping is a string but not valid JSON: {fub_stage_mapping}")
                    return

            if not fub_stage_mapping:
                print("No fub_stage_mapping configured for Referral Exchange.")
            else:
                print(f"\nFUB Stage -> Referral Exchange Status mapping:")
                print("-" * 60)
                for fub_stage, re_status in fub_stage_mapping.items():
                    print(f"  {fub_stage:30} -> {re_status}")
                print("-" * 60)
                print(f"\nTotal mappings: {len(fub_stage_mapping)}")

            # Also print other useful info
            print(f"\nOther settings for Referral Exchange:")
            print(f"  is_active: {referral_exchange_settings.get('is_active', 'N/A')}")
            print(f"  sync_interval_days: {referral_exchange_settings.get('sync_interval_days', 'N/A')}")
            print(f"  same_status_note: {referral_exchange_settings.get('same_status_note', 'N/A')}")

            # Print options if available
            options = referral_exchange_settings.get('options', {})
            if isinstance(options, str):
                try:
                    options = json.loads(options)
                except:
                    pass
            if options:
                print(f"\nAvailable options:")
                print(json.dumps(options, indent=2))
        else:
            print("No Referral Exchange source found for this user.")
            print("\nAvailable sources:")
            for settings in settings_result.data:
                print(f"  - {settings.get('source_name', 'Unknown')}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
