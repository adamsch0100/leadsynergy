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

    def to_context_string(self) -> str:
        """
        Convert profile to a detailed context string for the LLM.

        This is the key method that creates rich, readable context.
        """
        sections = []

        # === IDENTITY SECTION ===
        identity_parts = [f"Name: {self.full_name or self.first_name or 'Unknown'}"]
        if self.email:
            identity_parts.append(f"Email: {self.email}")
        if self.phone:
            identity_parts.append(f"Phone: {self.phone}")
        sections.append("LEAD IDENTITY:\n" + "\n".join(f"  - {p}" for p in identity_parts))

        # === SCORE & STATUS SECTION ===
        status_parts = [
            f"Score: {self.score}/100 ({self.score_label} lead)",
        ]
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
                source_parts.append(f"Source: {self.source}")
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
                search_parts.append("Pre-approved: No (opportunity to help!)")
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

        # === ENGAGEMENT HISTORY SECTION ===
        engagement_parts = []
        if self.total_messages_sent or self.total_messages_received:
            engagement_parts.append(
                f"Messages: {self.total_messages_received} received, {self.total_messages_sent} sent"
            )
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
        if self.days_since_created:
            engagement_parts.append(f"Lead age: {self.days_since_created} days")
        if engagement_parts:
            sections.append("ENGAGEMENT HISTORY:\n" + "\n".join(f"  - {p}" for p in engagement_parts))

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

        # Extract tags
        tags = [tag.get("tag", "") for tag in fub_person.get("tags", [])]

        # Get source info
        source = fub_person.get("source", "")
        source_url = fub_person.get("sourceUrl", "")

        # Custom fields (FUB stores various data here)
        custom_fields = {}
        for field in fub_person.get("customFields", []):
            custom_fields[field.get("name", "")] = field.get("value")

        # Calculate days since created
        created_at = fub_person.get("createdAt", "")
        days_since_created = 0
        if created_at:
            try:
                created_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                days_since_created = (datetime.now(created_date.tzinfo) - created_date).days
            except Exception:
                pass

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
            assigned_agent=fub_person.get("assignedTo", {}).get("name", ""),
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
        )


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
    """

    # Model configuration
    PRIMARY_MODEL = "claude-sonnet-4-20250514"
    FALLBACK_MODEL = "claude-3-5-haiku-20241022"
    MAX_TOKENS = 500
    MAX_CONTEXT_MESSAGES = 20  # Keep last N messages for context

    # Retry configuration
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 1.0  # seconds
    MAX_RETRY_DELAY = 10.0

    # Response validation
    MAX_SMS_LENGTH = 160
    MIN_RESPONSE_LENGTH = 10

    # Personality configurations
    PERSONALITY_PROMPTS = {
        "friendly_casual": """You are a friendly, casual real estate assistant helping people find their perfect home.

PERSONALITY TRAITS:
- Warm and approachable - like texting with a helpful friend
- Use first names and contractions naturally
- Express genuine interest and enthusiasm
- Never pushy, salesy, or aggressive
- Patient and understanding
- Use casual phrases naturally: "Totally!", "For sure!", "No worries!", "That's awesome!"
- Occasional emojis are OK but don't overdo it (max 1 per message)

