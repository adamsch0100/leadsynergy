from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement
from app.referral_scrapers.utils.web_interaction_simulator import (
    WebInteractionSimulator as wis,
)
from selenium.common.exceptions import TimeoutException
from datetime import datetime, timedelta, timezone
import os
import time
import random
import logging
from typing import List, Optional, Dict, Any, Tuple

from app.utils.constants import Credentials
from app.utils.email_2fa_helper import Email2FAHelper, get_redfin_2fa_code
from app.referral_scrapers.utils.driver_service import DriverService
from app.models.lead import Lead
from app.service.lead_service import LeadService, LeadServiceSingleton
from app.referral_scrapers.base_referral_service import BaseReferralService

CREDS = Credentials()
logger = logging.getLogger(__name__)


class RedfinService(BaseReferralService):
    def __init__(
        self,
        lead: Lead = None,
        status: str = None,
        organization_id: str = None,
        user_id: str = None,
        min_sync_interval_hours: int = 168
    ) -> None:
        # For bulk operations, lead can be None initially
        if lead:
            super().__init__(lead, organization_id=organization_id)
        else:
            self.organization_id = organization_id
            self.logger = logging.getLogger(__name__)
            self.email = None
            self.password = None

        self.base_url = "https://www.redfin.com/tools/new/login"
        self.dashboard_url = "https://www.redfin.com/tools/partnerCustomers"
        self.search_lead_url = (
            "https://www.redfin.com/tools/search?q={first_name}%20{last_name}"
        )
        self.status = status
        self.user_id = user_id
        self.min_sync_interval_hours = min_sync_interval_hours

        # Credentials are loaded by BaseReferralService._setup_credentials() from database
        # Fallback to environment variables if not in database
        if not self.email:
            self.email = CREDS.REDFIN_EMAIL
        if not self.password:
            self.password = CREDS.REDFIN_PASSWORD

        # 2FA email credentials (for automatic code retrieval)
        self.twofa_email = None
        self.twofa_app_password = None
        self._load_2fa_credentials()

        self.lead_service = LeadServiceSingleton.get_instance()
        self.lead = lead
        self.wis = wis()
        self.is_logged_in = False

    def _load_2fa_credentials(self):
        """Load 2FA email credentials from lead source settings or environment"""
        try:
            from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
            settings_service = LeadSourceSettingsSingleton.get_instance()

            # Try to get user-specific settings first
            if self.user_id:
                sources = settings_service.get_all(
                    filters={"source_name": "Redfin"},
                    user_id=self.user_id
                )
                source_settings = sources[0] if sources else None
            else:
                source_settings = settings_service.get_by_source_name("Redfin")

            if source_settings:
                metadata = source_settings.metadata if hasattr(source_settings, 'metadata') else source_settings.get('metadata')
                if isinstance(metadata, str):
                    import json
                    metadata = json.loads(metadata)

                if metadata:
                    two_fa_config = metadata.get('two_factor_auth', {})
                    if two_fa_config.get('enabled', False):
                        self.twofa_email = two_fa_config.get('email')
                        self.twofa_app_password = two_fa_config.get('app_password')
                        logger.info("Loaded 2FA credentials from database")

        except Exception as e:
            logger.warning(f"Could not load 2FA credentials from database: {e}")

        # Fallback to environment variables
        if not self.twofa_email:
            self.twofa_email = CREDS.GMAIL_EMAIL
        if not self.twofa_app_password:
            self.twofa_app_password = CREDS.GMAIL_APP_PASSWORD

    def redfin_run(self):
        # This is where the main process happens
        try:
            if self.login2():
                full_name = f"{self.lead.first_name} {self.lead.last_name}"
                # Get the status from lead metadata or from the lead source settings

                if self.status:
                    return self.find_and_click_customer_by_name2(full_name, self.status)
                else:
                    self.logger.warning("No status provided for update")
                    return False
            else:
                self.logger.error("Login failed")
                return False
        except Exception as e:
            self.logger.error("Login failed")
            return False

        finally:
            self.close()

    def _get_status_from_lead(self) -> Lead:
        return self.lead_service.get_by_fub_person_id(self.lead.fub_id)

    @classmethod
    def get_platform_name(cls) -> str:
        return "Redfin"

    def return_platform_name(self) -> str:
        return self.get_platform_name()

    def login(self) -> bool:
        try:
            if not self.driver_service.initialize_driver():
                return False

            if not self.driver_service.get_page(self.base_url):
                return False
            self.wis.human_delay(3, 5)

            # Find login elements
            email_field = self.driver_service.find_element(
                By.CSS_SELECTOR, 'input[name="login_email"]'
            )
            password_field = self.driver_service.find_element(
                By.CSS_SELECTOR, 'input[name="login_password"]'
            )
            login_button = self.driver_service.find_element(
                By.CSS_SELECTOR, 'button[data-rf-test-name="login_submit"]'
            )

            if not all([email_field, password_field, login_button]):
                return False

            self.wis.simulated_typing(email_field, self.email)
            self.wis.human_delay(1, 2)
            self.wis.simulated_typing(password_field, self.password)
            self.wis.human_delay(3, 5)
            login_button.click()
            self.wis.human_delay(3, 8)

            # Check for 2FA prompt
            if self._check_and_handle_2fa():
                logger.info("2FA handled successfully")

            # Verify login success by URL change first
            try:
                self.driver_service.wait.until(EC.url_contains("tools"))
            except Exception:
                pass

            current_url = self.driver_service.get_current_url()
            if current_url and ("partnerCustomers" in current_url or "tools" in current_url):
                self.is_logged_in = True
                self.logger.info("Redfin dashboard loaded successfully")
                return True

            # Fallback: look for edit buttons
            edit_buttons = self.driver_service.find_elements(
                By.CSS_SELECTOR, ".edit-status-button"
            )
            if edit_buttons:
                self.is_logged_in = True
                self.logger.info(f"Found {len(edit_buttons)} customers to process.")
                self.wis.human_delay(3, 5)
                return True

            return False

        except Exception as e:
            self.logger.error(f"Login failed: {e}")
            self.is_logged_in = False
            return False

    def _get_cookie_path(self):
        """Get path for storing session cookies."""
        import tempfile
        cookie_dir = os.path.join(tempfile.gettempdir(), "leadsynergy_cookies")
        os.makedirs(cookie_dir, exist_ok=True)
        return os.path.join(cookie_dir, "redfin_cookies.json")

    def _save_cookies(self):
        """Save browser cookies to file AND database for cross-machine session reuse."""
        try:
            import json
            cookies = self.driver_service.driver.get_cookies()
            # Save to local file
            cookie_path = self._get_cookie_path()
            with open(cookie_path, 'w') as f:
                json.dump(cookies, f)
            print(f"[Cookies] Saved {len(cookies)} cookies to {cookie_path}")

            # Also save to database for Railway to use
            self._save_cookies_to_db(cookies)
        except Exception as e:
            print(f"[Cookies] Failed to save cookies: {e}")

    def _save_cookies_to_db(self, cookies):
        """Save cookies to lead_source_settings metadata for cross-machine access."""
        try:
            import json
            from datetime import datetime, timezone
            from supabase import create_client
            sb = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
            result = sb.table('lead_source_settings').select('metadata').eq('source_name', 'Redfin').execute()
            if result.data:
                metadata = result.data[0].get('metadata') or {}
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)
                metadata['session_cookies'] = cookies
                metadata['cookies_saved_at'] = datetime.now(timezone.utc).isoformat()
                sb.table('lead_source_settings').update({'metadata': json.dumps(metadata)}).eq('source_name', 'Redfin').execute()
                print(f"[Cookies] Saved {len(cookies)} cookies to database")
        except Exception as e:
            print(f"[Cookies] Failed to save cookies to DB: {e}")

    def _load_cookies_from_db(self):
        """Load cookies from database (for Railway where local file doesn't exist)."""
        try:
            import json
            from datetime import datetime, timezone
            from supabase import create_client
            sb = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
            result = sb.table('lead_source_settings').select('metadata').eq('source_name', 'Redfin').execute()
            if result.data:
                metadata = result.data[0].get('metadata') or {}
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)
                cookies = metadata.get('session_cookies')
                saved_at = metadata.get('cookies_saved_at')
                if cookies and saved_at:
                    saved_time = datetime.fromisoformat(saved_at.replace('Z', '+00:00'))
                    age_hours = (datetime.now(timezone.utc) - saved_time).total_seconds() / 3600
                    if age_hours < 24:
                        print(f"[Cookies] Loaded {len(cookies)} cookies from database ({age_hours:.1f}h old)")
                        return cookies
                    else:
                        print(f"[Cookies] Database cookies expired ({age_hours:.1f}h old)")
                        return None
            return None
        except Exception as e:
            print(f"[Cookies] Failed to load cookies from DB: {e}")
            return None

    def _try_cookie_login(self) -> bool:
        """Try to login using saved cookies from a previous session (file or database)."""
        try:
            import json
            cookies = None

            # Try local file first
            cookie_path = self._get_cookie_path()
            if os.path.exists(cookie_path):
                file_age = time.time() - os.path.getmtime(cookie_path)
                if file_age <= 86400:  # 24 hours
                    with open(cookie_path, 'r') as f:
                        cookies = json.load(f)
                    if cookies:
                        print(f"[Cookies] Loading {len(cookies)} cookies from file ({file_age/60:.0f} min old)")
                else:
                    print(f"[Cookies] Local cookies expired ({file_age/3600:.1f} hours old)")
                    os.remove(cookie_path)

            # Fall back to database cookies (for Railway)
            if not cookies:
                cookies = self._load_cookies_from_db()

            if not cookies:
                print("[Cookies] No saved cookies found")
                return False

            # Navigate to Redfin domain first (needed to set cookies)
            self.driver_service.get_page("https://www.redfin.com")
            self.wis.human_delay(1, 2)

            # Add each cookie
            for cookie in cookies:
                try:
                    # Remove problematic fields
                    for field in ['sameSite', 'httpOnly', 'storeId']:
                        cookie.pop(field, None)
                    self.driver_service.driver.add_cookie(cookie)
                except Exception:
                    pass

            # Navigate to dashboard to verify
            self.driver_service.get_page(self.dashboard_url)
            self.wis.human_delay(3, 5)

            current_url = self.driver_service.get_current_url()
            if current_url and "partnerCustomers" in current_url:
                edit_buttons = self.driver_service.find_elements(
                    By.CSS_SELECTOR, ".edit-status-button"
                )
                if edit_buttons:
                    self.is_logged_in = True
                    print(f"[Cookies] SUCCESS - Session restored! Found {len(edit_buttons)} customers")
                    return True

            print("[Cookies] Saved cookies didn't work, proceeding with fresh login")
            return False

        except Exception as e:
            print(f"[Cookies] Error loading cookies: {e}")
            return False

    def login2(self) -> bool:
        if not self.driver_service.initialize_driver():
            return False

        try:
            # First, try using saved cookies from a previous successful login
            if self._try_cookie_login():
                return True

            print("Navigating to Redfin login page...")
            self.driver_service.get_page(self.base_url)
            self.wis.human_delay(2, 5)

            # Check login method from metadata (default to Google for Redfin)
            login_method = self._get_login_method()
            print(f"[Login] Using login method: {login_method}")

            if login_method == "google":
                # Try Google OAuth login
                google_login_success = self._try_google_login()
                if google_login_success:
                    # Save cookies for future sessions to skip 2FA
                    self._save_cookies()
                    return True
                print("[Login] Google login failed, trying direct login as fallback...")
                # Navigate back to Redfin login page - browser may be stuck on Google OAuth page
                print("[Login] Navigating back to Redfin login page for direct login...")
                self.driver_service.get_page(self.base_url)
                self.wis.human_delay(2, 5)

            # Try direct email/password login
            email_field = self.driver_service.find_element(
                By.CSS_SELECTOR, 'input[name="login_email"]'
            )
            password_field = self.driver_service.find_element(
                By.CSS_SELECTOR, 'input[name="login_password"]'
            )
            login_button = self.driver_service.find_element(
                By.CSS_SELECTOR, 'button[data-rf-test-name="login_submit"]'
            )

            if not all([email_field, password_field, login_button]):
                print("Direct login form not found")
                return False

            self.wis.simulated_typing(email_field, self.email)
            self.wis.human_delay(1, 2)
            self.wis.simulated_typing(password_field, self.password)
            self.wis.human_delay(3, 5)
            login_button.click()
            self.wis.human_delay(3, 8)

            # Check for 2FA prompt
            if self._check_and_handle_2fa():
                print("2FA handled successfully")

            # Verify login success
            result = self._verify_login_success()
            if result:
                self._save_cookies()
            return result

        except Exception as e:
            print(f"Login failed: {e}")
            self.is_logged_in = False
            return False

    def _get_login_method(self) -> str:
        """Get the login method from lead source settings metadata.
        Default is 'google' for Redfin.
        """
        try:
            from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
            settings_service = LeadSourceSettingsSingleton.get_instance()

            if self.user_id:
                sources = settings_service.get_all(
                    filters={"source_name": "Redfin"},
                    user_id=self.user_id
                )
                source_settings = sources[0] if sources else None
            else:
                source_settings = settings_service.get_by_source_name("Redfin")

            if source_settings:
                metadata = source_settings.metadata if hasattr(source_settings, 'metadata') else source_settings.get('metadata')
                if isinstance(metadata, str):
                    import json
                    metadata = json.loads(metadata)
                if metadata:
                    return metadata.get('login_method', 'google')
        except Exception as e:
            logger.warning(f"Could not get login method from settings: {e}")

        return "google"

    def _try_google_login(self) -> bool:
        """Handle Google OAuth login for Redfin"""
        try:
            print("[Google Login] Looking for Google sign-in button...")

            # Find "Sign in with Google" button
            # Verified selectors as of Feb 2026 from actual DOM inspection
            google_button_selectors = [
                'button[data-rf-test-id="googleSignIn"]',  # Primary - Redfin's test ID
                'button.google-btn',                        # Class-based fallback
                '.GoogleLogin .loginButton button',         # Container-based fallback
                '//span[contains(text(), "Sign in with Google")]//ancestor::button',  # XPath text-based
            ]

            google_button = None
            for selector in google_button_selectors:
                try:
                    if selector.startswith('//'):
                        google_button = self.driver_service.find_element(By.XPATH, selector)
                    else:
                        google_button = self.driver_service.find_element(By.CSS_SELECTOR, selector)
                    if google_button:
                        print(f"[Google Login] Found Google button: {selector}")
                        break
                except:
                    continue

            if not google_button:
                print("[Google Login] Google sign-in button not found")
                return False

            # Click Google sign-in button
            self.driver_service.safe_click(google_button)
            print("[Google Login] Clicked Google sign-in button")
            self.wis.human_delay(3, 5)

            # Handle Google OAuth popup/redirect
            # Google might open a popup or redirect to accounts.google.com
            return self._handle_google_oauth()

        except Exception as e:
            print(f"[Google Login] Error: {e}")
            return False

    def _handle_google_oauth(self) -> bool:
        """Handle the Google OAuth flow"""
        try:
            # Wait for popup or redirect to Google
            print("[Google OAuth] Waiting for Google sign-in page...")
            self.wis.human_delay(3, 5)
            current_url = self.driver_service.get_current_url()
            print(f"[Google OAuth] Current URL: {current_url}")

            # Handle popup window if opened
            original_window = self.driver_service.driver.current_window_handle
            all_windows = self.driver_service.driver.window_handles
            print(f"[Google OAuth] Number of windows: {len(all_windows)}")

            popup_window = None
            if len(all_windows) > 1:
                # Switch to popup
                for window in all_windows:
                    if window != original_window:
                        self.driver_service.driver.switch_to.window(window)
                        popup_window = window
                        print("[Google OAuth] Switched to popup window")
                        self.wis.human_delay(2, 3)
                        break

            current_url = self.driver_service.get_current_url()
            print(f"[Google OAuth] After popup check, URL: {current_url}")

            # Wait longer if not on Google yet
            if "google.com" not in current_url:
                print("[Google OAuth] Not on Google yet, waiting...")
                self.wis.human_delay(5, 8)
                current_url = self.driver_service.get_current_url()
                print(f"[Google OAuth] After wait, URL: {current_url}")

            # If we're on Google's login page
            if "accounts.google.com" in current_url or "google.com/signin" in current_url:
                print("[Google OAuth] On Google sign-in page")

                # Enter email
                email_selectors = [
                    'input[type="email"]',
                    'input[name="identifier"]',
                    '#identifierId',
                ]

                email_field = None
                for selector in email_selectors:
                    try:
                        email_field = self.driver_service.find_element(By.CSS_SELECTOR, selector)
                        if email_field:
                            break
                    except:
                        continue

                if email_field:
                    print(f"[Google OAuth] Entering email: {self.email}")
                    self.wis.simulated_typing(email_field, self.email)
                    self.wis.human_delay(1, 2)

                    # Click Next
                    next_button = None
                    next_selectors = [
                        '#identifierNext',
                        'button[type="submit"]',
                        '//button[contains(text(), "Next")]',
                        '//span[contains(text(), "Next")]//ancestor::button',
                    ]

                    for selector in next_selectors:
                        try:
                            if selector.startswith('//'):
                                next_button = self.driver_service.find_element(By.XPATH, selector)
                            else:
                                next_button = self.driver_service.find_element(By.CSS_SELECTOR, selector)
                            if next_button:
                                break
                        except:
                            continue

                    if next_button:
                        self.driver_service.safe_click(next_button)
                        print("[Google OAuth] Clicked Next after email")
                        self.wis.human_delay(5, 8)  # Longer wait for Google's password page animation

                # Debug: what page are we on after email Next?
                try:
                    current_url = self.driver_service.get_current_url()
                    page_text = self.driver_service.driver.find_element(By.TAG_NAME, "body").text[:300]
                    print(f"[Google OAuth] After email Next - URL: {current_url[:100]}")
                    print(f"[Google OAuth] Page text: {page_text[:200]}")
                except Exception as dbg_e:
                    print(f"[Google OAuth] Debug error: {dbg_e}")

                # Enter password - wait for field to be interactable (Google animates this)
                password_selectors = [
                    'input[type="password"]',
                    'input[name="password"]',
                    'input[name="Passwd"]',
                ]

                password_field = None
                for attempt in range(3):
                    for selector in password_selectors:
                        try:
                            from selenium.webdriver.support.ui import WebDriverWait
                            from selenium.webdriver.support import expected_conditions as EC
                            password_field = WebDriverWait(self.driver_service.driver, 10).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                            if password_field:
                                break
                        except:
                            continue
                    if password_field:
                        break
                    # Debug: dump all inputs on failed attempt
                    try:
                        all_inputs = self.driver_service.driver.find_elements(By.TAG_NAME, "input")
                        input_info = [(inp.get_attribute("type"), inp.get_attribute("name"), inp.is_displayed()) for inp in all_inputs]
                        print(f"[Google OAuth] Password field not interactable (attempt {attempt+1}/3). Inputs on page: {input_info}")
                    except:
                        print(f"[Google OAuth] Password field not interactable yet, retrying ({attempt+1}/3)...")
                    self.wis.human_delay(3, 5)

                if password_field:
                    print("[Google OAuth] Entering password")
                    password_field.click()
                    self.wis.human_delay(0.5, 1)
                    self.wis.simulated_typing(password_field, self.password)
                    self.wis.human_delay(1, 2)

                    # Click Next/Sign in
                    signin_button = None
                    signin_selectors = [
                        '#passwordNext',
                        'button[type="submit"]',
                        '//button[contains(text(), "Next")]',
                        '//span[contains(text(), "Next")]//ancestor::button',
                    ]

                    for selector in signin_selectors:
                        try:
                            if selector.startswith('//'):
                                signin_button = self.driver_service.find_element(By.XPATH, selector)
                            else:
                                signin_button = self.driver_service.find_element(By.CSS_SELECTOR, selector)
                            if signin_button:
                                break
                        except:
                            continue

                    if signin_button:
                        self.driver_service.safe_click(signin_button)
                        print("[Google OAuth] Clicked Sign in")
                        self.wis.human_delay(5, 8)

                if not password_field:
                    print("[Google OAuth] ERROR: Could not find password field after all retries")
                    # Take screenshot for debugging
                    try:
                        import tempfile
                        ss_path = os.path.join(tempfile.gettempdir(), "redfin_google_no_password.png")
                        self.driver_service.driver.save_screenshot(ss_path)
                        print(f"[Google OAuth] Screenshot saved: {ss_path}")
                    except:
                        pass
                    return False

                # Check for Google 2FA
                if self._check_and_handle_google_2fa():
                    print("[Google OAuth] Google 2FA handled")

            # Wait for popup to close (means OAuth callback completed)
            if popup_window:
                print("[Google OAuth] Waiting for popup to close (OAuth callback)...")
                max_popup_wait = 30
                popup_elapsed = 0
                while popup_elapsed < max_popup_wait:
                    try:
                        current_handles = self.driver_service.driver.window_handles
                        if popup_window not in current_handles:
                            print(f"[Google OAuth] Popup closed after {popup_elapsed}s")
                            break
                        # Check if we're already on Redfin in the popup (OAuth callback redirect)
                        try:
                            popup_url = self.driver_service.get_current_url()
                            if "redfin.com" in popup_url:
                                print(f"[Google OAuth] Popup redirected to Redfin: {popup_url[:80]}")
                                break
                        except:
                            pass
                    except Exception:
                        print(f"[Google OAuth] Window handle check failed - popup likely closed")
                        break
                    time.sleep(2)
                    popup_elapsed += 2

            # Switch back to main window
            try:
                current_handles = self.driver_service.driver.window_handles
                if original_window in current_handles:
                    self.driver_service.driver.switch_to.window(original_window)
                    print("[Google OAuth] Switched back to main Redfin window")
                elif current_handles:
                    self.driver_service.driver.switch_to.window(current_handles[0])
                    print("[Google OAuth] Switched to remaining window")
                self.wis.human_delay(5, 8)  # Longer wait for Redfin to process OAuth token
            except Exception as e:
                print(f"[Google OAuth] Window switch note: {e}")

            # Verify we're logged into Redfin
            return self._verify_login_success()

        except Exception as e:
            print(f"[Google OAuth] Error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _check_and_handle_google_2fa(self) -> bool:
        """Handle Google's 2FA if required.

        This account uses Google Prompt (phone notification) as the primary 2FA method.
        The flow is:
        1. Detect 2FA is required
        2. Wait for user to approve on their phone (Google sends a notification)
        3. The page auto-advances after approval
        """
        try:
            self.wis.human_delay(2, 3)
            page_source = self.driver_service.driver.page_source
            if not page_source:
                # page_source is None - popup likely closed (OAuth completed instantly)
                print("[Google 2FA] Page source unavailable - popup may have auto-closed (OAuth complete)")
                return True
            page_source = page_source.lower()

            # Check for 2FA indicators
            twofa_indicators = [
                "2-step verification",
                "verify it's you",
                "verification code",
                "enter the code",
                "check your phone",
                "check your galaxy",
                "check your iphone",
                "tap yes",
                "sent a notification",
            ]

            if not any(indicator in page_source for indicator in twofa_indicators):
                return True  # No 2FA needed

            print("[Google 2FA] Google 2FA detected - phone prompt verification")
            print("[Google 2FA] Waiting for approval on phone...")
            print("[Google 2FA] Please tap 'Yes' on the Google prompt on your phone")

            # Wait for the 2FA to be approved (poll for page change)
            # Google Prompt: user taps Yes on phone, page auto-redirects
            # The popup may also close after approval (Google OAuth callback)
            max_wait_seconds = 120  # 2 minutes to approve on phone
            poll_interval = 3
            elapsed = 0

            from urllib.parse import urlparse

            while elapsed < max_wait_seconds:
                time.sleep(poll_interval)
                elapsed += poll_interval

                try:
                    current_url = self.driver_service.get_current_url()
                except Exception:
                    # Window closed - could mean approval or failure
                    # Only trust if enough time passed for user to actually tap
                    if elapsed >= 10:
                        print(f"[Google 2FA] Window closed after {elapsed}s - checking main window...")
                        return True
                    print(f"[Google 2FA] Window closed too quickly ({elapsed}s) - likely auth failure")
                    return False

                # Parse URL properly - NEVER use string containment on full URLs
                # (query params contain redirect_uri with redfin.com and consent paths)
                parsed = urlparse(current_url)
                url_host = parsed.netloc.lower()
                url_path = parsed.path.lower()

                # Google consent page = definite success (user approved 2FA, now authorizing app)
                is_consent_page = ("google.com" in url_host and
                                   ("/consent" in url_path or "/oauth/consent" in url_path))
                if is_consent_page:
                    print(f"[Google 2FA] On Google consent page (path: {url_path}). 2FA approved! ({elapsed}s)")
                    # Click Allow/Continue on consent page
                    if not self._click_google_consent_button():
                        print("[Google 2FA] Could not click consent button - waiting for auto-redirect...")
                        # Wait up to 15s for popup to close or redirect
                        for _ in range(5):
                            self.wis.human_delay(2, 3)
                            try:
                                self.driver_service.get_current_url()
                            except Exception:
                                print("[Google 2FA] Popup closed after consent")
                                break
                    return True

                # Redirected to Redfin = OAuth callback completed
                is_on_redfin = "redfin.com" in url_host
                if is_on_redfin and elapsed >= 10:
                    print(f"[Google 2FA] Redirected to Redfin! ({elapsed}s) URL: {current_url[:80]}")
                    return True

                # If redirected to redfin.com very quickly (< 10s), 2FA was skipped/failed
                if is_on_redfin and elapsed < 10:
                    print(f"[Google 2FA] Quick redirect to Redfin ({elapsed}s) - 2FA likely failed/skipped")
                    return False

                # Check if 2FA text is gone (page moved to different state)
                try:
                    page_source = self.driver_service.driver.page_source.lower()
                    still_on_2fa = any(ind in page_source for ind in twofa_indicators)
                    if not still_on_2fa and elapsed >= 10:
                        print(f"[Google 2FA] 2FA page cleared after {elapsed}s!")
                        return True
                except Exception:
                    if elapsed >= 10:
                        print(f"[Google 2FA] Page changed after {elapsed}s - checking...")
                        return True
                    return False

                if elapsed % 10 == 0:
                    print(f"[Google 2FA] Still waiting... host={url_host} path={url_path} ({elapsed}s / {max_wait_seconds}s)")

            print(f"[Google 2FA] Timed out after {max_wait_seconds}s waiting for phone approval")
            return False

        except Exception as e:
            print(f"[Google 2FA] Error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _click_google_consent_button(self) -> bool:
        """Click Allow/Continue on Google's OAuth consent page.

        Google's consent UI has changed over the years. Try multiple selectors
        and fall back to JavaScript click if needed.
        """
        try:
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            self.wis.human_delay(2, 3)  # Let page fully render

            # Debug: capture page state
            try:
                consent_url = self.driver_service.get_current_url()
                print(f"[Google Consent] URL: {consent_url[:120]}")
                page_text = self.driver_service.driver.find_element(By.TAG_NAME, "body").text[:500]
                print(f"[Google Consent] Page text: {page_text[:300]}")
            except:
                pass

            # Try multiple consent button selectors (old and new Google UI)
            # These are ONLY for the consent/authorization page, NOT 2FA page
            consent_selectors = [
                # Text-based selectors first (most reliable for consent page)
                ('xpath', '//button[contains(., "Continue")]'),
                ('xpath', '//button[contains(., "Allow")]'),
                ('xpath', '//span[contains(text(), "Continue")]/ancestor::button'),
                ('xpath', '//span[contains(text(), "Allow")]/ancestor::button'),
                # Legacy consent page selectors
                ('css', '#submit_approve_access'),
                ('css', 'button[name="submit_approve_access"]'),
                ('css', '#oauthScopeDialog button'),
                # Modern Google consent UI (v3) - generic, use last
                ('css', 'button[data-idom-class*="nCP5yc"]'), # Material button
            ]

            for selector_type, selector in consent_selectors:
                try:
                    if selector_type == 'xpath':
                        btn = WebDriverWait(self.driver_service.driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                    else:
                        btn = WebDriverWait(self.driver_service.driver, 3).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                    if btn:
                        btn_text = btn.text.strip()
                        print(f"[Google Consent] Found button '{btn_text}' with selector: {selector}")
                        self.driver_service.safe_click(btn)
                        print(f"[Google Consent] Clicked consent button")
                        self.wis.human_delay(3, 5)
                        return True
                except:
                    continue

            # Last resort: find all buttons and click the most likely one
            try:
                all_buttons = self.driver_service.driver.find_elements(By.TAG_NAME, "button")
                btn_info = [(b.text.strip(), b.is_displayed(), b.is_enabled()) for b in all_buttons]
                print(f"[Google Consent] All buttons on page: {btn_info}")

                for btn in all_buttons:
                    text = btn.text.strip().lower()
                    if btn.is_displayed() and btn.is_enabled() and text in ('continue', 'allow', 'accept', 'approve', 'next'):
                        print(f"[Google Consent] Clicking button by text: '{btn.text.strip()}'")
                        self.driver_service.safe_click(btn)
                        self.wis.human_delay(3, 5)
                        return True

                # If no matching text, try JavaScript click on first visible enabled button
                for btn in all_buttons:
                    if btn.is_displayed() and btn.is_enabled():
                        print(f"[Google Consent] JS-clicking first visible button: '{btn.text.strip()}'")
                        self.driver_service.driver.execute_script("arguments[0].click();", btn)
                        self.wis.human_delay(3, 5)
                        return True
            except Exception as e:
                print(f"[Google Consent] Button enumeration error: {e}")

            # Save screenshot for debugging
            try:
                import tempfile
                ss_path = os.path.join(tempfile.gettempdir(), "google_consent_page.png")
                self.driver_service.driver.save_screenshot(ss_path)
                print(f"[Google Consent] Screenshot saved: {ss_path}")
            except:
                pass

            print("[Google Consent] Could not find any consent button")
            return False

        except Exception as e:
            print(f"[Google Consent] Error: {e}")
            return False

    def _verify_login_success(self) -> bool:
        """Verify that login was successful"""
        try:
            self.wis.human_delay(3, 5)

            # Check URL
            current_url = self.driver_service.get_current_url()
            print(f"[Login Verify] Current URL: {current_url}")

            # Check if we're already on the partner dashboard
            if current_url and "partnerCustomers" in current_url:
                edit_buttons = self.driver_service.find_elements(
                    By.CSS_SELECTOR, ".edit-status-button"
                )
                if edit_buttons:
                    self.is_logged_in = True
                    print(f"[Login Verify] SUCCESS - Found {len(edit_buttons)} customers on dashboard")
                    return True

            # Always try to navigate to the partner dashboard after OAuth
            print("[Login Verify] Navigating to partner dashboard...")
            self.driver_service.get_page(self.dashboard_url)
            self.wis.human_delay(5, 8)

            current_url = self.driver_service.get_current_url()
            print(f"[Login Verify] After navigation URL: {current_url}")

            # Check for dashboard elements
            edit_buttons = self.driver_service.find_elements(
                By.CSS_SELECTOR, ".edit-status-button"
            )
            if edit_buttons:
                self.is_logged_in = True
                print(f"[Login Verify] SUCCESS - Found {len(edit_buttons)} customers on dashboard")
                return True

            # Check if we got redirected to login (means OAuth failed)
            if "login" in current_url.lower():
                print("[Login Verify] FAILED - Redirected to login page (OAuth may have failed)")
                return False

            # Check for any content that indicates we're logged in
            page_source = self.driver_service.driver.page_source.lower()
            logged_in_indicators = [
                "partner customer",
                "your referrals",
                "edit status",
                "customer details",
            ]

            if any(indicator in page_source for indicator in logged_in_indicators):
                self.is_logged_in = True
                print("[Login Verify] SUCCESS - Found logged-in content")
                return True

            print("[Login Verify] FAILED - Could not verify login")
            return False

        except Exception as e:
            print(f"[Login Verify] Error: {e}")
            return False

    def _check_and_handle_2fa(self) -> bool:
        """
        Check if 2FA is required and handle it automatically.

        Returns:
            True if 2FA was handled (or not needed), False if 2FA failed
        """
        try:
            # Common 2FA field selectors for Redfin
            twofa_selectors = [
                'input[name="verification_code"]',
                'input[name="code"]',
                'input[name="otp"]',
                'input[type="tel"]',  # Often used for numeric codes
                'input[placeholder*="code"]',
                'input[placeholder*="verification"]',
                '#verification-code',
                '.verification-input',
                'input[autocomplete="one-time-code"]',
            ]

            # Wait briefly for 2FA page to load
            self.wis.human_delay(2, 3)

            # Check if we're on a 2FA page
            twofa_input = None
            for selector in twofa_selectors:
                try:
                    twofa_input = self.driver_service.find_element(By.CSS_SELECTOR, selector)
                    if twofa_input:
                        print(f"[2FA] Found 2FA input field: {selector}")
                        break
                except:
                    continue

            # Also check for 2FA text on page
            page_text = self.driver_service.driver.page_source.lower()
            twofa_indicators = [
                "verification code",
                "enter the code",
                "we sent a code",
                "check your email",
                "two-factor",
                "2fa",
                "verify your identity",
                "security code",
            ]

            has_twofa_text = any(indicator in page_text for indicator in twofa_indicators)

            if not twofa_input and not has_twofa_text:
                # No 2FA required
                return True

            print("[2FA] 2FA verification required - retrieving code from email...")

            # Check if we have 2FA credentials
            if not self.twofa_email or not self.twofa_app_password:
                print("[2FA] ERROR: No 2FA email credentials configured!")
                print("[2FA] Please configure 2FA in lead source settings or environment variables")
                return False

            # Get the 2FA code from email
            helper = Email2FAHelper(
                email_address=self.twofa_email,
                app_password=self.twofa_app_password
            )

            code = helper.get_verification_code(
                sender_contains="redfin",
                max_age_seconds=180,
                max_retries=15,
                retry_delay=2.0,
                code_length=6
            )

            if not code:
                print("[2FA] ERROR: Could not retrieve 2FA code from email")
                return False

            print(f"[2FA] Retrieved code: {code}")

            # Find the input field if we haven't already
            if not twofa_input:
                for selector in twofa_selectors:
                    try:
                        twofa_input = self.driver_service.find_element(By.CSS_SELECTOR, selector)
                        if twofa_input:
                            break
                    except:
                        continue

            if not twofa_input:
                print("[2FA] ERROR: Could not find 2FA input field")
                return False

            # Enter the code
            self.wis.simulated_typing(twofa_input, code)
            self.wis.human_delay(1, 2)

            # Look for submit button
            submit_selectors = [
                'button[type="submit"]',
                'button[data-rf-test-name*="verify"]',
                'button[data-rf-test-name*="submit"]',
                'input[type="submit"]',
                'button:contains("Verify")',
                'button:contains("Submit")',
                'button:contains("Continue")',
            ]

            submit_button = None
            for selector in submit_selectors:
                try:
                    submit_button = self.driver_service.find_element(By.CSS_SELECTOR, selector)
                    if submit_button:
                        break
                except:
                    continue

            # Try XPath as fallback
            if not submit_button:
                xpath_selectors = [
                    "//button[contains(text(), 'Verify')]",
                    "//button[contains(text(), 'Submit')]",
                    "//button[contains(text(), 'Continue')]",
                    "//button[@type='submit']",
                ]
                for xpath in xpath_selectors:
                    try:
                        submit_button = self.driver_service.find_element(By.XPATH, xpath)
                        if submit_button:
                            break
                    except:
                        continue

            if submit_button:
                self.driver_service.safe_click(submit_button)
                print("[2FA] Clicked submit button")
            else:
                # Try pressing Enter
                from selenium.webdriver.common.keys import Keys
                twofa_input.send_keys(Keys.RETURN)
                print("[2FA] Pressed Enter to submit")

            self.wis.human_delay(3, 5)
            print("[2FA] 2FA code submitted successfully")
            return True

        except Exception as e:
            print(f"[2FA] Error handling 2FA: {e}")
            import traceback
            traceback.print_exc()
            return False

    def find_and_click_customer_by_name2(self, target_name: str, status: str) -> bool:
        try:
            print(f"Finding and logging customer: {target_name}")
            # First, ensure we have a stable page by waiting a bit longer
            self.wis.human_delay(3, 5)

            # Use JS to search for the name in the customer table
            search_script = """
            function findCustomer(name) {
                name = name.toLowerCase();
                
                // Look for rows in the customer table
                var rows = document.querySelectorAll('table tr');
                console.log("Found " + rows.length + " rows to search through");
                
                // Track the found element for highlighting
                var foundElement = null;
                
                for (var i = 0; i < rows.length; i++) {
                    var rowText = rows[i].textContent.toLowerCase();
                    
                    // Check if this row contains the name
                    if (rowText.includes(name)) {
                        console.log("Found matching row: " + i);
                        
                        // Highlight the row for visibility
                        rows[i].style.backgroundColor = "yellow";
                        
                        // Scroll it into view
                        rows[i].scrollIntoView({behavior: 'smooth', block: 'center'});
                        
                        foundElement = rows[i];
                        break;
                    }
                }
                
                return foundElement;
            }
            
            return findCustomer(arguments[0]);
            """

            self.logger.info(f"Searching for customer: {target_name}")
            found_element = self.driver_service.driver.execute_script(
                search_script, target_name
            )
            self.wis.human_delay(2, 4)

            if found_element:
                self.logger.info(f"Found Lead: {target_name}")

                # Find the edit button in the found row
                find_edit_button_script = """
                function findEditButton(row) {
                    // Look for the edit button in this row
                    var button = row.querySelector('button.edit-status-button');
                    
                    if (button) {
                        // Highlight the button for visibility
                        button.style.border = '2px solid red';
                        return button;
                    }
                    
                    return null;
                }
                
                return findEditButton(arguments[0]);
                """

                edit_button = self.driver_service.driver.execute_script(
                    find_edit_button_script, found_element
                )

                if edit_button:
                    self.logger.info("Found edit button, clicking it")
                    # Click
                    self.driver_service.safe_click(edit_button)
                    self.wis.human_delay(1, 3)

                    if status:
                        self.update_customers(status)

                    return True
                else:
                    self.logger.error(
                        f"Found customer {target_name} but couldn't locate the edit button"
                    )
                    return False
            else:
                self.logger.error(f"Customer {target_name} not found on page")
                return False

        except Exception as e:
            self.logger.error(f"Error searching for customer {target_name}: {e}")
            return False

    def find_and_click_customer_by_name(self, target_name: str, status: str) -> bool:
        """
        Find a customer by name and click its edit status button.

        Args:
            target_name: The customer name to search for

        Returns:
            bool: True if customer was found and edit button clicked, False otherwise
            :param status:
        """
        try:
            # First, ensure we have a stable page by waiting a bit longer
            self.wis.human_delay(3, 5)

            # Try a direct approach first - get all edit buttons
            edit_buttons = self.driver_service.find_elements(
                By.CSS_SELECTOR, "button.edit-status-button"
            )
            print(f"Found {len(edit_buttons)} edit buttons")

            if not edit_buttons:
                print("No edit buttons found")
                return False

            # Get customer links to match with edit buttons
            customer_links = self.driver_service.find_elements(
                By.CSS_SELECTOR, "a.customer-details-page-link"
            )
            print(f"Found {len(customer_links)} customer links")

            # Simple approach: Print all customer names for debugging
            print("Available customers:")
            for i, link in enumerate(customer_links[:10]):  # Show first 10 for brevity
                try:
                    title = link.get_attribute("title")
                    print(f"  {i + 1}. {title}")
                except:
                    pass

            # Try to match customer title with target name
            matched_index = -1
            for i, link in enumerate(customer_links):
                try:
                    title = link.get_attribute("title")
                    if title and target_name.lower() in title.lower():
                        print(f"Found matching customer: {title} at index {i}")
                        matched_index = i
                        break
                except Exception as e:
                    continue

            if 0 <= matched_index < len(edit_buttons):
                # We found a matching customer and have a corresponding edit button
                print(f"Clicking edit button for customer at index {matched_index}")

                # Get the corresponding edit button (assuming they're in the same order)
                edit_button = edit_buttons[matched_index]

                # Use JavaScript to click directly without scrolling
                try:
                    self.wis.human_delay(1, 2)
                    self.driver_service.driver.execute_script(
                        "arguments[0].click();", edit_button
                    )
                    self.wis.human_delay(2, 4)
                    self.update_customers(status)
                    return True
                except Exception as e:
                    print(f"Failed to click with JavaScript: {e}")

                    # Fallback to regular click
                    try:
                        edit_button.click()
                        self.wis.human_delay(2, 4)
                        return True
                    except Exception as e2:
                        print(f"Failed to click with regular method: {e2}")

            # If we get here, we couldn't match or click
            print(f"Could not find or click edit button for customer '{target_name}'")

            # Take a screenshot for debugging
            try:
                self.driver_service.driver.save_screenshot("customer_search_failed.png")
                print("Saved debug screenshot to customer_search_failed.png")
            except:
                pass

            return False

        except Exception as e:
            print(f"Error finding customer: {e}")
            return False

    def update_customers(self, status_to_select) -> bool:
        try:
            self.driver_service.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "UpdateStatusForm"))
            )
            status_options = self.driver_service.find_elements(
                By.CLASS_NAME, "ItemPicker__option"
            )

            # Find all status options
            status_map = {}

            for option in status_options:
                pill_element = option.find_element(By.CLASS_NAME, "Pill")
                status_text = pill_element.text.strip()
                status_map[status_text] = option

            # Check if the requested status exists
            if status_to_select not in status_map:
                print(
                    f"Status `{status_to_select}` not found. Available options: {', '.join(status_map.keys())}"
                )
                return False

            # Check if the status is Create Deal
            if status_to_select == "Create Deal":
                status_map[status_to_select].click()
                status = ""
                if "Buyer" in self.lead.tags and "Seller" in self.lead.tags or "Buyer and Seller" in self.lead.tags or "Buyer/Seller" in self.lead.tags:
                    status = "Selling"
                elif "Buyer" in self.lead.tags:
                    status = "Buying"
                elif "Seller" in self.lead.tags:
                    status = "Selling"
                else:
                    print("No tags found, please add 'Buyer' or 'Seller' tag to the lead")
                    return False

                radio_button = self.driver_service.find_element(By.XPATH,
                                                                f"//div[@class='ItemPicker__text' and contains(text(), '{status}')]/ancestor::div[@role='radio']")

                # Check if it's already selected
                is_selected = radio_button.get_attribute("aria-checked") == "true"
                if is_selected:
                    print(f"Radio option '{status}' is already selected")
                    return True

                # Click using JavaScript for better reliability
                self.driver_service.driver.execute_script("arguments[0].click();", radio_button)
                print(f"Selected radio option '{status}' using JavaScript")
                self.wis.human_delay(1, 2)

                # Click the continue button
                continuing_button = self.driver_service.find_element(
                    By.XPATH,
                    "//button[contains(@class, 'Button primary')]/span[text()='Continue']"
                )
                continuing_button.click()
                self.wis.human_delay(2, 3)

                # Wait for the save action to complete
                self.driver_service.wait.until_not(
                    EC.presence_of_element_located((By.CLASS_NAME, "UpdateStatusForm"))
                )
            else:
                # Click on the matching status option
                status_map[status_to_select].click()
                # Wait briefly to ensure UI updates
                self.driver_service.driver.implicitly_wait(1)

                # Click the Save Button
                save_button = self.driver_service.find_element(
                    By.XPATH,
                    "//button[contains(@class, 'Button primary')]/span[text()='Save']/..",
                )
                save_button.click()

                # Wait for the save action to complete
                self.driver_service.wait.until_not(
                    EC.presence_of_element_located((By.CLASS_NAME, "UpdateStatusForm"))
                )

            return True
        except TimeoutException:
            print(
                "Timeout waiting for elements to load or form to disappear after save"
            )
            return False

        except Exception as e:
            print(f"Failed to update customer: {e}")
            return False

    def _process_customer(self, edit_button) -> None:
        # Scroll to element and ensure it's clickable
        self.driver_service.scroll_into_view(edit_button)
        self.wis.human_delay(2, 4)

        # Click edit button
        try:
            edit_button.click()
        except:
            self.driver_service.safe_click(edit_button)

        self.wis.human_delay(2, 4)

        # Click save button
        save_button = self.driver_service.find_clickable_element(
            By.XPATH, "//span[text()='Save']"
        )

        try:
            save_button.click()
        except:
            self.driver_service.safe_click(save_button)

        self.wis.human_delay(3, 5)

    def update_active_lead(self, lead: Lead, status: str) -> None:
        """Update the active lead for processing"""
        self.lead = lead
        self.status = status

    def update_multiple_leads(self, leads_data: List[Tuple[Lead, str]]) -> Dict[str, Any]:
        """
        Update multiple leads in a single browser session (login ONCE, process all)

        Args:
            leads_data: List of tuples containing (lead, target_status)

        Returns:
            Dict with sync results
        """
        results = {
            "total_leads": len(leads_data),
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "details": []
        }

        logger.info(f"Starting Redfin bulk update for {len(leads_data)} leads")
        print(f"[START] Beginning Redfin update process for {len(leads_data)} leads")

        try:
            print("[LOGIN] Logging into Redfin...")
            login_start = time.time()
            login_success = self.login2()
            login_time = time.time() - login_start

            if not login_success:
                error_msg = "Failed to login to Redfin - check credentials and network connection"
                print(f"[ERROR] {error_msg}")
                logger.error(error_msg)
                # Mark all leads as failed due to login failure
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

            print(f"[SUCCESS] Login successful (took {login_time:.1f}s)")
            logger.info(f"Successfully logged into Redfin in {login_time:.1f} seconds")
            print(f"[ROCKET] Processing {len(leads_data)} leads...")

            processed_count = 0
            for lead, target_status in leads_data:
                processed_count += 1
                lead_start_time = time.time()

                try:
                    # Update the service instance with this lead's data
                    self.update_active_lead(lead, target_status)

                    full_name = f"{lead.first_name} {lead.last_name}"

                    print(f"\n[LEAD {processed_count}/{len(leads_data)}] Processing: {full_name}")
                    print(f"[TARGET] Target Redfin Status: {target_status}")
                    logger.info(f"Processing lead {processed_count}/{len(leads_data)}: {full_name} -> {target_status}")

                    # Find and update the customer
                    print(f"[SEARCH] Searching for '{full_name}'...")
                    success = self.find_and_click_customer_by_name2(full_name, target_status)

                    lead_time = time.time() - lead_start_time

                    if success:
                        print(f"[SUCCESS] Updated {full_name} in {lead_time:.1f}s")
                        results["successful"] += 1
                        results["details"].append({
                            "lead_id": lead.id,
                            "fub_person_id": lead.fub_person_id,
                            "name": full_name,
                            "status": "success",
                            "target_status": target_status
                        })

                        # Update lead metadata
                        try:
                            from datetime import datetime, timezone
                            if not lead.metadata:
                                lead.metadata = {}
                            lead.metadata["redfin_last_updated"] = datetime.now(timezone.utc).isoformat()
                            lead.metadata["redfin_last_status"] = target_status
                            self.lead_service.update(lead)
                        except Exception as meta_error:
                            logger.warning(f"Failed to update metadata for {full_name}: {meta_error}")
                    else:
                        print(f"[FAILED] Could not find/update {full_name}")
                        results["failed"] += 1
                        results["details"].append({
                            "lead_id": lead.id,
                            "fub_person_id": lead.fub_person_id,
                            "name": full_name,
                            "status": "failed",
                            "error": "Customer not found or update failed"
                        })

                except Exception as e:
                    lead_time = time.time() - lead_start_time
                    error_msg = str(e)
                    print(f"[ERROR] Failed to process {lead.first_name} {lead.last_name}: {error_msg}")
                    logger.error(f"Error processing lead: {error_msg}")
                    results["failed"] += 1
                    results["details"].append({
                        "lead_id": lead.id,
                        "fub_person_id": lead.fub_person_id,
                        "name": f"{lead.first_name} {lead.last_name}",
                        "status": "failed",
                        "error": error_msg
                    })

                # Small delay between leads to avoid rate limiting
                self.wis.human_delay(1, 2)

            print(f"\n[COMPLETE] Processed {len(leads_data)} leads: {results['successful']} successful, {results['failed']} failed")

        except Exception as e:
            error_msg = f"Bulk update error: {str(e)}"
            logger.error(error_msg)
            print(f"[ERROR] {error_msg}")

        finally:
            print("[CLEANUP] Closing browser...")
            self.close()

        return results

    def update_multiple_leads_with_tracker(
        self,
        leads_data: List[Tuple[Lead, str]],
        sync_id: str,
        tracker
    ) -> Dict[str, Any]:
        """
        Update multiple leads with progress tracking via tracker

        Args:
            leads_data: List of tuples containing (lead, target_status)
            sync_id: Unique sync ID for tracking
            tracker: SyncStatusTracker instance

        Returns:
            Dict with sync results
        """
        results = {
            "total_leads": len(leads_data),
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "details": []
        }

        try:
            tracker.update_progress(sync_id, message="Logging into Redfin...")
            login_start = time.time()
            login_success = self.login2()
            login_time = time.time() - login_start

            if not login_success:
                error_msg = "Failed to login to Redfin"
                tracker.complete_sync(sync_id, error=error_msg)
                # Mark all as failed
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

            tracker.update_progress(
                sync_id,
                message=f"Login successful (took {login_time:.1f}s)"
            )

            processed_count = 0
            for lead, target_status in leads_data:
                # Check for cancellation
                if tracker.is_cancelled(sync_id):
                    logger.info(f"Sync {sync_id} cancelled, stopping at lead {processed_count}/{len(leads_data)}")
                    tracker.update_progress(
                        sync_id,
                        message=f"Sync cancelled. Processed {processed_count} of {len(leads_data)} leads."
                    )
                    results["details"].append({
                        "lead_id": None,
                        "fub_person_id": None,
                        "name": "SYNC CANCELLED",
                        "status": "cancelled",
                        "error": "Sync was cancelled by user"
                    })
                    break

                processed_count += 1
                full_name = f"{lead.first_name} {lead.last_name}"

                try:
                    self.update_active_lead(lead, target_status)

                    tracker.update_progress(
                        sync_id,
                        processed=processed_count,
                        current_lead=full_name,
                        message=f"Processing {processed_count}/{len(leads_data)}: {full_name}"
                    )

                    # Check if lead should be skipped (recently synced)
                    should_skip = False
                    try:
                        from datetime import datetime, timedelta, timezone
                        now = datetime.now(timezone.utc)
                        cutoff_time = now - timedelta(hours=self.min_sync_interval_hours)

                        if lead.metadata and isinstance(lead.metadata, dict):
                            last_synced_str = lead.metadata.get("redfin_last_updated")
                            if last_synced_str:
                                if isinstance(last_synced_str, str):
                                    last_synced = datetime.fromisoformat(last_synced_str.replace('Z', '+00:00'))
                                elif isinstance(last_synced_str, datetime):
                                    last_synced = last_synced_str
                                else:
                                    last_synced = None

                                if last_synced:
                                    if last_synced.tzinfo is None:
                                        last_synced = last_synced.replace(tzinfo=timezone.utc)
                                    if last_synced > cutoff_time:
                                        hours_since = (now - last_synced).total_seconds() / 3600
                                        should_skip = True
                                        logger.info(f"Skipping {full_name} - synced {hours_since:.1f}h ago")
                    except Exception as skip_error:
                        logger.warning(f"Error checking skip status: {skip_error}")

                    if should_skip:
                        results["skipped"] += 1
                        results["details"].append({
                            "lead_id": lead.id,
                            "fub_person_id": lead.fub_person_id,
                            "name": full_name,
                            "status": "skipped",
                            "error": "Recently synced"
                        })
                        continue

                    # Find and update the customer
                    success = self.find_and_click_customer_by_name2(full_name, target_status)

                    if success:
                        results["successful"] += 1
                        results["details"].append({
                            "lead_id": lead.id,
                            "fub_person_id": lead.fub_person_id,
                            "name": full_name,
                            "status": "success",
                            "target_status": target_status
                        })

                        # Update lead metadata
                        try:
                            from datetime import datetime, timezone
                            if not lead.metadata:
                                lead.metadata = {}
                            lead.metadata["redfin_last_updated"] = datetime.now(timezone.utc).isoformat()
                            lead.metadata["redfin_last_status"] = target_status
                            self.lead_service.update(lead)
                        except Exception as meta_error:
                            logger.warning(f"Failed to update metadata for {full_name}: {meta_error}")

                        tracker.update_progress(
                            sync_id,
                            processed=processed_count,
                            successful=results["successful"],
                            message=f"Updated {full_name} to {target_status}"
                        )
                    else:
                        results["failed"] += 1
                        results["details"].append({
                            "lead_id": lead.id,
                            "fub_person_id": lead.fub_person_id,
                            "name": full_name,
                            "status": "failed",
                            "error": "Customer not found or update failed"
                        })

                        tracker.update_progress(
                            sync_id,
                            processed=processed_count,
                            failed=results["failed"],
                            message=f"Failed to update {full_name}"
                        )

                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Error processing lead {full_name}: {error_msg}")
                    results["failed"] += 1
                    results["details"].append({
                        "lead_id": lead.id,
                        "fub_person_id": lead.fub_person_id,
                        "name": full_name,
                        "status": "failed",
                        "error": error_msg
                    })

                    tracker.update_progress(
                        sync_id,
                        processed=processed_count,
                        failed=results["failed"],
                        message=f"Error processing {full_name}: {error_msg}"
                    )

                # Small delay between leads
                self.wis.human_delay(1, 2)

            # Complete the sync
            tracker.complete_sync(
                sync_id,
                total=len(leads_data),
                successful=results["successful"],
                failed=results["failed"]
            )

        except Exception as e:
            error_msg = f"Bulk update error: {str(e)}"
            logger.error(error_msg)
            tracker.complete_sync(sync_id, error=error_msg)

        finally:
            self.close()

        return results

    def close(self) -> None:
        if self.driver_service:
            try:
                # Call the quit method directly instead of __exit__
                if (
                        hasattr(self.driver_service, "driver")
                        and self.driver_service.driver
                ):
                    self.driver_service.driver.quit()
            except Exception as e:
                self.logger.error(f"Error closing driver: {e}")

    @staticmethod
    def calculate_next_run_time(
            min_delay_hours: int = 72, max_delay_hours: int = 220
    ) -> datetime:
        now = datetime.now()
        random_delay = random.randint(min_delay_hours, max_delay_hours)
        return now + timedelta(hours=random_delay)


if __name__ == "__main__":
    redfin_service = RedfinService(Lead(), "Shit")
    # redfin_service.redfin_run()
