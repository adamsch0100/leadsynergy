"""
Voice AI Routes - Real-time voice AI communication endpoints.

Uses Flask-SocketIO for WebSocket support.

Provides:
- WebSocket endpoint for Chrome extension communication
- REST endpoints for voice settings and call history
"""

import logging
import json
from typing import Optional
from flask import Blueprint, request, jsonify

from .conversation_handler import VoiceConversationHandler
from .voice_prompts import get_first_message

logger = logging.getLogger(__name__)

voice_bp = Blueprint('voice', __name__)

# Global conversation handler
_conversation_handler: Optional[VoiceConversationHandler] = None

# SocketIO instance (will be set by init_voice_socketio)
_socketio = None


def get_conversation_handler() -> VoiceConversationHandler:
    """Get or create the conversation handler."""
    global _conversation_handler
    if _conversation_handler is None:
        try:
            from app.database.supabase_client import SupabaseClientSingleton
            supabase = SupabaseClientSingleton.get_instance()
            _conversation_handler = VoiceConversationHandler(supabase_client=supabase)
        except Exception as e:
            logger.warning(f"Could not initialize with Supabase: {e}")
            _conversation_handler = VoiceConversationHandler()
    return _conversation_handler


def init_voice_socketio(socketio):
    """
    Initialize Socket.IO event handlers for voice AI.

    Call this from main.py after creating the SocketIO instance.

    Args:
        socketio: Flask-SocketIO instance
    """
    global _socketio
    _socketio = socketio

    @socketio.on('connect', namespace='/voice')
    def handle_connect():
        """Handle client connection."""
        logger.info(f"Voice client connected: {request.sid}")

    @socketio.on('disconnect', namespace='/voice')
    def handle_disconnect():
        """Handle client disconnection."""
        logger.info(f"Voice client disconnected: {request.sid}")

    @socketio.on('start_session', namespace='/voice')
    def handle_start_session(data):
        """
        Start a voice AI session.

        Args:
            data: {person_id: int, organization_id: str}
        """
        import asyncio
        from flask_socketio import emit, join_room

        person_id = data.get('person_id')
        organization_id = data.get('organization_id')

        if not person_id:
            emit('error', {'message': 'person_id required'})
            return

        logger.info(f"Starting voice session for person {person_id}")

        # Join a room for this person
        join_room(f"person_{person_id}")

        handler = get_conversation_handler()

        # Start conversation (run async in sync context)
        loop = asyncio.new_event_loop()
        try:
            conversation = loop.run_until_complete(
                handler.start_conversation(
                    person_id=person_id,
                    organization_id=organization_id,
                )
            )

            # Send greeting
            if conversation.lead_profile:
                first_name = conversation.lead_profile.get("first_name", "there")
                agent_name = (
                    conversation.settings.get("agent_name", "Sarah")
                    if conversation.settings else "Sarah"
                )

                greeting = get_first_message(
                    message_type="new_lead",
                    first_name=first_name,
                    agent_name=agent_name,
                )

                emit('response', {
                    'response': greeting,
                    'action': None,
                    'is_greeting': True,
                })

            emit('session_started', {
                'person_id': person_id,
                'state': conversation.state.value,
            })

        except Exception as e:
            logger.error(f"Error starting voice session: {e}")
            emit('error', {'message': str(e)})
        finally:
            loop.close()

    @socketio.on('transcript', namespace='/voice')
    def handle_transcript(data):
        """
        Handle incoming transcript from Deepgram.

        Args:
            data: {person_id: int, transcript: str, timestamp: int}
        """
        import asyncio
        from flask_socketio import emit

        person_id = data.get('person_id')
        transcript = data.get('transcript', '').strip()

        if not person_id or not transcript:
            return

        logger.info(f"Received transcript for person {person_id}: {transcript}")

        handler = get_conversation_handler()

        # Process transcript
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                handler.process_transcript(
                    person_id=person_id,
                    transcript=transcript,
                )
            )

            # Send response
            emit('response', {
                'response': result['response'],
                'action': result.get('action'),
            })

            # Handle end call action
            if result.get('action', {}).get('type') == 'end_call':
                loop.run_until_complete(
                    handler.end_conversation(
                        person_id=person_id,
                        reason=result['action'].get('reason', 'normal'),
                    )
                )
                emit('session_ended', {
                    'person_id': person_id,
                    'reason': result['action'].get('reason'),
                })

        except Exception as e:
            logger.error(f"Error processing transcript: {e}")
            emit('error', {'message': str(e)})
        finally:
            loop.close()

    @socketio.on('end_session', namespace='/voice')
    def handle_end_session(data):
        """
        End a voice AI session.

        Args:
            data: {person_id: int, reason: str}
        """
        import asyncio
        from flask_socketio import emit, leave_room

        person_id = data.get('person_id')
        reason = data.get('reason', 'normal')

        if not person_id:
            return

        logger.info(f"Ending voice session for person {person_id}")

        leave_room(f"person_{person_id}")

        handler = get_conversation_handler()

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                handler.end_conversation(
                    person_id=person_id,
                    reason=reason,
                )
            )
            emit('session_ended', {
                'person_id': person_id,
                'reason': reason,
            })
        except Exception as e:
            logger.error(f"Error ending session: {e}")
        finally:
            loop.close()

    @socketio.on('ping', namespace='/voice')
    def handle_ping():
        """Handle keep-alive ping."""
        from flask_socketio import emit
        emit('pong')

    logger.info("Voice SocketIO handlers registered")


