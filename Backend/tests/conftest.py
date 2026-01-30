# -*- coding: utf-8 -*-
"""
Shared test fixtures for the AI Agent test suite.

Centralizes mock objects used across test_round4_features.py,
test_round4_scenarios.py, test_api_round4.py, and existing tests.
"""

import pytest
from datetime import datetime, time, timedelta
from unittest.mock import MagicMock, AsyncMock
from typing import Dict, Any

from app.ai_agent.settings_service import AIAgentSettings, AIAgentSettingsService
from app.ai_agent.conversation_manager import (
    ConversationContext,
    ConversationState,
    QualificationData,
)
from app.ai_agent.response_generator import LeadProfile, GeneratedResponse
from app.ai_agent.agent_service import AIAgentService


# =============================================================================
# DATABASE MOCKS
# =============================================================================

@pytest.fixture
def mock_supabase():
    """Create a mock Supabase client with chained query support."""
    mock = MagicMock()

    def create_table_mock(table_name):
        table = MagicMock()
        # Support full chaining: .select().eq().neq().lt().gt().gte().lte().limit().order().is_().in_()
        for method in [
            'select', 'eq', 'neq', 'lt', 'gt', 'gte', 'lte',
            'limit', 'order', 'is_', 'in_', 'not_',
        ]:
            getattr(table, method).return_value = table
        table.execute.return_value = MagicMock(data=[])
        table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "test-id"}])
        table.upsert.return_value.execute.return_value = MagicMock(data=[{"id": "test-id"}])
        table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "test-id"}])
        return table

    mock.table = create_table_mock
    return mock


@pytest.fixture
def mock_fub_api():
    """Create a mock FUB API client."""
    mock = MagicMock()
    mock.get_person.return_value = {
        'id': 3277,
        'firstName': 'John',
        'lastName': 'Test',
        'emails': [{'value': 'john@test.com'}],
        'phones': [{'value': '+14155551234'}],
        'stage': 'New Lead',
        'source': 'MyAgentFinder',
    }
    mock.send_text_message.return_value = {'success': True, 'id': 123}
    mock.create_task.return_value = {'success': True}
    mock.add_note.return_value = {'success': True}
    mock.add_tag.return_value = {'success': True}
    mock.update_person.return_value = {'success': True}
    return mock


# =============================================================================
# AI SERVICE
# =============================================================================

@pytest.fixture
def ai_service(mock_supabase, mock_fub_api):
    """Create an AIAgentService with mocked dependencies."""
    service = AIAgentService(
        anthropic_api_key="test-api-key",
        user_id="test-user-id",
        supabase_client=mock_supabase,
    )
    service.fub_client = mock_fub_api
    return service


# =============================================================================
# LEAD PROFILE
# =============================================================================

@pytest.fixture
def mock_lead_profile():
    """Create a fully populated mock lead profile."""
    return LeadProfile(
        first_name="John",
        last_name="Test",
        full_name="John Test",
        email="john@test.com",
        phone="+14155551234",
        score=50,
        score_label="Warm",
        stage="New Lead",
        stage_name="New Lead",
        source="MyAgentFinder",
        assigned_agent="Adam",
        tags=["buyer", "ai-enabled"],
    )


# =============================================================================
# CONVERSATION CONTEXT FACTORY
# =============================================================================

@pytest.fixture
def mock_conversation_context():
    """Factory fixture that returns a function to create ConversationContext in any state."""
    def make_context(
        state: str = "qualifying",
        score: int = 50,
        history_count: int = 5,
        fub_person_id: int = 3277,
    ) -> ConversationContext:
        ctx = ConversationContext(
            conversation_id="test-conv-001",
            fub_person_id=fub_person_id,
            user_id="test-user-id",
            organization_id="test-org-id",
            state=ConversationState(state),
            lead_score=score,
            qualification_data=QualificationData(),
            lead_name="John Test",
            lead_first_name="John",
            lead_phone="+14155551234",
            lead_email="john@test.com",
            lead_source="MyAgentFinder",
        )
        # Pre-populate conversation history
        for i in range(history_count):
            direction = "inbound" if i % 2 == 0 else "outbound"
            ctx.add_message(direction, f"Test message {i}", "sms")
        return ctx

    return make_context


# =============================================================================
# SETTINGS FIXTURES
# =============================================================================

