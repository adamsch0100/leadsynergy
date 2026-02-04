"""
Handoff Monitoring Celery Tasks.

Background tasks that monitor AI->human handoffs to ensure leads don't get abandoned.
"""

import logging
from datetime import datetime
from celery import shared_task
import asyncio

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2)
def check_handoff_fallback(
    self,
    fub_person_id: int,
    conversation_id: str,
    handoff_reason: str,
    organization_id: str,
):
    """
    Check if agent responded after handoff, send fallback if not.

    Runs 3 hours after handoff. If agent hasn't responded, sends:
    "Hey {name}! {agent} is working on {request} for you. Expect to hear from them by end of day!"

    Args:
        fub_person_id: FUB person ID
        conversation_id: Conversation ID
        handoff_reason: Why handoff occurred
        organization_id: Organization ID
    """
    logger.info(f"Checking handoff fallback for person {fub_person_id} (3h after handoff)")

    try:
        from app.ai_agent.handoff_monitor import check_if_agent_responded, send_fallback_message
        from app.database.supabase_client import SupabaseClientSingleton

        supabase = SupabaseClientSingleton.get_instance()

        # Get conversation to find handoff time
        result = supabase.table('ai_conversations').select('*').eq(
            'fub_person_id', fub_person_id
        ).execute()

        if not result.data:
            logger.warning(f"No conversation found for person {fub_person_id}")
            return {"success": False, "error": "Conversation not found"}

        conversation = result.data[0]

        # Check if still in HANDED_OFF state
        if conversation.get('state') != 'handed_off':
            logger.info(f"Conversation {fub_person_id} no longer in HANDED_OFF state, skipping fallback")
            return {"success": False, "reason": "State changed, no longer handed off"}

        # Get handoff time (approximate from last AI message)
        handoff_time_str = conversation.get('last_ai_message_at')
        if not handoff_time_str:
            logger.warning(f"No handoff timestamp found for person {fub_person_id}")
            return {"success": False, "error": "No handoff timestamp"}

        handoff_time = datetime.fromisoformat(handoff_time_str.replace('Z', '+00:00'))

        # Check if agent has responded
        agent_responded = asyncio.run(
            check_if_agent_responded(fub_person_id, handoff_time, supabase)
        )

        if agent_responded:
            logger.info(f"Agent already responded to person {fub_person_id}, no fallback needed")
            return {"success": True, "agent_responded": True}

        # Agent hasn't responded - send fallback
        logger.info(f"Agent hasn't responded to person {fub_person_id}, sending fallback")

        # Get lead info from FUB
        from app.integrations.fub.client import FUBClient
        from app.database.credentials import Credentials

        fub = FUBClient(api_key=Credentials().FUB_API_KEY)
        person = asyncio.run(fub.get_person(fub_person_id))

        if not person:
            logger.error(f"Could not fetch person {fub_person_id} from FUB")
            return {"success": False, "error": "Person not found in FUB"}

        first_name = person.get('firstName', 'there')
        assigned_agent = person.get('assignedTo', {}).get('name', 'our team')

        # Try to extract original request from handoff reason
        original_request = None
        if 'lender' in handoff_reason.lower():
            original_request = "getting those lender intros"
        elif 'showing' in handoff_reason.lower():
            original_request = "scheduling that showing"
        elif 'appointment' in handoff_reason.lower():
            original_request = "setting up that appointment"

        # Send fallback message
        fallback_sent = asyncio.run(
            send_fallback_message(
                fub_person_id=fub_person_id,
                first_name=first_name,
                agent_name=assigned_agent,
                original_request=original_request,
                organization_id=organization_id,
            )
        )

        if fallback_sent:
            logger.info(f"Fallback message sent to person {fub_person_id}")
            return {"success": True, "fallback_sent": True}
        else:
            logger.error(f"Failed to send fallback message to person {fub_person_id}")
            return {"success": False, "error": "Failed to send fallback"}

    except Exception as e:
        logger.error(f"Error in handoff fallback check for person {fub_person_id}: {e}", exc_info=True)
        raise


@shared_task(bind=True, max_retries=2)
def check_handoff_reactivation(
    self,
    fub_person_id: int,
    conversation_id: str,
    handoff_reason: str,
    organization_id: str,
):
    """
    Check if agent responded after handoff, reactivate AI if not.

    Runs 24 hours after handoff. If agent STILL hasn't responded, reactivates AI:
    - Changes state back to QUALIFYING
    - Sends: "Hey {name}! Haven't heard back from our team yet - I'm here if you need anything!"

    Args:
        fub_person_id: FUB person ID
        conversation_id: Conversation ID
        handoff_reason: Why handoff occurred
        organization_id: Organization ID
    """
    logger.info(f"Checking handoff reactivation for person {fub_person_id} (24h after handoff)")

    try:
        from app.ai_agent.handoff_monitor import check_if_agent_responded, reactivate_ai_conversation
        from app.database.supabase_client import SupabaseClientSingleton

        supabase = SupabaseClientSingleton.get_instance()

        # Get conversation
        result = supabase.table('ai_conversations').select('*').eq(
            'fub_person_id', fub_person_id
        ).execute()

        if not result.data:
            logger.warning(f"No conversation found for person {fub_person_id}")
            return {"success": False, "error": "Conversation not found"}

        conversation = result.data[0]

        # Check if still in HANDED_OFF state
        if conversation.get('state') != 'handed_off':
            logger.info(f"Conversation {fub_person_id} no longer in HANDED_OFF state, skipping reactivation")
            return {"success": False, "reason": "State changed, no longer handed off"}

        # Get handoff time
        handoff_time_str = conversation.get('last_ai_message_at')
        if not handoff_time_str:
            logger.warning(f"No handoff timestamp found for person {fub_person_id}")
            return {"success": False, "error": "No handoff timestamp"}

        handoff_time = datetime.fromisoformat(handoff_time_str.replace('Z', '+00:00'))

        # Check if agent has responded
        agent_responded = asyncio.run(
            check_if_agent_responded(fub_person_id, handoff_time, supabase)
        )

        if agent_responded:
            logger.info(f"Agent responded to person {fub_person_id}, no reactivation needed")
            return {"success": True, "agent_responded": True}

        # Agent STILL hasn't responded after 24 hours - reactivate AI
        logger.warning(f"Agent NEVER responded to person {fub_person_id} - reactivating AI")

        # Get lead info
        from app.integrations.fub.client import FUBClient
        from app.database.credentials import Credentials

        fub = FUBClient(api_key=Credentials().FUB_API_KEY)
        person = asyncio.run(fub.get_person(fub_person_id))

        if not person:
            logger.error(f"Could not fetch person {fub_person_id} from FUB")
            return {"success": False, "error": "Person not found in FUB"}

        first_name = person.get('firstName', 'there')

        # Reactivate AI
        reactivated = asyncio.run(
            reactivate_ai_conversation(
                fub_person_id=fub_person_id,
                first_name=first_name,
                reason=handoff_reason,
            )
        )

        if reactivated:
            logger.info(f"AI reactivated for person {fub_person_id}")
            return {"success": True, "ai_reactivated": True}
        else:
            logger.error(f"Failed to reactivate AI for person {fub_person_id}")
            return {"success": False, "error": "Failed to reactivate AI"}

    except Exception as e:
        logger.error(f"Error in handoff reactivation check for person {fub_person_id}: {e}", exc_info=True)
        raise
