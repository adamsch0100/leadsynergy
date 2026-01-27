"""
Conversation Flow Tests - Multi-Turn Scenario Simulations.

Tests complete conversation scenarios from first contact to resolution.
Each scenario represents a realistic lead interaction pattern.

Run with: pytest tests/test_conversation_flows.py -v
"""

import pytest
import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from app.ai_agent.agent_service import AIAgentService, AgentResponse, ProcessingResult
from app.ai_agent.conversation_manager import ConversationState
from app.ai_agent.response_generator import GeneratedResponse, LeadProfile


# =============================================================================
# CONVERSATION TEST HARNESS
# =============================================================================

@dataclass
class ConversationStep:
    """A single step in a conversation scenario."""
    lead_message: str  # What the lead says (empty for first contact)
    expected_ai_behavior: str  # Description of expected AI behavior
    expected_state: Optional[str] = None  # Expected state after this step
    expected_intent: Optional[str] = None  # Expected detected intent
    expected_score_change: Optional[str] = None  # "increase", "decrease", "stable"
    should_handoff: bool = False  # Whether handoff should trigger


@dataclass
class ConversationScenario:
    """A complete conversation scenario to test."""
    name: str
    description: str
    lead_source: str
    lead_type: str  # buyer, seller, both
    steps: List[ConversationStep]
    expected_final_state: str
    expected_final_outcome: str  # "appointment", "nurture", "opted_out", "handed_off"


# =============================================================================
# SCENARIO DEFINITIONS
# =============================================================================

