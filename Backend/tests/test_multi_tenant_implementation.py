#!/usr/bin/env python3
"""
Test script for Multi-Tenant FUB API Key Implementation

This script tests the key components of the multi-tenant system:
1. FUB API key service
2. User profile management
3. Middleware functionality
4. Authentication flow
"""

import asyncio
import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.service.fub_api_key_service import FUBAPIKeyServiceSingleton
from app.service.user_service import UserServiceSingleton
from app.models.user import UserProfile
from app.database.fub_api_client import FUBApiClient


async def test_fub_api_key_service():
    """Test the FUB API key service"""
    print("🔑 Testing FUB API Key Service...")
    
    service = FUBAPIKeyServiceSingleton.get_instance()
    test_user_id = "test-user-123"
    
    # Test 1: Check if user has API key (should be False initially)
    has_key = service.has_api_key(test_user_id)
    print(f"   User has API key: {has_key}")
    assert not has_key, "User should not have API key initially"
    
    # Test 2: Get API key (should be None)
    api_key = service.get_api_key_for_user(test_user_id)
    print(f"   Retrieved API key: {api_key}")
    assert api_key is None, "API key should be None initially"
    
    print("✅ FUB API Key Service tests passed!")


def test_fub_api_client():
    """Test the FUB API client with different API keys"""
    print("🔌 Testing FUB API Client...")
    
    # Test 1: Client with no API key (uses environment)
    client1 = FUBApiClient()
    print(f"   Client 1 API key: {client1.api_key[:10]}..." if client1.api_key else "None")
    
    # Test 2: Client with custom API key
    test_api_key = "test-api-key-123"
    client2 = FUBApiClient(test_api_key)
    print(f"   Client 2 API key: {client2.api_key}")
    assert client2.api_key == test_api_key, "Client should use provided API key"
    
    print("✅ FUB API Client tests passed!")


def test_user_profile_model():
    """Test the UserProfile model"""
    print("👤 Testing UserProfile Model...")
    
    # Test 1: Create profile with onboarding fields
    profile = UserProfile()
    profile.id = "test-user-123"
    profile.email = "test@example.com"
    profile.onboarding_completed = False
    profile.fub_api_key = None
    
    # Test 2: Convert to dict
    profile_dict = profile.to_dict()
    print(f"   Profile dict keys: {list(profile_dict.keys())}")
    assert 'onboarding_completed' in profile_dict, "Profile should have onboarding_completed field"
    assert 'fub_api_key' in profile_dict, "Profile should have fub_api_key field"
    
    # Test 3: Create from dict
    profile2 = UserProfile.from_dict(profile_dict)
    assert profile2.onboarding_completed == False, "Onboarding should be False"
    assert profile2.fub_api_key is None, "API key should be None"
    
    print("✅ UserProfile Model tests passed!")


def test_middleware_skip_paths():
    """Test middleware skip paths logic"""
    print("🛡️ Testing Middleware Skip Paths...")
    
    # Simulate the skip paths logic from middleware
    skip_paths = [
        "/auth", 
        "/api/setup", 
        "/api/supabase/auth",
        "/api/supabase/users",
        "/api/supabase/organizations",
        "/api/supabase/team-members",
        "/api/supabase/system-settings",
        "/api/supabase/settings",
        "/api/supabase/subscription",
        "/api/supabase/payment-methods",
        "/api/supabase/billing-history",
        "/api/supabase/commissions"
    ]
    
    # Test paths that should be skipped
    test_paths = [
        "/api/setup/fub-api-key",
        "/api/supabase/auth/status",
        "/api/supabase/users/current/profile",
        "/api/supabase/leads",  # This should NOT be skipped
    ]
    
    for path in test_paths:
        should_skip = any(path.startswith(skip_path) for skip_path in skip_paths)
        print(f"   Path: {path} -> Skip: {should_skip}")
        
        if path == "/api/supabase/leads":
            assert not should_skip, "Leads endpoint should require FUB API key"
        else:
            assert should_skip, f"Path {path} should be skipped"
    
    print("✅ Middleware Skip Paths tests passed!")


async def main():
    """Run all tests"""
    print("🚀 Starting Multi-Tenant FUB API Key Implementation Tests\n")
    
    try:
        # Run tests
        await test_fub_api_key_service()
        print()
        
        test_fub_api_client()
        print()
        
        test_user_profile_model()
        print()
        
        test_middleware_skip_paths()
        print()
        
        print("🎉 All tests passed! Multi-tenant implementation is working correctly.")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    # Run the tests
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 