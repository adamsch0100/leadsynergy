"""
AI Agent Settings Service - Load and manage AI agent configuration from database.

This service provides:
- Loading settings from ai_agent_settings table
- Caching settings to reduce database queries
- Default fallback values when no settings exist
- User-level and organization-level settings hierarchy
"""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, time
from functools import lru_cache
import json

logger = logging.getLogger(__name__)


@dataclass
class AIAgentSettings:
    """
    Configuration settings for the AI agent.

    Settings are loaded from the ai_agent_settings database table.
    Falls back to sensible defaults when settings are not configured.
    """
    # Identity
    agent_name: str = "Sarah"
    brokerage_name: str = "our team"
    team_members: str = ""  # Human agent names (e.g., "Adam and Mandi")
    personality_tone: str = "friendly_casual"  # friendly_casual, professional, energetic
    use_assigned_agent_name: bool = False  # If True, use lead's assigned agent name instead of branded name

    # Response timing settings (human-like delays)
    response_delay_seconds: int = 30  # Configurable delay (for UI)
    response_delay_min_seconds: int = 30  # Minimum delay to feel human
    response_delay_max_seconds: int = 120  # Maximum delay (2 minutes)
    first_message_delay_min: int = 45  # First message to lead - slightly longer
    first_message_delay_max: int = 180  # Up to 3 minutes for first message
    typing_speed_chars_per_second: float = 4.0  # Simulate typing time
    max_response_length: int = 160  # SMS character limit

    # Working hours (TCPA compliance)
    working_hours_start: time = field(default_factory=lambda: time(8, 0))  # 8 AM
    working_hours_end: time = field(default_factory=lambda: time(20, 0))  # 8 PM
    timezone: str = "America/New_York"

    # Automation settings
    auto_handoff_score: int = 80  # Score threshold for human handoff
    max_ai_messages_per_lead: int = 15
    max_qualification_questions: int = 8
    auto_schedule_score_threshold: int = 70  # Score to auto-suggest scheduling

    # Feature flags
    is_enabled: bool = True
    use_llm_for_all_responses: bool = True
    use_templates_as_fallback: bool = True
    enable_a_b_testing: bool = True

    # Re-engagement settings (smart automation restart)
    re_engagement_enabled: bool = True
    quiet_hours_before_re_engage: int = 24  # Hours of silence before re-engaging
    re_engagement_max_attempts: int = 3  # Max re-engagement sequences
    long_term_nurture_after_days: int = 7  # Days before moving to long-term drip
    re_engagement_channels: list = field(default_factory=lambda: ["sms", "email"])

    # ============================================================================
    # SEQUENCE SETTINGS - Control follow-up aggressiveness and channels
    # Research shows: 5-minute response = 21x higher conversion (MIT study)
    # ============================================================================

    # Channel toggles - enable/disable channels for automated sequences
    sequence_sms_enabled: bool = True       # SMS always on by default
    sequence_email_enabled: bool = True     # Email always on by default
    sequence_voice_enabled: bool = False    # Voice/RVM OFF by default (toggle on when ready)
    sequence_rvm_enabled: bool = False      # Ringless voicemail OFF by default

    # Day 0 aggression level: "aggressive" | "moderate" | "conservative"
    # aggressive: 4 touches on Day 0 (SMS → RVM → SMS → Call)
    # moderate: 2-3 touches on Day 0
    # conservative: 1 touch on Day 0 (current behavior)
    day_0_aggression: str = "aggressive"

    # Proactive appointment offering - offer time slots without being asked
    proactive_appointment_enabled: bool = True

    # Qualification questions - ask qualifying questions in early messages
    qualification_questions_enabled: bool = True

    # Instant response for new leads (< 1 minute)
    instant_response_enabled: bool = True
    instant_response_max_delay_seconds: int = 60  # Max 60 seconds for new leads

    # NBA (Next Best Action) scan intervals
    nba_hot_lead_scan_interval_minutes: int = 5   # Scan hot leads every 5 minutes
    nba_cold_lead_scan_interval_minutes: int = 15  # Scan cold leads every 15 minutes

    # Custom configuration (JSONB fields)
    qualification_questions: list = field(default_factory=list)
    custom_scripts: dict = field(default_factory=dict)

    # FUB Browser Login Credentials (for Playwright SMS)
    fub_login_email: Optional[str] = None
    fub_login_password: Optional[str] = None  # Should be encrypted in DB
    fub_login_type: str = "email"  # email, google, microsoft

    # LLM Model Configuration (for AI responses)
    # Provider options: "openrouter", "anthropic"
    llm_provider: str = "openrouter"  # Default to OpenRouter (free models available)

    # Model selection - user can choose from available models
    # Free models with tool calling support on OpenRouter:
    # - xiaomi/mimo-v2-flash:free (fast, good for conversations)
    # - meta-llama/llama-3.3-70b-instruct:free (high quality)
    # - google/gemini-2.0-flash-exp:free (1M context)
    # - qwen/qwen3-coder:free (best for tool use)
    # - openai/gpt-oss-120b:free (GPT quality)
    llm_model: str = "xiaomi/mimo-v2-flash:free"
    llm_model_fallback: str = "deepseek/deepseek-r1-0528:free"

    # Database metadata
    settings_id: Optional[str] = None
    user_id: Optional[str] = None
    organization_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, handling time objects."""
        data = asdict(self)
        # Convert time objects to string
        data['working_hours_start'] = self.working_hours_start.strftime('%H:%M')
        data['working_hours_end'] = self.working_hours_end.strftime('%H:%M')
        return data

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'AIAgentSettings':
        """Create settings from database row."""
        # Parse time fields
        working_start = time(8, 0)
        working_end = time(20, 0)

        if row.get('working_hours_start'):
            try:
                if isinstance(row['working_hours_start'], str):
                    parts = row['working_hours_start'].split(':')
                    working_start = time(int(parts[0]), int(parts[1]))
                elif isinstance(row['working_hours_start'], time):
                    working_start = row['working_hours_start']
            except (ValueError, IndexError):
                pass

        if row.get('working_hours_end'):
            try:
                if isinstance(row['working_hours_end'], str):
                    parts = row['working_hours_end'].split(':')
                    working_end = time(int(parts[0]), int(parts[1]))
                elif isinstance(row['working_hours_end'], time):
                    working_end = row['working_hours_end']
            except (ValueError, IndexError):
                pass

        return cls(
            settings_id=row.get('id'),
            user_id=row.get('user_id'),
            organization_id=row.get('organization_id'),
            agent_name=row.get('agent_name') or "Sarah",
            brokerage_name=row.get('brokerage_name') or "our team",
            team_members=row.get('team_members') or "",
            personality_tone=row.get('personality_tone') or "friendly_casual",
            use_assigned_agent_name=row.get('use_assigned_agent_name', False),
            response_delay_seconds=row.get('response_delay_seconds') or 30,
            working_hours_start=working_start,
            working_hours_end=working_end,
            timezone=row.get('timezone') or "America/New_York",
            auto_handoff_score=row.get('auto_handoff_score') or 80,
            max_ai_messages_per_lead=row.get('max_ai_messages_per_lead') or 15,
            is_enabled=row.get('is_enabled', True),
            qualification_questions=row.get('qualification_questions') or [],
            custom_scripts=row.get('custom_scripts') or {},
            # Re-engagement settings
            re_engagement_enabled=row.get('re_engagement_enabled', True),
            quiet_hours_before_re_engage=row.get('quiet_hours_before_re_engage') or 24,
            re_engagement_max_attempts=row.get('re_engagement_max_attempts') or 3,
            long_term_nurture_after_days=row.get('long_term_nurture_after_days') or 7,
            re_engagement_channels=row.get('re_engagement_channels') or ["sms", "email"],
            max_response_length=row.get('max_response_length') or 160,
            # FUB Browser Login
            fub_login_email=row.get('fub_login_email'),
            fub_login_password=row.get('fub_login_password'),
            fub_login_type=row.get('fub_login_type') or "email",
            # LLM Model Configuration
            llm_provider=row.get('llm_provider') or "openrouter",
            llm_model=row.get('llm_model') or "xiaomi/mimo-v2-flash:free",
            llm_model_fallback=row.get('llm_model_fallback') or "deepseek/deepseek-r1-0528:free",
            # Sequence settings
            sequence_sms_enabled=row.get('sequence_sms_enabled', True),
            sequence_email_enabled=row.get('sequence_email_enabled', True),
            sequence_voice_enabled=row.get('sequence_voice_enabled', False),
            sequence_rvm_enabled=row.get('sequence_rvm_enabled', False),
            day_0_aggression=row.get('day_0_aggression') or "aggressive",
            proactive_appointment_enabled=row.get('proactive_appointment_enabled', True),
            qualification_questions_enabled=row.get('qualification_questions_enabled', True),
            instant_response_enabled=row.get('instant_response_enabled', True),
            instant_response_max_delay_seconds=row.get('instant_response_max_delay_seconds') or 60,
            nba_hot_lead_scan_interval_minutes=row.get('nba_hot_lead_scan_interval_minutes') or 5,
            nba_cold_lead_scan_interval_minutes=row.get('nba_cold_lead_scan_interval_minutes') or 15,
        )


class AIAgentSettingsService:
    """
    Service for loading and managing AI agent settings from the database.

    Settings hierarchy:
    1. User-level settings (highest priority)
    2. Organization-level settings
    3. Default settings (fallback)

    Usage:
        service = AIAgentSettingsService(supabase_client)
        settings = await service.get_settings(user_id="abc123")

        # Or get settings for a user with org fallback
        settings = await service.get_settings(
            user_id="abc123",
            organization_id="org456"
        )
    """

    def __init__(self, supabase_client=None):
        """
        Initialize the settings service.

        Args:
            supabase_client: Supabase client for database access
        """
        self.supabase = supabase_client
        self._cache: Dict[str, tuple] = {}  # key -> (settings, timestamp)
        self._cache_ttl_seconds = 300  # 5 minutes

    def _get_cache_key(
        self,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> str:
        """Generate cache key for settings lookup."""
        return f"settings:{user_id or 'none'}:{organization_id or 'none'}"

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached settings are still valid."""
        if cache_key not in self._cache:
            return False
        _, cached_at = self._cache[cache_key]
        age = (datetime.utcnow() - cached_at).total_seconds()
        return age < self._cache_ttl_seconds

    async def get_settings(
        self,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        use_cache: bool = True,
    ) -> AIAgentSettings:
        """
        Get AI agent settings for a user or organization.

        Settings are loaded with the following priority:
        1. User-specific settings (if user_id provided)
        2. Organization-level settings (if org_id provided)
        3. Default settings

        Args:
            user_id: Optional user ID to get settings for
            organization_id: Optional organization ID for fallback
            use_cache: Whether to use cached settings (default True)

        Returns:
            AIAgentSettings object with the loaded or default settings
        """
        # Check cache first
        cache_key = self._get_cache_key(user_id, organization_id)
        if use_cache and self._is_cache_valid(cache_key):
            settings, _ = self._cache[cache_key]
            logger.debug(f"Returning cached settings for {cache_key}")
            return settings

        # No database client - return defaults
        if not self.supabase:
            logger.warning("No Supabase client - returning default settings")
            return AIAgentSettings()

        try:
            settings = None

            # Try to get user-specific settings first
            if user_id:
                result = self.supabase.table("ai_agent_settings").select("*").eq(
                    "user_id", user_id
                ).execute()

                if result.data:
                    settings = AIAgentSettings.from_db_row(result.data[0])
                    logger.info(f"Loaded user settings for user_id={user_id}")

            # Fall back to organization settings
            if not settings and organization_id:
                result = self.supabase.table("ai_agent_settings").select("*").eq(
                    "organization_id", organization_id
                ).is_("user_id", "null").execute()

                if result.data:
                    settings = AIAgentSettings.from_db_row(result.data[0])
                    logger.info(f"Loaded org settings for org_id={organization_id}")

            # Try to get any settings if none found yet (single-user setup)
            if not settings:
                result = self.supabase.table("ai_agent_settings").select("*").limit(1).execute()
                if result.data:
                    settings = AIAgentSettings.from_db_row(result.data[0])
                    logger.info("Loaded default settings from first available record")

            # Use defaults if no settings found
            if not settings:
                logger.info("No settings found - using defaults")
                settings = AIAgentSettings()

            # Cache the result
            self._cache[cache_key] = (settings, datetime.utcnow())

            return settings

        except Exception as e:
            logger.error(f"Error loading settings: {e}", exc_info=True)
            return AIAgentSettings()

    async def save_settings(
        self,
        settings: AIAgentSettings,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> bool:
        """
        Save AI agent settings to the database.

        Args:
            settings: Settings to save
            user_id: User ID for user-level settings
            organization_id: Organization ID for org-level settings

        Returns:
            True if save was successful
        """
        if not self.supabase:
            logger.error("No Supabase client - cannot save settings")
            return False

        try:
            data = {
                "agent_name": settings.agent_name,
                "brokerage_name": settings.brokerage_name,
                "personality_tone": settings.personality_tone,
                "response_delay_seconds": settings.response_delay_seconds,
                "working_hours_start": settings.working_hours_start.strftime('%H:%M'),
                "working_hours_end": settings.working_hours_end.strftime('%H:%M'),
                "timezone": settings.timezone,
                "auto_handoff_score": settings.auto_handoff_score,
                "max_ai_messages_per_lead": settings.max_ai_messages_per_lead,
                "is_enabled": settings.is_enabled,
                "qualification_questions": settings.qualification_questions,
                "custom_scripts": settings.custom_scripts,
            }

            # Add user/org ID
            if user_id:
                data["user_id"] = user_id
            if organization_id:
                data["organization_id"] = organization_id

            # Upsert based on existing settings
            if settings.settings_id:
                # Update existing
                result = self.supabase.table("ai_agent_settings").update(data).eq(
                    "id", settings.settings_id
                ).execute()
            elif user_id:
                # Upsert by user_id
                data["user_id"] = user_id
                result = self.supabase.table("ai_agent_settings").upsert(
                    data,
                    on_conflict="user_id"
                ).execute()
            elif organization_id:
                # Upsert by org_id (for org-level settings)
                result = self.supabase.table("ai_agent_settings").upsert(
                    data,
                    on_conflict="organization_id"
                ).execute()
            else:
                # Insert new
                result = self.supabase.table("ai_agent_settings").insert(data).execute()

            # Invalidate cache
            cache_key = self._get_cache_key(user_id, organization_id)
            self._cache.pop(cache_key, None)

            logger.info(f"Saved settings for user={user_id}, org={organization_id}")
            return True

        except Exception as e:
            logger.error(f"Error saving settings: {e}", exc_info=True)
            return False

    async def create_default_settings(
        self,
        user_id: str,
        organization_id: str,
        agent_name: str = None,
        brokerage_name: str = None,
    ) -> AIAgentSettings:
        """
        Create default settings for a new user/organization.

        Args:
            user_id: User ID to create settings for
            organization_id: Organization ID
            agent_name: Optional custom agent name
            brokerage_name: Optional custom brokerage name

        Returns:
            The created settings
        """
        settings = AIAgentSettings(
            user_id=user_id,
            organization_id=organization_id,
            agent_name=agent_name or "Sarah",
            brokerage_name=brokerage_name or "our team",
        )

        await self.save_settings(settings, user_id, organization_id)
        return settings

    def invalidate_cache(
        self,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ):
        """Invalidate cached settings."""
        if user_id or organization_id:
            cache_key = self._get_cache_key(user_id, organization_id)
            self._cache.pop(cache_key, None)
        else:
            # Clear all cache
            self._cache.clear()
        logger.debug("Settings cache invalidated")


# Singleton instance for global access
_settings_service_instance: Optional[AIAgentSettingsService] = None


def get_settings_service(supabase_client=None) -> AIAgentSettingsService:
    """
    Get the global settings service instance.

    Args:
        supabase_client: Supabase client (only needed on first call)

    Returns:
        AIAgentSettingsService instance
    """
    global _settings_service_instance

    if _settings_service_instance is None:
        _settings_service_instance = AIAgentSettingsService(supabase_client)
    elif supabase_client and not _settings_service_instance.supabase:
        _settings_service_instance.supabase = supabase_client

    return _settings_service_instance


async def get_agent_settings(
    supabase_client=None,
    user_id: Optional[str] = None,
    organization_id: Optional[str] = None,
) -> AIAgentSettings:
    """
    Convenience function to get agent settings.

    Args:
        supabase_client: Supabase client
        user_id: User ID for settings lookup
        organization_id: Organization ID for fallback

    Returns:
        AIAgentSettings object
    """
    service = get_settings_service(supabase_client)
    return await service.get_settings(user_id, organization_id)


async def get_fub_browser_credentials(
    supabase_client=None,
    user_id: Optional[str] = None,
    organization_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get FUB browser login credentials for Playwright SMS.

    Checks in order:
    1. User-specific settings from database
    2. Organization settings from database
    3. Environment variables (fallback)

    Args:
        supabase_client: Supabase client
        user_id: User ID for settings lookup
        organization_id: Organization ID for fallback

    Returns:
        Dict with 'type', 'email', 'password', 'agent_id' keys
    """
    import os

    # Try to get from database settings first
    settings = await get_agent_settings(supabase_client, user_id, organization_id)

    if settings.fub_login_email and settings.fub_login_password:
        return {
            "type": settings.fub_login_type or "email",
            "email": settings.fub_login_email,
            "password": settings.fub_login_password,
            "agent_id": user_id or organization_id or "default_agent",
        }

    # Fallback to environment variables
    fub_email = os.getenv("FUB_LOGIN_EMAIL")
    fub_password = os.getenv("FUB_LOGIN_PASSWORD")
    fub_login_type = os.getenv("FUB_LOGIN_TYPE", "email")

    if fub_email and fub_password:
        return {
            "type": fub_login_type,
            "email": fub_email,
            "password": fub_password,
            "agent_id": user_id or organization_id or "default_agent",
        }

    # No credentials available
    logger.warning("No FUB browser credentials found in settings or environment")
    return None
