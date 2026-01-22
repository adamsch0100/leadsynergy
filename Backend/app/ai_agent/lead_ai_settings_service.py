"""
Service for managing per-lead AI auto-respond settings.

Allows granular control over which leads receive AI responses:
- Enable AI for new leads automatically
- Toggle AI on/off for specific leads
- Bulk enable for "revival" campaigns
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from supabase import Client

logger = logging.getLogger(__name__)


class LeadAISettingsService:
    """Service for managing per-lead AI settings."""

    def __init__(self, supabase_client: Client):
        """
        Initialize the service.

        Args:
            supabase_client: Supabase client for database access
        """
        self.supabase = supabase_client
        self.table_name = "lead_ai_settings"

    async def is_ai_enabled_for_lead(
        self,
        fub_person_id: str,
        organization_id: str,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Check if AI auto-respond is enabled for a specific lead.

        Args:
            fub_person_id: FUB person ID
            organization_id: Organization ID
            user_id: Optional user ID

        Returns:
            True if AI is enabled for this lead, False otherwise
        """
        try:
            result = (
                self.supabase.table(self.table_name)
                .select("ai_enabled")
                .eq("fub_person_id", fub_person_id)
                .eq("organization_id", organization_id)
                .execute()
            )

            if result.data and len(result.data) > 0:
                return result.data[0].get("ai_enabled", False)

            # No record found - return None to indicate "use global setting"
            return None

        except Exception as e:
            logger.error(f"Error checking AI enabled for lead {fub_person_id}: {e}")
            return None

    async def enable_ai_for_lead(
        self,
        fub_person_id: str,
        organization_id: str,
        user_id: str,
        reason: str = "manual",
        enabled_by: Optional[str] = None,
    ) -> bool:
        """
        Enable AI auto-respond for a specific lead.

        Args:
            fub_person_id: FUB person ID
            organization_id: Organization ID
            user_id: User ID
            reason: Reason for enabling ('new_lead', 'revival', 'manual')
            enabled_by: User ID who enabled it

        Returns:
            True if successful, False otherwise
        """
        try:
            data = {
                "fub_person_id": fub_person_id,
                "organization_id": organization_id,
                "user_id": user_id,
                "ai_enabled": True,
                "enabled_at": datetime.now().isoformat(),
                "disabled_at": None,
                "enabled_by": enabled_by or user_id,
                "reason": reason,
                "updated_at": datetime.now().isoformat(),
            }

            # Upsert (insert or update)
            result = (
                self.supabase.table(self.table_name)
                .upsert(data, on_conflict="fub_person_id,organization_id")
                .execute()
            )

            return result.data and len(result.data) > 0

        except Exception as e:
            logger.error(f"Error enabling AI for lead {fub_person_id}: {e}")
            return False

    async def disable_ai_for_lead(
        self,
        fub_person_id: str,
        organization_id: str,
    ) -> bool:
        """
        Disable AI auto-respond for a specific lead.

        Args:
            fub_person_id: FUB person ID
            organization_id: Organization ID

        Returns:
            True if successful, False otherwise
        """
        try:
            result = (
                self.supabase.table(self.table_name)
                .update(
                    {
                        "ai_enabled": False,
                        "disabled_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat(),
                    }
                )
                .eq("fub_person_id", fub_person_id)
                .eq("organization_id", organization_id)
                .execute()
            )

            return result.data and len(result.data) > 0

        except Exception as e:
            logger.error(f"Error disabling AI for lead {fub_person_id}: {e}")
            return False

    async def bulk_enable_ai(
        self,
        fub_person_ids: List[str],
        organization_id: str,
        user_id: str,
        reason: str = "bulk_enable",
        enabled_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Enable AI for multiple leads at once.

        Args:
            fub_person_ids: List of FUB person IDs
            organization_id: Organization ID
            user_id: User ID
            reason: Reason for enabling
            enabled_by: User ID who enabled it

        Returns:
            Dict with 'success_count' and 'failed_count'
        """
        success_count = 0
        failed_count = 0

        for person_id in fub_person_ids:
            success = await self.enable_ai_for_lead(
                fub_person_id=person_id,
                organization_id=organization_id,
                user_id=user_id,
                reason=reason,
                enabled_by=enabled_by,
            )
            if success:
                success_count += 1
            else:
                failed_count += 1

        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "total": len(fub_person_ids),
        }

    async def get_ai_enabled_leads(
        self,
        organization_id: str,
        user_id: Optional[str] = None,
    ) -> List[str]:
        """
        Get list of FUB person IDs with AI enabled.

        Args:
            organization_id: Organization ID
            user_id: Optional user ID filter

        Returns:
            List of FUB person IDs
        """
        try:
            query = (
                self.supabase.table(self.table_name)
                .select("fub_person_id")
                .eq("organization_id", organization_id)
                .eq("ai_enabled", True)
            )

            if user_id:
                query = query.eq("user_id", user_id)

            result = query.execute()

            if result.data:
                return [row["fub_person_id"] for row in result.data]

            return []

        except Exception as e:
            logger.error(f"Error getting AI enabled leads: {e}")
            return []


class LeadAISettingsServiceSingleton:
    """Singleton for LeadAISettingsService."""

    _instance = None

    @classmethod
    def get_instance(cls, supabase_client: Client = None) -> LeadAISettingsService:
        """Get or create singleton instance."""
        if cls._instance is None:
            if supabase_client is None:
                from app.database.supabase_client import SupabaseClientSingleton
                supabase_client = SupabaseClientSingleton.get_instance()
            cls._instance = LeadAISettingsService(supabase_client)
        return cls._instance
