"""
Support Ticket API Routes.
Ported from Leaddata.

User endpoints:
- GET /api/support/tickets - List user's tickets
- POST /api/support/tickets - Create a ticket
- GET /api/support/tickets/<id> - Get ticket details
- POST /api/support/tickets/<id>/notes - Add note to ticket

Admin endpoints:
- GET /api/support/admin/tickets - List all tickets (admin only)
- PUT /api/support/admin/tickets/<id>/assign - Assign ticket
- PUT /api/support/admin/tickets/<id>/status - Update status
"""

from flask import request, jsonify
import logging
from datetime import datetime

from app.support import support_bp
from app.database.supabase_client import SupabaseClientSingleton
from app.models.support_ticket import SupportTicket, TicketNote

logger = logging.getLogger(__name__)


def get_user_id_from_request():
    """Extract user ID from request headers or body."""
    user_id = request.headers.get('X-User-ID')
    if not user_id and request.is_json:
        data = request.get_json(silent=True)
        if data:
            user_id = data.get('user_id')
    return user_id


def check_admin(user_id: str) -> bool:
    """Check if user is an admin."""
    try:
        supabase = SupabaseClientSingleton.get_instance()
        result = supabase.table('users').select('is_admin').eq('id', user_id).single().execute()
        return result.data.get('is_admin', False) if result.data else False
    except Exception:
        return False


# =============================================================================
# User Ticket Endpoints
# =============================================================================

@support_bp.route('/tickets', methods=['GET'])
def list_tickets():
    """
    List tickets for the current user.

    Query params:
        - status: Filter by status (open, in_progress, waiting, closed)
        - limit: Number of tickets to return (default 50, max 100)
        - offset: Offset for pagination (default 0)
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        supabase = SupabaseClientSingleton.get_instance()

        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))
        status = request.args.get('status')

        query = supabase.table('support_tickets').select('*').eq('user_id', user_id)

        if status:
            query = query.eq('status', status)

        result = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()

        tickets = [SupportTicket.from_dict(t).to_dict() for t in (result.data or [])]

        return jsonify({
            "success": True,
            "tickets": tickets,
            "limit": limit,
            "offset": offset
        })

    except Exception as e:
        logger.error(f"Error listing tickets: {e}")
        return jsonify({"error": str(e)}), 500


@support_bp.route('/tickets', methods=['POST'])
def create_ticket():
    """
    Create a new support ticket.

    Body:
        - subject: Ticket subject (required)
        - description: Detailed description (required)
        - priority: low, normal, high, urgent (default: normal)
        - category: billing, technical, feature_request, account, other (optional)
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    data = request.get_json()

    subject = data.get('subject')
    description = data.get('description')

    if not subject or not description:
        return jsonify({"error": "Subject and description are required"}), 400

    try:
        supabase = SupabaseClientSingleton.get_instance()

        ticket_data = {
            'user_id': user_id,
            'subject': subject,
            'description': description,
            'status': SupportTicket.STATUS_OPEN,
            'priority': data.get('priority', SupportTicket.PRIORITY_NORMAL),
            'category': data.get('category'),
        }

        result = supabase.table('support_tickets').insert(ticket_data).execute()

        if result.data:
            ticket = SupportTicket.from_dict(result.data[0])
            logger.info(f"Created ticket {ticket.id} for user {user_id}")

            return jsonify({
                "success": True,
                "ticket": ticket.to_dict()
            }), 201
        else:
            return jsonify({"error": "Failed to create ticket"}), 500

    except Exception as e:
        logger.error(f"Error creating ticket: {e}")
        return jsonify({"error": str(e)}), 500


