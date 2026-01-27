"""
Lead Communication Simulation - 3 Scenarios

This script simulates what happens when a new lead comes in under three conditions:
1. SCENARIO A: Lead responds immediately (within hours)
2. SCENARIO B: Lead responds after 3-4 weeks (delayed response)
3. SCENARIO C: Lead never responds

Run with: python scripts/simulate_lead_scenarios.py
"""

from datetime import datetime, timedelta

# ============================================================================
# LEAD PROFILE (Same for all scenarios)
# ============================================================================
LEAD = {
    "name": "Sarah Johnson",
    "source": "Top Agents Ranked",
    "type": "BUYER",
    "location": "Sacramento, CA",
    "timeline": "3-6 months",
    "phone": "(916) 555-1234",
    "email": "sarah.johnson@email.com",
    "fub_person_id": 9999,
}

AGENT = {
    "name": "Adam",
    "phone": "(916) 555-0000",
    "brokerage": "Schwartz and Associates",
}

def print_header(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_message(time_label: str, channel: str, direction: str, content: str, note: str = ""):
    arrow = "-->" if direction == "outbound" else "<--"
    emoji = {"sms": "SMS", "email": "EMAIL", "call": "CALL", "task": "TASK"}
    print(f"\n  [{time_label}] {emoji.get(channel, channel)} {arrow}")
    print(f"  {content[:200]}{'...' if len(content) > 200 else ''}")
    if note:
        print(f"  ** {note} **")

def print_system_action(action: str):
    print(f"\n  [SYSTEM] {action}")

# ============================================================================
# SCENARIO A: Lead Responds Immediately
# ============================================================================
def scenario_immediate_response():
    print_header("SCENARIO A: Lead Responds Immediately")
    print(f"\n  Lead: {LEAD['name']} | Source: {LEAD['source']} | Type: {LEAD['type']}")
    print(f"  Location: {LEAD['location']} | Timeline: {LEAD['timeline']}")

    # Day 0, 0 min - Lead comes in
    print("\n" + "-" * 40)
    print("  DAY 0 - Lead Arrives")
    print("-" * 40)

    print_message("0 min", "sms", "outbound",
        f"Hey Sarah! {AGENT['name']} here from {AGENT['brokerage']}. Top Agents Ranked connected us - I specialize in Sacramento! What neighborhoods are catching your eye?")

    print_message("2 min", "email", "outbound",
        f"Subject: Nice to meet you, Sarah!\n\nHey Sarah! I just shot you a text too! Top Agents Ranked connected us because I specialize in Sacramento...")

    # Lead responds!
    print("\n  *** LEAD RESPONDS ***")

    print_message("45 min", "sms", "inbound",
        "Hi Adam! Yes I'm looking in the Natomas area. We need at least 4 bedrooms for the kids.")

    print_system_action("cancel_lead_sequences() called - ALL pending follow-ups CANCELLED")
    print_system_action("AI brain takes over conversation")

    print_message("46 min", "sms", "outbound",
        "Great choice - Natomas has awesome schools! 4 bedrooms, got it. Are you pre-approved yet, or want me to connect you with a great lender?")

    print_message("52 min", "sms", "inbound",
        "We're pre-approved for $650k through Wells Fargo")

    print_message("53 min", "sms", "outbound",
        "Perfect! $650k gets you a lot in Natomas. I have a few listings that just hit - want me to send them over? Or we could schedule a tour this weekend?")

    # Lead shows excitement - HOT LEAD DETECTION
    print("\n  *** HOT LEAD DETECTED (AI Scoring) ***")

    print_message("1 hr", "sms", "inbound",
        "Yes! We're really excited about this. My husband and I both love the area. Let's do this!")

    print_system_action("AI scored message: 85/100 - HOT LEAD")
    print_system_action("Signals detected: 'excited', 'husband agrees', 'let's do this'")
    print_system_action("Handoff triggered - NOT waiting for exact 'schedule showing' keywords")
    print_system_action("Creating FUB task for agent...")

    print_message("1 hr", "task", "outbound",
        "TASK CREATED: HOT LEAD - Ready to act!\n"
        "Due: 2 hours\n"
        "Lead said: 'We're really excited... Let's do this!'\n"
        "AI Score: 85/100 (hot_lead)\n"
        "ACTION REQUIRED: Call Sarah immediately!")

    print_message("1 hr", "sms", "outbound",
        "This is exciting - sounds like you're ready to take the next step! Let me get Adam involved so we can make this happen. He'll reach out shortly!")

    print_system_action("Conversation state -> HANDED_OFF")
    print_system_action("Human agent takes over from here")

    print("\n" + "-" * 40)
    print("  RESULT: Hot lead detected by AI (not just keywords), agent notified")
    print("-" * 40)


# ============================================================================
# SCENARIO B: Lead Responds After 3-4 Weeks
# ============================================================================
def scenario_delayed_response():
    print_header("SCENARIO B: Lead Responds After 3-4 Weeks")
    print(f"\n  Lead: {LEAD['name']} | Source: {LEAD['source']} | Type: {LEAD['type']}")

    # Day 0 - Initial outreach
    print("\n" + "-" * 40)
    print("  DAY 0 - Lead Arrives (No Response)")
    print("-" * 40)

    print_message("0 min", "sms", "outbound",
        f"Hey Sarah! {AGENT['name']} here. Top Agents Ranked connected us - I specialize in Sacramento! What neighborhoods are catching your eye?")
    print_message("2 min", "email", "outbound", "Subject: Nice to meet you, Sarah!...")
    print_message("30 min", "sms", "outbound", "Sarah, I've got some great listings in your price range. Want me to send a few over?")

    print("\n  (No response...)")

    # Day 1-7 sequence runs
    print("\n" + "-" * 40)
    print("  DAYS 1-7 - 7-Day Intensive Sequence Runs")
    print("-" * 40)

    messages = [
        ("Day 1 AM", "sms", "What's your ideal move-in timeline? Just trying to find the perfect fit!"),
        ("Day 1 PM", "email", "Subject: Sacramento Market Update - prices holding steady..."),
        ("Day 2", "sms", "Just saw a 4BR in Natomas hit the market under $600k - thought of you!"),
        ("Day 3", "email", "Subject: Quick market report for Sacramento buyers..."),
        ("Day 4", "sms", "Sarah, helped a family close on their dream home last week. Happy to do the same when you're ready!"),
        ("Day 5 AM", "email", "Subject: How I helped a family just like yours..."),
        ("Day 5 PM", "sms", "No pressure at all - just here when you need me!"),
        ("Day 6", "sms", "Anything I can help with? Happy to answer questions about the process!"),
        ("Day 7 AM", "email", "Subject: Sarah, one last thing... (door always open)"),
        ("Day 7 PM", "sms", "Sarah - closing your file for now but I'm always just a text away. Best of luck!"),
    ]

    for time, channel, content in messages:
        print(f"\n  [{time}] {channel.upper()} --> {content[:60]}...")

    print("\n  (Still no response - moving to monthly nurture...)")

    # Monthly nurture
    print("\n" + "-" * 40)
    print("  WEEKS 2-4 - Monthly Nurture Mode")
    print("-" * 40)

    print_message("Week 2", "sms", "outbound", "Sarah, hope you're doing well! Sacramento market is still favorable for buyers. Here if you need anything!")
    print_message("Week 3", "email", "outbound", "Subject: January Market Update - Sacramento inventory up 12%...")

    # LEAD RESPONDS after 3.5 weeks!
    print("\n  *** LEAD FINALLY RESPONDS (Week 3.5) ***")

    print_message("Week 3.5", "sms", "inbound",
        "Hi Adam, sorry for the late reply! We've been dealing with some family stuff. We're ready to start looking now though!")

    print_system_action("cancel_lead_sequences() - Nurture sequence CANCELLED")
    print_system_action("Smart re-engagement activated")
    print_system_action("Conversation context loaded: RESUME_GENERAL trigger")
    print_system_action("AI knows: No qualification questions answered yet, lead went silent during initial outreach")

    print_message("Week 3.5", "sms", "outbound",
        "Sarah! No worries at all - life happens. Great to hear from you! You mentioned Sacramento earlier - are you still looking in that area? And what's your timeline looking like now?")

    print_system_action("AI resumes qualification flow with context")

    print_message("Week 3.5", "sms", "inbound",
        "Yes still Sacramento, Natomas ideally. We want to be moved by summer for the kids' school.")

    print_message("Week 3.5", "sms", "outbound",
        "Summer timeline - that's perfect! Gives us a few months to find the right place. Budget-wise, are you pre-approved yet?")

    print("\n" + "-" * 40)
    print("  RESULT: Lead re-engaged, qualification continues, eventually converts")
    print("-" * 40)


# ============================================================================
# SCENARIO C: Lead Never Responds
# ============================================================================
def scenario_no_response():
    print_header("SCENARIO C: Lead Never Responds")
    print(f"\n  Lead: {LEAD['name']} | Source: {LEAD['source']} | Type: {LEAD['type']}")

    # Day 0-7: Intensive sequence
    print("\n" + "-" * 40)
    print("  DAYS 0-7 - 7-Day Intensive Sequence")
    print("-" * 40)

    sequence = [
        ("Day 0, 0min", "SMS", "Initial outreach with source reference"),
        ("Day 0, 2min", "EMAIL", "Welcome email with full intro"),
        ("Day 0, 30min", "SMS", "Value + appointment CTA"),
        ("Day 1 AM", "SMS", "Qualify motivation question"),
        ("Day 1 PM", "EMAIL", "Market insights + time slots"),
        ("Day 2", "SMS", "Property listing mention"),
        ("Day 3", "EMAIL", "Market report + meeting offer"),
        ("Day 4", "SMS", "Social proof / success story"),
        ("Day 5 AM", "EMAIL", "Detailed success story"),
        ("Day 5 PM", "SMS", "Soft no-pressure check-in"),
        ("Day 6", "SMS", "Helpful offer - any questions?"),
        ("Day 7 AM", "EMAIL", "Warm close, door open"),
        ("Day 7 PM", "SMS", "Strategic break-up message"),
    ]

    for time, channel, desc in sequence:
        status = "SENT"
        print(f"  [{time}] {channel:5} - {desc} [{status}]")

    print("\n  Total: 7 SMS + 5 Email + 0 responses")
    print_system_action("7-day intensive complete. Moving to 12-month nurture...")

    # 12-Month Nurture (enhanced)
    print("\n" + "-" * 40)
    print("  MONTHS 1-12 - Long-Term Value Nurture")
    print("-" * 40)
    print("\n  Philosophy: Every message provides VALUE - never just 'checking in'")

    nurture = [
        ("Month 1", "EMAIL", "market_update", "Sacramento Market Update - What's Changed"),
        ("Month 1.5", "SMS", "new_listing_alert", "Just saw a 4BR in Natomas that made me think of you..."),
        ("Month 2", "EMAIL", "success_story", "How I helped a family find their dream home..."),
        ("Month 2.5", "SMS", "gentle_followup", "Hope you're doing well! Still here if you need me."),
        ("Month 3", "EMAIL", "requalify_check", "Quick check-in - has anything changed?"),
        ("Month 4", "SMS", "market_opportunity", "Seeing interesting movement in Sacramento..."),
        ("Month 4.5", "EMAIL", "neighborhood_spotlight", "Why Natomas is getting attention right now"),
        ("Month 5", "SMS", "new_listing_alert", "New listing alert - something just came up..."),
        ("Month 6", "SMS", "requalify_check", "It's been a few months - still looking in Sacramento?"),
        ("Month 7", "EMAIL", "market_update", "Mid-year market update for Sacramento"),
        ("Month 8", "SMS", "seasonal_content", "Fall market tip: Less competition right now..."),
        ("Month 9", "EMAIL", "success_story", "Just helped another family close in Natomas!"),
        ("Month 10", "SMS", "value_add", "Quick tip for Sacramento buyers..."),
        ("Month 11", "EMAIL", "market_opportunity", "Year-end could be great timing..."),
        ("Month 12", "EMAIL", "anniversary_checkin", "It's been a year since we first connected!"),
    ]

    for time, channel, msg_type, desc in nurture:
        print(f"  [{time:10}] {channel:5} | {msg_type:20} | {desc[:40]}...")

    # After 12 months
    print("\n" + "-" * 40)
    print("  YEAR 2+ - Quarterly Touchpoints")
    print("-" * 40)

    print_system_action("Lead moves to annual/quarterly cadence")
    print_system_action("Quarterly: market_update, requalify_check, success_story, anniversary")
    print_system_action("If they EVER respond, system wakes up and AI takes over!")

    print("\n  TOTAL OUTREACH OVER 12 MONTHS:")
    print("  - 15+ SMS messages")
    print("  - 12+ Emails")
    print("  - Varied content (market updates, listings, success stories)")
    print("  - 2 re-qualification checks (Month 3 and Month 6)")
    print("  - 0 Responses")
    print("  - 0 Cost to agent (fully automated)")

    print("\n" + "-" * 40)
    print("  RESULT: Lead nurtured hands-off for 12+ months with VALUE every time.")
    print("  If they ever respond, system immediately wakes up and AI takes over!")
    print("-" * 40)


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    print("\n")
    print("=" * 80)
    print("  LEADSYNERGY AI AGENT - LEAD COMMUNICATION SIMULATION")
    print("  Showing exactly what happens when a new lead comes in")
    print("=" * 80)

    scenario_immediate_response()
    input("\n  Press Enter for Scenario B...")

    scenario_delayed_response()
    input("\n  Press Enter for Scenario C...")

    scenario_no_response()

    # Summary
    print("\n")
    print("=" * 80)
    print("  SUMMARY - AUTONOMOUS AI AGENT CAPABILITIES")
    print("=" * 80)
    print("""
  WHAT THE SYSTEM DOES AUTOMATICALLY:

  1. INSTANT OUTREACH (Day 0)
     - AI-generated SMS + Email within seconds
     - Personalized based on source, location, timeline
     - References how they were connected

  2. 7-DAY INTENSIVE FOLLOW-UP
     - 13 touches (7 SMS + 5 Email)
     - AI-generated, context-aware messages
     - Strategic break-up message on Day 7 (highest response rate!)

  3. SMART CANCELLATION
     - Lead responds via SMS -> Cancel all pending messages
     - Lead responds via Email -> Cancel all pending messages
     - Lead answers phone call -> Cancel all pending messages

  4. INTELLIGENT HOT LEAD DETECTION
     - NOT just looking for "schedule showing" keywords!
     - AI scores every message for buying readiness (0-100)
     - Detects excitement, urgency, spouse agreement, commitment signals
     - 70+: HOT LEAD - immediate handoff
     - 50-69: HIGH INTENT - handoff
     - <50: Keep nurturing

  5. AI CONVERSATION BRAIN
     - Takes over when lead responds
     - Qualifies: timeline, budget, location, pre-approval
     - Smart re-engagement: picks up where conversation left off

  6. HANDOFF TO HUMAN
     - Creates FUB task for agent (2hr deadline)
     - Adds note with context and AI score
     - Sends acknowledgment to lead

  7. 12-MONTH VALUE NURTURE (if no response)
     - Every message provides VALUE - never just "checking in"
     - Varied content: market updates, listings, success stories
     - Re-qualification checks at Month 3 and Month 6
     - Neighborhood spotlights, seasonal tips, rate alerts
     - Anniversary check-in at Month 12

  8. YEAR 2+ QUARTERLY NURTURE
     - Quarterly touchpoints indefinitely
     - Market updates, success stories, re-qualification
     - If they EVER respond, AI wakes up immediately

  THE RESULT: Agent only gets involved when lead is READY TO ACT.
  Everything else is handled 24/7 by the AI - for MONTHS or YEARS.
""")
