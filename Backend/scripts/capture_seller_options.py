"""
Capture My Agent Finder SELLER dropdown options from Mary Kinney's referral
"""
import os
import sys
import time

os.environ["SELENIUM_HEADLESS"] = "false"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.referral_scrapers.my_agent_finder.my_agent_finder_service import MyAgentFinderService
from app.models.lead import Lead
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


def capture_seller_options():
    print("=" * 60)
    print("Capturing My Agent Finder SELLER Status Options")
    print("=" * 60)

    # Create a dummy lead just to initialize the service
    lead = Lead()
    lead.id = "test"
    lead.first_name = "Mary"
    lead.last_name = "Kinney"
    lead.source = "MyAgentFinder"
    lead.metadata = {}

    service = MyAgentFinderService(lead=lead, status="test")

    try:
        # Login
        print("\n[1] Logging in...", flush=True)
        if not service.login():
            print("Login failed!")
            return
        print("Logged in!", flush=True)

        # Navigate directly to Mary Kinney's seller referral
        print("\n[2] Navigating to Mary Kinney's seller referral...", flush=True)
        service.driver_service.get_page("https://app.myagentfinder.com/opp/13123ebc-2fe8-11ee-adb8-237b8b408ad1")
        time.sleep(3)

        print(f"\n[3] On detail page: {service.driver_service.get_current_url()}", flush=True)

        # Find the status dropdown input and click to open it
        print("\n[4] Opening status dropdown...", flush=True)
        status_input = service.driver_service.driver.find_element(By.CSS_SELECTOR, 'input.MuiAutocomplete-input')

        if status_input:
            # Get current value
            current_value = status_input.get_attribute('value')
            print(f"Current status: {current_value}", flush=True)

            # Click to open dropdown
            service.driver_service.driver.execute_script("arguments[0].click();", status_input)
            time.sleep(0.5)

            # Clear and press arrow to show all options
            status_input.clear()
            time.sleep(0.3)
            status_input.send_keys(Keys.ARROW_DOWN)
            time.sleep(1)

            # Capture options via JavaScript
            print("\n[5] Capturing SELLER options via JavaScript...", flush=True)

            options_js = """
            return Array.from(document.querySelectorAll('[role="listbox"] [role="option"], .MuiAutocomplete-listbox li, .MuiAutocomplete-option'))
                .map(opt => opt.textContent.trim());
            """
            options = service.driver_service.driver.execute_script(options_js)

            if options:
                print("\n" + "=" * 60)
                print("SELLER STATUS DROPDOWN OPTIONS:")
                print("=" * 60)
                for i, opt in enumerate(options, 1):
                    print(f"  {i}. \"{opt}\"")
                print("=" * 60)

                # Also print in Python dict format for easy copy
                print("\n# Python dict format:")
                print("SELLER_STATUS_OPTIONS = {")
                for opt in options:
                    key = opt.split(" - ")[0].lower().replace(" ", "_").replace("'", "")
                    print(f'    "{key}": "{opt}",')
                print("}")
            else:
                print("Could not capture options")
                service.driver_service.driver.save_screenshot("maf_seller_dropdown_debug.png")

        # Keep browser open
        print("\n\nBrowser will stay open for 30 seconds...")
        time.sleep(30)

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        time.sleep(30)
    finally:
        service.logout()
        print("Done!")


if __name__ == "__main__":
    capture_seller_options()
