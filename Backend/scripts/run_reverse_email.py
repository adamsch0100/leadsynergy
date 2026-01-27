"""
Quick script to run a reverse email lookup via Endato API.
"""
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.enrichment.endato_client import EndatoClient

def main():
    email = sys.argv[1] if len(sys.argv) > 1 else "r_kimbrow@yahoo.com"

    print(f"Running reverse email lookup for: {email}")
    print("-" * 50)

    client = EndatoClient()
    result = client.reverse_email(email)

    if result:
        print(json.dumps(result, indent=2))

        # Extract phone numbers if found
        if 'persons' in result:
            print("\n" + "=" * 50)
            print("PHONE NUMBERS FOUND:")
            print("=" * 50)
            for person in result.get('persons', []):
                name = person.get('name', {})
                full_name = f"{name.get('firstName', '')} {name.get('lastName', '')}"
                print(f"\nPerson: {full_name}")
                phones = person.get('phones', [])
                if phones:
                    for phone in phones:
                        phone_num = phone.get('phone', phone.get('number', 'N/A'))
                        phone_type = phone.get('type', 'Unknown')
                        print(f"  - {phone_num} ({phone_type})")
                else:
                    print("  No phones found")
        elif 'error' in result:
            print(f"\nError: {result['error'].get('message', 'Unknown error')}")
    else:
        print("No results returned")

if __name__ == "__main__":
    main()