@pytest.fixture
def mock_settings():
    """Create AIAgentSettings with all fields set to non-default values for testing."""
    return AIAgentSettings(
        agent_name="TestBot",
        brokerage_name="Test Realty",
        team_members="Adam and Mandi",
        personality_tone="professional",
        response_delay_seconds=45,
        response_delay_min_seconds=20,
        response_delay_max_seconds=90,
        first_message_delay_min=10,
        first_message_delay_max=45,
        max_sms_length=800,
        max_email_length=4000,
        working_hours_start=time(9, 0),
        working_hours_end=time(21, 0),
        timezone="America/Los_Angeles",
        auto_handoff_score=75,
        max_ai_messages_per_lead=20,
        is_enabled=True,
        auto_enable_new_leads=True,
        qualification_questions=["What's your timeline?", "Are you pre-approved?"],
        custom_scripts={"welcome": "Hi {name}!"},
        re_engagement_enabled=True,
        quiet_hours_before_re_engage=48,
        re_engagement_max_attempts=5,
        long_term_nurture_after_days=14,
        re_engagement_channels=["sms", "email", "voice"],
        sequence_sms_enabled=True,
        sequence_email_enabled=False,
        sequence_voice_enabled=True,
        sequence_rvm_enabled=True,
        day_0_aggression="moderate",
        proactive_appointment_enabled=False,
        qualification_questions_enabled=False,
        instant_response_enabled=False,
        instant_response_max_delay_seconds=30,
        nba_hot_lead_scan_interval_minutes=10,
        nba_cold_lead_scan_interval_minutes=30,
        llm_provider="anthropic",
        llm_model="claude-sonnet-4-20250514",
        llm_model_fallback="claude-haiku-4-20250414",
        notification_fub_person_id=12345,
        ai_respond_to_phone_numbers=["+19165551234"],
    )


@pytest.fixture
def mock_settings_db_row():
    """Dict matching the full ai_agent_settings DB row shape for round-trip testing."""
    return {
        "id": "settings-uuid-001",
        "user_id": "test-user-id",
        "organization_id": "test-org-id",
        "agent_name": "TestBot",
        "brokerage_name": "Test Realty",
        "team_members": "Adam and Mandi",
        "personality_tone": "professional",
        "response_delay_seconds": 45,
        "response_delay_min_seconds": 20,
        "response_delay_max_seconds": 90,
        "first_message_delay_min": 10,
        "first_message_delay_max": 45,
        "max_sms_length": 800,
        "max_email_length": 4000,
        "working_hours_start": "09:00",
        "working_hours_end": "21:00",
        "timezone": "America/Los_Angeles",
        "auto_handoff_score": 75,
        "max_ai_messages_per_lead": 20,
        "is_enabled": True,
        "auto_enable_new_leads": True,
        "qualification_questions": ["What's your timeline?", "Are you pre-approved?"],
        "custom_scripts": {"welcome": "Hi {name}!"},
        "re_engagement_enabled": True,
        "quiet_hours_before_re_engage": 48,
        "re_engagement_max_attempts": 5,
        "long_term_nurture_after_days": 14,
        "re_engagement_channels": ["sms", "email", "voice"],
        "sequence_sms_enabled": True,
        "sequence_email_enabled": False,
        "sequence_voice_enabled": True,
        "sequence_rvm_enabled": True,
        "day_0_aggression": "moderate",
        "proactive_appointment_enabled": False,
        "qualification_questions_enabled": False,
        "instant_response_enabled": False,
        "instant_response_max_delay_seconds": 30,
        "nba_hot_lead_scan_interval_minutes": 10,
        "nba_cold_lead_scan_interval_minutes": 30,
        "llm_provider": "anthropic",
        "llm_model": "claude-sonnet-4-20250514",
        "llm_model_fallback": "claude-haiku-4-20250414",
        "fub_login_email": None,
        "fub_login_password": None,
        "fub_login_type": "email",
        "notification_fub_person_id": 12345,
        "ai_respond_to_phone_numbers": ["+19165551234"],
    }


# =============================================================================
# CONVERSATION HISTORY
# =============================================================================

@pytest.fixture
def sample_conversation_history():
    """List of 55 message dicts — above the MAX_STORED_MESSAGES=50 cap."""
    messages = []
    for i in range(55):
        direction = "inbound" if i % 2 == 0 else "outbound"
        messages.append({
            "direction": direction,
            "content": f"Message number {i}",
            "channel": "sms",
            "timestamp": (datetime.utcnow() - timedelta(minutes=55 - i)).isoformat(),
        })
    return messages


# =============================================================================
# FLASK TEST CLIENT
# =============================================================================

@pytest.fixture
def flask_test_client():
    """Create a Flask test client with ai_settings and ai_monitoring blueprints."""
    from flask import Flask
    from app.api.ai_settings import ai_settings_bp
    from app.api.ai_monitoring import ai_monitoring_bp

    app = Flask(__name__)
    app.config['TESTING'] = True

    app.register_blueprint(ai_settings_bp, url_prefix='/api/ai-settings')
    app.register_blueprint(ai_monitoring_bp, url_prefix='/api/ai-monitoring')

    with app.test_client() as client:
        yield client


# =============================================================================
# GENERATED RESPONSE
# =============================================================================

@pytest.fixture
def mock_generated_response():
    """Create a mock generated response for testing."""
    return GeneratedResponse(
        response_text="Hey! When are you thinking of making a move?",
        next_state="qualifying",
        extracted_info={},
        lead_score_delta=5,
        should_handoff=False,
        detected_intent="greeting",
        detected_sentiment="neutral",
        confidence=0.85,
    )
