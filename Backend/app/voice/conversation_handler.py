"""
Voice Conversation Handler - Manages real-time voice AI conversations.

Handles:
- Conversation state management
- AI response generation for voice
- Integration with existing AI agent service
- Call logging and transcription
"""

import logging
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .voice_prompts import (
    get_voice_system_prompt,
    get_first_message,
    build_voice_context,
    VOICE_RESPONSE_GUIDELINES,
)

logger = logging.getLogger(__name__)


class CallState(Enum):
    """State of the voice call."""
    INITIALIZING = "initializing"
    GREETING = "greeting"
    QUALIFYING = "qualifying"
    SCHEDULING = "scheduling"
    CLOSING = "closing"
    ENDED = "ended"


@dataclass
class VoiceConversation:
    """Represents an active voice conversation."""
    person_id: int
    organization_id: Optional[str] = None
    state: CallState = CallState.INITIALIZING
    history: List[Dict[str, str]] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    lead_profile: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = None
    transcript: str = ""
    summary: Optional[str] = None


class VoiceConversationHandler:
    """
    Handles voice conversation state and AI response generation.

    This class manages the flow of a voice call, generating appropriate
    AI responses using the existing LLM infrastructure.
    """

    def __init__(self, supabase_client=None):
        """
        Initialize the voice conversation handler.

        Args:
            supabase_client: Database client for lead data and logging
        """
        self.supabase = supabase_client
        self.active_conversations: Dict[int, VoiceConversation] = {}

        # LLM configuration - use same as text AI
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.openrouter_base_url = "https://openrouter.ai/api/v1"

        # Voice-optimized model (faster responses)
        self.default_model = os.getenv(
            "VOICE_AI_MODEL",
            "anthropic/claude-3-5-haiku-20241022"  # Fast for voice
        )

    async def start_conversation(
        self,
        person_id: int,
        organization_id: Optional[str] = None,
    ) -> VoiceConversation:
        """
        Start a new voice conversation.

        Args:
            person_id: FUB person ID
            organization_id: Organization ID for settings

        Returns:
            VoiceConversation instance
        """
        logger.info(f"Starting voice conversation for person {person_id}")

        # Load lead profile
        lead_profile = await self._load_lead_profile(person_id)

        # Load AI settings
        settings = await self._load_settings(organization_id)

        # Create conversation
        conversation = VoiceConversation(
            person_id=person_id,
            organization_id=organization_id,
            lead_profile=lead_profile,
            settings=settings,
            state=CallState.GREETING,
        )

        self.active_conversations[person_id] = conversation

        logger.info(f"Voice conversation started for person {person_id}")
        return conversation

    async def process_transcript(
        self,
        person_id: int,
        transcript: str,
    ) -> Dict[str, Any]:
        """
        Process a transcript from the lead and generate AI response.

        Args:
            person_id: FUB person ID
            transcript: What the lead said (from Deepgram)

        Returns:
            Dict with 'response' (AI text) and optional 'action'
        """
        conversation = self.active_conversations.get(person_id)
        if not conversation:
            logger.warning(f"No active conversation for person {person_id}")
            return {
                "response": "I'm sorry, I didn't catch that. Could you repeat?",
                "action": None
            }

        # Add to history
        conversation.history.append({
            "role": "user",
            "content": transcript
        })

        # Update transcript
        conversation.transcript += f"\nLead: {transcript}"

        # Generate AI response
        response_text = await self._generate_response(conversation, transcript)

        # Add response to history
        conversation.history.append({
            "role": "assistant",
            "content": response_text
        })

        # Update transcript
        conversation.transcript += f"\nAgent: {response_text}"

        # Check for state transitions
        action = self._check_for_actions(conversation, transcript, response_text)

        # Update state based on conversation flow
        self._update_state(conversation, transcript)

        return {
            "response": response_text,
            "action": action
        }

    async def end_conversation(
        self,
        person_id: int,
        reason: str = "normal",
    ) -> Optional[VoiceConversation]:
        """
        End a voice conversation and save transcript.

        Args:
            person_id: FUB person ID
            reason: Why the call ended

        Returns:
            The ended conversation
        """
        conversation = self.active_conversations.pop(person_id, None)
        if not conversation:
            return None

        conversation.state = CallState.ENDED
        conversation.ended_at = datetime.utcnow()

        # Generate summary
        conversation.summary = await self._generate_summary(conversation)

        # Log to database
        await self._log_conversation(conversation, reason)

        logger.info(
            f"Voice conversation ended for person {person_id}: {reason}"
        )

        return conversation

    async def _generate_response(
        self,
        conversation: VoiceConversation,
        transcript: str,
    ) -> str:
        """
        Generate an AI response for the voice conversation.

        Args:
            conversation: Current conversation state
            transcript: What the lead just said

        Returns:
            AI response text (optimized for voice)
        """
        import httpx

        # Build context
        context = build_voice_context(
            lead_profile=conversation.lead_profile,
            conversation_history=conversation.history[:-1],  # Exclude current
            settings=conversation.settings,
        )

        # Get system prompt
        system_prompt = get_voice_system_prompt(**context)

        # Add response guidelines
        system_prompt += "\n\n" + VOICE_RESPONSE_GUIDELINES

        # Build messages
        messages = [
            {"role": "system", "content": system_prompt}
        ]

        # Add conversation history (last 6 exchanges max for speed)
        for msg in conversation.history[-12:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        # Generate response via OpenRouter
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.openrouter_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.openrouter_api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://leadsynergy.com",
                        "X-Title": "LeadSynergy Voice AI",
                    },
                    json={
                        "model": self.default_model,
                        "messages": messages,
                        "max_tokens": 100,  # Keep responses short for voice
                        "temperature": 0.7,
                    },
                    timeout=10.0,  # Fast timeout for voice
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    logger.error(f"OpenRouter error: {response.status_code}")
                    return "Sorry, I missed that. Could you say that again?"

        except Exception as e:
            logger.error(f"Error generating voice response: {e}")
            return "I'm having trouble hearing you. One more time?"

    def _check_for_actions(
        self,
        conversation: VoiceConversation,
        transcript: str,
        response: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Check if any special actions should be triggered.

        Args:
            conversation: Current conversation
            transcript: What lead said
            response: AI response

        Returns:
            Action dict if action needed, None otherwise
        """
        transcript_lower = transcript.lower()
        response_lower = response.lower()

        # Check for appointment scheduling
        schedule_keywords = [
            "thursday", "friday", "monday", "tuesday", "wednesday",
            "saturday", "sunday", "tomorrow", "next week",
            "works for me", "sounds good", "let's do", "i'm free"
        ]

        if any(kw in transcript_lower for kw in schedule_keywords):
            # Check if response confirms appointment
            if any(word in response_lower for word in ["perfect", "great", "see you", "confirmed"]):
                return {
                    "type": "schedule_appointment",
                    "details": {
                        "transcript_hint": transcript,
                        "response": response
                    }
                }

        # Check for transfer request
        transfer_keywords = [
            "speak to someone else", "talk to a person",
            "real person", "human", "manager", "transfer"
        ]

        if any(kw in transcript_lower for kw in transfer_keywords):
            return {
                "type": "transfer",
                "reason": "lead_requested"
            }

        # Check for end call signals
        end_keywords = [
            "goodbye", "bye", "talk later", "gotta go",
            "not interested", "stop calling", "remove me"
        ]

        if any(kw in transcript_lower for kw in end_keywords):
            return {
                "type": "end_call",
                "reason": "lead_ended" if "bye" in transcript_lower else "not_interested"
            }

        return None

    def _update_state(
        self,
        conversation: VoiceConversation,
        transcript: str,
    ) -> None:
        """
        Update conversation state based on flow.

        Args:
            conversation: Current conversation
            transcript: Latest transcript
        """
        transcript_lower = transcript.lower()

        # State transitions
        if conversation.state == CallState.GREETING:
            # After first exchange, move to qualifying
            if len(conversation.history) >= 2:
                conversation.state = CallState.QUALIFYING

        elif conversation.state == CallState.QUALIFYING:
            # Check for scheduling signals
            schedule_signals = [
                "when", "available", "meet", "show",
                "appointment", "schedule", "time"
            ]
            if any(s in transcript_lower for s in schedule_signals):
                conversation.state = CallState.SCHEDULING

        elif conversation.state == CallState.SCHEDULING:
            # Check for closing signals
            close_signals = [
                "see you", "sounds good", "confirmed",
                "thanks", "bye", "talk soon"
            ]
            if any(s in transcript_lower for s in close_signals):
                conversation.state = CallState.CLOSING

    async def _generate_summary(
        self,
        conversation: VoiceConversation,
    ) -> str:
        """
        Generate a summary of the call for logging.

        Args:
            conversation: Completed conversation

        Returns:
            Summary string
        """
        if not conversation.transcript:
            return "No transcript available"

        # For now, simple summary
        # Could use LLM for better summaries
        num_exchanges = len(conversation.history) // 2
        duration = (conversation.ended_at - conversation.started_at).seconds

        return (
            f"Voice call with {num_exchanges} exchanges over {duration} seconds. "
            f"Final state: {conversation.state.value}"
        )

    async def _load_lead_profile(
        self,
        person_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Load lead profile from database or FUB."""
        if not self.supabase:
            return {"first_name": "there", "lead_type": "buyer"}

        try:
            # Try to get from local cache/database
            result = self.supabase.table("lead_profiles").select("*").eq(
                "fub_person_id", person_id
            ).single().execute()

            if result.data:
                return result.data

        except Exception as e:
            logger.warning(f"Could not load lead profile: {e}")

        return {"first_name": "there", "lead_type": "buyer"}

    async def _load_settings(
        self,
        organization_id: Optional[str],
    ) -> Dict[str, Any]:
        """Load AI agent settings."""
        if not self.supabase or not organization_id:
            return {
                "agent_name": "Sarah",
                "brokerage_name": "our team",
            }

        try:
            result = self.supabase.table("ai_agent_settings").select("*").eq(
                "organization_id", organization_id
            ).single().execute()

            if result.data:
                return result.data

        except Exception as e:
            logger.warning(f"Could not load settings: {e}")

        return {
            "agent_name": "Sarah",
            "brokerage_name": "our team",
        }

    async def _log_conversation(
        self,
        conversation: VoiceConversation,
        reason: str,
    ) -> None:
        """Log the conversation to database."""
        if not self.supabase:
            return

        try:
            self.supabase.table("voice_call_logs").insert({
                "fub_person_id": conversation.person_id,
                "organization_id": conversation.organization_id,
                "started_at": conversation.started_at.isoformat(),
                "ended_at": conversation.ended_at.isoformat() if conversation.ended_at else None,
                "duration_seconds": (
                    (conversation.ended_at - conversation.started_at).seconds
                    if conversation.ended_at else 0
                ),
                "transcript": conversation.transcript,
                "summary": conversation.summary,
                "final_state": conversation.state.value,
                "end_reason": reason,
                "exchange_count": len(conversation.history) // 2,
            }).execute()

            logger.info(f"Voice call logged for person {conversation.person_id}")

        except Exception as e:
            logger.error(f"Failed to log voice call: {e}")
