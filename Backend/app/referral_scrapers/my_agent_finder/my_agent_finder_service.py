"""
My Agent Finder Referral Service

Automates lead status updates on My Agent Finder (https://app.myagentfinder.com)
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from datetime import datetime, timedelta, timezone
import time
import random
import logging
from typing import List, Optional, Dict, Any, Tuple

from app.utils.constants import Credentials
from app.referral_scrapers.utils.driver_service import DriverService
from app.referral_scrapers.utils.web_interaction_simulator import (
    WebInteractionSimulator as wis,
)
from app.models.lead import Lead
from app.service.lead_service import LeadServiceSingleton
from app.referral_scrapers.base_referral_service import BaseReferralService

# Constants
LOGIN_URL = "https://app.myagentfinder.com/login"
DASHBOARD_URL = "https://app.myagentfinder.com/dashboard"
REFERRALS_URL = "https://app.myagentfinder.com/referral/active/allactive"
CANCELLED_URL = "https://app.myagentfinder.com/referral/not-active/cancelled"
CREDS = Credentials()

# My Agent Finder status categories (based on URL structure)
STATUS_CATEGORIES = {
    "pending": "https://app.myagentfinder.com/referral/active/pending",
    "overdue": "https://app.myagentfinder.com/referral/active/overdue",
    "allactive": "https://app.myagentfinder.com/referral/active/allactive",
    "prospects": "https://app.myagentfinder.com/referral/active/prospects",
    "clients": "https://app.myagentfinder.com/referral/active/clients",
    "undercontract": "https://app.myagentfinder.com/referral/active/undercontract",
    "nurture": "https://app.myagentfinder.com/referral/active/nurture",
}

# Status options for the dropdown (MUI Autocomplete)
# EXACT strings from My Agent Finder dropdown (captured via Selenium)
# Note: Buyer and Seller referrals have different options

# BUYER status options (for Buyer referrals)
# NOTE: Use single spaces consistently - MAF dropdown uses single spaces
BUYER_STATUS_OPTIONS = {
    # Assigned (initial contact phase)
    "trying_to_reach": "Assigned - I am trying to reach this Client",
    "assigned": "Assigned - I am trying to reach this Client",

    # Prospect (engaged, pre-showing)
    "communicating": "Prospect - I'm communicating with this Client",
    "prospect_communicating": "Prospect - I'm communicating with this Client",
    "contacted": "Prospect - I'm communicating with this Client",
    "in_progress": "Prospect - I'm communicating with this Client",
    "appointment": "Prospect - I have an appointment to show this Buyer properties",
    "prospect_appointment": "Prospect - I have an appointment to show this Buyer properties",
    "lender": "Prospect - Connected to a lender",
    "prospect_lender": "Prospect - Connected to a lender",

    # Client (active showing/offer phase)
    "showing": "Client - I'm showing this Buyer properties",
    "showing_properties": "Client - I'm showing this Buyer properties",
    "client_showing": "Client - I'm showing this Buyer properties",
    "offer": "Client - I have submitted an offer for this Buyer",
    "offer_submitted": "Client - I have submitted an offer for this Buyer",
    "client_offer": "Client - I have submitted an offer for this Buyer",
    "mls_search": "Client - I've set this client up with an MLS search",
    "client_mls": "Client - I've set this client up with an MLS search",

    # In Escrow
    "in_escrow": "In Escrow - I am in escrow with this Client",
    "escrow": "In Escrow - I am in escrow with this Client",
    "under_contract": "In Escrow - I am in escrow with this Client",
    "undercontract": "In Escrow - I am in escrow with this Client",
    "pending": "In Escrow - I am in escrow with this Client",
    "offer_accepted": "In Escrow - I am in escrow with this Client",

    # Closed Escrow
    "closed": "Closed Escrow - Sold! I have closed escrow with this Client",
    "closed_escrow": "Closed Escrow - Sold! I have closed escrow with this Client",
    "sold": "Closed Escrow - Sold! I have closed escrow with this Client",

    # Nurture
    "nurture": "Nurture - I'm nurturing this client (long term)",
    "nurturing": "Nurture - I'm nurturing this client (long term)",
    "nurture_mls": "Nurture - I've set this client up with an MLS search",

    # No Longer Engaged
    "another_agent": "No Longer Engaged - Client has another agent",
    "unresponsive": "No Longer Engaged - Client is Unresponsive",
    "not_engaged": "No Longer Engaged - I'm not able to attend to this Client",
    "no_longer_engaged": "No Longer Engaged - I'm not able to attend to this Client",
    "other": "No Longer Engaged - Other",
}

# SELLER status options (for Seller referrals)
# NOTE: Use single spaces consistently - MAF dropdown uses single spaces
SELLER_STATUS_OPTIONS = {
    # Assigned (initial contact phase)
    "trying_to_reach": "Assigned - I am trying to reach this Client",
    "assigned": "Assigned - I am trying to reach this Client",

    # Prospect (engaged, pre-listing)
    "communicating": "Prospect - I'm communicating with this Client",
    "prospect_communicating": "Prospect - I'm communicating with this Client",
    "contacted": "Prospect - I'm communicating with this Client",
    "in_progress": "Prospect - I'm communicating with this Client",
    "appointment": "Prospect - I have a listing appointment scheduled with this Seller",
    "listing_appointment": "Prospect - I have a listing appointment scheduled with this Seller",
    "prospect_appointment": "Prospect - I have a listing appointment scheduled with this Seller",

    # Listed (active listing phase)
    "listing_agreement": "Listed - I have signed a listing agreement with this Seller",
    "signed_listing": "Listed - I have signed a listing agreement with this Seller",
    "listed": "Listed - I have listed this Seller's property",
    "property_listed": "Listed - I have listed this Seller's property",
    "showing": "Listed - I have listed this Seller's property",

    # In Escrow
    "in_escrow": "In Escrow - I am in escrow with this Client",
    "escrow": "In Escrow - I am in escrow with this Client",
    "under_contract": "In Escrow - I am in escrow with this Client",
    "undercontract": "In Escrow - I am in escrow with this Client",
    "pending": "In Escrow - I am in escrow with this Client",
    "offer_accepted": "In Escrow - I am in escrow with this Client",

    # Closed Escrow
    "closed": "Closed Escrow - Sold! I have closed escrow with this Client",
    "closed_escrow": "Closed Escrow - Sold! I have closed escrow with this Client",
    "sold": "Closed Escrow - Sold! I have closed escrow with this Client",

    # Nurture
    "nurture": "Nurture - I'm nurturing this client (long term)",
    "nurturing": "Nurture - I'm nurturing this client (long term)",
    "nurture_mls": "Nurture - I've set this client up with an MLS search",

    # No Longer Engaged
    "another_agent": "No Longer Engaged - Client has another agent",
    "unresponsive": "No Longer Engaged - Client is Unresponsive",
    "not_engaged": "No Longer Engaged - I'm not able to attend to this Client",
    "no_longer_engaged": "No Longer Engaged - I'm not able to attend to this Client",
    "other": "No Longer Engaged - Other",
}

# Default to buyer options for backwards compatibility
STATUS_OPTIONS = BUYER_STATUS_OPTIONS

# All available status options (for display/reference)
# NOTE: Use single spaces consistently - MAF dropdown uses single spaces
BUYER_STATUS_DISPLAY_OPTIONS = [
    "Assigned - I am trying to reach this Client",
    "Prospect - I'm communicating with this Client",
    "Prospect - I have an appointment to show this Buyer properties",
    "Prospect - Connected to a lender",
    "Client - I'm showing this Buyer properties",
    "Client - I have submitted an offer for this Buyer",
    "Client - I've set this client up with an MLS search",
    "In Escrow - I am in escrow with this Client",
    "Closed Escrow - Sold! I have closed escrow with this Client",
    "Nurture - I'm nurturing this client (long term)",
    "Nurture - I've set this client up with an MLS search",
    "No Longer Engaged - Client has another agent",
    "No Longer Engaged - Client is Unresponsive",
    "No Longer Engaged - I'm not able to attend to this Client",
    "No Longer Engaged - Other",
]

SELLER_STATUS_DISPLAY_OPTIONS = [
    "Assigned - I am trying to reach this Client",
    "Prospect - I'm communicating with this Client",
    "Prospect - I have a listing appointment scheduled with this Seller",
    "Listed - I have signed a listing agreement with this Seller",
    "Listed - I have listed this Seller's property",
    "In Escrow - I am in escrow with this Client",
    "Closed Escrow - Sold! I have closed escrow with this Client",
    "Nurture - I'm nurturing this client (long term)",
    "Nurture - I've set this client up with an MLS search",
    "No Longer Engaged - Client has another agent",
    "No Longer Engaged - Client is Unresponsive",
    "No Longer Engaged - I'm not able to attend to this Client",
    "No Longer Engaged - Other",
]


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace - replace multiple spaces with single space"""
    import re
    return re.sub(r'\s+', ' ', text).strip()

# Combined for backwards compatibility
STATUS_DISPLAY_OPTIONS = BUYER_STATUS_DISPLAY_OPTIONS


def get_status_options_for_type(referral_type: str) -> Dict[str, str]:
    """Get the appropriate status options based on referral type (buyer/seller)"""
    if referral_type and referral_type.lower() in ['seller', 'listing', 'list']:
        return SELLER_STATUS_OPTIONS
    return BUYER_STATUS_OPTIONS

logger = logging.getLogger(__name__)


