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

    def login2(self) -> bool:
        if not self.driver_service.initialize_driver():
            return False

        try:
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
                    return True
                print("[Login] Google login failed, trying direct login as fallback...")

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
            return self._verify_login_success()

        except Exception as e:
            print(f"Login failed: {e}")
            self.is_logged_in = False
            return False

    def _get_login_method(self) -> str:
        """Get the login method from lead source settings metadata"""
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
                    login_method = metadata.get('login_method', 'google')
                    return login_method

        except Exception as e:
            logger.warning(f"Could not load login method from database: {e}")

        # Default to google for Redfin
        return "google"

    def _try_google_login(self) -> bool:
        """Handle Google OAuth login for Redfin"""
        try:
            print("[Google Login] Looking for Google sign-in button...")

            # Find "Sign in with Google" button
            google_button_selectors = [
                'button[data-rf-test-name="google_login"]',
                'button[aria-label*="Google"]',
                '[class*="google"]',
                '//button[contains(text(), "Google")]',
                '//button[contains(text(), "Sign in with Google")]',
                '//div[contains(text(), "Google")]//ancestor::button',
                'button[class*="social"]',
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
                        self.wis.human_delay(3, 5)

                # Enter password
                password_selectors = [
                    'input[type="password"]',
                    'input[name="password"]',
                    'input[name="Passwd"]',
                ]

                password_field = None
                for selector in password_selectors:
                    try:
                        password_field = self.driver_service.find_element(By.CSS_SELECTOR, selector)
                        if password_field:
                            break
                    except:
                        continue

                if password_field:
                    print("[Google OAuth] Entering password")
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

                # Check for Google 2FA
                if self._check_and_handle_google_2fa():
                    print("[Google OAuth] Google 2FA handled")

            # Switch back to main window if we were in popup
            if len(all_windows) > 1:
                self.driver_service.driver.switch_to.window(original_window)
                self.wis.human_delay(3, 5)

            # Verify we're logged into Redfin
            return self._verify_login_success()

        except Exception as e:
            print(f"[Google OAuth] Error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _check_and_handle_google_2fa(self) -> bool:
        """Handle Google's 2FA if required"""
        try:
            self.wis.human_delay(2, 3)
            page_source = self.driver_service.driver.page_source.lower()

            # Check for 2FA indicators
            twofa_indicators = [
                "2-step verification",
                "verify it's you",
                "verification code",
                "enter the code",
                "check your phone",
            ]

            if not any(indicator in page_source for indicator in twofa_indicators):
                return True  # No 2FA needed

            print("[Google 2FA] Google 2FA detected...")

            # If it's showing "Check your phone", click "Try another way" to get email option
            if "check your phone" in page_source or "try another way" in page_source:
                print("[Google 2FA] Phone verification detected - clicking 'Try another way'...")
                try_another_selectors = [
                    '//button[contains(text(), "Try another way")]',
                    '//a[contains(text(), "Try another way")]',
                    '//span[contains(text(), "Try another way")]',
                    '[data-challengetype]',
                ]

                try_another = None
                for selector in try_another_selectors:
                    try:
                        if selector.startswith('//'):
                            try_another = self.driver_service.find_element(By.XPATH, selector)
                        else:
                            try_another = self.driver_service.find_element(By.CSS_SELECTOR, selector)
                        if try_another:
                            break
                    except:
                        continue

                if try_another:
                    self.driver_service.safe_click(try_another)
                    print("[Google 2FA] Clicked 'Try another way'")
                    self.wis.human_delay(2, 3)

                    # Now look for email verification option specifically
                    # Google shows multiple options like:
                    #   "Get a verification code at (***) ***-1234" (SMS - DO NOT select)
                    #   "Get a verification code at a****@s******.com" (Email - SELECT THIS)
                    # We need to find the one with "@" (email address indicator)
                    page_source = self.driver_service.driver.page_source.lower()

                    # First try Google's internal data attributes for email challenge
                    email_option = None
                    email_specific_selectors = [
                        '[data-challengetype="12"]',  # Email challenge type
                        '[data-sendmethod="EMAIL"]',
                    ]

                    for selector in email_specific_selectors:
                        try:
                            email_option = self.driver_service.find_element(By.CSS_SELECTOR, selector)
                            if email_option:
                                print(f"[Google 2FA] Found email option via: {selector}")
                                break
                        except:
                            continue

                    # If data attributes didn't work, find all "Get a verification code" options
                    # and pick the one containing "@" (email) rather than phone number
                    if not email_option:
                        try:
                            all_options = self.driver_service.find_elements(
                                By.XPATH, "//*[contains(text(), 'verification code') or contains(text(), 'Verification code')]"
                            )
                            print(f"[Google 2FA] Found {len(all_options)} verification options")
                            for opt in all_options:
                                opt_text = opt.text.strip()
                                print(f"[Google 2FA]   Option: '{opt_text}'")
                                # Select the one with "@" (email address)
                                if "@" in opt_text:
                                    email_option = opt
                                    print(f"[Google 2FA] Found EMAIL option (contains @): '{opt_text}'")
                                    break
                            # If no "@" option found, try to find any option with "email" text
                            if not email_option:
                                for opt in all_options:
                                    opt_text = opt.text.strip().lower()
                                    if "email" in opt_text:
                                        email_option = opt
                                        print(f"[Google 2FA] Found email option by text")
                                        break
                        except Exception as e:
                            print(f"[Google 2FA] Error finding options: {e}")

                    # Fallback: try broader selectors
                    if not email_option:
                        fallback_selectors = [
                            '//div[contains(text(), "email")]',
                            '//li[contains(text(), "email")]',
                            '//li[contains(text(), "@")]',
                            '//div[contains(text(), "@")]',
                        ]
                        for selector in fallback_selectors:
                            try:
                                email_option = self.driver_service.find_element(By.XPATH, selector)
                                if email_option:
                                    print(f"[Google 2FA] Found email option via fallback: {selector}")
                                    break
                            except:
                                continue

                    if email_option:
                        self.driver_service.safe_click(email_option)
                        print("[Google 2FA] Selected email verification option")
                        self.wis.human_delay(3, 5)
                    else:
                        print("[Google 2FA] WARNING: Could not find email-specific verification option")
                        print("[Google 2FA] Page text (first 500 chars):")
                        try:
                            body = self.driver_service.driver.find_element(By.TAG_NAME, "body")
                            print(f"[Google 2FA] {body.text[:500]}")
                        except:
                            pass

            # Check if we have 2FA credentials
            if not self.twofa_email or not self.twofa_app_password:
                print("[Google 2FA] ERROR: No 2FA email credentials configured!")
                return False

            # First try to get a magic link from email (Google often sends these)
            print("[Google 2FA] Checking for magic link in email...")
            helper = Email2FAHelper(
                email_address=self.twofa_email,
                app_password=self.twofa_app_password
            )

            # Try to get verification link first
            magic_link = helper.get_verification_link(
                sender_contains="google",
                link_contains="accounts.google.com",
                max_age_seconds=180,
                max_retries=10,
                retry_delay=3.0
            )

            if magic_link:
                print(f"[Google 2FA] Found magic link, navigating...")
                # Open the magic link in the browser
                self.driver_service.get_page(magic_link)
                self.wis.human_delay(5, 8)
                print("[Google 2FA] Clicked magic link from email")
                return True

            # If no magic link, try to get a 6-digit code
            print("[Google 2FA] No magic link found, trying verification code...")
            code = helper.get_verification_code(
                sender_contains="google",
                max_age_seconds=180,
                max_retries=10,
                retry_delay=2.0,
                code_length=6
            )

            if not code:
                print("[Google 2FA] ERROR: Could not retrieve 2FA code or link from email")
                print("[Google 2FA] You may need to manually approve on your phone")
                return False

            print(f"[Google 2FA] Retrieved code: {code}")

            # Find and fill the 2FA input
            twofa_selectors = [
                'input[name="totpPin"]',
                'input[type="tel"]',
                'input[name="idvPin"]',
                '#totpPin',
                'input[name="pin"]',
                'input[aria-label*="code"]',
            ]

            twofa_input = None
            for selector in twofa_selectors:
                try:
                    twofa_input = self.driver_service.find_element(By.CSS_SELECTOR, selector)
                    if twofa_input:
                        break
                except:
                    continue

            if twofa_input:
                self.wis.simulated_typing(twofa_input, code)
                self.wis.human_delay(1, 2)

                # Click verify/next
                verify_button = self.driver_service.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
                if verify_button:
                    self.driver_service.safe_click(verify_button)
                    print("[Google 2FA] Submitted 2FA code")
                    self.wis.human_delay(3, 5)

            return True

        except Exception as e:
            print(f"[Google 2FA] Error: {e}")
            import traceback
            traceback.print_exc()
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
                            self.lead_service.update_lead(lead)
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
                            self.lead_service.update_lead(lead)
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
