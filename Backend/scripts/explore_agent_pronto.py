"""
Explore Agent Pronto app to understand lead/referral structure
Logs in and then analyzes the dashboard/referrals page
"""
import os
import sys
import time
import json
from datetime import datetime, timezone

# Set headless mode to false so we can see the browser
os.environ["SELENIUM_HEADLESS"] = "false"

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.referral_scrapers.utils.driver_service import DriverService
from app.referral_scrapers.agent_pronto.agent_pronto_service import get_agent_pronto_magic_link
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from app.utils.constants import Credentials
CREDS = Credentials()

AGENT_PRONTO_EMAIL = "online@saahomes.com"
GMAIL_EMAIL = CREDS.GMAIL_EMAIL
GMAIL_APP_PASSWORD = CREDS.GMAIL_APP_PASSWORD

def explore_agent_pronto():
    """Explore Agent Pronto app structure"""

    driver_service = DriverService()

    print("=" * 60)
    print("Agent Pronto App Explorer")
    print("=" * 60)

    try:
        print("\n[1] Initializing browser...")
        driver_service.initialize_driver()

        # Login process
        print("\n[2] Logging in via magic link...")
        driver_service.get_page("https://agentpronto.com/sign-in")
        time.sleep(3)

        # Enter email
        email_field = driver_service.driver.find_element(By.CSS_SELECTOR, 'input[name="email"]')
        email_field.clear()
        email_field.send_keys(AGENT_PRONTO_EMAIL)
        time.sleep(1)

        # Record time and click Sign In
        magic_link_request_time = datetime.now(timezone.utc)
        submit_btn = driver_service.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        submit_btn.click()
        time.sleep(3)

        # Get magic link
        print("    Waiting for magic link email...")
        magic_link = get_agent_pronto_magic_link(
            email_address=GMAIL_EMAIL,
            app_password=GMAIL_APP_PASSWORD,
            max_retries=20,
            retry_delay=3.0,
            max_age_seconds=300,
            min_email_time=magic_link_request_time
        )

        if not magic_link:
            print("    [ERROR] Could not get magic link")
            return

        print("    Got magic link, navigating...")
        driver_service.get_page(magic_link)
        time.sleep(5)

        current_url = driver_service.get_current_url()
        print(f"    Current URL: {current_url}")

        if "/app" not in current_url:
            print("    Navigating to app...")
            driver_service.get_page("https://agentpronto.com/app")
            time.sleep(3)

        print("\n[3] LOGIN SUCCESSFUL - Now exploring app...")
        driver_service.driver.save_screenshot("explore_01_dashboard.png")

        # Analyze the main page
        print("\n" + "=" * 60)
        print("DASHBOARD ANALYSIS")
        print("=" * 60)

        # Find navigation elements
        nav_links = driver_service.driver.find_elements(By.CSS_SELECTOR, 'nav a, .nav a, [class*="nav"] a, aside a')
        print(f"\nNavigation links found: {len(nav_links)}")
        for link in nav_links[:15]:
            text = link.text.strip()
            href = link.get_attribute('href') or ''
            if text:
                print(f"  - {text}: {href}")

        # Look for referrals/leads section
        print("\n" + "=" * 60)
        print("LOOKING FOR REFERRALS/LEADS")
        print("=" * 60)

        # Try to navigate to referrals
        referral_urls = [
            "https://agentpronto.com/app/referrals",
            "https://agentpronto.com/app/leads",
            "https://agentpronto.com/app/dashboard",
        ]

        for url in referral_urls:
            print(f"\nTrying {url}...")
            driver_service.get_page(url)
            time.sleep(3)

            current = driver_service.get_current_url()
            print(f"  Landed at: {current}")

            if "sign" not in current.lower():
                driver_service.driver.save_screenshot(f"explore_{url.split('/')[-1]}.png")

                # Look for lead/referral cards
                page_source = driver_service.driver.page_source

                # Find any tables or lists
                tables = driver_service.driver.find_elements(By.TAG_NAME, 'table')
                print(f"  Tables found: {len(tables)}")

                # Find cards/items
                cards = driver_service.driver.find_elements(By.CSS_SELECTOR, '[class*="card"], [class*="item"], [class*="referral"], [class*="lead"]')
                print(f"  Card-like elements: {len(cards)}")

                # Find buttons
                buttons = driver_service.driver.find_elements(By.TAG_NAME, 'button')
                button_texts = [b.text.strip() for b in buttons if b.text.strip()]
                print(f"  Buttons: {button_texts[:10]}")

                # Look for status dropdowns or selects
                selects = driver_service.driver.find_elements(By.TAG_NAME, 'select')
                print(f"  Select dropdowns: {len(selects)}")

                # Look for status-related text
                if 'status' in page_source.lower():
                    print("  Found 'status' in page!")

                # Try to find lead names
                print("\n  Looking for lead/referral entries...")

                # Common patterns for lead lists
                list_items = driver_service.driver.find_elements(By.CSS_SELECTOR, 'tr, [class*="row"], [class*="list-item"]')
                for item in list_items[:10]:
                    text = item.text.strip()[:100]
                    if text and len(text) > 10:
                        print(f"    - {text}...")

        # Now let's try to find and click on a specific referral
        print("\n" + "=" * 60)
        print("LOOKING FOR INDIVIDUAL REFERRAL VIEW")
        print("=" * 60)

        driver_service.get_page("https://agentpronto.com/app/referrals")
        time.sleep(3)

        # Try to find clickable referral links
        all_links = driver_service.driver.find_elements(By.TAG_NAME, 'a')
        referral_links = []
        for link in all_links:
            href = link.get_attribute('href') or ''
            text = link.text.strip()
            if '/referral/' in href or '/lead/' in href:
                referral_links.append((text, href))

        print(f"\nReferral/lead links found: {len(referral_links)}")
        for text, href in referral_links[:5]:
            print(f"  - {text}: {href}")

        # Click on first referral if found
        if referral_links:
            print(f"\nClicking on first referral: {referral_links[0][1]}")
            driver_service.get_page(referral_links[0][1])
            time.sleep(3)
            driver_service.driver.save_screenshot("explore_referral_detail.png")

            # Analyze the detail page
            print("\n" + "=" * 60)
            print("REFERRAL DETAIL PAGE ANALYSIS")
            print("=" * 60)

            # Look for status options
            selects = driver_service.driver.find_elements(By.TAG_NAME, 'select')
            for select in selects:
                options = select.find_elements(By.TAG_NAME, 'option')
                if options:
                    print(f"\nSelect dropdown options:")
                    for opt in options:
                        print(f"  - {opt.text} (value: {opt.get_attribute('value')})")

            # Look for buttons that might be status updates
            buttons = driver_service.driver.find_elements(By.TAG_NAME, 'button')
            for btn in buttons:
                text = btn.text.strip()
                if text and len(text) < 50:
                    print(f"Button: {text}")

            # Look for form elements
            forms = driver_service.driver.find_elements(By.TAG_NAME, 'form')
            print(f"\nForms found: {len(forms)}")

            # Look for textarea (notes)
            textareas = driver_service.driver.find_elements(By.TAG_NAME, 'textarea')
            print(f"Textareas found: {len(textareas)}")

            # Try clicking on different tabs if they exist
            tabs = driver_service.driver.find_elements(By.CSS_SELECTOR, '[role="tab"], [class*="tab"]')
            print(f"\nTabs found: {len(tabs)}")
            for tab in tabs:
                print(f"  - {tab.text}")
        else:
            # Maybe leads are shown differently - look for any clickable elements with names
            print("\nNo direct referral links found. Looking for other patterns...")

            # Try clicking on table rows
            rows = driver_service.driver.find_elements(By.CSS_SELECTOR, 'tr[class*="click"], tr:not(:first-child), [class*="clickable"]')
            print(f"Clickable rows: {len(rows)}")

        print("\n" + "=" * 60)
        print("EXPLORATION COMPLETE")
        print("=" * 60)
        print("\nScreenshots saved. Browser will stay open for 300 seconds.")
        print("Please manually explore and note:")
        print("  1. How to find a specific referral")
        print("  2. What status options are available")
        print("  3. How to update a referral status")
        print("  4. How to add notes")
        print("\nPress Ctrl+C to close earlier")
        print("=" * 60)

        try:
            time.sleep(300)
        except KeyboardInterrupt:
            print("\nClosing...")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        time.sleep(60)

    finally:
        print("Closing browser...")
        driver_service.close()

if __name__ == "__main__":
    explore_agent_pronto()
