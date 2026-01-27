"""
Test 7-Day No-Response Sequence for a Lead

This script generates the full sequence of AI-powered SMS and Email messages
that would be sent over 7 days if the lead doesn't respond.

Usage:
    python scripts/test_7day_sequence.py 3294
"""

import asyncio
import os
import sys
import argparse
import logging
import re
from datetime import datetime, timedelta

# Fix Windows console encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Load environment variables
from dotenv import load_dotenv
load_dotenv()


def clean_text(text: str) -> str:
    """Remove emojis and special characters that cause encoding issues."""
    # Remove emojis and other problematic characters
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub('', text)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# Add Backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# 7-Day No-Response Sequence Definition
SEVEN_DAY_SEQUENCE = [
    # Day 0 - Initial Outreach
    {"day": 0, "hour": 0, "channel": "sms", "type": "initial", "description": "Initial SMS - AI personalized welcome"},
    {"day": 0, "hour": 0, "channel": "email", "type": "initial", "description": "Initial Email - Full intro + value offer"},

    # Day 0 - Same day follow-up (4 hours later)
    {"day": 0, "hour": 4, "channel": "sms", "type": "followup_gentle", "description": "Gentle SMS check-in"},

    # Day 1 - Next day
    {"day": 1, "hour": 10, "channel": "sms", "type": "followup_value", "description": "Value-add SMS with market insight"},
    {"day": 1, "hour": 14, "channel": "email", "type": "followup_value", "description": "Value Email - Market report or listing alert"},

    # Day 2
    {"day": 2, "hour": 11, "channel": "sms", "type": "followup_question", "description": "Question-based SMS - easy to respond"},

    # Day 3
    {"day": 3, "hour": 10, "channel": "email", "type": "followup_resource", "description": "Resource Email - Guide or checklist"},
    {"day": 3, "hour": 15, "channel": "sms", "type": "followup_casual", "description": "Casual SMS check-in"},

    # Day 4
    {"day": 4, "hour": 12, "channel": "sms", "type": "followup_timing", "description": "Timing-focused SMS"},

    # Day 5
    {"day": 5, "hour": 10, "channel": "email", "type": "followup_social_proof", "description": "Social proof Email - Success story"},
    {"day": 5, "hour": 16, "channel": "sms", "type": "followup_soft", "description": "Soft SMS - No pressure"},

    # Day 6
    {"day": 6, "hour": 11, "channel": "sms", "type": "followup_helpful", "description": "Helpful SMS - Offer specific assistance"},

    # Day 7 - Final push before nurture
    {"day": 7, "hour": 10, "channel": "email", "type": "followup_final", "description": "Final Email - Warm close, open door"},
    {"day": 7, "hour": 15, "channel": "sms", "type": "followup_final", "description": "Final SMS - Friendly close"},
]


