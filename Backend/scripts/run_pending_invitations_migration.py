#!/usr/bin/env python3
"""
Script to run the pending invitations migration for Magic Link Invitation System
"""

import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.migrations import MigrationManager, MIGRATIONS

def run_pending_invitations_migration():
    """Run only the pending invitations migration"""
    print("🚀 Running pending invitations migration...")
    
    # Find the pending invitations migration
    pending_invitations_migration = None
    for migration in MIGRATIONS:
        if migration['version'] == '20240125_add_pending_invitations':
            pending_invitations_migration = migration
            break
    
    if not pending_invitations_migration:
        print("❌ Pending invitations migration not found")
        return False
    
    # Run the migration
    manager = MigrationManager()
    success = manager.run_migrations([pending_invitations_migration])
    
    if success:
        print("✅ Pending invitations migration completed successfully")
        print("📋 Created table: pending_invitations")
        print("🔗 Added foreign key constraint to organizations table")
        print("📊 Added indexes for performance")
    else:
        print("❌ Pending invitations migration failed")
    
    return success

if __name__ == "__main__":
    success = run_pending_invitations_migration()
    sys.exit(0 if success else 1) 