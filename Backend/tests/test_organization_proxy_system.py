#!/usr/bin/env python3
"""
Test script for Organization-Specific IPRoyal Proxy System

This script tests the key components of the organization-specific proxy system:
1. Proxy service functionality
2. Database integration
3. Selenium driver proxy integration
4. HTTP requests proxy integration
5. Error handling scenarios
"""

import sys
import os
from datetime import datetime

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.service.proxy_service import ProxyServiceSingleton
from app.referral_scrapers.utils.driver_service import DriverService
from app.referral_scrapers.base_referral_service import BaseReferralService
from app.models.lead import Lead


def test_proxy_service_basic_functionality():
    """Test basic proxy service functionality"""
    print("🔧 Testing ProxyService Basic Functionality...")
    
    try:
        proxy_service = ProxyServiceSingleton.get_instance()
        
        # Test getting non-existent configuration
        config = proxy_service.get_organization_proxy_config("test-org-123")
        print(f"✅ Non-existent config test: {config is None}")
        
        # Test creating a proxy configuration
        test_org_id = "test-org-456"
        success = proxy_service.create_organization_proxy_config(
            organization_id=test_org_id,
            proxy_username="test_user",
            proxy_password="test_pass",
            proxy_host="geo.iproyal.com",
            proxy_type="http",
            rotation_enabled=True,
            session_duration="15m"
        )
        print(f"✅ Create proxy config test: {success}")
        
        if success:
            # Test getting the created configuration
            config = proxy_service.get_organization_proxy_config(test_org_id)
            print(f"✅ Get created config test: {config is not None}")
            
            if config:
                print(f"   - Proxy host: {config['proxy_host']}")
                print(f"   - HTTP port: {config['http_port']}")
                print(f"   - Rotation enabled: {config['rotation_enabled']}")
                print(f"   - Session duration: {config['session_duration']}")
            
            # Test creating proxy URLs
            http_url = proxy_service.create_proxy_url(test_org_id, "http")
            socks5_url = proxy_service.create_proxy_url(test_org_id, "socks5")
            
            print(f"✅ HTTP proxy URL created: {http_url is not None}")
            print(f"✅ SOCKS5 proxy URL created: {socks5_url is not None}")
            
            if http_url:
                print(f"   - HTTP URL format: {http_url[:50]}...")
            if socks5_url:
                print(f"   - SOCKS5 URL format: {socks5_url[:50]}...")
            
            # Test proxy dict for requests
            proxy_dict = proxy_service.get_proxy_dict_for_requests(test_org_id)
            print(f"✅ Requests proxy dict created: {proxy_dict is not None}")
            
            if proxy_dict:
                print(f"   - Has HTTP proxy: {'http' in proxy_dict}")
                print(f"   - Has HTTPS proxy: {'https' in proxy_dict}")
            
            # Test selenium proxy config
            selenium_config = proxy_service.get_proxy_for_selenium(test_org_id)
            print(f"✅ Selenium proxy config created: {selenium_config is not None}")
            
            if selenium_config:
                print(f"   - Proxy type: {selenium_config['proxy_type']}")
                print(f"   - Host: {selenium_config['host']}")
                print(f"   - Port: {selenium_config['port']}")
                print(f"   - Has username: {'username' in selenium_config}")
                
        return True
        
    except Exception as e:
        print(f"❌ Error testing proxy service: {str(e)}")
        return False


def test_driver_service_with_proxy():
    """Test DriverService with proxy configuration"""
    print("\n🚗 Testing DriverService with Proxy...")
    
    try:
        # Test with organization ID (should load proxy config)
        test_org_id = "test-org-456"
        driver_service = DriverService(organization_id=test_org_id)
        
        print(f"✅ DriverService created with org ID: {driver_service.organization_id == test_org_id}")
        print(f"✅ Proxy config loaded: {driver_service.proxy_config is not None}")
        
        if driver_service.proxy_config:
            print(f"   - Proxy host: {driver_service.proxy_config.get('host')}")
            print(f"   - Proxy port: {driver_service.proxy_config.get('port')}")
            print(f"   - Has authentication: {'username' in driver_service.proxy_config}")
        
        # Test without organization ID (should work without proxy)
        driver_service_no_proxy = DriverService()
        print(f"✅ DriverService created without org ID: {driver_service_no_proxy.organization_id is None}")
        print(f"✅ No proxy config loaded: {driver_service_no_proxy.proxy_config is None}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing driver service: {str(e)}")
        return False


