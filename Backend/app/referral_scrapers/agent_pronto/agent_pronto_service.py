"""
Agent Pronto Referral Service

Automates lead status updates on Agent Pronto (https://agentpronto.com)
Uses magic link authentication (login link sent via email)
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
from datetime import datetime, timedelta, timezone
import time
import random
import logging
import re
import imaplib
import email
from email.header import decode_header
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
LOGIN_URL = "https://agentpronto.com/sign-in"
APP_URL = "https://agentpronto.com/app"
DASHBOARD_URL = "https://agentpronto.com/app/dashboard"
REFERRALS_URL = "https://agentpronto.com/app/referrals"
DEALS_URL = "https://agentpronto.com/app/deals"
DEALS_IN_PROGRESS_URL = "https://agentpronto.com/app/deals?status=in-progress"
CREDS = Credentials()

# Agent Pronto Status Options
# Active statuses - these are submit buttons on the status update page
ACTIVE_STATUSES = {
    "communicating": "Communicating with referral",
    "showing": "Showing properties in person",
    "offer_accepted": "Offer accepted",
    # Aliases for FUB stage mapping
    "contacted": "Communicating with referral",
    "showing_properties": "Showing properties in person",
    "in_progress": "Communicating with referral",
}

# Lost/Inactive statuses - these require selecting radio + clicking Archive
LOST_STATUSES = {
    "agent_did_not_make_contact": "I was never able to contact this referral",
    "no_longer_buying_or_selling": "They're no longer buying / selling a property",
    "already_has_agent": "They already have an agent",
    "unresponsive": "They became unresponsive",
    "denied_loan_approval": "They don't have the means to buy",
    "listing_expired_or_cancelled": "The listing expired or was cancelled",
    "other": "Other",
    # Aliases for FUB stage mapping
    "lost": "unresponsive",
    "not_responding": "unresponsive",
    "no_contact": "agent_did_not_make_contact",
    "has_agent": "already_has_agent",
    "inactive": "unresponsive",
    "archived": "unresponsive",
}

logger = logging.getLogger(__name__)


def get_agent_pronto_magic_link(
    email_address: str,
    app_password: str,
    max_retries: int = 15,
    retry_delay: float = 3.0,
    max_age_seconds: int = 180,
    min_email_time: datetime = None
) -> Optional[str]:
    """
    Get the magic login link from Agent Pronto email.

    Args:
        email_address: Gmail/Google Workspace email address
        app_password: Google App Password
        max_retries: Number of times to check for the email
        retry_delay: Seconds between retries
        max_age_seconds: Only check emails from the last N seconds
        min_email_time: Only return emails received AFTER this time (UTC)

    Returns:
        The magic link URL or None if not found
    """
    imap_server = "imap.gmail.com"
    imap_port = 993

    for attempt in range(max_retries):
        try:
            logger.info(f"Checking for magic link email (attempt {attempt + 1}/{max_retries})...")

            # Connect to IMAP
            connection = imaplib.IMAP4_SSL(imap_server, imap_port)
            connection.login(email_address, app_password.replace(" ", ""))
            connection.select("INBOX")

            # Search for recent emails
            since_date = (datetime.now() - timedelta(seconds=max_age_seconds)).strftime("%d-%b-%Y")
            status, message_ids = connection.search(None, f'(SINCE "{since_date}")')

            if status == "OK" and message_ids[0]:
                ids = message_ids[0].split()
                ids.reverse()  # Most recent first

                for msg_id in ids[:20]:
                    try:
                        # Use BODY.PEEK to avoid marking email as read (may prevent link tracking)
                        status, msg_data = connection.fetch(msg_id, "(BODY.PEEK[])")
                        if status != "OK":
                            continue

                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)

                        # Check if from Agent Pronto
                        from_header = msg.get("From", "").lower()
                        if "agentpronto" not in from_header and "agent pronto" not in from_header:
                            continue

                        # Check email age and min time
                        date_str = msg.get("Date", "")
                        try:
                            msg_date = email.utils.parsedate_to_datetime(date_str)
                            if msg_date:
                                # Check max age
                                now = datetime.now(msg_date.tzinfo) if msg_date.tzinfo else datetime.now()
                                age = (now - msg_date).total_seconds()
                                if age > max_age_seconds:
                                    continue

                                # Check min time (only accept emails AFTER this time)
                                if min_email_time:
                                    # Convert to UTC for comparison
                                    msg_time_utc = msg_date.astimezone(timezone.utc) if msg_date.tzinfo else msg_date.replace(tzinfo=timezone.utc)
                                    min_time_utc = min_email_time if min_email_time.tzinfo else min_email_time.replace(tzinfo=timezone.utc)
                                    if msg_time_utc < min_time_utc:
                                        logger.debug(f"Email too old (before request time): {msg_time_utc} < {min_time_utc}")
                                        continue
                        except Exception as e:
                            logger.debug(f"Error parsing email date: {e}")

                        # Get email body
                        body = _get_email_body(msg)

                        # Find magic link
                        link = _extract_magic_link(body)
                        if link:
                            logger.info(f"Found magic link: {link[:50]}...")
                            connection.logout()
                            return link

                    except Exception as e:
                        logger.debug(f"Error parsing email: {e}")
                        continue

            connection.logout()

            if attempt < max_retries - 1:
                logger.info(f"Magic link not found yet, waiting {retry_delay}s...")
                time.sleep(retry_delay)

        except Exception as e:
            logger.error(f"Error checking email: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)

    logger.warning("Magic link not found after all retries")
    return None


def _get_email_body(msg) -> str:
    """Extract text body from email message"""
    body = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    body += payload.decode(charset, errors="ignore")
                except:
                    pass
            elif content_type == "text/html" and not body:
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    body += payload.decode(charset, errors="ignore")
                except:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="ignore")
        except:
            pass

    return body


def _extract_magic_link(text: str) -> Optional[str]:
    """Extract magic login link from email body"""
    if not text:
        return None

    # PRIORITY 1: Look for direct agentpronto.com links (not wrapped in tracking)
    direct_patterns = [
        r'(https?://(?:www\.)?agentpronto\.com/[^\s<>"\']*sign[_-]?in[^\s<>"\']*)',
        r'(https?://(?:www\.)?agentpronto\.com/[^\s<>"\']*login[^\s<>"\']*)',
        r'(https?://(?:www\.)?agentpronto\.com/[^\s<>"\']*auth[^\s<>"\']*)',
        r'(https?://(?:www\.)?agentpronto\.com/[^\s<>"\']*magic[^\s<>"\']*)',
        r'(https?://(?:www\.)?agentpronto\.com/[^\s<>"\']*token[^\s<>"\']*)',
        # Generic pattern for any direct agentpronto link with a token/code
        r'(https?://(?:www\.)?agentpronto\.com/[^\s<>"\']*[?&](?:token|code|t|c|key)=[^\s<>"\']+)',
    ]

    for pattern in direct_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # Filter out tracking subdomain links, prefer direct links
            direct_matches = [m for m in matches if 'lnx.' not in m.lower()]
            if direct_matches:
                return max(direct_matches, key=len)

    # PRIORITY 2: Look for any direct agentpronto.com link with long path/params
    all_direct_links = re.findall(r'(https?://(?:www\.)?agentpronto\.com/[^\s<>"\']+)', text, re.IGNORECASE)
    for link in all_direct_links:
        # Skip tracking links and static assets
        if 'lnx.' in link.lower():
            continue
        if any(skip in link.lower() for skip in ['.css', '.js', '.png', '.jpg', 'static', 'assets', 'unsubscribe']):
            continue
        # Accept links with tokens or long paths
        if len(link) > 60 or '?' in link:
            return link

    # PRIORITY 3: Fallback to tracking links (may be single-use and already consumed)
    tracking_patterns = [
        r'(https?://[^\s<>"\']*lnx\.agentpronto\.com[^\s<>"\']*)',
        r'(https?://[^\s<>"\']*agentpronto[^\s<>"\']*click[^\s<>"\']*)',
    ]

    for pattern in tracking_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            logger.warning("Only found tracking link (may be single-use) - prefer direct links")
            return max(matches, key=len)

    return None


class AgentProntoService(BaseReferralService):
    """Service for automating lead status updates on Agent Pronto"""

    def __init__(
        self,
        lead: Lead = None,
        status: Dict[str, Any] = None,
        organization_id: str = None,
        driver_service=None,
        min_sync_interval_hours: int = 168,
        same_status_note: str = None,
        force_sync: bool = False
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
            self.email = getattr(CREDS, 'AGENT_PRONTO_EMAIL', None)
        if not self.password:
            self.password = getattr(CREDS, 'AGENT_PRONTO_PASSWORD', None)

        # If still no credentials, try to load from database directly
        if not self.email:
            self._load_credentials_from_database()

        # Gmail credentials for magic link retrieval
        # Priority: DB two_factor_auth > Agent Pronto login email > GMAIL_EMAIL env
        self.gmail_email = getattr(CREDS, 'GMAIL_EMAIL', None)
        self.gmail_app_password = getattr(CREDS, 'GMAIL_APP_PASSWORD', None)

        # Also try to load from database two_factor_auth config
        self._load_gmail_credentials_from_database()

        # If the magic link goes to the AP login email (not the GMAIL_EMAIL),
        # use the AP login email for IMAP (assumes Google Workspace same domain)
        if self.email and self.gmail_email and self.email != self.gmail_email:
            ap_domain = self.email.split('@')[-1] if '@' in self.email else ''
            gmail_domain = self.gmail_email.split('@')[-1] if '@' in self.gmail_email else ''
            if ap_domain == gmail_domain:
                logger.info(f"Agent Pronto email ({self.email}) differs from GMAIL_EMAIL - using AP email for IMAP")
                self.gmail_email = self.email

        self.lead = lead
        self.lead_name = f"{self.lead.first_name} {self.lead.last_name}" if lead else ""
        self.min_sync_interval_hours = min_sync_interval_hours
        self.force_sync = force_sync
        self.is_logged_in = False
        self.same_status_note = same_status_note or "Same as previous update. Continuing to work with this referral."

        # Status handling - can be dict, list, or string
        self.status = status
        if isinstance(status, dict):
            # Convert dict to expected format if needed
            self.status = status.get('status', status)

        # Use provided driver service or create a new one
        if driver_service:
            self.driver_service = driver_service
            self.owns_driver = False
        else:
            self.driver_service = DriverService()
            self.owns_driver = True

        self.lead_service = LeadServiceSingleton.get_instance()
        self.wis = wis()

    def _load_credentials_from_database(self):
        """Load credentials from database if not set via environment"""
        try:
            from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
            settings_service = LeadSourceSettingsSingleton.get_instance()

            # Try both naming conventions
            for source_name in ["AgentPronto", "Agent Pronto"]:
                source_settings = settings_service.get_by_source_name(source_name)
                if source_settings and source_settings.metadata:
                    metadata = source_settings.metadata
                    if isinstance(metadata, str):
                        import json
                        metadata = json.loads(metadata)

                    creds = metadata.get('credentials', {})
                    if creds:
                        self.email = self.email or creds.get('email')
                        self.password = self.password or creds.get('password')
                        logger.info(f"Loaded AgentPronto credentials from database ({source_name})")
                        return

        except Exception as e:
            logger.warning(f"Could not load credentials from database: {e}")

    def _load_gmail_credentials_from_database(self):
        """Load Gmail credentials for magic link retrieval from database"""
        try:
            from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
            settings_service = LeadSourceSettingsSingleton.get_instance()

            for source_name in ["AgentPronto", "Agent Pronto"]:
                source_settings = settings_service.get_by_source_name(source_name)
                if source_settings and source_settings.metadata:
                    metadata = source_settings.metadata
                    if isinstance(metadata, str):
                        import json
                        metadata = json.loads(metadata)

                    # Check for two_factor_auth config (same as other services)
                    two_fa = metadata.get('two_factor_auth', {})
                    if two_fa.get('enabled'):
                        self.gmail_email = self.gmail_email or two_fa.get('email')
                        self.gmail_app_password = self.gmail_app_password or two_fa.get('app_password')
                        if self.gmail_email and self.gmail_app_password:
                            logger.info("Loaded Gmail credentials for magic link from database")
                            return

        except Exception as e:
            logger.warning(f"Could not load Gmail credentials from database: {e}")

    @classmethod
    def get_platform_name(cls) -> str:
        return "AgentPronto"

    def return_platform_name(self) -> str:
        return self.get_platform_name()

    def update_active_lead(self, lead: Lead, status: Any):
        """Update the active lead and status for this service instance"""
        self.lead = lead
        self.status = status
        self.lead_name = f"{lead.first_name} {lead.last_name}" if lead else ""

    def agent_pronto_run(self) -> bool:
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
            self.logger.error(f"AgentPronto run failed: {e}")
            return False

        finally:
            if self.owns_driver:
                self.logout()

    def login(self) -> bool:
        """Login to Agent Pronto using magic link authentication"""
        try:
            if not self.driver_service.driver:
                if not self.driver_service.initialize_driver():
                    logger.error("Failed to initialize driver")
                    return False

            logger.info(f"Navigating to {LOGIN_URL}")
            if not self.driver_service.get_page(LOGIN_URL):
                logger.error("Failed to load login page")
                return False

            self.wis.human_delay(2, 4)

            # Check if we're already logged in (redirected to app)
            current_url = self.driver_service.get_current_url()
            if current_url and "/app" in current_url and "sign" not in current_url.lower():
                logger.info("Already logged in - redirected to app")
                self.is_logged_in = True
                return True

            # Agent Pronto uses magic link login (email only, no password)
            # Step 1: Find and fill email field
            email_selectors = [
                'input[name="email"]',
                'input[type="email"]',
                'input[id="email"]',
                'input[placeholder*="email" i]',
            ]

            email_field = None
            for selector in email_selectors:
                try:
                    email_field = self.driver_service.driver.find_element(By.CSS_SELECTOR, selector)
                    if email_field:
                        logger.info(f"Found email field: {selector}")
                        break
                except:
                    continue

            if not email_field:
                logger.error("Could not find email field")
                self._take_screenshot("login_no_email_field")
                return False

            # Enter email
            email_field.clear()
            self.wis.simulated_typing(email_field, self.email)
            logger.info(f"Entered email: {self.email}")
            self.wis.human_delay(1, 2)

            # Step 2: Click Sign In button to request magic link
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
            ]

            submit_btn = None
            for selector in submit_selectors:
                try:
                    submit_btn = self.driver_service.driver.find_element(By.CSS_SELECTOR, selector)
                    if submit_btn and submit_btn.text and "sign" in submit_btn.text.lower():
                        break
                except:
                    continue

            if not submit_btn:
                # Try by text
                try:
                    submit_btn = self.driver_service.driver.find_element(By.XPATH, "//button[contains(text(), 'Sign In')]")
                except:
                    pass

            if submit_btn:
                self.driver_service.safe_click(submit_btn)
                logger.info("Clicked Sign In button - magic link email should be sent")
            else:
                # Try pressing Enter
                email_field.send_keys(Keys.RETURN)
                logger.info("Pressed Enter to submit")

            self.wis.human_delay(3, 5)

            # Record time when magic link was requested
            magic_link_request_time = datetime.now(timezone.utc)
            logger.info(f"Magic link requested at: {magic_link_request_time}")

            # Take screenshot of post-submit page
            self._take_screenshot("after_magic_link_request")

            # Step 3: Check for Gmail credentials to retrieve magic link
            if not self.gmail_email or not self.gmail_app_password:
                logger.error("Gmail credentials not configured - cannot retrieve magic link automatically")
                logger.info("Please configure two_factor_auth in lead source settings with Gmail email and app password")
                return False

            # Step 4: Retrieve magic link from email
            logger.info("Waiting for magic link email...")
            magic_link = get_agent_pronto_magic_link(
                email_address=self.gmail_email,
                app_password=self.gmail_app_password,
                max_retries=20,
                retry_delay=3.0,
                max_age_seconds=300,
                min_email_time=magic_link_request_time
            )

            if not magic_link:
                logger.error("Could not retrieve magic link from email")
                self._take_screenshot("magic_link_not_found")
                return False

            # Step 5: Navigate to magic link
            logger.info(f"Navigating to magic link...")
            self.driver_service.get_page(magic_link)
            self.wis.human_delay(5, 8)

            # Step 6: Verify login success
            current_url = self.driver_service.get_current_url()
            logger.info(f"Current URL after magic link: {current_url}")

            if current_url and ("/app" in current_url or "dashboard" in current_url.lower()):
                self.is_logged_in = True
                logger.info("Magic link login successful!")
                self._take_screenshot("login_success")
                return True

            # Magic link may redirect to home page - try navigating to app directly
            if current_url and "agentpronto.com" in current_url and "/app" not in current_url:
                logger.info("Redirected to home page, navigating to app...")
                self.driver_service.get_page(APP_URL)
                self.wis.human_delay(3, 5)

                current_url = self.driver_service.get_current_url()
                logger.info(f"URL after navigating to app: {current_url}")

                # If we're now in the app, login worked
                if current_url and "/app" in current_url and "sign" not in current_url.lower():
                    self.is_logged_in = True
                    logger.info("Login successful - now in app!")
                    self._take_screenshot("login_success")
                    return True

                # If redirected back to sign-in, login failed
                if current_url and "sign" in current_url.lower():
                    logger.error("Redirected back to sign-in - login failed")
                    self._take_screenshot("login_failed_redirect")
                    return False

            # Check for app elements as backup verification
            app_indicators = [
                ".dashboard",
                ".referrals",
                "[class*='dashboard']",
                "[class*='referral']",
                ".nav",
                ".sidebar",
            ]

            for selector in app_indicators:
                try:
                    element = self.driver_service.driver.find_element(By.CSS_SELECTOR, selector)
                    if element:
                        self.is_logged_in = True
                        logger.info(f"Login verified via element: {selector}")
                        return True
                except:
                    continue

            logger.warning("Could not verify login success")
            self._take_screenshot("login_verification_failed")
            return False

        except Exception as e:
            logger.error(f"Login failed: {e}")
            import traceback
            traceback.print_exc()
            self.is_logged_in = False
            return False

    def login_once(self) -> bool:
        """Login once for bulk operations - reuses existing session if available"""
        if self.is_logged_in:
            logger.info("Already logged in, reusing session")
            return True
        return self.login()

    def logout(self) -> None:
        """Logout and close browser"""
        try:
            if self.driver_service and hasattr(self.driver_service, 'driver') and self.driver_service.driver:
                self.driver_service.driver.quit()
        except Exception as e:
            logger.error(f"Error closing driver: {e}")
        finally:
            self.is_logged_in = False

    def navigate_to_referrals(self) -> bool:
        """Navigate to the deals/referrals list page"""
        try:
            # Agent Pronto uses /app/deals for referrals
            logger.info("Navigating to deals page...")
            self.driver_service.get_page(DEALS_IN_PROGRESS_URL)
            self.wis.human_delay(2, 3)

            current_url = self.driver_service.get_current_url()
            if "deals" in current_url and "sign" not in current_url.lower():
                logger.info(f"Navigated to deals page: {current_url}")
                return True

            # Fallback to other URLs
            referral_urls = [
                DEALS_URL,
                REFERRALS_URL,
                f"{APP_URL}/referrals",
                DASHBOARD_URL,
            ]

            for url in referral_urls:
                try:
                    self.driver_service.get_page(url)
                    self.wis.human_delay(2, 3)

                    current = self.driver_service.get_current_url()
                    if "sign" not in current.lower():
                        logger.info(f"Navigated to: {current}")
                        return True
                except:
                    continue

            logger.warning("Could not navigate to referrals/deals page")
            return False

        except Exception as e:
            logger.error(f"Error navigating to referrals: {e}")
            return False

    def _verify_referrals_page(self) -> bool:
        """Check if we're on a referrals/leads page"""
        try:
            current_url = self.driver_service.get_current_url()
            if "referral" in current_url.lower() or "lead" in current_url.lower():
                return True

            # Check for referral list elements
            list_indicators = [
                "table",
                ".referral-list",
                ".leads-list",
                "[class*='referral']",
                "[class*='lead-list']",
            ]

            for selector in list_indicators:
                try:
                    element = self.driver_service.find_element(By.CSS_SELECTOR, selector)
                    if element:
                        return True
                except:
                    continue

            return False
        except:
            return False

    def find_and_click_customer_by_name(self, target_name: str) -> bool:
        """Find a customer/lead by name and click to open their details"""
        try:
            logger.info(f"Searching for lead: {target_name}")
            self.wis.human_delay(1, 2)

            # Agent Pronto shows deals as links with the customer name
            # Look for links that contain the customer name
            target_name_lower = target_name.lower()
            target_parts = target_name_lower.split()

            # Find all deal links (they have href containing /deals/)
            all_links = self.driver_service.driver.find_elements(By.TAG_NAME, 'a')

            for link in all_links:
                try:
                    href = link.get_attribute('href') or ""
                    link_text = link.text.lower()

                    # Check if this is a deal link with matching name
                    if '/deals/' in href and '/deals?' not in href:
                        # Check for name match
                        if target_name_lower in link_text or all(part in link_text for part in target_parts):
                            logger.info(f"Found deal link for {target_name}: {href}")
                            self.driver_service.scroll_into_view(link)
                            self.wis.human_delay(0.5, 1)
                            # Navigate directly to avoid click issues
                            self.driver_service.get_page(href)
                            self.wis.human_delay(2, 3)

                            # Verify we're on the deal detail page
                            current_url = self.driver_service.get_current_url()
                            if '/deals/' in current_url and '/deals?' not in current_url:
                                logger.info(f"Successfully navigated to deal: {current_url}")
                                return True
                except:
                    continue

            # Fallback: Look for elements containing the name
            lead_element = self._find_lead_in_list(target_name)

            if lead_element:
                logger.info(f"Found lead via fallback: {target_name}")
                # Try to find a clickable link within/near the element
                try:
                    link = lead_element.find_element(By.TAG_NAME, 'a')
                    href = link.get_attribute('href')
                    if href and '/deals/' in href:
                        self.driver_service.get_page(href)
                        self.wis.human_delay(2, 3)
                        return True
                except:
                    pass

                self.driver_service.scroll_into_view(lead_element)
                self.wis.human_delay(0.5, 1)
                self.driver_service.safe_click(lead_element)
                self.wis.human_delay(2, 3)
                return True

            logger.warning(f"Lead not found: {target_name}")
            return False

        except Exception as e:
            logger.error(f"Error finding customer: {e}")
            return False

    def _find_lead_in_list(self, lead_name: str) -> Optional[Any]:
        """Find a lead element in the list by name"""
        try:
            lead_name_lower = lead_name.lower()
            lead_name_parts = lead_name_lower.split()

            # Common selectors for lead/customer rows
            row_selectors = [
                "tr",
                ".lead-row",
                ".referral-row",
                ".referral-item",
                ".lead-item",
                ".customer-row",
                "[class*='lead']",
                "[class*='referral']",
                ".card",
                ".list-item",
            ]

            for row_selector in row_selectors:
                try:
                    rows = self.driver_service.find_elements(By.CSS_SELECTOR, row_selector)
                    for row in rows:
                        row_text = row.text.lower()

                        # Exact match
                        if lead_name_lower in row_text:
                            return row

                        # Check if all name parts are present
                        if all(part in row_text for part in lead_name_parts):
                            return row
                except:
                    continue

            # Try JavaScript search as fallback
            search_script = """
            function findLead(name) {
                name = name.toLowerCase();
                var nameParts = name.split(' ');

                // Look for table rows first
                var rows = document.querySelectorAll('tr, .referral-item, .lead-item, .list-item');
                for (var i = 0; i < rows.length; i++) {
                    var row = rows[i];
                    var text = row.textContent.toLowerCase();

                    // Check for exact match or all parts match
                    if (text.includes(name)) {
                        return row;
                    }

                    var allPartsMatch = nameParts.every(function(part) {
                        return text.includes(part);
                    });
                    if (allPartsMatch && nameParts.length > 1) {
                        return row;
                    }
                }

                // Look for any clickable element with the name
                var links = document.querySelectorAll('a, button, [onclick]');
                for (var i = 0; i < links.length; i++) {
                    var link = links[i];
                    var text = link.textContent.toLowerCase();
                    if (text.includes(name) || nameParts.every(function(p) { return text.includes(p); })) {
                        return link;
                    }
                }

                return null;
            }
            return findLead(arguments[0]);
            """

            lead_element = self.driver_service.driver.execute_script(search_script, lead_name)
            if lead_element:
                return lead_element

            return None

        except Exception as e:
            logger.error(f"Error finding lead in list: {e}")
            return None

    def update_customers(self, status_to_select: Any, custom_comment: str = None) -> bool:
        """
        Update the current lead's status - implements abstract method.

        Args:
            status_to_select: The status to set
            custom_comment: Optional custom comment (from @update notes) to use instead of default
        """
        return self._update_lead_status_on_page(status_to_select, custom_comment=custom_comment)

    def _update_lead_status_on_page(self, status: Any, custom_comment: str = None) -> bool:
        """
        Update the status of the currently open lead on Agent Pronto.

        Args:
            status: The status to set
            custom_comment: Optional custom comment (from @update notes) to use
        """
        try:
            # Parse status if it's a complex type
            primary_status, sub_status = self._parse_status(status)
            logger.info(f"Updating status to: {primary_status}" + (f" / {sub_status}" if sub_status else ""))

            # Step 1: Find and click "Update Status" button on deal detail page
            update_status_link = None
            try:
                # Look for the Update Status link (class=button-alert or text contains "Update Status")
                update_status_link = self.driver_service.driver.find_element(By.CSS_SELECTOR, 'a.button-alert')
            except:
                pass

            if not update_status_link:
                try:
                    update_status_link = self.driver_service.driver.find_element(By.XPATH, "//a[contains(text(), 'Update Status')]")
                except:
                    pass

            if not update_status_link:
                # Try getting the link by looking for href containing status_updates
                try:
                    update_status_link = self.driver_service.driver.find_element(By.CSS_SELECTOR, 'a[href*="status_updates"]')
                except:
                    pass

            if update_status_link:
                href = update_status_link.get_attribute('href')
                logger.info(f"Found Update Status link: {href}")
                self.driver_service.get_page(href)
                self.wis.human_delay(2, 3)
            else:
                logger.error("Could not find 'Update Status' button on deal page")
                self._take_screenshot("no_update_status_button")
                return False

            # Step 2: We're now on the status update page
            # Determine if this is an active or lost status
            status_key = primary_status.lower().replace(' ', '_').replace("'", "")

            # Check if it's an active status
            is_active_status = False
            active_button_text = None

            # Check against ACTIVE_STATUSES
            for key, text in ACTIVE_STATUSES.items():
                if key in status_key or status_key in key or status_key in text.lower():
                    is_active_status = True
                    active_button_text = text
                    break

            # Also check by direct text match
            if not is_active_status:
                if any(s in status_key for s in ['communicat', 'contact', 'in_progress', 'progress']):
                    is_active_status = True
                    active_button_text = "Communicating with referral"
                elif any(s in status_key for s in ['show', 'viewing', 'tour']):
                    is_active_status = True
                    active_button_text = "Showing properties in person"
                elif any(s in status_key for s in ['offer', 'accepted', 'contract', 'pending']):
                    is_active_status = True
                    active_button_text = "Offer accepted"

            if is_active_status:
                # Click the appropriate active status button
                return self._click_active_status_button(active_button_text or primary_status, custom_comment=custom_comment)
            else:
                # Handle as lost/inactive status (no comment for lost statuses)
                return self._select_lost_status(status_key, sub_status)

        except Exception as e:
            logger.error(f"Error updating lead status: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _click_active_status_button(self, status_text: str, custom_comment: str = None) -> bool:
        """
        Click an active status button (Communicating, Showing, Offer accepted).

        Args:
            status_text: The status button text to click
            custom_comment: Optional custom comment (from @update notes) to use
        """
        try:
            logger.info(f"Clicking active status button: {status_text}")

            button_clicked = False

            # Try specific known button texts
            for btn_text in [status_text, "Communicating with referral", "Showing properties in person", "Offer accepted"]:
                if status_text.lower() in btn_text.lower() or btn_text.lower() in status_text.lower():
                    try:
                        button = self.driver_service.driver.find_element(By.XPATH, f"//button[contains(text(), '{btn_text}')]")
                        if button:
                            logger.info(f"Found button: {btn_text}")
                            self.driver_service.safe_click(button)
                            self.wis.human_delay(2, 3)
                            button_clicked = True
                            break
                    except:
                        continue

            # Fallback: find all submit buttons and click the matching one
            if not button_clicked:
                buttons = self.driver_service.driver.find_elements(By.CSS_SELECTOR, 'button[type="submit"]')
                for button in buttons:
                    btn_text = button.text.lower()
                    if any(s in btn_text for s in ['communicat', 'show', 'offer', 'accept']):
                        if status_text.lower() in btn_text or btn_text in status_text.lower():
                            logger.info(f"Clicking fallback button: {button.text}")
                            self.driver_service.safe_click(button)
                            self.wis.human_delay(2, 3)
                            button_clicked = True
                            break

            if not button_clicked:
                logger.warning(f"Could not find active status button for: {status_text}")
                self._take_screenshot("active_status_button_not_found")
                return False

            # After clicking status button, a comment form appears
            # Fill in the required comment and submit
            return self._fill_comment_and_submit(custom_comment=custom_comment)

        except Exception as e:
            logger.error(f"Error clicking active status button: {e}")
            return False

    def _fill_comment_and_submit(self, custom_comment: str = None) -> bool:
        """
        Fill in the required comment field and click Submit Update.

        Args:
            custom_comment: Optional custom comment (from @update notes) to use instead of default
        """
        try:
            logger.info("Filling in status update comment...")

            # Find the textarea for the comment
            textarea = None
            textarea_selectors = [
                'textarea',
                'textarea[required]',
                'textarea[name*="comment"]',
                'textarea[name*="note"]',
                'textarea[placeholder*="comment"]',
            ]

            for selector in textarea_selectors:
                try:
                    textarea = self.driver_service.driver.find_element(By.CSS_SELECTOR, selector)
                    if textarea:
                        break
                except:
                    continue

            if not textarea:
                logger.warning("Could not find comment textarea")
                self._take_screenshot("no_comment_textarea")
                return False

            # Clear and fill the comment
            # Priority: custom_comment (@update notes) > same_status_note > default
            textarea.clear()
            comment = custom_comment or self.same_status_note or "Continuing to work with this referral. Will provide updates as progress is made."
            if custom_comment:
                logger.info(f"Using @update comment: {custom_comment[:50]}...")
            self.wis.simulated_typing(textarea, comment)
            logger.info(f"Entered comment: {comment[:50]}...")
            self.wis.human_delay(1, 2)

            # Click Submit Update button
            submit_btn = None
            submit_selectors = [
                "//button[contains(text(), 'Submit Update')]",
                "//button[contains(text(), 'Submit')]",
                "//input[@type='submit']",
                "button[type='submit']",
            ]

            for selector in submit_selectors:
                try:
                    if selector.startswith('//'):
                        submit_btn = self.driver_service.driver.find_element(By.XPATH, selector)
                    else:
                        submit_btn = self.driver_service.driver.find_element(By.CSS_SELECTOR, selector)
                    if submit_btn and submit_btn.is_displayed():
                        break
                except:
                    continue

            if submit_btn:
                logger.info("Clicking Submit Update button...")
                self.driver_service.safe_click(submit_btn)
                self.wis.human_delay(3, 5)

                # Verify success - should redirect away from the comment form
                current_url = self.driver_service.get_current_url()
                if '/status_updates' not in current_url or '/deals/' in current_url:
                    logger.info("Status update submitted successfully!")
                    return True
                else:
                    # Check for success message on page
                    try:
                        page_text = self.driver_service.driver.find_element(By.TAG_NAME, 'body').text.lower()
                        if 'success' in page_text or 'updated' in page_text:
                            logger.info("Status update successful (confirmed via page text)")
                            return True
                    except:
                        pass

                    logger.warning("May not have submitted successfully - still on status page")
                    self._take_screenshot("submit_uncertain")
                    return True  # Assume success if we got this far
            else:
                logger.error("Could not find Submit Update button")
                self._take_screenshot("no_submit_button")
                return False

        except Exception as e:
            logger.error(f"Error filling comment and submitting: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _select_lost_status(self, status_key: str, reason_detail: str = None) -> bool:
        """Select a lost/inactive status radio button and archive"""
        try:
            logger.info(f"Selecting lost status: {status_key}")

            # Map status to radio button value
            radio_value = None
            for key, label in LOST_STATUSES.items():
                if key in status_key or status_key in key:
                    # Found a match - use the actual radio value (not the alias)
                    if key in ['lost', 'not_responding', 'no_contact', 'has_agent', 'inactive', 'archived']:
                        # These are aliases, get the actual value
                        radio_value = label  # label contains the actual key for aliases
                    else:
                        radio_value = key
                    break

            if not radio_value:
                # Default to unresponsive
                radio_value = 'unresponsive'
                logger.warning(f"No matching lost status for '{status_key}', defaulting to 'unresponsive'")

            # Find and click the radio button
            try:
                radio = self.driver_service.driver.find_element(
                    By.CSS_SELECTOR, f'input[type="radio"][value="{radio_value}"]'
                )
                self.driver_service.safe_click(radio)
                logger.info(f"Selected radio button: {radio_value}")
                self.wis.human_delay(1, 2)
            except:
                # Try clicking by label
                try:
                    label = self.driver_service.driver.find_element(
                        By.XPATH, f"//input[@value='{radio_value}']/following-sibling::label | //label[input[@value='{radio_value}']]"
                    )
                    self.driver_service.safe_click(label)
                    logger.info(f"Clicked label for radio: {radio_value}")
                    self.wis.human_delay(1, 2)
                except Exception as e:
                    logger.error(f"Could not select radio button {radio_value}: {e}")
                    return False

            # If reason is "other", fill in the explanation
            if radio_value == 'other' and reason_detail:
                try:
                    textarea = self.driver_service.driver.find_element(By.CSS_SELECTOR, 'textarea')
                    textarea.clear()
                    self.wis.simulated_typing(textarea, reason_detail)
                    self.wis.human_delay(0.5, 1)
                except:
                    pass

            # Click "Archive Inactive Referral" button
            try:
                archive_btn = self.driver_service.driver.find_element(
                    By.XPATH, "//button[contains(text(), 'Archive Inactive Referral')]"
                )
                self.driver_service.safe_click(archive_btn)
                logger.info("Clicked 'Archive Inactive Referral' button")
                self.wis.human_delay(2, 3)

                # Verify success
                current_url = self.driver_service.get_current_url()
                if '/status_updates/new' not in current_url:
                    logger.info("Lost status update successful!")
                    return True
            except Exception as e:
                logger.error(f"Could not click Archive button: {e}")
                return False

            return False

        except Exception as e:
            logger.error(f"Error selecting lost status: {e}")
            return False

    def _parse_status(self, status: Any) -> Tuple[str, Optional[str]]:
        """Parse status into primary and sub-status"""
        sub_status = None

        if isinstance(status, dict):
            primary = status.get('status', str(status))
            sub_status = status.get('sub_option') or status.get('sub_status')
        elif isinstance(status, (list, tuple)):
            primary = status[0] if status else ""
            sub_status = status[1] if len(status) > 1 else None
        elif isinstance(status, str) and "::" in status:
            parts = status.split("::", 1)
            primary = parts[0].strip()
            sub_status = parts[1].strip() if len(parts) > 1 else None
        else:
            primary = str(status) if status else ""

        return primary.strip() if primary else "", sub_status.strip() if sub_status else None

    def _select_status_from_dropdown(self, select_element: Any, status_text: str) -> bool:
        """Select a status from a <select> dropdown"""
        try:
            from selenium.webdriver.support.ui import Select
            select = Select(select_element)

            # Try exact match first
            try:
                select.select_by_visible_text(status_text)
                logger.info(f"Selected status by visible text: {status_text}")
                return True
            except:
                pass

            # Try partial match
            status_lower = status_text.lower()
            for option in select.options:
                if status_lower in option.text.lower():
                    select.select_by_visible_text(option.text)
                    logger.info(f"Selected status by partial match: {option.text}")
                    return True

            # Try by value
            try:
                select.select_by_value(status_text)
                logger.info(f"Selected status by value: {status_text}")
                return True
            except:
                pass

            logger.warning(f"Could not find status option: {status_text}")
            return False

        except Exception as e:
            logger.error(f"Error selecting from dropdown: {e}")
            return False

    def _select_status_from_options(self, primary_status: str, sub_status: Optional[str] = None) -> bool:
        """Select a status from a dropdown menu (non-select)"""
        try:
            self.wis.human_delay(0.5, 1)

            # Find options in dropdown
            option_selectors = [
                "li[role='option']",
                "div[role='option']",
                ".dropdown-item",
                ".dropdown-menu li",
                ".dropdown-menu a",
                "[class*='option']",
                "[class*='menu-item']",
            ]

            options = []
            for selector in option_selectors:
                try:
                    found = self.driver_service.find_elements(By.CSS_SELECTOR, selector)
                    if found:
                        options = found
                        break
                except:
                    continue

            if not options:
                # Try XPath
                options = self.driver_service.find_elements(
                    By.XPATH,
                    "//*[contains(@class, 'dropdown') or contains(@class, 'menu')]//*[self::li or self::a or self::div]"
                )

            primary_lower = primary_status.lower()

            for option in options:
                try:
                    option_text = option.text.strip().lower()
                    if primary_lower in option_text or option_text in primary_lower:
                        self.driver_service.safe_click(option)
                        logger.info(f"Selected status option: {option.text}")
                        self.wis.human_delay(1, 2)

                        # Handle sub-status if needed
                        if sub_status:
                            return self._select_sub_status(sub_status)

                        return True
                except:
                    continue

            logger.warning(f"Could not find status option: {primary_status}")
            return False

        except Exception as e:
            logger.error(f"Error selecting status option: {e}")
            return False

    def _select_sub_status(self, sub_status: str) -> bool:
        """Select a sub-status option if applicable"""
        try:
            self.wis.human_delay(0.5, 1)
            sub_lower = sub_status.lower()

            # Look for radio buttons or secondary options
            sub_selectors = [
                "input[type='radio']",
                ".sub-option",
                "[class*='sub-status']",
                ".radio-group label",
            ]

            for selector in sub_selectors:
                try:
                    elements = self.driver_service.find_elements(By.CSS_SELECTOR, selector)
                    for el in elements:
                        el_text = el.text.lower() if el.text else ""
                        label = el.get_attribute("aria-label") or ""

                        if sub_lower in el_text or sub_lower in label.lower():
                            self.driver_service.safe_click(el)
                            logger.info(f"Selected sub-status: {sub_status}")
                            return True
                except:
                    continue

            logger.warning(f"Could not find sub-status: {sub_status}")
            return True  # Don't fail the whole update for missing sub-status

        except Exception as e:
            logger.error(f"Error selecting sub-status: {e}")
            return True

    def _click_save_button(self) -> bool:
        """Find and click the save/update button"""
        try:
            save_selectors = [
                'button[type="submit"]',
                'button:contains("Save")',
                'button:contains("Update")',
                'button:contains("Submit")',
                '.btn-save',
                '.save-button',
                '.btn-primary',
                'input[type="submit"]',
            ]

            for selector in save_selectors:
                try:
                    save_btn = self.driver_service.find_element(By.CSS_SELECTOR, selector)
                    if save_btn:
                        self.driver_service.safe_click(save_btn)
                        logger.info(f"Clicked save button: {selector}")
                        self.wis.human_delay(2, 3)
                        return True
                except:
                    continue

            # Try XPath
            xpath_selectors = [
                "//button[contains(text(), 'Save')]",
                "//button[contains(text(), 'Update')]",
                "//button[contains(text(), 'Submit')]",
                "//button[@type='submit']",
            ]

            for xpath in xpath_selectors:
                try:
                    save_btn = self.driver_service.find_element(By.XPATH, xpath)
                    if save_btn:
                        self.driver_service.safe_click(save_btn)
                        logger.info(f"Clicked save button via XPath")
                        self.wis.human_delay(2, 3)
                        return True
                except:
                    continue

            logger.warning("Could not find save button")
            return False

        except Exception as e:
            logger.error(f"Error clicking save button: {e}")
            return False

    def find_and_update_lead(self, lead_name: str, status: Any, custom_comment: str = None) -> bool:
        """
        Find a lead by name and update their status.

        Args:
            lead_name: Name of the lead to find
            status: The status to set
            custom_comment: Optional custom comment (from @update notes) to use
        """
        try:
            # Navigate to referrals page first
            if not self._verify_referrals_page():
                self.navigate_to_referrals()

            # Find and click the lead
            if not self.find_and_click_customer_by_name(lead_name):
                return False

            # Update the status
            if not self.update_customers(status, custom_comment=custom_comment):
                return False

            # Try to save
            self._click_save_button()

            logger.info(f"Successfully updated lead {lead_name} to status: {status}")
            return True

        except Exception as e:
            logger.error(f"Error finding/updating lead: {e}")
            return False

    def _take_screenshot(self, name: str) -> None:
        """Take a screenshot for debugging"""
        try:
            filename = f"agentpronto_{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            self.driver_service.driver.save_screenshot(filename)
            logger.info(f"Screenshot saved: {filename}")
        except Exception as e:
            logger.warning(f"Failed to save screenshot: {e}")

    def update_multiple_leads(
        self,
        leads_data: List[Tuple[Lead, Any]],
        comments: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Update multiple leads in a single browser session (bulk sync).

        Args:
            leads_data: List of (Lead, status) tuples
            comments: Optional dict mapping lead.id -> comment string (from @update notes)

        Returns:
            Dict with sync results
        """
        if comments is None:
            comments = {}

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
            if not self.login_once():
                logger.error("Login failed - cannot process leads")
                for lead, _ in leads_data:
                    results["failed"] += 1
                    results["details"].append({
                        "name": f"{lead.first_name} {lead.last_name}",
                        "status": "failed",
                        "error": "Login failed"
                    })
                return results

            # Navigate to referrals page
            self.navigate_to_referrals()

            # Process each lead
            for i, (lead, status) in enumerate(leads_data):
                lead_name = f"{lead.first_name} {lead.last_name}"
                logger.info(f"[{i+1}/{len(leads_data)}] Processing: {lead_name}")

                try:
                    # Check if lead was recently synced
                    if self._should_skip_lead(lead):
                        results["skipped"] += 1
                        results["details"].append({
                            "name": lead_name,
                            "status": "skipped",
                            "reason": "Recently synced"
                        })
                        continue

                    # Navigate back to referrals between leads
                    if i > 0:
                        self.navigate_to_referrals()
                        self.wis.human_delay(1, 2)

                    # Update the active lead context
                    self.update_active_lead(lead, status)

                    # Get comment from @update notes if available
                    lead_comment = comments.get(lead.id)
                    if lead_comment:
                        logger.info(f"Using @update comment for {lead_name}: {lead_comment[:50]}...")

                    # Find and update lead
                    success = self.find_and_update_lead(lead_name, status, custom_comment=lead_comment)

                    if success:
                        results["successful"] += 1
                        results["details"].append({
                            "name": lead_name,
                            "status": "success"
                        })

                        # Update lead metadata
                        self._mark_lead_synced(lead)
                    else:
                        results["failed"] += 1
                        results["details"].append({
                            "name": lead_name,
                            "status": "failed",
                            "error": "Update failed"
                        })

                except Exception as e:
                    results["failed"] += 1
                    results["details"].append({
                        "name": lead_name,
                        "status": "failed",
                        "error": str(e)
                    })
                    logger.error(f"Error processing lead {lead_name}: {e}")

            logger.info(f"Bulk sync complete: {results['successful']} success, {results['failed']} failed, {results['skipped']} skipped")
            return results

        except Exception as e:
            logger.error(f"Bulk sync error: {e}")
            return results

        finally:
            if self.owns_driver:
                self.logout()

    def _should_skip_lead(self, lead: Lead) -> bool:
        """Check if lead was recently synced and should be skipped"""
        if self.force_sync:
            return False

        try:
            if not lead.metadata:
                return False

            last_synced_str = lead.metadata.get("agentpronto_last_updated")
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

            lead.metadata["agentpronto_last_updated"] = datetime.now(timezone.utc).isoformat()
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
