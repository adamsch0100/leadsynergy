"""
Response Template Engine - Personalized Message Templates.

Provides:
1. Pre-written templates for common scenarios (faster than LLM, guaranteed quality)
2. Variable substitution with lead profile data
3. A/B testing variants for optimization with performance tracking
4. Fallback templates when LLM fails
5. Conditional content based on lead attributes

Templates follow the friendly, casual tone and stay under SMS length limits.
"""

import logging
import random
import re
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class TemplateCategory(Enum):
    """Categories of message templates."""
    WELCOME = "welcome"
    QUALIFICATION = "qualification"
    FOLLOW_UP = "follow_up"
    OBJECTION = "objection"
    SCHEDULING = "scheduling"
    CONFIRMATION = "confirmation"
    NURTURE = "nurture"
    RE_ENGAGEMENT = "re_engagement"
    HANDOFF = "handoff"
    PROPERTY = "property"


class LeadTemperature(Enum):
    """Lead temperature for template selection."""
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


@dataclass
class TemplateVariable:
    """A variable that can be substituted in templates."""
    name: str
    default_value: str = ""
    formatter: Optional[Callable[[Any], str]] = None
    required: bool = False


@dataclass
class ABTestRecord:
    """Record of an A/B test variant usage for tracking performance."""
    id: str
    template_category: str
    template_id: str
    variant_index: int
    variant_name: str
    conversation_id: Optional[str] = None
    lead_id: Optional[str] = None
    sent_at: datetime = field(default_factory=datetime.utcnow)
    got_response: Optional[bool] = None
    response_time_seconds: Optional[int] = None
    led_to_appointment: bool = False
    led_to_optout: bool = False


@dataclass
class MessageTemplate:
    """A single message template with variants."""
    id: str
    category: TemplateCategory
    name: str
    variants: List[str]  # Multiple versions for A/B testing
    variables: List[str]  # Variable names used
    conditions: Dict[str, Any] = field(default_factory=dict)  # When to use
    temperature: Optional[LeadTemperature] = None
    max_chars: int = 1000
    tags: List[str] = field(default_factory=list)

    def render(
        self,
        variables: Dict[str, Any],
        variant_index: int = None,
    ) -> str:
        """
        Render template with variable substitution.

        Args:
            variables: Dict of variable name -> value
            variant_index: Specific variant to use (random if None)

        Returns:
            Rendered message string
        """
        # Select variant
        if variant_index is not None and 0 <= variant_index < len(self.variants):
            template = self.variants[variant_index]
        else:
            template = random.choice(self.variants)

        # Substitute variables
        result = template
        for var_name in self.variables:
            placeholder = f"{{{var_name}}}"
            value = variables.get(var_name, "")

            # Handle special formatting
            if var_name.endswith("_price") and isinstance(value, (int, float)):
                value = f"${value:,.0f}"
            elif var_name == "first_name" and not value:
                value = "there"

            result = result.replace(placeholder, str(value))

        # Handle conditional blocks {?condition:text}
        result = self._process_conditionals(result, variables)

        # Truncate if too long
        if len(result) > self.max_chars:
            result = result[:self.max_chars - 3] + "..."

        return result.strip()

    def _process_conditionals(self, text: str, variables: Dict[str, Any]) -> str:
        """Process conditional blocks in template."""
        # Pattern: {?var_name:text to show if truthy}
        pattern = r'\{\?(\w+):([^}]+)\}'

        def replace_conditional(match):
            var_name = match.group(1)
            conditional_text = match.group(2)
            if variables.get(var_name):
                return conditional_text
            return ""

        return re.sub(pattern, replace_conditional, text)


