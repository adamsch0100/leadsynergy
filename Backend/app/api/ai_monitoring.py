"""
AI Monitoring API endpoints.

Provides REST API for AI agent monitoring dashboard:
- GET /api/ai-monitoring/activity-feed - Get recent AI activity
- GET /api/ai-monitoring/lead/<person_id>/details - Get lead AI monitoring data
- GET /api/ai-monitoring/lead/<person_id>/conversation - Get conversation history
- GET /api/ai-monitoring/review-queue - Get leads requiring review
- POST /api/ai-monitoring/lead/<person_id>/action - Perform quick actions
- GET /api/ai-monitoring/pending-notes - Get pending @update notes
- POST /api/ai-monitoring/notes/<note_id>/approve - Approve a note
- POST /api/ai-monitoring/notes/<note_id>/dismiss - Dismiss a note
- POST /api/ai-monitoring/notes/bulk-approve - Bulk approve notes
- GET /api/ai-monitoring/stale-handoffs - Get leads with stale handoffs
- GET /api/ai-monitoring/deferred-followups - Get deferred follow-up schedule
- GET /api/ai-monitoring/nba-recommendations - Get NBA scanner results
"""

from flask import Blueprint, request, jsonify
import asyncio
import logging
from typing import Optional

from app.database import get_supabase_client
from app.ai_agent.note_service import get_note_service, AIUpdateNoteService
from app.ai_agent.lead_ai_settings_service import LeadAISettingsService

logger = logging.getLogger(__name__)

ai_monitoring_bp = Blueprint('ai_monitoring', __name__)


