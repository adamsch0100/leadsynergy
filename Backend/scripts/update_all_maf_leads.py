"""
Update All My Agent Finder Leads
Fetches all MAF leads from the database and updates them on the platform.
"""

import os
import sys
import logging

# Add the Backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.database.supabase_client import SupabaseClientSingleton
from app.referral_scrapers.my_agent_finder.my_agent_finder_service import MyAgentFinderService
from app.models.lead import Lead

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_maf_leads():
    """Fetch all My Agent Finder leads from the database"""
    supabase = SupabaseClientSingleton.get_instance()

    # Query leads where source is My Agent Finder
    result = supabase.table("leads").select("*").or_(
        "source.ilike.%myagentfinder%,source.ilike.%my agent finder%,source.ilike.%MAF%"
    ).execute()

    if not result.data:
        logger.info("No My Agent Finder leads found in database")
        return []

    leads = []
    for row in result.data:
        lead = Lead()
        lead.id = row.get('id')
        lead.first_name = row.get('first_name', '')
        lead.last_name = row.get('last_name', '')
        lead.email = row.get('email')
        lead.phone = row.get('phone')
        lead.source = row.get('source')
        lead.status = row.get('stage')  # FUB stage
        lead.fub_stage_name = row.get('fub_stage_name')
        lead.metadata = row.get('metadata') or {}
        leads.append(lead)

    return leads


def get_status_for_lead(lead):
    """Determine the status to set for a lead based on their FUB stage"""
    # Map FUB stages to My Agent Finder statuses
    stage = (lead.fub_stage_name or lead.status or '').lower()

    # Default mapping - adjust as needed
    stage_mapping = {
        'new lead': 'trying_to_reach',
        'attempting contact': 'trying_to_reach',
        'contacted': 'communicating',
        'appointment set': 'appointment',
        'showing': 'showing',
        'under contract': 'in_escrow',
        'closed': 'closed',
        'nurture': 'nurture',
        'not interested': 'unresponsive',
        'lost': 'another_agent',
    }

    # Find matching status
    for fub_stage, maf_status in stage_mapping.items():
        if fub_stage in stage:
            return maf_status

    # Default to communicating if no match
    return 'communicating'


def main(auto_confirm=False):
    print("=" * 60)
    print("MY AGENT FINDER - UPDATE ALL LEADS")
    print("=" * 60)

    # Get all MAF leads
    leads = get_maf_leads()

    if not leads:
        print("\nNo My Agent Finder leads found to update.")
        return

    print(f"\nFound {len(leads)} My Agent Finder lead(s):")
    for i, lead in enumerate(leads, 1):
        status = get_status_for_lead(lead)
        stage = lead.fub_stage_name or lead.status or 'Unknown'
        print(f"  {i}. {lead.first_name} {lead.last_name} - Stage: {stage} -> Status: {status}")

    # Confirm before proceeding
    if not auto_confirm:
        print("\n" + "-" * 40)
        response = input("Proceed with updating these leads? (y/n): ").strip().lower()
        if response != 'y':
            print("Cancelled.")
            return
    else:
        print("\n[Auto-confirmed with --yes flag]")

    # Prepare leads data for bulk update
    leads_data = []
    for lead in leads:
        status = get_status_for_lead(lead)
        leads_data.append((lead, status))

    # Create service and run bulk update
    print("\n" + "=" * 60)
    print("Starting bulk update...")
    print("=" * 60)

    service = MyAgentFinderService(
        lead=None,
        organization_id=None,
        same_status_note="Continuing to work with this client. Will provide updates as progress is made."
    )

    results = service.update_multiple_leads(leads_data)

    # Print results
    print("\n" + "=" * 60)
    print("UPDATE RESULTS")
    print("=" * 60)
    print(f"  Successful: {results['successful']}")
    print(f"  Failed: {results['failed']}")
    print(f"  Skipped: {results['skipped']}")

    if results['details']:
        print("\nDetails:")
        for detail in results['details']:
            status_icon = "✓" if detail['status'] == 'success' else "✗" if detail['status'] == 'failed' else "○"
            print(f"  {status_icon} {detail['name']}: {detail['status']}")
            if detail.get('error'):
                print(f"      Error: {detail['error']}")
            if detail.get('reason'):
                print(f"      Reason: {detail['reason']}")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    # Check for --yes flag to auto-confirm
    auto_confirm = '--yes' in sys.argv or '-y' in sys.argv
    main(auto_confirm)
