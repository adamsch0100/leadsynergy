#!/usr/bin/env python3
"""
Redis Lead Cache Management Utility

This script allows you to manage and inspect the Redis-based lead cache.
"""

import sys
import argparse
import os
import json
from datetime import datetime
from tabulate import tabulate  # You may need to install this: pip install tabulate
# Add the project root directory to Python's path
# This assumes the script is in app/utils/
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))
sys.path.insert(0, project_root)
# Assuming your LeadCache class is in a module called lead_cache
try:
    from app.database.lead_cache import LeadCacheService
    from app.models.lead import Lead
except ImportError as e:
    print(f"Error: {e}")
    # print("Error: Cannot import LeadCache from lead_cache.py")
    # print("Make sure this script is in the same directory as lead_cache.py or in your PYTHONPATH")


    # For demonstration, define a simple Lead class if import fails
    class Lead:
        def __init__(self):
            self.id = None
            self.fub_person_id = None
            self.email = None
            self.first_name = None
            self.last_name = None
            self.phone = None
            self.source = None
            self.status = None
            self.stage_id = None
            self.tags = None
            self.created_at = None
            self.updated_at = None


    # Define a simplified LeadCache class if import fails
    class LeadCache:
        def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0,
                     redis_password=None, ttl_hours=24):
            import redis
            self.redis = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                decode_responses=True
            )
            self.ttl_seconds = ttl_hours * 3600

        def get_lead(self, fub_person_id):
            # Simplified implementation
            key = f"lead:{fub_person_id}"
            data = self.redis.hgetall(key)
            if not data:
                return None

            lead = Lead()
            lead.id = data.get("id")
            lead.fub_person_id = data.get("fub_person_id")
            lead.email = data.get("email")
            lead.first_name = data.get("first_name")
            lead.last_name = data.get("last_name")
            lead.phone = data.get("phone")
            lead.source = data.get("source")
            lead.status = data.get("status")
            lead.stage_id = data.get("stage_id")

            tags_str = data.get("tags")
            if tags_str:
                lead.tags = json.loads(tags_str)

            return lead

        def get_leads_paginated(self, page=1, page_size=20, status=None):
            # Simplified implementation
            key = "leads:all"
            if status:
                key = f"leads:status:{status}"

            start = (page - 1) * page_size
            end = start + page_size - 1

            lead_ids = self.redis.zrevrange(key, start, end)
            total = self.redis.zcard(key)

            leads = []
            for lead_id in lead_ids:
                lead = self.get_lead(lead_id)
                if lead:
                    leads.append(lead)

            return {
                "leads": leads,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }

        def clear_all_leads(self):
            # Simplified implementation
            cursor = 0
            while True:
                cursor, keys = self.redis.scan(cursor, match="lead:*")
                if keys:
                    self.redis.delete(*keys)
                if cursor == 0:
                    break

            cursor = 0
            while True:
                cursor, keys = self.redis.scan(cursor, match="leads:*")
                if keys:
                    self.redis.delete(*keys)
                if cursor == 0:
                    break

        def invalidate_lead(self, fub_person_id):
            # Simplified implementation
            lead = self.get_lead(fub_person_id)
            if not lead:
                return

            if lead.email:
                self.redis.delete(f"lead:email:{lead.email}")

            if lead.phone:
                self.redis.delete(f"lead:phone:{lead.phone}")

            if lead.status:
                self.redis.zrem(f"leads:status:{lead.status}", fub_person_id)

            self.redis.zrem("leads:all", fub_person_id)
            self.redis.delete(f"lead:{fub_person_id}")

# Initialize the cache with configuration from environment variables
lead_cache = LeadCacheService(
    redis_host=os.environ.get('REDIS_HOST', 'localhost'),
    redis_port=int(os.environ.get('REDIS_PORT', 6379)),
    redis_db=int(os.environ.get('REDIS_DB', 0)),
    redis_password=os.environ.get('REDIS_PASSWORD', "Lancelot@123"),
    ttl_hours=int(os.environ.get('LEAD_CACHE_TTL_HOURS', 24))
)


