"""
AI Response Generator - Production-grade LLM integration for conversation responses.

This module provides:
- Robust Claude API integration with retry logic and fallbacks
- Structured output parsing with validation
- Context window management for long conversations
- Token usage tracking and cost monitoring
- Response quality validation
- Comprehensive error handling and recovery

The generator is designed to produce natural, helpful responses that:
- Match the configured personality tone
- Extract qualification information
- Handle objections gracefully
- Know when to hand off to humans
"""

import asyncio
import logging
import json
import os
import time
import re
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)

# Import source name mapping for consistent display across all communications
try:
    from app.ai_agent.initial_outreach_generator import SOURCE_NAME_MAP
except ImportError:
    # Fallback if initial_outreach_generator not available
    SOURCE_NAME_MAP = {
        "ReferralExchange": "Top Agents Ranked",
        "referralexchange": "Top Agents Ranked",
        "Referral Exchange": "Top Agents Ranked",
        "MyAgentFinder.com": "MyAgentFinder",
    }


def get_friendly_source_name(source: str) -> str:
    """Get the friendly display name for a lead source."""
    if not source:
        return ""
    for key, value in SOURCE_NAME_MAP.items():
        if key.lower() == source.lower():
            return value
    return source


# =============================================================================
# INTELLIGENT HANDOFF DETECTION
# =============================================================================
# Two-tier system:
# 1. FAST PATH: Obvious keyword triggers (immediate handoff)
# 2. AI SCORING: For messages that FEEL like a hot lead even without exact keywords
#
# The AI scoring catches things like:
# - "I'm ready to move forward"
# - "Let's do this!"
# - "Found one I absolutely love"
# - "We need to act fast on this"
# - "This is the one"
#
# Philosophy: If the lead FEELS hot, hand off. Don't wait for magic words.

# Fast-path keyword patterns (obvious triggers - no AI needed)
HANDOFF_KEYWORDS = {
    # =========================================================================
    # BUYER TRIGGERS
    # =========================================================================
    # Scheduling intent - buyer wants to see a property
    "schedule_showing": [
        r"schedule.*showing", r"set up a showing", r"book a showing",
        r"schedule a tour", r"when can (i|we) see",
        # Broader showing/touring intent
        r"(want|like|love|ready) to (see|tour|visit|look at|view) (homes?|houses?|properties|places|listings?|it|them)",
        r"show me (some|a few|the|these|those)?\s*(homes?|houses?|properties|places|listings?)",
        r"can (i|we|you) (show|see|tour|visit|view) (some|a few|the|these|those)?\s*(homes?|houses?|properties|places|it|them)",
        r"let'?s (go see|look at|tour|visit|check out) (some|a few)?\s*(homes?|houses?|properties|places)?",
        r"(see|tour|view|visit) (some|a few|the|these|those) (homes?|houses?|properties|places|listings?)",
        r"when (are you|can we|could we) (available|free) to (show|see|tour)",
        r"take me to see",
        r"(go|come) (see|look at|tour) (it|them|the home|the house|the property)",
    ],
    # Explicit offer intent - buyer ready to make an offer
    "price_negotiation": [
        r"make an offer", r"submit an offer", r"ready to offer", r"want to (bid|offer)",
    ],

    # =========================================================================
    # SELLER TRIGGERS
    # =========================================================================
    # Listing intent - seller wants to list their home
    "ready_to_list": [
        r"(ready to|want to|need to) (list|sell)",
        r"list my (home|house|property|place)",
        r"put.*(home|house|property) on (the )?market",
        r"when can (we|i|you) list",
        r"start the listing process",
    ],
    # Valuation request - seller wants to know home value
    "home_valuation": [
        r"what('s| is) my (home|house|property) worth",
        r"home (value|valuation|appraisal)",
        r"how much (is|can|could) my (home|house|property)",
        r"(get|want|need) a (cma|comparative market analysis)",
        r"what (can|could|would) (i|we) (get|sell|list) for",
    ],

    # =========================================================================
    # GENERAL TRIGGERS
    # =========================================================================
    # Explicit call request
    "wants_call": [
        r"call me", r"give me a call", r"can you call", r"please call",
    ],
    # Appointment agreement - lead confirmed a time/date for showing or meeting
    "appointment_agreed": [
        r"(saturday|sunday|monday|tuesday|wednesday|thursday|friday) (works|is good|at \d|morning|afternoon|evening)",
        r"(i'?m|we'?re|i am) free (at|on|this|next)",
        r"(sounds good|perfect|great|yes|yeah|yep|sure).*(saturday|sunday|monday|tuesday|wednesday|thursday|friday|tomorrow|weekend|10|11|noon|1|2|3|4)",
        r"let'?s do (it|that|saturday|sunday|tomorrow)",
        r"(book|confirm|lock) (it|that|me) in",
        r"(i|we) can (do|make) (that|it|\d)",
        r"see you (then|there|saturday|sunday|tomorrow|at \d)",
    ],
}

# Signals that indicate a HOT lead (used by AI scoring)
HOT_LEAD_SIGNALS = """
STRONG BUYING SIGNALS (any of these = likely hot lead):
- Ready to move forward / take action / get started
- "Let's do this" / "I'm in" / "Count me in"
- Found a property they love / excited about a listing
- Timeline urgency (need to move soon, lease ending, relocating)
- Asking about next steps / process / what's involved
- Mentioning pre-approval, down payment, or financing readiness
- Wanting to see multiple properties / serious about touring
- Comparing specific properties / narrowing down choices
- Spouse/partner agreement ("we both love it", "my husband agrees")
- Life event driving urgency (new job, baby, divorce, death)
- Frustration with searching / ready to stop looking
- Specific address or MLS number mentioned with interest
- "This is the one" / "Perfect for us" / strong enthusiasm
- Asking about availability / move-in dates
- Discussing contingencies, inspections, or offer terms

STRONG SELLING SIGNALS (any of these = likely hot seller):
- Ready to list / put home on market
- Asking about home value / what they can get
- Asking about listing process / how it works
- Already started packing / preparing to move
- Mentioning they've found their next home
- Job relocation / transfer driving timeline
- Life event (divorce, death, estate, downsizing)
- Asking about staging, repairs, or prep work
- Discussing timing of sale vs purchase
- Comparing agent commission / services
- Asking about marketing plan / how you'll sell it
- "Ready to get this done" / "Need to move fast"
- Mentioning they've been thinking about selling
- Asking about market conditions for sellers
- Questions about net proceeds / what they'll walk away with

MODERATE SIGNALS (consider handoff if multiple present):
- Increased response frequency / engagement
- Longer, more detailed messages
- Asking about specific neighborhoods or schools (buyer)
- Budget/price discussions getting specific
- Mentioning they've been pre-approved (buyer)
- Referencing other agents they're talking to
- Emotional language about their search/sale
- Asking about timeline / how long things take
- Questions about the process
"""

# Acknowledgment messages for each handoff type
HANDOFF_ACKNOWLEDGMENTS = {
    # Buyer triggers
    "schedule_showing": "I'd love to get you in to see that property! Let me connect you with {agent_name} to find a time that works for you. They'll reach out shortly!",
    "price_negotiation": "This is exciting! Making an offer is a big step. Let me get {agent_name} involved - they're the expert on negotiations.",

    # Seller triggers
    "ready_to_list": "That's exciting - sounds like you're ready to get your home on the market! Let me connect you with {agent_name} who can walk you through the listing process. They'll reach out shortly!",
    "home_valuation": "Great question! {agent_name} can provide a detailed analysis of your home's value based on recent sales in your area. They'll reach out to set up a time to discuss.",

    # General triggers
    "wants_call": "Absolutely, a call is a great idea! I'll have {agent_name} give you a call. What's the best time to reach you?",
    "urgent_timeline": "I understand time is of the essence! Let me get {agent_name} on this right away - they'll reach out within the hour.",
    "complex_question": "Great question! That's something {agent_name} can explain better than I can. Let me connect you with them.",

    # Appointment agreement
    "appointment_agreed": "Awesome, I'll have {agent_name} confirm the details and follow up with you shortly!",

    # AI-detected hot leads
    "hot_lead": "This is exciting - sounds like you're ready to take the next step! Let me get {agent_name} involved so we can make this happen. They'll reach out shortly!",
    "high_intent": "I can tell you're serious about this - that's great! Let me connect you with {agent_name} who can give you their full attention. They'll be in touch soon!",
    "hot_seller": "Sounds like you're ready to make a move! Let me get {agent_name} involved to discuss your options. They'll reach out shortly!",
}


def detect_handoff_triggers(message: str, use_ai_scoring: bool = True) -> Optional[str]:
    """
    Intelligent handoff detection using two-tier system:
    1. FAST PATH: Check for obvious keyword triggers
    2. AI SCORING: Assess "hot lead" signals even without exact keywords

    The AI scoring catches leads who are ready but don't use magic words like
    "schedule showing". Instead they might say "I'm ready!" or "Let's do this!"

    Args:
        message: The lead's message text
        use_ai_scoring: Whether to use AI for hot lead detection (default True)

    Returns:
        Trigger type (str) if detected, None otherwise
    """
    if not message:
        return None

    message_lower = message.lower()

    # =========================================================================
    # TIER 1: Fast-path keyword detection (no AI needed)
    # =========================================================================
    for trigger_type, patterns in HANDOFF_KEYWORDS.items():
        for pattern in patterns:
            if re.search(pattern, message_lower):
                logger.info(f"[HANDOFF] Fast-path trigger: {trigger_type} (pattern: {pattern})")
                return trigger_type

    # =========================================================================
    # TIER 2: AI-based hot lead scoring
    # =========================================================================
    if use_ai_scoring and len(message) > 20:  # Only score meaningful messages
        score = score_hot_lead_signals(message)
        if score >= 70:
            logger.info(f"[HANDOFF] AI scored HOT LEAD: {score}/100 - triggering handoff")
            return "hot_lead"
        elif score >= 50:
            logger.info(f"[HANDOFF] AI scored HIGH INTENT: {score}/100 - triggering handoff")
            return "high_intent"
        elif score >= 30:
            logger.info(f"[HANDOFF] AI scored moderate intent: {score}/100 - no handoff yet")

    return None


def score_hot_lead_signals(message: str) -> int:
    """
    Use AI to score a message for "hot lead" buying signals.

    Instead of looking for exact keywords, this analyzes the INTENT and
    SENTIMENT of the message to determine if the lead is ready to act.

    Args:
        message: The lead's message text

    Returns:
        Score from 0-100 where:
        - 70+: Hot lead - definitely hand off
        - 50-69: High intent - hand off
        - 30-49: Moderate interest - keep nurturing
        - <30: Low intent - continue automation
    """
    import aiohttp
    import asyncio

    # Quick heuristic checks first (avoid API call for obvious cases)
    quick_score = _quick_intent_score(message)
    if quick_score >= 70:
        return quick_score

    # For borderline cases, use AI scoring
    try:
        # Run async scoring in sync context if needed
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're already in async context - can't nest
            # Fall back to heuristic scoring
            return quick_score
        else:
            return loop.run_until_complete(_ai_score_message(message))
    except RuntimeError:
        # No event loop - create one
        return asyncio.run(_ai_score_message(message))
    except Exception as e:
        logger.warning(f"AI scoring failed, using heuristic: {e}")
        return quick_score


def _quick_intent_score(message: str) -> int:
    """
    Quick heuristic scoring for obvious hot lead signals.
    Avoids API calls for clear cases.
    """
    score = 0
    msg_lower = message.lower()

    # Strong signals (+25 each) - BUYER signals
    strong_signals = [
        r"ready to (move forward|get started|buy|make an offer|act)",
        r"let'?s do (this|it)",
        r"(this|that) is the one",
        r"we (love|found|want) (it|this|that one)",
        r"(perfect|ideal|exactly what) (we|i) (want|need|looking for)",
        r"(my|our) (husband|wife|spouse|partner) (agrees|loves|wants)",
        r"(need|have) to (move|act|decide) (fast|quickly|soon|now)",
        r"what('s| are) the next step",
        r"how (do|can) (we|i) (proceed|move forward|make this happen)",
        r"(when|how soon) can (we|i) (close|move in|get started)",
        r"(i'?m|we'?re) (pre-?approved|ready|serious)",
        r"(found|saw|love) (a|the|this) (house|home|property|place)",
        r"(can'?t|don'?t want to) (wait|lose|miss) (this|it)",
        # Strong signals - SELLER signals
        r"(ready to|want to|need to) (list|sell)",
        r"(put|get) .*(home|house|property) on (the )?market",
        r"(when|how soon) can (we|i|you) list",
        r"(found|buying|closing on) (a|our|my) (new|next) (home|house|place)",
        r"(already|started) (packing|moving|preparing)",
        r"(job|work) (relocation|transfer|moving)",
        r"(need|have) to sell (fast|quickly|asap|immediately)",
        r"(got|received|have) (a|an) (offer|transfer|new job)",
    ]

    for pattern in strong_signals:
        if re.search(pattern, msg_lower):
            score += 25
            if score >= 70:
                return min(score, 100)

    # Moderate signals (+15 each) - BUYER signals
    moderate_signals = [
        r"(very|really|super) (interested|excited|serious)",
        r"(want|need|looking) to (see|tour|visit)",
        r"(when|what time|how about) (can we|saturday|sunday|this week|next week)",
        r"(new job|relocating|moving for work|transferred)",
        r"(lease|rental|apartment) (ends|ending|expires|up)",
        r"(expecting|having) a baby",
        r"(getting|recently) (married|divorced)",
        r"(down payment|financing|mortgage|loan) (ready|approved|in place)",
        r"(comparing|deciding between|narrowed down)",
        r"(specific|particular) (house|property|address|listing)",
        # Moderate signals - SELLER signals
        r"what('s| is) my (home|house|property) worth",
        r"(cma|comparative market analysis)",
        r"(listing|selling) process",
        r"how (do|should) (i|we) (prepare|get ready) to (sell|list)",
        r"(thinking about|considering) (selling|listing)",
        r"(staging|repairs|updates) (before|to) (sell|list)",
        r"(divorce|estate|downsizing|upsizing)",
        r"(how long|how much time) to sell",
        r"(what|how much) (can|could|would) (i|we) (get|sell|list) for",
    ]

    for pattern in moderate_signals:
        if re.search(pattern, msg_lower):
            score += 15

    # Weak signals (+5 each)
    weak_signals = [
        r"interested",
        r"like (this|that|it)",
        r"looks (good|nice|great)",
        r"(tell|send) me more",
        r"(any|what) availability",
    ]

    for pattern in weak_signals:
        if re.search(pattern, msg_lower):
            score += 5

    # Message length bonus (engaged leads write more)
    if len(message) > 200:
        score += 10
    elif len(message) > 100:
        score += 5

    # Exclamation marks indicate enthusiasm
    exclamations = message.count('!')
    if exclamations >= 3:
        score += 15
    elif exclamations >= 1:
        score += 5

    return min(score, 100)


async def _ai_score_message(message: str) -> int:
    """
    Use AI to score message for buying intent.
    Only called for borderline cases where heuristics aren't enough.
    """
    import aiohttp

    openrouter_key = os.environ.get('OPENROUTER_API_KEY')
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY')

    if not openrouter_key and not anthropic_key:
        return _quick_intent_score(message)

    prompt = f"""Score this real estate lead message for buying/selling readiness on a scale of 0-100.

MESSAGE: "{message}"

SCORING GUIDE:
{HOT_LEAD_SIGNALS}

Respond with ONLY a number 0-100. Nothing else.
- 70-100: Hot lead - ready to act NOW
- 50-69: High intent - very interested, close to ready
- 30-49: Moderate interest - engaged but not urgent
- 0-29: Low intent - just browsing or early stage"""

    try:
        async with aiohttp.ClientSession() as session:
            if openrouter_key:
                headers = {
                    "Authorization": f"Bearer {openrouter_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": "anthropic/claude-3-5-haiku-20241022",  # Fast, cheap model for scoring
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 10,
                    "temperature": 0,
                }
                url = "https://openrouter.ai/api/v1/chat/completions"
            else:
                headers = {
                    "x-api-key": anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": "claude-3-5-haiku-20241022",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 10,
                }
                url = "https://api.anthropic.com/v1/messages"

            async with session.post(
                url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5),  # Quick timeout
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if openrouter_key:
                        text = data['choices'][0]['message']['content'].strip()
                    else:
                        text = data['content'][0]['text'].strip()

                    # Extract number from response
                    match = re.search(r'\d+', text)
                    if match:
                        return min(int(match.group()), 100)

    except Exception as e:
        logger.warning(f"AI scoring request failed: {e}")

    return _quick_intent_score(message)


def get_handoff_acknowledgment(trigger_type: str, agent_name: str = "your agent") -> str:
    """
    Get an appropriate acknowledgment message for a handoff trigger.

    Args:
        trigger_type: Type of handoff trigger detected
        agent_name: Name of the agent to connect with

    Returns:
        Acknowledgment message string
    """
    template = HANDOFF_ACKNOWLEDGMENTS.get(
        trigger_type,
        "Let me connect you with {agent_name} who can help you with that!"
    )
    return template.format(agent_name=agent_name)


