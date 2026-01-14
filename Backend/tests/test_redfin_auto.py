"""Automated test for Redfin login with 2FA - no user input required"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

print("="*60)
print("REDFIN 2FA LOGIN TEST (Automated)")
print("="*60)

# Check credentials
redfin_email = os.getenv("REDFIN_EMAIL")
redfin_password = os.getenv("REDFIN_PASSWORD")
gmail_email = os.getenv("GMAIL_EMAIL")
gmail_app_password = os.getenv("GMAIL_APP_PASSWORD")

print(f"\nRedfin Email: {redfin_email[:3] if redfin_email else 'NOT SET'}...{redfin_email[-10:] if redfin_email else ''}")
print(f"Redfin Password: {'SET' if redfin_password else 'NOT SET'}")
print(f"Gmail Email: {gmail_email[:3] if gmail_email else 'NOT SET'}...{gmail_email[-10:] if gmail_email else ''}")
print(f"Gmail App Password: {'SET' if gmail_app_password else 'NOT SET'}")

if not all([redfin_email, redfin_password, gmail_email, gmail_app_password]):
    print("\nERROR: Missing required environment variables!")
    sys.exit(1)

print("\nStarting Redfin login test...")

from app.referral_scrapers.redfin.redfin_service import RedfinService
from app.models.lead import Lead

# Create a dummy lead for testing
test_lead = Lead()
test_lead.first_name = "Test"
test_lead.last_name = "User"
test_lead.fub_person_id = "test123"

# Create service instance
service = RedfinService(lead=test_lead, status="In Progress")

try:
    # Try to login
    if service.login2():
        print("\n" + "="*60)
        print("SUCCESS! Redfin login completed!")
        print("="*60)

        current_url = service.driver_service.get_current_url()
        print(f"Current URL: {current_url}")

        # Count customers if on dashboard
        try:
            from selenium.webdriver.common.by import By
            edit_buttons = service.driver_service.find_elements(By.CSS_SELECTOR, ".edit-status-button")
            print(f"Found {len(edit_buttons)} customers on dashboard")
        except:
            pass
    else:
        print("\n" + "="*60)
        print("FAILED: Redfin login did not complete successfully")
        print("="*60)

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()

finally:
    print("\nClosing browser...")
    service.close()
    print("Test complete!")
