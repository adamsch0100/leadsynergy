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
from datetime import datetime
from typing import Dict, Any, Optional, List
from flask import Blueprint, request, Response
import uuid

from app.database.supabase_client import SupabaseClientSingleton
from app.database.fub_api_client import FUBApiClient
from app.utils.constants import Credentials

logger = logging.getLogger(__name__)

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

# Playwright SMS Service (lazy loaded)
_playwright_sms_service = None

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


def run_async_task(coroutine):
    """Helper function to run async tasks from sync code."""
    loop = asyncio.new_event_loop()

    def run_in_thread(loop, coro):
        asyncio.set_event_loop(loop)
        loop.run_until_complete(coro)
        loop.close()

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
    """
    try:
        webhook_data = request.get_json()
        logger.info(f"Received text message webhook: {webhook_data.get('event')}")

        event = webhook_data.get('event', '').lower()
        resource_uri = webhook_data.get('uri')
        resource_ids = webhook_data.get('resourceIds', [])

        if event != 'textmessagescreated':
            return Response("Event not applicable", status=200)

        # Process asynchronously
        run_async_task(process_inbound_text(webhook_data, resource_uri, resource_ids))

        return Response("OK", status=200)

    except Exception as e:
        logger.error(f"Error processing text webhook: {e}")
        return Response("Error processing webhook", status=500)


async def process_inbound_text(webhook_data: Dict[str, Any], resource_uri: str, resource_ids: list):
    """
    Process an inbound text message using the full AI Agent Service.

    Steps:
    1. Fetch the message details from FUB
    2. Check if it's an inbound message (not our own outbound)
    3. Build rich lead profile from FUB data
    4. Check compliance (opt-out keywords, rate limits)
    5. Process through full AI Agent Service (intent detection, qualification, objection handling)
    6. Send response via FUB native texting
    """
    global _playwright_sms_service

    try:
        import aiohttp
        import base64

        # Fetch message details
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {base64.b64encode(f"{CREDS.FUB_API_KEY}:".encode()).decode()}',
        }

        if not resource_ids:
            logger.warning("No resource IDs in text webhook")
            return

        message_id = resource_ids[0]

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
            return

        text_msg = text_messages[0]
        person_id = text_msg.get('personId')
        is_incoming = text_msg.get('isIncoming', False)
        message_content = text_msg.get('message', '')

        if not person_id:
            logger.warning("No person ID associated with text message")
            return

        # Only process incoming messages (from the lead)
        if not is_incoming:
            logger.info(f"Skipping outbound message for person {person_id}")
            return

        logger.info(f"Processing inbound text from person {person_id}: {message_content[:50]}...")

        # Import AI agent components
        from app.ai_agent.compliance_checker import ComplianceChecker
        from app.ai_agent.conversation_manager import ConversationManager, ConversationState

        # Get person details from FUB
        person_data = fub_client.get_person(person_id)

        # Resolve tenant (organization) for this person
        organization_id = await resolve_organization_for_person(person_id)
        user_id = await resolve_user_for_person(person_id, organization_id)

        if not organization_id or not user_id:
            logger.warning(f"Could not resolve organization/user for person {person_id}")
            return

        # Check for opt-out keywords first
        compliance_checker = ComplianceChecker(supabase_client=supabase)
        if compliance_checker.is_opt_out_keyword(message_content):
            logger.info(f"Opt-out keyword detected from person {person_id}")
            await compliance_checker.record_opt_out(
                fub_person_id=person_id,
                organization_id=organization_id,
                reason="STOP keyword received",
            )
            # Send confirmation via browser automation
            from app.messaging.playwright_sms_service import PlaywrightSMSService
            from app.ai_agent.settings_service import get_fub_browser_credentials

            credentials = await get_fub_browser_credentials(
                supabase_client=supabase,
                user_id=user_id,
                organization_id=organization_id,
            )

            if credentials:
                if _playwright_sms_service is None:
                    _playwright_sms_service = PlaywrightSMSService()

                agent_id = credentials.get("agent_id", user_id or "default")
                await _playwright_sms_service.send_sms(
                    agent_id=agent_id,
                    person_id=person_id,
                    message="You've been unsubscribed and won't receive any more messages from us. Reply START to opt back in.",
                    credentials=credentials,
                )
            return

        # Check compliance before responding
        phone = text_msg.get('to') or text_msg.get('from')
        compliance_result = await compliance_checker.check_sms_compliance(
            fub_person_id=person_id,
            organization_id=organization_id,
            phone_number=phone,
        )

        if not compliance_result.can_send:
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
        lead_profile = await build_lead_profile_from_fub(person_data, organization_id)

        # Get conversation history for context
        conversation_history = await get_conversation_history(person_id, limit=15)

        # Get or create conversation context
        conversation_manager = ConversationManager(supabase_client=supabase)
        context = await conversation_manager.get_or_create_conversation(
            fub_person_id=person_id,
            user_id=user_id,
            organization_id=organization_id,
            lead_data=person_data,
        )

        # Record inbound message
        context.add_message("inbound", message_content, "sms")

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
            logger.warning(f"Could not cancel sequences for lead {person_id}: {cancel_error}")
            # Continue processing even if cancellation fails

        # Process through full AI Agent Service
        agent_service = get_agent_service()
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

        if agent_response and agent_response.response_text:
            # Send response via FUB browser automation (Playwright)
            from app.messaging.playwright_sms_service import PlaywrightSMSService
            from app.ai_agent.settings_service import get_fub_browser_credentials

            # Get FUB browser credentials for this user/org
            credentials = await get_fub_browser_credentials(
                supabase_client=supabase,
                user_id=user_id,
                organization_id=organization_id,
            )

            if not credentials:
                logger.error(f"No FUB credentials found for user {user_id} / org {organization_id}")
                return

            # Get or create global playwright service
            if _playwright_sms_service is None:
                _playwright_sms_service = PlaywrightSMSService()

            agent_id = credentials.get("agent_id", user_id or "default")
            result = await _playwright_sms_service.send_sms(
                agent_id=agent_id,
                person_id=person_id,
                message=agent_response.response_text,
                credentials=credentials,
            )

            if result.get('success'):
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
                await compliance_checker.increment_message_count(person_id, organization_id)

                # Log the AI interaction
                await log_ai_message(
                    conversation_id=context.conversation_id,
                    fub_person_id=person_id,
                    direction="outbound",
                    channel="sms",
                    message_content=agent_response.response_text,
                    lead_score_delta=agent_response.lead_score_delta or 0,
                    extracted_data=agent_response.extracted_info or {},
                    intent_detected=agent_response.detected_intent.value if agent_response.detected_intent else None,
                )

                logger.info(f"AI response sent to person {person_id}: {agent_response.response_text[:50]}...")

        else:
            logger.warning(f"No AI response generated for person {person_id}")

    except Exception as e:
        logger.error(f"Error processing inbound text: {e}")
        import traceback
        traceback.print_exc()


async def build_lead_profile_from_fub(person_data: Dict[str, Any], organization_id: str) -> 'LeadProfile':
    """
    Build a rich LeadProfile from FUB person data.

    This creates the comprehensive lead context that the AI agent uses
    for personalized, context-aware responses.
    """
    from app.ai_agent.response_generator import LeadProfile

    # Extract basic info
    first_name = person_data.get('firstName', '')
    last_name = person_data.get('lastName', '')
    emails = person_data.get('emails', [])
    phones = person_data.get('phones', [])
    tags = person_data.get('tags', [])
    source = person_data.get('source', '')
    stage = person_data.get('stage', {})
    stage_name = stage.get('name', '') if isinstance(stage, dict) else str(stage)
    created = person_data.get('created', '')
    last_activity = person_data.get('lastActivity', '')

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
    property_type = None
    pre_approved = None

    for field in custom_fields:
        field_name = field.get('name', '').lower()
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
            pre_approved = field_value in ['Yes', 'yes', 'true', True, '1']

    # Calculate days since created
    days_in_system = 0
    if created:
        try:
            from dateutil.parser import parse as parse_date
            created_dt = parse_date(created)
            days_in_system = (datetime.now(created_dt.tzinfo) - created_dt).days
        except:
            pass

    # Get agent info
    agent_info = await get_agent_info_for_org(organization_id)

    # Calculate score label
    lead_score = person_data.get('leadScore', 0)
    if lead_score >= 70:
        score_label = "Hot"
    elif lead_score >= 40:
        score_label = "Warm"
    else:
        score_label = "Cold"

    # Build the profile using correct LeadProfile fields
    profile = LeadProfile(
        # Identity
        first_name=first_name,
        last_name=last_name,
        full_name=f"{first_name} {last_name}".strip(),
        email=emails[0].get('value', '') if emails else "",
        phone=phones[0].get('value', '') if phones else "",

        # Lead scoring and status
        score=lead_score,
        score_label=score_label,
        stage_name=stage_name,
        assigned_agent=agent_info.get('agent_name', ''),

        # Source
        source=source,

        # Property interests
        interested_property_type=property_type,
        preferred_cities=[city] if city else [],

        # Financial profile
        price_min=budget_min,
        price_max=budget_max,
        is_pre_approved=pre_approved,

        # Timeline
        timeline=timeline or "",

        # Tags
        tags=tags if tags else [],
    )

    return profile


async def get_conversation_history(fub_person_id: int, limit: int = 15) -> List[Dict[str, Any]]:
    """Get conversation history from database."""
    try:
        result = supabase.table("ai_message_log").select(
            "direction, channel, message_content, created_at"
        ).eq(
            "fub_person_id", fub_person_id
        ).order(
            "created_at", desc=True
        ).limit(limit).execute()

        if result.data:
            # Reverse to get chronological order
            history = list(reversed(result.data))
            return [
                {
                    "role": "lead" if h["direction"] == "inbound" else "agent",
                    "content": h["message_content"],
                    "channel": h["channel"],
                    "timestamp": h["created_at"],
                }
                for h in history
            ]
    except Exception as e:
        logger.error(f"Error fetching conversation history: {e}")

    return []


async def get_agent_info_for_org(organization_id: str) -> Dict[str, Any]:
    """Get agent info for an organization."""
    try:
        # Only select columns that exist in ai_agent_settings table
        result = supabase.table("ai_agent_settings").select(
            "agent_name, brokerage_name, team_members"
        ).eq("organization_id", organization_id).limit(1).execute()

        if result.data:
            data = result.data[0]
            return {
                "agent_name": data.get("agent_name", "Sarah"),
                "brokerage_name": data.get("brokerage_name", "our team"),
                "team_members": data.get("team_members", ""),
            }
    except Exception as e:
        logger.error(f"Error fetching agent info: {e}")

    return {
        "agent_name": "Sarah",
        "brokerage_name": "our team",
        "team_members": "",
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
        except:
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

        # Check if AI agent is enabled
        settings = await get_ai_agent_settings(organization_id, user_id)
        if not settings or not settings.get('is_enabled', True):
            logger.info(f"AI agent not enabled for organization {organization_id}")
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
        compliance_result = await compliance_checker.check_sms_compliance(
            fub_person_id=person_id,
            organization_id=organization_id,
            phone_number=phone,
        )

        if not compliance_result.can_send:
            logger.warning(f"Cannot initiate AI for new lead {person_id}: {compliance_result.reason}")
            return

        # Create conversation context
        from app.ai_agent.conversation_manager import ConversationManager
        conversation_manager = ConversationManager(supabase_client=supabase)

        context = await conversation_manager.get_or_create_conversation(
            fub_person_id=person_id,
            user_id=user_id,
            organization_id=organization_id,
            lead_data=person_data,
        )

        # Trigger welcome sequence via Celery task
        try:
            from app.scheduler.ai_tasks import start_new_lead_sequence
            start_new_lead_sequence.delay(
                fub_person_id=person_id,
                sequence_type="new_lead_24h",
            )
            logger.info(f"AI welcome sequence triggered for lead {person_id}")
        except Exception as celery_error:
            logger.error(f"Failed to trigger Celery task: {celery_error}")
            # Fallback to inline scheduling
            await schedule_welcome_sequence(context, settings)

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
- Keep responses under 160 characters for SMS
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

    Sequence:
    1. Immediate (or slight delay): Welcome message
    2. 15 min: Follow-up if no response
    3. 1 hour: Email intro
    4. 4 hours: Second text attempt
    """
    try:
        from datetime import timedelta

        # Get first name
        first_name = context.lead_first_name or "there"
        agent_name = settings.get('agent_name', 'Sarah')
        brokerage = settings.get('brokerage_name', 'our team')

        # Welcome message (send after short delay for more natural feel)
        welcome_msg = f"Hey {first_name}! I'm {agent_name} with {brokerage}. Saw you were looking at properties - that's exciting! Are you just starting to explore or getting closer to making a move?"

        # Schedule messages
        now = datetime.utcnow()
        delay_seconds = settings.get('response_delay_seconds', 30)

        messages_to_schedule = [
            {
                "scheduled_for": now + timedelta(seconds=delay_seconds),
                "message_content": welcome_msg,
                "message_template": "WELCOME_001",
                "channel": "sms",
            },
        ]

        for msg_data in messages_to_schedule:
            supabase.table("scheduled_messages").insert({
                "id": str(uuid.uuid4()),
                "conversation_id": context.conversation_id,
                "fub_person_id": context.fub_person_id,
                "user_id": context.user_id,
                "organization_id": context.organization_id,
                "channel": msg_data["channel"],
                "message_template": msg_data["message_template"],
                "message_content": msg_data["message_content"],
                "scheduled_for": msg_data["scheduled_for"].isoformat(),
                "status": "pending",
            }).execute()

        logger.info(f"Scheduled {len(messages_to_schedule)} messages for conversation {context.conversation_id}")

    except Exception as e:
        logger.error(f"Error scheduling welcome sequence: {e}")


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
    try:
        # Get assigned user if there is one, otherwise get organization owner
        result = supabase.table("users").select("id").eq("organization_id", organization_id).eq("role", "admin").limit(1).execute()
        if result.data:
            return result.data[0].get("id")
    except Exception as e:
        logger.error(f"Error resolving user: {e}")

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
            "response_delay_seconds": 30,
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
):
    """Log an AI message for analytics and auditing."""
    try:
        supabase.table("ai_message_log").insert({
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
        }).execute()
    except Exception as e:
        logger.error(f"Error logging AI message: {e}")
