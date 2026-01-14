"""
Exploration script for My Agent Finder platform
- Login and explore the dashboard
- Find where leads/referrals are displayed
- Understand the status update flow
- Identify available status options
"""
import os
import sys
import time

# Set headless mode to false so we can see the browser
os.environ["SELENIUM_HEADLESS"] = "false"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.referral_scrapers.utils.driver_service import DriverService
from selenium.webdriver.common.by import By
from dotenv import load_dotenv

load_dotenv()

# Credentials
EMAIL = os.getenv("MY_AGENT_FINDER_EMAIL")
PASSWORD = os.getenv("MY_AGENT_FINDER_PASSWORD")

LOGIN_URL = "https://app.myagentfinder.com/login"
DASHBOARD_URL = "https://app.myagentfinder.com/dashboard"


def explore_myagentfinder():
    driver_service = DriverService()

    print("=" * 60)
    print("My Agent Finder - Platform Exploration")
    print("=" * 60)
    print(f"\nEmail: {EMAIL[:3] if EMAIL else 'NOT SET'}...")
    print(f"Password: {'SET' if PASSWORD else 'NOT SET'}")

    if not EMAIL or not PASSWORD:
        print("\nERROR: Credentials not set in .env file")
        return

    try:
        print("\n[1] Initializing browser...")
        driver_service.initialize_driver()

        print(f"\n[2] Navigating to login page: {LOGIN_URL}")
        driver_service.get_page(LOGIN_URL)
        time.sleep(3)

        # Take screenshot of login page
        driver_service.driver.save_screenshot("maf_01_login_page.png")
        print("    Screenshot: maf_01_login_page.png")

        # Print page info
        print(f"\n    Current URL: {driver_service.get_current_url()}")
        print(f"    Page title: {driver_service.driver.title}")

        print("\n[3] Analyzing login page...")

        # Find form elements
        inputs = driver_service.driver.find_elements(By.TAG_NAME, 'input')
        print(f"    Input fields found: {len(inputs)}")
        for inp in inputs:
            inp_type = inp.get_attribute('type')
            inp_name = inp.get_attribute('name') or inp.get_attribute('id') or inp.get_attribute('placeholder')
            print(f"      - type='{inp_type}', name/id='{inp_name}'")

        buttons = driver_service.driver.find_elements(By.TAG_NAME, 'button')
        print(f"    Buttons found: {len(buttons)}")
        for btn in buttons:
            print(f"      - '{btn.text}' (type={btn.get_attribute('type')})")

        print("\n[4] Entering credentials...")

        # Find and fill email
        try:
            email_field = driver_service.driver.find_element(By.CSS_SELECTOR, 'input[type="email"], input[name="email"], input[id="email"]')
            email_field.clear()
            email_field.send_keys(EMAIL)
            print(f"    Entered email")
        except Exception as e:
            print(f"    ERROR finding email field: {e}")
            return

        time.sleep(1)

        # Find and fill password
        try:
            password_field = driver_service.driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
            password_field.clear()
            password_field.send_keys(PASSWORD)
            print(f"    Entered password")
        except Exception as e:
            print(f"    ERROR finding password field: {e}")
            return

        time.sleep(1)
        driver_service.driver.save_screenshot("maf_02_credentials_entered.png")

        print("\n[5] Clicking login button...")
        try:
            # Look for Sign In button (type="button" not "submit")
            submit_btn = None
            btn_selectors = [
                'button[type="submit"]',
                'button[type="button"]',
                "//button[contains(text(), 'Sign In')]",
                "//button[contains(text(), 'Login')]",
                "//button[contains(text(), 'Log in')]",
            ]

            for selector in btn_selectors:
                try:
                    if selector.startswith('//'):
                        submit_btn = driver_service.driver.find_element(By.XPATH, selector)
                    else:
                        submit_btn = driver_service.driver.find_element(By.CSS_SELECTOR, selector)
                    if submit_btn and submit_btn.is_displayed():
                        print(f"    Found button: {submit_btn.text}")
                        break
                except:
                    continue

            if submit_btn:
                # Use JavaScript click for better reliability
                driver_service.driver.execute_script("arguments[0].click();", submit_btn)
                print("    Clicked login button (via JS)")
            else:
                # Try enter key
                from selenium.webdriver.common.keys import Keys
                password_field.send_keys(Keys.RETURN)
                print("    Pressed Enter to submit")
        except Exception as e:
            print(f"    ERROR clicking login: {e}")

        print("    Waiting for login to complete...")
        time.sleep(8)

        # Check for error messages
        print("\n    Looking for error messages...")
        error_selectors = [
            '.error',
            '.alert',
            '[class*="error"]',
            '[class*="alert"]',
            '[role="alert"]',
            'p[class*="red"]',
            'span[class*="red"]',
        ]

        for selector in error_selectors:
            try:
                errors = driver_service.driver.find_elements(By.CSS_SELECTOR, selector)
                for err in errors:
                    if err.text.strip():
                        print(f"    ERROR MESSAGE: {err.text}")
            except:
                pass

        driver_service.driver.save_screenshot("maf_03_after_login.png")
        current_url = driver_service.get_current_url()
        print(f"    Current URL: {current_url}")

        # Check for login errors
        page_text = driver_service.driver.find_element(By.TAG_NAME, 'body').text
        if 'invalid' in page_text.lower() or 'error' in page_text.lower() or 'incorrect' in page_text.lower():
            print("    WARNING: Possible login error detected")

        if 'login' in current_url.lower() and 'dashboard' not in current_url.lower():
            print("    WARNING: Still on login page - login may have failed")
            driver_service.driver.save_screenshot("maf_login_failed.png")
        else:
            print("    Login appears successful!")

        print("\n[6] Exploring dashboard/main page...")
        print(f"    Page title: {driver_service.driver.title}")

        # Look for navigation links
        nav_links = driver_service.driver.find_elements(By.CSS_SELECTOR, 'a, nav a, .nav a, [class*="nav"] a')
        print(f"\n    Navigation links found: {len(nav_links)}")
        seen_links = set()
        for link in nav_links[:20]:
            href = link.get_attribute('href') or ''
            text = link.text.strip()
            if text and text not in seen_links and len(text) < 50:
                seen_links.add(text)
                print(f"      - '{text}' -> {href[:60] if href else 'no href'}")

        # Look for leads/referrals sections
        print("\n    Looking for leads/referrals sections...")
        keywords = ['lead', 'referral', 'client', 'customer', 'deal', 'prospect']
        for kw in keywords:
            elements = driver_service.driver.find_elements(By.XPATH, f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{kw}')]")
            if elements:
                print(f"      Found '{kw}' elements: {len(elements)}")

        # Look for tables or lists
        tables = driver_service.driver.find_elements(By.TAG_NAME, 'table')
        print(f"\n    Tables found: {len(tables)}")

        # Look for cards or list items that might be leads
        cards = driver_service.driver.find_elements(By.CSS_SELECTOR, '[class*="card"], [class*="item"], [class*="row"]')
        print(f"    Card/item elements: {len(cards)}")

        # Get page content
        print("\n" + "=" * 60)
        print("PAGE CONTENT (first 2000 chars)")
        print("=" * 60)
        body_text = driver_service.driver.find_element(By.TAG_NAME, 'body').text
        safe_text = body_text.encode('ascii', 'replace').decode('ascii')
        print(safe_text[:2000])

        # Try navigating to common referral pages
        print("\n[7] Trying referral pages...")
        common_urls = [
            "https://app.myagentfinder.com/dashboard",
            "https://app.myagentfinder.com/referral/active/allactive",
            "https://app.myagentfinder.com/referral/active/pending",
            "https://app.myagentfinder.com/referral/active/prospects",
            "https://app.myagentfinder.com/referral/active/clients",
            "https://app.myagentfinder.com/referral/active/undercontract",
            "https://app.myagentfinder.com/referral/active/nurture",
            "https://app.myagentfinder.com/referral/active/overdue",
        ]

        for url in common_urls:
            try:
                print(f"\n    Trying: {url}")
                driver_service.get_page(url)
                time.sleep(2)
                final_url = driver_service.get_current_url()
                if final_url and url.split('/')[-1] in final_url:
                    print(f"      SUCCESS - Page loaded!")
                    driver_service.driver.save_screenshot(f"maf_{url.split('/')[-1]}.png")

                    # Check for leads
                    page_text = driver_service.driver.find_element(By.TAG_NAME, 'body').text[:500]
                    safe_text = page_text.encode('ascii', 'replace').decode('ascii')
                    print(f"      Content preview: {safe_text[:200]}...")
                else:
                    print(f"      Redirected to: {final_url}")
            except Exception as e:
                print(f"      ERROR: {e}")

        print("\n" + "=" * 60)
        print("EXPLORATION COMPLETE")
        print("=" * 60)
        print("\nBrowser will stay open for 300 seconds for manual exploration.")
        print("Screenshots saved as maf_*.png")
        print("\nPress Ctrl+C to close earlier.")

        try:
            time.sleep(300)
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
        print("\nClosing browser...")
        driver_service.close()
        print("Done!")


if __name__ == "__main__":
    explore_myagentfinder()
