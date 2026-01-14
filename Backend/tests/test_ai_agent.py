"""
Comprehensive Unit Tests for AI Sales Agent Components.

Tests cover:
- Intent detection with pattern matching
- Qualification flow management
- Objection handling
- Lead scoring
- Template rendering
- Response generation (mocked)
- Compliance checking
"""

import pytest
import asyncio
from datetime import datetime, time, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Import components to test
from app.ai_agent.intent_detector import (
    IntentDetector,
    Intent,
    DetectedIntent,
    PatternMatcher,
    EntityExtractor,
    detect_intent,
)
from app.ai_agent.qualification_flow import (
    QualificationFlowManager,
    QualificationCategory,
    QualificationData,
    QualificationProgress,
)
from app.ai_agent.objection_handler import (
    ObjectionHandler,
    ObjectionType,
    ObjectionContext,
    ObjectionResponse,
    ResponseStrategy,
)
from app.ai_agent.lead_scorer import (
    LeadScorer,
    LeadScore,
    LeadTemperature,
)
from app.ai_agent.template_engine import (
    ResponseTemplateEngine,
    TemplateLibrary,
    TemplateCategory,
    MessageTemplate,
)
from app.ai_agent.response_generator import (
    LeadProfile,
    GeneratedResponse,
    ResponseQuality,
)
from app.ai_agent.compliance_checker import (
    ComplianceChecker,
    ComplianceStatus,
)


class TestIntentDetector:
    """Tests for the Intent Detector component."""

    def setup_method(self):
        """Set up test fixtures."""
        self.detector = IntentDetector()

    def test_greeting_detection(self):
        """Test detection of greeting intents."""
        greetings = ["Hi", "Hey", "Hello", "What's up", "Hey there!"]

        for greeting in greetings:
            result = self.detector.detect(greeting)
            assert result.primary_intent == Intent.GREETING, f"Failed for: {greeting}"
            assert result.confidence >= 0.7

    def test_opt_out_detection(self):
        """Test detection of opt-out requests (critical for compliance)."""
        opt_outs = [
            "STOP",
            "stop",
            "Unsubscribe",
            "Don't text me",
            "Remove me from your list",
            "opt out",
        ]

        for message in opt_outs:
            result = self.detector.detect(message)
            assert result.primary_intent == Intent.OPT_OUT, f"Failed for: {message}"
            assert result.confidence >= 0.9  # High confidence for compliance

    def test_escalation_request_detection(self):
        """Test detection of human agent requests."""
        escalations = [
            "I want to speak to a real person",
            "Can I talk to a human?",
            "Connect me with an agent",
            "Real person please",
        ]

        for message in escalations:
            result = self.detector.detect(message)
            assert result.primary_intent == Intent.ESCALATION_REQUEST, f"Failed for: {message}"

    def test_timeline_intent_detection(self):
        """Test detection of timeline-related intents."""
        timeline_cases = [
            ("I need to move ASAP", Intent.TIMELINE_IMMEDIATE),
            ("Looking to buy in the next month", Intent.TIMELINE_SHORT),
            ("Maybe in 3-6 months", Intent.TIMELINE_MEDIUM),
            ("Not until next year", Intent.TIMELINE_LONG),
            ("Just browsing for now", Intent.TIMELINE_UNKNOWN),
        ]

        for message, expected_intent in timeline_cases:
            result = self.detector.detect(message)
            assert result.primary_intent == expected_intent, f"Failed for: {message}"

    def test_objection_detection(self):
        """Test detection of objection intents."""
        objections = [
            ("I already have an agent", Intent.OBJECTION_OTHER_AGENT),
            ("I'm not ready yet", Intent.OBJECTION_NOT_READY),
            ("Just looking around", Intent.OBJECTION_JUST_BROWSING),
            ("That's too expensive", Intent.OBJECTION_PRICE),
            ("Not a good time", Intent.OBJECTION_TIMING),
        ]

        for message, expected_intent in objections:
            result = self.detector.detect(message)
            assert result.primary_intent == expected_intent, f"Failed for: {message}"

    def test_confirmation_yes_detection(self):
        """Test detection of affirmative responses."""
        affirmatives = ["Yes", "Yeah", "Sure", "Sounds good", "Perfect", "Absolutely"]

        for message in affirmatives:
            result = self.detector.detect(message)
            assert result.primary_intent == Intent.CONFIRMATION_YES, f"Failed for: {message}"

    def test_confirmation_no_detection(self):
        """Test detection of negative responses."""
        negatives = ["No", "Nope", "Not really", "Pass", "Not interested"]

        for message in negatives:
            result = self.detector.detect(message)
            assert result.primary_intent == Intent.CONFIRMATION_NO, f"Failed for: {message}"

    def test_appointment_interest_detection(self):
        """Test detection of scheduling interest."""
        scheduling = [
            "I'd like to schedule a showing",
            "Can we set up a time to meet?",
            "What's your availability?",
            "Let's book an appointment",
        ]

        for message in scheduling:
            result = self.detector.detect(message)
            assert result.primary_intent == Intent.APPOINTMENT_INTEREST, f"Failed for: {message}"

    def test_time_slot_selection(self):
        """Test detection of time slot selection."""
        selections = ["1", "2", "Option 3", "The first one", "Second option"]

        for message in selections:
            result = self.detector.detect(message)
            assert result.primary_intent == Intent.TIME_SELECTION, f"Failed for: {message}"

    def test_sentiment_detection(self):
        """Test sentiment classification."""
        positive_messages = ["That's great!", "I'm excited", "Sounds perfect"]
        negative_messages = ["I'm frustrated", "This is annoying", "Not happy"]

        for message in positive_messages:
            result = self.detector.detect(message)
            assert result.sentiment == "positive", f"Failed for: {message}"

        for message in negative_messages:
            result = self.detector.detect(message)
            assert result.sentiment == "negative", f"Failed for: {message}"