def list_leads(status=None, page=1, page_size=20):
    """List leads in the cache, optionally filtered by status"""
    result = lead_cache.get_leads_paginated(page, page_size, status)

    leads = result["leads"]
    if not leads:
        print("No leads found in cache.")
        return

    # Format data for display
    table_data = []
    for lead in leads:
        row = [
            lead.fub_person_id[:8] + "..." if lead.fub_person_id and len(
                lead.fub_person_id) > 10 else lead.fub_person_id,
            f"{lead.first_name} {lead.last_name}",
            lead.email,
            lead.phone,
            lead.status,
            lead.source,
            ", ".join(lead.tags[:3]) + "..." if lead.tags and len(lead.tags) > 3 else ", ".join(lead.tags or [])
        ]
        table_data.append(row)

    print(tabulate(
        table_data,
        headers=['ID', 'Name', 'Email', 'Phone', 'Status', 'Source', 'Tags'],
        tablefmt='grid'
    ))

    print(f"\nShowing page {result['page']} of {result['total_pages']} (Total: {result['total']} leads)")

    if result['page'] < result['total_pages']:
        print(f"Use --page {result['page'] + 1} to see the next page")


def show_lead(fub_person_id):
    """Show detailed information about a specific lead"""
    lead = lead_cache.get_lead(fub_person_id)

    if not lead:
        print(f"No lead found with ID: {fub_person_id}")
        return

    print("\n=== Lead Details ===")
    print(f"ID: {lead.id}")
    print(f"FUB Person ID: {lead.fub_person_id}")
    print(f"Name: {lead.first_name} {lead.last_name}")
    print(f"Email: {lead.email}")
    print(f"Phone: {lead.phone}")
    print(f"Status: {lead.status}")
    print(f"Source: {lead.source}")
    print(f"Stage ID: {lead.stage_id}")

    if lead.tags:
        print(f"Tags: {', '.join(lead.tags)}")
    else:
        print("Tags: None")

    if hasattr(lead, 'created_at') and lead.created_at:
        if isinstance(lead.created_at, str):
            print(f"Created: {lead.created_at}")
        else:
            print(f"Created: {lead.created_at.isoformat()}")

    if hasattr(lead, 'updated_at') and lead.updated_at:
        if isinstance(lead.updated_at, str):
            print(f"Updated: {lead.updated_at}")
        else:
            print(f"Updated: {lead.updated_at.isoformat()}")


def clear_cache():
    """Clear all leads from the cache"""
    confirm = input("Are you sure you want to clear all leads from the cache? (y/n): ")
    if confirm.lower() != 'y':
        print("Operation cancelled.")
        return

    lead_cache.clear_all_leads()
    print("All leads have been cleared from the cache.")


def invalidate_lead(fub_person_id):
    """Remove a specific lead from the cache"""
    lead = lead_cache.get_lead(fub_person_id)

    if not lead:
        print(f"No lead found with ID: {fub_person_id}")
        return

    confirm = input(f"Are you sure you want to remove {lead.first_name} {lead.last_name} from the cache? (y/n): ")
    if confirm.lower() != 'y':
        print("Operation cancelled.")
        return

    lead_cache.invalidate_lead(fub_person_id)
    print(f"Lead {fub_person_id} has been removed from the cache.")


def check_redis_connection():
    """Check if Redis is accessible"""
    try:
        # Simple ping to check connection
        result = lead_cache.redis.ping()
        if result:
            print("✓ Successfully connected to Redis server")
            print(f"  Host: {lead_cache.redis.connection_pool.connection_kwargs['host']}")
            print(f"  Port: {lead_cache.redis.connection_pool.connection_kwargs['port']}")
            print(f"  Database: {lead_cache.redis.connection_pool.connection_kwargs['db']}")
            return True
    except Exception as e:
        print(f"✗ Failed to connect to Redis: {e}")
        print("\nPlease check your Redis configuration:")
        print(f"  REDIS_HOST={os.environ.get('REDIS_HOST', 'localhost')}")
        print(f"  REDIS_PORT={os.environ.get('REDIS_PORT', 6379)}")
        print(f"  REDIS_DB={os.environ.get('REDIS_DB', 0)}")
        print(f"  REDIS_PASSWORD={'(set)' if os.environ.get('REDIS_PASSWORD') else '(not set)'}")
        return False