def run_async(coro):
    """Run async function in sync Flask context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def get_user_email(request_obj) -> Optional[str]:
    """Extract user email from request headers."""
    return request_obj.headers.get('X-User-Email') or request_obj.headers.get('X-User-ID')


# ==================== Activity Feed ====================

@ai_monitoring_bp.route('/activity-feed', methods=['GET'])
def get_activity_feed():
    """
    Get recent AI activity across all leads.

    Query params:
        limit: Max activities to return (default 50)
        person_id: Optional filter by person

    Returns:
        JSON array of activity events
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        person_id = request.args.get('person_id', type=int)

        note_service = get_note_service()
        activities = run_async(note_service.get_activity_feed(limit=limit, person_id=person_id))

        # Enrich activities with lead names (if we have them cached)
        # For now, just return the raw activities
        return jsonify({
            'success': True,
            'activities': activities,
            'count': len(activities)
        })

    except Exception as e:
        logger.error(f"Error getting activity feed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ==================== Lead Monitoring ====================

@ai_monitoring_bp.route('/lead/<int:person_id>/details', methods=['GET'])
def get_lead_monitoring_details(person_id: int):
    """
    Get full AI monitoring data for a specific lead.

    Returns:
        JSON object with conversation state, messages, extracted data, pending notes
    """
    try:
        supabase = get_supabase_client()
        note_service = get_note_service(supabase)

        # Get AI conversation data
        conv_result = supabase.table('ai_conversations').select('*').eq(
            'fub_person_id', person_id
        ).order('updated_at', desc=True).limit(1).execute()

        conversation = conv_result.data[0] if conv_result.data else None

        # Get recent messages
        msg_result = supabase.table('ai_message_log').select('*').eq(
            'fub_person_id', person_id
        ).order('created_at', desc=True).limit(20).execute()

        messages = msg_result.data or []

        # Get AI settings for this lead
        settings_result = supabase.table('lead_ai_settings').select('*').eq(
            'fub_person_id', str(person_id)
        ).execute()

        ai_settings = settings_result.data[0] if settings_result.data else None

        # Get pending notes
        pending_notes = run_async(note_service.get_notes_for_person(person_id))

        # Get recent activity for this lead
        activities = run_async(note_service.get_activity_feed(limit=10, person_id=person_id))

        return jsonify({
            'success': True,
            'person_id': person_id,
            'conversation': conversation,
            'messages': messages,
            'ai_settings': ai_settings,
            'pending_notes': [n for n in pending_notes if n.get('status') == 'pending'],
            'all_notes': pending_notes,
            'recent_activity': activities,
            'summary': {
                'state': conversation.get('state') if conversation else 'unknown',
                'score': conversation.get('current_score') if conversation else None,
                'messages_sent': len([m for m in messages if m.get('direction') == 'outbound']),
                'messages_received': len([m for m in messages if m.get('direction') == 'inbound']),
                'ai_enabled': ai_settings.get('ai_enabled') if ai_settings else None,
                'pending_notes_count': len([n for n in pending_notes if n.get('status') == 'pending']),
            }
        })

    except Exception as e:
        logger.error(f"Error getting lead monitoring details for {person_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@ai_monitoring_bp.route('/lead/<int:person_id>/conversation', methods=['GET'])
def get_lead_conversation(person_id: int):
    """
    Get full conversation history for a lead.

    Query params:
        limit: Max messages to return (default 50)

    Returns:
        JSON array of messages in chronological order
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        supabase = get_supabase_client()

        # Get messages from ai_message_log
        result = supabase.table('ai_message_log').select('*').eq(
            'fub_person_id', person_id
        ).order('created_at', desc=False).limit(limit).execute()

        messages = result.data or []

        return jsonify({
            'success': True,
            'person_id': person_id,
            'messages': messages,
            'count': len(messages)
        })

    except Exception as e:
        logger.error(f"Error getting conversation for {person_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@ai_monitoring_bp.route('/lead/<int:person_id>/action', methods=['POST'])
def perform_lead_action(person_id: int):
    """
    Perform a quick action on a lead's AI.

    Body:
        action: "pause" | "resume" | "escalate"

    Returns:
        JSON result of the action
    """
    try:
        data = request.get_json() or {}
        action = data.get('action')
        user_email = get_user_email(request)

        if not action:
            return jsonify({'error': 'action is required'}), 400

        supabase = get_supabase_client()
        note_service = get_note_service(supabase)
        settings_service = LeadAISettingsService(supabase)

        if action == 'pause':
            # Disable AI for this lead
            result = run_async(settings_service.set_ai_enabled(str(person_id), False))
            await_log = note_service.log_activity(
                person_id=person_id,
                activity_type='paused',
                description=f'AI paused by {user_email or "admin"}',
                activity_data={'action': 'pause', 'user': user_email}
            )
            run_async(await_log)
            return jsonify({'success': True, 'action': 'paused', 'ai_enabled': False})

        elif action == 'resume':
            # Enable AI for this lead
            result = run_async(settings_service.set_ai_enabled(str(person_id), True))
            await_log = note_service.log_activity(
                person_id=person_id,
                activity_type='resumed',
                description=f'AI resumed by {user_email or "admin"}',
                activity_data={'action': 'resume', 'user': user_email}
            )
            run_async(await_log)
            return jsonify({'success': True, 'action': 'resumed', 'ai_enabled': True})

        elif action == 'escalate':
            # Mark as escalated (update conversation state)
            supabase.table('ai_conversations').update({
                'state': 'escalated',
                'escalation_reason': f'Manually escalated by {user_email or "admin"}',
            }).eq('fub_person_id', person_id).execute()

            await_log = note_service.log_activity(
                person_id=person_id,
                activity_type='escalated',
                description=f'Escalated to human by {user_email or "admin"}',
                activity_data={'action': 'escalate', 'user': user_email}
            )
            run_async(await_log)
            return jsonify({'success': True, 'action': 'escalated'})

        else:
            return jsonify({'error': f'Unknown action: {action}'}), 400

    except Exception as e:
        logger.error(f"Error performing action on lead {person_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ==================== Review Queue ====================

@ai_monitoring_bp.route('/review-queue', methods=['GET'])
def get_review_queue():
    """
    Get leads requiring human review.

    Returns leads that:
    - Have pending @update notes
    - Were escalated
    - Have failed messages
    - Need attention

    Returns:
        JSON array of leads needing review
    """
    try:
        supabase = get_supabase_client()
        note_service = get_note_service(supabase)

        # Get pending notes
        pending_notes = run_async(note_service.get_pending_notes(limit=100))

        # Get escalated conversations
        escalated_result = supabase.table('ai_conversations').select('*').eq(
            'state', 'escalated'
        ).order('updated_at', desc=True).limit(50).execute()

        escalated = escalated_result.data or []

        # Get leads with errors (from ai_message_log)
        error_result = supabase.table('ai_message_log').select(
            'person_id, error_message, created_at'
        ).not_.is_('error_message', 'null').order('created_at', desc=True).limit(20).execute()

        errors = error_result.data or []

        # Group pending notes by person
        notes_by_person = {}
        for note in pending_notes:
            pid = note.get('person_id')
            if pid not in notes_by_person:
                notes_by_person[pid] = []
            notes_by_person[pid].append(note)

        # Build review queue
        review_items = []

        # Add escalated leads
        for conv in escalated:
            review_items.append({
                'person_id': conv.get('person_id'),
                'type': 'escalated',
                'reason': conv.get('escalation_reason', 'Escalated'),
                'timestamp': conv.get('updated_at'),
                'priority': 'high',
            })

        # Add leads with pending notes
        for person_id, notes in notes_by_person.items():
            # Skip if already in queue
            if any(r['person_id'] == person_id for r in review_items):
                continue

            review_items.append({
                'person_id': person_id,
                'type': 'pending_notes',
                'reason': f'{len(notes)} pending @update notes',
                'timestamp': notes[0].get('created_at'),
                'priority': 'medium',
                'pending_notes': notes,
            })

        # Sort by priority and timestamp
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        review_items.sort(key=lambda x: (priority_order.get(x.get('priority', 'low'), 2), x.get('timestamp', '')), reverse=True)

        return jsonify({
            'success': True,
            'review_queue': review_items,
            'counts': {
                'total': len(review_items),
                'escalated': len(escalated),
                'pending_notes': len(notes_by_person),
                'errors': len(set(e['person_id'] for e in errors)),
            }
        })

    except Exception as e:
        logger.error(f"Error getting review queue: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ==================== @update Notes Management ====================

@ai_monitoring_bp.route('/pending-notes', methods=['GET'])
def get_pending_notes():
    """
    Get all pending @update notes awaiting review.

    Query params:
        person_id: Optional filter by person
        limit: Max notes to return (default 50)

    Returns:
        JSON array of pending notes
    """
    try:
        person_id = request.args.get('person_id', type=int)
        limit = request.args.get('limit', 50, type=int)

        note_service = get_note_service()
        notes = run_async(note_service.get_pending_notes(person_id=person_id, limit=limit))

        return jsonify({
            'success': True,
            'notes': notes,
            'count': len(notes)
        })

    except Exception as e:
        logger.error(f"Error getting pending notes: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@ai_monitoring_bp.route('/notes/<note_id>/approve', methods=['POST'])
def approve_note(note_id: str):
    """
    Approve a pending note and create it in FUB.

    Returns:
        JSON result with FUB note ID
    """
    try:
        user_email = get_user_email(request) or 'admin'

        note_service = get_note_service()
        result = run_async(note_service.approve_note(note_id, user_email))

        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error approving note {note_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@ai_monitoring_bp.route('/notes/<note_id>/dismiss', methods=['POST'])
def dismiss_note(note_id: str):
    """
    Dismiss a pending note (don't create in FUB).

    Returns:
        JSON result
    """
    try:
        user_email = get_user_email(request) or 'admin'

        note_service = get_note_service()
        result = run_async(note_service.dismiss_note(note_id, user_email))

        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error dismissing note {note_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@ai_monitoring_bp.route('/notes/bulk-approve', methods=['POST'])
def bulk_approve_notes():
    """
    Approve multiple notes at once.

    Body:
        note_ids: List of note UUIDs to approve

    Returns:
        JSON with approved/failed counts
    """
    try:
        data = request.get_json() or {}
        note_ids = data.get('note_ids', [])
        user_email = get_user_email(request) or 'admin'

        if not note_ids:
            return jsonify({'error': 'note_ids is required'}), 400

        note_service = get_note_service()
        result = run_async(note_service.bulk_approve_notes(note_ids, user_email))

        return jsonify({
            'success': True,
            **result
        })

    except Exception as e:
        logger.error(f"Error bulk approving notes: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ==================== AI-Enabled Leads Overview ====================

@ai_monitoring_bp.route('/ai-enabled-leads', methods=['GET'])
def get_ai_enabled_leads():
    """
    Get overview of all leads with AI enabled.

    Query params:
        limit: Max leads to return (default 100)

    Returns:
        JSON array of AI-enabled leads with status summaries
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        supabase = get_supabase_client()

        # Get leads with AI enabled
        settings_result = supabase.table('lead_ai_settings').select('*').eq(
            'ai_enabled', True
        ).limit(limit).execute()

        ai_leads = settings_result.data or []

        # Get person IDs
        person_ids = [int(l.get('fub_person_id')) for l in ai_leads if l.get('fub_person_id')]

        # Get conversation states for these leads
        if person_ids:
            conv_result = supabase.table('ai_conversations').select(
                'fub_person_id, state, current_score, updated_at'
            ).in_('fub_person_id', person_ids).execute()

            conv_by_person = {c['fub_person_id']: c for c in (conv_result.data or [])}
        else:
            conv_by_person = {}

        # Get recent message counts
        if person_ids:
            # This is a simplified approach - in production you might want a more efficient query
            msg_result = supabase.table('ai_message_log').select(
                'fub_person_id, direction, created_at'
            ).in_('fub_person_id', person_ids).order('created_at', desc=True).limit(500).execute()

            msg_counts = {}
            for msg in (msg_result.data or []):
                pid = msg['fub_person_id']
                if pid not in msg_counts:
                    msg_counts[pid] = {'sent': 0, 'received': 0, 'last_activity': None}
                if msg['direction'] == 'outbound':
                    msg_counts[pid]['sent'] += 1
                else:
                    msg_counts[pid]['received'] += 1
                if not msg_counts[pid]['last_activity']:
                    msg_counts[pid]['last_activity'] = msg['created_at']
        else:
            msg_counts = {}

        # Build lead summaries
        leads_with_status = []
        for lead in ai_leads:
            person_id = int(lead.get('fub_person_id', 0))
            conv = conv_by_person.get(person_id, {})
            msgs = msg_counts.get(person_id, {'sent': 0, 'received': 0, 'last_activity': None})

            leads_with_status.append({
                'person_id': person_id,
                'ai_enabled': True,
                'auto_respond': lead.get('auto_respond'),
                'state': conv.get('state', 'unknown'),
                'score': conv.get('current_score'),
                'messages_sent': msgs['sent'],
                'messages_received': msgs['received'],
                'last_activity': msgs['last_activity'] or conv.get('updated_at'),
            })

        # Sort by last activity
        leads_with_status.sort(key=lambda x: x.get('last_activity') or '', reverse=True)

        return jsonify({
            'success': True,
            'leads': leads_with_status,
            'count': len(leads_with_status)
        })

    except Exception as e:
        logger.error(f"Error getting AI-enabled leads: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ==================== Scheduled Tasks ====================

@ai_monitoring_bp.route('/scheduled-tasks', methods=['GET'])
def get_scheduled_tasks():
    """
    Get upcoming scheduled AI tasks/follow-ups.

    Query params:
        limit: Max tasks to return (default 50)
        status: Filter by status (pending, sent, cancelled, failed)

    Returns:
        JSON array of scheduled tasks
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        status_filter = request.args.get('status', 'pending')

        supabase = get_supabase_client()

        # Get scheduled messages
        query = supabase.table('scheduled_messages').select(
            'id, fub_person_id, message_type, message_content, template_id, '
            'channel, scheduled_for, status, created_at, sequence_id, sequence_day'
        )

        if status_filter:
            query = query.eq('status', status_filter)

        # Order by scheduled time (soonest first for pending, most recent for others)
        if status_filter == 'pending':
            query = query.gte('scheduled_for', 'now()').order('scheduled_for', desc=False)
        else:
            query = query.order('scheduled_for', desc=True)

        result = query.limit(limit).execute()
        scheduled_messages = result.data or []

        # Get unique person IDs to fetch names
        person_ids = list(set(m.get('fub_person_id') for m in scheduled_messages if m.get('fub_person_id')))

        # Try to get lead names from ai_conversations or lead_ai_settings
        lead_names = {}
        if person_ids:
            try:
                conv_result = supabase.table('ai_conversations').select(
                    'fub_person_id, lead_first_name, lead_last_name'
                ).in_('fub_person_id', person_ids).execute()

                for conv in (conv_result.data or []):
                    pid = conv.get('fub_person_id')
                    first = conv.get('lead_first_name', '')
                    last = conv.get('lead_last_name', '')
                    if first or last:
                        lead_names[pid] = f"{first} {last}".strip()
            except Exception as name_err:
                logger.warning(f"Could not fetch lead names: {name_err}")

        # Enrich tasks with lead names and format for frontend
        tasks = []
        for msg in scheduled_messages:
            person_id = msg.get('fub_person_id')
            tasks.append({
                'id': msg.get('id'),
                'person_id': person_id,
                'lead_name': lead_names.get(person_id, f"Person #{person_id}"),
                'message_type': msg.get('message_type'),
                'message_preview': (msg.get('message_content') or '')[:100] + ('...' if len(msg.get('message_content') or '') > 100 else ''),
                'template_id': msg.get('template_id'),
                'channel': msg.get('channel', 'sms'),
                'scheduled_for': msg.get('scheduled_for'),
                'status': msg.get('status'),
                'sequence_id': msg.get('sequence_id'),
                'sequence_day': msg.get('sequence_day'),
                'created_at': msg.get('created_at'),
            })

        # Also get counts by status
        count_result = supabase.rpc('count_scheduled_by_status', {}).execute()
        status_counts = {}
        if count_result.data:
            for row in count_result.data:
                status_counts[row.get('status')] = row.get('count', 0)

        # Fallback: count manually if RPC doesn't exist
        if not status_counts:
            for status in ['pending', 'sent', 'cancelled', 'failed', 'skipped']:
                try:
                    count_res = supabase.table('scheduled_messages').select(
                        'id', count='exact'
                    ).eq('status', status).execute()
                    status_counts[status] = count_res.count or 0
                except:
                    pass

        return jsonify({
            'success': True,
            'tasks': tasks,
            'count': len(tasks),
            'status_counts': status_counts,
        })

    except Exception as e:
        logger.error(f"Error getting scheduled tasks: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@ai_monitoring_bp.route('/scheduled-tasks/<task_id>/cancel', methods=['POST'])
def cancel_scheduled_task(task_id: str):
    """
    Cancel a scheduled task.

    Returns:
        JSON result
    """
    try:
        user_email = get_user_email(request) or 'admin'
        supabase = get_supabase_client()

        # Update status to cancelled
        result = supabase.table('scheduled_messages').update({
            'status': 'cancelled',
            'cancelled_at': 'now()',
            'cancelled_by': user_email,
        }).eq('id', task_id).eq('status', 'pending').execute()

        if result.data:
            return jsonify({
                'success': True,
                'message': 'Task cancelled',
                'task_id': task_id
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Task not found or already processed'
            }), 404

    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@ai_monitoring_bp.route('/scheduled-tasks/cancel-for-lead/<int:person_id>', methods=['POST'])
def cancel_tasks_for_lead(person_id: int):
    """
    Cancel all pending scheduled tasks for a specific lead.

    Returns:
        JSON result with count of cancelled tasks
    """
    try:
        user_email = get_user_email(request) or 'admin'
        supabase = get_supabase_client()

        # Update all pending tasks for this lead
        result = supabase.table('scheduled_messages').update({
            'status': 'cancelled',
            'cancelled_at': 'now()',
            'cancelled_by': user_email,
            'cancellation_reason': 'Manual cancellation from monitor',
        }).eq('fub_person_id', person_id).eq('status', 'pending').execute()

        cancelled_count = len(result.data) if result.data else 0

        return jsonify({
            'success': True,
            'message': f'Cancelled {cancelled_count} tasks for lead {person_id}',
            'cancelled_count': cancelled_count,
            'person_id': person_id
        })

    except Exception as e:
        logger.error(f"Error cancelling tasks for lead {person_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@ai_monitoring_bp.route('/api/ai-monitoring/lead/<int:person_id>/clear-opt-out', methods=['POST'])
def clear_lead_opt_out(person_id):
    """Clear opt-out status for a lead (re-subscribe).

    Use when a lead was falsely opted out or explicitly opts back in.
    """
    try:
        supabase = get_supabase_client()

        # Clear opt-out directly on sms_consent table by fub_person_id
        result = supabase.table('sms_consent').update({
            'opted_out': False,
            'opted_out_at': None,
            'opt_out_reason': None,
        }).eq('fub_person_id', person_id).execute()

        if result.data:
            return jsonify({
                'success': True,
                'message': f'Opt-out cleared for person {person_id}',
                'person_id': person_id
            })
        else:
            return jsonify({'error': f'No consent record found for person {person_id}'}), 404

    except Exception as e:
        logger.error(f"Error clearing opt-out for person {person_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@ai_monitoring_bp.route('/stale-handoffs', methods=['GET'])
def get_stale_handoffs():
    """Get leads that were handed off but never followed up by a human agent.

    Query params:
        threshold_hours: Hours since handoff (default 48)
        limit: Max results (default 20)
    """
    try:
        from datetime import datetime, timedelta
        supabase = get_supabase_client()

        threshold_hours = int(request.args.get('threshold_hours', 48))
        limit = int(request.args.get('limit', 20))
        threshold = (datetime.utcnow() - timedelta(hours=threshold_hours)).isoformat()

        result = supabase.table('ai_conversations').select(
            'fub_person_id, state, handoff_reason, assigned_agent_id, '
            'last_ai_message_at, last_human_message_at, updated_at'
        ).eq(
            'state', 'handed_off'
        ).eq(
            'is_active', True
        ).lt(
            'updated_at', threshold
        ).order(
            'updated_at', desc=False
        ).limit(limit).execute()

        handoffs = []
        for conv in (result.data or []):
            updated_at = conv.get('updated_at', '')
            hours_stale = threshold_hours  # default
            if updated_at:
                try:
                    from datetime import timezone
                    updated_dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                    hours_stale = int((datetime.now(timezone.utc) - updated_dt).total_seconds() / 3600)
                except (ValueError, AttributeError):
                    pass

            handoffs.append({
                **conv,
                'hours_stale': hours_stale,
            })

        return jsonify({
            'success': True,
            'count': len(handoffs),
            'stale_handoffs': handoffs,
        })

    except Exception as e:
        logger.error(f"Error getting stale handoffs: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@ai_monitoring_bp.route('/deferred-followups', methods=['GET'])
def get_deferred_followups():
    """Get leads with deferred follow-up requests ('call me next month').

    Returns pending deferred follow-ups with their scheduled dates.
    """
    try:
        supabase = get_supabase_client()

        result = supabase.table('ai_scheduled_followups').select(
            'id, fub_person_id, scheduled_at, channel, message_type, status, sequence_id'
        ).eq(
            'message_type', 'deferred_followup'
        ).eq(
            'status', 'pending'
        ).order(
            'scheduled_at', desc=False
        ).limit(50).execute()

        return jsonify({
            'success': True,
            'count': len(result.data or []),
            'deferred_followups': result.data or [],
        })

    except Exception as e:
        logger.error(f"Error getting deferred follow-ups: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@ai_monitoring_bp.route('/nba-recommendations', methods=['GET'])
def get_nba_recommendations():
    """Get latest NBA (Next Best Action) scanner results.

    Runs a quick NBA scan and returns recommendations.
    """
    try:
        from app.ai_agent.next_best_action import run_nba_scan

        result = run_async(run_nba_scan(
            execute=False,  # Don't execute, just recommend
            batch_size=30,
        ))

        return jsonify({
            'success': True,
            'recommendations_count': result.get('recommendations_count', 0),
            'recommendations': result.get('recommendations', []),
            'scan_time': result.get('scan_time'),
        })

    except Exception as e:
        logger.error(f"Error running NBA scan: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
