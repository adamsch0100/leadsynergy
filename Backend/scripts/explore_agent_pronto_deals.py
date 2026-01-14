"""
Explore Agent Pronto DEALS page to understand lead structure
"""
import os
import sys
import time
from datetime import datetime, timezone

os.environ["SELENIUM_HEADLESS"] = "false"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.referral_scrapers.utils.driver_service import DriverService
from app.referral_scrapers.agent_pronto.agent_pronto_service import get_agent_pronto_magic_link
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

from app.utils.constants import Credentials
CREDS = Credentials()

AGENT_PRONTO_EMAIL = "online@saahomes.com"
GMAIL_EMAIL = CREDS.GMAIL_EMAIL
GMAIL_APP_PASSWORD = CREDS.GMAIL_APP_PASSWORD

def explore_deals():
    driver_service = DriverService()

    print("=" * 60)
    print("Agent Pronto DEALS Explorer")
    print("=" * 60)

    try:
        print("\n[1] Initializing and logging in...")
        driver_service.initialize_driver()
        driver_service.get_page("https://agentpronto.com/sign-in")
        time.sleep(3)

        email_field = driver_service.driver.find_element(By.CSS_SELECTOR, 'input[name="email"]')
        email_field.send_keys(AGENT_PRONTO_EMAIL)
        time.sleep(1)

        magic_link_request_time = datetime.now(timezone.utc)
        driver_service.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        time.sleep(3)

        print("    Waiting for magic link...")
        magic_link = get_agent_pronto_magic_link(
            email_address=GMAIL_EMAIL,
            app_password=GMAIL_APP_PASSWORD,
            max_retries=20,
            retry_delay=3.0,
            max_age_seconds=300,
            min_email_time=magic_link_request_time
        )

        if not magic_link:
            print("    ERROR: No magic link")
            return

        driver_service.get_page(magic_link)
        time.sleep(5)
        print("    Logged in!")

        # Go directly to In Progress deals
        print("\n[2] Navigating to In Progress deals...")
        driver_service.get_page("https://agentpronto.com/app/deals?status=in-progress")
        time.sleep(3)
        driver_service.driver.save_screenshot("deals_in_progress.png")

        print("\n" + "=" * 60)
        print("IN PROGRESS DEALS PAGE")
        print("=" * 60)

        # Get page HTML for analysis
        page_source = driver_service.driver.page_source
        page_text = driver_service.driver.find_element(By.TAG_NAME, 'body').text

        print(f"\nPage text preview (first 1000 chars):\n{page_text[:1000]}")

        # Find all clickable elements that might be deals
        print("\n\nLooking for deal entries...")

        # Try various selectors
        selectors_to_try = [
            'a[href*="deal"]',
            'div[class*="deal"]',
            'div[class*="card"]',
            'div[class*="item"]',
            'div[class*="row"]',
            '[class*="referral"]',
            'button',
            'a'
        ]

        for selector in selectors_to_try:
            elements = driver_service.driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                print(f"\n{selector}: {len(elements)} elements")
                for el in elements[:5]:
                    text = el.text.strip()[:80] if el.text else ""
                    href = el.get_attribute('href') or ""
                    onclick = el.get_attribute('onclick') or ""
                    classes = el.get_attribute('class') or ""
                    if text or href:
                        print(f"  - text: '{text}' | href: {href[:50] if href else 'none'} | class: {classes[:30]}")

        # Try to find the deal by looking for customer name or deal ID in the DOM
        print("\n\nLooking for specific deal content...")

        # Get all text nodes
        all_elements = driver_service.driver.find_elements(By.XPATH, '//*[string-length(text()) > 0]')
        print(f"\nAll elements with text: {len(all_elements)}")
        for el in all_elements:
            text = el.text.strip()
            if text and len(text) > 5 and len(text) < 100:
                tag = el.tag_name
                classes = el.get_attribute('class') or ""
                print(f"  [{tag}] ({classes[:20]}): {text}")

        # Now try to click on any deal-like element
        print("\n\n" + "=" * 60)
        print("TRYING TO CLICK ON A DEAL")
        print("=" * 60)

        # Look for links that might be deals
        all_links = driver_service.driver.find_elements(By.TAG_NAME, 'a')
        deal_links = []
        for link in all_links:
            href = link.get_attribute('href') or ""
            text = link.text.strip()
            if '/deal' in href.lower() or 'progress' in text.lower() or (text and len(text) > 10 and 'pronto' not in text.lower()):
                deal_links.append((link, text, href))

        print(f"\nPotential deal links: {len(deal_links)}")
        for link, text, href in deal_links:
            print(f"  - '{text}' -> {href}")

        if deal_links:
            # Click the first one
            link, text, href = deal_links[0]
            print(f"\nClicking: '{text}'")

            try:
                link.click()
                time.sleep(3)
                driver_service.driver.save_screenshot("deal_detail.png")

                print(f"\nLanded at: {driver_service.get_current_url()}")

                # Analyze detail page
                print("\n" + "=" * 60)
                print("DEAL DETAIL PAGE")
                print("=" * 60)

                detail_text = driver_service.driver.find_element(By.TAG_NAME, 'body').text
                print(f"\nPage text:\n{detail_text[:2000]}")

                # Look for status dropdown or buttons
                print("\n\nLooking for status controls...")

                selects = driver_service.driver.find_elements(By.TAG_NAME, 'select')
                print(f"Select dropdowns: {len(selects)}")
                for select in selects:
                    options = select.find_elements(By.TAG_NAME, 'option')
                    print(f"  Options: {[o.text for o in options]}")

                buttons = driver_service.driver.find_elements(By.TAG_NAME, 'button')
                print(f"\nButtons: {[b.text for b in buttons if b.text.strip()]}")

                # Look for status text
                status_elements = driver_service.driver.find_elements(By.XPATH, '//*[contains(text(), "Status") or contains(text(), "status")]')
                print(f"\nStatus-related elements: {len(status_elements)}")
                for el in status_elements:
                    print(f"  - {el.text[:100]}")

            except Exception as e:
                print(f"Click failed: {e}")

        print("\n\n" + "=" * 60)
        print("EXPLORATION COMPLETE")
        print("=" * 60)
        print("\nBrowser stays open for 300 seconds for manual exploration")
        print("Press Ctrl+C to close")

        time.sleep(300)

    except KeyboardInterrupt:
        print("\nClosing...")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        time.sleep(60)
    finally:
        driver_service.close()

if __name__ == "__main__":
    explore_deals()
