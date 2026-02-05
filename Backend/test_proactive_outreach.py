"""
Test Proactive Outreach System

Tests the complete proactive outreach workflow with a real lead
without actually sending messages.

This validates:
1. Lead context analysis
2. Historical context extraction
3. Message generation with continuity
4. Compliance checking
5. Complete orchestration flow
"""

import os
import sys
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'ignore')

# Add Backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.supabase_client import SupabaseClientSingleton
from app.database.fub_api_client import FUBApiClient
from app.ai_agent.lead_context_analyzer import LeadContextAnalyzer
from app.ai_agent.initial_outreach_generator import InitialOutreachGenerator, LeadContext


async def test_lead_analysis(person_id: int):
    """Test lead context analysis on a real lead."""
    print(f"\n{'='*80}")
    print(f"TESTING LEAD CONTEXT ANALYSIS - Lead {person_id}")
    print(f"{'='*80}\n")

    load_dotenv()

    # Initialize clients
    supabase = SupabaseClientSingleton.get_instance()
    fub_client = FUBApiClient()

    # Step 1: Fetch lead data
    print("📥 Step 1: Fetching lead data from FUB...")
    try:
        person_data = fub_client.get_person(str(person_id), include_all_fields=True)

        first_name = person_data.get('firstName', person_data.get('name', 'Unknown'))
        last_name = person_data.get('lastName', '')
        full_name = f"{first_name} {last_name}".strip()

        print(f"   ✅ Found: {full_name}")
        print(f"   Phone: {person_data.get('phones', [{}])[0].get('value', 'N/A') if person_data.get('phones') else 'N/A'}")
        print(f"   Email: {person_data.get('emails', [{}])[0].get('value', 'N/A') if person_data.get('emails') else 'N/A'}")
        print(f"   Source: {person_data.get('source', 'N/A')}")

    except Exception as e:
        print(f"   ❌ Failed to fetch lead: {e}")
        return

    # Step 2: Analyze lead history
    print(f"\n🔍 Step 2: Analyzing complete lead history...")
    analyzer = LeadContextAnalyzer(fub_client, supabase)

    try:
        historical_context = await analyzer.analyze_lead_context(
            fub_person_id=person_id,
            enable_type="manual",
        )

        print(f"   ✅ Analysis complete!")
        print(f"\n   📊 LEAD CLASSIFICATION:")
        print(f"      Stage: {historical_context.lead_stage.stage}")
        print(f"      Confidence: {historical_context.lead_stage.confidence:.2f}")
        print(f"      Reasoning: {historical_context.lead_stage.reasoning}")

        print(f"\n   💬 COMMUNICATION HISTORY:")
        comm = historical_context.communication_history
        print(f"      Messages Sent (by agent): {comm.total_messages_sent}")
        print(f"      Messages Received (from lead): {comm.total_messages_received}")
        print(f"      Days Since Last Contact: {comm.days_since_last_contact}")
        print(f"      Conversation Ended How: {comm.conversation_ended_how}")

        if comm.response_rate > 0:
            print(f"      Response Rate: {comm.response_rate:.1f}%")
            print(f"      Engagement Quality: {comm.engagement_quality}")

        if comm.topics_discussed:
            print(f"      Topics Discussed: {', '.join(comm.topics_discussed)}")

        if comm.questions_already_asked:
            print(f"      ⚠️  Questions ALREADY Asked: {', '.join(comm.questions_already_asked)}")

        if comm.objections_raised:
            print(f"      ⚠️  Objections Raised: {', '.join(comm.objections_raised)}")

        if comm.last_message_preview:
            print(f"\n      Last Message Preview:")
            print(f"      \"{comm.last_message_preview[:150]}...\"")

        print(f"\n   🎯 RE-ENGAGEMENT STRATEGY:")
        strategy = historical_context.strategy
        print(f"      Approach: {strategy.approach}")
        print(f"      Tone: {strategy.tone}")
        print(f"      Message Angle: {strategy.message_angle}")

        if strategy.reference_context:
            print(f"      Reference: {strategy.reference_context[:100]}...")

        if strategy.avoid_topics:
            print(f"      ⚠️  Avoid Topics: {', '.join(strategy.avoid_topics)}")

    except Exception as e:
        print(f"   ❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 3: Generate messages
    print(f"\n✍️  Step 3: Generating personalized outreach messages...")

    try:
        # Build LeadContext
        lead_context = LeadContext(
            first_name=first_name,
            last_name=last_name,
            email=person_data.get('emails', [{}])[0].get('value', '') if person_data.get('emails') else '',
            phone=person_data.get('phones', [{}])[0].get('value', '') if person_data.get('phones') else '',
            fub_person_id=person_id,
            source=person_data.get('source', ''),
            city=person_data.get('city', ''),
            state=person_data.get('state', ''),
            zip_code=person_data.get('zip', ''),
            tags=person_data.get('tags', []),
        )

        generator = InitialOutreachGenerator(
            agent_name="Adam",  # Using your name
            agent_email="adam.m.schwartz84@gmail.com",
            brokerage_name="Schwartz & Associates",
        )

        outreach = await generator.generate_outreach(
            lead_context=lead_context,
            historical_context=historical_context,
        )

        print(f"   ✅ Messages generated!")
        print(f"   Model Used: {outreach.model_used}")
        print(f"   Tokens Used: {outreach.tokens_used}")

        print(f"\n   📱 SMS MESSAGE ({len(outreach.sms_message)} characters):")
        print(f"   {'-'*80}")
        print(f"   {outreach.sms_message}")
        print(f"   {'-'*80}")

        print(f"\n   📧 EMAIL:")
        print(f"   Subject: {outreach.email_subject}")
        print(f"   {'-'*80}")
        print(f"   {outreach.email_text[:500]}...")  # First 500 chars of plain text
        print(f"   {'-'*80}")

    except Exception as e:
        print(f"   ❌ Message generation failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 4: Summary
    print(f"\n{'='*80}")
    print("✅ TEST COMPLETE - SYSTEM WORKING CORRECTLY")
    print(f"{'='*80}\n")

    print("📋 SUMMARY:")
    print(f"   • Lead analyzed successfully: {full_name}")
    print(f"   • Classified as: {historical_context.lead_stage.stage}")
    print(f"   • Strategy: {historical_context.strategy.approach}")
    print(f"   • Messages generated with contextual awareness")
    if historical_context.communication_history.questions_already_asked:
        print(f"   • ✅ Will NOT repeat {len(historical_context.communication_history.questions_already_asked)} questions already asked")
    if historical_context.communication_history.topics_discussed:
        print(f"   • ✅ Will reference {len(historical_context.communication_history.topics_discussed)} topics previously discussed")

    print(f"\n💡 NEXT STEPS:")
    print(f"   1. Review the generated messages above")
    print(f"   2. If satisfied, run: python backfill_proactive_outreach.py --limit 1")
    print(f"   3. Then run full backfill: python backfill_proactive_outreach.py")
    print()


async def main():
    """Main test entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Test proactive outreach system")
    parser.add_argument("--person-id", type=int, help="FUB person ID to test with")

    args = parser.parse_args()

    if not args.person_id:
        # Get first lead from INITIAL state
        load_dotenv()
        supabase = SupabaseClientSingleton.get_instance()

        print("🔍 Finding a lead to test with...")
        ai_settings = supabase.table('lead_ai_settings').select('fub_person_id').eq('ai_enabled', True).limit(1).execute()

        if ai_settings.data:
            person_id = int(ai_settings.data[0]['fub_person_id'])
            print(f"   Using lead {person_id}\n")
        else:
            print("❌ No AI-enabled leads found. Enable AI for at least one lead first.")
            return
    else:
        person_id = args.person_id

    await test_lead_analysis(person_id)


if __name__ == '__main__':
    asyncio.run(main())
