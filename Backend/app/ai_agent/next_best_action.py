"""
Smart Follow-Up Engine (aka "Next Best Action" / NBA in sales terminology)

This engine proactively scans ALL leads in your database and determines
the BEST action to take for each one RIGHT NOW. Think of it as your
AI sales manager that never sleeps.

WHAT IT DOES:
- Finds new leads that need immediate outreach (speed to lead = $$$)
- Identifies leads who went quiet and need follow-up
- Revives dormant/cold leads with value-based outreach
- Processes scheduled follow-up sequences
- Respects TCPA compliance (8 AM - 8 PM only)

HOW IT WORKS:
1. Scans all leads, calculates priority score for each
2. Sorts by priority (hot new leads first, then silent leads, etc.)
3. Recommends specific action (SMS, email, or wait)
4. Executes actions or returns recommendations for review

RUNS: Every 15 minutes via scheduled task (or manually via API)

WHY "NEXT BEST ACTION"?
- It's a sales/CRM industry term meaning "what should I do next for this lead?"
- The engine answers that question for EVERY lead, automatically
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum

from app.database.supabase_client import SupabaseClientSingleton
from app.database.fub_api_client import FUBApiClient
from app.ai_agent.lead_prioritizer import LeadPrioritizer, get_lead_prioritizer
from app.ai_agent.followup_manager import (
    FollowUpManager,
    FollowUpTrigger,
    get_followup_manager,
    is_within_tcpa_hours,
)

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of actions the engine can recommend."""
    FIRST_CONTACT_SMS = "first_contact_sms"      # New lead - send initial SMS
    FIRST_CONTACT_EMAIL = "first_contact_email"  # New lead - send initial email
    FOLLOWUP_SMS = "followup_sms"                # Follow-up SMS
    FOLLOWUP_EMAIL = "followup_email"            # Follow-up email
    REENGAGEMENT_SMS = "reengagement_sms"        # Re-engage dormant lead
    REENGAGEMENT_EMAIL = "reengagement_email"    # Re-engage via email
    CREATE_TASK = "create_task"                  # Escalate to human
    STALE_HANDOFF = "stale_handoff"              # Handed off but no human follow-up
    NO_ACTION = "no_action"                      # No action needed now
    WAIT = "wait"                                # Wait - within followup window


@dataclass
class RecommendedAction:
    """A recommended action for a lead."""
    fub_person_id: int
    action_type: ActionType
    priority_score: int
    reason: str
    execute_at: Optional[datetime] = None
    message_context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fub_person_id": self.fub_person_id,
            "action_type": self.action_type.value,
            "priority_score": self.priority_score,
            "reason": self.reason,
            "execute_at": self.execute_at.isoformat() if self.execute_at else None,
            "message_context": self.message_context,
        }