def list_status_categories():
    """List all status categories and counts"""
    cursor = 0
    status_keys = []

    # Find all status keys
    while True:
        cursor, keys = lead_cache.redis.scan(cursor, match="leads:status:*")
        status_keys.extend(keys)
        if cursor == 0:
            break

    if not status_keys:
        print("No status categories found in cache.")
        return

    # Get counts for each status
    table_data = []
    for key in status_keys:
        status = key.replace("leads:status:", "")
        count = lead_cache.redis.zcard(key)
        table_data.append([status, count])

    # Sort by count (descending)
    table_data.sort(key=lambda x: x[1], reverse=True)

    print(tabulate(
        table_data,
        headers=['Status', 'Count'],
        tablefmt='grid'
    ))


def get_cache_stats():
    """Show statistics about the lead cache"""
    # Check total lead count
    all_count = lead_cache.redis.zcard("leads:all")

    # Count total keys
    lead_keys = 0
    index_keys = 0
    cursor = 0

    while True:
        cursor, keys = lead_cache.redis.scan(cursor, match="lead:*")
        lead_keys += len(keys)
        if cursor == 0:
            break

    cursor = 0
    while True:
        cursor, keys = lead_cache.redis.scan(cursor, match="leads:*")
        index_keys += len(keys)
        if cursor == 0:
            break

    # Get memory usage if possible
    try:
        memory_info = lead_cache.redis.info("memory")
        used_memory = memory_info.get("used_memory_human", "Unknown")
        peak_memory = memory_info.get("used_memory_peak_human", "Unknown")
    except:
        used_memory = "Not available"
        peak_memory = "Not available"

    print("\n=== Lead Cache Statistics ===")
    print(f"Total leads: {all_count}")
    print(f"Lead keys: {lead_keys}")
    print(f"Index keys: {index_keys}")
    print(f"Memory used: {used_memory}")
    print(f"Peak memory: {peak_memory}")
    print(f"TTL: {lead_cache.ttl_seconds / 3600:.1f} hours ({lead_cache.ttl_seconds} seconds)")


def main():
    parser = argparse.ArgumentParser(description="Redis Lead Cache Management Utility")
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # list command
    list_parser = subparsers.add_parser('list', help='List leads in the cache')
    list_parser.add_argument('--status', help='Filter by status')
    list_parser.add_argument('--page', type=int, default=1, help='Page number')
    list_parser.add_argument('--page-size', type=int, default=20, help='Results per page')

    # show command
    show_parser = subparsers.add_parser('show', help='Show details for a specific lead')
    show_parser.add_argument('fub_person_id', help='FUB Person ID to show')

    # clear command
    clear_parser = subparsers.add_parser('clear', help='Clear all leads from the cache')

    # invalidate command
    invalidate_parser = subparsers.add_parser('invalidate', help='Remove a specific lead from the cache')
    invalidate_parser.add_argument('fub_person_id', help='FUB Person ID to invalidate')

    # ping command
    ping_parser = subparsers.add_parser('ping', help='Check Redis connection')

    # status command
    status_parser = subparsers.add_parser('status', help='List all status categories and counts')

    # stats command
    stats_parser = subparsers.add_parser('stats', help='Show statistics about the lead cache')

    args = parser.parse_args()

    # First, check Redis connection for all commands except help
    if args.command and args.command != 'help':
        if not check_redis_connection():
            return 1

    # Handle commands
    if args.command == 'list':
        list_leads(args.status, args.page, args.page_size)
    elif args.command == 'show':
        show_lead(args.fub_person_id)
    elif args.command == 'clear':
        clear_cache()
    elif args.command == 'invalidate':
        invalidate_lead(args.fub_person_id)
    elif args.command == 'ping':
        # Already checked above
        pass
    elif args.command == 'status':
        list_status_categories()
    elif args.command == 'stats':
        get_cache_stats()
    else:
        parser.print_help()


if __name__ == "__main__":
    sys.exit(main() or 0)