"""
AI Agent Webhook Handlers - Process FUB webhooks for AI sales agent.

Handles:
- textMessagesCreated: Inbound SMS triggers AI response via full agent service
- peopleCreated: New leads trigger AI welcome sequence
- peopleUpdated: Lead updates may trigger follow-up adjustments
- appointmentsCreated: Appointment confirmations and reminders

Uses the full AIAgentService for:
- Rich lead profile context
- Intent detection with pattern matching
- Smart qualification question flow
- Context-aware objection handling
- Appointment scheduling integration
"""

import logging
import asyncio
import threading
import random
import pytz
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from flask import Blueprint, request, Response
import uuid

from app.database.supabase_client import SupabaseClientSingleton
from app.database.fub_api_client import FUBApiClient
from app.utils.constants import Credentials
from app.ai_agent.lead_profile_cache import get_lead_profile_cache, LeadProfileCacheService

logger = logging.getLogger(__name__)

# Lead profile cache (lazy initialized)
_profile_cache: Optional[LeadProfileCacheService] = None

def get_profile_cache() -> LeadProfileCacheService:
    """Get the lead profile cache service."""
    global _profile_cache
    if _profile_cache is None:
        _profile_cache = get_lead_profile_cache(
            supabase_client=supabase,
            fub_client=fub_client,
        )
    return _profile_cache

# Create Blueprint for AI webhooks
ai_webhook_bp = Blueprint('ai_webhooks', __name__, url_prefix='/webhooks/ai')

# Credentials
CREDS = Credentials()

# Database
supabase = SupabaseClientSingleton.get_instance()

# FUB API Client
fub_client = FUBApiClient()

# AI Agent Service (lazy loaded)
_agent_service = None

# Playwright SMS Service (lazy loaded, used only for reading privacy-redacted messages)
_playwright_sms_service = None

# FUB Native SMS Service (API-based, preferred for sending - <1s vs 90s+ with Playwright)
from app.messaging.fub_sms_service import FUBSMSService

def get_agent_service():
    """Lazy load the AI agent service."""
    global _agent_service
    if _agent_service is None:
        from app.ai_agent import create_agent_service
        import os
        _agent_service = create_agent_service(
            supabase_client=supabase,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),  # Falls back to env var
        )
    return _agent_service


def calculate_queued_delivery_time(timezone_str: str = "America/Denver") -> datetime:
    """Calculate a random delivery time between 8-10 AM the next business day.

    Args:
        timezone_str: Timezone for the recipient

    Returns:
        datetime in UTC for when to send the message
    """
    try:
        tz = pytz.timezone(timezone_str)
    except pytz.exceptions.UnknownTimeZoneError:
        tz = pytz.timezone("America/Denver")

    now = datetime.now(tz)

    # Determine the next morning
    if now.hour < 8:
        # Before 8 AM today - schedule for today
        next_morning = now.replace(hour=8, minute=0, second=0, microsecond=0)
    else:
        # After 8 AM - schedule for tomorrow
        tomorrow = now.date() + timedelta(days=1)
        next_morning = datetime.combine(tomorrow, datetime.min.time().replace(hour=8))
        next_morning = tz.localize(next_morning)

    # Add random minutes between 0 and 120 (8:00 AM to 10:00 AM)
    random_minutes = random.randint(0, 120)
    scheduled_time = next_morning + timedelta(minutes=random_minutes)

    # Convert to UTC for storage
    scheduled_time_utc = scheduled_time.astimezone(pytz.UTC)

    return scheduled_time_utc


async def queue_message_for_delivery(
    fub_person_id: int,
    message_content: str,
    scheduled_for: datetime,
    organization_id: str = None,
    user_id: str = None,
    channel: str = "sms",
) -> dict:
    """Queue a message for later delivery.

    Args:
        fub_person_id: FUB person ID
        message_content: The message to send
        scheduled_for: When to send (UTC datetime)
        organization_id: Organization ID
        user_id: User ID
        channel: Message channel (sms/email)

    Returns:
        Dict with success status and message ID
    """
    try:
        message_data = {
            "fub_person_id": fub_person_id,
            "channel": channel,
            "message_content": message_content,
            "scheduled_for": scheduled_for.isoformat(),
            "status": "pending",
            "sequence_type": "off_hours_queue",
            "organization_id": organization_id,
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
        }

        result = supabase.table("scheduled_messages").insert(message_data).execute()

        if result.data:
            message_id = result.data[0]["id"]
            logger.info(f"Queued message {message_id} for person {fub_person_id} at {scheduled_for}")
            return {"success": True, "message_id": message_id, "scheduled_for": scheduled_for.isoformat()}
        else:
            logger.error(f"Failed to queue message for person {fub_person_id}")
            return {"success": False, "error": "Insert failed"}

    except Exception as e:
        logger.error(f"Error queuing message for person {fub_person_id}: {e}")
        return {"success": False, "error": str(e)}


