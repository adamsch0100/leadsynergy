"""
Backfill ai_message_log for leads that received proactive outreach but weren't logged.

This fixes the conversation history for the 7 leads that got SMS via Playwright
but the messages weren't logged to ai_message_log.
"""
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4
from dotenv import load_dotenv

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'ignore')

# Add Backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.supabase_client import SupabaseClientSingleton

def backfill_message_logs():
    """Add message logs for sent proactive outreach messages."""
    load_dotenv()

    print("\n" + "="*80)
    print("BACKFILL MESSAGE LOGS")
    print("="*80 + "\n")

    supabase = SupabaseClientSingleton.get_instance()

    # Find proactive outreach that was sent but not logged
    print("🔍 Finding sent messages without logs...\n")

    outreach_logs = supabase.table('proactive_outreach_log').select(
        'fub_person_id, sms_preview, sent_at, organization_id'
    ).eq('sms_sent', True).execute()

    sent_messages = outreach_logs.data or []
    print(f"   Found {len(sent_messages)} sent proactive messages\n")

    backfilled = 0
    skipped = 0

    for msg in sent_messages:
        person_id = int(msg['fub_person_id'])

        # Check if already logged
        existing = supabase.table('ai_message_log').select('id').eq(
            'fub_person_id', person_id
        ).eq('message_type', 'proactive_initial_outreach').execute()

        if existing.data:
            print(f"   ⏭️  Lead {person_id}: Already logged, skipping")
            skipped += 1
            continue

        # Backfill the message log
        try:
            # Get the full SMS text from proactive_outreach_log
            # (sms_preview is truncated, so we'll use it with a note)
            sms_text = msg['sms_preview']

            supabase.table('ai_message_log').insert({
                'id': str(uuid4()),
                'fub_person_id': person_id,
                'organization_id': msg['organization_id'],
                'direction': 'outbound',
                'channel': 'sms',
                'content': sms_text + "... [message truncated in log]",
                'sent_at': msg['sent_at'] or datetime.now(timezone.utc).isoformat(),
                'message_type': 'proactive_initial_outreach',
            }).execute()

            print(f"   ✅ Lead {person_id}: Backfilled message log")
            backfilled += 1

        except Exception as e:
            print(f"   ❌ Lead {person_id}: Failed - {e}")

    print("\n" + "="*80)
    print("BACKFILL COMPLETE")
    print("="*80)
    print(f"Backfilled: {backfilled}")
    print(f"Skipped (already logged): {skipped}")
    print(f"Total: {len(sent_messages)}")
    print("="*80 + "\n")

if __name__ == '__main__':
    backfill_message_logs()
