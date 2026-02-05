#!/usr/bin/env python3
"""
Diagnose actual platform issues by navigating to sites and inspecting elements
"""
import sys
import os
from datetime import datetime

# Add Backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.referral_scrapers.redfin.redfin_service import RedfinService
from app.referral_scrapers.my_agent_finder.my_agent_finder_service import MyAgentFinderService
from app.referral_scrapers.homelight.homelight_service import HomelightService
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
from app.service.lead_service import LeadServiceSingleton
from selenium.webdriver.common.by import By
import time

def diagnose_redfin():
    """Diagnose Redfin login issues"""
    print("\n" + "="*80)
    print("DIAGNOSING REDFIN")
    print("="*80)

    lead_service = LeadServiceSingleton.get_instance()

    # Get a test lead from Redfin
    leads = lead_service.get_by_source('Redfin', limit=1, offset=0)
    if not leads:
        print("ERROR: No Redfin leads found")
        return

    test_lead = leads[0]
    print(f"Using test lead: {test_lead.first_name} {test_lead.last_name}")

    print("Creating Redfin service...")
    service = RedfinService(
        lead=test_lead,
        status="Pending",
        organization_id=getattr(test_lead, 'organization_id', None),
        user_id=getattr(test_lead, 'user_id', None)
    )

    try:
        # Initialize driver
        print("Initializing browser...")
        service.driver_service.initialize_driver()

        print("Navigating to Redfin login page...")
        service.driver_service.driver.get("https://www.redfin.com/login")
        time.sleep(3)

        # Take screenshot
        screenshot_path = f"redfin_login_{datetime.now().strftime('%H%M%S')}.png"
        service.driver_service.driver.save_screenshot(screenshot_path)
        print(f"Screenshot saved: {screenshot_path}")

        # Try to find all button elements
        print("\n--- ALL BUTTONS ON PAGE ---")
        buttons = service.driver_service.driver.find_elements(By.TAG_NAME, "button")
        for i, btn in enumerate(buttons[:20]):  # First 20 buttons
            try:
                text = btn.text.strip()
                classes = btn.get_attribute("class") or ""
                data_test = btn.get_attribute("data-rf-test-name") or ""
                aria_label = btn.get_attribute("aria-label") or ""

                if "google" in text.lower() or "google" in classes.lower() or "google" in aria_label.lower():
                    print(f"\n[{i}] GOOGLE BUTTON FOUND:")
                    print(f"  Text: {text}")
                    print(f"  Classes: {classes}")
                    print(f"  data-rf-test-name: {data_test}")
                    print(f"  aria-label: {aria_label}")
                    print(f"  HTML: {btn.get_attribute('outerHTML')[:200]}")
            except:
                continue

        # Try to find all links
        print("\n--- ALL LINKS CONTAINING 'GOOGLE' ---")
        links = service.driver_service.driver.find_elements(By.TAG_NAME, "a")
        for i, link in enumerate(links):
            try:
                href = link.get_attribute("href") or ""
                text = link.text.strip()
                if "google" in href.lower() or "google" in text.lower():
                    print(f"\n[{i}] GOOGLE LINK:")
                    print(f"  Text: {text}")
                    print(f"  Href: {href}")
                    print(f"  HTML: {link.get_attribute('outerHTML')[:200]}")
            except:
                continue

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\nClosing browser...")
        try:
            service.close()
        except:
            pass


def diagnose_myagentfinder():
    """Diagnose MyAgentFinder login issues"""
    print("\n" + "="*80)
    print("DIAGNOSING MYAGENTFINDER")
    print("="*80)

    lead_service = LeadServiceSingleton.get_instance()

    # Get a test lead from MyAgentFinder
    leads = lead_service.get_by_source('MyAgentFinder', limit=1, offset=0)
    if not leads:
        print("ERROR: No MyAgentFinder leads found")
        return

    test_lead = leads[0]
    print(f"Using test lead: {test_lead.first_name} {test_lead.last_name}")

    print("Creating MyAgentFinder service...")
    service = MyAgentFinderService(
        lead=test_lead,
        status={"status": "Pending", "note": ""},
        organization_id=getattr(test_lead, 'organization_id', None)
    )

    try:
        # Initialize driver
        print("Initializing browser...")
        service.driver_service.initialize_driver()

        print("Navigating to MyAgentFinder login page...")
        service.driver_service.driver.get("https://myagentfinder.com/login")
        time.sleep(3)

        # Take screenshot
        screenshot_path = f"myagentfinder_login_{datetime.now().strftime('%H%M%S')}.png"
        service.driver_service.driver.save_screenshot(screenshot_path)
        print(f"Screenshot saved: {screenshot_path}")

        # Try to find all input elements
        print("\n--- ALL INPUT FIELDS ON PAGE ---")
        inputs = service.driver_service.driver.find_elements(By.TAG_NAME, "input")
        for i, inp in enumerate(inputs):
            try:
                input_type = inp.get_attribute("type") or ""
                name = inp.get_attribute("name") or ""
                id_attr = inp.get_attribute("id") or ""
                placeholder = inp.get_attribute("placeholder") or ""
                classes = inp.get_attribute("class") or ""
                autocomplete = inp.get_attribute("autocomplete") or ""

                print(f"\n[{i}] INPUT FIELD:")
                print(f"  Type: {input_type}")
                print(f"  Name: {name}")
                print(f"  ID: {id_attr}")
                print(f"  Placeholder: {placeholder}")
                print(f"  Classes: {classes}")
                print(f"  Autocomplete: {autocomplete}")
                print(f"  HTML: {inp.get_attribute('outerHTML')[:200]}")
            except:
                continue

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\nClosing browser...")
        try:
            service.close()
        except:
            pass


