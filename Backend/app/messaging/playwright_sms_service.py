"""Playwright SMS Service - Send SMS via FUB web interface."""

from playwright.async_api import async_playwright, Browser, Playwright
from typing import Dict, Optional
import asyncio
import threading
import logging
import os

from .session_store import SessionStore
from .fub_browser_session import FUBBrowserSession

logger = logging.getLogger(__name__)


class PlaywrightSMSService:
    """Send SMS via FUB web interface using Playwright browser automation.

    CRITICAL: This service serializes ALL Playwright operations per agent to avoid
    browser conflicts. Only one operation can use the browser at a time per agent.
    Uses a simple flag-based approach instead of locks to avoid async/sync deadlocks.
    """

    # Self-healing settings
    MAX_CONSECUTIVE_FAILURES = 2  # Destroy session after this many failures

    # Login rate limiting - prevent spamming FUB with verification emails
    LOGIN_COOLDOWN_SECONDS = 600  # 10 minutes cooldown after failed login

    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.sessions: Dict[str, FUBBrowserSession] = {}  # agent_id -> session
        self.session_store = SessionStore()
        self._initialized = False
        self._init_lock = threading.Lock()  # Only for initialization
        self._agent_busy: Dict[str, bool] = {}  # Track if agent is mid-operation
        self._agent_busy_lock = threading.Lock()  # Quick lock for flag check only
        self._consecutive_failures: Dict[str, int] = {}  # Track failures per agent
        self._login_cooldown: Dict[str, float] = {}  # agent_id -> timestamp when cooldown ends

    async def initialize(self):
        """Initialize Playwright and browser instance."""
        # Quick check without lock
        if self._initialized:
            return

        # Use lock only for initialization (fast operation)
        with self._init_lock:
            if self._initialized:
                return
            await self._do_initialize()

    async def _do_initialize(self):
        """Internal initialization."""
        logger.info("Initializing Playwright SMS Service")

        self.playwright = await async_playwright().start()

        # Browser launch options
        headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"

        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-gpu',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process'
            ]
        )

        self._initialized = True
        logger.info(f"Playwright initialized (headless={headless})")

    def _try_acquire_agent(self, agent_id: str) -> bool:
        """Try to mark agent as busy. Returns True if acquired, False if already busy."""
        with self._agent_busy_lock:
            if self._agent_busy.get(agent_id, False):
                return False
            self._agent_busy[agent_id] = True
            return True

    def _release_agent(self, agent_id: str):
        """Mark agent as no longer busy."""
        with self._agent_busy_lock:
            self._agent_busy[agent_id] = False

    def _record_success(self, agent_id: str):
        """Record successful operation, resetting failure count."""
        self._consecutive_failures[agent_id] = 0
        logger.debug(f"Recorded success for {agent_id}, failure count reset")

    def _record_failure(self, agent_id: str) -> int:
        """Record failed operation, returning new failure count."""
        current = self._consecutive_failures.get(agent_id, 0)
        self._consecutive_failures[agent_id] = current + 1
        logger.warning(f"Recorded failure for {agent_id}, consecutive failures: {current + 1}")
        return current + 1

    def _is_login_on_cooldown(self, agent_id: str) -> tuple[bool, int]:
        """Check if login is on cooldown for this agent.

        Returns (is_on_cooldown, seconds_remaining)
        """
        import time
        cooldown_until = self._login_cooldown.get(agent_id, 0)
        now = time.time()
        if now < cooldown_until:
            remaining = int(cooldown_until - now)
            return True, remaining
        return False, 0

    def _set_login_cooldown(self, agent_id: str, reason: str = "login failure"):
        """Set a login cooldown for this agent to prevent spamming FUB."""
        import time
        cooldown_until = time.time() + self.LOGIN_COOLDOWN_SECONDS
        self._login_cooldown[agent_id] = cooldown_until
        logger.warning(
            f"LOGIN COOLDOWN SET for {agent_id}: No login attempts for {self.LOGIN_COOLDOWN_SECONDS}s "
            f"(reason: {reason})"
        )

    def _clear_login_cooldown(self, agent_id: str):
        """Clear login cooldown after successful login."""
        if agent_id in self._login_cooldown:
            del self._login_cooldown[agent_id]
            logger.info(f"Login cooldown cleared for {agent_id}")

    async def _force_fresh_session(self, agent_id: str):
        """Force destroy session to create fresh one on next operation."""
        logger.warning(f"Forcing fresh session for {agent_id} due to consecutive failures")
        if agent_id in self.sessions:
            try:
                await self.sessions[agent_id].close()
            except Exception as e:
                logger.warning(f"Error closing session for fresh start: {e}")
            del self.sessions[agent_id]
        # Also clear any saved cookies that might be corrupted
        try:
            await self.session_store.delete_cookies(agent_id)
            logger.info(f"Cleared saved cookies for {agent_id}")
        except Exception as e:
            logger.warning(f"Error clearing cookies: {e}")
        # Reset failure counter since we're starting fresh
        self._consecutive_failures[agent_id] = 0

    async def get_or_create_session(self, agent_id: str, credentials: dict) -> FUBBrowserSession:
        """Get existing session or create new one for agent.

        Waits if another operation is in progress for the same agent.
        """
        logger.debug(f"get_or_create_session called for agent {agent_id}")

        # Wait for agent to become available (with timeout)
        max_wait = 120  # 2 minutes max wait
        waited = 0
        while not self._try_acquire_agent(agent_id):
            if waited >= max_wait:
                raise Exception(f"Timeout waiting for agent {agent_id} to become available")
            logger.info(f"Agent {agent_id} is busy, waiting... ({waited}s)")
            await asyncio.sleep(2)
            waited += 2

        try:
            logger.debug(f"Agent {agent_id} acquired, proceeding...")

            # Check for existing valid session
            if agent_id in self.sessions:
                logger.debug(f"Found existing session for agent {agent_id}, checking validity...")
                session = self.sessions[agent_id]
                try:
                    if await session.is_valid():
                        logger.debug(f"Reusing existing session for agent {agent_id}")
                        return session
                    else:
                        logger.debug(f"Session expired for agent {agent_id}, closing...")
                except Exception as e:
                    logger.warning(f"Session validity check failed: {e}")
                # Session invalid or error, close and remove it
                try:
                    await session.close()
                except Exception:
                    pass
                del self.sessions[agent_id]

            # Initialize browser if needed
            if not self._initialized:
                await self.initialize()

            # Create new session
            logger.info(f"Creating new session for agent {agent_id}")
            session = FUBBrowserSession(self.browser, agent_id, self.session_store)
            logger.debug(f"FUBBrowserSession created, calling login...")
            await session.login(credentials)
            logger.debug(f"Login complete for agent {agent_id}")
            self.sessions[agent_id] = session
            return session

        except Exception as e:
            logger.error(f"Error in get_or_create_session for {agent_id}: {e}")
            raise
        finally:
            # Always release the agent when done with session management
            # Note: We release here but the session is still usable
            # The caller will use the session for their operation
            pass  # Don't release here - release after the operation completes

    async def _run_with_session(self, agent_id: str, credentials: dict, operation_name: str, operation_func, timeout: int = 90):
        """Run an operation with proper agent locking and operation timeout.

        This ensures only one Playwright operation runs at a time per agent.
        The operation itself has a timeout to prevent indefinite hangs.

        Args:
            agent_id: Agent identifier
            credentials: FUB login credentials
            operation_name: Name for logging
            operation_func: Async function taking session as argument
            timeout: Max seconds for the operation (default 90s, reduced from 120s for faster failure)
        """
        # Wait for agent to become available
        max_wait = 120
        waited = 0
        while not self._try_acquire_agent(agent_id):
            if waited >= max_wait:
                raise Exception(f"Timeout waiting for agent {agent_id} to become available for {operation_name}")
            logger.info(f"Agent {agent_id} busy, waiting for {operation_name}... ({waited}s)")
            await asyncio.sleep(2)
            waited += 2

        try:
            logger.debug(f"Agent {agent_id} acquired for {operation_name}")

            # Check if we've had too many consecutive failures - force fresh session
            if self._consecutive_failures.get(agent_id, 0) >= self.MAX_CONSECUTIVE_FAILURES:
                logger.warning(f"Agent {agent_id} has {self._consecutive_failures[agent_id]} consecutive failures, forcing fresh session")
                await self._force_fresh_session(agent_id)

            # Get or create session (with timeout)
            session = await asyncio.wait_for(
                self._get_session_internal(agent_id, credentials),
                timeout=timeout
            )

            # Run the operation (with timeout to prevent indefinite hangs)
            logger.debug(f"Running {operation_name} with {timeout}s timeout")
            result = await asyncio.wait_for(operation_func(session), timeout=timeout)

            # Operation succeeded - reset failure counter
            self._record_success(agent_id)
            return result

        except asyncio.TimeoutError:
            logger.error(f"Operation {operation_name} timed out after {timeout}s for agent {agent_id}")
            self._record_failure(agent_id)
            raise Exception(f"Operation {operation_name} timed out after {timeout}s")

        except Exception as e:
            # Record the failure for tracking
            self._record_failure(agent_id)
            raise

        finally:
            self._release_agent(agent_id)
            logger.debug(f"Agent {agent_id} released after {operation_name}")

    async def _get_session_internal(self, agent_id: str, credentials: dict) -> FUBBrowserSession:
        """Internal session getter - assumes agent is already acquired."""
        # Check for existing valid session
        if agent_id in self.sessions:
            logger.debug(f"Found existing session for agent {agent_id}")
            session = self.sessions[agent_id]
            try:
                if await session.is_valid():
                    logger.debug(f"Session valid for agent {agent_id}")
                    return session
            except Exception as e:
                logger.warning(f"Session validity check failed: {e}")
            # Session invalid, close it
            try:
                await session.close()
            except Exception:
                pass
            del self.sessions[agent_id]

        # Check if login is on cooldown (prevents spamming FUB with verification emails)
        on_cooldown, remaining = self._is_login_on_cooldown(agent_id)
        if on_cooldown:
            raise Exception(
                f"Login on cooldown for {agent_id}. "
                f"Please wait {remaining}s before retrying. "
                f"This prevents spamming FUB with verification emails."
            )

        # Initialize browser if needed
        if not self._initialized:
            await self.initialize()

        # Create new session
        logger.info(f"Creating new session for agent {agent_id}")
        session = FUBBrowserSession(self.browser, agent_id, self.session_store)

        try:
            await session.login(credentials)
            # Login succeeded - clear any cooldown
            self._clear_login_cooldown(agent_id)
            self.sessions[agent_id] = session
            return session
        except Exception as e:
            error_msg = str(e)
            # If login failed due to email verification issue, set cooldown
            if any(x in error_msg.lower() for x in ['verification', 'security check', 'new location', 'email']):
                self._set_login_cooldown(agent_id, f"email verification failed: {error_msg[:100]}")
            raise

    async def send_sms(
        self,
        agent_id: str,
        person_id: int,
        message: str,
        credentials: dict
    ) -> dict:
        """Send SMS to lead via FUB web interface.

        Args:
            agent_id: The agent's unique identifier (for session management)
            person_id: The FUB person ID to send SMS to
            message: The message content
            credentials: Dict with 'type' (email/google/microsoft), 'email', 'password'

        Returns:
            Dict with 'success', 'message_id' or 'error'
        """
        async def do_send(session):
            await session.send_text_message(person_id, message)
            return {
                "success": True,
                "message_id": f"playwright_{person_id}_{asyncio.get_event_loop().time()}",
                "person_id": person_id,
                "agent_id": agent_id
            }

        max_retries = 2
        last_error = None

        for attempt in range(max_retries):
            try:
                return await self._run_with_session(agent_id, credentials, f"send_sms_{person_id}", do_send)
            except Exception as e:
                last_error = e
                logger.warning(f"Send SMS attempt {attempt + 1} failed for person {person_id}: {e}")

                # Invalidate session for retry
                if attempt < max_retries - 1:
                    logger.info(f"Invalidating session for {agent_id} and retrying...")
                    await self._invalidate_session(agent_id)
                    await asyncio.sleep(2)

        logger.error(f"Failed to send SMS to person {person_id} after {max_retries} attempts: {last_error}")
        return {"success": False, "error": str(last_error)}

    async def read_latest_message(
        self,
        agent_id: str,
        person_id: int,
        credentials: dict
    ) -> dict:
        """Read the latest incoming SMS from a lead via FUB web interface.

        This is used when FUB's API returns "Body is hidden for privacy reasons"
        but we need the actual message content for AI processing.

        Includes automatic retry with session recovery if the first attempt fails.

        Args:
            agent_id: The agent's unique identifier (for session management)
            person_id: The FUB person ID to read messages from
            credentials: Dict with 'type' (email/google/microsoft), 'email', 'password'

        Returns:
            Dict with 'success', 'message' (the text content) or 'error'
        """
        async def do_read(session):
            return await session.read_latest_message(person_id)

        max_retries = 2
        last_error = None

        for attempt in range(max_retries):
            try:
                return await self._run_with_session(agent_id, credentials, f"read_message_{person_id}", do_read)
            except Exception as e:
                last_error = e
                logger.warning(f"Read message attempt {attempt + 1} failed for person {person_id}: {e}")

                # Invalidate session for retry
                if attempt < max_retries - 1:
                    logger.info(f"Invalidating session for {agent_id} and retrying...")
                    await self._invalidate_session(agent_id)
                    await asyncio.sleep(2)

        logger.error(f"Failed to read message from person {person_id} after {max_retries} attempts: {last_error}")
        return {"success": False, "error": str(last_error)}

    async def read_call_summaries(
        self,
        agent_id: str,
        person_id: int,
        credentials: dict,
        limit: int = 5
    ) -> dict:
        """Read call summaries from a lead via FUB web interface.

        FUB auto-generates AI summaries for calls that appear in the timeline.
        The API doesn't expose these, so we scrape them from the UI.

        Args:
            agent_id: The agent's unique identifier (for session management)
            person_id: The FUB person ID to read call summaries from
            credentials: Dict with 'type' (email/google/microsoft), 'email', 'password'
            limit: Maximum number of call summaries to retrieve (default 5)

        Returns:
            Dict with 'success', 'summaries' (list of summary dicts) or 'error'
        """
        async def do_read(session):
            return await session.read_call_summaries(person_id, limit)

        max_retries = 2
        last_error = None

        for attempt in range(max_retries):
            try:
                return await self._run_with_session(agent_id, credentials, f"read_call_summaries_{person_id}", do_read)
            except Exception as e:
                last_error = e
                logger.warning(f"Read call summaries attempt {attempt + 1} failed for person {person_id}: {e}")

                # Invalidate session for retry
                if attempt < max_retries - 1:
                    logger.info(f"Invalidating session for {agent_id} and retrying...")
                    await self._invalidate_session(agent_id)
                    await asyncio.sleep(2)

        logger.error(f"Failed to read call summaries from person {person_id} after {max_retries} attempts: {last_error}")
        return {"success": False, "error": str(last_error), "summaries": []}

    async def read_recent_messages(
        self,
        agent_id: str,
        person_id: int,
        credentials: dict,
        limit: int = 15
    ) -> dict:
        """Read recent message history from a lead via FUB web interface.

        Used on first contact to sync conversation history for AI context.

        Args:
            agent_id: The agent's unique identifier (for session management)
            person_id: The FUB person ID to read messages from
            credentials: Dict with 'type' (email/google/microsoft), 'email', 'password'
            limit: Maximum number of messages to retrieve (default 15)

        Returns:
            Dict with 'success', 'messages' (list of message dicts) or 'error'
        """
        async def do_read(session):
            return await session.read_recent_messages(person_id, limit)

        max_retries = 2
        last_error = None

        for attempt in range(max_retries):
            try:
                return await self._run_with_session(agent_id, credentials, f"read_recent_messages_{person_id}", do_read)
            except Exception as e:
                last_error = e
                logger.warning(f"Read recent messages attempt {attempt + 1} failed for person {person_id}: {e}")

                # Invalidate session for retry
                if attempt < max_retries - 1:
                    logger.info(f"Invalidating session for {agent_id} and retrying...")
                    await self._invalidate_session(agent_id)
                    await asyncio.sleep(2)

        logger.error(f"Failed to read messages from person {person_id} after {max_retries} attempts: {last_error}")
        return {"success": False, "error": str(last_error), "messages": []}

    async def _invalidate_session(self, agent_id: str):
        """Invalidate a session without closing (for retry scenarios)."""
        with self._agent_busy_lock:
            if agent_id in self.sessions:
                try:
                    await self.sessions[agent_id].close()
                except Exception:
                    pass
                del self.sessions[agent_id]
                logger.info(f"Session invalidated for agent {agent_id}")

    async def close_session(self, agent_id: str):
        """Close a specific agent's session."""
        session = None
        with self._agent_busy_lock:
            if agent_id in self.sessions:
                session = self.sessions.pop(agent_id)
        # Close outside lock to avoid holding lock during async operation
        if session:
            await session.close()
            logger.info(f"Session closed for agent {agent_id}")

    async def close_all_sessions(self):
        """Close all sessions."""
        # Collect sessions under lock, then close outside lock
        sessions_to_close = []
        with self._agent_busy_lock:
            sessions_to_close = list(self.sessions.items())
            self.sessions.clear()
        # Close all sessions outside the lock
        for agent_id, session in sessions_to_close:
            try:
                await session.close()
            except Exception as e:
                logger.warning(f"Error closing session for {agent_id}: {e}")
        logger.info("All sessions closed")

    async def shutdown(self):
        """Shutdown the service and cleanup resources."""
        await self.close_all_sessions()

        if self.browser:
            await self.browser.close()
            self.browser = None

        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

        self._initialized = False
        logger.info("Playwright SMS Service shutdown complete")

    def get_active_sessions(self) -> list:
        """Get list of active session agent IDs."""
        return list(self.sessions.keys())


