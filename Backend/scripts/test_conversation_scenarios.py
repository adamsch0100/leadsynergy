# -*- coding: utf-8 -*-
"""
Conversation Scenario Runner - Test multi-turn AI conversations.

This script simulates complete conversation flows to verify the AI agent
behaves correctly across different scenarios from initial contact to qualified.

Usage:
    python -m scripts.test_conversation_scenarios                        # List all scenarios
    python -m scripts.test_conversation_scenarios --scenario hot_buyer   # Run specific scenario
    python -m scripts.test_conversation_scenarios --all                  # Run all scenarios
    python -m scripts.test_conversation_scenarios --all --live           # Run all with real AI
    python -m scripts.test_conversation_scenarios --scenario hot_buyer --live --interactive
    python -m scripts.test_conversation_scenarios --fub-lead 3277 --live --dry-run
"""

import argparse
import asyncio
import os
import sys
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


# =============================================================================
# SYNTHETIC LEAD PROFILES
# =============================================================================

def create_synthetic_lead_profile(profile_name: str) -> "LeadProfile":
    """
    Create a synthetic lead profile that mirrors real FUB data.

    These profiles are designed to test various conversation scenarios
    with realistic context that the AI agent would receive from FUB.
    """
    from app.ai_agent.response_generator import LeadProfile

    profiles = {
        "hot_buyer": LeadProfile(
            first_name="Marcus",
            last_name="Chen",
            full_name="Marcus Chen",
            email="marcus.chen@email.com",
            phone="+15551234567",
            score=65,
            score_label="Warm",
            stage_name="New Lead",
            lead_type="buyer",
            source="MyAgentFinder",
            source_url="https://myagentfinder.com/agents/austin-tx",
            property_inquiry_source="MyAgentFinder.com",
            property_inquiry_description="Primary Zip: 78704 | Time Frame: 0 - 3 Months | Pre-approved",
            property_inquiry_timeline="0 - 3 Months",
            property_inquiry_budget="$450,000 - $550,000",
            property_inquiry_financing="Pre-approved",
            preferred_cities=["Austin"],
            preferred_neighborhoods=["South Austin", "Travis Heights"],
            timeline="short",
            is_pre_approved=True,
            pre_approval_amount=525000,
            price_min=450000,
            price_max=550000,
            days_since_created=0,
            is_first_contact=True,
            has_received_any_messages=False,
            tags=["Buyer", "ReferralLink", "AI Follow-up"],
            fub_person_id=99901,
        ),

        "hot_seller": LeadProfile(
            first_name="Patricia",
            last_name="Williams",
            full_name="Patricia Williams",
            email="patricia.w@email.com",
            phone="+15559876543",
            score=70,
            score_label="Hot",
            stage_name="New Lead",
            lead_type="seller",
            source="HomeLight",
            source_url="https://homelight.com/sell",
            property_inquiry_source="HomeLight",
            property_inquiry_description="Wants to sell home | Timeline: 60-90 days | Reason: Downsizing",
            property_inquiry_timeline="60-90 days",
            current_address="4521 Oak Lane, Austin, TX 78731",
            motivation="downsizing",
            motivation_detail="Kids moved out, want smaller home",
            days_since_created=1,
            is_first_contact=True,
            has_received_any_messages=False,
            tags=["Seller", "ReferralLink", "AI Follow-up"],
            fub_person_id=99902,
        ),

        "warm_buyer": LeadProfile(
            first_name="David",
            last_name="Park",
            full_name="David Park",
            email="david.park@email.com",
            phone="+15553334444",
            score=45,
            score_label="Warm",
            stage_name="New Lead",
            lead_type="buyer",
            source="Zillow",
            source_url="https://zillow.com/austin-tx",
            property_inquiry_source="Zillow",
            property_inquiry_description="Searching in Austin | Budget: Not specified | Timeline: Not specified",
            preferred_cities=["Austin"],
            days_since_created=2,
            is_first_contact=True,
            has_received_any_messages=False,
            tags=["Buyer", "ReferralLink", "AI Follow-up"],
            fub_person_id=99903,
        ),

        "cold_buyer": LeadProfile(
            first_name="Emily",
            last_name="Johnson",
            full_name="Emily Johnson",
            email="emily.j@email.com",
            phone="+15556667777",
            score=25,
            score_label="Cold",
            stage_name="New Lead",
            lead_type="buyer",
            source="Redfin",
            days_since_created=5,
            is_first_contact=True,
            has_received_any_messages=False,
            tags=["ReferralLink", "AI Follow-up"],
            fub_person_id=99904,
        ),

        "objection_has_agent": LeadProfile(
            first_name="Robert",
            last_name="Garcia",
            full_name="Robert Garcia",
            email="robert.garcia@email.com",
            phone="+15558889999",
            score=55,
            score_label="Warm",
            stage_name="New Lead",
            lead_type="buyer",
            source="Redfin",
            preferred_cities=["Austin"],
            timeline="short",
            days_since_created=1,
            is_first_contact=True,
            has_received_any_messages=False,
            objection_count=0,
            previous_objections=[],
            tags=["Buyer", "ReferralLink", "AI Follow-up"],
            fub_person_id=99905,
        ),

        "objection_not_ready": LeadProfile(
            first_name="Lisa",
            last_name="Martinez",
            full_name="Lisa Martinez",
            email="lisa.m@email.com",
            phone="+15551112222",
            score=40,
            score_label="Warm",
            stage_name="New Lead",
            lead_type="buyer",
            source="Facebook",
            days_since_created=3,
            is_first_contact=True,
            has_received_any_messages=False,
            tags=["ReferralLink", "AI Follow-up"],
            fub_person_id=99906,
        ),

        "multiple_objections": LeadProfile(
            first_name="James",
            last_name="Wilson",
            full_name="James Wilson",
            email="james.w@email.com",
            phone="+15553334455",
            score=35,
            score_label="Cold",
            stage_name="New Lead",
            lead_type="buyer",
            source="Zillow",
            objection_count=1,
            previous_objections=["not_interested"],
            days_since_created=7,
            is_first_contact=False,
            has_received_any_messages=True,
            total_messages_sent=2,
            tags=["ReferralLink", "AI Follow-up"],
            fub_person_id=99907,
        ),

        "escalation_request": LeadProfile(
            first_name="Michelle",
            last_name="Thompson",
            full_name="Michelle Thompson",
            email="michelle.t@email.com",
            phone="+15557778888",
            score=60,
            score_label="Warm",
            stage_name="New Lead",
            lead_type="seller",
            source="ReferralExchange",
            property_inquiry_source="ReferralExchange",
            current_address="789 Pine St, Austin, TX",
            is_first_contact=True,
            has_received_any_messages=False,
            tags=["Seller", "ReferralLink", "AI Follow-up"],
            fub_person_id=99908,
        ),

        "opt_out": LeadProfile(
            first_name="Kevin",
            last_name="Brown",
            full_name="Kevin Brown",
            email="kevin.b@email.com",
            phone="+15559990000",
            score=30,
            score_label="Cold",
            stage_name="New Lead",
            lead_type="buyer",
            source="Facebook",
            is_first_contact=True,
            has_received_any_messages=False,
            tags=["ReferralLink", "AI Follow-up"],
            fub_person_id=99909,
        ),

        "frustrated_lead": LeadProfile(
            first_name="Amanda",
            last_name="Davis",
            full_name="Amanda Davis",
            email="amanda.d@email.com",
            phone="+15551234000",
            score=45,
            score_label="Warm",
            stage_name="New Lead",
            lead_type="buyer",
            source="Zillow",
            total_messages_sent=3,
            total_messages_received=2,
            is_first_contact=False,
            has_received_any_messages=True,
            previous_objections=["timing"],
            objection_count=1,
            tags=["ReferralLink", "AI Follow-up"],
            fub_person_id=99910,
        ),

        # =========================================================================
        # NON-RESPONSIVE / COLD LEAD PROFILES - For revival testing
        # =========================================================================

        "non_responsive_cold": LeadProfile(
            first_name="Janice",
            last_name="Moseychuck",
            full_name="Janice Moseychuck",
            email="janice.m@email.com",
            phone="+15129876543",
            score=15,
            score_label="Cold",
            stage_name="C - Cold 6+ Months",
            lead_type="buyer",
            source="Website",
            source_url="https://saahomes.com",
            property_inquiry_description="Looking for property in Austin area",
            preferred_cities=["Austin"],
            days_since_created=900,  # ~2.5 years old
            is_first_contact=False,  # Has had some contact before
            has_received_any_messages=True,
            total_messages_sent=2,  # 2 emails sent previously
            total_messages_received=0,  # Never responded
            last_contact_date="2024-07-15",  # 6+ months ago
            last_contact_type="email",
            tags=["Buyer", "Cold", "AI Follow-up"],
            fub_person_id=99911,
        ),

        "non_responsive_warm": LeadProfile(
            first_name="Michael",
            last_name="Turner",
            full_name="Michael Turner",
            email="m.turner@email.com",
            phone="+15125551234",
            score=35,
            score_label="Warm",
            stage_name="Working",
            lead_type="buyer",
            source="Zillow",
            property_inquiry_source="Zillow",
            property_inquiry_description="Viewing listings in 78704",
            property_inquiry_timeline="3-6 months",
            preferred_cities=["Austin"],
            preferred_neighborhoods=["South Austin", "78704"],
            days_since_created=14,  # 2 weeks old
            is_first_contact=False,
            has_received_any_messages=True,
            total_messages_sent=3,  # Multiple outreach attempts
            total_messages_received=1,  # Replied once then went quiet
            last_contact_date="2026-01-21",  # 5 days ago
            last_contact_type="sms",
            tags=["Buyer", "Working", "AI Follow-up"],
            fub_person_id=99912,
        ),
    }

    return profiles.get(profile_name)