def run_async_task(coroutine):
    """Helper function to run async tasks from sync code with error handling."""
    loop = asyncio.new_event_loop()

    def run_in_thread(loop, coro):
        try:
            asyncio.set_event_loop(loop)
            logger.info("Background task starting...")
            loop.run_until_complete(coro)
            logger.info("Background task completed successfully")
        except Exception as e:
            import traceback
            import sys
            logger.error(f"CRITICAL: Background task failed with error: {e}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            # Also print to stderr so Railway can capture it
            print(f"BACKGROUND TASK ERROR: {e}", file=sys.stderr)
            traceback.print_exc()
            sys.stderr.flush()
        finally:
            try:
                loop.close()
            except Exception:
                pass

    thread = threading.Thread(target=run_in_thread, args=(loop, coroutine))
    thread.daemon = True
    thread.start()


@ai_webhook_bp.route('/text-received', methods=['POST'])
def handle_text_message_webhook():
    """
    Handle inbound text message webhook from FUB.

    This is triggered when:
    - A lead sends a text message
    - A text is logged in FUB

    The AI agent will analyze the message and generate an appropriate response.

    MULTI-TENANT: Each organization registers webhooks with their org_id:
    https://api.leadsynergy.com/webhooks/ai/text-received?org_id=abc123

    This ensures each organization's webhooks are routed to the correct
    FUB credentials and AI settings.
    """
    try:
        webhook_data = request.get_json()
        logger.info(f"Received text message webhook: {webhook_data.get('event')}")

        event = webhook_data.get('event', '').lower()
        resource_uri = webhook_data.get('uri')
        resource_ids = webhook_data.get('resourceIds', [])

        # MULTI-TENANT: Get organization_id from query parameter
        # This is set when the organization registers their FUB webhooks
        org_id_from_url = request.args.get('org_id')
        if org_id_from_url:
            logger.info(f"Webhook org_id from URL: {org_id_from_url}")

        if event != 'textmessagescreated':
            return Response("Event not applicable", status=200)

        # Process asynchronously - pass org_id for multi-tenant routing
        run_async_task(process_inbound_text(webhook_data, resource_uri, resource_ids, org_id_from_url))

        return Response("OK", status=200)

    except Exception as e:
        logger.error(f"Error processing text webhook: {e}")
        return Response("Error processing webhook", status=500)


async def process_inbound_text(webhook_data: Dict[str, Any], resource_uri: str, resource_ids: list, org_id_hint: str = None):
    """
    Process an inbound text message using the full AI Agent Service.

    Steps:
    1. Fetch the message details from FUB
    2. Check if it's an inbound message (not our own outbound)
    3. Build rich lead profile from FUB data
    4. Check compliance (opt-out keywords, rate limits)
    5. Process through full AI Agent Service (intent detection, qualification, objection handling)
    6. Send response via FUB native texting

    Args:
        webhook_data: The webhook payload from FUB
        resource_uri: URI to fetch message details
        resource_ids: List of resource IDs
        org_id_hint: Organization ID from webhook URL (for multi-tenant routing)
    """
    global _playwright_sms_service

    try:
        import aiohttp
        import base64

        if not resource_ids:
            logger.warning("No resource IDs in text webhook")
            return

        message_id = resource_ids[0]

        # MULTI-TENANT: Get the correct FUB API key for this organization
        # If org_id is provided in URL, use that org's API key
        fub_api_key = CREDS.FUB_API_KEY  # Default fallback
        if org_id_hint:
            org_api_key = await get_fub_api_key_for_org(org_id_hint)
            if org_api_key:
                fub_api_key = org_api_key
                logger.info(f"Using org-specific FUB API key for org {org_id_hint}")

        # Fetch message details with the correct API key
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {base64.b64encode(f"{fub_api_key}:".encode()).decode()}',
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(resource_uri) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch text message: {response.status}")
                    return
                message_data = await response.json()

        # Get the text message details
        text_messages = message_data.get('textmessages', [])
        if not text_messages:
            logger.warning("No text messages in response")
            logger.debug(f"Full message_data: {message_data}")
            return

        text_msg = text_messages[0]
        logger.debug(f"Text message received, keys: {list(text_msg.keys())}")

        person_id = text_msg.get('personId')
        is_incoming = text_msg.get('isIncoming', False)
        message_content = text_msg.get('message', '')
        from_number = text_msg.get('fromNumber')  # Lead's phone for incoming messages

        if not person_id:
            logger.warning(f"No person ID associated with text message. Full msg: {text_msg}")
            return

        # Only process incoming messages (from the lead)
        if not is_incoming:
            logger.info(f"Skipping outbound message for person {person_id}")
            return

        # Get the FUB phone number that received this message
        to_number = text_msg.get('toNumber')

        # MULTI-TENANT: Use org_id from URL if provided, otherwise resolve
        organization_id = org_id_hint or await resolve_organization_for_person(person_id)
        user_id = await resolve_user_for_person(person_id, organization_id)

        if not organization_id or not user_id:
            logger.warning(f"Could not resolve organization/user for person {person_id}")
            return

        # ============================================
        # AI ENABLE CHECK - TWO-LEVEL OPT-IN MODEL
        # ============================================
        # Level 1: Global switch (master kill switch)
        # Level 2: Per-lead setting (must be explicitly enabled)
        #
        # Logic:
        # - Global OFF → System disabled, nothing works
        # - Global ON + Per-lead not enabled → AI does NOT respond
        # - Global ON + Per-lead enabled → AI responds
        # ============================================

        # First, check the GLOBAL switch (master kill switch)
        from app.ai_agent.settings_service import get_agent_settings
        ai_settings = await get_agent_settings(supabase, organization_id, user_id)

        if not ai_settings.is_enabled:
            logger.info(f"Skipping person {person_id} - AI system is GLOBALLY DISABLED")
            await log_ai_message(
                conversation_id=None,
                fub_person_id=person_id,
                direction="inbound",
                channel="sms",
                message_content=message_content,
                extracted_data={"ai_disabled": True, "reason": "AI system globally disabled"},
            )
            return

        # ============================================
        # PHONE NUMBER FILTER CHECK (BLACKLIST)
        # ============================================
        # If ai_respond_to_phone_numbers is configured, IGNORE messages
        # received on those specific FUB phone numbers (blacklist).
        # This allows teams to exclude certain numbers (sign calls, website leads, etc.)
        # while responding to everything else.
        # ============================================
        blocked_phone_numbers = ai_settings.ai_respond_to_phone_numbers or []
        if blocked_phone_numbers and to_number:
            # Normalize the to_number for comparison
            # FUB may send it in various formats: +1XXXXXXXXXX, (XXX) XXX-XXXX, etc.
            import re
            normalized_to = re.sub(r'[^\d]', '', to_number)
            if not normalized_to.startswith('1') and len(normalized_to) == 10:
                normalized_to = '1' + normalized_to
            normalized_to = '+' + normalized_to if not normalized_to.startswith('+') else normalized_to

            # Check if normalized_to matches any blocked number (BLACKLIST)
            is_blocked = False
            for blocked in blocked_phone_numbers:
                normalized_blocked = re.sub(r'[^\d]', '', blocked)
                if not normalized_blocked.startswith('1') and len(normalized_blocked) == 10:
                    normalized_blocked = '1' + normalized_blocked
                normalized_blocked = '+' + normalized_blocked if not normalized_blocked.startswith('+') else normalized_blocked

                if normalized_to == normalized_blocked:
                    is_blocked = True
                    break

            if is_blocked:
                logger.info(
                    f"Skipping person {person_id} - message received on phone {to_number} "
                    f"which is in blocked list: {blocked_phone_numbers}"
                )
                await log_ai_message(
                    conversation_id=None,
                    fub_person_id=person_id,
                    direction="inbound",
                    channel="sms",
                    message_content=message_content,
                    extracted_data={
                        "ai_disabled": True,
                        "reason": f"Phone number {to_number} in blocked list",
                        "to_number": to_number,
                        "blocked_numbers": blocked_phone_numbers,
                    },
                )
                return

            logger.info(f"Phone number {to_number} is not blocked - proceeding with AI response")

        # Global is ON - now check per-lead setting (OPT-IN model)
        from app.ai_agent.lead_ai_settings_service import LeadAISettingsServiceSingleton
        lead_ai_service = LeadAISettingsServiceSingleton.get_instance(supabase)
        per_lead_enabled = await lead_ai_service.is_ai_enabled_for_lead(
            fub_person_id=person_id,
            organization_id=organization_id,
            user_id=user_id,
        )

        # OPT-IN MODEL: Lead must be EXPLICITLY enabled
        # If per_lead_enabled is None (no setting) or False, AI does NOT respond
        if per_lead_enabled is not True:
            reason = "AI not enabled for this lead" if per_lead_enabled is None else "AI explicitly disabled for this lead"
            logger.info(f"Skipping person {person_id} - {reason} (per_lead_enabled={per_lead_enabled})")
            await log_ai_message(
                conversation_id=None,
                fub_person_id=person_id,
                direction="inbound",
                channel="sms",
                message_content=message_content,
                extracted_data={"ai_disabled": True, "reason": reason},
            )
            return

        logger.info(f"AI ENABLED for lead {person_id} - global=ON, per_lead=True")

        # Fetch person data for profile building
        fub_client = FUBApiClient(api_key=CREDS.FUB_API_KEY)
        person_data = fub_client.get_person(person_id)

        if not person_data:
            logger.warning(f"Could not fetch person data for {person_id}")
            return

        # Check for FUB privacy-redacted messages
        # FUB API intentionally hides SMS content with "* Body is hidden for privacy reasons *"
        # When this happens, we use Playwright browser automation to read the actual content
        logger.info(f"Message content for person {person_id}: [{message_content}]")
        if "Body is hidden" in message_content or "hidden for privacy" in message_content.lower():
            logger.warning(f"FUB API returned privacy-redacted message for person {person_id}. Using Playwright to read actual content...")

            # organization_id and user_id already resolved above

            # Get FUB browser credentials
            from app.ai_agent.settings_service import get_fub_browser_credentials
            credentials = await get_fub_browser_credentials(
                supabase_client=supabase,
                user_id=user_id,
                organization_id=organization_id,
            )

            if not credentials:
                logger.error(f"No FUB credentials found for Playwright read - cannot process message for person {person_id}")
                return

            # Use Playwright to read the actual message content
            from app.messaging.playwright_sms_service import PlaywrightSMSService
            global _playwright_sms_service
            if _playwright_sms_service is None:
                _playwright_sms_service = PlaywrightSMSService()

            agent_id = credentials.get("agent_id", user_id or "default")

            # Check if this is first contact - no message history in our database
            existing_history = await get_conversation_history(person_id, limit=1)
            is_first_contact = len(existing_history) == 0

            if is_first_contact:
                # First contact with this lead - sync their message history for AI context
                logger.info(f"First contact with person {person_id} - syncing message history...")
                history_result = await _playwright_sms_service.read_recent_messages(
                    agent_id=agent_id,
                    person_id=person_id,
                    credentials=credentials,
                    limit=15,  # Get last 15 messages for context
                )

                if history_result.get("success") and history_result.get("messages"):
                    # Save all historical messages to ai_message_log
                    history_messages = history_result.get("messages", [])
                    logger.info(f"Syncing {len(history_messages)} historical messages for person {person_id}")

                    for msg in reversed(history_messages):  # Oldest first
                        direction = "inbound" if msg.get("is_incoming") else "outbound"
                        await log_ai_message(
                            conversation_id=None,  # Historical messages don't have conversation ID
                            fub_person_id=person_id,
                            direction=direction,
                            channel="sms",
                            message_content=msg.get("text", ""),
                            ai_model="historical_sync",  # Mark as synced history
                        )

                    # Get the latest incoming message from history for current processing
                    for msg in history_messages:
                        if msg.get("is_incoming"):
                            message_content = msg.get("text", "")
                            logger.info(f"Using latest incoming message from history: {message_content[:50]}...")
                            break
                else:
                    logger.warning(f"Failed to sync history for person {person_id}, falling back to single message read")
                    # Fall back to reading just the latest message
                    read_result = await _playwright_sms_service.read_latest_message(
                        agent_id=agent_id,
                        person_id=person_id,
                        credentials=credentials,
                    )
                    if read_result.get("success"):
                        message_content = read_result.get("message", "")
            else:
                # Not first contact - just read the latest message
                logger.info(f"Reading latest message via Playwright for person {person_id}...")
                read_result = await _playwright_sms_service.read_latest_message(
                    agent_id=agent_id,
                    person_id=person_id,
                    credentials=credentials,
                )

                if not read_result.get("success"):
                    logger.error(f"Playwright read failed for person {person_id}: {read_result.get('error')}")
                    return

                message_content = read_result.get("message", "")

            if not message_content:
                logger.error(f"Could not get message content for person {person_id}")
                return

            logger.info(f"Successfully read message via Playwright: {message_content[:50]}...")

        logger.info(f"Processing inbound text from person {person_id}: {message_content[:50]}...")

        # Import AI agent components
        from app.ai_agent.compliance_checker import ComplianceChecker
        from app.ai_agent.conversation_manager import ConversationManager, ConversationState

        # person_data, organization_id, and user_id already fetched earlier - no need to fetch again

        # Check for opt-in keyword (START) - re-subscribe opted-out leads
        compliance_checker = ComplianceChecker(supabase_client=supabase)
        if message_content.strip().lower() == "start":
            logger.info(f"Opt-in keyword (START) detected from person {person_id}")
            await compliance_checker.clear_opt_out(
                fub_person_id=person_id,
                organization_id=organization_id,
            )
            # Send confirmation via FUB native API
            try:
                fub_sms = FUBSMSService(api_key=fub_api_key)
                await fub_sms.send_text_message_async(
                    person_id=person_id,
                    message="You've been re-subscribed! We're happy to have you back. How can we help?",
                )
            except Exception as e:
                logger.error(f"Failed to send opt-in confirmation to person {person_id}: {e}")
            return

        # Check for opt-out keywords
        if compliance_checker.is_opt_out_keyword(message_content):
            logger.info(f"Opt-out keyword detected from person {person_id}")
            await compliance_checker.record_opt_out(
                fub_person_id=person_id,
                organization_id=organization_id,
                reason="STOP keyword received",
            )
            # Send confirmation via FUB native API
            try:
                fub_sms = FUBSMSService(api_key=fub_api_key)
                await fub_sms.send_text_message_async(
                    person_id=person_id,
                    message="You've been unsubscribed and won't receive any more messages from us. Reply START to opt back in.",
                )
            except Exception as e:
                logger.error(f"Failed to send opt-out confirmation to person {person_id}: {e}")

            # Track A/B test outcome — opt-out is a negative outcome
            try:
                from app.ai_agent.template_engine import get_template_engine
                ab_engine = get_template_engine(supabase_client=supabase)
                # Use person_id as conversation lookup since we may not have conversation_id here
                ab_engine.record_ab_test_outcome(
                    conversation_id=str(person_id),
                    led_to_optout=True,
                )
            except Exception:
                pass  # A/B tracking is non-critical

            return

        # Check compliance before responding
        phone = text_msg.get('to') or text_msg.get('from')

        # Load AI agent settings to get the configured timezone
        from app.ai_agent.settings_service import get_agent_settings
        ai_settings = await get_agent_settings(supabase, organization_id)
        configured_timezone = ai_settings.timezone if ai_settings else "America/Denver"

        compliance_result = await compliance_checker.check_sms_compliance(
            fub_person_id=person_id,
            organization_id=organization_id,
            phone_number=phone,
            recipient_timezone=configured_timezone,
        )

        # Track if we need to queue the response for later (outside hours)
        queue_for_later = False
        queued_delivery_time = None

        if not compliance_result.can_send:
            # Check if this is just an outside-hours block - we still want to process and queue
            from app.ai_agent.compliance_checker import ComplianceStatus
            if compliance_result.status == ComplianceStatus.BLOCKED_OUTSIDE_HOURS:
                # Outside hours - still process but queue the response for morning
                queue_for_later = True
                queued_delivery_time = calculate_queued_delivery_time(configured_timezone)
                logger.info(f"Outside hours for person {person_id} - will queue response for {queued_delivery_time}")
            else:
                # Other compliance failures (opted out, DNC, etc) - truly block
                logger.warning(f"Compliance check failed for person {person_id}: {compliance_result.reason}")
                await log_ai_message(
                    conversation_id=None,
                    fub_person_id=person_id,
                    direction="inbound",
                    channel="sms",
                    message_content=message_content,
                    extracted_data={"compliance_blocked": True, "reason": compliance_result.reason},
                )
                return

        # Build rich lead profile from FUB data
        logger.info(f"Building lead profile for person {person_id}...")
        lead_profile = await build_lead_profile_from_fub(person_data, organization_id)
        logger.info(f"Lead profile built for {person_id}: {lead_profile.first_name} {lead_profile.last_name}")

        # Get conversation history for context
        logger.info(f"Getting conversation history for person {person_id}...")
        conversation_history = await get_conversation_history(person_id, limit=15)
        logger.info(f"Got {len(conversation_history) if conversation_history else 0} history messages")

        # Get or create conversation context
        logger.info(f"Getting conversation context for person {person_id}...")
        conversation_manager = ConversationManager(supabase_client=supabase)
        context = await conversation_manager.get_or_create_conversation(
            fub_person_id=person_id,
            user_id=user_id,
            organization_id=organization_id,
            lead_data=person_data,
        )
        logger.info(f"Conversation context ready, state: {context.state}")

        # CRITICAL: Skip AI responses if conversation has been handed off to human agent
        # Once handed off, the human agent owns the conversation thread
        if context.state == ConversationState.HANDED_OFF:
            logger.info(f"Conversation {context.conversation_id} is HANDED_OFF - skipping AI response. Human agent will handle.")

            # Still log the inbound message for history
            await log_ai_message(
                conversation_id=context.conversation_id,
                fub_person_id=person_id,
                direction="inbound",
                channel="sms",
                message_content=message_content,
                extracted_data={"state": "handed_off", "skipped_ai_response": True},
            )

            # Cancel any pending automation
            try:
                from app.scheduler.ai_tasks import cancel_lead_sequences
                cancel_lead_sequences.delay(
                    fub_person_id=person_id,
                    reason="Conversation handed off - human agent handling",
                )
            except Exception:
                pass

            logger.info(f"Skipped AI response for handed-off conversation {person_id}")
            return  # Exit early - let human agent handle

        # Record inbound message in context
        context.add_message("inbound", message_content, "sms")

        # Log inbound message to database for conversation history
        await log_ai_message(
            conversation_id=context.conversation_id,
            fub_person_id=person_id,
            direction="inbound",
            channel="sms",
            message_content=message_content,
        )

        # Track A/B test response — if we sent a template variant, record that the lead responded
        try:
            from app.ai_agent.template_engine import get_template_engine
            ab_engine = get_template_engine(supabase_client=supabase)
            ab_engine.record_ab_test_response(
                conversation_id=context.conversation_id,
            )
        except Exception:
            pass  # A/B tracking is non-critical, don't block message processing

        # ============================================
        # CRITICAL: Cancel pending automation when lead responds
        # ============================================
        # This prevents scheduled messages from continuing while
        # the lead is actively engaged in conversation
        try:
            from app.scheduler.ai_tasks import cancel_lead_sequences
            cancel_lead_sequences.delay(
                fub_person_id=person_id,
                reason="Lead responded - pausing automation",
            )
            logger.info(f"Cancelled pending automation for engaged lead {person_id}")
        except Exception as cancel_error:
            logger.error(f"CRITICAL: Could not cancel sequences for lead {person_id}: {cancel_error} - lead may receive duplicate messages")
            # Continue processing - but log at ERROR level since duplicate messages are possible

        # Process through full AI Agent Service
        logger.info(f"Processing message for person {person_id} through AI Agent Service...")

        agent_service = get_agent_service()
        logger.info(f"Agent service ready, processing: {message_content[:50]}...")

        try:
            agent_response = await agent_service.process_message(
                message=message_content,
                lead_profile=lead_profile,
                conversation_context=context,
                conversation_history=conversation_history,
                channel="sms",
                fub_person_id=person_id,
                user_id=user_id,
                organization_id=organization_id,
            )
            logger.info(f"AI processing complete for person {person_id}")
        except Exception as ai_error:
            logger.error(f"AI processing FAILED for person {person_id}: {ai_error}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

        if agent_response and agent_response.response_text:
            logger.info(f"AI generated response for person {person_id}: {agent_response.response_text[:100]}...")

            # Check if we need to queue for later (outside hours)
            if queue_for_later and queued_delivery_time:
                logger.info(f"Queueing response for person {person_id} - scheduled for {queued_delivery_time}")

                queue_result = await queue_message_for_delivery(
                    fub_person_id=person_id,
                    message_content=agent_response.response_text,
                    scheduled_for=queued_delivery_time,
                    organization_id=organization_id,
                    user_id=user_id,
                    channel="sms",
                )

                if queue_result.get('success'):
                    logger.info(f"Message queued successfully for person {person_id}: ID={queue_result.get('message_id')}")
                    # Log the queued message
                    await log_ai_message(
                        conversation_id=context.conversation_id if context else None,
                        fub_person_id=person_id,
                        direction="outbound",
                        channel="sms",
                        message_content=agent_response.response_text,
                        ai_model=agent_response.model_used,
                        tokens_used=agent_response.tokens_used,
                        response_time_ms=agent_response.response_time_ms,
                        extracted_data={
                            "queued": True,
                            "scheduled_for": queue_result.get('scheduled_for'),
                            "queue_id": queue_result.get('message_id'),
                        },
                    )
                    # Update context
                    context.add_message("outbound", agent_response.response_text, "sms")
                    await conversation_manager.save_context(context)
                else:
                    logger.error(f"Failed to queue message for person {person_id}: {queue_result.get('error')}")
                return  # Exit after queueing

            # Send response via Playwright browser automation
            # We use Playwright instead of FUB Native Texting API because we don't have
            # System-level API credentials (which would be required for the API endpoint)
            logger.info(f"Sending SMS via Playwright to person {person_id}...")

            try:
                from app.messaging.playwright_sms_service import PlaywrightSMSService
                from app.utils.constants import Credentials

                creds_config = Credentials()

                # Build FUB login credentials (same as used for reading messages)
                credentials = {
                    "type": creds_config.FUB_LOGIN_TYPE or "email",
                    "email": creds_config.FUB_LOGIN_EMAIL,
                    "password": creds_config.FUB_LOGIN_PASSWORD,
                }

                # Use browser automation to send SMS through FUB web UI
                sms_service = PlaywrightSMSService()
                result = await sms_service.send_sms(
                    agent_id=user_id,  # Use LeadSynergy user ID as agent identifier
                    person_id=person_id,
                    message=agent_response.response_text,
                    credentials=credentials,
                )
            except Exception as sms_err:
                logger.error(f"SMS send FAILED for person {person_id}: {sms_err}")
                import traceback
                traceback.print_exc()
                raise

            if result.get('success'):
                logger.info(f"SMS sent successfully to person {person_id}: {agent_response.response_text[:50]}...")
                # Record outbound message
                context.add_message("outbound", agent_response.response_text, "sms")

                # Update context from agent response
                if agent_response.lead_score_delta:
                    context.lead_score += agent_response.lead_score_delta

                if agent_response.state_changed and agent_response.conversation_state:
                    context.state = ConversationState(agent_response.conversation_state)

                # Update qualification data
                if agent_response.extracted_info:
                    for key, value in agent_response.extracted_info.items():
                        if value and hasattr(context.qualification_data, key):
                            setattr(context.qualification_data, key, value)

                # Handle handoff if needed
                if agent_response.should_handoff:
                    context.handoff_reason = agent_response.handoff_reason or 'AI recommended handoff'
                    context.state = ConversationState.HANDED_OFF
                    # Create task for human follow-up via FUB API
                    try:
                        fub_client.create_task(
                            person_id=person_id,
                            description=f"AI Handoff: {context.handoff_reason}",
                        )
                        # Also add a note
                        fub_client.add_note(
                            person_id=person_id,
                            note_content=f"<b>AI Agent Handoff</b><br>Reason: {context.handoff_reason}<br>Last message: {message_content}",
                        )
                    except Exception as task_error:
                        logger.warning(f"Could not create handoff task/note: {task_error}")

                # Save updated context
                await conversation_manager.save_context(context)

                # Update compliance counter
                await compliance_checker.increment_message_count(person_id, organization_id, from_number)

                # Log the AI interaction
                await log_ai_message(
                    conversation_id=context.conversation_id,
                    fub_person_id=person_id,
                    direction="outbound",
                    channel="sms",
                    message_content=agent_response.response_text,
                    lead_score_delta=agent_response.lead_score_delta or 0,
                    extracted_data=agent_response.extracted_info or {},
                    intent_detected=agent_response.detected_intent if agent_response.detected_intent else None,
                )

                # Track A/B test outcomes — appointment or opt-out
                try:
                    detected = (agent_response.detected_intent or "").lower()
                    if "appointment" in detected or "schedule" in detected or "time_selection" in detected:
                        from app.ai_agent.template_engine import get_template_engine
                        ab_engine = get_template_engine(supabase_client=supabase)
                        ab_engine.record_ab_test_outcome(
                            conversation_id=context.conversation_id,
                            led_to_appointment=True,
                        )
                except Exception:
                    pass  # A/B tracking is non-critical
            else:
                logger.error(f"SMS send FAILED for person {person_id}: {result.get('error', 'unknown error')}")

        else:
            logger.warning(f"No AI response generated for person {person_id}")

    except Exception as e:
        import traceback
        import sys
        error_msg = f"Error processing inbound text: {e}"
        logger.error(error_msg)
        logger.error(f"Full traceback: {traceback.format_exc()}")
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()


async def build_lead_profile_from_fub(person_data: Dict[str, Any], organization_id: str, force_refresh: bool = False) -> 'LeadProfile':
    """
    Build a COMPREHENSIVE LeadProfile from FUB data with SMART CACHING.

    This creates the world-class lead context that makes our AI agent
    the best in the industry by including:
    - All person data and custom fields
    - Full text message conversation history
    - Email history
    - Call logs
    - Notes from agents
    - Events (property inquiries, timeline)
    - Tasks assigned

    CACHING STRATEGY:
    - Profiles are cached in Supabase (ai_lead_profile_cache table)
    - Cache is refreshed every 24 hours or on-demand
    - Incremental updates via webhooks keep cache fresh between full refreshes
    - This reduces FUB API calls from 7 per message to 1 DB read
    """
    from app.ai_agent.response_generator import LeadProfile

    person_id = person_data.get('id')

    # Get COMPLETE lead context - try cache first, then FUB
    full_context = {}
    cache_hit = False

    if person_id:
        try:
            # Try to get from cache first
            cache = get_profile_cache()
            cached_profile = await cache.get_profile(
                fub_person_id=person_id,
                organization_id=organization_id,
                force_refresh=force_refresh,
            )

            if cached_profile:
                # Use cached data - much faster!
                cache_hit = True
                full_context = {
                    "person": cached_profile.person_data,
                    "text_messages": cached_profile.text_messages,
                    "emails": cached_profile.emails,
                    "calls": cached_profile.calls,
                    "notes": cached_profile.notes,
                    "events": cached_profile.events,
                    "tasks": cached_profile.tasks,
                }
                person_data = cached_profile.person_data or person_data
                logger.debug(f"Cache HIT for person {person_id} (updates: {cached_profile.update_count})")
            else:
                # Cache miss - fetch from FUB (this also populates the cache)
                full_context = fub_client.get_complete_lead_context(person_id)
                if full_context.get("person"):
                    person_data = full_context["person"]
                logger.debug(f"Cache MISS for person {person_id} - fetched from FUB")
        except Exception as e:
            logger.warning(f"Could not get lead context (cache or FUB): {e}")
            # Fallback to direct FUB call
            try:
                full_context = fub_client.get_complete_lead_context(person_id)
                if full_context.get("person"):
                    person_data = full_context["person"]
            except Exception as fub_error:
                logger.error(f"Fallback FUB call also failed: {fub_error}")

    # Extract basic info
    first_name = person_data.get('firstName', '')
    last_name = person_data.get('lastName', '')
    emails = person_data.get('emails', [])
    phones = person_data.get('phones', [])
    tags = person_data.get('tags', [])
    source = person_data.get('source', '')
    source_url = person_data.get('sourceUrl', '')
    stage = person_data.get('stage', {})
    stage_name = stage.get('name', '') if isinstance(stage, dict) else str(stage)
    created = person_data.get('created', '')
    last_activity = person_data.get('lastActivity', '')
    assigned_to = person_data.get('assignedTo', '')
    assigned_user_id = person_data.get('assignedUserId')

    # Extract addresses
    addresses = person_data.get('addresses', [])
    city = ''
    state = ''
    if addresses:
        city = addresses[0].get('city', '')
        state = addresses[0].get('state', '')

    # Extract custom fields for qualification data
    custom_fields = person_data.get('customFields', [])
    budget_min = None
    budget_max = None
    timeline = None
    timeline_detail = None
    property_type = None
    pre_approved = None
    pre_approval_amount = None
    motivation = None
    bedrooms = None
    bathrooms = None

    for field in custom_fields:
        field_name = field.get('name', '').lower() if field.get('name') else ''
        field_value = field.get('value')

        if 'budget' in field_name or 'price' in field_name:
            if 'min' in field_name:
                budget_min = parse_currency(field_value)
            elif 'max' in field_name:
                budget_max = parse_currency(field_value)
            else:
                budget_max = parse_currency(field_value)
        elif 'timeline' in field_name or 'timeframe' in field_name:
            timeline = field_value
        elif 'property' in field_name and 'type' in field_name:
            property_type = field_value
        elif 'pre-approv' in field_name or 'preapprov' in field_name:
            if isinstance(field_value, (int, float)):
                pre_approval_amount = int(field_value)
                pre_approved = True
            elif field_value in ['Yes', 'yes', 'true', True, '1']:
                pre_approved = True
            else:
                pre_approved = False
        elif 'motivation' in field_name or 'reason' in field_name:
            motivation = field_value
        elif 'bedroom' in field_name or 'bed' in field_name:
            try:
                bedrooms = int(field_value)
            except (ValueError, TypeError):
                pass
        elif 'bathroom' in field_name or 'bath' in field_name:
            try:
                bathrooms = int(field_value)
            except (ValueError, TypeError):
                pass

    # Calculate days since created
    days_in_system = 0
    if created:
        try:
            from dateutil.parser import parse as parse_date
            created_dt = parse_date(created)
            days_in_system = (datetime.now(created_dt.tzinfo) - created_dt).days
        except (ValueError, TypeError, ImportError):
            pass

    # Get agent info
    agent_info = await get_agent_info_for_org(organization_id)

    # Calculate score label
    lead_score = person_data.get('leadScore', 0) or 0
    if lead_score >= 70:
        score_label = "Hot"
    elif lead_score >= 40:
        score_label = "Warm"
    else:
        score_label = "Cold"

    # ========================================
    # PROCESS TEXT MESSAGE HISTORY (CRITICAL)
    # ========================================
    actual_messages_sent = []
    actual_messages_received = []
    has_received_any_messages = False

    text_messages = full_context.get("text_messages", [])
    for msg in text_messages:
        msg_data = {
            "content": msg.get("message", ""),
            "timestamp": msg.get("created", ""),
            "from": msg.get("fromNumber", ""),
            "to": msg.get("toNumber", ""),
        }
        if msg.get("isIncoming"):
            actual_messages_received.append(msg_data)
        else:
            actual_messages_sent.append(msg_data)
            has_received_any_messages = True  # Lead has received at least one message

    # ========================================
    # PROCESS EVENTS (PROPERTY INQUIRIES)
    # ========================================
    property_inquiry_source = ""
    property_inquiry_description = ""
    property_inquiry_location = ""
    property_inquiry_budget = ""
    property_inquiry_timeline = ""
    property_inquiry_financing = ""
    interested_property_address = ""
    interested_property_price = None

    events = full_context.get("events", [])
    for event in events:
        event_type = event.get("type", "")
        if event_type in ["Property Inquiry", "Registration", "General Inquiry", "Seller Inquiry"]:
            property_inquiry_source = event.get("source", "") or source
            property_inquiry_description = event.get("description", "")

            # Extract property details if available
            prop = event.get("property", {})
            if prop:
                interested_property_address = prop.get("address", "")
                interested_property_price = parse_currency(prop.get("price"))

            # Parse description for lead details (e.g., "Primary Zip: 80521 | Time Frame: 0 - 3 Months")
            desc = property_inquiry_description
            if desc:
                if "zip" in desc.lower() or "location" in desc.lower():
                    property_inquiry_location = desc
                if "time" in desc.lower() or "month" in desc.lower():
                    property_inquiry_timeline = desc
                if "budget" in desc.lower() or "price" in desc.lower():
                    property_inquiry_budget = desc
                if "pre-approv" in desc.lower() or "financ" in desc.lower():
                    property_inquiry_financing = desc
            break  # Use first relevant event

    # ========================================
    # PROCESS NOTES (AGENT INSIGHTS)
    # ========================================
    important_notes = []
    agent_notes_summary = ""
    notes = full_context.get("notes", [])
    for note in notes[:10]:  # Limit to most recent 10
        note_body = note.get("body", "")
        created_by = note.get("createdBy", "")

        # Skip KTS/automation notes - those are planned messages, not real notes
        if "KTS" in created_by or "Leadngage" in created_by:
            continue

        # These are real agent notes
        if note_body:
            # Clean HTML if present
            import re
            clean_note = re.sub(r'<[^>]+>', ' ', note_body).strip()
            if clean_note and len(clean_note) > 10:
                important_notes.append(clean_note[:500])  # Truncate long notes

    if important_notes:
        agent_notes_summary = " | ".join(important_notes[:5])

    # ========================================
    # DETERMINE IF THIS IS FIRST CONTACT
    # ========================================
    is_first_contact = not has_received_any_messages and len(actual_messages_received) == 0

    # Build the profile with ALL context
    profile = LeadProfile(
        # Identity
        first_name=first_name,
        last_name=last_name,
        full_name=f"{first_name} {last_name}".strip(),
        email=emails[0].get('value', '') if emails else "",
        phone=phones[0].get('value', '') if phones else "",
        fub_person_id=person_id,

        # Lead scoring and status
        score=lead_score,
        score_label=score_label,
        stage_name=stage_name,
        assigned_agent=assigned_to or agent_info.get('agent_name', ''),

        # Source and attribution
        source=source,
        source_url=source_url,
        original_source=source,

        # Property interests
        interested_property_address=interested_property_address,
        interested_property_price=interested_property_price,
        interested_property_type=property_type or "",
        preferred_cities=[city] if city else [],

        # Financial profile
        price_min=budget_min,
        price_max=budget_max,
        is_pre_approved=pre_approved,
        pre_approval_amount=pre_approval_amount,

        # Timeline
        timeline=timeline or "",
        timeline_detail=timeline_detail or "",
        motivation=motivation or "",

        # Property criteria
        bedrooms_min=bedrooms,
        property_types=[property_type] if property_type else [],

        # Tags and notes
        tags=tags if tags else [],
        important_notes=important_notes,
        agent_notes_summary=agent_notes_summary,

        # Property inquiry info (how they came in)
        property_inquiry_source=property_inquiry_source,
        property_inquiry_description=property_inquiry_description,
        property_inquiry_location=property_inquiry_location,
        property_inquiry_budget=property_inquiry_budget,
        property_inquiry_timeline=property_inquiry_timeline,
        property_inquiry_financing=property_inquiry_financing,

        # ACTUAL conversation history from FUB
        actual_messages_sent=actual_messages_sent,
        actual_messages_received=actual_messages_received,
        has_received_any_messages=has_received_any_messages,

        # First contact flag
        is_first_contact=is_first_contact,

        # Metadata
        created_date=created,
        days_since_created=days_in_system,
    )

    logger.info(
        f"Built comprehensive profile for {first_name} {last_name} (ID: {person_id}): "
        f"score={lead_score}, source={source}, "
        f"msgs_sent={len(actual_messages_sent)}, msgs_received={len(actual_messages_received)}, "
        f"notes={len(important_notes)}, first_contact={is_first_contact}"
    )

    return profile


async def get_conversation_history(fub_person_id: int, limit: int = 15) -> List[Dict[str, Any]]:
    """Get conversation history from database."""
    try:
        result = supabase.table("ai_message_log").select(
            "direction, channel, message_content, ai_model, created_at"
        ).eq(
            "fub_person_id", fub_person_id
        ).order(
            "created_at", desc=True
        ).limit(limit + 20).execute()  # Fetch extra to account for filtered messages

        if result.data:
            # Reverse to get chronological order
            history = list(reversed(result.data))

            # Filter out non-conversation messages
            filtered_history = []
            for h in history:
                content = h.get("message_content", "")
                ai_model = h.get("ai_model", "")

                # Skip messages that are privacy placeholders
                if "Body is hidden" in content or "hidden for privacy" in content.lower():
                    logger.debug(f"Skipping privacy-redacted message in history for person {fub_person_id}")
                    continue

                # Skip enrichment/skip trace data logged as messages
                # These are from historical_sync and contain contact info, criminal records, etc.
                if ai_model == "historical_sync" and (
                    "Contact Information:" in content
                    or "Criminal History" in content
                    or "Email Owner:" in content
                    or "Phone Numbers" in content and "Addresses" in content
                    or "Risk Assessment:" in content
                    or "Test note from" in content
                    or "Re-engagement Test" in content
                    or len(content) > 500  # Historical sync messages that are too long are likely enrichment data
                ):
                    logger.debug(f"Skipping enrichment/sync data in history for person {fub_person_id}")
                    continue

                filtered_history.append({
                    "role": "lead" if h["direction"] == "inbound" else "agent",
                    "content": content,
                    "channel": h["channel"],
                    "timestamp": h["created_at"],
                })

            # Return only the most recent `limit` messages after filtering
            return filtered_history[-limit:]
    except Exception as e:
        logger.error(f"Error fetching conversation history: {e}")

    return []


async def get_agent_info_for_org(organization_id: str) -> Dict[str, Any]:
    """Get agent info for an organization."""
    try:
        # Only select columns that exist in ai_agent_settings table
        result = supabase.table("ai_agent_settings").select(
            "agent_name, brokerage_name"
        ).eq("organization_id", organization_id).limit(1).execute()

        if result.data:
            data = result.data[0]
            return {
                "agent_name": data.get("agent_name", "Sarah"),
                "brokerage_name": data.get("brokerage_name", "our team"),
            }
    except Exception as e:
        logger.error(f"Error fetching agent info: {e}")

    return {
        "agent_name": "Sarah",
        "brokerage_name": "our team",
    }


def parse_currency(value: Any) -> Optional[int]:
    """Parse currency value to integer."""
    if not value:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        import re
        # Remove currency symbols and commas
        clean = re.sub(r'[$,\s]', '', value)
        try:
            return int(float(clean))
        except (ValueError, TypeError):
            pass
    return None


def categorize_source(source: str) -> str:
    """Categorize lead source type."""
    if not source:
        return "unknown"
    source_lower = source.lower()

    if any(x in source_lower for x in ['zillow', 'redfin', 'realtor.com', 'trulia']):
        return "portal"
    elif any(x in source_lower for x in ['facebook', 'instagram', 'social']):
        return "social_media"
    elif any(x in source_lower for x in ['google', 'ppc', 'ad']):
        return "paid_advertising"
    elif any(x in source_lower for x in ['referral', 'sphere']):
        return "referral"
    elif any(x in source_lower for x in ['website', 'web', 'organic']):
        return "organic_website"
    elif any(x in source_lower for x in ['open house', 'sign']):
        return "open_house"
    else:
        return "other"


@ai_webhook_bp.route('/lead-created', methods=['POST'])
def handle_lead_created_webhook():
    """
    Handle new lead webhook from FUB.

    This triggers the AI welcome sequence for new leads.
    """
    try:
        webhook_data = request.get_json()
        logger.info(f"Received lead created webhook: {webhook_data.get('event')}")

        event = webhook_data.get('event', '').lower()
        resource_uri = webhook_data.get('uri')
        resource_ids = webhook_data.get('resourceIds', [])

        if event != 'peoplecreated':
            return Response("Event not applicable", status=200)

        # Process asynchronously
        run_async_task(process_new_lead(webhook_data, resource_uri, resource_ids))

        return Response("OK", status=200)

    except Exception as e:
        logger.error(f"Error processing lead created webhook: {e}")
        return Response("Error processing webhook", status=500)


async def process_new_lead(webhook_data: Dict[str, Any], resource_uri: str, resource_ids: list):
    """
    Process a new lead and initiate AI welcome sequence via Celery tasks.

    Steps:
    1. Fetch lead details from FUB
    2. Check if AI agent is enabled for this organization
    3. Check compliance (consent, DNC)
    4. Create conversation context
    5. Trigger welcome sequence via Celery task
    """
    try:
        import aiohttp
        import base64

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {base64.b64encode(f"{CREDS.FUB_API_KEY}:".encode()).decode()}',
        }

        if not resource_ids:
            logger.warning("No resource IDs in lead webhook")
            return

        person_id = resource_ids[0]

        # Fetch person details
        person_data = fub_client.get_person(person_id)

        if not person_data:
            logger.warning(f"Could not fetch person {person_id}")
            return

        # Extract contact info
        first_name = person_data.get('firstName', '')
        phones = person_data.get('phones', [])
        phone = phones[0].get('value') if phones else None

        if not phone:
            logger.info(f"No phone number for person {person_id}, skipping AI sequence")
            return

        logger.info(f"Processing new lead: {first_name} ({person_id})")

        # Resolve organization
        organization_id = await resolve_organization_for_person(person_id)
        user_id = await resolve_user_for_person(person_id, organization_id)

        if not organization_id or not user_id:
            logger.warning(f"Could not resolve organization/user for new lead {person_id}")
            return

        # Check if AI agent is enabled (global switch)
        settings = await get_ai_agent_settings(organization_id, user_id)
        if not settings or not settings.get('is_enabled', True):
            logger.info(f"AI agent not enabled for organization {organization_id}")
            return

        # Check stage eligibility BEFORE enabling AI
        stage_name = person_data.get('stageName', '') or person_data.get('stage', '')
        if stage_name:
            from app.ai_agent.compliance_checker import ComplianceChecker
            stage_checker = ComplianceChecker(supabase_client=supabase)
            excluded_stages = settings.get('excluded_stages', [])
            is_eligible, _, stage_reason = stage_checker.check_stage_eligibility(stage_name, excluded_stages)
            if not is_eligible:
                logger.info(f"Skipping new lead {person_id} - stage '{stage_name}' excluded: {stage_reason}")
                return

        # Check if auto_enable_new_leads is set
        auto_enable_new_leads = settings.get('auto_enable_new_leads', False)

        if auto_enable_new_leads:
            # Auto-enable AI for this new lead
            from app.ai_agent.lead_ai_settings_service import LeadAISettingsServiceSingleton
            lead_ai_service = LeadAISettingsServiceSingleton.get_instance(supabase)

            success = await lead_ai_service.enable_ai_for_lead(
                fub_person_id=person_id,
                organization_id=organization_id,
                user_id=user_id,
                reason='auto_enable_new_leads',
                enabled_by='system',
            )

            if success:
                logger.info(f"AI auto-enabled for new lead {person_id} (auto_enable_new_leads=True)")
            else:
                logger.warning(f"Failed to auto-enable AI for new lead {person_id}")
        else:
            # Auto-enable is OFF - new leads require manual opt-in
            logger.info(f"Skipping new lead {person_id} - auto_enable_new_leads is OFF (requires manual opt-in via FUB tag)")
            return

        # Check compliance
        from app.ai_agent.compliance_checker import ComplianceChecker
        compliance_checker = ComplianceChecker(supabase_client=supabase)

        # Record implied consent for FUB leads (they inquired through a form)
        await compliance_checker.record_consent(
            fub_person_id=person_id,
            organization_id=organization_id,
            phone_number=phone,
            consent_source="fub_import",
        )

        # Check compliance before proceeding
        configured_timezone = settings.get('timezone', 'America/Denver') if settings else 'America/Denver'
        compliance_result = await compliance_checker.check_sms_compliance(
            fub_person_id=person_id,
            organization_id=organization_id,
            phone_number=phone,
            recipient_timezone=configured_timezone,
        )

        if not compliance_result.can_send:
            logger.warning(f"Cannot initiate AI for new lead {person_id}: {compliance_result.reason}")
            return

        # Ensure lead exists in database before creating conversation
        try:
            from app.models.lead import Lead
            import json

            # Check if lead already exists
            existing_lead = supabase.table("leads").select("id").eq(
                "fub_person_id", str(person_id)
            ).eq(
                "user_id", user_id
            ).execute()

            if not existing_lead.data:
                # Lead doesn't exist, create it
                lead_obj = Lead.from_fub(person_data)
                lead_dict = {
                    key: value
                    for key, value in lead_obj.to_dict().items()
                    if value is not None
                }
                lead_dict.pop("fub_id", None)
                lead_dict["fub_person_id"] = str(person_id)
                lead_dict["user_id"] = user_id
                lead_dict["organization_id"] = organization_id

                if lead_dict.get("price") is None:
                    lead_dict["price"] = 0
                if isinstance(lead_dict.get("tags"), list):
                    lead_dict["tags"] = json.dumps(lead_dict["tags"])

                # Insert the lead
                supabase.table("leads").insert(lead_dict).execute()
                logger.info(f"Created lead record in database for person {person_id}")
            else:
                logger.info(f"Lead record already exists for person {person_id}")

        except Exception as lead_error:
            logger.error(f"Error creating lead record: {lead_error}")
            # Continue anyway - the conversation can still work

        # Create conversation context
        from app.ai_agent.conversation_manager import ConversationManager
        conversation_manager = ConversationManager(supabase_client=supabase)

        context = await conversation_manager.get_or_create_conversation(
            fub_person_id=person_id,
            user_id=user_id,
            organization_id=organization_id,
            lead_data=person_data,
        )

        # ==================== PROACTIVE AI OUTREACH ====================
        # Trigger contextual proactive outreach (replaces old generic welcome sequence)
        logger.info(f"🚀 Triggering proactive AI outreach for lead {person_id}")

        try:
            from app.ai_agent.proactive_outreach_orchestrator import trigger_proactive_outreach

            outreach_result = await trigger_proactive_outreach(
                fub_person_id=person_id,
                organization_id=organization_id,
                user_id=user_id,
                trigger_reason="new_lead_ai_enabled",
                enable_type="auto",
                supabase_client=supabase,
            )

            if outreach_result["success"]:
                logger.info(f"✅ Proactive outreach completed: {', '.join(outreach_result['actions_taken'])}")
            else:
                logger.warning(f"⚠️  Proactive outreach issues: {', '.join(outreach_result.get('errors', []))}")

        except Exception as outreach_error:
            logger.error(f"❌ Proactive outreach failed: {outreach_error}", exc_info=True)
        # ==================== END PROACTIVE OUTREACH ====================

    except Exception as e:
        logger.error(f"Error processing new lead: {e}")
        import traceback
        traceback.print_exc()


async def generate_ai_response(context, incoming_message: str) -> Optional[Dict[str, Any]]:
    """
    Generate AI response using Claude.

    Args:
        context: Conversation context
        incoming_message: The message from the lead

    Returns:
        Dict with response, next_state, extracted_info, lead_score_delta, should_handoff
    """
    try:
        import anthropic
        import json
        import os

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error("ANTHROPIC_API_KEY not configured")
            return None

        client = anthropic.Anthropic(api_key=api_key)

        # Build conversation context
        from app.ai_agent.conversation_manager import ConversationManager
        manager = ConversationManager()
        prompt_context = manager.get_conversation_prompt_context(context)

        # Build conversation history
        history_str = ""
        for msg in context.conversation_history[-10:]:  # Last 10 messages
            role = "Lead" if msg['direction'] == 'inbound' else "You"
            history_str += f"{role}: {msg['content']}\n"

        system_prompt = f"""You are a friendly, casual real estate assistant named {context.agent_name or 'Sarah'} helping people find their perfect home, working with {context.brokerage_name or 'our team'}.

PERSONALITY: Friendly & Casual
- Use first names, contractions, and warm language
- Be conversational like texting a helpful friend
- Show genuine interest in helping them
- Never be pushy or salesy
- Use occasional casual phrases like "Totally!", "For sure!", "No worries!"

CURRENT CONTEXT:
{prompt_context}

CONVERSATION HISTORY:
{history_str}

RULES:
- Be substantive and conversational for SMS
- Ask ONE question at a time
- Never pressure or use urgency tactics
- If lead seems frustrated, asks for human, or uses profanity, set should_handoff to true
- Detect and extract qualification info (timeline, budget, location, pre_approved status)

Respond with ONLY valid JSON (no markdown, no explanation):
{{
    "response": "Your SMS message here",
    "next_state": "qualifying|scheduling|objection_handling|nurture|handed_off",
    "extracted_info": {{"timeline": null, "budget": null, "location": null, "pre_approved": null}},
    "lead_score_delta": 0,
    "should_handoff": false,
    "handoff_reason": null,
    "intent": "greeting|question|objection|interest|scheduling|human_request|other"
}}"""

        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[
                {"role": "user", "content": f"Lead said: {incoming_message}"}
            ],
            system=system_prompt,
        )

        # Parse response
        response_text = response.content[0].text.strip()

        # Try to extract JSON
        try:
            # Handle potential markdown code blocks
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            result = json.loads(response_text)
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.error(f"Response was: {response_text}")
            # Return a safe fallback
            return {
                "response": "Thanks for reaching out! Let me connect you with one of our agents who can help.",
                "next_state": "handed_off",
                "extracted_info": {},
                "lead_score_delta": 0,
                "should_handoff": True,
                "handoff_reason": "AI response parsing failed",
                "intent": "other",
            }

    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        return None


