"""Explore My Agent Finder status dropdown options"""
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
print("MY AGENT FINDER - STATUS OPTIONS EXPLORATION")
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
    print("    Login complete!")

    # Go to All Active to find a referral
    print("\n[2] Going to All Active referrals...")
    driver.get("https://app.myagentfinder.com/referral/active/allactive")
    time.sleep(3)

    # Find first referral row and get the detail link
    print("\n[3] Finding a referral to click...")

    # Look for links that go to referral detail pages
    # Pattern: /opp/{id}/referral or similar
    all_links = driver.find_elements(By.TAG_NAME, 'a')
    referral_detail_link = None

    for link in all_links:
        href = link.get_attribute('href') or ''
        # Look for /opp/ pattern which seems to be the detail page based on screenshot
        if '/opp/' in href and '/referral' in href:
            referral_detail_link = href
            print(f"    Found referral link: {href}")
            break

    if not referral_detail_link:
        # Try clicking on a table row
        print("    No direct link found, looking for clickable rows...")
        rows = driver.find_elements(By.CSS_SELECTOR, 'table tbody tr')
        if rows:
            # Click on first row
            driver.execute_script("arguments[0].click();", rows[0])
            time.sleep(3)
            referral_detail_link = driver.current_url
            print(f"    Clicked row, now at: {referral_detail_link}")
    else:
        driver.get(referral_detail_link)
        time.sleep(3)

    print(f"\n[4] On referral detail page: {driver.current_url}")
    driver.save_screenshot("maf_referral_detail.png")

    # Find the Status dropdown (MUI Autocomplete)
    print("\n[5] Looking for Status dropdown...")

    # The Status field is a MUI Autocomplete with a popup indicator button
    status_selectors = [
        '.MuiAutocomplete-popupIndicator',  # The dropdown arrow button
        'button[aria-label="Open"]',
        'input[role="combobox"]',
        '#\\:r5\\:',  # The specific ID from the HTML
        'input.MuiAutocomplete-input',
    ]

    status_trigger = None
    for selector in status_selectors:
        try:
            status_trigger = driver.find_element(By.CSS_SELECTOR, selector)
            if status_trigger:
                print(f"    Found status element: {selector}")
                break
        except:
            continue

    if status_trigger:
        print("\n[6] Clicking to open status dropdown...")
        driver.execute_script("arguments[0].click();", status_trigger)
        time.sleep(2)
        driver.save_screenshot("maf_status_dropdown_open.png")

        # Now find the dropdown options
        print("\n[7] Looking for status options...")

        # MUI Autocomplete options are typically in a listbox
        option_selectors = [
            '.MuiAutocomplete-listbox li',
            '.MuiAutocomplete-option',
            '[role="listbox"] [role="option"]',
            '.MuiAutocomplete-popper li',
            'ul[role="listbox"] li',
        ]

        options = []
        for selector in option_selectors:
            try:
                option_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if option_elements:
                    print(f"    Found {len(option_elements)} options with selector: {selector}")
                    for opt in option_elements:
                        text = opt.text.strip()
                        if text and text not in options:
                            options.append(text)
                    break
            except:
                continue

        if options:
            print("\n" + "=" * 60)
            print("STATUS OPTIONS FOUND:")
            print("=" * 60)
            for i, opt in enumerate(options, 1):
                print(f"  {i}. {opt}")
            print("=" * 60)
        else:
            # Try getting all visible text that might be options
            print("    No options found with standard selectors, checking page...")
            page_source = driver.page_source

            # Look for option-like patterns
            import re
            # MUI options often have data-option-index
            matches = re.findall(r'data-option-index="\d+"[^>]*>([^<]+)<', page_source)
            if matches:
                print("\n    Found options via regex:")
                for m in matches:
                    print(f"      - {m}")
    else:
        print("    Could not find Status dropdown element")

    # Also look at the current page structure
    print("\n[8] Page content (Keep Us Informed section):")
    print("-" * 40)
    body = driver.find_element(By.TAG_NAME, 'body').text
    # Find the "Keep Us Informed" section
    if "Keep Us Informed" in body:
        start = body.find("Keep Us Informed")
        end = body.find("History", start) if "History" in body[start:] else start + 500
        section = body[start:end]
        print(section.encode('ascii', 'replace').decode('ascii'))
    print("-" * 40)

    print("\n[9] Browser staying open for 120s...")
    print("    Please manually click the Status dropdown to see all options")
    print("    Then share the options you see!")
    time.sleep(120)

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
