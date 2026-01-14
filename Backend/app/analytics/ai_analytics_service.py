"""
AI Analytics Service - Comprehensive metrics for the AI sales agent.

Provides:
- Performance metrics (speed to lead, response rates, conversion rates)
- Lead funnel analysis
- A/B test tracking and statistical analysis
- Agent performance comparisons
- Compliance metrics
- ROI calculations
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import statistics

logger = logging.getLogger(__name__)


class AnalyticsPeriod(Enum):
    """Time periods for analytics."""
    TODAY = "today"
    YESTERDAY = "yesterday"
    LAST_7_DAYS = "7d"
    LAST_30_DAYS = "30d"
    LAST_90_DAYS = "90d"
    THIS_MONTH = "month"
    THIS_QUARTER = "quarter"
    THIS_YEAR = "year"
    CUSTOM = "custom"


@dataclass
class MetricsSummary:
    """Summary of key AI agent metrics."""
    # Speed & Responsiveness
    avg_speed_to_lead_seconds: float = 0.0
    median_speed_to_lead_seconds: float = 0.0
    avg_response_time_seconds: float = 0.0

    # Engagement
    total_conversations: int = 0
    total_messages_sent: int = 0
    total_messages_received: int = 0
    response_rate: float = 0.0  # % of leads that replied

    # Qualification
    leads_qualified: int = 0
    qualification_rate: float = 0.0  # % where we got key info
    avg_qualification_questions_asked: float = 0.0

    # Conversion
    appointments_booked: int = 0
    appointment_rate: float = 0.0  # % that booked
    handoffs_triggered: int = 0
    handoff_rate: float = 0.0

    # Compliance
    opt_outs: int = 0
    opt_out_rate: float = 0.0
    compliance_blocked: int = 0

    # Efficiency
    messages_per_appointment: float = 0.0
    avg_conversation_length: float = 0.0

    # Period info
    period: str = ""
    start_date: str = ""
    end_date: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConversionFunnel:
    """Lead conversion funnel data."""
    total_leads: int = 0
    contacted: int = 0
    responded: int = 0
    qualified: int = 0
    appointment_requested: int = 0
    appointment_booked: int = 0
    handed_off: int = 0

    # Conversion rates between stages
    contact_rate: float = 0.0
    response_rate: float = 0.0
    qualification_rate: float = 0.0
    appointment_request_rate: float = 0.0
    booking_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentPerformance:
    """Performance metrics for individual AI agent users."""
    user_id: str = ""
    user_name: str = ""
    conversations: int = 0
    appointments_booked: int = 0
    response_rate: float = 0.0
    avg_lead_score: float = 0.0
    opt_out_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ABTestResult:
    """A/B test performance data."""
    template_category: str = ""
    variant_a: str = ""
    variant_b: str = ""
    variant_a_sends: int = 0
    variant_b_sends: int = 0
    variant_a_responses: int = 0
    variant_b_responses: int = 0
    variant_a_response_rate: float = 0.0
    variant_b_response_rate: float = 0.0
    variant_a_appointments: int = 0
    variant_b_appointments: int = 0
    winner: str = ""  # "a", "b", or "inconclusive"
    statistical_significance: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AIAnalyticsService:
    """
    Service for computing and retrieving AI agent analytics.

    Usage:
        service = AIAnalyticsService(supabase_client)

        # Get summary metrics
        summary = await service.get_metrics_summary(
            organization_id="org123",
            period=AnalyticsPeriod.LAST_30_DAYS
        )

        # Get conversion funnel
        funnel = await service.get_conversion_funnel(
            organization_id="org123",
            period=AnalyticsPeriod.LAST_30_DAYS
        )
    """

    def __init__(self, supabase_client=None):
        self.supabase = supabase_client

    def _get_date_range(
        self,
        period: AnalyticsPeriod,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> tuple:
        """Calculate date range for the given period."""
        now = datetime.utcnow()

        if period == AnalyticsPeriod.CUSTOM and start_date and end_date:
            return start_date, end_date

        ranges = {
            AnalyticsPeriod.TODAY: (
                now.replace(hour=0, minute=0, second=0, microsecond=0),
                now
            ),
            AnalyticsPeriod.YESTERDAY: (
                (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0),
                now.replace(hour=0, minute=0, second=0, microsecond=0)
            ),
            AnalyticsPeriod.LAST_7_DAYS: (now - timedelta(days=7), now),
            AnalyticsPeriod.LAST_30_DAYS: (now - timedelta(days=30), now),
            AnalyticsPeriod.LAST_90_DAYS: (now - timedelta(days=90), now),
            AnalyticsPeriod.THIS_MONTH: (
                now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
                now
            ),
            AnalyticsPeriod.THIS_QUARTER: (
                now.replace(
                    month=((now.month - 1) // 3) * 3 + 1,
                    day=1, hour=0, minute=0, second=0, microsecond=0
                ),
                now
            ),
            AnalyticsPeriod.THIS_YEAR: (
                now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0),
                now
            ),
        }

        return ranges.get(period, (now - timedelta(days=30), now))

    async def get_metrics_summary(
        self,
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None,
        period: AnalyticsPeriod = AnalyticsPeriod.LAST_30_DAYS,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> MetricsSummary:
        """
        Get comprehensive metrics summary.

        Args:
            organization_id: Filter by organization
            user_id: Filter by user
            period: Time period for metrics
            start_date: Custom start date
            end_date: Custom end date

        Returns:
            MetricsSummary with all key metrics
        """
        if not self.supabase:
            logger.warning("No Supabase client - returning empty metrics")
            return MetricsSummary()

        start, end = self._get_date_range(period, start_date, end_date)

        try:
            # Build base query filters
            base_filter = {}
            if organization_id:
                base_filter["organization_id"] = organization_id
            if user_id:
                base_filter["user_id"] = user_id

            # Get conversations
            conv_query = self.supabase.table("ai_conversations").select("*")
            if organization_id:
                conv_query = conv_query.eq("organization_id", organization_id)
            if user_id:
                conv_query = conv_query.eq("user_id", user_id)
            conv_query = conv_query.gte("created_at", start.isoformat())
            conv_query = conv_query.lte("created_at", end.isoformat())
            conv_result = conv_query.execute()
            conversations = conv_result.data or []

            # Get messages
            msg_query = self.supabase.table("ai_message_log").select("*")
            if organization_id:
                # Need to join through conversations
                conv_ids = [c["id"] for c in conversations]
                if conv_ids:
                    msg_query = msg_query.in_("conversation_id", conv_ids)
                else:
                    messages = []
            else:
                msg_query = msg_query.gte("created_at", start.isoformat())
                msg_query = msg_query.lte("created_at", end.isoformat())

            if conversations:  # Only query if we have conversations
                msg_result = msg_query.execute()
                messages = msg_result.data or []
            else:
                messages = []

            # Get appointments
            apt_query = self.supabase.table("ai_appointments").select("*")
            if organization_id:
                apt_query = apt_query.eq("organization_id", organization_id)
            apt_query = apt_query.gte("created_at", start.isoformat())
            apt_query = apt_query.lte("created_at", end.isoformat())
            apt_result = apt_query.execute()
            appointments = apt_result.data or []

            # Get opt-outs
            optout_query = self.supabase.table("sms_consent").select("*")
            optout_query = optout_query.eq("opted_out", True)
            if organization_id:
                optout_query = optout_query.eq("organization_id", organization_id)
            optout_query = optout_query.gte("opted_out_at", start.isoformat())
            optout_query = optout_query.lte("opted_out_at", end.isoformat())
            optout_result = optout_query.execute()
            opt_outs = optout_result.data or []

            # Calculate metrics
            total_convs = len(conversations)
            outbound_msgs = [m for m in messages if m.get("direction") == "outbound"]
            inbound_msgs = [m for m in messages if m.get("direction") == "inbound"]

            # Speed to lead (time from lead creation to first AI message)
            speed_to_lead_times = []
            for conv in conversations:
                first_ai_msg = conv.get("last_ai_message_at")
                created = conv.get("created_at")
                if first_ai_msg and created:
                    try:
                        created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                        msg_dt = datetime.fromisoformat(first_ai_msg.replace('Z', '+00:00'))
                        delta = (msg_dt - created_dt).total_seconds()
                        if delta > 0 and delta < 86400:  # Within 24 hours
                            speed_to_lead_times.append(delta)
                    except Exception:
                        pass

            avg_speed = statistics.mean(speed_to_lead_times) if speed_to_lead_times else 0
            median_speed = statistics.median(speed_to_lead_times) if speed_to_lead_times else 0

            # Response rate
            convs_with_response = sum(
                1 for c in conversations
                if c.get("last_human_message_at")
            )
            response_rate = (convs_with_response / total_convs * 100) if total_convs > 0 else 0

            # Qualification rate
            qualified = sum(
                1 for c in conversations
                if c.get("qualification_data") and len(c.get("qualification_data", {})) >= 2
            )
            qual_rate = (qualified / total_convs * 100) if total_convs > 0 else 0

            # Handoff rate
            handoffs = sum(1 for c in conversations if c.get("state") == "handed_off")
            handoff_rate = (handoffs / total_convs * 100) if total_convs > 0 else 0

            # Appointment rate
            apt_count = len(appointments)
            apt_rate = (apt_count / total_convs * 100) if total_convs > 0 else 0

            # Opt-out rate
            optout_count = len(opt_outs)
            optout_rate = (optout_count / total_convs * 100) if total_convs > 0 else 0

            # Messages per appointment
            msgs_per_apt = (len(outbound_msgs) / apt_count) if apt_count > 0 else 0

            # Average conversation length
            avg_conv_len = (len(messages) / total_convs) if total_convs > 0 else 0

            return MetricsSummary(
                avg_speed_to_lead_seconds=round(avg_speed, 1),
                median_speed_to_lead_seconds=round(median_speed, 1),
                avg_response_time_seconds=0,  # TODO: Calculate from message timestamps
                total_conversations=total_convs,
                total_messages_sent=len(outbound_msgs),
                total_messages_received=len(inbound_msgs),
                response_rate=round(response_rate, 1),
                leads_qualified=qualified,
                qualification_rate=round(qual_rate, 1),
                avg_qualification_questions_asked=0,  # TODO: Calculate from conversation data
                appointments_booked=apt_count,
                appointment_rate=round(apt_rate, 1),
                handoffs_triggered=handoffs,
                handoff_rate=round(handoff_rate, 1),
                opt_outs=optout_count,
                opt_out_rate=round(optout_rate, 1),
                compliance_blocked=0,  # TODO: Track compliance blocks
                messages_per_appointment=round(msgs_per_apt, 1),
                avg_conversation_length=round(avg_conv_len, 1),
                period=period.value,
                start_date=start.isoformat(),
                end_date=end.isoformat(),
            )

        except Exception as e:
            logger.error(f"Error getting metrics summary: {e}", exc_info=True)
            return MetricsSummary()

    async def get_conversion_funnel(
        self,
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None,
        period: AnalyticsPeriod = AnalyticsPeriod.LAST_30_DAYS,
    ) -> ConversionFunnel:
        """
        Get conversion funnel data.

        Args:
            organization_id: Filter by organization
            user_id: Filter by user
            period: Time period

        Returns:
            ConversionFunnel with stage counts and conversion rates
        """
        if not self.supabase:
            return ConversionFunnel()

        start, end = self._get_date_range(period)

        try:
            # Get conversations
            conv_query = self.supabase.table("ai_conversations").select("*")
            if organization_id:
                conv_query = conv_query.eq("organization_id", organization_id)
            if user_id:
                conv_query = conv_query.eq("user_id", user_id)
            conv_query = conv_query.gte("created_at", start.isoformat())
            conv_result = conv_query.execute()
            conversations = conv_result.data or []

            # Get appointments
            apt_query = self.supabase.table("ai_appointments").select("*")
            if organization_id:
                apt_query = apt_query.eq("organization_id", organization_id)
            apt_query = apt_query.gte("created_at", start.isoformat())
            apt_result = apt_query.execute()
            appointments = apt_result.data or []

            total = len(conversations)

            # Contacted = has at least one outbound message
            contacted = sum(1 for c in conversations if c.get("last_ai_message_at"))

            # Responded = has at least one inbound message
            responded = sum(1 for c in conversations if c.get("last_human_message_at"))

            # Qualified = has meaningful qualification data
            qualified = sum(
                1 for c in conversations
                if c.get("qualification_data") and len(c.get("qualification_data", {})) >= 2
            )

            # Appointment requested = in scheduling state or has appointment
            apt_requested = sum(
                1 for c in conversations
                if c.get("state") in ["scheduling", "completed"] or
                   c.get("id") in [a.get("conversation_id") for a in appointments]
            )

            # Booked
            booked = len(appointments)

            # Handed off
            handed_off = sum(1 for c in conversations if c.get("state") == "handed_off")

            return ConversionFunnel(
                total_leads=total,
                contacted=contacted,
                responded=responded,
                qualified=qualified,
                appointment_requested=apt_requested,
                appointment_booked=booked,
                handed_off=handed_off,
                contact_rate=round(contacted / total * 100, 1) if total > 0 else 0,
                response_rate=round(responded / contacted * 100, 1) if contacted > 0 else 0,
                qualification_rate=round(qualified / responded * 100, 1) if responded > 0 else 0,
                appointment_request_rate=round(apt_requested / qualified * 100, 1) if qualified > 0 else 0,
                booking_rate=round(booked / apt_requested * 100, 1) if apt_requested > 0 else 0,
            )

        except Exception as e:
            logger.error(f"Error getting conversion funnel: {e}", exc_info=True)
            return ConversionFunnel()

    async def get_metrics_by_day(
        self,
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None,
        period: AnalyticsPeriod = AnalyticsPeriod.LAST_30_DAYS,
    ) -> List[Dict[str, Any]]:
        """
        Get metrics broken down by day for charts.

        Returns:
            List of daily metrics dicts
        """
        if not self.supabase:
            return []

        start, end = self._get_date_range(period)

        try:
            # Get conversations
            conv_query = self.supabase.table("ai_conversations").select(
                "created_at, state, last_human_message_at"
            )
            if organization_id:
                conv_query = conv_query.eq("organization_id", organization_id)
            if user_id:
                conv_query = conv_query.eq("user_id", user_id)
            conv_query = conv_query.gte("created_at", start.isoformat())
            conv_result = conv_query.execute()
            conversations = conv_result.data or []

            # Get appointments
            apt_query = self.supabase.table("ai_appointments").select("created_at")
            if organization_id:
                apt_query = apt_query.eq("organization_id", organization_id)
            apt_query = apt_query.gte("created_at", start.isoformat())
            apt_result = apt_query.execute()
            appointments = apt_result.data or []

            # Aggregate by day
            by_day = {}

            for conv in conversations:
                if conv.get("created_at"):
                    day = conv["created_at"][:10]
                    if day not in by_day:
                        by_day[day] = {
                            "date": day,
                            "conversations": 0,
                            "responded": 0,
                            "appointments": 0,
                            "handoffs": 0,
                        }
                    by_day[day]["conversations"] += 1
                    if conv.get("last_human_message_at"):
                        by_day[day]["responded"] += 1
                    if conv.get("state") == "handed_off":
                        by_day[day]["handoffs"] += 1

            for apt in appointments:
                if apt.get("created_at"):
                    day = apt["created_at"][:10]
                    if day in by_day:
                        by_day[day]["appointments"] += 1

            return sorted(by_day.values(), key=lambda x: x["date"])

        except Exception as e:
            logger.error(f"Error getting metrics by day: {e}", exc_info=True)
            return []

    async def get_agent_performance(
        self,
        organization_id: str,
        period: AnalyticsPeriod = AnalyticsPeriod.LAST_30_DAYS,
    ) -> List[AgentPerformance]:
        """
        Get performance metrics per agent.

        Args:
            organization_id: Organization to analyze
            period: Time period

        Returns:
            List of AgentPerformance for each agent
        """
        if not self.supabase:
            return []

        start, end = self._get_date_range(period)

        try:
            # Get users in org
            users_result = self.supabase.table("users").select(
                "id, name"
            ).eq("organization_id", organization_id).execute()
            users = users_result.data or []

            # Get conversations per user
            conv_result = self.supabase.table("ai_conversations").select(
                "user_id, state, lead_score, last_human_message_at"
            ).eq("organization_id", organization_id).gte(
                "created_at", start.isoformat()
            ).execute()
            conversations = conv_result.data or []

            # Get appointments per user
            apt_result = self.supabase.table("ai_appointments").select(
                "agent_id"
            ).eq("organization_id", organization_id).gte(
                "created_at", start.isoformat()
            ).execute()
            appointments = apt_result.data or []

            # Get opt-outs per user
            # (Would need to join through conversations)

            # Aggregate by user
            user_stats = {}
            for user in users:
                uid = user["id"]
                user_stats[uid] = {
                    "user_id": uid,
                    "user_name": user.get("name", "Unknown"),
                    "conversations": 0,
                    "responded": 0,
                    "lead_scores": [],
                    "appointments": 0,
                }

            for conv in conversations:
                uid = conv.get("user_id")
                if uid and uid in user_stats:
                    user_stats[uid]["conversations"] += 1
                    if conv.get("last_human_message_at"):
                        user_stats[uid]["responded"] += 1
                    if conv.get("lead_score"):
                        user_stats[uid]["lead_scores"].append(conv["lead_score"])

            for apt in appointments:
                uid = apt.get("agent_id")
                if uid and uid in user_stats:
                    user_stats[uid]["appointments"] += 1

            # Build results
            results = []
            for uid, stats in user_stats.items():
                convs = stats["conversations"]
                results.append(AgentPerformance(
                    user_id=uid,
                    user_name=stats["user_name"],
                    conversations=convs,
                    appointments_booked=stats["appointments"],
                    response_rate=round(
                        stats["responded"] / convs * 100, 1
                    ) if convs > 0 else 0,
                    avg_lead_score=round(
                        statistics.mean(stats["lead_scores"]), 1
                    ) if stats["lead_scores"] else 0,
                    opt_out_rate=0,  # TODO: Calculate
                ))

            # Sort by appointments desc
            results.sort(key=lambda x: x.appointments_booked, reverse=True)

            return results

        except Exception as e:
            logger.error(f"Error getting agent performance: {e}", exc_info=True)
            return []

    async def get_intent_distribution(
        self,
        organization_id: Optional[str] = None,
        period: AnalyticsPeriod = AnalyticsPeriod.LAST_30_DAYS,
    ) -> Dict[str, int]:
        """
        Get distribution of detected intents.

        Returns:
            Dict of intent -> count
        """
        if not self.supabase:
            return {}

        start, end = self._get_date_range(period)

        try:
            msg_query = self.supabase.table("ai_message_log").select(
                "intent_detected"
            ).eq("direction", "inbound").gte("created_at", start.isoformat())

            msg_result = msg_query.execute()
            messages = msg_result.data or []

            distribution = {}
            for msg in messages:
                intent = msg.get("intent_detected", "unknown")
                distribution[intent] = distribution.get(intent, 0) + 1

            return distribution

        except Exception as e:
            logger.error(f"Error getting intent distribution: {e}", exc_info=True)
            return {}

    async def get_ab_test_results(
        self,
        organization_id: Optional[str] = None,
        template_category: Optional[str] = None,
    ) -> List[ABTestResult]:
        """
        Get A/B test results for template variants.

        Returns:
            List of ABTestResult for each category
        """
        if not self.supabase:
            return []

        try:
            # Get test results from ab_test_results table
            query = self.supabase.table("ab_test_results").select("*")
            if organization_id:
                query = query.eq("organization_id", organization_id)
            if template_category:
                query = query.eq("template_category", template_category)

            result = query.execute()
            tests = result.data or []

            # Aggregate by category and variant
            aggregated = {}
            for test in tests:
                category = test.get("template_category", "unknown")
                variant = test.get("variant_name", "unknown")

                if category not in aggregated:
                    aggregated[category] = {}
                if variant not in aggregated[category]:
                    aggregated[category][variant] = {
                        "sends": 0,
                        "responses": 0,
                        "appointments": 0,
                    }

                aggregated[category][variant]["sends"] += 1
                if test.get("got_response"):
                    aggregated[category][variant]["responses"] += 1
                if test.get("led_to_appointment"):
                    aggregated[category][variant]["appointments"] += 1

            # Build results
            results = []
            for category, variants in aggregated.items():
                variant_names = list(variants.keys())
                if len(variant_names) >= 2:
                    a_name = variant_names[0]
                    b_name = variant_names[1]
                    a = variants[a_name]
                    b = variants[b_name]

                    a_rate = (a["responses"] / a["sends"] * 100) if a["sends"] > 0 else 0
                    b_rate = (b["responses"] / b["sends"] * 100) if b["sends"] > 0 else 0

                    # Simple winner determination (would use proper stats in production)
                    winner = "inconclusive"
                    if a["sends"] >= 30 and b["sends"] >= 30:
                        if a_rate > b_rate * 1.1:
                            winner = "a"
                        elif b_rate > a_rate * 1.1:
                            winner = "b"

                    results.append(ABTestResult(
                        template_category=category,
                        variant_a=a_name,
                        variant_b=b_name,
                        variant_a_sends=a["sends"],
                        variant_b_sends=b["sends"],
                        variant_a_responses=a["responses"],
                        variant_b_responses=b["responses"],
                        variant_a_response_rate=round(a_rate, 1),
                        variant_b_response_rate=round(b_rate, 1),
                        variant_a_appointments=a["appointments"],
                        variant_b_appointments=b["appointments"],
                        winner=winner,
                        statistical_significance=0,  # TODO: Calculate properly
                    ))

            return results

        except Exception as e:
            logger.error(f"Error getting A/B test results: {e}", exc_info=True)
            return []


# Singleton instance
_analytics_service_instance: Optional[AIAnalyticsService] = None


def get_analytics_service(supabase_client=None) -> AIAnalyticsService:
    """Get the global analytics service instance."""
    global _analytics_service_instance

    if _analytics_service_instance is None:
        _analytics_service_instance = AIAnalyticsService(supabase_client)
    elif supabase_client and not _analytics_service_instance.supabase:
        _analytics_service_instance.supabase = supabase_client

    return _analytics_service_instance