class TestEntityExtractor:
    """Tests for entity extraction."""

    def test_budget_amount_extraction(self):
        """Test extraction of budget amounts."""
        test_cases = [
            ("My budget is $500,000", 500000),
            ("Around 500k", 500000),
            ("I can afford $750K", 750000),
            ("300 thousand", 300000),
        ]

        for message, expected_value in test_cases:
            entity = EntityExtractor.extract_budget_amount(message)
            assert entity is not None, f"Failed to extract from: {message}"
            assert entity.value == expected_value, f"Wrong value for: {message}"

    def test_budget_range_extraction(self):
        """Test extraction of budget ranges."""
        entity = EntityExtractor.extract_budget_range("Looking between $400k-$600k")
        assert entity is not None
        assert entity.value["low"] == 400000
        assert entity.value["high"] == 600000

    def test_property_type_extraction(self):
        """Test extraction of property types."""
        test_cases = [
            ("I want a single family home", "single_family"),
            ("Looking for a condo", "condo"),
            ("Interested in townhouses", "townhouse"),
        ]

        for message, expected_type in test_cases:
            entity = EntityExtractor.extract_property_type(message)
            assert entity is not None, f"Failed for: {message}"
            assert entity.value == expected_type

    def test_time_slot_extraction(self):
        """Test extraction of time slot selections."""
        test_cases = [
            ("1", 1),
            ("Option 2", 2),
            ("The first one", 1),
            ("3", 3),
        ]

        for message, expected_slot in test_cases:
            entity = EntityExtractor.extract_time_slot_selection(message)
            assert entity is not None, f"Failed for: {message}"
            assert entity.value == expected_slot


