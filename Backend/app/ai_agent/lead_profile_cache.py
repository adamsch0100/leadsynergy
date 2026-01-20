"""
Lead Profile Cache - Smart caching and incremental updates for FUB data.

This provides:
- Cached lead profiles in Supabase (avoid re-fetching all data on every message)
- Incremental updates via webhooks (only update what changed)
- TTL-based full refresh (periodic re-fetch for data freshness)
- Performance optimization (7 FUB API calls → 1 DB read)

Update Strategy:
- textMessagesCreated → Add new message to cache
- emailsCreated → Add new email to cache
- notesCreated → Add new note to cache
- peopleUpdated → Refresh person data only
- eventsCreated → Add new event to cache
- Full refresh after 24 hours or on-demand
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Cache TTL - full refresh after this time
CACHE_TTL_HOURS = 24


@dataclass
class CachedLeadProfile:
    """Cached lead profile data."""
    fub_person_id: int
    organization_id: str

    # Person data
    person_data: Dict[str, Any]

    # Communication history
    text_messages: List[Dict[str, Any]]
    emails: List[Dict[str, Any]]
    calls: List[Dict[str, Any]]

    # Context
    notes: List[Dict[str, Any]]
    events: List[Dict[str, Any]]
    tasks: List[Dict[str, Any]]

    # Cache metadata
    cached_at: str
    last_updated_at: str
    update_count: int = 0

    def is_stale(self, ttl_hours: int = CACHE_TTL_HOURS) -> bool:
        """Check if cache is stale and needs full refresh."""
        try:
            cached_dt = datetime.fromisoformat(self.cached_at.replace('Z', '+00:00'))
            return datetime.now(cached_dt.tzinfo) - cached_dt > timedelta(hours=ttl_hours)
        except:
            return True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CachedLeadProfile":
        return cls(
            fub_person_id=data["fub_person_id"],
            organization_id=data["organization_id"],
            person_data=data.get("person_data", {}),
            text_messages=data.get("text_messages", []),
            emails=data.get("emails", []),
            calls=data.get("calls", []),
            notes=data.get("notes", []),
            events=data.get("events", []),
            tasks=data.get("tasks", []),
            cached_at=data.get("cached_at", datetime.utcnow().isoformat()),
            last_updated_at=data.get("last_updated_at", datetime.utcnow().isoformat()),
            update_count=data.get("update_count", 0),
        )


class LeadProfileCacheService:
    """
    Service for caching and incrementally updating lead profiles.

    Usage:
        cache = LeadProfileCacheService(supabase_client, fub_client)

        # Get cached profile (or fetch fresh if not cached/stale)
        profile = await cache.get_profile(person_id, org_id)

        # Incremental updates from webhooks
        await cache.add_text_message(person_id, message_data)
        await cache.add_email(person_id, email_data)
        await cache.add_note(person_id, note_data)
        await cache.update_person_data(person_id, person_data)
    """

    TABLE_NAME = "ai_lead_profile_cache"

    def __init__(self, supabase_client=None, fub_client=None):
        self.supabase = supabase_client
        self.fub = fub_client

    async def get_profile(
        self,
        fub_person_id: int,
        organization_id: str,
        force_refresh: bool = False,
    ) -> Optional[CachedLeadProfile]:
        """
        Get cached lead profile, fetching fresh data if needed.

        Args:
            fub_person_id: FUB person ID
            organization_id: Organization ID
            force_refresh: Force a full refresh from FUB

        Returns:
            Cached lead profile, or None if not available
        """
        # Try to get from cache first
        if not force_refresh:
            cached = await self._get_from_cache(fub_person_id, organization_id)
            if cached and not cached.is_stale():
                logger.debug(f"Cache hit for person {fub_person_id}")
                return cached

        # Cache miss or stale - fetch fresh from FUB
        logger.info(f"Fetching fresh profile for person {fub_person_id}")
        profile = await self._fetch_from_fub(fub_person_id, organization_id)

        if profile:
            await self._save_to_cache(profile)

        return profile

    async def _get_from_cache(
        self,
        fub_person_id: int,
        organization_id: str,
    ) -> Optional[CachedLeadProfile]:
        """Get profile from cache."""
        if not self.supabase:
            return None

        try:
            result = self.supabase.table(self.TABLE_NAME).select("*").eq(
                "fub_person_id", fub_person_id
            ).eq(
                "organization_id", organization_id
            ).limit(1).execute()

            if result.data:
                return CachedLeadProfile.from_dict(result.data[0])
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")

        return None

    async def _fetch_from_fub(
        self,
        fub_person_id: int,
        organization_id: str,
    ) -> Optional[CachedLeadProfile]:
        """Fetch fresh data from FUB API."""
        if not self.fub:
            return None

        try:
            context = self.fub.get_complete_lead_context(fub_person_id)

            now = datetime.utcnow().isoformat()
            return CachedLeadProfile(
                fub_person_id=fub_person_id,
                organization_id=organization_id,
                person_data=context.get("person", {}),
                text_messages=context.get("text_messages", []),
                emails=context.get("emails", []),
                calls=context.get("calls", []),
                notes=context.get("notes", []),
                events=context.get("events", []),
                tasks=context.get("tasks", []),
                cached_at=now,
                last_updated_at=now,
                update_count=0,
            )
        except Exception as e:
            logger.error(f"Failed to fetch from FUB: {e}")
            return None

    async def _save_to_cache(self, profile: CachedLeadProfile) -> bool:
        """Save profile to cache (upsert)."""
        if not self.supabase:
            return False

        try:
            data = profile.to_dict()

            # Try to update existing
            result = self.supabase.table(self.TABLE_NAME).upsert(
                data,
                on_conflict="fub_person_id,organization_id"
            ).execute()

            return bool(result.data)
        except Exception as e:
            logger.error(f"Cache write failed: {e}")
            return False

    # ========================================
    # INCREMENTAL UPDATE METHODS
    # ========================================

    async def add_text_message(
        self,
        fub_person_id: int,
        organization_id: str,
        message_data: Dict[str, Any],
    ) -> bool:
        """
        Add a new text message to cached profile.
        Called when textMessagesCreated webhook fires.
        """
        cached = await self._get_from_cache(fub_person_id, organization_id)
        if not cached:
            # No cache - will fetch fresh on next get_profile
            return False

        # Add message to list
        cached.text_messages.insert(0, message_data)  # Most recent first

        # Keep only last 50 messages
        cached.text_messages = cached.text_messages[:50]

        # Update metadata
        cached.last_updated_at = datetime.utcnow().isoformat()
        cached.update_count += 1

        return await self._save_to_cache(cached)

    async def add_email(
        self,
        fub_person_id: int,
        organization_id: str,
        email_data: Dict[str, Any],
    ) -> bool:
        """
        Add a new email to cached profile.
        Called when emailsCreated webhook fires.
        """
        cached = await self._get_from_cache(fub_person_id, organization_id)
        if not cached:
            return False

        cached.emails.insert(0, email_data)
        cached.emails = cached.emails[:20]
        cached.last_updated_at = datetime.utcnow().isoformat()
        cached.update_count += 1

        return await self._save_to_cache(cached)

    async def add_note(
        self,
        fub_person_id: int,
        organization_id: str,
        note_data: Dict[str, Any],
    ) -> bool:
        """
        Add a new note to cached profile.
        Called when notesCreated webhook fires.
        """
        cached = await self._get_from_cache(fub_person_id, organization_id)
        if not cached:
            return False

        cached.notes.insert(0, note_data)
        cached.notes = cached.notes[:30]
        cached.last_updated_at = datetime.utcnow().isoformat()
        cached.update_count += 1

        return await self._save_to_cache(cached)

    async def add_event(
        self,
        fub_person_id: int,
        organization_id: str,
        event_data: Dict[str, Any],
    ) -> bool:
        """
        Add a new event to cached profile.
        Called when eventsCreated webhook fires.
        """
        cached = await self._get_from_cache(fub_person_id, organization_id)
        if not cached:
            return False

        cached.events.insert(0, event_data)
        cached.events = cached.events[:30]
        cached.last_updated_at = datetime.utcnow().isoformat()
        cached.update_count += 1

        return await self._save_to_cache(cached)

    async def add_call(
        self,
        fub_person_id: int,
        organization_id: str,
        call_data: Dict[str, Any],
    ) -> bool:
        """
        Add a new call to cached profile.
        Called when callsCreated webhook fires.
        """
        cached = await self._get_from_cache(fub_person_id, organization_id)
        if not cached:
            return False

        cached.calls.insert(0, call_data)
        cached.calls = cached.calls[:20]
        cached.last_updated_at = datetime.utcnow().isoformat()
        cached.update_count += 1

        return await self._save_to_cache(cached)

    async def update_person_data(
        self,
        fub_person_id: int,
        organization_id: str,
        person_data: Dict[str, Any] = None,
    ) -> bool:
        """
        Update person data in cached profile.
        Called when peopleUpdated webhook fires.

        If person_data is None, fetches fresh from FUB.
        """
        cached = await self._get_from_cache(fub_person_id, organization_id)
        if not cached:
            return False

        # Fetch fresh person data if not provided
        if person_data is None and self.fub:
            try:
                person_data = self.fub.get_person(str(fub_person_id), include_all_fields=True)
            except Exception as e:
                logger.error(f"Failed to fetch person data: {e}")
                return False

        if person_data:
            cached.person_data = person_data
            cached.last_updated_at = datetime.utcnow().isoformat()
            cached.update_count += 1
            return await self._save_to_cache(cached)

        return False

    async def invalidate_cache(
        self,
        fub_person_id: int,
        organization_id: str,
    ) -> bool:
        """
        Invalidate cache for a lead (force fresh fetch on next access).
        """
        if not self.supabase:
            return False

        try:
            self.supabase.table(self.TABLE_NAME).delete().eq(
                "fub_person_id", fub_person_id
            ).eq(
                "organization_id", organization_id
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Cache invalidation failed: {e}")
            return False


# Global instance
_cache_service: Optional[LeadProfileCacheService] = None


def get_lead_profile_cache(
    supabase_client=None,
    fub_client=None,
) -> LeadProfileCacheService:
    """Get the global lead profile cache service."""
    global _cache_service

    if _cache_service is None:
        _cache_service = LeadProfileCacheService(supabase_client, fub_client)
    else:
        if supabase_client and not _cache_service.supabase:
            _cache_service.supabase = supabase_client
        if fub_client and not _cache_service.fub:
            _cache_service.fub = fub_client

    return _cache_service
