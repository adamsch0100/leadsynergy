# -*- coding: utf-8 -*-
"""
Round 4 API Endpoint Tests (~10 tests).

Tests Flask API endpoints for AI settings and monitoring.

Run with: pytest tests/test_api_round4.py -v
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

from app.ai_agent.settings_service import AIAgentSettings


# =============================================================================
# HELPERS
# =============================================================================

def make_table_mock(data=None):
    """Create a chained-query mock table returning given data."""
    mock_table = MagicMock()
    for method in [
        'select', 'eq', 'neq', 'lt', 'gt', 'gte', 'lte',
        'limit', 'order', 'is_', 'in_', 'not_',
    ]:
        getattr(mock_table, method).return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=data or [])
    mock_table.upsert.return_value.execute.return_value = MagicMock(data=[{"id": "test"}])
    mock_table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "test"}])
    mock_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "test"}])
    return mock_table


def make_mock_supabase(data=None):
    """Create a mock supabase client."""
    mock = MagicMock()
    mock_table = make_table_mock(data)
    mock.table = MagicMock(return_value=mock_table)
    return mock


# =============================================================================
# SETTINGS API TESTS
# =============================================================================

@pytest.mark.round4
@pytest.mark.api
class TestSettingsAPI:
    """Tests for GET/PUT /api/ai-settings endpoints."""

    def test_get_returns_all_new_fields(self):
        """GET /api/ai-settings should return Round 4 fields."""
        from flask import Flask
        from app.api.ai_settings import ai_settings_bp

        app = Flask(__name__)
        app.config['TESTING'] = True
        app.register_blueprint(ai_settings_bp, url_prefix='/api/ai-settings')

        settings = AIAgentSettings(
            sequence_sms_enabled=True,
            day_0_aggression="moderate",
            nba_hot_lead_scan_interval_minutes=10,
            llm_provider="anthropic",
            llm_model="claude-sonnet-4-20250514",
            instant_response_enabled=True,
        )

        with patch('app.api.ai_settings.get_supabase_client') as mock_get_sb:
            with patch('app.api.ai_settings.get_settings_service') as mock_get_svc:
                mock_service = MagicMock()
                mock_service.get_settings = AsyncMock(return_value=settings)
                mock_get_svc.return_value = mock_service

                with app.test_client() as client:
                    resp = client.get(
                        '/api/ai-settings',
                        headers={'X-User-ID': 'test-user'},
                    )
                    assert resp.status_code == 200
                    data = resp.get_json()
                    assert data['success'] is True
                    s = data['settings']
                    assert s['sequence_sms_enabled'] is True
                    assert s['day_0_aggression'] == "moderate"
                    assert s['nba_hot_lead_scan_interval_minutes'] == 10
                    assert s['llm_provider'] == "anthropic"
                    assert s['instant_response_enabled'] is True

    def test_put_saves_sequence_fields(self):
        """PUT /api/ai-settings with sequence fields persists them."""
        from flask import Flask
        from app.api.ai_settings import ai_settings_bp

        app = Flask(__name__)
        app.config['TESTING'] = True
        app.register_blueprint(ai_settings_bp, url_prefix='/api/ai-settings')

        current_settings = AIAgentSettings()

        with patch('app.api.ai_settings.get_supabase_client') as mock_get_sb:
            with patch('app.api.ai_settings.get_settings_service') as mock_get_svc:
                mock_service = MagicMock()
                mock_service.get_settings = AsyncMock(return_value=current_settings)
                mock_service.save_settings = AsyncMock(return_value=True)
                mock_get_svc.return_value = mock_service

                with app.test_client() as client:
                    resp = client.put(
                        '/api/ai-settings',
                        json={
                            'user_id': 'test-user',
                            'sequence_sms_enabled': True,
                            'sequence_email_enabled': False,
                            'day_0_aggression': 'moderate',
                        },
                    )
                    assert resp.status_code == 200
                    data = resp.get_json()
                    assert data['success'] is True

    def test_put_saves_timing_fields(self):
        """PUT with response_delay_min_seconds -> persisted."""
        from flask import Flask
        from app.api.ai_settings import ai_settings_bp

        app = Flask(__name__)
        app.config['TESTING'] = True
        app.register_blueprint(ai_settings_bp, url_prefix='/api/ai-settings')

        current_settings = AIAgentSettings()

        with patch('app.api.ai_settings.get_supabase_client'):
            with patch('app.api.ai_settings.get_settings_service') as mock_get_svc:
                mock_service = MagicMock()
                mock_service.get_settings = AsyncMock(return_value=current_settings)
                mock_service.save_settings = AsyncMock(return_value=True)
                mock_get_svc.return_value = mock_service

                with app.test_client() as client:
                    resp = client.put(
                        '/api/ai-settings',
                        json={
                            'user_id': 'test-user',
                            'response_delay_min_seconds': 10,
                            'response_delay_max_seconds': 60,
                            'first_message_delay_min': 5,
                        },
                    )
                    assert resp.status_code == 200

    def test_put_validates_day_0_aggression(self):
        """PUT with day_0_aggression='invalid' -> ignored (not saved)."""
        from flask import Flask
        from app.api.ai_settings import ai_settings_bp

        app = Flask(__name__)
        app.config['TESTING'] = True
        app.register_blueprint(ai_settings_bp, url_prefix='/api/ai-settings')

        current_settings = AIAgentSettings(day_0_aggression="aggressive")

        with patch('app.api.ai_settings.get_supabase_client'):
            with patch('app.api.ai_settings.get_settings_service') as mock_get_svc:
                mock_service = MagicMock()
                mock_service.get_settings = AsyncMock(return_value=current_settings)
                mock_service.save_settings = AsyncMock(return_value=True)
                mock_get_svc.return_value = mock_service

                with app.test_client() as client:
                    resp = client.put(
                        '/api/ai-settings',
                        json={
                            'user_id': 'test-user',
                            'day_0_aggression': 'invalid_value',
                        },
                    )
                    assert resp.status_code == 200
                    # The setting should remain as "aggressive" (invalid ignored)
                    assert current_settings.day_0_aggression == "aggressive"

    def test_put_requires_user_id(self):
        """PUT without user_id or X-User-ID -> 400."""
        from flask import Flask
        from app.api.ai_settings import ai_settings_bp

        app = Flask(__name__)
        app.config['TESTING'] = True
        app.register_blueprint(ai_settings_bp, url_prefix='/api/ai-settings')

        with app.test_client() as client:
            resp = client.put(
                '/api/ai-settings',
                json={'agent_name': 'Bot'},
            )
            assert resp.status_code == 400
            data = resp.get_json()
            assert 'error' in data


# =============================================================================
# MONITORING API TESTS
# =============================================================================

@pytest.mark.round4
@pytest.mark.api
class TestMonitoringAPI:
    """Tests for /api/ai-monitoring endpoints."""

    def test_stale_handoffs_endpoint(self):
        """GET /api/ai-monitoring/stale-handoffs returns success."""
        from flask import Flask
        from app.api.ai_monitoring import ai_monitoring_bp

        app = Flask(__name__)
        app.config['TESTING'] = True
        app.register_blueprint(ai_monitoring_bp, url_prefix='/api/ai-monitoring')

        stale_time = (datetime.utcnow() - timedelta(hours=50)).isoformat() + "Z"
        mock_sb = make_mock_supabase(data=[{
            "fub_person_id": 3277,
            "state": "handed_off",
            "handoff_reason": "hot_qualified_lead",
            "assigned_agent_id": "agent-1",
            "last_ai_message_at": stale_time,
            "last_human_message_at": None,
            "updated_at": stale_time,
        }])

        with patch('app.api.ai_monitoring.get_supabase_client', return_value=mock_sb):
            with app.test_client() as client:
                resp = client.get('/api/ai-monitoring/stale-handoffs')
                assert resp.status_code == 200
                data = resp.get_json()
                assert data['success'] is True
                assert 'stale_handoffs' in data

    def test_deferred_followups_endpoint(self):
        """GET /api/ai-monitoring/deferred-followups returns scheduled items."""
        from flask import Flask
        from app.api.ai_monitoring import ai_monitoring_bp

        app = Flask(__name__)
        app.config['TESTING'] = True
        app.register_blueprint(ai_monitoring_bp, url_prefix='/api/ai-monitoring')

        future_date = (datetime.utcnow() + timedelta(days=14)).isoformat()
        mock_sb = make_mock_supabase(data=[{
            "id": "followup-1",
            "fub_person_id": 3277,
            "scheduled_at": future_date,
            "channel": "sms",
            "message_type": "deferred_followup",
            "status": "pending",
            "sequence_id": None,
        }])

        with patch('app.api.ai_monitoring.get_supabase_client', return_value=mock_sb):
            with app.test_client() as client:
                resp = client.get('/api/ai-monitoring/deferred-followups')
                assert resp.status_code == 200
                data = resp.get_json()
                assert data['success'] is True
                assert 'deferred_followups' in data

    def test_nba_recommendations_endpoint(self):
        """GET /api/ai-monitoring/nba-recommendations returns recommendations."""
        from flask import Flask
        from app.api.ai_monitoring import ai_monitoring_bp

        app = Flask(__name__)
        app.config['TESTING'] = True
        app.register_blueprint(ai_monitoring_bp, url_prefix='/api/ai-monitoring')

        mock_result = {
            'recommendations_count': 2,
            'recommendations': [
                {'fub_person_id': 1, 'action_type': 'first_contact_sms', 'priority_score': 95},
                {'fub_person_id': 2, 'action_type': 'followup_sms', 'priority_score': 70},
            ],
            'scan_time': '0.5s',
        }

        with patch('app.api.ai_monitoring.run_async', return_value=mock_result):
            with app.test_client() as client:
                resp = client.get('/api/ai-monitoring/nba-recommendations')
                assert resp.status_code == 200
                data = resp.get_json()
                assert data['success'] is True
                assert data['recommendations_count'] == 2

    def test_stale_handoffs_empty_when_none(self):
        """No stale handoffs -> returns empty list."""
        from flask import Flask
        from app.api.ai_monitoring import ai_monitoring_bp

        app = Flask(__name__)
        app.config['TESTING'] = True
        app.register_blueprint(ai_monitoring_bp, url_prefix='/api/ai-monitoring')

        mock_sb = make_mock_supabase(data=[])

        with patch('app.api.ai_monitoring.get_supabase_client', return_value=mock_sb):
            with app.test_client() as client:
                resp = client.get('/api/ai-monitoring/stale-handoffs')
                assert resp.status_code == 200
                data = resp.get_json()
                assert data['success'] is True
                assert data['stale_handoffs'] == []
                assert data['count'] == 0

    def test_settings_get_requires_user_id(self):
        """GET /api/ai-settings without user_id -> 400."""
        from flask import Flask
        from app.api.ai_settings import ai_settings_bp

        app = Flask(__name__)
        app.config['TESTING'] = True
        app.register_blueprint(ai_settings_bp, url_prefix='/api/ai-settings')

        with app.test_client() as client:
            resp = client.get('/api/ai-settings')
            assert resp.status_code == 400
            data = resp.get_json()
            assert 'error' in data
