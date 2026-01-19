"""Script to check Redfin for any urgent/overdue leads - using Google OAuth"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

# Force headless OFF for debugging
os.environ["SELENIUM_HEADLESS"] = "false"

import time
from selenium.webdriver.common.by import By

print("=" * 60)
print("REDFIN LEADS CHECK (Google OAuth)")
print("=" * 60)

from app.referral_scrapers.redfin.redfin_service import RedfinService
from app.models.lead import Lead

# Create a dummy lead for initialization
dummy_lead = Lead()
dummy_lead.first_name = "Test"
dummy_lead.last_name = "User"

# Initialize service
service = RedfinService(
    lead=dummy_lead,
    status="Active",
    organization_id="cfde8fec-3b87-4558-b20f-5fe25fdcf149",
    min_sync_interval_hours=0
)

print("\n[STEP 1] Attempting Redfin login via Google OAuth...")
print(f"Email: {service.email}")
print(f"2FA Email: {service.twofa_email}")
print(f"2FA App Password: {'***' if service.twofa_app_password else 'NOT SET'}")

try:
    # Use login2() which tries Google OAuth first
    if service.login2():
        print("[OK] Login successful!")
        service.is_logged_in = True

        # Navigate to partner dashboard
        print("\n[STEP 2] Navigating to partner dashboard...")
        service.driver_service.get_page("https://www.redfin.com/tools/partnerCustomers")
        time.sleep(5)

        # Check page content for urgent/overdue indicators
        page_text = service.driver_service.driver.find_element(By.TAG_NAME, "body").text

        # Look for urgent/overdue keywords
        urgent_keywords = ['urgent', 'overdue', 'action required', 'needs attention', 'past due', 'update needed']
        found_urgent = []

        page_lower = page_text.lower()
        for keyword in urgent_keywords:
            if keyword in page_lower:
                found_urgent.append(keyword)

        if found_urgent:
            print(f"\n[ALERT] Found urgent indicators: {found_urgent}")
            print(f"\nPage text preview: {page_text[:1000]}")
        else:
            print("\n[OK] No urgent/overdue indicators found on the dashboard")
            print(f"\nPage text preview: {page_text[:500]}")

        service.logout()
    else:
        print("[FAILED] Login failed!")
        print("The browser will remain open for manual intervention if needed.")
        print("You may need to complete the Google OAuth flow manually.")
        input("\nPress Enter when done to close the browser...")

except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("REDFIN CHECK COMPLETE")
print("=" * 60)