async def generate_sequence_message(
    lead_context,
    step: dict,
    agent_name: str,
    agent_phone: str,
    brokerage_name: str,
    previous_messages: list,
) -> dict:
    """Generate a single message in the sequence using AI."""
    import aiohttp
    import json
    import re

    from app.ai_agent.initial_outreach_generator import SOURCE_NAME_MAP

    # Get friendly source name
    source = lead_context.get('source', '')
    friendly_source = source
    for key, value in SOURCE_NAME_MAP.items():
        if key.lower() == source.lower():
            friendly_source = value
            break

    # Build context about what's happened so far
    previous_context = ""
    if previous_messages:
        previous_context = "\n\nPREVIOUS MESSAGES SENT (no response yet):\n"
        for msg in previous_messages[-5:]:  # Last 5 messages
            previous_context += f"- Day {msg['day']}, {msg['channel'].upper()}: {msg['content'][:100]}...\n"

    # Determine lead type
    tags = lead_context.get('tags', [])
    tag_lower = [t.lower() for t in tags]
    is_buyer = any('buyer' in t for t in tag_lower)
    is_seller = any('seller' in t for t in tag_lower)

    if is_buyer and is_seller:
        lead_type = "BUYER AND SELLER (coordinated move)"
    elif is_seller:
        lead_type = "SELLER"
    elif is_buyer:
        lead_type = "BUYER"
    else:
        lead_type = "Unknown"

    # Build the prompt based on message type
    first_name = lead_context.get('firstName', 'there')
    location = lead_context.get('cities', '') or 'your area'

    message_type_prompts = {
        "initial": "This is the FIRST contact. Introduce yourself, explain the connection, offer value.",
        "followup_gentle": "Gentle check-in. Don't repeat the intro. Just making sure they saw the message.",
        "followup_value": "Provide actual VALUE. Share a market insight, new listing, or useful tip.",
        "followup_question": "Ask an EASY question they can quickly answer. Make responding effortless.",
        "followup_resource": "Offer a specific resource: guide, checklist, market report.",
        "followup_casual": "Very casual, human check-in. Like a friend following up.",
        "followup_timing": "Focus on timing/urgency without being pushy. Reference market conditions.",
        "followup_social_proof": "Share a success story or testimonial (make it relevant to their situation).",
        "followup_soft": "Zero pressure. Just letting them know you're here when ready.",
        "followup_helpful": "Offer specific help: answer questions, send listings, schedule a call.",
        "followup_final": "Warm close. Door is always open. Move to monthly check-ins if no response.",
    }

    type_guidance = message_type_prompts.get(step['type'], "Follow up naturally.")

    system_prompt = f"""You are {agent_name}, a friendly real estate agent with {brokerage_name}.

You're following up with {first_name} who hasn't responded yet. This is Day {step['day']} of your outreach.

CRITICAL RULES:
1. DO NOT repeat your introduction - they already know who you are from previous messages
2. DO NOT ask "are you buying or selling?" - we already know: {lead_type}
3. Reference their situation specifically: looking in {location}
4. Keep SMS under 160 characters ideal, max 250
5. For email, keep it SHORT (2-3 paragraphs max)
6. Be human, not robotic. Vary your approach each day.
7. Never guilt trip or be passive aggressive about no response
8. Always leave the door open

MESSAGE TYPE: {step['type']}
GUIDANCE: {type_guidance}

SOURCE: {friendly_source}
LEAD TYPE: {lead_type}
LOCATION: {location}
"""

    if step['channel'] == 'sms':
        user_prompt = f"""Generate a follow-up SMS for Day {step['day']}.

Type: {step['type']}
{type_guidance}

{previous_context}

Respond with ONLY the SMS text. No JSON, no explanation. Just the message.
Keep it under 200 characters. Be natural and human."""
    else:
        user_prompt = f"""Generate a follow-up EMAIL for Day {step['day']}.

Type: {step['type']}
{type_guidance}

{previous_context}

Respond in this JSON format:
{{
    "subject": "Short, personal subject line",
    "body": "<p>Short email body...</p><p>CTA...</p><p>{agent_name}</p>"
}}

Keep it SHORT - 2-3 paragraphs max. They've already received multiple messages."""

    # Call OpenRouter
    openrouter_key = os.environ.get('OPENROUTER_API_KEY')
    if not openrouter_key:
        return {"content": f"[AI generation skipped - no API key]", "subject": "Follow-up"}

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "anthropic/claude-sonnet-4",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": 500,
                "temperature": 0.7,
            },
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            if response.status != 200:
                return {"content": f"[API error: {response.status}]", "subject": "Follow-up"}

            data = await response.json()
            text = data['choices'][0]['message']['content'].strip()

            if step['channel'] == 'email':
                # Parse JSON for email
                try:
                    json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group())
                        return {
                            "subject": result.get('subject', 'Following up'),
                            "content": result.get('body', text),
                        }
                except:
                    pass
                return {"subject": "Following up", "content": text}
            else:
                # SMS is just the text
                return {"content": text}


