import sys
import os
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from app.database.supabase_client import SupabaseClientSingleton

def check_import_progress():
    print("Checking import progress...")
    print("=" * 60)
    
    supabase = SupabaseClientSingleton.get_instance()
    
    try:
        # Check total count
        result = supabase.table("leads").select("id, source", count="exact").execute()
        count = result.count if hasattr(result, 'count') else len(result.data)
        
        print(f"\nTotal leads imported so far: {count}")
        
        # Count by source
        if result.data:
            sources = {}
            for lead in result.data:
                source = lead.get('source', 'Unknown')
                sources[source] = sources.get(source, 0) + 1
            
            print("\nBreakdown by source:")
            for source, source_count in sorted(sources.items()):
                print(f"  {source}: {source_count}")
    
    except Exception as e:
        print(f"\n[ERROR] {e}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    check_import_progress()

