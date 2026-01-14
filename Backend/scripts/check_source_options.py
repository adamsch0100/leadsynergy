"""
Check lead source options in database and see what's available
"""
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.supabase_client import SupabaseClientSingleton

def check_source_options():
    supabase = SupabaseClientSingleton.get_instance()

    # First get the user ID for adam@saahomes.com
    user_result = supabase.from_("users").select("id, email").eq("email", "adam@saahomes.com").execute()

    if not user_result.data:
        print("User not found")
        return

    user_id = user_result.data[0]["id"]
    print(f"User: adam@saahomes.com ({user_id})")
    print("=" * 80)

    # Get all lead sources for this user with their options
    sources = supabase.table("lead_source_settings").select("*").eq("user_id", user_id).execute()

    print(f"\nFound {len(sources.data)} lead sources:\n")

    for source in sources.data:
        print(f"Source: {source['source_name']}")
        print(f"  ID: {source['id']}")
        print(f"  Active: {source['is_active']}")

        # Check options field
        options = source.get('options')
        if options:
            options_str = json.dumps(options, indent=4) if isinstance(options, (dict, list)) else str(options)
            print(f"  OPTIONS: {options_str[:500]}...")
        else:
            print(f"  OPTIONS: None/Empty")

        # Check metadata for any options (handle string or dict)
        metadata = source.get('metadata')
        if metadata:
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except:
                    print(f"  Metadata (raw string): {metadata[:200]}...")
                    metadata = {}
            if isinstance(metadata, dict):
                print(f"  Metadata keys: {list(metadata.keys())}")
                if 'status_options' in metadata:
                    print(f"  Status options in metadata: {metadata['status_options']}")
                if 'platform_name' in metadata:
                    print(f"  Platform name: {metadata['platform_name']}")

        # Check fub_stage_mapping
        mapping = source.get('fub_stage_mapping')
        if mapping:
            print(f"  FUB Stage Mapping: {json.dumps(mapping, indent=4)}")
        else:
            print(f"  FUB Stage Mapping: None")

        print("-" * 60)

if __name__ == "__main__":
    check_source_options()
