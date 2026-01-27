"""
AI Agent Celery Tasks - Background task processing for the AI sales agent.

Provides asynchronous task execution for:
- Scheduled message sending (follow-ups, nurture sequences)
- New lead welcome sequences
- Appointment reminders
- Re-engagement campaigns
- Batch processing for multiple leads

All tasks respect TCPA compliance and rate limits.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from celery import shared_task
import asyncio

logger = logging.getLogger(__name__)


# ============================================================================
# MESSAGE SENDING TASKS
# ============================================================================

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def send_scheduled_message(
    self,
    message_id: str,
    fub_person_id: int,
    message_content: str,
    channel: str = "sms",
    template_id: str = None,
    variables: Dict[str, Any] = None,
):
    """
    Send a scheduled message to a lead.

    Args:
        message_id: ID of the scheduled_messages record
        fub_person_id: FUB person ID
        message_content: Message text (or None if using template)
        channel: 'sms' or 'email'
        template_id: Optional template to use
        variables: Variables for template rendering
    """
    from app.ai_agent import LeadProfile
    from app.ai_agent.compliance_checker import ComplianceChecker
    from app.messaging.fub_sms_service import FUBSMSService
    from app.database.supabase_client import get_supabase_client

    logger.info(f"Sending scheduled message {message_id} to person {fub_person_id}")

    try:
        supabase = get_supabase_client()
        compliance = ComplianceChecker(supabase)
        sms_service = FUBSMSService()

        # Get lead info from FUB
        from app.fub.fub_client import FUBClient
        fub = FUBClient()
        person_data = fub.get_person(fub_person_id)

        if not person_data:
            logger.error(f"Person {fub_person_id} not found in FUB")
            _mark_message_failed(supabase, message_id, "Person not found")
            return {"success": False, "error": "Person not found"}

        # Build lead profile
        lead_profile = LeadProfile.from_fub_data(person_data)

        # Check compliance
        if channel == "sms":
            compliance_result = asyncio.run(
                compliance.check_send_allowed(
                    phone_number=lead_profile.phone,
                    fub_person_id=fub_person_id,
                )
            )

            if compliance_result.status.value != "allowed":
                logger.warning(f"Compliance blocked: {compliance_result.reason}")
                _mark_message_failed(supabase, message_id, f"Compliance: {compliance_result.reason}")
                return {"success": False, "error": compliance_result.reason}

        # ====================================================================
        # DEDUPLICATION CHECK: Did lead respond since this message was scheduled?
        # Prevents sending automated messages when lead is in active conversation
        # ====================================================================
        try:
            # Check if the scheduled message was cancelled (race condition protection)
            msg_result = supabase.table("scheduled_messages").select("status", "scheduled_for").eq(
                "id", message_id
            ).single().execute()

            if msg_result.data and msg_result.data.get("status") != "pending":
                logger.info(f"[DEDUP] Message {message_id} already {msg_result.data['status']}, skipping")
                return {"success": False, "skipped": True, "reason": "already_processed"}

            # Check if lead responded recently (within last 5 minutes)
            # This catches race conditions where lead responds just as message fires
            conv_result = supabase.table("ai_conversations").select(
                "last_lead_response_at"
            ).eq("fub_person_id", fub_person_id).single().execute()

            if conv_result.data and conv_result.data.get("last_lead_response_at"):
                last_response = datetime.fromisoformat(
                    conv_result.data["last_lead_response_at"].replace('Z', '+00:00')
                )
                minutes_since_response = (datetime.utcnow() - last_response.replace(tzinfo=None)).total_seconds() / 60

                if minutes_since_response < 5:
                    logger.info(
                        f"[DEDUP] Lead {fub_person_id} responded {minutes_since_response:.1f} min ago, "
                        f"skipping scheduled message {message_id}"
                    )
                    _mark_message_skipped(supabase, message_id, "lead_responded_recently")
                    return {"success": False, "skipped": True, "reason": "lead_responded_recently"}

        except Exception as dedup_error:
            # Don't block sending if dedup check fails - just log and continue
            logger.warning(f"[DEDUP] Check failed (continuing): {dedup_error}")

        # Render template if provided
        final_message = message_content
        if template_id and not message_content:
            from app.ai_agent.template_engine import get_template_engine
            engine = get_template_engine()
            final_message = engine.get_message(
                template_id,
                variables or {"first_name": lead_profile.first_name},
                lead_id=str(fub_person_id),
            )

        if not final_message:
            logger.error("No message content to send")
            _mark_message_failed(supabase, message_id, "No message content")
            return {"success": False, "error": "No message content"}

        # Send the message
        if channel == "sms":
            result = sms_service.send_text_message(
                person_id=fub_person_id,
                message=final_message,
            )
        else:
            # Email sending would go here
            from app.email.email_service import EmailService
            email_service = EmailService()
            result = email_service.send_email(
                to_email=lead_profile.email,
                subject="From your real estate agent",
                body=final_message,
                fub_person_id=fub_person_id,
            )

        if result.get("success"):
            _mark_message_sent(supabase, message_id)
            logger.info(f"Message {message_id} sent successfully")
            return {"success": True, "message_id": message_id}
        else:
            error = result.get("error", "Unknown error")
            _mark_message_failed(supabase, message_id, error)
            return {"success": False, "error": error}

    except Exception as e:
        logger.error(f"Error sending message {message_id}: {e}", exc_info=True)
        raise  # Let Celery retry


@shared_task(bind=True, max_retries=3)
def process_ai_response(
    self,
    fub_person_id: int,
    incoming_message: str,
    message_id: str = None,
    channel: str = "sms",
):
    """
    Process an incoming message with the AI agent and send response.

    This is the main task for handling inbound messages asynchronously.

    Args:
        fub_person_id: FUB person ID
        incoming_message: The message from the lead
        message_id: Optional FUB message ID
        channel: Communication channel
    """
    from app.ai_agent import (
        AIAgentService,
        AgentSettings,
        LeadProfile,
        ProcessingResult,
    )
    from app.database.supabase_client import get_supabase_client
    from app.fub.fub_client import FUBClient
    from app.messaging.fub_sms_service import FUBSMSService

    logger.info(f"Processing AI response for person {fub_person_id}")

    try:
        supabase = get_supabase_client()
        fub = FUBClient()
        sms_service = FUBSMSService()

        # Get person data from FUB
        person_data = fub.get_person(fub_person_id)
        if not person_data:
            logger.error(f"Person {fub_person_id} not found")
            return {"success": False, "error": "Person not found"}

        # Get conversation history
        conversation_history = _get_conversation_history(supabase, fub_person_id)

        # Get stored conversation state
        conversation_context = _get_conversation_context(supabase, fub_person_id)

        # Build rich lead profile
        additional_data = _get_additional_lead_data(supabase, fub_person_id)
        lead_profile = LeadProfile.from_fub_data(person_data, additional_data)

        # Initialize agent service
        agent = AIAgentService(
            settings=AgentSettings(),
            supabase_client=supabase,
        )

        # Process the message
        response = asyncio.run(
            agent.process_message(
                message=incoming_message,
                lead_profile=lead_profile,
                conversation_context=conversation_context,
                conversation_history=conversation_history,
                channel=channel,
                fub_person_id=fub_person_id,
            )
        )

        # Handle response
        if response.result == ProcessingResult.SUCCESS:
            # Send the response
            if channel == "sms" and response.response_text:
                send_result = sms_service.send_text_message(
                    person_id=fub_person_id,
                    message=response.response_text,
                )

                if not send_result.get("success"):
                    logger.error(f"Failed to send response: {send_result.get('error')}")

            # Save conversation state
            _save_conversation_state(supabase, fub_person_id, response)

            # Update lead score in FUB if changed
            if response.lead_score_delta != 0:
                _update_lead_score(fub, fub_person_id, response.lead_score_delta)

            # Handle handoff if needed
            if response.should_handoff:
                _trigger_handoff(fub, supabase, fub_person_id, response.handoff_reason)

            # Log the interaction
            _log_ai_interaction(supabase, fub_person_id, incoming_message, response)

        elif response.result == ProcessingResult.COMPLIANCE_BLOCKED:
            logger.warning(f"Compliance blocked response to {fub_person_id}")

        elif response.result == ProcessingResult.HANDOFF_TRIGGERED:
            _trigger_handoff(fub, supabase, fub_person_id, response.handoff_reason)

        return response.to_dict()

    except Exception as e:
        logger.error(f"Error processing AI response: {e}", exc_info=True)
        raise


# ============================================================================
# SEQUENCE TASKS
# ============================================================================

@shared_task(bind=True)
def start_new_lead_sequence(
    self,
    fub_person_id: int,
    sequence_type: str = "new_lead_24h",
):
    """
    Start an automated follow-up sequence for a new lead.

    Args:
        fub_person_id: FUB person ID
        sequence_type: Type of sequence to start
    """
    from app.database.supabase_client import get_supabase_client

    logger.info(f"Starting {sequence_type} sequence for person {fub_person_id}")

    supabase = get_supabase_client()

    # Check if already in a sequence
    existing = supabase.table("scheduled_messages").select("id").eq(
        "fub_person_id", fub_person_id
    ).eq("status", "pending").execute()

    if existing.data:
        logger.info(f"Person {fub_person_id} already has pending messages, skipping")
        return {"success": False, "reason": "Already in sequence"}

    # Get sequence definition
    sequence = SEQUENCES.get(sequence_type)
    if not sequence:
        logger.error(f"Unknown sequence type: {sequence_type}")
        return {"success": False, "error": "Unknown sequence"}

    # Schedule all messages in the sequence
    now = datetime.utcnow()
    scheduled_count = 0

    for step in sequence["steps"]:
        scheduled_time = now + timedelta(minutes=step["delay_minutes"])

        message_data = {
            "fub_person_id": fub_person_id,
            "channel": step.get("channel", "sms"),
            "message_template": step.get("template_id"),
            "message_content": step.get("content"),
            "scheduled_for": scheduled_time.isoformat(),
            "status": "pending",
            "sequence_type": sequence_type,
            "sequence_step": step["step"],
        }

        result = supabase.table("scheduled_messages").insert(message_data).execute()

        if result.data:
            # Schedule the Celery task
            send_scheduled_message.apply_async(
                kwargs={
                    "message_id": result.data[0]["id"],
                    "fub_person_id": fub_person_id,
                    "message_content": step.get("content"),
                    "channel": step.get("channel", "sms"),
                    "template_id": step.get("template_id"),
                },
                eta=scheduled_time,
            )
            scheduled_count += 1

    logger.info(f"Scheduled {scheduled_count} messages for person {fub_person_id}")
    return {"success": True, "scheduled_count": scheduled_count}


@shared_task(bind=True)
def start_nurture_sequence(
    self,
    fub_person_id: int,
    cadence_type: str = "8x8",
):
    """
    Start a long-term nurture sequence (8x8 or similar).

    Args:
        fub_person_id: FUB person ID
        cadence_type: Type of nurture cadence
    """
    from app.database.supabase_client import get_supabase_client

    logger.info(f"Starting {cadence_type} nurture for person {fub_person_id}")

    supabase = get_supabase_client()

    # Get nurture sequence
    sequence = NURTURE_SEQUENCES.get(cadence_type)
    if not sequence:
        return {"success": False, "error": "Unknown cadence type"}

    now = datetime.utcnow()
    scheduled_count = 0

    for step in sequence["steps"]:
        scheduled_time = now + timedelta(days=step["delay_days"])

        message_data = {
            "fub_person_id": fub_person_id,
            "channel": step.get("channel", "email"),
            "message_template": step.get("template_id"),
            "scheduled_for": scheduled_time.isoformat(),
            "status": "pending",
            "sequence_type": cadence_type,
            "sequence_step": step["step"],
        }

        result = supabase.table("scheduled_messages").insert(message_data).execute()

        if result.data:
            send_scheduled_message.apply_async(
                kwargs={
                    "message_id": result.data[0]["id"],
                    "fub_person_id": fub_person_id,
                    "message_content": None,
                    "channel": step.get("channel", "email"),
                    "template_id": step.get("template_id"),
                },
                eta=scheduled_time,
            )
            scheduled_count += 1

    return {"success": True, "scheduled_count": scheduled_count}


@shared_task(bind=True)
def cancel_lead_sequences(self, fub_person_id: int, reason: str = None):
    """
    Cancel all pending scheduled messages for a lead.

    Use when lead converts, opts out, or is handed off.
    Also schedules re-engagement check for later.

    This is a CRITICAL function for the autonomous AI agent:
    - Called whenever a lead responds (SMS, email, phone)
    - Prevents automated messages from being sent while in active conversation
    - Schedules check_dormant_lead to restart automation if lead goes silent

    Args:
        fub_person_id: FUB person ID
        reason: Reason for cancellation
    """
    from app.database.supabase_client import get_supabase_client

    logger.info(f"[CANCEL] Cancelling sequences for person {fub_person_id} (reason: {reason or 'lead_responded'})")

    supabase = get_supabase_client()
    total_cancelled = 0

    # Cancel from scheduled_messages table
    try:
        result = supabase.table("scheduled_messages").update({
            "status": "cancelled",
            "cancelled_reason": reason or "lead_responded",
            "cancelled_at": datetime.utcnow().isoformat(),
        }).eq("fub_person_id", fub_person_id).eq("status", "pending").execute()

        count = len(result.data) if result.data else 0
        total_cancelled += count
        if count > 0:
            logger.info(f"[CANCEL] Cancelled {count} scheduled_messages for person {fub_person_id}")
    except Exception as e:
        logger.warning(f"[CANCEL] Error cancelling scheduled_messages: {e}")

    # Also cancel from ai_scheduled_followups table if it exists
    try:
        result = supabase.table("ai_scheduled_followups").update({
            "status": "cancelled",
            "cancelled_reason": reason or "lead_responded",
            "cancelled_at": datetime.utcnow().isoformat(),
        }).eq("fub_person_id", fub_person_id).eq("status", "pending").execute()

        count = len(result.data) if result.data else 0
        total_cancelled += count
        if count > 0:
            logger.info(f"[CANCEL] Cancelled {count} ai_scheduled_followups for person {fub_person_id}")
    except Exception as e:
        # Table might not exist, that's OK
        logger.debug(f"[CANCEL] ai_scheduled_followups table: {e}")

    logger.info(f"[CANCEL] Total cancelled: {total_cancelled} pending follow-ups for person {fub_person_id}")

    # Update conversation to track last lead response
    try:
        supabase.table("ai_conversations").update({
            "last_human_message_at": datetime.utcnow().isoformat(),
            "last_lead_response_at": datetime.utcnow().isoformat(),
            "state": "engaged",  # Mark as engaged (active conversation)
        }).eq("fub_person_id", fub_person_id).execute()
    except Exception as e:
        logger.warning(f"[CANCEL] Error updating ai_conversations: {e}")

    # Schedule re-engagement check for later (24 hours by default)
    # This will restart automation if the lead goes quiet
    check_dormant_lead.apply_async(
        kwargs={"fub_person_id": fub_person_id},
        countdown=86400,  # 24 hours
    )
    logger.info(f"[CANCEL] Scheduled re-engagement check in 24h for person {fub_person_id}")

    return {"success": True, "cancelled_count": total_cancelled}


@shared_task(bind=True)
def check_dormant_lead(self, fub_person_id: int):
    """
    Check if a lead has gone dormant and needs re-engagement.

    This task is scheduled after cancelling sequences. It checks:
    1. Has the lead responded since the last AI message?
    2. If not, should we restart nurture automation?
    3. How many re-engagement attempts have been made?

    Args:
        fub_person_id: FUB person ID
    """
    from app.database.supabase_client import get_supabase_client
    from app.ai_agent.settings_service import get_settings_service

    logger.info(f"Checking if lead {fub_person_id} is dormant")

    supabase = get_supabase_client()

    # Get conversation state
    conv_result = supabase.table("ai_conversations").select("*").eq(
        "fub_person_id", fub_person_id
    ).single().execute()

    if not conv_result.data:
        logger.warning(f"No conversation found for person {fub_person_id}")
        return {"success": False, "reason": "No conversation found"}

    conversation = conv_result.data

    # Skip if handed off, completed, or opted out
    if conversation.get("state") in ["handed_off", "completed"]:
        logger.info(f"Lead {fub_person_id} is {conversation['state']}, skipping re-engagement")
        return {"success": True, "skipped": True, "reason": conversation["state"]}

    # Check opt-out status
    consent_result = supabase.table("sms_consent").select("opted_out").eq(
        "fub_person_id", fub_person_id
    ).single().execute()

    if consent_result.data and consent_result.data.get("opted_out"):
        logger.info(f"Lead {fub_person_id} opted out, skipping re-engagement")
        return {"success": True, "skipped": True, "reason": "opted_out"}

    # Get settings for re-engagement config
    user_id = conversation.get("user_id")
    org_id = conversation.get("organization_id")

    settings_service = get_settings_service(supabase)
    import asyncio
    settings = asyncio.run(settings_service.get_settings(user_id, org_id))

    if not settings.re_engagement_enabled:
        logger.info(f"Re-engagement disabled for org {org_id}")
        return {"success": True, "skipped": True, "reason": "re_engagement_disabled"}

    # Check when lead last responded
    last_response = conversation.get("last_human_message_at")
    last_ai_message = conversation.get("last_ai_message_at")

    if not last_ai_message:
        # No AI message sent yet, skip
        return {"success": True, "skipped": True, "reason": "no_ai_message"}

    last_ai_dt = datetime.fromisoformat(last_ai_message.replace('Z', '+00:00'))

    # If lead responded after last AI message, they're engaged - check again later
    if last_response:
        last_response_dt = datetime.fromisoformat(last_response.replace('Z', '+00:00'))
        if last_response_dt > last_ai_dt:
            # Lead responded, schedule another check
            logger.info(f"Lead {fub_person_id} still engaged, scheduling next check")
            check_dormant_lead.apply_async(
                kwargs={"fub_person_id": fub_person_id},
                countdown=settings.quiet_hours_before_re_engage * 3600,
            )
            return {"success": True, "still_engaged": True}

    # Calculate hours since last AI message
    hours_since_ai = (datetime.utcnow() - last_ai_dt.replace(tzinfo=None)).total_seconds() / 3600

    # Count re-engagement attempts
    re_engage_count = conversation.get("re_engagement_count", 0)

    logger.info(f"Lead {fub_person_id}: {hours_since_ai:.1f}h since AI msg, {re_engage_count} re-engage attempts")

    # Check if lead is dormant (no response for X hours)
    if hours_since_ai >= settings.quiet_hours_before_re_engage:
        # Lead is dormant - decide action
        if re_engage_count >= settings.re_engagement_max_attempts:
            # Max attempts reached, move to long-term nurture
            logger.info(f"Moving lead {fub_person_id} to long-term nurture after {re_engage_count} attempts")

            supabase.table("ai_conversations").update({
                "state": "nurture",
            }).eq("fub_person_id", fub_person_id).execute()

            # Start long-term nurture sequence
            start_nurture_sequence.delay(
                fub_person_id=fub_person_id,
                cadence_type="monthly",
            )

            return {"success": True, "action": "moved_to_nurture"}

        else:
            # Send re-engagement message
            logger.info(f"Sending re-engagement message {re_engage_count + 1} to lead {fub_person_id}")

            # Increment re-engagement count
            supabase.table("ai_conversations").update({
                "re_engagement_count": re_engage_count + 1,
            }).eq("fub_person_id", fub_person_id).execute()

            # Schedule re-engagement message
            send_re_engagement_message.delay(
                fub_person_id=fub_person_id,
                attempt_number=re_engage_count + 1,
            )

            # Schedule next dormancy check
            check_dormant_lead.apply_async(
                kwargs={"fub_person_id": fub_person_id},
                countdown=settings.quiet_hours_before_re_engage * 3600,
            )

            return {"success": True, "action": "re_engagement_sent", "attempt": re_engage_count + 1}

    # Not dormant yet, schedule another check
    remaining_hours = settings.quiet_hours_before_re_engage - hours_since_ai
    check_dormant_lead.apply_async(
        kwargs={"fub_person_id": fub_person_id},
        countdown=int(remaining_hours * 3600),
    )

    return {"success": True, "action": "waiting", "hours_remaining": remaining_hours}


@shared_task(bind=True)
def send_re_engagement_message(self, fub_person_id: int, attempt_number: int = 1):
    """
    Send a re-engagement message to a dormant lead.

    Respects the lead's channel preference:
    - Uses preferred channel first (sms, email, call)
    - Falls back to other channels if preferred is unavailable
    - Respects channel reduction requests (less frequent on that channel)

    Args:
        fub_person_id: FUB person ID
        attempt_number: Which re-engagement attempt this is (1, 2, 3...)
    """
    from app.database.supabase_client import get_supabase_client
    from app.messaging.fub_sms_service import FUBSMSService
    from app.ai_agent.template_engine import get_template_engine
    from app.ai_agent.compliance_checker import ComplianceChecker
    from app.fub.fub_client import FUBClient
    from app.ai_agent.settings_service import get_settings_service
    import asyncio

    logger.info(f"Sending re-engagement message #{attempt_number} to person {fub_person_id}")

    supabase = get_supabase_client()
    sms_service = FUBSMSService()
    template_engine = get_template_engine()
    fub = FUBClient()

    # Get person data
    person_data = fub.get_person(fub_person_id)
    if not person_data:
        return {"success": False, "error": "Person not found"}

    first_name = person_data.get("firstName", "there")
    phones = person_data.get("phones", [])
    emails = person_data.get("emails", [])
    phone = phones[0].get("value") if phones else None
    email = emails[0].get("value") if emails else None

    # Get conversation to check channel preference
    conv_result = supabase.table("ai_conversations").select(
        "preferred_channel", "channel_reduction", "user_id", "organization_id"
    ).eq("fub_person_id", fub_person_id).single().execute()

    preferred_channel = "sms"  # Default
    channel_reduction = None
    user_id = None
    org_id = None

    if conv_result.data:
        preferred_channel = conv_result.data.get("preferred_channel") or "sms"
        channel_reduction = conv_result.data.get("channel_reduction")
        user_id = conv_result.data.get("user_id")
        org_id = conv_result.data.get("organization_id")

    # Get settings for allowed re-engagement channels
    settings_service = get_settings_service(supabase)
    settings = asyncio.run(settings_service.get_settings(user_id, org_id))

    # Determine which channel to use (smart routing)
    channel = _determine_re_engagement_channel(
        preferred_channel=preferred_channel,
        channel_reduction=channel_reduction,
        attempt_number=attempt_number,
        has_phone=bool(phone),
        has_email=bool(email),
        allowed_channels=settings.re_engagement_channels,
    )

    logger.info(f"Using channel '{channel}' for re-engagement (preferred: {preferred_channel}, reduction: {channel_reduction})")

    # Handle based on channel
    if channel == "sms":
        if not phone:
            logger.warning(f"No phone for SMS, falling back to email")
            channel = "email" if email else None

        if channel == "sms":
            # Check SMS compliance
            compliance = ComplianceChecker(supabase)
            compliance_result = asyncio.run(
                compliance.check_send_allowed(phone_number=phone, fub_person_id=fub_person_id)
            )

            if compliance_result.status.value != "allowed":
                logger.warning(f"SMS compliance blocked, trying email")
                channel = "email" if email else None

    if channel == "email" and not email:
        logger.warning(f"No email address, falling back to SMS")
        channel = "sms" if phone else None

    if channel == "call":
        # For now, create a task for human to call
        # Future: integrate with voice AI
        logger.info(f"Call preference - creating callback task")
        fub.create_task(
            person_id=fub_person_id,
            title="Re-engagement callback requested",
            description=f"Lead prefers phone calls. Re-engagement attempt #{attempt_number}",
            due_date=(datetime.utcnow() + timedelta(hours=4)).isoformat(),
        )
        return {"success": True, "channel": "call", "action": "task_created"}

    if not channel:
        return {"success": False, "error": "No available channel for re-engagement"}

    # Get appropriate re-engagement template based on attempt number and channel
    template_map = {
        "sms": {
            1: "re_engage_gentle",
            2: "re_engage_value",
            3: "re_engage_final",
        },
        "email": {
            1: "email_re_engage_gentle",
            2: "email_re_engage_value",
            3: "email_re_engage_final",
        },
    }
    template_id = template_map.get(channel, template_map["sms"]).get(attempt_number, "re_engage_gentle")

    # Get message
    message = template_engine.get_message(
        template_id,
        {"first_name": first_name},
        lead_id=str(fub_person_id),
    )

    if not message:
        # Fallback messages by channel
        if channel == "sms":
            fallbacks = {
                1: f"Hey {first_name}! Just checking in - still thinking about your next move? I'm here whenever you're ready!",
                2: f"Hi {first_name}! Saw some new listings that might interest you. Want me to send them over?",
                3: f"Hey {first_name}, I don't want to bug you! Just wanted you to know I'm here if you ever have questions. No pressure!",
            }
        else:  # email
            fallbacks = {
                1: f"Hi {first_name},\n\nJust checking in to see how your home search is going! Let me know if you have any questions or want to see some new listings.\n\nBest,\nYour Agent",
                2: f"Hi {first_name},\n\nI came across some properties that might interest you based on what you're looking for. Would you like me to send you the details?\n\nBest,\nYour Agent",
                3: f"Hi {first_name},\n\nI hope you're doing well! I'm still here whenever you're ready to continue your home search. No rush - just know I'm happy to help.\n\nBest,\nYour Agent",
            }
        message = fallbacks.get(attempt_number, fallbacks[1])

    # Send message based on channel
    if channel == "sms":
        result = sms_service.send_text_message(
            person_id=fub_person_id,
            message=message,
        )
    else:  # email
        from app.email.email_service import EmailService
        email_service = EmailService()
        result = email_service.send_email(
            to_email=email,
            subject=f"Quick check-in from your real estate agent",
            body=message,
            fub_person_id=fub_person_id,
        )

    if result.get("success"):
        # Update last AI message timestamp
        supabase.table("ai_conversations").update({
            "last_ai_message_at": datetime.utcnow().isoformat(),
        }).eq("fub_person_id", fub_person_id).execute()

        # Log the message
        supabase.table("ai_message_log").insert({
            "fub_person_id": fub_person_id,
            "direction": "outbound",
            "channel": channel,
            "message_content": message,
            "intent_detected": f"re_engagement_{attempt_number}",
            "created_at": datetime.utcnow().isoformat(),
        }).execute()

        logger.info(f"Re-engagement message #{attempt_number} sent via {channel} to {fub_person_id}")

    return {**result, "channel": channel}


def _determine_re_engagement_channel(
    preferred_channel: str,
    channel_reduction: str,
    attempt_number: int,
    has_phone: bool,
    has_email: bool,
    allowed_channels: list,
) -> str:
    """
    Determine the best channel for re-engagement.

    Smart routing logic:
    1. Use preferred channel first (if available)
    2. If preferred channel has reduction request, use it less frequently
    3. Alternate channels on subsequent attempts for better coverage
    4. Respect allowed channels from settings

    Returns:
        Channel to use ('sms', 'email', 'call', or None)
    """
    # Filter to only available channels
    available = []
    if has_phone and "sms" in allowed_channels:
        available.append("sms")
    if has_email and "email" in allowed_channels:
        available.append("email")
    if has_phone and "call" in allowed_channels:
        available.append("call")

    if not available:
        return None

    # If preferred channel is "call", schedule callback
    if preferred_channel == "call" and "call" in available:
        return "call"

    # If there's a channel reduction request, use that channel less
    if channel_reduction:
        # Only use reduced channel on first attempt, alternate after
        if channel_reduction in available and attempt_number > 1:
            # Try preferred first, then others
            if preferred_channel in available and preferred_channel != channel_reduction:
                return preferred_channel
            # Get alternate channel
            alternates = [c for c in available if c != channel_reduction]
            if alternates:
                return alternates[0]

    # Use preferred channel if available
    if preferred_channel in available:
        return preferred_channel

    # Fall back to first available
    return available[0] if available else None


# ============================================================================
# APPOINTMENT TASKS
# ============================================================================

@shared_task(bind=True)
def send_appointment_reminder(
    self,
    appointment_id: str,
    reminder_type: str = "day_before",
):
    """
    Send appointment reminder to lead.

    Args:
        appointment_id: ID of the appointment
        reminder_type: 'day_before', 'hour_before', etc.
    """
    from app.database.supabase_client import get_supabase_client
    from app.messaging.fub_sms_service import FUBSMSService
    from app.ai_agent.template_engine import get_template_engine

    logger.info(f"Sending {reminder_type} reminder for appointment {appointment_id}")

    supabase = get_supabase_client()
    sms_service = FUBSMSService()
    template_engine = get_template_engine()

    # Get appointment details
    apt_result = supabase.table("ai_appointments").select("*").eq(
        "id", appointment_id
    ).single().execute()

    if not apt_result.data:
        logger.error(f"Appointment {appointment_id} not found")
        return {"success": False, "error": "Appointment not found"}

    appointment = apt_result.data

    # Check if already reminded
    if appointment.get("reminder_sent"):
        logger.info(f"Reminder already sent for {appointment_id}")
        return {"success": True, "already_sent": True}

    # Get lead info
    from app.fub.fub_client import FUBClient
    fub = FUBClient()
    person = fub.get_person(appointment["fub_person_id"])

    if not person:
        return {"success": False, "error": "Person not found"}

    # Format appointment time
    apt_time = datetime.fromisoformat(appointment["scheduled_at"])
    formatted_date = apt_time.strftime("%A, %B %d")
    formatted_time = apt_time.strftime("%I:%M %p")

    # Get reminder message
    message = template_engine.get_confirmation_message(
        appointment_date=formatted_date,
        appointment_time=formatted_time,
        first_name=person.get("firstName", "there"),
    )

    # Send reminder
    result = sms_service.send_text_message(
        person_id=appointment["fub_person_id"],
        message=message,
    )

    if result.get("success"):
        # Mark as reminded
        supabase.table("ai_appointments").update({
            "reminder_sent": True,
            "reminder_sent_at": datetime.utcnow().isoformat(),
        }).eq("id", appointment_id).execute()

    return result


@shared_task(bind=True)
def schedule_appointment_reminders(self, appointment_id: str):
    """
    Schedule all reminders for an appointment.

    Args:
        appointment_id: ID of the appointment
    """
    from app.database.supabase_client import get_supabase_client

    supabase = get_supabase_client()

    # Get appointment
    apt_result = supabase.table("ai_appointments").select("*").eq(
        "id", appointment_id
    ).single().execute()

    if not apt_result.data:
        return {"success": False, "error": "Appointment not found"}

    appointment = apt_result.data
    apt_time = datetime.fromisoformat(appointment["scheduled_at"])

    # Schedule day-before reminder
    day_before = apt_time - timedelta(days=1)
    if day_before > datetime.utcnow():
        send_appointment_reminder.apply_async(
            kwargs={
                "appointment_id": appointment_id,
                "reminder_type": "day_before",
            },
            eta=day_before,
        )

    # Schedule hour-before reminder
    hour_before = apt_time - timedelta(hours=1)
    if hour_before > datetime.utcnow():
        send_appointment_reminder.apply_async(
            kwargs={
                "appointment_id": appointment_id,
                "reminder_type": "hour_before",
            },
            eta=hour_before,
        )

    return {"success": True}


# ============================================================================
# BATCH PROCESSING TASKS
# ============================================================================

@shared_task(bind=True)
def process_pending_messages(self):
    """
    Process all pending scheduled messages that are due.

    This is a periodic task that runs every minute.
    """
    from app.database.supabase_client import get_supabase_client

    supabase = get_supabase_client()
    now = datetime.utcnow()

    # Get all due messages
    result = supabase.table("scheduled_messages").select("*").eq(
        "status", "pending"
    ).lte("scheduled_for", now.isoformat()).limit(100).execute()

    if not result.data:
        return {"processed": 0}

    processed = 0
    for message in result.data:
        try:
            send_scheduled_message.delay(
                message_id=message["id"],
                fub_person_id=message["fub_person_id"],
                message_content=message.get("message_content"),
                channel=message.get("channel", "sms"),
                template_id=message.get("message_template"),
            )
            processed += 1
        except Exception as e:
            logger.error(f"Error queueing message {message['id']}: {e}")

    logger.info(f"Queued {processed} pending messages")
    return {"processed": processed}


@shared_task(bind=True)
def cleanup_old_messages(self, days_old: int = 30):
    """
    Clean up old completed/cancelled messages.

    Args:
        days_old: Delete messages older than this many days
    """
    from app.database.supabase_client import get_supabase_client

    supabase = get_supabase_client()
    cutoff = datetime.utcnow() - timedelta(days=days_old)

    # Delete old sent/cancelled messages
    result = supabase.table("scheduled_messages").delete().in_(
        "status", ["sent", "cancelled"]
    ).lt("created_at", cutoff.isoformat()).execute()

    deleted = len(result.data) if result.data else 0
    logger.info(f"Cleaned up {deleted} old messages")

    return {"deleted": deleted}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _mark_message_sent(supabase, message_id: str):
    """Mark a scheduled message as sent."""
    supabase.table("scheduled_messages").update({
        "status": "sent",
        "sent_at": datetime.utcnow().isoformat(),
    }).eq("id", message_id).execute()


def _mark_message_failed(supabase, message_id: str, error: str):
    """Mark a scheduled message as failed."""
    supabase.table("scheduled_messages").update({
        "status": "failed",
        "error_message": error,
        "failed_at": datetime.utcnow().isoformat(),
    }).eq("id", message_id).execute()


def _mark_message_skipped(supabase, message_id: str, reason: str):
    """Mark a scheduled message as skipped (deduplication)."""
    supabase.table("scheduled_messages").update({
        "status": "skipped",
        "skipped_reason": reason,
        "skipped_at": datetime.utcnow().isoformat(),
    }).eq("id", message_id).execute()


def _get_conversation_history(supabase, fub_person_id: int) -> List[Dict]:
    """Get conversation history for a lead."""
    result = supabase.table("ai_message_log").select("*").eq(
        "fub_person_id", fub_person_id
    ).order("created_at", desc=True).limit(20).execute()

    if result.data:
        # Reverse to get chronological order
        return list(reversed(result.data))
    return []


def _get_conversation_context(supabase, fub_person_id: int):
    """Get stored conversation context for a lead."""
    from app.ai_agent import ConversationContext, ConversationState

    result = supabase.table("ai_conversations").select("*").eq(
        "fub_person_id", fub_person_id
    ).single().execute()

    if result.data:
        data = result.data
        return ConversationContext(
            fub_person_id=fub_person_id,
            state=ConversationState(data.get("state", "initial")),
            qualification_data=data.get("qualification_data", {}),
        )

    return None


def _get_additional_lead_data(supabase, fub_person_id: int) -> Dict:
    """Get additional lead data from our database."""
    result = supabase.table("ai_conversations").select("*").eq(
        "fub_person_id", fub_person_id
    ).single().execute()

    if result.data:
        return {
            "lead_score": result.data.get("lead_score", 0),
            "timeline": result.data.get("qualification_data", {}).get("timeline"),
            "motivation": result.data.get("qualification_data", {}).get("motivation"),
            "previous_objections": result.data.get("objection_history", []),
            "objection_count": len(result.data.get("objection_history", [])),
            **result.data.get("qualification_data", {}),
        }

    return {}


def _save_conversation_state(supabase, fub_person_id: int, response):
    """Save conversation state after processing."""
    now = datetime.utcnow().isoformat()

    # Upsert conversation record
    data = {
        "fub_person_id": fub_person_id,
        "state": response.conversation_state,
        "lead_score": response.lead_score,
        "last_ai_message_at": now,
        "updated_at": now,
    }

    if response.extracted_info:
        data["qualification_data"] = response.extracted_info

    # Check if record exists
    existing = supabase.table("ai_conversations").select("id").eq(
        "fub_person_id", fub_person_id
    ).single().execute()

    if existing.data:
        supabase.table("ai_conversations").update(data).eq(
            "fub_person_id", fub_person_id
        ).execute()
    else:
        data["created_at"] = now
        supabase.table("ai_conversations").insert(data).execute()


def _update_lead_score(fub_client, fub_person_id: int, delta: int):
    """Update lead score in FUB (via tags or custom field)."""
    try:
        # Add score-related tag
        if delta > 0:
            fub_client.add_tag(fub_person_id, "ai_engaged")
        elif delta < -5:
            fub_client.add_tag(fub_person_id, "ai_cooling")
    except Exception as e:
        logger.error(f"Error updating lead score: {e}")


def _trigger_handoff(fub_client, supabase, fub_person_id: int, reason: str):
    """Trigger handoff to human agent."""
    logger.info(f"Triggering handoff for {fub_person_id}: {reason}")

    try:
        # Create task in FUB for agent follow-up
        fub_client.create_task(
            person_id=fub_person_id,
            title="AI Handoff - Lead needs human follow-up",
            description=f"The AI agent has handed off this lead.\n\nReason: {reason}",
            due_date=(datetime.utcnow() + timedelta(hours=1)).isoformat(),
        )

        # Add handoff tag
        fub_client.add_tag(fub_person_id, "ai_handoff")

        # Update conversation state
        supabase.table("ai_conversations").update({
            "state": "handed_off",
            "handoff_reason": reason,
            "handoff_at": datetime.utcnow().isoformat(),
        }).eq("fub_person_id", fub_person_id).execute()

        # Cancel any pending automated messages
        cancel_lead_sequences.delay(fub_person_id, f"Handoff: {reason}")

    except Exception as e:
        logger.error(f"Error triggering handoff: {e}")


def _log_ai_interaction(supabase, fub_person_id: int, incoming: str, response):
    """Log AI interaction for analytics and debugging."""
    supabase.table("ai_message_log").insert({
        "fub_person_id": fub_person_id,
        "direction": "inbound",
        "content": incoming,
        "channel": "sms",
        "created_at": datetime.utcnow().isoformat(),
    }).execute()

    if response.response_text:
        supabase.table("ai_message_log").insert({
            "fub_person_id": fub_person_id,
            "direction": "outbound",
            "content": response.response_text,
            "channel": "sms",
            "ai_model": response.model_used,
            "detected_intent": response.detected_intent,
            "detected_sentiment": response.detected_sentiment,
            "conversation_state": response.conversation_state,
            "created_at": datetime.utcnow().isoformat(),
        }).execute()


# ============================================================================
# SEQUENCE DEFINITIONS
# ============================================================================
#
# Research backing these cadences:
# - MIT Study: 21x higher conversion within 5 minutes (speed critical)
# - LeadSimple: 78% of sales go to first responder
# - Industry data: 8-12 touchpoints needed to close a deal
# - Robert Slack mega-team: 45-day campaign = 34% → 65% connection rate
# - Strategic break-up message (Day 7) = highest response rate
#
# ============================================================================

SEQUENCES = {
    # ==========================================================================
    # 7-DAY INTENSIVE SEQUENCE - Research-backed aggressive follow-up
    # ==========================================================================
    # Total: 14 touches over 7 days (9 SMS + 5 Email)
    # After Day 7, transitions to monthly nurture if no response
    # ==========================================================================
    "new_lead_7day": {
        "name": "New Lead 7-Day Intensive",
        "description": "World-class 7-day follow-up based on MIT/LeadSimple research",
        "steps": [
            # ===== DAY 0: Speed-to-Lead (handled by trigger_instant_ai_response) =====
            # Initial SMS + Email are sent instantly via AI generation
            # This sequence picks up 4 hours later

            # Day 0, +4 hours: Gentle check-in
            {
                "step": 1,
                "delay_minutes": 240,  # 4 hours
                "channel": "sms",
                "type": "followup_gentle",
                "ai_generate": True,  # Use AI to generate contextual message
            },

            # ===== DAY 1: Value-focused =====
            # Day 1, 10am: Value SMS with market insight
            {
                "step": 2,
                "delay_minutes": 1020,  # ~17 hours (next day 10am-ish)
                "channel": "sms",
                "type": "followup_value",
                "ai_generate": True,
            },
            # Day 1, 2pm: Value email with market data
            {
                "step": 3,
                "delay_minutes": 1260,  # ~21 hours (next day 2pm-ish)
                "channel": "email",
                "type": "followup_value",
                "ai_generate": True,
            },

            # ===== DAY 2: Question-based (easy to respond) =====
            {
                "step": 4,
                "delay_minutes": 2520,  # Day 2, ~11am
                "channel": "sms",
                "type": "followup_question",
                "ai_generate": True,
            },

            # ===== DAY 3: Resource offer =====
            # Day 3, 10am: Resource email
            {
                "step": 5,
                "delay_minutes": 3900,  # Day 3, ~10am
                "channel": "email",
                "type": "followup_resource",
                "ai_generate": True,
            },
            # Day 3, 3pm: Casual check-in
            {
                "step": 6,
                "delay_minutes": 4200,  # Day 3, ~3pm
                "channel": "sms",
                "type": "followup_casual",
                "ai_generate": True,
            },

            # ===== DAY 4: Timing/urgency (soft) =====
            {
                "step": 7,
                "delay_minutes": 5580,  # Day 4, ~12pm
                "channel": "sms",
                "type": "followup_timing",
                "ai_generate": True,
            },

            # ===== DAY 5: Social proof =====
            # Day 5, 10am: Success story email
            {
                "step": 8,
                "delay_minutes": 6900,  # Day 5, ~10am
                "channel": "email",
                "type": "followup_social_proof",
                "ai_generate": True,
            },
            # Day 5, 4pm: Soft no-pressure SMS
            {
                "step": 9,
                "delay_minutes": 7260,  # Day 5, ~4pm
                "channel": "sms",
                "type": "followup_soft",
                "ai_generate": True,
            },

            # ===== DAY 6: Helpful offer =====
            {
                "step": 10,
                "delay_minutes": 8640,  # Day 6, ~11am
                "channel": "sms",
                "type": "followup_helpful",
                "ai_generate": True,
            },

            # ===== DAY 7: Strategic Break-Up (highest response rate!) =====
            # Day 7, 10am: Warm close email
            {
                "step": 11,
                "delay_minutes": 10020,  # Day 7, ~10am
                "channel": "email",
                "type": "followup_final",
                "ai_generate": True,
            },
            # Day 7, 3pm: Final SMS - transition to monthly
            {
                "step": 12,
                "delay_minutes": 10320,  # Day 7, ~3pm
                "channel": "sms",
                "type": "followup_final",
                "ai_generate": True,
                "triggers_nurture": True,  # After this, move to monthly nurture
            },
        ],
    },

    # Legacy 24-hour sequence (kept for backwards compatibility)
    "new_lead_24h": {
        "name": "New Lead 24-Hour Sequence (Legacy)",
        "description": "Shorter follow-up - use new_lead_7day instead",
        "steps": [
            {
                "step": 1,
                "delay_minutes": 0,
                "channel": "sms",
                "template_id": "welcome_new_lead",
            },
            {
                "step": 2,
                "delay_minutes": 15,
                "channel": "sms",
                "template_id": "followup_no_response_1",
            },
            {
                "step": 3,
                "delay_minutes": 240,  # 4 hours
                "channel": "sms",
                "content": "Hey! Just wanted to make sure you saw my message. I'm here to help whenever you're ready!",
            },
            {
                "step": 4,
                "delay_minutes": 480,  # 8 hours
                "channel": "email",
                "template_id": "email_intro",
            },
            {
                "step": 5,
                "delay_minutes": 1440,  # 24 hours
                "channel": "sms",
                "template_id": "followup_no_response_2",
            },
        ],
    },

    "post_showing": {
        "name": "Post-Showing Follow-up",
        "description": "Follow up after property showing",
        "steps": [
            {
                "step": 1,
                "delay_minutes": 120,  # 2 hours after
                "channel": "sms",
                "template_id": "followup_after_showing",
            },
            {
                "step": 2,
                "delay_minutes": 1440,  # Next day
                "channel": "sms",
                "content": "Had a chance to think about the place we saw? Let me know if you want to see more options!",
            },
        ],
    },
}

# ============================================================================
# NURTURE SEQUENCES - For leads after Day 7 intensive or opted for long-term
# ============================================================================

NURTURE_SEQUENCES = {
    # Monthly check-ins after 7-day intensive completes
    "post_intensive_monthly": {
        "name": "Monthly Nurture (Post-Intensive)",
        "description": "Monthly touchpoints after 7-day intensive sequence",
        "steps": [
            # Week 2 (Day 14): First monthly check-in
            {"step": 1, "delay_days": 7, "channel": "sms", "type": "nurture_checkin", "ai_generate": True},
            # Week 3 (Day 21): Market update email
            {"step": 2, "delay_days": 14, "channel": "email", "type": "nurture_market_update", "ai_generate": True},
            # Month 1 (Day 30): Monthly SMS
            {"step": 3, "delay_days": 23, "channel": "sms", "type": "nurture_value", "ai_generate": True},
            # Month 2 (Day 60): Email with new listings
            {"step": 4, "delay_days": 53, "channel": "email", "type": "nurture_new_listing", "ai_generate": True},
            # Month 3 (Day 90): Re-engagement attempt
            {"step": 5, "delay_days": 83, "channel": "sms", "type": "re_engage_warm", "ai_generate": True},
            # Continues monthly after this...
        ],
    },

    "8x8": {
        "name": "8x8 Nurture Cadence",
        "description": "8 touches over 8 weeks for long-term nurture",
        "steps": [
            {"step": 1, "delay_days": 0, "channel": "email", "template_id": "nurture_intro"},
            {"step": 2, "delay_days": 3, "channel": "sms", "template_id": "nurture_checkin"},
            {"step": 3, "delay_days": 7, "channel": "email", "template_id": "nurture_market_update"},
            {"step": 4, "delay_days": 14, "channel": "sms", "template_id": "nurture_value"},
            {"step": 5, "delay_days": 21, "channel": "email", "template_id": "nurture_new_listing"},
            {"step": 6, "delay_days": 28, "channel": "sms", "template_id": "nurture_checkin"},
            {"step": 7, "delay_days": 42, "channel": "email", "template_id": "nurture_market_update"},
            {"step": 8, "delay_days": 56, "channel": "sms", "template_id": "re_engage_cold"},
        ],
    },

    "monthly": {
        "name": "Monthly Check-in",
        "description": "Monthly touchpoint for cold leads",
        "steps": [
            {"step": 1, "delay_days": 30, "channel": "email", "template_id": "nurture_market_update"},
            {"step": 2, "delay_days": 60, "channel": "sms", "template_id": "nurture_checkin"},
            {"step": 3, "delay_days": 90, "channel": "email", "template_id": "nurture_new_listing"},
        ],
    },
}


# ============================================================================
# NEXT BEST ACTION SCAN TASK (Runs every 15 minutes)
# ============================================================================

@shared_task(bind=True)
def run_nba_scan_task(
    self,
    organization_id: str = None,
    execute: bool = True,
    batch_size: int = 50,
):
    """
    Run the Next Best Action scan to find leads needing attention.

    This task should be scheduled to run every 15 minutes via Celery Beat.
    It proactively scans all leads and determines the optimal action to take.

    Actions include:
    - First contact for new leads
    - Follow-up for leads that went silent
    - Re-engagement for dormant leads
    - Processing scheduled follow-ups

    Args:
        organization_id: Filter by organization (optional)
        execute: Whether to execute recommended actions
        batch_size: Number of leads to process per run

    Schedule via Celery Beat:
        'run-nba-scan': {
            'task': 'app.scheduler.ai_tasks.run_nba_scan_task',
            'schedule': crontab(minute='*/15'),  # Every 15 minutes
        }
    """
    logger.info(f"Starting NBA scan task (execute={execute}, batch_size={batch_size})")

    try:
        from app.ai_agent.next_best_action import run_nba_scan

        # Run the scan
        result = asyncio.run(run_nba_scan(
            organization_id=organization_id,
            execute=execute,
            batch_size=batch_size,
        ))

        logger.info(
            f"NBA scan complete: {result['recommendations_count']} recommendations, "
            f"{result['executed_count']} executed, {result['skipped_count']} skipped"
        )

        return result

    except Exception as e:
        logger.error(f"Error in NBA scan task: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@shared_task(bind=True)
def trigger_new_lead_followup(
    self,
    fub_person_id: int,
    source: str = None,
    organization_id: str = None,
):
    """
    Trigger follow-up sequence for a new lead.

    Call this when a new lead is created (via webhook or sync).

    Args:
        fub_person_id: FUB person ID
        source: Lead source (e.g., 'MyAgentFinder', 'Redfin')
        organization_id: Organization ID
    """
    logger.info(f"Triggering new lead follow-up for person {fub_person_id} (source: {source})")

    try:
        from app.ai_agent.next_best_action import get_nba_engine, RecommendedAction, ActionType
        from app.ai_agent.followup_manager import FollowUpTrigger

        engine = get_nba_engine()

        # Create first contact action
        action = RecommendedAction(
            fub_person_id=fub_person_id,
            action_type=ActionType.FIRST_CONTACT_SMS,
            priority_score=90,  # New leads are high priority
            reason=f"New lead from {source or 'Unknown'}",
            message_context={
                "source": source,
                "trigger": FollowUpTrigger.NEW_LEAD.value,
            }
        )

        # Execute the action
        result = asyncio.run(engine.execute_action(action))

        logger.info(f"New lead follow-up triggered: {result}")
        return result

    except Exception as e:
        logger.error(f"Error triggering new lead follow-up: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


# ============================================================================
# INSTANT RESPONSE TASK - Speed-to-Lead (< 1 minute)
# Research: MIT study - 21x higher conversion within 5 minutes
# ============================================================================

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,  # Quick retry for speed
    autoretry_for=(Exception,),
)
def trigger_instant_ai_response(
    self,
    fub_person_id: int,
    source: str = None,
    organization_id: str = None,
    user_id: str = None,
):
    """
    INSTANT response for new leads - triggered immediately by webhook.

    This is the speed-to-lead critical path:
    - Bypasses the 15-minute NBA scan
    - Sends first contact within 60 seconds
    - Schedules the full aggressive follow-up sequence

    Research backing:
    - MIT Study: 21x higher conversion within 5 minutes
    - 78% of sales go to first responder (LeadSimple)
    - 391% higher conversion within 1 minute

    Args:
        fub_person_id: FUB person ID
        source: Lead source (e.g., 'MyAgentFinder', 'Redfin')
        organization_id: Organization ID
        user_id: User ID for settings lookup
    """
    logger.info(
        f"🚀 INSTANT AI response triggered for person {fub_person_id} "
        f"(source: {source})"
    )

    try:
        from app.database.supabase_client import get_supabase_client
        from app.ai_agent.settings_service import get_settings_service
        from app.ai_agent.followup_manager import get_followup_manager, FollowUpTrigger
        from app.ai_agent.compliance_checker import ComplianceChecker
        from app.messaging.fub_sms_service import FUBSMSService
        from app.fub.fub_client import FUBClient
        import random

        supabase = get_supabase_client()

        # Load settings for channel toggles and configuration
        settings_service = get_settings_service(supabase)
        settings = asyncio.run(settings_service.get_settings(user_id, organization_id))

        # Check if instant response is enabled
        if not settings.instant_response_enabled:
            logger.info(f"Instant response disabled for org {organization_id}")
            return {"success": False, "reason": "instant_response_disabled"}

        # Get person data from FUB
        fub = FUBClient()
        person_data = fub.get_person(fub_person_id)

        if not person_data:
            logger.error(f"Person {fub_person_id} not found in FUB")
            return {"success": False, "error": "Person not found"}

        # Extract contact info
        first_name = person_data.get("firstName", "there")
        phones = person_data.get("phones", [])
        phone = phones[0].get("value") if phones else None

        # Check if we can send SMS
        if not phone:
            logger.warning(f"No phone number for person {fub_person_id}")
            return {"success": False, "error": "No phone number"}

        # Check compliance
        compliance = ComplianceChecker(supabase)
        compliance_result = asyncio.run(
            compliance.check_send_allowed(
                phone_number=phone,
                fub_person_id=fub_person_id,
            )
        )

        if compliance_result.status.value != "allowed":
            logger.warning(f"Compliance blocked instant response: {compliance_result.reason}")
            return {"success": False, "error": f"Compliance: {compliance_result.reason}"}

        # ================================================================
        # INTELLIGENT FIRST CONTACT - AI-Powered SMS + Email
        # Uses full lead context: source, location, timeline, financing
        # ================================================================
        from app.ai_agent.response_generator import LeadProfile
        from app.ai_agent.initial_outreach_generator import (
            generate_initial_outreach,
            LeadContext,
        )
        from app.email.ai_email_service import get_ai_email_service, EmailCategory

        # Build rich lead profile for intelligent context
        lead_profile = LeadProfile.from_fub_data(person_data)

        # Get events for additional context (timeline, financing, etc.)
        events = []
        try:
            import requests
            import base64
            import os
            fub_api_key = os.getenv('FUB_API_KEY')
            if fub_api_key:
                headers = {
                    'Authorization': f'Basic {base64.b64encode(f"{fub_api_key}:".encode()).decode()}',
                }
                resp = requests.get(
                    f'https://api.followupboss.com/v1/events?personId={fub_person_id}&limit=5',
                    headers=headers,
                    timeout=10,
                )
                if resp.status_code == 200:
                    events = resp.json().get('events', [])
                    logger.info(f"Got {len(events)} events for lead context")
        except Exception as e:
            logger.warning(f"Could not fetch events for context: {e}")

        # Get lead's email for email outreach
        emails = person_data.get("emails", [])
        lead_email = emails[0].get("value") if emails else None

        # Generate AI-powered initial outreach (SMS + Email)
        message = None
        outreach = None
        try:
            outreach = asyncio.run(
                generate_initial_outreach(
                    person_data=person_data,
                    events=events,
                    agent_name=settings.agent_name,
                    agent_email=settings.agent_email or "",
                    agent_phone=settings.agent_phone or "",
                    brokerage_name=settings.brokerage_name,
                )
            )

            message = outreach.sms_message
            logger.info(
                f"AI-generated initial outreach for {fub_person_id} "
                f"(model: {outreach.model_used}, context: {outreach.context_used})"
            )

        except Exception as ai_error:
            logger.warning(f"AI initial outreach failed, using fallback: {ai_error}")

        # Fallback if AI generation failed
        if not message:
            # Build context for smart fallback
            lead_ctx = LeadContext.from_fub_data(person_data, events)
            location = lead_ctx.get_location_str()
            message = f"Hey {first_name}! {settings.agent_name} here. Saw you were checking out {location} - great area! What's got you interested in that neighborhood?"

        # SEND THE MESSAGE IMMEDIATELY
        sms_service = FUBSMSService()
        result = sms_service.send_text_message(
            person_id=fub_person_id,
            message=message,
        )

        if result.get("success"):
            logger.info(f"✅ Instant SMS sent to person {fub_person_id}")

            # ================================================================
            # SEND IMMEDIATE EMAIL (if we have email and generated content)
            # ================================================================
            email_sent = False
            if lead_email and outreach and outreach.email_body:
                try:
                    email_service = get_ai_email_service()
                    email_result = email_service.send_email(
                        to_email=lead_email,
                        subject=outreach.email_subject,
                        html_content=outreach.email_body,
                        text_content=outreach.email_text,
                        from_email=settings.agent_email,
                        from_name=settings.agent_name,
                        fub_person_id=fub_person_id,
                        category=EmailCategory.WELCOME,
                        template_id="ai_initial_outreach_v1",
                        log_to_fub=True,
                    )

                    if email_result.success:
                        email_sent = True
                        logger.info(f"✅ Instant EMAIL sent to person {fub_person_id}")

                        # Log the email
                        supabase.table("ai_message_log").insert({
                            "fub_person_id": fub_person_id,
                            "direction": "outbound",
                            "channel": "email",
                            "message_content": outreach.email_subject,
                            "intent_detected": "first_contact_instant_email",
                            "created_at": datetime.utcnow().isoformat(),
                        }).execute()
                    else:
                        logger.warning(f"Email send failed: {email_result.error}")

                except Exception as email_error:
                    logger.warning(f"Could not send instant email: {email_error}")
            elif not lead_email:
                logger.info(f"No email address for person {fub_person_id}, skipping email")

            # Mark first AI contact timestamp
            supabase.table("ai_conversations").upsert({
                "fub_person_id": fub_person_id,
                "organization_id": organization_id,
                "first_ai_contact_at": datetime.utcnow().isoformat(),
                "last_ai_message_at": datetime.utcnow().isoformat(),
                "state": "initial",
            }, on_conflict="fub_person_id").execute()

            # Log the SMS message
            supabase.table("ai_message_log").insert({
                "fub_person_id": fub_person_id,
                "direction": "outbound",
                "channel": "sms",
                "message_content": message,
                "intent_detected": "first_contact_instant",
                "created_at": datetime.utcnow().isoformat(),
            }).execute()

            # Now schedule the REST of the aggressive sequence (skip step 0)
            # The remaining steps: 30min, Day 1, Day 2, etc.
            # Pass lead_profile for intelligent qualification skip logic
            followup_manager = get_followup_manager(supabase)
            sequence_result = asyncio.run(
                followup_manager.schedule_followup_sequence(
                    fub_person_id=fub_person_id,
                    organization_id=organization_id,
                    trigger=FollowUpTrigger.NEW_LEAD,
                    start_delay_hours=0,  # Immediate
                    preferred_channel="sms",
                    lead_timezone=person_data.get("timezone", "America/New_York"),
                    settings=settings,
                    lead_profile=lead_profile,  # For intelligent qualification skip
                )
            )

            logger.info(
                f"Scheduled {sequence_result['total_scheduled']} follow-ups "
                f"(skipped {sequence_result.get('total_skipped', 0)} voice steps)"
            )

            return {
                "success": True,
                "fub_person_id": fub_person_id,
                "sms_sent": True,
                "email_sent": email_sent,
                "sms_message": message,
                "email_subject": outreach.email_subject if outreach else None,
                "context_used": outreach.context_used if outreach else None,
                "model_used": outreach.model_used if outreach else "fallback",
                "sequence_scheduled": sequence_result["total_scheduled"],
            }

        else:
            logger.error(f"Failed to send instant message: {result.get('error')}")
            return {"success": False, "error": result.get("error")}

    except Exception as e:
        logger.error(f"Error in instant AI response: {e}", exc_info=True)
        raise  # Let Celery retry