SCENARIOS = {
    "hot_buyer_quick_close": ConversationScenario(
        name="Hot Buyer - Quick Close",
        description="Motivated buyer who provides info quickly and books appointment",
        lead_source="MyAgentFinder",
        lead_type="buyer",
        steps=[
            ConversationStep(
                lead_message="",
                expected_ai_behavior="AI sends warm first contact with qualification question",
                expected_state="initial",
                expected_intent="greeting",
            ),
            ConversationStep(
                lead_message="Yes interested!",
                expected_ai_behavior="AI detects interest, asks timeline",
                expected_state="qualifying",
                expected_intent="positive_interest",
                expected_score_change="increase",
            ),
            ConversationStep(
                lead_message="Looking to move in 30 days",
                expected_ai_behavior="AI extracts timeline, asks budget",
                expected_state="qualifying",
                expected_intent="timeline_info",
                expected_score_change="increase",
            ),
            ConversationStep(
                lead_message="Pre-approved for $500k",
                expected_ai_behavior="AI extracts budget, offers appointment",
                expected_state="scheduling",
                expected_intent="budget_info",
                expected_score_change="increase",
            ),
            ConversationStep(
                lead_message="Sure, Thursday works",
                expected_ai_behavior="AI confirms appointment, triggers handoff",
                expected_state="handed_off",
                expected_intent="confirmation",
                should_handoff=True,
            ),
        ],
        expected_final_state="handed_off",
        expected_final_outcome="appointment",
    ),

    "cold_lead_nurture": ConversationScenario(
        name="Cold Lead - Nurture",
        description="Lead who is just browsing, not ready to buy",
        lead_source="Zillow",
        lead_type="buyer",
        steps=[
            ConversationStep(
                lead_message="",
                expected_ai_behavior="AI sends first contact",
                expected_state="initial",
            ),
            ConversationStep(
                lead_message="Just browsing",
                expected_ai_behavior="AI acknowledges, gently qualifies timeline",
                expected_state="qualifying",
                expected_intent="low_interest",
            ),
            ConversationStep(
                lead_message="Not ready yet, maybe next year",
                expected_ai_behavior="AI moves to nurture mode, offers to stay in touch",
                expected_state="nurture",
                expected_intent="timeline_info",
                expected_score_change="decrease",
            ),
        ],
        expected_final_state="nurture",
        expected_final_outcome="nurture",
    ),

    "objection_handling": ConversationScenario(
        name="Objection Handling",
        description="Lead raises objection about working with another agent",
        lead_source="Redfin",
        lead_type="buyer",
        steps=[
            ConversationStep(
                lead_message="",
                expected_ai_behavior="AI sends first contact",
                expected_state="initial",
            ),
            ConversationStep(
                lead_message="Already working with an agent",
                expected_ai_behavior="AI handles objection gracefully, doesn't push",
                expected_state="objection_handling",
                expected_intent="objection",
                expected_score_change="decrease",
            ),
            ConversationStep(
                lead_message="Actually they're not great, they never respond",
                expected_ai_behavior="AI re-engages opportunity, offers help",
                expected_state="qualifying",
                expected_intent="positive_interest",
                expected_score_change="increase",
            ),
        ],
        expected_final_state="qualifying",
        expected_final_outcome="re_engaged",
    ),

    "escalation_request": ConversationScenario(
        name="Escalation Request",
        description="Lead immediately asks for human agent",
        lead_source="HomeLight",
        lead_type="seller",
        steps=[
            ConversationStep(
                lead_message="",
                expected_ai_behavior="AI sends first contact",
                expected_state="initial",
            ),
            ConversationStep(
                lead_message="I want to talk to a real person",
                expected_ai_behavior="AI immediately hands off to human",
                expected_state="handed_off",
                expected_intent="escalation",
                should_handoff=True,
            ),
        ],
        expected_final_state="handed_off",
        expected_final_outcome="handed_off",
    ),

    "opt_out_flow": ConversationScenario(
        name="Opt-Out Flow",
        description="Lead opts out of messages",
        lead_source="Facebook",
        lead_type="buyer",
        steps=[
            ConversationStep(
                lead_message="",
                expected_ai_behavior="AI sends first contact",
                expected_state="initial",
            ),
            ConversationStep(
                lead_message="STOP",
                expected_ai_behavior="AI sends opt-out confirmation, records opt-out",
                expected_state="completed",
                expected_intent="opt_out",
            ),
        ],
        expected_final_state="completed",
        expected_final_outcome="opted_out",
    ),

    "seller_listing_consultation": ConversationScenario(
        name="Seller - Listing Consultation",
        description="Seller inquiring about listing their home",
        lead_source="HomeLight",
        lead_type="seller",
        steps=[
            ConversationStep(
                lead_message="",
                expected_ai_behavior="AI sends seller-focused first contact",
                expected_state="initial",
            ),
            ConversationStep(
                lead_message="I want to sell my house",
                expected_ai_behavior="AI qualifies timeline for selling",
                expected_state="qualifying",
                expected_intent="positive_interest",
            ),
            ConversationStep(
                lead_message="Need to sell in 60 days for job relocation",
                expected_ai_behavior="AI extracts urgency, offers listing consultation",
                expected_state="scheduling",
                expected_intent="timeline_info",
                expected_score_change="increase",
            ),
            ConversationStep(
                lead_message="Yes, I'd like a consultation",
                expected_ai_behavior="AI schedules consultation, hands off",
                expected_state="handed_off",
                expected_intent="confirmation",
                should_handoff=True,
            ),
        ],
        expected_final_state="handed_off",
        expected_final_outcome="appointment",
    ),

    "frustrated_lead": ConversationScenario(
        name="Frustrated Lead",
        description="Lead becomes frustrated and AI escalates",
        lead_source="ReferralExchange",
        lead_type="buyer",
        steps=[
            ConversationStep(
                lead_message="",
                expected_ai_behavior="AI sends first contact",
                expected_state="initial",
            ),
            ConversationStep(
                lead_message="Stop bothering me",
                expected_ai_behavior="AI detects frustration, offers to back off or connect human",
                expected_state="objection_handling",
                expected_intent="frustration",
                expected_score_change="decrease",
            ),
            ConversationStep(
                lead_message="This is ridiculous, just stop",
                expected_ai_behavior="AI escalates to human agent",
                expected_state="handed_off",
                expected_intent="frustration",
                should_handoff=True,
            ),
        ],
        expected_final_state="handed_off",
        expected_final_outcome="handed_off",
    ),

    "multiple_objections": ConversationScenario(
        name="Multiple Objections",
        description="Lead raises multiple objections, triggering escalation",
        lead_source="Zillow",
        lead_type="buyer",
        steps=[
            ConversationStep(
                lead_message="",
                expected_ai_behavior="AI sends first contact",
                expected_state="initial",
            ),
            ConversationStep(
                lead_message="I'm not interested",
                expected_ai_behavior="AI handles first objection",
                expected_state="objection_handling",
                expected_intent="objection",
            ),
            ConversationStep(
                lead_message="I said I'm not interested",
                expected_ai_behavior="AI handles second objection more carefully",
                expected_state="objection_handling",
                expected_intent="objection",
            ),
            ConversationStep(
                lead_message="Seriously stop contacting me",
                expected_ai_behavior="AI escalates after 3rd objection",
                expected_state="handed_off",
                expected_intent="objection",
                should_handoff=True,
            ),
        ],
        expected_final_state="handed_off",
        expected_final_outcome="handed_off",
    ),
}


