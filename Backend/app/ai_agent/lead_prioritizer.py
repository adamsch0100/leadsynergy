"""
Lead Prioritizer - Intelligent scoring for re-engagement prioritization.

Scores dormant leads to prioritize re-engagement efforts based on:
- Recency of last contact (more recent = higher priority)
- Prior engagement history (responded before = good sign)
- Lead source quality (Redfin, referral = high value)
- Available qualification data (budget, timeline, preferences)
- Geographic match to agent's service area
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from app.database.lead_repository import get_lead_repository, LeadTier
from app.database.supabase_client import SupabaseClientSingleton

logger = logging.getLogger(__name__)


@dataclass
class PriorityScore:
    """Priority score breakdown for a lead."""
    fub_person_id: int
    total_score: int
    recency_score: int
    engagement_score: int
    source_score: int
    qualification_score: int
    breakdown: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fub_person_id": self.fub_person_id,
            "total_score": self.total_score,
            "recency_score": self.recency_score,
            "engagement_score": self.engagement_score,
            "source_score": self.source_score,
            "qualification_score": self.qualification_score,
            "breakdown": self.breakdown,
        }


class LeadPrioritizer:
    """
    Score dormant leads to prioritize re-engagement efforts.

    Higher score = higher priority for AI outreach.
    Score range: 0-100
    """

    # Scoring factors with point values
    SCORING_FACTORS = {
        # Recency scoring - recently dormant leads are higher priority
        "days_since_contact": {
            "30-60": 15,    # Recently dormant - highest priority
            "60-90": 12,
            "90-180": 8,
            "180-365": 4,
            "365+": 1,      # Very old - low priority
        },

        # Prior engagement - they responded before = good sign
        "engagement_history": {
            "responded_multiple": 20,    # Multiple responses - very engaged
            "responded_once": 15,        # At least one response
            "opened_email": 5,           # Email engagement
            "never_responded": 0,
        },

        # Lead source quality
        "lead_source_quality": {
            "referral": 15,              # Referrals are highest quality
            "redfin": 12,
            "zillow": 10,
            "realtor.com": 10,
            "trulia": 9,
            "homelight": 12,
            "website": 8,                # Direct website inquiry
            "open_house": 10,            # In-person contact
            "cold_list": 2,              # Purchased lists are low quality
            "unknown": 3,
        },

        # Qualification data available
        "has_property_preferences": 10,   # We know what they want
        "has_timeline": 12,               # They shared timeline
        "has_budget": 10,                 # They shared budget
        "has_preapproval": 15,            # Pre-approved buyer
        "geographic_match": 8,            # In agent's service area

        # Negative factors (subtract from score)
        "had_objection": -5,              # Previous objection noted
        "multiple_no_response": -10,      # Tried multiple times, no response
    }

    # Minimum score threshold for re-engagement (leads below this are skipped)
    MIN_REENGAGEMENT_SCORE = 20

    def __init__(self, supabase_client=None):
        """
        Initialize Lead Prioritizer.

        Args:
            supabase_client: Optional Supabase client
        """
        self.supabase = supabase_client or SupabaseClientSingleton.get_instance()
        self.lead_repo = get_lead_repository()

    async def calculate_priority_score(
        self,
        lead: Dict[str, Any],
        conversation: Dict[str, Any] = None,
    ) -> PriorityScore:
        """
        Calculate priority score for re-engagement.

        Args:
            lead: Lead record from database
            conversation: AI conversation record (optional)

        Returns:
            PriorityScore with total and breakdown
        """
        breakdown = {}
        fub_person_id = lead.get("fub_person_id", 0)

        # 1. Recency Score (how long since last contact)
        recency_score = self._calculate_recency_score(lead, breakdown)

        # 2. Engagement Score (did they respond before?)
        engagement_score = self._calculate_engagement_score(lead, conversation, breakdown)

        # 3. Source Score (lead quality based on source)
        source_score = self._calculate_source_score(lead, breakdown)

        # 4. Qualification Score (how much we know about them)
        qualification_score = self._calculate_qualification_score(lead, conversation, breakdown)

        # Calculate total (capped at 100)
        total_score = min(
            recency_score + engagement_score + source_score + qualification_score,
            100
        )

        # Ensure minimum of 0
        total_score = max(total_score, 0)

        return PriorityScore(
            fub_person_id=fub_person_id,
            total_score=total_score,
            recency_score=recency_score,
            engagement_score=engagement_score,
            source_score=source_score,
            qualification_score=qualification_score,
            breakdown=breakdown,
        )

    def _calculate_recency_score(
        self,
        lead: Dict[str, Any],
        breakdown: Dict[str, int],
    ) -> int:
        """Calculate score based on days since last contact."""
        score = 0

        last_contact = lead.get("last_activity_at") or lead.get("last_contact_at")
        if not last_contact:
            breakdown["recency"] = 1
            return 1  # No contact date - assume very old

        # Parse date if string
        if isinstance(last_contact, str):
            try:
                last_contact = datetime.fromisoformat(last_contact.replace("Z", "+00:00"))
            except:
                breakdown["recency"] = 1
                return 1

        days = (datetime.utcnow() - last_contact.replace(tzinfo=None)).days

        if 30 <= days < 60:
            score = self.SCORING_FACTORS["days_since_contact"]["30-60"]
            breakdown["recency_30_60_days"] = score
        elif 60 <= days < 90:
            score = self.SCORING_FACTORS["days_since_contact"]["60-90"]
            breakdown["recency_60_90_days"] = score
        elif 90 <= days < 180:
            score = self.SCORING_FACTORS["days_since_contact"]["90-180"]
            breakdown["recency_90_180_days"] = score
        elif 180 <= days < 365:
            score = self.SCORING_FACTORS["days_since_contact"]["180-365"]
            breakdown["recency_180_365_days"] = score
        else:
            score = self.SCORING_FACTORS["days_since_contact"]["365+"]
            breakdown["recency_365_plus_days"] = score

        return score

    def _calculate_engagement_score(
        self,
        lead: Dict[str, Any],
        conversation: Dict[str, Any],
        breakdown: Dict[str, int],
    ) -> int:
        """Calculate score based on prior engagement."""
        score = 0

        # Check conversation history
        if conversation:
            message_count = conversation.get("lead_message_count", 0)
            if message_count > 1:
                score = self.SCORING_FACTORS["engagement_history"]["responded_multiple"]
                breakdown["responded_multiple_times"] = score
            elif message_count == 1:
                score = self.SCORING_FACTORS["engagement_history"]["responded_once"]
                breakdown["responded_once"] = score

            # Check for previous objections (negative)
            qual_data = conversation.get("qualification_data", {})
            if qual_data.get("has_objection"):
                penalty = self.SCORING_FACTORS.get("had_objection", -5)
                score += penalty
                breakdown["had_objection"] = penalty

        # Check for multiple failed attempts (negative)
        re_engagement_count = lead.get("re_engagement_count", 0)
        if re_engagement_count > 2:
            penalty = self.SCORING_FACTORS.get("multiple_no_response", -10)
            score += penalty
            breakdown["multiple_failed_attempts"] = penalty

        return max(score, 0)

    def _calculate_source_score(
        self,
        lead: Dict[str, Any],
        breakdown: Dict[str, int],
    ) -> int:
        """Calculate score based on lead source quality."""
        source = lead.get("source", "").lower() if lead.get("source") else ""

        source_scores = self.SCORING_FACTORS["lead_source_quality"]

        # Check each source pattern
        for source_key, source_score in source_scores.items():
            if source_key in source:
                breakdown[f"source_{source_key}"] = source_score
                return source_score

        # Default for unknown sources
        breakdown["source_unknown"] = source_scores["unknown"]
        return source_scores["unknown"]

    def _calculate_qualification_score(
        self,
        lead: Dict[str, Any],
        conversation: Dict[str, Any],
        breakdown: Dict[str, int],
    ) -> int:
        """Calculate score based on available qualification data."""
        score = 0
        qual_data = {}

        # Get qualification data from conversation or lead
        if conversation:
            qual_data = conversation.get("qualification_data", {})

        # Check for property preferences
        if qual_data.get("property_preferences") or lead.get("property_type"):
            points = self.SCORING_FACTORS["has_property_preferences"]
            score += points
            breakdown["has_property_preferences"] = points

        # Check for timeline
        if qual_data.get("timeline") or lead.get("timeline"):
            points = self.SCORING_FACTORS["has_timeline"]
            score += points
            breakdown["has_timeline"] = points

        # Check for budget
        if qual_data.get("budget") or lead.get("price_range"):
            points = self.SCORING_FACTORS["has_budget"]
            score += points
            breakdown["has_budget"] = points

        # Check for pre-approval
        if qual_data.get("pre_approved") or lead.get("pre_approved"):
            points = self.SCORING_FACTORS["has_preapproval"]
            score += points
            breakdown["has_preapproval"] = points

        # Check for geographic match (simplified check)
        if lead.get("city") or lead.get("zip_code") or qual_data.get("preferred_area"):
            points = self.SCORING_FACTORS["geographic_match"]
            score += points
            breakdown["geographic_match"] = points

        return score

    async def get_top_reengagement_leads(
        self,
        organization_id: str,
        limit: int = 100,
        min_score: int = None,
    ) -> List[Dict[str, Any]]:
        """
        Get top leads to re-engage, sorted by priority score.

        Args:
            organization_id: Organization ID
            limit: Maximum leads to return
            min_score: Minimum score threshold (default: MIN_REENGAGEMENT_SCORE)

        Returns:
            List of leads with their priority scores
        """
        min_score = min_score or self.MIN_REENGAGEMENT_SCORE
        scored_leads = []
        cursor = None

        logger.info(f"Finding top {limit} re-engagement leads for org {organization_id}")

        # Get leads from dormant tier
        while len(scored_leads) < limit * 2:  # Get 2x to account for filtering
            result = await self.lead_repo.get_leads_cursor(
                organization_id=organization_id,
                tier=LeadTier.DORMANT,
                cursor=cursor,
                limit=500,
            )

            if not result.leads:
                break

            # Score each lead
            for lead in result.leads:
                fub_person_id = lead.get("fub_person_id")

                # Get conversation if available
                conversation = await self._get_conversation(fub_person_id)

                # Calculate score
                priority = await self.calculate_priority_score(lead, conversation)

                if priority.total_score >= min_score:
                    scored_leads.append({
                        **lead,
                        "priority_score": priority.total_score,
                        "priority_breakdown": priority.breakdown,
                    })

            if not result.has_more:
                break
            cursor = result.next_cursor

        # Sort by priority score (highest first)
        scored_leads.sort(key=lambda x: x["priority_score"], reverse=True)

        # Return top N
        return scored_leads[:limit]

    async def _get_conversation(self, fub_person_id: int) -> Optional[Dict[str, Any]]:
        """Get AI conversation record for a lead."""
        try:
            result = self.supabase.table("ai_conversations").select("*").eq(
                "fub_person_id", fub_person_id
            ).limit(1).execute()

            return result.data[0] if result.data else None
        except Exception as e:
            logger.debug(f"Could not get conversation for {fub_person_id}: {e}")
            return None

    async def batch_calculate_scores(
        self,
        fub_person_ids: List[int],
    ) -> Dict[int, PriorityScore]:
        """
        Calculate priority scores for a batch of leads.

        Args:
            fub_person_ids: List of FUB person IDs

        Returns:
            Dict mapping person_id to PriorityScore
        """
        scores = {}

        # Get leads in batch
        leads = await self.lead_repo.get_leads_by_ids(fub_person_ids)
        lead_map = {l["fub_person_id"]: l for l in leads}

        for person_id in fub_person_ids:
            lead = lead_map.get(person_id, {})
            conversation = await self._get_conversation(person_id)
            score = await self.calculate_priority_score(lead, conversation)
            scores[person_id] = score

        return scores


# Singleton access
class LeadPrioritizerSingleton:
    """Singleton wrapper for LeadPrioritizer."""

    _instance: Optional[LeadPrioritizer] = None

    @classmethod
    def get_instance(cls) -> LeadPrioritizer:
        if cls._instance is None:
            cls._instance = LeadPrioritizer()
        return cls._instance


def get_lead_prioritizer() -> LeadPrioritizer:
    """Get the lead prioritizer singleton."""
    return LeadPrioritizerSingleton.get_instance()
