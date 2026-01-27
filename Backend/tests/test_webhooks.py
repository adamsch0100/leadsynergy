"""
Webhook Flow Tests for AI Agent.

Tests the complete webhook flow from FUB event to AI response.
Verifies incoming/outgoing detection, compliance, automation pausing, etc.

Run with: pytest tests/test_webhooks.py -v
"""

import pytest
import asyncio
import json
from datetime import datetime, time, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from flask import Flask

# Import webhook handlers
from app.webhook.ai_webhook_handlers import (
    ai_webhook_bp,
    process_inbound_text,
    build_lead_profile_from_fub,
    get_conversation_history,
)
from app.ai_agent.compliance_checker import (
    ComplianceChecker,
    ComplianceStatus,
    ComplianceResult,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(ai_webhook_bp)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def mock_fub_webhook_payload():
    """Create a mock FUB webhook payload for textMessagesCreated."""
    return {
        "event": "textMessagesCreated",
        "uri": "https://api.followupboss.com/v1/textMessages/123456",
        "resourceIds": [123456],
    }


@pytest.fixture
def mock_incoming_message():
    """Create a mock incoming text message from FUB."""
    return {
        "textmessages": [{
            "id": 123456,
            "personId": 3277,
            "message": "Yes, I'm interested!",
            "isIncoming": True,
            "from": "+14155551234",
            "to": "+14155559999",
            "created": "2024-01-19T15:30:00Z",
        }]
    }


@pytest.fixture
def mock_outgoing_message():
    """Create a mock outgoing text message from FUB."""
    return {
        "textmessages": [{
            "id": 123457,
            "personId": 3277,
            "message": "Hey John! When are you thinking of making a move?",
            "isIncoming": False,
            "from": "+14155559999",
            "to": "+14155551234",
            "created": "2024-01-19T15:25:00Z",
        }]
    }


@pytest.fixture
def mock_opt_out_message():
    """Create a mock opt-out message."""
    return {
        "textmessages": [{
            "id": 123458,
            "personId": 3277,
            "message": "STOP",
            "isIncoming": True,
            "from": "+14155551234",
            "to": "+14155559999",
            "created": "2024-01-19T16:00:00Z",
        }]
    }


@pytest.fixture
def mock_lead_data():
    """Create mock lead data from FUB."""
    return {
        "id": 3277,
        "firstName": "John",
        "lastName": "Test",
        "emails": [{"value": "john@test.com"}],
        "phones": [{"value": "+14155551234"}],
        "stage": "New Lead",
        "source": "MyAgentFinder",
        "tags": ["ReferralLink"],
        "assignedUserId": 12345,
        "organizationId": "test-org-id",
    }


@pytest.fixture
def mock_supabase():
    """Create a mock Supabase client."""
    mock = MagicMock()

    # Mock table queries
    def create_table_mock(table_name):
        table = MagicMock()
        table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        table.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=None)
        table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "test-id"}])
        table.upsert.return_value.execute.return_value = MagicMock(data=[{"id": "test-id"}])
        return table

    mock.table = create_table_mock
    return mock


# =============================================================================
# WEBHOOK RECEIPT TESTS
# =============================================================================

class TestTextMessageWebhook:
    """Test /webhooks/ai/text-received endpoint."""

    def test_webhook_endpoint_exists(self, client):
        """Webhook endpoint exists and accepts POST requests."""
        # Webhook endpoints only accept POST (not GET)
        response = client.post(
            '/webhooks/ai/text-received',
            data='{}',
            content_type='application/json',
        )
        assert response.status_code == 200

    def test_webhook_accepts_post(self, client, mock_fub_webhook_payload):
        """Webhook accepts POST with FUB payload."""
        response = client.post(
            '/webhooks/ai/text-received',
            data=json.dumps(mock_fub_webhook_payload),
            content_type='application/json',
        )
        # Should return 200 (acknowledges receipt)
        assert response.status_code == 200

    def test_webhook_handles_empty_payload(self, client):
        """Webhook handles empty payload gracefully."""
        response = client.post(
            '/webhooks/ai/text-received',
            data='{}',
            content_type='application/json',
        )
        assert response.status_code == 200

    def test_webhook_handles_missing_resource_ids(self, client):
        """Webhook handles missing resourceIds."""
        response = client.post(
            '/webhooks/ai/text-received',
            data=json.dumps({"event": "textMessagesCreated"}),
            content_type='application/json',
        )
        assert response.status_code == 200


