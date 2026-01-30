"""
Intent Detector - Natural Language Understanding for Lead Messages.

Provides multi-layered intent detection:
1. Fast pattern matching for common intents (no API call)
2. LLM-based classification for complex/ambiguous messages
3. Entity extraction for qualification data
4. Confidence scoring and multi-intent support

Designed for real estate lead conversations with high accuracy.
"""

import re
import logging
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
import anthropic
import asyncio

logger = logging.getLogger(__name__)


class Intent(Enum):
    """All possible conversation intents."""

    # Greeting and general
    GREETING = "greeting"
    FAREWELL = "farewell"
    THANKS = "thanks"

    # Qualification signals
    TIMELINE_IMMEDIATE = "timeline_immediate"       # Ready now / ASAP
    TIMELINE_SHORT = "timeline_short"               # 1-3 months
    TIMELINE_MEDIUM = "timeline_medium"             # 3-6 months
    TIMELINE_LONG = "timeline_long"                 # 6+ months
    TIMELINE_UNKNOWN = "timeline_unknown"           # Just browsing / exploring

    BUDGET_SPECIFIC = "budget_specific"             # Has specific number
    BUDGET_RANGE = "budget_range"                   # Has a range
    BUDGET_PREAPPROVED = "budget_preapproved"       # Pre-approved for loan
    BUDGET_UNSURE = "budget_unsure"                 # Doesn't know yet

    LOCATION_PREFERENCE = "location_preference"     # Mentions specific area
    PROPERTY_TYPE = "property_type"                 # House, condo, townhome, etc.

    MOTIVATION_JOB = "motivation_job"               # Job relocation
    MOTIVATION_FAMILY = "motivation_family"         # Family changes
    MOTIVATION_INVESTMENT = "motivation_investment" # Investment property
    MOTIVATION_DOWNSIZE = "motivation_downsize"     # Downsizing
    MOTIVATION_UPGRADE = "motivation_upgrade"       # Upgrading

    # Objections
    OBJECTION_OTHER_AGENT = "objection_other_agent"     # Working with someone else
    OBJECTION_NOT_READY = "objection_not_ready"         # Not ready yet
    OBJECTION_JUST_BROWSING = "objection_just_browsing" # Just looking around
    OBJECTION_PRICE = "objection_price"                 # Too expensive
    OBJECTION_TIMING = "objection_timing"               # Bad timing

    # Engagement signals
    POSITIVE_INTEREST = "positive_interest"         # Shows interest
    NEGATIVE_INTEREST = "negative_interest"         # Shows disinterest
    QUESTION = "question"                           # Asking a question
    CONFIRMATION_YES = "confirmation_yes"           # Affirmative response
    CONFIRMATION_NO = "confirmation_no"             # Negative response

    # Appointment related
    APPOINTMENT_INTEREST = "appointment_interest"   # Wants to schedule
    APPOINTMENT_DECLINE = "appointment_decline"     # Doesn't want to meet
    APPOINTMENT_RESCHEDULE = "appointment_reschedule" # Wants to change time
    TIME_SELECTION = "time_selection"               # Selecting a time slot

    # Special handling
    OPT_OUT = "opt_out"                             # Wants to stop messages
    ESCALATION_REQUEST = "escalation_request"       # Wants human agent
    FRUSTRATION = "frustration"                     # Seems frustrated
    PROFANITY = "profanity"                         # Contains profanity

    # Channel preferences (smart routing - doesn't disable other channels)
    CHANNEL_PREFER_SMS = "channel_prefer_sms"       # Prefers text messages
    CHANNEL_PREFER_EMAIL = "channel_prefer_email"   # Prefers email contact
    CHANNEL_PREFER_CALL = "channel_prefer_call"     # Prefers phone calls
    CHANNEL_REDUCE_SMS = "channel_reduce_sms"       # Less texting (not opt-out)
    CHANNEL_REDUCE_EMAIL = "channel_reduce_email"   # Less email (not unsubscribe)

    # Property specific
    PROPERTY_QUESTION = "property_question"         # Question about a listing
    SHOWING_REQUEST = "showing_request"             # Wants to see a property

    # Deferred follow-up — lead wants contact at a specific future time
    DEFERRED_FOLLOWUP = "deferred_followup"         # "Call me next month", "reach out in 2 weeks"

    # Fallback
    UNKNOWN = "unknown"                             # Could not determine


@dataclass
class ExtractedEntity:
    """An extracted entity from the message."""
    entity_type: str  # budget, timeline, location, etc.
    value: Any
    raw_text: str
    confidence: float = 1.0


