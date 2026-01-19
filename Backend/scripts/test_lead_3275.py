"""
Test script to fetch lead 3275 from Follow Up Boss and analyze what the AI agent would do.
Run this from the Backend directory: python scripts/test_lead_3275.py
"""
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import json
from datetime import datetime

def main():
    print("=" * 80)
    print("LEAD SYNERGY - LEAD 3275 DIAGNOSTIC TEST")
    print("=" * 80)
    print(f"Run time: {datetime.now()}")
    print()

    # Step 1: Test FUB API Connection
    print("STEP 1: Testing FUB API Connection...")
    print("-" * 40)

    try:
        from app.database.fub_api_client import FUBApiClient
        api_client = FUBApiClient()
        print(f"  FUB API Key: {'*' * 20}...{api_client.api_key[-4:] if api_client.api_key else 'NOT SET'}")
        print(f"  Base URL: {api_client.base_url}")
    except Exception as e:
        print(f"  ERROR: Failed to initialize FUB API client: {e}")
        return

    # Step 2: Fetch Lead 3275
    print()
    print("STEP 2: Fetching Lead 3275 from FUB...")
    print("-" * 40)

    person_id = 3275
    lead_data = None

    try:
        lead_data = api_client.get_person(person_id)
        print(f"  SUCCESS: Retrieved lead data")
        print()
        print("  === LEAD DATA ===")
        print(f"  ID: {lead_data.get('id')}")
        print(f"  Name: {lead_data.get('firstName', 'N/A')} {lead_data.get('lastName', 'N/A')}")

        # Handle stage - could be string or object
        stage_data = lead_data.get('stage')
        if isinstance(stage_data, dict):
            stage_name = stage_data.get('name', 'N/A')
            stage_id = stage_data.get('id', 'N/A')
        else:
            stage_name = stage_data or 'N/A'
            stage_id = lead_data.get('stageId', 'N/A')
        print(f"  Stage: {stage_name} (ID: {stage_id})")

        print(f"  Source: {lead_data.get('source', 'N/A')}")
        print(f"  Created: {lead_data.get('created', 'N/A')}")

        # Contact info
        emails = lead_data.get('emails', [])
        phones = lead_data.get('phones', [])
        print(f"  Email(s): {', '.join([e.get('value', '') for e in emails]) if emails else 'N/A'}")
        print(f"  Phone(s): {', '.join([p.get('value', '') for p in phones]) if phones else 'N/A'}")

        # Tags
        tags = lead_data.get('tags', [])
        print(f"  Tags: {tags if tags else 'None'}")

        # Assigned agent
        assigned_to = lead_data.get('assignedTo')
        if assigned_to:
            if isinstance(assigned_to, dict):
                print(f"  Assigned To: {assigned_to.get('name', 'N/A')} (ID: {assigned_to.get('id', 'N/A')})")
            else:
                print(f"  Assigned To: {assigned_to}")
        else:
            print(f"  Assigned To: Unassigned")

        # Custom fields
        custom_fields = {k: v for k, v in lead_data.items() if k.startswith('custom')}
        if custom_fields:
            print(f"  Custom Fields: {json.dumps(custom_fields, indent=4)}")

    except Exception as e:
        print(f"  ERROR: Failed to fetch lead 3275: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 3: Check if lead exists in database
    print()
    print("STEP 3: Checking Lead in Database...")
    print("-" * 40)

    try:
        from app.database.supabase_client import SupabaseClientSingleton
        supabase = SupabaseClientSingleton.get_instance()

        # Check leads table
        result = supabase.table('leads').select('*').eq('fub_person_id', person_id).execute()

        if result.data and len(result.data) > 0:
            db_lead = result.data[0]
            print(f"  FOUND in database!")
            print(f"    Internal ID: {db_lead.get('id')}")
            print(f"    Status: {db_lead.get('status')}")
            print(f"    Source: {db_lead.get('source')}")
            print(f"    Tags: {db_lead.get('tags')}")
            print(f"    Created At: {db_lead.get('created_at')}")
            print(f"    Updated At: {db_lead.get('updated_at')}")
        else:
            print(f"  NOT FOUND in database")
            print(f"  -> Lead has not been synced to Lead Synergy yet")
            print(f"  -> Check if 'ReferralLink' tag is present: {'ReferralLink' in (lead_data.get('tags', []) or [])}")

    except Exception as e:
        print(f"  ERROR checking database: {e}")
        import traceback
        traceback.print_exc()

    # Step 4: Check lead source settings
    print()
    print("STEP 4: Checking Lead Source Configuration...")
    print("-" * 40)

    try:
        lead_source = lead_data.get('source', '')
        result = supabase.table('lead_source_settings').select('*').execute()

        if result.data:
            sources = [s.get('name') for s in result.data]
            print(f"  Configured sources: {sources}")

            # Check if lead's source is configured
            source_configured = any(
                lead_source.lower() in s.lower() or s.lower() in lead_source.lower()
                for s in sources
            ) if lead_source else False

            print(f"  Lead's source '{lead_source}' configured: {source_configured}")

            if not source_configured and lead_source:
                print(f"  WARNING: Lead source '{lead_source}' may not be configured in the system")
        else:
            print(f"  No lead source settings found")

    except Exception as e:
        print(f"  ERROR checking lead sources: {e}")

    # Step 5: Fetch Notes for Lead
    print()
    print("STEP 5: Fetching Notes for Lead...")
    print("-" * 40)

    try:
        notes = api_client.get_notes_for_person(person_id)
        print(f"  Found {len(notes)} notes")

        for i, note in enumerate(notes[:5], 1):  # Show first 5 notes
            print(f"  Note {i}:")
            print(f"    Subject: {note.get('subject', 'N/A')}")
            print(f"    Created: {note.get('created', 'N/A')}")
            body = note.get('body', '')
            preview = body[:100] + '...' if len(body) > 100 else body
            print(f"    Body: {preview}")

    except Exception as e:
        print(f"  ERROR fetching notes: {e}")

    # Step 6: Analyze AI Agent Response (NEW APPOINTMENT-FOCUSED)
    print()
    print("STEP 6: AI Agent Appointment Strategy Analysis...")
    print("-" * 40)

    try:
        from app.models.lead import Lead
        from app.ai_agent.response_generator import LeadProfile, AIResponseGenerator
        from app.ai_agent.compliance_checker import ComplianceChecker

        # Convert FUB data to Lead model
        lead = Lead.from_fub(lead_data)

        # Check stage eligibility
        compliance_checker = ComplianceChecker(supabase_client=supabase)

        if lead.status:
            is_eligible, status, reason = compliance_checker.check_stage_eligibility(lead.status)
            print(f"  Stage Eligibility Check:")
            print(f"    Current Stage: {lead.status}")
            print(f"    Is Eligible for AI Contact: {is_eligible}")
            print(f"    Status: {status.value if hasattr(status, 'value') else status}")
            print(f"    Reason: {reason}")

        # Build lead profile for AI
        lead_profile = LeadProfile.from_fub_data(lead_data)

        print()
        print("  Lead Profile for AI Agent:")
        print(f"    Name: {lead_profile.full_name}")
        print(f"    Lead Type: {lead_profile.lead_type.upper() if lead_profile.lead_type else 'UNKNOWN'}")
        print(f"    Source: {lead_profile.source}")
        print(f"    Days Since Created: {lead_profile.days_since_created}")
        print(f"    Tags: {lead_profile.tags}")

        # Initialize response generator to test new methods
        response_generator = AIResponseGenerator(
            personality="friendly_casual",
            agent_name="Sarah",
            brokerage_name="SAA Homes"
        )

        # NEW: Show appointment-focused AI strategy
        print()
        print("  === APPOINTMENT-FOCUSED AI STRATEGY ===")
        print()

        # 1. Goal Section
        goal_section = response_generator._build_goal_section(lead_profile)
        print("  1. GOAL SECTION (what the AI is trying to achieve):")
        print("-" * 40)
        for line in goal_section.strip().split('\n')[:6]:
            print(f"    {line}")
        print()

        # 2. Source Strategy
        strategy = response_generator._get_source_strategy(lead_profile.source)
        print(f"  2. SOURCE STRATEGY ({lead_profile.source}):")
        print(f"    Approach: {strategy['approach']}")
        print(f"    Urgency: {strategy['urgency']}")
        print(f"    Context: {strategy['context']}")
        print(f"    Opener Hint: {strategy['opener_hint']}")
        print()

        # 3. Lead Status Classification
        lead_status = response_generator._classify_lead_status(lead_profile)
        print(f"  3. LEAD STATUS: {lead_status}")
        status_descriptions = {
            "new_hot": "Brand new lead - respond immediately!",
            "active_engaged": "Recent and engaged - keep momentum!",
            "active_nurturing": "Active conversation - continue qualifying",
            "dormant_reengaging": "Need to re-engage - acknowledge gap naturally",
            "warm_following_up": "In between - gentle check-in"
        }
        print(f"    Description: {status_descriptions.get(lead_status, 'Unknown status')}")
        print()

        # 4. Known Info Section
        known_info = response_generator._build_known_info_section(lead_profile)
        print("  4. KNOWN INFORMATION (AI will NOT ask about these):")
        print("-" * 40)
        if known_info:
            for line in known_info.split('\n'):
                print(f"    {line}")
        else:
            print("    (No known info yet - AI will qualify)")
        print()

        # 5. Conversation Hints
        hints = response_generator._generate_conversation_hints(lead_profile, "initial")
        print("  5. CONVERSATION HINTS for AI:")
        for i, hint in enumerate(hints[:5], 1):
            print(f"    {i}. {hint[:100]}...")

        print()
        print("  === AI AGENT DECISION TREE ===")
        print()

        tags = lead_data.get('tags', []) or []
        has_referral_tag = 'ReferralLink' in tags

        print(f"  1. Has 'ReferralLink' tag? {has_referral_tag}")
        if not has_referral_tag:
            print(f"     -> BLOCKED: Lead won't be processed without ReferralLink tag")
            print(f"     -> ACTION NEEDED: Add 'ReferralLink' tag to this lead in FUB")
        else:
            print(f"     -> OK: Lead will be processed")

        print()
        print(f"  2. Lead Source check: '{lead.source}'")
        # This would need actual check against lead_source_settings

        print()
        print(f"  3. If lead is NEW (first webhook), AI would:")
        print(f"     -> Create lead in Lead Synergy database")
        print(f"     -> Create stage mapping for external platforms")
        print(f"     -> Generate welcome message via AI")

        print()
        print(f"  4. If lead REPLIES, AI would:")
        print(f"     -> Detect intent from message")
        print(f"     -> Check compliance (opt-out, quiet hours, rate limits)")
        print(f"     -> Generate contextual response")
        print(f"     -> Score the lead")
        print(f"     -> Track qualification progress")

    except Exception as e:
        print(f"  ERROR analyzing AI response: {e}")
        import traceback
        traceback.print_exc()

    # Step 7: Check for Errors
    print()
    print("STEP 7: Checking Error Logs...")
    print("-" * 40)

    try:
        # Check recent errors
        result = supabase.table('error_logs').select('*').order('created_at', desc=True).limit(5).execute()

        if result.data:
            print(f"  Recent errors ({len(result.data)} shown):")
            for error in result.data:
                print(f"    - [{error.get('error_type')}] {error.get('error_message', 'N/A')[:80]}")
                print(f"      Time: {error.get('created_at')}")
        else:
            print(f"  No recent errors found")

    except Exception as e:
        print(f"  ERROR checking error logs: {e}")

    # Step 8: Check AI Settings
    print()
    print("STEP 8: Checking AI Agent Settings...")
    print("-" * 40)

    try:
        result = supabase.table('ai_settings').select('*').limit(1).execute()

        if result.data:
            settings = result.data[0]
            print(f"  AI Agent Enabled: {settings.get('is_enabled', 'N/A')}")
            print(f"  Agent Name: {settings.get('agent_name', 'N/A')}")
            print(f"  Personality: {settings.get('personality_tone', 'N/A')}")
            print(f"  Working Hours: {settings.get('working_hours_start', 'N/A')} - {settings.get('working_hours_end', 'N/A')}")
            print(f"  Timezone: {settings.get('timezone', 'N/A')}")
        else:
            print(f"  No AI settings configured yet")

    except Exception as e:
        print(f"  ERROR checking AI settings: {e}")

    # Summary
    print()
    print("=" * 80)
    print("SUMMARY & RECOMMENDATIONS")
    print("=" * 80)

    tags = lead_data.get('tags', []) or []
    has_referral_tag = 'ReferralLink' in tags

    issues = []

    if not has_referral_tag:
        issues.append("Missing 'ReferralLink' tag - add this tag to enable Lead Synergy processing")

    # Check if in database
    try:
        result = supabase.table('leads').select('id').eq('fub_person_id', person_id).execute()
        if not result.data:
            issues.append("Lead not in database - needs to be synced via webhook or manual import")
    except:
        pass

    if issues:
        print("  ISSUES FOUND:")
        for i, issue in enumerate(issues, 1):
            print(f"    {i}. {issue}")
    else:
        print("  Lead appears to be properly configured!")

    print()
    print("  NEXT STEPS TO TEST AI AGENT:")
    print("    1. Ensure 'ReferralLink' tag is on the lead")
    print("    2. Trigger a webhook event (update lead in FUB)")
    print("    3. Check webhook endpoint is receiving events (check logs)")
    print("    4. Once lead is in database, send a test SMS to trigger AI response")
    print()
    print("  FULL LEAD DATA (JSON):")
    print("-" * 40)
    print(json.dumps(lead_data, indent=2, default=str))


if __name__ == "__main__":
    main()
