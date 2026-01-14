"""Test script to verify Redfin login with 2FA email code retrieval"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# Verify credentials
print("="*60)
print("REDFIN 2FA LOGIN TEST")
print("="*60)

# Check for required environment variables
redfin_email = os.getenv("REDFIN_EMAIL")
redfin_password = os.getenv("REDFIN_PASSWORD")
gmail_email = os.getenv("GMAIL_EMAIL")
gmail_app_password = os.getenv("GMAIL_APP_PASSWORD")

print(f"\nRedfin Email: {redfin_email[:3]}...{redfin_email[-10:] if redfin_email else 'NOT SET'}")
print(f"Redfin Password: {'SET' if redfin_password else 'NOT SET'}")
print(f"Gmail Email: {gmail_email[:3]}...{gmail_email[-10:] if gmail_email else 'NOT SET'}")
print(f"Gmail App Password: {'SET' if gmail_app_password else 'NOT SET'}")

if not all([redfin_email, redfin_password, gmail_email, gmail_app_password]):
    print("\nERROR: Missing required environment variables!")
    print("\nRequired in .env file:")
    print("  REDFIN_EMAIL=your_redfin_email@domain.com")
    print("  REDFIN_PASSWORD=your_redfin_password")
    print("  GMAIL_EMAIL=adam@saahomes.com")
    print("  GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx")
    sys.exit(1)

# Verify headless mode
headless = os.getenv("SELENIUM_HEADLESS", "true")
print(f"\nSELENIUM_HEADLESS = {headless}")
if headless.lower() in ["true", "1", "yes"]:
    print("WARNING: Headless mode is ON. Set SELENIUM_HEADLESS=false in .env to see browser")
else:
    print("Headless mode is OFF - browser should be visible")

print("\n" + "="*60)
print("This script will:")
print("  1. Navigate to Redfin login page")
print("  2. Enter email and password")
print("  3. Detect if 2FA is required")
print("  4. If 2FA required: Retrieve code from Gmail")
print("  5. Enter 2FA code and complete login")
print("  6. Report success/failure")
print("="*60)

input("\nPress Enter to start the Redfin 2FA login test...")

from app.referral_scrapers.redfin.redfin_service import RedfinService
from app.models.lead import Lead

# Create a dummy lead for testing
test_lead = Lead()
test_lead.first_name = "Test"
test_lead.last_name = "User"
test_lead.fub_person_id = "test123"

# Create service instance
service = RedfinService(lead=test_lead, status="In Progress")

print("\nStarting Redfin login test...")
print("Watch the browser to see the login process...\n")

try:
    # Try to login
    if service.login2():
        print("\n" + "="*60)
        print("SUCCESS! Redfin login completed!")
        print("="*60)

        # Get current URL to verify
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
        print("\nPossible issues:")
        print("  - Invalid Redfin credentials")
        print("  - 2FA code not found in email")
        print("  - 2FA input field selector not matching")
        print("  - Network/page loading issues")

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()

finally:
    print("\nClosing browser...")
    service.close()

input("\nPress Enter to exit...")
