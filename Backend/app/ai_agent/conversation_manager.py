"""
Conversation Manager - State machine for AI sales agent conversations.

Manages the flow of conversations through defined states:
- INITIAL: First contact with lead
- QUALIFYING: Gathering budget, timeline, location, motivation
- OBJECTION_HANDLING: Addressing concerns and objections
- SCHEDULING: Booking appointments for qualified leads
- NURTURE: Long-term follow-up for cold leads
- HANDED_OFF: Transferred to human agent
- COMPLETED: Conversation ended (appointment booked or lead disqualified)
"""

import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    """States in the conversation state machine."""
    INITIAL = "initial"
    QUALIFYING = "qualifying"
    OBJECTION_HANDLING = "objection_handling"
    SCHEDULING = "scheduling"
    NURTURE = "nurture"
    HANDED_OFF = "handed_off"
    COMPLETED = "completed"


@dataclass
class QualificationData:
    """Data collected during lead qualification."""
    timeline: Optional[str] = None  # e.g., "30_days", "60_90_days", "6_months_plus"
    budget: Optional[str] = None  # e.g., "$300k-$400k"
    location: Optional[str] = None  # Preferred area/neighborhood
    property_type: Optional[str] = None  # e.g., "single_family", "condo"
    motivation: Optional[str] = None  # e.g., "job_relocation", "growing_family"
    pre_approved: Optional[bool] = None
    transaction_type: Optional[str] = None  # "buyer" or "seller"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timeline": self.timeline,
            "budget": self.budget,
            "location": self.location,
            "property_type": self.property_type,
            "motivation": self.motivation,
            "pre_approved": self.pre_approved,
            "transaction_type": self.transaction_type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualificationData":
        return cls(
            timeline=data.get("timeline"),
            budget=data.get("budget"),
            location=data.get("location"),
            property_type=data.get("property_type"),
            motivation=data.get("motivation"),
            pre_approved=data.get("pre_approved"),
            transaction_type=data.get("transaction_type"),
        )

    def is_qualified(self) -> bool:
        """Check if lead has provided enough info to be considered qualified."""
        # Need at least timeline and one of: budget, location, or pre_approved
        has_timeline = self.timeline is not None
        has_key_info = any([
            self.budget is not None,
            self.location is not None,
            self.pre_approved is not None,
        ])
        return has_timeline and has_key_info

    def missing_fields(self) -> List[str]:
        """Return list of important fields still missing."""
        missing = []
        if self.timeline is None:
            missing.append("timeline")
        if self.budget is None:
            missing.append("budget")
        if self.location is None:
            missing.append("location")
        if self.pre_approved is None:
            missing.append("pre_approved")
        return missing


@dataclass
class ConversationContext:
    """Full context for a conversation with a lead."""
    conversation_id: str
    fub_person_id: int
    user_id: str
    organization_id: str
    state: ConversationState = ConversationState.INITIAL
    lead_score: int = 0
    qualification_data: QualificationData = field(default_factory=QualificationData)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    last_ai_message_at: Optional[datetime] = None
    last_human_message_at: Optional[datetime] = None
    message_count: int = 0
    objections_encountered: List[str] = field(default_factory=list)
    handoff_reason: Optional[str] = None
    assigned_agent_id: Optional[str] = None

    # Lead info from FUB
    lead_name: str = ""
    lead_first_name: str = ""
    lead_phone: Optional[str] = None
    lead_email: Optional[str] = None
    lead_source: Optional[str] = None

    # Settings
    max_ai_messages: int = 15
    agent_name: str = "Sarah"
    brokerage_name: str = "our team"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "fub_person_id": self.fub_person_id,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "state": self.state.value,
            "lead_score": self.lead_score,
            "qualification_data": self.qualification_data.to_dict(),
            "conversation_history": self.conversation_history,
            "last_ai_message_at": self.last_ai_message_at.isoformat() if self.last_ai_message_at else None,
            "last_human_message_at": self.last_human_message_at.isoformat() if self.last_human_message_at else None,
            "message_count": self.message_count,
            "objections_encountered": self.objections_encountered,
            "handoff_reason": self.handoff_reason,
            "assigned_agent_id": self.assigned_agent_id,
            "lead_name": self.lead_name,
            "lead_first_name": self.lead_first_name,
            "lead_phone": self.lead_phone,
            "lead_email": self.lead_email,
            "lead_source": self.lead_source,
        }

    def add_message(self, direction: str, content: str, channel: str = "sms"):
        """Add a message to conversation history."""
        self.conversation_history.append({
            "direction": direction,  # "inbound" or "outbound"
            "content": content,
            "channel": channel,
            "timestamp": datetime.utcnow().isoformat(),
        })

        if direction == "outbound":
            self.last_ai_message_at = datetime.utcnow()
            self.message_count += 1
        else:
            self.last_human_message_at = datetime.utcnow()

    def should_handoff(self) -> tuple[bool, Optional[str]]:
        """Determine if conversation should be handed off to human."""
        # Exceeded max AI messages
        if self.message_count >= self.max_ai_messages:
            return True, "max_messages_reached"

        # Lead score indicates hot lead ready for human
        if self.lead_score >= 80 and self.qualification_data.is_qualified():
            return True, "hot_qualified_lead"

        return False, None