COMMUNICATION STYLE:
- Keep it conversational and natural
- Ask one question at a time
- Acknowledge what they said before moving on
- Be helpful even if they're not ready to buy/sell
- Show you're listening by referencing their previous answers""",

        "professional": """You are a professional, knowledgeable real estate consultant.

PERSONALITY TRAITS:
- Polished and business-like
- Confident but not arrogant
- Focused on providing value and expertise
- Respectful of their time
- Clear and concise communication

COMMUNICATION STYLE:
- Use proper grammar and punctuation
- Be direct but courteous
- Provide relevant market insights when appropriate
- Maintain professional boundaries
- Focus on facts and solutions""",

        "energetic": """You are an enthusiastic, high-energy real estate professional.

PERSONALITY TRAITS:
- Upbeat and positive
- Excited about helping them
- Motivating and encouraging
- Action-oriented
- Celebrates their milestones

COMMUNICATION STYLE:
- Express excitement appropriately
- Use encouraging language
- Keep energy high but not overwhelming
- Focus on possibilities and opportunities
- Be genuinely enthusiastic about their journey""",
    }

    # State-specific guidance
    STATE_GUIDANCE = {
        "initial": """GOAL: Welcome them warmly and understand what brought them here.
- Thank them for reaching out
- Ask an open-ended question about their situation
- Don't jump straight into qualification questions""",

        "qualifying": """GOAL: Naturally learn about their timeline, budget, location preferences, and motivation.
- Only ask about ONE thing at a time
- Acknowledge their answers before asking the next question
- Be conversational, not interrogating
- Priority order: Timeline > Location > Budget > Pre-approval""",

        "objection_handling": """GOAL: Address their concern without being defensive.
- Acknowledge their concern first ("I totally understand...")
- Provide a helpful perspective or alternative
- Don't argue or push back
- Offer value without pressure
- If they're firm, respect their decision gracefully""",

        "scheduling": """GOAL: Get them booked for a call or showing.
- Offer specific time options (not open-ended)
- Make it easy to say yes
- Confirm details clearly
- Express excitement about meeting them""",

        "nurture": """GOAL: Stay helpful without being pushy.
- Check in periodically
- Share relevant market info or listings
- Keep the door open for when they're ready
- Respect their timeline""",

        "handed_off": """GOAL: Smoothly transition to human agent.
- Let them know a team member will follow up
- Provide context about what happens next
- Thank them for the conversation""",
    }

    def __init__(
        self,
        api_key: str = None,
        personality: str = "friendly_casual",
        agent_name: str = "Sarah",
        brokerage_name: str = "our team",
    ):
        """
        Initialize the AI response generator.

        Args:
            api_key: Anthropic API key (uses env var if not provided)
            personality: Personality tone to use
            agent_name: Name the AI will use
            brokerage_name: Brokerage/team name
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.personality = personality
        self.agent_name = agent_name
        self.brokerage_name = brokerage_name
        self._client = None
        self._total_tokens_used = 0
        self._request_count = 0

        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not configured - AI responses will fail")

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
            # Validate inputs
            if not incoming_message or not incoming_message.strip():
                return self._create_fallback_response(
                    "empty_input",
                    "Thanks for reaching out! What can I help you with today?",
                    warnings=["Empty input message received"]
                )

            # Build the prompt with rich context
            system_prompt = self._build_system_prompt(
                lead_context=lead_context,
                current_state=current_state,
                qualification_data=qualification_data,
                lead_profile=lead_profile,
            )

            # Build conversation messages for context
            messages = self._build_messages(
                incoming_message=incoming_message,
                conversation_history=conversation_history,
            )

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

    def _build_system_prompt(
        self,
        lead_context: Dict[str, Any],
        current_state: str,
        qualification_data: Dict[str, Any] = None,
        lead_profile: Optional[LeadProfile] = None,
    ) -> str:
        """
        Build comprehensive system prompt with rich lead context.

        This is the key method for providing excellent context to the LLM.
        The more relevant context we provide, the better the conversation.
        """
        personality_prompt = self.PERSONALITY_PROMPTS.get(
            self.personality,
            self.PERSONALITY_PROMPTS["friendly_casual"]
        )

        state_guidance = self.STATE_GUIDANCE.get(current_state, "")

        # Use rich lead profile if available, otherwise fall back to basic context
        if lead_profile:
            context_section = self._build_rich_context(lead_profile, current_state, qualification_data)
        else:
            context_section = self._build_basic_context(lead_context, current_state, qualification_data)

        # Build the complete prompt
        return f"""You are {self.agent_name}, a real estate assistant with {self.brokerage_name}.

