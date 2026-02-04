"""Handoff Monitor - Ensures leads don't get abandoned after AI handoff.

When AI hands off to a human agent, this monitors the handoff and:
1. Sends a fallback message if agent doesn't respond within 2-4 hours
2. Reactivates AI if agent doesn't respond within 24 hours

This prevents the "black hole" scenario where AI goes silent and agent never picks up.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class HandoffStatus(Enum):
    """Status of a handoff."""
    PENDING = "pending"  # Waiting for agent response
    AGENT_RESPONDED = "agent_responded"  # Agent took over
    FALLBACK_SENT = "fallback_sent"  # Sent fallback message
    AI_REACTIVATED = "ai_reactivated"  # AI took back over after 24h


async def schedule_handoff_monitoring(
    fub_person_id: int,
    conversation_id: str,
    handoff_reason: str,
    organization_id: str,
):
    """
    Schedule monitoring tasks when a handoff occurs.

    Creates two delayed tasks:
    1. Check at 3 hours - send fallback if agent hasn't responded
    2. Check at 24 hours - reactivate AI if agent hasn't responded

    Args:
        fub_person_id: FUB person ID
        conversation_id: Conversation ID
        handoff_reason: Why the handoff occurred
        organization_id: Organization ID for multi-tenant support
    """
    from app.scheduler.ai_tasks import (
        check_handoff_fallback,
        check_handoff_reactivation,
    )

    logger.info(f"Scheduling handoff monitoring for person {fub_person_id}")

    # Schedule 3-hour fallback check
    check_handoff_fallback.apply_async(
        args=[fub_person_id, conversation_id, handoff_reason, organization_id],
        countdown=3 * 60 * 60,  # 3 hours
    )

    # Schedule 24-hour reactivation check
    check_handoff_reactivation.apply_async(
        args=[fub_person_id, conversation_id, handoff_reason, organization_id],
        countdown=24 * 60 * 60,  # 24 hours
    )

    logger.info(f"Scheduled fallback (3h) and reactivation (24h) checks for person {fub_person_id}")


async def check_if_agent_responded(
    fub_person_id: int,
    handoff_time: datetime,
    supabase_client=None,
) -> bool:
    """
    Check if a human agent has responded after the handoff.

    Looks for messages sent by humans (not AI) after the handoff timestamp.

    Args:
        fub_person_id: FUB person ID
        handoff_time: When the handoff occurred
        supabase_client: Optional Supabase client

    Returns:
        True if agent has responded, False otherwise
    """
    if not supabase_client:
        from app.database.supabase_client import SupabaseClientSingleton
        supabase_client = SupabaseClientSingleton.get_instance()

    try:
        # Get conversation
        result = supabase_client.table('ai_conversations').select('*').eq(
            'fub_person_id', fub_person_id
        ).execute()

        if not result.data:
            logger.warning(f"No conversation found for person {fub_person_id}")
            return False

        conversation = result.data[0]
        conversation_history = conversation.get('conversation_history', [])

        # Check for any outbound messages after handoff that weren't from AI
        for msg in reversed(conversation_history):  # Check most recent first
            msg_time = datetime.fromisoformat(msg.get('timestamp', '').replace('Z', '+00:00'))

            # Only check messages after handoff
            if msg_time <= handoff_time:
                continue

            # Check if this is a human-sent message (outbound but not AI-generated)
            direction = msg.get('direction', '')

            # If we see an outbound message after handoff, it's likely from the agent
            # (AI is silenced when state=HANDED_OFF)
            if direction == 'outbound':
                logger.info(f"Agent responded to person {fub_person_id} at {msg_time}")
                return True

        # Also check FUB API for recent texts/emails from the agent
        from app.database.fub_api_client import FUBApiClient
        from app.utils.constants import Credentials

        fub = FUBApiClient(api_key=Credentials().FUB_API_KEY)

        # Get recent text messages
        texts = fub.get_text_messages_for_person(fub_person_id)
        for text in reversed(texts):  # Most recent first
            sent_time = datetime.fromisoformat(text.get('created', '').replace('Z', '+00:00'))
            if sent_time <= handoff_time:
                continue

            # Outgoing message after handoff = agent responded
            if text.get('direction') == 'outgoing':
                logger.info(f"Agent sent text to person {fub_person_id} via FUB at {sent_time}")
                return True

        logger.info(f"No agent response found for person {fub_person_id} since {handoff_time}")
        return False

    except Exception as e:
        logger.error(f"Error checking if agent responded for person {fub_person_id}: {e}")
        # Default to True to be safe - don't send fallback if we can't verify
        return True


async def send_fallback_message(
    fub_person_id: int,
    first_name: str,
    agent_name: str,
    original_request: str,
    organization_id: str,
):
    """
    Send a fallback message when agent hasn't responded.

    Message format:
    "Hey {first_name}! {agent_name} is working on {original_request} for you.
    Expect to hear from them by end of day. Hang tight!"

    Args:
        fub_person_id: FUB person ID
        first_name: Lead's first name
        agent_name: Human agent's name
        original_request: What the lead asked for (e.g., "getting those lender intros")
        organization_id: Organization ID
    """
    from app.messaging.playwright_sms_service import send_sms_with_auto_credentials

    # Build fallback message
    if original_request:
        message = f"Hey {first_name}! {agent_name} is working on {original_request} for you. Expect to hear from them by end of day. Hang tight!"
    else:
        message = f"Hey {first_name}! {agent_name} is looking into your request and will reach out by end of day. Hang tight!"

    logger.info(f"Sending fallback message to person {fub_person_id}: {message}")

    try:
        # Send via Playwright
        result = await send_sms_with_auto_credentials(
            person_id=fub_person_id,
            message=message,
            organization_id=organization_id,
        )

        if result.get('success'):
            logger.info(f"Fallback message sent successfully to person {fub_person_id}")

            # Update conversation to track that fallback was sent
            from app.database.supabase_client import SupabaseClientSingleton
            supabase = SupabaseClientSingleton.get_instance()

            supabase.table('ai_conversations').update({
                'handoff_fallback_sent_at': datetime.utcnow().isoformat(),
            }).eq('fub_person_id', fub_person_id).execute()

            return True
        else:
            logger.error(f"Failed to send fallback message: {result.get('error')}")
            return False

    except Exception as e:
        logger.error(f"Error sending fallback message to person {fub_person_id}: {e}")
        return False


async def reactivate_ai_conversation(
    fub_person_id: int,
    first_name: str,
    reason: str,
):
    """
    Reactivate AI conversation after 24 hours of no agent response.

    Changes conversation state back to QUALIFYING and sends a re-engagement message.

    Args:
        fub_person_id: FUB person ID
        first_name: Lead's first name
        reason: Original handoff reason
    """
    from app.database.supabase_client import SupabaseClientSingleton
    from app.ai_agent.conversation_manager import ConversationState

    logger.info(f"Reactivating AI for person {fub_person_id} - agent never responded")

    supabase = SupabaseClientSingleton.get_instance()

    try:
        # Change state back to QUALIFYING
        supabase.table('ai_conversations').update({
            'state': ConversationState.QUALIFYING.value,
            'handoff_reactivated_at': datetime.utcnow().isoformat(),
            'handoff_reactivation_reason': f"Agent didn't respond for 24h after handoff: {reason}",
        }).eq('fub_person_id', fub_person_id).execute()

        logger.info(f"AI reactivated for person {fub_person_id} - state changed to QUALIFYING")

        # Send re-engagement message
        from app.messaging.playwright_sms_service import send_sms_with_auto_credentials

        message = f"Hey {first_name}! Haven't heard back from our team yet - I'm here if you need anything in the meantime. What can I help with?"

        result = await send_sms_with_auto_credentials(
            person_id=fub_person_id,
            message=message,
        )

        if result.get('success'):
            logger.info(f"AI reactivation message sent to person {fub_person_id}")
            return True
        else:
            logger.error(f"Failed to send reactivation message: {result.get('error')}")
            return False

    except Exception as e:
        logger.error(f"Error reactivating AI for person {fub_person_id}: {e}")
        return False
