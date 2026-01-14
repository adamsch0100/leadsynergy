"""
Test script for Agent Pronto lead update - tests the full workflow:
1. Login via magic link
2. Navigate to deals
3. Find a specific lead
4. Update their status
"""
import os
import sys

# Set headless mode to false so we can see the browser
os.environ["SELENIUM_HEADLESS"] = "false"

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.referral_scrapers.agent_pronto.agent_pronto_service import AgentProntoService, ACTIVE_STATUSES, LOST_STATUSES
from app.models.lead import Lead
import time


def create_test_lead(first_name: str, last_name: str) -> Lead:
    """Create a mock lead object for testing"""
    lead = Lead()
    lead.id = "test-lead-id"
    lead.first_name = first_name
    lead.last_name = last_name
    lead.fub_person_id = "test-fub-id"
    lead.source = "AgentPronto"
    lead.status = "Contacted"
    lead.metadata = {}
    return lead


def test_lead_update():
    """Test updating a lead on Agent Pronto"""

    print("=" * 60)
    print("Agent Pronto Lead Update Test")
    print("=" * 60)

    # Configuration - UPDATE THIS WITH YOUR LEAD NAME
    lead_first_name = "Marvin"
    lead_last_name = "Holland"

    # Status to set - choose from ACTIVE_STATUSES or LOST_STATUSES
    # Active statuses: "Communicating with referral", "Showing properties in person", "Offer accepted"
    # Lost statuses: "unresponsive", "agent_did_not_make_contact", "already_has_agent", etc.
    test_status = "communicating"  # Will map to "Communicating with referral"

    print(f"\nTarget Lead: {lead_first_name} {lead_last_name}")
    print(f"Target Status: {test_status}")
    print(f"  -> Maps to: {ACTIVE_STATUSES.get(test_status, LOST_STATUSES.get(test_status, test_status))}")
    print("=" * 60)

    # Create mock lead
    lead = create_test_lead(lead_first_name, lead_last_name)

    # Create service
    service = AgentProntoService(
        lead=lead,
        status=test_status
    )

    try:
        # Step 1: Login
        print("\n[Step 1] Logging in via magic link...")
        if not service.login():
            print("[FAILED] Login failed!")
            return False
        print("[SUCCESS] Logged in!")

        # Step 2: Navigate to deals
        print("\n[Step 2] Navigating to deals page...")
        if not service.navigate_to_referrals():
            print("[FAILED] Could not navigate to deals page!")
            return False
        print("[SUCCESS] On deals page!")

        # Give user a chance to see the page
        time.sleep(2)

        # Step 3: Find and click the lead
        print(f"\n[Step 3] Finding lead: {lead_first_name} {lead_last_name}...")
        lead_name = f"{lead_first_name} {lead_last_name}"
        if not service.find_and_click_customer_by_name(lead_name):
            print(f"[FAILED] Could not find lead: {lead_name}")
            return False
        print("[SUCCESS] Found and clicked lead!")

        # Give user a chance to see the page
        time.sleep(2)

        # Step 4: Update the status
        print(f"\n[Step 4] Updating status to: {test_status}...")
        if not service.update_customers(test_status):
            print(f"[FAILED] Could not update status to: {test_status}")
            return False
        print("[SUCCESS] Status updated!")

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
    print("AVAILABLE AGENT PRONTO STATUS OPTIONS")
    print("=" * 60)

    print("\n--- ACTIVE STATUSES (keeps deal in progress) ---")
    seen = set()
    for key, value in ACTIVE_STATUSES.items():
        if value not in seen:
            print(f"  '{key}' -> \"{value}\"")
            seen.add(value)

    print("\n--- LOST STATUSES (archives the deal) ---")
    core_lost = ["agent_did_not_make_contact", "no_longer_buying_or_selling",
                 "already_has_agent", "unresponsive", "denied_loan_approval",
                 "listing_expired_or_cancelled", "other"]
    for key in core_lost:
        if key in LOST_STATUSES:
            print(f"  '{key}' -> \"{LOST_STATUSES[key]}\"")

    print("\n--- ALIASES (convenience mappings) ---")
    aliases = ["lost", "not_responding", "no_contact", "has_agent", "inactive", "archived",
               "contacted", "showing_properties", "in_progress"]
    for key in aliases:
        if key in ACTIVE_STATUSES:
            print(f"  '{key}' -> \"{ACTIVE_STATUSES[key]}\" (active)")
        elif key in LOST_STATUSES:
            print(f"  '{key}' -> maps to '{LOST_STATUSES[key]}' (lost)")

    print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test Agent Pronto lead update")
    parser.add_argument("--list-statuses", action="store_true", help="List available status options")
    parser.add_argument("--first-name", default="Marvin", help="Lead's first name")
    parser.add_argument("--last-name", default="Holland", help="Lead's last name")
    parser.add_argument("--status", default="communicating", help="Status to set")

    args = parser.parse_args()

    if args.list_statuses:
        list_available_statuses()
    else:
        # Override defaults if provided
        test_lead_update()