class ResponseQuality(Enum):
    """Quality assessment of generated response."""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    FAILED = "failed"


@dataclass
class GeneratedResponse:
    """Structured response from AI generation."""
    response_text: str
    next_state: str
    extracted_info: Dict[str, Any] = field(default_factory=dict)
    lead_score_delta: int = 0
    should_handoff: bool = False
    handoff_reason: Optional[str] = None
    detected_intent: Optional[str] = None
    detected_sentiment: Optional[str] = None
    confidence: float = 0.0
    tokens_used: int = 0
    response_time_ms: int = 0
    model_used: str = ""
    quality: ResponseQuality = ResponseQuality.GOOD
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "response": self.response_text,
            "next_state": self.next_state,
            "extracted_info": self.extracted_info,
            "lead_score_delta": self.lead_score_delta,
            "should_handoff": self.should_handoff,
            "handoff_reason": self.handoff_reason,
            "intent": self.detected_intent,
            "sentiment": self.detected_sentiment,
            "confidence": self.confidence,
            "tokens_used": self.tokens_used,
            "response_time_ms": self.response_time_ms,
            "model_used": self.model_used,
            "quality": self.quality.value,
            "warnings": self.warnings,
        }


@dataclass
class ToolResponse:
    """Response from Claude tool use - indicates which action to take."""
    action: str  # send_sms, send_email, create_task, schedule_showing, add_note, web_search, no_action
    parameters: Dict[str, Any] = field(default_factory=dict)
    reasoning: Optional[str] = None
    tokens_used: int = 0
    response_time_ms: int = 0
    model_used: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "parameters": self.parameters,
            "reasoning": self.reasoning,
            "tokens_used": self.tokens_used,
            "response_time_ms": self.response_time_ms,
            "model_used": self.model_used,
        }


@dataclass
class ConversationMessage:
    """A single message in conversation history."""
    role: str  # "lead" or "agent"
    content: str
    timestamp: datetime
    channel: str = "sms"


