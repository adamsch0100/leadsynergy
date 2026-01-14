"""
AI Agent Service - Main Orchestrator for Lead Conversations.

This is the central coordinator that ties together all AI agent components:
- Intent detection
- Conversation state management
- Response generation (LLM + templates)
- Qualification flow
- Objection handling
- Compliance checking
- Lead scoring
- Appointment scheduling
- Handoff management

The service processes incoming messages and returns appropriate responses
while maintaining conversation state and extracting valuable information.
"""

import logging
import asyncio
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum

logger = logging.getLogger(__name__)

# Import settings service
from app.ai_agent.settings_service import (
    AIAgentSettings as DBAgentSettings,
    AIAgentSettingsService,
    get_settings_service,
)

# Import all components
from app.ai_agent.conversation_manager import (
    ConversationManager,
    ConversationState,
    ConversationContext,
)
from app.ai_agent.lead_scorer import LeadScorer, LeadScore
from app.ai_agent.compliance_checker import ComplianceChecker, ComplianceStatus
from app.ai_agent.response_generator import (
    AIResponseGenerator,
    GeneratedResponse,
    LeadProfile,
    ResponseQuality,
)
from app.ai_agent.intent_detector import (
    IntentDetector,
    Intent,
    DetectedIntent,
)
from app.ai_agent.qualification_flow import (
    QualificationFlowManager,
    QualificationData,
    QualificationProgress,
)
from app.ai_agent.objection_handler import (
    ObjectionHandler,
    ObjectionType,
    ObjectionResponse,
    ObjectionContext,
)
from app.ai_agent.template_engine import (
    ResponseTemplateEngine,
    TemplateCategory,
)


