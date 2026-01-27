"""
AI-Powered Initial Outreach Generator

Generates intelligent, personalized initial contact messages (SMS + Email) for new leads
using full context from FUB including:
- Lead source (MyAgentFinder, Zillow, Redfin, etc.)
- Location interest (city, zip, neighborhood)
- Timeline (immediate, 6-12 months, just browsing)
- Financing status (pre-approved, not applied, etc.)
- Price range
- Property type interest

This replaces templated welcome messages with AI-generated, context-aware outreach
that feels personal and relevant to each lead's specific situation.
"""

import logging
import os
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


# Source name mapping - FUB source names to friendly display names
SOURCE_NAME_MAP = {
    # Top Agents Ranked / Referral Exchange
    "ReferralExchange": "Top Agents Ranked",
    "referralexchange": "Top Agents Ranked",
    "Referral Exchange": "Top Agents Ranked",
    "referral exchange": "Top Agents Ranked",
    "TopAgentsRanked": "Top Agents Ranked",
    "Top Agents Ranked": "Top Agents Ranked",
    # MyAgentFinder
    "MyAgentFinder.com": "MyAgentFinder",
    "myagentfinder": "MyAgentFinder",
    "MyAgentFinder": "MyAgentFinder",
    "myagentfinder.com": "MyAgentFinder",
    # Add more mappings as needed
}


