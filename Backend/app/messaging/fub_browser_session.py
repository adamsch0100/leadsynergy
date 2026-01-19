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

    def __init__(self, browser: Browser, agent_id: str, session_store: 'SessionStore'):
        self.browser = browser
        self.agent_id = agent_id
        self.session_store = session_store
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._logged_in = False

    async def login(self, credentials: dict):
        """Login to FUB with credentials or SSO."""
        logger.info(f"Starting login for agent {self.agent_id}")

        # Try to restore session from cookies
        cookies = await self.session_store.get_cookies(self.agent_id)

        self.context = await self.browser.new_context(
            storage_state=cookies if cookies else None,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        self.page = await self.context.new_page()

        # Check if already logged in by navigating to a protected page
        try:
            await self.page.goto(f"{self.FUB_BASE_URL}/people", wait_until="domcontentloaded")
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

        except PlaywrightTimeout as e:
            logger.error(f"Timeout during login check for agent {self.agent_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error during login for agent {self.agent_id}: {e}")
            raise

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
        await self.page.goto(f"{self.FUB_BASE_URL}/login", wait_until="domcontentloaded")
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

        # Find and fill email
        email_input = await self._find_element_by_selectors(email_selectors)
        if not email_input:
            raise Exception("Could not find email input field")
        await self._simulated_typing(email_input, email)
        await self._human_delay(0.5, 1)

        # Find and fill password
        password_input = await self._find_element_by_selectors(password_selectors)
        if not password_input:
            raise Exception("Could not find password input field")
        await self._simulated_typing(password_input, password)
        await self._human_delay(0.5, 1)

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
            # Check for error message
            error_elem = await self.page.query_selector('[class*="error"], [class*="alert"]')
            error_text = await error_elem.text_content() if error_elem else "Unknown error"
            raise Exception(f"Login failed: {error_text}")

        logger.info(f"Email login successful for {email}")

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

        # Wait for redirect back to FUB
        await self.page.wait_for_url(f"{self.FUB_BASE_URL}/**", timeout=30000)
        await self._human_delay(2, 3)

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

        # Wait for redirect back to FUB
        await self.page.wait_for_url(f"{self.FUB_BASE_URL}/**", timeout=30000)
        await self._human_delay(2, 3)

        logger.info("Microsoft SSO login successful")

    async def send_text_message(self, person_id: int, message: str) -> dict:
        """Navigate to lead profile and send SMS."""
        logger.info(f"Sending SMS to person {person_id}")

        if not self._logged_in:
            raise Exception("Not logged in. Call login() first.")

        # Navigate to lead profile - FUB uses /2/people/view/{id} format
        # Note: After login, FUB redirects to customer subdomain but /2/people/view works
        person_url = f"{self.FUB_BASE_URL}/2/people/view/{person_id}"
        logger.info(f"Navigating to person page: {person_url}")
        await self.page.goto(person_url, wait_until="domcontentloaded")
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
            'button:has-text("Messages")',
            'a:has-text("Messages")',
            '[role="tab"]:has-text("Messages")',
            # The tab with bubble icon
            '.BaseIcon-bubble',
            '[class*="bubble"]',
        ]

        compose_selectors = [
            # FUB specific - "Write your text..." placeholder
            'textarea[placeholder*="Write your text"]',
            'textarea[placeholder*="Write"]',
            'textarea[placeholder*="text" i]',
            'textarea[placeholder*="message" i]',
            # Generic textarea fallback
            'textarea',
        ]

        send_selectors = [
            # FUB specific - "Send Text" button
            'button:has-text("Send Text")',
            'button:has-text("Send")',
            '[class*="send"]',
            'button[type="submit"]',
        ]

        # Step 1: Click Messages tab to open the messaging panel
        try:
            messages_tab = await self._find_element_by_selectors(messages_tab_selectors)
            if messages_tab:
                logger.info("Found Messages tab, clicking it")
                await messages_tab.click()
                await self._human_delay(1, 2)  # Wait for panel to load
            else:
                logger.info("Messages tab not found, it may already be open")
        except Exception as e:
            logger.debug(f"Messages tab click failed: {e}")

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

        logger.info(f"SMS sent successfully to person {person_id}")
        return {"success": True, "person_id": person_id, "message_length": len(message)}

    async def is_valid(self) -> bool:
        """Check if session is still valid."""
        if not self.page or not self._logged_in:
            return False
        try:
            await self.page.goto(f"{self.FUB_BASE_URL}/people", wait_until="domcontentloaded")
            current_url = self.page.url
            return "login" not in current_url and "signin" not in current_url
        except Exception as e:
            logger.warning(f"Session validation failed: {e}")
            return False

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

    async def _find_element_by_selectors(self, selectors: list):
        """Try multiple selectors and return the first match."""
        for selector in selectors:
            try:
                element = await self.page.wait_for_selector(selector, timeout=3000)
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
