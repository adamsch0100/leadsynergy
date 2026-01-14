import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Tuple

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC

from app.models.lead import Lead
from app.referral_scrapers.base_referral_service import BaseReferralService
from app.referral_scrapers.utils.driver_service import DriverService
from app.referral_scrapers.utils.web_interaction_simulator import (
    WebInteractionSimulator as wis,
)
from app.utils.constants import Credentials

# Constants
LOGIN_URL = "https://www.referralexchange.com/login/password"
REFERRALS_URL = "https://www.referralexchange.com/matches"
CREDS = Credentials()

# Default status for leads that have never been updated on ReferralExchange
# Format: [main_option, sub_option]
DEFAULT_NEEDS_ACTION_STATUS = ["We are in contact", "is open to working with me"]


class ReferralExchangeService(BaseReferralService):
    def __init__(self, lead: Lead = None, status: Dict[str, Any] = None, organization_id: str = None,
                 driver_service=None, min_sync_interval_hours: int = 168) -> None:
        # For bulk operations, lead can be None initially
        if lead:
            super().__init__(lead, organization_id=organization_id)
        else:
            # Minimal init for bulk operations
            self.organization_id = organization_id
            self.logger = __import__('logging').getLogger(__name__)
            # Initialize credentials attributes
            self.email = None
            self.password = None

        # Credentials are loaded by BaseReferralService._setup_credentials() from database
        # Fallback to environment variables if not in database
        if not self.email:
            self.email = CREDS.REFERRAL_EXCHANGE_EMAIL
        if not self.password:
            self.password = CREDS.REFERRAL_EXCHANGE_PASSWORD

        # If still no credentials, try to load from database directly
        if not self.email or not self.password:
            try:
                from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
                settings_service = LeadSourceSettingsSingleton.get_instance()
                source_settings = settings_service.get_by_source_name("ReferralExchange")
                if source_settings and source_settings.metadata:
                    creds = source_settings.metadata.get('credentials', {})
                    if creds:
                        self.email = self.email or creds.get('email')
                        self.password = self.password or creds.get('password')
            except Exception as e:
                self.logger.warning(f"Could not load credentials from database: {e}")

        self.lead = lead
        self.lead_name = f"{self.lead.first_name} {self.lead.last_name}" if lead else ""
        self.min_sync_interval_hours = min_sync_interval_hours
        self.is_logged_in = False

        # Status can be dict, list, or will be set later
        # If it's a dict, convert to list format [main_option, sub_option]
        if isinstance(status, dict):
            self.status = [status.get("status", status.get("main_option", "")), status.get("sub_option", "")]
        elif isinstance(status, (list, tuple)):
            self.status = list(status) if len(status) >= 2 else [status[0] if status else "", ""]
        elif isinstance(status, str):
            if "::" in status:
                main, sub = [part.strip() for part in status.split("::", 1)]
                self.status = [main, sub]
            else:
                self.status = [status, ""]
        else:
            # Default: will be set by the calling code
            self.status = status if status is not None else ["", ""]

        # Support shared driver service for bulk operations
        if driver_service:
            self.driver_service = driver_service
            self.owns_driver = False
        else:
            self.owns_driver = True
            if not hasattr(self, 'driver_service'):
                self.driver_service = DriverService()
            initialized = self.driver_service.initialize_driver()

            if not initialized:
                self.logger.error("Failed to initialize Selenium driver")
                raise RuntimeError("Failed to initialize Selenium driver")

            # Add validation to ensure driver is available
            if not self.driver_service.driver or not self.driver_service.wait:
                self.logger.error("Driver or wait object is None after initialization")
                raise RuntimeError("Driver initialization failed - driver or wait is None")

    def update_active_lead(self, lead: Lead, status: Any):
        """Update the active lead and status for bulk operations"""
        self.lead = lead
        self.lead_name = f"{lead.first_name} {lead.last_name}"
        # Parse status
        if isinstance(status, dict):
            self.status = [status.get("status", status.get("main_option", "")), status.get("sub_option", "")]
        elif isinstance(status, (list, tuple)):
            self.status = list(status) if len(status) >= 2 else [status[0] if status else "", ""]
        elif isinstance(status, str):
            if "::" in status:
                main, sub = [part.strip() for part in status.split("::", 1)]
                self.status = [main, sub]
            else:
                self.status = [status, ""]
        else:
            self.status = [str(status), ""] if status else ["", ""]

    def referral_exchange_run(self) -> bool:
        try:
            print(
                f"Starting ReferralExchange process for {self.lead_name} with status: {self.status}"
            )

            # Login
            if not self.login():
                print("Login failed")
                return False

            # Find and select the customer
            if not self.find_and_click_customer_by_name(self.lead_name, self.status):
                print(f"Could not find customer: {self.lead_name}")
                return False

            # Update the customer status (uses self.status if None)
            if not self.update_customers():
                print(f"Could not update status for {self.lead_name}")
                return False

            print(f"Successfully updated status for {self.lead_name}")
            return True

        except Exception as e:
            print(f"Error in ReferralExchange service: {str(e)}")
            return False
        finally:
            self.close

    def login(self) -> bool:
        try:
            # Validate credentials before attempting login
            if not self.email or not self.password:
                missing = []
                if not self.email:
                    missing.append("email")
                if not self.password:
                    missing.append("password")
                error_msg = f"Missing credentials: {', '.join(missing)}. Please configure credentials in Lead Sources settings."
                print(f"Login failed: {error_msg}")
                self.logger.error(f"Login failed: {error_msg}")
                return False

            self.driver_service.get_page(LOGIN_URL)
            wis.human_delay(3, 5)

            # Enter email
            email_field = self.driver_service.find_element(By.ID, "email")
            wis.human_delay(1, 2)
            wis.simulated_typing(email_field, self.email)

            # Enter password
            password_field = self.driver_service.find_element(By.ID, "password")
            wis.human_delay(1, 2)
            wis.simulated_typing(password_field, self.password)

            # Click login button
            login_button = self.driver_service.find_element(By.ID, "submit")
            self.driver_service.safe_click(login_button)
            wis.human_delay(1, 2)

            print("Login successful")
            return True

        except Exception as e:
            print(f"Login failed: {str(e)}")
            self.logger.error(f"Login failed: {str(e)}")
            return False

    def update_customers(self, status_to_select: Any = None) -> bool:
        try:
            # Use self.status if status_to_select is not provided
            if status_to_select is None:
                status_to_select = self.status
            
            # Ensure status_to_select is a list/tuple
            if isinstance(status_to_select, dict):
                main_option = status_to_select.get("status", status_to_select.get("main_option", ""))
                sub_option = status_to_select.get("sub_option", "")
            elif isinstance(status_to_select, (list, tuple)):
                main_option = status_to_select[0] if len(status_to_select) > 0 else ""
                sub_option = status_to_select[1] if len(status_to_select) > 1 else ""
            else:
                # If it's a string, use it as main_option
                main_option = str(status_to_select)
                sub_option = ""



            # Click the status button to open the status modal
            status_button = self.driver_service.find_element(By.ID, "cta-status")
            self.driver_service.safe_click(status_button)
            wis.human_delay(1, 3)

            # Wait for the status update modal to appear
            try:
                self.driver_service.wait.until(
                    EC.presence_of_element_located(
                        (By.XPATH, f"//h1[contains(text(), 'Update Status')]")
                    )
                )
                print("Found status update modal with header")
            except TimeoutException:
                print("Looking for status options container...")
                self.driver_service.wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ".action-options, .options-reason")
                    )
                )
                print("Found a status options container")

            # Click main status option
            try:
                try:
                    status_option = self.driver_service.wait.until(
                        EC.element_to_be_clickable(
                            (
                                By.XPATH,
                                f"//button[contains(@class, 'action-option-reason')]/span[text()='{main_option}']",
                            )
                        )
                    )
                    print("Found status option by specific class and text")
                except TimeoutException:
                    try:
                        status_option = self.driver_service.wait.until(
                            EC.element_to_be_clickable(
                                (
                                    By.XPATH,
                                    f"//span[text()='{main_option}']/parent::button",
                                )
                            )
                        )
                        print("Found status option by text and parent")
                    except TimeoutException:
                        # List all available options
                        options = self.driver_service.find_elements(
                            By.CSS_SELECTOR,
                            ".action-options button, .options-reason button",
                        )
                        print(f"Found {len(options)} total status options")
                        for i, option in enumerate(options):
                            try:
                                text = option.text.strip()
                                print(f"Option {i + 1}: '{text}'")
                                if (
                                    text.lower()
                                    == main_option.lower()  # Exact match (case insensitive)
                                    or main_option.lower()
                                    in text.lower()  # Partial match
                                    or text.lower()
                                    in main_option.lower()  # Reverse partial match
                                ):
                                    status_option = option
                                    print(
                                        f"Selected option: {i + 1}: '{text}' - Matches main_option: '{main_option}'"
                                    )
                                    break
                            except:
                                continue
                    # Click JS
                    self.driver_service.execute_script(
                        "arguments[0].click();", status_option
                    )
                    # print("Clicked 'We are in contact' using JS")
                print(f"Found status option: {main_option}")
            except TimeoutException:
                print(f"Trying alternative xpath for {main_option}")
                status_option = self.driver_service.wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH, f"//*[contains(text(), '{main_option}')]")
                    )
                )

            # Click using JS to ensure the click works
            status_option.click()
            wis.human_delay(1, 2)

            # Select sub-option if needed
            if sub_option:
                try:
                    print(f"Attempting to find sub-option that contains: '{sub_option}'")

                    # Get all available buttons first
                    buttons = self.driver_service.find_elements(By.CSS_SELECTOR, "button.action-radio-group")
                    print(f"Found {len(buttons)} action-radio-group buttons")
                    
                    # Find the right button by text content
                    sub_option_button = None
                    for i, btn in enumerate(buttons):
                        try:
                            text = btn.text.strip()
                            print(f"Option {i + 1}: '{text}'")
                            # Use a more reliable way to check for partial text match
                            sub_pattern = sub_option.lower().replace(" ", "")
                            text_normalized = text.lower().replace(" ", "")
                            
                            if sub_pattern in text_normalized:
                                sub_option_button = btn
                                print(f"Selected matching button: '{text}'")
                                break
                            
                            # If the first approach fails, try a word-by-word match
                            if not sub_option_button:
                                sub_words = sub_option.lower().split()
                                text_words = text.lower().split()
                                
                                # Check if at least 3 words from sub_option appear in text
                                matches = sum(1 for word in sub_words if word in text_words)
                                if matches >= min(3, len(sub_words)):
                                    sub_option_button = btn
                                    print(f"Selected button by word match: '{text}'")
                                    break
                        except Exception as btn_e:
                            print(f"Error reading button {i+1} text: {str(btn_e)}")
                            continue
                    
                    # If still no match, just use the first button if "helping" is in it
                    if not sub_option_button and len(buttons) > 0:
                        for btn in buttons:
                            if "helping" in btn.text.lower():
                                sub_option_button = btn
                                print(f"Using first button with 'helping': '{btn.text}'")
                                break
                    
                    # If we have a button, try to click it
                    if sub_option_button:
                        print(f"Attempting to click button: '{sub_option_button.text}'")
                        
                        # Scroll into view first
                        self.driver_service.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", sub_option_button)
                        wis.human_delay(1, 2)
                        
                        # Try direct click first
                        sub_option_button.click()
                        print("Clicked with standard click")
                        
                        # Wait to ensure click took effect
                        wis.human_delay(2, 3)
                    else:
                        print("No matching button found by any method")
                        raise Exception("Could not find any suitable button to click")
                    
                except Exception as e:
                    print(f"Error selecting sub-option: {str(e)}")
                    return False

                wis.human_delay(1, 2)

            # Find and click the Update button
            update_button = self.driver_service.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='Update']"))
            )
            self.driver_service.safe_click(update_button)
            wis.human_delay(2, 3)
            return True

        except Exception as e:
            print(f"Error updating status: {str(e)}")
            return False

    def find_and_click_customer_by_name(self, target_name: str, status: Any) -> bool:
        """Find and click on the customer with the specified name

        Args:
            target_name (str): The name of the customer to find
            status (Any): The status to update to

        Returns:
            bool: True if found and clicked, False otherwise
        """
        try:
            # Parse target name into first/last components
            name_parts = target_name.strip().split()
            first_name = name_parts[0] if name_parts else ""
            last_name = name_parts[-1] if len(name_parts) > 1 else ""
            last_initial = last_name[0].upper() if last_name else ""

            # Use the search field to find the customer (search by first name only for better matches)
            search_field = self.driver_service.find_element(By.ID, "maching-search")
            wis.human_delay(2, 4)
            wis.simulated_typing(search_field, first_name)
            search_field.send_keys(Keys.ENTER)
            wis.human_delay(2, 4)

            # Wait for search results to load
            try:
                self.driver_service.wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".leads-row"))
                )
            except TimeoutException:
                print(f"No search results found for '{first_name}'")
                return False

            # Try to find exact match first
            try:
                lead_xpath = f"//span[text()='{target_name}' or contains(text(), '{target_name}')]/ancestor::a"
                lead_link = self.driver_service.wait.until(
                    EC.element_to_be_clickable((By.XPATH, lead_xpath))
                )
                self.driver_service.safe_click(lead_link)
                wis.human_delay(2, 3)
                print(f"Found exact match for '{target_name}'")
                return True
            except:
                pass

            # Try to find by first name + last initial (handles "Charles C." matching "Charles Closson")
            if first_name and last_initial:
                try:
                    # Match pattern like "FirstName L." or "FirstName LastInitial"
                    abbreviated_pattern = f"{first_name} {last_initial}"
                    lead_xpath = f"//span[starts-with(text(), '{abbreviated_pattern}')]/ancestor::a"
                    lead_link = self.driver_service.wait.until(
                        EC.element_to_be_clickable((By.XPATH, lead_xpath))
                    )
                    self.driver_service.safe_click(lead_link)
                    wis.human_delay(2, 3)
                    print(f"Found abbreviated match '{abbreviated_pattern}' for '{target_name}'")
                    return True
                except:
                    pass

            # Last resort: click the first result that contains the first name
            try:
                lead_xpath = f"//span[contains(text(), '{first_name}')]/ancestor::a"
                lead_links = self.driver_service.driver.find_elements(By.XPATH, lead_xpath)
                if lead_links:
                    self.driver_service.safe_click(lead_links[0])
                    wis.human_delay(2, 3)
                    print(f"Clicked first result containing '{first_name}'")
                    return True
            except:
                pass

            print(f"Could not find customer matching '{target_name}'")
            return False

        except Exception as e:
            print(f"There is an error: {str(e)}")
            return False

    def close(self) -> None:
        if self.owns_driver and hasattr(self, "driver_service") and self.driver_service:
            self.driver_service.close()

    def logout(self):
        """Logout and close the session (only if we own the driver)"""
        if self.owns_driver and self.driver_service:
            self.driver_service.close()
        self.is_logged_in = False

    def _navigate_to_referrals(self):
        """Navigate to the referrals/clients page"""
        try:
            self.driver_service.get_page(REFERRALS_URL)
            wis.human_delay(2, 3)
            return True
        except Exception as e:
            print(f"Error navigating to referrals: {e}")
            return False

    def _clear_search(self):
        """Clear the search field"""
        try:
            search_field = self.driver_service.find_element(By.ID, "maching-search")
            if search_field:
                search_field.clear()
                wis.human_delay(0.5, 1)
                search_field.send_keys(Keys.ESCAPE)
        except:
            pass

    def _check_should_skip(self, lead: Lead) -> Tuple[bool, str]:
        """Check if lead should be skipped based on metadata"""
        try:
            now = datetime.now(timezone.utc)
            cutoff_time = now - timedelta(hours=self.min_sync_interval_hours)

            if lead.metadata and isinstance(lead.metadata, dict):
                last_synced_str = lead.metadata.get("referralexchange_last_updated")
                if last_synced_str:
                    if isinstance(last_synced_str, str):
                        last_synced = datetime.fromisoformat(last_synced_str.replace('Z', '+00:00'))
                    elif isinstance(last_synced_str, datetime):
                        last_synced = last_synced_str
                    else:
                        return False, ""

                    if last_synced.tzinfo is None:
                        last_synced = last_synced.replace(tzinfo=timezone.utc)

                    hours_since = (now - last_synced).total_seconds() / 3600
                    if last_synced > cutoff_time:
                        return True, f"Synced {hours_since:.1f}h ago"
        except Exception as e:
            print(f"Error checking skip status: {e}")

        return False, ""

    def update_multiple_leads(self, leads_data: List[Tuple[Lead, Any]]) -> Dict[str, Any]:
        """
        Update multiple leads in a single browser session (login once)

        Args:
            leads_data: List of tuples containing (lead, target_status)

        Returns:
            Dict with sync results
        """
        import logging
        logger = logging.getLogger(__name__)

        results = {
            "total_leads": len(leads_data),
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "details": []
        }

        logger.info(f"Starting ReferralExchange bulk update for {len(leads_data)} leads")
        print(f"\n[START] Beginning ReferralExchange update process for {len(leads_data)} leads")

        try:
            # Login once
            print("[LOCK] Logging into ReferralExchange...")
            login_start = time.time()
            login_success = self.login()
            login_time = time.time() - login_start

            if not login_success:
                error_msg = "Failed to login to ReferralExchange"
                print(f"[ERROR] {error_msg}")
                for lead, status in leads_data:
                    results["failed"] += 1
                    results["details"].append({
                        "lead_id": lead.id,
                        "fub_person_id": lead.fub_person_id,
                        "name": f"{lead.first_name} {lead.last_name}",
                        "status": "failed",
                        "error": error_msg
                    })
                return results

            print(f"[SUCCESS] Login successful (took {login_time:.1f}s)\n")
            self.is_logged_in = True

            # Process each lead
            for idx, (lead, target_status) in enumerate(leads_data):
                lead_name = f"{lead.first_name} {lead.last_name}"
                print(f"\n[LEAD {idx+1}/{len(leads_data)}] Processing: {lead_name}")

                try:
                    # Check if should skip
                    should_skip, skip_reason = self._check_should_skip(lead)
                    if should_skip:
                        print(f"[SKIP] {lead_name} - {skip_reason}")
                        results["skipped"] += 1
                        results["details"].append({
                            "lead_id": lead.id,
                            "fub_person_id": lead.fub_person_id,
                            "name": lead_name,
                            "status": "skipped",
                            "reason": skip_reason
                        })
                        continue

                    # Update active lead
                    self.update_active_lead(lead, target_status)

                    # Navigate to referrals page
                    self._navigate_to_referrals()

                    # Find and update customer
                    if self.find_and_click_customer_by_name(lead_name, self.status):
                        if self.update_customers():
                            print(f"[SUCCESS] Updated {lead_name}")
                            results["successful"] += 1

                            # Update metadata
                            try:
                                if not lead.metadata:
                                    lead.metadata = {}
                                lead.metadata["referralexchange_last_updated"] = datetime.now(timezone.utc).isoformat()
                                from app.service.lead_service import LeadServiceSingleton
                                lead_service = LeadServiceSingleton.get_instance()
                                lead_service.update(lead)
                            except Exception as e:
                                print(f"[WARNING] Could not update metadata: {e}")

                            results["details"].append({
                                "lead_id": lead.id,
                                "fub_person_id": lead.fub_person_id,
                                "name": lead_name,
                                "status": "success"
                            })
                        else:
                            print(f"[ERROR] Failed to update status for {lead_name}")
                            results["failed"] += 1
                            results["details"].append({
                                "lead_id": lead.id,
                                "fub_person_id": lead.fub_person_id,
                                "name": lead_name,
                                "status": "failed",
                                "error": "Status update failed"
                            })
                    else:
                        print(f"[ERROR] Could not find {lead_name}")
                        results["failed"] += 1
                        results["details"].append({
                            "lead_id": lead.id,
                            "fub_person_id": lead.fub_person_id,
                            "name": lead_name,
                            "status": "failed",
                            "error": "Customer not found"
                        })

                except Exception as e:
                    print(f"[ERROR] Error processing {lead_name}: {e}")
                    results["failed"] += 1
                    results["details"].append({
                        "lead_id": lead.id,
                        "fub_person_id": lead.fub_person_id,
                        "name": lead_name,
                        "status": "failed",
                        "error": str(e)
                    })

            # Run Need Action sweep at the end
            print("\n[NEED ACTION] Running Need Action sweep...")
            results = self._process_need_action_sweep(leads_data, results)

            # Print summary
            skipped_count = results.get('skipped', 0)
            effective_success = results['successful'] + skipped_count

            print("\n" + "="*60)
            print("[FINISH] REFERRALEXCHANGE BULK SYNC COMPLETED!")
            print(f"[STATS] Total leads: {results['total_leads']}")
            print(f"[SUCCESS] Updated: {results['successful']}")
            print(f"[SKIP] Skipped (up-to-date): {skipped_count}")
            print(f"[ERROR] Failed: {results['failed']}")
            print(f"[RATE] Effective success: {(effective_success/results['total_leads']*100):.1f}%")
            print("="*60 + "\n")

        except Exception as e:
            print(f"[ERROR] Critical error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.logout()

        return results

    def _click_need_action_filter(self) -> bool:
        """Click the Needs Action filter to show leads requiring attention"""
        try:
            print("[NEEDS ACTION] Looking for Needs Action filter...")

            # Based on user-provided HTML:
            # <button type="button" class="filter-button">
            #   <div class="referral-type needs_action">
            #     <div class="referral-type-name large-font">Needs Action</div>
            #     <div class="referral-type-count">12</div>
            #   </div>
            # </button>
            selectors = [
                # Primary: the button containing needs_action div
                (By.CSS_SELECTOR, "button.filter-button div.needs_action"),
                (By.CSS_SELECTOR, "div.referral-type.needs_action"),
                (By.CSS_SELECTOR, ".needs_action"),
                # Click the button itself
                (By.XPATH, "//button[contains(@class, 'filter-button')]//div[contains(@class, 'needs_action')]"),
                (By.XPATH, "//div[contains(@class, 'referral-type-name') and contains(text(), 'Needs Action')]"),
                # Fallbacks
                (By.XPATH, "//*[contains(text(), 'Needs Action')]"),
            ]

            for selector_type, selector_value in selectors:
                try:
                    element = self.driver_service.find_element(selector_type, selector_value)
                    if element:
                        element_text = element.text.strip()
                        print(f"[NEEDS ACTION] Found element with text: '{element_text[:50]}...'")

                        # For .needs_action class selector, we don't need text match
                        is_needs_action_class = "needs_action" in selector_value or "needs-action" in selector_value
                        text_matches = "Needs Action" in element_text or "needs action" in element_text.lower()

                        if is_needs_action_class or text_matches:
                            print(f"[NEEDS ACTION] Clicking filter...")
                            # Try to click the parent button if this is a div inside a button
                            try:
                                parent_button = element.find_element(By.XPATH, "./ancestor::button")
                                if parent_button:
                                    print("[NEEDS ACTION] Clicking parent button instead")
                                    self.driver_service.safe_click(parent_button)
                                else:
                                    self.driver_service.safe_click(element)
                            except:
                                self.driver_service.safe_click(element)
                            wis.human_delay(2, 3)
                            return True
                except Exception as e:
                    print(f"[NEEDS ACTION] Selector {selector_value} failed: {str(e)[:50]}")
                    continue

            print("[NEEDS ACTION] Could not find Needs Action filter")
            return False

        except Exception as e:
            print(f"[NEEDS ACTION] Error: {e}")
            return False

    def _process_need_action_sweep(self, leads_data: List[Tuple[Lead, Any]], results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process all leads in Need Action status as a final sweep.
        Updates ALL leads to "is open to working with me" - no database lookup needed.

        Args:
            leads_data: Original list of leads (not used anymore)
            results: Current results dictionary

        Returns:
            Updated results dictionary
        """
        try:
            print("\n" + "="*60)
            print("[NEED ACTION] Starting Need Action sweep...")
            print("[NEED ACTION] All leads will be set to: 'We are in contact' -> 'is open to working with me'")
            print("="*60)

            # Navigate to referrals page first
            self._navigate_to_referrals()
            wis.human_delay(1, 2)

            # Try to click Need Action filter
            if not self._click_need_action_filter():
                print("[NEED ACTION] Skipping sweep - could not find filter")
                return results

            # Wait for results to load
            wis.human_delay(2, 3)

            # Get all leads in Need Action
            try:
                lead_rows = self.driver_service.driver.find_elements(By.CSS_SELECTOR, ".leads-row")
                need_action_count = len(lead_rows)
                print(f"[NEED ACTION] Found {need_action_count} leads in Need Action")

                if need_action_count == 0:
                    print("[NEED ACTION] No leads in Need Action - all clear!")
                    return results

                need_action_updated = 0
                status_for_service = DEFAULT_NEEDS_ACTION_STATUS.copy()

                # Process each Need Action lead - no database lookup needed
                for i in range(need_action_count):
                    try:
                        # Re-get the rows (they might change after updates)
                        lead_rows = self.driver_service.driver.find_elements(By.CSS_SELECTOR, ".leads-row")
                        if i >= len(lead_rows):
                            break

                        row = lead_rows[i]
                        row_text = row.text.strip()
                        row_lines = row_text.split('\n')
                        display_name = row_lines[0].strip() if row_lines else row_text[:30]

                        print(f"\n[NEED ACTION] Processing {i+1}/{need_action_count}: {display_name}")

                        # Click and update
                        try:
                            row.click()
                            wis.human_delay(2, 3)

                            self.status = status_for_service.copy()
                            if self.update_customers():
                                print(f"[NEED ACTION] SUCCESS! Updated to '{status_for_service[0]}' -> '{status_for_service[1]}'")
                                need_action_updated += 1
                            else:
                                print(f"[NEED ACTION] FAILED to update")

                            # Navigate back
                            self._navigate_to_referrals()
                            self._click_need_action_filter()
                            wis.human_delay(1, 2)

                        except Exception as e:
                            print(f"[NEED ACTION] Error updating: {e}")
                            self._navigate_to_referrals()
                            self._click_need_action_filter()

                    except Exception as e:
                        print(f"[NEED ACTION] Error processing row: {e}")
                        continue

                print("\n" + "="*60)
                print("[NEED ACTION] Sweep completed!")
                print(f"[NEED ACTION] Updated: {need_action_updated}/{need_action_count}")
                print("="*60)

            except Exception as e:
                print(f"[NEED ACTION] Error getting lead rows: {e}")

            return results

        except Exception as e:
            print(f"[NEED ACTION] Error during sweep: {e}")
            import traceback
            traceback.print_exc()
            return results

    def _search_database_for_lead(self, lead_service, first_name: str, last_name_part: str) -> Lead:
        """
        Search the database for a lead by name.
        Handles abbreviated names like "Charles C." -> searches for "Charles" with last name starting with "C"

        Args:
            lead_service: The lead service instance
            first_name: First name to search
            last_name_part: Last name or initial (e.g., "Chapman" or "C.")

        Returns:
            Lead if found, None otherwise
        """
        try:
            from app.database.supabase_client import SupabaseClientSingleton
            supabase = SupabaseClientSingleton.get_instance()

            # Clean up the last name part (remove periods)
            last_name_clean = last_name_part.replace(".", "").strip()

            # Search ReferralExchange leads by first name
            result = supabase.table('leads').select('*').eq('source', 'ReferralExchange').ilike('first_name', f'{first_name}%').execute()

            if not result.data:
                return None

            # Try to find best match
            for lead_data in result.data:
                db_first = lead_data.get('first_name', '').lower()
                db_last = lead_data.get('last_name', '').lower()

                # Check if first names match
                if db_first.startswith(first_name.lower()) or first_name.lower().startswith(db_first):
                    # If last_name_part is just an initial (1-2 chars)
                    if len(last_name_clean) <= 2:
                        if db_last.startswith(last_name_clean.lower()):
                            return Lead.from_dict(lead_data)
                    else:
                        # Full last name comparison
                        if db_last == last_name_clean.lower() or db_last.startswith(last_name_clean.lower()):
                            return Lead.from_dict(lead_data)

            return None

        except Exception as e:
            print(f"[DB SEARCH] Error: {e}")
            return None

    def run_standalone_need_action_sweep(self) -> Dict[str, Any]:
        """
        Run the Need Action sweep as a standalone operation.
        Logs in, navigates to Need Action, and updates ALL leads to "is open to working with me".

        Returns:
            Dict with sweep results
        """
        results = {
            "total_checked": 0,
            "updated": 0,
            "errors": 0,
            "updated_leads": [],
            "details": []
        }

        try:
            print("\n" + "="*60)
            print("[STANDALONE SWEEP] Starting Need Action sweep...")
            print("[STANDALONE SWEEP] All leads will be set to: 'We are in contact' -> 'is open to working with me'")
            print("="*60)

            # Login
            print("[STANDALONE SWEEP] Logging in...")
            if not self.login():
                print("[STANDALONE SWEEP] Login failed!")
                return results
            print("[STANDALONE SWEEP] Login successful!")

            # Navigate to referrals page
            self._navigate_to_referrals()
            wis.human_delay(1, 2)

            # Click Need Action filter
            if not self._click_need_action_filter():
                print("[STANDALONE SWEEP] Could not find Need Action filter")
                return results

            wis.human_delay(2, 3)

            # Get all leads in Need Action
            lead_rows = self.driver_service.driver.find_elements(By.CSS_SELECTOR, ".leads-row")
            results["total_checked"] = len(lead_rows)
            print(f"[STANDALONE SWEEP] Found {len(lead_rows)} leads in Need Action")

            if len(lead_rows) == 0:
                print("[STANDALONE SWEEP] No leads in Need Action - all clear!")
                return results

            # All Needs Action leads get set to "is open to working with me"
            status_for_service = DEFAULT_NEEDS_ACTION_STATUS.copy()
            print(f"[STANDALONE SWEEP] Target status for all: {status_for_service}")

            # Process each lead - no database lookup needed
            for i in range(len(lead_rows)):
                try:
                    # Re-get rows (they change after updates)
                    lead_rows = self.driver_service.driver.find_elements(By.CSS_SELECTOR, ".leads-row")
                    if i >= len(lead_rows):
                        break

                    row = lead_rows[i]
                    row_text = row.text.strip()
                    row_lines = row_text.split('\n')
                    display_name = row_lines[0].strip() if row_lines else row_text[:30]

                    print(f"\n[{i+1}/{results['total_checked']}] Processing: {display_name}")

                    # Click the lead row to open details
                    row.click()
                    wis.human_delay(2, 3)

                    # Set status (no lead object needed, just use the status)
                    self.status = status_for_service.copy()
                    if self.update_customers():
                        print(f"  SUCCESS! Updated to '{status_for_service[0]}' -> '{status_for_service[1]}'")
                        results["updated"] += 1
                        results["updated_leads"].append(display_name)
                    else:
                        print(f"  FAILED to update status")
                        results["errors"] += 1

                    # Navigate back to Need Action list
                    self._navigate_to_referrals()
                    self._click_need_action_filter()
                    wis.human_delay(1, 2)

                except Exception as e:
                    print(f"  ERROR: {e}")
                    results["errors"] += 1
                    self._navigate_to_referrals()
                    self._click_need_action_filter()
                    wis.human_delay(1, 2)

            # Summary
            print("\n" + "="*60)
            print("[STANDALONE SWEEP] COMPLETED!")
            print(f"  Total in Need Action: {results['total_checked']}")
            print(f"  Successfully updated: {results['updated']}")
            print(f"  Errors: {results['errors']}")
            if results["updated_leads"]:
                print(f"  Updated leads: {', '.join(results['updated_leads'])}")
            print("="*60)

        except Exception as e:
            print(f"[STANDALONE SWEEP] Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.logout()

        return results

    @staticmethod
    def calculate_next_run_time(
        min_delay_hours: int = 72, max_delay_hours: int = 220
    ) -> datetime:
        return super().calculate_next_run_time(min_delay_hours, max_delay_hours)

    @classmethod
    def get_platform_name(cls) -> str:
        """
        Returns the platform name for this service

        Returns:
            str: The platform name
        """
        return "ReferralExchange"
