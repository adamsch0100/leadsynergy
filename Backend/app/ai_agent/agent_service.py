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
    ToolResponse,
    detect_handoff_triggers,
    get_handoff_acknowledgment,
)
from app.ai_agent.tool_executor import ToolExecutor, ExecutionResult
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
    response_delay_seconds: int = 10  # Speed-to-lead: faster response = higher conversion
    max_sms_length: int = 1000  # Max SMS chars (configurable from frontend)
    max_email_length: int = 5000  # Max email chars (configurable from frontend)

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

    # Stage exclusion
    excluded_stages: list = field(default_factory=lambda: [
        "Sphere", "Past Client", "Active Client", "Trash", "Dead"
    ])


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

        # Tool executor for action execution
        self.tool_executor = ToolExecutor(api_key=None)  # FUB API key loaded per-org

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
            self.settings.excluded_stages = settings.excluded_stages or []

            # Update response generator with loaded settings
            self.response_generator.personality = settings.personality_tone
            self.response_generator.agent_name = settings.agent_name
            self.response_generator.brokerage_name = settings.brokerage_name
            self.response_generator.use_assigned_agent_name = settings.use_assigned_agent_name
            self.response_generator.max_sms_length = settings.max_sms_length
            self.response_generator.max_email_length = settings.max_email_length
            self.tool_executor.max_sms_length = settings.max_sms_length

            # Update LLM provider/model settings from database
            if settings.llm_provider:
                import os
                self.response_generator.use_openrouter = settings.llm_provider.lower() == "openrouter"
                if self.response_generator.use_openrouter:
                    self.response_generator.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
                    self.response_generator.api_key = self.response_generator.openrouter_api_key
                    self.response_generator.primary_model = settings.llm_model or self.response_generator.DEFAULT_OPENROUTER_MODEL
                    self.response_generator.fallback_model = settings.llm_model_fallback or self.response_generator.DEFAULT_OPENROUTER_FALLBACK
                    logger.info(f"Updated to use OpenRouter with model: {self.response_generator.primary_model}")
                else:
                    self.response_generator.api_key = os.getenv("ANTHROPIC_API_KEY")
                    self.response_generator.primary_model = settings.llm_model or self.response_generator.DEFAULT_ANTHROPIC_MODEL
                    self.response_generator.fallback_model = settings.llm_model_fallback or self.response_generator.DEFAULT_ANTHROPIC_FALLBACK
                    logger.info(f"Updated to use Anthropic with model: {self.response_generator.primary_model}")

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
            # Guard: Skip AI if conversation already handed off to human
            if conversation_context and conversation_context.state == ConversationState.HANDED_OFF:
                logger.info(f"Conversation already handed off for lead {lead_id} - skipping AI response")
                return AgentResponse(
                    response_text="",
                    result=ProcessingResult.SKIPPED,
                    error_message="Conversation already handed off to human agent",
                )

            # Guard: Check message count limit for handoff
            if conversation_context:
                should_hand_off, handoff_reason = conversation_context.should_handoff()
                if should_hand_off:
                    logger.info(f"Message count handoff for lead {lead_id}: {handoff_reason}")
                    return AgentResponse(
                        response_text="",
                        result=ProcessingResult.HANDOFF_TRIGGERED,
                        should_handoff=True,
                        handoff_reason=handoff_reason,
                    )

            # Initialize response
            response = AgentResponse(
                response_text="",
                channel=channel,
            )

            # Step 0: Stage Eligibility Check (smart pattern matching + user-excluded stages)
            # This blocks AI contact for stages like "Closed", "Sold", "Sphere", "Trash"
            # and flags handoff stages like "Under Contract", "Showing", "Negotiating"
            if lead_profile.stage_name:
                is_eligible, stage_status, stage_reason = self.compliance_checker.check_stage_eligibility(
                    lead_profile.stage_name, self.settings.excluded_stages
                )

                if not is_eligible:
                    logger.info(f"Stage eligibility blocked: {stage_reason}")
                    return AgentResponse(
                        response_text="",
                        result=ProcessingResult.COMPLIANCE_BLOCKED,
                        compliance_status=stage_status,
                        error_message=stage_reason,
                    )

                if stage_status == ComplianceStatus.HANDOFF_STAGE:
                    # Stage requires human attention - respond but flag for handoff
                    response.should_handoff = True
                    response.handoff_reason = stage_reason

            # Step 1: Compliance Check
            if channel == "sms" and organization_id:
                compliance_result = await self.compliance_checker.check_sms_compliance(
                    fub_person_id=fub_person_id,
                    organization_id=organization_id,
                    phone_number=lead_profile.phone or "",
                )

                if not compliance_result.can_send:
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

            # Step 2.5: Check for smart handoff triggers (showing requests, call requests, etc.)
            handoff_trigger = detect_handoff_triggers(message)
            if handoff_trigger:
                logger.info(f"Smart handoff trigger detected for {lead_id}: {handoff_trigger}")

                # Create FUB task for the agent
                await self._create_handoff_task(
                    fub_person_id=fub_person_id,
                    trigger_type=handoff_trigger,
                    lead_message=message,
                    lead_profile=lead_profile,
                )

                # Schedule fallback monitoring (3h + 24h checks)
                try:
                    from app.ai_agent.handoff_monitor import schedule_handoff_monitoring
                    await schedule_handoff_monitoring(
                        fub_person_id=fub_person_id,
                        conversation_id=conversation_context.conversation_id if conversation_context else str(fub_person_id),
                        handoff_reason=f"Smart trigger: {handoff_trigger}",
                        organization_id=getattr(self.settings, 'organization_id', 'default'),
                    )
                    logger.info(f"Scheduled handoff monitoring for person {fub_person_id}")

                    # Send immediate notifications to the agent (SMS + Email)
                    from app.ai_agent.agent_notifier import notify_agent_of_handoff
                    notify_result = await notify_agent_of_handoff(
                        fub_person_id=fub_person_id,
                        lead_name=f"{lead_profile.first_name} {lead_profile.last_name or ''}".strip(),
                        lead_phone=lead_profile.phone or "Unknown",
                        lead_email=lead_profile.email or "Unknown",
                        handoff_reason=f"Smart trigger: {handoff_trigger}",
                        last_message=message,
                        assigned_agent_email=getattr(lead_profile, 'assigned_agent_email', None),
                        settings=self.settings,
                    )
                    if notify_result.get('success'):
                        logger.info(f"Agent notifications sent for handoff: {notify_result['notifications_sent']}")
                    else:
                        logger.warning(f"Agent notification failed: {notify_result.get('errors')}")

                except Exception as e:
                    logger.error(f"Failed to schedule handoff monitoring: {e}")

                # Get world-class acknowledgment message
                # Use human agent name for handoff, pass AI name to avoid confusion
                human_agent_name = lead_profile.assigned_agent or "your agent"
                ai_agent_name = self.settings.agent_name
                response.response_text = get_handoff_acknowledgment(
                    trigger_type=handoff_trigger,
                    agent_name=human_agent_name,
                    ai_agent_name=ai_agent_name,
                    lead_message=message,
                    lead_first_name=lead_profile.first_name
                )
                response.should_handoff = True
                response.handoff_reason = f"Lead trigger: {handoff_trigger}"
                response.result = ProcessingResult.HANDOFF_TRIGGERED
                response.template_used = f"handoff_{handoff_trigger}"
                response.response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

                # Update conversation state to handed_off
                if conversation_context:
                    conversation_context.state = ConversationState.HANDED_OFF

                # Auto-disable AI + cancel pending follow-ups (the follow-up agent's job is done)
                try:
                    from app.ai_agent.lead_ai_settings_service import LeadAISettingsServiceSingleton
                    lead_ai_svc = LeadAISettingsServiceSingleton.get_instance(self.supabase)
                    org_id = getattr(self.settings, 'organization_id', None) or (
                        conversation_context.organization_id if conversation_context else 'default'
                    )
                    await lead_ai_svc.disable_ai_for_lead(
                        fub_person_id=str(fub_person_id),
                        organization_id=org_id,
                    )
                    # Cancel pending follow-ups
                    self.supabase.table('ai_scheduled_followups').update({
                        'status': 'cancelled',
                    }).eq('fub_person_id', fub_person_id).eq('status', 'pending').execute()
                    logger.info(f"Auto-disabled AI and cancelled follow-ups for lead {fub_person_id} (handoff)")
                except Exception as disable_err:
                    logger.warning(f"Failed to auto-disable AI on handoff for {fub_person_id}: {disable_err}")

                return response

            # Step 3: Check for immediate handoff triggers (frustration, profanity, explicit requests)
            if self._should_immediate_handoff(detected, lead_profile):
                return await self._handle_handoff(
                    response=response,
                    lead_profile=lead_profile,
                    reason=self._get_handoff_reason(detected),
                    start_time=start_time,
                    fub_person_id=fub_person_id,  # Pass person ID to create task
                )

            # Step 4: Check for opt-out
            if detected.primary_intent == Intent.OPT_OUT:
                return await self._handle_opt_out(
                    response=response,
                    lead_profile=lead_profile,
                    fub_person_id=fub_person_id,
                )

            # Step 4.2: Check for deferred follow-up ("call me next month")
            if detected.primary_intent == Intent.DEFERRED_FOLLOWUP:
                return await self._handle_deferred_followup(
                    response=response,
                    lead_profile=lead_profile,
                    fub_person_id=fub_person_id,
                    detected=detected,
                    conversation_context=conversation_context,
                    organization_id=organization_id,
                    start_time=start_time,
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

            # Step 5: Get qualification manager
            qual_manager = self._get_qualification_manager(lead_id)

            # Use passed-in conversation_context for state tracking
            # If no context passed, create a default one with all required fields
            if not conversation_context:
                import uuid
                conversation_context = ConversationContext(
                    conversation_id=str(uuid.uuid4()),
                    fub_person_id=fub_person_id or 0,
                    user_id=user_id or "",
                    organization_id=organization_id or "",
                )

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
                        conversation_context=conversation_context,
                        lead_profile=lead_profile,
                        start_time=start_time,
                    )

            # Step 7: Generate AI response
            previous_state = conversation_context.state.value
            qual_dict = qual_manager.data.to_dict()
            ai_response = await self.response_generator.generate_response(
                incoming_message=message,
                conversation_history=conversation_history or [],
                lead_context={
                    "first_name": lead_profile.first_name,
                    "score": lead_profile.score,
                    "source": lead_profile.source,
                    # Qualification progress
                    "budget": qual_dict.get("budget"),
                    "timeline": qual_dict.get("timeline"),
                    "pre_approved": qual_dict.get("pre_approved"),
                    "location_preference": qual_dict.get("location"),
                    "property_type": qual_dict.get("property_type"),
                    "motivation": qual_dict.get("motivation"),
                    # Lead profile
                    "stage_name": lead_profile.stage_name,
                    "assigned_agent": lead_profile.assigned_agent,
                    "tags": getattr(lead_profile, 'tags', []),
                    # Conversation metadata
                    "messages_exchanged": len(conversation_context.conversation_history),
                    "current_state": conversation_context.state.value,
                    "re_engagement_count": getattr(conversation_context, 're_engagement_count', 0),
                },
                current_state=conversation_context.state.value,
                qualification_data=qual_dict,
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
                    conversation_context.state = new_state

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
                    conversation_context.state,
                    lead_profile,
                )
                response.used_fallback = True

            # Step 9: Update conversation state
            response.previous_state = previous_state
            response.conversation_state = conversation_context.state.value
            response.state_changed = previous_state != response.conversation_state

            # Step 10: Finalize and return
            return await self._finalize_response(
                response=response,
                detected=detected,
                qual_manager=qual_manager,
                conversation_context=conversation_context,
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
        organization_id: str = None,
    ) -> AgentResponse:
        """
        Generate initial welcome message for a new lead.

        This is called when a new lead is created (not in response to a message).

        Args:
            lead_profile: Lead profile data
            channel: Communication channel
            fub_person_id: FUB person ID
            organization_id: Organization ID for compliance checks

        Returns:
            AgentResponse with welcome message
        """
        lead_id = str(lead_profile.fub_person_id or fub_person_id or "unknown")

        # Check compliance first
        if channel == "sms" and organization_id:
            compliance_result = await self.compliance_checker.check_sms_compliance(
                fub_person_id=fub_person_id,
                organization_id=organization_id,
                phone_number=lead_profile.phone or "",
            )

            if not compliance_result.can_send:
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

        # Note: Conversation context will be created when lead first responds
        # The initial state is returned in the response below

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
                supabase_client=self.supabase,
            )
        return self._conversation_managers[lead_id]

    def _get_qualification_manager(
        self,
        lead_id: str,
    ) -> QualificationFlowManager:
        """Get or create qualification flow manager for a lead."""
        if lead_id not in self._qualification_managers:
            qm = QualificationFlowManager()
            # Wire max_qualification_questions from settings (default: 8)
            if self.settings and hasattr(self.settings, 'max_qualification_questions'):
                qm.max_qualification_questions = getattr(self.settings, 'max_qualification_questions', 8)
            self._qualification_managers[lead_id] = qm
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
        fub_person_id: int = None,
    ) -> AgentResponse:
        """Handle handoff to human agent."""
        response.result = ProcessingResult.HANDOFF_TRIGGERED
        response.should_handoff = True
        response.handoff_reason = reason

        # Create FUB task to notify agent (CRITICAL - was missing!)
        if fub_person_id:
            try:
                await self._create_handoff_task(
                    fub_person_id=fub_person_id,
                    trigger_type="immediate_handoff",
                    lead_message=None,  # No specific message for frustration/profanity handoffs
                    lead_profile=lead_profile,
                )
                logger.info(f"Created handoff task for person {fub_person_id}: {reason}")

                # Schedule fallback monitoring (3h + 24h checks)
                from app.ai_agent.handoff_monitor import schedule_handoff_monitoring
                await schedule_handoff_monitoring(
                    fub_person_id=fub_person_id,
                    conversation_id=response.conversation_id or str(fub_person_id),
                    handoff_reason=reason,
                    organization_id=getattr(self.settings, 'organization_id', 'default'),
                )
                logger.info(f"Scheduled handoff monitoring for person {fub_person_id}")

                # Send immediate notifications to the agent (SMS + Email)
                from app.ai_agent.agent_notifier import notify_agent_of_handoff
                notify_result = await notify_agent_of_handoff(
                    fub_person_id=fub_person_id,
                    lead_name=f"{lead_profile.first_name} {lead_profile.last_name or ''}".strip(),
                    lead_phone=lead_profile.phone or "Unknown",
                    lead_email=lead_profile.email or "Unknown",
                    handoff_reason=reason,
                    last_message=getattr(response, 'original_message', 'No message'),
                    assigned_agent_email=getattr(lead_profile, 'assigned_agent_email', None),
                    settings=self.settings,
                )
                if notify_result.get('success'):
                    logger.info(f"Agent notifications sent for handoff: {notify_result['notifications_sent']}")
                else:
                    logger.warning(f"Agent notification failed: {notify_result.get('errors')}")

            except Exception as e:
                logger.error(f"Failed to create handoff task or schedule monitoring: {e}")
                # Don't fail the handoff just because task creation failed

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
        """
        Handle opt-out request - CRITICAL compliance function.

        When a lead says STOP/unsubscribe/remove me:
        1. Record opt-out in compliance database
        2. Cancel ALL pending follow-ups immediately
        3. Update FUB stage to Dead
        4. Send confirmation message
        5. Never contact them again
        """
        logger.info(f"[OPT-OUT] Processing opt-out for person {fub_person_id}")

        # 1. Record opt-out in compliance database
        await self.compliance_checker.record_opt_out(
            phone_number=lead_profile.phone,
            fub_person_id=fub_person_id,
            reason="Lead requested opt-out (STOP keyword)",
        )

        # 2. Cancel ALL pending follow-ups immediately
        try:
            from app.scheduler.ai_tasks import cancel_lead_sequences
            cancel_lead_sequences.delay(
                fub_person_id=fub_person_id,
                reason="opt_out_requested"
            )
            logger.info(f"[OPT-OUT] Cancelled all pending follow-ups for person {fub_person_id}")
        except Exception as e:
            logger.error(f"[OPT-OUT] Error cancelling sequences: {e}")

        # 3. Update FUB stage to Dead and add opt-out tag
        try:
            from app.database.fub_api_client import FUBApiClient
            fub = FUBApiClient()

            # Update stage to Dead
            fub.update_person(fub_person_id, {"stage": "Dead"})

            # Add opt-out tag for tracking
            fub.add_tag(fub_person_id, "ai_opted_out")

            # Add note explaining the opt-out
            fub.add_note(
                person_id=fub_person_id,
                note_content="<b>Lead Opted Out</b><br><br>The lead requested to stop receiving messages. All automated follow-ups have been cancelled. Do not contact unless they reach out first.",
            )

            logger.info(f"[OPT-OUT] Updated FUB stage to Dead for person {fub_person_id}")
        except Exception as e:
            logger.error(f"[OPT-OUT] Error updating FUB: {e}")

        # 4. Update conversation state
        if self.supabase:
            try:
                self.supabase.table("ai_conversations").update({
                    "state": "opted_out",
                    "opted_out_at": datetime.utcnow().isoformat(),
                }).eq("fub_person_id", fub_person_id).execute()
            except Exception as e:
                logger.error(f"[OPT-OUT] Error updating conversation state: {e}")

        # 5. Send confirmation message
        response.response_text = "You've been unsubscribed. Thanks, and best of luck with your search!"
        response.result = ProcessingResult.SUCCESS
        response.detected_intent = Intent.OPT_OUT.value
        response.template_used = "opt_out"

        logger.info(f"[OPT-OUT] Opt-out complete for person {fub_person_id}")
        return response

    async def _handle_deferred_followup(
        self,
        response: AgentResponse,
        lead_profile: LeadProfile,
        fub_person_id: int,
        detected,
        conversation_context=None,
        organization_id: str = None,
        start_time=None,
    ) -> AgentResponse:
        """
        Handle deferred follow-up request — lead wants contact at a specific future time.

        When a lead says "call me next month" or "reach out in 2 weeks":
        1. Extract the requested date from the message
        2. Cancel current follow-up sequence
        3. Schedule a single re-engagement at the requested date
        4. Set conversation state to NURTURE
        5. Send a graceful acknowledgment
        """
        logger.info(f"[DEFERRED] Processing deferred follow-up for person {fub_person_id}")

        # 1. Extract the target date from detected entities
        target_date = None
        timeframe_text = ""
        for entity in (detected.entities or []):
            if entity.entity_type == "deferred_date":
                target_date = entity.value  # "YYYY-MM-DD" string
                timeframe_text = entity.raw_text
                break

        if not target_date:
            # Fallback: default to 30 days if no date extracted
            from datetime import timedelta
            target_date = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")
            timeframe_text = "about a month"

        logger.info(f"[DEFERRED] Lead {fub_person_id} requested follow-up at {target_date} ('{timeframe_text}')")

        # 2. Cancel current follow-up sequences
        try:
            from app.scheduler.ai_tasks import cancel_lead_sequences
            cancel_lead_sequences.delay(
                fub_person_id=fub_person_id,
                reason="deferred_followup_requested"
            )
            logger.info(f"[DEFERRED] Cancelled current sequences for person {fub_person_id}")
        except Exception as e:
            logger.error(f"[DEFERRED] Error cancelling sequences: {e}")

        # 3. Schedule a re-engagement at the requested date
        try:
            if self.supabase:
                import uuid
                self.supabase.table("ai_scheduled_followups").insert({
                    "id": str(uuid.uuid4()),
                    "fub_person_id": fub_person_id,
                    "organization_id": organization_id,
                    "scheduled_at": f"{target_date}T10:00:00Z",  # 10 AM on the target date
                    "channel": "sms",
                    "message_type": "deferred_followup",
                    "sequence_step": 1,
                    "sequence_id": f"deferred_{fub_person_id}",
                    "status": "pending",
                }).execute()
                logger.info(f"[DEFERRED] Scheduled re-engagement for {target_date}")
        except Exception as e:
            logger.error(f"[DEFERRED] Error scheduling re-engagement: {e}")

        # 4. Update conversation state to NURTURE
        if conversation_context:
            conversation_context.state = ConversationState.NURTURE

        if self.supabase:
            try:
                self.supabase.table("ai_conversations").update({
                    "state": "nurture",
                    "handoff_reason": f"Deferred follow-up: {timeframe_text} ({target_date})",
                }).eq("fub_person_id", fub_person_id).eq("is_active", True).execute()
            except Exception as e:
                logger.error(f"[DEFERRED] Error updating conversation state: {e}")

        # 5. Add FUB note
        try:
            from app.database.fub_api_client import FUBApiClient
            fub = FUBApiClient()
            fub.add_note(
                person_id=fub_person_id,
                note_content=f"<b>AI: Deferred Follow-Up</b><br><br>Lead requested follow-up '{timeframe_text}'. Re-engagement scheduled for {target_date}. Current sequences cancelled.",
            )
        except Exception as e:
            logger.error(f"[DEFERRED] Error adding FUB note: {e}")

        # 6. Send graceful acknowledgment
        agent_name = self.settings.agent_name or "Sarah"
        response.response_text = f"Absolutely! I'll reach out {timeframe_text}. In the meantime, if anything comes up, don't hesitate to text back. Talk soon!"
        response.result = ProcessingResult.SUCCESS
        response.detected_intent = Intent.DEFERRED_FOLLOWUP.value
        response.template_used = "deferred_followup"
        if start_time:
            response.response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        logger.info(f"[DEFERRED] Deferred follow-up complete for person {fub_person_id}")
        return response

    async def _create_handoff_task(
        self,
        fub_person_id: int,
        trigger_type: str,
        lead_message: str,
        lead_profile: LeadProfile,
    ):
        """
        Create a FUB task for the agent when a handoff is triggered.

        This ensures the human agent is immediately notified and has
        context about what the lead wants.

        Args:
            fub_person_id: FUB person ID
            trigger_type: Type of handoff trigger (schedule_showing, wants_call, etc.)
            lead_message: The lead's message that triggered the handoff
            lead_profile: Lead profile for context
        """
        if not fub_person_id:
            logger.warning("Cannot create handoff task without fub_person_id")
            return

        # Task titles based on trigger type
        task_titles = {
            # Buyer triggers
            "schedule_showing": "Lead wants to schedule showing",
            "price_negotiation": "Lead ready to make offer",
            # Seller triggers
            "ready_to_list": "SELLER ready to list their home",
            "home_valuation": "Seller wants home valuation/CMA",
            "hot_seller": "HOT SELLER - Ready to list",
            # General triggers
            "wants_call": "Lead requested phone call",
            "urgent_timeline": "URGENT: Lead has time-sensitive needs",
            "complex_question": "Lead has question requiring expertise",
            # AI-detected hot leads
            "hot_lead": "HOT LEAD - AI detected high buying intent",
            "high_intent": "High intent lead - ready to act",
        }

        # Task priorities - some are more urgent than others
        task_priorities = {
            # Buyer triggers
            "schedule_showing": "high",
            "price_negotiation": "high",
            # Seller triggers
            "ready_to_list": "high",
            "home_valuation": "high",
            "hot_seller": "high",
            # General triggers
            "wants_call": "high",
            "urgent_timeline": "high",
            "complex_question": "medium",
            # AI-detected hot leads
            "hot_lead": "high",
            "high_intent": "high",
        }

        title = task_titles.get(trigger_type, f"AI Handoff: {trigger_type}")
        priority = task_priorities.get(trigger_type, "medium")

        # Build task description with context
        description = f"""AI Agent detected a handoff trigger and transferred this lead.

TRIGGER: {trigger_type.replace('_', ' ').title()}

LEAD MESSAGE:
"{lead_message}"

LEAD INFO:
- Name: {lead_profile.first_name} {lead_profile.last_name}
- Score: {lead_profile.score}/100 ({lead_profile.score_label})
- Source: {lead_profile.source}
- Timeline: {lead_profile.timeline or 'Unknown'}
- Pre-approved: {'Yes' if lead_profile.is_pre_approved else 'No' if lead_profile.is_pre_approved is not None else 'Unknown'}

ACTION REQUIRED: Respond to this lead promptly!
"""

        try:
            from app.database.fub_api_client import FUBApiClient
            from datetime import timedelta

            fub = FUBApiClient()

            # Create task in FUB
            due_date = datetime.utcnow() + timedelta(hours=2)  # Due in 2 hours

            fub.create_task(
                person_id=fub_person_id,
                description=f"{title}\n\n{description}",
                due_at=due_date.isoformat() + "Z",
            )

            # Also add a note for visibility
            fub.add_note(
                person_id=fub_person_id,
                note_content=f"<b>AI Agent Handoff</b><br><br>Trigger: {trigger_type}<br>Lead said: \"{lead_message[:200]}...\"<br><br>The AI has responded and alerted the team.",
            )

            logger.info(f"Created handoff task for person {fub_person_id}: {trigger_type}")

            # Send immediate notifications to agent (SMS via FUB + Email)
            # SMS is sent to a "notification lead" in FUB (a lead with the agent's phone)
            # Email is sent to the assigned agent's email address
            notification_person_id = None
            if self._db_settings:
                notification_person_id = self._db_settings.notification_fub_person_id

            agent_info = self._get_agent_contact_info(fub, fub_person_id)

            try:
                from app.notifications.agent_notifier import AgentNotifier
                notifier = AgentNotifier(notification_fub_person_id=notification_person_id)

                notifier.notify_agent(
                    agent_email=agent_info.get("email") if agent_info else None,
                    agent_name=agent_info.get("name", "Agent") if agent_info else "Agent",
                    lead_name=f"{lead_profile.first_name} {lead_profile.last_name}",
                    trigger_type=trigger_type.replace("_", " ").title(),
                    lead_message=lead_message,
                    lead_phone=lead_profile.phone,
                    lead_score=lead_profile.score,
                    lead_source=lead_profile.source,
                    fub_person_id=fub_person_id,
                )
            except Exception as notify_error:
                logger.error(f"Failed to notify agent: {notify_error}")
                # Don't raise - FUB task was still created

        except Exception as e:
            logger.error(f"Failed to create handoff task for person {fub_person_id}: {e}")
            # Don't raise - we still want to return the handoff response

    def _get_agent_contact_info(self, fub_client, fub_person_id: int) -> Optional[dict]:
        """
        Get assigned agent's contact info from FUB.

        Args:
            fub_client: FUB API client instance
            fub_person_id: FUB person ID to look up assigned agent

        Returns:
            Dict with agent id, name, email, phone or None if not found
        """
        try:
            # Get person to find assigned agent
            person = fub_client.get_person(str(fub_person_id))
            if not person:
                logger.warning(f"Could not fetch person {fub_person_id} for agent lookup")
                return None

            assigned_to = person.get("assignedTo", {})

            # assignedTo can be a dict with {id, name} or just a user ID
            if isinstance(assigned_to, dict):
                agent_id = assigned_to.get("id")
            else:
                agent_id = assigned_to

            if not agent_id:
                logger.info(f"No assigned agent for person {fub_person_id}")
                return None

            # Get agent details
            agent = fub_client.get_user(str(agent_id))
            if not agent:
                logger.warning(f"Could not fetch agent {agent_id}")
                return None

            return {
                "id": agent_id,
                "name": agent.get("name", "Agent"),
                "email": agent.get("email"),
                "phone": agent.get("phone") or agent.get("cellPhone") or agent.get("mobilePhone"),
            }

        except Exception as e:
            logger.error(f"Error getting agent contact info: {e}")
            return None

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
        conversation_context: ConversationContext,
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
        response.lead_score = current_score.total

        # CRITICAL: Force handoff for appointment scheduling interest regardless of score
        # Appointment scheduling is a HOT LEAD signal - don't let low score block handoff
        is_appointment_scheduling = (
            response.detected_intent in ['time_selection', 'appointment_interest', 'appointment_confirmed'] or
            (response.handoff_reason and 'appointment' in response.handoff_reason.lower()) or
            'appointment_agreed' in (response.handoff_reason or '')
        )

        if is_appointment_scheduling:
            logger.info(f"Appointment scheduling detected - forcing handoff (current score: {current_score.total})")

            # Boost score to reflect appointment interest (major signal)
            if current_score.total < self.settings.auto_handoff_score:
                score_boost = max(20, self.settings.auto_handoff_score - current_score.total + 10)
                logger.info(f"Boosting score by {score_boost} for appointment scheduling")
                response.lead_score_delta = getattr(response, 'lead_score_delta', 0) + score_boost
                response.lead_score = current_score.total + score_boost

            # Force handoff
            response.should_handoff = True
            response.handoff_reason = response.handoff_reason or "Appointment scheduling interest - immediate handoff required"
            response.appointment_requested = True

            if conversation_context:
                conversation_context.state = ConversationState.HANDED_OFF
                response.conversation_state = ConversationState.HANDED_OFF.value
                response.state_changed = True

        # Check if should suggest scheduling -> immediate handoff to human agent
        # When a lead is qualified enough for scheduling, hand off to the human
        # agent rather than having the AI try to book appointments itself.
        elif (current_score.total >= self.settings.auto_schedule_score_threshold and
            conversation_context.state == ConversationState.QUALIFYING and
            progress.is_minimally_qualified):
            response.appointment_requested = True
            conversation_context.state = ConversationState.HANDED_OFF
            response.conversation_state = ConversationState.HANDED_OFF.value
            response.state_changed = True
            response.should_handoff = True
            response.handoff_reason = "Lead is qualified and ready for appointment scheduling"

        # Check if should auto-handoff due to high score
        if current_score.total >= self.settings.auto_handoff_score_threshold:
            response.should_handoff = True
            response.handoff_reason = response.handoff_reason or "Lead is highly qualified and ready for human agent"

        # Sync qualification data to FUB CRM (async, non-blocking)
        if fub_person_id and response.extracted_info:
            await self._sync_to_crm(
                fub_person_id=fub_person_id,
                qualification_data=qual_manager.data.to_dict(),
                lead_score=response.lead_score,
                conversation_state=response.conversation_state,
            )

        # Auto-disable AI + cancel follow-ups when handoff fires
        if response.should_handoff and fub_person_id:
            try:
                from app.ai_agent.lead_ai_settings_service import LeadAISettingsServiceSingleton
                lead_ai_svc = LeadAISettingsServiceSingleton.get_instance(self.supabase)
                org_id = getattr(self.settings, 'organization_id', None) or (
                    conversation_context.organization_id if conversation_context else 'default'
                )
                await lead_ai_svc.disable_ai_for_lead(
                    fub_person_id=str(fub_person_id),
                    organization_id=org_id,
                )
                self.supabase.table('ai_scheduled_followups').update({
                    'status': 'cancelled',
                }).eq('fub_person_id', fub_person_id).eq('status', 'pending').execute()
                logger.info(f"Auto-disabled AI and cancelled follow-ups for lead {fub_person_id} (handoff from _finalize_response)")
            except Exception as disable_err:
                logger.warning(f"Failed to auto-disable AI on handoff for {fub_person_id}: {disable_err}")

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

        This persists AI-extracted data (timeline, budget, location, etc.)
        back to FUB so human agents can see it and it's available for future
        conversations.
        """
        try:
            from app.ai_agent.crm_sync_service import get_crm_sync_service
            from app.database.fub_api_client import FUBApiClient
        except ImportError as e:
            logger.warning(f"CRM sync modules not available: {e}")
            return

        try:
            # Create FUB client for API calls
            fub_client = FUBApiClient()

            # Get CRM sync service with FUB client
            crm_service = get_crm_sync_service(
                supabase_client=self.supabase,
                fub_client=fub_client,
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
                synced = result.get('synced_fields', 0)
                if synced > 0:
                    logger.info(f"Synced {synced} fields to FUB for person {fub_person_id}")
            else:
                logger.warning(f"CRM sync failed for person {fub_person_id}: {result.get('error')}")

        except Exception as e:
            # Log but don't fail the response - we still have data in ai_conversations table
            logger.error(f"Error syncing to CRM for person {fub_person_id}: {e}")

    async def get_conversation_state(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Get current conversation state for a lead."""
        qual_manager = self._qualification_managers.get(lead_id)

        if not qual_manager:
            return None

        progress = qual_manager.get_progress()

        return {
            "state": ConversationState.QUALIFYING.value,  # Default state
            "qualification_data": qual_manager.data.to_dict(),
            "qualification_progress": progress.overall_percentage if progress else 0,
            "is_qualified": progress.is_minimally_qualified if progress else False,
        }

    def reset_conversation(self, lead_id: str):
        """Reset conversation state for a lead."""
        self._conversation_managers.pop(lead_id, None)
        self._qualification_managers.pop(lead_id, None)

    async def process_message_with_tools(
        self,
        message: str,
        lead_profile: LeadProfile,
        conversation_history: List[Dict[str, Any]] = None,
        fub_person_id: int = None,
        user_id: str = None,
        organization_id: str = None,
    ) -> Dict[str, Any]:
        """
        Process message using Claude's tool use for intelligent action selection.

        This is the "smart" mode where Claude decides what action to take:
        - send_sms: Send a text message
        - send_email: Draft an email for review
        - create_task: Create a follow-up task for human agent
        - schedule_showing: Propose showing times
        - add_note: Document information in lead profile
        - no_action: Skip response (e.g., lead said "ok", "thanks")

        This is a single LLM call - Claude picks the best action AND generates content.

        Args:
            message: Incoming message from lead
            lead_profile: Rich lead profile for context
            conversation_history: Previous messages
            fub_person_id: FUB person ID
            user_id: User ID for settings
            organization_id: Organization ID

        Returns:
            Dict with tool_response, execution_result, and metadata
        """
        start_time = datetime.utcnow()
        lead_id = str(lead_profile.fub_person_id or fub_person_id or "unknown")

        # Load settings
        await self._load_db_settings(user_id, organization_id)

        # Check if AI is enabled
        if self._db_settings and not self._db_settings.is_enabled:
            return {
                "success": False,
                "skipped": True,
                "reason": "AI agent is disabled",
            }

        # Step 0: Stage Eligibility Check (includes user-excluded stages)
        if lead_profile.stage_name:
            is_eligible, stage_status, stage_reason = self.compliance_checker.check_stage_eligibility(
                lead_profile.stage_name, self.settings.excluded_stages
            )

            if not is_eligible:
                logger.info(f"Stage eligibility blocked: {stage_reason}")
                return {
                    "success": False,
                    "blocked": True,
                    "reason": stage_reason,
                    "status": stage_status.value,
                }

        # Step 1: Get qualification manager and create conversation context
        qual_manager = self._get_qualification_manager(lead_id)

        # Create conversation context for state tracking
        import uuid
        conversation_context = ConversationContext(
            conversation_id=str(uuid.uuid4()),
            fub_person_id=fub_person_id or 0,
            user_id=user_id or "",
            organization_id=organization_id or "",
        )

        try:
            # Step 2: Let Claude choose the action using tool use
            tool_response: ToolResponse = await self.response_generator.generate_response_with_tools(
                incoming_message=message,
                conversation_history=conversation_history or [],
                lead_profile=lead_profile,
                current_state=conversation_context.state.value,
                qualification_data=qual_manager.data.to_dict(),
            )

            logger.info(f"Claude selected action: {tool_response.action} for lead {lead_id}")

            # Step 3: Execute the selected action
            execution_result: ExecutionResult = await self.tool_executor.execute(
                tool_response=tool_response,
                fub_person_id=fub_person_id,
                lead_context={
                    "first_name": lead_profile.first_name,
                    "email": lead_profile.email,
                    "stage": lead_profile.stage_name,
                },
            )

            # Step 4: Update conversation state based on action
            if tool_response.action == "schedule_showing":
                conversation_context.state = ConversationState.SCHEDULING
            elif tool_response.action == "create_task":
                # Task created may indicate handoff
                conversation_context.state = ConversationState.HANDED_OFF
            elif tool_response.action == "no_action":
                # No state change for no_action
                pass

            # Calculate response time
            response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            return {
                "success": execution_result.success,
                "action": tool_response.action,
                "action_parameters": tool_response.parameters,
                "execution_result": execution_result.to_dict(),
                "conversation_state": conversation_context.state.value,
                "tokens_used": tool_response.tokens_used,
                "model_used": tool_response.model_used,
                "response_time_ms": response_time_ms,
            }

        except Exception as e:
            logger.error(f"Error in process_message_with_tools: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "action": "error",
            }


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