async def schedule_welcome_sequence(context, settings: Dict[str, Any]):
    """
    Schedule the welcome message sequence for a new lead.

    This is a FALLBACK when Celery is unavailable. It sends both SMS and email
    immediately via Playwright so they appear in FUB.

    Sequence:
    1. Immediate SMS: Welcome message via Playwright
    2. Immediate Email: AI-generated welcome email via Playwright
    """
    try:
        from datetime import timedelta
        from app.messaging.playwright_sms_service import send_sms_with_auto_credentials, send_email_with_auto_credentials

        # Get lead info
        first_name = context.lead_first_name or "there"
        agent_name = settings.get('agent_name', 'Sarah')
        brokerage = settings.get('brokerage_name', 'our team')
        fub_person_id = context.fub_person_id
        user_id = context.user_id
        organization_id = context.organization_id

        logger.info(f"[FALLBACK] Sending immediate SMS + Email for lead {fub_person_id} (Celery unavailable)")

        # ================================================================
        # 1. SEND WELCOME SMS VIA PLAYWRIGHT
        # ================================================================
        welcome_sms = f"Hey {first_name}! I'm {agent_name} with {brokerage}. Saw you were looking at properties - that's exciting! Are you just starting to explore or getting closer to making a move?"

        try:
            sms_result = await send_sms_with_auto_credentials(
                person_id=fub_person_id,
                message=welcome_sms,
                user_id=user_id,
                organization_id=organization_id,
                supabase_client=supabase,
            )

            if sms_result.get("success"):
                logger.info(f"[FALLBACK] SMS sent to lead {fub_person_id}")
            else:
                logger.error(f"[FALLBACK] SMS failed for lead {fub_person_id}: {sms_result.get('error')}")
        except Exception as sms_error:
            logger.error(f"[FALLBACK] SMS exception for lead {fub_person_id}: {sms_error}")

        # ================================================================
        # 2. GENERATE AND SEND WELCOME EMAIL VIA PLAYWRIGHT
        # ================================================================
        try:
            # Get person data for AI email generation
            person_data = fub_client.get_person(fub_person_id)

            if person_data:
                # Get lead's email
                emails = person_data.get('emails', [])
                lead_email = emails[0].get('value') if emails else None

                if lead_email:
                    # Get recent events for context
                    import requests
                    import base64
                    import os
                    events = []
                    try:
                        fub_api_key = os.getenv('FUB_API_KEY') or CREDS.FUB_API_KEY
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
                    except Exception as e:
                        logger.warning(f"Could not fetch events for email context: {e}")

                    # Generate AI-powered email
                    from app.ai_agent.initial_outreach_generator import generate_initial_outreach

                    outreach = await generate_initial_outreach(
                        person_data=person_data,
                        events=events,
                        agent_name=agent_name,
                        agent_email=settings.get('agent_email', ''),
                        agent_phone=settings.get('agent_phone', ''),
                        brokerage_name=brokerage,
                    )

                    if outreach and outreach.email_body:
                        # Send email via Playwright (so it appears in FUB)
                        email_result = await send_email_with_auto_credentials(
                            person_id=fub_person_id,
                            subject=outreach.email_subject,
                            body=outreach.email_body,
                            user_id=user_id,
                            organization_id=organization_id,
                            supabase_client=supabase,
                        )

                        if email_result.get("success"):
                            logger.info(f"[FALLBACK] Email sent to lead {fub_person_id} via Playwright")

                            # Log to database
                            supabase.table("ai_message_log").insert({
                                "fub_person_id": fub_person_id,
                                "direction": "outbound",
                                "channel": "email",
                                "message_content": outreach.email_subject,
                                "intent_detected": "fallback_welcome_email",
                                "created_at": datetime.utcnow().isoformat(),
                            }).execute()
                        else:
                            logger.error(f"[FALLBACK] Email failed for lead {fub_person_id}: {email_result.get('error')}")
                    else:
                        logger.warning(f"[FALLBACK] Could not generate AI email for lead {fub_person_id}")
                else:
                    logger.info(f"[FALLBACK] No email address for lead {fub_person_id}, skipping email")
            else:
                logger.warning(f"[FALLBACK] Could not fetch person data for lead {fub_person_id}")

        except Exception as email_error:
            logger.error(f"[FALLBACK] Email exception for lead {fub_person_id}: {email_error}")

        logger.info(f"[FALLBACK] Completed welcome sequence for lead {fub_person_id}")

    except Exception as e:
        logger.error(f"Error in fallback welcome sequence: {e}")
        import traceback
        traceback.print_exc()


