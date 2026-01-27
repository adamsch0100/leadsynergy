#!/usr/bin/env python
"""Test the webhook flow locally to debug AI responses."""

import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

async def test_ai_response():
    from app.ai_agent import create_agent_service
    from app.ai_agent.response_generator import LeadProfile

    print("=" * 60)
    print("Testing AI Agent Response")
    print("=" * 60)

    # Create agent service
    print("\n1. Creating agent service...")
    agent = create_agent_service()
    print(f"   Agent created: OK")
    print(f"   API key set: {bool(agent.response_generator.api_key)}")

    # Create a test lead profile
    print("\n2. Creating lead profile...")
    lead_profile = LeadProfile(
        first_name='Adam',
        last_name='Test',
        phone='+14155551234',
        source='MyAgentFinder',
        stage_name='New Lead',
        fub_person_id=2099,
    )
    print(f"   Lead: {lead_profile.first_name} {lead_profile.last_name}")

    print("\n3. Processing test message...")
    print("   Message: 'Hello, I am interested in buying a home'")

    try:
        response = await agent.process_message(
            message='Hello, I am interested in buying a home',
            lead_profile=lead_profile,
            fub_person_id=2099,
            channel='sms',
            user_id='87fecfda-3123-459b-8d95-62d4f943e60f',
            organization_id='8b8c289e-bccd-481b-98ca-2389a4b6648e',
        )

        print("\n4. Response received:")
        print(f"   Result: {response.result}")
        print(f"   State: {response.conversation_state}")
        print(f"   Intent: {response.detected_intent}")
        print(f"   Handoff: {response.should_handoff}")
        print(f"   Error: {response.error_message}")
        print(f"\n   Response text ({len(response.response_text) if response.response_text else 0} chars):")
        if response.response_text:
            print(f"   '{response.response_text}'")
        else:
            print("   [EMPTY - NO RESPONSE GENERATED]")

    except Exception as e:
        print(f"\n   ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_ai_response())
