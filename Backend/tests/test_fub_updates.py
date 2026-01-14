#!/usr/bin/env python3
"""
Test script to verify FUB lead import updates work correctly
"""
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.database.supabase_client import SupabaseClientSingleton
from app.service.fub_api_key_service import FUBAPIKeyServiceSingleton

def main():
    try:
        supabase = SupabaseClientSingleton.get_instance()
        fub_service = FUBAPIKeyServiceSingleton.get_instance()

        # Get users
        users_result = supabase.table('users').select('id, email').execute()
        print('Available users:')
        for user in users_result.data:
            user_id = user['id']
            has_fub_key = fub_service.has_api_key(user_id)
            print(f'  {user["email"]} (ID: {user_id[:8]}...) - FUB Key: {has_fub_key}')

        # Test import for the first user with FUB key
        test_user = None
        for user in users_result.data:
            if fub_service.has_api_key(user['id']):
                test_user = user
                break

        if test_user:
            print(f'\nTesting import for user: {test_user["email"]}')

            # Check current lead count for this user
            leads_result = supabase.table('leads').select('id', count='exact').eq('user_id', test_user['id']).execute()
            print(f'Current leads for user: {leads_result.count}')

            # Check lead source count
            sources_result = supabase.table('lead_source_settings').select('id', count='exact').eq('user_id', test_user['id']).execute()
            print(f'Current lead sources for user: {sources_result.count}')

            print('\nTo test the import, you would call:')
            print(f'POST /api/supabase/import-fub-leads')
            print(f'Headers: X-User-ID: {test_user["id"]}')

            # Check if there are any leads without user_id (old data)
            old_leads = supabase.table('leads').select('id', count='exact').is_('user_id', 'null').execute()
            print(f'\nLeads without user_id (need migration): {old_leads.count}')

            # Check lead sources without user_id
            old_sources = supabase.table('lead_source_settings').select('id', count='exact').is_('user_id', 'null').execute()
            print(f'Lead sources without user_id (need migration): {old_sources.count}')

        else:
            print('No users found with FUB API keys')

    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    main()