class TemplateLibrary:
    """
    Library of all message templates.

    Organized by category and searchable by conditions.
    """

    TEMPLATES: Dict[str, MessageTemplate] = {}

    @classmethod
    def _init_templates(cls):
        """Initialize all templates."""
        if cls.TEMPLATES:
            return

        templates = [
            # ==================== WELCOME TEMPLATES ====================
            MessageTemplate(
                id="welcome_new_lead",
                category=TemplateCategory.WELCOME,
                name="New Lead Welcome",
                variants=[
                    "Hey {first_name}! I'm {agent_name} - saw you were checking out places in {area}. Super cool area! Are you just starting to look around or getting closer to making a move?",
                    "Hi {first_name}! This is {agent_name}. I noticed you were looking at homes in {area} - great choice! What's got you interested in that area?",
                    "Hey {first_name}! {agent_name} here. I see you're interested in {area}! Are you thinking about buying soon, or just exploring what's out there?",
                ],
                variables=["first_name", "agent_name", "area"],
            ),
            MessageTemplate(
                id="welcome_property_inquiry",
                category=TemplateCategory.WELCOME,
                name="Property Inquiry Welcome",
                variants=[
                    "Hey {first_name}! Thanks for reaching out about {property_address}. It's a great place! Want me to set up a time to show you around?",
                    "Hi {first_name}! I see you're interested in the property at {property_address}. I'd love to tell you more - what questions do you have?",
                    "Hey {first_name}! That property at {property_address} is awesome - {?property_feature:it has {property_feature}!} Would you like to schedule a tour?",
                ],
                variables=["first_name", "property_address", "property_feature"],
            ),
            MessageTemplate(
                id="welcome_referral",
                category=TemplateCategory.WELCOME,
                name="Referral Welcome",
                variants=[
                    "Hey {first_name}! {referrer_name} mentioned you might be looking for a new place - that's so great they thought of you! How can I help?",
                    "Hi {first_name}! {referrer_name} told me to reach out. I'd love to help you find your next home! What are you looking for?",
                ],
                variables=["first_name", "referrer_name"],
            ),

            # ==================== QUALIFICATION TEMPLATES ====================
            MessageTemplate(
                id="qual_timeline",
                category=TemplateCategory.QUALIFICATION,
                name="Timeline Question",
                variants=[
                    "So what's your timeline looking like? Trying to move soon or just exploring what's out there?",
                    "Any idea when you're hoping to make a move? Just curious where you're at in the process!",
                    "Are you looking to move pretty soon, or more just seeing what's available right now?",
                ],
                variables=[],
                tags=["timeline"],
            ),
            MessageTemplate(
                id="qual_budget",
                category=TemplateCategory.QUALIFICATION,
                name="Budget Question",
                variants=[
                    "Have you figured out your budget yet, or still working on that part?",
                    "Do you have a price range in mind? Just helps me know what to look for!",
                    "What are you thinking budget-wise? No pressure - just helps me find the right matches!",
                ],
                variables=[],
                tags=["budget"],
            ),
            MessageTemplate(
                id="qual_location",
                category=TemplateCategory.QUALIFICATION,
                name="Location Question",
                variants=[
                    "Any specific areas you're really into? I can keep an eye out for new listings there!",
                    "Where are you hoping to end up? Got any neighborhoods or areas in mind?",
                    "What areas are you looking at? Close to work, good schools, nightlife - what matters most?",
                ],
                variables=[],
                tags=["location"],
            ),
            MessageTemplate(
                id="qual_preapproval",
                category=TemplateCategory.QUALIFICATION,
                name="Pre-approval Question",
                variants=[
                    "Have you chatted with a lender yet about getting pre-approved? I know some great ones if you need a rec!",
                    "Are you pre-approved already, or is that something you still need to do?",
                    "Quick question - have you talked to a mortgage person yet? Just helps sellers take offers more seriously!",
                ],
                variables=[],
                tags=["pre_approval"],
            ),

            # ==================== SCHEDULING TEMPLATES ====================
            MessageTemplate(
                id="schedule_offer",
                category=TemplateCategory.SCHEDULING,
                name="Offer to Schedule",
                variants=[
                    "I'd love to help you find the right place! Want to hop on a quick 15-min call this week? I'm free {time_option_1} or {time_option_2} - which works better?",
                    "Should we set up a quick call to chat more? I've got {time_option_1} or {time_option_2} available!",
                    "Want to schedule a quick chat? I can do {time_option_1} or {time_option_2} - what works for you?",
                ],
                variables=["time_option_1", "time_option_2"],
                temperature=LeadTemperature.HOT,
            ),
            MessageTemplate(
                id="schedule_showing",
                category=TemplateCategory.SCHEDULING,
                name="Showing Offer",
                variants=[
                    "Want to see it in person? I could show you around {time_option_1} or {time_option_2}!",
                    "I'd love to show you the place! Does {time_option_1} or {time_option_2} work for a tour?",
                    "Let's get you in there! I'm free {time_option_1} or {time_option_2} for a showing - which is better?",
                ],
                variables=["time_option_1", "time_option_2"],
            ),
            MessageTemplate(
                id="schedule_confirm_time",
                category=TemplateCategory.SCHEDULING,
                name="Time Selection Confirmation",
                variants=[
                    "Perfect! {selected_time} it is. I'll send you a calendar invite. See you then, {first_name}!",
                    "Awesome, you're all set for {selected_time}! I'll send over the details. Can't wait to chat!",
                    "Great choice! I've got you down for {selected_time}. Looking forward to it!",
                ],
                variables=["first_name", "selected_time"],
            ),

            # ==================== CONFIRMATION TEMPLATES ====================
            MessageTemplate(
                id="confirm_appointment",
                category=TemplateCategory.CONFIRMATION,
                name="Appointment Confirmation",
                variants=[
                    "Hey {first_name}! Just confirming we're all set for {appointment_date} at {appointment_time}. See you then!",
                    "Quick reminder - we're meeting {appointment_date} at {appointment_time}! Let me know if anything changes.",
                    "All set for {appointment_date} at {appointment_time}! Text me if you have any questions before then!",
                ],
                variables=["first_name", "appointment_date", "appointment_time"],
            ),
            MessageTemplate(
                id="confirm_appointment_details",
                category=TemplateCategory.CONFIRMATION,
                name="Appointment Details",
                variants=[
                    "Perfect! Here are the details:\n{appointment_date} at {appointment_time}\n{?location:📍 {location}}\nSee you soon!",
                ],
                variables=["appointment_date", "appointment_time", "location"],
            ),

            # ==================== FOLLOW-UP TEMPLATES ====================
            MessageTemplate(
                id="followup_no_response_1",
                category=TemplateCategory.FOLLOW_UP,
                name="First Follow-up",
                variants=[
                    "Hey {first_name}! Just checking in - did you get my last message? Happy to help whenever you're ready!",
                    "Hi {first_name}! Just following up. Let me know if you have any questions about homes in {area}!",
                    "Hey {first_name}! Still here if you need anything. No rush - just wanted to make sure you're all set!",
                ],
                variables=["first_name", "area"],
            ),
            MessageTemplate(
                id="followup_no_response_2",
                category=TemplateCategory.FOLLOW_UP,
                name="Second Follow-up",
                variants=[
                    "Hey {first_name}! Hope you're having a great week. Any updates on your home search? I'm here if you need me!",
                    "Hi {first_name}! Just wanted to touch base. Still thinking about {area}? I'd love to help when you're ready!",
                ],
                variables=["first_name", "area"],
            ),
            MessageTemplate(
                id="followup_after_showing",
                category=TemplateCategory.FOLLOW_UP,
                name="Post-Showing Follow-up",
                variants=[
                    "Hey {first_name}! Great meeting you today! What did you think of the place? Any other homes you want to check out?",
                    "It was awesome showing you around today! Let me know your thoughts - and if you want to see more places!",
                ],
                variables=["first_name"],
            ),

            # ==================== NURTURE TEMPLATES ====================
            MessageTemplate(
                id="nurture_market_update",
                category=TemplateCategory.NURTURE,
                name="Market Update",
                variants=[
                    "Hey {first_name}! Quick market update - {market_update}. Thought you'd want to know! How's the search going?",
                    "Hi {first_name}! FYI - {market_update}. Let me know if you want to chat about what this means for your search!",
                ],
                variables=["first_name", "market_update"],
                temperature=LeadTemperature.COLD,
            ),
            MessageTemplate(
                id="nurture_new_listing",
                category=TemplateCategory.NURTURE,
                name="New Listing Alert",
                variants=[
                    "Hey {first_name}! Just saw a new listing pop up in {area} - {property_summary}. Want details?",
                    "Hi {first_name}! New listing alert! There's a {property_summary} in {area}. Thought of you - interested?",
                ],
                variables=["first_name", "area", "property_summary"],
            ),

            # ==================== RE-ENGAGEMENT TEMPLATES ====================
            MessageTemplate(
                id="re_engage_cold",
                category=TemplateCategory.RE_ENGAGEMENT,
                name="Cold Lead Re-engagement",
                variants=[
                    "Hey {first_name}! Been a while - hope you're doing great! I just saw some new listings pop up in {area} and thought of you. Still on the hunt?",
                    "Hi {first_name}! Long time no talk! The market in {area} has been interesting lately. Are you still thinking about making a move?",
                    "Hey {first_name}! Just checking in after a while. Has anything changed with your home search, or are you still exploring?",
                ],
                variables=["first_name", "area"],
                temperature=LeadTemperature.COLD,
            ),

            # ==================== HANDOFF TEMPLATES ====================
            MessageTemplate(
                id="handoff_to_agent",
                category=TemplateCategory.HANDOFF,
                name="Human Agent Handoff",
                variants=[
                    "Perfect timing, {first_name}! I'm connecting you with {human_agent_name}, our local market expert who's helped dozens of buyers find their dream homes. They'll reach out within the hour with exactly what you need. You're in great hands!",
                    "Awesome, {first_name}! {human_agent_name} is our specialist for this area and knows the market inside-out. They'll follow up today with personalized insights and next steps. Excited for you!",
                    "Great call, {first_name}! {human_agent_name} is the perfect person to help you - they've closed over 50 deals in this market and get outstanding results. Expect a call/text within a few hours with your next steps!",
                ],
                variables=["first_name", "human_agent_name"],
            ),
            MessageTemplate(
                id="handoff_complex_question",
                category=TemplateCategory.HANDOFF,
                name="Complex Question Handoff",
                variants=[
                    "Great question! Let me have {human_agent_name} get back to you on that - they know way more about this than I do!",
                    "That's a good one! I'll have {human_agent_name} reach out to give you the full scoop.",
                ],
                variables=["human_agent_name"],
            ),

            # ==================== PROPERTY TEMPLATES ====================
            MessageTemplate(
                id="property_info",
                category=TemplateCategory.PROPERTY,
                name="Property Information",
                variants=[
                    "That property at {property_address} is {property_beds}bd/{property_baths}ba, {property_sqft} sqft, listed at {property_price}. Want to see it?",
                    "Great choice! {property_address}: {property_beds} beds, {property_baths} baths, {property_sqft} sqft for {property_price}. Should I schedule a showing?",
                ],
                variables=["property_address", "property_beds", "property_baths", "property_sqft", "property_price"],
            ),
        ]

        for template in templates:
            cls.TEMPLATES[template.id] = template

    @classmethod
    def get_template(cls, template_id: str) -> Optional[MessageTemplate]:
        """Get template by ID."""
        cls._init_templates()
        return cls.TEMPLATES.get(template_id)

    @classmethod
    def get_templates_by_category(
        cls,
        category: TemplateCategory,
    ) -> List[MessageTemplate]:
        """Get all templates in a category."""
        cls._init_templates()
        return [t for t in cls.TEMPLATES.values() if t.category == category]

    @classmethod
    def get_templates_by_tag(cls, tag: str) -> List[MessageTemplate]:
        """Get templates with a specific tag."""
        cls._init_templates()
        return [t for t in cls.TEMPLATES.values() if tag in t.tags]

    @classmethod
    def get_templates_by_temperature(
        cls,
        temperature: LeadTemperature,
    ) -> List[MessageTemplate]:
        """Get templates for a specific lead temperature."""
        cls._init_templates()
        return [t for t in cls.TEMPLATES.values() if t.temperature == temperature]