class ProcessingResult(Enum):
    """Result of message processing."""
    SUCCESS = "success"
    COMPLIANCE_BLOCKED = "compliance_blocked"
    HANDOFF_TRIGGERED = "handoff_triggered"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class AgentResponse:
    """Complete response from the AI agent."""
    # The response to send
    response_text: str
    channel: str = "sms"  # sms, email

    # Processing details
    result: ProcessingResult = ProcessingResult.SUCCESS
    error_message: Optional[str] = None

    # State information
    conversation_state: str = ""
    previous_state: str = ""
    state_changed: bool = False

    # Intent and sentiment
    detected_intent: Optional[str] = None
    detected_sentiment: str = "neutral"

    # Scoring
    lead_score: int = 0
    lead_score_delta: int = 0

    # Extracted information
    extracted_info: Dict[str, Any] = field(default_factory=dict)
    qualification_progress: float = 0.0

    # Handoff information
    should_handoff: bool = False
    handoff_reason: Optional[str] = None
    handoff_to_agent_id: Optional[str] = None

    # Scheduling information
    appointment_requested: bool = False
    suggested_times: List[str] = field(default_factory=list)

    # Channel preference (smart routing)
    channel_preference_changed: bool = False
    preferred_channel: Optional[str] = None  # sms, email, call
    channel_reduction_requested: Optional[str] = None  # sms, email (reduce frequency)

    # Compliance
    compliance_status: ComplianceStatus = ComplianceStatus.COMPLIANT

    # Metadata
    response_time_ms: int = 0
    model_used: str = ""
    template_used: Optional[str] = None
    tokens_used: int = 0
    used_fallback: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/API response."""
        return {
            "response_text": self.response_text,
            "channel": self.channel,
            "result": self.result.value,
            "error_message": self.error_message,
            "conversation_state": self.conversation_state,
            "previous_state": self.previous_state,
            "state_changed": self.state_changed,
            "detected_intent": self.detected_intent,
            "detected_sentiment": self.detected_sentiment,
            "lead_score": self.lead_score,
            "lead_score_delta": self.lead_score_delta,
            "extracted_info": self.extracted_info,
            "qualification_progress": self.qualification_progress,
            "should_handoff": self.should_handoff,
            "handoff_reason": self.handoff_reason,
            "appointment_requested": self.appointment_requested,
            "suggested_times": self.suggested_times,
            "channel_preference_changed": self.channel_preference_changed,
            "preferred_channel": self.preferred_channel,
            "channel_reduction_requested": self.channel_reduction_requested,
            "compliance_status": self.compliance_status.value,
            "response_time_ms": self.response_time_ms,
            "model_used": self.model_used,
            "template_used": self.template_used,
            "tokens_used": self.tokens_used,
            "used_fallback": self.used_fallback,
        }


@dataclass
class AgentSettings:
    """Configuration settings for the AI agent."""
    # Personality and identity
    agent_name: str = "Sarah"
    brokerage_name: str = "our team"
    personality: str = "friendly_casual"  # friendly_casual, professional, energetic

    # Response settings
    response_delay_seconds: int = 30  # Delay to feel more human
    max_response_length: int = 160  # SMS character limit

    # Qualification settings
    max_qualification_questions: int = 8
    auto_schedule_score_threshold: int = 70  # Score to auto-suggest scheduling

    # Handoff settings
    auto_handoff_score_threshold: int = 85  # Score to auto-handoff to human
    max_ai_messages_per_lead: int = 15

    # Working hours (local time)
    working_hours_start: int = 8  # 8 AM
    working_hours_end: int = 20  # 8 PM
    timezone: str = "America/New_York"

    # Feature flags
    use_llm_for_all_responses: bool = True
    use_templates_as_fallback: bool = True
    enable_a_b_testing: bool = True


class AIAgentService:
    """
    Main AI Agent Service - orchestrates all components.

    This is the primary interface for the AI agent. Call `process_message()`
    to handle incoming lead messages and get responses.

    Usage:
        agent = AIAgentService(settings=AgentSettings())
        response = await agent.process_message(
            message="Hi, I'm looking for a house",
            lead_profile=lead_profile,
            conversation_context=context,
        )
        if response.result == ProcessingResult.SUCCESS:
            send_sms(response.response_text)
    """

    def __init__(
        self,
        settings: AgentSettings = None,
        anthropic_api_key: str = None,
        supabase_client=None,
        user_id: str = None,
        organization_id: str = None,
    ):
        """
        Initialize the AI Agent Service.

        Args:
            settings: Agent configuration settings (overrides DB settings)
            anthropic_api_key: Anthropic API key for Claude
            supabase_client: Database client for state persistence
            user_id: User ID to load settings for
            organization_id: Organization ID for fallback settings
        """
        self.supabase = supabase_client
        self.user_id = user_id
        self.organization_id = organization_id
        self._settings_service = get_settings_service(supabase_client) if supabase_client else None
        self._db_settings: Optional[DBAgentSettings] = None

        # Use provided settings or defaults (DB settings loaded lazily)
        self.settings = settings or AgentSettings()

        # Initialize all components
        self.intent_detector = IntentDetector()
        self.compliance_checker = ComplianceChecker(supabase_client)
        self.lead_scorer = LeadScorer()
        self.objection_handler = ObjectionHandler()
        self.template_engine = ResponseTemplateEngine()

        # Response generator with settings (will be updated when DB settings load)
        self.response_generator = AIResponseGenerator(
            api_key=anthropic_api_key,
            personality=self.settings.personality,
            agent_name=self.settings.agent_name,
            brokerage_name=self.settings.brokerage_name,
        )

        # State managers (created per-conversation)
        self._conversation_managers: Dict[str, ConversationManager] = {}
        self._qualification_managers: Dict[str, QualificationFlowManager] = {}

        logger.info("AI Agent Service initialized")

    async def _load_db_settings(self, user_id: str = None, org_id: str = None) -> DBAgentSettings:
        """
        Load settings from database with caching.

        Args:
            user_id: User ID to load settings for
            org_id: Organization ID for fallback

        Returns:
            DBAgentSettings loaded from database
        """
        # Use provided IDs or fall back to instance IDs
        user_id = user_id or self.user_id
        org_id = org_id or self.organization_id

        if not self._settings_service:
            logger.warning("No settings service available - using defaults")
            return DBAgentSettings()

        settings = await self._settings_service.get_settings(user_id, org_id)
        self._db_settings = settings

        # Update local settings from DB
        if settings:
            self.settings.agent_name = settings.agent_name
            self.settings.brokerage_name = settings.brokerage_name
            self.settings.personality = settings.personality_tone
            self.settings.response_delay_seconds = settings.response_delay_seconds
            self.settings.working_hours_start = settings.working_hours_start.hour if isinstance(settings.working_hours_start, time) else 8
            self.settings.working_hours_end = settings.working_hours_end.hour if isinstance(settings.working_hours_end, time) else 20
            self.settings.timezone = settings.timezone
            self.settings.auto_handoff_score_threshold = settings.auto_handoff_score
            self.settings.max_ai_messages_per_lead = settings.max_ai_messages_per_lead

            # Update response generator with loaded settings
            self.response_generator.personality = settings.personality_tone
            self.response_generator.agent_name = settings.agent_name
            self.response_generator.brokerage_name = settings.brokerage_name

        return settings

    async def process_message(
        self,
        message: str,
        lead_profile: LeadProfile,
        conversation_context: ConversationContext = None,
        conversation_history: List[Dict[str, Any]] = None,
        channel: str = "sms",
        fub_person_id: int = None,
        user_id: str = None,
        organization_id: str = None,
    ) -> AgentResponse:
        """
        Process an incoming message and generate a response.

        This is the main entry point for the AI agent. It:
        1. Loads settings from database
        2. Checks compliance (opt-out, time windows, rate limits)
        3. Detects intent and sentiment
        4. Updates conversation state
        5. Handles objections if detected
        6. Generates appropriate response
        7. Updates lead score
        8. Extracts qualification information
        9. Determines if handoff is needed

        Args:
            message: The incoming message from the lead
            lead_profile: Rich lead profile for context
            conversation_context: Current conversation state
            conversation_history: Previous messages in conversation
            channel: Communication channel (sms, email)
            fub_person_id: Follow Up Boss person ID
            user_id: User ID for settings lookup
            organization_id: Organization ID for settings fallback

        Returns:
            AgentResponse with response text and all metadata
        """
        start_time = datetime.utcnow()
        lead_id = str(lead_profile.fub_person_id or fub_person_id or "unknown")

        # Load settings from database (cached)
        await self._load_db_settings(user_id, organization_id)

        # Check if AI is enabled
        if self._db_settings and not self._db_settings.is_enabled:
            logger.info(f"AI agent disabled for user {user_id} - skipping message processing")
            return AgentResponse(
                response_text="",
                result=ProcessingResult.SKIPPED,
                error_message="AI agent is disabled",
            )

        try:
            # Initialize response
            response = AgentResponse(
                response_text="",
                channel=channel,
            )

            # Step 1: Compliance Check
            if channel == "sms":
                compliance_result = await self.compliance_checker.check_send_allowed(
                    phone_number=lead_profile.phone,
                    fub_person_id=fub_person_id,
                )

                if compliance_result.status != ComplianceStatus.ALLOWED:
                    response.result = ProcessingResult.COMPLIANCE_BLOCKED
                    response.compliance_status = compliance_result.status
                    response.error_message = compliance_result.reason
                    return response

            # Step 2: Detect Intent
            intent_context = {
                "current_state": conversation_context.state if conversation_context else "initial",
                "last_ai_message": conversation_history[-1].get("content", "") if conversation_history else "",
            }
            detected = await self.intent_detector.detect_async(
                message=message,
                conversation_context=intent_context,
                use_llm_fallback=True,
            )

            response.detected_intent = detected.primary_intent.value
            response.detected_sentiment = detected.sentiment

            # Step 3: Check for immediate handoff triggers
            if self._should_immediate_handoff(detected, lead_profile):
                return await self._handle_handoff(
                    response=response,
                    lead_profile=lead_profile,
                    reason=self._get_handoff_reason(detected),
                    start_time=start_time,
                )

            # Step 4: Check for opt-out
            if detected.primary_intent == Intent.OPT_OUT:
                return await self._handle_opt_out(
                    response=response,
                    lead_profile=lead_profile,
                    fub_person_id=fub_person_id,
                )

            # Step 4.5: Check for channel preference changes (smart routing)
            channel_pref_result = self._handle_channel_preference(detected, response)
            if channel_pref_result:
                response = channel_pref_result
                # Store channel preference in database if it changed
                if response.channel_preference_changed and fub_person_id:
                    await self._save_channel_preference(
                        fub_person_id=fub_person_id,
                        preferred_channel=response.preferred_channel,
                        channel_reduction=response.channel_reduction_requested,
                    )

            # Step 5: Get/create conversation manager
            conv_manager = self._get_conversation_manager(lead_id, conversation_context)
            qual_manager = self._get_qualification_manager(lead_id)

            # Update qualification data from detected entities
            if detected.extracted_entities:
                qual_manager.update_from_intent(
                    intent_name=detected.primary_intent.value,
                    extracted_entities=[e.__dict__ for e in detected.extracted_entities],
                    raw_message=message,
                )

            # Step 6: Handle objections if detected
            if self._is_objection_intent(detected.primary_intent):
                objection_response = await self._handle_objection(
                    detected=detected,
                    lead_profile=lead_profile,
                    lead_id=lead_id,
                )

                if objection_response:
                    response.response_text = objection_response.response_text
                    response.template_used = "objection_handler"

                    # Update state if objection suggests handoff
                    if objection_response.mark_as_closed:
                        response.should_handoff = True
                        response.handoff_reason = "Multiple objections - lead not interested"

                    return self._finalize_response(
                        response=response,
                        detected=detected,
                        qual_manager=qual_manager,
                        conv_manager=conv_manager,
                        lead_profile=lead_profile,
                        start_time=start_time,
                    )

            # Step 7: Generate AI response
            previous_state = conv_manager.current_state.value
            ai_response = await self.response_generator.generate_response(
                incoming_message=message,
                conversation_history=conversation_history or [],
                lead_context={
                    "first_name": lead_profile.first_name,
                    "score": lead_profile.score,
                    "source": lead_profile.source,
                },
                current_state=conv_manager.current_state.value,
                qualification_data=qual_manager.data.to_dict(),
                lead_profile=lead_profile,
            )

            # Step 8: Use response or fallback
            if ai_response.quality in [ResponseQuality.EXCELLENT, ResponseQuality.GOOD, ResponseQuality.ACCEPTABLE]:
                response.response_text = ai_response.response_text
                response.model_used = ai_response.model_used
                response.tokens_used = ai_response.tokens_used

                # Update state from AI response
                if ai_response.next_state:
                    new_state = ConversationState(ai_response.next_state)
                    conv_manager.transition_to(new_state)

                # Update extracted info
                if ai_response.extracted_info:
                    qual_manager.update_from_intent(
                        intent_name=ai_response.detected_intent or "",
                        extracted_entities=[
                            {"type": k, "value": v}
                            for k, v in ai_response.extracted_info.items()
                            if v is not None
                        ],
                        raw_message=message,
                    )
                    response.extracted_info = ai_response.extracted_info

                # Check for handoff
                if ai_response.should_handoff:
                    response.should_handoff = True
                    response.handoff_reason = ai_response.handoff_reason

                response.lead_score_delta = ai_response.lead_score_delta

            else:
                # Use template fallback
                response.response_text = self._get_fallback_response(
                    conv_manager.current_state,
                    lead_profile,
                )
                response.used_fallback = True

            # Step 9: Update conversation state
            response.previous_state = previous_state
            response.conversation_state = conv_manager.current_state.value
            response.state_changed = previous_state != response.conversation_state

            # Step 10: Finalize and return
            return await self._finalize_response(
                response=response,
                detected=detected,
                qual_manager=qual_manager,
                conv_manager=conv_manager,
                lead_profile=lead_profile,
                start_time=start_time,
                fub_person_id=fub_person_id,
            )

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return AgentResponse(
                response_text=self.template_engine.get_message(
                    "handoff_to_agent",
                    {"first_name": lead_profile.first_name, "human_agent_name": "a team member"},
                ) or "Let me connect you with someone who can help better!",
                result=ProcessingResult.ERROR,
                error_message=str(e),
                should_handoff=True,
                handoff_reason=f"Error: {str(e)}",
            )

    async def process_new_lead(
        self,
        lead_profile: LeadProfile,
        channel: str = "sms",
        fub_person_id: int = None,
    ) -> AgentResponse:
        """
        Generate initial welcome message for a new lead.

        This is called when a new lead is created (not in response to a message).

        Args:
            lead_profile: Lead profile data
            channel: Communication channel
            fub_person_id: FUB person ID

        Returns:
            AgentResponse with welcome message
        """
        lead_id = str(lead_profile.fub_person_id or fub_person_id or "unknown")

        # Check compliance first
        if channel == "sms":
            compliance_result = await self.compliance_checker.check_send_allowed(
                phone_number=lead_profile.phone,
                fub_person_id=fub_person_id,
            )

            if compliance_result.status != ComplianceStatus.ALLOWED:
                return AgentResponse(
                    response_text="",
                    result=ProcessingResult.COMPLIANCE_BLOCKED,
                    compliance_status=compliance_result.status,
                    error_message=compliance_result.reason,
                )

        # Get welcome message
        welcome_text = self.template_engine.get_welcome_message(
            lead_profile={
                "first_name": lead_profile.first_name,
                "id": lead_id,
                "interested_property_address": lead_profile.interested_property_address,
                "interested_area": (
                    lead_profile.preferred_neighborhoods[0]
                    if lead_profile.preferred_neighborhoods
                    else lead_profile.preferred_cities[0] if lead_profile.preferred_cities else None
                ),
                "source_area": lead_profile.source_url[:50] if lead_profile.source_url else None,
                "referrer_name": lead_profile.custom_fields.get("referrer_name"),
            },
            agent_name=self.settings.agent_name,
        )

        # Initialize conversation state
        conv_manager = self._get_conversation_manager(lead_id)
        conv_manager.transition_to(ConversationState.INITIAL)

        return AgentResponse(
            response_text=welcome_text,
            channel=channel,
            result=ProcessingResult.SUCCESS,
            conversation_state=ConversationState.INITIAL.value,
            lead_score=lead_profile.score,
            template_used="welcome",
        )

    def _get_conversation_manager(
        self,
        lead_id: str,
        context: ConversationContext = None,
    ) -> ConversationManager:
        """Get or create conversation manager for a lead."""
        if lead_id not in self._conversation_managers:
            self._conversation_managers[lead_id] = ConversationManager(
                context=context,
            )
        return self._conversation_managers[lead_id]

    def _get_qualification_manager(
        self,
        lead_id: str,
    ) -> QualificationFlowManager:
        """Get or create qualification flow manager for a lead."""
        if lead_id not in self._qualification_managers:
            self._qualification_managers[lead_id] = QualificationFlowManager()
        return self._qualification_managers[lead_id]

    def _should_immediate_handoff(
        self,
        detected: DetectedIntent,
        lead_profile: LeadProfile,
    ) -> bool:
        """Determine if immediate handoff is needed."""
        # Explicit request for human
        if detected.primary_intent == Intent.ESCALATION_REQUEST:
            return True

        # Frustrated or using profanity
        if detected.primary_intent in [Intent.FRUSTRATION, Intent.PROFANITY]:
            return True

        # Multiple objections
        if lead_profile.objection_count >= 3:
            return True

        return False

    def _get_handoff_reason(self, detected: DetectedIntent) -> str:
        """Get reason for handoff based on detected intent."""
        reasons = {
            Intent.ESCALATION_REQUEST: "Lead requested to speak with a human",
            Intent.FRUSTRATION: "Lead appears frustrated",
            Intent.PROFANITY: "Inappropriate language detected",
        }
        return reasons.get(detected.primary_intent, "Handoff triggered")

    def _is_objection_intent(self, intent: Intent) -> bool:
        """Check if intent is an objection."""
        objection_intents = {
            Intent.OBJECTION_OTHER_AGENT,
            Intent.OBJECTION_NOT_READY,
            Intent.OBJECTION_JUST_BROWSING,
            Intent.OBJECTION_PRICE,
            Intent.OBJECTION_TIMING,
            Intent.NEGATIVE_INTEREST,
        }
        return intent in objection_intents

    async def _handle_objection(
        self,
        detected: DetectedIntent,
        lead_profile: LeadProfile,
        lead_id: str,
    ) -> Optional[ObjectionResponse]:
        """Handle detected objection."""
        objection_type = self.objection_handler.classify_objection(detected.primary_intent.value)

        if objection_type == ObjectionType.UNKNOWN:
            return None

        context = ObjectionContext(
            objection_type=objection_type,
            objection_count=lead_profile.objection_count + 1,
            lead_score=lead_profile.score,
            timeline=lead_profile.timeline,
            sentiment=detected.sentiment,
        )

        return self.objection_handler.handle_objection(
            objection_type=objection_type,
            context=context,
            lead_id=lead_id,
        )

    async def _handle_handoff(
        self,
        response: AgentResponse,
        lead_profile: LeadProfile,
        reason: str,
        start_time: datetime,
    ) -> AgentResponse:
        """Handle handoff to human agent."""
        response.result = ProcessingResult.HANDOFF_TRIGGERED
        response.should_handoff = True
        response.handoff_reason = reason

        # Get handoff message
        response.response_text = self.template_engine.get_handoff_message(
            first_name=lead_profile.first_name,
            human_agent_name=lead_profile.assigned_agent or "a team member",
            is_complex_question=False,
        )

        response.response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        response.template_used = "handoff"

        return response

    async def _handle_opt_out(
        self,
        response: AgentResponse,
        lead_profile: LeadProfile,
        fub_person_id: int,
    ) -> AgentResponse:
        """Handle opt-out request."""
        # Record opt-out
        await self.compliance_checker.record_opt_out(
            phone_number=lead_profile.phone,
            fub_person_id=fub_person_id,
        )

        response.response_text = "You've been unsubscribed. Thanks, and best of luck with your search!"
        response.result = ProcessingResult.SUCCESS
        response.detected_intent = Intent.OPT_OUT.value
        response.template_used = "opt_out"

        return response

    def _handle_channel_preference(
        self,
        detected: DetectedIntent,
        response: AgentResponse,
    ) -> Optional[AgentResponse]:
        """
        Handle channel preference intents (smart routing).

        This doesn't stop other channels - it sets a PRIMARY preference.
        Other channels remain available for fallback, re-engagement, etc.

        Args:
            detected: Detected intent with entities
            response: Current response being built

        Returns:
            Updated response if channel preference detected, None otherwise
        """
        # Channel preference intents
        channel_pref_intents = {
            Intent.CHANNEL_PREFER_SMS: "sms",
            Intent.CHANNEL_PREFER_EMAIL: "email",
            Intent.CHANNEL_PREFER_CALL: "call",
        }

        # Channel reduction intents (reduce frequency, don't disable)
        channel_reduce_intents = {
            Intent.CHANNEL_REDUCE_SMS: "sms",
            Intent.CHANNEL_REDUCE_EMAIL: "email",
        }

        # Check for preference change
        if detected.primary_intent in channel_pref_intents:
            preferred = channel_pref_intents[detected.primary_intent]
            response.channel_preference_changed = True
            response.preferred_channel = preferred

            # Generate acknowledgment based on preference
            ack_messages = {
                "sms": "Got it! I'll make sure to text you. 📱",
                "email": "Sure thing! I'll send you an email. 📧",
                "call": "Sounds good! I'll give you a call. 📞",
            }
            # Note: This acknowledgment can be prepended to the main response
            # or sent as a separate note. We store it in extracted_info.
            response.extracted_info["channel_preference_ack"] = ack_messages.get(preferred, "")

            logger.info(f"Channel preference changed to: {preferred}")
            return response

        # Check for channel reduction request
        if detected.primary_intent in channel_reduce_intents:
            channel = channel_reduce_intents[detected.primary_intent]
            response.channel_reduction_requested = channel
            response.channel_preference_changed = True

            # Acknowledge reduction
            ack_messages = {
                "sms": "No problem, I'll text you less often. Just didn't want to miss you! 😊",
                "email": "Got it, I'll ease up on the emails. Just keeping you in the loop!",
            }
            response.extracted_info["channel_reduction_ack"] = ack_messages.get(channel, "")

            logger.info(f"Channel reduction requested for: {channel}")
            return response

        # Also check extracted entities for channel preference
        channel_entity = detected.get_entity("channel_preference")
        if channel_entity:
            response.channel_preference_changed = True
            response.preferred_channel = channel_entity.value
            logger.info(f"Channel preference extracted from entity: {channel_entity.value}")
            return response

        channel_reduce_entity = detected.get_entity("channel_reduction")
        if channel_reduce_entity:
            response.channel_preference_changed = True
            response.channel_reduction_requested = channel_reduce_entity.value
            logger.info(f"Channel reduction extracted from entity: {channel_reduce_entity.value}")
            return response

        return None

    async def _save_channel_preference(
        self,
        fub_person_id: int,
        preferred_channel: Optional[str] = None,
        channel_reduction: Optional[str] = None,
    ):
        """
        Save channel preference to database.

        Args:
            fub_person_id: FUB person ID
            preferred_channel: Preferred channel (sms, email, call)
            channel_reduction: Channel to reduce frequency for
        """
        if not self.supabase:
            logger.warning("No Supabase client - cannot save channel preference")
            return

        try:
            # Update ai_conversations table
            update_data = {}
            if preferred_channel:
                update_data["preferred_channel"] = preferred_channel
            if channel_reduction:
                # Store as metadata or separate field
                update_data["channel_reduction"] = channel_reduction

            if update_data:
                self.supabase.table("ai_conversations").update(update_data).eq(
                    "fub_person_id", fub_person_id
                ).execute()
                logger.info(f"Saved channel preference for person {fub_person_id}: {update_data}")

        except Exception as e:
            logger.error(f"Error saving channel preference: {e}", exc_info=True)

    def _get_fallback_response(
        self,
        state: ConversationState,
        lead_profile: LeadProfile,
    ) -> str:
        """Get template-based fallback response."""
        category_map = {
            ConversationState.INITIAL: TemplateCategory.WELCOME,
            ConversationState.QUALIFYING: TemplateCategory.QUALIFICATION,
            ConversationState.OBJECTION_HANDLING: TemplateCategory.OBJECTION,
            ConversationState.SCHEDULING: TemplateCategory.SCHEDULING,
            ConversationState.NURTURE: TemplateCategory.NURTURE,
            ConversationState.HANDED_OFF: TemplateCategory.HANDOFF,
        }

        category = category_map.get(state, TemplateCategory.FOLLOW_UP)

        return self.template_engine.get_fallback_message(
            category=category,
            variables={
                "first_name": lead_profile.first_name,
                "agent_name": self.settings.agent_name,
                "area": (
                    lead_profile.preferred_neighborhoods[0]
                    if lead_profile.preferred_neighborhoods
                    else ""
                ),
            },
        )

    async def _finalize_response(
        self,
        response: AgentResponse,
        detected: DetectedIntent,
        qual_manager: QualificationFlowManager,
        conv_manager: ConversationManager,
        lead_profile: LeadProfile,
        start_time: datetime,
        fub_person_id: int = None,
    ) -> AgentResponse:
        """Finalize response with all metadata and sync to CRM."""
        # Calculate response time
        response.response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        # Get qualification progress
        progress = qual_manager.get_progress()
        response.qualification_progress = progress.overall_percentage

        # Update lead score
        current_score = self.lead_scorer.calculate_score(
            qual_manager.data.to_dict()
        )
        response.lead_score = current_score.total_score

        # Check if should suggest scheduling
        if (current_score.total_score >= self.settings.auto_schedule_score_threshold and
            conv_manager.current_state == ConversationState.QUALIFYING and
            progress.is_minimally_qualified):
            response.appointment_requested = True
            conv_manager.transition_to(ConversationState.SCHEDULING)
            response.conversation_state = ConversationState.SCHEDULING.value
            response.state_changed = True

        # Check if should auto-handoff due to high score
        if current_score.total_score >= self.settings.auto_handoff_score_threshold:
            response.should_handoff = True
            response.handoff_reason = "Lead is highly qualified and ready for human agent"

        # Sync qualification data to FUB CRM (async, non-blocking)
        if fub_person_id and response.extracted_info:
            await self._sync_to_crm(
                fub_person_id=fub_person_id,
                qualification_data=qual_manager.data.to_dict(),
                lead_score=response.lead_score,
                conversation_state=response.conversation_state,
            )

        return response

    async def _sync_to_crm(
        self,
        fub_person_id: int,
        qualification_data: Dict[str, Any],
        lead_score: int,
        conversation_state: str,
    ):
        """
        Sync qualification data to FUB CRM custom fields.

        This runs asynchronously to not block the response.
        """
        try:
            from app.ai_agent.crm_sync_service import get_crm_sync_service
            from app.fub.fub_client import FUBClient

            # Get CRM sync service
            crm_service = get_crm_sync_service(
                supabase_client=self.supabase,
                fub_client=FUBClient(),
            )

            # Sync data to FUB
            result = await crm_service.sync_to_fub(
                fub_person_id=fub_person_id,
                qualification_data=qualification_data,
                lead_score=lead_score,
                conversation_state=conversation_state,
                organization_id=self.organization_id,
            )

            if result.get("success"):
                logger.info(f"Synced {result.get('synced_fields', 0)} fields to FUB for person {fub_person_id}")
            else:
                logger.warning(f"CRM sync failed: {result.get('error')}")

        except Exception as e:
            # Log but don't fail the response
            logger.error(f"Error syncing to CRM: {e}", exc_info=True)

    async def get_conversation_state(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Get current conversation state for a lead."""
        conv_manager = self._conversation_managers.get(lead_id)
        qual_manager = self._qualification_managers.get(lead_id)

        if not conv_manager:
            return None

        progress = qual_manager.get_progress() if qual_manager else None

        return {
            "state": conv_manager.current_state.value,
            "qualification_data": qual_manager.data.to_dict() if qual_manager else {},
            "qualification_progress": progress.overall_percentage if progress else 0,
            "is_qualified": progress.is_minimally_qualified if progress else False,
        }

    def reset_conversation(self, lead_id: str):
        """Reset conversation state for a lead."""
        self._conversation_managers.pop(lead_id, None)
        self._qualification_managers.pop(lead_id, None)


# Factory function for creating agent instances
def create_agent_service(
    settings: AgentSettings = None,
    anthropic_api_key: str = None,
    supabase_client=None,
    user_id: str = None,
    organization_id: str = None,
) -> AIAgentService:
    """
    Create a configured AI Agent Service instance.

    Args:
        settings: Agent configuration (overrides DB settings)
        anthropic_api_key: API key for Claude
        supabase_client: Database client
        user_id: User ID for loading settings from DB
        organization_id: Organization ID for settings fallback

    Returns:
        Configured AIAgentService instance
    """
    return AIAgentService(
        settings=settings,
        anthropic_api_key=anthropic_api_key,
        supabase_client=supabase_client,
        user_id=user_id,
        organization_id=organization_id,
    )
