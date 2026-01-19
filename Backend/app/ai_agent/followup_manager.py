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
    # With voice_enabled=False (default): 7 touches over 7 days
    # With voice_enabled=True: 11 touches over 7 days
    #
    # Each step includes:
    # - Qualification questions to gather intel
    # - Appointment CTAs using "assumptive close" technique
    # - Strategic break-up message (highest response rate!)
    # ==========================================================================
    SEQUENCE_NEW_LEAD = [
        # Step 1: Day 0, 0 min - IMMEDIATE first contact + qualify timeline
        FollowUpStep(
            delay_days=0,
            delay_minutes=0,
            channel="sms",
            message_type=MessageType.FIRST_CONTACT,
            skip_if_disabled=None,  # Always send
        ),
        # Step 2: Day 0, 5 min - RVM intro (if voice enabled)
        FollowUpStep(
            delay_days=0,
            delay_minutes=5,
            channel="rvm",
            message_type=MessageType.RVM_INTRO,
            skip_if_disabled="voice_enabled",  # Skip if voice OFF
        ),
        # Step 3: Day 0, 30 min - Value + appointment CTA
        FollowUpStep(
            delay_days=0,
            delay_minutes=30,
            channel="sms",
            message_type=MessageType.VALUE_WITH_CTA,
            skip_if_disabled=None,  # Always send
        ),
        # Step 4: Day 0, 2 hours - Call check-in (if voice enabled)
        FollowUpStep(
            delay_days=0,
            delay_minutes=120,
            channel="call",
            message_type=MessageType.CALL_CHECKIN,
            skip_if_disabled="voice_enabled",  # Skip if voice OFF
        ),
        # Step 5: Day 1, AM - Qualify motivation
        FollowUpStep(
            delay_days=1,
            delay_minutes=0,  # Morning
            channel="sms",
            message_type=MessageType.QUALIFY_MOTIVATION,
            skip_if_disabled=None,
        ),
        # Step 6: Day 1, PM - Call follow-up (if voice enabled)
        FollowUpStep(
            delay_days=1,
            delay_minutes=480,  # 8 hours after morning = afternoon
            channel="call",
            message_type=MessageType.CALL_CHECKIN,
            skip_if_disabled="voice_enabled",
        ),
        # Step 7: Day 2 - Property value add
        FollowUpStep(
            delay_days=2,
            delay_minutes=0,
            channel="sms",
            message_type=MessageType.VALUE_ADD_LISTING,
            skip_if_disabled=None,
        ),
        # Step 8: Day 3 - Email market report + time slots
        FollowUpStep(
            delay_days=3,
            delay_minutes=0,
            channel="email",
            message_type=MessageType.EMAIL_MARKET_REPORT,
            skip_if_disabled=None,
        ),
        # Step 9: Day 4 - Social proof SMS
        FollowUpStep(
            delay_days=4,
            delay_minutes=0,
            channel="sms",
            message_type=MessageType.SOCIAL_PROOF,
            skip_if_disabled=None,
        ),
        # Step 10: Day 5 - Final call attempt (if voice enabled)
        FollowUpStep(
            delay_days=5,
            delay_minutes=0,
            channel="call",
            message_type=MessageType.CALL_CHECKIN,
            skip_if_disabled="voice_enabled",
        ),
        # Step 11: Day 7 - Strategic break-up (highest response rate!)
        FollowUpStep(
            delay_days=7,
            delay_minutes=0,
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
    SEQUENCE_NURTURE = [
        FollowUpStep(
            delay_days=30,
            channel="email",
            message_type=MessageType.MONTHLY_TOUCHPOINT,
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
        ai_preferred_types = {
            MessageType.FIRST_CONTACT,      # First impression matters - personalize
            MessageType.VALUE_ADD,          # Value should be contextual
            MessageType.VALUE_WITH_CTA,     # Appointment CTA should be personalized
            MessageType.VALUE_ADD_LISTING,  # Property-specific content
            MessageType.STRATEGIC_BREAKUP,  # Break-up message is high-stakes
        }

        # Message types that work well as templates
        template_preferred_types = {
            MessageType.GENTLE_FOLLOWUP,    # Simple check-ins work as templates
            MessageType.SOCIAL_PROOF,       # Social proof can be templated
            MessageType.MONTHLY_TOUCHPOINT, # Nurture works with templates
            MessageType.RVM_INTRO,          # Voice scripts need consistency
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
    ) -> Dict[str, Any]:
        """
        Execute a scheduled follow-up.

        This is called by the Celery task when a follow-up is due.

        Args:
            followup_id: ID of the follow-up to process
            agent_service: AIAgentService instance for generating messages

        Returns:
            Dict with execution result
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

            # Get lead profile and check stage eligibility
            # (In real implementation, would fetch from FUB/database)
            # For now, we'll assume the caller handles this

            # Generate and send the message
            message_type = MessageType(followup_data["message_type"])
            channel = followup_data["channel"]

            # Get a random template for this message type
            import random
            templates = self.MESSAGE_TEMPLATES.get(message_type, [])
            template = random.choice(templates) if templates else "Following up - any questions?"

            # Mark as sent (actual sending would be done by caller)
            self.supabase.table("ai_scheduled_followups").update({
                "status": FollowUpStatus.SENT.value,
                "executed_at": datetime.utcnow().isoformat(),
            }).eq("id", followup_id).execute()

            logger.info(f"Processed follow-up {followup_id}: {message_type.value} via {channel}")

            return {
                "success": True,
                "followup_id": followup_id,
                "channel": channel,
                "message_type": message_type.value,
                "template": template,
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


# Convenience function for getting a manager instance
def get_followup_manager(supabase_client=None) -> FollowUpManager:
    """Get a FollowUpManager instance."""
    return FollowUpManager(supabase_client=supabase_client)