@dataclass
class LeadContext:
    """Rich context about a new lead for personalized outreach."""
    # Identity
    first_name: str
    last_name: str = ""
    email: str = ""
    phone: str = ""
    fub_person_id: int = 0

    # Source & Attribution
    source: str = ""  # MyAgentFinder, Zillow, Redfin, Facebook, etc.
    source_url: str = ""

    # Location Interest
    city: str = ""
    state: str = ""
    zip_code: str = ""
    neighborhoods: list = None

    # Property Interest
    property_type: str = ""  # Single Family, Condo, Townhouse, etc.
    price_min: int = 0
    price_max: int = 0
    beds: int = 0
    baths: float = 0

    # Timeline & Motivation
    timeline: str = ""  # Immediate, 1-3 months, 6-12 months, Just Browsing
    financing_status: str = ""  # Pre-approved, Not Applied, Working on it
    buyer_type: str = ""  # First-time, Move-up, Investor, Relocating

    # Lead Type (derived from tags)
    lead_type: str = ""  # "buyer", "seller", "both", or ""

    # Tags from FUB
    tags: list = None

    def __post_init__(self):
        if self.neighborhoods is None:
            self.neighborhoods = []
        if self.tags is None:
            self.tags = []

    def get_friendly_source(self) -> str:
        """Get the friendly display name for the source."""
        if not self.source:
            return ""
        # Check mapping (case-insensitive)
        for key, value in SOURCE_NAME_MAP.items():
            if key.lower() == self.source.lower():
                return value
        return self.source

    @classmethod
    def from_fub_data(cls, person_data: Dict[str, Any], events: list = None) -> 'LeadContext':
        """Build LeadContext from FUB person data and events."""
        # Extract basic info
        first_name = person_data.get('firstName', 'there')
        last_name = person_data.get('lastName', '')

        emails = person_data.get('emails', [])
        email = emails[0].get('value', '') if emails else ''

        phones = person_data.get('phones', [])
        phone = phones[0].get('value', '') if phones else ''

        # Extract location from addresses or events
        city = ''
        state = ''
        zip_code = ''
        neighborhoods = []

        addresses = person_data.get('addresses', [])
        if addresses:
            addr = addresses[0]
            city = addr.get('city', '')
            state = addr.get('state', '')
            zip_code = addr.get('code', '')  # FUB uses 'code' for zip

        # Check cities field (FUB stores location interest here)
        if person_data.get('cities'):
            cities_str = person_data['cities']
            if isinstance(cities_str, str):
                neighborhoods = [c.strip() for c in cities_str.split(',')]
                if neighborhoods and not city:
                    city = neighborhoods[0]

        # Extract price range
        price_min = person_data.get('priceMin', 0) or 0
        price_max = person_data.get('priceMax', 0) or 0

        # Extract property interest
        property_type = person_data.get('propertyType', '')

        # Extract timeline and financing from events/notes
        timeline = ''
        financing_status = ''

        if events:
            for event in events:
                desc = event.get('description', '')
                # Parse common patterns like "Time Frame: 6 - 12 Months"
                if 'Time Frame:' in desc:
                    timeline = desc.split('Time Frame:')[1].split('|')[0].strip()
                if 'Financing:' in desc:
                    financing_status = desc.split('Financing:')[1].split('|')[0].strip()
                # Also check for zip code in event description
                if 'Primary Zip:' in desc and not zip_code:
                    zip_code = desc.split('Primary Zip:')[1].split('|')[0].strip()

        # Extract tags
        tags = person_data.get('tags', [])

        # Determine lead type (buyer, seller, both) from tags
        tag_lower = [t.lower() for t in tags]
        is_buyer = any('buyer' in t for t in tag_lower)
        is_seller = any('seller' in t for t in tag_lower)

        if is_buyer and is_seller:
            lead_type = 'both'
        elif is_seller:
            lead_type = 'seller'
        elif is_buyer:
            lead_type = 'buyer'
        else:
            lead_type = ''

        # Also check custom field 'type' for seller indication
        if person_data.get('type', '').lower() == 'seller' and not is_seller:
            if is_buyer:
                lead_type = 'both'
            else:
                lead_type = 'seller'

        # Determine buyer type from tags (first-time, investor, etc.)
        buyer_type = ''
        if any('first' in t and 'buyer' in t for t in tag_lower):
            buyer_type = 'First-time'
        elif any('investor' in t for t in tag_lower):
            buyer_type = 'Investor'
        elif any('relocat' in t for t in tag_lower):
            buyer_type = 'Relocating'

        return cls(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            fub_person_id=person_data.get('id', 0),
            source=person_data.get('source', ''),
            source_url=person_data.get('sourceUrl', ''),
            city=city,
            state=state,
            zip_code=zip_code,
            neighborhoods=neighborhoods,
            property_type=property_type,
            price_min=price_min,
            price_max=price_max,
            timeline=timeline,
            financing_status=financing_status,
            buyer_type=buyer_type,
            lead_type=lead_type,
            tags=tags,
        )

    def get_location_str(self) -> str:
        """Get a friendly location string."""
        if self.city and self.state:
            return f"{self.city}, {self.state}"
        if self.city:
            return self.city
        if self.zip_code:
            return f"the {self.zip_code} area"
        if self.neighborhoods:
            return self.neighborhoods[0]
        return "your area"

    def get_price_str(self) -> str:
        """Get a friendly price range string."""
        if self.price_min and self.price_max:
            return f"${self.price_min:,} - ${self.price_max:,}"
        if self.price_max:
            return f"around ${self.price_max:,}"
        if self.price_min:
            return f"${self.price_min:,}+"
        return ""

    def get_timeline_str(self) -> str:
        """Get a friendly timeline string."""
        if not self.timeline:
            return ""
        tl = self.timeline.lower()
        if 'immediate' in tl or 'asap' in tl or '0-3' in tl or '1-3' in tl:
            return "looking to move soon"
        if '3-6' in tl or '6' in tl:
            return "planning ahead"
        if '12' in tl or 'year' in tl:
            return "exploring options for down the road"
        if 'brows' in tl or 'just' in tl:
            return "just getting a feel for what's out there"
        return self.timeline


@dataclass
class InitialOutreach:
    """Generated initial outreach messages."""
    sms_message: str
    email_subject: str
    email_body: str  # HTML
    email_text: str  # Plain text fallback
    context_used: Dict[str, Any]  # What context was used
    model_used: str = ""
    tokens_used: int = 0


