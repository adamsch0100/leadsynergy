"""
Cleanup old pending messages that are past their relevance window.

Use this to clear out stale pending messages before starting Celery workers
for the first time, so you don't send 2-week-old welcome messages.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add Backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.database.supabase_client import SupabaseClientSingleton


def cleanup_old_pending_messages(days_old: int = 3):
    """
    Delete pending messages older than N days.

    Args:
        days_old: Messages older than this many days will be deleted
    """
    supabase = SupabaseClientSingleton.get_instance()

    # Calculate cutoff date
    cutoff = datetime.utcnow() - timedelta(days=days_old)
    cutoff_iso = cutoff.isoformat()

    print(f"[*] Finding pending messages older than {days_old} days (before {cutoff.strftime('%Y-%m-%d %H:%M:%S UTC')})...")

    # Get old pending messages
    result = supabase.table('scheduled_messages').select('id, fub_person_id, scheduled_for, message_content').eq(
        'status', 'pending'
    ).lt('scheduled_for', cutoff_iso).execute()

    if not result.data:
        print("[OK] No old pending messages found. Database is clean!")
        return

    print(f"\n[*] Found {len(result.data)} old pending messages:")
    print("-" * 80)
    for msg in result.data[:10]:  # Show first 10
        scheduled = msg['scheduled_for'][:19]  # Trim to readable format
        preview = msg['message_content'][:60] + "..." if len(msg['message_content']) > 60 else msg['message_content']
        print(f"  Person {msg['fub_person_id']} | {scheduled} | {preview}")

    if len(result.data) > 10:
        print(f"  ... and {len(result.data) - 10} more")
    print("-" * 80)

    # Confirm deletion
    response = input(f"\n[WARNING] Delete all {len(result.data)} old pending messages? (yes/no): ")

    if response.lower() != 'yes':
        print("[CANCELLED] No messages were deleted.")
        return

    # Delete the messages
    print(f"\n[*] Deleting {len(result.data)} old pending messages...")

    delete_result = supabase.table('scheduled_messages').delete().eq(
        'status', 'pending'
    ).lt('scheduled_for', cutoff_iso).execute()

    deleted_count = len(delete_result.data) if delete_result.data else 0

    print(f"[OK] Successfully deleted {deleted_count} old pending messages!")
    print(f"\n[TIP] When you start Celery workers, only fresh messages will be sent.")


def show_pending_summary():
    """Show summary of all pending messages."""
    supabase = SupabaseClientSingleton.get_instance()

    result = supabase.table('scheduled_messages').select('scheduled_for, status').eq('status', 'pending').execute()

    if not result.data:
        print("[OK] No pending messages in the database.")
        return

    # Group by date
    from collections import defaultdict
    by_date = defaultdict(int)

    for msg in result.data:
        date = msg['scheduled_for'][:10]  # YYYY-MM-DD
        by_date[date] += 1

    print(f"\n[SUMMARY] Pending messages by date:")
    print("-" * 40)
    for date in sorted(by_date.keys()):
        print(f"  {date}: {by_date[date]} messages")
    print("-" * 40)
    print(f"  Total: {len(result.data)} pending messages\n")


if __name__ == "__main__":
    print("=" * 80)
    print("LeadSynergy - Cleanup Old Pending Messages")
    print("=" * 80)
    print()

    # Show current state
    show_pending_summary()

    # Cleanup old messages (older than 3 days)
    cleanup_old_pending_messages(days_old=3)

    print()
    print("=" * 80)
