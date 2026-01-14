"""Test script to verify My Agent Finder login and navigation"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

print("="*60)
print("MY AGENT FINDER LOGIN TEST")
print("="*60)

# Check credentials
my_agent_finder_email = os.getenv("MY_AGENT_FINDER_EMAIL")
my_agent_finder_password = os.getenv("MY_AGENT_FINDER_PASSWORD")

print(f"\nMyAgentFinder Email: {my_agent_finder_email[:3] if my_agent_finder_email else 'NOT SET'}...")
print(f"MyAgentFinder Password: {'SET' if my_agent_finder_password else 'NOT SET'}")

if not my_agent_finder_email or not my_agent_finder_password:
    print("\nWARNING: MyAgentFinder credentials not set in .env file")
    print("Add these to your .env file:")
    print("  MY_AGENT_FINDER_EMAIL=your_email")
    print("  MY_AGENT_FINDER_PASSWORD=your_password")

# Verify headless mode
headless = os.getenv("SELENIUM_HEADLESS", "true")
print(f"\nSELENIUM_HEADLESS = {headless}")
if headless.lower() in ["true", "1", "yes"]:
    print("WARNING: Headless mode is ON. Set SELENIUM_HEADLESS=false in .env to see browser")
else:
    print("Headless mode is OFF - browser should be visible")

print("\n" + "="*60)
print("This script will:")
print("  1. Navigate to My Agent Finder login page")
print("  2. Enter credentials")
print("  3. Verify login success")
print("  4. Explore the dashboard")
print("="*60)

input("\nPress Enter to start the My Agent Finder login test...")

from app.referral_scrapers.my_agent_finder.my_agent_finder_service import MyAgentFinderService
from app.models.lead import Lead

# Create a dummy lead for testing
test_lead = Lead()
test_lead.first_name = "Test"
test_lead.last_name = "User"
test_lead.fub_person_id = "test123"

# Create service instance
service = MyAgentFinderService(lead=test_lead, status="In Progress")

print("\nStarting My Agent Finder login test...")
print("Watch the browser to see the login process...\n")

try:
    if service.login():
        print("\n" + "="*60)
        print("SUCCESS! My Agent Finder login completed!")
        print("="*60)

        current_url = service.driver_service.get_current_url()
        print(f"Current URL: {current_url}")

        # Explore the page structure
        print("\nExploring page structure...")

        from selenium.webdriver.common.by import By

        # Look for key elements
        elements_to_find = [
            ("search input", "input[type='search'], input[placeholder*='search' i]"),
            ("leads/referrals table", "table, .leads-list, .referrals"),
            ("navigation menu", "nav, .nav, .sidebar"),
            ("status dropdowns", "select[name*='status' i], .status-dropdown"),
        ]

        for name, selector in elements_to_find:
            try:
                element = service.driver_service.find_element(By.CSS_SELECTOR, selector)
                if element:
                    print(f"  Found {name}: {selector}")
            except:
                print(f"  Not found: {name}")

        # Print page source snippet for debugging
        print("\nPage title:", service.driver_service.driver.title)

        # Wait for user to explore
        input("\nPress Enter to close the browser...")

    else:
        print("\n" + "="*60)
        print("FAILED: My Agent Finder login did not complete successfully")
        print("="*60)
        print("\nPossible issues:")
        print("  - Invalid credentials")
        print("  - Login page structure changed")
        print("  - Network/page loading issues")

        # Save screenshot for debugging
        try:
            service.driver_service.driver.save_screenshot("myagentfinder_login_failed.png")
            print("\nSaved debug screenshot: myagentfinder_login_failed.png")
        except:
            pass

        input("\nPress Enter to close the browser...")

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()

finally:
    print("\nClosing browser...")
    service.close()

print("\nTest complete!")