# REST API endpoints

@voice_bp.route('/settings', methods=['GET'])
def get_voice_settings():
    """
    Get voice AI settings for an organization.

    Query params:
        organization_id: Optional organization ID
    """
    import asyncio

    organization_id = request.args.get('organization_id')
    handler = get_conversation_handler()

    loop = asyncio.new_event_loop()
    try:
        settings = loop.run_until_complete(
            handler._load_settings(organization_id)
        )
    finally:
        loop.close()

    return jsonify({
        "enabled": settings.get("sequence_voice_enabled", False),
        "agent_name": settings.get("agent_name", "Sarah"),
        "voice_model": settings.get("voice_model", "eleven_turbo_v2_5"),
        "max_call_duration": settings.get("voice_call_max_duration", 300),
    })


@voice_bp.route('/call-history/<int:person_id>', methods=['GET'])
def get_call_history(person_id: int):
    """
    Get voice call history for a lead.

    Args:
        person_id: FUB person ID

    Query params:
        limit: Maximum number of calls to return (default 10, max 50)
    """
    limit = min(int(request.args.get('limit', 10)), 50)

    handler = get_conversation_handler()

    if not handler.supabase:
        return jsonify({"calls": [], "message": "Database not configured"})

    try:
        result = handler.supabase.table("voice_call_logs").select("*").eq(
            "fub_person_id", person_id
        ).order(
            "started_at", desc=True
        ).limit(limit).execute()

        return jsonify({"calls": result.data or []})

    except Exception as e:
        logger.error(f"Error fetching call history: {e}")
        return jsonify({"error": "Failed to fetch call history"}), 500


@voice_bp.route('/test-connection', methods=['POST'])
def test_voice_connection():
    """
    Test endpoint to verify voice AI is working.
    """
    handler = get_conversation_handler()

    return jsonify({
        "status": "ok",
        "handler_initialized": handler is not None,
        "openrouter_configured": bool(handler.openrouter_api_key) if handler else False,
        "active_conversations": len(handler.active_conversations) if handler else 0,
        "socketio_initialized": _socketio is not None,
    })


@voice_bp.route('/respond', methods=['POST'])
def voice_respond():
    """
    Process a transcript and return AI response.

    This is the main endpoint called by the Chrome extension
    when it receives a transcript from Deepgram.

    Request body:
        {
            "person_id": 123,
            "transcript": "What they said",
            "timestamp": 1234567890
        }

    Response:
        {
            "response": "AI response text",
            "action": null or {"type": "end_call", ...}
        }
    """
    import asyncio

    data = request.get_json()
    person_id = data.get('person_id')
    transcript = data.get('transcript', '').strip()

    if not person_id:
        return jsonify({"error": "person_id required"}), 400

    if not transcript:
        return jsonify({"response": "", "action": None})

    handler = get_conversation_handler()

    # Check if conversation exists, if not start one
    if person_id not in handler.active_conversations:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                handler.start_conversation(person_id=person_id)
            )
        finally:
            loop.close()

    # Process transcript
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            handler.process_transcript(
                person_id=person_id,
                transcript=transcript,
            )
        )
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error processing voice respond: {e}")
        return jsonify({
            "response": "Sorry, I didn't catch that. Could you repeat?",
            "action": None
        })
    finally:
        loop.close()


@voice_bp.route('/end-session', methods=['POST'])
def end_voice_session():
    """
    End a voice AI session.

    Called when the Chrome extension detects the call has ended.

    Request body:
        {
            "person_id": 123,
            "reason": "session_ended"
        }
    """
    import asyncio

    data = request.get_json()
    person_id = data.get('person_id')
    reason = data.get('reason', 'normal')

    if not person_id:
        return jsonify({"error": "person_id required"}), 400

    handler = get_conversation_handler()

    loop = asyncio.new_event_loop()
    try:
        conversation = loop.run_until_complete(
            handler.end_conversation(
                person_id=person_id,
                reason=reason,
            )
        )
        return jsonify({
            "status": "ended",
            "person_id": person_id,
            "summary": conversation.summary if conversation else None,
        })
    except Exception as e:
        logger.error(f"Error ending voice session: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        loop.close()


@voice_bp.route('/health', methods=['GET'])
def voice_health():
    """Voice module health check."""
    return jsonify({"status": "healthy", "module": "voice"})