# =============================================================================
# SCENARIO DEFINITIONS
# =============================================================================

@dataclass
class ConversationStep:
    """A single step in a conversation scenario."""
    lead_message: str  # Empty string for AI-initiated first contact
    expected_behavior: str  # Human-readable description
    expected_state: Optional[str] = None
    should_handoff: bool = False
    score_change: Optional[str] = None  # "increase", "decrease", "stable"


@dataclass
class Scenario:
    """A complete conversation scenario."""
    name: str
    description: str
    profile_name: str  # Maps to synthetic lead profile
    steps: List[ConversationStep]
    expected_outcome: str
    lead_type: str = "buyer"
    channel: str = "sms"  # "sms" or "email"


SCENARIOS: Dict[str, Scenario] = {
    "hot_buyer": Scenario(
        name="Hot Buyer - Full Qualification to Appointment",
        description="Motivated pre-approved buyer provides info, books appointment",
        profile_name="hot_buyer",
        lead_type="buyer",
        steps=[
            ConversationStep(
                "",
                "AI sends warm first contact, references source and pre-approval",
                "initial",
            ),
            ConversationStep(
                "Yes I'm interested! Looking to move soon",
                "AI acknowledges interest, asks about timeline specifics",
                "qualifying",
                score_change="increase",
            ),
            ConversationStep(
                "Need to move in 30 days for my new job",
                "AI confirms urgency, asks about areas",
                "qualifying",
                score_change="increase",
            ),
            ConversationStep(
                "South Austin near Travis Heights",
                "AI confirms location, offers appointment",
                "scheduling",
                score_change="increase",
            ),
            ConversationStep(
                "Yes Thursday afternoon works",
                "AI confirms appointment, triggers handoff to human agent",
                "handed_off",
                should_handoff=True,
                score_change="increase",
            ),
        ],
        expected_outcome="appointment_booked",
    ),

    "hot_seller": Scenario(
        name="Hot Seller - Listing Consultation",
        description="Seller wants to list home, books consultation",
        profile_name="hot_seller",
        lead_type="seller",
        steps=[
            ConversationStep(
                "",
                "AI sends seller-focused first contact, mentions their home",
                "initial",
            ),
            ConversationStep(
                "Yes I want to sell my house on Oak Lane",
                "AI acknowledges, asks about timeline and motivation",
                "qualifying",
                score_change="increase",
            ),
            ConversationStep(
                "Kids moved out, need to sell in 60 days so I can close on my condo",
                "AI acknowledges urgency, offers listing consultation",
                "scheduling",
                score_change="increase",
            ),
            ConversationStep(
                "Yes let's set something up",
                "AI confirms consultation, triggers handoff",
                "handed_off",
                should_handoff=True,
                score_change="increase",
            ),
        ],
        expected_outcome="appointment_booked",
    ),

    "warm_buyer_nurture": Scenario(
        name="Warm Buyer - Moves to Nurture",
        description="Buyer just started looking, 6+ month timeline, moves to nurture",
        profile_name="warm_buyer",
        lead_type="buyer",
        steps=[
            ConversationStep(
                "",
                "AI sends first contact",
                "initial",
            ),
            ConversationStep(
                "Just started looking, not sure yet",
                "AI gently qualifies, asks about timeline",
                "qualifying",
            ),
            ConversationStep(
                "Probably 6-12 months from now",
                "AI acknowledges long timeline, offers to stay in touch",
                "nurture",
                score_change="decrease",
            ),
            ConversationStep(
                "Sure that would be helpful",
                "AI confirms nurture, offers value",
                "nurture",
            ),
        ],
        expected_outcome="nurture_sequence",
    ),

    "cold_lead": Scenario(
        name="Cold Lead - Just Browsing",
        description="Lead not interested, moves to long-term nurture",
        profile_name="cold_buyer",
        lead_type="buyer",
        steps=[
            ConversationStep(
                "",
                "AI sends first contact",
                "initial",
            ),
            ConversationStep(
                "Just browsing, not really interested",
                "AI respects, offers to be available",
                "nurture",
                score_change="decrease",
            ),
            ConversationStep(
                "Maybe next year",
                "AI moves to long-term nurture, leaves door open",
                "nurture",
            ),
        ],
        expected_outcome="nurture_long_term",
    ),

    "objection": Scenario(
        name="Objection - Already Has Agent",
        description="Lead says they have agent, AI handles objection and re-engages",
        profile_name="objection_has_agent",
        lead_type="buyer",
        steps=[
            ConversationStep(
                "",
                "AI sends first contact",
                "initial",
            ),
            ConversationStep(
                "I already have an agent",
                "AI handles objection gracefully, asks what made them look",
                "objection_handling",
            ),
            ConversationStep(
                "They never respond to my messages though",
                "AI acknowledges frustration, offers responsive service",
                "qualifying",
                score_change="increase",
            ),
            ConversationStep(
                "Actually yes, I'd like to talk",
                "AI re-engages, continues qualification",
                "qualifying",
                score_change="increase",
            ),
        ],
        expected_outcome="re_engaged",
    ),

    "objection_not_ready": Scenario(
        name="Objection - Not Ready",
        description="Lead not ready, AI gracefully moves to nurture",
        profile_name="objection_not_ready",
        lead_type="buyer",
        steps=[
            ConversationStep(
                "",
                "AI sends first contact",
                "initial",
            ),
            ConversationStep(
                "Not ready to buy yet",
                "AI acknowledges, asks when might be ready",
                "objection_handling",
            ),
            ConversationStep(
                "Still saving for down payment",
                "AI offers resources, moves to nurture",
                "nurture",
            ),
        ],
        expected_outcome="nurture_graceful",
    ),

    "multiple_objections": Scenario(
        name="Multiple Objections - Escalate",
        description="Lead repeatedly objects, AI escalates to human",
        profile_name="multiple_objections",
        lead_type="buyer",
        steps=[
            ConversationStep(
                "",
                "AI sends follow-up message",
                "initial",
            ),
            ConversationStep(
                "I said I'm not interested",
                "AI apologizes, offers one last value",
                "objection_handling",
            ),
            ConversationStep(
                "Stop contacting me",
                "AI acknowledges, offers human agent option",
                "objection_handling",
            ),
            ConversationStep(
                "Fine, have someone call me",
                "AI escalates to human agent",
                "handed_off",
                should_handoff=True,
            ),
        ],
        expected_outcome="escalated_to_human",
    ),

    "escalation": Scenario(
        name="Immediate Escalation Request",
        description="Lead immediately asks for human, AI hands off",
        profile_name="escalation_request",
        lead_type="seller",
        steps=[
            ConversationStep(
                "",
                "AI sends first contact",
                "initial",
            ),
            ConversationStep(
                "I want to talk to a real person, not a bot",
                "AI immediately hands off to human",
                "handed_off",
                should_handoff=True,
            ),
        ],
        expected_outcome="immediate_handoff",
    ),

    "opt_out": Scenario(
        name="Opt-Out Flow",
        description="Lead opts out with STOP keyword, AI confirms",
        profile_name="opt_out",
        lead_type="buyer",
        steps=[
            ConversationStep(
                "",
                "AI sends first contact",
                "initial",
            ),
            ConversationStep(
                "STOP",
                "AI sends opt-out confirmation message",
                "completed",
            ),
        ],
        expected_outcome="opted_out",
    ),

    "frustrated": Scenario(
        name="Frustrated Lead",
        description="Lead becomes frustrated, AI escalates",
        profile_name="frustrated_lead",
        lead_type="buyer",
        steps=[
            ConversationStep(
                "",
                "AI sends follow-up message",
                "initial",
            ),
            ConversationStep(
                "Stop bothering me!",
                "AI backs off gently, apologizes",
                "objection_handling",
            ),
            ConversationStep(
                "This is ridiculous, I've told you multiple times",
                "AI escalates to human agent immediately",
                "handed_off",
                should_handoff=True,
            ),
        ],
        expected_outcome="escalated_frustrated",
    ),

    # =========================================================================
    # EMAIL SCENARIOS
    # =========================================================================

    "email_hot_buyer": Scenario(
        name="Email - Hot Buyer Qualification",
        description="Email conversation with motivated buyer",
        profile_name="hot_buyer",
        lead_type="buyer",
        channel="email",
        steps=[
            ConversationStep(
                "",
                "AI sends personalized email introduction",
                "initial",
            ),
            ConversationStep(
                "Hi, yes I got your email. I'm looking to buy in South Austin area.",
                "AI acknowledges, asks qualifying questions about timeline and budget",
                "qualifying",
                score_change="increase",
            ),
            ConversationStep(
                "We're pre-approved for $525k and need to move within 30 days for my new job at Dell.",
                "AI recognizes hot lead, offers to schedule a call",
                "scheduling",
                score_change="increase",
            ),
            ConversationStep(
                "Yes, I can do a call Thursday afternoon",
                "AI confirms appointment, hands off to human agent",
                "handed_off",
                should_handoff=True,
                score_change="increase",
            ),
        ],
        expected_outcome="appointment_booked_email",
    ),

    "email_seller_listing": Scenario(
        name="Email - Seller Listing Inquiry",
        description="Email conversation with seller wanting to list",
        profile_name="hot_seller",
        lead_type="seller",
        channel="email",
        steps=[
            ConversationStep(
                "",
                "AI sends seller-focused email about their property",
                "initial",
            ),
            ConversationStep(
                "I received your email. Yes I want to sell my home at 4521 Oak Lane. The kids have moved out and we're looking to downsize.",
                "AI acknowledges motivation, asks about timeline",
                "qualifying",
                score_change="increase",
            ),
            ConversationStep(
                "We want to sell within 60 days so we can close on our new condo.",
                "AI offers free home valuation and listing consultation",
                "scheduling",
                score_change="increase",
            ),
            ConversationStep(
                "That sounds great, let's schedule the consultation",
                "AI confirms consultation, hands off",
                "handed_off",
                should_handoff=True,
            ),
        ],
        expected_outcome="listing_consultation_email",
    ),

    # =========================================================================
    # NON-RESPONSIVE LEAD SCENARIOS - Testing follow-up sequences
    # =========================================================================

    "non_responsive_cold_revival": Scenario(
        name="Non-Responsive Cold Lead - Revival Sequence",
        description="Cold lead (6+ months), AI attempts revival sequence, no response",
        profile_name="non_responsive_cold",
        lead_type="buyer",
        channel="sms",
        steps=[
            # Day 0: AI sends value-first revival message
            ConversationStep(
                "",
                "AI sends value-first revival message (not salesy), references their original interest",
                None,  # State can vary - AI may start qualifying immediately
            ),
            # Day 0 + 30 min: Follow-up with CTA (no response yet)
            ConversationStep(
                "[NO_RESPONSE]",
                "AI sends value + appointment CTA (30 min later if no response)",
                None,  # State maintained - still no response
            ),
            # Day 1: Qualify motivation (still no response)
            ConversationStep(
                "[NO_RESPONSE]",
                "AI asks about their situation/motivation (Day 1)",
                None,  # State maintained
            ),
            # Day 3: Email channel switch
            ConversationStep(
                "[NO_RESPONSE]",
                "AI switches to email with market report (Day 3)",
                None,  # State maintained
            ),
            # Day 7: Strategic breakup message
            ConversationStep(
                "[NO_RESPONSE]",
                "AI sends strategic breakup message - highest response rate! (Day 7)",
                None,  # Final state varies - could be nurture or qualifying
            ),
        ],
        expected_outcome="moved_to_long_term_nurture",
    ),

    "non_responsive_cold_reengaged": Scenario(
        name="Non-Responsive Cold Lead - Re-engaged",
        description="Cold lead re-engages after breakup message",
        profile_name="non_responsive_cold",
        lead_type="buyer",
        channel="sms",
        steps=[
            # Day 0: AI sends value-first revival message
            ConversationStep(
                "",
                "AI sends value-first revival message",
                "initial",
            ),
            # Day 1: No response
            ConversationStep(
                "[NO_RESPONSE]",
                "AI sends qualification question (Day 1)",
                "initial",
            ),
            # Day 7: Strategic breakup
            ConversationStep(
                "[NO_RESPONSE]",
                "AI sends strategic breakup message (Day 7)",
                "initial",
            ),
            # Lead re-engages after breakup!
            ConversationStep(
                "Hey sorry I've been busy. Actually yes I'm still looking to buy",
                "AI welcomes back, re-qualifies timeline",
                "qualifying",
                score_change="increase",
            ),
            ConversationStep(
                "Probably in the next 3-6 months when my lease ends",
                "AI acknowledges timeline, offers value and stays in touch",
                "nurture",
            ),
        ],
        expected_outcome="re_engaged_to_nurture",
    ),

    "non_responsive_warm_sequence": Scenario(
        name="Non-Responsive Warm Lead - Standard Sequence",
        description="Warm lead went quiet, AI runs standard follow-up",
        profile_name="non_responsive_warm",
        lead_type="buyer",
        channel="sms",
        steps=[
            # Day 0: Gentle follow-up since they've engaged before
            ConversationStep(
                "",
                "AI sends gentle follow-up referencing previous conversation",
                "initial",
            ),
            # Day 1: No response
            ConversationStep(
                "[NO_RESPONSE]",
                "AI adds value (property alert style)",
                "initial",
            ),
            # Day 3: No response - try email
            ConversationStep(
                "[NO_RESPONSE]",
                "AI switches to email with market insights",
                "initial",
            ),
            # Day 7: Final attempt
            ConversationStep(
                "[NO_RESPONSE]",
                "AI sends breakup message, leaves door open",
                "nurture",
            ),
        ],
        expected_outcome="moved_to_nurture",
    ),

    "non_responsive_then_response": Scenario(
        name="Non-Responsive Then Responds",
        description="Lead doesn't respond initially, then engages mid-sequence",
        profile_name="non_responsive_warm",
        lead_type="buyer",
        channel="sms",
        steps=[
            # Day 0: Follow-up
            ConversationStep(
                "",
                "AI sends follow-up",
                "initial",
            ),
            # Day 1: No response
            ConversationStep(
                "[NO_RESPONSE]",
                "AI sends value add",
                "initial",
            ),
            # Lead responds mid-sequence!
            ConversationStep(
                "Hey! Sorry been traveling. Yes still interested in South Austin",
                "AI welcomes back, cancels follow-up sequence, resumes qualifying",
                "qualifying",
                score_change="increase",
            ),
            ConversationStep(
                "Looking in the 400-500k range, need at least 3 bedrooms",
                "AI acknowledges requirements, asks about timeline",
                "qualifying",
                score_change="increase",
            ),
            ConversationStep(
                "Probably 2-3 months, my lease ends in March",
                "AI offers to schedule a call since timeline is actionable",
                "scheduling",
                score_change="increase",
            ),
        ],
        expected_outcome="re_engaged_to_scheduling",
    ),
}