{personality_prompt}

{context_section}

STATE-SPECIFIC GUIDANCE:
{state_guidance}

CRITICAL RULES:
1. RESPONSE LENGTH: Keep under 160 characters for SMS. This is critical!
2. ONE QUESTION: Ask only ONE question per message
3. NO PRESSURE: Never use high-pressure tactics or artificial urgency
4. HANDOFF TRIGGERS: Set should_handoff=true if:
   - They explicitly ask for a human/real person
   - They seem frustrated, angry, or use profanity
   - They mention legal issues, complaints, or threats
   - The conversation is going in circles
   - They have complex questions you can't answer
5. EXTRACT INFO: Parse their messages for timeline, budget, location, pre-approval status
6. NATURAL FLOW: Reference their previous answers to show you're listening
7. PERSONALIZE: Use the lead profile info to make responses relevant and personal

RESPONSE FORMAT:
You must respond with ONLY valid JSON (no markdown, no code blocks, no explanation):
{{
    "response": "Your SMS message here (under 160 chars)",
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
    ) -> str:
        """
        Build rich context string from LeadProfile.

        This provides the LLM with comprehensive information for personalized responses.
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

    def _generate_conversation_hints(self, profile: LeadProfile, current_state: str) -> List[str]:
        """
        Generate strategic conversation hints based on lead profile.

        These hints help the LLM make more relevant, personalized responses.
        """
        hints = []

        # Source-based hints
        if profile.interested_property_address:
            hints.append(f"They inquired about a specific property ({profile.interested_property_address}) - ask if they want to schedule a showing!")

        if profile.source and "zillow" in profile.source.lower():
            hints.append("They came from Zillow - they're likely comparing agents/properties")

        if profile.source and "referral" in profile.source.lower():
            hints.append("They were referred - mention you appreciate the referral!")

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

    async def _generate_with_retry(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
    ) -> Tuple[str, str, int]:
        """
        Generate response with retry logic and model fallback.

        Returns:
            Tuple of (response_text, model_used, tokens_used)
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
                        messages=messages,
                    )

                    # Extract response
                    response_text = response.content[0].text
                    tokens_used = response.usage.input_tokens + response.usage.output_tokens

                    # Track usage
                    self._total_tokens_used += tokens_used
                    self._request_count += 1

                    logger.info(f"AI response generated with {model}, tokens: {tokens_used}")
                    return response_text, model, tokens_used

                except Exception as e:
                    last_error = e
                    error_str = str(e).lower()

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
        if len(response) > self.MAX_SMS_LENGTH:
            warnings.append(f"Response too long ({len(response)} chars, max {self.MAX_SMS_LENGTH})")

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
        if len(warnings) == 0 and len(response) <= self.MAX_SMS_LENGTH:
            return ResponseQuality.EXCELLENT, warnings
        elif len(warnings) <= 1 and len(response) <= self.MAX_SMS_LENGTH + 20:
            return ResponseQuality.GOOD, warnings
        elif len(warnings) <= 2:
            return ResponseQuality.ACCEPTABLE, warnings
        else:
            return ResponseQuality.POOR, warnings

    def _improve_response(self, response: str, current_state: str) -> Optional[str]:
        """Attempt to improve a poor quality response."""
        # Truncate if too long
        if len(response) > self.MAX_SMS_LENGTH:
            # Try to truncate at a natural break point
            truncated = response[:self.MAX_SMS_LENGTH]

            # Find last complete sentence
            last_period = truncated.rfind(".")
            last_question = truncated.rfind("?")
            last_exclaim = truncated.rfind("!")

            break_point = max(last_period, last_question, last_exclaim)

            if break_point > self.MAX_SMS_LENGTH // 2:
                return truncated[:break_point + 1]

            # Just truncate with ellipsis
            return truncated[:self.MAX_SMS_LENGTH - 3] + "..."

        return response

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