def diagnose_homelight():
    """Diagnose HomeLight table row issues"""
    print("\n" + "="*80)
    print("DIAGNOSING HOMELIGHT")
    print("="*80)

    lead_service = LeadServiceSingleton.get_instance()

    # Get a test lead from HomeLight
    leads = lead_service.get_by_source('HomeLight', limit=1, offset=0)
    if not leads:
        print("ERROR: No HomeLight leads found")
        return

    test_lead = leads[0]
    print(f"Using test lead: {test_lead.first_name} {test_lead.last_name}")

    print("Creating HomeLight service...")
    service = HomelightService(
        lead=test_lead,
        status="Pending",
        organization_id=getattr(test_lead, 'organization_id', None),
        same_status_note="Update note"
    )

    try:
        # Initialize driver
        print("Initializing browser...")
        service.driver_service.initialize_driver()

        print("Attempting login...")
        if not service.login():
            print("ERROR: Login failed")
            return

        print("Login successful!")
        time.sleep(3)

        # Take screenshot after login
        screenshot_path = f"homelight_after_login_{datetime.now().strftime('%H%M%S')}.png"
        service.driver_service.driver.save_screenshot(screenshot_path)
        print(f"Screenshot saved: {screenshot_path}")

        # Use test lead from initialization
        test_name = f"{test_lead.first_name} {test_lead.last_name}"
        print(f"\nTest lead: {test_name}")

        # Try to search
        print(f"\nSearching for: {test_name}")

        # Find search box
        print("Looking for search box...")
        search_box = service.driver_service.find_element(By.CSS_SELECTOR, 'input[placeholder="Search"]')
        print("Search box found!")

        # Clear and search
        search_box.clear()
        time.sleep(0.5)
        search_box.send_keys(test_name)
        time.sleep(0.5)

        from selenium.webdriver.common.keys import Keys
        search_box.send_keys(Keys.ENTER)
        print("Search submitted, waiting for results...")
        time.sleep(5)

        # Take screenshot after search
        screenshot_path = f"homelight_after_search_{datetime.now().strftime('%H%M%S')}.png"
        service.driver_service.driver.save_screenshot(screenshot_path)
        print(f"Screenshot saved: {screenshot_path}")

        # Try to find all clickable elements that might be referral rows
        print("\n--- LOOKING FOR REFERRAL ROWS ---")

        # Try various selectors
        selectors_to_try = [
            "a[data-test='referralsList-row']",
            "a[data-testid='referralsList-row']",
            "[data-test*='referral']",
            "[data-testid*='referral']",
            "a[href*='referral']",
            "div[role='row']",
            "tr",
            "a[class*='row']",
        ]

        for selector in selectors_to_try:
            try:
                elements = service.driver_service.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    print(f"\n[{selector}] Found {len(elements)} elements")
                    for i, elem in enumerate(elements[:3]):  # Show first 3
                        try:
                            text = elem.text.strip()[:100]
                            classes = elem.get_attribute("class") or ""
                            data_test = elem.get_attribute("data-test") or ""
                            print(f"  [{i}] Text: {text}")
                            print(f"      Classes: {classes[:100]}")
                            print(f"      data-test: {data_test}")
                        except:
                            continue
            except:
                continue

        # Show page source snippet
        print("\n--- PAGE SOURCE SNIPPET (looking for 'referral') ---")
        page_source = service.driver_service.driver.page_source
        lines = page_source.split('\n')
        for i, line in enumerate(lines):
            if 'referral' in line.lower() and i < 100:  # First occurrences
                print(f"Line {i}: {line.strip()[:200]}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\nClosing browser...")
        try:
            service.close()
        except:
            pass


def main():
    print("="*80)
    print("PLATFORM DIAGNOSTICS - Finding Actual Selectors")
    print("="*80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Diagnose each platform
    diagnose_redfin()
    diagnose_myagentfinder()
    diagnose_homelight()

    print("\n" + "="*80)
    print("DIAGNOSTICS COMPLETE")
    print("="*80)
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nCheck screenshots and output above for actual HTML elements.")


if __name__ == "__main__":
    main()
