"""
Re-engagement Campaign Manager - Bulk campaign orchestration for dormant leads.

Manages re-engagement campaigns that reach out to dormant leads in bulk:
- Market update campaigns
- Price drop alerts
- "Just checking in" touchpoints
- New listings announcements

Key features:
- Daily send limits to avoid overwhelming recipients
- Priority-based lead selection
- Automatic cancellation when leads respond
- Campaign analytics and tracking
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import uuid

from app.database.supabase_client import SupabaseClientSingleton
from app.ai_agent.lead_prioritizer import get_lead_prioritizer, LeadPrioritizer
from app.ai_agent.followup_manager import get_next_valid_send_time

logger = logging.getLogger(__name__)


class CampaignType(Enum):
    """Types of re-engagement campaigns."""
    MARKET_UPDATE = "market_update"
    PRICE_DROP_ALERT = "price_drop_alert"
    JUST_CHECKING_IN = "just_checking_in"
    NEW_LISTINGS = "new_listings"
    CUSTOM = "custom"


class CampaignStatus(Enum):
    """Campaign lifecycle status."""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class CampaignConfig:
    """Configuration for a campaign type."""
    campaign_type: CampaignType
    best_for: List[str]  # ["buyers", "sellers", "all"]
    requires: List[str]  # Required lead data fields
    frequency: str  # "weekly", "monthly", "quarterly"
    default_message_template: str


# Campaign type configurations
CAMPAIGN_CONFIGS = {
    CampaignType.MARKET_UPDATE: CampaignConfig(
        campaign_type=CampaignType.MARKET_UPDATE,
        best_for=["buyers", "sellers"],
        requires=[],
        frequency="monthly",
        default_message_template="market_update_v1",
    ),
    CampaignType.PRICE_DROP_ALERT: CampaignConfig(
        campaign_type=CampaignType.PRICE_DROP_ALERT,
        best_for=["buyers"],
        requires=["property_preferences"],
        frequency="weekly",
        default_message_template="price_drop_v1",
    ),
    CampaignType.JUST_CHECKING_IN: CampaignConfig(
        campaign_type=CampaignType.JUST_CHECKING_IN,
        best_for=["all"],
        requires=[],
        frequency="quarterly",
        default_message_template="check_in_v1",
    ),
    CampaignType.NEW_LISTINGS: CampaignConfig(
        campaign_type=CampaignType.NEW_LISTINGS,
        best_for=["buyers"],
        requires=["property_preferences"],
        frequency="weekly",
        default_message_template="new_listings_v1",
    ),
}


@dataclass
class Campaign:
    """Campaign record."""
    id: str
    organization_id: str
    campaign_name: str
    campaign_type: CampaignType
    status: CampaignStatus
    total_leads: int
    leads_processed: int
    messages_sent: int
    leads_responded: int
    leads_converted: int
    daily_limit: int
    lead_filters: Dict[str, Any]
    target_tiers: List[str]
    message_template: Optional[str]
    custom_message: Optional[str]
    scheduled_start_at: Optional[datetime]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    cancelled_at: Optional[datetime]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "campaign_name": self.campaign_name,
            "campaign_type": self.campaign_type.value,
            "status": self.status.value,
            "total_leads": self.total_leads,
            "leads_processed": self.leads_processed,
            "messages_sent": self.messages_sent,
            "leads_responded": self.leads_responded,
            "leads_converted": self.leads_converted,
            "response_rate": round(self.leads_responded / self.messages_sent * 100, 1) if self.messages_sent > 0 else 0,
            "conversion_rate": round(self.leads_converted / self.leads_responded * 100, 1) if self.leads_responded > 0 else 0,
            "daily_limit": self.daily_limit,
            "lead_filters": self.lead_filters,
            "target_tiers": self.target_tiers,
            "message_template": self.message_template,
            "scheduled_start_at": self.scheduled_start_at.isoformat() if self.scheduled_start_at else None,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class ReengagementCampaignManager:
    """
    Manage bulk re-engagement campaigns for dormant leads.

    Handles campaign creation, scheduling, execution, and analytics.
    """

    DEFAULT_DAILY_LIMIT = 200
    MAX_DAILY_LIMIT = 500

    def __init__(self, supabase_client=None):
        """
        Initialize Re-engagement Campaign Manager.

        Args:
            supabase_client: Optional Supabase client
        """
        self.supabase = supabase_client or SupabaseClientSingleton.get_instance()
        self.prioritizer = get_lead_prioritizer()

    async def create_campaign(
        self,
        organization_id: str,
        campaign_name: str,
        campaign_type: CampaignType,
        lead_filters: Dict[str, Any] = None,
        max_leads: int = 1000,
        daily_send_limit: int = None,
        message_template: str = None,
        custom_message: str = None,
        scheduled_start_at: datetime = None,
        created_by: str = None,
    ) -> Campaign:
        """
        Create a new re-engagement campaign.

        Args:
            organization_id: Organization ID
            campaign_name: Human-readable campaign name
            campaign_type: Type of campaign
            lead_filters: Additional filters for lead selection
            max_leads: Maximum leads to include
            daily_send_limit: Max messages per day (default 200)
            message_template: Template to use for messages
            custom_message: Custom message content (for CUSTOM type)
            scheduled_start_at: When to start the campaign
            created_by: User ID who created the campaign

        Returns:
            Campaign object
        """
        campaign_id = str(uuid.uuid4())
        daily_limit = min(daily_send_limit or self.DEFAULT_DAILY_LIMIT, self.MAX_DAILY_LIMIT)
        lead_filters = lead_filters or {}

        logger.info(
            f"Creating campaign {campaign_id}: {campaign_name} "
            f"(type={campaign_type.value}, max_leads={max_leads})"
        )

        # Get prioritized leads
        leads = await self.prioritizer.get_top_reengagement_leads(
            organization_id=organization_id,
            limit=max_leads,
        )

        # Apply additional filters
        if lead_filters:
            leads = self._apply_filters(leads, lead_filters)

        total_leads = len(leads)
        logger.info(f"Campaign {campaign_id}: Found {total_leads} eligible leads")

        if total_leads == 0:
            logger.warning(f"Campaign {campaign_id}: No eligible leads found")

        # Get default template if not specified
        if not message_template and campaign_type != CampaignType.CUSTOM:
            config = CAMPAIGN_CONFIGS.get(campaign_type)
            message_template = config.default_message_template if config else None

        # Calculate days needed
        days_needed = (total_leads + daily_limit - 1) // daily_limit if daily_limit > 0 else 1

        # Create campaign record
        campaign_data = {
            "id": campaign_id,
            "organization_id": organization_id,
            "campaign_name": campaign_name,
            "campaign_type": campaign_type.value,
            "status": CampaignStatus.SCHEDULED.value,
            "total_leads": total_leads,
            "leads_processed": 0,
            "messages_sent": 0,
            "leads_responded": 0,
            "leads_converted": 0,
            "daily_limit": daily_limit,
            "lead_filters": lead_filters,
            "target_tiers": ["dormant"],
            "message_template": message_template,
            "custom_message": custom_message,
            "scheduled_start_at": (scheduled_start_at or datetime.utcnow()).isoformat(),
            "created_at": datetime.utcnow().isoformat(),
            "created_by": created_by,
        }

        try:
            self.supabase.table("ai_campaigns").insert(campaign_data).execute()
        except Exception as e:
            logger.error(f"Error creating campaign: {e}")
            raise

        # Add leads to campaign with batch assignments
        await self._assign_leads_to_batches(campaign_id, leads, daily_limit)

        campaign = Campaign(
            id=campaign_id,
            organization_id=organization_id,
            campaign_name=campaign_name,
            campaign_type=campaign_type,
            status=CampaignStatus.SCHEDULED,
            total_leads=total_leads,
            leads_processed=0,
            messages_sent=0,
            leads_responded=0,
            leads_converted=0,
            daily_limit=daily_limit,
            lead_filters=lead_filters,
            target_tiers=["dormant"],
            message_template=message_template,
            custom_message=custom_message,
            scheduled_start_at=scheduled_start_at or datetime.utcnow(),
            created_at=datetime.utcnow(),
            started_at=None,
            completed_at=None,
            cancelled_at=None,
        )

        logger.info(
            f"Campaign {campaign_id} created: {total_leads} leads, "
            f"{days_needed} days at {daily_limit}/day"
        )

        return campaign

    async def _assign_leads_to_batches(
        self,
        campaign_id: str,
        leads: List[Dict[str, Any]],
        daily_limit: int,
    ):
        """Assign leads to daily batches for sending."""
        batch_data = []

        for i, lead in enumerate(leads):
            batch_num = i // daily_limit  # Which day this lead will be sent
            batch_data.append({
                "campaign_id": campaign_id,
                "fub_person_id": lead["fub_person_id"],
                "status": "pending",
                "priority_score": lead.get("priority_score", 0),
                "scheduled_batch": batch_num,
                "created_at": datetime.utcnow().isoformat(),
            })

        # Insert in batches of 100
        for i in range(0, len(batch_data), 100):
            chunk = batch_data[i:i + 100]
            try:
                self.supabase.table("ai_campaign_leads").insert(chunk).execute()
            except Exception as e:
                logger.error(f"Error inserting campaign leads: {e}")

    def _apply_filters(
        self,
        leads: List[Dict[str, Any]],
        filters: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Apply additional filters to lead list."""
        filtered = []

        for lead in leads:
            include = True

            # Source filter
            if "sources" in filters:
                source = lead.get("source", "").lower()
                if not any(s.lower() in source for s in filters["sources"]):
                    include = False

            # Min score filter
            if "min_score" in filters:
                if lead.get("priority_score", 0) < filters["min_score"]:
                    include = False

            # Max score filter
            if "max_score" in filters:
                if lead.get("priority_score", 0) > filters["max_score"]:
                    include = False

            # Lead type filter
            if "lead_types" in filters:
                lead_type = lead.get("type", "").lower()
                if lead_type not in [t.lower() for t in filters["lead_types"]]:
                    include = False

            if include:
                filtered.append(lead)

        return filtered

    async def start_campaign(self, campaign_id: str) -> bool:
        """
        Start a scheduled campaign.

        Args:
            campaign_id: Campaign ID to start

        Returns:
            True if started successfully
        """
        try:
            self.supabase.table("ai_campaigns").update({
                "status": CampaignStatus.RUNNING.value,
                "started_at": datetime.utcnow().isoformat(),
            }).eq("id", campaign_id).eq("status", CampaignStatus.SCHEDULED.value).execute()

            logger.info(f"Campaign {campaign_id} started")
            return True
        except Exception as e:
            logger.error(f"Error starting campaign {campaign_id}: {e}")
            return False

    async def pause_campaign(self, campaign_id: str) -> bool:
        """Pause a running campaign."""
        try:
            self.supabase.table("ai_campaigns").update({
                "status": CampaignStatus.PAUSED.value,
            }).eq("id", campaign_id).eq("status", CampaignStatus.RUNNING.value).execute()

            logger.info(f"Campaign {campaign_id} paused")
            return True
        except Exception as e:
            logger.error(f"Error pausing campaign {campaign_id}: {e}")
            return False

    async def resume_campaign(self, campaign_id: str) -> bool:
        """Resume a paused campaign."""
        try:
            self.supabase.table("ai_campaigns").update({
                "status": CampaignStatus.RUNNING.value,
            }).eq("id", campaign_id).eq("status", CampaignStatus.PAUSED.value).execute()

            logger.info(f"Campaign {campaign_id} resumed")
            return True
        except Exception as e:
            logger.error(f"Error resuming campaign {campaign_id}: {e}")
            return False

    async def cancel_campaign(self, campaign_id: str) -> bool:
        """Cancel a campaign (cannot be undone)."""
        try:
            self.supabase.table("ai_campaigns").update({
                "status": CampaignStatus.CANCELLED.value,
                "cancelled_at": datetime.utcnow().isoformat(),
            }).eq("id", campaign_id).in_(
                "status", [CampaignStatus.SCHEDULED.value, CampaignStatus.RUNNING.value, CampaignStatus.PAUSED.value]
            ).execute()

            # Cancel all pending leads
            self.supabase.table("ai_campaign_leads").update({
                "status": "skipped",
            }).eq("campaign_id", campaign_id).eq("status", "pending").execute()

            logger.info(f"Campaign {campaign_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"Error cancelling campaign {campaign_id}: {e}")
            return False

    async def get_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """Get campaign by ID."""
        try:
            result = self.supabase.table("ai_campaigns").select("*").eq("id", campaign_id).single().execute()

            if not result.data:
                return None

            data = result.data
            return Campaign(
                id=data["id"],
                organization_id=data["organization_id"],
                campaign_name=data["campaign_name"],
                campaign_type=CampaignType(data["campaign_type"]),
                status=CampaignStatus(data["status"]),
                total_leads=data["total_leads"],
                leads_processed=data["leads_processed"],
                messages_sent=data["messages_sent"],
                leads_responded=data["leads_responded"],
                leads_converted=data["leads_converted"],
                daily_limit=data["daily_limit"],
                lead_filters=data.get("lead_filters", {}),
                target_tiers=data.get("target_tiers", ["dormant"]),
                message_template=data.get("message_template"),
                custom_message=data.get("custom_message"),
                scheduled_start_at=datetime.fromisoformat(data["scheduled_start_at"]) if data.get("scheduled_start_at") else None,
                created_at=datetime.fromisoformat(data["created_at"]),
                started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
                completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
                cancelled_at=datetime.fromisoformat(data["cancelled_at"]) if data.get("cancelled_at") else None,
            )
        except Exception as e:
            logger.error(f"Error getting campaign {campaign_id}: {e}")
            return None

    async def get_campaigns(
        self,
        organization_id: str,
        status: CampaignStatus = None,
        limit: int = 50,
    ) -> List[Campaign]:
        """Get campaigns for an organization."""
        try:
            query = self.supabase.table("ai_campaigns").select("*").eq("organization_id", organization_id)

            if status:
                query = query.eq("status", status.value)

            query = query.order("created_at", desc=True).limit(limit)
            result = query.execute()

            campaigns = []
            for data in result.data or []:
                campaigns.append(Campaign(
                    id=data["id"],
                    organization_id=data["organization_id"],
                    campaign_name=data["campaign_name"],
                    campaign_type=CampaignType(data["campaign_type"]),
                    status=CampaignStatus(data["status"]),
                    total_leads=data["total_leads"],
                    leads_processed=data["leads_processed"],
                    messages_sent=data["messages_sent"],
                    leads_responded=data["leads_responded"],
                    leads_converted=data["leads_converted"],
                    daily_limit=data["daily_limit"],
                    lead_filters=data.get("lead_filters", {}),
                    target_tiers=data.get("target_tiers", ["dormant"]),
                    message_template=data.get("message_template"),
                    custom_message=data.get("custom_message"),
                    scheduled_start_at=datetime.fromisoformat(data["scheduled_start_at"]) if data.get("scheduled_start_at") else None,
                    created_at=datetime.fromisoformat(data["created_at"]),
                    started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
                    completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
                    cancelled_at=datetime.fromisoformat(data["cancelled_at"]) if data.get("cancelled_at") else None,
                ))

            return campaigns
        except Exception as e:
            logger.error(f"Error getting campaigns: {e}")
            return []

    async def get_pending_batch(
        self,
        campaign_id: str,
        batch_num: int,
    ) -> List[Dict[str, Any]]:
        """Get pending leads for a specific batch."""
        try:
            result = self.supabase.table("ai_campaign_leads").select("*").eq(
                "campaign_id", campaign_id
            ).eq(
                "scheduled_batch", batch_num
            ).eq(
                "status", "pending"
            ).order("priority_score", desc=True).execute()

            return result.data or []
        except Exception as e:
            logger.error(f"Error getting batch: {e}")
            return []

    async def mark_lead_sent(
        self,
        campaign_id: str,
        fub_person_id: int,
    ) -> bool:
        """Mark a campaign lead as sent."""
        try:
            self.supabase.table("ai_campaign_leads").update({
                "status": "sent",
                "sent_at": datetime.utcnow().isoformat(),
            }).eq("campaign_id", campaign_id).eq("fub_person_id", fub_person_id).execute()

            return True
        except Exception as e:
            logger.error(f"Error marking lead sent: {e}")
            return False

    async def mark_lead_responded(
        self,
        fub_person_id: int,
    ) -> int:
        """
        Mark a lead as responded across all active campaigns.

        Returns number of campaigns updated.
        """
        try:
            result = self.supabase.table("ai_campaign_leads").update({
                "status": "responded",
                "responded_at": datetime.utcnow().isoformat(),
            }).eq("fub_person_id", fub_person_id).eq("status", "sent").execute()

            return len(result.data) if result.data else 0
        except Exception as e:
            logger.error(f"Error marking lead responded: {e}")
            return 0

    async def get_campaign_analytics(
        self,
        campaign_id: str,
    ) -> Dict[str, Any]:
        """Get detailed analytics for a campaign."""
        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            return {}

        # Get lead status breakdown
        try:
            result = self.supabase.rpc("get_campaign_lead_stats", {
                "p_campaign_id": campaign_id
            }).execute()

            status_breakdown = result.data if result.data else {}
        except:
            status_breakdown = {}

        return {
            "campaign": campaign.to_dict(),
            "status_breakdown": status_breakdown,
            "days_elapsed": (datetime.utcnow() - campaign.started_at).days if campaign.started_at else 0,
            "estimated_days_remaining": (campaign.total_leads - campaign.leads_processed) // campaign.daily_limit if campaign.daily_limit > 0 else 0,
        }


# Singleton access
class ReengagementCampaignManagerSingleton:
    """Singleton wrapper for ReengagementCampaignManager."""

    _instance: Optional[ReengagementCampaignManager] = None

    @classmethod
    def get_instance(cls) -> ReengagementCampaignManager:
        if cls._instance is None:
            cls._instance = ReengagementCampaignManager()
        return cls._instance


def get_campaign_manager() -> ReengagementCampaignManager:
    """Get the campaign manager singleton."""
    return ReengagementCampaignManagerSingleton.get_instance()
