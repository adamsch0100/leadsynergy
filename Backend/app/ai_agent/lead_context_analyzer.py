"""
Lead Context Analyzer

Analyzes complete lead history to determine optimal re-engagement strategy.

This service:
1. Fetches all available FUB data (messages, calls, emails, notes)
2. Classifies lead stage (NEW, DORMANT, WARM, COLD, RETURNING)
3. Extracts topics discussed, questions asked, objections raised
4. Determines conversation outcome (went silent, objection, engaged)
5. Returns re-engagement strategy tailored to lead history

This enables contextual, non-repetitive proactive outreach that feels personal.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# =========================================
# DATA MODELS
# =========================================

@dataclass
class CommunicationHistory:
    """Parsed communication history with intelligence extracted."""
    last_contact_date: Optional[datetime] = None
    days_since_last_contact: int = 0
    total_messages_sent: int = 0  # From agent
    total_messages_received: int = 0  # From lead
    last_message_direction: str = ""  # "inbound" or "outbound"
    last_message_preview: str = ""  # Last 200 chars for context
    conversation_ended_how: str = "unknown"  # "went_silent", "said_call_later", "objection", "engaged"

    # Extracted intelligence
    topics_discussed: List[str] = field(default_factory=list)  # ["budget", "timeline", "specific_property"]
    questions_already_asked: List[str] = field(default_factory=list)  # ["budget", "preapproval", "timeline"]
    objections_raised: List[str] = field(default_factory=list)  # ["too_expensive", "not_ready", "other_agent"]

    # Engagement metrics
    response_rate: float = 0.0  # % of messages that got responses
    engagement_quality: str = "none"  # "high", "medium", "low", "none"

    # Call summaries (if available)
    call_summaries: List[str] = field(default_factory=list)


@dataclass
class LeadStageClassification:
    """Lead stage determination with reasoning."""
    stage: str  # NEW / DORMANT / WARM / COLD / RETURNING
    confidence: float = 1.0  # 0.0-1.0
    reasoning: str = ""  # Why we classified this way

    # Stage definitions (for reference):
    # NEW: 0-7 days old, 0-2 messages sent, no prior engagement
    # DORMANT: 30-180 days since last contact, had previous engagement
    # WARM: 7-30 days since last contact, active conversation ongoing
    # COLD: 180+ days since last contact, needs soft value-first approach
    # RETURNING: Had conversation, went silent 30-90 days, now being re-enabled


@dataclass
class ReEngagementStrategy:
    """Strategy for re-engaging this specific lead."""
    approach: str  # "enthusiastic_intro", "soft_reconnection", "value_first", "continuity"
    tone: str  # "energetic", "casual", "professional", "empathetic"
    message_angle: str  # What to lead with
    avoid_topics: List[str] = field(default_factory=list)  # Topics that caused drop-off
    reference_context: Optional[str] = None  # Specific thing to reference from prior convo


@dataclass
class HistoricalContext:
    """Complete historical context for proactive outreach."""
    communication_history: CommunicationHistory
    lead_stage: LeadStageClassification
    strategy: ReEngagementStrategy

    # High-level lead info
    lead_type: str = ""  # buyer/seller/both
    budget_discussed: bool = False
    timeline_discussed: bool = False
    specific_property_interest: Optional[str] = None


# =========================================
# LEAD CONTEXT ANALYZER
# =========================================

class LeadContextAnalyzer:
    """Analyzes lead history to determine optimal re-engagement approach."""

    def __init__(self, fub_client, supabase_client=None):
        """
        Initialize analyzer.

        Args:
            fub_client: FUBAPIClient instance for fetching lead data
            supabase_client: Optional Supabase client for cached profiles
        """
        self.fub_client = fub_client
        self.supabase = supabase_client

    async def analyze_lead_context(
        self,
        fub_person_id: int,
        enable_type: str = "auto",
    ) -> HistoricalContext:
        """
        Analyze complete lead context and determine re-engagement strategy.

        Args:
            fub_person_id: FUB person ID
            enable_type: "auto" or "manual" (affects classification)

        Returns:
            HistoricalContext with analysis results
        """
        try:
            # Fetch complete lead data
            logger.info(f"Fetching complete context for lead {fub_person_id}")
            complete_context = self.fub_client.get_complete_lead_context(fub_person_id)

            person_data = complete_context.get('person', {})
            text_messages = complete_context.get('text_messages', [])
            emails = complete_context.get('emails', [])
            calls = complete_context.get('calls', [])
            notes = complete_context.get('notes', [])

            # Parse communication history
            comm_history = self._parse_communication_history(
                text_messages=text_messages,
                emails=emails,
                calls=calls,
                notes=notes,
            )

            # Classify lead stage
            lead_stage = self._classify_lead_stage(
                person_data=person_data,
                comm_history=comm_history,
                enable_type=enable_type,
            )

            # Determine re-engagement strategy
            strategy = self._determine_strategy(
                lead_stage=lead_stage,
                comm_history=comm_history,
                person_data=person_data,
            )

            # Extract high-level info
            lead_type = self._extract_lead_type(person_data)
            budget_discussed = "budget" in comm_history.topics_discussed
            timeline_discussed = "timeline" in comm_history.topics_discussed
            specific_property = self._extract_property_interest(person_data, text_messages)

            return HistoricalContext(
                communication_history=comm_history,
                lead_stage=lead_stage,
                strategy=strategy,
                lead_type=lead_type,
                budget_discussed=budget_discussed,
                timeline_discussed=timeline_discussed,
                specific_property_interest=specific_property,
            )

        except Exception as e:
            logger.error(f"Error analyzing lead context: {e}", exc_info=True)
            # Return minimal context for NEW lead
            return self._create_fallback_context()

    def _parse_communication_history(
        self,
        text_messages: List[Dict],
        emails: List[Dict],
        calls: List[Dict],
        notes: List[Dict],
    ) -> CommunicationHistory:
        """Parse all communications and extract intelligence."""

        # Count messages by direction
        messages_sent = 0
        messages_received = 0
        last_message_date = None
        last_message_direction = ""
        last_message_preview = ""

        all_messages = []

        # Process text messages
        for msg in text_messages:
            created_at_str = msg.get('created') or msg.get('createdAt')
            if not created_at_str:
                continue

            try:
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            except:
                continue

            direction = "outbound" if msg.get('outbound') else "inbound"
            content = msg.get('body', '')

            all_messages.append({
                'date': created_at,
                'direction': direction,
                'content': content,
                'type': 'sms'
            })

            if direction == "outbound":
                messages_sent += 1
            else:
                messages_received += 1

        # Sort by date (newest first)
        all_messages.sort(key=lambda x: x['date'], reverse=True)

        if all_messages:
            last_msg = all_messages[0]
            last_message_date = last_msg['date']
            last_message_direction = last_msg['direction']
            last_message_preview = last_msg['content'][:200]

        # Calculate days since last contact
        days_since = 0
        if last_message_date:
            now = datetime.now(timezone.utc)
            delta = now - last_message_date
            days_since = int(delta.total_seconds() / 86400)

        # Calculate response rate
        response_rate = 0.0
        if messages_sent > 0:
            response_rate = (messages_received / messages_sent) * 100

        # Determine engagement quality
        engagement_quality = "none"
        if response_rate >= 75:
            engagement_quality = "high"
        elif response_rate >= 40:
            engagement_quality = "medium"
        elif response_rate > 0:
            engagement_quality = "low"

        # Extract topics discussed
        topics = self._extract_topics(all_messages)

        # Extract questions already asked
        questions = self._extract_questions_asked(all_messages)

        # Detect objections
        objections = self._detect_objections(all_messages)

        # Determine conversation outcome
        outcome = self._determine_conversation_outcome(all_messages, days_since)

        # Extract call summaries from notes
        call_summaries = self._extract_call_summaries(notes)

        return CommunicationHistory(
            last_contact_date=last_message_date,
            days_since_last_contact=days_since,
            total_messages_sent=messages_sent,
            total_messages_received=messages_received,
            last_message_direction=last_message_direction,
            last_message_preview=last_message_preview,
            conversation_ended_how=outcome,
            topics_discussed=topics,
            questions_already_asked=questions,
            objections_raised=objections,
            response_rate=response_rate,
            engagement_quality=engagement_quality,
            call_summaries=call_summaries,
        )

    def _extract_topics(self, messages: List[Dict]) -> List[str]:
        """Extract topics discussed from message content."""
        topics = set()
        all_text = " ".join([m['content'].lower() for m in messages])

        # Budget keywords
        if any(k in all_text for k in ['price', 'afford', 'payment', 'preapproval', '$', 'budget', 'financing']):
            topics.add("budget")

        # Timeline keywords
        if any(k in all_text for k in ['soon', 'months', 'year', 'when', 'timeline', 'immediate', 'asap']):
            topics.add("timeline")

        # Location keywords
        if any(k in all_text for k in ['location', 'area', 'neighborhood', 'city', 'looking in', 'near']):
            topics.add("location")

        # Property type
        if any(k in all_text for k in ['condo', 'townhouse', 'single family', 'apartment', 'house', 'home']):
            topics.add("property_type")

        # Specific property
        if any(k in all_text for k in ['this property', 'that house', 'the listing', '123 ', 'address']):
            topics.add("specific_property")

        # Showing/tour
        if any(k in all_text for k in ['tour', 'showing', 'see the house', 'visit', 'walk through']):
            topics.add("showing")

        return list(topics)

    def _extract_questions_asked(self, messages: List[Dict]) -> List[str]:
        """Extract questions that were already asked by agent."""
        questions = set()

        # Only check outbound messages (from agent)
        outbound_msgs = [m for m in messages if m['direction'] == 'outbound']
        all_text = " ".join([m['content'].lower() for m in outbound_msgs])

        # Budget questions
        if any(k in all_text for k in ['budget?', 'price range?', 'how much', 'afford?', 'preapproved?']):
            questions.add("budget")

        # Timeline questions
        if any(k in all_text for k in ['when are you', 'timeline?', 'how soon', 'move by when']):
            questions.add("timeline")

        # Preapproval questions
        if 'preapprove' in all_text or 'pre-approve' in all_text or 'financing' in all_text:
            questions.add("preapproval")

        # Location questions
        if any(k in all_text for k in ['where are you', 'which area', 'location?', 'neighborhoods']):
            questions.add("location")

        return list(questions)

    def _detect_objections(self, messages: List[Dict]) -> List[str]:
        """Detect objections raised by lead."""
        objections = set()

        # Only check inbound messages (from lead)
        inbound_msgs = [m for m in messages if m['direction'] == 'inbound']
        all_text = " ".join([m['content'].lower() for m in inbound_msgs])

        # Price objections
        if any(k in all_text for k in ['too expensive', 'too much', "can't afford", 'over budget', 'out of my price']):
            objections.add("too_expensive")

        # Timing objections
        if any(k in all_text for k in ['not ready', "i'm not", 'not yet', 'need more time', 'too soon']):
            objections.add("not_ready")

        # Other agent
        if any(k in all_text for k in ['other agent', 'another realtor', 'working with someone', 'already have']):
            objections.add("other_agent")

        # Just browsing
        if any(k in all_text for k in ['just looking', 'just browsing', 'not serious', 'just curious']):
            objections.add("just_browsing")

        return list(objections)

    def _determine_conversation_outcome(self, messages: List[Dict], days_since: int) -> str:
        """Determine how the conversation ended."""
        if not messages:
            return "no_contact"

        # Get last 5 messages
        recent_msgs = messages[:5]

        # If last message was from lead and it's been <2 days → "engaged"
        if recent_msgs[0]['direction'] == 'inbound' and days_since < 2:
            return "engaged"

        # If last 2-3 messages are all from agent → "went_silent"
        if len(recent_msgs) >= 2 and all(m['direction'] == 'outbound' for m in recent_msgs[:3]):
            return "went_silent"

        # Check for "call me later" indicators
        inbound_text = " ".join([m['content'].lower() for m in recent_msgs if m['direction'] == 'inbound'])
        if any(k in inbound_text for k in ['call me', 'reach out', 'next week', 'next month', 'later', 'few months']):
            return "said_call_later"

        # Check for objection keywords
        if any(k in inbound_text for k in ['expensive', 'not ready', 'think about', 'other agent']):
            return "objection"

        # Default
        if days_since > 30:
            return "went_silent"

        return "engaged"

    def _extract_call_summaries(self, notes: List[Dict]) -> List[str]:
        """Extract call summaries from FUB notes."""
        summaries = []
        for note in notes:
            body = note.get('body', '')
            if 'call summary' in body.lower() or 'spoke with' in body.lower():
                summaries.append(body[:300])  # First 300 chars
        return summaries

    def _classify_lead_stage(
        self,
        person_data: Dict,
        comm_history: CommunicationHistory,
        enable_type: str,
    ) -> LeadStageClassification:
        """Classify the lead's current stage."""

        days_since = comm_history.days_since_last_contact
        messages_sent = comm_history.total_messages_sent
        messages_received = comm_history.total_messages_received

        # Parse created date
        created_str = person_data.get('created', person_data.get('createdAt', ''))
        days_old = 999  # Default to old if can't parse
        if created_str:
            try:
                created_dt = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                days_old = int((now - created_dt).total_seconds() / 86400)
            except:
                pass

        # NEW: 0-7 days old, <3 messages sent, no responses
        if days_old <= 7 and messages_sent < 3 and messages_received == 0:
            return LeadStageClassification(
                stage="NEW",
                confidence=0.95,
                reasoning=f"Lead is {days_old} days old with {messages_sent} messages sent and no responses yet"
            )

        # WARM: Last contact < 30 days, active engagement
        if days_since < 30 and messages_received > 0 and comm_history.engagement_quality in ["high", "medium"]:
            return LeadStageClassification(
                stage="WARM",
                confidence=0.9,
                reasoning=f"Active conversation with last contact {days_since} days ago and {comm_history.engagement_quality} engagement"
            )

        # DORMANT: 30-180 days since last contact, had prior engagement
        if 30 <= days_since <= 180 and messages_sent > 0:
            return LeadStageClassification(
                stage="DORMANT",
                confidence=0.9,
                reasoning=f"Had {messages_sent} messages sent, went silent {days_since} days ago"
            )

        # COLD: 180+ days since last contact
        if days_since > 180:
            return LeadStageClassification(
                stage="COLD",
                confidence=0.95,
                reasoning=f"No contact for {days_since} days (6+ months)"
            )

        # RETURNING: Manually enabled dormant lead
        if enable_type == "manual" and messages_sent > 0 and days_since >= 30:
            return LeadStageClassification(
                stage="RETURNING",
                confidence=0.85,
                reasoning=f"Manually re-enabled after {days_since} days silence"
            )

        # Default: NEW
        return LeadStageClassification(
            stage="NEW",
            confidence=0.7,
            reasoning="Couldn't determine stage clearly, defaulting to NEW"
        )

    def _determine_strategy(
        self,
        lead_stage: LeadStageClassification,
        comm_history: CommunicationHistory,
        person_data: Dict,
    ) -> ReEngagementStrategy:
        """Determine re-engagement strategy based on stage and history."""

        stage = lead_stage.stage

        # NEW lead strategy
        if stage == "NEW":
            return ReEngagementStrategy(
                approach="enthusiastic_intro",
                tone="energetic",
                message_angle="Reference their property inquiry source and express excitement to help",
                avoid_topics=[],
                reference_context=None,
            )

        # DORMANT lead strategy
        if stage == "DORMANT":
            # Find reference context from last messages
            ref_context = None
            if comm_history.topics_discussed:
                topics_str = ", ".join(comm_history.topics_discussed)
                ref_context = f"Previous discussion about {topics_str}"

            avoid = list(comm_history.objections_raised)

            return ReEngagementStrategy(
                approach="soft_reconnection",
                tone="casual",
                message_angle="Acknowledge time gap, offer market update or new value",
                avoid_topics=avoid,
                reference_context=ref_context,
            )

        # WARM lead strategy
        if stage == "WARM":
            return ReEngagementStrategy(
                approach="continuity",
                tone="professional",
                message_angle="Continue where you left off, check in on progress",
                avoid_topics=[],
                reference_context=comm_history.last_message_preview,
            )

        # COLD lead strategy
        if stage == "COLD":
            return ReEngagementStrategy(
                approach="value_first",
                tone="empathetic",
                message_angle="Lead with market insight or value, no pressure",
                avoid_topics=list(comm_history.objections_raised),
                reference_context=None,
            )

        # RETURNING lead strategy
        if stage == "RETURNING":
            ref_context = None
            if comm_history.topics_discussed:
                topics_str = ", ".join(comm_history.topics_discussed[:2])  # Top 2 topics
                ref_context = f"Our conversation about {topics_str}"

            return ReEngagementStrategy(
                approach="empathetic_continuity",
                tone="empathetic",
                message_angle="Welcome back, reference what you discussed before, low pressure",
                avoid_topics=list(comm_history.objections_raised),
                reference_context=ref_context,
            )

        # Default
        return ReEngagementStrategy(
            approach="enthusiastic_intro",
            tone="professional",
            message_angle="Introduce yourself and offer help",
            avoid_topics=[],
            reference_context=None,
        )

    def _extract_lead_type(self, person_data: Dict) -> str:
        """Extract lead type: buyer, seller, or both."""
        tags_str = str(person_data.get('tags', [])).lower()
        type_field = str(person_data.get('type', '')).lower()

        is_buyer = 'buyer' in tags_str or 'buyer' in type_field
        is_seller = 'seller' in tags_str or 'seller' in type_field

        if is_buyer and is_seller:
            return "both"
        elif is_seller:
            return "seller"
        elif is_buyer:
            return "buyer"
        else:
            return ""

    def _extract_property_interest(self, person_data: Dict, messages: List[Dict]) -> Optional[str]:
        """Extract specific property address if mentioned."""
        # Check custom fields
        addresses = person_data.get('addresses', [])
        if addresses:
            return str(addresses[0])

        # Check messages for addresses (simple pattern)
        all_text = " ".join([m.get('body', '') for m in messages])
        # Look for patterns like "123 Main St"
        address_pattern = r'\d+\s+[A-Z][a-z]+\s+(St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Way|Ln|Lane)'
        match = re.search(address_pattern, all_text)
        if match:
            return match.group(0)

        return None

    def _create_fallback_context(self) -> HistoricalContext:
        """Create minimal fallback context for error cases."""
        return HistoricalContext(
            communication_history=CommunicationHistory(),
            lead_stage=LeadStageClassification(stage="NEW", reasoning="Fallback due to analysis error"),
            strategy=ReEngagementStrategy(
                approach="enthusiastic_intro",
                tone="professional",
                message_angle="Introduce yourself and offer help"
            ),
            lead_type="",
            budget_discussed=False,
            timeline_discussed=False,
            specific_property_interest=None,
        )
