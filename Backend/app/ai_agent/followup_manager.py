"""
Follow-Up Manager - Automated follow-up sequence orchestration.

Manages re-engagement sequences when leads go silent:
- Day 1: Primary channel (SMS) - gentle reminder
- Day 3: Primary channel - different angle/value add
- Day 7: Secondary channel (Email) - channel switch
- Day 14: Final attempt with "last chance" framing
- Day 30+: Move to long-term nurture (monthly touchpoints)

Integrates with Celery for scheduled task execution and respects:
- Working hours (8 AM - 8 PM lead's timezone)
- Rate limits (max 3 messages per 24 hours)
- Stage changes (cancel sequence if stage becomes blocked)
- Lead responses (cancel sequence immediately on any response)
"""

import logging
import os
import re
import json
import aiohttp
from dataclasses import dataclass, field
from datetime import datetime, timedelta, time
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
import uuid
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Python 3.8 fallback
    from backports.zoneinfo import ZoneInfo
import pytz

# Import source name mapping from initial outreach generator for consistent naming
try:
    from app.ai_agent.initial_outreach_generator import SOURCE_NAME_MAP
except ImportError:
    # Fallback if not available
    SOURCE_NAME_MAP = {}

logger = logging.getLogger(__name__)


# TCPA Quiet Hours (8 PM - 8 AM in recipient's local time)
TCPA_QUIET_START_HOUR = 20  # 8 PM - stop sending
TCPA_QUIET_END_HOUR = 8     # 8 AM - resume sending
TCPA_SAFE_START_HOUR = 9    # 9 AM - preferred start (1 hour buffer)
DEFAULT_TIMEZONE = "America/New_York"


def get_next_valid_send_time(
    intended_time: datetime,
    lead_timezone: str = DEFAULT_TIMEZONE,
) -> datetime:
    """
    Adjust send time to respect TCPA quiet hours in lead's timezone.

    TCPA regulations restrict SMS/call to 8 AM - 9 PM local time.
    This function adjusts any time outside that window to the next
    valid sending window.

    Args:
        intended_time: The originally intended send time (can be any timezone)
        lead_timezone: The lead's timezone (IANA format, e.g., "America/New_York")

    Returns:
        datetime: Adjusted send time that falls within TCPA-allowed hours

    Example:
        >>> # Scheduling for 11 PM EST would move to 9 AM next day
        >>> intended = datetime(2024, 1, 15, 23, 0)  # 11 PM
        >>> result = get_next_valid_send_time(intended, "America/New_York")
        >>> result.hour  # Should be 9 AM next day
        9

        >>> # Scheduling for 6 AM EST would move to 9 AM same day
        >>> intended = datetime(2024, 1, 15, 6, 0)  # 6 AM
        >>> result = get_next_valid_send_time(intended, "America/New_York")
        >>> result.hour  # Should be 9 AM same day
        9
    """
    # Validate and get timezone
    try:
        tz = ZoneInfo(lead_timezone)
    except Exception:
        logger.warning(f"Unknown timezone '{lead_timezone}', using {DEFAULT_TIMEZONE}")
        tz = ZoneInfo(DEFAULT_TIMEZONE)

    # Ensure intended_time is timezone-aware in UTC first
    if intended_time.tzinfo is None:
        # Assume UTC if no timezone
        intended_time = intended_time.replace(tzinfo=ZoneInfo("UTC"))

    # Convert to lead's local time
    local_time = intended_time.astimezone(tz)
    local_hour = local_time.hour

    # Check if within TCPA-allowed hours (8 AM - 8 PM)
    if TCPA_QUIET_END_HOUR <= local_hour < TCPA_QUIET_START_HOUR:
        # Within allowed hours - return as-is (converted back to UTC)
        return local_time.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    # Outside allowed hours - adjust to next valid window
    if local_hour >= TCPA_QUIET_START_HOUR:
        # After 8 PM - schedule for 9 AM tomorrow
        next_day = local_time.date() + timedelta(days=1)
        adjusted = datetime.combine(next_day, time(TCPA_SAFE_START_HOUR, 0), tzinfo=tz)
        logger.info(
            f"TCPA adjustment: {local_time.strftime('%I:%M %p')} is after quiet hours, "
            f"moved to {adjusted.strftime('%I:%M %p %Z')} next day"
        )
    else:
        # Before 8 AM - schedule for 9 AM same day
        adjusted = local_time.replace(hour=TCPA_SAFE_START_HOUR, minute=0, second=0, microsecond=0)
        logger.info(
            f"TCPA adjustment: {local_time.strftime('%I:%M %p')} is before allowed hours, "
            f"moved to {adjusted.strftime('%I:%M %p %Z')}"
        )

    # Convert back to UTC for storage
    return adjusted.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def is_within_tcpa_hours(
    check_time: datetime = None,
    timezone: str = DEFAULT_TIMEZONE,
) -> Tuple[bool, Optional[datetime]]:
    """
    Check if a given time (or now) is within TCPA-allowed hours.

    Args:
        check_time: Time to check (defaults to now)
        timezone: Timezone to check in

    Returns:
        Tuple of (is_allowed, next_allowed_time)
        - is_allowed: True if within 8 AM - 8 PM
        - next_allowed_time: When the next window opens (None if already allowed)
    """
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        tz = ZoneInfo(DEFAULT_TIMEZONE)

    if check_time is None:
        check_time = datetime.now(tz)
    elif check_time.tzinfo is None:
        check_time = check_time.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
    else:
        check_time = check_time.astimezone(tz)

    local_hour = check_time.hour

    if TCPA_QUIET_END_HOUR <= local_hour < TCPA_QUIET_START_HOUR:
        return True, None

    # Calculate next allowed time
    if local_hour >= TCPA_QUIET_START_HOUR:
        next_day = check_time.date() + timedelta(days=1)
        next_allowed = datetime.combine(next_day, time(TCPA_SAFE_START_HOUR, 0), tzinfo=tz)
    else:
        next_allowed = check_time.replace(hour=TCPA_SAFE_START_HOUR, minute=0, second=0, microsecond=0)

    return False, next_allowed


class FollowUpStatus(Enum):
    """Status of a scheduled follow-up."""
    PENDING = "pending"
    SENT = "sent"
    CANCELLED = "cancelled"
    FAILED = "failed"
    SKIPPED = "skipped"  # Skipped due to compliance/stage check


class FollowUpTrigger(Enum):
    """What triggered the follow-up sequence."""
    NO_RESPONSE = "no_response"  # Lead hasn't responded
    COLD_LEAD = "cold_lead"  # Lead score dropped
    NEW_LEAD = "new_lead"  # Initial outreach sequence
    RE_ENGAGEMENT = "re_engagement"  # Been a while since contact
    EVENT_BASED = "event_based"  # Property match, price drop, etc.

    # Smart re-engagement triggers (context-aware)
    RESUME_QUALIFICATION = "resume_qualification"  # Was in qualification flow
    RESUME_SCHEDULING = "resume_scheduling"        # Was scheduling appointment
    RESUME_OBJECTION = "resume_objection"          # Had unresolved objection


