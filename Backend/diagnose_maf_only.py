#!/usr/bin/env python3
"""Quick diagnostic for MyAgentFinder with correct URL"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.referral_scrapers.my_agent_finder.my_agent_finder_service import MyAgentFinderService
from app.service.lead_service import LeadServiceSingleton
from selenium.webdriver.common.by import By
import time

def main():
    print("="*80)
    print("MYAGENTFINDER DIAGNOSTIC - Correct URL")
    print("="*80)

    lead_service = LeadServiceSingleton.get_instance()
    leads = lead_service.get_by_source('MyAgentFinder', limit=1, offset=0)

    if not leads:
        print("ERROR: No MyAgentFinder leads found")
        return

    test_lead = leads[0]
    print(f"Using test lead: {test_lead.first_name} {test_lead.last_name}")

    service = MyAgentFinderService(
        lead=test_lead,
        status={"status": "Pending", "note": ""},
        organization_id=getattr(test_lead, 'organization_id', None)
    )

    try:
        print("Initializing browser...")
        service.driver_service.initialize_driver()

        # Use CORRECT URL
        print("Navigating to CORRECT MyAgentFinder login URL...")
        service.driver_service.driver.get("https://app.myagentfinder.com/login")
        time.sleep(3)

        screenshot_path = f"maf_correct_url_{datetime.now().strftime('%H%M%S')}.png"
        service.driver_service.driver.save_screenshot(screenshot_path)
        print(f"Screenshot saved: {screenshot_path}")

        print("\n--- ALL INPUT FIELDS ---")
        inputs = service.driver_service.driver.find_elements(By.TAG_NAME, "input")
        print(f"Found {len(inputs)} input fields")

        for i, inp in enumerate(inputs):
            try:
                input_type = inp.get_attribute("type") or ""
                name = inp.get_attribute("name") or ""
                id_attr = inp.get_attribute("id") or ""
                placeholder = inp.get_attribute("placeholder") or ""
                autocomplete = inp.get_attribute("autocomplete") or ""

                print(f"\n[{i}] INPUT:")
                print(f"  Type: {input_type}")
                print(f"  Name: {name}")
                print(f"  ID: {id_attr}")
                print(f"  Placeholder: {placeholder}")
                print(f"  Autocomplete: {autocomplete}")
                if i < 5:  # Show HTML for first 5
                    print(f"  HTML: {inp.get_attribute('outerHTML')[:150]}")
            except Exception as e:
                print(f"  Error: {e}")

        print("\n--- ALL BUTTONS ---")
        buttons = service.driver_service.driver.find_elements(By.TAG_NAME, "button")
        print(f"Found {len(buttons)} buttons")

        for i, btn in enumerate(buttons[:10]):  # First 10
            try:
                text = btn.text.strip()
                btn_type = btn.get_attribute("type") or ""
                print(f"\n[{i}] BUTTON: '{text}'")
                print(f"  Type: {btn_type}")
                if i < 3:
                    print(f"  HTML: {btn.get_attribute('outerHTML')[:150]}")
            except:
                pass

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

if __name__ == "__main__":
    main()