class ResponseTemplateEngine:
    """
    Engine for selecting and rendering message templates.

    Provides intelligent template selection based on:
    - Conversation context
    - Lead profile
    - Message category
    - A/B test tracking with performance analytics
    """

    def __init__(self, supabase_client=None):
        """Initialize the template engine."""
        self._ab_test_assignments: Dict[str, Dict[str, int]] = {}
        self._supabase = supabase_client
        self._pending_ab_records: Dict[str, ABTestRecord] = {}  # Track records awaiting outcome
        TemplateLibrary._init_templates()

    def set_supabase_client(self, client):
        """Set or update the supabase client."""
        self._supabase = client

    def get_message(
        self,
        template_id: str,
        variables: Dict[str, Any],
        lead_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        track_ab_test: bool = True,
    ) -> Optional[str]:
        """
        Get a rendered message from a template.

        Args:
            template_id: Template ID to use
            variables: Variables for substitution
            lead_id: Optional lead ID for A/B testing
            conversation_id: Optional conversation ID for tracking
            track_ab_test: Whether to log A/B test usage (default True)

        Returns:
            Rendered message string or None if template not found
        """
        template = TemplateLibrary.get_template(template_id)
        if not template:
            logger.warning(f"Template not found: {template_id}")
            return None

        # Get consistent variant for A/B testing
        variant_index = None
        if lead_id and len(template.variants) > 1:
            variant_index = self._get_ab_variant(lead_id, template_id, len(template.variants))

            # Track A/B test usage if enabled
            if track_ab_test:
                self._log_ab_test_usage(
                    template=template,
                    variant_index=variant_index,
                    lead_id=lead_id,
                    conversation_id=conversation_id,
                )

        return template.render(variables, variant_index)

    def get_welcome_message(
        self,
        lead_profile: Dict[str, Any],
        agent_name: str = "Sarah",
    ) -> str:
        """
        Get appropriate welcome message based on lead source.

        Args:
            lead_profile: Lead profile data
            agent_name: Name of the AI agent

        Returns:
            Rendered welcome message
        """
        variables = {
            "first_name": lead_profile.get("first_name", "there"),
            "agent_name": agent_name,
            "area": lead_profile.get("interested_area", lead_profile.get("source_area", "the area")),
        }

        # Property inquiry
        if lead_profile.get("interested_property_address"):
            variables["property_address"] = lead_profile["interested_property_address"]
            variables["property_feature"] = lead_profile.get("property_feature", "")
            return self.get_message("welcome_property_inquiry", variables, lead_profile.get("id"))

        # Referral
        if lead_profile.get("referrer_name"):
            variables["referrer_name"] = lead_profile["referrer_name"]
            return self.get_message("welcome_referral", variables, lead_profile.get("id"))

        # Default new lead
        return self.get_message("welcome_new_lead", variables, lead_profile.get("id"))

    def get_qualification_question(
        self,
        question_type: str,
        variables: Dict[str, Any] = None,
        lead_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get a qualification question by type.

        Args:
            question_type: Type of question (timeline, budget, location, preapproval)
            variables: Optional variables
            lead_id: Optional lead ID for A/B testing

        Returns:
            Rendered question or None
        """
        template_map = {
            "timeline": "qual_timeline",
            "budget": "qual_budget",
            "location": "qual_location",
            "preapproval": "qual_preapproval",
            "pre_approval": "qual_preapproval",
        }

        template_id = template_map.get(question_type.lower())
        if not template_id:
            return None

        return self.get_message(template_id, variables or {}, lead_id)

    def get_followup_message(
        self,
        followup_number: int,
        variables: Dict[str, Any],
        lead_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get follow-up message based on sequence number.

        Args:
            followup_number: Which follow-up (1, 2, etc.)
            variables: Variables for rendering
            lead_id: Optional lead ID

        Returns:
            Rendered follow-up message
        """
        if followup_number <= 1:
            template_id = "followup_no_response_1"
        else:
            template_id = "followup_no_response_2"

        return self.get_message(template_id, variables, lead_id)

    def get_scheduling_message(
        self,
        time_options: List[str],
        variables: Dict[str, Any] = None,
        lead_id: Optional[str] = None,
        is_showing: bool = False,
    ) -> Optional[str]:
        """
        Get scheduling message with time options.

        Args:
            time_options: List of available time strings
            variables: Additional variables
            lead_id: Optional lead ID
            is_showing: Whether this is for a property showing

        Returns:
            Rendered scheduling message
        """
        vars_dict = variables or {}
        vars_dict["time_option_1"] = time_options[0] if len(time_options) > 0 else "tomorrow"
        vars_dict["time_option_2"] = time_options[1] if len(time_options) > 1 else "later this week"

        template_id = "schedule_showing" if is_showing else "schedule_offer"
        return self.get_message(template_id, vars_dict, lead_id)

    def get_confirmation_message(
        self,
        appointment_date: str,
        appointment_time: str,
        first_name: str,
        location: Optional[str] = None,
        lead_id: Optional[str] = None,
    ) -> str:
        """Get appointment confirmation message."""
        variables = {
            "first_name": first_name,
            "appointment_date": appointment_date,
            "appointment_time": appointment_time,
            "location": location or "",
        }

        template_id = "confirm_appointment_details" if location else "confirm_appointment"
        return self.get_message(template_id, variables, lead_id)

    def get_re_engagement_message(
        self,
        lead_profile: Dict[str, Any],
        agent_name: str = "Sarah",
    ) -> str:
        """Get re-engagement message for cold leads."""
        variables = {
            "first_name": lead_profile.get("first_name", "there"),
            "area": lead_profile.get("interested_area", lead_profile.get("preferred_area", "the area")),
            "agent_name": agent_name,
        }
        return self.get_message("re_engage_cold", variables, lead_profile.get("id"))

    def get_handoff_message(
        self,
        first_name: str,
        human_agent_name: str,
        is_complex_question: bool = False,
        lead_id: Optional[str] = None,
    ) -> str:
        """Get handoff message when transitioning to human."""
        variables = {
            "first_name": first_name,
            "human_agent_name": human_agent_name,
        }

        template_id = "handoff_complex_question" if is_complex_question else "handoff_to_agent"
        return self.get_message(template_id, variables, lead_id)

    def _get_ab_variant(
        self,
        lead_id: str,
        template_id: str,
        num_variants: int,
    ) -> int:
        """
        Get consistent A/B variant for a lead/template combination.

        Uses lead_id to ensure consistent variant selection.
        """
        # Check cache first
        if lead_id in self._ab_test_assignments:
            if template_id in self._ab_test_assignments[lead_id]:
                return self._ab_test_assignments[lead_id][template_id]

        # Generate deterministic variant based on lead_id and template_id
        hash_input = f"{lead_id}:{template_id}"
        hash_value = hash(hash_input)
        variant = abs(hash_value) % num_variants

        # Cache the assignment
        if lead_id not in self._ab_test_assignments:
            self._ab_test_assignments[lead_id] = {}
        self._ab_test_assignments[lead_id][template_id] = variant

        return variant

    def _log_ab_test_usage(
        self,
        template: MessageTemplate,
        variant_index: int,
        lead_id: str,
        conversation_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Log A/B test variant usage to database.

        Args:
            template: The template being used
            variant_index: Which variant was selected
            lead_id: Lead ID
            conversation_id: Optional conversation ID

        Returns:
            Record ID for later outcome tracking
        """
        if not self._supabase:
            logger.debug("No supabase client - skipping A/B test logging")
            return None

        try:
            record_id = str(uuid.uuid4())
            variant_name = f"variant_{variant_index + 1}"  # 1-indexed for display

            data = {
                "id": record_id,
                "template_category": template.category.value,
                "template_id": template.id,
                "variant_index": variant_index,
                "variant_name": variant_name,
                "conversation_id": conversation_id,
                "lead_id": lead_id,
                "sent_at": datetime.utcnow().isoformat(),
            }

            self._supabase.table("ab_test_results").insert(data).execute()

            # Track in pending records for outcome updates
            record = ABTestRecord(
                id=record_id,
                template_category=template.category.value,
                template_id=template.id,
                variant_index=variant_index,
                variant_name=variant_name,
                conversation_id=conversation_id,
                lead_id=lead_id,
            )
            self._pending_ab_records[record_id] = record

            # Also index by conversation for easy lookup
            if conversation_id:
                self._pending_ab_records[f"conv:{conversation_id}"] = record

            logger.debug(
                f"Logged A/B test: template={template.id}, variant={variant_name}"
            )
            return record_id

        except Exception as e:
            logger.error(f"Error logging A/B test usage: {e}")
            return None

    def record_ab_test_response(
        self,
        conversation_id: str,
        response_time_seconds: Optional[int] = None,
    ) -> bool:
        """
        Record that a lead responded to a message.

        Args:
            conversation_id: Conversation that got a response
            response_time_seconds: Time between send and response

        Returns:
            True if recorded successfully
        """
        if not self._supabase:
            return False

        try:
            # Find the most recent A/B test record for this conversation
            result = self._supabase.table("ab_test_results").select(
                "id"
            ).eq(
                "conversation_id", conversation_id
            ).is_(
                "got_response", "null"
            ).order(
                "sent_at", desc=True
            ).limit(1).execute()

            if not result.data:
                return False

            record_id = result.data[0]["id"]
            update_data = {"got_response": True}
            if response_time_seconds is not None:
                update_data["response_time_seconds"] = response_time_seconds

            self._supabase.table("ab_test_results").update(
                update_data
            ).eq("id", record_id).execute()

            logger.debug(f"Recorded A/B test response for conversation {conversation_id}")
            return True

        except Exception as e:
            logger.error(f"Error recording A/B test response: {e}")
            return False

    def record_ab_test_outcome(
        self,
        conversation_id: str,
        led_to_appointment: bool = False,
        led_to_optout: bool = False,
    ) -> bool:
        """
        Record the final outcome of an A/B test.

        Args:
            conversation_id: Conversation ID
            led_to_appointment: Whether this led to an appointment
            led_to_optout: Whether the lead opted out

        Returns:
            True if recorded successfully
        """
        if not self._supabase:
            return False

        try:
            # Update all A/B test records for this conversation
            update_data = {}
            if led_to_appointment:
                update_data["led_to_appointment"] = True
            if led_to_optout:
                update_data["led_to_optout"] = True

            if not update_data:
                return True

            self._supabase.table("ab_test_results").update(
                update_data
            ).eq("conversation_id", conversation_id).execute()

            logger.debug(
                f"Recorded A/B test outcome: conversation={conversation_id}, "
                f"appointment={led_to_appointment}, optout={led_to_optout}"
            )
            return True

        except Exception as e:
            logger.error(f"Error recording A/B test outcome: {e}")
            return False

    async def get_ab_test_performance(
        self,
        template_id: Optional[str] = None,
        template_category: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get A/B test performance statistics.

        Args:
            template_id: Filter by specific template
            template_category: Filter by category
            days: Number of days to look back

        Returns:
            Dict with variant performance statistics
        """
        if not self._supabase:
            return {"error": "No database connection"}

        try:
            from datetime import timedelta
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

            # Build query
            query = self._supabase.table("ab_test_results").select("*").gte(
                "sent_at", cutoff
            )

            if template_id:
                query = query.eq("template_id", template_id)
            if template_category:
                query = query.eq("template_category", template_category)

            result = query.execute()

            if not result.data:
                return {"variants": [], "total_tests": 0}

            # Aggregate by variant
            variants: Dict[str, Dict[str, Any]] = {}
            for row in result.data:
                variant_key = f"{row['template_id']}:{row['variant_name']}"
                if variant_key not in variants:
                    variants[variant_key] = {
                        "template_id": row["template_id"],
                        "template_category": row["template_category"],
                        "variant_name": row["variant_name"],
                        "variant_index": row["variant_index"],
                        "total_sent": 0,
                        "responses": 0,
                        "appointments": 0,
                        "optouts": 0,
                        "total_response_time": 0,
                        "response_count_with_time": 0,
                    }

                v = variants[variant_key]
                v["total_sent"] += 1
                if row.get("got_response"):
                    v["responses"] += 1
                if row.get("led_to_appointment"):
                    v["appointments"] += 1
                if row.get("led_to_optout"):
                    v["optouts"] += 1
                if row.get("response_time_seconds"):
                    v["total_response_time"] += row["response_time_seconds"]
                    v["response_count_with_time"] += 1

            # Calculate rates
            variant_list = []
            for key, v in variants.items():
                v["response_rate"] = (
                    round(v["responses"] / v["total_sent"] * 100, 1)
                    if v["total_sent"] > 0 else 0
                )
                v["appointment_rate"] = (
                    round(v["appointments"] / v["total_sent"] * 100, 1)
                    if v["total_sent"] > 0 else 0
                )
                v["optout_rate"] = (
                    round(v["optouts"] / v["total_sent"] * 100, 1)
                    if v["total_sent"] > 0 else 0
                )
                v["avg_response_time"] = (
                    round(v["total_response_time"] / v["response_count_with_time"])
                    if v["response_count_with_time"] > 0 else None
                )
                # Clean up internal fields
                del v["total_response_time"]
                del v["response_count_with_time"]
                variant_list.append(v)

            # Sort by response rate descending
            variant_list.sort(key=lambda x: x["response_rate"], reverse=True)

            return {
                "variants": variant_list,
                "total_tests": len(result.data),
                "period_days": days,
            }

        except Exception as e:
            logger.error(f"Error getting A/B test performance: {e}")
            return {"error": str(e)}

    def get_fallback_message(
        self,
        category: TemplateCategory,
        variables: Dict[str, Any],
    ) -> str:
        """
        Get a fallback message when LLM fails.

        Args:
            category: What type of message is needed
            variables: Variables for substitution

        Returns:
            Rendered fallback message
        """
        templates = TemplateLibrary.get_templates_by_category(category)
        if templates:
            template = random.choice(templates)
            return template.render(variables)

        # Ultimate fallback
        first_name = variables.get("first_name", "there")
        return f"Hey {first_name}! Thanks for reaching out. What can I help you with?"


# Singleton for convenience
_engine_instance: Optional[ResponseTemplateEngine] = None


def get_template_engine(supabase_client=None) -> ResponseTemplateEngine:
    """
    Get singleton template engine instance.

    Args:
        supabase_client: Optional supabase client for A/B test tracking

    Returns:
        ResponseTemplateEngine instance
    """
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ResponseTemplateEngine(supabase_client)
    elif supabase_client and not _engine_instance._supabase:
        _engine_instance.set_supabase_client(supabase_client)
    return _engine_instance
