"""Script to process ALL Redfin 'Needs Attention' leads"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

# Force headless OFF for debugging
os.environ["SELENIUM_HEADLESS"] = "false"

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

print("=" * 60)
print("REDFIN NEEDS ATTENTION - BULK UPDATE")
print("=" * 60)

from app.referral_scrapers.redfin.redfin_service import RedfinService
from app.models.lead import Lead

# Create a dummy lead for initialization
dummy_lead = Lead()
dummy_lead.first_name = "Test"
dummy_lead.last_name = "User"

# Initialize service
service = RedfinService(
    lead=dummy_lead,
    status="Communicating",
    organization_id="cfde8fec-3b87-4558-b20f-5fe25fdcf149",
    min_sync_interval_hours=0
)

print("\n[STEP 1] Logging in via Google OAuth...")

try:
    if not service.login2():
        print("[FAILED] Login failed!")
        sys.exit(1)

    print("[OK] Login successful!")
    service.is_logged_in = True

    # Navigate to Needs Attention filter
    print("\n[STEP 2] Navigating to Needs Attention leads...")
    needs_attention_url = "https://www.redfin.com/tools/partnerCustomers?agentId=59062&settings=%7B%22queryId%22%3A%22needsAttention%22%7D"
    service.driver_service.get_page(needs_attention_url)
    time.sleep(5)

    # Get the page and find all "needs attention" rows
    print("\n[STEP 3] Finding leads that need attention...")

    results = {'successful': 0, 'failed': 0, 'skipped': 0}
    processed_names = set()
    max_iterations = 150  # Safety limit

    for iteration in range(max_iterations):
        # Find all edit status buttons
        edit_buttons = service.driver_service.find_elements(By.CSS_SELECTOR, ".edit-status-button")

        if not edit_buttons:
            print(f"\nNo more edit buttons found. Total processed: {results['successful'] + results['failed']}")
            break

        print(f"\n[Iteration {iteration + 1}] Found {len(edit_buttons)} edit buttons")

        # Get customer rows to find names
        customer_rows = service.driver_service.find_elements(By.CSS_SELECTOR, "tr[data-rf-test-name='customer-row']")

        if not customer_rows:
            # Try alternative selector
            customer_rows = service.driver_service.find_elements(By.CSS_SELECTOR, ".customer-row, [class*='CustomerRow']")

        processed_this_iteration = False

        for i, button in enumerate(edit_buttons):
            try:
                # Get the customer name from the row
                row = button.find_element(By.XPATH, "./ancestor::tr")
                name_element = row.find_element(By.CSS_SELECTOR, "a[href*='/customer/']")
                customer_name = name_element.text.strip() if name_element else f"Customer_{i}"

                # Skip if already processed
                if customer_name in processed_names:
                    continue

                print(f"\n{'#' * 50}")
                print(f"# Processing: {customer_name}")
                print(f"{'#' * 50}")

                # Scroll to button and click
                service.driver_service.scroll_into_view(button)
                time.sleep(1)

                try:
                    button.click()
                except:
                    service.driver_service.safe_click(button)

                time.sleep(2)

                # Wait for the status form to appear
                try:
                    WebDriverWait(service.driver_service.driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "UpdateStatusForm"))
                    )

                    # Find current status and just click Save to update timestamp
                    # Or find "Communicating" status and select it
                    status_options = service.driver_service.find_elements(By.CLASS_NAME, "ItemPicker__option")

                    # Find Communicating option (safe default)
                    for option in status_options:
                        try:
                            pill = option.find_element(By.CLASS_NAME, "Pill")
                            if "Communicating" in pill.text:
                                option.click()
                                print(f"  Selected: Communicating")
                                time.sleep(1)
                                break
                        except:
                            continue

                    # Click Save button
                    save_button = service.driver_service.find_element(
                        By.XPATH,
                        "//button[contains(@class, 'Button primary')]/span[text()='Save']/.."
                    )
                    if save_button:
                        save_button.click()
                        print(f"  [SUCCESS] Saved status for {customer_name}")
                        results['successful'] += 1
                        processed_names.add(customer_name)
                        processed_this_iteration = True
                        time.sleep(2)

                except Exception as e:
                    print(f"  [FAILED] Error updating {customer_name}: {e}")
                    results['failed'] += 1
                    # Try to close any open modal
                    try:
                        close_btn = service.driver_service.find_element(By.CSS_SELECTOR, ".modal-close, [aria-label='Close']")
                        if close_btn:
                            close_btn.click()
                            time.sleep(1)
                    except:
                        pass

                # Break after processing one to refresh the list
                break

            except Exception as e:
                print(f"  [ERROR] {e}")
                results['failed'] += 1

        if not processed_this_iteration:
            print("\nNo leads processed this iteration, checking for more...")
            # Scroll down to load more
            service.driver_service.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            # Check if we're done
            new_buttons = service.driver_service.find_elements(By.CSS_SELECTOR, ".edit-status-button")
            if len(new_buttons) == 0:
                break

        # Progress update every 10 leads
        if results['successful'] > 0 and results['successful'] % 10 == 0:
            print(f"\n=== PROGRESS: {results['successful']} successful, {results['failed']} failed ===\n")

except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()

finally:
    # Close browser
    try:
        service.driver_service.close()
    except:
        pass

print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)
print(f"Successful: {results['successful']}")
print(f"Failed: {results['failed']}")
print(f"Skipped: {results['skipped']}")
print("=" * 60)