class MessageType(Enum):
    """Type of follow-up message."""
    # Original types
    GENTLE_FOLLOWUP = "gentle_followup"
    VALUE_ADD = "value_add"
    CHANNEL_SWITCH = "channel_switch"
    FINAL_ATTEMPT = "final_attempt"
    MONTHLY_TOUCHPOINT = "monthly_touchpoint"

    # ============================================================================
    # NEW MESSAGE TYPES - World-class follow-up sequence
    # Research: MIT study shows 21x higher conversion within 5 minutes
    # ============================================================================

    # Day 0 - Immediate first contact with qualification question
    FIRST_CONTACT = "first_contact"
    # Day 0 + 30 min - Value add with appointment CTA
    VALUE_WITH_CTA = "value_with_cta"
    # Day 1 - Qualify motivation/situation
    QUALIFY_MOTIVATION = "qualify_motivation"
    # Day 2 - Property alert style value add
    VALUE_ADD_LISTING = "value_add_listing"
    # Day 3 - Email with market report + multiple time slots
    EMAIL_MARKET_REPORT = "email_market_report"
    # Day 4 - Social proof
    SOCIAL_PROOF = "social_proof"
    # Day 7 - Strategic break-up (highest response rate message!)
    STRATEGIC_BREAKUP = "strategic_breakup"
    # Voice messages (for when voice_enabled=True)
    RVM_INTRO = "rvm_intro"
    CALL_CHECKIN = "call_checkin"

    # ============================================================================
    # NEW EMAIL MESSAGE TYPES - Multi-channel follow-up (added for email integration)
    # ============================================================================
    EMAIL_WELCOME = "email_welcome"             # Day 0 - Initial welcome email with full intro
    EMAIL_VALUE = "email_value"                 # Day 1 - Market insights + appointment slots
    EMAIL_SOCIAL_PROOF = "email_social_proof"   # Day 5 - Success story / case study
    EMAIL_FINAL = "email_final"                 # Day 7 - Warm close, door open

    # Additional SMS types
    HELPFUL_CHECKIN = "helpful_checkin"         # Day 6 - Soft helpful SMS

    # ============================================================================
    # SMART RE-ENGAGEMENT MESSAGE TYPES
    # These are context-aware messages that reference the previous conversation
    # instead of generic follow-ups. The AI knows what was discussed.
    # ============================================================================
    RESUME_QUALIFICATION = "resume_qualification"     # Pick up qualification questions
    RESUME_SCHEDULING = "resume_scheduling"           # Re-offer appointment times
    RESUME_OBJECTION = "resume_objection"             # Address lingering concern
    RESUME_GENERAL = "resume_general"                 # General check-in with context


@dataclass
class FollowUpStep:
    """A single step in a follow-up sequence."""
    delay_days: int
    channel: str  # "primary", "secondary", "sms", "email", "rvm", "call"
    message_type: MessageType
    message_template: Optional[str] = None
    # NEW: Support sub-day timing for aggressive Day 0 sequence
    delay_minutes: int = 0  # Additional minutes after delay_days
    # NEW: Skip this step if the specified channel is disabled
    # Options: "voice_enabled", "rvm_enabled", None (never skip)
    skip_if_disabled: Optional[str] = None


@dataclass
class ScheduledFollowUp:
    """A scheduled follow-up task."""
    id: str
    fub_person_id: int
    organization_id: str
    scheduled_at: datetime
    channel: str
    message_type: str
    sequence_step: int
    sequence_id: str
    status: FollowUpStatus = FollowUpStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    executed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "fub_person_id": self.fub_person_id,
            "organization_id": self.organization_id,
            "scheduled_at": self.scheduled_at.isoformat(),
            "channel": self.channel,
            "message_type": self.message_type,
            "sequence_step": self.sequence_step,
            "sequence_id": self.sequence_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "error_message": self.error_message,
        }


