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
            'person_id', person_id
        ).order('updated_at', desc=True).limit(1).execute()

        conversation = conv_result.data[0] if conv_result.data else None

        # Get recent messages
        msg_result = supabase.table('ai_message_log').select('*').eq(
            'person_id', person_id
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
            'person_id', person_id
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
            }).eq('person_id', person_id).execute()

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
                'person_id, state, current_score, updated_at'
            ).in_('person_id', person_ids).execute()

            conv_by_person = {c['person_id']: c for c in (conv_result.data or [])}
        else:
            conv_by_person = {}

        # Get recent message counts
        if person_ids:
            # This is a simplified approach - in production you might want a more efficient query
            msg_result = supabase.table('ai_message_log').select(
                'person_id, direction, created_at'
            ).in_('person_id', person_ids).order('created_at', desc=True).limit(500).execute()

            msg_counts = {}
            for msg in (msg_result.data or []):
                pid = msg['person_id']
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
