"""
Explore Agent Pronto deal DETAIL page to see status options
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

def explore_deal_detail():
    driver_service = DriverService()

    print("=" * 60)
    print("Agent Pronto - Exploring Deal Detail Page")
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

        # Go directly to the Marvin Holland deal
        print("\n[2] Going to deal detail page...")
        driver_service.get_page("https://agentpronto.com/app/deals/846895")
        time.sleep(3)
        driver_service.driver.save_screenshot("deal_detail_page.png")

        print("\n" + "=" * 60)
        print("DEAL DETAIL PAGE - Marvin Holland")
        print("=" * 60)

        # Get all page text
        body_text = driver_service.driver.find_element(By.TAG_NAME, 'body').text
        # Encode to handle special characters
        safe_text = body_text.encode('ascii', 'replace').decode('ascii')
        print(f"\nPage content:\n{safe_text}")

        # Look for status elements
        print("\n\n" + "=" * 60)
        print("LOOKING FOR STATUS OPTIONS")
        print("=" * 60)

        # Find all select elements
        selects = driver_service.driver.find_elements(By.TAG_NAME, 'select')
        print(f"\nSelect dropdowns: {len(selects)}")
        for i, select in enumerate(selects):
            print(f"\n  Select #{i}:")
            name = select.get_attribute('name') or select.get_attribute('id') or 'unnamed'
            print(f"    Name/ID: {name}")
            options = select.find_elements(By.TAG_NAME, 'option')
            print(f"    Options ({len(options)}):")
            for opt in options:
                val = opt.get_attribute('value')
                txt = opt.text
                selected = opt.is_selected()
                print(f"      - '{txt}' (value='{val}') {'<-- SELECTED' if selected else ''}")

        # Find all buttons
        buttons = driver_service.driver.find_elements(By.TAG_NAME, 'button')
        print(f"\nButtons: {len(buttons)}")
        for btn in buttons:
            text = btn.text.strip()
            if text:
                print(f"  - {text}")

        # Find radio buttons
        radios = driver_service.driver.find_elements(By.CSS_SELECTOR, 'input[type="radio"]')
        print(f"\nRadio buttons: {len(radios)}")
        for radio in radios:
            name = radio.get_attribute('name')
            value = radio.get_attribute('value')
            label = radio.find_element(By.XPATH, './following-sibling::label | ./parent::label').text if radio else ""
            print(f"  - name={name}, value={value}, label={label}")

        # Find forms
        forms = driver_service.driver.find_elements(By.TAG_NAME, 'form')
        print(f"\nForms: {len(forms)}")
        for i, form in enumerate(forms):
            action = form.get_attribute('action')
            method = form.get_attribute('method')
            print(f"  Form #{i}: action={action}, method={method}")
            inputs = form.find_elements(By.TAG_NAME, 'input')
            for inp in inputs:
                inp_type = inp.get_attribute('type')
                inp_name = inp.get_attribute('name')
                inp_val = inp.get_attribute('value')
                print(f"    - input: type={inp_type}, name={inp_name}, value={inp_val[:30] if inp_val else ''}")

        # Find textareas (for notes)
        textareas = driver_service.driver.find_elements(By.TAG_NAME, 'textarea')
        print(f"\nTextareas: {len(textareas)}")
        for ta in textareas:
            name = ta.get_attribute('name') or ta.get_attribute('id')
            placeholder = ta.get_attribute('placeholder')
            print(f"  - name={name}, placeholder={placeholder}")

        # Look for any element containing "status" in attributes
        print("\n\nElements with 'status' in attributes/text:")
        status_elements = driver_service.driver.find_elements(By.XPATH, '//*[contains(@*, "status") or contains(text(), "Status") or contains(text(), "status")]')
        for el in status_elements[:10]:
            tag = el.tag_name
            text = el.text[:50] if el.text else ""
            classes = el.get_attribute('class') or ""
            print(f"  [{tag}] class={classes[:30]} text='{text}'")

        # Look for dropdown/listbox
        print("\n\nLooking for dropdown/listbox elements:")
        listboxes = driver_service.driver.find_elements(By.CSS_SELECTOR, '[role="listbox"], [role="combobox"], [class*="dropdown"], [class*="select"]')
        for lb in listboxes:
            print(f"  - {lb.tag_name}: {lb.get_attribute('class')[:50]}")

        print("\n\n" + "=" * 60)
        print("Browser stays open - please explore manually")
        print("Look for: status dropdown, update button, notes field")
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
    explore_deal_detail()