@dataclass
class DetectedIntent:
    """Result of intent detection."""
    primary_intent: Intent
    confidence: float
    secondary_intents: List[Tuple[Intent, float]] = field(default_factory=list)
    extracted_entities: List[ExtractedEntity] = field(default_factory=list)
    requires_llm_verification: bool = False
    sentiment: str = "neutral"  # positive, negative, neutral
    urgency: str = "normal"  # low, normal, high, urgent
    raw_message: str = ""

    def has_intent(self, intent: Intent, min_confidence: float = 0.5) -> bool:
        """Check if a specific intent was detected with sufficient confidence."""
        if self.primary_intent == intent and self.confidence >= min_confidence:
            return True
        for sec_intent, conf in self.secondary_intents:
            if sec_intent == intent and conf >= min_confidence:
                return True
        return False

    def get_entity(self, entity_type: str) -> Optional[ExtractedEntity]:
        """Get an extracted entity by type."""
        for entity in self.extracted_entities:
            if entity.entity_type == entity_type:
                return entity
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/logging."""
        return {
            "primary_intent": self.primary_intent.value,
            "confidence": self.confidence,
            "secondary_intents": [
                {"intent": i.value, "confidence": c}
                for i, c in self.secondary_intents
            ],
            "extracted_entities": [
                {
                    "type": e.entity_type,
                    "value": e.value,
                    "raw_text": e.raw_text,
                    "confidence": e.confidence,
                }
                for e in self.extracted_entities
            ],
            "sentiment": self.sentiment,
            "urgency": self.urgency,
        }


class PatternMatcher:
    """Fast pattern-based intent detection using regex."""

    # Pattern definitions: (compiled_regex, intent, confidence, entity_extractor)
    PATTERNS: List[Tuple[re.Pattern, Intent, float, Optional[str]]] = []

    @classmethod
    def _init_patterns(cls):
        """Initialize compiled regex patterns."""
        if cls.PATTERNS:
            return  # Already initialized

        pattern_defs = [
            # Opt-out (highest priority - compliance critical)
            (r'\b(stop|unsubscribe|opt.?out|remove me|don\'?t (text|contact|message))\b',
             Intent.OPT_OUT, 0.95, None),

            # Escalation requests
            (r'\b(speak|talk|connect).*(human|person|agent|someone|real)\b',
             Intent.ESCALATION_REQUEST, 0.9, None),
            (r'\b(real person|human agent|actual (person|agent))\b',
             Intent.ESCALATION_REQUEST, 0.9, None),

            # Frustration indicators
            (r'\b(frustrated|annoyed|angry|upset|sick of|tired of|hate)\b',
             Intent.FRUSTRATION, 0.85, None),
            (r'(!{2,}|\?{2,})', Intent.FRUSTRATION, 0.6, None),

            # Profanity (common variations)
            (r'\b(f+u+c+k+|sh+i+t+|a+ss+h+o+le+|damn|hell|crap)\b',
             Intent.PROFANITY, 0.95, None),

            # Channel preferences - SMS preferred
            (r'\b(text|sms|message) (me|is better|works better|is easier)\b',
             Intent.CHANNEL_PREFER_SMS, 0.9, 'channel_preference'),
            (r'\b(prefer|rather|better).*(text|sms|message)\b',
             Intent.CHANNEL_PREFER_SMS, 0.85, 'channel_preference'),
            (r'\b(just|only) (text|sms|message)\b',
             Intent.CHANNEL_PREFER_SMS, 0.8, 'channel_preference'),
            (r'\btext (is |works )?(best|better|easier)\b',
             Intent.CHANNEL_PREFER_SMS, 0.85, 'channel_preference'),

            # Channel preferences - Email preferred
            (r'\b(email|e-mail) (me|is better|works better|is easier)\b',
             Intent.CHANNEL_PREFER_EMAIL, 0.9, 'channel_preference'),
            (r'\b(prefer|rather|better).*(email|e-mail)\b',
             Intent.CHANNEL_PREFER_EMAIL, 0.85, 'channel_preference'),
            (r'\b(send|use|reach).*(email|e-mail)\b',
             Intent.CHANNEL_PREFER_EMAIL, 0.8, 'channel_preference'),
            (r'\bemail (is |works )?(best|better|easier)\b',
             Intent.CHANNEL_PREFER_EMAIL, 0.85, 'channel_preference'),
            (r'\b(email me instead|switch to email)\b',
             Intent.CHANNEL_PREFER_EMAIL, 0.9, 'channel_preference'),

            # Channel preferences - Call preferred
            (r'\b(call|phone) (me|is better|works better|is easier)\b',
             Intent.CHANNEL_PREFER_CALL, 0.9, 'channel_preference'),
            (r'\b(prefer|rather|better).*(call|phone|talk)\b',
             Intent.CHANNEL_PREFER_CALL, 0.85, 'channel_preference'),
            (r'\b(give me a call|just call)\b',
             Intent.CHANNEL_PREFER_CALL, 0.9, 'channel_preference'),
            (r'\b(easier to talk|rather talk|prefer to talk)\b',
             Intent.CHANNEL_PREFER_CALL, 0.85, 'channel_preference'),
            (r'\b(can you call|could you call)\b',
             Intent.CHANNEL_PREFER_CALL, 0.8, 'channel_preference'),

            # Channel reduction - Less SMS (different from opt-out)
            (r'\b(less|fewer) (texts?|messages?|sms)\b',
             Intent.CHANNEL_REDUCE_SMS, 0.85, 'channel_preference'),
            (r'\b(too many|so many) (texts?|messages?)\b',
             Intent.CHANNEL_REDUCE_SMS, 0.8, 'channel_preference'),
            (r'\b(slow down|ease up).*(text|message)\b',
             Intent.CHANNEL_REDUCE_SMS, 0.8, 'channel_preference'),
            (r'\bdon\'?t text (me )?(so much|as much|too much)\b',
             Intent.CHANNEL_REDUCE_SMS, 0.85, 'channel_preference'),

            # Channel reduction - Less email
            (r'\b(less|fewer) emails?\b',
             Intent.CHANNEL_REDUCE_EMAIL, 0.85, 'channel_preference'),
            (r'\b(too many|so many) emails?\b',
             Intent.CHANNEL_REDUCE_EMAIL, 0.8, 'channel_preference'),
            (r'\bdon\'?t email (me )?(so much|as much|too much)\b',
             Intent.CHANNEL_REDUCE_EMAIL, 0.85, 'channel_preference'),

            # Greetings
            (r'^(hi|hey|hello|yo|sup|what\'?s up|howdy|good (morning|afternoon|evening))[\s!.,]*$',
             Intent.GREETING, 0.9, None),
            (r'^(hi|hey|hello)\b', Intent.GREETING, 0.7, None),

            # Farewell
            (r'\b(bye|goodbye|later|see (you|ya)|talk (soon|later)|take care)\b',
             Intent.FAREWELL, 0.85, None),

            # Thanks
            (r'\b(thank(s| you)|appreciate|grateful)\b', Intent.THANKS, 0.85, None),

            # Confirmation - Yes
            (r'^(yes|yeah|yep|yup|sure|ok(ay)?|sounds good|perfect|great|absolutely|definitely|for sure)[\s!.,]*$',
             Intent.CONFIRMATION_YES, 0.9, None),
            (r'^(y|ye|ya|k)[\s!.,]*$', Intent.CONFIRMATION_YES, 0.8, None),
            (r'\b(works for me|that works|i\'?m (in|down|interested))\b',
             Intent.CONFIRMATION_YES, 0.85, None),

            # Confirmation - No
            (r'^(no|nope|nah|not really|not interested|pass)[\s!.,]*$',
             Intent.CONFIRMATION_NO, 0.9, None),
            (r'^(n)[\s!.,]*$', Intent.CONFIRMATION_NO, 0.7, None),

            # Timeline - Immediate
            (r'\b(asap|right (now|away)|immediately|urgent|this week|next (few )?days)\b',
             Intent.TIMELINE_IMMEDIATE, 0.85, 'timeline'),
            (r'\b(as soon as possible|ready (now|to (go|move|buy)))\b',
             Intent.TIMELINE_IMMEDIATE, 0.85, 'timeline'),

            # Timeline - Short (1-3 months)
            (r'\b(next (month|few weeks)|within (a |the next )?(month|30 days|few weeks))\b',
             Intent.TIMELINE_SHORT, 0.85, 'timeline'),
            (r'\b(1-3|one to three|couple) months?\b', Intent.TIMELINE_SHORT, 0.8, 'timeline'),

            # Timeline - Medium (3-6 months)
            (r'\b(3-6|three to six|few) months?\b', Intent.TIMELINE_MEDIUM, 0.8, 'timeline'),
            (r'\b(by (summer|fall|winter|spring|end of year))\b',
             Intent.TIMELINE_MEDIUM, 0.7, 'timeline'),

            # Timeline - Long (6+ months)
            (r'\b(6\+|six\+|next year|year from now|long term)\b',
             Intent.TIMELINE_LONG, 0.8, 'timeline'),
            (r'\b(no (rush|hurry)|take (my|our) time|not in a (rush|hurry))\b',
             Intent.TIMELINE_LONG, 0.75, 'timeline'),

            # Timeline - Unknown/Browsing
            (r'\b(just (looking|browsing|exploring)|not sure (when|yet)|window shopping)\b',
             Intent.TIMELINE_UNKNOWN, 0.85, 'timeline'),

            # Budget - Pre-approved
            (r'\b(pre.?approv|prequalif|got approved|approved for)\b',
             Intent.BUDGET_PREAPPROVED, 0.9, 'budget'),

            # Budget - Specific (with amount extraction)
            (r'\$\s*(\d{1,3}(?:,\d{3})*(?:k|K)?|\d+(?:k|K))',
             Intent.BUDGET_SPECIFIC, 0.9, 'budget_amount'),
            (r'\b(\d{2,3})\s*(?:k|K|thousand)\b',
             Intent.BUDGET_SPECIFIC, 0.85, 'budget_amount'),

            # Budget - Range
            (r'\$?\s*(\d+[kK]?)\s*[-–to]+\s*\$?\s*(\d+[kK]?)',
             Intent.BUDGET_RANGE, 0.85, 'budget_range'),
            (r'\b(between|around|roughly)\s*\$?\s*(\d+)',
             Intent.BUDGET_RANGE, 0.75, 'budget_range'),

            # Budget - Unsure
            (r'\b(not sure|don\'?t know|haven\'?t (thought|figured)|need to (figure|check))\b.*(budget|afford|price|spend)',
             Intent.BUDGET_UNSURE, 0.8, 'budget'),

            # Objection - Other agent
            (r'\b(already (have|got|working with)|using|have) (an?|another|my) (agent|realtor|broker)\b',
             Intent.OBJECTION_OTHER_AGENT, 0.9, None),
            (r'\b(working with someone|already represented|have representation)\b',
             Intent.OBJECTION_OTHER_AGENT, 0.9, None),

            # Deferred follow-up — lead wants contact at a specific future time
            # These must come BEFORE OBJECTION_NOT_READY to match the more specific intent
            (r'\b(call|text|reach out|contact|follow up|check back|get back to) (me )?(in|next|after) \w+',
             Intent.DEFERRED_FOLLOWUP, 0.9, 'deferred_date'),
            (r'\b(try (me )?again|hit me up|circle back) (in|next|after) \w+',
             Intent.DEFERRED_FOLLOWUP, 0.85, 'deferred_date'),
            (r'\bnot (right )?now[,.]* (but )?(maybe |try )?(in|next|after) \w+',
             Intent.DEFERRED_FOLLOWUP, 0.85, 'deferred_date'),
            (r'\b(let\'?s (talk|connect|chat) (in|next|after)|after the holidays|after (christmas|thanksgiving|new year))',
             Intent.DEFERRED_FOLLOWUP, 0.85, 'deferred_date'),

            # Objection - Not ready (generic "not now" without a specific time)
            (r'\b(not ready|not (quite )?there yet|need (more )?time|not (right )?now)\b',
             Intent.OBJECTION_NOT_READY, 0.85, None),
            (r'\b(maybe later|down the (road|line)|some(day|time))\b',
             Intent.OBJECTION_NOT_READY, 0.75, None),

            # Objection - Just browsing
            (r'\b(just (looking|browsing|curious)|window shopping|exploring options)\b',
             Intent.OBJECTION_JUST_BROWSING, 0.85, None),
            (r'\b(killing time|seeing what\'?s out there|no (serious|real) plans)\b',
             Intent.OBJECTION_JUST_BROWSING, 0.8, None),

            # Objection - Price
            (r'\b(too (expensive|pricey|much)|can\'?t afford|out of (my |our )?(budget|range|price))\b',
             Intent.OBJECTION_PRICE, 0.85, None),
            (r'\b(overpriced|high price|costs too much)\b', Intent.OBJECTION_PRICE, 0.8, None),

            # Objection - Timing
            (r'\b(bad time|not (a )?good time|busy (right now|lately)|lot going on)\b',
             Intent.OBJECTION_TIMING, 0.8, None),

            # Appointment interest
            (r'\b(schedule|book|set up|arrange).*(meeting|call|appointment|time|showing|tour)\b',
             Intent.APPOINTMENT_INTEREST, 0.85, None),
            (r'\b(want to|would like to|can we|let\'?s).*(meet|talk|chat|call|get together)\b',
             Intent.APPOINTMENT_INTEREST, 0.8, None),
            (r'\b(when (are you|can we)|what times?|availability)\b',
             Intent.APPOINTMENT_INTEREST, 0.75, None),

            # Appointment decline
            (r'\b(can\'?t (make it|meet)|not available|don\'?t (want|need) to meet)\b',
             Intent.APPOINTMENT_DECLINE, 0.85, None),

            # Time selection (when responding to time options)
            (r'^[1-6][\s!.,]*$', Intent.TIME_SELECTION, 0.9, 'time_slot'),
            (r'\b(option|number|choice)\s*[1-6]\b', Intent.TIME_SELECTION, 0.85, 'time_slot'),
            (r'\b(first|second|third|fourth|1st|2nd|3rd|4th)\s*(one|option|time)?\b',
             Intent.TIME_SELECTION, 0.8, 'time_slot'),

            # Showing request
            (r'\b(want to see|can I see|show me|tour|walk.?through|view)\b.*(house|home|property|place|listing)',
             Intent.SHOWING_REQUEST, 0.85, None),
            (r'\b(schedule|book).*(showing|tour|viewing)\b', Intent.SHOWING_REQUEST, 0.85, None),

            # Property question
            (r'\b(how (many|much)|what\'?s the|is (it|there)|does (it|the))\b.*(bedroom|bathroom|sqft|square|garage|yard|pool|price|cost)',
             Intent.PROPERTY_QUESTION, 0.8, None),
            (r'\b(tell me (more )?about|info on|details (on|about)|learn more)\b',
             Intent.PROPERTY_QUESTION, 0.75, None),

            # Motivation indicators
            (r'\b(new job|job (transfer|relocation)|relocat|moving for work|company)\b',
             Intent.MOTIVATION_JOB, 0.85, 'motivation'),
            (r'\b(baby|kid|child|family|pregnant|school|grow(ing)? family)\b',
             Intent.MOTIVATION_FAMILY, 0.8, 'motivation'),
            (r'\b(invest|rental|flip|income property|cash flow)\b',
             Intent.MOTIVATION_INVESTMENT, 0.85, 'motivation'),
            (r'\b(downsize|smaller|empty nest|retire)\b',
             Intent.MOTIVATION_DOWNSIZE, 0.8, 'motivation'),
            (r'\b(upgrade|bigger|more (space|room)|outgrow)\b',
             Intent.MOTIVATION_UPGRADE, 0.8, 'motivation'),

            # Positive interest
            (r'\b(interested|love|like|want|need|looking for|excited)\b',
             Intent.POSITIVE_INTEREST, 0.7, None),
            (r'\b(perfect|exactly|dream|ideal)\b', Intent.POSITIVE_INTEREST, 0.75, None),

            # Negative interest
            (r'\b(not interested|don\'?t (want|like|need)|pass|no thanks)\b',
             Intent.NEGATIVE_INTEREST, 0.85, None),

            # Question detection
            (r'\?$', Intent.QUESTION, 0.6, None),
            (r'^(what|where|when|why|how|who|which|can|could|would|is|are|do|does)\b',
             Intent.QUESTION, 0.7, None),
        ]

        cls.PATTERNS = [
            (re.compile(pattern, re.IGNORECASE), intent, confidence, extractor)
            for pattern, intent, confidence, extractor in pattern_defs
        ]

    @classmethod
    def match(cls, text: str) -> List[Tuple[Intent, float, Optional[re.Match]]]:
        """Find all matching patterns in text."""
        cls._init_patterns()

        matches = []
        for pattern, intent, confidence, _ in cls.PATTERNS:
            match = pattern.search(text)
            if match:
                matches.append((intent, confidence, match))

        return matches


class EntityExtractor:
    """Extract structured entities from message text."""

    @staticmethod
    def extract_budget_amount(text: str) -> Optional[ExtractedEntity]:
        """Extract budget amount from text."""
        # Pattern: $500k, $500,000, 500k, 500000
        patterns = [
            (r'\$\s*(\d{1,3}(?:,\d{3})*)\b', lambda m: int(m.group(1).replace(',', ''))),
            (r'\$\s*(\d+)\s*(?:k|K)\b', lambda m: int(m.group(1)) * 1000),
            (r'\b(\d{2,3})\s*(?:k|K|thousand)\b', lambda m: int(m.group(1)) * 1000),
            (r'\b(\d{6,7})\b', lambda m: int(m.group(1))),  # 6-7 digit number
        ]

        for pattern, converter in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    value = converter(match)
                    if 50000 <= value <= 50000000:  # Reasonable home price range
                        return ExtractedEntity(
                            entity_type="budget",
                            value=value,
                            raw_text=match.group(0),
                            confidence=0.9
                        )
                except (ValueError, IndexError):
                    continue

        return None

    @staticmethod
    def extract_budget_range(text: str) -> Optional[ExtractedEntity]:
        """Extract budget range from text."""
        pattern = r'\$?\s*(\d+[kK]?)\s*[-–to]+\s*\$?\s*(\d+[kK]?)'
        match = re.search(pattern, text)

        if match:
            def parse_amount(s: str) -> int:
                s = s.lower().replace(',', '')
                if 'k' in s:
                    return int(s.replace('k', '')) * 1000
                return int(s)

            try:
                low = parse_amount(match.group(1))
                high = parse_amount(match.group(2))

                if low < high and 50000 <= high <= 50000000:
                    return ExtractedEntity(
                        entity_type="budget_range",
                        value={"low": low, "high": high},
                        raw_text=match.group(0),
                        confidence=0.85
                    )
            except ValueError:
                pass

        return None

    @staticmethod
    def extract_location(text: str) -> Optional[ExtractedEntity]:
        """Extract location preferences from text."""
        # Common patterns for location mentions
        patterns = [
            r'\b(?:in|near|around|by|close to)\s+([A-Z][a-zA-Z\s]{2,20})\b',
            r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\s+(?:area|neighborhood|district)\b',
            r'\bdowntown\s+([A-Z][a-zA-Z]+)\b',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                location = match.group(1).strip()
                # Filter out common false positives
                false_positives = {'I', 'We', 'The', 'And', 'But', 'Just', 'Maybe', 'Please'}
                if location not in false_positives and len(location) > 2:
                    return ExtractedEntity(
                        entity_type="location",
                        value=location,
                        raw_text=match.group(0),
                        confidence=0.75
                    )

        return None

    @staticmethod
    def extract_property_type(text: str) -> Optional[ExtractedEntity]:
        """Extract property type from text."""
        patterns = {
            'single_family': r'\b(single family|house|home|detached)\b',
            'condo': r'\b(condo|condominium)\b',
            'townhouse': r'\b(townhouse|townhome|row house)\b',
            'multi_family': r'\b(multi.?family|duplex|triplex|fourplex)\b',
            'land': r'\b(land|lot|acreage)\b',
        }

        for prop_type, pattern in patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                return ExtractedEntity(
                    entity_type="property_type",
                    value=prop_type,
                    raw_text=re.search(pattern, text, re.IGNORECASE).group(0),
                    confidence=0.85
                )

        return None

    @staticmethod
    def extract_time_slot_selection(text: str) -> Optional[ExtractedEntity]:
        """Extract time slot selection from text."""
        # Direct number selection
        match = re.search(r'^([1-6])[\s!.,]*$', text.strip())
        if match:
            return ExtractedEntity(
                entity_type="time_slot",
                value=int(match.group(1)),
                raw_text=match.group(0),
                confidence=0.95
            )

        # "Option X" or "Number X"
        match = re.search(r'\b(?:option|number|choice)\s*([1-6])\b', text, re.IGNORECASE)
        if match:
            return ExtractedEntity(
                entity_type="time_slot",
                value=int(match.group(1)),
                raw_text=match.group(0),
                confidence=0.9
            )

        # Ordinal words
        ordinals = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5, 'sixth': 6,
                    '1st': 1, '2nd': 2, '3rd': 3, '4th': 4, '5th': 5, '6th': 6}
        for word, num in ordinals.items():
            if re.search(rf'\b{word}\b', text, re.IGNORECASE):
                return ExtractedEntity(
                    entity_type="time_slot",
                    value=num,
                    raw_text=word,
                    confidence=0.85
                )

        return None

    @staticmethod
    def extract_channel_preference(text: str) -> Optional[ExtractedEntity]:
        """Extract channel preference from text."""
        text_lower = text.lower()

        # Check for email preference
        email_patterns = [
            r'\b(email|e-mail) (me|is better|works better|is easier|instead)\b',
            r'\b(prefer|rather|better).*(email|e-mail)\b',
            r'\bswitch to email\b',
            r'\bemail (is |works )?(best|better|easier)\b',
        ]
        for pattern in email_patterns:
            if re.search(pattern, text_lower):
                return ExtractedEntity(
                    entity_type="channel_preference",
                    value="email",
                    raw_text=text,
                    confidence=0.9
                )

        # Check for call preference
        call_patterns = [
            r'\b(call|phone) (me|is better|works better|is easier)\b',
            r'\b(give me a call|just call)\b',
            r'\b(prefer|rather|better).*(call|phone|talk)\b',
            r'\b(easier to talk|rather talk|prefer to talk)\b',
        ]
        for pattern in call_patterns:
            if re.search(pattern, text_lower):
                return ExtractedEntity(
                    entity_type="channel_preference",
                    value="call",
                    raw_text=text,
                    confidence=0.9
                )

        # Check for SMS preference
        sms_patterns = [
            r'\b(text|sms|message) (me|is better|works better|is easier)\b',
            r'\b(prefer|rather|better).*(text|sms|message)\b',
            r'\btext (is |works )?(best|better|easier)\b',
        ]
        for pattern in sms_patterns:
            if re.search(pattern, text_lower):
                return ExtractedEntity(
                    entity_type="channel_preference",
                    value="sms",
                    raw_text=text,
                    confidence=0.9
                )

        # Check for channel reduction requests (not opt-out)
        reduce_sms_patterns = [
            r'\b(less|fewer) (texts?|messages?|sms)\b',
            r'\b(too many|so many) (texts?|messages?)\b',
            r'\bdon\'?t text (me )?(so much|as much|too much)\b',
        ]
        for pattern in reduce_sms_patterns:
            if re.search(pattern, text_lower):
                return ExtractedEntity(
                    entity_type="channel_reduction",
                    value="sms",
                    raw_text=text,
                    confidence=0.85
                )

        reduce_email_patterns = [
            r'\b(less|fewer) emails?\b',
            r'\b(too many|so many) emails?\b',
            r'\bdon\'?t email (me )?(so much|as much|too much)\b',
        ]
        for pattern in reduce_email_patterns:
            if re.search(pattern, text_lower):
                return ExtractedEntity(
                    entity_type="channel_reduction",
                    value="email",
                    raw_text=text,
                    confidence=0.85
                )

        return None

    @classmethod
    def extract_deferred_date(cls, text: str) -> Optional[ExtractedEntity]:
        """Extract a deferred follow-up date from text like 'call me next month' or 'in 2 weeks'."""
        from datetime import datetime, timedelta
        text_lower = text.lower()

        # Map relative time expressions to approximate days
        time_mappings = {
            # "in X weeks/months"
            r'in (\d+) weeks?': lambda m: int(m.group(1)) * 7,
            r'in (\d+) months?': lambda m: int(m.group(1)) * 30,
            r'in (\d+) days?': lambda m: int(m.group(1)),
            r'in a (week|couple weeks)': lambda m: 7 if 'couple' not in m.group(0) else 14,
            r'in a (month|couple months)': lambda m: 30 if 'couple' not in m.group(0) else 60,
            # "next week/month"
            r'next week': lambda m: 7,
            r'next month': lambda m: 30,
            r'next (spring|summer|fall|winter)': lambda m: 90,
            # "after" holidays
            r'after (the )?holidays': lambda m: 30,
            r'after (christmas|thanksgiving|new year)': lambda m: 30,
            # "a few weeks/months"
            r'(a )?few weeks': lambda m: 21,
            r'(a )?few months': lambda m: 90,
            r'(a )?couple (of )?weeks': lambda m: 14,
            r'(a )?couple (of )?months': lambda m: 60,
        }

        for pattern, days_fn in time_mappings.items():
            match = re.search(pattern, text_lower)
            if match:
                days = days_fn(match)
                target_date = datetime.utcnow() + timedelta(days=days)
                return ExtractedEntity(
                    entity_type="deferred_date",
                    value=target_date.strftime("%Y-%m-%d"),
                    raw_text=match.group(0),
                    confidence=0.85,
                )

        return None

    @classmethod
    def extract_all(cls, text: str) -> List[ExtractedEntity]:
        """Extract all entities from text."""
        entities = []

        # Try each extractor
        extractors = [
            cls.extract_budget_amount,
            cls.extract_budget_range,
            cls.extract_location,
            cls.extract_property_type,
            cls.extract_time_slot_selection,
            cls.extract_channel_preference,
            cls.extract_deferred_date,
        ]

        for extractor in extractors:
            entity = extractor(text)
            if entity:
                entities.append(entity)

        return entities


class IntentDetector:
    """
    Multi-layered intent detection system.

    Uses fast pattern matching first, then LLM for complex cases.
    """

    # Intents that always require immediate attention
    HIGH_PRIORITY_INTENTS = {
        Intent.OPT_OUT,
        Intent.ESCALATION_REQUEST,
        Intent.FRUSTRATION,
        Intent.PROFANITY,
    }

    # Confidence threshold below which LLM verification is needed
    LLM_VERIFICATION_THRESHOLD = 0.75

    def __init__(self, anthropic_client: Optional[anthropic.Anthropic] = None):
        """Initialize the intent detector."""
        self.client = anthropic_client
        self._llm_enabled = anthropic_client is not None

    def detect(
        self,
        message: str,
        conversation_context: Optional[Dict[str, Any]] = None,
        use_llm_fallback: bool = True,
    ) -> DetectedIntent:
        """
        Detect intents in a message.

        Args:
            message: The message to analyze
            conversation_context: Optional context about the conversation
            use_llm_fallback: Whether to use LLM for ambiguous cases

        Returns:
            DetectedIntent with primary and secondary intents
        """
        if not message or not message.strip():
            return DetectedIntent(
                primary_intent=Intent.UNKNOWN,
                confidence=0.0,
                raw_message=message,
            )

        # Normalize message
        normalized = self._normalize_message(message)

        # Phase 1: Fast pattern matching
        pattern_matches = PatternMatcher.match(normalized)

        # Phase 2: Entity extraction
        entities = EntityExtractor.extract_all(normalized)

        # Phase 3: Consolidate results
        result = self._consolidate_matches(
            message=normalized,
            pattern_matches=pattern_matches,
            entities=entities,
            context=conversation_context,
        )

        # Phase 4: LLM verification for low-confidence or complex cases
        if (use_llm_fallback and
            self._llm_enabled and
            self._needs_llm_verification(result)):
            result = self._enhance_with_llm(result, conversation_context)

        result.raw_message = message
        return result

    async def detect_async(
        self,
        message: str,
        conversation_context: Optional[Dict[str, Any]] = None,
        use_llm_fallback: bool = True,
    ) -> DetectedIntent:
        """Async version of detect for use in async contexts."""
        # Pattern matching is fast, run synchronously
        result = self.detect(
            message=message,
            conversation_context=conversation_context,
            use_llm_fallback=False,  # We'll do LLM separately
        )

        # LLM verification if needed
        if (use_llm_fallback and
            self._llm_enabled and
            self._needs_llm_verification(result)):
            result = await self._enhance_with_llm_async(result, conversation_context)

        return result

    def _normalize_message(self, message: str) -> str:
        """Normalize message for better matching."""
        # Basic normalization - keep case for entity extraction
        text = message.strip()

        # Normalize multiple spaces
        text = re.sub(r'\s+', ' ', text)

        # Normalize common texting abbreviations
        abbreviations = {
            r'\bu\b': 'you',
            r'\br\b': 'are',
            r'\bur\b': 'your',
            r'\bpls\b': 'please',
            r'\bthx\b': 'thanks',
            r'\btmrw\b': 'tomorrow',
            r'\bw/\b': 'with',
            r'\bw/o\b': 'without',
        }

        normalized = text
        for abbrev, full in abbreviations.items():
            normalized = re.sub(abbrev, full, normalized, flags=re.IGNORECASE)

        return normalized

    def _consolidate_matches(
        self,
        message: str,
        pattern_matches: List[Tuple[Intent, float, re.Match]],
        entities: List[ExtractedEntity],
        context: Optional[Dict[str, Any]],
    ) -> DetectedIntent:
        """Consolidate pattern matches and entities into final result."""

        if not pattern_matches:
            # No patterns matched - try to infer from context
            primary_intent = Intent.UNKNOWN
            confidence = 0.3

            # If message contains a question mark, likely a question
            if '?' in message:
                primary_intent = Intent.QUESTION
                confidence = 0.6
        else:
            # Group matches by intent, keep highest confidence
            intent_scores: Dict[Intent, float] = {}
            for intent, conf, _ in pattern_matches:
                if intent not in intent_scores or conf > intent_scores[intent]:
                    intent_scores[intent] = conf

            # Sort by confidence
            sorted_intents = sorted(
                intent_scores.items(),
                key=lambda x: (x[0] in self.HIGH_PRIORITY_INTENTS, x[1]),
                reverse=True
            )

            primary_intent, confidence = sorted_intents[0]
            secondary_intents = sorted_intents[1:5]  # Keep top 5 secondary

        # Determine sentiment
        sentiment = self._detect_sentiment(message, pattern_matches)

        # Determine urgency
        urgency = self._detect_urgency(message, pattern_matches, context)

        result = DetectedIntent(
            primary_intent=primary_intent,
            confidence=confidence,
            secondary_intents=secondary_intents if pattern_matches else [],
            extracted_entities=entities,
            sentiment=sentiment,
            urgency=urgency,
        )

        # Check if LLM verification is needed
        result.requires_llm_verification = self._needs_llm_verification(result)

        return result

    def _detect_sentiment(
        self,
        message: str,
        pattern_matches: List[Tuple[Intent, float, re.Match]],
    ) -> str:
        """Detect overall message sentiment."""
        intents = {m[0] for m in pattern_matches}

        # Negative indicators
        if intents & {Intent.FRUSTRATION, Intent.PROFANITY, Intent.NEGATIVE_INTEREST}:
            return "negative"

        if intents & {Intent.OBJECTION_OTHER_AGENT, Intent.OBJECTION_NOT_READY,
                      Intent.OBJECTION_JUST_BROWSING, Intent.OBJECTION_PRICE,
                      Intent.APPOINTMENT_DECLINE, Intent.CONFIRMATION_NO}:
            return "negative"

        # Positive indicators
        if intents & {Intent.POSITIVE_INTEREST, Intent.APPOINTMENT_INTEREST,
                      Intent.SHOWING_REQUEST, Intent.CONFIRMATION_YES,
                      Intent.THANKS}:
            return "positive"

        if intents & {Intent.TIMELINE_IMMEDIATE, Intent.TIMELINE_SHORT,
                      Intent.BUDGET_PREAPPROVED}:
            return "positive"

        return "neutral"

    def _detect_urgency(
        self,
        message: str,
        pattern_matches: List[Tuple[Intent, float, re.Match]],
        context: Optional[Dict[str, Any]],
    ) -> str:
        """Detect urgency level."""
        intents = {m[0] for m in pattern_matches}

        # Urgent
        if intents & {Intent.OPT_OUT, Intent.ESCALATION_REQUEST, Intent.FRUSTRATION}:
            return "urgent"

        # High
        if intents & {Intent.TIMELINE_IMMEDIATE, Intent.APPOINTMENT_INTEREST,
                      Intent.SHOWING_REQUEST}:
            return "high"

        # Low
        if intents & {Intent.TIMELINE_LONG, Intent.TIMELINE_UNKNOWN,
                      Intent.OBJECTION_JUST_BROWSING}:
            return "low"

        return "normal"

    def _needs_llm_verification(self, result: DetectedIntent) -> bool:
        """Determine if LLM verification would improve accuracy."""
        # High-confidence matches don't need verification
        if result.confidence >= 0.85:
            return False

        # Unknown intents should try LLM
        if result.primary_intent == Intent.UNKNOWN:
            return True

        # Low confidence matches benefit from LLM
        if result.confidence < self.LLM_VERIFICATION_THRESHOLD:
            return True

        # Multiple competing intents
        if result.secondary_intents:
            top_secondary_conf = result.secondary_intents[0][1]
            if abs(result.confidence - top_secondary_conf) < 0.15:
                return True

        return False

    def _enhance_with_llm(
        self,
        result: DetectedIntent,
        context: Optional[Dict[str, Any]],
    ) -> DetectedIntent:
        """Use LLM to verify or improve detection."""
        if not self.client:
            return result

        try:
            response = self.client.messages.create(
                model="claude-3-5-haiku-20241022",  # Fast model for classification
                max_tokens=500,
                system=self._get_llm_system_prompt(),
                messages=[
                    {
                        "role": "user",
                        "content": self._format_llm_request(result, context),
                    }
                ],
            )

            return self._parse_llm_response(response.content[0].text, result)

        except Exception as e:
            logger.warning(f"LLM enhancement failed: {e}")
            return result

    async def _enhance_with_llm_async(
        self,
        result: DetectedIntent,
        context: Optional[Dict[str, Any]],
    ) -> DetectedIntent:
        """Async version of LLM enhancement."""
        if not self.client:
            return result

        try:
            # Run sync client in executor
            loop = asyncio.get_event_loop()
            enhanced = await loop.run_in_executor(
                None,
                lambda: self._enhance_with_llm(result, context)
            )
            return enhanced

        except Exception as e:
            logger.warning(f"Async LLM enhancement failed: {e}")
            return result

    def _get_llm_system_prompt(self) -> str:
        """Get system prompt for LLM intent classification."""
        return """You are an intent classifier for a real estate lead conversation system.