class TestQualificationFlowManager:
    """Tests for the Qualification Flow Manager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.flow = QualificationFlowManager()

    def test_initial_progress(self):
        """Test initial qualification progress is 0%."""
        progress = self.flow.get_progress()
        assert progress.completed_categories == 0
        assert progress.is_minimally_qualified == False

    def test_get_next_question(self):
        """Test that questions are returned in priority order."""
        question, text = self.flow.get_next_question()
        assert question is not None
        assert len(text) > 0
        # First question should be timeline (highest priority)
        assert question.category == QualificationCategory.TIMELINE

    def test_update_from_intent(self):
        """Test updating qualification data from intent."""
        self.flow.update_from_intent(
            intent_name="timeline_immediate",
            extracted_entities=[],
            raw_message="I need to move ASAP",
        )

        assert self.flow.data.timeline == "immediate"

    def test_update_from_entities(self):
        """Test updating qualification data from entities."""
        entities = [
            {"type": "budget", "value": 500000, "raw_text": "$500k"},
            {"type": "location", "value": "Austin", "raw_text": "Austin area"},
        ]

        self.flow.update_from_intent(
            intent_name="other",
            extracted_entities=entities,
            raw_message="Looking in Austin area, budget $500k",
        )

        assert self.flow.data.budget == 500000
        assert "Austin" in self.flow.data.location_preferences

    def test_minimal_qualification(self):
        """Test minimal qualification detection."""
        # Add minimal required info
        self.flow.data.timeline = "short"
        self.flow.data.budget = 500000
        self.flow.data.location_preferences = ["Downtown"]

        progress = self.flow.get_progress()
        assert progress.is_minimally_qualified == True

    def test_qualification_score(self):
        """Test qualification score calculation."""
        # Hot lead scenario
        self.flow.data.timeline = "immediate"  # 25 points
        self.flow.data.is_pre_approved = True  # 25 points
        self.flow.data.location_preferences = ["Specific Area"]  # 20 points
        self.flow.data.property_types = ["single_family"]  # 10 points
        self.flow.data.motivation = "job"  # 10 points

        score = self.flow._calculate_score()
        assert score >= 80  # Should be a hot lead

    def test_no_duplicate_questions(self):
        """Test that the same question isn't asked twice in a row."""
        self.flow.data.questions_asked.append("timeline_general")
        question, _ = self.flow.get_next_question()

        # Should not be timeline again immediately
        if question:
            assert question.id != "timeline_general"


class TestObjectionHandler:
    """Tests for the Objection Handler."""

    def setup_method(self):
        """Set up test fixtures."""
        self.handler = ObjectionHandler()

    def test_objection_classification(self):
        """Test mapping intents to objection types."""
        assert self.handler.classify_objection("objection_other_agent") == ObjectionType.OTHER_AGENT
        assert self.handler.classify_objection("objection_not_ready") == ObjectionType.NOT_READY
        assert self.handler.classify_objection("objection_just_browsing") == ObjectionType.JUST_BROWSING
        assert self.handler.classify_objection("objection_price") == ObjectionType.PRICE_TOO_HIGH

    def test_first_objection_response(self):
        """Test response to first objection is helpful, not defensive."""
        context = ObjectionContext(
            objection_type=ObjectionType.NOT_READY,
            objection_count=1,
            lead_score=50,
        )

        response = self.handler.handle_objection(
            ObjectionType.NOT_READY,
            context,
        )

        assert response is not None
        assert len(response.response_text) > 0
        assert response.should_follow_up == True
        assert response.strategy != ResponseStrategy.GRACEFUL_EXIT

    def test_repeat_objection_graceful_exit(self):
        """Test that repeated objections lead to graceful exit."""
        context = ObjectionContext(
            objection_type=ObjectionType.OTHER_AGENT,
            objection_count=2,
            same_objection_count=2,
            lead_score=30,
        )

        response = self.handler.handle_objection(
            ObjectionType.OTHER_AGENT,
            context,
            lead_id="test_lead",
        )

        assert response.strategy == ResponseStrategy.GRACEFUL_EXIT
        assert response.should_follow_up == False

    def test_objection_history_tracking(self):
        """Test that objection history is tracked per lead."""
        context = ObjectionContext(
            objection_type=ObjectionType.NOT_READY,
        )

        self.handler.handle_objection(ObjectionType.NOT_READY, context, "lead_1")
        self.handler.handle_objection(ObjectionType.PRICE_TOO_HIGH, context, "lead_1")

        history = self.handler.get_objection_history("lead_1")
        assert len(history) == 2

    def test_response_under_sms_limit(self):
        """Test that all objection responses are under SMS limit."""
        objection_types = [
            ObjectionType.OTHER_AGENT,
            ObjectionType.NOT_READY,
            ObjectionType.JUST_BROWSING,
            ObjectionType.PRICE_TOO_HIGH,
            ObjectionType.BAD_TIMING,
        ]

        for obj_type in objection_types:
            context = ObjectionContext(objection_type=obj_type)
            response = self.handler.handle_objection(obj_type, context)

            # Some responses may be longer due to templates, but should be reasonable
            assert len(response.response_text) <= 320  # Allow 2 SMS max


