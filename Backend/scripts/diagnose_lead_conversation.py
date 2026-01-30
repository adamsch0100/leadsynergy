#!/usr/bin/env python3
"""
Diagnose a lead's AI conversation - view full message history, state, and context.

Usage:
    python scripts/diagnose_lead_conversation.py 2099
    python scripts/diagnose_lead_conversation.py 2099 --verbose
"""

import os
import sys
import json
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add Backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.database.supabase_client import SupabaseClientSingleton


def diagnose_lead(person_id: int, verbose: bool = False):
    """Pull and display all AI conversation data for a lead."""
    supabase = SupabaseClientSingleton.get_instance()

    print("=" * 70)
    print(f"  DIAGNOSING LEAD {person_id}")
    print("=" * 70)

    # 1. Conversation state
    print("\n--- CONVERSATION STATE ---")
    conv_result = supabase.table('ai_conversations').select('*').eq(
        'fub_person_id', person_id
    ).order('updated_at', desc=True).limit(1).execute()

    conversation = conv_result.data[0] if conv_result.data else None
    if conversation:
        print(f"  State:          {conversation.get('state', 'N/A')}")
        print(f"  Lead Score:     {conversation.get('current_score', conversation.get('lead_score', 'N/A'))}")
        print(f"  Handoff Reason: {conversation.get('handoff_reason', 'None')}")
        print(f"  Last AI Msg:    {conversation.get('last_ai_message_at', 'N/A')}")
        print(f"  Last Human Msg: {conversation.get('last_human_message_at', 'N/A')}")
        print(f"  Created:        {conversation.get('created_at', 'N/A')}")
        print(f"  Updated:        {conversation.get('updated_at', 'N/A')}")
        print(f"  Is Active:      {conversation.get('is_active', 'N/A')}")

        if verbose:
            qual_data = conversation.get('qualification_data', {})
            if qual_data:
                print(f"\n  Qualification Data:")
                if isinstance(qual_data, str):
                    qual_data = json.loads(qual_data)
                for k, v in qual_data.items():
                    if v:
                        print(f"    {k}: {v}")
    else:
        print("  No conversation record found in ai_conversations table.")

    # 2. Message log
    print("\n--- MESSAGE HISTORY (ai_message_log) ---")
    msg_result = supabase.table('ai_message_log').select('*').eq(
        'fub_person_id', person_id
    ).order('created_at', desc=False).limit(100).execute()

    messages = msg_result.data or []
    if messages:
        print(f"  Total messages logged: {len(messages)}")
        inbound = [m for m in messages if m.get('direction') == 'inbound']
        outbound = [m for m in messages if m.get('direction') == 'outbound']
        print(f"  Inbound (from lead): {len(inbound)}")
        print(f"  Outbound (from AI):  {len(outbound)}")
        print()

        for i, msg in enumerate(messages, 1):
            direction = msg.get('direction', '?')
            content = msg.get('message_content', '(empty)')
            created = msg.get('created_at', '?')
            intent = msg.get('intent_detected', '')
            channel = msg.get('channel', 'sms')

            # Format timestamp
            if created and created != '?':
                try:
                    dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    created = dt.strftime('%m/%d %I:%M %p')
                except (ValueError, AttributeError):
                    pass

            arrow = ">>" if direction == "inbound" else "<<"
            label = "LEAD" if direction == "inbound" else "AI  "
            intent_str = f" [{intent}]" if intent else ""

            print(f"  {i:3}. [{created}] {arrow} {label}: {content}{intent_str}")

            if verbose and direction == 'outbound':
                model = msg.get('ai_model', '')
                tokens = msg.get('tokens_used', '')
                score_delta = msg.get('lead_score_delta', 0)
                extracted = msg.get('extracted_data', {})
                if model:
                    print(f"       Model: {model}, Tokens: {tokens}, Score Delta: {score_delta}")
                if extracted and extracted != {}:
                    print(f"       Extracted: {json.dumps(extracted, default=str)}")
    else:
        print("  No messages found in ai_message_log table.")

    # 3. Conversation history from ai_conversations JSONB
    if conversation and conversation.get('conversation_history'):
        history = conversation['conversation_history']
        if isinstance(history, str):
            history = json.loads(history)
        print(f"\n--- CONVERSATION HISTORY (JSONB, {len(history)} entries) ---")
        if verbose:
            for i, entry in enumerate(history, 1):
                direction = entry.get('direction', '?')
                content = entry.get('content', '(empty)')
                ts = entry.get('timestamp', '?')
                arrow = ">>" if direction == "inbound" else "<<"
                label = "LEAD" if direction == "inbound" else "AI  "
                print(f"  {i:3}. [{ts}] {arrow} {label}: {content}")
        else:
            print(f"  (Use --verbose to see full JSONB history)")

    # 4. Cached profile
    print("\n--- LEAD PROFILE CACHE ---")
    cache_result = supabase.table('ai_lead_profile_cache').select('*').eq(
        'fub_person_id', person_id
    ).execute()

    if cache_result.data:
        cache = cache_result.data[0]
        person_data = cache.get('person_data', {})
        if isinstance(person_data, str):
            person_data = json.loads(person_data)

        print(f"  Name:       {person_data.get('firstName', 'N/A')} {person_data.get('lastName', 'N/A')}")

        stage = person_data.get('stage')
        if isinstance(stage, dict):
            print(f"  Stage:      {stage.get('name', 'N/A')}")
        else:
            print(f"  Stage:      {stage or 'N/A'}")

        print(f"  Source:     {person_data.get('source', 'N/A')}")
        print(f"  Cached At:  {cache.get('cached_at', 'N/A')}")
        print(f"  Updated:    {cache.get('last_updated_at', 'N/A')}")

        # Show cached text messages count
        texts = cache.get('text_messages', [])
        if isinstance(texts, str):
            texts = json.loads(texts)
        emails = cache.get('emails', [])
        if isinstance(emails, str):
            emails = json.loads(emails)
        print(f"  Cached SMS: {len(texts)}")
        print(f"  Cached Emails: {len(emails)}")

        if verbose and texts:
            print(f"\n  Cached Text Messages (last 10):")
            for msg in texts[-10:]:
                if isinstance(msg, dict):
                    direction = msg.get('direction', '?')
                    body = msg.get('body', msg.get('message', '(empty)'))
                    ts = msg.get('dateCreated', msg.get('timestamp', '?'))
                    print(f"    [{ts}] {direction}: {body[:120]}")
    else:
        print("  No cached profile found.")

    # 5. AI settings for this lead
    print("\n--- AI SETTINGS ---")
    settings_result = supabase.table('lead_ai_settings').select('*').eq(
        'fub_person_id', str(person_id)
    ).execute()

    if settings_result.data:
        settings = settings_result.data[0]
        print(f"  AI Enabled: {settings.get('ai_enabled', 'N/A')}")
        print(f"  Created:    {settings.get('created_at', 'N/A')}")
    else:
        print("  No lead-specific AI settings found.")

    # 6. Scheduled messages
    print("\n--- SCHEDULED MESSAGES ---")
    sched_result = supabase.table('scheduled_messages').select('*').eq(
        'fub_person_id', person_id
    ).order('scheduled_for', desc=True).limit(10).execute()

    if sched_result.data:
        for sched in sched_result.data:
            status = sched.get('status', '?')
            content = sched.get('message_content', '(empty)')
            scheduled_for = sched.get('scheduled_for', '?')
            sent_at = sched.get('sent_at', 'not sent')
            channel = sched.get('channel', '?')
            print(f"  [{status}] {channel} @ {scheduled_for} | Sent: {sent_at}")
            print(f"    Content: {content[:120]}")
    else:
        print("  No scheduled messages found.")

    # 7. Summary
    print("\n" + "=" * 70)
    print("  DIAGNOSIS SUMMARY")
    print("=" * 70)

    state = conversation.get('state', 'unknown') if conversation else 'no_conversation'
    msg_count = len(messages)
    ai_count = len([m for m in messages if m.get('direction') == 'outbound'])

    print(f"  Current State:  {state}")
    print(f"  Messages Total: {msg_count} ({ai_count} from AI)")

    if state == 'handed_off':
        print(f"  Status: HANDED OFF - Reason: {conversation.get('handoff_reason', 'unknown')}")
    elif state == 'scheduling':
        print(f"  Status: IN SCHEDULING STATE - AI is trying to book appointments")
        print(f"  NOTE: This should trigger handoff but currently doesn't auto-handoff")
    elif ai_count >= 15:
        print(f"  WARNING: {ai_count} AI messages sent - exceeds typical max of 15")

    # Check for potential hallucination in AI responses
    hallucination_keywords = ['off-market', 'off market', 'exclusive listing', 'pocket listing']
    for msg in messages:
        if msg.get('direction') == 'outbound':
            content = (msg.get('message_content') or '').lower()
            for keyword in hallucination_keywords:
                if keyword in content:
                    print(f"\n  WARNING: Possible hallucination detected!")
                    print(f"  AI mentioned '{keyword}' in: {msg.get('message_content')}")

    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/diagnose_lead_conversation.py <person_id> [--verbose]")
        print("Example: python scripts/diagnose_lead_conversation.py 2099 --verbose")
        sys.exit(1)

    person_id = int(sys.argv[1])
    verbose = "--verbose" in sys.argv

    diagnose_lead(person_id, verbose=verbose)
