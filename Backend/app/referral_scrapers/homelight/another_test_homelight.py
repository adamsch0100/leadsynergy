if __name__ == '__main__':
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    import time
    import random
    from datetime import datetime, timedelta
    import re

    # Hardcoded credentials
    url = "https://agent.homelight.com"
    email = "online@saahomes.com"
    password = "SAA$quad#1Rank"

    # Lead interaction settings
    NOTES_BY_STAGE = {
        "Agent Left Voicemail": [
            "Left a detailed voicemail about our services and next steps.",
            "Called and left a message explaining the current market and our approach.",
            "Left voicemail with details about comparable properties in their area.",
            "Left a message with introduction and brief overview of our team's success rate.",
            "Called and left voicemail requesting a call back to discuss their property goals.",
            "Left message introducing our team and services.",
            "Called and left contact information for follow-up.",
            "Left voicemail with brief market update.",
            "Called to touch base, left detailed message.",
            "Left message about potential listing options."
        ],
        "Connected": [
            "Had an introductory call to understand their timeline and property needs.",
            "Spoke with client about their selling goals and timeline expectations.",
            "Connected and discussed their property situation and initial questions.",
            "Had a productive first conversation about their real estate objectives.",
            "Made initial contact and established rapport, will follow up with more information.",
            "Had brief call to introduce our services.",
            "Connected and explained next steps.",
            "Quick call to establish timeline needs.",
            "Spoke about property values in their area.",
            "Initial contact made, scheduled follow-up."
        ],
        "Meeting Scheduled": [
            "Scheduled property walk-through for next Tuesday at 2pm.",
            "Set up initial consultation for Friday morning to discuss marketing strategy.",
            "Meeting arranged for this weekend to assess property and discuss valuation.",
            "Appointment confirmed for next week to review comparable properties and pricing strategy.",
            "Virtual consultation scheduled to go over selling process and answer questions.",
            "Set appointment for initial consultation.",
            "Confirmed meeting time for property assessment.",
            "Scheduled video call to discuss market conditions.",
            "Meeting booked for listing presentation.",
            "Arranged time to review selling strategy."
        ],
        "Met With Person": [
            "Completed initial consultation and property assessment. Client is considering timeline options.",
            "Met at the property and discussed potential improvements before listing.",
            "Completed walk-through and provided initial valuation estimate, which was well-received.",
            "Met client and toured property, provided detailed market analysis and next steps.",
            "In-person meeting complete - discussed staging options and marketing approach.",
            "Completed property tour and evaluation.",
            "Met with client to discuss pricing strategy.",
            "Initial meeting complete, reviewed comps.",
            "Walk-through finished, provided recommendations.",
            "Consultation complete, client deciding on timeline."
        ],
        "Coming Soon": [
            "Property prep underway, targeting MLS listing next week after photos are complete.",
            "Final staging scheduled for this Thursday, listing to go live next Monday.",
            "Pre-marketing activities underway, professional photos scheduled for tomorrow.",
            "Property details finalized, coming soon listing will be published this Friday.",
            "Preparing marketing materials and finalizing listing details for upcoming launch.",
            "Coming soon listing ready to activate.",
            "Photographer scheduled for property photos.",
            "Finalizing property description and details.",
            "Staging complete, preparing for launch.",
            "Pre-marketing activities in progress."
        ],
        "Listing": [
            "Property officially listed on MLS. First open house scheduled for Sunday.",
            "Listing is active and generating significant interest with 15 showings scheduled.",
            "Property has been on market for 5 days with strong showing activity.",
            "Listed property with premium placement, already received two showing requests.",
            "Listing is active with virtual tour and featured placement on major portals.",
            "Property listed, social media campaign active.",
            "MLS listing active, generated 3 inquiries.",
            "Open house scheduled for this weekend.",
            "Listed property, distributing feature cards.",
            "Listing active, digital marketing launched."
        ],
        "In Escrow": [
            "Offer accepted, currently in escrow with inspection scheduled for Wednesday.",
            "Property under contract, inspection completed with minor items to address.",
            "In escrow with qualified buyer, appraisal scheduled for next week.",
            "Contract moving forward smoothly, all contingencies on track to be removed by Friday.",
            "Escrow proceeding well, buyer's loan approval received and closing on schedule.",
            "In escrow, inspection completed successfully.",
            "Appraisal came in at value, moving forward.",
            "Loan documents in process, on track.",
            "Working through contingency period, no issues.",
            "All parties working toward closing date."
        ],
        "Failed": [
            "Client decided to postpone selling until next spring due to personal circumstances.",
            "Transaction fell through during inspection period, will reconnect in 30 days.",
            "Client has decided to rent property instead of selling at this time.",
            "Property taken off market temporarily to address repair issues, will follow up next month.",
            "Client proceeding with different agent due to relocation package requirements.",
            "Lead no longer interested in selling.",
            "Client decided to refinance instead.",
            "Deal fell through, buyer financing issue.",
            "No longer moving forward, will follow up later.",
            "Client decided to wait for market changes."
        ],
        # Default notes for any other stage
        "default": [
            "Followed up to discuss next steps in the selling process.",
            "Reached out to provide updated market information relevant to their property.",
            "Called to check in on their timeline and current plans.",
            "Contacted to provide additional resources and answer any questions.",
            "Followed up to maintain communication and offer continued support.",
            "Quick check-in about property status.",
            "Left message with updated information.",
            "Provided resources on market trends.",
            "Reached out to offer assistance.",
            "General follow-up on their real estate needs."
        ],
        "Agent Left VM/Email": [
            "Left voicemail with details about our services.",
            "Sent email with market information and introduction.",
            "Left message explaining our team's approach.",
            "Emailed property valuation resources.",
            "Left detailed message about listing process.",
            "Sent intro email with testimonials.",
            "Left VM with contact information.",
            "Emailed market report for their area.",
            "Left message about our listing services.",
            "Sent follow-up email with helpful resources."
        ]
    }


    def get_random_note(stage):
        """Return a random pre-written note based on the current stage"""
        if stage in NOTES_BY_STAGE:
            return random.choice(NOTES_BY_STAGE[stage])
        return random.choice(NOTES_BY_STAGE["default"])


    def human_like_typing(element, text):
        """Simulate human typing with random delays between characters"""
        for char in text:
            element.send_keys(char)
            # Random delay between keystrokes (30-100ms)
            time.sleep(random.uniform(0.03, 0.1))


    def random_human_delay(min_sec=1.0, max_sec=3.0):
        """Add a random delay to simulate human behavior"""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)
        return delay


    def parse_date_from_text(date_text):
        """Parse date from text like 'Mar 07, 2025' into a datetime object"""
        try:
            return datetime.strptime(date_text, '%b %d, %Y')
        except ValueError:
            return None


    def should_update_lead(last_update_date):
        """Check if lead should be updated based on last update date"""
        if not last_update_date:
            return True

        # Calculate days since last update
        days_since_update = (datetime.now() - last_update_date).days
        return days_since_update >= 2


    def get_last_update_date(driver, wait):
        """Extract the last update date from the page"""
        try:
            # Look for the date element with the specific class
            date_element = wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR, "p.sc-5412458c-1.kehpyJ"
            )))
            date_text = date_element.text
            return parse_date_from_text(date_text)
        except:
            try:
                # Try alternative date formats or elements
                date_elements = driver.find_elements(By.XPATH, "//p[contains(@class, 'kehpyJ')]")
                for element in date_elements:
                    date_text = element.text
                    parsed_date = parse_date_from_text(date_text)
                    if parsed_date:
                        return parsed_date
            except:
                pass
        return None


    # Configuration settings
    MAX_LEADS_TO_PROCESS = 20  # Set to None to process all leads
    MAX_PAGES_TO_PROCESS = 5  # Maximum number of pages to process

    # Setup Chrome driver
    print("Setting up Chrome driver...")
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # Login process
        print("Navigating to Homelight login page...")
        driver.get(url)

        wait = WebDriverWait(driver, 20)

        # Login steps...
        print("Entering email...")
        email_field = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, "input.email-field-input[placeholder='Enter your email']"
        )))
        email_field.send_keys(email)

        print("Clicking Continue...")
        continue_button = wait.until(EC.element_to_be_clickable((
            By.CSS_SELECTOR, "a.button.email-submit"
        )))
        continue_button.click()

        print("Entering password...")
        password_field = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, "input#user_password[type='password'][name='user[password]']"
        )))
        password_field.send_keys(password)

        print("Clicking Sign In...")
        sign_in_button = wait.until(EC.element_to_be_clickable((
            By.CSS_SELECTOR, "input[type='submit'][name='commit'][value='Sign In']"
        )))
        sign_in_button.click()

        # Wait for login to complete and dashboard to load
        print("Waiting for dashboard to load...")
        wait.until(EC.url_contains("/dashboard"))
        print("Successfully logged in!")

        # Pause to let the dashboard fully load
        time.sleep(3)

        # Click on Referrals link as specified by the user
        print("\nNavigating to Referrals page...")
        referrals_link = wait.until(EC.element_to_be_clickable((
            By.XPATH, "//a[contains(@href, '/referrals')]"
        )))
        referrals_link.click()

        # Wait for referrals page to load
        print("Waiting for Referrals page to load...")
        time.sleep(3)

        # Track the total leads processed
        total_leads_processed = 0
        current_page = 1

        # Continue processing pages until we hit our limits
        while (MAX_PAGES_TO_PROCESS is None or current_page <= MAX_PAGES_TO_PROCESS) and \
                (MAX_LEADS_TO_PROCESS is None or total_leads_processed < MAX_LEADS_TO_PROCESS):

            print(f"\n==== Processing Page {current_page} ====")

            # Find leads/referrals with the data-test attribute provided
            print("Looking for leads in the referrals list...")
            leads = wait.until(EC.presence_of_all_elements_located((
                By.CSS_SELECTOR, "a[data-test='referralsList-row']"
            )))

            print(f"Found {len(leads)} leads/referrals on page {current_page}")

            # Calculate how many leads to process on this page
            leads_remaining = None if MAX_LEADS_TO_PROCESS is None else MAX_LEADS_TO_PROCESS - total_leads_processed
            leads_to_process = len(leads) if leads_remaining is None else min(len(leads), leads_remaining)

            # Process each lead on this page
            for i, lead in enumerate(leads[:leads_to_process]):
                try:
                    lead_number = total_leads_processed + i + 1

                    try:
                        client_name_element = lead.find_element(By.CSS_SELECTOR,
                                                                "div[data-test='referralsList-rowClientName']")
                        client_name = client_name_element.text
                    except:
                        client_name = f"Lead #{lead_number}"

                    print(f"\nProcessing lead {lead_number}: {client_name}...")

                    # Click on the lead to open details
                    random_human_delay(1.5, 3.0)
                    lead.click()

                    # Wait for lead details to load
                    print("Waiting for lead details to load...")
                    random_human_delay(2.0, 4.0)

                    # Get last update date
                    last_update_date = get_last_update_date(driver, wait)
                    if last_update_date:
                        if not should_update_lead(last_update_date):
                            print(
                                f"Skipping {client_name} - Last updated on {last_update_date.strftime('%b %d, %Y')}, less than 2 days ago")
                            # Close lead details and continue to next lead
                            try:
                                close_button = wait.until(EC.element_to_be_clickable((
                                    By.CSS_SELECTOR, "button.modal-close, button[aria-label='Close'], div.close-button"
                                )))
                                close_button.click()
                            except:
                                driver.get(url + "/referrals")
                            continue

                    # Find and click on the stage selector
                    try:
                        print("Looking for stage selector...")
                        # First wait for modal to be fully loaded
                        modal = wait.until(EC.presence_of_element_located((
                            By.CSS_SELECTOR, "div.referrals-modal__wrapper"
                        )))

                        # Wait for stage selector to be present
                        stage_selector = wait.until(EC.presence_of_element_located((
                            By.CSS_SELECTOR, "div[data-test='select-selected-item']"
                        )))

                        # Get current stage
                        current_stage = stage_selector.text
                        print(f"Current stage: {current_stage}")

                        # Use JavaScript to click the stage selector
                        driver.execute_script("arguments[0].click();", stage_selector)
                        random_human_delay(1.0, 2.0)

                        # Keep the current stage using JavaScript click
                        stage_option = wait.until(EC.presence_of_element_located((
                            By.XPATH, f"//div[text()='{current_stage}']"
                        )))
                        driver.execute_script("arguments[0].click();", stage_option)
                        print(f"Selected stage: {current_stage}")

                        random_human_delay(1.0, 2.0)
                    except Exception as e:
                        print(f"Error selecting stage: {e}")

                    # Add a note
                    try:
                        print("Adding a note...")
                        add_note_button = wait.until(EC.element_to_be_clickable((
                            By.CSS_SELECTOR, "button#referral-detail-modal-add-note-button"
                        )))
                        random_human_delay(0.8, 1.8)
                        add_note_button.click()

                        note_textarea = wait.until(EC.presence_of_element_located((
                            By.CSS_SELECTOR, "textarea[data-test='referral-add-note-textarea']"
                        )))

                        # If last update was found, use "Same as previous update" note
                        if last_update_date:
                            note_text = "Same as previous update"
                        else:
                            note_text = get_random_note(current_stage)

                        random_human_delay(0.5, 1.0)
                        human_like_typing(note_textarea, note_text)

                        random_human_delay(0.8, 1.5)

                        submit_note_button = wait.until(EC.element_to_be_clickable((
                            By.CSS_SELECTOR, "button[data-test='referral-add-note-btn']"
                        )))
                        submit_note_button.click()

                        print(f"Added note: {note_text}")
                        random_human_delay(1.5, 2.5)
                    except Exception as e:
                        print(f"Error adding note: {e}")

                    # Close the lead details
                    try:
                        print("Closing lead details...")
                        try:
                            close_button = wait.until(EC.element_to_be_clickable((
                                By.CSS_SELECTOR, "button.modal-close, button[aria-label='Close'], div.close-button"
                            )))
                            random_human_delay(0.8, 1.5)
                            close_button.click()
                            print("Clicked close button")
                        except:
                            try:
                                close_icon = wait.until(EC.element_to_be_clickable((
                                    By.CSS_SELECTOR, "svg.close-icon, i.fa-times, button.close"
                                )))
                                random_human_delay(0.8, 1.5)
                                close_icon.click()
                                print("Clicked close icon")
                            except:
                                try:
                                    from selenium.webdriver.common.keys import Keys

                                    print("Trying Escape key...")
                                    webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                                except:
                                    print("Navigating back to referrals page...")
                                    driver.get(url + "/referrals")
                    except Exception as e:
                        print(f"Error closing lead details: {e}")
                        driver.get(url + "/referrals")

                    print(f"Completed processing lead {lead_number}")
                    delay = random_human_delay(3.0, 5.0)
                    print(f"Waiting {delay:.1f} seconds before next lead...")

                except Exception as e:
                    print(f"Error processing lead {lead_number}: {e}")
                    driver.get(url + "/referrals")
                    time.sleep(3)

            total_leads_processed += leads_to_process

            if MAX_LEADS_TO_PROCESS is not None and total_leads_processed >= MAX_LEADS_TO_PROCESS:
                print(f"\nReached maximum number of leads to process ({MAX_LEADS_TO_PROCESS})")
                break

            # Check for pagination
            try:
                # First, check if a "Next" button exists
                next_button_xpath = "//button[.//svg[contains(@width, '7') and contains(@height, '10')] or contains(@aria-label, 'Next') or contains(text(), 'Next')]"
                next_buttons = driver.find_elements(By.XPATH, next_button_xpath)

                # If no explicit next button, look for SVG arrows (like the one in the example)
                if not next_buttons:
                    next_button_xpath = "//button[.//svg//path[contains(@d, 'L6.34674')]] | //a[.//svg//path[contains(@d, 'L6.34674')]]"
                    next_buttons = driver.find_elements(By.XPATH, next_button_xpath)

                # If we found any next buttons that are enabled
                enabled_next_buttons = [btn for btn in next_buttons if btn.is_enabled() and btn.is_displayed()]

                if enabled_next_buttons:
                    print(f"\nNavigating to page {current_page + 1}...")
                    random_human_delay(1.0, 2.0)
                    enabled_next_buttons[0].click()

                    # Wait for the next page to load
                    print("Waiting for next page to load...")
                    random_human_delay(2.0, 3.0)

                    # Increment page counter
                    current_page += 1
                else:
                    print("\nNo more pages available. Reached the end of leads.")
                    break
            except Exception as e:
                print(f"Error navigating to next page: {e}")
                print("Completed processing all accessible leads.")
                break

        print(f"\nCompleted processing {total_leads_processed} leads across {current_page} pages!")

    except Exception as e:
        print(f"An error occurred: {e}")
        driver.save_screenshot("error.png")
        print("Screenshot saved as error.png")

    finally:
        input("Script completed. Press Enter to close the browser...")
        print("Closing browser...")
        driver.quit()