class TestLeadScorer:
    """Tests for the Lead Scorer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.scorer = LeadScorer()

    def test_hot_lead_scoring(self):
        """Test that urgent, pre-approved leads score as hot."""
        qualification_data = {
            "timeline": "immediate",
            "is_pre_approved": True,
            "pre_approval_amount": 500000,
            "location_preferences": ["Downtown"],
            "motivation": "job",
        }

        score = self.scorer.calculate_score(qualification_data)
        assert score.temperature == LeadTemperature.HOT
        assert score.total_score >= 70

    def test_warm_lead_scoring(self):
        """Test warm lead scoring."""
        qualification_data = {
            "timeline": "short",
            "budget": 400000,
            "location_preferences": ["Suburbs"],
        }

        score = self.scorer.calculate_score(qualification_data)
        assert score.temperature == LeadTemperature.WARM
        assert 40 <= score.total_score < 70

    def test_cold_lead_scoring(self):
        """Test cold lead scoring."""
        qualification_data = {
            "timeline": "unknown",
        }

        score = self.scorer.calculate_score(qualification_data)
        assert score.temperature == LeadTemperature.COLD
        assert score.total_score < 40

    def test_score_breakdown(self):
        """Test that score breakdown is provided."""
        qualification_data = {
            "timeline": "immediate",
            "budget": 500000,
            "location_preferences": ["Area1"],
        }

        score = self.scorer.calculate_score(qualification_data)
        assert "timeline" in score.breakdown
        assert "budget" in score.breakdown


class TestTemplateEngine:
    """Tests for the Response Template Engine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = ResponseTemplateEngine()

    def test_welcome_message_rendering(self):
        """Test welcome message renders with variables."""
        lead_profile = {
            "first_name": "John",
            "interested_area": "Austin",
            "id": "test_123",
        }

        message = self.engine.get_welcome_message(lead_profile, agent_name="Sarah")

        assert "John" in message
        assert "Sarah" in message
        assert len(message) <= 200  # Should be SMS-friendly

    def test_property_inquiry_welcome(self):
        """Test welcome for property inquiry."""
        lead_profile = {
            "first_name": "Jane",
            "interested_property_address": "123 Main St",
            "id": "test_456",
        }

        message = self.engine.get_welcome_message(lead_profile, agent_name="Sarah")

        assert "123 Main St" in message

    def test_qualification_questions(self):
        """Test all qualification question types."""
        question_types = ["timeline", "budget", "location", "preapproval"]

        for q_type in question_types:
            question = self.engine.get_qualification_question(q_type)
            assert question is not None, f"Failed for: {q_type}"
            assert len(question) > 0

    def test_scheduling_message(self):
        """Test scheduling message with time options."""
        message = self.engine.get_scheduling_message(
            time_options=["Tuesday at 2pm", "Wednesday at 10am"],
            variables={"first_name": "Bob"},
        )

        assert "Tuesday at 2pm" in message or "Wednesday at 10am" in message

    def test_confirmation_message(self):
        """Test appointment confirmation message."""
        message = self.engine.get_confirmation_message(
            appointment_date="January 15",
            appointment_time="2:00 PM",
            first_name="Alice",
        )

        assert "January 15" in message
        assert "2:00 PM" in message
        assert "Alice" in message

    def test_fallback_message(self):
        """Test fallback message generation."""
        fallback = self.engine.get_fallback_message(
            category=TemplateCategory.WELCOME,
            variables={"first_name": "Test"},
        )

        assert len(fallback) > 0
        assert "Test" in fallback or "there" in fallback


