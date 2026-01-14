"""
Test script to verify platform credentials work for login
"""
import sys
import os
from dotenv import load_dotenv

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from app.models.lead import Lead
from app.referral_scrapers.redfin.redfin_service import RedfinService
from app.referral_scrapers.homelight.homelight_service import HomelightService
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton

def test_credentials_loading():
    """Test that credentials are loaded from database"""
    print("=" * 60)
    print("Testing Credentials Loading from Database")
    print("=" * 60)
    
    settings_service = LeadSourceSettingsSingleton.get_instance()
    
    platforms = ["Redfin", "HomeLight", "ReferralExchange", "Estately"]
    
    for platform_name in platforms:
        print(f"\n--- Testing {platform_name} ---")
        lead_source_settings = settings_service.get_by_source_name(platform_name)
        
        if lead_source_settings:
            if isinstance(lead_source_settings, dict):
                metadata = lead_source_settings.get('metadata', {})
            else:
                metadata = lead_source_settings.metadata if hasattr(lead_source_settings, 'metadata') else {}
            
            # Parse metadata if it's a string
            if isinstance(metadata, str):
                import json
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}
            
            credentials = metadata.get('credentials', {}) if isinstance(metadata, dict) else {}
            
            if credentials and credentials.get('email') and credentials.get('password'):
                print(f"[OK] Credentials found in database")
                print(f"  Email: {credentials.get('email')}")
                print(f"  Password: {'*' * len(credentials.get('password', ''))}")
            else:
                print(f"[FAIL] No credentials found in database")
        else:
            print(f"[FAIL] Lead source not found in database")


def test_redfin_login():
    """Test Redfin login with credentials from database"""
    print("\n" + "=" * 60)
    print("Testing Redfin Login")
    print("=" * 60)
    
    # Create a dummy lead for testing
    test_lead = Lead()
    test_lead.fub_person_id = "test_123"
    test_lead.first_name = "Test"
    test_lead.last_name = "Lead"
    test_lead.email = "test@example.com"
    test_lead.phone = "1234567890"
    
    try:
        service = RedfinService(test_lead, status="Active")
        print(f"\nCredentials loaded:")
        print(f"  Email: {service.email}")
        print(f"  Password: {'*' * len(service.password) if service.password else 'None'}")
        
        if not service.email or not service.password:
            print("\n[FAIL] Missing credentials - cannot test login")
            return False
        
        print("\nAttempting login...")
        # Note: This will actually try to login, so we'll just test credential loading
        # Uncomment the next line to test actual login (requires Selenium/Chrome)
        # success = service.login()
        # print(f"Login result: {'[OK] Success' if success else '[FAIL] Failed'}")
        print("[OK] Credentials loaded successfully (login test skipped - requires browser)")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if hasattr(service, 'close'):
            service.close()


def test_homelight_login():
    """Test HomeLight login with credentials from database"""
    print("\n" + "=" * 60)
    print("Testing HomeLight Login")
    print("=" * 60)
    
    # Create a dummy lead for testing
    test_lead = Lead()
    test_lead.fub_person_id = "test_123"
    test_lead.first_name = "Test"
    test_lead.last_name = "Lead"
    test_lead.email = "test@example.com"
    test_lead.phone = "1234567890"
    
    try:
        service = HomelightService(test_lead, status="Active")
        print(f"\nCredentials loaded:")
        print(f"  Email: {service.email}")
        print(f"  Password: {'*' * len(service.password) if service.password else 'None'}")
        
        if not service.email or not service.password:
            print("\n[FAIL] Missing credentials - cannot test login")
            return False
        
        print("\nAttempting login...")
        # Note: This will actually try to login, so we'll just test credential loading
        # Uncomment the next line to test actual login (requires Selenium/Chrome)
        # success = service.login()
        # print(f"Login result: {'[OK] Success' if success else '[FAIL] Failed'}")
        print("[OK] Credentials loaded successfully (login test skipped - requires browser)")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if hasattr(service, 'close'):
            service.close()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Platform Credentials Test")
    print("=" * 60)
    
    # Test 1: Verify credentials are in database
    test_credentials_loading()
    
    # Test 2: Test Redfin credential loading
    test_redfin_login()
    
    # Test 3: Test HomeLight credential loading
    test_homelight_login()
    
    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)

