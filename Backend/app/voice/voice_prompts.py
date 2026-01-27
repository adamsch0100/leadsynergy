"""
Voice-specific prompts for AI phone conversations.

These prompts are optimized for spoken conversation:
- Short, concise responses (1-2 sentences max)
- Natural speech patterns
- Clear pauses for turn-taking
"""

from typing import Optional, Dict, Any


VOICE_SYSTEM_PROMPT = """You are {agent_name}, a friendly real estate assistant from {brokerage_name} on a live phone call.

CRITICAL VOICE CALL GUIDELINES:
- Keep ALL responses to 1-2 sentences maximum
- Speak naturally and conversationally
- Pause after asking questions - let them respond
- NEVER monologue or give long explanations
- Use contractions (I'm, you're, we'll, etc.)
- If you don't understand, ask them to repeat
- Match their energy level and pace

CONVERSATION FLOW:
1. Greet warmly but briefly
2. Ask ONE question at a time
3. Listen for their response
4. Respond to what they said
5. Guide toward scheduling if appropriate

LEAD INFORMATION:
- Name: {lead_name}
- Type: {lead_type}
- Timeline: {timeline}
- Preferred Areas: {areas}
- Previous Context: {previous_context}

CALL OBJECTIVE: {objective}

THINGS TO AVOID:
- Long explanations or market data
- Multiple questions in one response
- Sounding robotic or scripted
- Saying "As an AI" or similar
- Awkward transitions

Remember: This is a PHONE CALL. Be brief, be human, be helpful."""


VOICE_FIRST_MESSAGE_TEMPLATES = {
    "new_lead": [
        "Hey {first_name}, this is {agent_name}! Thanks for picking up. I saw you're looking at homes in {area} - exciting stuff! What's got you interested in that area?",
        "Hi {first_name}! {agent_name} here. Got a quick minute? I wanted to chat about your home search.",
        "{first_name}, hey! It's {agent_name}. Caught you at a good time?",
    ],
    "follow_up": [
        "Hey {first_name}, {agent_name} again! Just wanted to check in - any updates on your home search?",
        "Hi {first_name}! Quick follow-up from our earlier conversation. How's everything going?",
    ],
    "appointment_reminder": [
        "Hey {first_name}! {agent_name} here. Just confirming we're still on for {appointment_time}?",
    ],
    "re_engagement": [
        "Hey {first_name}, it's {agent_name}! Been a little while - just wanted to see if you're still thinking about real estate?",
    ],
}


VOICE_RESPONSE_GUIDELINES = """
When generating a voice response, follow these rules:

1. LENGTH: Maximum 2 sentences. Shorter is better.

2. STRUCTURE:
   - Acknowledge what they said (briefly)
   - Add value or ask a follow-up question

3. EXAMPLES OF GOOD RESPONSES:
   - "Oh nice, 3 bedrooms is perfect for that area. Are you pre-approved yet?"
   - "Totally get it. What's your timeline looking like?"
   - "Got it. Let's find a time to look at some places - how's Thursday afternoon?"

4. EXAMPLES OF BAD RESPONSES (TOO LONG):
   - "That's great to hear! The real estate market in that area has been really active lately with inventory levels rising and prices stabilizing. There are several neighborhoods that might work well for a family of your size. Have you considered..."

5. IF THEY'RE READY TO SCHEDULE:
   - "Perfect! How does [day] at [time] work?"
   - Confirm the details clearly
   - Keep it simple

6. IF THEY SEEM BUSY:
   - "No worries, sounds like you're busy. When's a better time to chat?"
   - Respect their time

7. IF THEY'RE NOT INTERESTED:
   - "Totally understand! I'll let you go. Feel free to reach out if anything changes."
   - End gracefully

8. NATURAL FILLER WORDS (use sparingly):
   - "So...", "Yeah...", "Oh nice...", "Got it..."
   - Don't overuse, but they add naturalness
"""


