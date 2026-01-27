"""
Quick script to add credits to a user for testing.
Usage: python scripts/add_credits.py <email> <enhancement> <criminal> <dnc>
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.supabase_client import SupabaseClientSingleton

def add_credits(email: str, enhancement: int = 100, criminal: int = 100, dnc: int = 100):
    """Add credits to a user by email."""
    supabase = SupabaseClientSingleton.get_instance()

    # Find user by email
    result = supabase.table('users').select('id, email, bundle_enhancement_credits, bundle_criminal_credits, bundle_dnc_credits').eq('email', email).single().execute()

    if not result.data:
        print(f"User not found: {email}")
        return False

    user = result.data
    user_id = user['id']

    # Get current credits
    current_enhancement = user.get('bundle_enhancement_credits') or 0
    current_criminal = user.get('bundle_criminal_credits') or 0
    current_dnc = user.get('bundle_dnc_credits') or 0

    print(f"Found user: {email} (ID: {user_id})")
    print(f"Current credits - Enhancement: {current_enhancement}, Criminal: {current_criminal}, DNC: {current_dnc}")

    # Add credits
    new_enhancement = current_enhancement + enhancement
    new_criminal = current_criminal + criminal
    new_dnc = current_dnc + dnc

    supabase.table('users').update({
        'bundle_enhancement_credits': new_enhancement,
        'bundle_criminal_credits': new_criminal,
        'bundle_dnc_credits': new_dnc
    }).eq('id', user_id).execute()

    print(f"Added credits - Enhancement: +{enhancement}, Criminal: +{criminal}, DNC: +{dnc}")
    print(f"New totals - Enhancement: {new_enhancement}, Criminal: {new_criminal}, DNC: {new_dnc}")
    return True

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/add_credits.py <email> [enhancement] [criminal] [dnc]")
        print("Example: python scripts/add_credits.py user@example.com 100 100 100")
        sys.exit(1)

    email = sys.argv[1]
    enhancement = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    criminal = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    dnc = int(sys.argv[4]) if len(sys.argv) > 4 else 100

    add_credits(email, enhancement, criminal, dnc)