class PlaywrightSMSServiceSingleton:
    """Singleton accessor for PlaywrightSMSService.

    Uses a simple flag-based approach to avoid async/sync lock deadlocks.
    """

    _instance: Optional[PlaywrightSMSService] = None
    _creating = False
    _lock = threading.Lock()  # Only for quick flag checks

    @classmethod
    async def get_instance(cls) -> PlaywrightSMSService:
        """Get or create the singleton instance."""
        # Fast path - instance exists
        if cls._instance is not None:
            return cls._instance

        # Check if creation is in progress
        max_wait = 60
        waited = 0
        while True:
            with cls._lock:
                if cls._instance is not None:
                    return cls._instance
                if not cls._creating:
                    cls._creating = True
                    break
            # Another task is creating, wait
            if waited >= max_wait:
                raise Exception("Timeout waiting for Playwright service initialization")
            await asyncio.sleep(1)
            waited += 1

        # We're the creator
        try:
            instance = PlaywrightSMSService()
            await instance.initialize()
            cls._instance = instance
            return instance
        finally:
            with cls._lock:
                cls._creating = False

    @classmethod
    async def shutdown(cls):
        """Shutdown the singleton instance."""
        instance = None
        with cls._lock:
            if cls._instance:
                instance = cls._instance
                cls._instance = None
        # Shutdown outside lock since it's async
        if instance:
            await instance.shutdown()


