"""
Capture My Agent Finder dropdown options using Selenium
This script logs in, opens a referral detail page, and captures the status dropdown options
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


def capture_options():
    print("=" * 60)
    print("Capturing My Agent Finder Status Dropdown Options")
    print("=" * 60)

    # Create a dummy lead just to initialize the service
    lead = Lead()
    lead.id = "test"
    lead.first_name = "Test"
    lead.last_name = "User"
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

        # Navigate to All Active
        print("\n[2] Navigating to referrals...", flush=True)
        service.driver_service.get_page("https://app.myagentfinder.com/referral/active/allactive")
        time.sleep(3)

        # Find and click first referral to go to detail page
        print("\n[3] Finding a referral to click...", flush=True)
        rows = service.driver_service.driver.find_elements(By.CSS_SELECTOR, "tr")

        detail_link = None
        for row in rows:
            try:
                links = row.find_elements(By.TAG_NAME, 'a')
                for link in links:
                    href = link.get_attribute('href') or ''
                    if '/opp/' in href:
                        detail_link = link
                        print(f"Found detail link: {href}", flush=True)
                        break
                if detail_link:
                    break
            except:
                continue

        if not detail_link:
            print("Could not find any referral detail links!")
            return

        # Click to open detail page
        service.driver_service.driver.execute_script("arguments[0].click();", detail_link)
        time.sleep(3)

        print(f"\n[4] On detail page: {service.driver_service.get_current_url()}", flush=True)

        # Find the status dropdown input and click to open it
        print("\n[5] Opening status dropdown...", flush=True)
        status_input = service.driver_service.driver.find_element(By.CSS_SELECTOR, 'input.MuiAutocomplete-input')

        if status_input:
            # Click to open dropdown
            service.driver_service.driver.execute_script("arguments[0].click();", status_input)
            time.sleep(1)

            # Use JavaScript to capture options from the listbox
            print("\n[6] Capturing options via JavaScript...", flush=True)

            # Method 1: Direct query of listbox options
            options_js = """
            return Array.from(document.querySelectorAll('[role="listbox"] [role="option"], .MuiAutocomplete-listbox li, .MuiAutocomplete-option'))
                .map(opt => opt.textContent.trim());
            """
            options = service.driver_service.driver.execute_script(options_js)

            if options:
                print("\n" + "=" * 60)
                print("STATUS DROPDOWN OPTIONS:")
                print("=" * 60)
                for i, opt in enumerate(options, 1):
                    print(f"  {i}. \"{opt}\"")
                print("=" * 60)
            else:
                print("No options found in listbox. Trying alternative method...")

                # Method 2: Clear input and type to trigger autocomplete
                status_input.clear()
                time.sleep(0.5)

                # Try pressing down arrow to open dropdown
                from selenium.webdriver.common.keys import Keys
                status_input.send_keys(Keys.ARROW_DOWN)
                time.sleep(1)

                options = service.driver_service.driver.execute_script(options_js)
                if options:
                    print("\n" + "=" * 60)
                    print("STATUS DROPDOWN OPTIONS (via arrow key):")
                    print("=" * 60)
                    for i, opt in enumerate(options, 1):
                        print(f"  {i}. \"{opt}\"")
                    print("=" * 60)
                else:
                    # Take a screenshot
                    service.driver_service.driver.save_screenshot("maf_dropdown_debug.png")
                    print("Could not capture options. Screenshot saved to maf_dropdown_debug.png")

                    # Try to get all visible text on page that might be options
                    print("\nTrying to find any autocomplete-related elements...")
                    all_options = service.driver_service.driver.execute_script("""
                        return {
                            listbox: document.querySelector('[role="listbox"]')?.innerHTML || 'not found',
                            popper: document.querySelector('.MuiAutocomplete-popper')?.innerHTML || 'not found',
                            paper: document.querySelector('.MuiAutocomplete-paper')?.innerHTML || 'not found'
                        };
                    """)
                    print(f"Listbox: {all_options.get('listbox', 'N/A')[:200]}...")

        # Keep browser open
        print("\n\nBrowser will stay open for 30 seconds so you can verify...")
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
    capture_options()
