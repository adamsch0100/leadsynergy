import sys
import os
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from app.database.supabase_client import SupabaseClientSingleton

def check_and_clear_leads():
    print("Checking leads table in Supabase...")
    print("=" * 60)
    
    supabase = SupabaseClientSingleton.get_instance()
    
    # Check how many leads exist
    try:
        result = supabase.table("leads").select("id", count="exact").execute()
        count = result.count if hasattr(result, 'count') else len(result.data)
        
        print(f"\nCurrent number of leads in database: {count}")
        
        if count > 0:
            print(f"\nFound {count} existing leads in the database.")
            response = input("\nDo you want to DELETE ALL leads and start fresh? (yes/no): ")
            
            if response.lower() in ['yes', 'y']:
                print("\nDeleting all leads...")
                delete_result = supabase.table("leads").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
                print(f"Deleted leads successfully!")
                
                # Verify deletion
                verify_result = supabase.table("leads").select("id", count="exact").execute()
                verify_count = verify_result.count if hasattr(verify_result, 'count') else len(verify_result.data)
                print(f"Leads remaining: {verify_count}")
            else:
                print("\nKeeping existing leads. Import will update existing leads or add new ones.")
        else:
            print("\nLeads table is empty. Ready for fresh import!")
    
    except Exception as e:
        print(f"\nError checking leads table: {e}")
        print("\nNote: If the table doesn't exist, it will be created automatically during import.")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    check_and_clear_leads()

