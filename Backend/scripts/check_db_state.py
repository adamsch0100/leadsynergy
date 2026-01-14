#!/usr/bin/env python3
"""
Check database state for testing FUB import updates
"""
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.database.supabase_client import SupabaseClientSingleton

def main():
    try:
        supabase = SupabaseClientSingleton.get_instance()

        # Check users table
        users = supabase.table('users').select('*').execute()
        print('Users in database:')
        for user in users.data:
            print(f'  ID: {user["id"]}')
            print(f'  Email: {user.get("email", "None")}')
            print(f'  Full Name: {user.get("full_name", "None")}')
            print()

        # Check user_profiles table
        try:
            profiles = supabase.table('user_profiles').select('*').execute()
            print('User profiles in database:')
            for profile in profiles.data:
                print(f'  User ID: {profile.get("id", "None")}')
                fub_key = profile.get("fub_api_key", "")
                masked_key = "***" + fub_key[-4:] if fub_key else "None"
                print(f'  FUB API Key: {masked_key}')
                print()
        except Exception as e:
            print(f'Error checking user_profiles: {e}')

        # Check leads table
        leads = supabase.table('leads').select('id, user_id, source', count='exact').execute()
        print(f'Total leads: {leads.count}')
        if leads.count > 0:
            leads_with_user = supabase.table('leads').select('id', count='exact').not_('user_id', 'is', 'null').execute()
            print(f'Leads with user_id: {leads_with_user.count}')
            leads_without_user = supabase.table('leads').select('id', count='exact').is_('user_id', 'null').execute()
            print(f'Leads without user_id: {leads_without_user.count}')

        # Check lead sources
        sources = supabase.table('lead_source_settings').select('id, user_id, source_name, is_active', count='exact').execute()
        print(f'Total lead sources: {sources.count}')
        if sources.count > 0:
            sources_with_user = supabase.table('lead_source_settings').select('id', count='exact').not_('user_id', 'is', 'null').execute()
            print(f'Lead sources with user_id: {sources_with_user.count}')
            sources_without_user = supabase.table('lead_source_settings').select('id', count='exact').is_('user_id', 'null').execute()
            print(f'Lead sources without user_id: {sources_without_user.count}')

    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    main()




