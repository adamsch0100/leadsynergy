"""
Voice AI Module - Real-time voice conversation handling for FUB call hijacking.

This module provides:
- WebSocket endpoint for real-time voice AI communication (via Flask-SocketIO)
- Voice-specific prompt handling
- Integration with existing AI agent service
"""

from .routes import voice_bp, init_voice_socketio
from .conversation_handler import VoiceConversationHandler
from .voice_prompts import get_voice_system_prompt

__all__ = [
    'voice_bp',
    'init_voice_socketio',
    'VoiceConversationHandler',
    'get_voice_system_prompt',
]
