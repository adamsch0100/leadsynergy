"""
Test script to verify Railway deployment is working.
This will create a test lead and monitor if the AI agent responds.
"""

import sys
from pathlib import Path
import time
from datetime import datetime

# Add Backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.database.supabase_client import SupabaseClientSingleton

def monitor_system(duration_seconds=120):
    """
    Monitor the system for activity.

    Args:
        duration_seconds: How long to monitor (default 2 minutes)
    """
    print("=" * 80)
    print("RAILWAY SYSTEM MONITOR")
    print("=" * 80)
    print()
    print("Monitoring for AI agent activity...")
    print(f"Duration: {duration_seconds} seconds")
    print()
    print("What to look for:")
    print("  1. New scheduled messages being created")
    print("  2. Messages changing from 'pending' to 'sent'")
    print("  3. Conversations getting updated with messages")
    print()
    print("-" * 80)

    supabase = SupabaseClientSingleton.get_instance()

    start_time = time.time()
    last_msg_count = 0
    last_sent_count = 0

    try:
        while time.time() - start_time < duration_seconds:
            elapsed = int(time.time() - start_time)

            # Check scheduled messages
            messages = supabase.table('scheduled_messages').select('id, status').execute()
            total_messages = len(messages.data) if messages.data else 0

            pending = sum(1 for m in (messages.data or []) if m.get('status') == 'pending')
            sent = sum(1 for m in (messages.data or []) if m.get('status') == 'sent')

            # Check for new activity
            if total_messages > last_msg_count:
                print(f"\n[{elapsed}s] NEW MESSAGE scheduled! Total: {total_messages}")
                last_msg_count = total_messages

            if sent > last_sent_count:
                print(f"\n[{elapsed}s] MESSAGE SENT! Total sent: {sent}")
                last_sent_count = sent

            # Print status every 10 seconds
            if elapsed > 0 and elapsed % 10 == 0:
                print(f"[{elapsed}s] Status: {total_messages} total messages ({pending} pending, {sent} sent)")

            time.sleep(2)

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")

    print()
    print("-" * 80)
    print("FINAL STATUS")
    print("-" * 80)

    # Final check
    messages = supabase.table('scheduled_messages').select('id, status, scheduled_for').execute()

    if messages.data:
        from collections import Counter
        status_counts = Counter([m['status'] for m in messages.data])

        print(f"Total messages: {len(messages.data)}")
        for status, count in status_counts.items():
            print(f"  {status}: {count}")
    else:
        print("No messages found")

    # Check conversations
    conversations = supabase.table('ai_conversations').select(
        'fub_person_id, state, lead_score, last_ai_message_at'
    ).not_.is_('last_ai_message_at', 'null').execute()

    if conversations.data:
        print(f"\nConversations with AI messages: {len(conversations.data)}")
        for conv in conversations.data[:3]:
            last_msg = conv.get('last_ai_message_at', '')[:19] if conv.get('last_ai_message_at') else 'Never'
            print(f"  Person {conv['fub_person_id']}: Last message at {last_msg}")
    else:
        print("\nNo conversations with AI messages yet")

    print()
    print("=" * 80)


def check_worker_status():
    """Check if Worker is processing tasks by looking at recent activity."""
    supabase = SupabaseClientSingleton.get_instance()

    print("=" * 80)
    print("WORKER STATUS CHECK")
    print("=" * 80)
    print()

    # Check for any sent messages in last 10 minutes
    from datetime import timedelta
    ten_min_ago = (datetime.utcnow() - timedelta(minutes=10)).isoformat()

    recent_sent = supabase.table('scheduled_messages').select('id, sent_at').eq(
        'status', 'sent'
    ).gte('sent_at', ten_min_ago).execute()

    if recent_sent.data:
        print(f"[OK] Worker is ACTIVE - {len(recent_sent.data)} messages sent in last 10 minutes")
    else:
        print("[INFO] No messages sent in last 10 minutes")
        print("       This is normal if there are no new leads")

    print()

    # Check for pending messages that should have been sent
    now = datetime.utcnow().isoformat()
    overdue = supabase.table('scheduled_messages').select('id, scheduled_for').eq(
        'status', 'pending'
    ).lt('scheduled_for', now).execute()

    if overdue.data:
        print(f"[WARNING] {len(overdue.data)} messages are overdue!")
        print("          Worker may not be running or Redis not connected")
        print()
        print("Check Railway logs:")
        print("  railway logs --service worker")
    else:
        print("[OK] No overdue messages")

    print()
    print("=" * 80)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "monitor":
        # Monitor mode - watch for activity
        duration = int(sys.argv[2]) if len(sys.argv) > 2 else 120
        monitor_system(duration)
    else:
        # Quick status check
        check_worker_status()