@dataclass
class LeadProfile:
    """
    Comprehensive lead profile for AI context.

    This provides the LLM with rich context about who they're talking to,
    enabling more personalized, relevant conversations.
    """
    # Basic identification
    first_name: str = ""
    last_name: str = ""
    full_name: str = ""
    email: str = ""
    phone: str = ""

    # Lead scoring and status
    score: int = 0
    score_label: str = "Cold"  # Hot, Warm, Cold
    stage: str = ""  # FUB stage
    stage_name: str = ""
    assigned_agent: str = ""
    lead_type: str = ""  # "seller", "buyer", "both", or ""

    # Source and attribution
    source: str = ""  # Where lead came from
    source_url: str = ""  # Specific page/listing they came from
    medium: str = ""  # organic, paid, referral, etc.
    campaign: str = ""  # Marketing campaign if any
    original_source: str = ""  # First ever source

    # Property interests
    interested_property_address: str = ""
    interested_property_price: Optional[int] = None
    interested_property_type: str = ""
    interested_property_url: str = ""
    search_criteria: Dict[str, Any] = field(default_factory=dict)
    viewed_properties: List[str] = field(default_factory=list)
    favorited_properties: List[str] = field(default_factory=list)

    # Location preferences
    preferred_cities: List[str] = field(default_factory=list)
    preferred_neighborhoods: List[str] = field(default_factory=list)
    preferred_zip_codes: List[str] = field(default_factory=list)

    # Financial profile
    price_min: Optional[int] = None
    price_max: Optional[int] = None
    is_pre_approved: Optional[bool] = None
    pre_approval_amount: Optional[int] = None
    lender_name: str = ""
    down_payment_ready: Optional[bool] = None

    # Timeline and motivation
    timeline: str = ""
    timeline_detail: str = ""
    motivation: str = ""
    motivation_detail: str = ""
    move_reason: str = ""  # Why they're moving

    # Current situation
    current_home_status: str = ""  # renting, own-must-sell, own-can-buy
    current_address: str = ""
    lease_end_date: str = ""
    needs_to_sell: Optional[bool] = None

    # Property requirements
    property_types: List[str] = field(default_factory=list)
    bedrooms_min: Optional[int] = None
    bedrooms_max: Optional[int] = None
    bathrooms_min: Optional[float] = None
    square_feet_min: Optional[int] = None
    lot_size_min: Optional[int] = None
    year_built_min: Optional[int] = None
    must_have_features: List[str] = field(default_factory=list)
    nice_to_have_features: List[str] = field(default_factory=list)
    deal_breakers: List[str] = field(default_factory=list)

    # Engagement history
    total_messages_sent: int = 0
    total_messages_received: int = 0
    total_calls: int = 0
    total_emails: int = 0
    last_contact_date: str = ""
    last_contact_type: str = ""
    average_response_time_hours: Optional[float] = None
    engagement_level: str = ""  # high, medium, low, none

    # Key events
    has_toured_property: bool = False
    tour_dates: List[str] = field(default_factory=list)
    has_made_offer: bool = False
    attended_open_house: bool = False
    open_house_dates: List[str] = field(default_factory=list)
    scheduled_appointments: List[str] = field(default_factory=list)

    # Tags and notes
    tags: List[str] = field(default_factory=list)
    important_notes: List[str] = field(default_factory=list)
    agent_notes_summary: str = ""
    call_summaries: List[str] = field(default_factory=list)  # Summaries from phone calls

    # Objection history
    previous_objections: List[str] = field(default_factory=list)
    objection_count: int = 0

    # Communication preferences
    preferred_contact_method: str = ""  # text, call, email
    best_time_to_contact: str = ""
    do_not_call: bool = False
    do_not_text: bool = False
    do_not_email: bool = False
    timezone: str = ""
    language_preference: str = "en"

    # Household information
    decision_makers: str = ""  # "just me", "me and spouse", etc.
    household_size: Optional[int] = None
    has_children: Optional[bool] = None
    has_pets: Optional[bool] = None
    pet_types: List[str] = field(default_factory=list)

    # Metadata
    created_date: str = ""
    days_since_created: int = 0
    fub_person_id: Optional[int] = None
    custom_fields: Dict[str, Any] = field(default_factory=dict)

    # Property inquiry info (from FUB events - how lead came in)
    property_inquiry_source: str = ""  # e.g., "MyAgentFinder.com"
    property_inquiry_description: str = ""  # e.g., "Primary Zip: 80521 | Time Frame: 0 - 3 Months"
    property_inquiry_location: str = ""  # Specific location mentioned
    property_inquiry_budget: str = ""  # Budget from inquiry
    property_inquiry_timeline: str = ""  # Timeline from inquiry
    property_inquiry_financing: str = ""  # Financing status from inquiry

    # Conversation history - ACTUAL messages that were delivered
    actual_messages_sent: List[Dict[str, Any]] = field(default_factory=list)
    actual_messages_received: List[Dict[str, Any]] = field(default_factory=list)
    has_received_any_messages: bool = False  # True if lead received any actual SMS/email

    # Planned messages (KTS notes that were NOT actually sent)
    planned_messages_not_sent: List[Dict[str, Any]] = field(default_factory=list)

    # First contact flag
    is_first_contact: bool = True  # True if no actual outreach has happened yet

    def to_context_string(self) -> str:
        """
        Convert profile to a detailed context string for the LLM.

        This is the key method that creates rich, readable context.
        NOTE: We intentionally exclude email and phone to avoid triggering
        model PII filters. The AI doesn't need these to have a conversation.
        """
        sections = []

        # === IDENTITY SECTION ===
        # NOTE: We only include name, not email/phone to avoid PII filtering by the model
        identity_parts = [f"Name: {self.full_name or self.first_name or 'Unknown'}"]
        # Email and phone are intentionally excluded - they can trigger model PII filters
        # if self.email:
        #     identity_parts.append(f"Email: {self.email}")
        # if self.phone:
        #     identity_parts.append(f"Phone: {self.phone}")
        sections.append("LEAD IDENTITY:\n" + "\n".join(f"  - {p}" for p in identity_parts))

        # === SCORE & STATUS SECTION ===
        status_parts = [
            f"Score: {self.score}/100 ({self.score_label} lead)",
        ]
        if self.lead_type:
            status_parts.append(f"Lead Type: {self.lead_type.upper()}")
        if self.stage_name:
            status_parts.append(f"Stage: {self.stage_name}")
        if self.assigned_agent:
            status_parts.append(f"Assigned to: {self.assigned_agent}")
        if self.tags:
            status_parts.append(f"Tags: {', '.join(self.tags[:5])}")
        sections.append("STATUS:\n" + "\n".join(f"  - {p}" for p in status_parts))

        # === SOURCE SECTION ===
        if self.source or self.source_url:
            source_parts = []
            if self.source:
                # Use friendly display name for source
                friendly_source = get_friendly_source_name(self.source)
                source_parts.append(f"Source: {friendly_source}")
            if self.source_url:
                # Extract key info from URL
                source_parts.append(f"Came from: {self.source_url[:100]}")
            if self.campaign:
                source_parts.append(f"Campaign: {self.campaign}")
            if self.interested_property_address:
                source_parts.append(f"Interested in: {self.interested_property_address}")
                if self.interested_property_price:
                    source_parts.append(f"Property price: ${self.interested_property_price:,}")
            sections.append("WHERE THEY CAME FROM:\n" + "\n".join(f"  - {p}" for p in source_parts))

        # === PROPERTY SEARCH SECTION ===
        search_parts = []
        if self.price_min or self.price_max:
            if self.price_min and self.price_max:
                search_parts.append(f"Budget: ${self.price_min:,} - ${self.price_max:,}")
            elif self.price_max:
                search_parts.append(f"Budget: Up to ${self.price_max:,}")
            elif self.price_min:
                search_parts.append(f"Budget: ${self.price_min:,}+")
        if self.is_pre_approved is not None:
            if self.is_pre_approved:
                amt = f" for ${self.pre_approval_amount:,}" if self.pre_approval_amount else ""
                search_parts.append(f"Pre-approved: Yes{amt}")
            else:
                search_parts.append("Pre-approved: No (already asked - do not ask again)")
        if self.preferred_cities or self.preferred_neighborhoods:
            locations = self.preferred_neighborhoods or self.preferred_cities
            search_parts.append(f"Preferred areas: {', '.join(locations[:3])}")
        if self.property_types:
            search_parts.append(f"Property types: {', '.join(self.property_types)}")
        if self.bedrooms_min:
            search_parts.append(f"Min bedrooms: {self.bedrooms_min}+")
        if self.must_have_features:
            search_parts.append(f"Must-haves: {', '.join(self.must_have_features[:3])}")
        if self.deal_breakers:
            search_parts.append(f"Deal-breakers: {', '.join(self.deal_breakers[:3])}")
        if search_parts:
            sections.append("PROPERTY SEARCH:\n" + "\n".join(f"  - {p}" for p in search_parts))

        # === TIMELINE & MOTIVATION SECTION ===
        timeline_parts = []
        if self.timeline:
            timeline_labels = {
                "immediate": "Ready NOW - very urgent",
                "short": "1-3 months - active buyer",
                "medium": "3-6 months - planning ahead",
                "long": "6+ months - early stages",
                "unknown": "Timeline unclear - needs discovery"
            }
            timeline_parts.append(f"Timeline: {timeline_labels.get(self.timeline, self.timeline)}")
        if self.timeline_detail:
            timeline_parts.append(f"Details: {self.timeline_detail}")
        if self.motivation:
            timeline_parts.append(f"Motivation: {self.motivation}")
        if self.move_reason:
            timeline_parts.append(f"Reason for moving: {self.move_reason}")
        if self.needs_to_sell:
            timeline_parts.append("Has home to sell first: Yes")
        if self.lease_end_date:
            timeline_parts.append(f"Lease ends: {self.lease_end_date}")
        if timeline_parts:
            sections.append("TIMELINE & MOTIVATION:\n" + "\n".join(f"  - {p}" for p in timeline_parts))

        # === LEAD FRESHNESS (critical for tone) ===
        if self.days_since_created is not None and self.days_since_created <= 1:
            sections.append("""*** BRAND NEW LEAD (just came in today!) ***
- This lead JUST signed up - they're expecting quick contact
- Be warm and reference how you got their info (the source)
- If someone else on your team already called/emailed, mention you're following up""")
        elif self.days_since_created is not None and self.days_since_created <= 7:
            sections.append(f"RECENT LEAD: Came in {self.days_since_created} days ago - still fresh")

        # === CONTACT HISTORY (what's already happened) ===
        contact_parts = []
        if self.total_calls and self.total_calls > 0:
            contact_parts.append(f"Calls made: {self.total_calls} (someone already tried calling!)")
        if self.total_emails and self.total_emails > 0:
            contact_parts.append(f"Emails sent: {self.total_emails}")
        if self.total_messages_sent and self.total_messages_sent > 0:
            contact_parts.append(f"Texts sent: {self.total_messages_sent}")
        if self.total_messages_received and self.total_messages_received > 0:
            contact_parts.append(f"Texts received: {self.total_messages_received}")
        if not contact_parts and self.is_first_contact:
            contact_parts.append("NO CONTACT YET - this is the first outreach!")
        if contact_parts:
            sections.append("CONTACT HISTORY:\n" + "\n".join(f"  - {p}" for p in contact_parts))

        # === CALL SUMMARIES (what was discussed on calls) ===
        if self.call_summaries:
            sections.append("CALL SUMMARIES (what was discussed):\n" + "\n".join(f"  - {s}" for s in self.call_summaries[:3]))

        # === ENGAGEMENT HISTORY SECTION ===
        engagement_parts = []
        if self.last_contact_date:
            engagement_parts.append(f"Last contact: {self.last_contact_date} via {self.last_contact_type or 'unknown'}")
        if self.engagement_level:
            engagement_parts.append(f"Engagement level: {self.engagement_level}")
        if self.has_toured_property:
            engagement_parts.append("Has toured properties: Yes")
        if self.has_made_offer:
            engagement_parts.append("Has made offer: Yes (serious buyer!)")
        if self.scheduled_appointments:
            engagement_parts.append(f"Upcoming appointments: {', '.join(self.scheduled_appointments[:2])}")
        if self.days_since_created and self.days_since_created > 7:
            engagement_parts.append(f"Lead age: {self.days_since_created} days")
        if engagement_parts:
            sections.append("ENGAGEMENT:\n" + "\n".join(f"  - {p}" for p in engagement_parts))

        # === PROPERTY INQUIRY DETAILS (from referral source) ===
        if self.property_inquiry_source or self.property_inquiry_description:
            inquiry_parts = []
            if self.property_inquiry_source:
                inquiry_parts.append(f"Referral source: {self.property_inquiry_source}")
            if self.property_inquiry_location:
                inquiry_parts.append(f"Looking in: {self.property_inquiry_location}")
            if self.property_inquiry_budget:
                inquiry_parts.append(f"Budget: {self.property_inquiry_budget}")
            if self.property_inquiry_timeline:
                inquiry_parts.append(f"Timeline: {self.property_inquiry_timeline}")
            if self.property_inquiry_financing:
                inquiry_parts.append(f"Financing: {self.property_inquiry_financing}")
            if self.property_inquiry_description and not (self.property_inquiry_timeline or self.property_inquiry_financing):
                # Only show raw description if we didn't parse specific fields
                inquiry_parts.append(f"Details: {self.property_inquiry_description}")
            if inquiry_parts:
                sections.append("REFERRAL INQUIRY DETAILS:\n" + "\n".join(f"  - {p}" for p in inquiry_parts))

        # === COMMUNICATION STATUS ===
        comm_status_parts = []
        if self.is_first_contact:
            comm_status_parts.append("FIRST CONTACT - No texts or calls have been sent to this lead yet!")
        if self.planned_messages_not_sent:
            comm_status_parts.append(f"Note: {len(self.planned_messages_not_sent)} planned messages were NEVER actually sent (system issue)")
            # Show what was planned so AI can reference it or use similar approach
            for i, msg in enumerate(self.planned_messages_not_sent[:2]):
                body = msg.get("body", "")[:100]
                comm_status_parts.append(f"  Planned msg {i+1}: \"{body}...\"")
        if self.actual_messages_sent:
            comm_status_parts.append(f"Actual texts sent: {len(self.actual_messages_sent)}")
        if self.actual_messages_received:
            comm_status_parts.append(f"Texts received from lead: {len(self.actual_messages_received)}")
        if comm_status_parts:
            sections.append("COMMUNICATION STATUS:\n" + "\n".join(f"  - {p}" for p in comm_status_parts))

        # === OBJECTIONS & CONCERNS ===
        if self.previous_objections:
            objection_str = ", ".join(self.previous_objections[:3])
            sections.append(f"PREVIOUS OBJECTIONS:\n  - {objection_str}\n  (Be mindful of these concerns!)")

        # === HOUSEHOLD INFO ===
        household_parts = []
        if self.decision_makers:
            household_parts.append(f"Decision makers: {self.decision_makers}")
        if self.has_children:
            household_parts.append("Has children: Yes (schools may be important)")
        if self.has_pets and self.pet_types:
            household_parts.append(f"Pets: {', '.join(self.pet_types)} (yard/space may matter)")
        elif self.has_pets:
            household_parts.append("Has pets: Yes")
        if household_parts:
            sections.append("HOUSEHOLD:\n" + "\n".join(f"  - {p}" for p in household_parts))

        # === COMMUNICATION PREFERENCES ===
        comm_parts = []
        if self.preferred_contact_method:
            comm_parts.append(f"Prefers: {self.preferred_contact_method}")
        if self.best_time_to_contact:
            comm_parts.append(f"Best time: {self.best_time_to_contact}")
        if self.timezone:
            comm_parts.append(f"Timezone: {self.timezone}")
        if comm_parts:
            sections.append("COMMUNICATION PREFS:\n" + "\n".join(f"  - {p}" for p in comm_parts))

        # === IMPORTANT NOTES ===
        if self.important_notes or self.agent_notes_summary:
            notes_content = self.agent_notes_summary or "\n".join(self.important_notes[:3])
            sections.append(f"IMPORTANT NOTES:\n  {notes_content}")

        return "\n\n".join(sections)

    @classmethod
    def from_fub_data(cls, fub_person: Dict[str, Any], additional_data: Dict[str, Any] = None) -> "LeadProfile":
        """
        Create LeadProfile from Follow Up Boss person data.

        This maps FUB's data structure to our rich profile format.
        """
        additional = additional_data or {}

        # Extract names
        first_name = fub_person.get("firstName", "")
        last_name = fub_person.get("lastName", "")
        full_name = f"{first_name} {last_name}".strip()

        # Get primary email and phone
        emails = fub_person.get("emails", [])
        phones = fub_person.get("phones", [])
        primary_email = emails[0].get("value", "") if emails else ""
        primary_phone = phones[0].get("value", "") if phones else ""

        # Extract addresses
        addresses = fub_person.get("addresses", [])
        current_address = ""
        if addresses:
            addr = addresses[0]
            current_address = f"{addr.get('street', '')}, {addr.get('city', '')} {addr.get('state', '')}".strip(", ")

        # Score calculation
        score = additional.get("lead_score", 0)
        if score >= 70:
            score_label = "Hot"
        elif score >= 40:
            score_label = "Warm"
        else:
            score_label = "Cold"

        # Extract tags - handle both string format and object format
        raw_tags = fub_person.get("tags", [])
        if raw_tags and isinstance(raw_tags[0], dict):
            tags = [tag.get("tag", "") for tag in raw_tags]
        else:
            tags = list(raw_tags) if raw_tags else []

        # Extract lead type (Seller/Buyer) - PRIORITIZE TAGS over FUB type field
        # Tags are more reliable because they're explicitly set by agents/automation
        tags_lower = [t.lower() for t in tags]
        has_seller_tag = any("seller" in t for t in tags_lower)
        has_buyer_tag = any("buyer" in t for t in tags_lower)

        # Determine lead type - tags take priority
        if has_seller_tag and not has_buyer_tag:
            lead_type = "seller"
        elif has_buyer_tag and not has_seller_tag:
            lead_type = "buyer"
        elif has_seller_tag and has_buyer_tag:
            lead_type = "both"  # Has both tags
        else:
            # No tags - fall back to FUB type field
            lead_type = (fub_person.get("type") or "").lower()

        # Get source info
        source = fub_person.get("source", "")
        source_url = fub_person.get("sourceUrl", "")

        # Custom fields (FUB stores various data here)
        custom_fields = {}
        for field in fub_person.get("customFields", []):
            custom_fields[field.get("name", "")] = field.get("value")

        # Calculate days since created - FUB uses "created" not "createdAt"
        created_at = fub_person.get("created") or fub_person.get("createdAt", "")
        days_since_created = 0
        if created_at:
            try:
                created_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                # Use UTC now for proper comparison with UTC timestamps
                from datetime import timezone
                now_utc = datetime.now(timezone.utc)
                days_since_created = (now_utc - created_date).days
            except Exception as e:
                logger.warning(f"Failed to parse created_at '{created_at}': {e}")

        return cls(
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
            email=primary_email,
            phone=primary_phone,
            score=score,
            score_label=score_label,
            stage=fub_person.get("stage", ""),
            stage_name=fub_person.get("stageName", ""),
            assigned_agent=(
                fub_person.get("assignedTo", {}).get("name", "")
                if isinstance(fub_person.get("assignedTo"), dict)
                else fub_person.get("assignedTo", "")
            ),
            lead_type=lead_type,
            source=source,
            source_url=source_url,
            interested_property_address=additional.get("property_address", ""),
            interested_property_price=additional.get("property_price"),
            tags=tags,
            current_address=current_address,
            created_date=created_at[:10] if created_at else "",
            days_since_created=days_since_created,
            fub_person_id=fub_person.get("id"),
            custom_fields=custom_fields,
            # These would come from additional_data
            timeline=additional.get("timeline", ""),
            motivation=additional.get("motivation", ""),
            price_min=additional.get("price_min"),
            price_max=additional.get("price_max"),
            is_pre_approved=additional.get("is_pre_approved"),
            pre_approval_amount=additional.get("pre_approval_amount"),
            preferred_cities=additional.get("preferred_cities", []),
            preferred_neighborhoods=additional.get("preferred_neighborhoods", []),
            property_types=additional.get("property_types", []),
            bedrooms_min=additional.get("bedrooms_min"),
            must_have_features=additional.get("must_have_features", []),
            deal_breakers=additional.get("deal_breakers", []),
            previous_objections=additional.get("previous_objections", []),
            objection_count=additional.get("objection_count", 0),
            engagement_level=additional.get("engagement_level", ""),
            total_messages_sent=additional.get("total_messages_sent", 0),
            total_messages_received=additional.get("total_messages_received", 0),
            last_contact_date=additional.get("last_contact_date", ""),
            last_contact_type=additional.get("last_contact_type", ""),
            decision_makers=additional.get("decision_makers", ""),
            has_children=additional.get("has_children"),
            has_pets=additional.get("has_pets"),
            important_notes=additional.get("important_notes", []),
            agent_notes_summary=additional.get("agent_notes_summary", ""),
            call_summaries=additional.get("call_summaries", []),
            # Property inquiry details (from FUB events)
            property_inquiry_source=additional.get("property_inquiry_source", ""),
            property_inquiry_description=additional.get("property_inquiry_description", ""),
            property_inquiry_location=additional.get("property_inquiry_location", ""),
            property_inquiry_budget=additional.get("property_inquiry_budget", ""),
            property_inquiry_timeline=additional.get("property_inquiry_timeline", ""),
            property_inquiry_financing=additional.get("property_inquiry_financing", ""),
            # Communication status
            actual_messages_sent=additional.get("actual_messages_sent", []),
            actual_messages_received=additional.get("actual_messages_received", []),
            has_received_any_messages=additional.get("has_received_any_messages", False),
            planned_messages_not_sent=additional.get("planned_messages_not_sent", []),
            is_first_contact=additional.get("is_first_contact", True),
        )

    @staticmethod
    def parse_property_inquiry(description: str) -> Dict[str, str]:
        """
        Parse property inquiry description to extract key details.

        Example input: "Primary Zip: 80521 | Time Frame: 0 - 3 Months | Financing: I am in the process of getting pre-approved"

        Returns dict with: location, timeline, financing, budget
        """
        result = {}
        if not description:
            return result

        # Parse pipe-delimited fields
        parts = description.split("|")
        for part in parts:
            part = part.strip()
            if ":" in part:
                key, value = part.split(":", 1)
                key = key.strip().lower()
                value = value.strip()

                if "zip" in key or "location" in key or "city" in key:
                    result["location"] = value
                elif "time" in key or "frame" in key or "timeline" in key:
                    result["timeline"] = value
                elif "financ" in key or "pre-approv" in key or "mortgage" in key:
                    result["financing"] = value
                elif "price" in key or "budget" in key:
                    result["budget"] = value

        return result

    @classmethod
    def process_fub_context(cls, fub_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process raw FUB context into structured additional_data for LeadProfile.

        Takes the output of get_complete_lead_context() and extracts:
        - Message history (sent/received)
        - Notes summary
        - Property inquiry details from events
        - Communication status

        Args:
            fub_context: Raw context from FUBApiClient.get_complete_lead_context()

        Returns:
            Structured additional_data dict for from_fub_data()
        """
        additional = {}

        # Process text messages
        text_messages = fub_context.get("text_messages", [])
        sent_messages = []
        received_messages = []

        for msg in text_messages:
            msg_data = {
                "content": msg.get("message", ""),
                "timestamp": msg.get("created", ""),
                "direction": "outbound" if msg.get("isOutgoing") else "inbound",
            }
            if msg.get("isOutgoing"):
                sent_messages.append(msg_data)
            else:
                received_messages.append(msg_data)

        additional["actual_messages_sent"] = sent_messages
        additional["actual_messages_received"] = received_messages
        additional["total_messages_sent"] = len(sent_messages)
        additional["total_messages_received"] = len(received_messages)
        additional["has_received_any_messages"] = len(sent_messages) > 0
        additional["is_first_contact"] = len(sent_messages) == 0

        # Process calls for call notes/summaries/outcomes
        calls = fub_context.get("calls", [])
        call_summaries = []
        additional["total_calls"] = len(calls)
        for call in calls[:5]:  # Last 5 calls
            call_note = call.get("note", "")
            duration = call.get("duration", 0)
            direction = "outgoing" if not call.get("isIncoming") else "incoming"
            outcome = call.get("outcome", "")  # Interested, Not Interested, Left Message, No Answer, etc.

            if call_note:
                outcome_str = f" - {outcome}" if outcome else ""
                call_summaries.append(f"[{direction} call, {duration}s{outcome_str}]: {call_note[:200]}")
            elif outcome:
                call_summaries.append(f"[{direction} call, {duration}s]: Outcome: {outcome}")
            elif duration and duration > 30:  # Only mention substantial calls without notes
                call_summaries.append(f"[{direction} call, {duration}s - no notes recorded]")

        if call_summaries:
            additional["call_summaries"] = call_summaries

        # Process notes for summary
        notes = fub_context.get("notes", [])
        important_notes = []
        for note in notes[:10]:  # Limit to recent 10
            content = note.get("body", "")[:200]  # Truncate long notes
            if content:
                important_notes.append(content)

        additional["important_notes"] = important_notes
        if important_notes:
            additional["agent_notes_summary"] = " | ".join(important_notes[:3])

        # Process events for property inquiry details
        events = fub_context.get("events", [])
        for event in events:
            event_type = event.get("type", "")
            description = event.get("description", "") or event.get("body", "")

            # Property inquiry events have rich context
            if event_type in ["PropertyInquiry", "propertyInquiry"] or "inquiry" in event_type.lower():
                source = event.get("source", "") or event.get("provider", "")
                if source:
                    additional["property_inquiry_source"] = source
                if description:
                    additional["property_inquiry_description"] = description
                    # Parse the description for structured data
                    parsed = cls.parse_property_inquiry(description)
                    if parsed.get("location"):
                        additional["property_inquiry_location"] = parsed["location"]
                    if parsed.get("timeline"):
                        additional["property_inquiry_timeline"] = parsed["timeline"]
                        # Convert to standard timeline
                        timeline_lower = parsed["timeline"].lower()
                        if "0 - 3" in timeline_lower or "immediate" in timeline_lower:
                            additional["timeline"] = "short"
                        elif "3 - 6" in timeline_lower:
                            additional["timeline"] = "medium"
                        elif "6" in timeline_lower or "12" in timeline_lower:
                            additional["timeline"] = "long"
                    if parsed.get("financing"):
                        additional["property_inquiry_financing"] = parsed["financing"]
                        financing_lower = parsed["financing"].lower()
                        # Check "in process" first since it also contains "pre-approved"
                        if "process" in financing_lower or "getting" in financing_lower or "working on" in financing_lower:
                            additional["is_pre_approved"] = False  # In process = not yet approved
                        elif "pre-approved" in financing_lower or "preapproved" in financing_lower or "already" in financing_lower:
                            additional["is_pre_approved"] = True
                        elif "cash" in financing_lower:
                            additional["is_pre_approved"] = True  # Cash buyer = no approval needed
                    if parsed.get("budget"):
                        additional["property_inquiry_budget"] = parsed["budget"]
                break  # Use first property inquiry found

        # Get last contact info
        if sent_messages:
            last_sent = sorted(sent_messages, key=lambda x: x.get("timestamp", ""), reverse=True)[0]
            additional["last_contact_date"] = last_sent.get("timestamp", "")[:10]
            additional["last_contact_type"] = "sms"
        elif received_messages:
            last_received = sorted(received_messages, key=lambda x: x.get("timestamp", ""), reverse=True)[0]
            additional["last_contact_date"] = last_received.get("timestamp", "")[:10]
            additional["last_contact_type"] = "sms_inbound"

        return additional


class AIResponseGenerator:
    """
    Production-grade AI response generator using Claude.

    Features:
    - Automatic retry with exponential backoff
    - Model fallback (Sonnet -> Haiku if needed)
    - Response validation and quality checking
    - Context window management
    - Token usage tracking
    - Comprehensive logging
    - Appointment-focused goal-driven responses
    - Source-aware conversation strategies
    """

    # Model configuration - Anthropic (defaults)
    DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
    DEFAULT_ANTHROPIC_FALLBACK = "claude-3-5-haiku-20241022"

    # Model configuration - OpenRouter
    # Primary: Grok 4.1 Fast - very cheap ($0.20/$0.50 per million tokens), fast, reliable
    # Fallback: Gemini for cost efficiency
    DEFAULT_OPENROUTER_MODEL = "x-ai/grok-4.1-fast"
    DEFAULT_OPENROUTER_FALLBACK = "google/gemini-2.5-flash-lite"
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

    # Rate limit avoidance settings
    # Free tier models have strict limits - for texting we can be very conservative
    # Real conversations have minutes/hours between messages, so no rush
    MIN_REQUEST_INTERVAL = 10.0  # Minimum seconds between requests (very conservative for free tier)
    REQUEST_JITTER = 5.0  # Random jitter (0-5s) to spread out requests

    # Available free models for user selection (with tool calling support)
    AVAILABLE_FREE_MODELS = [
        {"id": "xiaomi/mimo-v2-flash:free", "name": "Xiaomi MiMo v2 Flash", "description": "Fast, good for conversations"},
        {"id": "meta-llama/llama-3.3-70b-instruct:free", "name": "Meta Llama 3.3 70B", "description": "High quality, function calling"},
        {"id": "google/gemini-2.0-flash-exp:free", "name": "Google Gemini 2.0 Flash", "description": "1M context, multimodal"},
        {"id": "qwen/qwen3-coder:free", "name": "Qwen3 Coder 480B", "description": "Best for tool use"},
        {"id": "openai/gpt-oss-120b:free", "name": "OpenAI GPT-OSS 120B", "description": "GPT quality, tool use"},
        {"id": "deepseek/deepseek-r1-0528:free", "name": "DeepSeek R1", "description": "Reasoning model"},
        {"id": "deepseek/deepseek-chat-v3-0324:free", "name": "DeepSeek Chat v3", "description": "General chat"},
    ]

    MAX_TOKENS = 500
    MAX_CONTEXT_MESSAGES = 20  # Keep last N messages for context

    # Retry configuration
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 1.0  # seconds
    MAX_RETRY_DELAY = 10.0

    # Response validation
    MAX_SMS_LENGTH = 1000  # Default fallback; overridden by self.max_sms_length from settings
    MIN_RESPONSE_LENGTH = 10

    # Source-aware conversation strategies
    SOURCE_STRATEGIES = {
        "referralexchange": {
            "approach": "warm_referral",
            "urgency": "high",
            "context": "They came through ReferralExchange - a referral network. They're actively looking and expect quick response.",
            "opener_hint": "If someone on your team already called/emailed, SAY SO: 'Following up on Adam's call' or 'I work with Adam who reached out'. Don't pretend you're the first contact if you're not."
        },
        "homelight": {
            "approach": "warm_referral",
            "urgency": "high",
            "context": "HomeLight qualified lead - they've expressed intent to buy/sell. High conversion potential.",
            "opener_hint": "Acknowledge their interest, validate their goals, offer immediate appointment"
        },
        "redfin": {
            "approach": "property_specific",
            "urgency": "high",
            "context": "They saw specific properties on Redfin. Property-focused conversation.",
            "opener_hint": "Reference the property interest, offer to show similar homes or discuss listing"
        },
        "zillow": {
            "approach": "competitive",
            "urgency": "medium",
            "context": "Zillow lead - they're likely talking to multiple agents. Differentiate yourself.",
            "opener_hint": "Stand out from other agents, offer unique value, don't be pushy but be available"
        },
        "agentpronto": {
            "approach": "warm_referral",
            "urgency": "high",
            "context": "AgentPronto lead - pre-qualified referral. They're ready to work with an agent.",
            "opener_hint": "Thank them for choosing you, understand their goals, schedule appointment"
        },
        "myagentfinder": {
            "approach": "warm_referral",
            "urgency": "high",
            "context": "MyAgentFinder lead - they requested an agent match. Motivated lead.",
            "opener_hint": "Acknowledge the match, build rapport quickly, move to appointment"
        },
        "website": {
            "approach": "warm_organic",
            "urgency": "medium",
            "context": "They found you directly - some existing trust. Build on that.",
            "opener_hint": "Thank them for reaching out, understand their needs, guide to appointment"
        },
        "default": {
            "approach": "consultative",
            "urgency": "medium",
            "context": "Standard lead approach - qualify, build rapport, schedule.",
            "opener_hint": "Friendly introduction, understand their situation, offer helpful next step"
        }
    }

    # Tool definitions for Claude tool use - lets AI choose the best action
    AVAILABLE_TOOLS = [
        {
            "name": "send_sms",
            "description": "Send an SMS text message to the lead. Use for quick responses, urgent matters, conversational follow-ups, or when the lead prefers texting.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The SMS message content"
                    },
                    "urgency": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "How urgent is this message"
                    }
                },
                "required": ["message"]
            }
        },
        {
            "name": "send_email",
            "description": "Send an email to the lead. Use for detailed information, property listings, market reports, formal introductions, or when SMS isn't appropriate.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                        "description": "Email subject line"
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body content"
                    },
                    "include_listings": {
                        "type": "boolean",
                        "description": "Whether to attach relevant property listings based on lead preferences"
                    }
                },
                "required": ["subject", "body"]
            }
        },
        {
            "name": "create_task",
            "description": "Create a follow-up task for the human agent. Use when human intervention is needed, complex questions arise, lead requests a call, or situation requires human judgment.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Task title describing what needs to be done"
                    },
                    "due_in_hours": {
                        "type": "integer",
                        "description": "Hours until task is due (default 24)"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Task priority level"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Additional context for the agent"
                    }
                },
                "required": ["title"]
            }
        },
        {
            "name": "schedule_showing",
            "description": "Schedule an appointment with the lead. For BUYERS: property showings, buyer consultations. For SELLERS: listing appointments, home valuations, CMA presentations. Use when lead is qualified and ready to meet.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "appointment_type": {
                        "type": "string",
                        "enum": ["showing", "listing"],
                        "description": "Type of appointment: 'showing' for buyers (property tours), 'listing' for sellers (listing consultation/home valuation)"
                    },
                    "property_address": {
                        "type": "string",
                        "description": "Property address - for showings: property to view; for listings: seller's property"
                    },
                    "proposed_times": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "2-3 proposed appointment times (e.g., 'Saturday at 10am', 'Tuesday afternoon')"
                    },
                    "message": {
                        "type": "string",
                        "description": "Message to send proposing the appointment"
                    },
                    "lead_name": {
                        "type": "string",
                        "description": "Lead's first name for the task description"
                    }
                },
                "required": ["message", "appointment_type"]
            }
        },
        {
            "name": "add_note",
            "description": "Add an internal note to the lead's profile without contacting them. Use to document important information discovered during conversation.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "note": {
                        "type": "string",
                        "description": "Note content to add to lead profile"
                    },
                    "category": {
                        "type": "string",
                        "enum": ["qualification", "objection", "preference", "timeline", "other"],
                        "description": "Category of the note"
                    }
                },
                "required": ["note"]
            }
        },
        {
            "name": "web_search",
            "description": "Search the web for information to help answer lead questions. Use for: property/market research, neighborhood info, school ratings, local amenities, recent home sales, or any real estate question you need data to answer accurately.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to find relevant information"
                    },
                    "search_type": {
                        "type": "string",
                        "enum": ["general", "real_estate", "schools", "neighborhoods", "market_data"],
                        "description": "Type of search to optimize results"
                    },
                    "location": {
                        "type": "string",
                        "description": "Location context for the search (city, neighborhood, zip)"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "no_action",
            "description": "Take no action. Use when lead's message doesn't require a response (like 'ok', 'thanks'), when in a blocked stage, or when waiting is the best strategy.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Reason for not taking action"
                    }
                },
                "required": ["reason"]
            }
        }
    ]

    # Personality configurations
    PERSONALITY_PROMPTS = {
        "friendly_casual": """You are a top-producing real estate agent's assistant — warm, knowledgeable, and genuinely helpful. You sound like someone who knows the market, cares about people, and makes every conversation feel easy and natural.

MESSAGE STRUCTURE (follow this for every response):
1. ACKNOWLEDGE what they said — show you're actually listening (reference their specific words/situation)
2. ADD VALUE — share something useful, relevant, or reassuring based on what you know
3. ASK ONE clear question — move the conversation forward toward scheduling

LENGTH & STYLE:
- Write 2-3 sentences per message, aim for 200-320 characters. Shorter texts convert better.
- Hard limit: {max_sms_length} chars. But shorter is always better for SMS.
- Use contractions naturally: "I'd", "that's", "you'll", "we've"
- Vary your opening — don't always start with "Hey [name]!"
- Sound confident and knowledgeable, like you do this every day
- Match the lead's energy — if they're casual, be casual; if they're detailed, match it

BANNED PHRASES (these sound robotic/salesy):
- "Just checking in" / "touching base" / "reaching out" (overused corporate)
- "Hope you're doing well" / "Hope all is well" (generic filler)
- "I'd be happy to help!" / "I'm here to assist" (customer service bot)
- "Absolutely!" / "Certainly!" (too eager)
- "Thank you for reaching out" (formal)
- "Great question!" / "That's a great point!" (patronizing)
- "What's driving your search?" (sounds like a survey)
- Too many exclamation points!!!
- "Please don't hesitate" / "At your earliest convenience" (formal)

WORLD-CLASS EXAMPLES:
- "That's a great area — we've been seeing a lot of movement there lately. Are you pre-approved yet, or is that something you'd want to get squared away first?"
- "3 months is solid timing. That gives us room to be selective and find the right fit. What neighborhoods are you drawn to?"
- "Totally understand wanting to wait. The market's shifting a bit right now, so when you're ready I can show you how that works in your favor. Mind if I send you a few listings to browse in the meantime?"
- "Good call on Greeley — prices there have been really competitive. Are you looking for something with a yard, or would a townhome work too?"

NOT LIKE THIS:
- "Ok sounds good!" (too short, no value)
- "Just checking in to see if you had any questions!" (generic)
- "I'd love to help you find your dream home!" (salesy)

EMPATHY IS KEY:
- When someone shares life circumstances (divorce, job loss, death, relocation, growing family, financial stress), ACKNOWLEDGE IT genuinely before anything else
- Don't rush past emotional moments to ask your next qualifying question
- "That sounds like a lot to navigate — I'm glad you're thinking about what's next. No pressure at all, I'm here whenever you're ready."
- "Congrats on the new baby! That's exciting. Makes total sense you'd want more space."
- "I'm sorry to hear that. Moving during a tough time is stressful, but I'll make it as easy as possible on my end."
- Match their emotional tone — if they're stressed, be reassuring. If they're excited, share the excitement. If they're overwhelmed, simplify.

VIBE: Confident, knowledgeable, warm, and genuinely human. Like the best agent you know — someone who makes you feel taken care of without being pushy. You listen, you care, and every message moves the conversation forward.""",

        "professional": """You are a highly respected real estate professional — confident, market-savvy, and results-driven. You communicate with the authority of someone who closes deals consistently and knows the market inside-out.

MESSAGE STRUCTURE:
1. ACKNOWLEDGE their situation with confidence
2. ADD VALUE with market knowledge or expert insight
3. MOVE FORWARD with one clear next step

LENGTH & STYLE:
- Write 2-3 sentences, aim for 200-320 characters. Concise = professional. Hard limit: {max_sms_length} chars.
- Use contractions naturally — you're a pro, not a robot
- Lead with expertise — reference market data, trends, or experience when relevant
- Don't waste words, but don't be terse either

SOUND LIKE THIS:
- "That area's been competitive — homes are moving in under 10 days. If you're pre-approved, we can get you in front of the right listings before they're gone. When works for a quick call?"
- "Based on what you're describing, you're in a strong position. I'd want to look at recent comps in your neighborhood before giving you a number. What's a good day for me to swing by?"
- "Smart move getting started now — rates are shifting and inventory is opening up. What's your budget range so I can narrow things down?"

VIBE: Expert who delivers results. Confident, direct, no fluff — but still personable.""",

        "energetic": """You genuinely love real estate and it shows — but in a natural, authentic way. Your enthusiasm comes from knowledge and genuine care, not hype.

MESSAGE STRUCTURE:
1. ACKNOWLEDGE with genuine engagement — show you're excited about their situation
2. ADD VALUE with insider knowledge or enthusiasm that's earned
3. ASK ONE question that moves things forward

LENGTH & STYLE:
- Write 2-3 sentences, aim for 200-320 characters. Keep that energy tight. Hard limit: {max_sms_length} chars.
- Use contractions and casual language — you're approachable
- Enthusiasm is great, but earned — tie it to something specific (their area, timing, goals)
- Don't force positivity if the lead seems stressed or uncertain

SOUND LIKE THIS:
- "Oh nice, that neighborhood is one of my favorites! They just finished the new trail system too. Are you looking to be close to downtown or more on the outskirts?"
- "First-time buyer — love it! You picked a great time too, there's actually more inventory right now than we've seen in a while. Have you gotten pre-approved yet?"
- "Your place has great bones — honestly, with a few small updates you could do really well in this market. Want me to come take a look and give you some numbers?"

VIBE: Genuinely passionate, knowledgeable, and makes the whole process feel exciting instead of stressful.""",
    }

    # State-specific guidance - Research-backed from Follow Up Boss, The Close (2024-2025)
    STATE_GUIDANCE = {
        "initial": """GOAL: Welcome them warmly and start building rapport.
- Be personal and specific — reference their source, location, or situation
- Ask ONE open question about their goals or timeline
- Match the energy of their source (referral = warm acknowledgment, portal = more direct value)
- Example: "Hey [name]! I see you're looking in the [area] area — are you just starting to explore, or are you closer to making a move?"
- DON'T over-thank or sound like a customer service bot""",

        "qualifying": """GOAL: Naturally learn about their situation while building trust. Every response should feel like a conversation, not an interview.

PRIORITY ORDER:
- FOR BUYERS: Timeline → Pre-approval → Areas → Budget → Property type
- FOR SELLERS: Timeline → Motivation → Price expectations → Property condition

TECHNIQUE: Acknowledge → Add value → Ask next question
- ALWAYS acknowledge what they just told you before asking the next question
- Add a brief insight or validation to show you know what you're talking about
- Then ask ONE natural follow-up question

EXAMPLES:
- "3 months is great timing — that gives us room to be selective. Are you pre-approved yet, or is that something you'd want to knock out first?"
- "Nice choice — [area] has been really competitive lately but inventory is opening up. What kind of budget range are you working with?"
- "Selling in [season] is smart — we typically see strong demand then. Have you thought about where you'd move next, or is that still up in the air?"

EMPATHY FIRST: If they share life circumstances (divorce, relocation, job change, family growth, financial stress), pause qualifying and acknowledge it genuinely. Then gently continue when it feels natural.
- "Wow, relocating with a family is a big move — glad you're getting started early. What area are you leaning toward?"
- "I'm sorry to hear that. Moving on top of everything else can feel overwhelming, but I'll keep things simple on my end. What's your ideal timeline?"

CRITICAL: If they already answered a question in a previous message, DO NOT ask it again. Move to the next topic.""",

        "objection_handling": """GOAL: Address their concern with empathy and expertise, then gently redirect toward value.

TECHNIQUE: Validate → Reframe with value → Leave the door open

COMMON OBJECTIONS:
- "I'm just looking" → "Totally makes sense — a lot of people start that way. When you say looking, is that more like 6 months out or just keeping an eye on what's out there? Either way, I can send you listings that match so you stay in the loop."
- "Already have an agent" → "No worries at all! Hope it's going well. If anything changes or you ever want a second opinion, don't hesitate to reach out."
- "Not ready yet" → "That's fair — no rush at all. The market's been shifting a bit, so when you are ready, I can catch you up on what's changed. Mind if I check back in a few weeks?"
- "Just want to see prices" → "Totally — prices in [area] have been [trend]. I can send you a quick market snapshot if you want to see where things stand. Would that be helpful?"

RULES:
- Never argue or pressure
- Always offer value even in the objection response
- If they're firm, respect it gracefully — they may come back later""",

        "scheduling": """GOAL: Get them booked for a showing or consultation. This is the payoff — make it effortless.

TECHNIQUE: Assumptive close with specific options
- BAD: "Would you like to schedule a time?" (easy to say no)
- GOOD: "Are you free Saturday morning or does Sunday afternoon work better?" (easy to say yes)

FOR BUYERS: "I've pulled a few homes that match what you're looking for — want to check them out this weekend? I could do Saturday morning or Sunday afternoon."
FOR SELLERS: "I'd love to take a look at your place and give you some real numbers. What's a good day this week for me to swing by?"

WHEN THEY AGREE:
- Set should_handoff=true and next_state="handed_off" so the human agent can take over scheduling
- Confirm enthusiasm: "Awesome, [agent name] will reach out to lock in the details!"
- Make it feel seamless — they shouldn't feel like they're being passed around""",

        "nurture": """GOAL: Stay top-of-mind by providing value, not pressure.
- Lead with VALUE every time — market update, new listing, neighborhood news, rate changes
- Keep it conversational: "Hey [name], saw a new listing near [area] that reminded me of what you described — want me to send it over?"
- Respect their timeline — don't push for appointments
- Vary your approach — sometimes ask a question, sometimes just share info
- Re-engage by connecting to their original goals: "Still thinking about [area]? A few things have changed since we last talked."
- If no response after multiple touches, try a different angle (market insight, seasonal advice, etc.)""",

        "handed_off": """GOAL: Smoothly transition to the human agent.
- Be specific about who will follow up: "[Agent name] is going to reach out to get everything set up."
- Give them a timeframe so they're not left wondering
- Express genuine enthusiasm (not over the top): "Really looking forward to helping you find the right place!"
- Don't leave any loose ends — they should feel taken care of""",
    }

    def __init__(
        self,
        api_key: str = None,
        personality: str = "friendly_casual",
        agent_name: str = "Sarah",
        brokerage_name: str = "our team",
        team_members: str = "",  # Human agent names (e.g., "Adam and Mandi")
        use_assigned_agent_name: bool = False,
        llm_provider: str = None,  # "openrouter" or "anthropic"
        llm_model: str = None,  # Custom model ID
        llm_model_fallback: str = None,  # Fallback model ID
        max_sms_length: int = None,  # Configurable SMS limit (from settings)
        max_email_length: int = None,  # Configurable email limit (from settings)
    ):
        """
        Initialize the AI response generator.

        Supports both Anthropic and OpenRouter APIs. Priority:
        1. Provided api_key parameter
        2. OPENROUTER_API_KEY environment variable (preferred - free models)
        3. ANTHROPIC_API_KEY environment variable

        Args:
            api_key: API key (uses env var if not provided)
            personality: Personality tone to use
            agent_name: Name the AI will use (branded name like "Sarah")
            brokerage_name: Brokerage/team name
            team_members: Human agent names the AI works with
            use_assigned_agent_name: If True, use lead's assigned agent name instead
            llm_provider: LLM provider to use ("openrouter" or "anthropic")
            llm_model: Custom model ID to use
            llm_model_fallback: Fallback model ID
        """
        # Check for API keys
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.anthropic_api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

        # Determine which provider to use based on settings or available keys
        if llm_provider:
            self.use_openrouter = llm_provider.lower() == "openrouter"
        else:
            # Default: prefer OpenRouter (Grok 4.1 Fast - cheap & reliable)
            self.use_openrouter = bool(self.openrouter_api_key)

        self.api_key = self.openrouter_api_key if self.use_openrouter else self.anthropic_api_key

        # Set model configuration (use provided or defaults)
        if self.use_openrouter:
            self.primary_model = llm_model or self.DEFAULT_OPENROUTER_MODEL
            self.fallback_model = llm_model_fallback or self.DEFAULT_OPENROUTER_FALLBACK
        else:
            self.primary_model = llm_model or self.DEFAULT_ANTHROPIC_MODEL
            self.fallback_model = llm_model_fallback or self.DEFAULT_ANTHROPIC_FALLBACK

        self.personality = personality
        self.agent_name = agent_name
        self.brokerage_name = brokerage_name
        self.team_members = team_members
        self.use_assigned_agent_name = use_assigned_agent_name
        # Dynamic message length limits (override class constant)
        self.max_sms_length = max_sms_length or self.MAX_SMS_LENGTH
        self.max_email_length = max_email_length or 5000
        self._client = None
        self._openrouter_client = None
        self._total_tokens_used = 0
        self._request_count = 0
        self._last_request_time = 0.0  # For rate limit avoidance

        if self.use_openrouter:
            key_preview = f"{self.openrouter_api_key[:8]}..." if self.openrouter_api_key else "NOT SET"
            logger.info(f"Using OpenRouter API with model: {self.primary_model}, key: {key_preview}")
        elif self.api_key:
            logger.info(f"Using Anthropic API with model: {self.primary_model}")
        else:
            logger.warning("No AI API key configured - AI responses will fail")

    def _get_effective_agent_name(self, lead_profile: Optional[LeadProfile] = None) -> str:
        """
        Get the agent name to use in responses.

        If use_assigned_agent_name=True and lead has an assigned agent,
        use their first name. Otherwise fall back to configured branded name.
        """
        if self.use_assigned_agent_name and lead_profile and lead_profile.assigned_agent:
            # Extract first name from "Adam Schwartz" -> "Adam"
            return lead_profile.assigned_agent.split()[0]
        return self.agent_name  # Fall back to branded name (e.g., "Sarah")

    def _get_source_strategy(self, source: str) -> dict:
        """Get approach strategy based on lead source."""
        source_lower = (source or "").lower().replace(" ", "")
        for key, strategy in self.SOURCE_STRATEGIES.items():
            if key in source_lower:
                return strategy
        return self.SOURCE_STRATEGIES["default"]

    def calculate_human_like_delay(
        self,
        message_length: int,
        is_first_message: bool = False,
        source_urgency: str = "medium",
        conversation_velocity: str = "normal",
    ) -> int:
        """
        Calculate a human-like delay before responding.

        This prevents the AI from appearing robotic by responding instantly.
        Factors in:
        - Simulated typing time
        - First message vs back-and-forth
        - Source urgency (referrals = faster response)
        - Random variation for naturalness

        Args:
            message_length: Length of the response message
            is_first_message: True if this is the first outreach to lead
            source_urgency: "high", "medium", or "low"
            conversation_velocity: "fast" (rapid back-and-forth), "normal", "slow"

        Returns:
            Delay in seconds before sending the message
        """
        import random

        # Base delay ranges — speed-to-lead is critical
        # Research: 5-minute response = 21x higher conversion (MIT study)
        # With FUB native API (<1s send time), these delays are the main bottleneck
        if is_first_message:
            min_delay = 5   # First message: 5 seconds minimum
            max_delay = 15  # Up to 15 seconds
        else:
            min_delay = 10  # Follow-up: 10 seconds minimum
            max_delay = 30  # Up to 30 seconds

        # Adjust for source urgency
        urgency_multipliers = {
            "high": 0.5,    # Referral leads (paid for) - respond fastest
            "medium": 1.0,  # Normal
            "low": 1.2,     # Zillow etc - slightly longer is fine
        }
        multiplier = urgency_multipliers.get(source_urgency, 1.0)
        min_delay = int(min_delay * multiplier)
        max_delay = int(max_delay * multiplier)

        # Adjust for conversation velocity
        if conversation_velocity == "fast":
            # Rapid back-and-forth - respond quicker
            min_delay = max(3, min_delay - 5)
            max_delay = max(10, max_delay - 10)
        elif conversation_velocity == "slow":
            # Slower pace - can take slightly longer
            min_delay += 5
            max_delay += 10

        # Small typing simulation (faster than real typing)
        typing_time = min(int(message_length / 8.0), 10)
        base_delay = random.randint(min_delay, max(min_delay, max_delay))

        # Add typing time but cap total delay
        total_delay = min(base_delay + typing_time, max_delay + 5)

        # Add small random jitter for naturalness
        jitter = random.randint(-2, 3)
        total_delay = max(3, total_delay + jitter)  # Never less than 3 seconds

        return total_delay

    def _classify_lead_status(self, profile: LeadProfile) -> str:
        """
        Classify lead status for messaging strategy.

        Returns one of:
        - new_hot: Brand new lead (<=1 day) - respond immediately
        - active_engaged: Recent and engaged (<=7 days, responding)
        - active_nurturing: Active conversation (<=30 days)
        - dormant_reengaging: Need to re-engage (old or no recent contact)
        - warm_following_up: In between states
        """
        days = profile.days_since_created
        engagement = profile.engagement_level

        # Calculate days since last contact from last_contact_date
        days_since_last_contact = None
        if profile.last_contact_date:
            try:
                last_contact = datetime.fromisoformat(profile.last_contact_date.replace("Z", "+00:00"))
                days_since_last_contact = (datetime.now(last_contact.tzinfo) - last_contact).days
            except Exception as e:
                logger.warning(f"Failed to parse last_contact_date '{profile.last_contact_date}': {e}")

        # If no last contact date, assume dormant if lead is old
        if days_since_last_contact is None:
            days_since_last_contact = days  # Treat lead age as last contact age

        # Classification logic
        if days <= 1:
            return "new_hot"
        elif days <= 7 and engagement in ["high", "medium"]:
            return "active_engaged"
        elif days <= 30 and days_since_last_contact <= 7:
            return "active_nurturing"
        elif days > 60 or days_since_last_contact > 14:
            # Old leads (60+ days) or no recent contact = dormant
            return "dormant_reengaging"
        else:
            return "warm_following_up"

    def _build_goal_section(self, lead_profile: Optional[LeadProfile] = None) -> str:
        """
        Build goal section based on lead type.

        This tells the AI exactly what appointment type to drive toward:
        - Sellers → Listing appointment (home valuation, CMA)
        - Buyers → Showing appointment (property tours)
        """
        if not lead_profile:
            return self._build_goal_section_unknown()

        lead_type = (lead_profile.lead_type or "").lower()

        if lead_type == "seller":
            return """
YOUR PRIMARY GOAL: Book a LISTING APPOINTMENT

OBJECTIVE: Schedule a listing consultation / home valuation
- Understand their timeline to sell and motivation
- Offer to visit their home to provide a professional market analysis
- Ideal outcome: "Let's schedule a time for me to see your home and discuss pricing strategy"

SELLER APPOINTMENT STRATEGY:
- If you have their address, reference it specifically - don't ask what area they're in
- Ask about their timeline (when do they want/need to sell?)
- Ask about their motivation (why are they selling?)
- Once you understand their situation, propose the listing appointment
- Use assumptive close: "I'd love to come see your home and give you an idea of what it could sell for"
"""
        elif lead_type == "both":
            # BUYER AND SELLER - They're making a coordinated move!
            return """
YOUR PRIMARY GOAL: Book a CONSULTATION to discuss BOTH their sale AND purchase

CRITICAL: This lead is BOTH buying AND selling - they're making a move!
- DO NOT ask "are you looking to buy or sell?" - we ALREADY KNOW they're doing BOTH
- Focus on coordinating both transactions
- Understand their timeline for BOTH selling current home AND buying new one

DUAL TRANSACTION STRATEGY:
- Acknowledge BOTH needs upfront: "I see you're looking to sell and buy - exciting move!"
- Ask about coordination preference: sell first vs buy first vs simultaneous
- Understand what's driving the move (upsizing, downsizing, relocating?)
- If they have a timeline, it likely applies to both transactions

APPOINTMENT OPTIONS:
1. Combined consultation: "Let's meet to discuss your sale AND start looking at homes"
2. Start with valuation: "I can come see your current home and we'll also talk about what you're looking for"
3. Coordinate timing: "Whether you sell first or buy first, I'll help coordinate both sides"

IDEAL OUTCOME:
- "Let's schedule a time to visit your home for a valuation AND discuss what you're looking for in your next place"
- Make it clear you handle BOTH sides of the transaction
"""

        elif lead_type == "buyer":
            # Build dynamic strategy based on what we already know
            strategy_items = []
            strategy_items.append("- If they inquired about a specific property, reference it - offer to show it")

            # Only ask about things we DON'T know
            if lead_profile.is_pre_approved is None:
                strategy_items.append("- Ask about pre-approval status (this qualifies them)")
            else:
                strategy_items.append("- Pre-approval is ALREADY KNOWN - do NOT ask about it")

            if not lead_profile.timeline:
                strategy_items.append("- Ask about timeline (when do they need to move?)")
            else:
                strategy_items.append("- Timeline is ALREADY KNOWN - do NOT ask about it")

            strategy_items.append("- Once qualified, propose showings with specific time options")
            strategy_items.append("- Use assumptive close: \"I've got some great homes to show you - are you free Saturday or Sunday?\"")

            return f"""
YOUR PRIMARY GOAL: Book a SHOWING APPOINTMENT

OBJECTIVE: Schedule property showings or a buyer consultation
- Offer to show them homes that match their criteria
- Ideal outcome: "Let's schedule a time to tour some homes this weekend"

BUYER APPOINTMENT STRATEGY:
{chr(10).join(strategy_items)}
"""
        else:
            return self._build_goal_section_unknown()

    def _build_goal_section_unknown(self) -> str:
        """Goal section when we don't know if they're buying or selling."""
        return """
YOUR PRIMARY GOAL: Book an APPOINTMENT

FIRST: Determine if they're buying or selling (ask if not clear)
THEN: Guide toward the appropriate appointment type:
- For SELLERS → listing consultation / home valuation
- For BUYERS → property showings / buyer consultation

DISCOVERY STRATEGY:
- Ask what brought them to you / what they're looking to do
- Once you know buyer vs seller, switch to that appointment strategy
"""

    def _build_known_info_section(self, profile: LeadProfile) -> str:
        """
        Build a section showing what information we ALREADY HAVE.

        This prevents the AI from asking redundant questions - if we have
        their address, don't ask "what area are you in?"

        Differentiates between SELLER, BUYER, and BOTH qualification needs:
        - Sellers: address, timeline to sell, motivation, price expectation
        - Buyers: areas, timeline, budget, pre-approval status
        - Both: combines seller AND buyer needs (they're selling AND buying)
        """
        known = []
        unknown = []
        lead_type = (profile.lead_type or "").lower()

        # Handle "both" - buyer AND seller
        if lead_type == "both":
            known.append("Lead Type: BUYER AND SELLER (coordinated move - DO NOT ask if buying or selling!)")

            # For BOTH, we need info for selling their current home
            if profile.current_address:
                known.append(f"Property to Sell: {profile.current_address}")
            else:
                unknown.append("current property address (to sell)")

            # AND info for buying their next home
            if profile.interested_property_address:
                known.append(f"Property of Interest: {profile.interested_property_address}")
            elif profile.preferred_cities or profile.preferred_neighborhoods:
                areas = profile.preferred_neighborhoods or profile.preferred_cities
                known.append(f"Target Areas (to buy): {', '.join(areas[:3])}")
            else:
                unknown.append("target areas/neighborhoods (to buy)")

        # Address / Location - different meaning for sellers vs buyers
        elif lead_type == "seller":
            # Sellers: we need THEIR property address
            if profile.current_address:
                known.append(f"Property to Sell: {profile.current_address}")
            else:
                unknown.append("property address")
        else:
            # Buyers: we need areas they're interested in
            if profile.interested_property_address:
                known.append(f"Interested Property: {profile.interested_property_address}")
            elif profile.preferred_cities or profile.preferred_neighborhoods:
                areas = profile.preferred_neighborhoods or profile.preferred_cities
                known.append(f"Preferred Areas: {', '.join(areas[:3])}")
            elif profile.current_address:
                # For buyers, current address might hint at area preference
                known.append(f"Current Location: {profile.current_address}")
            else:
                unknown.append("preferred areas/neighborhoods")

        # Timeline - applies to all but phrased differently
        if profile.timeline:
            timeline_labels = {
                "immediate": "Ready NOW",
                "short": "1-3 months",
                "medium": "3-6 months",
                "long": "6+ months"
            }
            timeline_label = timeline_labels.get(profile.timeline, profile.timeline)
            if lead_type == "both":
                known.append(f"Timeline for Move: {timeline_label}")
            elif lead_type == "seller":
                known.append(f"Timeline to Sell: {timeline_label}")
            else:
                known.append(f"Timeline to Buy: {timeline_label}")
        else:
            if lead_type == "both":
                unknown.append("timeline for move (when do they need to sell AND buy?)")
            elif lead_type == "seller":
                unknown.append("timeline to sell (when do they need to move?)")
            else:
                unknown.append("timeline to buy (when do they need to move?)")

        # Price - DIFFERENT for sellers vs buyers vs both
        if lead_type == "both":
            # Both: they need budget for purchase AND maybe have expectations for sale
            if profile.price_min or profile.price_max:
                if profile.price_min and profile.price_max:
                    known.append(f"Budget for Purchase: ${profile.price_min:,} - ${profile.price_max:,}")
                elif profile.price_max:
                    known.append(f"Budget for Purchase: Up to ${profile.price_max:,}")
            else:
                unknown.append("budget range for purchase")
            # Sale price will come from CMA - don't ask
        elif lead_type == "seller":
            # Sellers: we ask about price EXPECTATION, not budget
            if profile.price_min or profile.price_max:
                if profile.price_max:
                    known.append(f"Price Expectation: ${profile.price_max:,}")
            # Don't add to unknown - AI will discover this naturally or provide CMA
        else:
            # Buyers: we ask about budget
            if profile.price_min or profile.price_max:
                if profile.price_min and profile.price_max:
                    known.append(f"Budget: ${profile.price_min:,} - ${profile.price_max:,}")
                elif profile.price_max:
                    known.append(f"Budget: Up to ${profile.price_max:,}")
            else:
                unknown.append("budget range")

        # Pre-approval - for buyers and "both" (since they're also buying)
        if lead_type in ("buyer", "both") or not lead_type:
            if profile.is_pre_approved is not None:
                if profile.is_pre_approved:
                    amt = f" for ${profile.pre_approval_amount:,}" if profile.pre_approval_amount else ""
                    known.append(f"Pre-approved: Yes{amt}")
                else:
                    known.append("Pre-approved: No - DO NOT ask about this again, we already know")
            elif lead_type == "buyer":
                unknown.append("pre-approval status")

        # Motivation - important for both but especially sellers
        if profile.motivation:
            known.append(f"Motivation: {profile.motivation}")
        elif lead_type == "seller":
            unknown.append("motivation for selling (why are they moving?)")

        # Build the section
        sections = []

        if known:
            sections.append("INFORMATION WE ALREADY HAVE (DO NOT ASK AGAIN):\n" +
                          "\n".join(f"  [KNOWN] {item}" for item in known))

        if unknown:
            sections.append("INFORMATION TO DISCOVER (ask about these):\n" +
                          "\n".join(f"  [ASK] {item}" for item in unknown))

        return "\n\n".join(sections) if sections else ""

    @property
    def client(self):
        """Lazy initialization of Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                logger.error("anthropic package not installed. Run: pip install anthropic")
                raise
        return self._client

    async def generate_response(
        self,
        incoming_message: str,
        conversation_history: List[Dict[str, Any]],
        lead_context: Dict[str, Any],
        current_state: str,
        qualification_data: Dict[str, Any] = None,
        lead_profile: Optional[LeadProfile] = None,
    ) -> GeneratedResponse:
        """
        Generate an AI response to a lead's message.

        Args:
            incoming_message: The message from the lead
            conversation_history: List of previous messages
            lead_context: Information about the lead (name, score, etc.)
            current_state: Current conversation state
            qualification_data: Data collected during qualification
            lead_profile: Optional rich LeadProfile for enhanced context

        Returns:
            GeneratedResponse with all details
        """
        start_time = time.time()
        warnings = []

        try:
            # Handle first contact (no incoming message)
            is_first_contact = lead_profile.is_first_contact if lead_profile else False
            if not incoming_message or not incoming_message.strip():
                if is_first_contact and lead_profile:
                    # Generate first contact message - tell AI to initiate conversation
                    incoming_message = "[FIRST CONTACT - Generate an opening message to this lead. They have NOT received any texts from us yet. Introduce yourself and start the conversation naturally.]"
                    warnings.append("Generating first contact message")
                else:
                    return self._create_fallback_response(
                        "empty_input",
                        "Thanks for reaching out! What can I help you with today?",
                        warnings=["Empty input message received"]
                    )

            # Handle follow-up sequence triggers (when lead hasn't responded)
            if incoming_message.startswith("[FOLLOWUP_SEQUENCE:"):
                # Parse the message type from trigger: [FOLLOWUP_SEQUENCE:value_with_cta]
                try:
                    followup_type = incoming_message.split(":")[1].rstrip("]").strip()
                except (IndexError, AttributeError):
                    followup_type = "gentle_followup"

                # Build follow-up specific instructions based on type
                followup_instructions = self._get_followup_instructions(followup_type, lead_profile)
                incoming_message = followup_instructions
                warnings.append(f"Generating follow-up message: {followup_type}")

            # Build the prompt with rich context
            system_prompt = self._build_system_prompt(
                lead_context=lead_context,
                current_state=current_state,
                qualification_data=qualification_data,
                lead_profile=lead_profile,
                conversation_history=conversation_history,
            )

            # Build conversation messages for context
            messages = self._build_messages(
                incoming_message=incoming_message,
                conversation_history=conversation_history,
            )

            # Debug: Log what we're sending to the model
            logger.info(f"[DEBUG] System prompt length: {len(system_prompt)} chars")
            logger.info(f"[DEBUG] Messages count: {len(messages)}")
            if messages:
                logger.info(f"[DEBUG] Last message: {messages[-1]}")

            # Generate response with retries
            response, model_used, tokens = await self._generate_with_retry(
                system_prompt=system_prompt,
                messages=messages,
            )

            # Parse and validate response
            parsed = self._parse_response(response)

            if not parsed:
                warnings.append("Failed to parse AI response - using fallback")
                return self._create_fallback_response(
                    "parse_error",
                    self._get_safe_fallback(current_state, lead_context),
                    warnings=warnings,
                )

            # Validate response quality
            quality, quality_warnings = self._validate_response_quality(
                parsed.get("response", ""),
                current_state,
                incoming_message,
            )
            warnings.extend(quality_warnings)

            # If quality is poor, try to improve or use fallback
            if quality == ResponseQuality.POOR:
                improved = self._improve_response(parsed.get("response", ""), current_state)
                if improved:
                    parsed["response"] = improved
                    quality = ResponseQuality.ACCEPTABLE
                    warnings.append("Response was improved due to quality issues")

            response_time = int((time.time() - start_time) * 1000)

            return GeneratedResponse(
                response_text=parsed.get("response", ""),
                next_state=parsed.get("next_state", current_state),
                extracted_info=parsed.get("extracted_info", {}),
                lead_score_delta=parsed.get("lead_score_delta", 0),
                should_handoff=parsed.get("should_handoff", False),
                handoff_reason=parsed.get("handoff_reason"),
                detected_intent=parsed.get("intent"),
                detected_sentiment=parsed.get("sentiment"),
                confidence=parsed.get("confidence", 0.8),
                tokens_used=tokens,
                response_time_ms=response_time,
                model_used=model_used,
                quality=quality,
                warnings=warnings,
            )

        except Exception as e:
            logger.error(f"Error generating AI response: {e}", exc_info=True)
            response_time = int((time.time() - start_time) * 1000)

            return self._create_fallback_response(
                "exception",
                self._get_safe_fallback(current_state, lead_context),
                warnings=[f"Exception during generation: {str(e)}"],
                response_time_ms=response_time,
            )

    async def generate_response_with_tools(
        self,
        incoming_message: str,
        conversation_history: List[Dict[str, Any]],
        lead_profile: LeadProfile,
        current_state: str,
        qualification_data: Dict[str, Any] = None,
    ) -> ToolResponse:
        """
        Generate a response using Claude tool use - lets AI choose the best action.

        Instead of code deciding whether to text, email, or create a task,
        this lets Claude analyze the context and choose the most appropriate action.

        Args:
            incoming_message: The message from the lead
            conversation_history: List of previous messages
            lead_profile: Rich LeadProfile with all lead context
            current_state: Current conversation state
            qualification_data: Data collected during qualification

        Returns:
            ToolResponse indicating which action to take and its parameters
        """
        start_time = time.time()

        try:
            # Build system prompt for tool use
            system_prompt = self._build_tool_use_system_prompt(
                lead_profile=lead_profile,
                current_state=current_state,
                qualification_data=qualification_data,
                conversation_history=conversation_history,
            )

            # Build conversation messages
            messages = self._build_messages(
                incoming_message=incoming_message,
                conversation_history=conversation_history,
            )

            # Generate with tool use
            response, model_used, tokens = await self._generate_with_tools(
                system_prompt=system_prompt,
                messages=messages,
            )

            response_time = int((time.time() - start_time) * 1000)

            return ToolResponse(
                action=response.get("action", "no_action"),
                parameters=response.get("parameters", {}),
                reasoning=response.get("reasoning"),
                tokens_used=tokens,
                response_time_ms=response_time,
                model_used=model_used,
            )

        except Exception as e:
            logger.error(f"Error generating tool response: {e}", exc_info=True)
            response_time = int((time.time() - start_time) * 1000)

            # Fallback to SMS with a safe message
            return ToolResponse(
                action="send_sms",
                parameters={
                    "message": self._get_safe_fallback(current_state, {"first_name": lead_profile.first_name}),
                    "urgency": "low"
                },
                reasoning=f"Fallback due to error: {str(e)}",
                tokens_used=0,
                response_time_ms=response_time,
                model_used="fallback",
            )

    def _build_tool_use_system_prompt(
        self,
        lead_profile: LeadProfile,
        current_state: str,
        qualification_data: Dict[str, Any] = None,
        conversation_history: List[Dict[str, Any]] = None,
    ) -> str:
        """Build system prompt optimized for tool use decisions with appointment focus."""
        personality_prompt = self.PERSONALITY_PROMPTS.get(
            self.personality,
            self.PERSONALITY_PROMPTS["friendly_casual"]
        ).format(max_sms_length=self.max_sms_length)

        state_guidance = self.STATE_GUIDANCE.get(current_state, "")
        context_section = self._build_rich_context(
            lead_profile, current_state, qualification_data, conversation_history
        )

        # Get effective agent name
        effective_name = self._get_effective_agent_name(lead_profile)

        # Add stage-aware guidance
        stage_guidance = self._get_stage_guidance(lead_profile.stage_name)

        # Build goal section based on lead type
        goal_section = self._build_goal_section(lead_profile)

        # Build known info section
        known_info_section = self._build_known_info_section(lead_profile)

        # Get source strategy
        source_strategy_section = ""
        if lead_profile.source:
            strategy = self._get_source_strategy(lead_profile.source)
            source_strategy_section = f"""
