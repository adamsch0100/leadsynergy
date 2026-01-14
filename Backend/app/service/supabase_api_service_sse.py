"""
Server-Sent Events endpoints for real-time sync updates
"""
from flask import Response, stream_with_context, Blueprint
from app.service.sync_status_tracker import get_tracker
import json
import time
import logging

logger = logging.getLogger(__name__)

# Create blueprint for SSE endpoints
sse_bp = Blueprint('sse', __name__)

@sse_bp.route("/active-syncs", methods=["GET"])
def get_active_syncs():
    """Get all active syncs for the current user"""
    from flask import jsonify, request
    try:
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            return jsonify({
                "success": False,
                "error": "User ID required"
            }), 400

        tracker = get_tracker()
        active_syncs = tracker.get_active_syncs(user_id)

        return jsonify({
            "success": True,
            "data": active_syncs
        }), 200
    except Exception as e:
        logger.error(f"Error getting active syncs: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@sse_bp.route("/sync-status/<sync_id>", methods=["GET"])
def get_sync_status(sync_id):
    """Get current sync status (for polling)"""
    from flask import jsonify
    try:
        tracker = get_tracker()
        status = tracker.get_status(sync_id)
        
        if not status:
            return jsonify({
                "success": False,
                "error": "Sync not found"
            }), 404
        
        return jsonify({
            "success": True,
            "data": status
        }), 200
    except Exception as e:
        logger.error(f"Error getting sync status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@sse_bp.route("/sync-status/<sync_id>/cancel", methods=["POST"])
def cancel_sync(sync_id):
    """Cancel a running sync"""
    from flask import jsonify
    try:
        tracker = get_tracker()
        cancelled = tracker.cancel_sync(sync_id)
        
        if not cancelled:
            return jsonify({
                "success": False,
                "error": "Sync not found or cannot be cancelled"
            }), 400
        
        return jsonify({
            "success": True,
            "message": "Sync cancellation requested"
        }), 200
    except Exception as e:
        logger.error(f"Error cancelling sync: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@sse_bp.route("/sync-status/<sync_id>/stream", methods=["GET"])
def stream_sync_status(sync_id):
    """Stream sync status updates via Server-Sent Events"""
    def generate():
        tracker = get_tracker()
        last_message_count = 0
        
        try:
            # Send initial status
            status = tracker.get_status(sync_id)
            if not status:
                yield f"data: {json.dumps({'error': 'Sync not found'})}\n\n"
                return
            
            yield f"data: {json.dumps({'type': 'status', 'data': status})}\n\n"
            
            # Keep connection alive and send updates
            while True:
                status = tracker.get_status(sync_id)
                
                if not status:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Sync not found'})}\n\n"
                    break
                
                # Check if sync is complete
                if status.get("status") in ["completed", "failed", "cancelled"]:
                    yield f"data: {json.dumps({'type': 'complete', 'data': status})}\n\n"
                    break
                
                # Check if sync is being cancelled
                if status.get("status") == "cancelling":
                    yield f"data: {json.dumps({'type': 'status', 'data': status})}\n\n"
                
                # Send update if there are new messages
                current_message_count = len(status.get("messages", []))
                if current_message_count > last_message_count:
                    new_messages = status.get("messages", [])[last_message_count:]
                    for msg in new_messages:
                        yield f"data: {json.dumps({'type': 'message', 'data': msg})}\n\n"
                    last_message_count = current_message_count
                
                # Send periodic status update
                yield f"data: {json.dumps({'type': 'status', 'data': status})}\n\n"
                
                # Wait before next check
                time.sleep(1)
                
        except GeneratorExit:
            # Client disconnected
            pass
        except Exception as e:
            logger.error(f"Error in sync stream: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )

