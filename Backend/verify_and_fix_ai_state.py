#!/usr/bin/env python3
"""Verify AI agent state and fix common issues after world-class improvements."""

import asyncio
from datetime import datetime, timedelta
from app.database.supabase_client import SupabaseClientSingleton
from app.ai_agent.conversation_manager import ConversationState

async def main():
    supabase = SupabaseClientSingleton.get_instance()

    print("=" * 80)
    print("AI AGENT STATE VERIFICATION")
    print("=" * 80)
    print()

    # 1. Check for false opt-outs
    print("1. Checking for false opt-outs...")
    opt_outs = supabase.table("sms_consent").select("*").eq("opted_out", True).execute()
    if opt_outs.data:
        print(f"   ⚠️  Found {len(opt_outs.data)} opted-out leads:")
        for opt_out in opt_outs.data:
            print(f"      - Person {opt_out['fub_person_id']}: {opt_out.get('opt_out_reason', 'No reason')}")
    else:
        print("   ✅ No opted-out leads")
    print()

    # 2. Check conversation states
    print("2. Checking conversation states...")
    conversations = supabase.table("ai_conversations").select("*").eq("ai_enabled", True).execute()

    state_counts = {}
    for conv in conversations.data:
        state = conv.get("state", "unknown")
        state_counts[state] = state_counts.get(state, 0) + 1

    print(f"   Total active AI conversations: {len(conversations.data)}")
    for state, count in sorted(state_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"      {state}: {count}")
    print()

    # 3. Check for conversations that should be HANDED_OFF
    print("3. Checking for conversations that should be HANDED_OFF...")
    recent_messages = supabase.table("ai_messages").select("*").gte(
        "created_at",
        (datetime.utcnow() - timedelta(days=7)).isoformat()
    ).execute()

    appointment_conversations = set()
    for msg in recent_messages.data:
        extracted = msg.get("extracted_data", {})
        if isinstance(extracted, dict):
            intent = extracted.get("detected_intent", "")
            handoff_reason = extracted.get("handoff_reason", "")

            if any(keyword in str(intent).lower() + str(handoff_reason).lower()
                   for keyword in ["appointment", "schedule", "showing", "time_selection"]):
                appointment_conversations.add(msg["conversation_id"])

    # Check which of these are NOT in HANDED_OFF state
    needs_handoff = []
    for conv_id in appointment_conversations:
        conv = next((c for c in conversations.data if c["conversation_id"] == conv_id), None)
        if conv and conv.get("state") != "HANDED_OFF":
            needs_handoff.append(conv)

    if needs_handoff:
        print(f"   ⚠️  Found {len(needs_handoff)} conversations with appointment interest NOT in HANDED_OFF state:")
        for conv in needs_handoff:
            print(f"      - Person {conv['fub_person_id']}: Current state = {conv.get('state', 'unknown')}")
    else:
        print("   ✅ All appointment conversations properly handed off")
    print()

    # 4. Check recent activity
    print("4. Checking recent activity (last 24 hours)...")
    recent = supabase.table("ai_messages").select("*").gte(
        "created_at",
        (datetime.utcnow() - timedelta(hours=24)).isoformat()
    ).execute()

    if recent.data:
        inbound = sum(1 for m in recent.data if m.get("direction") == "inbound")
        outbound = sum(1 for m in recent.data if m.get("direction") == "outbound")
        print(f"   Messages in last 24h: {len(recent.data)}")
        print(f"      Inbound: {inbound}")
        print(f"      Outbound: {outbound}")
    else:
        print("   ⚠️  No messages in last 24 hours")
    print()

    # 5. Check for person 3310 specifically (test lead)
    print("5. Checking test lead (person 3310)...")
    consent_3310 = supabase.table("sms_consent").select("*").eq("fub_person_id", 3310).execute()
    conv_3310 = supabase.table("ai_conversations").select("*").eq("fub_person_id", 3310).execute()

    if consent_3310.data:
        consent = consent_3310.data[0]
        print(f"   SMS Consent: opted_out = {consent.get('opted_out', False)}")
    else:
        print("   ⚠️  No SMS consent record found")

    if conv_3310.data:
        conv = conv_3310.data[0]
        print(f"   Conversation: state = {conv.get('state', 'unknown')}, ai_enabled = {conv.get('ai_enabled', False)}")
    else:
        print("   ⚠️  No conversation record found")
    print()

    # 6. Offer to fix issues
    print("=" * 80)
    print("FIXES AVAILABLE")
    print("=" * 80)
    print()

    if opt_outs.data:
        print("Would you like to clear false opt-outs? (Run clear_optout_3310.py)")

    if needs_handoff:
        print(f"Would you like to set {len(needs_handoff)} conversations to HANDED_OFF state?")
        print("(Update ai_conversations table manually or create fix script)")

    if not recent.data:
        print("Check if webhooks are configured correctly in FUB")

    print()
    print("=" * 80)
    print("Verification complete!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