# Convenience function for one-off sends
async def send_sms_via_browser(
    agent_id: str,
    person_id: int,
    message: str,
    credentials: dict
) -> dict:
    """Convenience function to send SMS via browser.

    Args:
        agent_id: Agent identifier for session management
        person_id: FUB person ID
        message: SMS content
        credentials: Dict with 'type', 'email', 'password'

    Returns:
        Dict with 'success' and either 'message_id' or 'error'
    """
    service = await PlaywrightSMSServiceSingleton.get_instance()
    return await service.send_sms(agent_id, person_id, message, credentials)


async def send_sms_with_auto_credentials(
    person_id: int,
    message: str,
    user_id: str = None,
    organization_id: str = None,
    supabase_client=None,
) -> dict:
    """
    Send SMS via browser with automatic credential lookup.

    This function automatically retrieves FUB browser credentials from:
    1. User-specific settings in database
    2. Organization settings in database
    3. Environment variables (fallback)

    Args:
        person_id: FUB person ID to send SMS to
        message: SMS content
        user_id: Optional user ID for credential lookup
        organization_id: Optional org ID for credential lookup
        supabase_client: Optional Supabase client for DB lookup

    Returns:
        Dict with 'success' and either 'message_id' or 'error'
    """
    from app.ai_agent.settings_service import get_fub_browser_credentials

    # Get credentials from settings or environment
    credentials = await get_fub_browser_credentials(
        supabase_client=supabase_client,
        user_id=user_id,
        organization_id=organization_id,
    )

    if not credentials:
        return {
            "success": False,
            "error": "No FUB browser credentials configured. Set FUB_LOGIN_EMAIL and FUB_LOGIN_PASSWORD in environment or database settings."
        }

    # Get agent_id from credentials or generate one
    agent_id = credentials.get("agent_id") or user_id or organization_id or "default_agent"

    service = await PlaywrightSMSServiceSingleton.get_instance()
    return await service.send_sms(agent_id, person_id, message, credentials)