def get_voice_system_prompt(
    agent_name: str = "Sarah",
    brokerage_name: str = "our team",
    lead_name: str = "there",
    lead_type: str = "buyer",
    timeline: str = "unknown",
    areas: str = "your area",
    previous_context: str = "First call",
    objective: str = "qualify and schedule",
) -> str:
    """
    Generate a voice-optimized system prompt.

    Args:
        agent_name: Name the AI should use
        brokerage_name: Name of the brokerage/team
        lead_name: Lead's name
        lead_type: buyer, seller, or both
        timeline: When they want to buy/sell
        areas: Preferred areas/neighborhoods
        previous_context: Summary of previous interactions
        objective: Goal of this call

    Returns:
        Formatted system prompt for voice AI
    """
    return VOICE_SYSTEM_PROMPT.format(
        agent_name=agent_name,
        brokerage_name=brokerage_name,
        lead_name=lead_name,
        lead_type=lead_type,
        timeline=timeline or "unknown",
        areas=areas or "your area",
        previous_context=previous_context or "First call",
        objective=objective,
    )


def get_first_message(
    message_type: str,
    first_name: str,
    agent_name: str = "Sarah",
    area: str = "the area",
    appointment_time: str = None,
) -> str:
    """
    Get an appropriate first message for the call.

    Args:
        message_type: Type of call (new_lead, follow_up, etc.)
        first_name: Lead's first name
        agent_name: Agent's name
        area: Area of interest
        appointment_time: If reminding about appointment

    Returns:
        First message string
    """
    import random

    templates = VOICE_FIRST_MESSAGE_TEMPLATES.get(
        message_type,
        VOICE_FIRST_MESSAGE_TEMPLATES["new_lead"]
    )

    template = random.choice(templates)

    return template.format(
        first_name=first_name,
        agent_name=agent_name,
        area=area,
        appointment_time=appointment_time or "our meeting",
    )


def build_voice_context(
    lead_profile: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[list] = None,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    Build context dictionary for voice prompt generation.

    Args:
        lead_profile: Lead profile data
        conversation_history: Previous messages in this call
        settings: AI agent settings

    Returns:
        Dictionary of context values for prompt formatting
    """
    context = {
        "agent_name": "Sarah",
        "brokerage_name": "our team",
        "lead_name": "there",
        "lead_type": "buyer",
        "timeline": "unknown",
        "areas": "your area",
        "previous_context": "First call",
        "objective": "qualify their needs and schedule an appointment",
    }

    if settings:
        context["agent_name"] = settings.get("agent_name", "Sarah")
        context["brokerage_name"] = settings.get("brokerage_name", "our team")

    if lead_profile:
        context["lead_name"] = lead_profile.get("first_name", "there")
        context["lead_type"] = lead_profile.get("lead_type", "buyer")
        context["timeline"] = lead_profile.get("timeline", "unknown")

        # Build areas string
        areas = []
        if lead_profile.get("preferred_cities"):
            areas.extend(lead_profile["preferred_cities"])
        if lead_profile.get("preferred_neighborhoods"):
            areas.extend(lead_profile["preferred_neighborhoods"])
        if areas:
            context["areas"] = ", ".join(areas[:3])  # Limit to 3 areas

        # Build previous context
        if lead_profile.get("last_interaction"):
            context["previous_context"] = f"Last spoke {lead_profile['last_interaction']}"

        # Determine objective based on lead state
        if lead_profile.get("is_hot_lead"):
            context["objective"] = "schedule a showing or consultation"
        elif lead_profile.get("qualification_score", 0) > 60:
            context["objective"] = "confirm interest and schedule appointment"
        else:
            context["objective"] = "qualify their timeline and motivation"

    # Add conversation summary if available
    if conversation_history and len(conversation_history) > 0:
        recent = conversation_history[-3:]  # Last 3 exchanges
        summary = "; ".join([
            f"{msg['role']}: {msg['content'][:50]}..."
            for msg in recent
        ])
        context["previous_context"] = f"In this call: {summary}"

    return context