SOURCE STRATEGY ({lead_profile.source}):
- Approach: {strategy['approach']} | Urgency: {strategy['urgency']}
- {strategy['opener_hint']}
"""

        team_context = f" You work alongside {self.team_members}." if self.team_members else ""
        return f"""You are {effective_name}, a real estate assistant with {self.brokerage_name}.{team_context}

YOUR IDENTITY:
- Your name is ALWAYS {effective_name}. NEVER use any other name. NEVER invent a name.
- You are an AI text assistant who helps qualify leads and connect them with the right agent.
- You CANNOT show homes in person, attend appointments, or meet anyone face-to-face.
- When the lead is ready for showings or appointments, use create_task to hand off to a human agent.

{personality_prompt}

{goal_section}

APPOINTMENT STRATEGY:
- Every conversation should move toward booking an appointment
- Use assumptive closes: "Let's find a time" not "Would you like to schedule?"
- NEVER ask for information you already have
- When the lead agrees to a showing or appointment, use create_task to hand off to the human agent

{known_info_section}

{source_strategy_section}

{context_section}

STATE-SPECIFIC GUIDANCE:
{state_guidance}

{stage_guidance}

YOUR TASK:
Analyze the lead's message and choose the BEST action to take using the available tools.

DECISION GUIDELINES:
1. **send_sms**: Default for quick, conversational responses. Be substantive — acknowledge what they said, add value, ask one question.
2. **send_email**: Use for detailed info, property lists, or when lead prefers email.
3. **create_task**: When human agent needs to follow up - complex questions, call requests, frustrated leads, or lead is ready for showings/appointments.
4. **schedule_showing**: When lead is qualified and ready to meet. Use appointment_type="showing" for BUYERS (property tours), appointment_type="listing" for SELLERS (listing consultation/home valuation).
5. **add_note**: To document important info discovered (timeline, motivation, objections) without messaging.
6. **web_search**: When you need current info to answer questions - neighborhood data, school ratings, market trends, specific properties.
7. **no_action**: When message is just acknowledgment (ok, thanks) or no response is best.