async def read_latest_message_via_browser(
    agent_id: str,
    person_id: int,
    credentials: dict
) -> dict:
    """Convenience function to read latest message via browser.

    This is used when FUB's API returns "Body is hidden for privacy reasons"
    but we need the actual message content for AI processing.

    Args:
        agent_id: Agent identifier for session management
        person_id: FUB person ID
        credentials: Dict with 'type', 'email', 'password'

    Returns:
        Dict with 'success' and either 'message' or 'error'
    """
    service = await PlaywrightSMSServiceSingleton.get_instance()
    return await service.read_latest_message(agent_id, person_id, credentials)


async def read_call_summaries_via_browser(
    agent_id: str,
    person_id: int,
    credentials: dict,
    limit: int = 5
) -> dict:
    """Convenience function to read call summaries via browser.

    FUB auto-generates AI summaries for calls. These aren't available
    via API, so we scrape them from the UI.

    Args:
        agent_id: Agent identifier for session management
        person_id: FUB person ID
        credentials: Dict with 'type', 'email', 'password'
        limit: Maximum number of call summaries (default 5)

    Returns:
        Dict with 'success' and either 'summaries' or 'error'
    """
    service = await PlaywrightSMSServiceSingleton.get_instance()
    return await service.read_call_summaries(agent_id, person_id, credentials, limit)