Analyze the message and classify the PRIMARY intent from these categories:
- greeting, farewell, thanks
- timeline_immediate, timeline_short, timeline_medium, timeline_long, timeline_unknown
- budget_specific, budget_range, budget_preapproved, budget_unsure
- location_preference, property_type
- motivation_job, motivation_family, motivation_investment, motivation_downsize, motivation_upgrade
- objection_other_agent, objection_not_ready, objection_just_browsing, objection_price, objection_timing
- positive_interest, negative_interest, question
- confirmation_yes, confirmation_no
- appointment_interest, appointment_decline, appointment_reschedule, time_selection
- opt_out, escalation_request, frustration, profanity
- channel_prefer_sms, channel_prefer_email, channel_prefer_call (when lead asks for specific contact method)
- channel_reduce_sms, channel_reduce_email (when lead wants fewer messages but NOT full opt-out)
- property_question, showing_request
- unknown

IMPORTANT: channel_prefer_* intents are for when lead expresses a PREFERENCE, not an opt-out.
"Email me instead" = channel_prefer_email (still interested, just different channel)
"Stop texting" = opt_out (wants no more messages)
"Less texts please" = channel_reduce_sms (reduce frequency, not stop entirely)

Respond in JSON format:
{
    "primary_intent": "intent_name",
    "confidence": 0.0-1.0,
    "secondary_intents": [{"intent": "name", "confidence": 0.0-1.0}],
    "sentiment": "positive|negative|neutral",
    "reasoning": "brief explanation"
}"""

    def _format_llm_request(
        self,
        result: DetectedIntent,
        context: Optional[Dict[str, Any]],
    ) -> str:
        """Format the request for LLM analysis."""
        parts = [f"Message: \"{result.raw_message}\""]

        if result.primary_intent != Intent.UNKNOWN:
            parts.append(f"\nPattern matching suggests: {result.primary_intent.value} "
                        f"(confidence: {result.confidence:.2f})")

        if result.secondary_intents:
            secondary = ", ".join(f"{i.value}({c:.2f})"
                                 for i, c in result.secondary_intents[:3])
            parts.append(f"Other possibilities: {secondary}")

        if context:
            if context.get('current_state'):
                parts.append(f"Conversation state: {context['current_state']}")
            if context.get('last_ai_message'):
                parts.append(f"Previous AI message: \"{context['last_ai_message'][:100]}\"")

        parts.append("\nClassify the intent:")

        return "\n".join(parts)

    def _parse_llm_response(
        self,
        response_text: str,
        original_result: DetectedIntent,
    ) -> DetectedIntent:
        """Parse LLM response and update result."""
        import json

        try:
            # Extract JSON from response
            json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
            if not json_match:
                return original_result

            data = json.loads(json_match.group())

            # Map intent string to enum
            intent_str = data.get('primary_intent', 'unknown').lower()
            try:
                primary_intent = Intent(intent_str)
            except ValueError:
                primary_intent = original_result.primary_intent

            confidence = float(data.get('confidence', original_result.confidence))

            # Parse secondary intents
            secondary = []
            for s in data.get('secondary_intents', [])[:5]:
                try:
                    sec_intent = Intent(s['intent'].lower())
                    sec_conf = float(s['confidence'])
                    secondary.append((sec_intent, sec_conf))
                except (ValueError, KeyError):
                    continue

            # Update result
            return DetectedIntent(
                primary_intent=primary_intent,
                confidence=confidence,
                secondary_intents=secondary or original_result.secondary_intents,
                extracted_entities=original_result.extracted_entities,
                sentiment=data.get('sentiment', original_result.sentiment),
                urgency=original_result.urgency,
                raw_message=original_result.raw_message,
                requires_llm_verification=False,
            )

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return original_result


# Convenience function for simple usage
def detect_intent(
    message: str,
    context: Optional[Dict[str, Any]] = None,
    anthropic_client: Optional[anthropic.Anthropic] = None,
) -> DetectedIntent:
    """
    Convenience function for intent detection.

    Args:
        message: Message to analyze
        context: Optional conversation context
        anthropic_client: Optional Anthropic client for LLM fallback

    Returns:
        DetectedIntent with classification results
    """
    detector = IntentDetector(anthropic_client)
    return detector.detect(message, context)


# Batch processing for efficiency
async def detect_intents_batch(
    messages: List[str],
    anthropic_client: Optional[anthropic.Anthropic] = None,
) -> List[DetectedIntent]:
    """
    Detect intents for multiple messages efficiently.

    Args:
        messages: List of messages to analyze
        anthropic_client: Optional Anthropic client for LLM fallback

    Returns:
        List of DetectedIntent results
    """
    detector = IntentDetector(anthropic_client)

    # Process all pattern matching first (fast)
    results = [detector.detect(msg, use_llm_fallback=False) for msg in messages]

    # Batch LLM verification for those that need it
    if anthropic_client:
        tasks = []
        indices = []
        for i, result in enumerate(results):
            if result.requires_llm_verification:
                tasks.append(detector._enhance_with_llm_async(result, None))
                indices.append(i)

        if tasks:
            enhanced = await asyncio.gather(*tasks, return_exceptions=True)
            for i, enhanced_result in zip(indices, enhanced):
                if not isinstance(enhanced_result, Exception):
                    results[i] = enhanced_result

    return results