class NextBestActionEngine:
    """
    Proactive lead engagement engine.

    Scans all leads periodically and determines the optimal action
    to maximize conversion while respecting compliance.
    """

    # Time thresholds for action determination
    NEW_LEAD_THRESHOLD_HOURS = 1       # Lead created within 1 hour = new lead
    SILENT_THRESHOLD_HOURS = 24        # No response in 24h = needs follow-up
    DORMANT_THRESHOLD_DAYS = 30        # No contact in 30 days = dormant
    REVIVAL_THRESHOLD_DAYS = 90        # No contact in 90 days = revival candidate
    STALE_HANDOFF_THRESHOLD_HOURS = 48 # Handed off 48h+ ago with no human follow-up

    # Batch processing settings
    DEFAULT_BATCH_SIZE = 50
    MAX_ACTIONS_PER_RUN = 100

    def __init__(
        self,
        supabase_client=None,
        fub_client: FUBApiClient = None,
    ):
        """
        Initialize the Next Best Action Engine.

        Args:
            supabase_client: Database client
            fub_client: FUB API client
        """
        self.supabase = supabase_client or SupabaseClientSingleton.get_instance()
        self.fub_client = fub_client or FUBApiClient()
        self.prioritizer = get_lead_prioritizer()
        self.followup_manager = get_followup_manager(supabase_client=self.supabase)

    async def scan_and_recommend(
        self,
        organization_id: str = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> List[RecommendedAction]:
        """
        Scan leads and recommend actions for each.

        This is the main entry point for the scheduled task.

        Args:
            organization_id: Filter by organization (optional for now)
            batch_size: Number of leads to process

        Returns:
            List of recommended actions, sorted by priority
        """
        logger.info(f"Starting Next Best Action scan (batch_size={batch_size})")

        recommendations = []

        # 1. Check for new leads needing first contact
        new_lead_actions = await self._check_new_leads(organization_id, batch_size // 3)
        recommendations.extend(new_lead_actions)

        # 2. Check for leads that went silent (need follow-up)
        silent_lead_actions = await self._check_silent_leads(organization_id, batch_size // 3)
        recommendations.extend(silent_lead_actions)

        # 3. Check for dormant leads (re-engagement candidates)
        dormant_lead_actions = await self._check_dormant_leads(organization_id, batch_size // 3)
        recommendations.extend(dormant_lead_actions)

        # 4. Check pending follow-ups due for execution
        followup_actions = await self._check_pending_followups(organization_id)
        recommendations.extend(followup_actions)

        # 5. Check for stale handoffs (human agent didn't follow up)
        stale_handoff_actions = await self._check_stale_handoffs(organization_id)
        recommendations.extend(stale_handoff_actions)

        # Sort by priority score (highest first)
        recommendations.sort(key=lambda x: x.priority_score, reverse=True)

        # Limit to max actions per run
        if len(recommendations) > self.MAX_ACTIONS_PER_RUN:
            recommendations = recommendations[:self.MAX_ACTIONS_PER_RUN]

        logger.info(f"NBA scan complete: {len(recommendations)} actions recommended")

        return recommendations

    async def _check_new_leads(
        self,
        organization_id: str,
        limit: int,
    ) -> List[RecommendedAction]:
        """
        Find new leads that haven't received first contact.

        New lead criteria:
        - Created within last 24 hours
        - No AI conversation started
        - No outbound messages sent
        """
        actions = []

        try:
            # Query leads created recently with no AI contact
            threshold = datetime.utcnow() - timedelta(hours=24)

            query = self.supabase.table("leads").select(
                "fub_person_id, first_name, last_name, source, created_at, phone, email"
            ).gte(
                "created_at", threshold.isoformat()
            ).is_(
                "first_ai_contact_at", "null"
            ).limit(limit)

            if organization_id:
                query = query.eq("organization_id", organization_id)

            result = query.execute()

            for lead in result.data or []:
                fub_person_id = lead.get("fub_person_id")

                # Check if within TCPA hours
                is_allowed, next_allowed = is_within_tcpa_hours()

                # Determine action based on contact info
                has_phone = bool(lead.get("phone"))
                has_email = bool(lead.get("email"))

                if has_phone:
                    action_type = ActionType.FIRST_CONTACT_SMS
                elif has_email:
                    action_type = ActionType.FIRST_CONTACT_EMAIL
                else:
                    continue  # Skip leads with no contact info

                # Calculate priority (new leads are high priority)
                hours_since_created = (datetime.utcnow() - datetime.fromisoformat(
                    lead["created_at"].replace("Z", "+00:00")
                ).replace(tzinfo=None)).total_seconds() / 3600

                # Higher priority for more recent leads
                priority = max(90 - int(hours_since_created * 2), 50)

                actions.append(RecommendedAction(
                    fub_person_id=fub_person_id,
                    action_type=action_type,
                    priority_score=priority,
                    reason=f"New lead from {lead.get('source', 'Unknown')} - needs first contact",
                    execute_at=datetime.utcnow() if is_allowed else next_allowed,
                    message_context={
                        "first_name": lead.get("first_name"),
                        "source": lead.get("source"),
                        "trigger": FollowUpTrigger.NEW_LEAD.value,
                    }
                ))

        except Exception as e:
            logger.error(f"Error checking new leads: {e}")

        return actions

    async def _check_silent_leads(
        self,
        organization_id: str,
        limit: int,
    ) -> List[RecommendedAction]:
        """
        Find leads that received messages but haven't responded.

        Silent lead criteria:
        - AI sent message 24+ hours ago
        - No response received
        - Not in blocked stage
        - No pending follow-up scheduled

        SMART RE-ENGAGEMENT:
        Instead of generic follow-ups, we check the conversation state
        and choose the appropriate RESUME_* trigger so the AI can
        pick up where it left off with full context.
        """
        actions = []

        try:
            # Query conversations where we sent a message and haven't heard back
            # Include qualification_data for smart re-engagement context
            threshold = datetime.utcnow() - timedelta(hours=self.SILENT_THRESHOLD_HOURS)

            query = self.supabase.table("ai_conversations").select(
                "fub_person_id, state, last_ai_message_at, last_lead_response_at, lead_score, "
                "qualification_data, last_topic, unanswered_questions, objections_raised"
            ).lt(
                "last_ai_message_at", threshold.isoformat()
            ).neq(
                "state", "handed_off"
            ).neq(
                "state", "completed"
            ).eq(
                "is_active", True
            ).limit(limit)

            if organization_id:
                query = query.eq("organization_id", organization_id)

            result = query.execute()

            for conv in result.data or []:
                fub_person_id = conv.get("fub_person_id")

                # Check if they ever responded
                last_response = conv.get("last_lead_response_at")
                last_ai_msg = conv.get("last_ai_message_at")

                if last_response and last_ai_msg:
                    # They responded before but went silent
                    last_response_dt = datetime.fromisoformat(
                        last_response.replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                    last_ai_dt = datetime.fromisoformat(
                        last_ai_msg.replace("Z", "+00:00")
                    ).replace(tzinfo=None)

                    if last_response_dt > last_ai_dt:
                        continue  # They responded after our last message - not silent

                # Check if there's already a pending follow-up
                has_pending = await self._has_pending_followup(fub_person_id)
                if has_pending:
                    continue

                # Determine priority based on lead score and time silent
                lead_score = conv.get("lead_score", 50)
                priority = lead_score  # Use lead score as base priority

                # Check TCPA hours
                is_allowed, next_allowed = is_within_tcpa_hours()

                # ============================================================
                # SMART RE-ENGAGEMENT: Choose trigger based on conversation state
                # ============================================================
                conv_state = conv.get("state", "initial")
                qualification_data = conv.get("qualification_data") or {}
                objections = conv.get("objections_raised") or []

                # Determine the appropriate trigger based on state
                if conv_state in ["qualifying", "initial"]:
                    trigger = FollowUpTrigger.RESUME_QUALIFICATION
                    reason = "Lead went silent during qualification - picking up where we left off"
                elif conv_state == "scheduling":
                    trigger = FollowUpTrigger.RESUME_SCHEDULING
                    reason = "Lead went silent while scheduling - re-offering appointment times"
                elif objections:
                    trigger = FollowUpTrigger.RESUME_OBJECTION
                    reason = f"Lead had objection: {objections[-1] if objections else 'unknown'} - addressing concern"
                else:
                    trigger = FollowUpTrigger.NO_RESPONSE
                    reason = "Lead went silent - needs follow-up"

                # Build conversation summary for context-aware follow-up
                answered_questions = []
                if qualification_data:
                    if qualification_data.get("timeline"):
                        answered_questions.append(f"Timeline: {qualification_data['timeline']}")
                    if qualification_data.get("budget"):
                        answered_questions.append(f"Budget: {qualification_data['budget']}")
                    if qualification_data.get("location"):
                        answered_questions.append(f"Location: {qualification_data['location']}")
                    if qualification_data.get("pre_approved") is not None:
                        answered_questions.append(f"Pre-approved: {'Yes' if qualification_data['pre_approved'] else 'No'}")

                conversation_summary = {
                    "last_topic": conv.get("last_topic", "General introduction"),
                    "answered_questions": ", ".join(answered_questions) if answered_questions else "None yet",
                    "open_questions": conv.get("unanswered_questions", "Timeline, budget, location"),
                    "objections": ", ".join(objections) if objections else "None",
                    "score": lead_score,
                    "state": conv_state,
                }

                logger.info(f"Smart re-engagement for {fub_person_id}: trigger={trigger.value}, state={conv_state}")

                actions.append(RecommendedAction(
                    fub_person_id=fub_person_id,
                    action_type=ActionType.FOLLOWUP_SMS,
                    priority_score=priority,
                    reason=reason,
                    execute_at=datetime.utcnow() if is_allowed else next_allowed,
                    message_context={
                        "trigger": trigger.value,
                        "state": conv_state,
                        "conversation_summary": conversation_summary,
                    }
                ))

        except Exception as e:
            logger.error(f"Error checking silent leads: {e}")

        return actions

    async def _check_dormant_leads(
        self,
        organization_id: str,
        limit: int,
    ) -> List[RecommendedAction]:
        """
        Find dormant leads for re-engagement.

        Uses the LeadPrioritizer to score and prioritize dormant leads.
        """
        actions = []

        try:
            # Use the prioritizer to get scored dormant leads
            # For now, we'll use a simpler query since prioritizer needs full setup
            threshold = datetime.utcnow() - timedelta(days=self.DORMANT_THRESHOLD_DAYS)

            query = self.supabase.table("leads").select(
                "fub_person_id, first_name, last_name, source, last_activity_at, phone, email"
            ).lt(
                "last_activity_at", threshold.isoformat()
            ).neq(
                "stage", "Closed"
            ).neq(
                "stage", "Lost"
            ).neq(
                "stage", "Trash"
            ).limit(limit)

            if organization_id:
                query = query.eq("organization_id", organization_id)

            result = query.execute()

            for lead in result.data or []:
                fub_person_id = lead.get("fub_person_id")

                # Check if there's already a pending follow-up
                has_pending = await self._has_pending_followup(fub_person_id)
                if has_pending:
                    continue

                # Calculate days since last contact
                last_activity = lead.get("last_activity_at")
                if last_activity:
                    last_dt = datetime.fromisoformat(
                        last_activity.replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                    days_dormant = (datetime.utcnow() - last_dt).days
                else:
                    days_dormant = 90  # Assume long dormant if no date

                # Prioritize recently dormant over very old leads
                priority = max(60 - (days_dormant - 30), 20)

                # Revival leads (90+ days) get different treatment
                if days_dormant >= self.REVIVAL_THRESHOLD_DAYS:
                    action_type = ActionType.REENGAGEMENT_EMAIL
                    reason = f"Revival candidate - {days_dormant} days dormant"
                else:
                    action_type = ActionType.REENGAGEMENT_SMS
                    reason = f"Re-engagement needed - {days_dormant} days dormant"

                # Check TCPA hours
                is_allowed, next_allowed = is_within_tcpa_hours()

                actions.append(RecommendedAction(
                    fub_person_id=fub_person_id,
                    action_type=action_type,
                    priority_score=priority,
                    reason=reason,
                    execute_at=datetime.utcnow() if is_allowed else next_allowed,
                    message_context={
                        "first_name": lead.get("first_name"),
                        "source": lead.get("source"),
                        "trigger": FollowUpTrigger.RE_ENGAGEMENT.value,
                        "days_dormant": days_dormant,
                    }
                ))

        except Exception as e:
            logger.error(f"Error checking dormant leads: {e}")

        return actions

    async def _check_pending_followups(
        self,
        organization_id: str,
    ) -> List[RecommendedAction]:
        """
        Check for follow-ups that are due now.
        """
        actions = []

        try:
            # Get follow-ups due now
            due_before = datetime.utcnow()
            pending = await self.followup_manager.get_pending_followups(
                organization_id=organization_id,
                due_before=due_before,
            )

            for followup in pending:
                # Determine action type based on channel
                if followup.channel == "sms":
                    action_type = ActionType.FOLLOWUP_SMS
                else:
                    action_type = ActionType.FOLLOWUP_EMAIL

                actions.append(RecommendedAction(
                    fub_person_id=followup.fub_person_id,
                    action_type=action_type,
                    priority_score=70,  # Scheduled follow-ups are medium-high priority
                    reason=f"Scheduled follow-up ({followup.message_type})",
                    execute_at=followup.scheduled_at,
                    message_context={
                        "followup_id": followup.id,
                        "message_type": followup.message_type,
                        "sequence_id": followup.sequence_id,
                        "sequence_step": followup.sequence_step,
                    }
                ))

        except Exception as e:
            logger.error(f"Error checking pending follow-ups: {e}")

        return actions

    async def _has_pending_followup(self, fub_person_id: int) -> bool:
        """Check if lead has pending follow-ups."""
        try:
            result = self.supabase.table("ai_scheduled_followups").select(
                "id"
            ).eq(
                "fub_person_id", fub_person_id
            ).eq(
                "status", "pending"
            ).limit(1).execute()

            return bool(result.data)
        except Exception:
            return False

    async def _check_stale_handoffs(
        self,
        organization_id: str = None,
    ) -> List[RecommendedAction]:
        """
        Check for leads that were handed off to a human agent but never followed up.

        Detects the "dropped ball" scenario where:
        1. AI handed off to human agent
        2. 48+ hours have passed
        3. No human message was sent after handoff
        """
        actions = []

        try:
            threshold = datetime.utcnow() - timedelta(
                hours=self.STALE_HANDOFF_THRESHOLD_HOURS
            )

            query = self.supabase.table("ai_conversations").select(
                "fub_person_id, state, last_ai_message_at, last_human_message_at, "
                "handoff_reason, assigned_agent_id, updated_at"
            ).eq(
                "state", "handed_off"
            ).eq(
                "is_active", True
            ).lt(
                "updated_at", threshold.isoformat()
            ).limit(20)

            if organization_id:
                query = query.eq("organization_id", organization_id)

            result = query.execute()

            for conv in (result.data or []):
                person_id = conv.get("fub_person_id")
                last_human = conv.get("last_human_message_at")
                updated_at = conv.get("updated_at")

                # If a human message was sent AFTER the handoff, it's not stale
                if last_human and updated_at:
                    try:
                        human_dt = datetime.fromisoformat(last_human.replace("Z", "+00:00"))
                        updated_dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                        if human_dt > updated_dt:
                            continue  # Human followed up — not stale
                    except (ValueError, AttributeError):
                        pass

                # Calculate how long it's been stale
                hours_stale = 48  # default
                if updated_at:
                    try:
                        updated_dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                        hours_stale = (datetime.utcnow().replace(tzinfo=updated_dt.tzinfo) - updated_dt).total_seconds() / 3600
                    except (ValueError, AttributeError):
                        pass

                # Higher priority the longer it's been stale
                priority = 85 if hours_stale >= 72 else 75

                actions.append(RecommendedAction(
                    fub_person_id=person_id,
                    action_type=ActionType.STALE_HANDOFF,
                    priority_score=priority,
                    reason=f"Handed off {int(hours_stale)}h ago — no human follow-up. Reason: {conv.get('handoff_reason', 'unknown')}",
                    message_context={
                        "hours_stale": int(hours_stale),
                        "handoff_reason": conv.get("handoff_reason"),
                        "assigned_agent_id": conv.get("assigned_agent_id"),
                    }
                ))

            if actions:
                logger.warning(f"Found {len(actions)} stale handoffs needing attention")

        except Exception as e:
            logger.error(f"Error checking stale handoffs: {e}")

        return actions

    async def execute_action(
        self,
        action: RecommendedAction,
        agent_service=None,
    ) -> Dict[str, Any]:
        """
        Execute a recommended action.

        Args:
            action: The action to execute
            agent_service: AIAgentService for generating responses

        Returns:
            Result of the action execution
        """
        logger.info(
            f"Executing action {action.action_type.value} for lead {action.fub_person_id}"
        )

        # Check TCPA compliance before executing
        is_allowed, next_allowed = is_within_tcpa_hours()
        if not is_allowed and action.action_type in (
            ActionType.FIRST_CONTACT_SMS,
            ActionType.FOLLOWUP_SMS,
            ActionType.REENGAGEMENT_SMS,
        ):
            logger.info(f"TCPA: Deferring SMS action until {next_allowed}")
            return {
                "success": False,
                "reason": "outside_tcpa_hours",
                "deferred_until": next_allowed.isoformat() if next_allowed else None,
            }

        try:
            if action.action_type == ActionType.FIRST_CONTACT_SMS:
                return await self._execute_first_contact(action, "sms", agent_service)

            elif action.action_type == ActionType.FIRST_CONTACT_EMAIL:
                return await self._execute_first_contact(action, "email", agent_service)

            elif action.action_type in (ActionType.FOLLOWUP_SMS, ActionType.FOLLOWUP_EMAIL):
                return await self._execute_followup(action, agent_service)

            elif action.action_type in (ActionType.REENGAGEMENT_SMS, ActionType.REENGAGEMENT_EMAIL):
                return await self._execute_reengagement(action, agent_service)

            elif action.action_type == ActionType.CREATE_TASK:
                return await self._execute_create_task(action)

            else:
                return {"success": True, "action": "no_action_needed"}

        except Exception as e:
            logger.error(f"Error executing action: {e}")
            return {"success": False, "error": str(e)}

    async def _execute_first_contact(
        self,
        action: RecommendedAction,
        channel: str,
        agent_service=None,
    ) -> Dict[str, Any]:
        """Execute first contact action."""
        fub_person_id = action.fub_person_id

        # Schedule the follow-up sequence
        sequence_result = await self.followup_manager.schedule_followup_sequence(
            fub_person_id=fub_person_id,
            organization_id="default",  # TODO: Get from context
            trigger=FollowUpTrigger.NEW_LEAD,
            start_delay_hours=0,  # Start immediately
            preferred_channel=channel,
        )

        # Mark first contact time
        try:
            self.supabase.table("leads").update({
                "first_ai_contact_at": datetime.utcnow().isoformat(),
            }).eq("fub_person_id", fub_person_id).execute()
        except Exception as e:
            logger.warning(f"Could not update first_ai_contact_at: {e}")

        return {
            "success": True,
            "action": "first_contact",
            "channel": channel,
            "sequence_id": sequence_result.get("sequence_id"),
            "fub_person_id": fub_person_id,
        }

    async def _execute_followup(
        self,
        action: RecommendedAction,
        agent_service=None,
    ) -> Dict[str, Any]:
        """Execute a follow-up action."""
        context = action.message_context or {}

        # Fetch agent settings so messages use real names, not "Your Agent"
        agent_name = "Your Agent"
        agent_phone = ""
        brokerage_name = ""
        try:
            settings = self.supabase.table("ai_agent_settings").select(
                "agent_name, brokerage_name"
            ).limit(1).execute()
            if settings.data:
                s = settings.data[0]
                agent_name = s.get("agent_name") or "Your Agent"
                brokerage_name = s.get("brokerage_name") or ""
        except Exception as e:
            logger.warning(f"Could not fetch agent settings: {e}")

        # If this is a scheduled follow-up, process it
        if context.get("followup_id"):
            return await self.followup_manager.process_scheduled_followup(
                followup_id=context["followup_id"],
                agent_service=agent_service,
                agent_name=agent_name,
                agent_phone=agent_phone,
                brokerage_name=brokerage_name,
            )

        # Otherwise, schedule a new sequence
        return await self.followup_manager.schedule_followup_sequence(
            fub_person_id=action.fub_person_id,
            organization_id="default",
            trigger=FollowUpTrigger(context.get("trigger", "no_response")),
            start_delay_hours=0,
        )

    async def _execute_reengagement(
        self,
        action: RecommendedAction,
        agent_service=None,
    ) -> Dict[str, Any]:
        """Execute re-engagement action."""
        channel = "email" if action.action_type == ActionType.REENGAGEMENT_EMAIL else "sms"

        return await self.followup_manager.schedule_followup_sequence(
            fub_person_id=action.fub_person_id,
            organization_id="default",
            trigger=FollowUpTrigger.RE_ENGAGEMENT,
            start_delay_hours=0,
            preferred_channel=channel,
        )

    async def _execute_create_task(
        self,
        action: RecommendedAction,
    ) -> Dict[str, Any]:
        """Create a task for human follow-up."""
        try:
            self.fub_client.create_task(
                person_id=action.fub_person_id,
                title=f"AI Recommended: {action.reason}",
                due_date=(datetime.utcnow() + timedelta(hours=24)).isoformat(),
            )
            return {"success": True, "action": "task_created"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Singleton for easy access
_nba_engine: Optional[NextBestActionEngine] = None


def get_nba_engine() -> NextBestActionEngine:
    """Get the Next Best Action Engine singleton."""
    global _nba_engine
    if _nba_engine is None:
        _nba_engine = NextBestActionEngine()
    return _nba_engine


async def run_nba_scan(
    organization_id: str = None,
    execute: bool = True,
    batch_size: int = 50,
) -> Dict[str, Any]:
    """
    Run a Next Best Action scan and optionally execute actions.

    This is the main entry point for scheduled tasks.

    Args:
        organization_id: Filter by organization
        execute: Whether to execute recommended actions
        batch_size: Number of leads to process

    Returns:
        Summary of scan results and executed actions
    """
    engine = get_nba_engine()

    # Get recommendations
    recommendations = await engine.scan_and_recommend(
        organization_id=organization_id,
        batch_size=batch_size,
    )

    executed = []
    skipped = []

    if execute:
        login_broken = False
        for action in recommendations:
            # Skip remaining follow-ups if browser login is broken
            if login_broken and action.action_type.value in ("followup_sms", "followup_email"):
                skipped.append({
                    "fub_person_id": action.fub_person_id,
                    "action": action.action_type.value,
                    "reason": "Skipped - browser login unavailable",
                })
                continue

            result = await engine.execute_action(action)
            if result.get("success"):
                executed.append({
                    "fub_person_id": action.fub_person_id,
                    "action": action.action_type.value,
                    "result": result,
                })
            else:
                error = result.get("error") or result.get("delivery_error") or result.get("reason") or ""
                # Detect login failures and stop trying follow-ups
                if any(kw in error.lower() for kw in ["cooldown", "login failed", "suspicious login"]):
                    login_broken = True
                    logger.warning(f"Browser login broken - skipping remaining follow-ups")
                skipped.append({
                    "fub_person_id": action.fub_person_id,
                    "action": action.action_type.value,
                    "reason": error,
                })

    return {
        "scan_time": datetime.utcnow().isoformat(),
        "recommendations_count": len(recommendations),
        "executed_count": len(executed),
        "skipped_count": len(skipped),
        "recommendations": [r.to_dict() for r in recommendations[:20]],  # First 20
        "executed": executed[:20],
        "skipped": skipped[:10],
    }