class ConversationManager:
    """
    Manages conversation state transitions and business logic.

    State Transitions:
    - INITIAL -> QUALIFYING: After welcome message sent
    - QUALIFYING -> SCHEDULING: Lead score >= 70 and qualified
    - QUALIFYING -> OBJECTION_HANDLING: Objection detected
    - QUALIFYING -> NURTURE: Lead score < 40 or timeline > 6 months
    - OBJECTION_HANDLING -> QUALIFYING: Objection resolved
    - OBJECTION_HANDLING -> HANDED_OFF: Multiple objections or frustration
    - SCHEDULING -> HANDED_OFF: Appointment booked (for follow-up)
    - SCHEDULING -> COMPLETED: Appointment confirmed
    - NURTURE -> QUALIFYING: Lead re-engages with interest
    - Any -> HANDED_OFF: Human requested or frustration detected
    """

    # Score thresholds
    HOT_LEAD_THRESHOLD = 70
    WARM_LEAD_THRESHOLD = 40
    HANDOFF_THRESHOLD = 80

    # Timeline mappings for scoring
    TIMELINE_SCORES = {
        "immediately": 25,
        "30_days": 25,
        "60_days": 20,
        "60_90_days": 15,
        "3_6_months": 10,
        "6_months_plus": 5,
        "just_browsing": 0,
    }

    def __init__(self, supabase_client=None):
        """Initialize the conversation manager."""
        self.supabase = supabase_client

    async def get_or_create_conversation(
        self,
        fub_person_id: int,
        user_id: str,
        organization_id: str,
        lead_data: Dict[str, Any] = None,
    ) -> ConversationContext:
        """Get existing conversation or create a new one."""

        # Try to find existing active conversation
        if self.supabase:
            result = self.supabase.table("ai_conversations").select("*").eq(
                "fub_person_id", fub_person_id
            ).eq(
                "organization_id", organization_id
            ).eq(
                "is_active", True
            ).execute()

            if result.data:
                return self._context_from_db(result.data[0])

        # Create new conversation
        context = ConversationContext(
            conversation_id="",  # Will be set after DB insert
            fub_person_id=fub_person_id,
            user_id=user_id,
            organization_id=organization_id,
        )

        # Populate lead data if provided
        if lead_data:
            context.lead_name = lead_data.get("name", "")
            context.lead_first_name = lead_data.get("firstName", lead_data.get("name", "").split()[0] if lead_data.get("name") else "")
            context.lead_phone = lead_data.get("phones", [{}])[0].get("value") if lead_data.get("phones") else None
            context.lead_email = lead_data.get("emails", [{}])[0].get("value") if lead_data.get("emails") else None
            context.lead_source = lead_data.get("source")

        # Save to database
        if self.supabase:
            insert_data = {
                "fub_person_id": fub_person_id,
                "user_id": user_id,
                "organization_id": organization_id,
                "state": context.state.value,
                "lead_score": context.lead_score,
                "qualification_data": context.qualification_data.to_dict(),
                "conversation_history": context.conversation_history,
            }
            result = self.supabase.table("ai_conversations").insert(insert_data).execute()
            if result.data:
                context.conversation_id = result.data[0]["id"]

        return context

    def _context_from_db(self, data: Dict[str, Any]) -> ConversationContext:
        """Create ConversationContext from database row."""
        return ConversationContext(
            conversation_id=data["id"],
            fub_person_id=data["fub_person_id"],
            user_id=data["user_id"],
            organization_id=data["organization_id"],
            state=ConversationState(data["state"]),
            lead_score=data["lead_score"],
            qualification_data=QualificationData.from_dict(data.get("qualification_data", {})),
            conversation_history=data.get("conversation_history", []),
            last_ai_message_at=datetime.fromisoformat(data["last_ai_message_at"]) if data.get("last_ai_message_at") else None,
            last_human_message_at=datetime.fromisoformat(data["last_human_message_at"]) if data.get("last_human_message_at") else None,
            handoff_reason=data.get("handoff_reason"),
            assigned_agent_id=data.get("assigned_agent_id"),
        )

    async def save_context(self, context: ConversationContext) -> bool:
        """Save conversation context to database."""
        if not self.supabase or not context.conversation_id:
            return False

        update_data = {
            "state": context.state.value,
            "lead_score": context.lead_score,
            "qualification_data": context.qualification_data.to_dict(),
            "conversation_history": context.conversation_history,
            "last_ai_message_at": context.last_ai_message_at.isoformat() if context.last_ai_message_at else None,
            "last_human_message_at": context.last_human_message_at.isoformat() if context.last_human_message_at else None,
            "handoff_reason": context.handoff_reason,
            "assigned_agent_id": context.assigned_agent_id,
        }

        result = self.supabase.table("ai_conversations").update(update_data).eq(
            "id", context.conversation_id
        ).execute()

        return bool(result.data)

    def determine_next_state(
        self,
        context: ConversationContext,
        intent: Optional[str] = None,
        sentiment: Optional[str] = None,
    ) -> ConversationState:
        """
        Determine the next conversation state based on context and detected intent.

        Args:
            context: Current conversation context
            intent: Detected intent from the message (e.g., "objection", "schedule", "human_request")
            sentiment: Detected sentiment (e.g., "positive", "negative", "frustrated")

        Returns:
            The next conversation state
        """
        current_state = context.state
        lead_score = context.lead_score

        # Always hand off if human requested or frustrated
        if intent == "human_request" or sentiment == "frustrated":
            return ConversationState.HANDED_OFF

        # Check if we should hand off due to max messages or hot lead
        should_handoff, reason = context.should_handoff()
        if should_handoff:
            context.handoff_reason = reason
            return ConversationState.HANDED_OFF

        # State-specific transitions
        if current_state == ConversationState.INITIAL:
            # After initial contact, move to qualifying
            return ConversationState.QUALIFYING

        elif current_state == ConversationState.QUALIFYING:
            # Check for objection
            if intent == "objection":
                return ConversationState.OBJECTION_HANDLING

            # Hot lead that's qualified -> scheduling
            if lead_score >= self.HOT_LEAD_THRESHOLD and context.qualification_data.is_qualified():
                return ConversationState.SCHEDULING

            # Cold lead or very long timeline -> nurture
            if lead_score < self.WARM_LEAD_THRESHOLD:
                return ConversationState.NURTURE

            # Stay in qualifying
            return ConversationState.QUALIFYING

        elif current_state == ConversationState.OBJECTION_HANDLING:
            # If we've handled multiple objections, might need human
            if len(context.objections_encountered) >= 3:
                return ConversationState.HANDED_OFF

            # Objection resolved, back to qualifying
            if intent != "objection":
                return ConversationState.QUALIFYING

            return ConversationState.OBJECTION_HANDLING

        elif current_state == ConversationState.SCHEDULING:
            # If appointment confirmed
            if intent == "appointment_confirmed":
                context.handoff_reason = "appointment_booked"
                return ConversationState.HANDED_OFF  # Hand off after booking

            # If they're backing out
            if intent == "objection":
                return ConversationState.OBJECTION_HANDLING

            return ConversationState.SCHEDULING

        elif current_state == ConversationState.NURTURE:
            # If lead shows renewed interest
            if intent in ["interested", "schedule", "question"] and lead_score >= self.WARM_LEAD_THRESHOLD:
                return ConversationState.QUALIFYING

            return ConversationState.NURTURE

        # Default: stay in current state
        return current_state

    def get_conversation_prompt_context(self, context: ConversationContext) -> str:
        """Generate context string for AI prompt based on conversation state."""
        state = context.state
        qual = context.qualification_data

        base_context = f"""
Lead: {context.lead_first_name or 'there'}
Score: {context.lead_score}/100 ({'Hot' if context.lead_score >= 70 else 'Warm' if context.lead_score >= 40 else 'Cold'})
State: {state.value}
Messages sent: {context.message_count}
"""

        if qual.timeline:
            base_context += f"Timeline: {qual.timeline}\n"
        if qual.budget:
            base_context += f"Budget: {qual.budget}\n"
        if qual.location:
            base_context += f"Location: {qual.location}\n"
        if qual.pre_approved is not None:
            base_context += f"Pre-approved: {'Yes' if qual.pre_approved else 'No'}\n"

        # Add state-specific guidance
        if state == ConversationState.INITIAL:
            base_context += "\nGoal: Welcome warmly and ask what brought them here."
        elif state == ConversationState.QUALIFYING:
            missing = qual.missing_fields()
            if missing:
                base_context += f"\nGoal: Learn about their {missing[0]}. Ask naturally, one question at a time."
            else:
                base_context += "\nGoal: Confirm details and move toward scheduling."
        elif state == ConversationState.OBJECTION_HANDLING:
            base_context += "\nGoal: Acknowledge their concern, provide value, don't be pushy."
        elif state == ConversationState.SCHEDULING:
            base_context += "\nGoal: Offer specific times and confirm the appointment."
        elif state == ConversationState.NURTURE:
            base_context += "\nGoal: Stay helpful and check in periodically. Don't push."

        return base_context

    def record_objection(self, context: ConversationContext, objection_type: str):
        """Record an objection encountered in the conversation."""
        if objection_type not in context.objections_encountered:
            context.objections_encountered.append(objection_type)
        logger.info(f"Objection recorded: {objection_type} for conversation {context.conversation_id}")
