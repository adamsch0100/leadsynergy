"""
Analytics Module.
Provides dashboard analytics for admin and broker users.

Admin endpoints:
- GET /api/analytics/admin/overview - Dashboard stats
- GET /api/analytics/admin/revenue - Revenue breakdown
- GET /api/analytics/admin/lookups - Lookup statistics
- GET /api/analytics/admin/users - User metrics

Broker endpoints:
- GET /api/analytics/broker/credits - Team credit breakdown
- GET /api/analytics/broker/team - Agent performance
- GET /api/analytics/broker/usage - Usage over time

AI Analytics (separate blueprint at /api/ai-analytics):
- GET /api/ai-analytics/summary - AI metrics summary
- GET /api/ai-analytics/funnel - Conversion funnel
- GET /api/ai-analytics/daily - Daily metrics
- GET /api/ai-analytics/agents - Per-agent performance
- GET /api/ai-analytics/intents - Intent distribution
- GET /api/ai-analytics/ab-tests - A/B test results
- GET /api/ai-analytics/dashboard - All dashboard data
"""

from flask import Blueprint

analytics_bp = Blueprint('analytics', __name__)

# Import AI analytics service components
from app.analytics.ai_analytics_service import (
    AIAnalyticsService,
    get_analytics_service,
    AnalyticsPeriod,
    MetricsSummary,
    ConversionFunnel,
    AgentPerformance,
    ABTestResult,
)

from app.analytics import routes

__all__ = [
    "analytics_bp",
    "AIAnalyticsService",
    "get_analytics_service",
    "AnalyticsPeriod",
    "MetricsSummary",
    "ConversionFunnel",
    "AgentPerformance",
    "ABTestResult",
]
