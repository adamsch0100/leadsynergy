"""Test script to run ReferralExchange Needs Action sweep - updates ALL leads to 'is open to working with me'"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# Verify headless is off
headless = os.getenv("SELENIUM_HEADLESS", "true")
print(f"SELENIUM_HEADLESS = {headless}")
if headless.lower() in ["true", "1", "yes"]:
    print("WARNING: Headless mode is ON. Set SELENIUM_HEADLESS=false in .env to see browser")
else:
    print("Headless mode is OFF - browser should be visible")

print("\n" + "="*60)
print("REFERRALEXCHANGE NEEDS ACTION SWEEP")
print("="*60)
print("\nThis script will:")
print("  1. Login to ReferralExchange")
print("  2. Navigate to the 'Needs Action' filter")
print("  3. For EVERY lead in Needs Action:")
print("     -> Update to 'We are in contact' -> 'is open to working with me'")
print("  4. Report how many leads were updated")
print("\nNo database lookup needed - all Needs Action leads get the same status.")
print("="*60)

input("\nPress Enter to start the Needs Action sweep...")

from app.referral_scrapers.referral_exchange.referral_exchange_service import ReferralExchangeService

# Create service instance (no lead needed for standalone sweep)
service = ReferralExchangeService(organization_id=None)

print("\nStarting Needs Action sweep...")
print("Watch the browser to see the process...\n")

results = service.run_standalone_need_action_sweep()

print("\n" + "="*60)
print("FINAL RESULTS")
print("="*60)
print(f"Total leads in Needs Action: {results['total_checked']}")
print(f"Successfully updated: {results['updated']}")
print(f"Errors: {results['errors']}")

if results['updated_leads']:
    print(f"\nUpdated leads:")
    for name in results['updated_leads']:
        print(f"  - {name}")

input("\nPress Enter to close...")
