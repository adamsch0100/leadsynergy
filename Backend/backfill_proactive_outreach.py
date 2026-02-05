"""
Backfill Proactive Outreach for Existing AI-Enabled Leads

This script triggers proactive outreach for leads that have AI enabled
but haven't received any messages yet (in INITIAL state with 0 messages).

This is used for:
1. Backfilling the 11 leads manually enabled before this feature was deployed
2. Re-triggering outreach for leads where initial outreach failed

Usage:
    python backfill_proactive_outreach.py
"""

import os
import sys
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'ignore')

# Add Backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.supabase_client import SupabaseClientSingleton
from app.database.fub_api_client import FUBApiClient
from app.ai_agent.proactive_outreach_orchestrator import ProactiveOutreachOrchestrator
from app.messaging.fub_sms_service import FUBSMSService
from app.ai_agent.compliance_checker import ComplianceChecker


async def get_leads_needing_outreach(supabase):
    """
    Get leads with AI enabled but no messages sent.

    Returns leads that:
    - Have AI enabled (lead_ai_settings.ai_enabled = true)
    - Have conversation in INITIAL state
    - Have 0 messages sent
    """
    print("\n🔍 Finding leads that need proactive outreach...")

    # Get AI-enabled leads
    ai_settings = supabase.table('lead_ai_settings').select('*').eq('ai_enabled', True).execute()
    ai_enabled_leads = ai_settings.data or []

    print(f"   Found {len(ai_enabled_leads)} leads with AI enabled")

    # Get their person IDs
    person_ids = [int(l['fub_person_id']) for l in ai_enabled_leads]

    if not person_ids:
        print("   No AI-enabled leads found")
        return []

    # Get conversations in INITIAL state
    conversations = supabase.table('ai_conversations').select(
        'fub_person_id, state, organization_id, user_id'
    ).in_('fub_person_id', person_ids).eq('state', 'initial').execute()

    initial_convos = conversations.data or []

    print(f"   Found {len(initial_convos)} leads in INITIAL state")

    # Get message counts for these leads
    message_counts = supabase.table('ai_message_log').select(
        'fub_person_id'
    ).in_('fub_person_id', person_ids).execute()

    # Count messages per person
    messages_by_person = {}
    for msg in (message_counts.data or []):
        pid = msg['fub_person_id']
        messages_by_person[pid] = messages_by_person.get(pid, 0) + 1

    # Filter to leads with 0 messages
    leads_needing_outreach = []
    for convo in initial_convos:
        person_id = convo['fub_person_id']
        msg_count = messages_by_person.get(person_id, 0)

        if msg_count == 0:
            leads_needing_outreach.append({
                'fub_person_id': person_id,
                'organization_id': convo['organization_id'],
                'user_id': convo['user_id'],
            })

    print(f"   ✅ Found {len(leads_needing_outreach)} leads needing proactive outreach")

    return leads_needing_outreach


async def trigger_outreach_for_lead(orchestrator, lead, dry_run=False):
    """Trigger proactive outreach for a single lead."""
    person_id = lead['fub_person_id']
    org_id = lead['organization_id']
    user_id = lead['user_id']

    print(f"\n📤 Processing lead {person_id}...")

    if dry_run:
        print(f"   [DRY RUN] Would trigger outreach for lead {person_id}")
        return {"success": True, "dry_run": True}

    try:
        result = await orchestrator.trigger_proactive_outreach(
            fub_person_id=person_id,
            organization_id=org_id,
            user_id=user_id,
            trigger_reason="backfill",
            enable_type="manual",  # These were manually enabled
        )

        if result["success"]:
            print(f"   ✅ Success - Actions: {', '.join(result['actions_taken'])}")
            print(f"      Lead Stage: {result['lead_stage']}")
            if result.get('messages', {}).get('sms_preview'):
                print(f"      SMS Preview: {result['messages']['sms_preview']}")
        else:
            print(f"   ❌ Failed - Errors: {', '.join(result.get('errors', []))}")

        return result

    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return {"success": False, "errors": [str(e)]}


async def backfill_proactive_outreach(dry_run=False, limit=None, delay_seconds=5):
    """
    Backfill proactive outreach for existing leads.

    Args:
        dry_run: If True, don't actually send messages (just print what would happen)
        limit: Limit to N leads (for testing)
        delay_seconds: Delay between leads to avoid rate limits
    """
    load_dotenv()

    print("\n" + "="*80)
    print("BACKFILL PROACTIVE AI OUTREACH")
    print("="*80)

    if dry_run:
        print("\n⚠️  DRY RUN MODE - No messages will be sent\n")

    # Initialize clients
    supabase = SupabaseClientSingleton.get_instance()
    fub_client = FUBApiClient()

    # Find leads needing outreach
    leads = await get_leads_needing_outreach(supabase)

    if not leads:
        print("\n✅ No leads need backfill - all caught up!")
        return

    if limit:
        leads = leads[:limit]
        print(f"\n⚠️  Limited to {limit} leads")

    # Initialize orchestrator
    orchestrator = ProactiveOutreachOrchestrator(
        supabase_client=supabase,
        fub_client=fub_client,
        sms_service=FUBSMSService(),
        compliance_checker=ComplianceChecker(supabase_client=supabase),
    )

    print(f"\n🚀 Starting backfill for {len(leads)} leads...")
    print(f"   Delay between leads: {delay_seconds} seconds")

    # Process each lead
    results = {
        "success": 0,
        "failed": 0,
        "total": len(leads),
    }

    for idx, lead in enumerate(leads, 1):
        print(f"\n[{idx}/{len(leads)}] Lead {lead['fub_person_id']}")

        result = await trigger_outreach_for_lead(orchestrator, lead, dry_run=dry_run)

        if result.get("success"):
            results["success"] += 1
        else:
            results["failed"] += 1

        # Delay between leads
        if idx < len(leads):
            print(f"   ⏳ Waiting {delay_seconds} seconds before next lead...")
            await asyncio.sleep(delay_seconds)

    # Print summary
    print("\n" + "="*80)
    print("BACKFILL COMPLETE")
    print("="*80)
    print(f"Total Leads: {results['total']}")
    print(f"✅ Successful: {results['success']}")
    print(f"❌ Failed: {results['failed']}")
    print("="*80 + "\n")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Backfill proactive outreach for AI-enabled leads")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually send messages")
    parser.add_argument("--limit", type=int, help="Limit to N leads (for testing)")
    parser.add_argument("--delay", type=int, default=5, help="Delay seconds between leads (default: 5)")

    args = parser.parse_args()

    await backfill_proactive_outreach(
        dry_run=args.dry_run,
        limit=args.limit,
        delay_seconds=args.delay,
    )


if __name__ == '__main__':
    asyncio.run(main())
