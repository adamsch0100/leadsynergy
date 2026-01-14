"""Explore My Agent Finder status update flow"""
import os
import sys
import time

os.environ["SELENIUM_HEADLESS"] = "false"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.referral_scrapers.utils.driver_service import DriverService
from selenium.webdriver.common.by import By

EMAIL = os.getenv("MY_AGENT_FINDER_EMAIL")
PASSWORD = os.getenv("MY_AGENT_FINDER_PASSWORD")

print("=" * 60)
print("MY AGENT FINDER - STATUS UPDATE EXPLORATION")
print("=" * 60)

driver_service = DriverService()

try:
    driver_service.initialize_driver()
    driver = driver_service.driver

    # Login
    print("\n[1] Logging in...")
    driver.get("https://app.myagentfinder.com/login")
    time.sleep(3)

    email_field = driver.find_element(By.CSS_SELECTOR, 'input[type="email"]')
    email_field.send_keys(EMAIL)
    pass_field = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
    pass_field.send_keys(PASSWORD)
    time.sleep(1)

    btn = driver.find_element(By.CSS_SELECTOR, "button[type='button']")
    driver.execute_script("arguments[0].click();", btn)
    time.sleep(5)

    if "dashboard" in driver.current_url.lower():
        print("    Login successful!")
    else:
        print("    Login may have failed")

    # Go to All Active
    print("\n[2] Going to All Active referrals...")
    driver.get("https://app.myagentfinder.com/referral/active/allactive")
    time.sleep(3)

    # Find the table rows
    print("\n[3] Finding referral rows...")

    # Look for table rows with lead data
    rows = driver.find_elements(By.CSS_SELECTOR, 'table tbody tr, tr')
    print(f"    Found {len(rows)} table rows")

    # Find a clickable lead - look for links or buttons in the ACTION column
    action_elements = driver.find_elements(By.CSS_SELECTOR, '[class*="action"], td:first-child a, td:first-child button')
    print(f"    Found {len(action_elements)} action elements")

    # Try finding by lead name
    lead_name = "Dean Askew"  # First lead from previous output
    print(f"\n[4] Looking for lead: {lead_name}")

    # Try to find the lead name in the page and click nearby action
    try:
        name_elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{lead_name}')]")
        print(f"    Found {len(name_elements)} elements with name")

        for elem in name_elements:
            print(f"      Tag: {elem.tag_name}, Text: {elem.text[:50]}")

            # Try to find parent row
            try:
                parent_row = elem.find_element(By.XPATH, "./ancestor::tr")
                print(f"      Found parent row")

                # Look for action button/link in this row
                actions = parent_row.find_elements(By.CSS_SELECTOR, 'a, button')
                for action in actions:
                    href = action.get_attribute('href') or ''
                    text = action.text.strip()
                    if text or href:
                        print(f"        Action: '{text}' -> {href[:50] if href else 'no href'}")
            except:
                pass
    except Exception as e:
        print(f"    Error: {e}")

    # Look for any edit/update buttons
    print("\n[5] Looking for edit/update buttons...")
    edit_btns = driver.find_elements(By.CSS_SELECTOR, '[class*="edit"], [class*="update"], [class*="action"] a, [class*="action"] button')
    for btn in edit_btns[:10]:
        try:
            href = btn.get_attribute('href') or ''
            text = btn.text.strip()
            onclick = btn.get_attribute('onclick') or ''
            print(f"    '{text}' -> {href[:50] if href else onclick[:50] if onclick else 'no action'}")
        except:
            pass

    # Try to find a referral detail page link pattern
    print("\n[6] Looking for referral detail links...")
    all_links = driver.find_elements(By.TAG_NAME, 'a')
    referral_links = []
    for link in all_links:
        href = link.get_attribute('href') or ''
        if '/referral/' in href and href not in [l[0] for l in referral_links]:
            text = link.text.strip()[:30]
            referral_links.append((href, text))

    print(f"    Found {len(referral_links)} referral links:")
    for href, text in referral_links[:15]:
        print(f"      '{text}' -> {href}")

    # Click on first referral that looks like a detail page
    print("\n[7] Trying to click on a referral to see detail page...")
    detail_link = None
    for href, text in referral_links:
        # Look for links that might be referral details (not category pages)
        if '/referral/' in href and '/active/' not in href:
            detail_link = href
            break

    if not detail_link:
        # Try clicking on a row to see if it opens details
        print("    No direct detail link found, trying to click on row...")
        try:
            first_data_row = driver.find_element(By.CSS_SELECTOR, 'table tbody tr:first-child')
            driver.execute_script("arguments[0].click();", first_data_row)
            time.sleep(2)
            print(f"    Clicked row, now at: {driver.current_url}")
            driver.save_screenshot("maf_after_row_click.png")
        except Exception as e:
            print(f"    Could not click row: {e}")
    else:
        print(f"    Navigating to: {detail_link}")
        driver.get(detail_link)
        time.sleep(3)
        driver.save_screenshot("maf_referral_detail.png")
        print(f"    Now at: {driver.current_url}")

    # Check current page for status options
    print("\n[8] Looking for status options on current page...")

    # Look for select dropdowns
    selects = driver.find_elements(By.TAG_NAME, 'select')
    print(f"    Select dropdowns: {len(selects)}")
    for select in selects:
        try:
            name = select.get_attribute('name') or select.get_attribute('id') or ''
            options = select.find_elements(By.TAG_NAME, 'option')
            print(f"      Select '{name}': {len(options)} options")
            for opt in options[:10]:
                print(f"        - {opt.text}")
        except:
            pass

    # Look for radio buttons
    radios = driver.find_elements(By.CSS_SELECTOR, 'input[type="radio"]')
    print(f"    Radio buttons: {len(radios)}")
    for radio in radios:
        try:
            value = radio.get_attribute('value') or ''
            name = radio.get_attribute('name') or ''
            label = ''
            try:
                label_elem = driver.find_element(By.CSS_SELECTOR, f'label[for="{radio.get_attribute("id")}"]')
                label = label_elem.text
            except:
                pass
            print(f"      Radio: name='{name}', value='{value}', label='{label}'")
        except:
            pass

    # Print page content
    print("\n[9] Page content:")
    print("-" * 40)
    body = driver.find_element(By.TAG_NAME, 'body').text
    print(body[:2000].encode('ascii', 'replace').decode('ascii'))
    print("-" * 40)

    print("\n[10] Browser staying open for 180s - explore manually...")
    print("     Look for: status dropdown, update button, detail pages")
    time.sleep(180)

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
    try:
        time.sleep(60)
    except:
        pass

finally:
    print("\nClosing browser...")
    driver_service.close()
