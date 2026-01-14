#!/usr/bin/env python3
"""
Test script to verify USE_PROXY environment variable functionality
"""

import os
import sys
import logging
from unittest.mock import Mock

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_proxy_flag():
    """Test the USE_PROXY environment variable flag"""
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info("Testing USE_PROXY environment variable flag")
    
    # Test 1: Default behavior (no proxy)
    logger.info("\n=== Test 1: Default behavior (USE_PROXY not set) ===")
    if 'USE_PROXY' in os.environ:
        del os.environ['USE_PROXY']
    
    try:
        from app.referral_scrapers.utils.driver_service import DriverService
        from app.referral_scrapers.base_referral_service import BaseReferralService
        from app.models.lead import Lead
        
        # Test DriverService
        driver_service = DriverService(organization_id="test_org")
        logger.info(f"DriverService use_proxy: {driver_service.use_proxy}")
        assert driver_service.use_proxy == False, "Default should be False"
        
        # Test BaseReferralService (we'll use a mock implementation)
        class MockReferralService(BaseReferralService):
            def login(self):
                return True
            def update_customers(self, status):
                return True
            @classmethod
            def get_platform_name(cls):
                return "mock"
        
        mock_lead = Mock(spec=Lead)
        service = MockReferralService(mock_lead, organization_id="test_org")
        logger.info(f"BaseReferralService use_proxy: {service.use_proxy}")
        assert service.use_proxy == False, "Default should be False"
        
        logger.info("✓ Test 1 PASSED: Default behavior works correctly")
        
    except Exception as e:
        logger.error(f"✗ Test 1 FAILED: {str(e)}")
        return False
    
    # Test 2: Proxy enabled
    logger.info("\n=== Test 2: Proxy enabled (USE_PROXY=true) ===")
    os.environ['USE_PROXY'] = 'true'
    
    try:
        # Re-import to get fresh instances
        import importlib
        from app.referral_scrapers import utils
        importlib.reload(utils.driver_service)
        from app.referral_scrapers.utils.driver_service import DriverService
        
        driver_service = DriverService(organization_id="test_org")
        logger.info(f"DriverService use_proxy: {driver_service.use_proxy}")
        assert driver_service.use_proxy == True, "Should be True when USE_PROXY=true"
        
        # Test with different values
        for test_value in ['1', 'yes', 'True', 'TRUE']:
            os.environ['USE_PROXY'] = test_value
            driver_service = DriverService(organization_id="test_org")
            assert driver_service.use_proxy == True, f"Should be True for USE_PROXY={test_value}"
            logger.info(f"✓ USE_PROXY={test_value} correctly enables proxy")
        
        logger.info("✓ Test 2 PASSED: Proxy enabling works correctly")
        
    except Exception as e:
        logger.error(f"✗ Test 2 FAILED: {str(e)}")
        return False
    
    # Test 3: Proxy disabled
    logger.info("\n=== Test 3: Proxy disabled (USE_PROXY=false) ===")
    
    try:
        for test_value in ['false', '0', 'no', 'False', 'FALSE']:
            os.environ['USE_PROXY'] = test_value
            driver_service = DriverService(organization_id="test_org")
            assert driver_service.use_proxy == False, f"Should be False for USE_PROXY={test_value}"
            logger.info(f"✓ USE_PROXY={test_value} correctly disables proxy")
        
        logger.info("✓ Test 3 PASSED: Proxy disabling works correctly")
        
    except Exception as e:
        logger.error(f"✗ Test 3 FAILED: {str(e)}")
        return False
    
    # Test 4: ReferralExecutor
    logger.info("\n=== Test 4: ReferralExecutor proxy awareness ===")
    
    try:
        os.environ['USE_PROXY'] = 'true'
        from app.referral_scrapers.referral_executor import ReferralExecutor
        from app.models.stage_mapping import StageMapping
        
        # Create mock objects for required parameters
        mock_lead = Mock(spec=Lead)
        mock_stage_mapping = Mock(spec=StageMapping)
        
        executor = ReferralExecutor(mock_lead, mock_stage_mapping, organization_id="test_org")
        logger.info(f"ReferralExecutor use_proxy: {executor.use_proxy}")
        assert executor.use_proxy == True, "ReferralExecutor should be proxy-aware"
        
        os.environ['USE_PROXY'] = 'false'
        executor = ReferralExecutor(mock_lead, mock_stage_mapping, organization_id="test_org")
        assert executor.use_proxy == False, "ReferralExecutor should respect proxy flag"
        
        logger.info("✓ Test 4 PASSED: ReferralExecutor proxy awareness works")
        
    except Exception as e:
        logger.error(f"✗ Test 4 FAILED: {str(e)}")
        return False
    
    logger.info("\n🎉 ALL TESTS PASSED! USE_PROXY flag is working correctly")
    return True

def main():
    """Main test function"""
    
    # Save original environment
    original_env = os.environ.get('USE_PROXY')
    
    try:
        success = test_proxy_flag()
        
        if success:
            print("\n✅ Proxy flag test completed successfully!")
            print("You can now control proxy usage with the USE_PROXY environment variable:")
            print("  USE_PROXY=true   - Enable proxy usage")
            print("  USE_PROXY=false  - Disable proxy usage (default)")
        else:
            print("\n❌ Proxy flag test failed!")
            sys.exit(1)
            
    finally:
        # Restore original environment
        if original_env is not None:
            os.environ['USE_PROXY'] = original_env
        elif 'USE_PROXY' in os.environ:
            del os.environ['USE_PROXY']

if __name__ == "__main__":
    main() 