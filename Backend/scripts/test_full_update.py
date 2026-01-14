"""
Full test of MyAgentFinder update flow:
1. Login
2. Search for a lead (first name only)
3. Click into lead detail
4. Click status dropdown
5. Select status
6. Fill details
7. Click Update
"""
import os
import sys
import time

# Force visible browser
os.environ["SELENIUM_HEADLESS"] = "false"

# Add Backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.referral_scrapers.my_agent_finder.my_agent_finder_service import MyAgentFinderService
from app.models.lead import Lead

# Test configuration - change these as needed
TEST_LEAD_FIRST_NAME = "Victor"
TEST_LEAD_LAST_NAME = "Medina"
TEST_STATUS = "communicating"  # Maps to "Prospect - I'm communicating with this Client"

def main():
    print("="*60)
    print(f"Testing Full MyAgentFinder Update Flow")
    print(f"Lead: {TEST_LEAD_FIRST_NAME} {TEST_LEAD_LAST_NAME}")
    print(f"Status: {TEST_STATUS}")
    print("="*60)

    # Create a test lead object
    test_lead = Lead()
    test_lead.first_name = TEST_LEAD_FIRST_NAME
    test_lead.last_name = TEST_LEAD_LAST_NAME
    test_lead.id = "test-123"

    # Create service instance
    service = MyAgentFinderService(
        lead=test_lead,
        status=TEST_STATUS,
        same_status_note="Test update from automation script"
    )

    try:
        print("\n[1] Logging in...")
        if not service.login():
            print("    FAILED: Login failed")
            return

        print("    SUCCESS: Logged in")

        print(f"\n[2] Finding and updating lead: {TEST_LEAD_FIRST_NAME} {TEST_LEAD_LAST_NAME}")
        lead_name = f"{TEST_LEAD_FIRST_NAME} {TEST_LEAD_LAST_NAME}"

        success = service.find_and_update_lead(lead_name, TEST_STATUS)

        if success:
            print("\n" + "="*60)
            print("SUCCESS! Lead status updated!")
            print("="*60)
        else:
            print("\n" + "="*60)
            print(f"FAILED: Could not update lead")
            print(f"Last find result: {service.last_find_result}")
            print("="*60)

        # Keep browser open for inspection
        print("\nBrowser will stay open for 30 seconds...")
        time.sleep(30)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        time.sleep(30)

    finally:
        print("\nClosing browser...")
        service.close()

if __name__ == "__main__":
    main()
