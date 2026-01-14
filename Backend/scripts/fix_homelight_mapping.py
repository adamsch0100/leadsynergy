"""Quick script to fix HomeLight stage mappings"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.database.supabase_client import SupabaseClientSingleton

# Fixed stage mappings - no "Left Voicemail" (not a valid HomeLight option)
fixed_mapping = {
    "A -  Hot 1-3 months": "Connected",
    "Active Client": "Listing",
    "Active listing": "Listing",
    "Appointment set": "Meeting Scheduled",
    "Attempted contact": "Connected",
    "B - Warm 3-6 Months": "Connected",
    "C - Cold 6+ Months": "Connected",  # Was "Left Voicemail"
    "Closed": "Failed",
    "Contact": "Connected",  # Was "Left Voicemail"
    "Lead": "Connected",
    "Listing agreement": "Coming Soon",
    "Met with customer": "Met With Person",
    "Nurture": "Connected",
    "Pending": "In Escrow",
    "Recruiting": "Failed",
    "Referred to Agent": "Failed",
    "Renter - future buyer": "Connected",
    "Showing homes": "Met With Person",
    "Sphere": "Connected",
    "Spoke with customer": "Connected",
    "Submitting offers": "Met With Person",
    "Test Closed": "Failed",
    "Test Stage": "Connected",
    "Trash": "Failed",
    "Under contract": "In Escrow"
}

# HomeLight source ID
source_id = "a8032a81-df21-4627-b6ae-5ba14ebc73b6"

try:
    supabase = SupabaseClientSingleton.get_instance()

    result = supabase.table("lead_source_settings").update({
        "fub_stage_mapping": fixed_mapping
    }).eq("id", source_id).execute()

    if result.data:
        print("SUCCESS: HomeLight stage mappings updated!")
        print(f"Updated source: {source_id}")
    else:
        print("ERROR: No data returned from update")
        print(result)
except Exception as e:
    print(f"ERROR: {e}")
