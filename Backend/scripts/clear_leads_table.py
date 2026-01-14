import sys
import os
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from app.database.supabase_client import SupabaseClientSingleton

def clear_leads_table():
    print("Clearing leads table in Supabase...")
    print("=" * 60)
    
    supabase = SupabaseClientSingleton.get_instance()
    
    try:
        # Check current count
        result = supabase.table("leads").select("id", count="exact").execute()
        count = result.count if hasattr(result, 'count') else len(result.data)
        
        print(f"\nCurrent number of leads in database: {count}")
        
        if count > 0:
            print(f"\nDeleting all {count} leads...")
            # Delete all leads
            delete_result = supabase.table("leads").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            print(f"[OK] Deleted successfully!")
            
            # Verify deletion
            verify_result = supabase.table("leads").select("id", count="exact").execute()
            verify_count = verify_result.count if hasattr(verify_result, 'count') else len(verify_result.data)
            print(f"[OK] Leads remaining: {verify_count}")
            print(f"\n[OK] Leads table is now empty and ready for fresh import!")
        else:
            print("\n[OK] Leads table is already empty!")
    
    except Exception as e:
        print(f"\n[ERROR] {e}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    clear_leads_table()