async def resolve_organization_for_person(person_id: int) -> Optional[str]:
    """Resolve the organization ID for a FUB person."""
    # In production, this would look up based on FUB account mapping
    # For now, return a default or lookup from configuration
    try:
        # Try to find a user with this FUB account configured
        result = supabase.table("users").select("organization_id").not_.is_("fub_api_key", "null").limit(1).execute()
        if result.data:
            return result.data[0].get("organization_id")
    except Exception as e:
        logger.error(f"Error resolving organization: {e}")

    return None


async def resolve_user_for_person(person_id: int, organization_id: str) -> Optional[str]:
    """Resolve the user ID for handling this person."""
    if not organization_id:
        return None
    try:
        # Get assigned user if there is one, otherwise get organization owner
        result = supabase.table("users").select("id").eq("organization_id", organization_id).eq("role", "admin").limit(1).execute()
        if result.data:
            return result.data[0].get("id")
    except Exception as e:
        logger.error(f"Error resolving user: {e}")

    return None


async def get_fub_api_key_for_org(organization_id: str) -> Optional[str]:
    """
    Get the FUB API key for a specific organization.

    Used for multi-tenant webhook handling - each organization has their own
    FUB account and API key.

    Args:
        organization_id: The organization ID

    Returns:
        FUB API key string or None if not found
    """
    if not organization_id:
        return None

    try:
        # Get the admin user for this organization who has FUB configured
        result = supabase.table("users").select("fub_api_key").eq(
            "organization_id", organization_id
        ).not_.is_("fub_api_key", "null").limit(1).execute()

        if result.data and result.data[0].get("fub_api_key"):
            return result.data[0]["fub_api_key"]

    except Exception as e:
        logger.error(f"Error getting FUB API key for org {organization_id}: {e}")

    return None