class MyAgentFinderService(BaseReferralService):
    """Service for automating lead status updates on My Agent Finder"""

    def __init__(
        self,
        lead: Lead = None,
        status: Dict[str, Any] = None,
        organization_id: str = None,
        driver_service=None,
        min_sync_interval_hours: int = 168,
        same_status_note: str = None,
        nurture_days_offset: int = 180  # Default 6 months for Nurture status
    ) -> None:
        # For bulk operations, lead can be None initially
        if lead:
            super().__init__(lead, organization_id=organization_id)
        else:
            self.organization_id = organization_id
            self.logger = logging.getLogger(__name__)
            self.email = None
            self.password = None

        # Credentials are loaded by BaseReferralService._setup_credentials() from database
        # Fallback to environment variables if not in database
        if not self.email:
            self.email = CREDS.MY_AGENT_FINDER_EMAIL
        if not self.password:
            self.password = CREDS.MY_AGENT_FINDER_PASSWORD

        # If still no credentials, try to load from database directly
        if not self.email or not self.password:
            self._load_credentials_from_database()

        self.lead = lead
        self.lead_name = f"{self.lead.first_name} {self.lead.last_name}" if lead else ""
        self.min_sync_interval_hours = min_sync_interval_hours
        self.is_logged_in = False

        # Status handling - can be dict, list, or string
        self.status = status
        if isinstance(status, dict):
            # Convert dict to expected format if needed
            self.status = status.get('status', status)

        # Use provided driver service or create a new one
        if driver_service:
            self.driver_service = driver_service
        else:
            self.driver_service = DriverService()

        self.lead_service = LeadServiceSingleton.get_instance()
        self.wis = wis()
        self.same_status_note = same_status_note or "Continuing to work with this client. Will provide updates as progress is made."

        # Nurture status date offset (days in future for "Next Status Update Date")
        # Default is 180 days (6 months) - can be overridden via lead source settings metadata
        self.nurture_days_offset = nurture_days_offset

        # Track the result of the last find operation for better reporting
        self.last_find_result = None  # "active", "cancelled", "not_found"

    def _load_credentials_from_database(self):
        """Load credentials from database if not set via environment"""
        try:
            from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
            settings_service = LeadSourceSettingsSingleton.get_instance()
            source_settings = settings_service.get_by_source_name("MyAgentFinder")

            if source_settings and source_settings.metadata:
                metadata = source_settings.metadata
                if isinstance(metadata, str):
                    import json
                    metadata = json.loads(metadata)

                creds = metadata.get('credentials', {})
                if creds:
                    self.email = self.email or creds.get('email')
                    self.password = self.password or creds.get('password')
                    logger.info("Loaded MyAgentFinder credentials from database")

        except Exception as e:
            logger.warning(f"Could not load credentials from database: {e}")

    @classmethod
    def get_platform_name(cls) -> str:
        return "MyAgentFinder"

    def return_platform_name(self) -> str:
        return self.get_platform_name()

    def my_agent_finder_run(self) -> bool:
        """Main entry point for processing a single lead"""
        try:
            if self.login():
                full_name = f"{self.lead.first_name} {self.lead.last_name}"

                if self.status:
                    return self.find_and_update_lead(full_name, self.status)
                else:
                    self.logger.warning("No status provided for update")
                    return False
            else:
                self.logger.error("Login failed")
                return False

        except Exception as e:
            self.logger.error(f"MyAgentFinder run failed: {e}")
            return False

        finally:
            self.logout()

    def login(self) -> bool:
        """Login to My Agent Finder"""
        try:
            # Check if credentials are available
            if not self.email or not self.password:
                logger.error(f"Missing credentials - email: {'set' if self.email else 'NOT SET'}, password: {'set' if self.password else 'NOT SET'}")
                return False

            logger.info(f"Attempting login with email: {self.email[:3]}***@{self.email.split('@')[-1] if '@' in self.email else '...'}")

            if not self.driver_service.initialize_driver():
                logger.error("Failed to initialize driver")
                return False

            logger.info(f"Navigating to {LOGIN_URL}")
            if not self.driver_service.get_page(LOGIN_URL):
                logger.error("Failed to load login page")
                return False

            self.wis.human_delay(2, 4)

            # Find login form elements
            # Common selectors for login forms - comprehensive fallbacks
            email_selectors = [
                'input[type="email"]',  # CORRECT selector as of Feb 2026 (MUI component)
                'input.MuiInputBase-input[type="email"]',
                'input[name="email"]',
                'input[name="Email"]',
                'input[name="username"]',
                'input[name="Username"]',
                'input[type="text"][name*="email" i]',
                'input[type="text"][name*="username" i]',
                'input[placeholder*="email" i]',
                'input[placeholder*="username" i]',
                'input[placeholder*="Email" i]',
                'input[id*="email" i]',
                'input[id*="username" i]',
                'input[class*="email"]',
                'input[class*="username"]',
                '#email',
                '#Email',
                '#username',
                '#Username',
                'input[autocomplete="email"]',
                'input[autocomplete="username"]',
                'input[type="text"]:first-of-type',  # Often first input is email
            ]

            password_selectors = [
                'input[type="password"]',  # CORRECT selector as of Feb 2026 (MUI component)
                'input.MuiInputBase-input[type="password"]',
                'input[name="password"]',
                'input[placeholder*="password" i]',
                'input[id*="password" i]',
                '#password',
            ]

            submit_selectors = [
                'button[type="button"]',  # My Agent Finder uses type="button" for login
                'button[type="submit"]',
                'input[type="submit"]',
            ]

            # Find email field
            email_field = None
            for selector in email_selectors:
                try:
                    email_field = self.driver_service.find_element(By.CSS_SELECTOR, selector)
                    if email_field:
                        logger.info(f"Found email field: {selector}")
                        break
                except:
                    continue

            if not email_field:
                logger.error("Could not find email field")
                self._take_screenshot("login_no_email_field")
                return False

            # Find password field
            password_field = None
            for selector in password_selectors:
                try:
                    password_field = self.driver_service.find_element(By.CSS_SELECTOR, selector)
                    if password_field:
                        logger.info(f"Found password field: {selector}")
                        break
                except:
                    continue

            if not password_field:
                logger.error("Could not find password field")
                self._take_screenshot("login_no_password_field")
                return False

            # Enter credentials
            logger.info("Entering credentials...")
            self.wis.simulated_typing(email_field, self.email)
            self.wis.human_delay(1, 2)
            self.wis.simulated_typing(password_field, self.password)
            self.wis.human_delay(1, 2)

            # Find and click submit button
            submit_button = None
            for selector in submit_selectors:
                try:
                    submit_button = self.driver_service.find_element(By.CSS_SELECTOR, selector)
                    if submit_button:
                        logger.info(f"Found submit button: {selector}")
                        break
                except:
                    continue

            # Try XPath if CSS didn't work
            if not submit_button:
                xpath_selectors = [
                    "//button[contains(text(), 'Log')]",
                    "//button[contains(text(), 'Sign')]",
                    "//button[@type='submit']",
                    "//input[@type='submit']",
                ]
                for xpath in xpath_selectors:
                    try:
                        submit_button = self.driver_service.find_element(By.XPATH, xpath)
                        if submit_button:
                            logger.info(f"Found submit button via XPath: {xpath}")
                            break
                    except:
                        continue

            if submit_button:
                self.driver_service.safe_click(submit_button)
            else:
                # Try pressing Enter
                from selenium.webdriver.common.keys import Keys
                password_field.send_keys(Keys.RETURN)
                logger.info("Pressed Enter to submit")

            self.wis.human_delay(3, 6)

            # Take a screenshot after login attempt for debugging
            self._take_screenshot("after_login_attempt")

            # Verify login success
            current_url = self.driver_service.get_current_url()
            logger.info(f"Current URL after login: {current_url}")

            # Check if still on login page (login failed)
            if current_url and "login" in current_url.lower():
                logger.warning("Still on login page - login may have failed")
                # Check page content for error messages
                try:
                    page_source = self.driver_service.driver.page_source.lower()
                    if "invalid" in page_source or "incorrect" in page_source or "failed" in page_source:
                        logger.error("Login page shows error indicators")
                        self._take_screenshot("login_failed_error")
                        return False
                except:
                    pass

            # Check for successful navigation to dashboard or other logged-in pages
            if current_url and ("dashboard" in current_url.lower() or "leads" in current_url.lower() or
                                "referral" in current_url.lower() or "/opp/" in current_url.lower()):
                self.is_logged_in = True
                logger.info("MyAgentFinder login successful!")
                return True

            # Check for common dashboard elements
            dashboard_indicators = [
                ".dashboard",
                "#dashboard",
                "[class*='dashboard']",
                ".leads-list",
                ".referrals",
            ]

            for selector in dashboard_indicators:
                try:
                    element = self.driver_service.find_element(By.CSS_SELECTOR, selector)
                    if element:
                        self.is_logged_in = True
                        logger.info(f"Found dashboard element: {selector}")
                        return True
                except:
                    continue

            # Check for login error messages
            error_selectors = [
                ".error",
                ".alert-danger",
                "[class*='error']",
                "[class*='invalid']",
            ]

            for selector in error_selectors:
                try:
                    error = self.driver_service.find_element(By.CSS_SELECTOR, selector)
                    if error and error.text:
                        logger.error(f"Login error: {error.text}")
                        return False
                except:
                    continue

            logger.warning("Could not verify login success - URL and elements not matched")
            self._take_screenshot("login_verification_failed")
            return False

        except Exception as e:
            logger.error(f"Login failed: {e}")
            import traceback
            traceback.print_exc()
            self.is_logged_in = False
            return False

    def logout(self) -> None:
        """Logout and close browser"""
        try:
            if self.driver_service and hasattr(self.driver_service, 'driver') and self.driver_service.driver:
                self.driver_service.driver.quit()
        except Exception as e:
            logger.error(f"Error closing driver: {e}")
        finally:
            self.is_logged_in = False

    def find_and_update_lead(self, lead_name: str, status: Any) -> bool:
        """Find a lead by name and update their status"""
        try:
            logger.info(f"Searching for lead: {lead_name}")
            self.last_find_result = None
            self.wis.human_delay(2, 3)

            # First try to find in Active section
            lead_found, location = self._search_lead_in_section(lead_name, REFERRALS_URL, "Active")

            if lead_found:
                logger.info(f"Found lead '{lead_name}' in Active section")
                self.last_find_result = "active"
                return self._update_lead_status(lead_found, status)

            # If not in Active, check Cancelled section
            logger.info(f"Lead '{lead_name}' not found in Active, checking Cancelled section...")
            lead_found, location = self._search_lead_in_section(lead_name, CANCELLED_URL, "Cancelled")

            if lead_found:
                logger.warning(f"Lead '{lead_name}' found in CANCELLED section - cannot update status")
                self.last_find_result = "cancelled"
                # Return a special indicator that the lead is cancelled
                # We could potentially click into it and try to reactivate, but for now just skip
                return False

            logger.warning(f"Lead '{lead_name}' not found in Active or Cancelled sections")
            self.last_find_result = "not_found"
            return False

        except Exception as e:
            logger.error(f"Error finding/updating lead: {e}")
            self.last_find_result = "error"
            return False

    def _search_lead_in_section(self, lead_name: str, section_url: str, section_name: str) -> Tuple[Optional[Any], str]:
        """
        Search for a lead in a specific section (Active, Cancelled, etc.)
        Returns (lead_element, section_name) or (None, "") if not found
        """
        try:
            # Navigate to the section
            current_url = self.driver_service.get_current_url()
            if section_url.split('/')[-1] not in current_url.lower() and "/opp/" not in current_url:
                logger.info(f"Navigating to {section_name} section: {section_url}")
                self.driver_service.get_page(section_url)
                self.wis.human_delay(3, 5)

            # Try to find a search box - extended selectors for MAF
            search_selectors = [
                'input[type="search"]',
                'input[placeholder*="search" i]',
                'input[placeholder*="Search" i]',
                'input[name="search"]',
                'input[name*="search" i]',
                '.search-input',
                '#search',
                'input.MuiInputBase-input',  # MUI input
                'input[class*="search" i]',
            ]

            search_box = None
            for selector in search_selectors:
                try:
                    elements = self.driver_service.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        if elem.is_displayed():
                            # Check if it looks like a search box (not a status dropdown)
                            placeholder = elem.get_attribute('placeholder') or ''
                            elem_type = elem.get_attribute('type') or ''
                            role = elem.get_attribute('role') or ''

                            # Skip autocomplete dropdowns (status selector)
                            if role == 'combobox':
                                continue

                            if 'search' in placeholder.lower() or elem_type == 'search':
                                search_box = elem
                                logger.info(f"Found search box in {section_name}: {selector} (placeholder: {placeholder})")
                                break
                    if search_box:
                        break
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue

            if not search_box:
                # Try JavaScript to find search input
                logger.warning(f"Could not find search box with CSS selectors, trying JavaScript...")
                search_script = """
                var inputs = document.querySelectorAll('input');
                for (var i = 0; i < inputs.length; i++) {
                    var inp = inputs[i];
                    var placeholder = (inp.placeholder || '').toLowerCase();
                    var type = (inp.type || '').toLowerCase();
                    if (placeholder.includes('search') || type === 'search') {
                        return inp;
                    }
                }
                return null;
                """
                search_box = self.driver_service.driver.execute_script(search_script)
                if search_box:
                    logger.info(f"Found search box via JavaScript")

            if search_box:
                # Clear and search - ONLY use first name because MAF search breaks with spaces
                # The full name will be verified when matching the row
                search_term = lead_name.split()[0] if ' ' in lead_name else lead_name
                logger.info(f"Searching for '{search_term}' (from full name '{lead_name}')")

                # Clear existing text
                search_box.clear()
                self.wis.human_delay(0.5, 1)

                # Type the search term
                self.wis.simulated_typing(search_box, search_term)

                # Dispatch input event for React/MUI components
                self.driver_service.driver.execute_script("""
                    var el = arguments[0];
                    var event = new Event('input', { bubbles: true });
                    el.dispatchEvent(event);
                    var changeEvent = new Event('change', { bubbles: true });
                    el.dispatchEvent(changeEvent);
                """, search_box)
                logger.info(f"Dispatched input/change events for React")

                # Small delay to let the filter process
                self.wis.human_delay(1, 2)

                # Press Enter to trigger search (some sites require this)
                from selenium.webdriver.common.keys import Keys
                search_box.send_keys(Keys.RETURN)
                logger.info(f"Sent Enter key to trigger search")

                # Wait for search results to load - look for table rows to appear
                logger.info(f"Waiting for search results...")
                self.wis.human_delay(2, 3)

                # Wait for table to load (additional wait for dynamic content)
                try:
                    WebDriverWait(self.driver_service.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr"))
                    )
                    logger.info("Table rows found after search")
                except TimeoutException:
                    logger.warning("Timeout waiting for table rows after search")

                # Additional short delay for any animations/filtering
                self.wis.human_delay(1, 2)

                # Take screenshot after search to help debug
                self._take_screenshot(f"after_search_{search_term}")
            else:
                logger.warning(f"NO SEARCH BOX FOUND in {section_name} section! Will try to find lead without searching.")
                # Log all visible inputs for debugging
                all_inputs = self.driver_service.driver.find_elements(By.TAG_NAME, "input")
                visible_inputs = [inp for inp in all_inputs if inp.is_displayed()]
                logger.info(f"Found {len(visible_inputs)} visible inputs on page:")
                for i, inp in enumerate(visible_inputs[:10]):  # Log first 10
                    try:
                        logger.info(f"  Input {i}: type={inp.get_attribute('type')}, placeholder={inp.get_attribute('placeholder')}, class={inp.get_attribute('class')[:50] if inp.get_attribute('class') else None}")
                    except:
                        pass

            # Look for the lead in the list - this will match the FULL name
            lead_found = self._find_lead_row(lead_name)

            if lead_found:
                return (lead_found, section_name)

            return (None, "")

        except Exception as e:
            logger.error(f"Error searching {section_name} section: {e}")
            import traceback
            traceback.print_exc()
            return (None, "")

    def _find_lead_row(self, lead_name: str) -> Optional[Any]:
        """Find a lead row by name"""
        try:
            # Wait for any loading spinners to disappear
            self._wait_for_page_load()

            # Normalize the lead name for matching
            lead_name_lower = lead_name.lower().strip()
            lead_name_parts = lead_name_lower.split()

            logger.info(f"Looking for lead: '{lead_name}' (normalized: '{lead_name_lower}')")

            # Common selectors for lead/customer rows - try in order of specificity
            row_selectors = [
                "tbody tr",  # Table body rows (more specific than just tr)
                "tr",
                ".lead-row",
                ".referral-row",
                ".customer-row",
                "[class*='referral']",
                "[class*='lead']",
                "[class*='opp']",
                ".MuiTableRow-root",
                "[role='row']",
            ]

            # Log all visible rows for debugging
            all_rows = self.driver_service.driver.find_elements(By.CSS_SELECTOR, "tbody tr")
            logger.info(f"Found {len(all_rows)} table body rows")
            if all_rows:
                for i, row in enumerate(all_rows[:5]):  # Log first 5 rows
                    try:
                        row_text = row.text[:100].replace('\n', ' ') if row.text else "(empty)"
                        logger.info(f"  Row {i}: '{row_text}...'")
                    except:
                        pass

            for row_selector in row_selectors:
                try:
                    # Use driver directly to avoid error logging for expected failures
                    rows = self.driver_service.driver.find_elements(By.CSS_SELECTOR, row_selector)
                    if rows:
                        logger.debug(f"Found {len(rows)} elements with selector '{row_selector}'")
                        for row in rows:
                            try:
                                row_text = row.text.lower()

                                # Try exact full name match first
                                if lead_name_lower in row_text:
                                    logger.info(f"Found lead '{lead_name}' using selector '{row_selector}' (exact match)")
                                    return row

                                # Try matching both first and last name separately (handles "Last, First" format)
                                if len(lead_name_parts) >= 2:
                                    first_name = lead_name_parts[0]
                                    last_name = lead_name_parts[-1]
                                    if first_name in row_text and last_name in row_text:
                                        logger.info(f"Found lead '{lead_name}' using selector '{row_selector}' (parts match)")
                                        return row
                            except:
                                continue
                except:
                    continue

            # Try JavaScript search as fallback - more comprehensive
            search_script = """
            function findLead(name, nameParts) {
                name = name.toLowerCase();
                var firstName = nameParts[0] || '';
                var lastName = nameParts[nameParts.length - 1] || '';

                // Look for table rows first
                var rows = document.querySelectorAll('tbody tr');
                for (var i = 0; i < rows.length; i++) {
                    var rowText = rows[i].textContent.toLowerCase();
                    // Try full name
                    if (rowText.includes(name)) {
                        return rows[i];
                    }
                    // Try first + last name separately (handles "Last, First" format)
                    if (firstName && lastName && rowText.includes(firstName) && rowText.includes(lastName)) {
                        return rows[i];
                    }
                }

                // Look for any element containing the name
                var elements = document.querySelectorAll('*');
                for (var i = 0; i < elements.length; i++) {
                    var el = elements[i];
                    var text = el.textContent.toLowerCase();
                    if (text.includes(name) || (firstName && lastName && text.includes(firstName) && text.includes(lastName))) {
                        // Return the closest clickable parent
                        var parent = el.closest('tr') ||
                                    el.closest('[onclick]') ||
                                    el.closest('.lead') ||
                                    el.closest('.referral') ||
                                    el.closest('[class*="row"]') ||
                                    el.closest('[role="row"]') ||
                                    el.closest('a[href*="opp"]');
                        if (parent) return parent;
                    }
                }
                return null;
            }
            return findLead(arguments[0], arguments[1]);
            """

            lead_element = self.driver_service.driver.execute_script(search_script, lead_name_lower, lead_name_parts)
            if lead_element:
                logger.info(f"Found lead '{lead_name}' using JavaScript fallback")
                return lead_element

            # If still not found, log the page state for debugging
            logger.warning(f"Could not find lead '{lead_name}' on page")
            logger.warning(f"Page URL: {self.driver_service.get_current_url()}")

            # Log page text content for debugging
            try:
                body_text = self.driver_service.driver.find_element(By.TAG_NAME, "body").text
                logger.info(f"Page contains '{lead_name_parts[0]}': {lead_name_parts[0] in body_text.lower() if lead_name_parts else False}")
                if lead_name_parts:
                    # Find where the first name appears
                    body_lower = body_text.lower()
                    idx = body_lower.find(lead_name_parts[0])
                    if idx >= 0:
                        snippet = body_text[max(0, idx-20):idx+50]
                        logger.info(f"First name found in context: '...{snippet}...'")
            except:
                pass

            self._take_screenshot(f"lead_not_found_{lead_name.replace(' ', '_')}")

            return None

        except Exception as e:
            logger.error(f"Error finding lead row: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _wait_for_page_load(self, timeout: int = 10) -> None:
        """Wait for the page to fully load by checking for loading indicators"""
        try:
            # Common loading indicator selectors
            loading_selectors = [
                ".loading",
                ".spinner",
                "[class*='loading']",
                "[class*='spinner']",
                ".MuiCircularProgress-root",
            ]

            import time
            start_time = time.time()

            while time.time() - start_time < timeout:
                loading_visible = False
                for selector in loading_selectors:
                    try:
                        elements = self.driver_service.driver.find_elements(By.CSS_SELECTOR, selector)
                        for el in elements:
                            if el.is_displayed():
                                loading_visible = True
                                break
                    except:
                        continue
                    if loading_visible:
                        break

                if not loading_visible:
                    # No loading indicator found, page should be ready
                    return

                time.sleep(0.5)

            logger.warning("Timeout waiting for page load, proceeding anyway")
        except Exception as e:
            logger.debug(f"Error checking page load state: {e}")

    def _detect_referral_type(self) -> str:
        """
        Detect if this referral is a Buyer or Seller type from the page content.
        Returns 'buyer' or 'seller'.
        """
        try:
            # Look for referral type indicators on the detail page
            # My Agent Finder typically shows "Buyer" or "Seller" somewhere on the page
            page_text = self.driver_service.driver.find_element(By.TAG_NAME, 'body').text.lower()

            # Check for explicit type indicators
            # Look for patterns like "Seller Referral", "Buyer Referral", "Type: Seller", etc.
            seller_indicators = [
                'seller referral',
                'listing referral',
                'type: seller',
                'referral type: seller',
                'listing appointment',
                'list the property',
            ]

            buyer_indicators = [
                'buyer referral',
                'type: buyer',
                'referral type: buyer',
                'showing properties',
                'show this buyer',
            ]

            # Check for seller indicators first (more specific)
            for indicator in seller_indicators:
                if indicator in page_text:
                    logger.info(f"Detected SELLER referral (matched: '{indicator}')")
                    return 'seller'

            # Check for buyer indicators
            for indicator in buyer_indicators:
                if indicator in page_text:
                    logger.info(f"Detected BUYER referral (matched: '{indicator}')")
                    return 'buyer'

            # Try to find a specific element that indicates the type
            type_selectors = [
                '[class*="type"]',
                '[class*="referral-type"]',
                'span:contains("Buyer")',
                'span:contains("Seller")',
            ]

            for selector in type_selectors:
                try:
                    elements = self.driver_service.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        text = elem.text.lower()
                        if 'seller' in text or 'listing' in text:
                            logger.info(f"Detected SELLER referral from element: {elem.text}")
                            return 'seller'
                        if 'buyer' in text:
                            logger.info(f"Detected BUYER referral from element: {elem.text}")
                            return 'buyer'
                except:
                    continue

            # Default to buyer if we can't determine
            logger.info("Could not determine referral type, defaulting to BUYER")
            return 'buyer'

        except Exception as e:
            logger.warning(f"Error detecting referral type: {e}")
            return 'buyer'

    def _update_lead_status(self, lead_element: Any, status: Any) -> bool:
        """Update the status of a lead on the referral detail page"""
        try:
            # Find and click on a link within the row that leads to the detail page
            # My Agent Finder uses links like /opp/{id}/referral for detail pages
            detail_link = None

            # First try to find a link within the row
            try:
                links = lead_element.find_elements(By.TAG_NAME, 'a')
                for link in links:
                    href = link.get_attribute('href') or ''
                    # Look for detail page links
                    if '/opp/' in href or '/referral/' in href:
                        if 'active' not in href.lower():  # Avoid category links
                            detail_link = link
                            logger.info(f"Found detail link in row: {href}")
                            break
            except Exception as e:
                logger.debug(f"Error finding links in row: {e}")

            # If no specific link found, try clicking the first cell (name column)
            if not detail_link:
                try:
                    cells = lead_element.find_elements(By.TAG_NAME, 'td')
                    if cells:
                        # Try to find a link in the first cell (name column)
                        first_cell_links = cells[0].find_elements(By.TAG_NAME, 'a')
                        if first_cell_links:
                            detail_link = first_cell_links[0]
                            logger.info(f"Found link in first cell: {detail_link.get_attribute('href')}")
                        else:
                            # Click the first cell itself
                            detail_link = cells[0]
                            logger.info("Clicking first cell (no link found)")
                except Exception as e:
                    logger.debug(f"Error finding cells: {e}")

            # Fall back to clicking the row itself
            if detail_link:
                self.driver_service.driver.execute_script("arguments[0].click();", detail_link)
            else:
                logger.info("Clicking on lead row directly")
                self.driver_service.safe_click(lead_element)

            self.wis.human_delay(3, 5)

            # Verify we navigated to a detail page
            current_url = self.driver_service.get_current_url()
            logger.info(f"Current URL after click: {current_url}")

            # If still on list page, the navigation failed
            if '/referral/active/' in current_url and '/opp/' not in current_url:
                logger.warning("Navigation to detail page may have failed")
                self._take_screenshot("navigation_failed")

            # Detect referral type (buyer or seller) from page content
            referral_type = self._detect_referral_type()

            # Get the appropriate status options based on referral type
            status_options = get_status_options_for_type(referral_type)

            # Map the status to the dropdown option text
            # Handle different status formats: string, dict (buyer/seller), or list
            if isinstance(status, str):
                status_str = status
            elif isinstance(status, dict):
                # New buyer/seller format - extract based on detected referral type
                status_str = status.get(referral_type) or status.get('buyer') or status.get('seller', '')
                logger.info(f"Extracted status '{status_str}' from buyer/seller dict for {referral_type} referral")
            elif isinstance(status, list):
                status_str = status[0] if status else ''
            else:
                status_str = str(status)

            logger.info(f"RAW status from mapping: '{status_str}'")

            # Parse compound status format: "Buyer - Assigned::trying_to_reach" or "Seller - Prospect::communicating"
            # The format is: {ReferralType} - {Category}::{status_key}
            parsed_status_key = status_str
            if '::' in status_str:
                # Extract the status key after ::
                parsed_status_key = status_str.split('::')[-1].strip()
                logger.info(f"Parsed status key from compound format: '{parsed_status_key}'")
            elif ' - ' in status_str and not status_str.startswith(('Assigned', 'Prospect', 'Client', 'In Escrow', 'Closed', 'Nurture', 'No Longer', 'Listed')):
                # Format might be "Buyer - trying_to_reach" without category
                parsed_status_key = status_str.split(' - ')[-1].strip()
                logger.info(f"Parsed status key from simple format: '{parsed_status_key}'")

            # Look up the status in our predefined options
            status_key = parsed_status_key.lower().replace(' ', '_').replace('-', '_')
            status_text = status_options.get(status_key)

            # Track if we found a valid mapped status
            has_valid_mapping = status_text is not None

            if not has_valid_mapping:
                # Check if the status_str itself is already the full dropdown text
                # (user might have configured the exact dropdown text)
                status_str_lower = status_str.lower()
                for option_text in BUYER_STATUS_DISPLAY_OPTIONS + SELLER_STATUS_DISPLAY_OPTIONS:
                    if status_str_lower == option_text.lower() or status_str_lower in option_text.lower():
                        status_text = option_text
                        has_valid_mapping = True
                        logger.info(f"Status '{status_str}' matched directly to dropdown option: {option_text}")
                        break

            if not status_text:
                # Fall back to raw string but mark as unmapped
                status_text = status_str
                logger.warning(f"Status '{status_str}' (key: '{status_key}') NOT FOUND in status options - this may cause incorrect matching!")

            logger.info(f"Looking for status option ({referral_type}): {status_text} (valid_mapping={has_valid_mapping})")

            # First scroll to the "Keep Us Informed" section where the status dropdown is
            logger.info("Scrolling to status update section...")
            try:
                # Look for the "Keep Us Informed" section and scroll to it
                scroll_targets = [
                    "//*[contains(text(), 'Keep Us Informed')]",
                    "//*[contains(text(), 'Update the current status')]",
                    "//*[contains(text(), 'Status')]",
                ]
                for xpath in scroll_targets:
                    try:
                        targets = self.driver_service.driver.find_elements(By.XPATH, xpath)
                        for target in targets:
                            if target.is_displayed():
                                self.driver_service.driver.execute_script(
                                    "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                                    target
                                )
                                logger.info(f"Scrolled to: {target.text[:50] if target.text else xpath}")
                                self.wis.human_delay(1, 2)
                                break
                    except:
                        continue
            except Exception as e:
                logger.debug(f"Scroll failed: {e}")
                # Fallback: scroll down 300px
                self.driver_service.driver.execute_script("window.scrollBy(0, 300);")
                self.wis.human_delay(1, 2)

            # Find the Status dropdown - it's an MUI Autocomplete input with role="combobox"
            # Need to click the input to open dropdown, then select from options
            dropdown_clicked = False

            # The Status dropdown is an input with class MuiAutocomplete-input and role="combobox"
            dropdown_selectors = [
                'input.MuiAutocomplete-input[role="combobox"]',  # Most specific
                'input[role="combobox"]',  # Combobox input
                '.MuiAutocomplete-input',  # Autocomplete input class
            ]

            for selector in dropdown_selectors:
                try:
                    elements = self.driver_service.driver.find_elements(By.CSS_SELECTOR, selector)
                    logger.info(f"Found {len(elements)} elements with selector '{selector}'")
                    for elem in elements:
                        if elem.is_displayed():
                            # Scroll element into view before clicking
                            self.driver_service.driver.execute_script(
                                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                                elem
                            )
                            self.wis.human_delay(0.5, 1)
                            logger.info(f"Clicking Status dropdown: {selector}")
                            # Click to focus and open
                            elem.click()
                            self.wis.human_delay(1, 2)
                            dropdown_clicked = True
                            break
                    if dropdown_clicked:
                        break
                except Exception as e:
                    logger.debug(f"Dropdown selector failed: {selector} - {e}")
                    continue

            if not dropdown_clicked:
                logger.warning("Could not find/click Status dropdown")
                self._take_screenshot("no_status_dropdown")
                return False

            # Now find and click the matching status option
            logger.info(f"Looking for status option: {status_text}")
            option_clicked = False

            # Wait for dropdown to fully open
            self.wis.human_delay(1, 2)

            # Find options in the dropdown - try multiple selectors
            option_selectors = [
                '.MuiAutocomplete-listbox li',
                '.MuiAutocomplete-option',
                '[role="listbox"] [role="option"]',
                'ul[role="listbox"] li',
                '[role="option"]',
                '.MuiAutocomplete-popper li',  # Popper container
            ]

            all_options_found = []
            for opt_selector in option_selectors:
                try:
                    options = self.driver_service.driver.find_elements(By.CSS_SELECTOR, opt_selector)
                    if options:
                        logger.info(f"Found {len(options)} options with selector '{opt_selector}'")
                        for option in options:
                            try:
                                if option.is_displayed():
                                    option_text = option.text.strip()
                                    if option_text and option_text not in [o[1] for o in all_options_found]:
                                        all_options_found.append((option, option_text))
                                        logger.info(f"  Option: {option_text[:60]}")
                            except:
                                continue
                except Exception as e:
                    logger.debug(f"Option selector failed: {opt_selector} - {e}")
                    continue

            logger.info(f"Total unique options found: {len(all_options_found)}")
            logger.info(f"Target status to match: {status_text}")
            logger.info(f"Available options: {[o[1] for o in all_options_found]}")

            # Normalize the target for comparison (handle whitespace differences)
            target_lower = status_text.lower()
            target_normalized = normalize_whitespace(target_lower)

            # Step 1: Try EXACT match first (with whitespace normalization)
            for option_elem, option_text in all_options_found:
                option_lower = option_text.lower()
                option_normalized = normalize_whitespace(option_lower)
                # Exact match (normalized)
                if target_normalized == option_normalized:
                    logger.info(f"EXACT MATCH - Clicking: {option_text}")
                    try:
                        option_elem.click()
                        option_clicked = True
                        break
                    except:
                        self.driver_service.driver.execute_script("arguments[0].click();", option_elem)
                        option_clicked = True
                        break

            # Step 2: Try containment match (target in option or option in target) - normalized
            if not option_clicked:
                for option_elem, option_text in all_options_found:
                    option_lower = option_text.lower()
                    option_normalized = normalize_whitespace(option_lower)
                    if target_normalized in option_normalized or option_normalized in target_normalized:
                        logger.info(f"CONTAINMENT MATCH - Clicking: {option_text}")
                        try:
                            option_elem.click()
                            option_clicked = True
                            break
                        except:
                            self.driver_service.driver.execute_script("arguments[0].click();", option_elem)
                            option_clicked = True
                            break

            # Step 3: ONLY if we have a valid mapping, try matching key action words
            # This prevents guessing for unmapped statuses
            if not option_clicked and has_valid_mapping:
                # Extract key action words from target (communicating, appointment, showing, escrow, etc.)
                action_keywords = ['communicating', 'appointment', 'showing', 'escrow', 'closed', 'nurture',
                                   'unresponsive', 'another agent', 'offer', 'listing', 'lender', 'mls']
                target_action = None
                for keyword in action_keywords:
                    if keyword in target_lower:
                        target_action = keyword
                        break

                if target_action:
                    logger.info(f"Looking for action keyword: {target_action}")
                    for option_elem, option_text in all_options_found:
                        option_lower = option_text.lower()
                        if target_action in option_lower:
                            logger.info(f"ACTION KEYWORD MATCH ({target_action}) - Clicking: {option_text}")
                            try:
                                option_elem.click()
                                option_clicked = True
                                break
                            except:
                                self.driver_service.driver.execute_script("arguments[0].click();", option_elem)
                                option_clicked = True
                                break
            elif not option_clicked and not has_valid_mapping:
                logger.warning(f"No valid mapping found and no exact match - NOT using fallback keyword matching to avoid incorrect selection")

            if not option_clicked:
                logger.error(f"FAILED to find matching status option for: {status_text}")
                logger.error(f"RAW status was: {status_str}")
                logger.error(f"Has valid mapping: {has_valid_mapping}")
                logger.warning(f"Available options: {[o[1][:50] for o in all_options_found]}")
                self._take_screenshot("no_status_option")
                # Try to close dropdown by pressing Escape
                try:
                    from selenium.webdriver.common.keys import Keys
                    self.driver_service.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                except:
                    pass
                return False

            self.wis.human_delay(1, 2)

            # Fill in the Details textarea and click Update
            # Pass the selected status to handle special cases like Nurture date
            return self._fill_details_and_submit(selected_status=status_text)

        except Exception as e:
            logger.error(f"Error updating lead status: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _fill_details_and_submit(self, selected_status: str = None) -> bool:
        """Fill in the Details textarea and click the Update button"""
        try:
            logger.info("Filling in details and submitting update...")

            # Find the Details textarea
            textarea_selectors = [
                'textarea',
                'textarea[placeholder*="Details" i]',
                'textarea[placeholder*="Add Details" i]',
                '.MuiOutlinedInput-input',
            ]

            textarea = None
            for selector in textarea_selectors:
                try:
                    textareas = self.driver_service.driver.find_elements(By.CSS_SELECTOR, selector)
                    for ta in textareas:
                        if ta.is_displayed():
                            textarea = ta
                            logger.info(f"Found details textarea: {selector}")
                            break
                    if textarea:
                        break
                except:
                    continue

            if textarea:
                # Fill in the details
                textarea.clear()
                self.wis.simulated_typing(textarea, self.same_status_note)
                logger.info(f"Entered details: {self.same_status_note[:50]}...")
                self.wis.human_delay(1, 2)
            else:
                logger.warning("Could not find details textarea")

            # Handle Nurture status - set future date for "Next Status Update Date"
            # MAF requires a future date, not today
            if selected_status and 'nurture' in selected_status.lower():
                self._set_nurture_date()

            # Click the Update button
            # MUI buttons often have the text inside a span, so we need to search by XPath and CSS
            update_btn = None

            # First try XPath which handles nested text (MUI buttons have <span>Update</span>)
            xpath_selectors = [
                "//button[.//text()[contains(., 'Update')]]",
                "//button[contains(., 'Update')]",
                "//button[.//span[contains(text(), 'Update')]]",
            ]

            for xpath in xpath_selectors:
                try:
                    btns = self.driver_service.driver.find_elements(By.XPATH, xpath)
                    for btn in btns:
                        if btn.is_displayed():
                            update_btn = btn
                            logger.info(f"Found update button via XPath: {btn.text}")
                            break
                    if update_btn:
                        break
                except Exception as e:
                    logger.debug(f"XPath selector failed: {xpath} - {e}")
                    continue

            # Try CSS selectors if XPath failed
            if not update_btn:
                css_selectors = [
                    "button.MuiButton-containedPrimary",
                    "button.MuiButton-contained",
                    'button[type="button"]',
                ]
                for selector in css_selectors:
                    try:
                        btns = self.driver_service.driver.find_elements(By.CSS_SELECTOR, selector)
                        for btn in btns:
                            btn_text = btn.text.strip().lower()
                            if 'update' in btn_text and btn.is_displayed():
                                update_btn = btn
                                logger.info(f"Found update button via CSS: {btn.text}")
                                break
                        if update_btn:
                            break
                    except Exception as e:
                        logger.debug(f"CSS selector failed: {selector} - {e}")
                        continue

            if update_btn:
                self.driver_service.driver.execute_script("arguments[0].click();", update_btn)
                logger.info("Clicked Update button")
                self.wis.human_delay(3, 5)

                # Verify success - check for success message or page change
                current_url = self.driver_service.get_current_url()
                logger.info(f"After update, URL: {current_url}")
                return True
            else:
                logger.error("Could not find Update button")
                self._take_screenshot("no_update_button")
                return False

        except Exception as e:
            logger.error(f"Error filling details and submitting: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _set_nurture_date(self) -> bool:
        """
        Set the 'Next Status Update Date' to a future date for Nurture status.
        MAF requires a future date - defaults to today + nurture_days_offset days.
        Uses keyboard-based input clearing and typing for reliability.
        """
        from selenium.webdriver.common.keys import Keys

        try:
            # Calculate future date
            future_date = datetime.now() + timedelta(days=self.nurture_days_offset)
            # MAF uses US date format MM/DD/YYYY for text input fields
            date_str = future_date.strftime("%m/%d/%Y")  # Format: 07/14/2026
            logger.info(f"Setting Nurture date to {date_str} ({self.nurture_days_offset} days from now)")

            # Log all visible inputs on page for debugging
            all_inputs = self.driver_service.driver.find_elements(By.TAG_NAME, "input")
            visible_inputs = [inp for inp in all_inputs if inp.is_displayed()]
            logger.info(f"Found {len(visible_inputs)} visible inputs on page")

            # Find the date input - try multiple approaches
            date_input = None

            # Approach 1: Look for input with date-like value (most reliable for MAF)
            logger.info("Approach 1: Looking for input with date-like value...")
            for inp in visible_inputs:
                try:
                    inp_value = inp.get_attribute("value") or ""
                    inp_role = inp.get_attribute("role") or ""
                    inp_placeholder = inp.get_attribute("placeholder") or ""

                    # Skip status dropdown (combobox) and search
                    if inp_role == "combobox":
                        continue
                    if "search" in inp_placeholder.lower():
                        continue

                    # Look for input with date-like value (contains / and is date length)
                    if '/' in inp_value and len(inp_value) >= 8 and len(inp_value) <= 12:
                        logger.info(f"Found date input with current value: {inp_value}")
                        date_input = inp
                        break
                except:
                    continue

            # Approach 2: Find by label text "Next Status Update Date"
            if not date_input:
                logger.info("Approach 2: Trying label proximity approach...")
                try:
                    label_xpaths = [
                        "//*[contains(text(), 'Next Status Update')]",
                        "//*[contains(text(), 'Update Date')]",
                        "//*[contains(text(), 'Status Update Date')]",
                    ]
                    for xpath in label_xpaths:
                        labels = self.driver_service.driver.find_elements(By.XPATH, xpath)
                        for label in labels:
                            logger.info(f"Found label: {label.text[:50] if label.text else 'empty'}")
                            # Try to find input in parent containers
                            parent = label
                            for _ in range(5):
                                try:
                                    parent = parent.find_element(By.XPATH, "..")
                                    inputs = parent.find_elements(By.TAG_NAME, "input")
                                    for inp in inputs:
                                        if inp.is_displayed():
                                            role = inp.get_attribute("role") or ""
                                            placeholder = inp.get_attribute("placeholder") or ""
                                            if role != "combobox" and "search" not in placeholder.lower():
                                                date_input = inp
                                                logger.info(f"Found input near label")
                                                break
                                    if date_input:
                                        break
                                except:
                                    break
                            if date_input:
                                break
                        if date_input:
                            break
                except Exception as e:
                    logger.debug(f"Label search failed: {e}")

            # Approach 3: Standard HTML date input or date-related selectors
            if not date_input:
                logger.info("Approach 3: Trying CSS selectors...")
                date_selectors = [
                    'input[type="date"]',
                    'input[placeholder*="date" i]',
                    'input[name*="date" i]',
                    'input[id*="date" i]',
                ]
                for selector in date_selectors:
                    try:
                        inputs = self.driver_service.driver.find_elements(By.CSS_SELECTOR, selector)
                        for inp in inputs:
                            if inp.is_displayed():
                                date_input = inp
                                logger.info(f"Found date input via selector: {selector}")
                                break
                        if date_input:
                            break
                    except:
                        continue

            # Approach 4: Exclusion approach - find visible text input that isn't status/search/textarea
            if not date_input:
                logger.info("Approach 4: Trying exclusion approach...")
                for inp in visible_inputs:
                    try:
                        inp_role = inp.get_attribute("role") or ""
                        inp_placeholder = inp.get_attribute("placeholder") or ""
                        inp_class = inp.get_attribute("class") or ""
                        inp_type = inp.get_attribute("type") or ""
                        inp_tag = inp.tag_name.lower()

                        # Skip: combobox, search, checkbox, hidden, button, textarea
                        if inp_role == "combobox":
                            continue
                        if "search" in inp_placeholder.lower():
                            continue
                        if inp_type in ["checkbox", "hidden", "submit", "button"]:
                            continue
                        if "Autocomplete" in inp_class:
                            continue
                        if inp_tag == "textarea":
                            continue

                        # This might be our date input
                        logger.info(f"Potential date input found - type:{inp_type}, placeholder:{inp_placeholder}")
                        date_input = inp
                        break
                    except:
                        continue

            if date_input:
                logger.info(f"Attempting to set date value using keyboard method...")

                # Take screenshot before attempting date change
                self._take_screenshot("before_date_set")

                # Click on the date field to focus it
                try:
                    date_input.click()
                    logger.info("Clicked on date input to focus it")
                    self.wis.human_delay(0.3, 0.5)
                except Exception as e:
                    logger.debug(f"Click on date input failed: {e}")

                # Use keyboard to clear and type new date (most reliable method)
                try:
                    # Select all content
                    date_input.send_keys(Keys.CONTROL + "a")
                    self.wis.human_delay(0.1, 0.2)

                    # Delete selected content
                    date_input.send_keys(Keys.DELETE)
                    self.wis.human_delay(0.1, 0.2)

                    # Type new date in US format
                    date_input.send_keys(date_str)
                    logger.info(f"Typed date via keyboard: {date_str}")
                    self.wis.human_delay(0.2, 0.3)

                    # Press Tab to commit the change and move focus
                    date_input.send_keys(Keys.TAB)
                    self.wis.human_delay(0.3, 0.5)

                    logger.info(f"Successfully set date to {date_str}")

                except Exception as e:
                    logger.warning(f"Keyboard method failed: {e}, trying JavaScript fallback")

                    # JavaScript fallback for React/MUI
                    try:
                        self.driver_service.driver.execute_script(
                            """
                            var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            nativeInputValueSetter.call(arguments[0], arguments[1]);
                            arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                            arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                            arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));
                            """,
                            date_input, date_str
                        )
                        logger.info(f"Set date via JavaScript fallback: {date_str}")
                    except Exception as js_e:
                        logger.error(f"JavaScript fallback also failed: {js_e}")

                # Take screenshot after date input attempt
                self._take_screenshot("after_date_set")

                self.wis.human_delay(0.5, 1)
                return True
            else:
                logger.warning("Could not find date input for Nurture status - taking screenshot")
                self._take_screenshot("nurture_no_date_input")
                # Don't fail the update just because date couldn't be set
                logger.info("Continuing without setting date - status update will still proceed")
                return True  # Return True to not fail the entire update

        except Exception as e:
            logger.error(f"Error setting nurture date: {e}")
            import traceback
            traceback.print_exc()
            return True  # Don't fail the update just because of date issue

    def _find_status_option(self, status_text: str) -> Optional[Any]:
        """Find a status option in dropdown/list"""
        try:
            # Common option selectors
            option_selectors = [
                f"option[value*='{status_text}' i]",
                f"li:contains('{status_text}')",
                f"[class*='option']:contains('{status_text}')",
                f"div[role='option']:contains('{status_text}')",
            ]

            for selector in option_selectors:
                try:
                    option = self.driver_service.find_element(By.CSS_SELECTOR, selector)
                    if option:
                        return option
                except:
                    continue

            # Try XPath
            xpath = f"//*[contains(text(), '{status_text}')]"
            try:
                option = self.driver_service.find_element(By.XPATH, xpath)
                if option:
                    return option
            except:
                pass

            return None

        except Exception as e:
            logger.error(f"Error finding status option: {e}")
            return None

    def _take_screenshot(self, name: str) -> None:
        """Take a screenshot for debugging"""
        try:
            # Save to debug_screenshots folder
            import os
            screenshot_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "debug_screenshots")
            os.makedirs(screenshot_dir, exist_ok=True)
            filename = os.path.join(screenshot_dir, f"myagentfinder_{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            self.driver_service.driver.save_screenshot(filename)
            logger.info(f"Screenshot saved: {filename}")
        except Exception as e:
            logger.warning(f"Failed to save screenshot: {e}")

    def update_multiple_leads(self, leads_data: List[Tuple[Lead, Any]], tracker=None, sync_id: str = None) -> Dict[str, Any]:
        """
        Update multiple leads in a single browser session (bulk sync).

        Args:
            leads_data: List of (Lead, status) tuples
            tracker: Optional sync status tracker for cancellation support
            sync_id: Optional sync ID for cancellation checks

        Returns:
            Dict with sync results
        """
        results = {
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "details": []
        }

        if not leads_data:
            return results

        try:
            # Login once
            logger.info(f"Starting bulk sync for {len(leads_data)} leads")
            if not self.login():
                logger.error("Login failed - cannot process leads")
                for lead, _ in leads_data:
                    results["failed"] += 1
                    results["details"].append({
                        "name": f"{lead.first_name} {lead.last_name}",
                        "status": "failed",
                        "error": "Login failed"
                    })
                return results

            # Process each lead
            for i, (lead, status) in enumerate(leads_data):
                # Check for cancellation before processing each lead
                if tracker and sync_id and tracker.is_cancelled(sync_id):
                    logger.info(f"Sync {sync_id} cancelled, stopping at lead {i}/{len(leads_data)}")
                    if tracker:
                        tracker.update_progress(
                            sync_id,
                            message=f"Sync cancelled. Processed {i} of {len(leads_data)} leads before cancellation."
                        )
                    results["details"].append({
                        "name": "SYNC CANCELLED",
                        "status": "cancelled",
                        "error": "Sync was cancelled by user"
                    })
                    break

                lead_name = f"{lead.first_name} {lead.last_name}"
                logger.info(f"[{i+1}/{len(leads_data)}] Processing: {lead_name}")

                # Update tracker progress if available
                if tracker and sync_id:
                    tracker.update_progress(
                        sync_id,
                        processed=i + 1,
                        current_lead=lead_name,
                        message=f"Processing {i+1}/{len(leads_data)}: {lead_name}"
                    )

                try:
                    # Check if lead was recently synced
                    if self._should_skip_lead(lead):
                        results["skipped"] += 1
                        results["details"].append({
                            "name": lead_name,
                            "status": "skipped",
                            "reason": "Recently synced"
                        })
                        # Update tracker with real-time counts
                        if tracker and sync_id:
                            tracker.update_progress(
                                sync_id,
                                successful=results["successful"],
                                failed=results["failed"],
                                skipped=results["skipped"],
                                message=f"Skipped {lead_name} (recently synced)"
                            )
                        continue

                    # Navigate to All Active referrals page between leads
                    if i > 0:
                        self.driver_service.get_page(REFERRALS_URL)
                        self.wis.human_delay(2, 3)

                    # Find and update lead
                    success = self.find_and_update_lead(lead_name, status)

                    if success:
                        results["successful"] += 1
                        results["details"].append({
                            "name": lead_name,
                            "status": "success"
                        })

                        # Update lead metadata
                        self._mark_lead_synced(lead)

                        # Update tracker with real-time success count
                        if tracker and sync_id:
                            tracker.update_progress(
                                sync_id,
                                successful=results["successful"],
                                failed=results["failed"],
                                skipped=results["skipped"],
                                message=f"Successfully updated {lead_name}"
                            )
                    else:
                        # Check why it failed based on last_find_result
                        if self.last_find_result == "cancelled":
                            # Track cancelled leads separately
                            if "cancelled" not in results:
                                results["cancelled"] = 0
                            results["cancelled"] += 1
                            results["details"].append({
                                "name": lead_name,
                                "status": "cancelled",
                                "error": "Lead is in Cancelled section on MyAgentFinder"
                            })
                            error_msg = f"{lead_name} is in Cancelled section"
                        elif self.last_find_result == "not_found":
                            results["failed"] += 1
                            results["details"].append({
                                "name": lead_name,
                                "status": "not_found",
                                "error": "Lead not found in Active or Cancelled sections"
                            })
                            error_msg = f"{lead_name} not found on MAF"
                        else:
                            results["failed"] += 1
                            results["details"].append({
                                "name": lead_name,
                                "status": "failed",
                                "error": f"Update failed ({self.last_find_result or 'unknown'})"
                            })
                            error_msg = f"Failed to update {lead_name}"

                        # Update tracker with real-time fail count
                        if tracker and sync_id:
                            tracker.update_progress(
                                sync_id,
                                successful=results["successful"],
                                failed=results["failed"],
                                skipped=results["skipped"],
                                message=error_msg
                            )

                except Exception as e:
                    results["failed"] += 1
                    results["details"].append({
                        "name": lead_name,
                        "status": "failed",
                        "error": str(e)
                    })
                    logger.error(f"Error processing lead {lead_name}: {e}")

                    # Update tracker with real-time fail count
                    if tracker and sync_id:
                        tracker.update_progress(
                            sync_id,
                            successful=results["successful"],
                            failed=results["failed"],
                            skipped=results["skipped"],
                            message=f"Error processing {lead_name}: {str(e)[:50]}"
                        )

            cancelled_count = results.get('cancelled', 0)
            logger.info(f"Bulk sync complete: {results['successful']} success, {results['failed']} failed, {cancelled_count} cancelled, {results['skipped']} skipped")
            return results

        except Exception as e:
            logger.error(f"Bulk sync error: {e}")
            return results

        finally:
            self.logout()

    def _should_skip_lead(self, lead: Lead) -> bool:
        """Check if lead was recently synced and should be skipped"""
        try:
            if not lead.metadata:
                return False

            last_synced_str = lead.metadata.get("myagentfinder_last_updated")
            if not last_synced_str:
                return False

            last_synced = datetime.fromisoformat(last_synced_str.replace('Z', '+00:00'))
            if last_synced.tzinfo is None:
                last_synced = last_synced.replace(tzinfo=timezone.utc)

            cutoff = datetime.now(timezone.utc) - timedelta(hours=self.min_sync_interval_hours)
            return last_synced > cutoff

        except Exception as e:
            logger.warning(f"Error checking sync status: {e}")
            return False

    def _mark_lead_synced(self, lead: Lead) -> None:
        """Update lead metadata with sync timestamp"""
        try:
            if not lead.metadata:
                lead.metadata = {}

            lead.metadata["myagentfinder_last_updated"] = datetime.now(timezone.utc).isoformat()
            self.lead_service.update(lead)

        except Exception as e:
            logger.warning(f"Failed to update lead sync timestamp: {e}")

    @staticmethod
    def calculate_next_run_time(
        min_delay_hours: int = 72, max_delay_hours: int = 220
    ) -> datetime:
        now = datetime.now()
        random_delay = random.randint(min_delay_hours, max_delay_hours)
        return now + timedelta(hours=random_delay)

    def close(self) -> None:
        """Close the browser"""
        self.logout()

    def update_customers(self, status_to_select: Any) -> bool:
        """Update all customers with the given status (required by BaseReferralService)"""
        # This method is used for single lead updates through my_agent_finder_run
        if self.lead:
            return self.my_agent_finder_run()
        return False

    def process_overdue_leads(self, max_leads: int = 50) -> Dict[str, Any]:
        """
        Process all overdue leads from the MyAgentFinder platform.
        This method navigates to the overdue page and updates each lead's
        Next Status Update Date to 6 months (nurture_days_offset) from now.

        Args:
            max_leads: Maximum number of overdue leads to process

        Returns:
            Dict with successful, failed, and details of each lead processed
        """
        from selenium.webdriver.common.keys import Keys

        results = {'successful': 0, 'failed': 0, 'details': []}

        try:
            # Login if needed
            if not self.is_logged_in:
                if not self.login():
                    logger.error("Failed to login for overdue processing")
                    return results
                self.is_logged_in = True

            # Navigate to overdue page
            overdue_url = STATUS_CATEGORIES.get("overdue", "https://app.myagentfinder.com/referral/active/overdue")
            logger.info(f"Navigating to overdue page: {overdue_url}")
            self.driver_service.get_page(overdue_url)
            self.wis.human_delay(3, 4)

            # Calculate target date (6 months out)
            future_date = datetime.now() + timedelta(days=self.nurture_days_offset)
            # Use US date format MM/DD/YYYY as MAF expects
            target_date_str = future_date.strftime("%m/%d/%Y")
            logger.info(f"Will set overdue leads date to: {target_date_str} ({self.nurture_days_offset} days out)")

            processed_count = 0
            processed_leads = set()  # Track leads we've already processed
            max_consecutive_duplicates = 3  # Stop after seeing same lead 3 times in a row
            consecutive_duplicates = 0
            last_lead_name = None

            while processed_count < max_leads:
                # Check if there are any overdue leads
                page_text = self.driver_service.driver.find_element(By.TAG_NAME, "body").text.lower()
                if "no referrals" in page_text or "no results" in page_text:
                    logger.info("No more overdue leads found")
                    break

                # Find table rows
                rows = self.driver_service.driver.find_elements(By.CSS_SELECTOR, "tbody tr")
                if not rows:
                    logger.info("No table rows found - checking if overdue page is empty")
                    break

                # Get first unprocessed row
                data_row = None
                lead_name = None
                for row in rows:
                    row_text = row.text.strip()
                    if not row_text:
                        continue
                    if 'action' in row_text.lower()[:20] or 'contact info' in row_text.lower()[:20]:
                        continue

                    lines = row_text.split('\n')
                    potential_name = lines[0] if lines else None
                    if potential_name and potential_name not in processed_leads:
                        data_row = row
                        lead_name = potential_name
                        break

                if not data_row or not lead_name:
                    # All visible leads have been processed, try scrolling or we're done
                    logger.info("All visible leads have been processed or no more data rows")
                    break

                # Check for consecutive duplicates (same lead appearing after navigation)
                if lead_name == last_lead_name:
                    consecutive_duplicates += 1
                    if consecutive_duplicates >= max_consecutive_duplicates:
                        logger.warning(f"Same lead '{lead_name}' appeared {consecutive_duplicates} times - MAF may not be saving updates. Skipping.")
                        processed_leads.add(lead_name)
                        continue
                else:
                    consecutive_duplicates = 0

                last_lead_name = lead_name
                logger.info(f"Processing overdue lead: {lead_name}")

                # Click on the edit/pencil button to open lead detail page
                try:
                    # First try to find the edit button (pencil icon) in the row's first cell
                    clickable = None

                    # Look for svg/icon in first cell (edit icon)
                    try:
                        first_cell = data_row.find_element(By.TAG_NAME, "td")
                        edit_icon = first_cell.find_element(By.TAG_NAME, "svg")
                        if edit_icon:
                            clickable = first_cell  # Click the cell containing the icon
                            logger.info("Found edit icon in first cell")
                    except:
                        pass

                    # Try to find links with /opp/ in href
                    if not clickable:
                        try:
                            links = data_row.find_elements(By.TAG_NAME, "a")
                            for link in links:
                                href = link.get_attribute("href") or ""
                                if "/opp/" in href:
                                    clickable = link
                                    logger.info(f"Found link: {href}")
                                    break
                        except:
                            pass

                    # Look for any button in the row
                    if not clickable:
                        try:
                            btns = data_row.find_elements(By.TAG_NAME, "button")
                            if btns:
                                clickable = btns[0]
                                logger.info("Found button in row")
                        except:
                            pass

                    # Last resort - click on the lead name (second column usually)
                    if not clickable:
                        try:
                            cells = data_row.find_elements(By.TAG_NAME, "td")
                            if len(cells) >= 2:
                                # Second cell usually has the name
                                name_cell = cells[1]
                                link = name_cell.find_element(By.TAG_NAME, "a")
                                if link:
                                    clickable = link
                                    logger.info("Found name link in second cell")
                        except:
                            pass

                    if not clickable:
                        clickable = data_row

                    # Click to open detail page
                    try:
                        clickable.click()
                    except:
                        self.driver_service.driver.execute_script("arguments[0].click();", clickable)

                    self.wis.human_delay(3, 4)

                    # Wait for detail page to load - check URL
                    current_url = self.driver_service.driver.current_url
                    logger.info(f"Current URL after click: {current_url}")

                    if "/opp/" not in current_url:
                        logger.warning("May not have navigated to detail page, trying alternative methods")
                        navigated = False

                        # Try 1: Find link with /opp/ href and navigate directly
                        try:
                            opp_links = self.driver_service.driver.find_elements(
                                By.CSS_SELECTOR, "a[href*='/opp/']"
                            )
                            for link in opp_links:
                                href = link.get_attribute("href") or ""
                                if link.is_displayed() and "/opp/" in href:
                                    logger.info(f"Found /opp/ link, navigating: {href}")
                                    self.driver_service.driver.get(href)
                                    self.wis.human_delay(3, 4)
                                    if "/opp/" in self.driver_service.driver.current_url:
                                        navigated = True
                                        logger.info("Successfully navigated via direct link")
                                    break
                        except Exception as e:
                            logger.debug(f"Direct link navigation failed: {e}")

                        # Try 2: Click on name text with href containing /opp/
                        if not navigated:
                            name_parts = lead_name.split()
                            if name_parts:
                                try:
                                    name_elems = self.driver_service.driver.find_elements(
                                        By.XPATH, f"//a[contains(text(), '{name_parts[0]}')]"
                                    )
                                    for elem in name_elems:
                                        if elem.is_displayed():
                                            href = elem.get_attribute("href") or ""
                                            if "/opp/" in href:
                                                self.driver_service.driver.get(href)
                                                self.wis.human_delay(3, 4)
                                                if "/opp/" in self.driver_service.driver.current_url:
                                                    navigated = True
                                                    logger.info(f"Navigated via name link: {href}")
                                                break
                                except Exception as e:
                                    logger.debug(f"Name link failed: {e}")

                        # If still not on detail page, skip this lead
                        if not navigated and "/opp/" not in self.driver_service.driver.current_url:
                            logger.warning(f"Could not navigate to detail page for {lead_name}, skipping")
                            results['failed'] += 1
                            results['details'].append({
                                'name': lead_name,
                                'status': 'failed',
                                'reason': 'Could not navigate to detail page'
                            })
                            processed_leads.add(lead_name)
                            self.driver_service.get_page(overdue_url)
                            self.wis.human_delay(2, 3)
                            processed_count += 1
                            continue

                    # Scroll to Keep Us Informed section
                    try:
                        keep_informed = self.driver_service.driver.find_element(
                            By.XPATH, "//*[contains(text(), 'Keep Us Informed')]"
                        )
                        self.driver_service.driver.execute_script(
                            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                            keep_informed
                        )
                        self.wis.human_delay(1, 2)
                    except:
                        self.driver_service.driver.execute_script("window.scrollBy(0, 300);")
                        self.wis.human_delay(1, 2)

                    # Re-select the nurture status to trigger the date picker
                    # The date picker only appears when a status is selected
                    nurture_status = "I'm nurturing this client (long term)"
                    logger.info(f"Re-selecting nurture status to trigger date picker: {nurture_status}")

                    status_selected = self._select_status_for_overdue(nurture_status)
                    if status_selected:
                        self.wis.human_delay(1, 2)

                        # MAF requires a detail/note for the update to be saved
                        # Add detail FIRST before setting date to avoid form reset issues
                        self._add_detail_for_update()
                        self.wis.human_delay(0.5, 1)

                        # Now set the date LAST (right before clicking Update)
                        # This prevents other form interactions from resetting the date
                        date_set = self._set_overdue_lead_date(target_date_str)
                        if not date_set:
                            logger.warning("Date input still not found after selecting status")
                    else:
                        logger.warning("Could not re-select nurture status")

                    # Click Update button
                    update_clicked = self._click_update_button()

                    if update_clicked:
                        results['successful'] += 1
                        results['details'].append({
                            'name': lead_name,
                            'status': 'success',
                            'new_date': target_date_str
                        })
                        processed_leads.add(lead_name)  # Mark as processed
                        logger.info(f"[SUCCESS] Updated overdue lead: {lead_name}")
                    else:
                        results['failed'] += 1
                        results['details'].append({
                            'name': lead_name,
                            'status': 'failed',
                            'reason': 'Could not click Update button'
                        })
                        processed_leads.add(lead_name)  # Still mark as processed to avoid infinite loop
                        logger.warning(f"[FAILED] Could not update: {lead_name}")

                    self.wis.human_delay(2, 3)

                except Exception as e:
                    logger.error(f"Error processing overdue lead {lead_name}: {e}")
                    results['failed'] += 1
                    results['details'].append({
                        'name': lead_name,
                        'status': 'failed',
                        'reason': str(e)
                    })

                # Navigate back to overdue page for next lead
                self.driver_service.get_page(overdue_url)
                self.wis.human_delay(2, 3)
                processed_count += 1

            logger.info(f"Overdue processing complete: {results['successful']} success, {results['failed']} failed")
            return results

        except Exception as e:
            logger.error(f"Error in process_overdue_leads: {e}")
            import traceback
            traceback.print_exc()
            return results

    def _add_detail_for_update(self) -> bool:
        """Add a detail/note to the Details textarea - MAF requires this for updates to be saved"""
        try:
            # Find the Details textarea
            textareas = self.driver_service.driver.find_elements(By.TAG_NAME, "textarea")
            details_textarea = None

            for ta in textareas:
                if ta.is_displayed():
                    # This is likely the Details field
                    details_textarea = ta
                    logger.info("Found Details textarea")
                    break

            if not details_textarea:
                # Try finding by label
                try:
                    labels = self.driver_service.driver.find_elements(
                        By.XPATH, "//*[contains(text(), 'Details')]"
                    )
                    for label in labels:
                        parent = label
                        for _ in range(5):
                            try:
                                parent = parent.find_element(By.XPATH, "..")
                                tas = parent.find_elements(By.TAG_NAME, "textarea")
                                for ta in tas:
                                    if ta.is_displayed():
                                        details_textarea = ta
                                        break
                                if details_textarea:
                                    break
                            except:
                                break
                        if details_textarea:
                            break
                except:
                    pass

            if details_textarea:
                # Add a note about the date update
                note = "Status update - continuing long term nurture. Next follow-up scheduled."
                details_textarea.click()
                self.wis.human_delay(0.2, 0.4)
                details_textarea.send_keys(note)
                logger.info(f"Added detail note: {note[:50]}...")
                self.wis.human_delay(0.3, 0.5)
                return True
            else:
                logger.warning("Could not find Details textarea")
                return False

        except Exception as e:
            logger.error(f"Error adding detail: {e}")
            return False

    def _select_status_for_overdue(self, status_text: str) -> bool:
        """Select a status from the dropdown to trigger the date picker"""
        from selenium.webdriver.common.keys import Keys

        try:
            # Find the status dropdown (combobox or select)
            dropdown = None

            # Look for MUI Autocomplete
            try:
                dropdowns = self.driver_service.driver.find_elements(
                    By.CSS_SELECTOR, 'input[role="combobox"], .MuiAutocomplete-input, [class*="Autocomplete"] input'
                )
                for d in dropdowns:
                    if d.is_displayed():
                        dropdown = d
                        logger.info("Found status dropdown (combobox)")
                        break
            except:
                pass

            if not dropdown:
                # Try finding by label
                try:
                    labels = self.driver_service.driver.find_elements(
                        By.XPATH, "//*[contains(text(), 'Update the current status')]"
                    )
                    for label in labels:
                        parent = label
                        for _ in range(5):
                            try:
                                parent = parent.find_element(By.XPATH, "..")
                                inputs = parent.find_elements(By.TAG_NAME, "input")
                                for inp in inputs:
                                    if inp.is_displayed():
                                        dropdown = inp
                                        logger.info("Found status dropdown near label")
                                        break
                                if dropdown:
                                    break
                            except:
                                break
                        if dropdown:
                            break
                except:
                    pass

            if dropdown:
                # Click to open dropdown
                dropdown.click()
                self.wis.human_delay(0.5, 1)

                # Look for the nurture option in the dropdown list
                try:
                    # Wait for dropdown options to appear
                    self.wis.human_delay(0.5, 1)

                    # Find options containing "nurturing" or "long term"
                    option_selectors = [
                        f"//li[contains(text(), 'nurturing')]",
                        f"//li[contains(text(), 'long term')]",
                        f"//*[contains(@class, 'MuiAutocomplete-option')][contains(text(), 'nurtur')]",
                        f"//div[contains(@role, 'option')][contains(text(), 'nurtur')]",
                    ]

                    option_clicked = False
                    for selector in option_selectors:
                        try:
                            options = self.driver_service.driver.find_elements(By.XPATH, selector)
                            for opt in options:
                                if opt.is_displayed() and 'nurtur' in opt.text.lower():
                                    logger.info(f"Found nurture option: {opt.text[:50]}")
                                    opt.click()
                                    option_clicked = True
                                    break
                            if option_clicked:
                                break
                        except:
                            continue

                    if not option_clicked:
                        # Try typing to filter
                        dropdown.clear()
                        dropdown.send_keys("nurturing")
                        self.wis.human_delay(0.5, 1)

                        # Click first option
                        options = self.driver_service.driver.find_elements(
                            By.CSS_SELECTOR, ".MuiAutocomplete-option, [role='option']"
                        )
                        for opt in options:
                            if opt.is_displayed():
                                opt.click()
                                option_clicked = True
                                logger.info("Selected nurture option via type-ahead")
                                break

                    self.wis.human_delay(0.5, 1)
                    return option_clicked

                except Exception as e:
                    logger.error(f"Error selecting status option: {e}")
                    return False
            else:
                logger.warning("Could not find status dropdown")
                return False

        except Exception as e:
            logger.error(f"Error in _select_status_for_overdue: {e}")
            return False

    def _set_overdue_lead_date(self, date_str: str) -> bool:
        """Set the date field for an overdue lead"""
        from selenium.webdriver.common.keys import Keys

        try:
            # Take screenshot for debugging
            self._take_screenshot("before_set_overdue_date")

            # Find all visible inputs
            all_inputs = self.driver_service.driver.find_elements(By.TAG_NAME, "input")
            visible_inputs = [inp for inp in all_inputs if inp.is_displayed()]
            logger.info(f"Found {len(visible_inputs)} visible inputs on page")

            # Log all visible inputs for debugging
            for i, inp in enumerate(visible_inputs):
                try:
                    inp_value = inp.get_attribute("value") or ""
                    inp_type = inp.get_attribute("type") or ""
                    inp_role = inp.get_attribute("role") or ""
                    inp_placeholder = inp.get_attribute("placeholder") or ""
                    logger.debug(f"  Input {i}: type={inp_type}, role={inp_role}, value='{inp_value[:20]}', placeholder='{inp_placeholder}'")
                except:
                    pass

            date_input = None

            # Look for input with date-like value (MM/DD/YYYY format)
            for inp in visible_inputs:
                try:
                    inp_value = inp.get_attribute("value") or ""
                    inp_role = inp.get_attribute("role") or ""
                    inp_placeholder = inp.get_attribute("placeholder") or ""
                    inp_type = inp.get_attribute("type") or ""

                    # Skip status dropdown and search
                    if inp_role == "combobox":
                        continue
                    if "search" in inp_placeholder.lower():
                        continue

                    # Look for date-like value (contains / and is date length)
                    if '/' in inp_value and len(inp_value) >= 8 and len(inp_value) <= 12:
                        logger.info(f"Found date input with current value: {inp_value}")
                        date_input = inp
                        break

                    # Also check for date type input
                    if inp_type == "date":
                        logger.info(f"Found HTML date input")
                        date_input = inp
                        break
                except:
                    continue

            # Fallback: find by label "Next Status Update"
            if not date_input:
                logger.info("Trying to find date input by label...")
                try:
                    labels = self.driver_service.driver.find_elements(
                        By.XPATH, "//*[contains(text(), 'Next Status Update')]"
                    )
                    logger.info(f"Found {len(labels)} labels with 'Next Status Update'")
                    for label in labels:
                        parent = label
                        for depth in range(5):
                            try:
                                parent = parent.find_element(By.XPATH, "..")
                                inputs = parent.find_elements(By.TAG_NAME, "input")
                                for inp in inputs:
                                    if inp.is_displayed():
                                        role = inp.get_attribute("role") or ""
                                        if role != "combobox":
                                            logger.info(f"Found input near label at depth {depth}")
                                            date_input = inp
                                            break
                                if date_input:
                                    break
                            except:
                                break
                        if date_input:
                            break
                except Exception as e:
                    logger.debug(f"Label search failed: {e}")

            # Fallback: look for any text input that's not status/search
            if not date_input:
                logger.info("Trying exclusion approach to find date input...")
                for inp in visible_inputs:
                    try:
                        inp_role = inp.get_attribute("role") or ""
                        inp_placeholder = inp.get_attribute("placeholder") or ""
                        inp_type = inp.get_attribute("type") or ""
                        inp_class = inp.get_attribute("class") or ""

                        # Skip inappropriate inputs
                        if inp_role == "combobox":
                            continue
                        if "search" in inp_placeholder.lower():
                            continue
                        if inp_type in ["checkbox", "hidden", "submit", "button", "email", "tel"]:
                            continue
                        if "Autocomplete" in inp_class:
                            continue

                        # This could be our date input
                        logger.info(f"Found potential date input via exclusion - type={inp_type}, value='{inp.get_attribute('value') or ''}'")
                        date_input = inp
                        break
                    except:
                        continue

            if date_input:
                logger.info(f"Found date input, attempting to set to: {date_str}")

                # Parse target date
                target_month = int(date_str.split('/')[0])
                target_day = int(date_str.split('/')[1])
                target_year = int(date_str.split('/')[2])

                # MAF uses a MUI DatePicker - the input is read-only and we need to use the calendar
                # Step 1: Click the date input or find calendar icon to open the picker
                try:
                    # Look for calendar icon/button near the date input
                    parent = date_input
                    calendar_btn = None
                    for _ in range(3):
                        try:
                            parent = parent.find_element(By.XPATH, "./..")
                            # Look for button or icon in parent
                            btns = parent.find_elements(By.TAG_NAME, "button")
                            for btn in btns:
                                if btn.is_displayed():
                                    calendar_btn = btn
                                    break
                            if calendar_btn:
                                break
                            # Also look for SVG calendar icons
                            svgs = parent.find_elements(By.TAG_NAME, "svg")
                            for svg in svgs:
                                if svg.is_displayed():
                                    # Click the parent of SVG (likely a button)
                                    svg_parent = svg.find_element(By.XPATH, "./..")
                                    if svg_parent.tag_name in ['button', 'div', 'span']:
                                        calendar_btn = svg_parent
                                        break
                            if calendar_btn:
                                break
                        except:
                            break

                    if calendar_btn:
                        logger.info("Found calendar button, clicking to open picker")
                        calendar_btn.click()
                    else:
                        logger.info("No calendar button found, clicking input directly")
                        date_input.click()

                    self.wis.human_delay(1, 1.5)

                    # Take screenshot to see what opened
                    self._take_screenshot("after_date_click")

                    # Step 2: Navigate the calendar to the target date
                    # Look for the calendar dialog/popup
                    calendar_success = self._navigate_calendar_to_date(target_month, target_day, target_year)

                    if calendar_success:
                        logger.info(f"Successfully selected {date_str} from calendar")
                        self._take_screenshot("after_calendar_selection")
                        return True

                except Exception as cal_e:
                    logger.warning(f"Calendar interaction failed: {cal_e}")

                # Fallback: Try JavaScript to directly set the underlying React state
                try:
                    # Try to find and trigger the onChange handler
                    self.driver_service.driver.execute_script(
                        """
                        // Find React fiber
                        var input = arguments[0];
                        var date = new Date(arguments[1]);

                        // Try to find MUI DatePicker's onChange
                        var key = Object.keys(input).find(k => k.startsWith('__reactFiber'));
                        if (key) {
                            var fiber = input[key];
                            // Navigate up to find DatePicker component
                            var current = fiber;
                            for (var i = 0; i < 20 && current; i++) {
                                if (current.memoizedProps && current.memoizedProps.onChange) {
                                    current.memoizedProps.onChange(date);
                                    console.log('Called onChange with date');
                                    break;
                                }
                                current = current.return;
                            }
                        }

                        // Also dispatch events
                        var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        nativeInputValueSetter.call(input, arguments[2]);
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                        """,
                        date_input,
                        f"{target_year}-{target_month:02d}-{target_day:02d}",  # ISO format for Date()
                        date_str  # Display format
                    )
                    logger.info(f"Attempted React state update for: {date_str}")
                    self.wis.human_delay(0.5, 0.8)
                except Exception as react_e:
                    logger.warning(f"React state update failed: {react_e}")

                logger.info(f"Attempted to set date to: {date_str}")
                return True
            else:
                logger.warning("Could not find date input for overdue lead")
                return False

        except Exception as e:
            logger.error(f"Error setting overdue lead date: {e}")
            return False

    def _navigate_calendar_to_date(self, target_month: int, target_day: int, target_year: int) -> bool:
        """Navigate MUI calendar picker to select a specific date"""
        try:
            from datetime import datetime
            current_date = datetime.now()
            current_month = current_date.month
            current_year = current_date.year

            # Calculate months to navigate (positive = forward, negative = backward)
            months_diff = (target_year - current_year) * 12 + (target_month - current_month)
            logger.info(f"Need to navigate {months_diff} months to reach {target_month}/{target_year}")

            # Take screenshot to see calendar state
            self._take_screenshot("calendar_before_nav")

            # Strategy 1: Try to find month/year dropdown for direct selection
            month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                          'July', 'August', 'September', 'October', 'November', 'December']
            target_month_name = month_names[target_month - 1]

            # Look for clickable month header (might allow direct selection)
            try:
                month_header = self.driver_service.driver.find_element(
                    By.XPATH, f"//*[contains(text(), '{month_names[current_month - 1]}')]"
                )
                if month_header and month_header.is_displayed():
                    # Check if it's clickable (has a dropdown)
                    parent = month_header
                    for _ in range(3):
                        try:
                            parent = parent.find_element(By.XPATH, "./..")
                            if parent.tag_name == 'button' or 'select' in (parent.get_attribute('class') or '').lower():
                                logger.info("Found clickable month header, trying direct month selection")
                                parent.click()
                                self.wis.human_delay(0.5, 1)
                                # Look for month option
                                month_options = self.driver_service.driver.find_elements(
                                    By.XPATH, f"//*[text()='{target_month_name}']"
                                )
                                for opt in month_options:
                                    if opt.is_displayed():
                                        opt.click()
                                        self.wis.human_delay(0.5, 1)
                                        logger.info(f"Directly selected {target_month_name}")
                                        months_diff = 0  # Skip arrow navigation
                                        break
                                break
                        except:
                            continue
            except:
                pass

            # Strategy 2: Try to find and click the right arrow button directly using JavaScript
            arrow_nav_success = False
            if months_diff > 0:
                try:
                    # First, debug: log ALL clickable elements in the calendar area
                    # Also look for the calendar popup specifically
                    debug_info = self.driver_service.driver.execute_script("""
                        var info = {buttons: [], calendarElements: [], popups: []};

                        // Find all buttons
                        var allButtons = document.querySelectorAll('button');
                        for (var i = 0; i < allButtons.length; i++) {
                            var btn = allButtons[i];
                            var rect = btn.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                info.buttons.push({
                                    text: (btn.innerText || btn.textContent || '').substring(0, 20).trim(),
                                    x: Math.round(rect.x),
                                    y: Math.round(rect.y),
                                    w: Math.round(rect.width),
                                    h: Math.round(rect.height),
                                    hasSvg: !!btn.querySelector('svg')
                                });
                            }
                        }

                        // Look for calendar-related elements (MUI DatePicker components)
                        var calSelectors = [
                            '.MuiCalendarPicker-root', '.MuiDateCalendar-root',
                            '.MuiPickersCalendarHeader-root', '.MuiDayCalendar-root',
                            '[class*="calendar"]', '[class*="Calendar"]',
                            '[class*="picker"]', '[class*="Picker"]'
                        ];
                        calSelectors.forEach(function(sel) {
                            var els = document.querySelectorAll(sel);
                            els.forEach(function(el) {
                                var rect = el.getBoundingClientRect();
                                if (rect.width > 0) {
                                    info.calendarElements.push({
                                        sel: sel,
                                        x: Math.round(rect.x),
                                        y: Math.round(rect.y),
                                        w: Math.round(rect.width),
                                        h: Math.round(rect.height)
                                    });
                                }
                            });
                        });

                        // Look for any popup/modal that might contain the calendar
                        var popupSelectors = [
                            '.MuiPopover-root', '.MuiPopper-root', '.MuiModal-root',
                            '[role="dialog"]', '[role="presentation"]',
                            '.MuiPaper-root'
                        ];
                        popupSelectors.forEach(function(sel) {
                            var els = document.querySelectorAll(sel);
                            els.forEach(function(el) {
                                var rect = el.getBoundingClientRect();
                                if (rect.width > 0 && rect.height > 0) {
                                    info.popups.push({
                                        sel: sel,
                                        x: Math.round(rect.x),
                                        y: Math.round(rect.y),
                                        w: Math.round(rect.width),
                                        h: Math.round(rect.height),
                                        html: el.innerHTML.substring(0, 200)
                                    });
                                }
                            });
                        });

                        return info;
                    """)
                    logger.debug(f"Buttons found: {len(debug_info.get('buttons', []))}, Calendar elements: {len(debug_info.get('calendarElements', []))}")

                    # Find the calendar container first, then look for navigation elements inside it
                    # Debug: get info about elements inside the calendar
                    cal_elements_debug = self.driver_service.driver.execute_script("""
                        var calContainer = document.querySelector('[class*="calendar"]');
                        if (!calContainer) return {error: 'No calendar container'};

                        var result = {elements: [], svgs: []};
                        var allElements = calContainer.querySelectorAll('*');

                        for (var i = 0; i < Math.min(allElements.length, 50); i++) {
                            var el = allElements[i];
                            var rect = el.getBoundingClientRect();
                            if (rect.width > 5 && rect.height > 5 && rect.width < 80) {
                                result.elements.push({
                                    tag: el.tagName,
                                    text: (el.innerText || '').substring(0, 15).trim(),
                                    x: Math.round(rect.x),
                                    y: Math.round(rect.y),
                                    w: Math.round(rect.width),
                                    h: Math.round(rect.height),
                                    class: (el.getAttribute('class') || '').substring(0, 25)
                                });
                            }
                        }

                        var svgs = calContainer.querySelectorAll('svg');
                        for (var i = 0; i < svgs.length; i++) {
                            var rect = svgs[i].getBoundingClientRect();
                            result.svgs.push({
                                x: Math.round(rect.x),
                                y: Math.round(rect.y),
                                w: Math.round(rect.width),
                                h: Math.round(rect.height)
                            });
                        }

                        return result;
                    """)
                    logger.debug(f"Calendar internal: {len(cal_elements_debug.get('elements', []))} elements, {len(cal_elements_debug.get('svgs', []))} SVGs")

                    js_result = self.driver_service.driver.execute_script("""
                        // Find the calendar container
                        var calContainer = null;
                        var calSelectors = ['[class*="calendar"]', '[class*="Calendar"]', '.MuiCalendarPicker-root', '.MuiDateCalendar-root'];
                        for (var i = 0; i < calSelectors.length; i++) {
                            var el = document.querySelector(calSelectors[i]);
                            if (el) {
                                var rect = el.getBoundingClientRect();
                                if (rect.width > 100) {
                                    calContainer = el;
                                    console.log('Found calendar at x=' + rect.x + ', y=' + rect.y);
                                    break;
                                }
                            }
                        }

                        if (!calContainer) {
                            console.log('No calendar container found');
                            return null;
                        }

                        // Look for navigation arrows inside the calendar
                        // They could be buttons, divs, spans, or SVGs
                        var navElements = [];

                        // Strategy 1: Look for elements with arrow-related text or class
                        var allElements = calContainer.querySelectorAll('*');
                        for (var i = 0; i < allElements.length; i++) {
                            var el = allElements[i];
                            var rect = el.getBoundingClientRect();

                            // Skip very small or hidden elements
                            if (rect.width < 10 || rect.height < 10) continue;

                            var text = (el.innerText || el.textContent || '').trim();
                            var className = (el.getAttribute('class') || '').toLowerCase();
                            var ariaLabel = (el.getAttribute('aria-label') || '').toLowerCase();

                            // Check if this looks like a navigation element
                            var isNavElement = (
                                text === '>' || text === '<' ||
                                text === 'chevron_right' || text === 'chevron_left' ||
                                text === 'arrow_right' || text === 'arrow_left' ||
                                className.includes('arrow') ||
                                className.includes('next') || className.includes('prev') ||
                                ariaLabel.includes('next') || ariaLabel.includes('previous') ||
                                ariaLabel.includes('month')
                            );

                            // Also check for SVG icons that might be arrows
                            var hasSvg = !!el.querySelector('svg') || el.tagName === 'SVG';
                            var isSmall = rect.width < 50 && rect.height < 50;

                            if (isNavElement || (hasSvg && isSmall)) {
                                navElements.push({
                                    el: el,
                                    x: rect.x,
                                    y: rect.y,
                                    text: text,
                                    tag: el.tagName
                                });
                            }
                        }

                        console.log('Found ' + navElements.length + ' potential nav elements');

                        // Sort by x position and return rightmost (next button)
                        navElements.sort(function(a, b) { return b.x - a.x; });

                        if (navElements.length >= 1) {
                            console.log('Returning nav element at x=' + navElements[0].x + ', text=' + navElements[0].text);
                            return navElements[0].el;
                        }

                        // Fallback: look for any SVG elements in the top part of the calendar
                        var calRect = calContainer.getBoundingClientRect();
                        var topHalf = calRect.y + calRect.height / 3;

                        var svgs = calContainer.querySelectorAll('svg');
                        var topSvgs = [];
                        for (var i = 0; i < svgs.length; i++) {
                            var rect = svgs[i].getBoundingClientRect();
                            if (rect.y < topHalf && rect.width > 5 && rect.height > 5) {
                                topSvgs.push({el: svgs[i], x: rect.x, y: rect.y});
                            }
                        }

                        topSvgs.sort(function(a, b) { return b.x - a.x; });
                        if (topSvgs.length >= 1) {
                            // Return the parent element (might be a clickable wrapper)
                            var parent = topSvgs[0].el.parentElement;
                            console.log('Returning SVG parent at x=' + topSvgs[0].x);
                            return parent || topSvgs[0].el;
                        }

                        return null;
                    """)

                    if js_result:
                        logger.info(f"Found calendar nav element, will click {months_diff} times to reach target month")
                        for i in range(months_diff):
                            # Re-find the nav element each time since the DOM might change
                            next_clicked = self.driver_service.driver.execute_script("""
                                // Find the calendar container
                                var calContainer = null;
                                var calSelectors = ['[class*="calendar"]', '[class*="Calendar"]', '.MuiCalendarPicker-root'];
                                for (var j = 0; j < calSelectors.length; j++) {
                                    var el = document.querySelector(calSelectors[j]);
                                    if (el) {
                                        var rect = el.getBoundingClientRect();
                                        if (rect.width > 100) {
                                            calContainer = el;
                                            break;
                                        }
                                    }
                                }

                                if (!calContainer) return false;

                                // Look for navigation elements
                                var navElements = [];
                                var allElements = calContainer.querySelectorAll('*');
                                for (var j = 0; j < allElements.length; j++) {
                                    var el = allElements[j];
                                    var rect = el.getBoundingClientRect();
                                    if (rect.width < 10 || rect.height < 10) continue;

                                    var text = (el.innerText || el.textContent || '').trim();
                                    var className = (el.getAttribute('class') || '').toLowerCase();
                                    var ariaLabel = (el.getAttribute('aria-label') || '').toLowerCase();

                                    var isNavElement = (
                                        text === '>' || text === '<' ||
                                        className.includes('arrow') || className.includes('next') ||
                                        ariaLabel.includes('next') || ariaLabel.includes('month')
                                    );

                                    var hasSvg = !!el.querySelector('svg') || el.tagName === 'SVG';
                                    var isSmall = rect.width < 50 && rect.height < 50;

                                    if (isNavElement || (hasSvg && isSmall)) {
                                        navElements.push({el: el, x: rect.x});
                                    }
                                }

                                // Click rightmost element (next button)
                                navElements.sort(function(a, b) { return b.x - a.x; });
                                if (navElements.length >= 1) {
                                    navElements[0].el.click();
                                    return true;
                                }

                                // Fallback: SVGs in top of calendar
                                var calRect = calContainer.getBoundingClientRect();
                                var topHalf = calRect.y + calRect.height / 3;
                                var svgs = calContainer.querySelectorAll('svg');
                                var topSvgs = [];
                                for (var j = 0; j < svgs.length; j++) {
                                    var rect = svgs[j].getBoundingClientRect();
                                    if (rect.y < topHalf && rect.width > 5) {
                                        topSvgs.push({el: svgs[j], x: rect.x});
                                    }
                                }
                                topSvgs.sort(function(a, b) { return b.x - a.x; });
                                if (topSvgs.length >= 1) {
                                    var parent = topSvgs[0].el.parentElement;
                                    (parent || topSvgs[0].el).click();
                                    return true;
                                }

                                return false;
                            """)

                            if next_clicked:
                                self.wis.human_delay(0.4, 0.6)
                                logger.debug(f"Calendar nav: clicked next month ({i+1}/{months_diff})")
                            else:
                                logger.warning(f"JS could not find next button on iteration {i+1}")
                                break

                        self._take_screenshot("calendar_after_js_nav")
                        self.wis.human_delay(0.5, 1)
                        arrow_nav_success = True
                        logger.info("JavaScript navigation completed")
                    else:
                        logger.warning("Could not find calendar nav buttons via JS")

                except Exception as js_e:
                    logger.warning(f"JavaScript navigation failed: {js_e}")

            # Strategy 3: Navigate using arrow buttons (fallback) - only if JS nav failed
            if months_diff > 0 and not arrow_nav_success:
                logger.info("Keyboard nav failed, trying button clicks")
                # Navigate forward - click next button multiple times
                for i in range(months_diff):
                    clicked = False

                    # First, try to find all buttons in the calendar popup
                    # and identify the right arrow by position (rightmost button in header)
                    try:
                        # Find calendar header/container
                        calendar_containers = self.driver_service.driver.find_elements(
                            By.CSS_SELECTOR,
                            ".MuiCalendarPicker-root, .MuiDateCalendar-root, .MuiPickersCalendarHeader-root, [class*='calendar'], [class*='Calendar']"
                        )

                        for container in calendar_containers:
                            if not container.is_displayed():
                                continue
                            # Find buttons within this container
                            btns_in_cal = container.find_elements(By.TAG_NAME, "button")
                            # The navigation buttons are usually at the top, find rightmost
                            nav_buttons = []
                            for btn in btns_in_cal:
                                try:
                                    if btn.is_displayed():
                                        # Navigation buttons typically have SVG icons and are small
                                        rect = btn.rect
                                        if rect['width'] < 60 and rect['height'] < 60:
                                            nav_buttons.append(btn)
                                except:
                                    continue

                            if len(nav_buttons) >= 2:
                                # Sort by x position, rightmost is next
                                nav_buttons.sort(key=lambda b: b.rect['x'], reverse=True)
                                next_btn = nav_buttons[0]
                                self.driver_service.driver.execute_script("arguments[0].click();", next_btn)
                                self.wis.human_delay(0.4, 0.6)
                                clicked = True
                                logger.info(f"Clicked next month by position ({i+1}/{months_diff})")
                                break
                    except Exception as e:
                        logger.debug(f"Position-based nav failed: {e}")

                    # Try specific MUI selectors
                    if not clicked:
                        next_selectors = [
                            "button[aria-label*='Next month']",
                            "button[aria-label*='next month']",
                            ".MuiPickersCalendarHeader-switchHeader button:last-child",
                            ".MuiPickersArrowSwitcher-root button:last-child",
                            ".MuiPickersArrowSwitcher-button:last-of-type",
                            "button.MuiIconButton-root:last-of-type",
                            "[class*='ArrowRight']",
                            "[class*='arrowRight']",
                            "[class*='next']",
                            "[class*='Next']",
                        ]

                        for selector in next_selectors:
                            try:
                                btns = self.driver_service.driver.find_elements(By.CSS_SELECTOR, selector)
                                for btn in btns:
                                    if btn.is_displayed():
                                        self.driver_service.driver.execute_script("arguments[0].click();", btn)
                                        self.wis.human_delay(0.4, 0.6)
                                        clicked = True
                                        logger.info(f"Clicked next month via selector ({i+1}/{months_diff})")
                                        break
                                if clicked:
                                    break
                            except:
                                continue

                    # Fallback: Find SVG icons and click their parent buttons
                    if not clicked:
                        try:
                            svgs = self.driver_service.driver.find_elements(By.TAG_NAME, "svg")
                            right_arrow_svgs = []
                            for svg in svgs:
                                if svg.is_displayed():
                                    # Check if it looks like a right arrow (ChevronRight, ArrowRight, etc.)
                                    svg_class = svg.get_attribute("class") or ""
                                    svg_data = svg.get_attribute("data-testid") or ""
                                    if "right" in svg_class.lower() or "right" in svg_data.lower() or "chevron" in svg_class.lower():
                                        right_arrow_svgs.append(svg)
                                    else:
                                        # Check position - rightmost SVG in header area
                                        rect = svg.rect
                                        if rect['y'] < 200:  # In header area
                                            right_arrow_svgs.append(svg)

                            # Sort by x position and click the rightmost
                            if right_arrow_svgs:
                                right_arrow_svgs.sort(key=lambda s: s.rect['x'], reverse=True)
                                svg = right_arrow_svgs[0]
                                parent = svg.find_element(By.XPATH, "./..")
                                self.driver_service.driver.execute_script("arguments[0].click();", parent)
                                self.wis.human_delay(0.4, 0.6)
                                clicked = True
                                logger.info(f"Clicked next via SVG parent ({i+1}/{months_diff})")
                        except Exception as e:
                            logger.debug(f"SVG fallback failed: {e}")

                    # Last resort: JavaScript to simulate arrow key
                    if not clicked:
                        try:
                            # Try keyboard navigation
                            from selenium.webdriver.common.keys import Keys
                            active = self.driver_service.driver.switch_to.active_element
                            active.send_keys(Keys.ARROW_RIGHT)
                            self.wis.human_delay(0.3, 0.5)
                            # Check if month changed (this might not work for all calendars)
                        except:
                            pass

                    if not clicked:
                        logger.warning(f"Could not click next month button on iteration {i+1}")
                        self._take_screenshot(f"calendar_nav_failed_{i+1}")

            elif months_diff < 0:
                # Navigate backward
                for i in range(abs(months_diff)):
                    clicked = False
                    prev_selectors = [
                        "button[aria-label*='Previous month']",
                        "button[aria-label*='previous month']",
                        ".MuiPickersCalendarHeader-switchHeader button:first-child",
                        ".MuiPickersArrowSwitcher-root button:first-child",
                        "button.MuiIconButton-root:first-of-type",
                    ]

                    for selector in prev_selectors:
                        try:
                            btns = self.driver_service.driver.find_elements(By.CSS_SELECTOR, selector)
                            for btn in btns:
                                if btn.is_displayed():
                                    btn.click()
                                    self.wis.human_delay(0.4, 0.6)
                                    clicked = True
                                    break
                            if clicked:
                                break
                        except:
                            continue

                    if not clicked:
                        logger.warning(f"Could not click previous month button")

            self.wis.human_delay(0.5, 1)

            # Now click on the target day
            day_clicked = False

            # MUI typically uses buttons for days with the day number as text
            # Find all buttons and look for one with the exact day number
            buttons = self.driver_service.driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                try:
                    if not btn.is_displayed():
                        continue
                    btn_text = btn.text.strip()
                    # Check if button text is exactly the day number
                    if btn_text == str(target_day):
                        # Verify it's a calendar day button (not other buttons)
                        btn_class = btn.get_attribute("class") or ""
                        # MUI day buttons typically have "day" in class or are in a calendar grid
                        if "day" in btn_class.lower() or "MuiPickersDay" in btn_class or len(btn_text) <= 2:
                            btn.click()
                            self.wis.human_delay(0.3, 0.5)
                            day_clicked = True
                            logger.info(f"Clicked day {target_day}")
                            break
                except:
                    continue

            # Secondary fallback: look for any element with the day text
            if not day_clicked:
                day_elements = self.driver_service.driver.find_elements(
                    By.XPATH, f"//*[text()='{target_day}']"
                )
                for elem in day_elements:
                    try:
                        if elem.is_displayed() and elem.tag_name in ['button', 'div', 'span', 'td']:
                            elem.click()
                            self.wis.human_delay(0.3, 0.5)
                            day_clicked = True
                            logger.info(f"Clicked day {target_day} via xpath")
                            break
                    except:
                        continue

            if day_clicked:
                logger.info(f"Successfully selected day {target_day}")
                # Some calendars auto-close, wait a moment
                self.wis.human_delay(0.5, 1)
                self._take_screenshot("calendar_day_selected")
                return True
            else:
                logger.warning(f"Could not click day {target_day}")
                self._take_screenshot("calendar_day_not_found")
                return False

        except Exception as e:
            logger.error(f"Error navigating calendar: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _click_update_button(self) -> bool:
        """Find and click the Update button"""
        try:
            update_xpaths = [
                "//button[.//text()[contains(., 'Update')]]",
                "//button[contains(text(), 'Update')]",
                "//button[.//span[contains(text(), 'Update')]]",
            ]

            for xpath in update_xpaths:
                btns = self.driver_service.driver.find_elements(By.XPATH, xpath)
                for btn in btns:
                    if btn.is_displayed():
                        btn_text = btn.text.strip().lower()
                        if 'update' in btn_text:
                            self.driver_service.driver.execute_script("arguments[0].click();", btn)
                            logger.info("Clicked Update button")
                            self.wis.human_delay(2, 3)
                            return True

            # CSS fallback
            css_selectors = [
                "button.MuiButton-containedPrimary",
                "button.MuiButton-contained",
            ]
            for sel in css_selectors:
                btns = self.driver_service.driver.find_elements(By.CSS_SELECTOR, sel)
                for btn in btns:
                    if btn.is_displayed() and 'update' in btn.text.lower():
                        self.driver_service.driver.execute_script("arguments[0].click();", btn)
                        logger.info("Clicked Update button (CSS)")
                        self.wis.human_delay(2, 3)
                        return True

            logger.warning("Could not find Update button")
            return False

        except Exception as e:
            logger.error(f"Error clicking Update button: {e}")
            return False