@support_bp.route('/tickets/<int:ticket_id>', methods=['GET'])
def get_ticket(ticket_id):
    """
    Get ticket details with notes.
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        supabase = SupabaseClientSingleton.get_instance()

        # Get ticket
        ticket_result = supabase.table('support_tickets').select('*').eq('id', ticket_id).single().execute()

        if not ticket_result.data:
            return jsonify({"error": "Ticket not found"}), 404

        ticket = SupportTicket.from_dict(ticket_result.data)

        # Check if user owns the ticket or is admin
        if ticket.user_id != user_id and not check_admin(user_id):
            return jsonify({"error": "Access denied"}), 403

        # Get notes (exclude internal notes for non-admin)
        notes_query = supabase.table('ticket_notes').select('*').eq('ticket_id', ticket_id)

        if not check_admin(user_id):
            notes_query = notes_query.eq('is_internal', False)

        notes_result = notes_query.order('created_at').execute()

        notes = [TicketNote.from_dict(n).to_dict() for n in (notes_result.data or [])]

        return jsonify({
            "success": True,
            "ticket": ticket.to_dict(),
            "notes": notes
        })

    except Exception as e:
        logger.error(f"Error getting ticket: {e}")
        return jsonify({"error": str(e)}), 500


@support_bp.route('/tickets/<int:ticket_id>/notes', methods=['POST'])
def add_note(ticket_id):
    """
    Add a note to a ticket.

    Body:
        - content: Note content (required)
        - is_internal: Whether this is an internal note (admin only, default: false)
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    data = request.get_json()
    content = data.get('content')

    if not content:
        return jsonify({"error": "Content is required"}), 400

    try:
        supabase = SupabaseClientSingleton.get_instance()

        # Verify ticket exists and user has access
        ticket_result = supabase.table('support_tickets').select('user_id').eq('id', ticket_id).single().execute()

        if not ticket_result.data:
            return jsonify({"error": "Ticket not found"}), 404

        ticket_user_id = ticket_result.data['user_id']
        is_admin = check_admin(user_id)

        if ticket_user_id != user_id and not is_admin:
            return jsonify({"error": "Access denied"}), 403

        # Only admins can create internal notes
        is_internal = data.get('is_internal', False) and is_admin

        note_data = {
            'ticket_id': ticket_id,
            'user_id': user_id,
            'content': content,
            'is_internal': is_internal,
        }

        result = supabase.table('ticket_notes').insert(note_data).execute()

        if result.data:
            note = TicketNote.from_dict(result.data[0])

            # Update ticket's updated_at
            supabase.table('support_tickets').update({
                'updated_at': datetime.utcnow().isoformat()
            }).eq('id', ticket_id).execute()

            return jsonify({
                "success": True,
                "note": note.to_dict()
            }), 201
        else:
            return jsonify({"error": "Failed to add note"}), 500

    except Exception as e:
        logger.error(f"Error adding note: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Admin Ticket Endpoints
# =============================================================================

@support_bp.route('/admin/tickets', methods=['GET'])
def admin_list_tickets():
    """
    List all tickets (admin only).

    Query params:
        - status: Filter by status
        - priority: Filter by priority
        - assigned_to: Filter by assignee
        - limit: Number of tickets (default 50, max 100)
        - offset: Offset for pagination
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    if not check_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    try:
        supabase = SupabaseClientSingleton.get_instance()

        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))
        status = request.args.get('status')
        priority = request.args.get('priority')
        assigned_to = request.args.get('assigned_to')

        query = supabase.table('support_tickets').select('*')

        if status:
            query = query.eq('status', status)
        if priority:
            query = query.eq('priority', priority)
        if assigned_to:
            query = query.eq('assigned_to', assigned_to)

        result = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()

        tickets = [SupportTicket.from_dict(t).to_dict() for t in (result.data or [])]

        # Get counts by status
        counts_result = supabase.table('support_tickets').select('status').execute()
        status_counts = {}
        for t in (counts_result.data or []):
            s = t.get('status')
            status_counts[s] = status_counts.get(s, 0) + 1

        return jsonify({
            "success": True,
            "tickets": tickets,
            "counts": status_counts,
            "limit": limit,
            "offset": offset
        })

    except Exception as e:
        logger.error(f"Error listing admin tickets: {e}")
        return jsonify({"error": str(e)}), 500


@support_bp.route('/admin/tickets/<int:ticket_id>/assign', methods=['PUT'])
def assign_ticket(ticket_id):
    """
    Assign a ticket to an admin (admin only).

    Body:
        - assigned_to: User ID of the assignee (required)
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    if not check_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    data = request.get_json()
    assigned_to = data.get('assigned_to')

    if not assigned_to:
        return jsonify({"error": "assigned_to is required"}), 400

    try:
        supabase = SupabaseClientSingleton.get_instance()

        # Verify assignee exists and is admin
        assignee_result = supabase.table('users').select('is_admin').eq('id', assigned_to).single().execute()

        if not assignee_result.data or not assignee_result.data.get('is_admin'):
            return jsonify({"error": "Assignee must be an admin"}), 400

        # Update ticket
        result = supabase.table('support_tickets').update({
            'assigned_to': assigned_to,
            'status': SupportTicket.STATUS_IN_PROGRESS,
            'updated_at': datetime.utcnow().isoformat()
        }).eq('id', ticket_id).execute()

        if result.data:
            ticket = SupportTicket.from_dict(result.data[0])
            logger.info(f"Ticket {ticket_id} assigned to {assigned_to} by {user_id}")

            return jsonify({
                "success": True,
                "ticket": ticket.to_dict()
            })
        else:
            return jsonify({"error": "Ticket not found"}), 404

    except Exception as e:
        logger.error(f"Error assigning ticket: {e}")
        return jsonify({"error": str(e)}), 500


@support_bp.route('/admin/tickets/<int:ticket_id>/status', methods=['PUT'])
def update_ticket_status(ticket_id):
    """
    Update ticket status (admin only).

    Body:
        - status: New status (open, in_progress, waiting, closed)
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    if not check_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    data = request.get_json()
    status = data.get('status')

    valid_statuses = [
        SupportTicket.STATUS_OPEN,
        SupportTicket.STATUS_IN_PROGRESS,
        SupportTicket.STATUS_WAITING,
        SupportTicket.STATUS_CLOSED
    ]

    if not status or status not in valid_statuses:
        return jsonify({"error": f"Invalid status. Must be one of: {valid_statuses}"}), 400

    try:
        supabase = SupabaseClientSingleton.get_instance()

        update_data = {
            'status': status,
            'updated_at': datetime.utcnow().isoformat()
        }

        # If closing, set closed_at
        if status == SupportTicket.STATUS_CLOSED:
            update_data['closed_at'] = datetime.utcnow().isoformat()

        result = supabase.table('support_tickets').update(update_data).eq('id', ticket_id).execute()

        if result.data:
            ticket = SupportTicket.from_dict(result.data[0])
            logger.info(f"Ticket {ticket_id} status updated to {status} by {user_id}")

            return jsonify({
                "success": True,
                "ticket": ticket.to_dict()
            })
        else:
            return jsonify({"error": "Ticket not found"}), 404

    except Exception as e:
        logger.error(f"Error updating ticket status: {e}")
        return jsonify({"error": str(e)}), 500


@support_bp.route('/admin/stats', methods=['GET'])
def get_support_stats():
    """
    Get support ticket statistics (admin only).
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    if not check_admin(user_id):
        return jsonify({"error": "Admin access required"}), 403

    try:
        supabase = SupabaseClientSingleton.get_instance()

        # Get all tickets for stats
        tickets_result = supabase.table('support_tickets').select('status, priority, created_at, closed_at').execute()
        tickets = tickets_result.data or []

        # Calculate stats
        total = len(tickets)
        by_status = {}
        by_priority = {}
        resolved = 0
        resolution_times = []

        for t in tickets:
            # Status counts
            status = t.get('status')
            by_status[status] = by_status.get(status, 0) + 1

            # Priority counts
            priority = t.get('priority')
            by_priority[priority] = by_priority.get(priority, 0) + 1

            # Resolution stats
            if status == SupportTicket.STATUS_CLOSED and t.get('closed_at') and t.get('created_at'):
                resolved += 1
                try:
                    created = datetime.fromisoformat(t['created_at'].replace('Z', '+00:00'))
                    closed = datetime.fromisoformat(t['closed_at'].replace('Z', '+00:00'))
                    resolution_times.append((closed - created).total_seconds() / 3600)  # Hours
                except Exception:
                    pass

        avg_resolution_hours = sum(resolution_times) / len(resolution_times) if resolution_times else 0

        return jsonify({
            "success": True,
            "stats": {
                "total_tickets": total,
                "open_tickets": by_status.get(SupportTicket.STATUS_OPEN, 0),
                "in_progress": by_status.get(SupportTicket.STATUS_IN_PROGRESS, 0),
                "waiting": by_status.get(SupportTicket.STATUS_WAITING, 0),
                "closed": by_status.get(SupportTicket.STATUS_CLOSED, 0),
                "by_priority": by_priority,
                "resolved_count": resolved,
                "avg_resolution_hours": round(avg_resolution_hours, 1),
                "resolution_rate": round(resolved / total * 100, 1) if total > 0 else 0
            }
        })

    except Exception as e:
        logger.error(f"Error getting support stats: {e}")
        return jsonify({"error": str(e)}), 500