async def get_fub_user_id_for_user(user_id: str) -> Optional[int]:
    """
    Get the FUB user ID for a LeadSynergy user.

    This maps LeadSynergy users to their FUB user accounts so that
    AI messages can be sent from the assigned agent's phone number.

    Args:
        user_id: LeadSynergy user ID (UUID)

    Returns:
        FUB user ID (integer) or None if not found
    """
    if not user_id:
        return None

    try:
        # First, try to get the cached FUB user ID from our users table
        result = supabase.table("users").select("fub_user_id").eq("id", user_id).single().execute()

        if result.data and result.data.get("fub_user_id"):
            return result.data["fub_user_id"]

        # If not cached, try to look up via FUB API
        # This requires the user's FUB API key to be configured
        user_result = supabase.table("users").select("fub_api_key, email").eq("id", user_id).single().execute()

        if user_result.data and user_result.data.get("fub_api_key"):
            # Query FUB for the user ID using their API key
            import base64
            import aiohttp

            api_key = user_result.data["fub_api_key"]
            email = user_result.data.get("email", "")

            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Basic {base64.b64encode(f"{api_key}:".encode()).decode()}',
            }

            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get("https://api.followupboss.com/v1/me") as response:
                    if response.status == 200:
                        me_data = await response.json()
                        fub_user_id = me_data.get("id")

                        if fub_user_id:
                            # Cache the FUB user ID for future lookups
                            supabase.table("users").update({
                                "fub_user_id": fub_user_id
                            }).eq("id", user_id).execute()

                            logger.info(f"Cached FUB user ID {fub_user_id} for user {user_id}")
                            return fub_user_id

        logger.warning(f"Could not determine FUB user ID for user {user_id}")
        return None

    except Exception as e:
        logger.error(f"Error getting FUB user ID for user {user_id}: {e}")
        return None


