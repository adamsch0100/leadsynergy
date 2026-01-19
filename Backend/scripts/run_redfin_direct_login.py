"""Script to check Redfin using direct login (not Google OAuth)"""
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
print("REDFIN LEADS CHECK (Direct Login)")
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

print("\n[CONFIG]")
print(f"  Redfin Email: {service.email}")
print(f"  2FA Email: {service.twofa_email}")
print(f"  2FA App Password: {'***SET***' if service.twofa_app_password else 'NOT SET'}")

print("\n[STEP 1] Attempting direct Redfin login (not Google OAuth)...")

try:
    # Use login() which does direct email/password login
    if service.login():
        print("[OK] Login successful!")
        service.is_logged_in = True

        # Navigate to partner dashboard
        print("\n[STEP 2] Navigating to partner dashboard...")
        service.driver_service.get_page("https://www.redfin.com/tools/partnerCustomers")
        time.sleep(5)

        # Check page content
        page_text = service.driver_service.driver.find_element(By.TAG_NAME, "body").text

        # Look for urgent/overdue keywords
        urgent_keywords = ['urgent', 'overdue', 'action required', 'needs attention', 'past due', 'update needed', 'action']
        found_urgent = []

        page_lower = page_text.lower()
        for keyword in urgent_keywords:
            if keyword in page_lower:
                found_urgent.append(keyword)

        if found_urgent:
            print(f"\n[ALERT] Found urgent indicators: {found_urgent}")
        else:
            print("\n[OK] No urgent/overdue indicators found")

        print(f"\nPage text preview:\n{page_text[:800]}")

        service.logout()
    else:
        print("[FAILED] Login failed!")

except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("REDFIN CHECK COMPLETE")
print("=" * 60)
