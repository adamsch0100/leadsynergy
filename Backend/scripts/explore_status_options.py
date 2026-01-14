"""
Click Update Status to see available status options
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

from app.utils.constants import Credentials
CREDS = Credentials()

def explore_status_options():
    driver_service = DriverService()

    print("=" * 60)
    print("Agent Pronto - Finding Status Options")
    print("=" * 60)

    try:
        print("\n[1] Logging in...")
        driver_service.initialize_driver()
        driver_service.get_page("https://agentpronto.com/sign-in")
        time.sleep(3)

        driver_service.driver.find_element(By.CSS_SELECTOR, 'input[name="email"]').send_keys("online@saahomes.com")
        time.sleep(1)

        magic_link_request_time = datetime.now(timezone.utc)
        driver_service.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        time.sleep(3)

        magic_link = get_agent_pronto_magic_link(
            email_address=CREDS.GMAIL_EMAIL,
            app_password=CREDS.GMAIL_APP_PASSWORD,
            max_retries=20,
            retry_delay=3.0,
            max_age_seconds=300,
            min_email_time=magic_link_request_time
        )

        if not magic_link:
            print("ERROR: No magic link")
            return

        driver_service.get_page(magic_link)
        time.sleep(5)
        print("    Logged in!")

        # Go to deal detail page
        print("\n[2] Going to deal page...")
        driver_service.get_page("https://agentpronto.com/app/deals/846895")
        time.sleep(3)

        # Find and click Update Status
        print("\n[3] Looking for 'Update Status' button...")

        # Try different selectors
        update_btn = None
        selectors = [
            'a.button-alert',
            'a[href*="status"]',
            'button[class*="status"]',
            '//*[contains(text(), "Update Status")]',
        ]

        for selector in selectors:
            try:
                if selector.startswith('//'):
                    update_btn = driver_service.driver.find_element(By.XPATH, selector)
                else:
                    update_btn = driver_service.driver.find_element(By.CSS_SELECTOR, selector)
                if update_btn:
                    print(f"    Found with: {selector}")
                    print(f"    Text: {update_btn.text}")
                    print(f"    Href: {update_btn.get_attribute('href')}")
                    break
            except:
                continue

        if update_btn:
            print("\n[4] Clicking Update Status...")
            href = update_btn.get_attribute('href')
            if href:
                # Navigate directly to the URL
                driver_service.get_page(href)
            else:
                update_btn.click()
            time.sleep(3)
            driver_service.driver.save_screenshot("status_update_page.png")

            print(f"\nLanded at: {driver_service.get_current_url()}")

            # Get page content
            body_text = driver_service.driver.find_element(By.TAG_NAME, 'body').text
            safe_text = body_text.encode('ascii', 'replace').decode('ascii')
            print(f"\n" + "=" * 60)
            print("STATUS UPDATE PAGE CONTENT")
            print("=" * 60)
            print(safe_text)

            # Look for status options
            print("\n" + "=" * 60)
            print("LOOKING FOR STATUS OPTIONS")
            print("=" * 60)

            # Find select dropdowns
            selects = driver_service.driver.find_elements(By.TAG_NAME, 'select')
            print(f"\nSelect dropdowns: {len(selects)}")
            for select in selects:
                name = select.get_attribute('name') or select.get_attribute('id') or 'unnamed'
                options = select.find_elements(By.TAG_NAME, 'option')
                print(f"\n  {name}:")
                for opt in options:
                    print(f"    - {opt.text} (value={opt.get_attribute('value')})")

            # Find radio buttons
            radios = driver_service.driver.find_elements(By.CSS_SELECTOR, 'input[type="radio"]')
            print(f"\nRadio buttons: {len(radios)}")
            for radio in radios:
                name = radio.get_attribute('name')
                value = radio.get_attribute('value')
                checked = radio.is_selected()
                # Try to find label
                try:
                    label_el = driver_service.driver.find_element(By.CSS_SELECTOR, f'label[for="{radio.get_attribute("id")}"]')
                    label = label_el.text
                except:
                    label = ""
                print(f"    - name={name}, value={value}, label='{label}', checked={checked}")

            # Find all buttons
            buttons = driver_service.driver.find_elements(By.TAG_NAME, 'button')
            print(f"\nButtons:")
            for btn in buttons:
                text = btn.text.strip()
                btn_type = btn.get_attribute('type')
                if text and len(text) < 50:
                    print(f"    - {text} (type={btn_type})")

            # Find form
            forms = driver_service.driver.find_elements(By.TAG_NAME, 'form')
            print(f"\nForms: {len(forms)}")
            for form in forms:
                action = form.get_attribute('action')
                print(f"  Action: {action}")

                # All inputs
                inputs = form.find_elements(By.CSS_SELECTOR, 'input, select, textarea')
                for inp in inputs:
                    tag = inp.tag_name
                    name = inp.get_attribute('name')
                    inp_type = inp.get_attribute('type')
                    value = inp.get_attribute('value') or ""
                    print(f"    [{tag}] name={name}, type={inp_type}, value={value[:30]}")

            # Look for divs/buttons that look like status options
            print("\n\nLooking for status-related clickable elements:")
            status_candidates = driver_service.driver.find_elements(By.CSS_SELECTOR,
                '[class*="status"], [class*="option"], [role="radio"], [role="button"], [class*="selectable"]')
            for el in status_candidates[:20]:
                text = el.text[:50] if el.text else ""
                classes = el.get_attribute('class') or ""
                if text:
                    print(f"    - {el.tag_name}: '{text}' (class={classes[:30]})")

        else:
            print("    Could not find Update Status button!")

        print("\n\n" + "=" * 60)
        print("Browser stays open for manual exploration")
        print("=" * 60)

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
    explore_status_options()
