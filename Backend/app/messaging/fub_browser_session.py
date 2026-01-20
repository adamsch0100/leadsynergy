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
        self._actual_base_url: Optional[str] = None  # Team subdomain URL after login

    async def login(self, credentials: dict):
        """Login to FUB with credentials or SSO."""
        logger.info(f"Starting login for agent {self.agent_id}")

        # Try to restore session from cookies
        logger.debug("Checking for saved cookies...")
        cookies = await self.session_store.get_cookies(self.agent_id)
        logger.debug(f"Cookies found: {cookies is not None}")

        logger.debug("Creating browser context...")
        self.context = await self.browser.new_context(
            storage_state=cookies if cookies else None,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        self.page = await self.context.new_page()
        logger.debug("Browser context created")

        # Check if already logged in by navigating to a protected page
        try:
            logger.debug(f"Navigating to {self.FUB_BASE_URL}/people to check login status...")
            await self.page.goto(f"{self.FUB_BASE_URL}/people", wait_until="domcontentloaded")
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
            # Check for error message
            error_elem = await self.page.query_selector('[class*="error"], [class*="alert"]')
            error_text = await error_elem.text_content() if error_elem else "Unknown error"
            raise Exception(f"Login failed: {error_text}")

        # Capture the team subdomain after successful login
        self._capture_base_url()
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

        # Navigate to lead profile - FUB uses /2/people/view/{id} format
        # Use the captured team subdomain URL to avoid session loss
        person_url = f"{self._get_base_url()}/2/people/view/{person_id}"
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

        # Navigate to lead profile - use the captured team subdomain URL
        person_url = f"{self._get_base_url()}/2/people/view/{person_id}"
        logger.info(f"Navigating to person page: {person_url}")
        await self.page.goto(person_url, wait_until="domcontentloaded")
        await self._human_delay(1.5, 2.5)

        # Click Messages tab to see conversation
        # FUB Jan 2026: Messages tab is a div with BoxTabPadding class containing BaseIcon-bubble
        messages_tab_selectors = [
            # Specific FUB selector - BoxTabPadding containing bubble icon
            '.BoxTabPadding:has(.BaseIcon-bubble)',
            '[class*="BoxTabPadding"]:has([class*="bubble"])',
            # Click the parent of the bubble icon
            '.BaseIcon-bubble',
            '[class*="bubble"]',
            # Fallback text-based selectors
            'button:has-text("Messages")',
            'a:has-text("Messages")',
            '[role="tab"]:has-text("Messages")',
        ]

        try:
            messages_tab = await self._find_element_by_selectors(messages_tab_selectors)
            if messages_tab:
                logger.info("Found Messages tab, clicking it")
                await messages_tab.click()
                await self._human_delay(1, 2)  # Wait for messages to load
        except Exception as e:
            logger.debug(f"Messages tab click failed: {e}")

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

        return {
            "success": True,
            "message": latest_message,
            "person_id": person_id,
            "is_incoming": True,
        }

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

        # Navigate to lead profile
        person_url = f"{self._get_base_url()}/2/people/view/{person_id}"
        logger.info(f"Navigating to person page: {person_url}")
        await self.page.goto(person_url, wait_until="domcontentloaded")
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
        js_script = """
        (args) => {
            const { leadName, limit } = args;

            // Find all BodyContainer elements directly - these contain the actual message text
            // Each message has exactly one BodyContainer
            const bodyContainers = document.querySelectorAll('[class*="BodyContainer"]');
            let messages = [];
            let seenTexts = new Set();  // Track seen messages to avoid duplicates

            for (const bodyContainer of bodyContainers) {
                if (messages.length >= limit) break;

                // Get the message text from the first div child
                const msgDiv = bodyContainer.querySelector('div');
                if (!msgDiv) continue;

                const msgText = msgDiv.textContent?.trim();
                if (!msgText || msgText.length < 1) continue;

                // Skip "View X more text messages" links
                if (msgText.includes('View') && msgText.includes('more text messages')) continue;

                // Skip duplicates (same message text)
                if (seenTexts.has(msgText)) continue;
                seenTexts.add(msgText);

                // Walk up to find the parent container that has the header info
                let container = bodyContainer.parentElement;
                while (container && !container.className?.includes('ContainerBase') && !container.className?.includes('TimelineItem')) {
                    container = container.parentElement;
                    if (!container || container === document.body) break;
                }

                // Determine if incoming by checking tooltips
                // First tooltip = sender name, second tooltip = recipient name
                // If first tooltip matches lead name, message is FROM the lead (incoming)
                let isIncoming = false;
                let senderName = null;

                if (container) {
                    const tooltips = container.querySelectorAll('[class*="tooltip"]');
                    if (tooltips.length >= 1 && leadName) {
                        senderName = tooltips[0].textContent?.trim();
                        const leadFirstName = leadName.split(' ')[0].toLowerCase();
                        // If first tooltip (sender) matches lead's name, it's incoming
                        if (senderName && senderName.toLowerCase().includes(leadFirstName)) {
                            isIncoming = true;
                        }
                    }
                }

                // Try to get timestamp from the container
                let timestamp = null;
                if (container) {
                    const timeEl = container.querySelector('time, [class*="time"], [class*="date"]');
                    if (timeEl) {
                        timestamp = timeEl.getAttribute('datetime') || timeEl.textContent?.trim();
                    }
                }

                messages.push({
                    text: msgText,
                    is_incoming: isIncoming,
                    timestamp: timestamp,
                    sender: senderName
                });
            }

            return messages;
        }
        """

        try:
            messages = await self.page.evaluate(js_script, {"leadName": lead_name or "", "limit": limit})
            logger.info(f"Found {len(messages)} messages")

            if messages:
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

    async def is_valid(self) -> bool:
        """Check if session is still valid."""
        if not self.page or not self._logged_in:
            return False
        try:
            # Use the captured base URL to check session validity
            await self.page.goto(f"{self._get_base_url()}/people", wait_until="domcontentloaded")
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

    async def _find_element_by_selectors(self, selectors: list, timeout: int = 1500):
        """Try multiple selectors and return the first match."""
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
