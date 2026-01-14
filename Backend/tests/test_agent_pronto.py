"""
Test script for Agent Pronto login - runs with visible browser
Tests magic link authentication
"""
import os
import sys

# Set headless mode to false so we can see the browser
os.environ["SELENIUM_HEADLESS"] = "false"

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.referral_scrapers.utils.driver_service import DriverService
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time
from datetime import datetime, timezone

# === CONFIGURATION ===
# Load from environment/constants
from app.utils.constants import Credentials
CREDS = Credentials()

# Agent Pronto login email
AGENT_PRONTO_EMAIL = "online@saahomes.com"

# Gmail credentials for retrieving magic link (from env)
GMAIL_EMAIL = CREDS.GMAIL_EMAIL
GMAIL_APP_PASSWORD = CREDS.GMAIL_APP_PASSWORD

def test_magic_link_flow():
    """Test the magic link login flow with visible browser"""

    driver_service = DriverService()

    print("="*60)
    print("Agent Pronto Login Test - Magic Link Flow")
    print("="*60)
    print(f"\nAgent Pronto Email: {AGENT_PRONTO_EMAIL}")
    print(f"Gmail Email: {GMAIL_EMAIL or 'NOT SET'}")
    print(f"Gmail App Password: {'SET' if GMAIL_APP_PASSWORD else 'NOT SET'}")
    print("="*60)

    try:
        print("\n[Step 1] Initializing browser...")
        driver_service.initialize_driver()

        print("\n[Step 2] Navigating to sign-in page...")
        driver_service.get_page("https://agentpronto.com/sign-in")
        time.sleep(3)

        current_url = driver_service.get_current_url()
        print(f"Current URL: {current_url}")
        driver_service.driver.save_screenshot("01_signin_page.png")

        # First, let's see what's on the page
        print("\n[Step 3] Analyzing sign-in page...")
        page_source = driver_service.driver.page_source.lower()

        # Check for password field
        has_password = 'type="password"' in page_source or 'name="password"' in page_source
        print(f"Has password field: {has_password}")

        # Check for alternative login methods
        has_google = 'google' in page_source
        has_sso = 'sso' in page_source or 'single sign' in page_source
        print(f"Has Google login: {has_google}")
        print(f"Has SSO: {has_sso}")

        # Find all buttons
        buttons = driver_service.driver.find_elements(By.TAG_NAME, 'button')
        print(f"Buttons on page: {[b.text for b in buttons if b.text]}")

        # Find all links
        links = driver_service.driver.find_elements(By.TAG_NAME, 'a')
        link_texts = [l.text for l in links if l.text and len(l.text) < 50]
        print(f"Links on page: {link_texts}")

        driver_service.driver.save_screenshot("02a_page_analysis.png")

        print("\n[Step 4] Finding and filling email field...")
        email_field = driver_service.driver.find_element(By.CSS_SELECTOR, 'input[name="email"]')
        email_field.clear()
        email_field.send_keys(AGENT_PRONTO_EMAIL)
        print(f"Entered email: {AGENT_PRONTO_EMAIL}")
        time.sleep(1)
        driver_service.driver.save_screenshot("02_email_entered.png")

        print("\n[Step 5] Clicking Sign In button to request magic link...")
        submit_btn = driver_service.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        print(f"Button text: '{submit_btn.text}'")

        # Record time BEFORE clicking to filter out old emails
        magic_link_request_time = datetime.now(timezone.utc)
        print(f"Magic link requested at: {magic_link_request_time}")

        submit_btn.click()
        time.sleep(3)

        driver_service.driver.save_screenshot("03_after_submit.png")
        print("Screenshot saved: 03_after_submit.png")
        print(f"Current URL: {driver_service.get_current_url()}")

        # Check page content for confirmation message
        page_text = driver_service.driver.find_element(By.TAG_NAME, "body").text
        if "check your email" in page_text.lower() or "sent" in page_text.lower() or "link" in page_text.lower():
            print("\n[SUCCESS] Magic link appears to have been sent!")
            print("Check your email for the login link from Agent Pronto")

        if GMAIL_EMAIL and GMAIL_APP_PASSWORD:
            print("\n[Step 6] Attempting to retrieve magic link from email...")
            from app.referral_scrapers.agent_pronto.agent_pronto_service import get_agent_pronto_magic_link

            magic_link = get_agent_pronto_magic_link(
                email_address=GMAIL_EMAIL,
                app_password=GMAIL_APP_PASSWORD,
                max_retries=20,
                retry_delay=3.0,
                max_age_seconds=300,
                min_email_time=magic_link_request_time
            )

            if magic_link:
                print(f"\n[SUCCESS] Found magic link!")
                print(f"Link: {magic_link[:80]}...")

                print("\n[Step 7] Navigating to magic link...")
                driver_service.get_page(magic_link)
                time.sleep(5)

                final_url = driver_service.get_current_url()
                print(f"URL after magic link: {final_url}")
                driver_service.driver.save_screenshot("04_after_magic_link.png")

                if "/app" in final_url or "dashboard" in final_url.lower():
                    print("\n[SUCCESS] LOGIN SUCCESSFUL!")
                else:
                    # Try navigating to app directly
                    print("\n[Step 8] Navigating to app URL directly...")
                    driver_service.get_page("https://agentpronto.com/app")
                    time.sleep(3)

                    final_url = driver_service.get_current_url()
                    print(f"Final URL: {final_url}")
                    driver_service.driver.save_screenshot("05_app_page.png")

                    if "/app" in final_url and "sign" not in final_url.lower():
                        print("\n[SUCCESS] LOGIN SUCCESSFUL - Now in app!")
                    elif "sign" in final_url.lower():
                        print("\n[FAILED] Redirected back to sign-in - login failed")
                    else:
                        print("\n[WARNING] May not be fully logged in - check browser")
            else:
                print("\n[FAILED] Could not retrieve magic link from email")
                print("Check that:")
                print("  - The email was sent to the correct address")
                print("  - Gmail app password is correct")
                print("  - IMAP is enabled for the Gmail account")
        else:
            print("\n[INFO] Gmail credentials not set - cannot auto-retrieve magic link")
            print("To test automatic login, set GMAIL_EMAIL and GMAIL_APP_PASSWORD")
            print("\nYou can manually:")
            print("  1. Check your email for the magic link")
            print("  2. Click the link in your email")
            print("  3. Come back here to see if login worked")

        print("\n" + "="*60)
        print("Browser will stay open for 180 seconds")
        print("Press Ctrl+C to close earlier")
        print("="*60)

        try:
            time.sleep(180)
        except KeyboardInterrupt:
            print("\nClosing...")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

        try:
            time.sleep(60)
        except:
            pass

    finally:
        print("Closing browser...")
        driver_service.close()
        print("Done!")

if __name__ == "__main__":
    test_magic_link_flow()
