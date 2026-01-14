#!/usr/bin/env python3
"""
Script to run the organization proxy configuration migration for IPRoyal Proxy System
"""

import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.migrations import MigrationManager, MIGRATIONS

def run_proxy_config_migration():
    """Run only the organization proxy configuration migration"""
    print("🚀 Running organization proxy configuration migration...")
    
    # Find the proxy configuration migration
    proxy_migration = None
    for migration in MIGRATIONS:
        if migration['version'] == '20240126_add_organization_proxy_configs':
            proxy_migration = migration
            break
    
    if not proxy_migration:
        print("❌ Organization proxy configuration migration not found")
        return False
    
    # Run the migration
    manager = MigrationManager()
    success = manager.run_migrations([proxy_migration])
    
    if success:
        print("✅ Organization proxy configuration migration completed successfully")
        print("📋 Created table: organization_proxy_configs")
        print("🔗 Added foreign key constraint to organizations table")
        print("📊 Added indexes for performance")
        print("🔐 Added unique constraint for one active config per organization")
    else:
        print("❌ Organization proxy configuration migration failed")
    
    return success

if __name__ == "__main__":
    success = run_proxy_config_migration()
    sys.exit(0 if success else 1) 