# =============================================================================
# SCENARIO RUNNER
# =============================================================================

class ScenarioRunner:
    """Runs conversation scenarios and reports results."""

    def __init__(
        self,
        live_mode: bool = False,
        interactive: bool = False,
        fub_person_id: Optional[int] = None,
        dry_run: bool = True,
        verbose: bool = False,
    ):
        self.live_mode = live_mode
        self.interactive = interactive
        self.fub_person_id = fub_person_id
        self.dry_run = dry_run
        self.verbose = verbose
        self.results: List[Dict[str, Any]] = []

        # Track conversation state across turns
        self._conversation_context = None
        self._lead_profile = None
        self._conversation_history = []
        self._qualification_data = {}  # Track extracted info across turns

    def _print_separator(self, char: str = "=", width: int = 70):
        """Print a separator line."""
        print(char * width)

    def _print_header(self, scenario: Scenario, profile: Any):
        """Print scenario header with lead info."""
        self._print_separator()
        print(f"  SCENARIO: {scenario.name}")
        print(f"  {scenario.description}")
        self._print_separator("-")
        print(f"  Lead: {profile.full_name} ({profile.lead_type})")
        print(f"  Source: {profile.source}")
        print(f"  Channel: {scenario.channel.upper()}")
        print(f"  Score: {profile.score}/100 ({profile.score_label})")
        if profile.is_pre_approved:
            print(f"  Pre-approved: ${profile.pre_approval_amount:,}")
        if profile.timeline:
            print(f"  Timeline: {profile.timeline}")
        if profile.property_inquiry_description:
            print(f"  Inquiry: {profile.property_inquiry_description[:60]}...")
        self._print_separator()

    def _print_turn_header(self, turn_num: int, total: int, step: ConversationStep):
        """Print turn header."""
        print(f"\n  Turn {turn_num}/{total}:", end="")
        if step.lead_message == "[NO_RESPONSE]":
            print(" Follow-up (No Response)")
        elif step.lead_message:
            print(" Lead Reply")
        else:
            print(" First Contact (AI initiates)")

    def _print_lead_message(self, message: str, is_no_response: bool = False):
        """Print lead's message."""
        if is_no_response:
            print(f"  LEAD: [NO RESPONSE - Follow-up sequence continues]")
        elif message:
            print(f"  LEAD: \"{message}\"")
        else:
            print(f"  LEAD: (awaiting first contact)")

    def _print_context(self, profile: Any, state: str, score: int):
        """Print AI context used for this turn."""
        print(f"\n  CONTEXT:")
        print(f"    Score: {score}/100")
        print(f"    State: {state}")
        print(f"    First contact: {profile.is_first_contact}")
        print(f"    Messages sent: {profile.total_messages_sent}")
        if profile.previous_objections:
            print(f"    Previous objections: {', '.join(profile.previous_objections)}")

    def _print_ai_response(self, response: Dict[str, Any], is_live: bool):
        """Print AI response with details."""
        mode = "Claude" if is_live else "Simulated"
        response_text = response.get("ai_response", "N/A")

        # Wrap long responses
        if len(response_text) > 70:
            words = response_text.split()
            lines = []
            current_line = ""
            for word in words:
                if len(current_line) + len(word) + 1 <= 66:
                    current_line += (" " if current_line else "") + word
                else:
                    lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
            formatted = '\n    '.join(lines)
            print(f"\n  AI RESPONSE ({mode}):")
            print(f"    {formatted}")
        else:
            print(f"\n  AI RESPONSE ({mode}):")
            print(f"    \"{response_text}\"")

    def _print_detection(self, response: Dict[str, Any]):
        """Print intent/sentiment detection results."""
        intent = response.get("intent")
        sentiment = response.get("sentiment")
        extracted = response.get("extracted_info", {})

        if intent or sentiment or extracted:
            print(f"\n  DETECTED:")
            if intent:
                confidence = response.get("confidence", 0)
                print(f"    Intent: {intent} ({confidence:.2f})")
            if sentiment:
                print(f"    Sentiment: {sentiment}")
            if extracted:
                print(f"    Extracted: {json.dumps(extracted, default=str)[:60]}")

    def _print_state_change(self, prev_state: str, new_state: str, prev_score: int, new_score: int):
        """Print state and score changes."""
        state_str = f"{prev_state} -> {new_state}" if prev_state != new_state else new_state
        score_delta = new_score - prev_score
        score_str = f"{prev_score} -> {new_score}"
        if score_delta > 0:
            score_str += f" (+{score_delta})"
        elif score_delta < 0:
            score_str += f" ({score_delta})"

        print(f"\n  STATE: {state_str}")
        print(f"  SCORE: {score_str}")

    def _print_handoff(self, response: Dict[str, Any]):
        """Print handoff information."""
        if response.get("handoff"):
            reason = response.get("handoff_reason", "N/A")
            print(f"  ** HANDOFF TRIGGERED: {reason} **")

    def _print_tokens(self, response: Dict[str, Any]):
        """Print token usage if available."""
        tokens = response.get("tokens_used", 0)
        time_ms = response.get("response_time_ms", 0)
        if tokens or time_ms:
            print(f"  TOKENS: {tokens} | TIME: {time_ms/1000:.1f}s")

    def _print_verification(self, step: ConversationStep, response: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Verify expectations and print results."""
        passed = True
        failures = []

        # Check state (only if expected_state is specified)
        if step.expected_state is not None and response.get("state") != step.expected_state:
            passed = False
            failures.append(f"State: expected {step.expected_state}, got {response.get('state')}")

        # Check handoff
        if step.should_handoff and not response.get("handoff"):
            passed = False
            failures.append("Expected handoff but didn't trigger")

        # Print result
        print(f"\n  [{('PASS' if passed else 'FAIL')}] Expected: {step.expected_behavior}")
        for f in failures:
            print(f"       X {f}")

        return passed, failures

    def _wait_for_interactive(self):
        """Wait for user input in interactive mode."""
        print("\n  [Press Enter to continue, 's' to skip, 'q' to quit]")
        try:
            user_input = input("  > ").strip().lower()
            if user_input == 'q':
                raise KeyboardInterrupt()
            return user_input != 's'
        except EOFError:
            return True

    async def run_scenario(self, scenario: Scenario) -> Dict[str, Any]:
        """Run a single scenario."""
        # Get or create lead profile
        if self.fub_person_id:
            profile = await self._fetch_fub_lead_profile(self.fub_person_id)
        else:
            profile = create_synthetic_lead_profile(scenario.profile_name)

        if not profile:
            print(f"ERROR: Could not load profile for {scenario.profile_name}")
            return {"scenario": scenario.name, "passed": False, "error": "No profile"}

        self._lead_profile = profile
        self._conversation_history = []
        self._qualification_data = {}  # Reset qualification data for new scenario

        # Print header
        self._print_header(scenario, profile)

        step_results = []
        current_state = "initial"
        lead_score = profile.score
        followup_step = 0  # Track follow-up sequence position

        for i, step in enumerate(scenario.steps):
            # Check if this is a NO_RESPONSE follow-up step
            is_no_response = step.lead_message == "[NO_RESPONSE]"

            self._print_turn_header(i + 1, len(scenario.steps), step)
            self._print_lead_message(step.lead_message, is_no_response=is_no_response)

            if self.verbose:
                self._print_context(profile, current_state, lead_score)

            # Execute step
            prev_state = current_state
            prev_score = lead_score

            if self.live_mode:
                result = await self._execute_live_step(
                    step, profile, current_state, scenario.channel,
                    is_followup=is_no_response,
                    followup_step=followup_step,
                )
            else:
                result = await self._simulate_step(
                    step, current_state, lead_score,
                    is_followup=is_no_response,
                    followup_step=followup_step,
                )

            # Increment follow-up step counter if this was a no-response
            if is_no_response:
                followup_step += 1

            # Update state
            current_state = result.get("state", current_state)
            lead_score = result.get("score", lead_score)

            # Update profile for next turn
            # Don't add [NO_RESPONSE] to history - it's a marker, not a real message
            if step.lead_message and not is_no_response:
                profile.is_first_contact = False
                profile.has_received_any_messages = True
                profile.total_messages_received += 1
                self._conversation_history.append({
                    "role": "lead",
                    "content": step.lead_message,
                    "timestamp": datetime.now().isoformat(),
                })

            # Add AI response to history
            if result.get("ai_response"):
                profile.total_messages_sent += 1
                self._conversation_history.append({
                    "role": "agent",
                    "content": result.get("ai_response"),
                    "timestamp": datetime.now().isoformat(),
                })

            # Update objections if detected
            if result.get("intent") and "objection" in str(result.get("intent", "")).lower():
                profile.objection_count += 1

            # Accumulate extracted info into qualification data AND update profile
            extracted = result.get("extracted_info", {})
            if extracted:
                for key, value in extracted.items():
                    if value is not None:
                        self._qualification_data[key] = value
                        # Also update the profile so AI knows what's already collected
                        if key == "timeline" and value:
                            profile.timeline = value
                        elif key == "location" and value:
                            if not profile.preferred_neighborhoods:
                                profile.preferred_neighborhoods = []
                            profile.preferred_neighborhoods.append(value)
                        elif key == "budget" and value:
                            # Try to parse budget like "$450,000 - $550,000"
                            try:
                                import re
                                nums = re.findall(r'[\d,]+', str(value))
                                if nums:
                                    profile.price_max = int(nums[-1].replace(',', ''))
                                    if len(nums) > 1:
                                        profile.price_min = int(nums[0].replace(',', ''))
                            except:
                                pass
                        elif key in ["pre_approval", "pre_approved", "is_pre_approved"] and value is not None:
                            # Handle various formats: True/False, "yes"/"no", etc.
                            if isinstance(value, bool):
                                profile.is_pre_approved = value
                            elif isinstance(value, str):
                                profile.is_pre_approved = value.lower() in ["true", "yes", "approved"]
                            else:
                                profile.is_pre_approved = bool(value)

            # Print results
            self._print_ai_response(result, self.live_mode)

            if self.live_mode:
                self._print_detection(result)

            self._print_state_change(prev_state, current_state, prev_score, lead_score)
            self._print_handoff(result)

            if self.live_mode:
                self._print_tokens(result)

            # Verify expectations
            passed, failures = self._print_verification(step, result)

            step_results.append({
                "step": i + 1,
                "lead_message": step.lead_message,
                "ai_response": result.get("ai_response"),
                "state_before": prev_state,
                "state_after": current_state,
                "score_before": prev_score,
                "score_after": lead_score,
                "passed": passed,
                "failures": failures,
                "intent": result.get("intent"),
                "sentiment": result.get("sentiment"),
                "handoff": result.get("handoff"),
                "tokens_used": result.get("tokens_used", 0),
                "response_time_ms": result.get("response_time_ms", 0),
            })

            self._print_separator("-", 70)

            # Interactive mode
            if self.interactive and i < len(scenario.steps) - 1:
                if not self._wait_for_interactive():
                    continue

        # Summary
        all_passed = all(s["passed"] for s in step_results)
        total_tokens = sum(s.get("tokens_used", 0) for s in step_results)
        total_time = sum(s.get("response_time_ms", 0) for s in step_results)

        result = {
            "scenario": scenario.name,
            "profile": scenario.profile_name,
            "lead_type": scenario.lead_type,
            "passed": all_passed,
            "final_state": current_state,
            "final_score": lead_score,
            "expected_outcome": scenario.expected_outcome,
            "step_results": step_results,
            "total_tokens": total_tokens,
            "total_time_ms": total_time,
        }

        self._print_separator()
        if all_passed:
            print(f"  SCENARIO PASSED")
        else:
            print(f"  SCENARIO FAILED")
        print(f"  Final State: {current_state}")
        print(f"  Final Score: {lead_score}/100")
        print(f"  Expected Outcome: {scenario.expected_outcome}")
        if total_tokens:
            print(f"  Total Tokens: {total_tokens}")
        if total_time:
            print(f"  Total Time: {total_time/1000:.1f}s")
        self._print_separator()

        return result

    async def _simulate_step(
        self,
        step: ConversationStep,
        current_state: str,
        lead_score: int,
        is_followup: bool = False,
        followup_step: int = 0,
    ) -> Dict[str, Any]:
        """Simulate a conversation step (no actual API calls)."""
        # Standard responses for interactive conversations
        responses = {
            "initial": "Hey! Sarah here from SAA Homes. When are you thinking of making a move?",
            "qualifying": "Great! What's your timeline looking like?",
            "scheduling": "Perfect! Would Thursday at 3pm work for a quick call?",
            "objection_handling": "I totally understand. What made you start looking in the first place?",
            "nurture": "No problem at all! I'll check back in when you're ready. Feel free to reach out anytime.",
            "handed_off": "I'm connecting you with Sarah right now. She'll give you a call shortly!",
            "completed": "You've been unsubscribed from our messages. Reply START anytime to opt back in.",
        }

        # Follow-up sequence messages (for NO_RESPONSE steps)
        followup_responses = [
            # Step 0: Day 0 + 30 min - Value with CTA
            "Btw, I have a few times open this week if you want to chat about Austin. Would Thursday afternoon work for a quick call?",
            # Step 1: Day 1 - Qualify motivation
            "Quick question - what's driving your home search? Job change, growing family, or just ready for something new?",
            # Step 2: Day 3 - Email channel switch
            "[EMAIL] Subject: Austin Market Update\n\nHey! Wanted to share some insights on the Austin market. Prices are up 3% this quarter. Let me know if you'd like to chat!",
            # Step 3: Day 4 - Social proof
            "Just helped a buyer close on a great place in Austin last week. Happy to do the same for you when you're ready!",
            # Step 4: Day 7 - Strategic breakup
            "I'm closing your file for now since I haven't heard back - but I totally get it, timing is everything! If your situation changes, I'll be here 👋",
        ]

        target_state = step.expected_state or current_state

        # Determine response based on whether this is a follow-up sequence
        if is_followup:
            # Use follow-up response based on step number
            if followup_step < len(followup_responses):
                ai_response = followup_responses[followup_step]
            else:
                ai_response = followup_responses[-1]  # Use last message if beyond sequence
            score_change = -2  # Slight score decrease for non-response
        else:
            ai_response = responses.get(target_state, "How can I help you today?")
            # Adjust score based on step
            score_change = 0
            message_lower = step.lead_message.lower()
            if "interested" in message_lower or "yes" in message_lower:
                score_change = 10
            elif "stop" in message_lower:
                score_change = -50
            elif "not" in message_lower or "no" in message_lower:
                score_change = -5
            elif any(word in message_lower for word in ["30 days", "asap", "soon", "urgent"]):
                score_change = 15
            elif "already have" in message_lower or "have an agent" in message_lower:
                score_change = -10

        return {
            "ai_response": ai_response,
            "state": target_state,
            "score": lead_score + score_change,
            "handoff": step.should_handoff,
            "handoff_reason": "appointment_scheduled" if step.should_handoff else None,
            "intent": "no_response" if is_followup else None,
            "sentiment": "neutral",
            "confidence": 0.0,
            "tokens_used": 0,
            "response_time_ms": 0,
            "followup_step": followup_step if is_followup else None,
        }

    async def _execute_live_step(
        self,
        step: ConversationStep,
        profile: Any,
        current_state: str,
        channel: str = "sms",
        is_followup: bool = False,
        followup_step: int = 0,
    ) -> Dict[str, Any]:
        """Execute a live conversation step with real AI via OpenRouter."""
        import time
        from app.ai_agent.response_generator import AIResponseGenerator
        from app.ai_agent.followup_manager import FollowUpManager, MessageType

        try:
            start_time = time.time()

            # Initialize response generator with OpenRouter
            generator = AIResponseGenerator(
                llm_provider="openrouter",  # Use OpenRouter, not Anthropic
                personality="friendly_casual",
                agent_name="Sarah",
                brokerage_name="SAA Homes",
            )

            # Build conversation history for context
            # Use direction: "inbound"/"outbound" format that the response generator expects
            history_messages = []
            for msg in self._conversation_history:
                direction = "outbound" if msg["role"] == "agent" else "inbound"
                history_messages.append({
                    "direction": direction,
                    "content": msg["content"]
                })

            # Determine message type for follow-up sequences
            followup_message_type = None
            if is_followup:
                # Map follow-up step to message type
                followup_types = [
                    MessageType.VALUE_WITH_CTA,      # Step 0: Day 0 + 30 min
                    MessageType.QUALIFY_MOTIVATION,  # Step 1: Day 1
                    MessageType.EMAIL_MARKET_REPORT, # Step 2: Day 3
                    MessageType.SOCIAL_PROOF,        # Step 3: Day 4
                    MessageType.STRATEGIC_BREAKUP,   # Step 4: Day 7
                ]
                followup_message_type = followup_types[min(followup_step, len(followup_types) - 1)]

            # Debug: Show what context is being passed
            if self.verbose:
                print(f"\n  [DEBUG] Conversation history ({len(history_messages)} messages):")
                for i, msg in enumerate(history_messages[-4:]):  # Show last 4
                    print(f"    {i+1}. [{msg['direction']}] {msg['content'][:50]}...")
                print(f"  [DEBUG] Qualification data: {self._qualification_data}")
                if is_followup:
                    print(f"  [DEBUG] Follow-up step: {followup_step} ({followup_message_type.value if followup_message_type else 'N/A'})")

            # Build lead context dict from profile
            lead_context = {
                "first_name": profile.first_name,
                "full_name": profile.full_name,
                "lead_type": profile.lead_type,
                "source": profile.source,
                "score": profile.score,
                "score_label": profile.score_label,
                "is_first_contact": profile.is_first_contact,
                "timeline": profile.timeline,
                "is_pre_approved": profile.is_pre_approved,
                "channel": channel,
                # Add follow-up context
                "is_followup_sequence": is_followup,
                "followup_step": followup_step,
                "followup_message_type": followup_message_type.value if followup_message_type else None,
                "last_contact_date": profile.last_contact_date,
                "total_attempts": profile.total_messages_sent + (followup_step if is_followup else 0),
            }

            # For first contact (no incoming message), use a trigger message
            # For follow-up (no response), use a FOLLOWUP trigger
            if is_followup:
                incoming_msg = f"[FOLLOWUP_SEQUENCE:{followup_message_type.value if followup_message_type else 'VALUE_ADD'}]"
            elif step.lead_message:
                incoming_msg = step.lead_message
            else:
                incoming_msg = "[FIRST_CONTACT]"

            # Generate response using OpenRouter
            response = await generator.generate_response(
                incoming_message=incoming_msg,
                conversation_history=history_messages,
                lead_context=lead_context,
                current_state=current_state,
                qualification_data=self._qualification_data,  # Pass accumulated data
                lead_profile=profile,
            )

            elapsed_ms = int((time.time() - start_time) * 1000)

            if response:
                # Calculate new score based on delta
                # For follow-up with no response, score should decrease slightly
                if is_followup:
                    new_score = profile.score - 2  # Slight decrease for non-response
                else:
                    new_score = profile.score + response.lead_score_delta

                return {
                    "ai_response": response.response_text,
                    "state": response.next_state,
                    "score": new_score,
                    "handoff": response.should_handoff,
                    "handoff_reason": response.handoff_reason,
                    "intent": "no_response" if is_followup else response.detected_intent,
                    "sentiment": response.detected_sentiment,
                    "confidence": response.confidence,
                    "tokens_used": response.tokens_used,
                    "response_time_ms": elapsed_ms,
                    "extracted_info": response.extracted_info,
                    "model_used": response.model_used,
                    "followup_step": followup_step if is_followup else None,
                    "followup_message_type": followup_message_type.value if is_followup and followup_message_type else None,
                }
            else:
                return {
                    "ai_response": "[No response generated]",
                    "state": current_state,
                    "score": profile.score,
                    "handoff": False,
                    "response_time_ms": elapsed_ms,
                    "followup_step": followup_step if is_followup else None,
                }

        except Exception as e:
            import traceback
            print(f"\n  ERROR: {e}")
            if self.verbose:
                traceback.print_exc()
            return {
                "ai_response": f"[Error: {str(e)[:50]}]",
                "state": current_state,
                "score": profile.score,
                "handoff": False,
                "error": str(e),
            }

    async def _fetch_fub_lead_profile(self, person_id: int) -> Optional[Any]:
        """Fetch a real lead profile from FUB."""
        try:
            from app.database.fub_api_client import FUBApiClient
            from app.ai_agent.response_generator import LeadProfile

            api_key = os.getenv("FUB_API_KEY") or os.getenv("FOLLOWUPBOSS_API_KEY")
            if not api_key:
                print("ERROR: No FUB API key found in environment")
                return None

            client = FUBApiClient(api_key=api_key)

            # Get complete lead context (sync function, no await)
            context = client.get_complete_lead_context(person_id)
            if not context:
                print(f"ERROR: Could not fetch lead {person_id} from FUB")
                return None

            # Extract person data
            person_data = context.get("person", context)

            # Process raw FUB context into structured additional_data
            additional_data = LeadProfile.process_fub_context(context)

            # Print lead info for debugging
            print(f"  Lead: {person_data.get('firstName', '')} {person_data.get('lastName', '')}")
            print(f"  Source: {person_data.get('source', 'Unknown')}")
            print(f"  Type: {person_data.get('type', 'Unknown')}")
            print(f"  Price: ${person_data.get('price', 0):,}")
            print(f"  Messages sent: {additional_data.get('total_messages_sent', 0)}")
            print(f"  Messages received: {additional_data.get('total_messages_received', 0)}")
            print(f"  First contact: {additional_data.get('is_first_contact', True)}")
            if additional_data.get('property_inquiry_source'):
                print(f"  Inquiry source: {additional_data.get('property_inquiry_source')}")
            if additional_data.get('timeline'):
                print(f"  Timeline: {additional_data.get('timeline')}")
            if additional_data.get('is_pre_approved') is not None:
                print(f"  Pre-approved: {additional_data.get('is_pre_approved')}")

            # Convert to LeadProfile using the factory method
            profile = LeadProfile.from_fub_data(person_data, additional_data)
            return profile

        except Exception as e:
            print(f"ERROR fetching FUB lead: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def run_all_scenarios(self, filter_type: str = None, filter_channel: str = None) -> Dict[str, Any]:
        """Run all scenarios and report results."""
        self._print_separator()
        print("  CONVERSATION SCENARIO TEST SUITE")
        self._print_separator()
        print(f"  Mode: {'LIVE (Real AI via OpenRouter)' if self.live_mode else 'SIMULATION'}")
        print(f"  Interactive: {'Yes' if self.interactive else 'No'}")

        scenarios_to_run = SCENARIOS
        if filter_type:
            scenarios_to_run = {
                k: v for k, v in scenarios_to_run.items()
                if v.lead_type == filter_type
            }
            print(f"  Filter Type: {filter_type} leads only")
        if filter_channel:
            scenarios_to_run = {
                k: v for k, v in scenarios_to_run.items()
                if v.channel == filter_channel
            }
            print(f"  Filter Channel: {filter_channel.upper()} only")

        print(f"  Scenarios: {len(scenarios_to_run)}")
        self._print_separator()

        all_results = []
        for name, scenario in scenarios_to_run.items():
            try:
                result = await self.run_scenario(scenario)
                all_results.append(result)
                self.results.append(result)
            except KeyboardInterrupt:
                print("\n  Interrupted by user")
                break
            except Exception as e:
                print(f"\n  ERROR in {name}: {e}")
                all_results.append({
                    "scenario": scenario.name,
                    "passed": False,
                    "error": str(e),
                })

        # Final summary
        passed = sum(1 for r in all_results if r.get("passed"))
        failed = len(all_results) - passed
        total_tokens = sum(r.get("total_tokens", 0) for r in all_results)
        total_time = sum(r.get("total_time_ms", 0) for r in all_results)

        self._print_separator()
        print("  FINAL SUMMARY")
        self._print_separator()
        print(f"  Total Scenarios: {len(all_results)}")
        print(f"  Passed: {passed}")
        print(f"  Failed: {failed}")
        print(f"  Pass Rate: {passed/len(all_results)*100:.1f}%")

        if total_tokens:
            print(f"  Total Tokens Used: {total_tokens}")
        if total_time:
            print(f"  Total Time: {total_time/1000:.1f}s")

        if failed > 0:
            print("\n  Failed Scenarios:")
            for r in all_results:
                if not r.get("passed"):
                    print(f"    - {r['scenario']}")
                    if r.get("error"):
                        print(f"      Error: {r['error']}")

        self._print_separator()

        return {
            "total": len(all_results),
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / len(all_results) * 100 if all_results else 0,
            "total_tokens": total_tokens,
            "total_time_ms": total_time,
            "results": all_results,
        }


# =============================================================================
# CLI
# =============================================================================

def list_scenarios():
    """List all available scenarios."""
    print("\n" + "=" * 70)
    print("  AVAILABLE SCENARIOS")
    print("=" * 70)

    # Group by channel and lead type
    sms_buyers = [(k, v) for k, v in SCENARIOS.items()
                  if v.lead_type == "buyer" and v.channel == "sms" and not k.startswith("non_responsive")]
    sms_sellers = [(k, v) for k, v in SCENARIOS.items()
                   if v.lead_type == "seller" and v.channel == "sms"]
    email_scenarios = [(k, v) for k, v in SCENARIOS.items() if v.channel == "email"]
    non_responsive = [(k, v) for k, v in SCENARIOS.items() if k.startswith("non_responsive")]

    print("\n  SMS SCENARIOS - BUYERS:")
    for name, scenario in sms_buyers:
        print(f"\n    {name}")
        print(f"      {scenario.description}")
        print(f"      Profile: {scenario.profile_name} | Steps: {len(scenario.steps)}")
        print(f"      Expected: {scenario.expected_outcome}")

    print("\n  SMS SCENARIOS - SELLERS:")
    for name, scenario in sms_sellers:
        print(f"\n    {name}")
        print(f"      {scenario.description}")
        print(f"      Profile: {scenario.profile_name} | Steps: {len(scenario.steps)}")
        print(f"      Expected: {scenario.expected_outcome}")

    print("\n  EMAIL SCENARIOS:")
    for name, scenario in email_scenarios:
        print(f"\n    {name}")
        print(f"      {scenario.description}")
        print(f"      Profile: {scenario.profile_name} | Lead: {scenario.lead_type} | Steps: {len(scenario.steps)}")
        print(f"      Expected: {scenario.expected_outcome}")

    print("\n  NON-RESPONSIVE / FOLLOW-UP SEQUENCE SCENARIOS:")
    for name, scenario in non_responsive:
        print(f"\n    {name}")
        print(f"      {scenario.description}")
        print(f"      Profile: {scenario.profile_name} | Steps: {len(scenario.steps)}")
        print(f"      Expected: {scenario.expected_outcome}")

    print("\n" + "=" * 70)
    print("  USAGE:")
    print("=" * 70)
    print("""
    # List scenarios
    python -m scripts.test_conversation_scenarios --list

    # Run specific scenario (simulation mode - fast)
    python -m scripts.test_conversation_scenarios --scenario hot_buyer

    # Run with real AI (recommended for testing)
    python -m scripts.test_conversation_scenarios --scenario hot_buyer --live

    # Interactive mode - pause between turns
    python -m scripts.test_conversation_scenarios --scenario hot_buyer --live --interactive

    # Run all scenarios
    python -m scripts.test_conversation_scenarios --all --live

    # Filter by lead type
    python -m scripts.test_conversation_scenarios --all --live --type buyer

    # Test with real FUB lead (dry run - no messages sent)
    python -m scripts.test_conversation_scenarios --fub-lead 3277 --live --dry-run

    # Verbose output (show AI context)
    python -m scripts.test_conversation_scenarios --scenario hot_buyer --live --verbose
    """)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test AI agent conversation scenarios"
    )
    parser.add_argument(
        "--scenario", type=str, default=None,
        help="Run specific scenario by name"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Run all scenarios"
    )
    parser.add_argument(
        "--type", type=str, choices=["buyer", "seller"], default=None,
        help="Filter scenarios by lead type"
    )
    parser.add_argument(
        "--channel", type=str, choices=["sms", "email"], default=None,
        help="Filter scenarios by channel (sms or email)"
    )
    parser.add_argument(
        "--fub-lead", type=int, default=None,
        help="FUB Person ID to test with real lead data"
    )
    parser.add_argument(
        "--live", action="store_true",
        help="Run in live mode (actual Claude API calls)"
    )
    parser.add_argument(
        "--interactive", action="store_true",
        help="Interactive mode - pause between turns"
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Dry run - don't send actual messages (default)"
    )
    parser.add_argument(
        "--send-sms", action="store_true",
        help="Actually send SMS messages (requires confirmation)"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show verbose output including AI context"
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List all available scenarios"
    )
    parser.add_argument(
        "--output", type=str, choices=["console", "json", "markdown"],
        default="console",
        help="Output format"
    )

    args = parser.parse_args()

    if args.list or (not args.scenario and not args.all and not args.fub_lead):
        list_scenarios()
        return

    # Safety check for sending real SMS
    if args.send_sms:
        print("\n  WARNING: You've enabled --send-sms which will send REAL messages!")
        confirm = input("  Type 'yes' to confirm: ").strip().lower()
        if confirm != 'yes':
            print("  Aborted.")
            return
        dry_run = False
    else:
        dry_run = True

    runner = ScenarioRunner(
        live_mode=args.live,
        interactive=args.interactive,
        fub_person_id=args.fub_lead,
        dry_run=dry_run,
        verbose=args.verbose,
    )

    try:
        if args.all:
            results = await runner.run_all_scenarios(filter_type=args.type, filter_channel=args.channel)

            if args.output == "json":
                print(json.dumps(results, indent=2, default=str))
            elif args.output == "markdown":
                print(_generate_markdown_report(results))

        elif args.scenario:
            if args.scenario not in SCENARIOS:
                print(f"ERROR: Unknown scenario '{args.scenario}'")
                print(f"Available: {', '.join(SCENARIOS.keys())}")
                return

            result = await runner.run_scenario(SCENARIOS[args.scenario])

            if args.output == "json":
                print(json.dumps(result, indent=2, default=str))

        elif args.fub_lead:
            # Use hot_buyer scenario structure but with real FUB lead
            print(f"\n  Testing with real FUB lead: {args.fub_lead}")
            scenario = SCENARIOS["hot_buyer"]
            result = await runner.run_scenario(scenario)

    except KeyboardInterrupt:
        print("\n  Interrupted by user")


def _generate_markdown_report(results: Dict[str, Any]) -> str:
    """Generate a markdown report from results."""
    lines = [
        "# AI Conversation Test Report",
        f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"\n## Summary",
        f"\n| Metric | Value |",
        f"|--------|-------|",
        f"| Total Scenarios | {results['total']} |",
        f"| Passed | {results['passed']} |",
        f"| Failed | {results['failed']} |",
        f"| Pass Rate | {results['pass_rate']:.1f}% |",
        f"| Total Tokens | {results.get('total_tokens', 0)} |",
        f"| Total Time | {results.get('total_time_ms', 0)/1000:.1f}s |",
        f"\n## Results",
        f"\n| Scenario | Type | Result | Final State | Score |",
        f"|----------|------|--------|-------------|-------|",
    ]

    for r in results.get("results", []):
        status = "PASS" if r.get("passed") else "FAIL"
        lead_type = r.get("lead_type", "?")
        final_state = r.get("final_state", "?")
        final_score = r.get("final_score", 0)
        lines.append(f"| {r['scenario']} | {lead_type} | {status} | {final_state} | {final_score} |")

    return "\n".join(lines)


if __name__ == "__main__":
    asyncio.run(main())