async def get_ai_agent_settings(organization_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Get AI agent settings for the organization/user."""
    try:
        # Try user-specific settings first
        result = supabase.table("ai_agent_settings").select("*").eq("user_id", user_id).execute()
        if result.data:
            return result.data[0]

        # Fall back to organization settings
        result = supabase.table("ai_agent_settings").select("*").eq("organization_id", organization_id).is_("user_id", "null").execute()
        if result.data:
            return result.data[0]

        # Return defaults
        return {
            "is_enabled": True,
            "auto_enable_new_leads": False,
            "response_delay_seconds": 10,
            "working_hours_start": "08:00",
            "working_hours_end": "20:00",
            "timezone": "America/New_York",
            "auto_handoff_score": 80,
            "max_ai_messages_per_lead": 15,
            "personality_tone": "friendly_casual",
            "agent_name": "Sarah",
            "brokerage_name": "our team",
        }

    except Exception as e:
        logger.error(f"Error getting AI agent settings: {e}")
        return None


async def log_ai_message(
    conversation_id: Optional[str],
    fub_person_id: int,
    direction: str,
    channel: str,
    message_content: str,
    ai_model: str = "claude-3-5-sonnet",
    lead_score_delta: int = 0,
    extracted_data: Dict[str, Any] = None,
    intent_detected: str = None,
    tokens_used: int = None,
    response_time_ms: int = None,
):
    """Log an AI message for analytics and auditing."""
    try:
        row = {
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "fub_person_id": fub_person_id,
            "direction": direction,
            "channel": channel,
            "message_content": message_content,
            "ai_model": ai_model,
            "lead_score_delta": lead_score_delta,
            "extracted_data": extracted_data or {},
            "intent_detected": intent_detected,
        }
        if tokens_used is not None:
            row["tokens_used"] = tokens_used
        if response_time_ms is not None:
            row["response_time_ms"] = response_time_ms
        supabase.table("ai_message_log").insert(row).execute()
    except Exception as e:
        logger.error(f"Error logging AI message: {e}")


# ============================================
# INCREMENTAL CACHE UPDATE WEBHOOK HANDLERS
# ============================================
# These handlers keep the lead profile cache fresh by
# incrementally updating it when FUB events occur.
# This avoids full re-fetches and keeps our AI agent
# context up-to-date in real-time.


@ai_webhook_bp.route('/cache/email-created', methods=['POST'])
def handle_email_created_webhook():
    """
    Handle emailsCreated webhook - incrementally update cache.

    This is triggered when:
    - An email is sent to or received from a lead
    - An email is logged in FUB
    """
    try:
        webhook_data = request.get_json()
        event = webhook_data.get('event', '').lower()

        if event != 'emailscreated':
            return Response("Event not applicable", status=200)

        run_async_task(process_email_cache_update(webhook_data))
        return Response("OK", status=200)
    except Exception as e:
        logger.error(f"Error processing email webhook: {e}")
        return Response("Error", status=500)


async def process_email_cache_update(webhook_data: Dict[str, Any]):
    """Process email created event and update cache incrementally."""
    try:
        import aiohttp
        import base64

        resource_uri = webhook_data.get('uri')
        resource_ids = webhook_data.get('resourceIds', [])

        if not resource_ids or not resource_uri:
            return

        # Fetch email details
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {base64.b64encode(f"{CREDS.FUB_API_KEY}:".encode()).decode()}',
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(resource_uri) as response:
                if response.status != 200:
                    return
                email_data = await response.json()

        emails = email_data.get('emails', [])
        if not emails:
            return

        email = emails[0]
        person_id = email.get('personId')

        if not person_id:
            return

        # CRITICAL: If this is an INCOMING email from the lead, cancel pending follow-ups
        # This ensures the AI agent stops automation when the lead responds via email
        is_incoming = email.get('isIncoming', False)
        if is_incoming:
            logger.info(f"[EMAIL] Incoming email from lead {person_id} - cancelling pending sequences")
            from app.scheduler.ai_tasks import cancel_lead_sequences
            cancel_lead_sequences.delay(
                fub_person_id=person_id,
                reason="lead_responded_email"
            )

        # Resolve organization
        organization_id = await resolve_organization_for_person(person_id)
        if not organization_id:
            return

        # Update cache incrementally
        cache = get_profile_cache()
        await cache.add_email(
            fub_person_id=person_id,
            organization_id=organization_id,
            email_data={
                "id": email.get("id"),
                "subject": email.get("subject"),
                "body": email.get("body"),
                "isIncoming": email.get("isIncoming"),
                "created": email.get("created"),
                "from": email.get("from"),
                "to": email.get("to"),
            }
        )

        logger.debug(f"Cache updated with new email for person {person_id}")

    except Exception as e:
        logger.error(f"Error updating cache for email: {e}")


@ai_webhook_bp.route('/cache/note-created', methods=['POST'])
def handle_note_created_webhook():
    """
    Handle notesCreated webhook - incrementally update cache.
    """
    try:
        webhook_data = request.get_json()
        event = webhook_data.get('event', '').lower()

        if event != 'notescreated':
            return Response("Event not applicable", status=200)

        run_async_task(process_note_cache_update(webhook_data))
        return Response("OK", status=200)
    except Exception as e:
        logger.error(f"Error processing note webhook: {e}")
        return Response("Error", status=500)


async def process_note_cache_update(webhook_data: Dict[str, Any]):
    """Process note created event and update cache incrementally."""
    try:
        import aiohttp
        import base64

        resource_uri = webhook_data.get('uri')
        resource_ids = webhook_data.get('resourceIds', [])

        if not resource_ids or not resource_uri:
            return

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {base64.b64encode(f"{CREDS.FUB_API_KEY}:".encode()).decode()}',
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(resource_uri) as response:
                if response.status != 200:
                    return
                note_data = await response.json()

        notes = note_data.get('notes', [])
        if not notes:
            return

        note = notes[0]
        person_id = note.get('personId')

        if not person_id:
            return

        organization_id = await resolve_organization_for_person(person_id)
        if not organization_id:
            return

        cache = get_profile_cache()
        await cache.add_note(
            fub_person_id=person_id,
            organization_id=organization_id,
            note_data={
                "id": note.get("id"),
                "body": note.get("body"),
                "createdBy": note.get("createdBy"),
                "created": note.get("created"),
                "isHtml": note.get("isHtml"),
            }
        )

        logger.debug(f"Cache updated with new note for person {person_id}")

    except Exception as e:
        logger.error(f"Error updating cache for note: {e}")


@ai_webhook_bp.route('/cache/event-created', methods=['POST'])
def handle_event_created_webhook():
    """
    Handle eventsCreated webhook - incrementally update cache.
    """
    try:
        webhook_data = request.get_json()
        event = webhook_data.get('event', '').lower()

        if event != 'eventscreated':
            return Response("Event not applicable", status=200)

        run_async_task(process_event_cache_update(webhook_data))
        return Response("OK", status=200)
    except Exception as e:
        logger.error(f"Error processing event webhook: {e}")
        return Response("Error", status=500)


async def process_event_cache_update(webhook_data: Dict[str, Any]):
    """Process event created and update cache incrementally."""
    try:
        import aiohttp
        import base64

        resource_uri = webhook_data.get('uri')
        resource_ids = webhook_data.get('resourceIds', [])

        if not resource_ids or not resource_uri:
            return

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {base64.b64encode(f"{CREDS.FUB_API_KEY}:".encode()).decode()}',
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(resource_uri) as response:
                if response.status != 200:
                    return
                event_data = await response.json()

        events = event_data.get('events', [])
        if not events:
            return

        event = events[0]
        person_id = event.get('personId')

        if not person_id:
            return

        organization_id = await resolve_organization_for_person(person_id)
        if not organization_id:
            return

        cache = get_profile_cache()
        await cache.add_event(
            fub_person_id=person_id,
            organization_id=organization_id,
            event_data={
                "id": event.get("id"),
                "type": event.get("type"),
                "source": event.get("source"),
                "description": event.get("description"),
                "property": event.get("property"),
                "created": event.get("created"),
            }
        )

        logger.debug(f"Cache updated with new event for person {person_id}")

    except Exception as e:
        logger.error(f"Error updating cache for event: {e}")


@ai_webhook_bp.route('/cache/call-created', methods=['POST'])
def handle_call_created_webhook():
    """
    Handle callsCreated webhook - incrementally update cache.
    """
    try:
        webhook_data = request.get_json()
        event = webhook_data.get('event', '').lower()

        if event != 'callscreated':
            return Response("Event not applicable", status=200)

        run_async_task(process_call_cache_update(webhook_data))
        return Response("OK", status=200)
    except Exception as e:
        logger.error(f"Error processing call webhook: {e}")
        return Response("Error", status=500)


async def process_call_cache_update(webhook_data: Dict[str, Any]):
    """Process call created and update cache incrementally."""
    try:
        import aiohttp
        import base64

        resource_uri = webhook_data.get('uri')
        resource_ids = webhook_data.get('resourceIds', [])

        if not resource_ids or not resource_uri:
            return

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {base64.b64encode(f"{CREDS.FUB_API_KEY}:".encode()).decode()}',
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(resource_uri) as response:
                if response.status != 200:
                    return
                call_data = await response.json()

        calls = call_data.get('calls', [])
        if not calls:
            return

        call = calls[0]
        person_id = call.get('personId')

        if not person_id:
            return

        # CRITICAL: If this is an INCOMING call or a CONNECTED call, cancel pending follow-ups
        # This ensures the AI agent stops automation when there's phone contact with the lead
        direction = call.get('direction', '').lower()
        outcome = call.get('outcome', '').lower()

        # Cancel on: incoming calls, or any connected call (agent spoke with lead)
        if direction == 'incoming' or outcome in ['connected', 'answered', 'voicemail']:
            logger.info(f"[CALL] Call detected for lead {person_id} (direction={direction}, outcome={outcome}) - cancelling pending sequences")
            from app.scheduler.ai_tasks import cancel_lead_sequences
            cancel_lead_sequences.delay(
                fub_person_id=person_id,
                reason=f"phone_contact_{direction}_{outcome}"
            )

        organization_id = await resolve_organization_for_person(person_id)
        if not organization_id:
            return

        cache = get_profile_cache()
        await cache.add_call(
            fub_person_id=person_id,
            organization_id=organization_id,
            call_data={
                "id": call.get("id"),
                "direction": call.get("direction"),
                "duration": call.get("duration"),
                "outcome": call.get("outcome"),
                "from": call.get("from"),
                "to": call.get("to"),
                "created": call.get("created"),
                "recordingUrl": call.get("recordingUrl"),
            }
        )

        logger.debug(f"Cache updated with new call for person {person_id}")

    except Exception as e:
        logger.error(f"Error updating cache for call: {e}")


@ai_webhook_bp.route('/cache/person-updated', methods=['POST'])
def handle_person_updated_webhook():
    """
    Handle peopleUpdated webhook - refresh person data in cache.

    This is triggered when lead info changes (stage, tags, custom fields, etc.)
    We only refresh the person data, not the entire cache.
    """
    try:
        webhook_data = request.get_json()
        event = webhook_data.get('event', '').lower()

        if event != 'peopleupdated':
            return Response("Event not applicable", status=200)

        run_async_task(process_person_cache_update(webhook_data))
        return Response("OK", status=200)
    except Exception as e:
        logger.error(f"Error processing person update webhook: {e}")
        return Response("Error", status=500)


async def process_person_cache_update(webhook_data: Dict[str, Any]):
    """Process person updated and refresh person data in cache."""
    try:
        resource_ids = webhook_data.get('resourceIds', [])

        if not resource_ids:
            return

        person_id = resource_ids[0]

        organization_id = await resolve_organization_for_person(person_id)
        if not organization_id:
            return

        # Fetch fresh person data and update cache
        cache = get_profile_cache()
        await cache.update_person_data(
            fub_person_id=person_id,
            organization_id=organization_id,
            person_data=None,  # Will fetch fresh from FUB
        )

        logger.debug(f"Cache refreshed person data for {person_id}")

    except Exception as e:
        logger.error(f"Error updating cache for person: {e}")


@ai_webhook_bp.route('/cache/text-created', methods=['POST'])
def handle_text_cache_webhook():
    """
    Handle textMessagesCreated webhook - incrementally update cache.

    Note: This is SEPARATE from the main text-received handler.
    This only updates the cache; the main handler processes AI responses.
    """
    try:
        webhook_data = request.get_json()
        event = webhook_data.get('event', '').lower()

        if event != 'textmessagescreated':
            return Response("Event not applicable", status=200)

        run_async_task(process_text_cache_update(webhook_data))
        return Response("OK", status=200)
    except Exception as e:
        logger.error(f"Error processing text cache webhook: {e}")
        return Response("Error", status=500)


async def process_text_cache_update(webhook_data: Dict[str, Any]):
    """Process text message and update cache incrementally."""
    try:
        import aiohttp
        import base64

        resource_uri = webhook_data.get('uri')
        resource_ids = webhook_data.get('resourceIds', [])

        if not resource_ids or not resource_uri:
            return

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {base64.b64encode(f"{CREDS.FUB_API_KEY}:".encode()).decode()}',
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(resource_uri) as response:
                if response.status != 200:
                    return
                msg_data = await response.json()

        messages = msg_data.get('textmessages', [])
        if not messages:
            return

        msg = messages[0]
        person_id = msg.get('personId')

        if not person_id:
            return

        organization_id = await resolve_organization_for_person(person_id)
        if not organization_id:
            return

        cache = get_profile_cache()
        await cache.add_text_message(
            fub_person_id=person_id,
            organization_id=organization_id,
            message_data={
                "id": msg.get("id"),
                "message": msg.get("message"),
                "isIncoming": msg.get("isIncoming"),
                "fromNumber": msg.get("fromNumber"),
                "toNumber": msg.get("toNumber"),
                "created": msg.get("created"),
            }
        )

        logger.debug(f"Cache updated with new text for person {person_id}")

    except Exception as e:
        logger.error(f"Error updating cache for text: {e}")


@ai_webhook_bp.route('/tag-sync', methods=['POST'])
def handle_tag_sync_webhook():
    """
    Handle FUB tag changes and sync with AI settings.
    
    When "AI Follow-up" tag is added → enable AI for lead
    When "AI Follow-up" tag is removed → disable AI for lead
    """
    try:
        webhook_data = request.get_json()
        logger.info(f"Received tag sync webhook: {webhook_data.get('event')}")
        
        event = webhook_data.get('event', '').lower()
        
        if event not in ['tagadded', 'tagremoved']:
            return Response("Event not applicable", status=200)
        
        # Process asynchronously
        run_async_task(process_tag_change(webhook_data, event))
        
        return Response("OK", status=200)
        
    except Exception as e:
        logger.error(f"Error processing tag sync webhook: {e}")
        return Response("Error processing webhook", status=500)


async def process_tag_change(webhook_data: Dict[str, Any], event: str):
    """
    Process tag changes and sync with AI settings.
    
    Args:
        webhook_data: Webhook payload from FUB
        event: 'tagadded' or 'tagremoved'
    """
    try:
        # Extract tag info
        tag_name = webhook_data.get('data', {}).get('tag', '')
        person_id = webhook_data.get('data', {}).get('personId')
        
        if not person_id:
            logger.warning("No person ID in tag webhook")
            return
        
        # Check if it's the AI Follow-up tag
        ai_tag_variations = ['ai follow-up', 'ai followup', 'ai-follow-up', 'ai follow up']
        if tag_name.lower() not in ai_tag_variations:
            logger.debug(f"Tag '{tag_name}' is not an AI tag, ignoring")
            return
        
        logger.info(f"AI tag '{tag_name}' {event} for person {person_id}")
        
        # Resolve organization/user
        organization_id = await resolve_organization_for_person(person_id)
        user_id = await resolve_user_for_person(person_id, organization_id)
        
        if not organization_id or not user_id:
            logger.warning(f"Could not resolve organization/user for person {person_id}")
            return
        
        # Get AI settings service
        from app.ai_agent.lead_ai_settings_service import LeadAISettingsServiceSingleton
        lead_ai_service = LeadAISettingsServiceSingleton.get_instance(supabase)
        
        if event == 'tagadded':
            # Check stage eligibility before enabling AI
            try:
                from app.database.fub_api_client import FUBApiClient
                fub_client = FUBApiClient()
                person_data = fub_client.get_person(str(person_id))
                stage_name = person_data.get('stageName', '') or person_data.get('stage', '') if person_data else ''
                if stage_name:
                    settings = await get_ai_agent_settings(organization_id, user_id)
                    excluded_stages = settings.get('excluded_stages', []) if settings else []
                    from app.ai_agent.compliance_checker import ComplianceChecker
                    stage_checker = ComplianceChecker(supabase_client=supabase)
                    is_eligible, _, reason = stage_checker.check_stage_eligibility(stage_name, excluded_stages)
                    if not is_eligible:
                        logger.info(f"Skipping AI enable for person {person_id} - stage '{stage_name}' excluded: {reason}")
                        return
            except Exception as stage_err:
                logger.warning(f"Stage check failed for {person_id}, proceeding: {stage_err}")

            # Enable AI for this lead
            success = await lead_ai_service.enable_ai_for_lead(
                fub_person_id=person_id,
                organization_id=organization_id,
                user_id=user_id,
                reason='fub_tag_added',
                enabled_by=user_id,
            )
            if success:
                logger.info(f"AI enabled for person {person_id} via FUB tag")

                # Trigger proactive outreach
                try:
                    from app.ai_agent.proactive_outreach_orchestrator import trigger_proactive_outreach
                    await trigger_proactive_outreach(
                        fub_person_id=int(person_id),
                        organization_id=organization_id,
                        user_id=user_id,
                        trigger_reason="fub_tag_added",
                        enable_type="manual",
                        supabase_client=supabase,
                    )
                except Exception as outreach_error:
                    logger.error(f"Proactive outreach failed for {person_id}: {outreach_error}")
            else:
                logger.error(f"Failed to enable AI for person {person_id}")
                
        elif event == 'tagremoved':
            # Disable AI for this lead
            success = await lead_ai_service.disable_ai_for_lead(
                fub_person_id=person_id,
                organization_id=organization_id,
            )
            if success:
                logger.info(f"AI disabled for person {person_id} via FUB tag removal")
            else:
                logger.error(f"Failed to disable AI for person {person_id}")
    
    except Exception as e:
        logger.error(f"Error processing tag change: {e}")
        import traceback
        traceback.print_exc()