async def read_call_summaries_with_auto_credentials(
    person_id: int,
    user_id: str = None,
    organization_id: str = None,
    supabase_client=None,
    limit: int = 5
) -> dict:
    """
    Read call summaries via browser with automatic credential lookup.

    FUB auto-generates AI summaries for calls. These aren't available
    via API, so we scrape them from the UI.

    Args:
        person_id: FUB person ID to read call summaries from
        user_id: Optional user ID for credential lookup
        organization_id: Optional org ID for credential lookup
        supabase_client: Optional Supabase client for DB lookup
        limit: Maximum number of call summaries (default 5)

    Returns:
        Dict with 'success' and either 'summaries' or 'error'
    """
    from app.ai_agent.settings_service import get_fub_browser_credentials

    # Get credentials from settings or environment
    credentials = await get_fub_browser_credentials(
        supabase_client=supabase_client,
        user_id=user_id,
        organization_id=organization_id,
    )

    if not credentials:
        return {
            "success": False,
            "error": "No FUB browser credentials configured. Set FUB_LOGIN_EMAIL and FUB_LOGIN_PASSWORD in environment or database settings.",
            "summaries": []
        }

    # Get agent_id from credentials or generate one
    agent_id = credentials.get("agent_id") or user_id or organization_id or "default_agent"

    service = await PlaywrightSMSServiceSingleton.get_instance()
    return await service.read_call_summaries(agent_id, person_id, credentials, limit)


