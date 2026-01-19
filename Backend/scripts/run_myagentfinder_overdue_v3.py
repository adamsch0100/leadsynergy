"""
Script to process ALL MyAgentFinder overdue leads using the service method.
This version uses the built-in process_overdue_leads method from MyAgentFinderService.
"""
import os
import sys

# Ensure stdout is unbuffered
sys.stdout.reconfigure(line_buffering=True)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

# Force headless OFF for debugging
os.environ["SELENIUM_HEADLESS"] = "false"

print("=" * 60, flush=True)
print("MYAGENTFINDER OVERDUE LEADS - SERVICE METHOD V3", flush=True)
print("=" * 60, flush=True)

from app.referral_scrapers.my_agent_finder.my_agent_finder_service import MyAgentFinderService

# Set up console logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
NURTURE_DAYS_OFFSET = 180  # 6 months
ORGANIZATION_ID = "cfde8fec-3b87-4558-b20f-5fe25fdcf149"

print(f"\n[CONFIG] Nurture days offset: {NURTURE_DAYS_OFFSET} days", flush=True)
print(f"[CONFIG] Organization ID: {ORGANIZATION_ID}", flush=True)

# Initialize service
service = MyAgentFinderService(
    lead=None,
    status=None,
    organization_id=ORGANIZATION_ID,
    min_sync_interval_hours=0,
    nurture_days_offset=NURTURE_DAYS_OFFSET
)

try:
    print("\n[STEP 1] Processing overdue leads...", flush=True)
    results = service.process_overdue_leads(max_leads=50)

    print("\n" + "=" * 60, flush=True)
    print("RESULTS", flush=True)
    print("=" * 60, flush=True)
    print(f"Successful: {results.get('successful', 0)}", flush=True)
    print(f"Failed: {results.get('failed', 0)}", flush=True)
    print("=" * 60, flush=True)

    details = results.get('details', [])
    for detail in details:
        status = detail.get('status', 'unknown')
        name = detail.get('name', 'Unknown')
        if status == 'success':
            print(f"  [OK] {name} -> date set to {detail.get('new_date', 'N/A')}", flush=True)
        else:
            print(f"  [FAIL] {name}: {detail.get('reason', 'Unknown error')}", flush=True)

except Exception as e:
    print(f"\nFATAL ERROR: {e}", flush=True)
    import traceback
    traceback.print_exc()

finally:
    try:
        service.logout()
    except:
        pass

print("\n[DONE]", flush=True)
