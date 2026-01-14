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
            # Common selectors for login forms
            email_selectors = [
                'input[name="email"]',
                'input[type="email"]',
                'input[placeholder*="email" i]',
                'input[id*="email" i]',
                '#email',
            ]

            password_selectors = [
                'input[name="password"]',
                'input[type="password"]',
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

            # Try to find a search box
            search_selectors = [
                'input[type="search"]',
                'input[placeholder*="search" i]',
                'input[name="search"]',
                '.search-input',
                '#search',
            ]

            search_box = None
            for selector in search_selectors:
                try:
                    search_box = self.driver_service.find_element(By.CSS_SELECTOR, selector)
                    if search_box:
                        logger.info(f"Found search box in {section_name}: {selector}")
                        break
                except:
                    continue

            if search_box:
                # Clear and search - ONLY use first name because MAF search breaks with spaces
                # The full name will be verified when matching the row
                search_term = lead_name.split()[0] if ' ' in lead_name else lead_name
                logger.info(f"Searching for '{search_term}' (from full name '{lead_name}')")
                search_box.clear()
                self.wis.simulated_typing(search_box, search_term)
                self.wis.human_delay(2, 3)

            # Look for the lead in the list - this will match the FULL name
            lead_found = self._find_lead_row(lead_name)

            if lead_found:
                return (lead_found, section_name)

            return (None, "")

        except Exception as e:
            logger.error(f"Error searching {section_name} section: {e}")
            return (None, "")

    def _find_lead_row(self, lead_name: str) -> Optional[Any]:
        """Find a lead row by name"""
        try:
            # Wait for any loading spinners to disappear
            self._wait_for_page_load()

            # Common selectors for lead/customer rows - try in order of specificity
            row_selectors = [
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

            for row_selector in row_selectors:
                try:
                    # Use driver directly to avoid error logging for expected failures
                    rows = self.driver_service.driver.find_elements(By.CSS_SELECTOR, row_selector)
                    if rows:
                        logger.debug(f"Found {len(rows)} elements with selector '{row_selector}'")
                        for row in rows:
                            try:
                                row_text = row.text.lower()
                                if lead_name.lower() in row_text:
                                    logger.info(f"Found lead '{lead_name}' using selector '{row_selector}'")
                                    return row
                            except:
                                continue
                except:
                    continue

            # Try JavaScript search as fallback - more comprehensive
            search_script = """
            function findLead(name) {
                name = name.toLowerCase();

                // Look for any element containing the name
                var elements = document.querySelectorAll('*');
                for (var i = 0; i < elements.length; i++) {
                    var el = elements[i];
                    if (el.textContent.toLowerCase().includes(name)) {
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
            return findLead(arguments[0]);
            """

            lead_element = self.driver_service.driver.execute_script(search_script, lead_name)
            if lead_element:
                logger.info(f"Found lead '{lead_name}' using JavaScript fallback")
                return lead_element

            # If still not found, log the page state for debugging
            logger.warning(f"Could not find lead '{lead_name}' on page")
            self._take_screenshot(f"lead_not_found_{lead_name.replace(' ', '_')}")

            return None

        except Exception as e:
            logger.error(f"Error finding lead row: {e}")
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
        """
        try:
            # Calculate future date
            future_date = datetime.now() + timedelta(days=self.nurture_days_offset)
            date_str = future_date.strftime("%Y-%m-%d")  # Format: 2026-07-14
            logger.info(f"Setting Nurture date to {date_str} ({self.nurture_days_offset} days from now)")

            # Find the date input - look for input with type="date" or the Next Status Update Date field
            date_input = None
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
                            logger.info(f"Found date input: {selector}")
                            break
                    if date_input:
                        break
                except:
                    continue

            if not date_input:
                # Try to find by label text
                try:
                    # Look for input near "Next Status Update Date" label
                    labels = self.driver_service.driver.find_elements(By.XPATH, "//*[contains(text(), 'Next Status Update Date')]")
                    for label in labels:
                        # Try to find nearby input
                        parent = label.find_element(By.XPATH, "./..")
                        inputs = parent.find_elements(By.TAG_NAME, "input")
                        for inp in inputs:
                            if inp.is_displayed():
                                date_input = inp
                                logger.info("Found date input via label proximity")
                                break
                        if date_input:
                            break
                except Exception as e:
                    logger.debug(f"Label search failed: {e}")

            if date_input:
                # Clear and set the new date
                # For date inputs, we can use JavaScript to set the value directly
                self.driver_service.driver.execute_script(
                    "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', { bubbles: true })); arguments[0].dispatchEvent(new Event('change', { bubbles: true }));",
                    date_input, date_str
                )
                logger.info(f"Set date input to: {date_str}")
                self.wis.human_delay(0.5, 1)
                return True
            else:
                logger.warning("Could not find date input for Nurture status")
                self._take_screenshot("nurture_no_date_input")
                return False

        except Exception as e:
            logger.error(f"Error setting nurture date: {e}")
            return False

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