# =============================================================================
# TEST HARNESS
# =============================================================================

class ConversationTestHarness:
    """
    Test harness for running conversation scenarios.

    Maintains state across multiple messages and verifies expectations.
    """

    def __init__(self, fub_person_id: int, scenario: ConversationScenario):
        self.fub_person_id = fub_person_id
        self.scenario = scenario
        self.conversation_history: List[Dict[str, Any]] = []
        self.current_state: str = "initial"
        self.lead_score: int = 50  # Starting score
        self.qualification_data: Dict[str, Any] = {}
        self.step_results: List[Dict[str, Any]] = []

    async def simulate_lead_message(
        self,
        message: str,
        ai_service: AIAgentService,
        mock_response: GeneratedResponse,
    ) -> Dict[str, Any]:
        """
        Simulate a lead message and AI response.

        Args:
            message: Lead's message (empty for first contact)
            ai_service: The AI service to use
            mock_response: Mocked LLM response

        Returns:
            Dict with response details and state
        """
        # Add lead message to history (if not empty)
        if message:
            self.conversation_history.append({
                "direction": "inbound",
                "content": message,
                "timestamp": datetime.utcnow().isoformat(),
            })

        # Get AI response
        with patch.object(
            ai_service, '_generate_ai_response',
            new_callable=AsyncMock, return_value=mock_response
        ):
            response = await ai_service.process_message(
                fub_person_id=self.fub_person_id,
                incoming_message=message,
                channel="sms",
            )

        # Update harness state
        if response:
            self.current_state = response.conversation_state
            self.lead_score = response.lead_score

            # Add AI response to history
            self.conversation_history.append({
                "direction": "outbound",
                "content": response.message_text,
                "timestamp": datetime.utcnow().isoformat(),
            })

            # Update qualification data
            if response.extracted_info:
                self.qualification_data.update(response.extracted_info)

        result = {
            "lead_message": message,
            "ai_response": response.message_text if response else None,
            "state": self.current_state,
            "lead_score": self.lead_score,
            "should_handoff": response.should_handoff if response else False,
            "extracted_info": response.extracted_info if response else {},
        }

        self.step_results.append(result)
        return result

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of the conversation test."""
        return {
            "scenario": self.scenario.name,
            "final_state": self.current_state,
            "final_score": self.lead_score,
            "total_messages": len(self.conversation_history),
            "qualification_data": self.qualification_data,
            "step_results": self.step_results,
        }


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_supabase():
    """Create a mock Supabase client."""
    mock = MagicMock()

    def create_table_mock(table_name):
        table = MagicMock()
        table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "test"}])
        table.upsert.return_value.execute.return_value = MagicMock(data=[{"id": "test"}])
        return table

    mock.table = create_table_mock
    return mock


@pytest.fixture
def mock_fub_api():
    """Create a mock FUB API."""
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
    return mock


@pytest.fixture
def ai_service(mock_supabase, mock_fub_api):
    """Create an AI service for testing."""
    with patch('app.ai_agent.agent_service.SupabaseClientSingleton') as mock_singleton:
        mock_singleton.get_instance.return_value = mock_supabase

        service = AIAgentService(
            fub_api_key="test-api-key",
            user_id="test-user-id",
        )
        service.fub_client = mock_fub_api

        return service


# =============================================================================
# SCENARIO TESTS
# =============================================================================

class TestConversationScenarios:
    """Test multi-turn conversation scenarios."""

    @pytest.mark.asyncio
    async def test_hot_buyer_quick_close(self, ai_service):
        """Test hot buyer scenario - quick qualification to appointment."""
        scenario = SCENARIOS["hot_buyer_quick_close"]
        harness = ConversationTestHarness(fub_person_id=3277, scenario=scenario)

        # Mock responses for each step
        responses = [
            GeneratedResponse(
                response_text="Hey John! Sarah here. When are you thinking of making a move?",
                next_state="initial",
                extracted_info={},
                lead_score_delta=5,
                should_handoff=False,
                intent="greeting",
                sentiment="neutral",
                confidence=0.85,
            ),
            GeneratedResponse(
                response_text="Great! What's your timeline?",
                next_state="qualifying",
                extracted_info={"interest_level": "high"},
                lead_score_delta=10,
                should_handoff=False,
                intent="positive_interest",
                sentiment="positive",
                confidence=0.9,
            ),
            GeneratedResponse(
                response_text="Perfect! What's your budget range?",
                next_state="qualifying",
                extracted_info={"timeline": "30_days"},
                lead_score_delta=15,
                should_handoff=False,
                intent="timeline_info",
                sentiment="positive",
                confidence=0.9,
            ),
            GeneratedResponse(
                response_text="Excellent! Thursday at 3pm work for a quick call?",
                next_state="scheduling",
                extracted_info={"budget": 500000, "is_pre_approved": True},
                lead_score_delta=20,
                should_handoff=False,
                intent="budget_info",
                sentiment="positive",
                confidence=0.95,
            ),
            GeneratedResponse(
                response_text="Perfect! I'll send a calendar invite. Talk soon!",
                next_state="handed_off",
                extracted_info={"appointment_accepted": True},
                lead_score_delta=10,
                should_handoff=True,
                handoff_reason="appointment_scheduled",
                intent="confirmation",
                sentiment="positive",
                confidence=0.95,
            ),
        ]

        # Run each step
        for i, step in enumerate(scenario.steps):
            result = await harness.simulate_lead_message(
                message=step.lead_message,
                ai_service=ai_service,
                mock_response=responses[i],
            )

            # Verify expectations
            if step.should_handoff:
                assert result["should_handoff"] is True

        # Verify final state
        summary = harness.get_summary()
        assert summary["final_state"] == scenario.expected_final_state

    @pytest.mark.asyncio
    async def test_cold_lead_nurture(self, ai_service):
        """Test cold lead moves to nurture state."""
        scenario = SCENARIOS["cold_lead_nurture"]
        harness = ConversationTestHarness(fub_person_id=3277, scenario=scenario)

        responses = [
            GeneratedResponse(
                response_text="Hey! When are you thinking of making a move?",
                next_state="initial",
                extracted_info={},
                lead_score_delta=5,
                should_handoff=False,
                intent="greeting",
                sentiment="neutral",
                confidence=0.85,
            ),
            GeneratedResponse(
                response_text="No problem! What are you looking for when you're ready?",
                next_state="qualifying",
                extracted_info={"interest_level": "low"},
                lead_score_delta=-5,
                should_handoff=False,
                intent="low_interest",
                sentiment="neutral",
                confidence=0.8,
            ),
            GeneratedResponse(
                response_text="Got it! I'll check in next year. Good luck!",
                next_state="nurture",
                extracted_info={"timeline": "12_months_plus"},
                lead_score_delta=-10,
                should_handoff=False,
                intent="timeline_info",
                sentiment="neutral",
                confidence=0.85,
            ),
        ]

        for i, step in enumerate(scenario.steps):
            await harness.simulate_lead_message(
                message=step.lead_message,
                ai_service=ai_service,
                mock_response=responses[i],
            )

        summary = harness.get_summary()
        assert summary["final_state"] == "nurture"

    @pytest.mark.asyncio
    async def test_objection_recovery(self, ai_service):
        """Test objection handling and re-engagement."""
        scenario = SCENARIOS["objection_handling"]
        harness = ConversationTestHarness(fub_person_id=3277, scenario=scenario)

        responses = [
            GeneratedResponse(
                response_text="Hey! When are you thinking of making a move?",
                next_state="initial",
                extracted_info={},
                lead_score_delta=5,
                should_handoff=False,
                intent="greeting",
                sentiment="neutral",
                confidence=0.85,
            ),
            GeneratedResponse(
                response_text="Totally understand! Just curious - what made you start looking?",
                next_state="objection_handling",
                extracted_info={"objection": "working_with_agent"},
                lead_score_delta=-10,
                should_handoff=False,
                intent="objection",
                sentiment="negative",
                confidence=0.9,
            ),
            GeneratedResponse(
                response_text="I hear that a lot. I always respond same day. Want to chat?",
                next_state="qualifying",
                extracted_info={"objection_resolved": True},
                lead_score_delta=15,
                should_handoff=False,
                intent="positive_interest",
                sentiment="positive",
                confidence=0.85,
            ),
        ]

        for i, step in enumerate(scenario.steps):
            await harness.simulate_lead_message(
                message=step.lead_message,
                ai_service=ai_service,
                mock_response=responses[i],
            )

        summary = harness.get_summary()
        assert summary["final_state"] == "qualifying"

    @pytest.mark.asyncio
    async def test_immediate_escalation(self, ai_service):
        """Test immediate escalation request."""
        scenario = SCENARIOS["escalation_request"]
        harness = ConversationTestHarness(fub_person_id=3277, scenario=scenario)

        responses = [
            GeneratedResponse(
                response_text="Hey! When are you thinking of selling?",
                next_state="initial",
                extracted_info={},
                lead_score_delta=5,
                should_handoff=False,
                intent="greeting",
                sentiment="neutral",
                confidence=0.85,
            ),
            GeneratedResponse(
                response_text="Of course! Let me connect you with Sarah right now.",
                next_state="handed_off",
                extracted_info={},
                lead_score_delta=0,
                should_handoff=True,
                handoff_reason="escalation_request",
                intent="escalation",
                sentiment="neutral",
                confidence=0.95,
            ),
        ]

        for i, step in enumerate(scenario.steps):
            result = await harness.simulate_lead_message(
                message=step.lead_message,
                ai_service=ai_service,
                mock_response=responses[i],
            )

        summary = harness.get_summary()
        assert summary["final_state"] == "handed_off"
        assert harness.step_results[-1]["should_handoff"] is True

    @pytest.mark.asyncio
    async def test_opt_out_flow(self, ai_service):
        """Test opt-out is handled correctly."""
        scenario = SCENARIOS["opt_out_flow"]
        harness = ConversationTestHarness(fub_person_id=3277, scenario=scenario)

        responses = [
            GeneratedResponse(
                response_text="Hey! When are you thinking of making a move?",
                next_state="initial",
                extracted_info={},
                lead_score_delta=5,
                should_handoff=False,
                intent="greeting",
                sentiment="neutral",
                confidence=0.85,
            ),
            GeneratedResponse(
                response_text="You've been unsubscribed. Reply START to opt back in.",
                next_state="completed",
                extracted_info={"opted_out": True},
                lead_score_delta=0,
                should_handoff=False,
                intent="opt_out",
                sentiment="neutral",
                confidence=1.0,
            ),
        ]

        for i, step in enumerate(scenario.steps):
            await harness.simulate_lead_message(
                message=step.lead_message,
                ai_service=ai_service,
                mock_response=responses[i],
            )

        summary = harness.get_summary()
        assert summary["final_state"] == "completed"
        assert summary["qualification_data"].get("opted_out") is True


# =============================================================================
# PARAMETERIZED TESTS
# =============================================================================

class TestAllScenarios:
    """Run all scenarios with parameterized tests."""

    @pytest.mark.parametrize("scenario_name", list(SCENARIOS.keys()))
    @pytest.mark.asyncio
    async def test_scenario_completes(self, scenario_name, ai_service):
        """Each scenario completes without error."""
        scenario = SCENARIOS[scenario_name]
        harness = ConversationTestHarness(fub_person_id=3277, scenario=scenario)

        # Generate basic mock responses
        for i, step in enumerate(scenario.steps):
            mock_response = GeneratedResponse(
                response_text=f"AI response for step {i}",
                next_state=step.expected_state or "qualifying",
                extracted_info={},
                lead_score_delta=5,
                should_handoff=step.should_handoff,
                intent=step.expected_intent or "unknown",
                sentiment="neutral",
                confidence=0.85,
            )

            await harness.simulate_lead_message(
                message=step.lead_message,
                ai_service=ai_service,
                mock_response=mock_response,
            )

        # Verify scenario completed
        summary = harness.get_summary()
        assert len(summary["step_results"]) == len(scenario.steps)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