async def read_message_with_auto_credentials(
    person_id: int,
    user_id: str = None,
    organization_id: str = None,
    supabase_client=None,
) -> dict:
    """
    Read latest message via browser with automatic credential lookup.

    This is used when FUB's API returns "Body is hidden for privacy reasons"
    but we need the actual message content for AI processing.

    Args:
        person_id: FUB person ID to read message from
        user_id: Optional user ID for credential lookup
        organization_id: Optional org ID for credential lookup
        supabase_client: Optional Supabase client for DB lookup

    Returns:
        Dict with 'success' and either 'message' or 'error'
    """
    from app.ai_agent.settings_service import get_fub_browser_credentials

    # Get credentials from settings or environment
    credentials = await get_fub_browser_credentials(
        supabase_client=supabase_client,
        user_id=user_id,
        organization_id=organization_id,
    )

    if not credentials:
        return {
            "success": False,
            "error": "No FUB browser credentials configured. Set FUB_LOGIN_EMAIL and FUB_LOGIN_PASSWORD in environment or database settings."
        }

    # Get agent_id from credentials or generate one
    agent_id = credentials.get("agent_id") or user_id or organization_id or "default_agent"

    service = await PlaywrightSMSServiceSingleton.get_instance()
    return await service.read_latest_message(agent_id, person_id, credentials)


