"""Automated test for Redfin lead status update - no user input required"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

print("="*60)
print("REDFIN LEAD UPDATE TEST (Automated)")
print("="*60)

# Check credentials
redfin_email = os.getenv("REDFIN_EMAIL")
redfin_password = os.getenv("REDFIN_PASSWORD")

print(f"\nRedfin Email: {redfin_email[:3] if redfin_email else 'NOT SET'}...{redfin_email[-10:] if redfin_email else ''}")
print(f"Redfin Password: {'SET' if redfin_password else 'NOT SET'}")

if not all([redfin_email, redfin_password]):
    print("\nERROR: Missing required environment variables!")
    sys.exit(1)

print("\nStarting Redfin login...")

from app.referral_scrapers.redfin.redfin_service import RedfinService
from app.models.lead import Lead
from selenium.webdriver.common.by import By

# Create a dummy lead for testing - we'll update this with a real customer
test_lead = Lead()
test_lead.first_name = "Test"
test_lead.last_name = "User"
test_lead.fub_person_id = "test123"
test_lead.tags = ["Buyer"]

# Create service instance
service = RedfinService(lead=test_lead, status="Communicating")

try:
    # Login
    if service.login2():
        print("\n" + "="*60)
        print("SUCCESS! Redfin login completed!")
        print("="*60)

        current_url = service.driver_service.get_current_url()
        print(f"Current URL: {current_url}")

        # Get first customer from the list
        print("\n--- FETCHING FIRST CUSTOMER ---")

        customer_links = service.driver_service.find_elements(
            By.CSS_SELECTOR, "a.customer-details-page-link"
        )

        if not customer_links:
            print("ERROR: No customers found on dashboard")
            sys.exit(1)

        # Get first customer name
        first_customer_name = customer_links[0].get_attribute("title")
        print(f"\nTest customer: {first_customer_name}")

        # Update the test lead with this customer's name
        name_parts = first_customer_name.split()
        if len(name_parts) >= 2:
            test_lead.first_name = name_parts[0]
            test_lead.last_name = " ".join(name_parts[1:])
        else:
            test_lead.first_name = first_customer_name
            test_lead.last_name = ""

        # Get current status of first customer
        edit_buttons = service.driver_service.find_elements(
            By.CSS_SELECTOR, "button.edit-status-button"
        )

        if edit_buttons:
            # Click to see current status
            service.driver_service.safe_click(edit_buttons[0])
            service.wis.human_delay(1, 2)

            # Find current selected status
            try:
                selected_status = service.driver_service.find_element(
                    By.CSS_SELECTOR, ".ItemPicker__option--selected .Pill"
                )
                if selected_status:
                    current_status = selected_status.text.strip()
                    print(f"Current status: {current_status}")
            except:
                current_status = "Unknown"
                print("Could not determine current status")

            # Get all available statuses
            status_options = service.driver_service.find_elements(
                By.CLASS_NAME, "ItemPicker__option"
            )

            statuses = []
            for option in status_options:
                try:
                    pill_element = option.find_element(By.CLASS_NAME, "Pill")
                    status_text = pill_element.text.strip()
                    if status_text:
                        statuses.append(status_text)
                except:
                    pass

            print(f"Available statuses: {statuses}")

            # Choose a different status to switch to (for testing)
            # We'll switch to "Communicating" or if already there, switch to "No Response"
            new_status = "Communicating"
            if current_status == "Communicating":
                new_status = "No Response"
            elif current_status == "No Response":
                new_status = "Communicating"

            print(f"\nChanging status from '{current_status}' to '{new_status}'...")

            # Close the dialog first
            from selenium.webdriver.common.keys import Keys
            service.driver_service.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            service.wis.human_delay(1, 2)

            # Now perform the actual update using the service method
            print(f"\n--- TESTING STATUS UPDATE ---")
            print(f"Customer: {first_customer_name}")
            print(f"New Status: {new_status}")

            result = service.find_and_click_customer_by_name2(first_customer_name, new_status)

            if result:
                print("\n" + "="*60)
                print("SUCCESS! Lead status update completed!")
                print("="*60)

                # Verify the change
                service.wis.human_delay(2, 3)

                # Refresh and check
                service.driver_service.get_page(service.dashboard_url)
                service.wis.human_delay(3, 5)

                # Find the customer again and verify status
                customer_links = service.driver_service.find_elements(
                    By.CSS_SELECTOR, "a.customer-details-page-link"
                )

                for i, link in enumerate(customer_links):
                    title = link.get_attribute("title")
                    if title == first_customer_name:
                        # Click the edit button at this index
                        edit_buttons = service.driver_service.find_elements(
                            By.CSS_SELECTOR, "button.edit-status-button"
                        )
                        if i < len(edit_buttons):
                            service.driver_service.safe_click(edit_buttons[i])
                            service.wis.human_delay(1, 2)

                            try:
                                selected_status = service.driver_service.find_element(
                                    By.CSS_SELECTOR, ".ItemPicker__option--selected .Pill"
                                )
                                if selected_status:
                                    verified_status = selected_status.text.strip()
                                    print(f"\nVerified status: {verified_status}")

                                    if verified_status == new_status:
                                        print("STATUS CHANGE VERIFIED!")
                                    else:
                                        print(f"WARNING: Status is '{verified_status}', expected '{new_status}'")
                            except:
                                print("Could not verify status change")
                        break

            else:
                print("\n" + "="*60)
                print("FAILED: Could not update lead status")
                print("="*60)

    else:
        print("\n" + "="*60)
        print("FAILED: Redfin login did not complete successfully")
        print("="*60)

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()

finally:
    print("\nClosing browser...")
    service.close()
    print("Test complete!")
