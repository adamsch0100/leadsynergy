"""
Check how Michael Wimberley is stored in the database
"""
from dotenv import load_dotenv

load_dotenv()

from app.service.lead_service import LeadServiceSingleton

lead_service = LeadServiceSingleton.get_instance()

# Find Michael Wimberley by FUB ID
fub_id = "3027"
lead = lead_service.get_by_fub_person_id(fub_id)

if lead:
    print("="*80)
    print("MICHAEL WIMBERLEY LEAD DATA")
    print("="*80)
    print(f"FUB Person ID: {lead.fub_person_id}")
    print(f"First Name: '{lead.first_name}'")
    print(f"Last Name: '{lead.last_name}'")
    print(f"Full Name: '{lead.first_name} {lead.last_name}'")
    print(f"Full Name Length: {len(f'{lead.first_name} {lead.last_name}')}")
    print(f"First Name Repr: {repr(lead.first_name)}")
    print(f"Last Name Repr: {repr(lead.last_name)}")
    print(f"Full Name Repr: {repr(f'{lead.first_name} {lead.last_name}')}")
    
    # Check for any special characters
    full_name = f"{lead.first_name} {lead.last_name}"
    print(f"\nCharacter Analysis:")
    print(f"  Total characters: {len(full_name)}")
    for i, char in enumerate(full_name):
        if ord(char) > 127:
            print(f"  Position {i}: '{char}' (Unicode: U+{ord(char):04X})")
    
    # Check if there are any hidden characters or duplicates
    if full_name.count("Michael") > 1 or full_name.count("Wimberley") > 1:
        print(f"\nWARNING: Name contains duplicates!")
        print(f"  'Michael' appears {full_name.count('Michael')} times")
        print(f"  'Wimberley' appears {full_name.count('Wimberley')} times")
    
    # Check all attributes
    print(f"\nAll Lead Attributes:")
    for attr in dir(lead):
        if not attr.startswith('_'):
            try:
                value = getattr(lead, attr)
                if not callable(value):
                    print(f"  {attr}: {repr(value)}")
            except:
                pass
else:
    print(f"Lead with FUB ID {fub_id} not found")