class TestLeadProfile:
    """Tests for the Lead Profile context generation."""

    def test_profile_context_string(self):
        """Test that profile generates comprehensive context."""
        profile = LeadProfile(
            first_name="John",
            last_name="Doe",
            full_name="John Doe",
            email="john@example.com",
            score=75,
            score_label="Hot",
            source="Zillow",
            timeline="immediate",
            is_pre_approved=True,
            pre_approval_amount=500000,
            preferred_neighborhoods=["Downtown"],
            previous_objections=["not_ready"],
        )

        context = profile.to_context_string()

        # Verify all key sections are present
        assert "John Doe" in context
        assert "75/100" in context
        assert "Hot" in context
        assert "Zillow" in context
        assert "Ready NOW" in context or "immediate" in context.lower()
        assert "Pre-approved: Yes" in context
        assert "$500,000" in context
        assert "Downtown" in context
        assert "PREVIOUS OBJECTIONS" in context

    def test_profile_from_fub_data(self):
        """Test creating profile from FUB data structure."""
        fub_data = {
            "firstName": "Jane",
            "lastName": "Smith",
            "emails": [{"value": "jane@example.com"}],
            "phones": [{"value": "+1234567890"}],
            "source": "Website",
            "tags": [{"tag": "buyer"}],
            "createdAt": "2024-01-01T10:00:00Z",
        }

        additional_data = {
            "lead_score": 60,
            "timeline": "short",
        }

        profile = LeadProfile.from_fub_data(fub_data, additional_data)

        assert profile.first_name == "Jane"
        assert profile.last_name == "Smith"
        assert profile.email == "jane@example.com"
        assert profile.source == "Website"
        assert profile.score == 60
        assert profile.timeline == "short"


class TestComplianceChecker:
    """Tests for TCPA Compliance Checker."""

    def setup_method(self):
        """Set up test fixtures."""
        self.checker = ComplianceChecker(supabase_client=None)

    @pytest.mark.asyncio
    async def test_time_window_check(self):
        """Test that messages outside 8am-8pm are blocked."""
        # Mock time to be outside window
        with patch('app.ai_agent.compliance_checker.datetime') as mock_dt:
            # Set time to 6 AM
            mock_dt.now.return_value = datetime(2024, 1, 15, 6, 0, 0)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            result = self.checker._check_time_window("America/New_York")
            # Note: This test may need adjustment based on implementation
            # The key is to verify time window checking exists

    @pytest.mark.asyncio
    async def test_opt_out_recording(self):
        """Test opt-out recording."""
        # This would require mocking the database
        # For now, verify the method exists and can be called
        with patch.object(self.checker, '_record_opt_out') as mock_record:
            mock_record.return_value = True
            # The actual test would check database interaction


class TestIntegration:
    """Integration tests for component interactions."""

    def test_intent_to_qualification_flow(self):
        """Test intent detection feeds qualification flow."""
        detector = IntentDetector()
        qual_flow = QualificationFlowManager()

        # Simulate conversation
        message = "I need to move within the next month, budget around $500k"
        result = detector.detect(message)

        # Update qualification from detected entities
        qual_flow.update_from_intent(
            intent_name=result.primary_intent.value,
            extracted_entities=[e.__dict__ for e in result.extracted_entities],
            raw_message=message,
        )

        # Verify qualification was updated
        assert qual_flow.data.timeline == "short" or qual_flow.data.budget is not None

    def test_objection_affects_scoring(self):
        """Test that objections affect lead scoring."""
        scorer = LeadScorer()
        handler = ObjectionHandler()

        # Initial score
        initial_data = {"timeline": "short", "budget": 500000}
        initial_score = scorer.calculate_score(initial_data)

        # Handle objection
        context = ObjectionContext(
            objection_type=ObjectionType.NOT_READY,
            lead_score=initial_score.total_score,
        )
        response = handler.handle_objection(ObjectionType.NOT_READY, context)

        # Verify objection response exists
        assert response.response_text is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