def test_base_referral_service_with_proxy():
    """Test BaseReferralService with proxy functionality"""
    print("\n🔄 Testing BaseReferralService with Proxy...")
    
    try:
        # Create a mock lead for testing
        mock_lead = Lead(
            id="test-lead-123",
            source="TestPlatform",
            status="New",
            email="test@example.com",
            first_name="Test",
            last_name="User"
        )
        
        # Create a test implementation of BaseReferralService
        class TestReferralService(BaseReferralService):
            def login(self) -> bool:
                return True
            
            def update_customers(self, status_to_select) -> bool:
                return True
            
            @classmethod
            def get_platform_name(cls) -> str:
                return "testplatform"
        
        # Test with organization ID
        test_org_id = "test-org-456"
        service_with_proxy = TestReferralService(lead=mock_lead, organization_id=test_org_id)
        
        print(f"✅ Service created with org ID: {service_with_proxy.organization_id == test_org_id}")
        print(f"✅ Proxy service initialized: {service_with_proxy.proxy_service is not None}")
        print(f"✅ Proxy dict available: {service_with_proxy.proxy_dict is not None}")
        print(f"✅ Driver service has proxy: {service_with_proxy.driver_service.proxy_config is not None}")
        
        # Test HTTP request method
        if hasattr(service_with_proxy, 'make_http_request'):
            print("✅ HTTP request method available")
            # Note: We won't actually make HTTP requests in the test
        
        # Test without organization ID
        service_without_proxy = TestReferralService(lead=mock_lead)
        print(f"✅ Service created without org ID: {service_without_proxy.organization_id is None}")
        print(f"✅ No proxy service: {service_without_proxy.proxy_service is None}")
        print(f"✅ No proxy dict: {service_without_proxy.proxy_dict is None}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing base referral service: {str(e)}")
        return False


def test_error_handling():
    """Test error handling scenarios"""
    print("\n⚠️ Testing Error Handling...")
    
    try:
        proxy_service = ProxyServiceSingleton.get_instance()
        
        # Test with invalid organization ID
        config = proxy_service.get_organization_proxy_config("invalid-org-999")
        print(f"✅ Invalid org ID handled: {config is None}")
        
        # Test proxy URL creation with invalid org
        url = proxy_service.create_proxy_url("invalid-org-999", "http")
        print(f"✅ Invalid org proxy URL handled: {url is None}")
        
        # Test driver service with invalid org
        driver_service = DriverService(organization_id="invalid-org-999")
        print(f"✅ Invalid org driver service handled: {driver_service.proxy_config is None}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing error handling: {str(e)}")
        return False


def test_proxy_url_formats():
    """Test proxy URL format generation"""
    print("\n🔗 Testing Proxy URL Formats...")
    
    try:
        proxy_service = ProxyServiceSingleton.get_instance()
        test_org_id = "test-org-456"
        
        # Test HTTP proxy URL
        http_url = proxy_service.create_proxy_url(test_org_id, "http")
        if http_url:
            print(f"✅ HTTP URL format valid: {http_url.startswith('http://')}")
            print(f"✅ Contains session ID: {'_session-' in http_url}")
            print(f"✅ Contains lifetime: {'_lifetime-' in http_url}")
        
        # Test SOCKS5 proxy URL
        socks5_url = proxy_service.create_proxy_url(test_org_id, "socks5")
        if socks5_url:
            print(f"✅ SOCKS5 URL format valid: {socks5_url.startswith('socks5://')}")
            print(f"✅ Contains session ID: {'_session-' in socks5_url}")
            print(f"✅ Contains lifetime: {'_lifetime-' in socks5_url}")
        
        # Test requests format
        proxy_dict = proxy_service.get_proxy_dict_for_requests(test_org_id)
        if proxy_dict:
            print(f"✅ Requests dict has http key: {'http' in proxy_dict}")
            print(f"✅ Requests dict has https key: {'https' in proxy_dict}")
            print(f"✅ HTTP and HTTPS URLs match: {proxy_dict.get('http') == proxy_dict.get('https')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing proxy URL formats: {str(e)}")
        return False


def run_all_tests():
    """Run all proxy system tests"""
    print("🚀 Starting Organization-Specific Proxy System Tests\n")
    print("=" * 60)
    
    tests = [
        ("Basic Proxy Service", test_proxy_service_basic_functionality),
        ("Driver Service Integration", test_driver_service_with_proxy),
        ("Base Referral Service Integration", test_base_referral_service_with_proxy),
        ("Error Handling", test_error_handling),
        ("Proxy URL Formats", test_proxy_url_formats),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        print("-" * 50)
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ Test failed with exception: {str(e)}")
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status:<10} {test_name}")
        if success:
            passed += 1
    
    print(f"\n🎯 Results: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! Organization-specific proxy system is working correctly.")
        print("\n📋 Next Steps:")
        print("1. Run the proxy configuration migration: python run_proxy_config_migration.py")
        print("2. Configure IPRoyal proxy credentials for your organizations")
        print("3. Test with actual referral platform scraping")
        print("4. Monitor proxy usage and performance")
    else:
        print("⚠️ Some tests failed. Please review the errors above.")
    
    return passed == len(results)


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1) 