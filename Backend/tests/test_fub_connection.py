"""Test script to verify Follow Up Boss API connection"""
import asyncio
import sys
from app.database.fub_api_client import FUBApiClient

async def test_fub_connection():
    """Test FUB API connection"""
    try:
        print("Testing Follow Up Boss API connection...")
        client = FUBApiClient()
        
        # Test the connection
        result = await client.test_connection()
        
        print("Successfully connected to Follow Up Boss API!")
        print(f"Response: {result}")
        
        # Try to get a few people/leads
        if 'people' in result:
            people_count = len(result.get('people', []))
            print(f"Found {people_count} people in response")
            if people_count > 0:
                print(f"Sample person: {result['people'][0].get('name', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"Failed to connect to Follow Up Boss API: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_fub_connection())
    sys.exit(0 if success else 1)

