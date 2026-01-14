"""Test script for Redfin lead update functionality"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

print("="*60)
print("REDFIN LEAD UPDATE TEST")
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

# Create a dummy lead for testing
test_lead = Lead()
test_lead.first_name = "Test"
test_lead.last_name = "User"
test_lead.fub_person_id = "test123"
test_lead.tags = ["Buyer"]  # For Create Deal status

# Create service instance
service = RedfinService(lead=test_lead, status="In Progress")

try:
    # Login
    if service.login2():
        print("\n" + "="*60)
        print("SUCCESS! Redfin login completed!")
        print("="*60)

        current_url = service.driver_service.get_current_url()
        print(f"Current URL: {current_url}")

        # Get list of customers
        print("\n--- FETCHING CUSTOMER LIST ---")

        # Find customer links
        customer_links = service.driver_service.find_elements(
            By.CSS_SELECTOR, "a.customer-details-page-link"
        )

        print(f"\nFound {len(customer_links)} customers on dashboard")

        # Display first 20 customers
        print("\nFirst 20 customers:")
        customer_names = []
        for i, link in enumerate(customer_links[:20]):
            try:
                title = link.get_attribute("title")
                if title:
                    customer_names.append(title)
                    print(f"  {i + 1}. {title}")
            except:
                pass

        # Find edit buttons
        edit_buttons = service.driver_service.find_elements(
            By.CSS_SELECTOR, "button.edit-status-button"
        )
        print(f"\nFound {len(edit_buttons)} edit buttons")

        # Get available statuses by clicking first edit button
        if edit_buttons:
            print("\n--- DISCOVERING AVAILABLE STATUSES ---")

            # Click first edit button to see available statuses
            try:
                service.driver_service.safe_click(edit_buttons[0])
                service.wis.human_delay(1, 2)

                # Find status options
                status_options = service.driver_service.find_elements(
                    By.CLASS_NAME, "ItemPicker__option"
                )

                print("\nAvailable status options:")
                statuses = []
                for option in status_options:
                    try:
                        pill_element = option.find_element(By.CLASS_NAME, "Pill")
                        status_text = pill_element.text.strip()
                        if status_text:
                            statuses.append(status_text)
                            print(f"  - {status_text}")
                    except:
                        pass

                # Close the dialog without saving
                # Try clicking outside or pressing Escape
                from selenium.webdriver.common.keys import Keys
                service.driver_service.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                service.wis.human_delay(1, 2)

            except Exception as e:
                print(f"Error discovering statuses: {e}")

        # Interactive test - ask user which customer to update
        print("\n" + "="*60)
        print("INTERACTIVE TEST")
        print("="*60)

        if customer_names:
            print("\nEnter a customer name to test update (or 'skip' to skip):")
            customer_name = input("> ").strip()

            if customer_name.lower() != 'skip' and customer_name:
                print(f"\nEnter the status to set (available: {', '.join(statuses) if statuses else 'unknown'}):")
                new_status = input("> ").strip()

                if new_status:
                    print(f"\nAttempting to update '{customer_name}' to status '{new_status}'...")

                    # Update the test lead with the customer name
                    name_parts = customer_name.split()
                    if len(name_parts) >= 2:
                        test_lead.first_name = name_parts[0]
                        test_lead.last_name = " ".join(name_parts[1:])
                    else:
                        test_lead.first_name = customer_name
                        test_lead.last_name = ""

                    # Create new service with proper lead
                    result = service.find_and_click_customer_by_name2(customer_name, new_status)

                    if result:
                        print("\n" + "="*60)
                        print("SUCCESS! Lead status updated!")
                        print("="*60)
                    else:
                        print("\n" + "="*60)
                        print("FAILED: Could not update lead status")
                        print("="*60)
                else:
                    print("No status entered, skipping update test")
            else:
                print("Skipping update test")

        input("\nPress Enter to close the browser...")

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