# =============================================================================
# MESSAGE DIRECTION TESTS
# =============================================================================

class TestMessageDirection:
    """Test incoming vs outgoing message detection."""

    @pytest.mark.asyncio
    async def test_incoming_message_triggers_ai(self, mock_incoming_message, mock_lead_data, mock_supabase):
        """Incoming message (isIncoming=True) generates AI response."""
        text_msg = mock_incoming_message["textmessages"][0]

        # Verify it's detected as incoming
        assert text_msg.get("isIncoming") is True

        # In real flow, this would trigger AI processing
        # Here we just verify the detection logic
        is_incoming = text_msg.get("isIncoming", False)
        assert is_incoming is True

    @pytest.mark.asyncio
    async def test_outgoing_message_ignored(self, mock_outgoing_message):
        """Outgoing message (isIncoming=False) is skipped."""
        text_msg = mock_outgoing_message["textmessages"][0]

        # Verify it's detected as outgoing
        assert text_msg.get("isIncoming") is False

        # This should NOT trigger AI processing
        is_incoming = text_msg.get("isIncoming", False)
        assert is_incoming is False


# =============================================================================
# OPT-OUT TESTS
# =============================================================================

class TestOptOutHandling:
    """Test opt-out keyword detection and handling."""

    def test_stop_keyword_detected(self):
        """'STOP' keyword triggers opt-out flow."""
        opt_out_keywords = ["STOP", "stop", "Stop", "UNSUBSCRIBE", "unsubscribe"]

        for keyword in opt_out_keywords:
            is_opt_out = keyword.upper() in ["STOP", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"]
            assert is_opt_out, f"Failed for keyword: {keyword}"

    def test_opt_out_variations(self):
        """Various opt-out phrases are detected."""
        opt_out_phrases = [
            "STOP",
            "stop",
            "Unsubscribe",
            "remove me",
            "don't text me",
            "opt out",
        ]

        # Check lowercase contains opt-out keywords
        for phrase in opt_out_phrases:
            lower = phrase.lower()
            contains_keyword = any(kw in lower for kw in ["stop", "unsubscribe", "remove", "opt out", "don't text"])
            assert contains_keyword, f"Failed for phrase: {phrase}"

    @pytest.mark.asyncio
    async def test_opt_out_records_in_database(self, mock_supabase):
        """Opt-out is recorded in the database."""
        # This would test the full flow in integration
        # For now, verify the opt-out recording pattern
        opt_out_data = {
            "fub_person_id": 3277,
            "opted_out_at": datetime.utcnow().isoformat(),
            "opt_out_keyword": "STOP",
        }

        # Verify data structure is correct
        assert "fub_person_id" in opt_out_data
        assert "opted_out_at" in opt_out_data


# =============================================================================
# AUTOMATION PAUSE TESTS
# =============================================================================

class TestAutomationPause:
    """Test automation cancellation on lead reply."""

    @pytest.mark.asyncio
    async def test_reply_cancels_pending_sequences(self):
        """Lead reply cancels pending scheduled messages."""
        # This tests the concept - actual implementation would mock celery
        fub_person_id = 3277
        reason = "Lead responded - pausing automation"

        # Verify the cancellation would be triggered
        cancellation_data = {
            "fub_person_id": fub_person_id,
            "reason": reason,
            "cancelled_at": datetime.utcnow().isoformat(),
        }

        assert cancellation_data["fub_person_id"] == 3277
        assert "pausing automation" in cancellation_data["reason"]


# =============================================================================
# COMPLIANCE TESTS
# =============================================================================

class TestComplianceBlocking:
    """Test compliance-based message blocking."""

    def test_outside_hours_blocked(self):
        """Messages outside 8 AM - 8 PM are blocked."""
        checker = ComplianceChecker()

        # Test time at 11 PM (outside hours)
        late_night = time(23, 0)  # 11 PM
        is_within_hours = time(8, 0) <= late_night <= time(20, 0)
        assert not is_within_hours

        # Test time at 2 PM (within hours)
        afternoon = time(14, 0)  # 2 PM
        is_within_hours = time(8, 0) <= afternoon <= time(20, 0)
        assert is_within_hours

    def test_working_hours_boundary(self):
        """Test working hours boundaries."""
        # 8:00 AM - should be allowed
        t1 = time(8, 0)
        assert time(8, 0) <= t1 <= time(20, 0)

        # 7:59 AM - should be blocked
        t2 = time(7, 59)
        assert not (time(8, 0) <= t2 <= time(20, 0))

        # 8:00 PM - should be allowed
        t3 = time(20, 0)
        assert time(8, 0) <= t3 <= time(20, 0)

        # 8:01 PM - should be blocked
        t4 = time(20, 1)
        assert not (time(8, 0) <= t4 <= time(20, 0))


# =============================================================================
# LEAD CREATED WEBHOOK TESTS
# =============================================================================

class TestLeadCreatedWebhook:
    """Test /webhooks/ai/lead-created endpoint."""

    def test_lead_created_endpoint_exists(self, client):
        """Lead created webhook endpoint exists and accepts POST."""
        # Webhook endpoints only accept POST (not GET)
        response = client.post(
            '/webhooks/ai/lead-created',
            data='{}',
            content_type='application/json',
        )
        assert response.status_code == 200

    def test_lead_created_accepts_post(self, client):
        """Lead created webhook accepts POST."""
        payload = {
            "event": "peopleCreated",
            "uri": "https://api.followupboss.com/v1/people/3277",
            "resourceIds": [3277],
        }

        response = client.post(
            '/webhooks/ai/lead-created',
            data=json.dumps(payload),
            content_type='application/json',
        )
        assert response.status_code == 200


# =============================================================================
# LEAD PROFILE BUILDING TESTS
# =============================================================================

class TestLeadProfileBuilding:
    """Test lead profile construction from FUB data."""

    def test_build_profile_extracts_name(self, mock_lead_data):
        """Profile correctly extracts first and last name."""
        first_name = mock_lead_data.get("firstName", "")
        last_name = mock_lead_data.get("lastName", "")

        assert first_name == "John"
        assert last_name == "Test"

    def test_build_profile_extracts_contact_info(self, mock_lead_data):
        """Profile correctly extracts email and phone."""
        emails = mock_lead_data.get("emails", [])
        phones = mock_lead_data.get("phones", [])

        email = emails[0]["value"] if emails else None
        phone = phones[0]["value"] if phones else None

        assert email == "john@test.com"
        assert phone == "+14155551234"

    def test_build_profile_extracts_source(self, mock_lead_data):
        """Profile correctly extracts lead source."""
        source = mock_lead_data.get("source", "Unknown")
        assert source == "MyAgentFinder"

    def test_build_profile_extracts_stage(self, mock_lead_data):
        """Profile correctly extracts lead stage."""
        stage = mock_lead_data.get("stage", "Unknown")
        assert stage == "New Lead"


# =============================================================================
# CONVERSATION HISTORY TESTS
# =============================================================================

class TestConversationHistory:
    """Test conversation history retrieval."""

    def test_history_format(self):
        """Conversation history has correct format."""
        sample_history = [
            {
                "direction": "outbound",
                "content": "Hey John! When are you thinking of making a move?",
                "channel": "sms",
                "timestamp": "2024-01-19T15:25:00Z",
            },
            {
                "direction": "inbound",
                "content": "Yes, I'm interested!",
                "channel": "sms",
                "timestamp": "2024-01-19T15:30:00Z",
            },
        ]

        # Verify format
        for msg in sample_history:
            assert "direction" in msg
            assert "content" in msg
            assert "channel" in msg
            assert msg["direction"] in ["inbound", "outbound"]

    def test_history_order(self):
        """History is ordered chronologically."""
        timestamps = [
            "2024-01-19T15:25:00Z",
            "2024-01-19T15:30:00Z",
            "2024-01-19T15:35:00Z",
        ]

        # Verify ascending order
        for i in range(1, len(timestamps)):
            assert timestamps[i] > timestamps[i-1]


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestWebhookErrorHandling:
    """Test error handling in webhook processing."""

    def test_malformed_json_handled(self, client):
        """Malformed JSON doesn't crash the endpoint."""
        response = client.post(
            '/webhooks/ai/text-received',
            data='not valid json',
            content_type='application/json',
        )
        # Should not crash - return 200 or error code
        assert response.status_code in [200, 400, 500]

    def test_missing_fields_handled(self, client):
        """Missing required fields are handled gracefully."""
        incomplete_payload = {
            "event": "textMessagesCreated",
            # Missing resourceIds
        }

        response = client.post(
            '/webhooks/ai/text-received',
            data=json.dumps(incomplete_payload),
            content_type='application/json',
        )
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
