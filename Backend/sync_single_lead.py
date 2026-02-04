"""
Quick script to sync a single lead from FUB to the database.
Usage: python sync_single_lead.py <fub_person_id>
"""
import sys
import json
import uuid
from app.database.supabase_client import SupabaseClientSingleton
from app.database.fub_api_client import FUBApiClient
from app.models.lead import Lead
from app.utils.constants import Credentials

def sync_single_lead(fub_person_id: int):
    """Sync a single lead from FUB to Supabase."""

    # Initialize clients
    supabase = SupabaseClientSingleton.get_instance()
    fub_client = FUBApiClient(Credentials.FUB_API_KEY)

    print(f"Fetching person {fub_person_id} from FUB...")
    person_data = fub_client.get_person(fub_person_id)

    if not person_data:
        print(f"❌ Person {fub_person_id} not found in FUB")
        return False

    print(f"✓ Found: {person_data.get('firstName', '')} {person_data.get('lastName', '')}")

    # Get user_id from database (first user with FUB API key)
    user_result = supabase.table("users").select("id, organization_id").not_.is_("fub_api_key", "null").limit(1).execute()

    if not user_result.data:
        print("❌ No user with FUB API key found in database")
        return False

    user_id = user_result.data[0]["id"]
    organization_id = user_result.data[0]["organization_id"]
    print(f"✓ Using user_id: {user_id}, organization_id: {organization_id}")

    # Check if lead already exists
    existing = supabase.table("leads").select("id").eq("fub_person_id", str(fub_person_id)).eq("user_id", user_id).execute()

    if existing.data:
        print(f"⚠ Lead already exists in database with ID: {existing.data[0]['id']}")
        print("Updating existing lead...")

        # Update existing lead
        lead_obj = Lead.from_fub(person_data)
        lead_dict = {key: value for key, value in lead_obj.to_dict().items() if value is not None}
        lead_dict.pop("fub_id", None)
        lead_dict["id"] = existing.data[0]["id"]
        lead_dict["fub_person_id"] = str(fub_person_id)
        lead_dict["user_id"] = user_id
        lead_dict["organization_id"] = organization_id

        if lead_dict.get("price") is None:
            lead_dict["price"] = 0
        if isinstance(lead_dict.get("tags"), list):
            lead_dict["tags"] = json.dumps(lead_dict["tags"])

        result = supabase.table("leads").update(lead_dict).eq("id", existing.data[0]["id"]).execute()
        print(f"✓ Updated lead in database")
    else:
        print("Creating new lead in database...")

        # Create new lead
        lead_obj = Lead.from_fub(person_data)
        lead_dict = {key: value for key, value in lead_obj.to_dict().items() if value is not None}
        lead_dict.pop("fub_id", None)
        lead_dict["id"] = str(uuid.uuid4())
        lead_dict["fub_person_id"] = str(fub_person_id)
        lead_dict["user_id"] = user_id
        lead_dict["organization_id"] = organization_id

        if lead_dict.get("price") is None:
            lead_dict["price"] = 0
        if isinstance(lead_dict.get("tags"), list):
            lead_dict["tags"] = json.dumps(lead_dict["tags"])

        result = supabase.table("leads").insert(lead_dict).execute()
        print(f"✓ Created lead in database with ID: {result.data[0]['id']}")

    print("\n=== Lead Summary ===")
    print(f"FUB Person ID: {fub_person_id}")
    print(f"Name: {person_data.get('firstName', '')} {person_data.get('lastName', '')}")
    print(f"Phone: {person_data.get('phones', [{}])[0].get('value') if person_data.get('phones') else 'N/A'}")
    print(f"Email: {person_data.get('emails', [{}])[0].get('value') if person_data.get('emails') else 'N/A'}")
    print(f"Source: {person_data.get('source', 'N/A')}")
    print(f"Stage: {person_data.get('stage', {}).get('name', 'N/A')}")

    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python sync_single_lead.py <fub_person_id>")
        print("Example: python sync_single_lead.py 3311")
        sys.exit(1)

    try:
        fub_person_id = int(sys.argv[1])
        success = sync_single_lead(fub_person_id)
        sys.exit(0 if success else 1)
    except ValueError:
        print("❌ Invalid FUB person ID. Must be a number.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
