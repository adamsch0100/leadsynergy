"""
Script to analyze failed HomeLight leads and find common patterns
"""
import json
from dotenv import load_dotenv

load_dotenv()

from app.service.lead_service import LeadServiceSingleton
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton

# Failed leads data
failed_leads = {
    "customer_not_found": [
        3143,  # Benjamin Atchison
        3027,  # Michael Wimberley
        3023,  # Bruce Brotemarkle
        2800,  # Linda Decker
        2781,  # Denise Alexander
        2775,  # Robert Karyadeva
        2709,  # Richard Bamrick
        2921,  # Enrique Jimenez
    ],
    "status_update_failed": [
        3056,  # Patricia Kurtz
        3028,  # Steve Eisler
        3158,  # Tony Choi
        3021,  # Daniel Najar
        3010,  # Glenna Vansickle
        3009,  # Sandra Nye
        2999,  # Kristine
        2989,  # Karon Sadhnani
        2982,  # Cesar Holguin
        2974,  # Nathan Brounce
        2949,  # Ashley Brimhall
        2944,  # Charles Closson
        2929,  # Eric Kisskalt
        2925,  # Tim Mincer
        2923,  # Garret Dirks
        2920,  # Leeann Dye
        2907,  # Augustine Rodriguez
        2877,  # Frank Fischetta
        2826,  # Li Hwa
        2811,  # Robert Adams
        2759,  # Mark Sims
        2757,  # Stacey Allen
        2738,  # Karen Parish
        2706,  # Ramon Ramirez
        2666,  # Willie H
        2627,  # Charles Ward
        2576,  # Kristina Peterson
        2571,  # Rex Freburg
        2566,  # Chaim Bennell
    ]
}

lead_service = LeadServiceSingleton.get_instance()
settings_service = LeadSourceSettingsSingleton.get_instance()
settings = settings_service.get_by_source_name('HomeLight')

print("="*80)
print("ANALYZING FAILED HOMELIGHT LEADS")
print("="*80)

def analyze_leads(lead_ids, category):
    print(f"\n{'='*80}")
    print(f"CATEGORY: {category.upper().replace('_', ' ')}")
    print(f"{'='*80}")
    print(f"Total: {len(lead_ids)} leads\n")
    
    leads_data = []
    for fub_id in lead_ids:
        lead = lead_service.get_by_fub_person_id(str(fub_id))
        if lead:
            leads_data.append(lead)
        else:
            print(f"  ⚠ Lead with FUB ID {fub_id} not found in database")
    
    if not leads_data:
        print("  No leads found in database for this category")
        return
    
    # Analyze common characteristics
    print(f"\nFound {len(leads_data)} leads in database")
    
    # Check statuses
    statuses = {}
    for lead in leads_data:
        status = getattr(lead, 'status', 'N/A')
        statuses[status] = statuses.get(status, 0) + 1
    
    print(f"\nStatus Distribution:")
    for status, count in sorted(statuses.items(), key=lambda x: x[1], reverse=True):
        print(f"  {status}: {count}")
    
    # Check mapped stages
    print(f"\nMapped HomeLight Stages:")
    mapped_stages = {}
    for lead in leads_data:
        if settings:
            mapped = settings.get_mapped_stage(lead.status) if hasattr(lead, 'status') else None
            if isinstance(mapped, (list, tuple)):
                mapped_str = mapped[0] if mapped else 'None'
            else:
                mapped_str = str(mapped) if mapped else 'None'
            mapped_stages[mapped_str] = mapped_stages.get(mapped_str, 0) + 1
    
    for stage, count in sorted(mapped_stages.items(), key=lambda x: x[1], reverse=True):
        print(f"  {stage}: {count}")
    
    # Check names (for customer not found)
    if category == "customer_not_found":
        print(f"\nNames (for search analysis):")
        for lead in leads_data:
            full_name = f"{lead.first_name} {lead.last_name}"
            print(f"  {full_name} (ID: {lead.fub_person_id})")
    
    # Check metadata
    print(f"\nMetadata Analysis:")
    has_metadata = sum(1 for lead in leads_data if lead.metadata and isinstance(lead.metadata, dict))
    print(f"  Leads with metadata: {has_metadata}/{len(leads_data)}")
    
    # Check if any have homelight_last_updated
    has_sync_time = 0
    for lead in leads_data:
        if lead.metadata and isinstance(lead.metadata, dict):
            if lead.metadata.get("homelight_last_updated"):
                has_sync_time += 1
    print(f"  Leads with homelight_last_updated: {has_sync_time}/{len(leads_data)}")
    
    # Sample a few leads for detailed inspection
    print(f"\nSample Lead Details (first 3):")
    for i, lead in enumerate(leads_data[:3], 1):
        print(f"\n  Lead {i}:")
        print(f"    Name: {lead.first_name} {lead.last_name}")
        print(f"    FUB ID: {lead.fub_person_id}")
        print(f"    Status: {getattr(lead, 'status', 'N/A')}")
        if settings:
            mapped = settings.get_mapped_stage(lead.status) if hasattr(lead, 'status') else None
            print(f"    Mapped Stage: {mapped}")
        print(f"    Source: {getattr(lead, 'source', 'N/A')}")
        if lead.metadata:
            print(f"    Metadata: {json.dumps(lead.metadata, indent=6)}")

# Analyze each category
analyze_leads(failed_leads["customer_not_found"], "customer_not_found")
analyze_leads(failed_leads["status_update_failed"], "status_update_failed")

print(f"\n{'='*80}")
print("ANALYSIS COMPLETE")
print("="*80)

