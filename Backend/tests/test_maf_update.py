"""
Test script for My Agent Finder lead update - tests the full workflow:
1. Login
2. Navigate to All Active referrals
3. Find a specific lead
4. Update their status
"""
import os
import sys

os.environ["SELENIUM_HEADLESS"] = "false"
# Add Backend directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from app.referral_scrapers.my_agent_finder.my_agent_finder_service import (
    MyAgentFinderService,
    STATUS_OPTIONS,
    STATUS_DISPLAY_OPTIONS
)
from app.models.lead import Lead
import time


def create_test_lead(first_name: str, last_name: str) -> Lead:
    """Create a mock lead object for testing"""
    lead = Lead()
    lead.id = "test-lead-id"
    lead.first_name = first_name
    lead.last_name = last_name
    lead.fub_person_id = "test-fub-id"
    lead.source = "MyAgentFinder"
    lead.status = "Contacted"
    lead.metadata = {}
    return lead


def test_lead_update():
    """Test updating a lead on My Agent Finder"""
    import sys

    print("=" * 60, flush=True)
    print("My Agent Finder Lead Update Test", flush=True)
    print("=" * 60, flush=True)

    # Configuration - UPDATE THIS WITH YOUR LEAD NAME
    lead_first_name = "Dean"
    lead_last_name = "Askew"

    # Status to set - choose from STATUS_OPTIONS
    # Options: "communicating", "trying_to_reach", "prospects", "clients", "under_contract", "nurture"
    test_status = "communicating"  # Will map to "Assigned - I'm communicating with this Client"

    print(f"\nTarget Lead: {lead_first_name} {lead_last_name}", flush=True)
    print(f"Target Status: {test_status}", flush=True)
    print(f"  -> Maps to: {STATUS_OPTIONS.get(test_status, test_status)}", flush=True)
    print("=" * 60, flush=True)

    # Create mock lead
    lead = create_test_lead(lead_first_name, lead_last_name)

    # Create service
    print("\nCreating MyAgentFinderService...", flush=True)
    service = MyAgentFinderService(
        lead=lead,
        status=test_status,
        same_status_note="Continuing to communicate with this client. Will provide updates on progress."
    )
    print(f"Service created. Email: {service.email[:5] if service.email else 'NOT SET'}...", flush=True)

    try:
        # Step 1: Login
        print("\n[Step 1] Logging in...", flush=True)
        sys.stdout.flush()
        if not service.login():
            print("[FAILED] Login failed!", flush=True)
            return False
        print("[SUCCESS] Logged in!", flush=True)

        # Step 2: Navigate to All Active
        print("\n[Step 2] Navigating to All Active referrals...", flush=True)
        sys.stdout.flush()
        service.driver_service.get_page("https://app.myagentfinder.com/referral/active/allactive")
        time.sleep(3)
        print("[SUCCESS] On All Active page!", flush=True)

        # Step 3: Find the lead
        print(f"\n[Step 3] Finding lead: {lead_first_name} {lead_last_name}...", flush=True)
        sys.stdout.flush()
        lead_row = service._find_lead_row(f"{lead_first_name} {lead_last_name}")

        if not lead_row:
            print(f"[FAILED] Could not find lead: {lead_first_name} {lead_last_name}", flush=True)
            return False
        print("[SUCCESS] Found lead!", flush=True)

        # Step 4: Update the status
        print(f"\n[Step 4] Updating status to: {test_status}...", flush=True)
        sys.stdout.flush()
        if not service._update_lead_status(lead_row, test_status):
            print(f"[FAILED] Could not update status", flush=True)
            return False
        print("[SUCCESS] Status updated!", flush=True)

        print("\n" + "=" * 60)
        print("TEST PASSED - Lead successfully updated!")
        print("=" * 60)

        # Keep browser open for verification
        print("\nBrowser will stay open for 60 seconds for verification...")
        print("Press Ctrl+C to close earlier.")
        try:
            time.sleep(60)
        except KeyboardInterrupt:
            print("\nClosing...")

        return True

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

        # Keep browser open for debugging
        print("\nBrowser will stay open for 60 seconds for debugging...")
        try:
            time.sleep(60)
        except:
            pass

        return False

    finally:
        print("Closing browser...")
        service.logout()
        print("Done!")


def list_available_statuses():
    """Print available status options"""
    print("\n" + "=" * 60)
    print("AVAILABLE MY AGENT FINDER STATUS OPTIONS")
    print("=" * 60)

    print("\n--- STATUS OPTIONS (for stage mapping) ---")
    for key, value in STATUS_OPTIONS.items():
        print(f"  '{key}' -> \"{value}\"")

    print("\n--- DISPLAY OPTIONS (shown in dropdown) ---")
    for opt in STATUS_DISPLAY_OPTIONS:
        print(f"  - {opt}")

    print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test My Agent Finder lead update")
    parser.add_argument("--list-statuses", action="store_true", help="List available status options")
    parser.add_argument("--first-name", default="Dean", help="Lead's first name")
    parser.add_argument("--last-name", default="Askew", help="Lead's last name")
    parser.add_argument("--status", default="communicating", help="Status to set")

    args = parser.parse_args()

    if args.list_statuses:
        list_available_statuses()
    else:
        test_lead_update()