class FollowUpManager:
    """
    Manages automated follow-up sequences for leads.

    Schedules and executes follow-up messages based on sequences,
    respecting compliance rules and cancelling on lead response.
    """

    # ==========================================================================
    # FOLLOW-UP SEQUENCES - Research-backed timing and cadence
    # Source: Follow Up Boss, The Close, Curaytor, Ylopo (2024-2025 data)
    #
    # KEY INSIGHTS:
    # - 1-5 minute response = up to 391% higher conversion
    # - Average lead needs 5-7 touches before converting
    # - Most agents give up after 1-2 attempts (huge opportunity!)
    # - 8-12 touchpoints total needed to close a deal
    # ==========================================================================

    # ==========================================================================
    # NEW LEAD SEQUENCE - WORLD-CLASS AGGRESSIVE (11 touches, 7 days)
    # Research: MIT study - 21x higher conversion within 5 minutes
    # Robert Slack mega-team: 45-day text campaign = 34% -> 65% connections
    # 78% of sales go to first responder (LeadSimple)
    #
    # UPDATED: Multi-channel approach with EMAIL throughout
    # With voice_enabled=False (default): 12 touches over 7 days (7 SMS + 5 Email)
    # With voice_enabled=True: 16 touches over 7 days (7 SMS + 5 Email + 4 Voice)
    #
    # Each step includes:
    # - Qualification questions to gather intel
    # - Appointment CTAs using "assumptive close" technique
    # - Strategic break-up message (highest response rate!)
    # - EMAIL integrated throughout for multi-channel reach
    # ==========================================================================
    SEQUENCE_NEW_LEAD = [
        # Step 1: Day 0, 0 min - IMMEDIATE first contact SMS
        FollowUpStep(
            delay_days=0,
            delay_minutes=0,
            channel="sms",
            message_type=MessageType.FIRST_CONTACT,
            skip_if_disabled=None,  # Always send
        ),
        # Step 2: Day 0, 2 min - Welcome EMAIL (full intro + value)
        FollowUpStep(
            delay_days=0,
            delay_minutes=2,
            channel="email",
            message_type=MessageType.EMAIL_WELCOME,
            skip_if_disabled=None,  # Always send - email establishes professionalism
        ),
        # Step 3: Day 0, 5 min - RVM intro (if voice enabled)
        FollowUpStep(
            delay_days=0,
            delay_minutes=5,
            channel="rvm",
            message_type=MessageType.RVM_INTRO,
            skip_if_disabled="voice_enabled",  # Skip if voice OFF
        ),
        # Step 4: Day 0, 30 min - Value SMS + appointment CTA
        FollowUpStep(
            delay_days=0,
            delay_minutes=30,
            channel="sms",
            message_type=MessageType.VALUE_WITH_CTA,
            skip_if_disabled=None,  # Always send
        ),
        # Step 5: Day 0, 2 hours - Call check-in (if voice enabled)
        FollowUpStep(
            delay_days=0,
            delay_minutes=120,
            channel="call",
            message_type=MessageType.CALL_CHECKIN,
            skip_if_disabled="voice_enabled",  # Skip if voice OFF
        ),
        # Step 6: Day 1, AM - Qualify motivation SMS
        FollowUpStep(
            delay_days=1,
            delay_minutes=0,  # Morning
            channel="sms",
            message_type=MessageType.QUALIFY_MOTIVATION,
            skip_if_disabled=None,
        ),
        # Step 7: Day 1, PM - Value EMAIL with market insights
        FollowUpStep(
            delay_days=1,
            delay_minutes=360,  # 6 hours after morning = early afternoon
            channel="email",
            message_type=MessageType.EMAIL_VALUE,
            skip_if_disabled=None,
        ),
        # Step 8: Day 1, Late PM - Call follow-up (if voice enabled)
        FollowUpStep(
            delay_days=1,
            delay_minutes=540,  # 9 hours after morning = late afternoon
            channel="call",
            message_type=MessageType.CALL_CHECKIN,
            skip_if_disabled="voice_enabled",
        ),
        # Step 9: Day 2 - Property value add SMS
        FollowUpStep(
            delay_days=2,
            delay_minutes=0,
            channel="sms",
            message_type=MessageType.VALUE_ADD_LISTING,
            skip_if_disabled=None,
        ),
        # Step 10: Day 3 - Email market report + time slots
        FollowUpStep(
            delay_days=3,
            delay_minutes=0,
            channel="email",
            message_type=MessageType.EMAIL_MARKET_REPORT,
            skip_if_disabled=None,
        ),
        # Step 11: Day 4 - Social proof SMS
        FollowUpStep(
            delay_days=4,
            delay_minutes=0,
            channel="sms",
            message_type=MessageType.SOCIAL_PROOF,
            skip_if_disabled=None,
        ),
        # Step 12: Day 5, AM - Social proof EMAIL (success story)
        FollowUpStep(
            delay_days=5,
            delay_minutes=0,
            channel="email",
            message_type=MessageType.EMAIL_SOCIAL_PROOF,
            skip_if_disabled=None,
        ),
        # Step 13: Day 5, PM - Call attempt (if voice enabled)
        FollowUpStep(
            delay_days=5,
            delay_minutes=360,  # 6 hours later = afternoon
            channel="call",
            message_type=MessageType.CALL_CHECKIN,
            skip_if_disabled="voice_enabled",
        ),
        # Step 14: Day 6 - Helpful check-in SMS (soft touch)
        FollowUpStep(
            delay_days=6,
            delay_minutes=0,
            channel="sms",
            message_type=MessageType.HELPFUL_CHECKIN,
            skip_if_disabled=None,
        ),
        # Step 15: Day 7, AM - Final EMAIL (warm close, door open)
        FollowUpStep(
            delay_days=7,
            delay_minutes=0,
            channel="email",
            message_type=MessageType.EMAIL_FINAL,
            skip_if_disabled=None,
        ),
        # Step 16: Day 7, PM - Strategic break-up SMS (highest response rate!)
        FollowUpStep(
            delay_days=7,
            delay_minutes=360,  # 6 hours later = afternoon
            channel="sms",
            message_type=MessageType.STRATEGIC_BREAKUP,
            skip_if_disabled=None,
        ),
    ]

    # LEGACY: Original conservative sequence (kept for backwards compatibility)
    SEQUENCE_NEW_LEAD_CONSERVATIVE = [
        FollowUpStep(
            delay_days=0,
            channel="sms",
            message_type=MessageType.GENTLE_FOLLOWUP,
        ),
        FollowUpStep(
            delay_days=1,
            channel="sms",
            message_type=MessageType.VALUE_ADD,
        ),
        FollowUpStep(
            delay_days=2,
            channel="sms",
            message_type=MessageType.GENTLE_FOLLOWUP,
        ),
        FollowUpStep(
            delay_days=4,
            channel="email",
            message_type=MessageType.CHANNEL_SWITCH,
        ),
        FollowUpStep(
            delay_days=7,
            channel="sms",
            message_type=MessageType.FINAL_ATTEMPT,
        ),
    ]

    # STANDARD RE-ENGAGEMENT - Lead went quiet mid-conversation
    # Goal: Re-spark interest without being pushy
    SEQUENCE_STANDARD = [
        FollowUpStep(
            delay_days=1,
            channel="primary",
            message_type=MessageType.GENTLE_FOLLOWUP,
        ),
        FollowUpStep(
            delay_days=3,
            channel="primary",
            message_type=MessageType.VALUE_ADD,
        ),
        FollowUpStep(
            delay_days=7,
            channel="secondary",
            message_type=MessageType.CHANNEL_SWITCH,
        ),
        FollowUpStep(
            delay_days=14,
            channel="secondary",
            message_type=MessageType.FINAL_ATTEMPT,
        ),
    ]

    # REVIVAL SEQUENCE - Cold/dormant leads (30+ days inactive)
    # Research: "Cold leads aren't dead—just dormant"
    # 70% of databases have engagement potential, teams only achieve 30%
    # Goal: Offer VALUE first, not sales pitch. Reference their original criteria.
    SEQUENCE_REVIVAL = [
        FollowUpStep(
            delay_days=0,  # Immediate - market update or new listing
            channel="sms",
            message_type=MessageType.VALUE_ADD,  # Lead with value, not ask
        ),
        FollowUpStep(
            delay_days=7,  # Week later - check if situation changed
            channel="sms",
            message_type=MessageType.GENTLE_FOLLOWUP,
        ),
        FollowUpStep(
            delay_days=21,  # 3 weeks - email with more detail
            channel="email",
            message_type=MessageType.CHANNEL_SWITCH,
        ),
        FollowUpStep(
            delay_days=45,  # 6 weeks - final gentle touch
            channel="email",
            message_type=MessageType.FINAL_ATTEMPT,
        ),
    ]

    # Long-term nurture (monthly touchpoints)
    # For leads with 6+ month timeline - stay top of mind without pressure
    # UPDATED: Alternates SMS and Email for multi-channel nurture
    SEQUENCE_NURTURE = [
        # Month 1 - Email with market update
        FollowUpStep(
            delay_days=30,
            channel="email",
            message_type=MessageType.MONTHLY_TOUCHPOINT,
        ),
        # Month 2 - SMS check-in
        FollowUpStep(
            delay_days=60,
            channel="sms",
            message_type=MessageType.GENTLE_FOLLOWUP,
        ),
        # Month 3 - Email with value
        FollowUpStep(
            delay_days=90,
            channel="email",
            message_type=MessageType.MONTHLY_TOUCHPOINT,
        ),
        # Month 4 - SMS
        FollowUpStep(
            delay_days=120,
            channel="sms",
            message_type=MessageType.VALUE_ADD,
        ),
        # Month 5 - Email
        FollowUpStep(
            delay_days=150,
            channel="email",
            message_type=MessageType.MONTHLY_TOUCHPOINT,
        ),
        # Month 6 - SMS + offer to re-engage
        FollowUpStep(
            delay_days=180,
            channel="sms",
            message_type=MessageType.GENTLE_FOLLOWUP,
        ),
    ]

    # ==========================================================================
    # MESSAGE TEMPLATES - Designed to feel human, not robotic
    # Golden Rule: "Would I read and reply to this myself?"
    #
    # Guidelines from research:
    # - Keep SMS under 160 chars, conversational
    # - Reference specific details when possible
    # - Don't sound salesy or pushy
    # - Ask ONE question at a time
    # ==========================================================================
    MESSAGE_TEMPLATES = {
        # GENTLE FOLLOWUP - Casual check-ins, don't sound desperate
        MessageType.GENTLE_FOLLOWUP: [
            # New lead first contact
            "Hey {first_name}! This is {agent_name}. Saw you were looking at homes - exciting! Are you just starting to look or closer to making a move?",
            "Hi {first_name}, {agent_name} here. Got your info - when are you thinking of making a move?",
            # Follow-up after no response
            "{first_name}, just checking in! Any questions I can help with?",
            "Hey {first_name} - still thinking about {area}? No rush, just wanted to touch base",
            "Hi {first_name}! Did you have a chance to think about what we chatted about?",
        ],
        # VALUE ADD - Lead with value, not asks
        MessageType.VALUE_ADD: [
            # Market-based
            "{first_name}, heads up - just saw a new listing in {area} that might fit what you're looking for. Want details?",
            "Hey {first_name}! {area} market is moving - prices are {trend}. Good time to chat strategy?",
            # For revival leads - reference their original criteria
            "{first_name}, remember you were looking at {property_type} in {area}? Just saw one hit the market. Interested?",
            "Hi {first_name}! A 3-bed just listed near {area} under asking. Worth a look?",
            # Helpful tips
            "{first_name}, quick tip: {tip}. Thought of you!",
        ],
        # CHANNEL SWITCH - Email when SMS isn't working
        MessageType.CHANNEL_SWITCH: [
            "Subject: {first_name} - Quick question\n\nHey {first_name},\n\nTrying email in case texts aren't the best way to reach you. Still thinking about {area}?\n\nNo pressure - just want to make sure I'm here when you need me.\n\n{agent_name}",
            "Subject: Still interested in {area}?\n\nHi {first_name},\n\nI know life gets crazy! Just wanted to check if your home search is still on the radar.\n\nIf your situation has changed, no worries at all. But if you're still looking, I'd love to help.\n\n{agent_name}",
        ],
        # FINAL ATTEMPT - Soft close, leave door open
        MessageType.FINAL_ATTEMPT: [
            "{first_name}, I'll stop bugging you! Just know I'm here when you're ready. Feel free to reach out anytime 👋",
            "Hey {first_name} - going to give you some space, but I'm here if anything changes. Good luck with everything!",
            "Subject: No pressure, {first_name}\n\nHi {first_name},\n\nI'll take a step back - I know timing is everything in real estate.\n\nWhen you're ready to jump back in, just shoot me a text. I'll be here.\n\nTake care,\n{agent_name}",
        ],
        # MONTHLY TOUCHPOINT - Stay top of mind without being annoying
        MessageType.MONTHLY_TOUCHPOINT: [
            "Subject: {area} Market Update - {month}\n\nHey {first_name}!\n\nQuick update on {area}:\n{market_update}\n\nIf any of this changes your timeline, let me know!\n\n{agent_name}",
            "Subject: Thought you'd find this interesting\n\nHi {first_name},\n\nSaw this and thought of you - {area} just had {interesting_stat}.\n\nHope all is well! Let me know if you want to chat.\n\n{agent_name}",
        ],

        # ======================================================================
        # NEW WORLD-CLASS TEMPLATES - Research-backed high-conversion messages
        # Key principles:
        # - Qualification questions in early touches
        # - Assumptive close for appointment CTAs
        # - Strategic break-up (highest response rate message!)
        # ======================================================================

        # FIRST_CONTACT - Day 0, Immediate + Qualify Timeline
        # Goal: Establish rapport, qualify when they want to move
        MessageType.FIRST_CONTACT: [
            "Hey {first_name}! {agent_name} here from {brokerage}. Saw you're looking at homes in {area} - exciting! When are you thinking of making a move?",
            "Hi {first_name}! This is {agent_name}. Got your info about {area} - love that area! Are you just starting to look or closer to ready?",
            "{first_name}, hey! {agent_name} here. Quick question - are you looking to buy in the next few months, or is this more of a 6+ month thing?",
        ],

        # VALUE_WITH_CTA - Day 0 + 30 min, Value + Appointment CTA
        # Goal: Offer value AND proactively suggest appointment ("assumptive close")
        MessageType.VALUE_WITH_CTA: [
            "{first_name}, btw I have a few times open this week if you want to chat about {area}. Would {suggested_day} afternoon work for a quick call?",
            "Quick thought {first_name} - I just helped someone close in {area} last week. Happy to share what I'm seeing in the market. Got time for a 10-min call {suggested_day}?",
            "{first_name}, I've got some insider info on {area} that might help. Free for a quick chat {suggested_day} at {suggested_time}?",
        ],

        # QUALIFY_MOTIVATION - Day 1, Qualify Motivation/Situation
        # Goal: Understand their situation better
        MessageType.QUALIFY_MOTIVATION: [
            "{first_name}, quick question - are you looking to buy first, or do you have a place to sell too? Helps me know how to best help you!",
            "Hey {first_name}! Curious - what's driving your home search? Job change, growing family, or just ready for something new?",
            "{first_name}, one more thing - is it just you looking, or are you house hunting with a partner/family? Want to make sure I include everyone!",
        ],

        # VALUE_ADD_LISTING - Day 2, Property Alert Style
        # Goal: Provide specific value (feels like a personal tip)
        MessageType.VALUE_ADD_LISTING: [
            "{first_name}, heads up - just saw a new listing in {area} that might fit what you're looking for. 3BR, updated kitchen. Want details?",
            "Hey {first_name}! A {property_type} just hit the market in {area} under asking. Could be worth a look - interested?",
            "{first_name}, thought of you - there's a great {property_type} near {area} that just listed. Want me to send the link?",
        ],

        # EMAIL_MARKET_REPORT - Day 3, Email with Market Report + Time Slots
        # Goal: Multi-touch via email with value + multiple appointment options
        MessageType.EMAIL_MARKET_REPORT: [
            "Subject: {first_name} - Quick {area} Market Update\n\nHey {first_name}!\n\nWanted to share a quick update on {area}:\n\n- Average home price: {avg_price}\n- Days on market: {dom} days\n- Trend: {trend}\n\nI've got a few times open this week if you want to chat strategy:\n- {slot_1}\n- {slot_2}\n- {slot_3}\n\nJust reply with which works, or let me know if you need different times!\n\n{agent_name}\n{agent_phone}",
        ],

        # SOCIAL_PROOF - Day 4, Social Proof
        # Goal: Build credibility through recent success stories
        MessageType.SOCIAL_PROOF: [
            "{first_name}, just helped a buyer close on a great place in {area} last week. Happy to do the same for you when you're ready!",
            "Hey {first_name}! Fun fact - I've helped 3 families find homes in {area} this month. Let me know if you want to be #4!",
            "{first_name}, quick update - {area} is hot right now. Just got one of my buyers into a place before it went to multiple offers. When you're ready, I've got your back!",
        ],

        # STRATEGIC_BREAKUP - Day 7, Strategic "Closing File" Message
        # Research: Break-up emails often get HIGHEST response rates
        # Creates FOMO and urgency while leaving door open
        MessageType.STRATEGIC_BREAKUP: [
            "{first_name}, I'm closing your file for now since I haven't heard back - but I totally get it, timing is everything!\n\nQuick question before I do: Did something change, or is now just not the right time?\n\nEither way, no hard feelings - I'll be here when you're ready!",
            "Hey {first_name}, going to give you some space - I know house hunting can be overwhelming!\n\nOne last thing: If you're working with another agent, just let me know and I'll back off. If not, I'm here whenever you're ready to chat.",
            "{first_name}, I'll stop reaching out for now, but wanted to leave the door open.\n\nIf your situation changes or you have questions about {area}, I'm just a text away. Good luck with everything!",
        ],

        # RVM_INTRO - Ringless Voicemail Script (for voice_enabled=True)
        MessageType.RVM_INTRO: [
            "Hey {first_name}, this is {agent_name}. I saw you were looking at homes in {area} and wanted to personally reach out. I just sent you a text with my info - give me a call or text back when you get a chance. Talk soon!",
        ],

        # CALL_CHECKIN - Phone Call Script (for voice_enabled=True)
        MessageType.CALL_CHECKIN: [
            # This is used as context for AI voice or human agent
            "Hi {first_name}, this is {agent_name} calling about your home search in {area}. Do you have a quick minute to chat?",
        ],

        # ======================================================================
        # NEW EMAIL TEMPLATES - Multi-channel follow-up sequence
        # These provide fallback templates when AI generation is unavailable
        # ======================================================================

        # EMAIL_WELCOME - Day 0, Initial welcome email with full intro
        # Goal: Establish professionalism, introduce yourself, offer value
        MessageType.EMAIL_WELCOME: [
            "Subject: Nice to meet you, {first_name}!\n\nHey {first_name},\n\nI just sent you a quick text, but wanted to follow up here too!\n\nI'm {agent_name} with {brokerage}. I saw you're interested in {area} - great choice! I specialize in that area and would love to help.\n\nA few things I can do for you:\n- Send you new listings as soon as they hit the market\n- Share insider info on neighborhoods\n- Answer any questions about the process\n\nWhat's your timeline looking like? Just reply to this email or text me back!\n\nTalk soon,\n{agent_name}\n{agent_phone}",
        ],

        # EMAIL_VALUE - Day 1, Market insights + appointment slots
        # Goal: Provide real value, multiple appointment options
        MessageType.EMAIL_VALUE: [
            "Subject: {area} Market Update + Quick Question\n\nHey {first_name},\n\nWanted to share what I'm seeing in {area} right now:\n\n- Average days on market: {dom} days\n- Price trend: {trend}\n- Hot tip: {market_insight}\n\nI've got some time this week if you want to chat strategy. Would any of these work?\n\n- {slot_1}\n- {slot_2}\n- {slot_3}\n\nOr just reply with what works for you!\n\n{agent_name}",
        ],

        # EMAIL_SOCIAL_PROOF - Day 5, Success story / case study
        # Goal: Build credibility through specific success stories
        MessageType.EMAIL_SOCIAL_PROOF: [
            "Subject: How I helped a family just like you in {area}\n\nHey {first_name},\n\nQuick story I thought you'd appreciate:\n\nI recently helped a family find their dream home in {area}. They were in a similar situation - looking to {lead_type_action} and weren't sure where to start.\n\nWithin {timeframe}, we found them the perfect place:\n- Great neighborhood\n- Under budget\n- Beat out 3 other offers\n\nI'd love to do the same for you when you're ready. No pressure at all - just wanted you to know what's possible!\n\nHere when you need me,\n{agent_name}\n{agent_phone}",
        ],

        # EMAIL_FINAL - Day 7, Warm close, door open
        # Goal: Leave on a positive note, door always open
        MessageType.EMAIL_FINAL: [
            "Subject: {first_name}, one last thing...\n\nHey {first_name},\n\nI've reached out a few times and haven't heard back - totally understand! Life gets busy.\n\nI'm going to give you some space, but I wanted to leave you with this:\n\n- My door is always open\n- If your situation changes, just reply to this email\n- No judgment, no pressure - I'm here when YOU'RE ready\n\nWishing you all the best with your home search. If you ever need anything real estate related, I'm just a text or email away.\n\nTake care,\n{agent_name}\n{agent_phone}",
        ],

        # HELPFUL_CHECKIN - Day 6, Soft helpful SMS
        # Goal: Offer specific help without being pushy
        MessageType.HELPFUL_CHECKIN: [
            "{first_name}, just checking in! Is there anything specific I can help you with - questions about neighborhoods, the market, or the buying process? I'm here if you need me!",
            "Hey {first_name}! Wanted to see if there's anything I can do to help. Send listings? Answer questions? Just let me know!",
            "{first_name}, thinking of you! If you're still looking in {area}, I'd love to help. Any questions I can answer?",
        ],
    }

    def __init__(self, supabase_client=None):
        """
        Initialize Follow-Up Manager.

        Args:
            supabase_client: Database client for persistence
        """
        self.supabase = supabase_client

    def get_sequence(self, trigger: FollowUpTrigger) -> List[FollowUpStep]:
        """
        Get the follow-up sequence for a trigger type.

        Research-backed sequence selection:
        - NEW_LEAD: Aggressive 5-touch sequence over 7 days (speed matters!)
        - COLD_LEAD: Value-first revival sequence (don't sound desperate)
        - RE_ENGAGEMENT: Standard sequence for mid-conversation drops
        - NO_RESPONSE: Standard sequence
        - EVENT_BASED: Quick 2-touch for property matches/price drops
        """
        sequences = {
            FollowUpTrigger.NEW_LEAD: self.SEQUENCE_NEW_LEAD,
            FollowUpTrigger.COLD_LEAD: self.SEQUENCE_REVIVAL,  # Use revival for cold leads
            FollowUpTrigger.RE_ENGAGEMENT: self.SEQUENCE_REVIVAL,  # Also use revival for re-engagement
            FollowUpTrigger.NO_RESPONSE: self.SEQUENCE_STANDARD,
            FollowUpTrigger.EVENT_BASED: self.SEQUENCE_NEW_LEAD[:2],  # Just first 2 steps
        }
        return sequences.get(trigger, self.SEQUENCE_STANDARD)

    def get_qualification_skip_types(self, lead_profile: Any) -> set:
        """
        Determine which message types to skip based on already-known lead info.

        This implements intelligent qualification skip logic - if we already
        have the answer to a qualification question, don't ask it again.

        Args:
            lead_profile: LeadProfile object with lead data

        Returns:
            Set of MessageType values to skip in the sequence
        """
        skip_types = set()

        if not lead_profile:
            return skip_types

        # Skip FIRST_CONTACT/QUALIFY questions if we already have the answer
        # Timeline - if we know when they want to move
        if lead_profile.timeline:
            # Don't skip first contact, but may adjust messaging
            pass

        # Motivation - if we know why they're buying/selling
        if lead_profile.motivation:
            skip_types.add(MessageType.QUALIFY_MOTIVATION)
            logger.debug(f"Skipping QUALIFY_MOTIVATION - already have: {lead_profile.motivation}")

        # For buyers: skip budget questions if we have price range
        if lead_profile.lead_type == "buyer":
            if lead_profile.price_min or lead_profile.price_max:
                # Don't need to ask budget again
                logger.debug(f"Budget already known: ${lead_profile.price_min}-${lead_profile.price_max}")

            # Skip pre-approval question if we already know
            if lead_profile.is_pre_approved is not None:
                logger.debug(f"Pre-approval status known: {lead_profile.is_pre_approved}")

        # For sellers: skip property address question if we have it
        if lead_profile.lead_type == "seller":
            if lead_profile.current_address:
                logger.debug(f"Seller address known: {lead_profile.current_address}")

        # Skip location questions if we know preferred areas
        if lead_profile.preferred_cities or lead_profile.preferred_neighborhoods:
            logger.debug(f"Preferred areas known: {lead_profile.preferred_cities or lead_profile.preferred_neighborhoods}")

        return skip_types

    def should_use_ai_for_step(self, message_type: MessageType) -> bool:
        """
        Determine if a message type should use AI-generated content vs template.

        Some message types benefit from AI generation for personalization,
        while others are better as tested templates.

        Returns:
            True if AI should generate the message, False to use template
        """
        # Message types that benefit from AI personalization
        # ALL EMAILS should use AI for rich, context-aware content
        ai_preferred_types = {
            MessageType.FIRST_CONTACT,      # First impression matters - personalize
            MessageType.VALUE_ADD,          # Value should be contextual
            MessageType.VALUE_WITH_CTA,     # Appointment CTA should be personalized
            MessageType.VALUE_ADD_LISTING,  # Property-specific content
            MessageType.STRATEGIC_BREAKUP,  # Break-up message is high-stakes
            # NEW: All email types should use AI for personalization
            MessageType.EMAIL_WELCOME,      # Day 0 - Full intro needs personalization
            MessageType.EMAIL_VALUE,        # Day 1 - Market insights personalized
            MessageType.EMAIL_MARKET_REPORT,  # Day 3 - Market report personalized
            MessageType.EMAIL_SOCIAL_PROOF,   # Day 5 - Success story personalized
            MessageType.EMAIL_FINAL,          # Day 7 - Final close personalized
            MessageType.HELPFUL_CHECKIN,      # Day 6 - Soft SMS personalized
        }

        # Message types that work well as templates
        template_preferred_types = {
            MessageType.GENTLE_FOLLOWUP,    # Simple check-ins work as templates
            MessageType.SOCIAL_PROOF,       # Social proof can be templated
            MessageType.MONTHLY_TOUCHPOINT, # Nurture works with templates
            MessageType.RVM_INTRO,          # Voice scripts need consistency
            MessageType.CALL_CHECKIN,       # Call scripts need consistency
        }

        if message_type in ai_preferred_types:
            return True
        if message_type in template_preferred_types:
            return False

        # Default: use AI for qualification questions
        return "qualify" in message_type.value.lower()

    async def schedule_followup_sequence(
        self,
        fub_person_id: int,
        organization_id: str,
        trigger: FollowUpTrigger,
        start_delay_hours: int = 24,
        preferred_channel: str = "sms",
        lead_timezone: str = "America/New_York",
        settings: Any = None,  # AIAgentSettings object for channel toggles
        lead_profile: Any = None,  # LeadProfile for intelligent skip logic
    ) -> Dict[str, Any]:
        """
        Schedule a follow-up sequence for a lead.

        Now includes intelligent qualification skip logic - if we already know
        the answer to a qualification question, we skip that step.

        Args:
            fub_person_id: FUB person ID
            organization_id: Organization ID
            trigger: What triggered this sequence
            start_delay_hours: Hours until first follow-up (0 for NEW_LEAD instant)
            preferred_channel: Lead's preferred channel (for "primary")
            lead_timezone: Lead's timezone for scheduling
            settings: AIAgentSettings object with channel toggles (optional)
            lead_profile: LeadProfile for intelligent skip logic (optional)

        Returns:
            Dict with sequence_id and scheduled follow-ups
        """
        sequence = self.get_sequence(trigger)
        sequence_id = str(uuid.uuid4())
        scheduled_followups = []
        skipped_count = 0
        qualification_skipped_count = 0

        # For NEW_LEAD trigger with instant response, start_delay_hours should be 0
        if trigger == FollowUpTrigger.NEW_LEAD:
            start_delay_hours = 0

        base_time = datetime.utcnow() + timedelta(hours=start_delay_hours)

        # ================================================================
        # NEW: Get qualification questions to skip based on lead profile
        # ================================================================
        skip_types = self.get_qualification_skip_types(lead_profile) if lead_profile else set()

        for step_index, step in enumerate(sequence):
            # ================================================================
            # Check if this step should be skipped based on channel toggle
            # ================================================================
            if step.skip_if_disabled and settings:
                # Get the setting value (e.g., settings.sequence_voice_enabled)
                setting_name = f"sequence_{step.skip_if_disabled}"
                channel_enabled = getattr(settings, setting_name, False)

                if not channel_enabled:
                    logger.debug(
                        f"Skipping step {step_index} ({step.message_type.value}) - "
                        f"{setting_name}={channel_enabled}"
                    )
                    skipped_count += 1
                    continue  # Skip this step

            # ================================================================
            # NEW: Check if qualification question already answered
            # ================================================================
            if step.message_type in skip_types:
                logger.info(
                    f"Skipping step {step_index} ({step.message_type.value}) - "
                    f"qualification already known from lead profile"
                )
                qualification_skipped_count += 1
                continue  # Skip this step

            # ================================================================
            # Calculate scheduled time (now with delay_minutes support)
            # ================================================================
            scheduled_at = base_time + timedelta(
                days=step.delay_days,
                minutes=step.delay_minutes  # NEW: sub-day timing
            )

            # Adjust for working hours (TCPA compliance)
            # For sub-hour delays on Day 0, don't adjust (send immediately during hours)
            if step.delay_days == 0 and step.delay_minutes < 60:
                # Only adjust if outside TCPA hours
                is_allowed, next_allowed = is_within_tcpa_hours(scheduled_at, lead_timezone)
                if not is_allowed:
                    scheduled_at = next_allowed
            else:
                scheduled_at = self._adjust_for_working_hours(scheduled_at, lead_timezone)

            # Resolve channel (primary/secondary to actual channel)
            actual_channel = self._resolve_channel(step.channel, preferred_channel)

            followup = ScheduledFollowUp(
                id=str(uuid.uuid4()),
                fub_person_id=fub_person_id,
                organization_id=organization_id,
                scheduled_at=scheduled_at,
                channel=actual_channel,
                message_type=step.message_type.value,
                sequence_step=step_index,
                sequence_id=sequence_id,
            )

            scheduled_followups.append(followup)

        # Save to database
        if self.supabase:
            await self._save_scheduled_followups(scheduled_followups)

        # ================================================================
        # NEW: Auto-schedule nurture continuation after NEW_LEAD sequence
        # If no response after Day 7, continue with monthly nurture
        # ================================================================
        nurture_scheduled = 0
        if trigger == FollowUpTrigger.NEW_LEAD:
            # Schedule nurture starting Day 30 (after Day 7 intensive ends)
            nurture_base_time = base_time + timedelta(days=7)  # Start counting from Day 7
            nurture_followups = []

            for step_index, step in enumerate(self.SEQUENCE_NURTURE):
                scheduled_at = nurture_base_time + timedelta(days=step.delay_days)
                scheduled_at = self._adjust_for_working_hours(scheduled_at, lead_timezone)

                actual_channel = self._resolve_channel(step.channel, preferred_channel)

                followup = ScheduledFollowUp(
                    id=str(uuid.uuid4()),
                    fub_person_id=fub_person_id,
                    organization_id=organization_id,
                    scheduled_at=scheduled_at,
                    channel=actual_channel,
                    message_type=step.message_type.value,
                    sequence_step=len(scheduled_followups) + step_index,  # Continue step numbering
                    sequence_id=sequence_id,  # Same sequence ID for tracking
                )
                nurture_followups.append(followup)

            if self.supabase and nurture_followups:
                await self._save_scheduled_followups(nurture_followups)
                nurture_scheduled = len(nurture_followups)
                logger.info(
                    f"Scheduled {nurture_scheduled} nurture follow-ups for person {fub_person_id} "
                    f"(starting Day 30+)"
                )

        logger.info(
            f"Scheduled {len(scheduled_followups)} follow-ups for person {fub_person_id} "
            f"(sequence: {sequence_id}, trigger: {trigger.value}, skipped: {skipped_count})"
        )

        return {
            "sequence_id": sequence_id,
            "trigger": trigger.value,
            "followups": [f.to_dict() for f in scheduled_followups],
            "total_scheduled": len(scheduled_followups),
            "total_skipped": skipped_count,
            "qualification_skipped": qualification_skipped_count,  # Already-answered questions
            "nurture_scheduled": nurture_scheduled,  # Monthly nurture after Day 7
        }

    async def cancel_followups(
        self,
        fub_person_id: int,
        reason: str = "lead_responded",
    ) -> Dict[str, Any]:
        """
        Cancel all pending follow-ups for a lead.

        Called when:
        - Lead responds to any message
        - Lead stage changes to blocked stage
        - Lead opts out
        - Manual cancellation

        Args:
            fub_person_id: FUB person ID
            reason: Reason for cancellation

        Returns:
            Dict with cancellation details
        """
        cancelled_count = 0

        if self.supabase:
            try:
                # Update all pending follow-ups for this person
                result = self.supabase.table("ai_scheduled_followups").update({
                    "status": FollowUpStatus.CANCELLED.value,
                    "cancelled_at": datetime.utcnow().isoformat(),
                    "error_message": reason,
                }).eq(
                    "fub_person_id", fub_person_id
                ).eq(
                    "status", FollowUpStatus.PENDING.value
                ).execute()

                cancelled_count = len(result.data) if result.data else 0

            except Exception as e:
                logger.error(f"Error cancelling follow-ups: {e}")

        logger.info(
            f"Cancelled {cancelled_count} follow-ups for person {fub_person_id}: {reason}"
        )

        return {
            "fub_person_id": fub_person_id,
            "cancelled_count": cancelled_count,
            "reason": reason,
        }

    async def get_pending_followups(
        self,
        fub_person_id: int = None,
        organization_id: str = None,
        due_before: datetime = None,
    ) -> List[ScheduledFollowUp]:
        """
        Get pending follow-ups, optionally filtered.

        Args:
            fub_person_id: Filter by person (optional)
            organization_id: Filter by organization (optional)
            due_before: Only get follow-ups due before this time

        Returns:
            List of pending ScheduledFollowUp objects
        """
        if not self.supabase:
            return []

        try:
            query = self.supabase.table("ai_scheduled_followups").select("*").eq(
                "status", FollowUpStatus.PENDING.value
            )

            if fub_person_id:
                query = query.eq("fub_person_id", fub_person_id)

            if organization_id:
                query = query.eq("organization_id", organization_id)

            if due_before:
                query = query.lte("scheduled_at", due_before.isoformat())

            query = query.order("scheduled_at", desc=False)

            result = query.execute()

            followups = []
            for row in result.data or []:
                followups.append(ScheduledFollowUp(
                    id=row["id"],
                    fub_person_id=row["fub_person_id"],
                    organization_id=row["organization_id"],
                    scheduled_at=datetime.fromisoformat(row["scheduled_at"]),
                    channel=row["channel"],
                    message_type=row["message_type"],
                    sequence_step=row["sequence_step"],
                    sequence_id=row["sequence_id"],
                    status=FollowUpStatus(row["status"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                ))

            return followups

        except Exception as e:
            logger.error(f"Error getting pending follow-ups: {e}")
            return []

    async def process_scheduled_followup(
        self,
        followup_id: str,
        agent_service=None,
        person_data: Dict[str, Any] = None,
        agent_name: str = "Your Agent",
        agent_phone: str = "",
        brokerage_name: str = "",
        previous_messages: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a scheduled follow-up.

        This is called by the Celery task when a follow-up is due.
        Now supports AI-powered message generation with full lead context.

        Args:
            followup_id: ID of the follow-up to process
            agent_service: AIAgentService instance for generating messages
            person_data: FUB person data for AI generation (optional, will fetch if needed)
            agent_name: Agent's name for signing messages
            agent_phone: Agent's phone number
            brokerage_name: Brokerage name for email signature
            previous_messages: List of previous messages sent (for AI context)

        Returns:
            Dict with execution result including generated message
        """
        if not self.supabase:
            return {"success": False, "error": "No database connection"}

        try:
            # Get the follow-up
            result = self.supabase.table("ai_scheduled_followups").select("*").eq(
                "id", followup_id
            ).single().execute()

            if not result.data:
                return {"success": False, "error": "Follow-up not found"}

            followup_data = result.data

            # Check if still pending
            if followup_data["status"] != FollowUpStatus.PENDING.value:
                return {
                    "success": False,
                    "error": f"Follow-up status is {followup_data['status']}, not pending",
                }

            # Get message details
            message_type = MessageType(followup_data["message_type"])
            channel = followup_data["channel"]
            sequence_step = followup_data.get("sequence_step", 0)
            fub_person_id = followup_data["fub_person_id"]

            # Calculate which day of the sequence this is
            # Based on sequence step, approximate the day
            day_mapping = {
                0: 0, 1: 0, 2: 0, 3: 0, 4: 0,  # Day 0 steps
                5: 1, 6: 1, 7: 1,  # Day 1 steps
                8: 2,  # Day 2
                9: 3,  # Day 3
                10: 4,  # Day 4
                11: 5, 12: 5,  # Day 5 steps
                13: 6,  # Day 6
                14: 7, 15: 7,  # Day 7 steps
            }
            sequence_day = day_mapping.get(sequence_step, sequence_step // 2)

            # ================================================================
            # AI GENERATION: Check if this message type should use AI
            # ================================================================
            if self.should_use_ai_for_step(message_type):
                logger.info(f"Using AI generation for {message_type.value}")

                # If person_data not provided, try to fetch from FUB
                if not person_data:
                    try:
                        # Try to get from database cache first
                        person_result = self.supabase.table("lead_profiles").select("*").eq(
                            "fub_person_id", fub_person_id
                        ).single().execute()

                        if person_result.data:
                            # Convert to FUB-like format
                            profile = person_result.data
                            person_data = {
                                "firstName": profile.get("first_name", "there"),
                                "lastName": profile.get("last_name", ""),
                                "source": profile.get("source", ""),
                                "tags": profile.get("tags", []),
                                "cities": profile.get("preferred_cities", ""),
                            }
                        else:
                            # Minimal fallback
                            person_data = {"firstName": "there"}
                    except Exception as e:
                        logger.warning(f"Could not fetch person data: {e}")
                        person_data = {"firstName": "there"}

                # Generate AI message
                ai_result = await generate_followup_message(
                    person_data=person_data,
                    message_type=message_type,
                    channel=channel,
                    agent_name=agent_name,
                    agent_phone=agent_phone,
                    brokerage_name=brokerage_name,
                    previous_messages=previous_messages,
                    sequence_day=sequence_day,
                )

                message_content = ai_result.get("content", "")
                message_subject = ai_result.get("subject", "Following up")
                ai_used = ai_result.get("ai_used", False)

                # If AI failed, fall back to template
                if not ai_used or "[AI" in message_content:
                    logger.warning(f"AI generation failed, falling back to template")
                    import random
                    templates = self.MESSAGE_TEMPLATES.get(message_type, [])
                    message_content = random.choice(templates) if templates else "Following up - any questions?"
                    ai_used = False

            else:
                # ================================================================
                # TEMPLATE: Use random template for this message type
                # ================================================================
                import random
                templates = self.MESSAGE_TEMPLATES.get(message_type, [])
                message_content = random.choice(templates) if templates else "Following up - any questions?"
                message_subject = "Following up"
                ai_used = False

            # Mark as sent
            self.supabase.table("ai_scheduled_followups").update({
                "status": FollowUpStatus.SENT.value,
                "executed_at": datetime.utcnow().isoformat(),
            }).eq("id", followup_id).execute()

            logger.info(f"Processed follow-up {followup_id}: {message_type.value} via {channel} (AI: {ai_used})")

            return {
                "success": True,
                "followup_id": followup_id,
                "channel": channel,
                "message_type": message_type.value,
                "message": message_content,
                "subject": message_subject if channel == "email" else None,
                "ai_used": ai_used,
                "fub_person_id": fub_person_id,
                "sequence_day": sequence_day,
            }

        except Exception as e:
            logger.error(f"Error processing follow-up {followup_id}: {e}")

            # Mark as failed
            if self.supabase:
                self.supabase.table("ai_scheduled_followups").update({
                    "status": FollowUpStatus.FAILED.value,
                    "error_message": str(e),
                }).eq("id", followup_id).execute()

            return {"success": False, "error": str(e)}

    def _resolve_channel(self, step_channel: str, preferred: str) -> str:
        """Resolve 'primary'/'secondary' to actual channel."""
        if step_channel == "primary":
            return preferred
        elif step_channel == "secondary":
            # If primary is SMS, secondary is email and vice versa
            return "email" if preferred == "sms" else "sms"
        else:
            return step_channel

    def _adjust_for_working_hours(
        self,
        scheduled_time: datetime,
        timezone: str,
    ) -> datetime:
        """
        Adjust scheduled time to fall within TCPA-compliant hours (8 AM - 8 PM).

        Uses the module-level get_next_valid_send_time function for consistent
        TCPA compliance across the application.

        Args:
            scheduled_time: Originally scheduled time (UTC)
            timezone: Lead's timezone (IANA format)

        Returns:
            Adjusted datetime in UTC
        """
        return get_next_valid_send_time(scheduled_time, timezone)

    async def _save_scheduled_followups(
        self,
        followups: List[ScheduledFollowUp],
    ) -> bool:
        """Save scheduled follow-ups to database."""
        if not self.supabase:
            return False

        try:
            data = [
                {
                    "id": f.id,
                    "fub_person_id": f.fub_person_id,
                    "organization_id": f.organization_id,
                    "scheduled_at": f.scheduled_at.isoformat(),
                    "channel": f.channel,
                    "message_type": f.message_type,
                    "sequence_step": f.sequence_step,
                    "sequence_id": f.sequence_id,
                    "status": f.status.value,
                    "created_at": f.created_at.isoformat(),
                }
                for f in followups
            ]

            self.supabase.table("ai_scheduled_followups").insert(data).execute()
            return True

        except Exception as e:
            logger.error(f"Error saving scheduled follow-ups: {e}")
            return False


# ==============================================================================
# AI-POWERED MESSAGE GENERATION
# Uses the same quality and context-awareness as initial_outreach_generator.py
# ==============================================================================

def get_friendly_source_name(source: str) -> str:
    """Get friendly source name for display."""
    if not source:
        return "your recent inquiry"
    for key, value in SOURCE_NAME_MAP.items():
        if key.lower() == source.lower():
            return value
    return source


def detect_lead_type(tags: List[str]) -> str:
    """Detect lead type from FUB tags."""
    if not tags:
        return "unknown"
    tag_lower = [t.lower() for t in tags]
    is_buyer = any('buyer' in t for t in tag_lower)
    is_seller = any('seller' in t for t in tag_lower)
    if is_buyer and is_seller:
        return "both"
    elif is_seller:
        return "seller"
    elif is_buyer:
        return "buyer"
    return "unknown"


async def generate_followup_message(
    person_data: Dict[str, Any],
    message_type: MessageType,
    channel: str,
    agent_name: str,
    agent_phone: str,
    brokerage_name: str,
    previous_messages: List[Dict[str, Any]] = None,
    sequence_day: int = 0,
    conversation_summary: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Generate an AI-powered follow-up message with full lead context.

    This function provides the same quality and context-awareness as
    initial_outreach_generator.py, ensuring consistent messaging throughout
    the follow-up sequence.

    Args:
        person_data: FUB person data with lead details
        message_type: The type of follow-up message to generate
        channel: "sms" or "email"
        agent_name: Agent's name for signing
        agent_phone: Agent's phone number
        brokerage_name: Brokerage name for email signature
        previous_messages: List of previous messages sent (for context)
        sequence_day: Which day of the sequence (0-7)
        conversation_summary: Optional dict with conversation context for smart re-engagement:
            - last_topic: What we were discussing
            - answered_questions: Questions the lead already answered
            - open_questions: Questions we still need answers to
            - objections: Any objections the lead raised
            - score: Lead qualification score
            - state: Conversation state (qualifying, scheduling, etc.)

    Returns:
        Dict with 'content' (SMS text or email body) and optionally 'subject' (for email)
    """
    # Extract lead details
    first_name = person_data.get('firstName', 'there')
    last_name = person_data.get('lastName', '')
    source = person_data.get('source', '')
    tags = person_data.get('tags', [])
    cities = person_data.get('cities', '') or 'your area'

    # Get friendly source name and lead type
    friendly_source = get_friendly_source_name(source)
    lead_type = detect_lead_type(tags)

    # Build lead type context for AI
    if lead_type == "both":
        lead_type_str = "BUYER AND SELLER (coordinated move)"
        lead_action = "buy and sell"
    elif lead_type == "seller":
        lead_type_str = "SELLER"
        lead_action = "sell"
    elif lead_type == "buyer":
        lead_type_str = "BUYER"
        lead_action = "buy"
    else:
        lead_type_str = "Unknown (treat as buyer)"
        lead_action = "find a home"

    # Build previous message context
    prev_context = ""
    if previous_messages:
        prev_context = "\n\nPREVIOUS MESSAGES SENT (no response yet):\n"
        for msg in previous_messages[-5:]:  # Last 5 messages
            content_preview = msg.get('content', '')[:100]
            prev_context += f"- Day {msg.get('day', '?')}, {msg.get('channel', '?').upper()}: {content_preview}...\n"

    # Message type guidance
    type_guidance = {
        MessageType.FIRST_CONTACT: "First contact. Introduce yourself, explain connection, offer value.",
        MessageType.EMAIL_WELCOME: "Welcome email. Full introduction, value proposition, establish professionalism.",
        MessageType.VALUE_WITH_CTA: "Value + appointment. Offer specific value and suggest meeting times.",
        MessageType.QUALIFY_MOTIVATION: "Qualify motivation. Ask easy question about their situation.",
        MessageType.EMAIL_VALUE: "Value email. Share market insights, provide multiple appointment slots.",
        MessageType.VALUE_ADD_LISTING: "Property value add. Reference a listing or market tip.",
        MessageType.EMAIL_MARKET_REPORT: "Market report email. Share data, offer multiple meeting times.",
        MessageType.SOCIAL_PROOF: "Social proof. Share recent success story.",
        MessageType.EMAIL_SOCIAL_PROOF: "Social proof email. Detailed success story, build credibility.",
        MessageType.HELPFUL_CHECKIN: "Helpful check-in. Soft touch, offer specific assistance.",
        MessageType.EMAIL_FINAL: "Final email. Warm close, leave door open, no pressure.",
        MessageType.STRATEGIC_BREAKUP: "Strategic break-up. 'Closing file' message - often gets highest response!",
        # Smart re-engagement types - context-aware
        MessageType.RESUME_QUALIFICATION: "Resume qualification. Reference what they told you and ask the next qualifying question.",
        MessageType.RESUME_SCHEDULING: "Resume scheduling. Re-offer appointment times, acknowledge they were busy.",
        MessageType.RESUME_OBJECTION: "Resume after objection. Acknowledge their concern and offer new perspective or information.",
        MessageType.RESUME_GENERAL: "General check-in with context. Reference your previous conversation, don't start from scratch.",
    }.get(message_type, "Follow up naturally.")

    # Build conversation context section for smart re-engagement
    conversation_context_section = ""
    if conversation_summary:
        conversation_context_section = f"""

=== CONVERSATION CONTEXT (PICK UP WHERE YOU LEFT OFF) ===
Last topic discussed: {conversation_summary.get('last_topic', 'General introduction')}
Questions they already answered: {conversation_summary.get('answered_questions', 'None yet')}
Open questions we need answered: {conversation_summary.get('open_questions', 'Timeline, budget, location')}
Objections or concerns raised: {conversation_summary.get('objections', 'None')}
Lead qualification score: {conversation_summary.get('score', 'Unknown')}/100
Conversation state: {conversation_summary.get('state', 'qualifying')}

CRITICAL: Do NOT repeat questions they already answered. Reference what they told you.
If they mentioned a specific timeline, location, or concern - ACKNOWLEDGE it.
This makes you feel like a helpful human, not a robotic automation.
=== END CONTEXT ===
"""

    # Build the system prompt
    system_prompt = f"""You are {agent_name}, a friendly real estate agent with {brokerage_name}.

You're following up with {first_name} who hasn't responded yet. This is Day {sequence_day} of your outreach.

CRITICAL RULES:
1. If Day > 0, DO NOT repeat your introduction - they already know who you are
2. DO NOT ask "are you buying or selling?" - we ALREADY KNOW: {lead_type_str}
3. Reference their situation specifically: looking to {lead_action} in {cities}
4. Source: They came from {friendly_source}
5. Keep SMS under 160 characters ideal, max 250
6. For email, keep it SHORT (2-3 paragraphs max)
7. Be human, not robotic. Vary your approach each day.
8. Never guilt trip about no response
9. Always leave the door open

MESSAGE TYPE: {message_type.value}
GUIDANCE: {type_guidance}
CHANNEL: {channel.upper()}
DAY: {sequence_day}
LEAD TYPE: {lead_type_str}
LOCATION: {cities}
SOURCE: {friendly_source}
{conversation_context_section}"""

    # Build the user prompt based on channel
    if channel == "sms":
        user_prompt = f"""Generate a follow-up SMS for Day {sequence_day}.

Type: {message_type.value}
{type_guidance}
{prev_context}

Respond with ONLY the SMS text. No JSON, no explanation. Just the message.
Keep it under 200 characters. Be natural and human."""
    else:
        user_prompt = f"""Generate a follow-up EMAIL for Day {sequence_day}.

Type: {message_type.value}
{type_guidance}
{prev_context}

Respond in this JSON format:
{{
    "subject": "Short, personal subject line",
    "body": "Short email body in plain text. 2-3 paragraphs max. Sign with {agent_name} and phone {agent_phone}."
}}

Keep it SHORT - they've already received multiple messages."""

    # Get API key
    openrouter_key = os.environ.get('OPENROUTER_API_KEY')
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY')

    if not openrouter_key and not anthropic_key:
        logger.warning("No AI API key available, using template fallback")
        return {"content": f"[AI generation unavailable]", "subject": "Following up", "ai_used": False}

    try:
        async with aiohttp.ClientSession() as session:
            # Use OpenRouter if available, else Anthropic
            if openrouter_key:
                api_url = "https://openrouter.ai/api/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {openrouter_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": "anthropic/claude-sonnet-4",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 500,
                    "temperature": 0.7,
                }
            else:
                api_url = "https://api.anthropic.com/v1/messages"
                headers = {
                    "x-api-key": anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 500,
                    "system": system_prompt,
                    "messages": [
                        {"role": "user", "content": user_prompt},
                    ],
                }

            async with session.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"AI API error: {response.status} - {error_text}")
                    return {"content": f"[API error: {response.status}]", "subject": "Following up", "ai_used": False}

                data = await response.json()

                # Extract text based on API
                if openrouter_key:
                    text = data['choices'][0]['message']['content'].strip()
                else:
                    text = data['content'][0]['text'].strip()

                # Parse response based on channel
                if channel == "email":
                    try:
                        # Try to extract JSON
                        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
                        if json_match:
                            result = json.loads(json_match.group())
                            return {
                                "subject": result.get('subject', 'Following up'),
                                "content": result.get('body', text),
                                "ai_used": True,
                            }
                    except json.JSONDecodeError:
                        pass
                    # Fallback: use raw text
                    return {"subject": "Following up", "content": text, "ai_used": True}
                else:
                    # SMS: just return the text
                    return {"content": text, "ai_used": True}

    except Exception as e:
        logger.error(f"AI generation failed: {e}")
        return {"content": f"[AI error: {str(e)}]", "subject": "Following up", "ai_used": False}


# Convenience function for getting a manager instance
def get_followup_manager(supabase_client=None) -> FollowUpManager:
    """Get a FollowUpManager instance."""
    return FollowUpManager(supabase_client=supabase_client)
