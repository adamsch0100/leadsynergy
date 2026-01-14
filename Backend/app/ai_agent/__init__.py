"""
AI Sales Agent Module for LeadSynergy.

Provides automated lead engagement through:
- Intelligent conversation management with state machine
- Lead scoring and qualification
- TCPA-compliant SMS/email communication
- Appointment scheduling with Google Calendar
- Seamless handoff to human agents
- Natural language understanding for intent detection
- Smart qualification question sequencing
- Context-aware objection handling

Components:
- ConversationManager: State machine for managing conversation flow
- LeadScorer: Scoring system based on qualification criteria
- ComplianceChecker: TCPA compliance verification
- ResponseGenerator: AI-powered response generation with rich context
- IntentDetector: NLU for understanding lead messages
- QualificationFlowManager: Smart question sequencing
- ObjectionHandler: Context-aware objection handling
- LeadProfile: Comprehensive lead context for personalization
"""

from app.ai_agent.conversation_manager import (
    ConversationManager,
    ConversationState,
    ConversationContext,
)
from app.ai_agent.lead_scorer import (
    LeadScorer,
    LeadScore,
)
from app.ai_agent.compliance_checker import (
    ComplianceChecker,
    ComplianceStatus,
    check_sms_compliance,
)
from app.ai_agent.response_generator import (
    AIResponseGenerator,
    ResponseGeneratorSingleton,
    GeneratedResponse,
    LeadProfile,
    ResponseQuality,
)
from app.ai_agent.intent_detector import (
    IntentDetector,
    Intent,
    DetectedIntent,
    detect_intent,
)
from app.ai_agent.qualification_flow import (
    QualificationFlowManager,
    QualificationCategory,
    QualificationData as QualificationFlowData,
    QualificationProgress,
    SmartQuestionSelector,
)
from app.ai_agent.objection_handler import (
    ObjectionHandler,
    ObjectionType,
    ObjectionResponse,
    ObjectionContext,
    handle_lead_objection,
)
from app.ai_agent.template_engine import (
    ResponseTemplateEngine,
    TemplateLibrary,
    MessageTemplate,
    TemplateCategory,
    ABTestRecord,
    get_template_engine,
)
from app.ai_agent.agent_service import (
    AIAgentService,
    AgentResponse,
    AgentSettings,
    ProcessingResult,
    create_agent_service,
)
from app.ai_agent.appointment_scheduler import (
    AppointmentScheduler,
    AppointmentSchedulerSingleton,
    AppointmentType,
    SchedulingContext,
    SchedulingResult,
    SchedulingState,
    get_appointment_scheduler,
)
from app.ai_agent.settings_service import (
    AIAgentSettings,
    AIAgentSettingsService,
    get_settings_service,
    get_agent_settings,
)
from app.ai_agent.crm_sync_service import (
    CRMSyncService,
    FieldMapping,
    get_crm_sync_service,
)

__all__ = [
    # Conversation management
    'ConversationManager',
    'ConversationState',
    'ConversationContext',
    # Lead scoring
    'LeadScorer',
    'LeadScore',
    # Compliance
    'ComplianceChecker',
    'ComplianceStatus',
    'check_sms_compliance',
    # Response generation
    'AIResponseGenerator',
    'ResponseGeneratorSingleton',
    'GeneratedResponse',
    'LeadProfile',
    'ResponseQuality',
    # Intent detection
    'IntentDetector',
    'Intent',
    'DetectedIntent',
    'detect_intent',
    # Qualification flow
    'QualificationFlowManager',
    'QualificationCategory',
    'QualificationFlowData',
    'QualificationProgress',
    'SmartQuestionSelector',
    # Objection handling
    'ObjectionHandler',
    'ObjectionType',
    'ObjectionResponse',
    'ObjectionContext',
    'handle_lead_objection',
    # Template engine
    'ResponseTemplateEngine',
    'TemplateLibrary',
    'MessageTemplate',
    'TemplateCategory',
    'ABTestRecord',
    'get_template_engine',
    # Agent service (main orchestrator)
    'AIAgentService',
    'AgentResponse',
    'AgentSettings',
    'ProcessingResult',
    'create_agent_service',
    # Appointment scheduling
    'AppointmentScheduler',
    'AppointmentSchedulerSingleton',
    'AppointmentType',
    'SchedulingContext',
    'SchedulingResult',
    'SchedulingState',
    'get_appointment_scheduler',
    # Settings service
    'AIAgentSettings',
    'AIAgentSettingsService',
    'get_settings_service',
    'get_agent_settings',
    # CRM sync service
    'CRMSyncService',
    'FieldMapping',
    'get_crm_sync_service',
]