async def test_7day_sequence(person_id: int):
    """Test the full 7-day sequence for a lead."""
    import requests
    import base64

    from app.ai_agent.initial_outreach_generator import (
        generate_initial_outreach,
        LeadContext,
    )

    print("\n" + "=" * 80)
    print(f"7-DAY NO-RESPONSE SEQUENCE TEST - Lead #{person_id}")
    print("=" * 80)

    # Get FUB API key
    fub_api_key = os.getenv('FUB_API_KEY')
    if not fub_api_key:
        print("ERROR: FUB_API_KEY not set")
        return

    headers = {
        'Authorization': f'Basic {base64.b64encode(f"{fub_api_key}:".encode()).decode()}',
    }

    # Fetch person data
    print("\n1. Fetching lead data from FUB...")
    resp = requests.get(
        f'https://api.followupboss.com/v1/people/{person_id}',
        headers=headers,
        timeout=30,
    )

    if resp.status_code != 200:
        print(f"   ERROR: Could not fetch person: {resp.status_code}")
        return

    person_data = resp.json()
    first_name = person_data.get('firstName', 'there')
    last_name = person_data.get('lastName', '')
    source = person_data.get('source', '')
    tags = person_data.get('tags', [])
    cities = person_data.get('cities', '')

    print(f"   Name: {first_name} {last_name}")
    print(f"   Source: {source}")
    print(f"   Tags: {tags}")
    print(f"   Location: {cities}")

    # Fetch events
    resp = requests.get(
        f'https://api.followupboss.com/v1/events?personId={person_id}&limit=5',
        headers=headers,
        timeout=30,
    )
    events = resp.json().get('events', []) if resp.status_code == 200 else []

    # Agent info
    agent_name = "Adam"
    agent_phone = "(916) 555-1234"
    agent_email = "adam@saahomes.com"
    brokerage_name = "Schwartz and Associates"

    # Generate all messages in sequence
    all_messages = []
    start_time = datetime.now()

    print("\n" + "=" * 80)
    print("FULL 7-DAY SEQUENCE")
    print("=" * 80)

    for i, step in enumerate(SEVEN_DAY_SEQUENCE):
        send_time = start_time + timedelta(days=step['day'], hours=step['hour'])

        print(f"\n{'-' * 80}")
        print(f"DAY {step['day']} | {send_time.strftime('%A %I:%M %p')} | {step['channel'].upper()}")
        print(f"Type: {step['description']}")
        print("-" * 80)

        if step['type'] == 'initial':
            # Use the initial outreach generator
            if step['channel'] == 'sms':
                outreach = await generate_initial_outreach(
                    person_data=person_data,
                    events=events,
                    agent_name=agent_name,
                    agent_email=agent_email,
                    agent_phone=agent_phone,
                    brokerage_name=brokerage_name,
                )
                content = clean_text(outreach.sms_message)
                print(f"\n{content}")
                print(f"\n[{len(content)} characters]")
                all_messages.append({
                    "day": step['day'],
                    "channel": "sms",
                    "content": content,
                })
            else:
                outreach = await generate_initial_outreach(
                    person_data=person_data,
                    events=events,
                    agent_name=agent_name,
                    agent_email=agent_email,
                    agent_phone=agent_phone,
                    brokerage_name=brokerage_name,
                )
                content = clean_text(outreach.email_text)
                subject = clean_text(outreach.email_subject)
                print(f"\nSubject: {subject}")
                print(f"\n{content}")
                all_messages.append({
                    "day": step['day'],
                    "channel": "email",
                    "content": content,
                    "subject": subject,
                })
        else:
            # Generate follow-up message
            result = await generate_sequence_message(
                lead_context=person_data,
                step=step,
                agent_name=agent_name,
                agent_phone=agent_phone,
                brokerage_name=brokerage_name,
                previous_messages=all_messages,
            )

            if step['channel'] == 'email':
                content = clean_text(result['content'])
                subject = clean_text(result.get('subject', 'N/A'))
                print(f"\nSubject: {subject}")
                print(f"\n{content}")
                all_messages.append({
                    "day": step['day'],
                    "channel": "email",
                    "content": content,
                    "subject": subject,
                })
            else:
                content = clean_text(result['content'])
                print(f"\n{content}")
                print(f"\n[{len(content)} characters]")
                all_messages.append({
                    "day": step['day'],
                    "channel": "sms",
                    "content": content,
                })

    # Summary
    print("\n" + "=" * 80)
    print("SEQUENCE SUMMARY")
    print("=" * 80)

    sms_count = sum(1 for m in all_messages if m['channel'] == 'sms')
    email_count = sum(1 for m in all_messages if m['channel'] == 'email')

    print(f"\nTotal Messages: {len(all_messages)}")
    print(f"  - SMS: {sms_count}")
    print(f"  - Email: {email_count}")
    print(f"\nCadence: Day 0-7 intensive, then moves to monthly nurture")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test 7-day no-response sequence')
    parser.add_argument('person_id', type=int, help='FUB person ID')
    args = parser.parse_args()

    asyncio.run(test_7day_sequence(args.person_id))
