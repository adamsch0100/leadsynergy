"""
AI Analytics API endpoints.

Provides REST API for AI agent performance metrics:
- GET /api/ai-analytics/summary - Get metrics summary
- GET /api/ai-analytics/funnel - Get conversion funnel
- GET /api/ai-analytics/daily - Get daily metrics
- GET /api/ai-analytics/agents - Get per-agent performance
- GET /api/ai-analytics/intents - Get intent distribution
- GET /api/ai-analytics/ab-tests - Get A/B test results
"""

from flask import Blueprint, request, jsonify
import asyncio
import logging

from app.analytics.ai_analytics_service import (
    AIAnalyticsService,
    get_analytics_service,
    AnalyticsPeriod,
)
from app.database import get_supabase_client

logger = logging.getLogger(__name__)

ai_analytics_bp = Blueprint('ai_analytics', __name__)


def run_async(coro):
    """Run async function in sync Flask context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def get_user_info(request_obj):
    """Extract user and organization info from request."""
    user_id = request_obj.headers.get('X-User-ID')
    org_id = request_obj.headers.get('X-Organization-ID')
    return user_id, org_id


def parse_period(period_str: str) -> AnalyticsPeriod:
    """Parse period string to enum."""
    period_map = {
        'today': AnalyticsPeriod.TODAY,
        'yesterday': AnalyticsPeriod.YESTERDAY,
        '7d': AnalyticsPeriod.LAST_7_DAYS,
        '30d': AnalyticsPeriod.LAST_30_DAYS,
        '90d': AnalyticsPeriod.LAST_90_DAYS,
        'month': AnalyticsPeriod.THIS_MONTH,
        'quarter': AnalyticsPeriod.THIS_QUARTER,
        'year': AnalyticsPeriod.THIS_YEAR,
    }
    return period_map.get(period_str, AnalyticsPeriod.LAST_30_DAYS)


@ai_analytics_bp.route('/summary', methods=['GET'])
def get_metrics_summary():
    """
    Get comprehensive AI metrics summary.

    Query params:
        period: Time period (today, yesterday, 7d, 30d, 90d, month, quarter, year)
        user_id: Optional user ID filter
        organization_id: Optional org ID filter

    Returns:
        JSON object with metrics summary
    """
    user_id, org_id = get_user_info(request)

    # Allow query param overrides
    filter_user_id = request.args.get('user_id') or user_id
    filter_org_id = request.args.get('organization_id') or org_id
    period_str = request.args.get('period', '30d')

    if not filter_user_id and not filter_org_id:
        return jsonify({"error": "User ID or Organization ID is required"}), 400

    try:
        supabase = get_supabase_client()
        service = get_analytics_service(supabase)
        period = parse_period(period_str)

        summary = run_async(service.get_metrics_summary(
            organization_id=filter_org_id,
            user_id=filter_user_id,
            period=period,
        ))

        return jsonify({
            "success": True,
            "summary": summary.to_dict()
        })

    except Exception as e:
        logger.error(f"Error getting AI metrics summary: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@ai_analytics_bp.route('/funnel', methods=['GET'])
def get_conversion_funnel():
    """
    Get lead conversion funnel data.

    Query params:
        period: Time period
        organization_id: Optional org ID filter

    Returns:
        JSON object with funnel stages and conversion rates
    """
    user_id, org_id = get_user_info(request)
    filter_org_id = request.args.get('organization_id') or org_id
    period_str = request.args.get('period', '30d')

    if not filter_org_id:
        return jsonify({"error": "Organization ID is required"}), 400

    try:
        supabase = get_supabase_client()
        service = get_analytics_service(supabase)
        period = parse_period(period_str)

        funnel = run_async(service.get_conversion_funnel(
            organization_id=filter_org_id,
            period=period,
        ))

        return jsonify({
            "success": True,
            "funnel": funnel.to_dict()
        })

    except Exception as e:
        logger.error(f"Error getting conversion funnel: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@ai_analytics_bp.route('/daily', methods=['GET'])
def get_daily_metrics():
    """
    Get metrics broken down by day for charts.

    Query params:
        period: Time period
        organization_id: Optional org ID filter

    Returns:
        JSON array of daily metrics
    """
    user_id, org_id = get_user_info(request)
    filter_org_id = request.args.get('organization_id') or org_id
    period_str = request.args.get('period', '30d')

    if not filter_org_id:
        return jsonify({"error": "Organization ID is required"}), 400

    try:
        supabase = get_supabase_client()
        service = get_analytics_service(supabase)
        period = parse_period(period_str)

        daily = run_async(service.get_metrics_by_day(
            organization_id=filter_org_id,
            period=period,
        ))

        return jsonify({
            "success": True,
            "daily": daily
        })

    except Exception as e:
        logger.error(f"Error getting daily metrics: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@ai_analytics_bp.route('/agents', methods=['GET'])
def get_agent_performance():
    """
    Get performance metrics per agent.

    Query params:
        organization_id: Required org ID
        period: Time period

    Returns:
        JSON array of agent performance metrics
    """
    user_id, org_id = get_user_info(request)
    filter_org_id = request.args.get('organization_id') or org_id
    period_str = request.args.get('period', '30d')

    if not filter_org_id:
        return jsonify({"error": "Organization ID is required"}), 400

    try:
        supabase = get_supabase_client()
        service = get_analytics_service(supabase)
        period = parse_period(period_str)

        agents = run_async(service.get_agent_performance(
            organization_id=filter_org_id,
            period=period,
        ))

        return jsonify({
            "success": True,
            "agents": [a.to_dict() for a in agents]
        })

    except Exception as e:
        logger.error(f"Error getting agent performance: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@ai_analytics_bp.route('/intents', methods=['GET'])
def get_intent_distribution():
    """
    Get distribution of detected intents.

    Query params:
        organization_id: Optional org ID filter
        period: Time period

    Returns:
        JSON object with intent -> count mapping
    """
    user_id, org_id = get_user_info(request)
    filter_org_id = request.args.get('organization_id') or org_id
    period_str = request.args.get('period', '30d')

    try:
        supabase = get_supabase_client()
        service = get_analytics_service(supabase)
        period = parse_period(period_str)

        distribution = run_async(service.get_intent_distribution(
            organization_id=filter_org_id,
            period=period,
        ))

        # Sort by count descending
        sorted_dist = dict(sorted(
            distribution.items(),
            key=lambda x: x[1],
            reverse=True
        ))

        return jsonify({
            "success": True,
            "intents": sorted_dist,
            "total": sum(distribution.values())
        })

    except Exception as e:
        logger.error(f"Error getting intent distribution: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@ai_analytics_bp.route('/ab-tests', methods=['GET'])
def get_ab_test_results():
    """
    Get A/B test results for template variants.

    Query params:
        organization_id: Optional org ID filter
        template_category: Optional category filter

    Returns:
        JSON array of A/B test results
    """
    user_id, org_id = get_user_info(request)
    filter_org_id = request.args.get('organization_id') or org_id
    template_category = request.args.get('template_category')

    try:
        supabase = get_supabase_client()
        service = get_analytics_service(supabase)

        results = run_async(service.get_ab_test_results(
            organization_id=filter_org_id,
            template_category=template_category,
        ))

        return jsonify({
            "success": True,
            "ab_tests": [r.to_dict() for r in results]
        })

    except Exception as e:
        logger.error(f"Error getting A/B test results: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@ai_analytics_bp.route('/dashboard', methods=['GET'])
def get_dashboard_data():
    """
    Get all dashboard data in a single call (for efficiency).

    Query params:
        organization_id: Optional org ID
        user_id: Optional user ID (alternative to org_id)
        period: Time period

    Returns:
        JSON object with all dashboard data
    """
    user_id, org_id = get_user_info(request)
    filter_user_id = request.args.get('user_id') or user_id
    filter_org_id = request.args.get('organization_id') or org_id
    period_str = request.args.get('period', '30d')

    if not filter_user_id and not filter_org_id:
        return jsonify({"error": "User ID or Organization ID is required"}), 400

    try:
        supabase = get_supabase_client()
        service = get_analytics_service(supabase)
        period = parse_period(period_str)

        # Get all data in parallel using asyncio.gather would be ideal
        # but for simplicity, we'll call them sequentially
        summary = run_async(service.get_metrics_summary(
            organization_id=filter_org_id,
            user_id=filter_user_id,
            period=period,
        ))

        funnel = run_async(service.get_conversion_funnel(
            organization_id=filter_org_id,
            user_id=filter_user_id,
            period=period,
        ))

        daily = run_async(service.get_metrics_by_day(
            organization_id=filter_org_id,
            user_id=filter_user_id,
            period=period,
        ))

        intents = run_async(service.get_intent_distribution(
            organization_id=filter_org_id,
            period=period,
        ))

        return jsonify({
            "success": True,
            "summary": summary.to_dict() if summary else {},
            "funnel": funnel.to_dict() if funnel else {},
            "daily_metrics": daily or [],
            "intents": [
                {"intent": k, "count": v, "percentage": (v / max(sum(intents.values()), 1)) * 100}
                for k, v in sorted(intents.items(), key=lambda x: x[1], reverse=True)[:10]
            ] if intents else [],
            "ab_tests": [],  # TODO: Add A/B test results
            "period": period_str,
        })

    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