async def get_fub_phone_numbers_with_auto_credentials(
    user_id: str = None,
    organization_id: str = None,
    supabase_client=None,
) -> dict:
    """
    Fetch all phone numbers from FUB account via browser with automatic credential lookup.

    Navigates to the FUB phone numbers settings page and scrapes all
    phone numbers, their assigned users, and their purposes.

    Args:
        user_id: Optional user ID for credential lookup
        organization_id: Optional org ID for credential lookup
        supabase_client: Optional Supabase client for DB lookup

    Returns:
        Dict with 'success', 'phone_numbers' (list of dicts with
        number, normalized, assigned_to, purpose, is_active)
    """
    from app.ai_agent.settings_service import get_fub_browser_credentials

    # Get credentials from settings or environment
    credentials = await get_fub_browser_credentials(
        supabase_client=supabase_client,
        user_id=user_id,
        organization_id=organization_id,
    )

    if not credentials:
        return {
            "success": False,
            "error": "No FUB browser credentials configured. Set FUB_LOGIN_EMAIL and FUB_LOGIN_PASSWORD in environment or database settings.",
            "phone_numbers": []
        }

    # Get agent_id from credentials or generate one
    agent_id = credentials.get("agent_id") or user_id or organization_id or "default_agent"

    service = await PlaywrightSMSServiceSingleton.get_instance()

    # Use the _run_with_session pattern for proper locking
    async def do_get_phones(session):
        return await session.get_phone_numbers()

    max_retries = 2
    last_error = None

    for attempt in range(max_retries):
        try:
            return await service._run_with_session(
                agent_id, credentials, "get_phone_numbers", do_get_phones
            )
        except Exception as e:
            last_error = e
            logger.warning(f"Get phone numbers attempt {attempt + 1} failed: {e}")

            # Invalidate session for retry
            if attempt < max_retries - 1:
                logger.info(f"Invalidating session for {agent_id} and retrying...")
                await service._invalidate_session(agent_id)
                await asyncio.sleep(2)

    logger.error(f"Failed to get phone numbers after {max_retries} attempts: {last_error}")
    return {"success": False, "error": str(last_error), "phone_numbers": []}
