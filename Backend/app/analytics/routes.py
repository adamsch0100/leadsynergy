"""
Analytics API Routes.

Provides comprehensive analytics for admin and broker dashboards.
"""

from flask import request, jsonify
import logging
from datetime import datetime, timedelta

from app.analytics import analytics_bp
from app.database.supabase_client import SupabaseClientSingleton
from app.models.support_ticket import SupportTicket

logger = logging.getLogger(__name__)


def get_user_id_from_request():
    """Extract user ID from request headers."""
    return request.headers.get('X-User-ID')


def check_admin(user_id: str) -> bool:
    """Check if user is an admin."""
    try:
        supabase = SupabaseClientSingleton.get_instance()
        result = supabase.table('users').select('is_admin').eq('id', user_id).single().execute()
        return result.data.get('is_admin', False) if result.data else False
    except Exception:
        return False


def check_broker(user_id: str) -> bool:
    """Check if user is a broker."""
    try:
        supabase = SupabaseClientSingleton.get_instance()
        result = supabase.table('users').select('user_type').eq('id', user_id).single().execute()
        return result.data.get('user_type') == 'broker' if result.data else False
    except Exception:
        return False


# =============================================================================
# Admin Analytics Endpoints
# =============================================================================

@analytics_bp.route('/admin/overview', methods=['GET'])
def admin_overview():
    """
    Get comprehensive admin dashboard overview.

    Returns user counts, lookup stats, credit totals, revenue, and ticket stats.
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    if not check_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    try:
        supabase = SupabaseClientSingleton.get_instance()

        # Get user counts
        users_result = supabase.table('users').select('id, user_type, created_at').execute()
        users = users_result.data or []

        total_users = len(users)
        brokers = sum(1 for u in users if u.get('user_type') == 'broker')
        agents = sum(1 for u in users if u.get('user_type') == 'agent')

        # Active users in last 30 days (based on lookups)
        thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
        active_result = supabase.table('lookup_history').select('user_id').gte('created_at', thirty_days_ago).execute()
        active_user_ids = set(l.get('user_id') for l in (active_result.data or []))
        active_users_30d = len(active_user_ids)

        # Get lookup stats for this month
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        lookups_result = supabase.table('lookup_history').select('id, success, search_type').gte('created_at', month_start).execute()
        lookups = lookups_result.data or []

        monthly_lookups = len(lookups)
        successful_lookups = sum(1 for l in lookups if l.get('success'))
        lookup_success_rate = round((successful_lookups / monthly_lookups * 100), 1) if monthly_lookups > 0 else 0

        # Get total credits available across all users
        credits_result = supabase.table('users').select(
            'plan_enhancement_credits, plan_criminal_credits, plan_dnc_credits, '
            'bundle_enhancement_credits, bundle_criminal_credits, bundle_dnc_credits'
        ).execute()

        total_credits = 0
        for u in (credits_result.data or []):
            total_credits += (
                (u.get('plan_enhancement_credits') or 0) +
                (u.get('plan_criminal_credits') or 0) +
                (u.get('plan_dnc_credits') or 0) +
                (u.get('bundle_enhancement_credits') or 0) +
                (u.get('bundle_criminal_credits') or 0) +
                (u.get('bundle_dnc_credits') or 0)
            )

        # Get support ticket stats
        tickets_result = supabase.table('support_tickets').select('status, created_at, closed_at').execute()
        tickets = tickets_result.data or []

        open_tickets = sum(1 for t in tickets if t.get('status') == SupportTicket.STATUS_OPEN)
        in_progress_tickets = sum(1 for t in tickets if t.get('status') == SupportTicket.STATUS_IN_PROGRESS)

        # Calculate average resolution time
        resolution_times = []
        for t in tickets:
            if t.get('status') == SupportTicket.STATUS_CLOSED and t.get('closed_at') and t.get('created_at'):
                try:
                    created = datetime.fromisoformat(t['created_at'].replace('Z', '+00:00'))
                    closed = datetime.fromisoformat(t['closed_at'].replace('Z', '+00:00'))
                    resolution_times.append((closed - created).total_seconds() / 3600)
                except Exception:
                    pass

        avg_resolution_hours = round(sum(resolution_times) / len(resolution_times), 1) if resolution_times else 0

        return jsonify({
            "success": True,
            "overview": {
                "total_users": total_users,
                "active_users_30d": active_users_30d,
                "brokers": brokers,
                "agents": agents,
                "monthly_lookups": monthly_lookups,
                "lookup_success_rate": lookup_success_rate,
                "total_credits_available": total_credits,
                "support_tickets": {
                    "open": open_tickets,
                    "in_progress": in_progress_tickets,
                    "avg_resolution_hours": avg_resolution_hours
                }
            }
        })

    except Exception as e:
        logger.error(f"Error getting admin overview: {e}")
        return jsonify({"error": str(e)}), 500


@analytics_bp.route('/admin/revenue', methods=['GET'])
def admin_revenue():
    """
    Get revenue breakdown.

    Query params:
        - period: month, quarter, year (default: month)
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    if not check_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    try:
        supabase = SupabaseClientSingleton.get_instance()
        period = request.args.get('period', 'month')

        # Calculate date range
        now = datetime.utcnow()
        if period == 'year':
            start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == 'quarter':
            quarter_month = ((now.month - 1) // 3) * 3 + 1
            start_date = now.replace(month=quarter_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:  # month
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Get credit transactions (bundle purchases)
        transactions_result = supabase.table('credit_transactions').select(
            'amount, transaction_type, created_at'
        ).gte('created_at', start_date.isoformat()).execute()

        transactions = transactions_result.data or []

        bundle_revenue = sum(
            (t.get('amount') or 0) / 100  # Convert cents to dollars
            for t in transactions
            if t.get('transaction_type') == 'purchase'
        )

        # For subscription revenue, we'd need to query Stripe or a subscriptions table
        # This is a placeholder - in production, integrate with Stripe API
        subscription_revenue = 0

        # Get revenue by day for chart
        revenue_by_day = {}
        for t in transactions:
            if t.get('transaction_type') == 'purchase' and t.get('created_at'):
                day = t['created_at'][:10]
                revenue_by_day[day] = revenue_by_day.get(day, 0) + ((t.get('amount') or 0) / 100)

        revenue_chart = [
            {"date": day, "revenue": amount}
            for day, amount in sorted(revenue_by_day.items())
        ]

        return jsonify({
            "success": True,
            "revenue": {
                "period": period,
                "start_date": start_date.isoformat(),
                "subscriptions": round(subscription_revenue, 2),
                "bundles": round(bundle_revenue, 2),
                "total": round(subscription_revenue + bundle_revenue, 2),
                "by_day": revenue_chart
            }
        })

    except Exception as e:
        logger.error(f"Error getting admin revenue: {e}")
        return jsonify({"error": str(e)}), 500


@analytics_bp.route('/admin/lookups', methods=['GET'])
def admin_lookups():
    """
    Get lookup statistics.

    Query params:
        - days: Number of days to analyze (default: 30, max: 90)
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    if not check_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    try:
        supabase = SupabaseClientSingleton.get_instance()
        days = min(int(request.args.get('days', 30)), 90)

        start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

        lookups_result = supabase.table('lookup_history').select(
            'id, search_type, success, created_at'
        ).gte('created_at', start_date).execute()

        lookups = lookups_result.data or []

        # Aggregate by type
        by_type = {}
        for l in lookups:
            t = l.get('search_type', 'unknown')
            if t not in by_type:
                by_type[t] = {'total': 0, 'successful': 0}
            by_type[t]['total'] += 1
            if l.get('success'):
                by_type[t]['successful'] += 1

        # Calculate success rates
        type_stats = []
        for t, stats in by_type.items():
            type_stats.append({
                "type": t,
                "total": stats['total'],
                "successful": stats['successful'],
                "success_rate": round(stats['successful'] / stats['total'] * 100, 1) if stats['total'] > 0 else 0
            })

        # Aggregate by day
        by_day = {}
        for l in lookups:
            if l.get('created_at'):
                day = l['created_at'][:10]
                if day not in by_day:
                    by_day[day] = {'total': 0, 'successful': 0}
                by_day[day]['total'] += 1
                if l.get('success'):
                    by_day[day]['successful'] += 1

        daily_stats = [
            {"date": day, "total": stats['total'], "successful": stats['successful']}
            for day, stats in sorted(by_day.items())
        ]

        total = len(lookups)
        successful = sum(1 for l in lookups if l.get('success'))
        daily_avg = round(total / days, 1) if days > 0 else 0

        return jsonify({
            "success": True,
            "lookups": {
                "period_days": days,
                "total": total,
                "successful": successful,
                "success_rate": round(successful / total * 100, 1) if total > 0 else 0,
                "daily_average": daily_avg,
                "by_type": type_stats,
                "by_day": daily_stats
            }
        })

    except Exception as e:
        logger.error(f"Error getting lookup stats: {e}")
        return jsonify({"error": str(e)}), 500


@analytics_bp.route('/admin/users', methods=['GET'])
def admin_users():
    """
    Get user growth and activity metrics.

    Query params:
        - days: Number of days to analyze (default: 30)
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    if not check_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    try:
        supabase = SupabaseClientSingleton.get_instance()
        days = int(request.args.get('days', 30))

        start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

        # Get all users
        users_result = supabase.table('users').select(
            'id, user_type, created_at, email, name'
        ).execute()
        users = users_result.data or []

        # New users in period
        new_users = [u for u in users if u.get('created_at', '') >= start_date]

        # User growth by day
        by_day = {}
        for u in new_users:
            if u.get('created_at'):
                day = u['created_at'][:10]
                by_day[day] = by_day.get(day, 0) + 1

        growth_chart = [
            {"date": day, "new_users": count}
            for day, count in sorted(by_day.items())
        ]

        # Get active users (made lookups in period)
        lookups_result = supabase.table('lookup_history').select(
            'user_id'
        ).gte('created_at', start_date).execute()

        active_user_ids = set(l.get('user_id') for l in (lookups_result.data or []))

        # Top users by lookups
        user_lookup_counts = {}
        for l in (lookups_result.data or []):
            uid = l.get('user_id')
            user_lookup_counts[uid] = user_lookup_counts.get(uid, 0) + 1

        # Get user details for top users
        top_users = sorted(user_lookup_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        top_user_ids = [u[0] for u in top_users]

        top_users_result = supabase.table('users').select(
            'id, name, email, user_type'
        ).in_('id', top_user_ids).execute()

        user_map = {u['id']: u for u in (top_users_result.data or [])}

        top_users_list = []
        for uid, count in top_users:
            if uid in user_map:
                user = user_map[uid]
                top_users_list.append({
                    "id": uid,
                    "name": user.get('name', 'Unknown'),
                    "email": user.get('email', ''),
                    "user_type": user.get('user_type', 'agent'),
                    "lookup_count": count
                })

        return jsonify({
            "success": True,
            "users": {
                "period_days": days,
                "total_users": len(users),
                "new_users_in_period": len(new_users),
                "active_users_in_period": len(active_user_ids),
                "by_type": {
                    "brokers": sum(1 for u in users if u.get('user_type') == 'broker'),
                    "agents": sum(1 for u in users if u.get('user_type') == 'agent')
                },
                "growth_by_day": growth_chart,
                "top_users": top_users_list
            }
        })

    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Broker Analytics Endpoints
# =============================================================================

@analytics_bp.route('/broker/credits', methods=['GET'])
def broker_credits():
    """
    Get credit breakdown for a broker's team.
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    if not check_broker(user_id):
        return jsonify({"error": "Broker access required"}), 403

    try:
        supabase = SupabaseClientSingleton.get_instance()

        # Get broker's own credits
        broker_result = supabase.table('users').select(
            'plan_enhancement_credits, plan_criminal_credits, plan_dnc_credits, '
            'bundle_enhancement_credits, bundle_criminal_credits, bundle_dnc_credits'
        ).eq('id', user_id).single().execute()

        broker = broker_result.data or {}

        # Get team agents
        agents_result = supabase.table('users').select(
            'id, allocated_enhancement_credits, allocated_criminal_credits, allocated_dnc_credits'
        ).eq('broker_id', user_id).execute()

        agents = agents_result.data or []

        # Calculate totals
        total_enhancement = (
            (broker.get('plan_enhancement_credits') or 0) +
            (broker.get('bundle_enhancement_credits') or 0)
        )
        total_criminal = (
            (broker.get('plan_criminal_credits') or 0) +
            (broker.get('bundle_criminal_credits') or 0)
        )
        total_dnc = (
            (broker.get('plan_dnc_credits') or 0) +
            (broker.get('bundle_dnc_credits') or 0)
        )

        allocated_enhancement = sum(a.get('allocated_enhancement_credits') or 0 for a in agents)
        allocated_criminal = sum(a.get('allocated_criminal_credits') or 0 for a in agents)
        allocated_dnc = sum(a.get('allocated_dnc_credits') or 0 for a in agents)

        # Get usage this month
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

        agent_ids = [a['id'] for a in agents] + [user_id]
        usage_result = supabase.table('credit_transactions').select(
            'enhancement_credits, criminal_credits, dnc_credits, created_at'
        ).in_('user_id', agent_ids).eq('transaction_type', 'usage').gte('created_at', month_start).execute()

        usage = usage_result.data or []
        usage_this_month = sum(
            (abs(u.get('enhancement_credits') or 0) +
             abs(u.get('criminal_credits') or 0) +
             abs(u.get('dnc_credits') or 0))
            for u in usage
        )

        # Usage by day for chart
        usage_by_day = {}
        for u in usage:
            if u.get('created_at'):
                day = u['created_at'][:10]
                if day not in usage_by_day:
                    usage_by_day[day] = {'enhancement': 0, 'criminal': 0, 'dnc': 0}
                usage_by_day[day]['enhancement'] += abs(u.get('enhancement_credits') or 0)
                usage_by_day[day]['criminal'] += abs(u.get('criminal_credits') or 0)
                usage_by_day[day]['dnc'] += abs(u.get('dnc_credits') or 0)

        usage_chart = [
            {
                "date": day,
                "enhancement": stats['enhancement'],
                "criminal": stats['criminal'],
                "dnc": stats['dnc']
            }
            for day, stats in sorted(usage_by_day.items())
        ]

        return jsonify({
            "success": True,
            "credits": {
                "enhancement": {
                    "total": total_enhancement,
                    "allocated": allocated_enhancement,
                    "available": total_enhancement - allocated_enhancement
                },
                "criminal": {
                    "total": total_criminal,
                    "allocated": allocated_criminal,
                    "available": total_criminal - allocated_criminal
                },
                "dnc": {
                    "total": total_dnc,
                    "allocated": allocated_dnc,
                    "available": total_dnc - allocated_dnc
                },
                "usage_this_month": usage_this_month,
                "usage_by_day": usage_chart
            }
        })

    except Exception as e:
        logger.error(f"Error getting broker credits: {e}")
        return jsonify({"error": str(e)}), 500


@analytics_bp.route('/broker/team', methods=['GET'])
def broker_team():
    """
    Get team member performance stats.
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    if not check_broker(user_id):
        return jsonify({"error": "Broker access required"}), 403

    try:
        supabase = SupabaseClientSingleton.get_instance()

        # Get team agents
        agents_result = supabase.table('users').select(
            'id, name, email, created_at, '
            'allocated_enhancement_credits, allocated_criminal_credits, allocated_dnc_credits'
        ).eq('broker_id', user_id).execute()

        agents = agents_result.data or []
        agent_ids = [a['id'] for a in agents]

        if not agent_ids:
            return jsonify({
                "success": True,
                "team": {
                    "total_agents": 0,
                    "agents": []
                }
            })

        # Get lookup counts per agent (last 30 days)
        thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
        lookups_result = supabase.table('lookup_history').select(
            'user_id, success'
        ).in_('user_id', agent_ids).gte('created_at', thirty_days_ago).execute()

        lookups = lookups_result.data or []

        agent_lookups = {}
        for l in lookups:
            uid = l.get('user_id')
            if uid not in agent_lookups:
                agent_lookups[uid] = {'total': 0, 'successful': 0}
            agent_lookups[uid]['total'] += 1
            if l.get('success'):
                agent_lookups[uid]['successful'] += 1

        # Build agent list
        agent_list = []
        for a in agents:
            aid = a['id']
            lookup_stats = agent_lookups.get(aid, {'total': 0, 'successful': 0})

            agent_list.append({
                "id": aid,
                "name": a.get('name', 'Unknown'),
                "email": a.get('email', ''),
                "joined": a.get('created_at'),
                "credits": {
                    "enhancement": a.get('allocated_enhancement_credits') or 0,
                    "criminal": a.get('allocated_criminal_credits') or 0,
                    "dnc": a.get('allocated_dnc_credits') or 0
                },
                "lookups_30d": lookup_stats['total'],
                "success_rate": round(
                    lookup_stats['successful'] / lookup_stats['total'] * 100, 1
                ) if lookup_stats['total'] > 0 else 0
            })

        # Sort by lookups descending
        agent_list.sort(key=lambda x: x['lookups_30d'], reverse=True)

        return jsonify({
            "success": True,
            "team": {
                "total_agents": len(agents),
                "agents": agent_list
            }
        })

    except Exception as e:
        logger.error(f"Error getting broker team: {e}")
        return jsonify({"error": str(e)}), 500


@analytics_bp.route('/broker/usage', methods=['GET'])
def broker_usage():
    """
    Get detailed usage statistics for the broker's team.

    Query params:
        - days: Number of days (default: 30, max: 90)
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    if not check_broker(user_id):
        return jsonify({"error": "Broker access required"}), 403

    try:
        supabase = SupabaseClientSingleton.get_instance()
        days = min(int(request.args.get('days', 30)), 90)

        # Get team agents
        agents_result = supabase.table('users').select('id').eq('broker_id', user_id).execute()
        agents = agents_result.data or []
        agent_ids = [a['id'] for a in agents] + [user_id]

        start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

        # Get lookups
        lookups_result = supabase.table('lookup_history').select(
            'search_type, success, created_at'
        ).in_('user_id', agent_ids).gte('created_at', start_date).execute()

        lookups = lookups_result.data or []

        # Aggregate by type
        by_type = {}
        for l in lookups:
            t = l.get('search_type', 'unknown')
            if t not in by_type:
                by_type[t] = {'total': 0, 'successful': 0}
            by_type[t]['total'] += 1
            if l.get('success'):
                by_type[t]['successful'] += 1

        type_breakdown = [
            {
                "type": t,
                "total": stats['total'],
                "successful": stats['successful']
            }
            for t, stats in by_type.items()
        ]

        # Daily usage
        by_day = {}
        for l in lookups:
            if l.get('created_at'):
                day = l['created_at'][:10]
                if day not in by_day:
                    by_day[day] = 0
                by_day[day] += 1

        daily_chart = [
            {"date": day, "lookups": count}
            for day, count in sorted(by_day.items())
        ]

        total = len(lookups)
        successful = sum(1 for l in lookups if l.get('success'))

        return jsonify({
            "success": True,
            "usage": {
                "period_days": days,
                "total_lookups": total,
                "successful": successful,
                "success_rate": round(successful / total * 100, 1) if total > 0 else 0,
                "daily_average": round(total / days, 1) if days > 0 else 0,
                "by_type": type_breakdown,
                "by_day": daily_chart
            }
        })

    except Exception as e:
        logger.error(f"Error getting broker usage: {e}")
        return jsonify({"error": str(e)}), 500