class InitialOutreachGenerator:
    """
    AI-powered generator for initial lead outreach.

    Uses Claude to craft personalized SMS and email messages based on
    all available context about the lead.
    """

    # System prompt for generating initial outreach
    SYSTEM_PROMPT = """You are a friendly, professional real estate agent assistant. Your job is to craft the perfect initial outreach to a brand new lead.

CRITICAL RULES:
1. Be warm, conversational, and human - NOT salesy or pushy
2. Reference specific details about the lead (location, timeline, price range if known) to show you paid attention
3. Keep SMS under 160 characters if possible, max 300 characters
4. Match the urgency to their timeline (immediate = ready to help now, 6-12 months = no pressure)
5. NEVER use generic phrases like "I saw your inquiry" - be specific about WHERE they came from
6. Don't oversell or make promises - just start a friendly conversation
7. Use the agent's actual name, not "your agent" or similar
8. If they inquired about a SPECIFIC PROPERTY, mention it by address!
9. DO NOT ASK about buyer/seller status if Lead Type is already provided - we already know!

LEAD TYPE RULES (critical - pay attention to Lead Type field!):
- If Lead Type is "BUYER only": Focus on home search, listings, neighborhoods, market conditions for buyers
- If Lead Type is "SELLER only": Focus on home valuation, market timing, listing strategy, comparable sales
- If Lead Type is "BUYER AND SELLER": Acknowledge BOTH needs! They're making a move. Focus on:
  * Coordinating the sale of their current home with purchasing a new one
  * Understanding their timeline for both transactions
  * "Whether you sell first or buy first - I'll help coordinate the whole thing"
  * DO NOT ask "are you looking to buy or sell?" - we already know they're doing BOTH!

EMAIL REQUIRED STRUCTURE (you MUST include ALL of these):
1. GREETING: "Hey [Name]!" or "Hi [Name]!"
2. TEXT ACKNOWLEDGMENT: Brief mention you also sent a text (1 sentence)
3. CONNECTION INTRO: Explain how you were matched/connected (1-2 sentences)
4. BRIEF SELF-INTRO: Who you are (1 sentence)
5. VALUE OFFER: Something useful you can provide them (1-2 sentences)
6. CALL TO ACTION: <strong>Clear CTA telling them what to do</strong>
7. SIGN-OFF: "Looking forward to connecting!" or similar + Agent name
8. PS LINE: <em>P.S. Second soft CTA or personal touch</em>

EMAIL-SPECIFIC RULES:
- The email is an INTRODUCTION - first time they're hearing from you
- IMPORTANT: We ARE also sending a text message at the same time! Acknowledge this:
  * "I just shot you a quick text too, but wanted to send more details here..."
  * "You might see my text come through as well..."
- MUST explain the connection: HOW you were matched (e.g., "Top Agents Ranked connected us...", "MyAgentFinder matched us because...")
- MUST briefly introduce yourself: who you are, your role
- MUST OFFER VALUE UPFRONT:
  * For BUYERS: Offer curated listings, neighborhood guides, off-market properties
  * For SELLERS: Offer free home valuation, market analysis, comparable sales data
  * For BOTH: Offer to coordinate both transactions, timeline planning
- MUST end with a CLEAR, EXPLICIT CALL TO ACTION in <strong> tags:
  * "Just hit reply and tell me [specific thing] - I'll [specific result]!"
- Add a PS line in <em> tags at the end - most-read part!
- Keep body SHORT - 4-6 paragraphs max
- Subject line should feel personal and specific, not automated
- Use proper HTML: <p> tags for paragraphs, <strong> for CTA, <em> for PS

SOURCE-SPECIFIC TONE:
- Top Agents Ranked/ReferralExchange: "They connected us because..." (emphasize the match)
- MyAgentFinder/referral sites: "They connected us because..." (emphasize the match)
- Zillow/Redfin/Realtor.com: Reference the property/area they were looking at
- Facebook/social: More casual, friendly tone
- Direct/website: "I saw you were exploring..."

SMS RULES:
- Super casual and brief - email handles the full intro
- End with a simple question they can easily answer
- Under 160 chars ideal, max 300
- Can mention you're also sending an email with more info
- DO NOT ask buyer/seller if Lead Type is known!

TONE GUIDE by timeline:
- Immediate/ASAP: Enthusiastic, "Let's find you something this weekend!"
- 1-3 months: Helpful, "Let me send you what's hitting the market"
- 3-6 months: Supportive, "Perfect time to start exploring"
- 6-12 months: Very relaxed, "No rush - I'll be a resource when you're ready"
- Just browsing: Zero pressure, "Happy to share market insights whenever"""

    def __init__(
        self,
        agent_name: str = "Sarah",
        agent_email: str = "",
        agent_phone: str = "",
        brokerage_name: str = "",
        api_key: str = None,
    ):
        self.agent_name = agent_name
        self.agent_email = agent_email
        self.agent_phone = agent_phone
        self.brokerage_name = brokerage_name
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')

    async def generate_outreach(
        self,
        lead_context: LeadContext,
    ) -> InitialOutreach:
        """
        Generate personalized SMS and email for initial lead contact.

        Args:
            lead_context: Rich context about the new lead

        Returns:
            InitialOutreach with SMS and email content
        """
        # Build the context prompt
        context_prompt = self._build_context_prompt(lead_context)

        # Call Claude to generate messages
        try:
            sms, email_subject, email_body, model, tokens = await self._call_ai(
                context_prompt, lead_context
            )

            # Generate plain text email from HTML
            email_text = self._html_to_text(email_body)

            return InitialOutreach(
                sms_message=sms,
                email_subject=email_subject,
                email_body=email_body,
                email_text=email_text,
                context_used={
                    "source": lead_context.source,
                    "location": lead_context.get_location_str(),
                    "timeline": lead_context.timeline,
                    "price_range": lead_context.get_price_str(),
                },
                model_used=model,
                tokens_used=tokens,
            )

        except Exception as e:
            logger.error(f"AI generation failed, using smart fallback: {e}")
            return self._generate_smart_fallback(lead_context)

    def _build_context_prompt(self, ctx: LeadContext) -> str:
        """Build the context section of the prompt."""
        parts = []

        parts.append(f"Lead Name: {ctx.first_name}")

        # Use friendly source name
        friendly_source = ctx.get_friendly_source()
        if friendly_source:
            parts.append(f"Lead Source: {friendly_source}")

        # Lead type is critical - buyer, seller, or both
        if ctx.lead_type:
            lead_type_desc = {
                'buyer': 'BUYER only - looking to purchase a home',
                'seller': 'SELLER only - looking to sell their home',
                'both': 'BUYER AND SELLER - looking to sell current home AND buy a new one',
            }.get(ctx.lead_type, ctx.lead_type)
            parts.append(f"Lead Type: {lead_type_desc}")

        location = ctx.get_location_str()
        if location and location != "your area":
            parts.append(f"Location Interest: {location}")

        if ctx.zip_code:
            parts.append(f"ZIP Code: {ctx.zip_code}")

        price = ctx.get_price_str()
        if price:
            parts.append(f"Price Range: {price}")

        if ctx.property_type:
            parts.append(f"Property Type: {ctx.property_type}")

        if ctx.timeline:
            parts.append(f"Timeline: {ctx.timeline}")

        if ctx.financing_status:
            parts.append(f"Financing: {ctx.financing_status}")

        if ctx.buyer_type:
            parts.append(f"Buyer Type: {ctx.buyer_type}")

        if ctx.tags:
            parts.append(f"Tags: {', '.join(ctx.tags)}")

        parts.append(f"\nAgent Name: {self.agent_name}")
        if self.brokerage_name:
            parts.append(f"Brokerage: {self.brokerage_name}")

        return "\n".join(parts)

    async def _call_ai(
        self,
        context_prompt: str,
        lead_context: LeadContext,
    ) -> Tuple[str, str, str, str, int]:
        """Call AI API to generate messages. Supports Anthropic or OpenRouter."""
        import json
        import re

        friendly_source = lead_context.get_friendly_source()
        user_prompt = f"""Based on this lead information, generate a world-class initial outreach:

1. SMS: Short, casual, ends with easy question (under 160 chars ideal, max 300)
2. Email subject: Personal, specific to them, not generic
3. Email body: COMPLETE HTML email with ALL required sections:
   - Greeting ("Hey [Name]!")
   - Text acknowledgment (1 sentence about also sending a text)
   - Connection intro (how you were matched via {friendly_source or 'lead source'})
   - Self-intro (1 sentence about who you are)
   - Value offer (what useful thing you'll give them)
   - CTA in <strong> tags (tell them exactly what to do)
   - Sign-off ("Looking forward to connecting!" + Agent name)
   - PS line in <em> tags (second soft CTA)

LEAD CONTEXT:
{context_prompt}

Agent Phone (for PS line): {self.agent_phone or 'not provided'}

Respond in this exact JSON format:
{{
    "sms": "Your SMS message here",
    "email_subject": "Your subject line here",
    "email_body": "<p>Hey {lead_context.first_name}!</p><p>I just shot you a quick text too! {friendly_source or 'The platform'} connected us because...</p><p>I'm {self.agent_name}, and I...</p><p>Value offer here...</p><p><strong>Reply with X and I'll send you Y!</strong></p><p>Looking forward to connecting!</p><p>{self.agent_name}</p><p><em>P.S. Soft CTA or personal touch here!</em></p>"
}}

KEY DETAILS TO REFERENCE:
- Lead Name: {lead_context.first_name}
- Lead Type: {lead_context.lead_type or 'unknown - ask what they need'}
- Location: {lead_context.get_location_str()}
- Timeline: {lead_context.timeline or 'not specified'}
- Price range: {lead_context.get_price_str() or 'not specified'}
- Source (use this name): {friendly_source or 'not specified'}
- Agent: {self.agent_name}

IMPORTANT: The email_body MUST be a complete email with greeting, body paragraphs, sign-off, and PS line. Do not generate a partial email!"""

        # Try OpenRouter first (if available), then Anthropic
        openrouter_key = os.environ.get('OPENROUTER_API_KEY')
        anthropic_key = self.api_key or os.environ.get('ANTHROPIC_API_KEY')

        if openrouter_key:
            # Use OpenRouter with Claude
            return await self._call_openrouter(user_prompt, openrouter_key)
        elif anthropic_key:
            # Use Anthropic directly
            return await self._call_anthropic(user_prompt, anthropic_key)
        else:
            raise ValueError("No API key available (OPENROUTER_API_KEY or ANTHROPIC_API_KEY)")

    async def _call_openrouter(
        self,
        user_prompt: str,
        api_key: str,
    ) -> Tuple[str, str, str, str, int]:
        """Call OpenRouter API."""
        import aiohttp
        import json
        import re

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://leadsynergy.com",
                    "X-Title": "LeadSynergy AI",
                },
                json={
                    "model": "anthropic/claude-sonnet-4",
                    "messages": [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 1000,
                    "temperature": 0.7,
                },
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ValueError(f"OpenRouter API error {response.status}: {error_text}")

                data = await response.json()
                text = data['choices'][0]['message']['content']

                # Parse JSON from response
                json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    raise ValueError(f"Could not parse JSON from response: {text}")

                model_used = data.get('model', 'openrouter/claude')
                tokens = data.get('usage', {}).get('total_tokens', 0)

                return (
                    result.get('sms', ''),
                    result.get('email_subject', ''),
                    result.get('email_body', ''),
                    model_used,
                    tokens,
                )

    async def _call_anthropic(
        self,
        user_prompt: str,
        api_key: str,
    ) -> Tuple[str, str, str, str, int]:
        """Call Anthropic API directly."""
        import anthropic
        import json
        import re

        client = anthropic.AsyncAnthropic(api_key=api_key)

        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}]
        )

        text = response.content[0].text

        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
        else:
            raise ValueError(f"Could not parse JSON from response: {text}")

        return (
            data.get('sms', ''),
            data.get('email_subject', ''),
            data.get('email_body', ''),
            response.model,
            response.usage.input_tokens + response.usage.output_tokens,
        )

    def _generate_smart_fallback(self, ctx: LeadContext) -> InitialOutreach:
        """Generate fallback messages without AI if API fails."""
        location = ctx.get_location_str()
        timeline = ctx.get_timeline_str()

        # Smart SMS based on timeline
        if 'soon' in timeline or 'immediate' in ctx.timeline.lower() if ctx.timeline else False:
            sms = f"Hey {ctx.first_name}! {self.agent_name} here. Saw you're looking at {location} - great area! When's a good time to chat about what you're looking for?"
        elif ctx.timeline and ('12' in ctx.timeline or 'year' in ctx.timeline.lower()):
            sms = f"Hey {ctx.first_name}! {self.agent_name} here. I see you're exploring {location} for down the road. Happy to be a resource - what questions can I answer for you?"
        else:
            sms = f"Hey {ctx.first_name}! {self.agent_name} here. Noticed you're interested in {location}. What's got you looking in that area?"

        # Email subject
        if ctx.source:
            email_subject = f"Hey {ctx.first_name}! Quick note from your {ctx.source} inquiry"
        else:
            email_subject = f"Hey {ctx.first_name}! Let's find your perfect place in {location}"

        # Email body
        email_body = f"""<p>Hey {ctx.first_name}!</p>

<p>I saw you were checking out {location}"""

        if ctx.source:
            email_body += f" through {ctx.source}"

        email_body += " - great choice!"

        if ctx.get_price_str():
            email_body += f" Looks like you're looking in the {ctx.get_price_str()} range."

        email_body += "</p>"

        if timeline:
            email_body += f"\n<p>Since you're {timeline}, I want to make sure I'm helpful without being pushy. "
        else:
            email_body += "\n<p>"

        email_body += "What would be most useful for you right now - market insights, specific listings, or just someone to answer questions when they come up?</p>"

        email_body += f"\n<p>Looking forward to connecting!</p>\n<p>{self.agent_name}</p>"

        return InitialOutreach(
            sms_message=sms,
            email_subject=email_subject,
            email_body=email_body,
            email_text=self._html_to_text(email_body),
            context_used={
                "source": ctx.source,
                "location": location,
                "timeline": ctx.timeline,
                "fallback": True,
            },
            model_used="fallback",
            tokens_used=0,
        )

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text."""
        import re
        text = re.sub(r'<p[^>]*>', '\n', html)
        text = re.sub(r'</p>', '\n', text)
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        return text.strip()


async def generate_initial_outreach(
    person_data: Dict[str, Any],
    events: list = None,
    agent_name: str = "Sarah",
    agent_email: str = "",
    agent_phone: str = "",
    brokerage_name: str = "",
) -> InitialOutreach:
    """
    Convenience function to generate initial outreach for a new lead.

    Args:
        person_data: FUB person data dict
        events: FUB events for this person
        agent_name: Agent's name
        agent_email: Agent's email
        agent_phone: Agent's phone
        brokerage_name: Brokerage name

    Returns:
        InitialOutreach with SMS and email content
    """
    # Build lead context
    context = LeadContext.from_fub_data(person_data, events)

    # Create generator
    generator = InitialOutreachGenerator(
        agent_name=agent_name,
        agent_email=agent_email,
        agent_phone=agent_phone,
        brokerage_name=brokerage_name,
    )

    # Generate outreach
    return await generator.generate_outreach(context)
