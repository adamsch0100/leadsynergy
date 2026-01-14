"""
Test script to verify Selenium scrapers can login with database credentials
Requires: Chrome/Chromium browser and ChromeDriver installed
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

def test_redfin_login():
    """Test Redfin login with credentials from database"""
    print("=" * 60)
    print("Testing Redfin Login (Selenium)")
    print("=" * 60)
    
    test_lead = Lead()
    test_lead.fub_person_id = "test_123"
    test_lead.first_name = "Test"
    test_lead.last_name = "Lead"
    test_lead.source = "Redfin"
    
    service = None
    try:
        service = RedfinService(test_lead, status="Active")
        print(f"\nCredentials loaded:")
        print(f"  Email: {service.email}")
        print(f"  Password: {'*' * len(service.password) if service.password else 'None'}")
        
        if not service.email or not service.password:
            print("\n[FAIL] Missing credentials")
            return False
        
        print("\nAttempting login (this will open a browser)...")
        success = service.login()
        
        if success:
            print("[OK] Login successful!")
            return True
        else:
            print("[FAIL] Login failed")
            return False
            
    except Exception as e:
        print(f"\n[FAIL] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if service and hasattr(service, 'close'):
            service.close()


def test_homelight_login():
    """Test HomeLight login with credentials from database"""
    print("\n" + "=" * 60)
    print("Testing HomeLight Login (Selenium)")
    print("=" * 60)
    
    test_lead = Lead()
    test_lead.fub_person_id = "test_123"
    test_lead.first_name = "Test"
    test_lead.last_name = "Lead"
    test_lead.source = "HomeLight"
    
    service = None
    try:
        service = HomelightService(test_lead, status="Active")
        print(f"\nCredentials loaded:")
        print(f"  Email: {service.email}")
        print(f"  Password: {'*' * len(service.password) if service.password else 'None'}")
        
        if not service.email or not service.password:
            print("\n[FAIL] Missing credentials")
            return False
        
        print("\nAttempting login (this will open a browser)...")
        success = service.login()
        
        if success:
            print("[OK] Login successful!")
            return True
        else:
            print("[FAIL] Login failed")
            return False
            
    except Exception as e:
        print(f"\n[FAIL] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if service and hasattr(service, 'close'):
            service.close()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Selenium Scraper Login Test")
    print("=" * 60)
    print("\nNOTE: This will open Chrome browser windows for testing")
    print("Make sure ChromeDriver is installed and in your PATH")
    print("\nPress Ctrl+C to cancel, or wait 5 seconds to continue...")
    
    import time
    try:
        time.sleep(5)
    except KeyboardInterrupt:
        print("\nTest cancelled")
        sys.exit(0)
    
    # Test Redfin
    redfin_success = test_redfin_login()
    
    # Test HomeLight
    homelight_success = test_homelight_login()
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Redfin: {'[OK]' if redfin_success else '[FAIL]'}")
    print(f"HomeLight: {'[OK]' if homelight_success else '[FAIL]'}")
    print("=" * 60)

