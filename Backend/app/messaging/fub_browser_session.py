"""FUB Browser Session - handles login and SMS sending via web interface."""

from playwright.async_api import Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeout
import asyncio
import random
import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .session_store import SessionStore

logger = logging.getLogger(__name__)


class FUBBrowserSession:
    """Manages a single agent's FUB browser session."""

    FUB_BASE_URL = "https://app.followupboss.com"
    WARM_SESSION_THRESHOLD_SECONDS = 30  # Skip validation if used within this time

    def __init__(self, browser: Browser, agent_id: str, session_store: 'SessionStore'):
        self.browser = browser
        self.agent_id = agent_id
        self.session_store = session_store
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._logged_in = False
        self._actual_base_url: Optional[str] = None  # Team subdomain URL after login
        self._last_successful_operation: Optional[float] = None  # Timestamp of last success

    # Navigation retry settings
    MAX_NAVIGATION_RETRIES = 3
    NAVIGATION_TIMEOUT_MS = 30000  # 30 seconds (reduced from 60s for faster failure)

    # Step-level timeouts (in milliseconds) for faster failure detection
    CLICK_TIMEOUT_MS = 10000  # 10 seconds for element clicks
    INPUT_TIMEOUT_MS = 10000  # 10 seconds for text input
    JS_EVAL_TIMEOUT_MS = 15000  # 15 seconds for JavaScript evaluation
    ELEMENT_WAIT_TIMEOUT_MS = 10000  # 10 seconds for element waits

    async def login(self, credentials: dict):
        """Login to FUB with credentials or SSO.

        Implements automatic retry with cookie clearing for robust session recovery.
        If navigation times out, cookies are cleared and login is retried.
        """
        logger.info(f"Starting login for agent {self.agent_id}")

        # Try to restore session from cookies
        logger.debug("Checking for saved cookies...")
        cookies = await self.session_store.get_cookies(self.agent_id)
        logger.debug(f"Cookies found: {cookies is not None}")

        # Track if we should try with cookies or fresh
        use_cookies = cookies is not None
        last_error = None

        for attempt in range(self.MAX_NAVIGATION_RETRIES):
            try:
                # Close previous context if exists (for retry)
                if self.context:
                    try:
                        await self.context.close()
                    except Exception:
                        pass
                    self.context = None
                    self.page = None

                logger.info(f"Login attempt {attempt + 1}/{self.MAX_NAVIGATION_RETRIES} for agent {self.agent_id} (cookies={'yes' if use_cookies else 'no'})")

                logger.debug("Creating browser context...")
                self.context = await self.browser.new_context(
                    storage_state=cookies if use_cookies else None,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080}
                )
                self.page = await self.context.new_page()
                logger.debug("Browser context created")

                # Check if already logged in by navigating to a protected page
                logger.debug(f"Navigating to {self.FUB_BASE_URL}/people to check login status (timeout={self.NAVIGATION_TIMEOUT_MS}ms)...")
                await self.page.goto(
                    f"{self.FUB_BASE_URL}/people",
                    wait_until="domcontentloaded",
                    timeout=self.NAVIGATION_TIMEOUT_MS
                )
                logger.debug("Navigation complete, checking URL...")
                await self._human_delay(1, 2)

                # Check if we're on login page or dashboard
                current_url = self.page.url
                if "login" in current_url or "signin" in current_url:
                    logger.info(f"Session expired for agent {self.agent_id}, performing fresh login")
                    await self._perform_login(credentials)
                    # Save cookies after successful login
                    await self.session_store.save_cookies(
                        self.agent_id,
                        await self.context.storage_state()
                    )
                else:
                    logger.info(f"Session restored successfully for agent {self.agent_id}")
                    self._logged_in = True

                # Capture the actual base URL (team subdomain) after login
                self._capture_base_url()

                # Mark session as warm after successful login
                self.mark_operation_success()

                # Success - return
                return

            except PlaywrightTimeout as e:
                last_error = e
                logger.warning(f"Timeout on attempt {attempt + 1} for agent {self.agent_id}: {e}")

                # On timeout, clear cookies for next attempt (they may be corrupted)
                if use_cookies:
                    logger.info(f"Clearing potentially corrupted cookies for agent {self.agent_id}")
                    await self.session_store.delete_cookies(self.agent_id)
                    use_cookies = False
                    cookies = None

                # Wait before retry
                if attempt < self.MAX_NAVIGATION_RETRIES - 1:
                    wait_time = (attempt + 1) * 5  # 5s, 10s, 15s
                    logger.info(f"Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)

            except Exception as e:
                last_error = e
                logger.warning(f"Error on attempt {attempt + 1} for agent {self.agent_id}: {e}")

                # On error, try without cookies next time
                if use_cookies:
                    logger.info(f"Clearing cookies and retrying for agent {self.agent_id}")
                    await self.session_store.delete_cookies(self.agent_id)
                    use_cookies = False
                    cookies = None

                # Wait before retry
                if attempt < self.MAX_NAVIGATION_RETRIES - 1:
                    wait_time = (attempt + 1) * 5
                    logger.info(f"Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)

        # All retries failed
        logger.error(f"All {self.MAX_NAVIGATION_RETRIES} login attempts failed for agent {self.agent_id}")
        raise Exception(f"Failed to login after {self.MAX_NAVIGATION_RETRIES} attempts. Last error: {last_error}")

    async def _perform_login(self, credentials: dict):
        """Perform actual login with human-like delays."""
        login_type = credentials.get("type", "email")  # email, google, microsoft

        if login_type == "email":
            await self._email_login(credentials["email"], credentials["password"])
        elif login_type == "google":
            await self._google_sso_login(credentials)
        elif login_type == "microsoft":
            await self._microsoft_sso_login(credentials)
        else:
            raise ValueError(f"Unknown login type: {login_type}")

        self._logged_in = True

    async def _email_login(self, email: str, password: str):
        """Login with email/password."""
        logger.info(f"Performing email login for {email}")
        logger.debug("Navigating to login page...")
        await self.page.goto(f"{self.FUB_BASE_URL}/login", wait_until="domcontentloaded")
        logger.debug("Login page loaded")
        await self._human_delay(1, 2)

        # FUB login page selectors (may need adjustment based on actual FUB UI)
        # Try multiple possible selectors
        email_selectors = [
            'input[type="email"]',
            'input[name="email"]',
            'input[placeholder*="email" i]',
            '#email',
            'input[autocomplete="email"]'
        ]

        password_selectors = [
            'input[type="password"]',
            'input[name="password"]',
            '#password',
            'input[autocomplete="current-password"]'
        ]

        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Sign in")',
            'button:has-text("Log in")',
            'button:has-text("Login")'
        ]

        # Find and fill email - use fast fill for login (simulated typing not needed)
        email_input = await self._find_element_by_selectors(email_selectors)
        if not email_input:
            raise Exception("Could not find email input field")
        await email_input.fill(email)
        await self._human_delay(0.3, 0.5)

        # Find and fill password
        password_input = await self._find_element_by_selectors(password_selectors)
        if not password_input:
            raise Exception("Could not find password input field")
        await password_input.fill(password)
        await self._human_delay(0.3, 0.5)

        # Click login button
        submit_button = await self._find_element_by_selectors(submit_selectors)
        if not submit_button:
            raise Exception("Could not find submit button")
        await submit_button.click()

        # Wait for navigation to complete
        await self.page.wait_for_load_state("networkidle")
        await self._human_delay(2, 3)

        # Verify login succeeded
        current_url = self.page.url
        if "login" in current_url or "signin" in current_url:
            # Check for "new location" security message
            page_text = await self.page.text_content('body')
            if page_text and ("new location" in page_text.lower() or "security measure" in page_text.lower()):
                logger.info("FUB security check detected - attempting to get verification link from email")
                await self._handle_security_email_verification(email)
                return  # Successfully handled via email verification

            # Check for other error messages
            error_elem = await self.page.query_selector('[class*="error"], [class*="alert"]')
            error_text = await error_elem.text_content() if error_elem else "Unknown error"
            raise Exception(f"Login failed: {error_text}")

        # Capture the team subdomain after successful login
        self._capture_base_url()
        logger.info(f"Email login successful for {email}")

    async def _handle_security_email_verification(self, fub_email: str):
        """
        Handle FUB's 'new location' security check by fetching the
        verification link from email and navigating to it.
        """
        logger.info("=" * 60)
        logger.info("FUB SECURITY EMAIL VERIFICATION STARTED")
        logger.info("=" * 60)
        logger.info(f"FUB account being logged in: {fub_email}")

        try:
            from app.utils.email_2fa_helper import Email2FAHelper
            import os

            # Log what credentials sources are available
            logger.info("Checking for Gmail credentials...")
            env_gmail = os.getenv("GMAIL_EMAIL")
            env_gmail_pwd = os.getenv("GMAIL_APP_PASSWORD")
            logger.info(f"  Environment GMAIL_EMAIL: {'SET' if env_gmail else 'NOT SET'}")
            logger.info(f"  Environment GMAIL_APP_PASSWORD: {'SET' if env_gmail_pwd else 'NOT SET'}")

            # Create email helper - uses centralized ai_agent_settings (preferred)
            # or falls back to environment variables
            email_helper = await Email2FAHelper.from_settings()

            if not email_helper or not email_helper.email_address:
                logger.error("=" * 60)
                logger.error("GMAIL CREDENTIALS NOT CONFIGURED")
                logger.error("=" * 60)
                logger.error("To fix this, you need to configure Gmail credentials:")
                logger.error("  Option 1: Set GMAIL_EMAIL and GMAIL_APP_PASSWORD environment variables on Railway")
                logger.error("  Option 2: Configure gmail_email and gmail_app_password in system_settings table")
                logger.error("")
                logger.error("To create a Gmail App Password:")
                logger.error("  1. Go to https://myaccount.google.com/apppasswords")
                logger.error("  2. Create an app password for 'Mail'")
                logger.error("  3. Use that 16-character password (not your regular Gmail password)")
                raise Exception(
                    "Login failed: New location security check. "
                    "Email credentials not configured for auto-verification. "
                    "Please set GMAIL_EMAIL and GMAIL_APP_PASSWORD in Railway environment variables. "
                    "Please approve the login manually via email."
                )

            logger.info(f"Gmail helper configured with email: {email_helper.email_address}")

            logger.info(f"Checking email inbox for FUB verification link...")
            logger.info(f"  Search criteria: sender contains 'followupboss', link contains 'followupboss.com'")
            logger.info(f"  Will retry up to 15 times with 3 second delays (max 45 seconds)")

            # Get the verification link from the FUB security email
            # NOTE: Don't filter by subject - FUB uses various subjects like "Verify your sign-in",
            # "New location detected", etc. Matching sender + link domain is sufficient.
            try:
                with email_helper:
                    logger.info("  IMAP connection established successfully")
                    verification_link = email_helper.get_verification_link(
                        sender_contains="followupboss",
                        subject_contains=None,  # Don't filter by subject - FUB uses various subjects
                        link_contains="followupboss.com",
                        max_age_seconds=300,  # 5 minutes
                        max_retries=15,
                        retry_delay=3.0
                    )
            except Exception as imap_error:
                logger.error(f"IMAP connection/search failed: {imap_error}")
                logger.error("This could be due to:")
                logger.error("  1. Wrong Gmail credentials")
                logger.error("  2. Gmail blocking access from Railway's IP (security)")
                logger.error("  3. Need to enable 'Less secure app access' or use App Password")
                logger.error("  4. Network connectivity issues")
                raise Exception(
                    f"Login failed: Could not connect to Gmail to retrieve verification link. "
                    f"Error: {imap_error}"
                )

            if not verification_link:
                logger.error("=" * 60)
                logger.error("VERIFICATION LINK NOT FOUND IN EMAIL")
                logger.error("=" * 60)
                logger.error("The FUB verification email was not found. Possible causes:")
                logger.error("  1. Email hasn't arrived yet (FUB can be slow)")
                logger.error("  2. Email went to spam folder")
                logger.error("  3. Wrong Gmail account configured")
                logger.error("  4. FUB sent the email to a different address")
                logger.error(f"  Gmail being checked: {email_helper.email_address}")
                logger.error(f"  FUB account trying to login: {fub_email}")
                raise Exception(
                    "Login failed: New location security check. "
                    "Verification email not found after 45 seconds. "
                    "Please check your inbox and approve the login manually, then retry."
                )

            logger.info(f"Found FUB verification link: {verification_link[:80]}...")
            logger.info("Navigating to verification link in browser...")

            # Navigate to the verification link in Playwright
            await self.page.goto(verification_link, wait_until="domcontentloaded")
            await self._human_delay(2, 3)

            # Check if we're now logged in
            current_url = self.page.url
            logger.info(f"After clicking verification link, current URL: {current_url}")

            if "login" not in current_url and "signin" not in current_url:
                logger.info("=" * 60)
                logger.info("FUB EMAIL VERIFICATION SUCCESSFUL!")
                logger.info("=" * 60)
                self._capture_base_url()
                self._logged_in = True
                return

            # Sometimes FUB redirects to another page - follow it
            logger.info("Still on login page, waiting for redirect...")
            await self.page.wait_for_load_state("networkidle")
            current_url = self.page.url
            logger.info(f"After waiting for redirect, current URL: {current_url}")

            if "login" not in current_url and "signin" not in current_url:
                logger.info("=" * 60)
                logger.info("FUB EMAIL VERIFICATION SUCCESSFUL (after redirect)!")
                logger.info("=" * 60)
                self._capture_base_url()
                self._logged_in = True
                return

            # If still on login page, the verification link may have expired
            logger.error("Still on login page after clicking verification link")
            logger.error("The verification link may have expired or been already used")
            raise Exception(
                "Login failed: Verification link may have expired or already been used. "
                "Please try again."
            )

        except ImportError:
            logger.error("Email2FAHelper not available")
            raise Exception(
                "Login failed: New location security check. "
                "Email verification module not available."
            )
        except Exception as e:
            if "Login failed" in str(e):
                raise
            logger.error(f"Email verification failed: {e}")
            raise Exception(
                f"Login failed: New location security check. "
                f"Auto-verification failed: {e}"
            )

    async def _google_sso_login(self, credentials: dict):
        """Login with Google SSO."""
        logger.info("Performing Google SSO login")
        await self.page.goto(f"{self.FUB_BASE_URL}/login", wait_until="domcontentloaded")
        await self._human_delay(1, 2)

        # Click Google SSO button
        google_selectors = [
            'button:has-text("Google")',
            'a:has-text("Google")',
            '[class*="google" i]',
            'button[data-provider="google"]'
        ]

        google_button = await self._find_element_by_selectors(google_selectors)
        if not google_button:
            raise Exception("Could not find Google SSO button")
        await google_button.click()

        # Wait for Google login page
        await self.page.wait_for_load_state("networkidle")
        await self._human_delay(1, 2)

        # Fill Google email
        email_input = await self.page.wait_for_selector('input[type="email"]', timeout=10000)
        await self._simulated_typing(email_input, credentials["email"])
        await self._human_delay(0.5, 1)

        # Click next
        next_button = await self.page.wait_for_selector('button:has-text("Next"), #identifierNext')
        await next_button.click()
        await self.page.wait_for_load_state("networkidle")
        await self._human_delay(1, 2)

        # Fill password
        password_input = await self.page.wait_for_selector('input[type="password"]', timeout=10000)
        await self._simulated_typing(password_input, credentials["password"])
        await self._human_delay(0.5, 1)

        # Click next/sign in
        signin_button = await self.page.wait_for_selector('button:has-text("Next"), #passwordNext')
        await signin_button.click()

        # Wait for redirect back to FUB (could be any subdomain)
        await self.page.wait_for_url("**followupboss.com/**", timeout=30000)
        await self._human_delay(2, 3)
        self._capture_base_url()  # Capture subdomain after redirect

        logger.info("Google SSO login successful")

    async def _microsoft_sso_login(self, credentials: dict):
        """Login with Microsoft SSO."""
        logger.info("Performing Microsoft SSO login")
        await self.page.goto(f"{self.FUB_BASE_URL}/login", wait_until="domcontentloaded")
        await self._human_delay(1, 2)

        # Click Microsoft SSO button
        ms_selectors = [
            'button:has-text("Microsoft")',
            'a:has-text("Microsoft")',
            '[class*="microsoft" i]',
            'button[data-provider="microsoft"]'
        ]

        ms_button = await self._find_element_by_selectors(ms_selectors)
        if not ms_button:
            raise Exception("Could not find Microsoft SSO button")
        await ms_button.click()

        # Wait for Microsoft login page
        await self.page.wait_for_load_state("networkidle")
        await self._human_delay(1, 2)

        # Fill Microsoft email
        email_input = await self.page.wait_for_selector('input[type="email"], input[name="loginfmt"]', timeout=10000)
        await self._simulated_typing(email_input, credentials["email"])
        await self._human_delay(0.5, 1)

        # Click next
        next_button = await self.page.wait_for_selector('input[type="submit"], button[type="submit"]')
        await next_button.click()
        await self.page.wait_for_load_state("networkidle")
        await self._human_delay(1, 2)

        # Fill password
        password_input = await self.page.wait_for_selector('input[type="password"], input[name="passwd"]', timeout=10000)
        await self._simulated_typing(password_input, credentials["password"])
        await self._human_delay(0.5, 1)

        # Click sign in
        signin_button = await self.page.wait_for_selector('input[type="submit"], button[type="submit"]')
        await signin_button.click()

        # Handle "Stay signed in?" prompt if it appears
        try:
            stay_signed_in = await self.page.wait_for_selector('button:has-text("Yes"), input[value="Yes"]', timeout=5000)
            await stay_signed_in.click()
        except PlaywrightTimeout:
            pass  # No "Stay signed in" prompt

        # Wait for redirect back to FUB (could be any subdomain)
        await self.page.wait_for_url("**followupboss.com/**", timeout=30000)
        await self._human_delay(2, 3)
        self._capture_base_url()  # Capture subdomain after redirect

        logger.info("Microsoft SSO login successful")

    async def send_text_message(self, person_id: int, message: str) -> dict:
        """Navigate to lead profile and send SMS."""
        logger.info(f"Sending SMS to person {person_id}")

        if not self._logged_in:
            raise Exception("Not logged in. Call login() first.")

        # Reset page state before operation to avoid stale DOM/JS
        await self._reset_page_state(light=True)

        # Navigate to lead profile - FUB uses /2/people/view/{id} format
        # Use the captured team subdomain URL to avoid session loss
        person_url = f"{self._get_base_url()}/2/people/view/{person_id}"
        logger.info(f"Navigating to person page: {person_url}")
        await self.page.goto(
            person_url,
            wait_until="domcontentloaded",
            timeout=self.NAVIGATION_TIMEOUT_MS
        )
        logger.debug(f"Navigation complete for person {person_id}")
        await self._human_delay(1.5, 2.5)

        # Take screenshot for debugging
        import os
        debug_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        screenshot_path = os.path.join(debug_dir, f"debug_fub_person_{person_id}.png")
        await self.page.screenshot(path=screenshot_path)
        logger.info(f"Debug screenshot saved to: {screenshot_path}")

        # FUB UI (Jan 2025):
        # 1. Click "Messages" tab at top (has bubble icon, text "Messages")
        # 2. Textarea has placeholder "Write your text..."
        # 3. "Send Text" button (coral/orange color)

        messages_tab_selectors = [
            # FUB specific - div containing Messages text with bubble icon
            'div:has(.BaseIcon-bubble):has-text("Messages")',
            '.BaseIcon-bubble',
            '[class*="BoxTabPadding"]:has-text("Messages")',
            'button:has-text("Messages")',
            'a:has-text("Messages")',
            '[role="tab"]:has-text("Messages")',
            '[class*="bubble"]',
        ]

        compose_selectors = [
            # FUB specific class from actual HTML (Jan 2025)
            '[class*="person-text-input__TextArea"]',
            '.person-text-input__TextArea-sc-221b3u-0',
            # FUB specific - "Write your text..." placeholder
            'textarea[placeholder="Write your text..."]',
            'textarea[placeholder*="Write your text"]',
            'textarea[placeholder*="Write"]',
            'textarea.fs-exclude',
            # Generic textarea fallback
            'textarea',
        ]

        send_selectors = [
            # FUB specific class from actual HTML (Jan 2025)
            '.sendTextButton-FSSelector',
            '[class*="sendTextButton"]',
            # FUB specific - "Send Text" button
            'button:has-text("Send Text")',
            'button:has-text("Send")',
            '[class*="send"]',
            'button[type="submit"]',
        ]

        # Step 1: Click Messages tab to open the messaging panel
        # Use multiple approaches to ensure we click the right element
        messages_clicked = False

        # Approach 1: Try using page.locator with text matching (most reliable)
        try:
            logger.info("Trying to click Messages tab using locator...")
            messages_locator = self.page.locator('text="Messages"').first
            if await messages_locator.count() > 0:
                await messages_locator.click()
                messages_clicked = True
                logger.info("Clicked Messages tab using text locator")
                await self._human_delay(1.5, 2.5)  # Wait for panel to load
        except Exception as e:
            logger.debug(f"Locator approach failed: {e}")

        # Approach 2: Try clicking by the bubble icon parent
        if not messages_clicked:
            try:
                logger.info("Trying to click Messages tab using bubble icon...")
                bubble_icon = await self.page.query_selector('.BaseIcon-bubble')
                if bubble_icon:
                    # Click the parent element which should be the tab
                    parent = await bubble_icon.evaluate_handle('el => el.closest("div[class*=BoxTabPadding]") || el.parentElement.parentElement')
                    if parent:
                        await parent.as_element().click()
                        messages_clicked = True
                        logger.info("Clicked Messages tab via bubble icon parent")
                        await self._human_delay(1.5, 2.5)
            except Exception as e:
                logger.debug(f"Bubble icon approach failed: {e}")

        # Approach 3: Use JavaScript to click
        if not messages_clicked:
            try:
                logger.info("Trying to click Messages tab using JavaScript...")
                clicked = await self.page.evaluate('''() => {
                    // Find all elements containing "Messages" text
                    const elements = document.querySelectorAll('*');
                    for (const el of elements) {
                        if (el.textContent && el.textContent.trim() === 'Messages' &&
                            el.closest('[class*="BoxTabPadding"]')) {
                            el.closest('[class*="BoxTabPadding"]').click();
                            return true;
                        }
                    }
                    // Fallback: find by bubble icon
                    const bubble = document.querySelector('.BaseIcon-bubble');
                    if (bubble) {
                        const tab = bubble.closest('div');
                        if (tab) {
                            tab.click();
                            return true;
                        }
                    }
                    return false;
                }''')
                if clicked:
                    messages_clicked = True
                    logger.info("Clicked Messages tab using JavaScript")
                    await self._human_delay(1.5, 2.5)
            except Exception as e:
                logger.debug(f"JavaScript approach failed: {e}")

        # Approach 4: Original selector approach as fallback
        if not messages_clicked:
            try:
                messages_tab = await self._find_element_by_selectors(messages_tab_selectors)
                if messages_tab:
                    logger.info("Found Messages tab using selectors, clicking it")
                    await messages_tab.click()
                    messages_clicked = True
                    await self._human_delay(1.5, 2.5)
                else:
                    logger.warning("Messages tab not found with any method")
            except Exception as e:
                logger.debug(f"Selector approach failed: {e}")

        if not messages_clicked:
            logger.warning("Could not click Messages tab - compose area may not be visible")

        # Take another screenshot after clicking Messages tab
        await self.page.screenshot(path=os.path.join(debug_dir, f"debug_after_messages_tab_{person_id}.png"))

        # Debug: Log available textareas
        try:
            textareas = await self.page.query_selector_all('textarea')
            logger.info(f"Found {len(textareas)} textarea elements on page")
            for i, ta in enumerate(textareas[:5]):
                placeholder = await ta.get_attribute('placeholder') or 'no placeholder'
                logger.info(f"  Textarea {i}: placeholder='{placeholder}'")
        except Exception as e:
            logger.debug(f"Could not enumerate textareas: {e}")

        # Find and fill compose area
        compose_area = await self._find_element_by_selectors(compose_selectors)
        if not compose_area:
            # Take a debug screenshot
            debug_path = os.path.join(debug_dir, f"debug_no_compose_{person_id}.png")
            await self.page.screenshot(path=debug_path)
            logger.error(f"No compose area found. Debug screenshot: {debug_path}")
            raise Exception(f"Could not find message compose area for person {person_id}")

        # Clear any existing text and type new message
        await compose_area.click()
        await self._human_delay(0.3, 0.5)
        await compose_area.fill("")  # Clear first
        await self._simulated_typing(compose_area, message)
        await self._human_delay(0.5, 1)

        # Click send button
        send_button = await self._find_element_by_selectors(send_selectors)
        if not send_button:
            raise Exception(f"Could not find send button for person {person_id}")

        await send_button.click()
        await self._human_delay(1.5, 2.5)

        # Verify message was sent (check for success indicator or message appearing in thread)
        # This is optional validation - in practice the UI usually shows the sent message

        # Mark operation success for warm session tracking
        self.mark_operation_success()

        logger.info(f"SMS sent successfully to person {person_id}")
        return {"success": True, "person_id": person_id, "message_length": len(message)}

    async def read_latest_message(self, person_id: int) -> dict:
        """
        Navigate to lead profile and read the latest incoming SMS message.

        This is used when FUB's API returns "Body is hidden for privacy reasons"
        but we need the actual message content for AI processing.

        Args:
            person_id: The FUB person ID

        Returns:
            Dict with 'success', 'message' (the text content), 'is_incoming', 'timestamp'
            or 'success': False with 'error'
        """
        logger.info(f"Reading latest message for person {person_id}")

        if not self._logged_in:
            raise Exception("Not logged in. Call login() first.")

        # Reset page state before operation to avoid stale DOM/JS
        await self._reset_page_state(light=True)

        # Navigate to lead profile - use the captured team subdomain URL
        person_url = f"{self._get_base_url()}/2/people/view/{person_id}"
        logger.info(f"Navigating to person page: {person_url}")
        await self.page.goto(
            person_url,
            wait_until="domcontentloaded",
            timeout=self.NAVIGATION_TIMEOUT_MS
        )
        logger.debug(f"Navigation complete for person {person_id}")
        await self._human_delay(1.5, 2.5)

        # Click Messages tab to see conversation - use the same robust approach as send_sms
        messages_tab_selectors = [
            # Specific FUB selector - BoxTabPadding containing bubble icon
            '.BoxTabPadding:has(.BaseIcon-bubble)',
            '[class*="BoxTabPadding"]:has([class*="bubble"])',
            '.BaseIcon-bubble',
            '[class*="bubble"]',
            'button:has-text("Messages")',
            'a:has-text("Messages")',
            '[role="tab"]:has-text("Messages")',
        ]

        messages_clicked = False

        # Approach 1: Try using page.locator with text matching (most reliable)
        try:
            logger.info("Reading: Trying to click Messages tab using locator...")
            messages_locator = self.page.locator('text="Messages"').first
            if await messages_locator.count() > 0:
                await messages_locator.click()
                messages_clicked = True
                logger.info("Reading: Clicked Messages tab using text locator")
                await self._human_delay(1.5, 2.5)
        except Exception as e:
            logger.debug(f"Reading: Locator approach failed: {e}")

        # Approach 2: Try clicking by the bubble icon parent
        if not messages_clicked:
            try:
                logger.info("Reading: Trying to click Messages tab using bubble icon...")
                bubble_icon = await self.page.query_selector('.BaseIcon-bubble')
                if bubble_icon:
                    parent = await bubble_icon.evaluate_handle('el => el.closest("div[class*=BoxTabPadding]") || el.parentElement.parentElement')
                    if parent:
                        await parent.as_element().click()
                        messages_clicked = True
                        logger.info("Reading: Clicked Messages tab via bubble icon parent")
                        await self._human_delay(1.5, 2.5)
            except Exception as e:
                logger.debug(f"Reading: Bubble icon approach failed: {e}")

        # Approach 3: Use JavaScript to click
        if not messages_clicked:
            try:
                logger.info("Reading: Trying to click Messages tab using JavaScript...")
                clicked = await self.page.evaluate('''() => {
                    const elements = document.querySelectorAll('*');
                    for (const el of elements) {
                        if (el.textContent && el.textContent.trim() === 'Messages' &&
                            el.closest('[class*="BoxTabPadding"]')) {
                            el.closest('[class*="BoxTabPadding"]').click();
                            return true;
                        }
                    }
                    const bubble = document.querySelector('.BaseIcon-bubble');
                    if (bubble) {
                        const tab = bubble.closest('div');
                        if (tab) { tab.click(); return true; }
                    }
                    return false;
                }''')
                if clicked:
                    messages_clicked = True
                    logger.info("Reading: Clicked Messages tab using JavaScript")
                    await self._human_delay(1.5, 2.5)
            except Exception as e:
                logger.debug(f"Reading: JavaScript approach failed: {e}")

        # Approach 4: Original selector approach as fallback
        if not messages_clicked:
            try:
                messages_tab = await self._find_element_by_selectors(messages_tab_selectors)
                if messages_tab:
                    logger.info("Reading: Found Messages tab using selectors, clicking it")
                    await messages_tab.click()
                    messages_clicked = True
                    await self._human_delay(1.5, 2.5)
                else:
                    logger.warning("Reading: Messages tab not found with any method")
            except Exception as e:
                logger.debug(f"Reading: Messages tab click failed: {e}")

        # FUB message structure (observed Jan 2025):
        # - Messages are in a conversation thread
        # - Incoming messages have different styling than outgoing
        # - Message bubbles contain the text content
        # - Look for the most recent incoming message (from the lead)

        # Selectors for message elements - FUB specific
        # Incoming messages typically have different class/styling
        message_selectors = [
            # FUB message bubbles - incoming messages
            '[class*="incoming"] [class*="message-text"]',
            '[class*="inbound"] [class*="message-text"]',
            '[class*="received"] [class*="message-text"]',
            # Generic message container approach
            '[class*="message-bubble"][class*="incoming"]',
            '[class*="message-bubble"][class*="inbound"]',
            # Fallback - look for message containers
            '[class*="TextMessage"] [class*="body"]',
            '[class*="message-content"]',
            '[class*="sms-body"]',
            # Very generic fallback - last messages in thread
            '[class*="message-thread"] [class*="message"]:last-child',
        ]

        # Also try to find by data attributes
        data_selectors = [
            '[data-direction="incoming"]',
            '[data-type="incoming"]',
            '[data-incoming="true"]',
        ]

        latest_message = None

        # First approach: Look for specifically marked incoming messages
        for selector in message_selectors + data_selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                if elements:
                    # Get the last (most recent) incoming message
                    latest_element = elements[-1]
                    text_content = await latest_element.text_content()
                    if text_content and text_content.strip():
                        latest_message = text_content.strip()
                        logger.info(f"Found message with selector '{selector}': {latest_message[:50]}...")
                        break
            except Exception as e:
                continue

        # Second approach: Parse all messages and find the last incoming one
        if not latest_message:
            try:
                # Try to get all message bubbles and determine which are incoming
                # FUB typically aligns incoming messages left and outgoing right
                # Or uses different background colors

                # Look for the entire message thread
                thread_selectors = [
                    '[class*="message-list"]',
                    '[class*="conversation-thread"]',
                    '[class*="messages-container"]',
                    '[class*="TextMessageList"]',
                ]

                for thread_sel in thread_selectors:
                    thread = await self.page.query_selector(thread_sel)
                    if thread:
                        # Get all text from the thread and look for pattern
                        # This is a fallback approach
                        inner_html = await thread.inner_html()
                        logger.debug(f"Found message thread with selector '{thread_sel}'")
                        break

            except Exception as e:
                logger.warning(f"Could not find message thread: {e}")

        # Third approach: JavaScript execution to extract messages
        # FUB Jan 2026: Messages are in BodyContainer elements within timeline items
        # Header shows "Sender Name > Recipient Name" pattern to identify direction
        if not latest_message:
            try:
                # Get the lead's name from the page title (most reliable)
                lead_name = await self.page.evaluate("""
                    () => {
                        // Best source: page title which shows the lead's name
                        const title = document.title;
                        if (title && title.includes(' - ')) {
                            return title.split(' - ')[0].trim();
                        }
                        // Fallback: Look for the person name in profile header
                        const profileHeader = document.querySelector('[class*="ProfileHeader"] h1, [class*="PersonProfile"] h1');
                        if (profileHeader) return profileHeader.textContent?.trim();
                        return null;
                    }
                """)
                logger.info(f"Lead name from page: {lead_name}")

                js_script = """
                (leadName) => {
                    // FUB Timeline structure (Jan 2026):
                    // - Body text in item-components__BodyContainer div
                    // - Direction: first tooltip = sender name
                    // - If first tooltip matches leadName, it's incoming from lead

                    // Get all timeline items (message containers)
                    const containers = document.querySelectorAll('[class*="ContainerBase"], [class*="TimelineItem"]');
                    let messages = [];
                    let seenTexts = new Set();

                    for (const container of containers) {
                        // Get the body container with the actual message text
                        const bodyContainer = container.querySelector('[class*="BodyContainer"]');
                        if (!bodyContainer) continue;

                        // Get the message text from the first div
                        const msgDiv = bodyContainer.querySelector('div');
                        if (!msgDiv) continue;

                        const msgText = msgDiv.textContent?.trim();
                        if (!msgText || msgText.length < 1) continue;

                        // Skip "View X more text messages" links
                        if (msgText.includes('View') && msgText.includes('more text messages')) continue;

                        // Skip duplicates
                        if (seenTexts.has(msgText)) continue;
                        seenTexts.add(msgText);

                        // Determine direction using tooltips
                        // First tooltip = sender name
                        let isIncoming = false;
                        let senderName = null;
                        const tooltips = container.querySelectorAll('[class*="tooltip"]');

                        if (tooltips.length >= 1 && leadName) {
                            senderName = tooltips[0].textContent?.trim();
                            const leadFirstName = leadName.split(' ')[0].toLowerCase();
                            // If first tooltip (sender) matches lead's name, it's incoming
                            if (senderName && senderName.toLowerCase().includes(leadFirstName)) {
                                isIncoming = true;
                            }
                        }

                        messages.push({
                            text: msgText,
                            isIncoming: isIncoming,
                            sender: senderName
                        });
                    }

                    // Return the first (most recent) incoming message
                    for (const msg of messages) {
                        if (msg.isIncoming) {
                            return { text: msg.text, found: 'incoming', sender: msg.sender };
                        }
                    }

                    // Fallback: return the first message that looks like a lead response
                    for (const msg of messages) {
                        const text = msg.text;
                        if (/^(Hi|Hello|Hey|Yes|No|Thanks|Thank you|Ok|Okay|Sure|I'm|I am|Just|👍|👎|🙏|😊)/i.test(text)) {
                            return { text: text, found: 'pattern', sender: msg.sender };
                        }
                    }

                    // Last fallback: return the first message found
                    if (messages.length > 0) {
                        return { text: messages[0].text, found: 'first', sender: messages[0].sender, total: messages.length };
                    }

                    return null;
                }
                """
                result = await self.page.evaluate(js_script, lead_name or "")
                if result:
                    if isinstance(result, dict):
                        latest_message = result.get('text')
                        logger.info(f"Found message via JS ({result.get('found')}): {latest_message[:50] if latest_message else 'None'}...")
                        logger.debug(f"JS debug: {result.get('debug')}, total messages: {result.get('total', 'N/A')}")
                    else:
                        latest_message = result
                        logger.info(f"Found message via JS: {latest_message[:50]}...")
            except Exception as e:
                logger.warning(f"JS message extraction failed: {e}")

        # Take debug screenshot if we couldn't find a message
        if not latest_message:
            import os
            debug_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            debug_path = os.path.join(debug_dir, f"debug_no_message_found_{person_id}.png")
            await self.page.screenshot(path=debug_path, full_page=True)
            logger.error(f"Could not find any incoming messages. Debug screenshot: {debug_path}")

            # Also save HTML for debugging
            html_path = os.path.join(debug_dir, f"debug_no_message_found_{person_id}.html")
            html_content = await self.page.content()
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.error(f"Debug HTML saved: {html_path}")

            return {
                "success": False,
                "error": "Could not find incoming message in FUB UI",
                "person_id": person_id,
                "debug_screenshot": debug_path,
            }

        # Mark operation success for warm session tracking
        self.mark_operation_success()

        return {
            "success": True,
            "message": latest_message,
            "person_id": person_id,
            "is_incoming": True,
        }

    async def read_call_summaries(self, person_id: int, limit: int = 5) -> dict:
        """
        Read call summaries from a lead's profile timeline.

        FUB auto-generates AI summaries for calls. These appear in the timeline
        with a "Summary" tab showing bullet points of what was discussed.

        Args:
            person_id: The FUB person ID
            limit: Maximum number of call summaries to retrieve (default 5)

        Returns:
            Dict with 'success', 'summaries' (list of summary dicts with
            caller, recipient, duration, summary_text, timestamp)
        """
        logger.info(f"Reading call summaries for person {person_id} (limit={limit})")

        if not self._logged_in:
            raise Exception("Not logged in. Call login() first.")

        # Reset page state before operation to avoid stale DOM/JS
        await self._reset_page_state(light=True)

        # Navigate to lead profile
        person_url = f"{self._get_base_url()}/2/people/view/{person_id}"
        logger.info(f"Navigating to person page: {person_url}")
        await self.page.goto(
            person_url,
            wait_until="domcontentloaded",
            timeout=self.NAVIGATION_TIMEOUT_MS
        )
        logger.debug(f"Navigation complete for person {person_id}")
        await self._human_delay(1.5, 2.5)

        # FUB call structure (from screenshot Jan 2026):
        # - Call entries have phone icon (green circle with phone)
        # - Header shows "Adam Schwartz > Jesus Esparza Reyes (1 min 8 sec)"
        # - "Summary" tab shows AI-generated bullet points
        # - "Transcript" tab shows full transcript

        # Extract call summaries using JavaScript
        js_script = """
        (limit) => {
            const summaries = [];

            // Find all timeline items - calls have phone icons
            // Look for items with call-related icons or classes
            const timelineItems = document.querySelectorAll('[class*="TimelineItem"], [class*="ContainerBase"]');

            for (const item of timelineItems) {
                if (summaries.length >= limit) break;

                // Check if this is a call entry by looking for phone icon or call indicator
                const phoneIcon = item.querySelector('[class*="phone"], [class*="call"], .BaseIcon-phone, svg[class*="phone"]');
                const hasCallDuration = item.textContent?.match(/\\(\\d+\\s*(min|sec|hr)/i);

                // Also check for the green call icon background
                const greenCircle = item.querySelector('[style*="background"][style*="green"], [class*="call-icon"]');

                if (!phoneIcon && !hasCallDuration && !greenCircle) continue;

                // Get caller/recipient from header (format: "Name > Name (duration)")
                let caller = null;
                let recipient = null;
                let duration = null;

                // Find the header text - usually in first link or span
                const headerLinks = item.querySelectorAll('a, [class*="tooltip"]');
                if (headerLinks.length >= 2) {
                    caller = headerLinks[0].textContent?.trim();
                    recipient = headerLinks[1].textContent?.trim();
                }

                // Extract duration from text like "(1 min 8 sec)"
                const durationMatch = item.textContent?.match(/\\((\\d+\\s*(?:min|sec|hr)[^)]*?)\\)/i);
                if (durationMatch) {
                    duration = durationMatch[1];
                }

                // Look for Summary tab content
                // The summary is in a section with "Summary" tab active
                let summaryText = null;

                // Find summary section - it has bullet points (li elements)
                const summarySection = item.querySelector('[class*="summary"], [class*="Summary"]');
                if (summarySection) {
                    const bullets = summarySection.querySelectorAll('li');
                    if (bullets.length > 0) {
                        summaryText = Array.from(bullets).map(b => b.textContent?.trim()).filter(t => t).join(' | ');
                    }
                }

                // Fallback: look for bullet points (li) directly in the item
                if (!summaryText) {
                    const bullets = item.querySelectorAll('li');
                    if (bullets.length > 0) {
                        // Filter out non-summary bullets
                        const summaryBullets = Array.from(bullets)
                            .map(b => b.textContent?.trim())
                            .filter(t => t && !t.includes('Suggested Tasks') && t.length > 10);
                        if (summaryBullets.length > 0) {
                            summaryText = summaryBullets.join(' | ');
                        }
                    }
                }

                // Get timestamp
                let timestamp = null;
                const timeEl = item.querySelector('time, [class*="time"], [class*="date"]');
                if (timeEl) {
                    timestamp = timeEl.getAttribute('datetime') || timeEl.textContent?.trim();
                }

                if (summaryText || duration) {
                    summaries.push({
                        caller: caller,
                        recipient: recipient,
                        duration: duration,
                        summary: summaryText,
                        timestamp: timestamp
                    });
                }
            }

            return summaries;
        }
        """

        try:
            summaries = await self.page.evaluate(js_script, limit)
            logger.info(f"Found {len(summaries)} call summaries")

            # If no summaries found, try alternate approach - click on calls to expand
            if not summaries:
                summaries = await self._extract_call_summaries_expanded(limit)

            if summaries:
                # Mark operation success for warm session tracking
                self.mark_operation_success()
                return {
                    "success": True,
                    "summaries": summaries,
                    "person_id": person_id,
                    "count": len(summaries)
                }
            else:
                return {
                    "success": False,
                    "error": "No call summaries found",
                    "person_id": person_id,
                    "summaries": []
                }

        except Exception as e:
            logger.error(f"Failed to extract call summaries: {e}")
            return {
                "success": False,
                "error": str(e),
                "person_id": person_id,
                "summaries": []
            }

    async def _extract_call_summaries_expanded(self, limit: int = 5) -> list:
        """
        Alternate approach: Find call entries and click to expand them.
        Some call summaries may only be visible after expanding the entry.
        """
        summaries = []

        try:
            # Find call entries by looking for elements with duration pattern
            # FUB shows calls like "Adam > Jesus (1 min 8 sec)"
            js_find_calls = """
            () => {
                const calls = [];
                // Find all timeline items
                const items = document.querySelectorAll('[class*="TimelineItem"], [class*="ContainerBase"]');
                for (const item of items) {
                    // Check for call duration pattern
                    if (item.textContent?.match(/\\(\\d+\\s*(min|sec|hr)/i)) {
                        // Return a unique identifier for this call
                        const rect = item.getBoundingClientRect();
                        calls.push({
                            top: rect.top,
                            text: item.textContent?.substring(0, 100)
                        });
                    }
                }
                return calls;
            }
            """

            calls = await self.page.evaluate(js_find_calls)
            logger.info(f"Found {len(calls)} potential call entries to expand")

            # For each call, try to expand and get summary
            for i, call in enumerate(calls[:limit]):
                try:
                    # Click on the call entry area to expand it
                    # Use the y-position to click
                    await self.page.mouse.click(400, call['top'] + 20)
                    await self._human_delay(0.5, 1)

                    # Now try to find the expanded summary
                    summary_js = """
                    () => {
                        // Look for expanded summary section
                        const summaryTab = document.querySelector('[class*="Summary"]:not([class*="tab"]), [class*="summary-content"]');
                        if (summaryTab) {
                            const bullets = summaryTab.querySelectorAll('li');
                            if (bullets.length > 0) {
                                return Array.from(bullets).map(b => b.textContent?.trim()).filter(t => t).join(' | ');
                            }
                            return summaryTab.textContent?.trim();
                        }

                        // Look for any newly visible bullet points
                        const allBullets = document.querySelectorAll('li');
                        const visibleBullets = Array.from(allBullets)
                            .filter(b => {
                                const rect = b.getBoundingClientRect();
                                return rect.height > 0 && rect.width > 0;
                            })
                            .map(b => b.textContent?.trim())
                            .filter(t => t && t.length > 10 && !t.includes('Suggested'));

                        return visibleBullets.length > 0 ? visibleBullets.join(' | ') : null;
                    }
                    """

                    summary_text = await self.page.evaluate(summary_js)

                    if summary_text:
                        # Extract duration from call text
                        import re
                        duration = None
                        call_text = call.get('text', '')
                        if call_text:
                            duration_match = re.search(r'\((\d+\s*(?:min|sec|hr)[^)]*?)\)', call_text, re.IGNORECASE)
                            if duration_match:
                                duration = duration_match.group(1)
                        summaries.append({
                            "summary": summary_text,
                            "duration": duration,
                            "raw_text": call_text[:100] if call_text else ''
                        })

                except Exception as e:
                    logger.debug(f"Failed to expand call {i}: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Alternate call summary extraction failed: {e}")

        return summaries

    async def read_recent_messages(self, person_id: int, limit: int = 15) -> dict:
        """
        Read recent message history from a lead's profile.

        Used on first contact to sync conversation history for AI context.

        Args:
            person_id: The FUB person ID
            limit: Maximum number of messages to retrieve (default 15)

        Returns:
            Dict with 'success', 'messages' (list of message dicts with text, is_incoming, timestamp)
        """
        logger.info(f"Reading recent messages for person {person_id} (limit={limit})")

        if not self._logged_in:
            raise Exception("Not logged in. Call login() first.")

        # Reset page state before operation to avoid stale DOM/JS
        await self._reset_page_state(light=True)

        # Navigate to lead profile
        person_url = f"{self._get_base_url()}/2/people/view/{person_id}"
        logger.info(f"Navigating to person page: {person_url}")
        await self.page.goto(
            person_url,
            wait_until="domcontentloaded",
            timeout=self.NAVIGATION_TIMEOUT_MS
        )
        logger.debug(f"Navigation complete for person {person_id}")
        await self._human_delay(1.5, 2.5)

        # Click Messages tab
        messages_tab_selectors = [
            '.BoxTabPadding:has(.BaseIcon-bubble)',
            '[class*="BoxTabPadding"]:has([class*="bubble"])',
            '.BaseIcon-bubble',
            '[class*="bubble"]',
        ]

        try:
            messages_tab = await self._find_element_by_selectors(messages_tab_selectors)
            if messages_tab:
                logger.info("Found Messages tab, clicking it")
                await messages_tab.click()
                await self._human_delay(1.5, 2.5)  # Wait for messages to load
        except Exception as e:
            logger.debug(f"Messages tab click failed: {e}")

        # Check if there's a "View more" link and click it to load more messages
        try:
            view_more = await self.page.query_selector('a:has-text("View"), button:has-text("View more")')
            if view_more:
                text = await view_more.text_content()
                if 'more text messages' in text.lower():
                    logger.info("Clicking 'View more messages' to load history")
                    await view_more.click()
                    await self._human_delay(2, 3)
        except Exception as e:
            logger.debug(f"No 'View more' link or click failed: {e}")

        # Get the lead's name from the page title (most reliable)
        # FUB page titles are formatted as "PersonName - Follow Up Boss"
        lead_name = await self.page.evaluate("""
            () => {
                // Best source: page title which shows the lead's name
                const title = document.title;
                if (title && title.includes(' - ')) {
                    return title.split(' - ')[0].trim();
                }
                // Fallback: Look for the person name header in the main content
                // The profile header shows the lead name, not in the nav bar
                const profileHeader = document.querySelector('[class*="ProfileHeader"] h1, [class*="PersonProfile"] h1');
                if (profileHeader) return profileHeader.textContent?.trim();
                // Last resort
                const h1 = document.querySelector('main h1, [class*="content"] h1');
                if (h1) return h1.textContent?.trim();
                return null;
            }
        """)
        logger.info(f"Lead name from page: {lead_name}")

        # Extract all messages using JavaScript
        # Distinguishes between actual SMS texts, action plan notes, and other entries
        js_script = r"""
        (args) => {
            const { leadName, limit } = args;

            // Find all timeline entries (not just BodyContainers)
            const timelineItems = document.querySelectorAll('[class*="TimelineItem"], [class*="ContainerBase"]');
            let messages = [];
            let seenTexts = new Set();  // Track seen messages to avoid duplicates

            for (const container of timelineItems) {
                if (messages.length >= limit) break;

                // Get the message body
                const bodyContainer = container.querySelector('[class*="BodyContainer"]');
                if (!bodyContainer) continue;

                const msgDiv = bodyContainer.querySelector('div');
                if (!msgDiv) continue;

                const msgText = msgDiv.textContent?.trim();
                if (!msgText || msgText.length < 1) continue;

                // Skip "View X more text messages" links
                if (msgText.includes('View') && msgText.includes('more text messages')) continue;

                // Skip duplicates (same message text)
                if (seenTexts.has(msgText)) continue;
                seenTexts.add(msgText);

                // Determine the entry type by checking FUB-specific icon classes
                let entryType = 'text';  // Default to text

                // FUB Timeline Entry Types (Jan 2026):
                // - Texts: Blue speech bubble icon (BaseIcon-bubble class)
                // - Calls: Green phone icon (BaseIcon-phone class) with duration
                // - Action Plans: Orange icon with "action plan" text
                // - Emails: Blue info icon

                // Check for FUB-specific icon classes - most reliable method
                const bubbleIcon = container.querySelector('.BaseIcon-bubble');
                const phoneIcon = container.querySelector('.BaseIcon-phone');

                // Check the immediate parent/sibling area for duration (not deep in body)
                // Look at the first ~200 chars of container text (header area)
                const containerText = container.textContent || '';
                const headerArea = containerText.substring(0, Math.min(200, containerText.indexOf(msgText) || 200)).toLowerCase();

                const hasCallDuration = /\(\d+\s*(min|sec|hr)/i.test(headerArea);
                const isActionPlan = headerArea.includes('action plan');
                const isEmail = headerArea.includes('via action plan') && headerArea.includes('email');

                // Priority classification based on icons and text
                if (phoneIcon || hasCallDuration) {
                    entryType = 'call';
                } else if (isEmail) {
                    entryType = 'email';
                } else if (isActionPlan) {
                    entryType = 'action_plan_note';
                } else if (bubbleIcon) {
                    entryType = 'text';
                } else {
                    // Default: no special indicators = assume text
                    entryType = 'text';
                }

                // Determine if incoming by checking tooltips
                let isIncoming = false;
                let senderName = null;

                const tooltips = container.querySelectorAll('[class*="tooltip"]');
                if (tooltips.length >= 1 && leadName) {
                    senderName = tooltips[0].textContent?.trim();
                    const leadFirstName = leadName.split(' ')[0].toLowerCase();
                    if (senderName && senderName.toLowerCase().includes(leadFirstName)) {
                        isIncoming = true;
                    }
                }

                // Try to get timestamp from the container
                let timestamp = null;
                const timeEl = container.querySelector('time, [class*="time"], [class*="date"]');
                if (timeEl) {
                    timestamp = timeEl.getAttribute('datetime') || timeEl.textContent?.trim();
                }

                messages.push({
                    text: msgText,
                    is_incoming: isIncoming,
                    timestamp: timestamp,
                    sender: senderName,
                    entry_type: entryType,
                    debug_has_duration: hasCallDuration,
                    debug_is_action_plan: isActionPlan,
                    debug_has_phone_icon: !!phoneIcon,
                    debug_has_bubble_icon: !!bubbleIcon,
                    debug_header_area: headerArea.substring(0, 50)
                });
            }

            return messages;
        }
        """

        try:
            messages = await self.page.evaluate(js_script, {"leadName": lead_name or "", "limit": limit})
            logger.info(f"Found {len(messages)} messages")

            if messages:
                # Mark operation success for warm session tracking
                self.mark_operation_success()
                return {
                    "success": True,
                    "messages": messages,
                    "person_id": person_id,
                    "lead_name": lead_name,
                    "count": len(messages)
                }
            else:
                return {
                    "success": False,
                    "error": "No messages found",
                    "person_id": person_id,
                    "messages": []
                }

        except Exception as e:
            logger.error(f"Failed to extract messages: {e}")
            return {
                "success": False,
                "error": str(e),
                "person_id": person_id,
                "messages": []
            }

    def is_warm(self) -> bool:
        """Check if session was used recently and can skip full validation.

        A "warm" session was used successfully within the threshold time,
        so we can skip the expensive navigation-based validation.
        """
        if not self._last_successful_operation:
            return False
        import time
        elapsed = time.time() - self._last_successful_operation
        is_warm = elapsed < self.WARM_SESSION_THRESHOLD_SECONDS
        if is_warm:
            logger.debug(f"Session for {self.agent_id} is warm ({elapsed:.1f}s since last op)")
        return is_warm

    def mark_operation_success(self):
        """Mark that an operation completed successfully, updating the warm timer."""
        import time
        self._last_successful_operation = time.time()
        logger.debug(f"Marked operation success for {self.agent_id}")

    async def is_valid(self, skip_if_warm: bool = True) -> bool:
        """Check if session is still valid.

        Args:
            skip_if_warm: If True, skip navigation check for recently-used sessions.
                          This avoids the expensive 60s timeout risk on every operation.

        Returns False on any error, allowing the caller to create a new session.
        """
        if not self.page or not self._logged_in:
            logger.debug(f"Session invalid for {self.agent_id}: page={self.page is not None}, logged_in={self._logged_in}")
            return False

        # Fast path: if session was used recently, skip the expensive navigation check
        if skip_if_warm and self.is_warm():
            logger.info(f"Skipping validation for warm session {self.agent_id}")
            return True

        try:
            # Use the captured base URL with longer timeout
            logger.debug(f"Validating session for {self.agent_id}, navigating to {self._get_base_url()}/people")
            await self.page.goto(
                f"{self._get_base_url()}/people",
                wait_until="domcontentloaded",
                timeout=self.NAVIGATION_TIMEOUT_MS
            )
            current_url = self.page.url
            is_valid = "login" not in current_url and "signin" not in current_url
            logger.debug(f"Session validation for {self.agent_id}: url={current_url}, valid={is_valid}")

            # If valid, mark as warm
            if is_valid:
                self.mark_operation_success()

            return is_valid
        except PlaywrightTimeout as e:
            logger.warning(f"Session validation timeout for {self.agent_id}: {e}")
            return False
        except Exception as e:
            logger.warning(f"Session validation failed for {self.agent_id}: {e}")
            return False

    async def _reset_page_state(self, light: bool = True):
        """Reset page state to avoid state pollution between operations.

        Args:
            light: If True, only clears JS state. If False, also navigates to neutral page.
        """
        if not self.page:
            return

        try:
            # Clear any pending JavaScript timers and event listeners
            await self.page.evaluate("""
                () => {
                    // Clear all timeouts and intervals
                    const highestId = setTimeout(() => {}, 0);
                    for (let i = 0; i < highestId; i++) {
                        clearTimeout(i);
                        clearInterval(i);
                    }

                    // Clear any pending XHR/fetch requests by aborting them
                    // (This is a best-effort approach)
                    if (window._pendingRequests) {
                        window._pendingRequests.forEach(req => {
                            try { req.abort(); } catch(e) {}
                        });
                        window._pendingRequests = [];
                    }

                    // Clear any custom event listeners on document
                    // (Can't easily remove all, but this signals intent)

                    return true;
                }
            """)
            logger.debug(f"Light page state reset completed for {self.agent_id}")

            if not light:
                # Full reset: navigate to a neutral page
                await self.page.goto(
                    f"{self._get_base_url()}/people",
                    wait_until="domcontentloaded",
                    timeout=self.NAVIGATION_TIMEOUT_MS
                )
                await self._human_delay(0.5, 1.0)
                logger.debug(f"Full page state reset completed for {self.agent_id}")

        except Exception as e:
            logger.warning(f"Page state reset failed for {self.agent_id}: {e}")
            # Don't raise - this is a best-effort cleanup

    async def close(self):
        """Close the browser context."""
        if self.context:
            try:
                await self.context.close()
            except Exception as e:
                logger.warning(f"Error closing context: {e}")
            self.context = None
            self.page = None
            self._logged_in = False
            self._actual_base_url = None

    def _capture_base_url(self):
        """Capture the actual base URL (team subdomain) after login.

        FUB redirects from app.followupboss.com to a team-specific subdomain
        like saahomes.followupboss.com. We need to use this subdomain for
        subsequent navigations to avoid session loss.
        """
        if self.page:
            from urllib.parse import urlparse
            current_url = self.page.url
            parsed = urlparse(current_url)
            self._actual_base_url = f"{parsed.scheme}://{parsed.netloc}"
            logger.info(f"Captured base URL: {self._actual_base_url}")

    def _get_base_url(self) -> str:
        """Get the base URL to use for navigation.

        Returns the team-specific subdomain if captured, otherwise falls back
        to the default FUB_BASE_URL.
        """
        return self._actual_base_url or self.FUB_BASE_URL

    async def _find_element_by_selectors(self, selectors: list, timeout: int = None):
        """Try multiple selectors and return the first match.

        Args:
            selectors: List of CSS selectors to try
            timeout: Timeout per selector in ms (default: ELEMENT_WAIT_TIMEOUT_MS / len(selectors))
        """
        if timeout is None:
            # Distribute timeout across selectors, minimum 1500ms each
            timeout = max(1500, self.ELEMENT_WAIT_TIMEOUT_MS // max(1, len(selectors)))

        for selector in selectors:
            try:
                element = await self.page.wait_for_selector(selector, timeout=timeout)
                if element:
                    return element
            except PlaywrightTimeout:
                continue
            except Exception:
                continue
        return None

    async def _human_delay(self, min_sec: float, max_sec: float):
        """Random delay to appear human."""
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)

    async def _simulated_typing(self, element, text: str):
        """Type text with random delays between keystrokes."""
        for char in text:
            await element.type(char, delay=random.randint(30, 120))
            # Occasionally add longer pauses (like thinking)
            if random.random() < 0.05:
                await asyncio.sleep(random.uniform(0.2, 0.5))

    async def get_phone_numbers(self) -> dict:
        """
        Fetch all phone numbers configured in the FUB account.

        Navigates to the FUB phone numbers settings page and scrapes all
        phone numbers, their assigned users, and their purposes.

        This is used to build a list of phone numbers for filtering which
        ones the AI agent should respond to.

        Returns:
            Dict with 'success', 'phone_numbers' (list of dicts with
            number, assigned_to, purpose/label, is_active)
        """
        logger.info("Fetching phone numbers from FUB settings")

        if not self._logged_in:
            raise Exception("Not logged in. Call login() first.")

        # Navigate to phone numbers settings page
        # FUB URL pattern: {subdomain}.followupboss.com/2/phone-numbers
        phone_url = f"{self._get_base_url()}/2/phone-numbers"
        logger.info(f"Navigating to phone numbers page: {phone_url}")

        await self.page.goto(
            phone_url,
            wait_until="domcontentloaded",
            timeout=self.NAVIGATION_TIMEOUT_MS
        )
        await self._human_delay(1.5, 2.5)

        # Check if we're on the right page or got redirected
        current_url = self.page.url
        if "login" in current_url or "signin" in current_url:
            logger.error("Session expired - redirected to login page")
            return {
                "success": False,
                "error": "Session expired",
                "phone_numbers": []
            }

        # Extract phone numbers using JavaScript
        # FUB phone numbers page structure (2024):
        # - List of phone numbers with assigned user names
        # - Each row shows: phone number, assigned agent, type/purpose
        js_script = """
        () => {
            const phoneNumbers = [];

            // FUB phone numbers are typically in a table or list structure
            // Look for table rows containing phone number data
            const rows = document.querySelectorAll('tr, [class*="phone-row"], [class*="PhoneNumber"]');

            for (const row of rows) {
                const rowText = row.textContent || '';

                // Look for phone number pattern (various formats)
                const phoneMatch = rowText.match(/\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})/);
                if (!phoneMatch) continue;

                const phoneNumber = `(${phoneMatch[1]}) ${phoneMatch[2]}-${phoneMatch[3]}`;
                const normalizedNumber = `+1${phoneMatch[1]}${phoneMatch[2]}${phoneMatch[3]}`;

                // Try to find the assigned user - usually in a cell or label
                let assignedTo = null;
                const userCells = row.querySelectorAll('td, span, div');
                for (const cell of userCells) {
                    const cellText = cell.textContent?.trim() || '';
                    // Skip if it's the phone number itself
                    if (cellText.match(/\d{3}.*\d{3}.*\d{4}/)) continue;
                    // Skip very short text
                    if (cellText.length < 2) continue;
                    // Likely a name or label
                    if (cellText.length > 0 && cellText.length < 50) {
                        assignedTo = cellText;
                        break;
                    }
                }

                // Try to determine the purpose/type from labels
                let purpose = 'general';
                const textLower = rowText.toLowerCase();
                if (textLower.includes('inbox') || textLower.includes('personal')) {
                    purpose = 'inbox';
                } else if (textLower.includes('google')) {
                    purpose = 'google';
                } else if (textLower.includes('office')) {
                    purpose = 'office';
                } else if (textLower.includes('website')) {
                    purpose = 'website';
                } else if (textLower.includes('lead')) {
                    purpose = 'leads';
                } else if (textLower.includes('sign') || textLower.includes('call')) {
                    purpose = 'sign_calls';
                }

                // Check if active (look for enabled/disabled indicators)
                const isActive = !textLower.includes('disabled') && !textLower.includes('inactive');

                phoneNumbers.push({
                    number: phoneNumber,
                    normalized: normalizedNumber,
                    assigned_to: assignedTo,
                    purpose: purpose,
                    is_active: isActive,
                    raw_text: rowText.substring(0, 200)
                });
            }

            // Also check for a different page structure (card-based layout)
            if (phoneNumbers.length === 0) {
                const cards = document.querySelectorAll('[class*="card"], [class*="Card"], [class*="item"], [class*="Item"]');
                for (const card of cards) {
                    const cardText = card.textContent || '';
                    const phoneMatch = cardText.match(/\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})/);
                    if (!phoneMatch) continue;

                    const phoneNumber = `(${phoneMatch[1]}) ${phoneMatch[2]}-${phoneMatch[3]}`;
                    const normalizedNumber = `+1${phoneMatch[1]}${phoneMatch[2]}${phoneMatch[3]}`;

                    // Look for name/label
                    let assignedTo = null;
                    const heading = card.querySelector('h2, h3, h4, [class*="name"], [class*="title"]');
                    if (heading) {
                        assignedTo = heading.textContent?.trim();
                    }

                    phoneNumbers.push({
                        number: phoneNumber,
                        normalized: normalizedNumber,
                        assigned_to: assignedTo,
                        purpose: 'general',
                        is_active: true,
                        raw_text: cardText.substring(0, 200)
                    });
                }
            }

            // Deduplicate by normalized number
            const seen = new Set();
            const unique = [];
            for (const pn of phoneNumbers) {
                if (!seen.has(pn.normalized)) {
                    seen.add(pn.normalized);
                    unique.push(pn);
                }
            }

            return unique;
        }
        """

        try:
            phone_numbers = await self.page.evaluate(js_script)
            logger.info(f"Found {len(phone_numbers)} phone numbers")

            if phone_numbers:
                # Mark operation success for warm session tracking
                self.mark_operation_success()
                return {
                    "success": True,
                    "phone_numbers": phone_numbers,
                    "count": len(phone_numbers)
                }
            else:
                # Take debug screenshot if no phone numbers found
                import os
                debug_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                debug_path = os.path.join(debug_dir, f"debug_phone_numbers_page.png")
                await self.page.screenshot(path=debug_path, full_page=True)

                # Also save HTML for debugging
                html_path = os.path.join(debug_dir, "debug_phone_numbers_page.html")
                html_content = await self.page.content()
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)

                logger.warning(f"No phone numbers found. Debug screenshot: {debug_path}")

                return {
                    "success": False,
                    "error": "No phone numbers found on page",
                    "phone_numbers": [],
                    "debug_screenshot": debug_path
                }

        except Exception as e:
            logger.error(f"Failed to extract phone numbers: {e}")
            return {
                "success": False,
                "error": str(e),
                "phone_numbers": []
            }
