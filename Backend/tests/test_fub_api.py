import sys
import os
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from app.database.fub_api_client import FUBApiClient

def test_fub_api():
    print("Testing FUB API to see what's actually returned...")
    print("=" * 60)
    
    fub_client = FUBApiClient()
    
    # Test 1: Get first page
    print("\n1. Fetching first page (limit=100, page=1)...")
    response = fub_client.get_people(limit=100, page=1)
    
    print(f"   Total people in response: {len(response.get('people', []))}")
    print(f"   Metadata: {response.get('_metadata', {})}")
    
    # Test 2: Check if there's a total count
    metadata = response.get('_metadata', {})
    if 'total' in metadata:
        print(f"\n   TOTAL LEADS IN FUB: {metadata['total']}")
    
    # Test 3: Show some sample sources
    people = response.get('people', [])
    if people:
        sources = set()
        for person in people[:20]:  # Check first 20
            source = person.get('source', 'NO_SOURCE')
            sources.add(source)
        
        print(f"\n2. Sample sources found in first 20 leads:")
        for source in sorted(sources):
            print(f"   - {source}")
    
    # Test 4: Try with source filter
    print("\n3. Testing source filter (source='Redfin')...")
    try:
        response_filtered = fub_client.get_people(limit=100, page=1, source="Redfin")
        print(f"   People returned with source='Redfin': {len(response_filtered.get('people', []))}")
        print(f"   Metadata: {response_filtered.get('_metadata', {})}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "=" * 60)
    print("Test complete!")

if __name__ == "__main__":
    test_fub_api()

