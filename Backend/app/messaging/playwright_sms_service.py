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

    IMPORTANT: Uses threading.RLock instead of asyncio.Lock because webhook handlers
    create separate event loops per request. asyncio.Lock is NOT cross-event-loop safe
    and causes deadlocks when multiple webhooks try to access the same session.
    """

    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.sessions: Dict[str, FUBBrowserSession] = {}  # agent_id -> session
        self.session_store = SessionStore()
        self._initialized = False
        self._lock = threading.RLock()  # Thread-safe for cross-event-loop access
        self._login_locks: Dict[str, threading.RLock] = {}  # Per-agent locks (thread-safe)
        self._login_in_progress: Dict[str, bool] = {}  # Track login attempts

    async def initialize(self):
        """Initialize Playwright and browser instance. Thread-safe."""
        with self._lock:  # Use 'with' for threading.RLock, not 'async with'
            await self._do_initialize()

    async def _do_initialize(self):
        """Internal initialization - called when lock is already held."""
        if self._initialized:
            return

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

    async def get_or_create_session(self, agent_id: str, credentials: dict) -> FUBBrowserSession:
        """Get existing session or create new one for agent.

        Uses per-agent locks to prevent multiple concurrent login attempts,
        which could trigger multiple security emails from FUB.
        """
        logger.debug(f"get_or_create_session called for agent {agent_id}")

        # Get or create per-agent lock (thread-safe)
        with self._lock:
            if agent_id not in self._login_locks:
                self._login_locks[agent_id] = threading.RLock()
            agent_lock = self._login_locks[agent_id]

        # Use per-agent lock to prevent concurrent logins for the same agent
        with agent_lock:
            logger.debug(f"Acquired agent lock for {agent_id}")

            # Check if login is already in progress (shouldn't happen with lock, but safety check)
            if self._login_in_progress.get(agent_id, False):
                logger.warning(f"Login already in progress for agent {agent_id}, waiting...")
                # Wait a bit and check for existing session
                for _ in range(30):  # Wait up to 30 seconds
                    await asyncio.sleep(1)
                    if agent_id in self.sessions and await self.sessions[agent_id].is_valid():
                        return self.sessions[agent_id]
                    if not self._login_in_progress.get(agent_id, False):
                        break

            # Check for existing valid session
            if agent_id in self.sessions:
                logger.debug(f"Found existing session for agent {agent_id}, checking validity...")
                session = self.sessions[agent_id]
                if await session.is_valid():
                    logger.debug(f"Reusing existing session for agent {agent_id}")
                    return session
                else:
                    # Session expired, close and remove it
                    logger.debug(f"Session expired for agent {agent_id}, closing...")
                    await session.close()
                    del self.sessions[agent_id]

            # Initialize browser if needed
            with self._lock:
                if not self._initialized:
                    logger.debug("Service not initialized, initializing...")
                    await self._do_initialize()
                    logger.debug("Service initialized")

            # Mark login as in progress
            self._login_in_progress[agent_id] = True

            try:
                logger.info(f"Creating new session for agent {agent_id}")
                session = FUBBrowserSession(self.browser, agent_id, self.session_store)
                logger.debug(f"FUBBrowserSession created, calling login...")
                await session.login(credentials)
                logger.debug(f"Login complete for agent {agent_id}")
                self.sessions[agent_id] = session
                return session
            finally:
                # Clear login in progress flag
                self._login_in_progress[agent_id] = False

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
        max_retries = 2
        last_error = None

        for attempt in range(max_retries):
            try:
                session = await self.get_or_create_session(agent_id, credentials)
                result = await session.send_text_message(person_id, message)
                return {
                    "success": True,
                    "message_id": f"playwright_{person_id}_{asyncio.get_event_loop().time()}",
                    "person_id": person_id,
                    "agent_id": agent_id
                }
            except Exception as e:
                last_error = e
                logger.warning(f"Send SMS attempt {attempt + 1} failed for person {person_id}: {e}")

                # If this looks like a session issue, invalidate and retry
                if attempt < max_retries - 1:
                    logger.info(f"Invalidating session for {agent_id} and retrying...")
                    await self.close_session(agent_id)
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
        max_retries = 2
        last_error = None

        for attempt in range(max_retries):
            try:
                session = await self.get_or_create_session(agent_id, credentials)
                result = await session.read_latest_message(person_id)
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"Read message attempt {attempt + 1} failed for person {person_id}: {e}")

                # If this looks like a session issue, invalidate and retry
                if attempt < max_retries - 1:
                    logger.info(f"Invalidating session for {agent_id} and retrying...")
                    await self.close_session(agent_id)
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
        try:
            session = await self.get_or_create_session(agent_id, credentials)
            result = await session.read_call_summaries(person_id, limit)
            return result
        except Exception as e:
            logger.error(f"Failed to read call summaries from person {person_id}: {e}")
            return {"success": False, "error": str(e), "summaries": []}

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
        try:
            session = await self.get_or_create_session(agent_id, credentials)
            result = await session.read_recent_messages(person_id, limit)
            return result
        except Exception as e:
            logger.error(f"Failed to read messages from person {person_id}: {e}")
            return {"success": False, "error": str(e), "messages": []}

    async def close_session(self, agent_id: str):
        """Close a specific agent's session."""
        session = None
        with self._lock:
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
        with self._lock:
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

    Uses threading.RLock for cross-event-loop safety since webhook handlers
    create separate event loops per request.
    """

    _instance: Optional[PlaywrightSMSService] = None
    _lock = threading.RLock()

    @classmethod
    async def get_instance(cls) -> PlaywrightSMSService:
        """Get or create the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = PlaywrightSMSService()
                # Initialize outside lock since it's async and may take time
                await cls._instance.initialize()
            return cls._instance

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