COMBINATION EXAMPLES:
- Lead shares timeline info → add_note (document it) + send_sms (acknowledge and ask next question)
- Lead asks complex question → create_task (for agent) + send_sms (acknowledge, agent will follow up)
- BUYER qualified → create_task (for agent to schedule showing) + send_sms (let them know agent will set up showings)
- SELLER interested → create_task (for agent to schedule listing appt) + send_sms (let them know agent will reach out)
- Lead asks about schools → web_search (get current data) + send_sms (share relevant info)

CRITICAL - NEVER FABRICATE:
- NEVER invent property addresses, listings, prices, MLS numbers, or claim "off-market" inventory.
- You have ZERO access to MLS or listing data. If the lead asks about specific properties, say the team will pull matching listings.
- NEVER make up addresses. NEVER say a property "went pending" to cover a mistake.

Choose the action that best serves this lead's current needs and moves them toward an appointment."""

    def _get_stage_guidance(self, stage_name: str) -> str:
        """Get stage-specific guidance for tool selection."""
        if not stage_name:
            return ""

        stage_lower = stage_name.lower()

        # Blocked stages - should have been filtered before this, but add guidance anyway
        block_patterns = ["closed", "sold", "lost", "sphere", "trash", "not interested", "archived", "inactive"]
        if any(p in stage_lower for p in block_patterns):
            return f"""STAGE WARNING: Lead is in "{stage_name}" stage.
This stage typically should NOT receive AI outreach. Consider using no_action unless this is a response to their direct message."""

        # Handoff stages
        handoff_patterns = ["showing", "offer", "negotiat", "contract"]
        if any(p in stage_lower for p in handoff_patterns):
            return f"""STAGE: Lead is in "{stage_name}" stage - active transaction!
Prefer create_task to loop in human agent. Only send_sms for simple acknowledgments."""

        # Active stages
        if "search" in stage_lower or "active" in stage_lower:
            return f"""STAGE: Lead is in "{stage_name}" stage - actively looking!
Focus on providing value, answering questions, and moving toward schedule_showing when appropriate."""

        if "new" in stage_lower or "uncontacted" in stage_lower:
            return f"""STAGE: Lead is in "{stage_name}" stage - new lead!
Focus on warm introduction and beginning qualification. Use send_sms for conversational tone."""

        if "nurture" in stage_lower or "long term" in stage_lower:
            return f"""STAGE: Lead is in "{stage_name}" stage - long-term nurture.
Light touch approach. Don't push for appointments. Check in and provide market value."""

        if "past client" in stage_lower:
            return f"""STAGE: Lead is "{stage_name}" - a past client!
Warm, personal tone. Ask for referrals when appropriate. Celebrate their homeownership."""

        return ""

    async def _generate_with_tools(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
    ) -> Tuple[Dict[str, Any], str, int]:
        """
        Generate response using Claude tool use.

        Returns:
            Tuple of (tool_response_dict, model_used, tokens_used)
        """
        models_to_try = [self.PRIMARY_MODEL, self.FALLBACK_MODEL]
        last_error = None

        for model in models_to_try:
            for attempt in range(self.MAX_RETRIES):
                try:
                    response = self.client.messages.create(
                        model=model,
                        max_tokens=self.MAX_TOKENS,
                        system=system_prompt,
                        tools=self.AVAILABLE_TOOLS,
                        tool_choice={"type": "auto"},
                        messages=messages,
                    )

                    tokens_used = response.usage.input_tokens + response.usage.output_tokens
                    self._total_tokens_used += tokens_used
                    self._request_count += 1

                    # Parse tool use from response
                    tool_response = {"action": "no_action", "parameters": {}, "reasoning": None}

                    for block in response.content:
                        if hasattr(block, 'type') and block.type == "tool_use":
                            tool_response = {
                                "action": block.name,
                                "parameters": block.input,
                                "reasoning": f"Tool selected: {block.name}"
                            }
                            break
                        elif hasattr(block, 'type') and block.type == "text":
                            # If Claude responded with text instead of tool, wrap in send_sms
                            if block.text.strip():
                                tool_response = {
                                    "action": "send_sms",
                                    "parameters": {"message": block.text[:self.max_sms_length], "urgency": "medium"},
                                    "reasoning": "Text response converted to SMS"
                                }

                    logger.info(f"Tool response generated with {model}: {tool_response['action']}, tokens: {tokens_used}")
                    return tool_response, model, tokens_used

                except Exception as e:
                    last_error = e
                    error_str = str(e).lower()

                    if "rate" in error_str or "overload" in error_str or "529" in error_str:
                        delay = min(self.BASE_RETRY_DELAY * (2 ** attempt), self.MAX_RETRY_DELAY)
                        logger.warning(f"Rate limited, retrying in {delay}s (attempt {attempt + 1})")
                        time.sleep(delay)
                        continue

                    logger.error(f"Error with {model} tool use: {e}")
                    break

        raise Exception(f"All tool generation attempts failed. Last error: {last_error}")

    def _build_system_prompt(
        self,
        lead_context: Dict[str, Any],
        current_state: str,
        qualification_data: Dict[str, Any] = None,
        lead_profile: Optional[LeadProfile] = None,
        conversation_history: List[Dict[str, Any]] = None,
    ) -> str:
        """
        Build comprehensive system prompt with rich lead context.

        This is the key method for providing excellent context to the LLM.
        The more relevant context we provide, the better the conversation.
        Includes appointment-focused goal-driven messaging.
        Now includes conversation intelligence to avoid repeating questions.
        """
        personality_prompt = self.PERSONALITY_PROMPTS.get(
            self.personality,
            self.PERSONALITY_PROMPTS["friendly_casual"]
        ).format(max_sms_length=self.max_sms_length)

        state_guidance = self.STATE_GUIDANCE.get(current_state, "")

        # Use rich lead profile if available, otherwise fall back to basic context
        if lead_profile:
            context_section = self._build_rich_context(
                lead_profile, current_state, qualification_data, conversation_history
            )
        else:
            context_section = self._build_basic_context(lead_context, current_state, qualification_data)

        # Get effective agent name (either branded name or assigned agent's first name)
        effective_name = self._get_effective_agent_name(lead_profile)

        # Build goal section based on lead type (seller/buyer)
        goal_section = self._build_goal_section(lead_profile)

        # Build known info section to prevent redundant questions
        known_info_section = ""
        if lead_profile:
            known_info_section = self._build_known_info_section(lead_profile)

        # Get source-specific strategy with friendly display name
        source_strategy_section = ""
        if lead_profile and lead_profile.source:
            friendly_source = get_friendly_source_name(lead_profile.source)
            strategy = self._get_source_strategy(lead_profile.source)
            source_strategy_section = f"""
SOURCE STRATEGY ({friendly_source}):
- Display this source as: "{friendly_source}" (not "{lead_profile.source}")
- Approach: {strategy['approach']}
- Urgency: {strategy['urgency']}
- Context: {strategy['context']}
- Opener hint: {strategy['opener_hint']}
"""

        # Build the complete prompt with appointment focus
        team_context = f" You work alongside {self.team_members}." if self.team_members else ""
        return f"""You are {effective_name}, a real estate assistant with {self.brokerage_name}.{team_context}

YOUR IDENTITY - READ THIS FIRST:
- Your name is ALWAYS {effective_name}. NEVER use any other name. NEVER invent a name.
- You are an AI text assistant who helps qualify leads and connect them with the right agent.
- You CANNOT show homes in person, attend appointments, or meet anyone face-to-face.
- When the lead asks to see properties or schedule showings, connect them with a human agent on the team.
- NEVER say "I'll show you" or "I'll be there" — instead say things like "Let me get you connected with someone on the team to show you around" or "I'll have one of our agents set that up for you."

{personality_prompt}

{goal_section}

CRITICAL RULE - READ THIS FIRST:
- NEVER ask about something that is already marked as [KNOWN] in the "INFORMATION WE ALREADY HAVE" section below
- If pre-approval status is [KNOWN], DO NOT ask about pre-approval or financing
- If location is [KNOWN], DO NOT ask what area they're looking in
- If timeline is [KNOWN], DO NOT ask when they're looking to move
- If they already answered a question in the conversation history, DO NOT ask it again. Read the history carefully.
- VIOLATION OF THIS RULE IS A FAILURE

APPOINTMENT STRATEGY:
- Be consultative and helpful, but EVERY conversation should move toward booking an appointment
- Ask qualifying questions to understand their situation, then transition to scheduling
- Use assumptive closes: "Let's find a time that works for you" not "Would you like to schedule?"
- If they hesitate, address the concern, then circle back to scheduling
- Since you already know their pre-approval status and areas, move directly to scheduling
- When the lead agrees to a showing or appointment, set should_handoff=true and next_state="handed_off" so the human agent can take over

WHAT SUCCESS LOOKS LIKE:
- Seller: "I'll have [agent name] reach out to schedule your listing consultation!"
- Buyer: "Let me have [agent name] set up some showings for you this weekend!"

{known_info_section}

{source_strategy_section}

{context_section}

STATE-SPECIFIC GUIDANCE:
{state_guidance}

CRITICAL RULES:
1. RESPONSE LENGTH: Be substantive (2-4 sentences) — acknowledge what they said, add value, and ask one clear question.
2. ONE QUESTION: Ask only ONE question per message
3. NO PRESSURE: Never use high-pressure tactics or artificial urgency
4. DON'T REPEAT: NEVER ask a question that was already asked or answered in the conversation history. Read the history above carefully before asking anything. If the lead says "I told you" or seems frustrated by repetition, acknowledge it and move forward.
5. HANDOFF TRIGGERS: Set should_handoff=true AND next_state="handed_off" if:
   - They explicitly ask for a human/real person
   - They seem frustrated, angry, or use profanity
   - They mention legal issues, complaints, or threats
   - The conversation is going in circles
   - They have complex questions you can't answer
   - They agree to a showing, appointment, tour, or meeting (e.g. "Saturday works", "I'm free at 10", "Let's do it")
   - They want to see specific properties or ask for addresses/listings
   - They ask who will show them homes or want to meet someone in person
6. EXTRACT INFO: Parse their messages for timeline, budget, location, pre-approval status
7. NATURAL FLOW: Reference their previous answers to show you're listening
8. PERSONALIZE: Use the lead profile info to make responses relevant and personal
9. NEVER FABRICATE: Do NOT invent property addresses, listings, prices, MLS numbers, or claim "off-market" inventory. You have ZERO access to MLS or listing data. If the lead asks about specific properties, say the team will pull matching listings for them. NEVER make up addresses. NEVER say a property "went pending" to cover a mistake. If you don't have the info, say so honestly.
10. YOUR NAME: You are {effective_name}. NEVER use a different name. NEVER invent a name.
11. BE HUMAN: When someone shares life circumstances (divorce, death, job change, financial stress, growing family, health issues), acknowledge it with genuine empathy FIRST. Don't skip past emotional moments to ask qualifying questions. People remember how you made them feel.

RESPONSE FORMAT:
You must respond with ONLY valid JSON (no markdown, no code blocks, no explanation):
{{
    "response": "Your SMS message here (2-4 sentences, substantive and personal)",
    "next_state": "initial|qualifying|objection_handling|scheduling|nurture|handed_off",
    "extracted_info": {{
        "timeline": null or "30_days|60_days|90_days|6_months|1_year|just_browsing",
        "budget": null or "$XXXk-$XXXk",
        "location": null or "area name",
        "pre_approved": null or true or false,
        "motivation": null or "job_relocation|growing_family|downsizing|investment|other",
        "property_type": null or "single_family|condo|townhouse|multi_family"
    }},
    "lead_score_delta": -10 to +15 (based on engagement/qualification),
    "should_handoff": false,
    "handoff_reason": null or "reason for handoff",
    "intent": "greeting|question|objection|interest|scheduling|human_request|frustration|other",
    "sentiment": "positive|neutral|negative|frustrated",
    "confidence": 0.0 to 1.0
}}"""

    def _build_rich_context(
        self,
        profile: LeadProfile,
        current_state: str,
        qualification_data: Dict[str, Any] = None,
        conversation_history: List[Dict[str, Any]] = None,
    ) -> str:
        """
        Build rich context string from LeadProfile.

        This provides the LLM with comprehensive information for personalized responses.
        Now includes conversation history intelligence to avoid repeating questions.
        """
        sections = []

        # Start with the profile's built-in context
        sections.append(profile.to_context_string())

        # Add conversation state context
        sections.append(f"\nCURRENT CONVERSATION STATE: {current_state}")

        # Add qualification progress if available
        if qualification_data:
            qual_summary = self._build_qualification_summary(qualification_data)
            if qual_summary:
                sections.append(qual_summary)

        # NEW: Add conversation history intelligence
        if conversation_history:
            conv_intelligence = self._build_conversation_intelligence_section(
                conversation_history, profile
            )
            if conv_intelligence:
                sections.append("\n" + conv_intelligence)

        # Add strategic hints based on profile
        hints = self._generate_conversation_hints(profile, current_state)
        if hints:
            sections.append("\nCONVERSATION STRATEGY HINTS:\n" + "\n".join(f"  - {h}" for h in hints))

        return "\n".join(sections)

    def _build_basic_context(
        self,
        lead_context: Dict[str, Any],
        current_state: str,
        qualification_data: Dict[str, Any] = None,
    ) -> str:
        """Build basic context when LeadProfile is not available."""
        lead_name = lead_context.get("first_name", "there")
        lead_score = lead_context.get("score", 0)
        lead_source = lead_context.get("source", "unknown")

        score_label = "Hot" if lead_score >= 70 else "Warm" if lead_score >= 40 else "Cold"

        context_section = f"""
LEAD INFORMATION:
- Name: {lead_name}
- Score: {lead_score}/100 ({score_label} lead)
- Source: {lead_source}
- Current State: {current_state}"""

        # Add qualification data if available
        if qualification_data:
            qual_summary = self._build_qualification_summary(qualification_data)
            if qual_summary:
                context_section += "\n" + qual_summary

        return context_section

    def _build_qualification_summary(self, qualification_data: Dict[str, Any]) -> str:
        """Build qualification data summary for prompt."""
        qual_items = []
        if qualification_data.get("timeline"):
            qual_items.append(f"- Timeline: {qualification_data['timeline']}")
        if qualification_data.get("budget"):
            qual_items.append(f"- Budget: {qualification_data['budget']}")
        if qualification_data.get("location") or qualification_data.get("location_preferences"):
            loc = qualification_data.get("location") or ", ".join(qualification_data.get("location_preferences", []))
            qual_items.append(f"- Location preference: {loc}")
        if qualification_data.get("pre_approved") is not None or qualification_data.get("is_pre_approved") is not None:
            pre_app = qualification_data.get("pre_approved") or qualification_data.get("is_pre_approved")
            qual_items.append(f"- Pre-approved: {'Yes' if pre_app else 'No'}")
        if qualification_data.get("motivation"):
            qual_items.append(f"- Motivation: {qualification_data['motivation']}")
        if qualification_data.get("property_type") or qualification_data.get("property_types"):
            pt = qualification_data.get("property_type") or ", ".join(qualification_data.get("property_types", []))
            qual_items.append(f"- Property type: {pt}")

        if not qual_items:
            return ""

        result = "\nQUALIFICATION DATA COLLECTED:\n" + "\n".join(qual_items)

        # Show what's still missing
        missing = []
        if not qualification_data.get("timeline"):
            missing.append("timeline")
        if not qualification_data.get("budget") and not qualification_data.get("price_max"):
            missing.append("budget")
        if not qualification_data.get("location") and not qualification_data.get("location_preferences"):
            missing.append("location")
        if qualification_data.get("pre_approved") is None and qualification_data.get("is_pre_approved") is None:
            missing.append("pre-approval status")

        if missing:
            result += f"\n\nSTILL NEED TO LEARN: {', '.join(missing)}"

        return result

    def _analyze_conversation_history(
        self,
        conversation_history: List[Dict[str, Any]],
        lead_profile: Optional[LeadProfile] = None,
    ) -> Dict[str, Any]:
        """
        Analyze conversation history to extract intelligence about the conversation.

        This prevents the AI from:
        - Asking questions that were already answered
        - Repeating the same messages
        - Ignoring context from previous exchanges

        Returns a dict with:
        - questions_asked: List of qualification questions already asked
        - information_shared: Dict of info the lead has shared
        - topics_covered: List of topics discussed
        - last_ai_action: What the AI did last (asked question, made offer, etc.)
        - conversation_tone: The overall tone (warm, cold, frustrated)
        """
        analysis = {
            "questions_asked": [],
            "information_shared": {},
            "topics_covered": set(),
            "last_ai_action": None,
            "conversation_tone": "neutral",
            "ai_messages_count": 0,
            "lead_messages_count": 0,
        }

        if not conversation_history:
            return analysis

        # Question patterns to detect what we've already asked
        timeline_questions = ["when", "timeline", "how soon", "when are you", "time frame", "how long"]
        budget_questions = ["budget", "price range", "how much", "afford", "spend"]
        preapproval_questions = ["pre-approved", "pre approval", "preapproved", "lender", "financing"]
        location_questions = ["where", "area", "neighborhood", "city", "looking in"]
        motivation_questions = ["why", "what's bringing", "reason", "motivation", "what made you"]

        # Patterns indicating specific info was shared by lead
        timeline_shared_patterns = ["month", "week", "asap", "soon", "immediately", "year", "ready now"]
        budget_shared_patterns = ["$", "k", "thousand", "million", "budget is", "looking around"]
        location_shared_patterns = ["in ", "near", "area", "neighborhood", "zip", "city"]

        positive_sentiment = ["thanks", "great", "awesome", "sounds good", "yes", "definitely", "love"]
        negative_sentiment = ["no", "not interested", "stop", "busy", "later", "already have"]

        for msg in conversation_history:
            direction = msg.get("direction", "")
            content = (msg.get("content", "") or "").lower()

            if direction == "outbound":
                analysis["ai_messages_count"] += 1

                # Check what questions were asked
                if any(q in content for q in timeline_questions):
                    analysis["questions_asked"].append("timeline")
                    analysis["topics_covered"].add("timeline")
                if any(q in content for q in budget_questions):
                    analysis["questions_asked"].append("budget")
                    analysis["topics_covered"].add("budget")
                if any(q in content for q in preapproval_questions):
                    analysis["questions_asked"].append("pre_approval")
                    analysis["topics_covered"].add("financing")
                if any(q in content for q in location_questions):
                    analysis["questions_asked"].append("location")
                    analysis["topics_covered"].add("location")
                if any(q in content for q in motivation_questions):
                    analysis["questions_asked"].append("motivation")
                    analysis["topics_covered"].add("motivation")

                # Detect last AI action
                if "?" in content:
                    analysis["last_ai_action"] = "asked_question"
                elif any(w in content for w in ["schedule", "appointment", "meet", "showing", "free"]):
                    analysis["last_ai_action"] = "proposed_appointment"
                elif any(w in content for w in ["market", "listing", "price", "sold"]):
                    analysis["last_ai_action"] = "provided_market_info"

            elif direction == "inbound":
                analysis["lead_messages_count"] += 1

                # Check what info lead shared
                if any(p in content for p in timeline_shared_patterns):
                    analysis["information_shared"]["timeline_mentioned"] = True
                if any(p in content for p in budget_shared_patterns):
                    analysis["information_shared"]["budget_mentioned"] = True
                if any(p in content for p in location_shared_patterns):
                    analysis["information_shared"]["location_mentioned"] = True

                # Track sentiment
                if any(w in content for w in positive_sentiment):
                    analysis["conversation_tone"] = "positive"
                elif any(w in content for w in negative_sentiment):
                    analysis["conversation_tone"] = "cold"

        analysis["topics_covered"] = list(analysis["topics_covered"])
        return analysis

    def _build_conversation_intelligence_section(
        self,
        conversation_history: List[Dict[str, Any]],
        lead_profile: Optional[LeadProfile] = None,
    ) -> str:
        """
        Build a section for the prompt that provides conversation intelligence.

        This tells the AI exactly what has already happened so it doesn't repeat itself.
        """
        analysis = self._analyze_conversation_history(conversation_history, lead_profile)

        sections = []

        # Show what questions have already been asked
        if analysis["questions_asked"]:
            unique_questions = list(set(analysis["questions_asked"]))
            sections.append(
                f"QUESTIONS ALREADY ASKED (do NOT ask these again):\n" +
                "\n".join(f"  - {q.replace('_', ' ').title()}" for q in unique_questions)
            )

        # Show what the lead has shared
        if analysis["information_shared"]:
            shared_items = []
            if analysis["information_shared"].get("timeline_mentioned"):
                shared_items.append("They mentioned their timeline")
            if analysis["information_shared"].get("budget_mentioned"):
                shared_items.append("They mentioned budget/price")
            if analysis["information_shared"].get("location_mentioned"):
                shared_items.append("They mentioned location preferences")
            if shared_items:
                sections.append(
                    f"INFORMATION LEAD HAS SHARED:\n" +
                    "\n".join(f"  - {item}" for item in shared_items)
                )

        # Provide guidance based on last AI action
        if analysis["last_ai_action"] == "asked_question":
            sections.append("LAST ACTION: You asked a question. If they answered, acknowledge their answer FIRST before asking anything else.")
        elif analysis["last_ai_action"] == "proposed_appointment":
            sections.append("LAST ACTION: You proposed an appointment. If they're responding to that, handle their response appropriately.")

        # Show conversation statistics
        if analysis["ai_messages_count"] > 0 or analysis["lead_messages_count"] > 0:
            sections.append(
                f"CONVERSATION STATUS:\n" +
                f"  - Your messages sent: {analysis['ai_messages_count']}\n" +
                f"  - Lead responses: {analysis['lead_messages_count']}\n" +
                f"  - Overall tone: {analysis['conversation_tone']}"
            )

        return "\n\n".join(sections) if sections else ""

    def _generate_conversation_hints(self, profile: LeadProfile, current_state: str) -> List[str]:
        """
        Generate strategic conversation hints based on lead profile.

        These hints help the LLM make more relevant, personalized responses.
        Includes lead status classification for appropriate messaging strategy.
        """
        hints = []

        # PRIORITY 1: Lead status hints - this sets the tone for the entire conversation
        lead_status = self._classify_lead_status(profile)

        if lead_status == "new_hot":
            hints.append("NEW LEAD - Respond quickly! First response sets the tone. Introduce yourself, acknowledge their interest, move toward scheduling appointment.")
        elif lead_status == "dormant_reengaging":
            hints.append(f"RE-ENGAGEMENT - Lead hasn't been contacted recently ({profile.days_since_created} days old). Acknowledge the gap naturally ('Hey! Just checking in...'), offer fresh value, re-propose appointment.")
        elif lead_status == "active_engaged":
            hints.append("ENGAGED LEAD - They're responsive! Keep momentum, qualify remaining questions, then close for appointment with specific times.")
        elif lead_status == "active_nurturing":
            hints.append("ACTIVE CONVERSATION - Continue building rapport, address any concerns, guide toward appointment when ready.")
        elif lead_status == "warm_following_up":
            hints.append("FOLLOW-UP - Gentle check-in, provide value, keep appointment option open.")

        # PRIORITY 2: Lead type hints - CRITICAL for conversation approach
        if profile.lead_type == "both":
            hints.append("BUYER AND SELLER - Goal: Book COMBINED consultation. They're making a coordinated move! Focus on: timeline for BOTH transactions, sell first vs buy first, coordinate both sides. DO NOT ask if buying or selling - we know they're doing BOTH!")
        elif profile.lead_type == "seller":
            hints.append("SELLER LEAD - Goal: Book LISTING appointment. Focus on: their timeline to sell, property condition, pricing expectations.")
        elif profile.lead_type == "buyer":
            hints.append("BUYER LEAD - Goal: Book SHOWING appointment. Focus on: pre-approval, timeline, must-haves, preferred areas.")

        # Source-based hints
        if profile.interested_property_address:
            hints.append(f"Interested in specific property ({profile.interested_property_address}) - offer to show it or discuss it!")

        if profile.source:
            source_lower = profile.source.lower()
            if "zillow" in source_lower:
                hints.append("Zillow lead - they're likely comparing agents. Differentiate yourself with responsiveness and local expertise.")
            elif "referral" in source_lower or "homelight" in source_lower:
                hints.append("Referral lead - warm introduction, they expect quick response. Move to appointment fast.")

        # Timeline-based hints
        if profile.timeline == "immediate":
            hints.append("URGENT: They're ready now! Focus on scheduling a showing or call ASAP")
        elif profile.timeline == "long":
            hints.append("Long timeline - focus on building relationship, don't push for appointment yet")

        # Financial hints
        if profile.is_pre_approved is False:
            hints.append("They're not pre-approved - offer to connect them with a lender")
        elif profile.is_pre_approved and profile.pre_approval_amount:
            hints.append(f"They're pre-approved for ${profile.pre_approval_amount:,} - they're serious!")

        # Objection awareness
        if profile.previous_objections:
            obj_str = ", ".join(profile.previous_objections[:2])
            hints.append(f"Previous objections: {obj_str} - address carefully if they come up again")

        # Engagement-based hints
        if profile.engagement_level == "high":
            hints.append("Highly engaged lead - they're responsive, keep momentum going!")
        elif profile.engagement_level == "low":
            hints.append("Low engagement so far - keep messages short and value-focused")

        # Household considerations
        if profile.decision_makers and "spouse" in profile.decision_makers.lower():
            hints.append("Spouse involved in decision - offer to include them in conversations")

        if profile.has_children:
            hints.append("They have kids - school districts may be important to discuss")

        if profile.has_pets:
            hints.append("They have pets - yard size and HOA pet policies may matter")

        # State-specific hints
        if current_state == "qualifying" and profile.score >= 60:
            hints.append("Score is warming up - if qualified, transition to scheduling")

        if current_state == "scheduling" and not profile.scheduled_appointments:
            hints.append("No appointments yet - offer specific time options")

        # Lead age hints
        if profile.days_since_created > 30 and profile.engagement_level != "high":
            hints.append("Lead is over 30 days old with low engagement - try a re-engagement approach")

        return hints[:5]  # Limit to 5 most relevant hints

    def _build_system_prompt_legacy(
        self,
        lead_context: Dict[str, Any],
        current_state: str,
        qualification_data: Dict[str, Any] = None,
    ) -> str:
        """Legacy prompt builder - kept for backwards compatibility."""
        return self._build_system_prompt(lead_context, current_state, qualification_data, None)

    def _build_messages(
        self,
        incoming_message: str,
        conversation_history: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        """Build message list for API call with proper context."""
        messages = []

        # Add relevant conversation history (last N messages)
        history = conversation_history[-self.MAX_CONTEXT_MESSAGES:]

        for msg in history:
            role = "user" if msg.get("direction") == "inbound" else "assistant"
            content = msg.get("content", "")

            # For assistant messages, wrap in a simple format
            if role == "assistant":
                # Pretend previous AI responses were just the text
                messages.append({
                    "role": "assistant",
                    "content": json.dumps({"response": content})
                })
            else:
                messages.append({
                    "role": "user",
                    "content": f"Lead said: {content}"
                })

        # Add current message
        messages.append({
            "role": "user",
            "content": f"Lead said: {incoming_message}"
        })

        return messages

    async def _throttle_request(self):
        """
        Throttle requests to avoid rate limiting.

        Ensures minimum interval between requests with random jitter
        to prevent thundering herd problems.
        """
        import time
        import random

        current_time = time.time()
        elapsed = current_time - self._last_request_time
        min_interval = self.MIN_REQUEST_INTERVAL + random.uniform(0, self.REQUEST_JITTER)

        if elapsed < min_interval:
            sleep_time = min_interval - elapsed
            logger.debug(f"Throttling request, sleeping {sleep_time:.2f}s")
            await asyncio.sleep(sleep_time)

        self._last_request_time = time.time()

    async def _generate_with_openrouter(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        model: str,
    ) -> Tuple[str, str, int]:
        """
        Generate response using OpenRouter API (OpenAI-compatible).

        Returns:
            Tuple of (response_text, model_used, tokens_used)
        """
        import aiohttp

        # Throttle to avoid rate limits
        await self._throttle_request()

        # Convert messages to OpenAI format
        openai_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            openai_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://leadsynergy.ai",
            "X-Title": "LeadSynergy AI Agent"
        }

        payload = {
            "model": model,
            "messages": openai_messages,
            "max_tokens": self.MAX_TOKENS,
            "temperature": 0.7,
            # Explicitly disable web search to avoid $0.02/request charges
            # See: https://openrouter.ai/docs/guides/features/plugins/web-search
            "plugins": [{"id": "web", "enabled": False}],
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"OpenRouter API error {response.status}: {error_text}")

                data = await response.json()

                # Extract response
                response_text = data["choices"][0]["message"]["content"]
                tokens_used = data.get("usage", {}).get("total_tokens", 0)

                # Debug logging to diagnose response issues
                logger.info(f"[DEBUG] OpenRouter raw response text (first 500 chars): {response_text[:500] if response_text else 'EMPTY'}")
                if "hidden" in response_text.lower() or "privacy" in response_text.lower():
                    logger.warning(f"[DEBUG] PRIVACY PLACEHOLDER DETECTED in response!")
                    logger.warning(f"[DEBUG] Full response: {response_text}")
                    logger.warning(f"[DEBUG] System prompt length: {len(system_prompt)} chars")
                    logger.warning(f"[DEBUG] Messages count: {len(openai_messages)}")
                    # Log last user message content
                    if openai_messages:
                        last_msg = openai_messages[-1]
                        logger.warning(f"[DEBUG] Last message role: {last_msg.get('role')}, content: {last_msg.get('content', '')[:200]}")

                return response_text, model, tokens_used

    async def _generate_with_retry(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
    ) -> Tuple[str, str, int]:
        """
        Generate response with retry logic and model fallback.
        Supports both Anthropic and OpenRouter APIs.

        Returns:
            Tuple of (response_text, model_used, tokens_used)
        """
        # Use configured models (set in __init__ based on provider/settings)
        models_to_try = [self.primary_model, self.fallback_model]

        last_error = None

        for model in models_to_try:
            for attempt in range(self.MAX_RETRIES):
                try:
                    if self.use_openrouter:
                        # Use OpenRouter API
                        response_text, model_used, tokens_used = await self._generate_with_openrouter(
                            system_prompt, messages, model
                        )
                    else:
                        # Use Anthropic API
                        response = self.client.messages.create(
                            model=model,
                            max_tokens=self.MAX_TOKENS,
                            system=system_prompt,
                            messages=messages,
                        )
                        response_text = response.content[0].text
                        tokens_used = response.usage.input_tokens + response.usage.output_tokens
                        model_used = model

                    # Track usage
                    self._total_tokens_used += tokens_used
                    self._request_count += 1

                    logger.info(f"AI response generated with {model_used}, tokens: {tokens_used}")
                    return response_text, model_used, tokens_used

                except Exception as e:
                    last_error = e
                    error_str = str(e).lower()

                    # Log full error for debugging
                    logger.error(f"[AI ERROR] Model {model}, attempt {attempt + 1}: {e}")

                    # Check if it's a rate limit or overload error
                    if "rate" in error_str or "overload" in error_str or "529" in error_str:
                        delay = min(
                            self.BASE_RETRY_DELAY * (2 ** attempt),
                            self.MAX_RETRY_DELAY
                        )
                        logger.warning(f"Rate limited, retrying in {delay}s (attempt {attempt + 1})")
                        time.sleep(delay)
                        continue

                    # For other errors, log and try next model
                    logger.error(f"Error with {model}: {e}")
                    break

        # All retries failed
        raise Exception(f"All generation attempts failed. Last error: {last_error}")

    def _parse_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse AI response with robust error handling."""
        try:
            # Clean up response
            text = response_text.strip()

            # Handle markdown code blocks
            if text.startswith("```"):
                # Extract content between code blocks
                parts = text.split("```")
                if len(parts) >= 2:
                    text = parts[1]
                    # Remove language identifier if present
                    if text.startswith("json"):
                        text = text[4:]
                    text = text.strip()

            # Try to parse JSON
            parsed = json.loads(text)

            # Validate required fields
            if "response" not in parsed:
                logger.warning("Parsed response missing 'response' field")
                return None

            # Set defaults for missing fields
            parsed.setdefault("next_state", "qualifying")
            parsed.setdefault("extracted_info", {})
            parsed.setdefault("lead_score_delta", 0)
            parsed.setdefault("should_handoff", False)
            parsed.setdefault("handoff_reason", None)
            parsed.setdefault("intent", "other")
            parsed.setdefault("sentiment", "neutral")
            parsed.setdefault("confidence", 0.8)

            return parsed

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.debug(f"Raw response: {response_text[:500]}")

            # Try to extract just the response text using regex
            match = re.search(r'"response"\s*:\s*"([^"]+)"', response_text)
            if match:
                return {
                    "response": match.group(1),
                    "next_state": "qualifying",
                    "extracted_info": {},
                    "lead_score_delta": 0,
                    "should_handoff": False,
                    "intent": "other",
                    "sentiment": "neutral",
                    "confidence": 0.5,
                }

            return None

    def _validate_response_quality(
        self,
        response: str,
        current_state: str,
        incoming_message: str,
    ) -> Tuple[ResponseQuality, List[str]]:
        """Validate response quality and return warnings."""
        warnings = []

        if not response:
            return ResponseQuality.FAILED, ["Empty response"]

        # Check length
        if len(response) > self.max_sms_length:
            warnings.append(f"Response too long ({len(response)} chars, max {self.max_sms_length})")

        if len(response) < self.MIN_RESPONSE_LENGTH:
            warnings.append(f"Response too short ({len(response)} chars)")
            return ResponseQuality.POOR, warnings

        # Check for problematic patterns
        problematic_patterns = [
            (r'\{|\}', "Contains JSON brackets"),
            (r'"response"', "Contains JSON field name"),
            (r'```', "Contains code blocks"),
            (r'I am an AI|I\'m an AI|as an AI', "Reveals AI nature"),
            (r'I cannot|I can\'t help', "Refusal pattern"),
        ]

        for pattern, warning in problematic_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                warnings.append(warning)

        # Check for multiple questions
        question_marks = response.count("?")
        if question_marks > 1:
            warnings.append(f"Multiple questions detected ({question_marks})")

        # Check for high-pressure language
        pressure_words = ["act now", "limited time", "hurry", "don't miss", "last chance"]
        for word in pressure_words:
            if word.lower() in response.lower():
                warnings.append(f"High-pressure language detected: {word}")

        # Determine quality
        if len(warnings) == 0 and len(response) <= self.max_sms_length:
            return ResponseQuality.EXCELLENT, warnings
        elif len(warnings) <= 1 and len(response) <= self.max_sms_length + 20:
            return ResponseQuality.GOOD, warnings
        elif len(warnings) <= 2:
            return ResponseQuality.ACCEPTABLE, warnings
        else:
            return ResponseQuality.POOR, warnings

    def _improve_response(self, response: str, current_state: str) -> Optional[str]:
        """Attempt to improve a poor quality response."""
        # Truncate if too long
        if len(response) > self.max_sms_length:
            # Try to truncate at a natural break point
            truncated = response[:self.max_sms_length]

            # Find last complete sentence
            last_period = truncated.rfind(".")
            last_question = truncated.rfind("?")
            last_exclaim = truncated.rfind("!")

            break_point = max(last_period, last_question, last_exclaim)

            if break_point > self.max_sms_length // 2:
                return truncated[:break_point + 1]

            # Just truncate with ellipsis
            return truncated[:self.max_sms_length - 3] + "..."

        return response

    def _get_followup_instructions(
        self,
        followup_type: str,
        lead_profile: Optional[LeadProfile] = None,
    ) -> str:
        """
        Generate instructions for follow-up messages when lead hasn't responded.

        This tells the AI to generate an OUTBOUND follow-up message, not respond
        to an incoming message. Each follow-up type has specific goals and tone.

        Args:
            followup_type: Type of follow-up (value_with_cta, qualify_motivation, etc.)
            lead_profile: Lead profile for personalization

        Returns:
            Instruction string for the AI to generate appropriate follow-up
        """
        first_name = lead_profile.first_name if lead_profile else "there"
        area = ""
        if lead_profile:
            if lead_profile.preferred_cities:
                area = lead_profile.preferred_cities[0]
            elif lead_profile.preferred_neighborhoods:
                area = lead_profile.preferred_neighborhoods[0]

        # Base context - sound like a REAL PERSON, not a robot or salesperson
        base_context = f"""[FOLLOW-UP - {first_name} hasn't replied yet. Send another message.]

CRITICAL RULES:
- Sound like a real human texting a friend, NOT a salesperson or robot
- Keep it short (1-2 sentences max)
- Don't be pushy or desperate
- Use contractions (I'm, you're, what's) - nobody texts formally
- Don't start every message with "Hey {first_name}!" - mix it up
- NO corporate buzzwords: "checking in", "touching base", "following up", "reaching out"
- NO robotic phrases: "curious what sparked", "driving your search", "I wanted to"
- NEVER mention specific properties, addresses, prices, or "off-market" listings you don't have data for

"""

        # Type-specific instructions - all focused on sounding HUMAN
        instructions = {
            "value_with_cta": f"""{base_context}Send a message offering to chat + suggest a time:

GOOD examples:
- "Got some time Thursday if you wanna talk about {area or 'the market'}. Work for you?"
- "Free this week if you want to hop on a quick call - maybe Thursday?"
- "I can fill you in on what's happening in {area or 'the area'} if you've got 10 min this week"

BAD (don't say):
- "I have availability" (too formal)
- "Would Thursday afternoon work for a quick call?" (sounds scripted)
- "I'd love to chat" (salesy)""",

            "qualify_motivation": f"""{base_context}Ask why they're looking to buy/move - be casual about it:

GOOD examples:
- "What's making you want to move?"
- "Job change, growing family, or just ready for something new?"
- "What's the move for - work thing or just want a change?"

BAD (don't say):
- "Curious what sparked your interest" (robotic af)
- "What's driving your home search?" (sounds like a survey)
- "I'd love to learn more about your situation" (too formal)""",

            "email_market_report": f"""{base_context}Share something useful about the {area or 'local'} market:

GOOD examples:
- "Saw some interesting stuff in {area or 'the area'} this week - prices are holding but more homes coming on. Want me to send you what I'm seeing?"
- "Quick heads up - {area or 'the market'} is getting a bit more inventory lately. Good sign if you're still looking."

Keep it conversational, not like a formal report.""",

            "social_proof": f"""{base_context}Mention you helped someone recently (but don't be braggy):

GOOD examples:
- "Just got a buyer into a place in {area or 'the area'} last week - market's moving! Lmk if you want to chat"
- "Helped someone close on a great spot nearby - made me think of you. Still looking?"

BAD (don't say):
- "I've helped many clients" (braggy)
- "I have extensive experience" (formal/braggy)""",

            "strategic_breakup": f"""{base_context}This is your last message for a while - be real and give them an easy out:

GOOD examples:
- "Hey - gonna back off for now, but no hard feelings! If things change or you have questions later, I'm around"
- "I'll give you some space - just let me know if you ever want to pick this back up"
- "Stepping back for now. If your situation changes, hit me up - if not, no worries at all"

This message often gets the BEST response rate because there's no pressure. Keep it genuine.""",

            "gentle_followup": f"""{base_context}Quick casual check-in:

GOOD examples:
- "Hey! Still thinking about buying or did things change?"
- "How's it going? Any questions come up?"
- "Still on your radar or taking a break from the search?"

BAD (don't say):
- "Just checking in" (overused)
- "Touching base" (corporate speak)
- "Hope you're doing well!" (generic)""",

            "value_add": f"""{base_context}Share something useful - a listing, tip, or market info:

GOOD examples:
- "Heads up - saw a place in {area or 'your area'} that might work. Want me to send it?"
- "Saw something hit the market near {area or 'where you were looking'} - want details?"
- "Quick tip - {area or 'this area'} is seeing more listings pop up. Good time to look if you're still interested"

Don't ask for anything in return - just be helpful.""",

            "channel_switch": f"""{base_context}Try email since texts aren't working:

GOOD examples:
- "Trying email in case that's easier - still interested in {area or 'buying'}?"
- "Not sure if texts are getting through - shooting you an email instead"

Keep it super short.""",

            "final_attempt": f"""{base_context}Last message - leave the door open nicely:

GOOD examples:
- "I'll back off - but hit me up anytime if you want to chat about {area or 'real estate'}"
- "Gonna give you some space! I'm here if anything changes"
- "No worries if now's not the time - reach out whenever"

Be warm, not guilt-trippy.""",
        }

        return instructions.get(followup_type, instructions["gentle_followup"])

    def _create_fallback_response(
        self,
        error_type: str,
        response_text: str,
        warnings: List[str] = None,
        response_time_ms: int = 0,
    ) -> GeneratedResponse:
        """Create a safe fallback response."""
        return GeneratedResponse(
            response_text=response_text,
            next_state="handed_off" if error_type == "exception" else "qualifying",
            extracted_info={},
            lead_score_delta=0,
            should_handoff=error_type == "exception",
            handoff_reason=f"Fallback used: {error_type}" if error_type == "exception" else None,
            detected_intent="other",
            detected_sentiment="neutral",
            confidence=0.3,
            tokens_used=0,
            response_time_ms=response_time_ms,
            model_used="fallback",
            quality=ResponseQuality.ACCEPTABLE,
            warnings=warnings or [],
        )

    def _get_safe_fallback(self, current_state: str, lead_context: Dict[str, Any]) -> str:
        """Get a safe fallback response based on state."""
        first_name = lead_context.get("first_name", "there")

        fallbacks = {
            "initial": f"Hey {first_name}! Thanks for reaching out. What can I help you with today?",
            "qualifying": "That's great! What area are you most interested in?",
            "objection_handling": "I totally understand! Is there anything specific I can help clarify?",
            "scheduling": "I'd love to chat more! What day works best for a quick call?",
            "nurture": f"Hey {first_name}! Just checking in. Let me know if you have any questions!",
            "handed_off": "Let me connect you with one of our agents who can help you better!",
        }

        return fallbacks.get(current_state, fallbacks["qualifying"])

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        return {
            "total_tokens_used": self._total_tokens_used,
            "request_count": self._request_count,
            "avg_tokens_per_request": (
                self._total_tokens_used / self._request_count
                if self._request_count > 0 else 0
            ),
        }


class ResponseGeneratorSingleton:
    """Singleton wrapper for response generator."""

    _instances: Dict[str, AIResponseGenerator] = {}

    @classmethod
    def get_instance(
        cls,
        organization_id: str = "default",
        **kwargs,
    ) -> AIResponseGenerator:
        """Get or create instance for organization."""
        if organization_id not in cls._instances:
            cls._instances[organization_id] = AIResponseGenerator(**kwargs)
        return cls._instances[organization_id]

    @classmethod
    def reset(cls, organization_id: str = None):
        """Reset instance(s)."""
        if organization_id:
            cls._instances.pop(organization_id, None)
        else:
            cls._instances.clear()
