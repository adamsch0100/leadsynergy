"""
Lead Update Strategy Engine

Ensures lead source updates are always positive and action-oriented to maintain
strong relationships with referral partners (ReferralExchange, HomeLight, etc.).

Key Philosophy:
- Default to POSITIVE, forward-looking updates
- Show proactive engagement even with dormant leads
- Only use negative updates when there's legitimate proof lead is dead
- Protect the relationship with lead sources at all costs
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class LeadDisposition(Enum):
    """Classification of lead status for update strategy"""
    ACTIVE_ENGAGED = "active_engaged"           # Recent activity, moving forward
    DORMANT_RECOVERABLE = "dormant_recoverable" # No recent activity but still viable
    GHOSTING = "ghosting"                       # Not responding but not explicitly dead
    DEAD_CONFIRMED = "dead_confirmed"           # Explicit reason lead is dead
    DEAD_UNRESPONSIVE = "dead_unresponsive"    # Many attempts, zero response


class UpdateTone(Enum):
    """Tone for the update message"""
    OPTIMISTIC = "optimistic"       # Lead is moving forward
    PERSISTENT = "persistent"       # Still trying, staying positive
    STRATEGIC = "strategic"         # Adjusting approach, still engaged
    CLOSING = "closing"             # Negative but professional


@dataclass
class LeadContext:
    """Context about the lead for update generation"""
    lead_id: str
    lead_name: str
    source_name: str

    # Activity data
    days_since_last_contact: int
    days_since_created: int
    total_attempts: int
    total_responses: int

    # Status indicators
    fub_stage: str
    has_recent_notes: bool
    has_recent_messages: bool

    # Dead indicators (if any)
    explicit_dead_reason: Optional[str] = None  # "Not interested", "Working with another agent", etc.
    opted_out: bool = False
    complaint_filed: bool = False


@dataclass
class UpdateStrategy:
    """Strategy for generating the update"""
    disposition: LeadDisposition
    tone: UpdateTone
    template_category: str
    key_message: str
    show_action_plan: bool
    reasoning: str


class LeadUpdateStrategyEngine:
    """
    Determines the right update strategy based on lead context

    Rules:
    1. If lead has recent activity (7 days) → ACTIVE_ENGAGED → Optimistic
    2. If lead is dormant but < 30 days → DORMANT_RECOVERABLE → Persistent
    3. If lead is dormant 30-60 days → GHOSTING → Strategic
    4. If lead has explicit dead reason → DEAD_CONFIRMED → Closing
    5. If lead has 10+ attempts with 0 responses → DEAD_UNRESPONSIVE → Closing
    6. Default (no clear signal) → DORMANT_RECOVERABLE → Persistent
    """

    # Thresholds
    ACTIVE_THRESHOLD_DAYS = 7
    DORMANT_THRESHOLD_DAYS = 30
    GHOSTING_THRESHOLD_DAYS = 60
    DEAD_ATTEMPTS_THRESHOLD = 10

    # Dead reasons that are legitimate
    DEAD_KEYWORDS = [
        "not interested",
        "working with another",
        "already bought",
        "already sold",
        "changed mind",
        "no longer looking",
        "found another agent",
        "going with someone else",
        "withdrew",
        "cancelled",
    ]

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def determine_strategy(self, context: LeadContext) -> UpdateStrategy:
        """
        Analyze lead context and determine update strategy

        Args:
            context: LeadContext with all relevant lead information

        Returns:
            UpdateStrategy with recommended approach
        """

        # Check for explicit dead indicators first
        if self._is_explicitly_dead(context):
            return self._create_dead_confirmed_strategy(context)

        # Check for unresponsive dead (many attempts, zero engagement)
        if self._is_unresponsive_dead(context):
            return self._create_dead_unresponsive_strategy(context)

        # Check for active engagement
        if self._is_actively_engaged(context):
            return self._create_active_engaged_strategy(context)

        # Check for ghosting (long dormant)
        if self._is_ghosting(context):
            return self._create_ghosting_strategy(context)

        # Default: Dormant but recoverable (stay positive!)
        return self._create_dormant_recoverable_strategy(context)

    def _is_explicitly_dead(self, context: LeadContext) -> bool:
        """Check if lead has explicit dead reason"""
        if context.opted_out or context.complaint_filed:
            return True

        if context.explicit_dead_reason:
            reason_lower = context.explicit_dead_reason.lower()
            return any(keyword in reason_lower for keyword in self.DEAD_KEYWORDS)

        # Check FUB stage
        stage_lower = context.fub_stage.lower()
        if "dead" in stage_lower or "lost" in stage_lower or "unqualified" in stage_lower:
            return True

        return False

    def _is_unresponsive_dead(self, context: LeadContext) -> bool:
        """Check if lead is dead due to complete unresponsiveness"""
        # Need many attempts with ZERO responses over long period
        return (
            context.total_attempts >= self.DEAD_ATTEMPTS_THRESHOLD
            and context.total_responses == 0
            and context.days_since_last_contact > self.GHOSTING_THRESHOLD_DAYS
        )

    def _is_actively_engaged(self, context: LeadContext) -> bool:
        """Check if lead is actively engaged"""
        return (
            context.days_since_last_contact <= self.ACTIVE_THRESHOLD_DAYS
            or context.has_recent_messages
            or (context.has_recent_notes and context.days_since_last_contact <= 14)
        )

    def _is_ghosting(self, context: LeadContext) -> bool:
        """Check if lead is ghosting (long dormant)"""
        return context.days_since_last_contact > self.DORMANT_THRESHOLD_DAYS

    def _create_active_engaged_strategy(self, context: LeadContext) -> UpdateStrategy:
        """Strategy for actively engaged leads - show momentum!"""
        return UpdateStrategy(
            disposition=LeadDisposition.ACTIVE_ENGAGED,
            tone=UpdateTone.OPTIMISTIC,
            template_category="active_progress",
            key_message="Lead is actively engaged and moving forward",
            show_action_plan=True,
            reasoning=f"Recent activity detected (last contact {context.days_since_last_contact} days ago)"
        )

    def _create_dormant_recoverable_strategy(self, context: LeadContext) -> UpdateStrategy:
        """Strategy for dormant but recoverable leads - stay positive!"""
        return UpdateStrategy(
            disposition=LeadDisposition.DORMANT_RECOVERABLE,
            tone=UpdateTone.PERSISTENT,
            template_category="persistent_engagement",
            key_message="Continuing to nurture relationship and stay top of mind",
            show_action_plan=True,
            reasoning=f"Dormant for {context.days_since_last_contact} days but still viable. Showing persistence."
        )

    def _create_ghosting_strategy(self, context: LeadContext) -> UpdateStrategy:
        """Strategy for ghosting leads - strategic re-engagement"""
        return UpdateStrategy(
            disposition=LeadDisposition.GHOSTING,
            tone=UpdateTone.STRATEGIC,
            template_category="strategic_reengagement",
            key_message="Adjusting approach to re-engage and add value",
            show_action_plan=True,
            reasoning=f"No contact for {context.days_since_last_contact} days. Using strategic approach."
        )

    def _create_dead_confirmed_strategy(self, context: LeadContext) -> UpdateStrategy:
        """Strategy for confirmed dead leads - professional closure"""
        reason = context.explicit_dead_reason or "Lead is no longer viable"
        return UpdateStrategy(
            disposition=LeadDisposition.DEAD_CONFIRMED,
            tone=UpdateTone.CLOSING,
            template_category="professional_closure",
            key_message=f"Lead closed: {reason}",
            show_action_plan=False,
            reasoning=f"Explicit dead reason: {reason}"
        )

    def _create_dead_unresponsive_strategy(self, context: LeadContext) -> UpdateStrategy:
        """Strategy for unresponsive dead leads - respectful closure"""
        return UpdateStrategy(
            disposition=LeadDisposition.DEAD_UNRESPONSIVE,
            tone=UpdateTone.CLOSING,
            template_category="respectful_closure",
            key_message=f"Unable to connect after {context.total_attempts} attempts",
            show_action_plan=False,
            reasoning=f"{context.total_attempts} attempts with 0 responses over {context.days_since_last_contact} days"
        )


# Update templates for each category
# IMPORTANT: All templates must be HONEST and based on actual activity
UPDATE_TEMPLATES = {
    "active_progress": [
        "Currently in active communication. Discussed {topic} and moving forward with next steps.",
        "Making good progress. Last spoke on {date} about {topic}. Following up with {action}.",
        "Lead is engaged and responsive. Working through {stage} and will {next_step}.",
        "Recent conversation was productive. Addressing {concern} and planning {action}.",
    ],

    "persistent_engagement": [
        "Continuing outreach with market updates. Working to re-engage and provide value.",
        "Maintaining contact with relevant information about their area. Will follow up this week.",
        "Staying in touch periodically. Planning next touchpoint with fresh market data.",
        "Keeping relationship warm with periodic check-ins and local market insights.",
        "Working to stay top of mind through consistent, value-focused communication.",
    ],

    "strategic_reengagement": [
        "Adjusting outreach strategy to provide more targeted value around {interest}.",
        "Trying different communication channels and times to reconnect.",
        "Shifting approach to focus on {angle} which may resonate better.",
        "Pivoting strategy to re-engage with fresh perspective on {topic}.",
    ],

    "professional_closure": [
        "Lead has indicated they are {reason}. Closing respectfully and wishing them well.",
        "Client confirmed they are {reason}. Maintaining positive relationship for future referrals.",
        "Lead decided to {reason}. Handled professionally and left door open.",
    ],

    "respectful_closure": [
        "After multiple attempts across different channels, unable to establish contact. Closing respectfully.",
        "Reached out {attempts} times via phone, email, and text without response. Moving to inactive status.",
        "Despite consistent follow-up, lead has not engaged. Closing to focus efforts on responsive leads.",
    ],
}


def generate_update_text(strategy: UpdateStrategy, context: LeadContext,
                        template_vars: Optional[Dict[str, str]] = None) -> str:
    """
    Generate the actual update text based on strategy

    Args:
        strategy: UpdateStrategy from determine_strategy()
        context: LeadContext with lead details
        template_vars: Optional variables to fill templates (topic, action, etc.)

    Returns:
        Update text ready to send to lead source platform
    """
    import random

    templates = UPDATE_TEMPLATES.get(strategy.template_category, [])
    if not templates:
        # Fallback
        return strategy.key_message

    # Pick a random template for variety
    template = random.choice(templates)

    # Fill in variables if provided
    if template_vars:
        try:
            return template.format(**template_vars)
        except KeyError:
            # Missing variable, use template as-is
            pass

    # Replace common placeholders with generic text
    generic_replacements = {
        "{topic}": "their needs",
        "{date}": "recently",
        "{action}": "connect again",
        "{stage}": "their options",
        "{next_step}": "schedule a follow-up",
        "{concern}": "their questions",
        "{approach}": "a fresh angle",
        "{interest}": "their situation",
        "{angle}": "market opportunities",
        "{reason}": context.explicit_dead_reason or "pursuing other options",
        "{attempts}": str(context.total_attempts),
    }

    result = template
    for placeholder, replacement in generic_replacements.items():
        result = result.replace(placeholder, replacement)

    return result


# Example usage
if __name__ == "__main__":
    # Test with different scenarios

    engine = LeadUpdateStrategyEngine()

    # Scenario 1: Active lead
    active_context = LeadContext(
        lead_id="1",
        lead_name="John Doe",
        source_name="ReferralExchange",
        days_since_last_contact=3,
        days_since_created=10,
        total_attempts=5,
        total_responses=3,
        fub_stage="Active",
        has_recent_notes=True,
        has_recent_messages=True
    )

    strategy = engine.determine_strategy(active_context)
    update = generate_update_text(strategy, active_context)

    print(f"Active Lead Update:")
    print(f"  Strategy: {strategy.disposition.value} - {strategy.tone.value}")
    print(f"  Update: {update}")
    print()

    # Scenario 2: Dormant but recoverable
    dormant_context = LeadContext(
        lead_id="2",
        lead_name="Jane Smith",
        source_name="HomeLight",
        days_since_last_contact=20,
        days_since_created=45,
        total_attempts=3,
        total_responses=1,
        fub_stage="Lead",
        has_recent_notes=False,
        has_recent_messages=False
    )

    strategy = engine.determine_strategy(dormant_context)
    update = generate_update_text(strategy, dormant_context)

    print(f"Dormant Lead Update:")
    print(f"  Strategy: {strategy.disposition.value} - {strategy.tone.value}")
    print(f"  Update: {update}")
    print()

    # Scenario 3: Dead confirmed
    dead_context = LeadContext(
        lead_id="3",
        lead_name="Bob Johnson",
        source_name="Redfin",
        days_since_last_contact=5,
        days_since_created=30,
        total_attempts=2,
        total_responses=1,
        fub_stage="Dead",
        has_recent_notes=True,
        has_recent_messages=False,
        explicit_dead_reason="Working with another agent"
    )

    strategy = engine.determine_strategy(dead_context)
    update = generate_update_text(strategy, dead_context)

    print(f"Dead Lead Update:")
    print(f"  Strategy: {strategy.disposition.value} - {strategy.tone.value}")
    print(f"  Update: {update}")
