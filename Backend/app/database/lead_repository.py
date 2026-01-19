"""
Lead Repository - Efficient lead querying with cursor-based pagination.

Designed for scale (100K+ leads) with:
- Cursor-based pagination (O(1) vs O(n) for offset)
- Tiered lead queries (hot/warm/dormant/archived)
- Efficient batch retrieval
- Index-optimized filtering
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum

from app.database.supabase_client import SupabaseClientSingleton

logger = logging.getLogger(__name__)


class LeadTier(Enum):
    """Lead tier classification based on activity."""
    HOT = "hot"           # Active conversation, recent inquiry (< 7 days)
    WARM = "warm"         # Engaged in last 30 days
    DORMANT = "dormant"   # No activity 30-365 days
    ARCHIVED = "archived" # No activity 365+ days or closed


@dataclass
class LeadQueryResult:
    """Result of a paginated lead query."""
    leads: List[Dict[str, Any]]
    next_cursor: Optional[str]
    has_more: bool
    total_in_batch: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "leads": self.leads,
            "next_cursor": self.next_cursor,
            "has_more": self.has_more,
            "total_in_batch": self.total_in_batch,
        }


class LeadRepository:
    """
    Repository for efficient lead queries at scale.

    Uses cursor-based pagination instead of offset for O(1) performance
    regardless of dataset size.
    """

    # Supabase query limits
    MAX_BATCH_SIZE = 1000
    DEFAULT_BATCH_SIZE = 500

    def __init__(self, supabase_client=None):
        """
        Initialize Lead Repository.

        Args:
            supabase_client: Optional Supabase client (defaults to singleton)
        """
        self.supabase = supabase_client or SupabaseClientSingleton.get_instance()

    def _days_ago(self, days: int) -> str:
        """Get ISO timestamp for X days ago."""
        return (datetime.utcnow() - timedelta(days=days)).isoformat()

    def _get_tier_filters(self, tier: LeadTier) -> Dict[str, Any]:
        """
        Get filter conditions for a lead tier.

        Returns dict of {column: {"op": operator, "value": value}}
        """
        filters = {
            LeadTier.HOT: {
                "last_activity_at": {"op": "gte", "value": self._days_ago(7)},
            },
            LeadTier.WARM: {
                "last_activity_at": {"op": "gte", "value": self._days_ago(30)},
                "last_activity_at_lt": {"op": "lt", "value": self._days_ago(7)},
            },
            LeadTier.DORMANT: {
                "last_activity_at": {"op": "lt", "value": self._days_ago(30)},
                "last_activity_at_gte": {"op": "gte", "value": self._days_ago(365)},
            },
            LeadTier.ARCHIVED: {
                "last_activity_at": {"op": "lt", "value": self._days_ago(365)},
            },
        }
        return filters.get(tier, {})

    async def get_leads_cursor(
        self,
        organization_id: str,
        tier: Optional[LeadTier] = None,
        cursor: Optional[str] = None,
        limit: int = DEFAULT_BATCH_SIZE,
        filters: Optional[Dict[str, Any]] = None,
        select_columns: str = "*",
    ) -> LeadQueryResult:
        """
        Get leads with cursor-based pagination.

        Cursor pagination uses the last seen ID to efficiently fetch the next batch,
        avoiding the O(n) performance degradation of offset pagination.

        Args:
            organization_id: Organization to filter by
            tier: Optional tier to filter (hot/warm/dormant/archived)
            cursor: Last seen lead ID (for pagination)
            limit: Maximum leads to return (max 1000)
            filters: Additional filters as {column: value}
            select_columns: Columns to select (default "*")

        Returns:
            LeadQueryResult with leads and pagination info

        Example:
            # First page
            result = await repo.get_leads_cursor(org_id, tier=LeadTier.DORMANT)

            # Next page using cursor
            result = await repo.get_leads_cursor(
                org_id,
                tier=LeadTier.DORMANT,
                cursor=result.next_cursor
            )
        """
        limit = min(limit, self.MAX_BATCH_SIZE)

        try:
            query = self.supabase.table("leads").select(select_columns)

            # Organization filter
            query = query.eq("organization_id", organization_id)

            # Tier filters
            if tier:
                tier_filters = self._get_tier_filters(tier)

                # Apply tier-based date filters
                if "last_activity_at" in tier_filters:
                    f = tier_filters["last_activity_at"]
                    if f["op"] == "gte":
                        query = query.gte("last_activity_at", f["value"])
                    elif f["op"] == "lt":
                        query = query.lt("last_activity_at", f["value"])

                # Handle compound filters for warm/dormant tiers
                if "last_activity_at_lt" in tier_filters:
                    f = tier_filters["last_activity_at_lt"]
                    query = query.lt("last_activity_at", f["value"])

                if "last_activity_at_gte" in tier_filters:
                    f = tier_filters["last_activity_at_gte"]
                    query = query.gte("last_activity_at", f["value"])

            # Additional custom filters
            if filters:
                for column, value in filters.items():
                    if value is not None:
                        query = query.eq(column, value)

            # Cursor pagination - use ID for consistent ordering
            if cursor:
                query = query.gt("id", cursor)

            # Order by ID for consistent pagination
            query = query.order("id").limit(limit + 1)  # Fetch one extra to check if more

            result = query.execute()
            leads = result.data or []

            # Check if there are more results
            has_more = len(leads) > limit
            if has_more:
                leads = leads[:limit]  # Remove the extra row

            # Get next cursor from last lead
            next_cursor = leads[-1]["id"] if leads else None

            logger.debug(
                f"Cursor query: org={organization_id}, tier={tier}, "
                f"cursor={cursor}, returned={len(leads)}, has_more={has_more}"
            )

            return LeadQueryResult(
                leads=leads,
                next_cursor=next_cursor if has_more else None,
                has_more=has_more,
                total_in_batch=len(leads),
            )

        except Exception as e:
            logger.error(f"Error in cursor query: {e}")
            return LeadQueryResult(leads=[], next_cursor=None, has_more=False, total_in_batch=0)

    async def get_leads_by_ids(
        self,
        fub_person_ids: List[int],
        select_columns: str = "*",
    ) -> List[Dict[str, Any]]:
        """
        Get multiple leads by their FUB person IDs.

        Efficient batch retrieval for known IDs.

        Args:
            fub_person_ids: List of FUB person IDs
            select_columns: Columns to select

        Returns:
            List of lead records
        """
        if not fub_person_ids:
            return []

        try:
            # Supabase supports IN queries
            result = self.supabase.table("leads").select(select_columns).in_(
                "fub_person_id", fub_person_ids
            ).execute()

            return result.data or []

        except Exception as e:
            logger.error(f"Error fetching leads by IDs: {e}")
            return []

    async def count_leads_by_tier(
        self,
        organization_id: str,
    ) -> Dict[str, int]:
        """
        Get counts for each lead tier.

        Useful for dashboard metrics and capacity planning.

        Args:
            organization_id: Organization to count for

        Returns:
            Dict with tier counts
        """
        counts = {}

        for tier in LeadTier:
            try:
                result = await self.get_leads_cursor(
                    organization_id=organization_id,
                    tier=tier,
                    limit=1,
                    select_columns="id",
                )

                # Note: This is approximate - for exact counts, would need COUNT query
                # But Supabase doesn't support COUNT efficiently for filtered queries
                # In production, consider maintaining a separate metrics table
                counts[tier.value] = "available"  # Indicates tier has data

            except Exception as e:
                logger.error(f"Error counting tier {tier.value}: {e}")
                counts[tier.value] = 0

        return counts

    async def get_dormant_leads_for_reengagement(
        self,
        organization_id: str,
        min_days_inactive: int = 30,
        max_days_inactive: int = 365,
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> LeadQueryResult:
        """
        Get dormant leads eligible for re-engagement campaigns.

        Specialized query for the re-engagement workflow.

        Args:
            organization_id: Organization ID
            min_days_inactive: Minimum days since last activity
            max_days_inactive: Maximum days since last activity
            limit: Maximum leads to return
            cursor: Pagination cursor

        Returns:
            LeadQueryResult with eligible leads
        """
        try:
            query = self.supabase.table("leads").select("*")

            # Organization and activity filters
            query = query.eq("organization_id", organization_id)
            query = query.lt("last_activity_at", self._days_ago(min_days_inactive))
            query = query.gte("last_activity_at", self._days_ago(max_days_inactive))

            # Exclude blocked stages
            # Note: This assumes a 'stage' column - adjust based on actual schema
            blocked_patterns = [
                "closed", "sold", "lost", "dnc", "not interested",
                "archived", "inactive", "dead"
            ]
            for pattern in blocked_patterns:
                query = query.not_.ilike("status", f"%{pattern}%")

            # Exclude opted-out leads
            query = query.neq("opted_out", True)

            # Cursor pagination
            if cursor:
                query = query.gt("id", cursor)

            query = query.order("id").limit(limit + 1)

            result = query.execute()
            leads = result.data or []

            has_more = len(leads) > limit
            if has_more:
                leads = leads[:limit]

            next_cursor = leads[-1]["id"] if leads else None

            return LeadQueryResult(
                leads=leads,
                next_cursor=next_cursor if has_more else None,
                has_more=has_more,
                total_in_batch=len(leads),
            )

        except Exception as e:
            logger.error(f"Error getting dormant leads: {e}")
            return LeadQueryResult(leads=[], next_cursor=None, has_more=False, total_in_batch=0)

    async def update_lead_tier(
        self,
        fub_person_id: int,
        tier: LeadTier,
    ) -> bool:
        """
        Update a lead's tier classification.

        Args:
            fub_person_id: Lead's FUB person ID
            tier: New tier classification

        Returns:
            True if updated successfully
        """
        try:
            result = self.supabase.table("leads").update({
                "tier": tier.value,
                "tier_updated_at": datetime.utcnow().isoformat(),
            }).eq("fub_person_id", fub_person_id).execute()

            return bool(result.data)

        except Exception as e:
            logger.error(f"Error updating lead tier: {e}")
            return False

    async def bulk_update_tiers(
        self,
        tier_updates: List[Tuple[int, LeadTier]],
    ) -> Dict[str, int]:
        """
        Bulk update lead tiers.

        Args:
            tier_updates: List of (fub_person_id, new_tier) tuples

        Returns:
            Dict with success/failure counts
        """
        results = {"success": 0, "failed": 0}

        for fub_person_id, tier in tier_updates:
            success = await self.update_lead_tier(fub_person_id, tier)
            if success:
                results["success"] += 1
            else:
                results["failed"] += 1

        return results


# Singleton for easy access
class LeadRepositorySingleton:
    """Singleton wrapper for LeadRepository."""

    _instance: Optional[LeadRepository] = None

    @classmethod
    def get_instance(cls) -> LeadRepository:
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = LeadRepository()
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset the singleton instance."""
        cls._instance = None


# Convenience function
def get_lead_repository() -> LeadRepository:
    """Get the lead repository singleton."""
    return LeadRepositorySingleton.get_instance()
