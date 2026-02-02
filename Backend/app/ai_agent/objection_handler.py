"""
Objection Handler - Smart Handling of Lead Objections.

Provides context-aware objection handling:
1. Recognizes different types of objections
2. Selects appropriate response strategies
3. Tracks objection history to avoid repetition
4. Knows when to gracefully exit vs. persist
5. Maintains friendly, non-pushy tone

Designed for natural, empathetic conversations.
"""

import logging
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import random

logger = logging.getLogger(__name__)


class ObjectionType(Enum):
    """Types of objections leads commonly raise."""

    # Working with competition
    OTHER_AGENT = "other_agent"           # Already have an agent
    LOYALTY = "loyalty"                   # Loyal to current agent

    # Not ready
    NOT_READY = "not_ready"               # Not ready to buy/sell
    JUST_BROWSING = "just_browsing"       # Just looking around
    NEED_TIME = "need_time"               # Need time to think

    # Financial
    PRICE_TOO_HIGH = "price_too_high"     # Too expensive (for sellers)
    CANT_AFFORD = "cant_afford"           # Can't afford (for buyers)
    NEED_FINANCING = "need_financing"     # Need to figure out financing

    # Timing
    BAD_TIMING = "bad_timing"             # Not a good time
    WAITING = "waiting"                   # Waiting for something

    # Trust/skepticism
    NOT_INTERESTED = "not_interested"     # General disinterest
    DONT_TRUST = "dont_trust"             # Skeptical of agents/process
    HAD_BAD_EXPERIENCE = "bad_experience" # Previous bad experience

    # Logistics
    TOO_FAR = "too_far"                   # Property/area too far
    WRONG_SIZE = "wrong_size"             # Wrong property size/type

    # Decision-making
    NEED_SPOUSE = "need_spouse"           # Need to consult spouse/partner
    NEED_FAMILY = "need_family"           # Need to consult family

    # Unknown
    UNKNOWN = "unknown"


class ResponseStrategy(Enum):
    """Strategies for handling objections."""

    ACKNOWLEDGE_RESPECT = "acknowledge_respect"  # Acknowledge and respect decision
    SOFT_PIVOT = "soft_pivot"                   # Acknowledge then offer alternative
    VALUE_ADD = "value_add"                     # Offer value without pressure
    FUTURE_FOCUS = "future_focus"              # Focus on future contact
    INFORMATION_OFFER = "information_offer"     # Offer helpful information
    EMPATHY_CONNECT = "empathy_connect"        # Connect through empathy
    GRACEFUL_EXIT = "graceful_exit"            # Politely end pursuit


@dataclass
class ObjectionContext:
    """Context about the objection and lead."""
    objection_type: ObjectionType
    objection_count: int = 1           # How many times they've objected
    same_objection_count: int = 1      # How many times this specific objection
    lead_score: int = 0
    timeline: Optional[str] = None
    has_previous_engagement: bool = False
    conversation_turn: int = 0
    sentiment: str = "neutral"


@dataclass
class ObjectionResponse:
    """A response to an objection."""
    response_text: str
    strategy: ResponseStrategy
    should_follow_up: bool = True
    follow_up_delay_days: int = 7
    add_to_nurture: bool = False
    mark_as_closed: bool = False
    tags_to_add: List[str] = field(default_factory=list)
    notes_to_add: str = ""


class ObjectionScriptLibrary:
    """
    Library of objection handling scripts.

    Each script is friendly, casual, and non-pushy per the
    configured personality style.
    """

    # Scripts organized by objection type and strategy
    SCRIPTS: Dict[ObjectionType, Dict[ResponseStrategy, List[str]]] = {
        ObjectionType.OTHER_AGENT: {
            ResponseStrategy.ACKNOWLEDGE_RESPECT: [
                "No worries at all! Glad you've got someone helping you out. If anything changes or you ever want a second opinion, feel free to reach out. Good luck with your search!",
                "That's great you're already working with someone! I hope they find you the perfect place. Feel free to keep my number just in case - no pressure at all!",
                "Totally understand! Having a good agent makes all the difference. Wishing you the best - and I'm here if you ever need anything!",
            ],
            ResponseStrategy.VALUE_ADD: [
                "That's awesome you've got help! Just so you know, I send out weekly market updates for the area - totally free, no strings attached. Want me to add you to the list?",
                "Nice! If you ever want a second set of eyes on a property or just want to bounce ideas off someone, I'm happy to help. No pressure to switch or anything!",
            ],
        },

        ObjectionType.NOT_READY: {
            ResponseStrategy.FUTURE_FOCUS: [
                "That's totally fine! When do you think you might be ready to start looking more seriously? I can check back in then!",
                "No rush at all! Would it be helpful if I touched base in a few months? That way you'll have my info when you're ready.",
                "Completely understand! Real estate is a big decision. When you think you might be closer to ready, just give me a shout!",
            ],
            ResponseStrategy.VALUE_ADD: [
                "No problem! In the meantime, want me to send you some market updates so you know what's happening in the areas you're interested in? No commitment - just good info!",
                "Totally get it! If it helps, I can keep an eye on prices in your target areas and let you know if anything crazy happens. Just so you're prepared when the time comes!",
            ],
            ResponseStrategy.SOFT_PIVOT: [
                "Makes sense! Even though you're not ready to move forward, would it help to know what your current place might be worth? Could be useful for planning!",
                "No worries! Just curious - what would need to change for you to be ready? Maybe I can help with some of those things!",
            ],
        },

        ObjectionType.JUST_BROWSING: {
            ResponseStrategy.VALUE_ADD: [
                "Totally get it! Most people start that way. Want me to send you some listings that match what you're looking for? No strings attached - just thought it might be helpful!",
                "That's cool! Browsing is the best way to figure out what you want. I can set up an alert to send you new listings as they pop up - interested?",
                "No pressure at all! Just window shopping is totally fine. If you see something you like and want more info, just holler!",
            ],
            ResponseStrategy.FUTURE_FOCUS: [
                "That's how most people start! When you get more serious about it, feel free to reach out. I'd love to help when the time is right!",
                "Browsing is smart - you learn a lot! Let me know if you have any questions as you're looking around. Happy to help!",
            ],
        },

        ObjectionType.PRICE_TOO_HIGH: {
            ResponseStrategy.INFORMATION_OFFER: [
                "I hear you! The market can be tricky. How about we look at a few recent sales in your neighborhood together? That way you can see exactly where the numbers come from.",
                "I get it - pricing is tough! Want me to put together a quick breakdown of what similar homes sold for recently? Might help you see the full picture.",
                "Totally understand the concern! Prices have been all over the place. I can show you the data behind the number if that would help - sometimes it makes more sense when you see the comps.",
            ],
            ResponseStrategy.EMPATHY_CONNECT: [
                "I know it can feel that way! Pricing is honestly one of the trickiest parts. What number were you thinking would work better?",
                "I hear you - and you're not wrong to question it. The market's been wild. What would feel more reasonable to you?",
            ],
        },

        ObjectionType.CANT_AFFORD: {
            ResponseStrategy.VALUE_ADD: [
                "I totally get it - buying a home is a big financial step! Have you talked to a lender yet? Sometimes people are surprised by what they can actually afford. I know some great ones who are super helpful!",
                "Budget is so important! There are also some great programs for first-time buyers that might help. Want me to send you some info on those?",
                "I understand! There might be more options than you think, though. Want to grab a quick coffee and chat about what might work? No pressure - just brainstorming!",
            ],
            ResponseStrategy.SOFT_PIVOT: [
                "I hear you! What if we looked at some different areas or property types that might fit better? Sometimes there are hidden gems that aren't as expensive!",
                "Makes sense! Would it help to look at what's out there in a lower price range? I can show you what's possible!",
            ],
        },

        ObjectionType.BAD_TIMING: {
            ResponseStrategy.ACKNOWLEDGE_RESPECT: [
                "Totally understand! Life gets busy. When would be a better time to chat? I'm flexible!",
                "No problem at all! Is there a better time I could reach out? Happy to work around your schedule.",
                "Got it! Things happen. Just shoot me a text when you have a free moment - no rush!",
            ],
            ResponseStrategy.FUTURE_FOCUS: [
                "I hear you - timing is everything! When do you think things will calm down? I can check back then.",
                "Completely understand! Would it be better if I followed up in a week or two when things settle down?",
            ],
        },

        ObjectionType.NOT_INTERESTED: {
            ResponseStrategy.ACKNOWLEDGE_RESPECT: [
                "No problem at all! Thanks for letting me know. If anything changes down the road, feel free to reach out. Take care!",
                "Got it! I appreciate you being upfront. Wishing you all the best - and I'm here if you ever change your mind!",
                "Totally understand! Thanks for your time. If you ever need anything real estate related, you know where to find me!",
            ],
            ResponseStrategy.GRACEFUL_EXIT: [
                "No worries! I don't want to bug you if it's not a good fit. All the best to you!",
                "I appreciate you letting me know! I'll leave you be. Take care!",
            ],
        },

        ObjectionType.NEED_SPOUSE: {
            ResponseStrategy.SOFT_PIVOT: [
                "Of course! That totally makes sense. Would it help if we all got on a quick call together? I'm happy to answer any questions they might have too!",
                "Totally get it - big decisions should be made together! Want me to send some info you can share with them? That way they're in the loop.",
                "Makes sense! Would your spouse want to join us for a quick showing or call? Sometimes it's easier to talk things through together.",
            ],
            ResponseStrategy.FUTURE_FOCUS: [
                "Absolutely! Chat it over and let me know what you both decide. I'm here whenever you're ready!",
                "Of course! Take the time you need. When you've had a chance to talk, just give me a shout!",
            ],
        },

        ObjectionType.NEED_TIME: {
            ResponseStrategy.ACKNOWLEDGE_RESPECT: [
                "Totally understand! Take all the time you need. No pressure from me - I'm here when you're ready!",
                "Of course! It's a big decision. Just reach out when you've had a chance to think it over.",
                "No rush at all! Sleep on it and let me know what you're thinking. I'm not going anywhere!",
            ],
            ResponseStrategy.FUTURE_FOCUS: [
                "Makes sense! Would it help if I checked back in a few days? Sometimes it's nice to have a deadline to think by!",
                "Take your time! Want me to follow up next week, or would you rather reach out when you're ready?",
            ],
        },

        ObjectionType.HAD_BAD_EXPERIENCE: {
            ResponseStrategy.EMPATHY_CONNECT: [
                "Oh man, I'm sorry to hear that! Bad experiences really suck. If you don't mind sharing, what went wrong? I'd want to make sure that doesn't happen again.",
                "That's really frustrating - I'm sorry you went through that. I totally get being hesitant. What would help you feel more comfortable this time?",
                "I hear you - a bad experience can really sour things. I'd love the chance to show you it doesn't have to be that way, but I completely understand if you're hesitant.",
            ],
            ResponseStrategy.VALUE_ADD: [
                "I'm sorry you had that experience! If it helps, I'm happy to do things differently - whatever works for you. What would make this feel better?",
            ],
        },

        ObjectionType.NEED_FINANCING: {
            ResponseStrategy.VALUE_ADD: [
                "That's actually a great first step! I know some awesome lenders who are super easy to work with. Want me to make an intro? They can help you figure out exactly where you stand.",
                "Smart to sort that out first! Getting pre-approved makes everything easier. I can connect you with a few lenders who are really good - no pressure, just options!",
                "Totally makes sense! Financing is huge. Want me to send you some info on the process? And I know some great lenders if you need recommendations!",
            ],
            ResponseStrategy.INFORMATION_OFFER: [
                "A lot of buyers start the process before they're fully pre-approved! Would it help if I sent some info on what lenders look for?",
                "There are some great programs out there - FHA, VA, down payment assistance. Want me to send you a quick overview of options?",
            ],
            ResponseStrategy.FUTURE_FOCUS: [
                "Smart to get your ducks in a row! Once you're pre-approved, I can start sending you homes that fit your budget. Want me to check back in a couple weeks?",
            ],
        },

        ObjectionType.WAITING: {
            ResponseStrategy.INFORMATION_OFFER: [
                "That makes sense! Just curious - what are you waiting for? Sometimes I can help with the stuff that's holding things up!",
                "Totally get it! Is there something specific you're waiting on? I might be able to help speed things along!",
            ],
            ResponseStrategy.FUTURE_FOCUS: [
                "No problem! When do you think that will be sorted out? I can check back in then!",
                "Makes sense! Let me know when things are clearer on your end. Happy to help when you're ready!",
            ],
        },

        ObjectionType.LOYALTY: {
            ResponseStrategy.ACKNOWLEDGE_RESPECT: [
                "That's awesome that you have a good relationship with your agent! Loyalty says a lot about you. If you ever need a second opinion on anything, I'm here!",
                "Love hearing that! A good agent relationship is everything. If things ever change or you need help in a different area, don't hesitate to reach out!",
                "Totally respect that! Having an agent you trust is huge. I'm here as a resource if you ever need anything - no strings attached!",
            ],
            ResponseStrategy.VALUE_ADD: [
                "Completely understand! Just so you know, I specialize in this area and I'm always happy to share market insights - even if you're working with someone else!",
                "No worries at all! I know the local market really well, so if you ever want a fresh perspective on pricing or neighborhoods, I'm just a text away!",
            ],
        },

        ObjectionType.DONT_TRUST: {
            ResponseStrategy.EMPATHY_CONNECT: [
                "I totally get it - there are definitely some pushy agents out there. I promise I'm not one of them! I'm here to help, not to pressure you into anything.",
                "I hear you, and honestly, that's fair. Real estate can feel overwhelming. I'm just here to answer questions and share info - zero pressure!",
                "Completely understand the hesitation. The best thing I can do is just be straight with you and let my actions speak for themselves. No tricks, just help!",
            ],
            ResponseStrategy.VALUE_ADD: [
                "I get it! How about this - no commitment, no pressure. If you have any questions about the market or the process, I'm happy to just be a resource for you.",
                "Tell you what - I'll just send you some useful info about the area. No strings attached. If you find it helpful, great. If not, no hard feelings!",
            ],
            ResponseStrategy.ACKNOWLEDGE_RESPECT: [
                "Appreciate you being honest with me! That actually helps me serve you better. I'll keep things simple and straightforward - just real info, no sales pitch.",
            ],
        },

        ObjectionType.TOO_FAR: {
            ResponseStrategy.SOFT_PIVOT: [
                "I hear you on the distance! Have you considered any closer neighborhoods? I know some great areas that might give you what you're looking for without the commute.",
                "That's a valid concern! What areas would work better for you? I can look at options that are more convenient.",
                "Distance is definitely a factor! What's your ideal commute time? I might know some spots you haven't considered yet.",
            ],
            ResponseStrategy.INFORMATION_OFFER: [
                "Totally get it! If it helps, I can put together some options in areas closer to you. What neighborhoods or zip codes work best?",
                "Makes sense! I cover a pretty wide area - let me know your preferred location and I'll see what's available there.",
            ],
        },

        ObjectionType.WRONG_SIZE: {
            ResponseStrategy.SOFT_PIVOT: [
                "Got it! What size/type of home are you looking for? I can filter my search to match exactly what you need.",
                "No problem! What would be the right fit for you - bedrooms, bathrooms, square footage? I'll narrow things down!",
                "Totally understand! Let me know what you're looking for specifically and I'll send you options that actually match.",
            ],
            ResponseStrategy.INFORMATION_OFFER: [
                "That's good to know! Are you looking for something bigger, smaller, or a different layout? I want to make sure I'm sending you the right stuff.",
                "Fair enough! What's your must-have list look like? I'll make sure everything I send is on target.",
            ],
        },

        ObjectionType.NEED_FAMILY: {
            ResponseStrategy.ACKNOWLEDGE_RESPECT: [
                "Of course! Family decisions are the most important ones. Take all the time you need to talk it through!",
                "Totally makes sense - big decisions like this should be a family thing. No rush at all!",
                "Absolutely! Want me to send some info they can look at too? Sometimes having the details in front of everyone helps the conversation.",
            ],
            ResponseStrategy.FUTURE_FOCUS: [
                "Take your time! When do you think you'll have a chance to chat with them? I can follow up after that.",
                "No problem! Would it help if I checked back in a few days after you've had a chance to talk it over?",
            ],
            ResponseStrategy.VALUE_ADD: [
                "That's smart! If it helps, I can put together a quick summary of what we've talked about so you have something to share with your family.",
            ],
        },
    }

    # Default scripts for unmapped objection types
    DEFAULT_SCRIPTS: Dict[ResponseStrategy, List[str]] = {
        ResponseStrategy.ACKNOWLEDGE_RESPECT: [
            "I totally understand! Thanks for being upfront with me. If anything changes, don't hesitate to reach out!",
            "No problem at all! I appreciate you letting me know. I'm here if you ever need anything!",
        ],
        ResponseStrategy.FUTURE_FOCUS: [
            "Got it! When would be a better time to reconnect? I'm happy to follow up later!",
            "Understood! Would it be okay if I checked back in a few weeks?",
        ],
        ResponseStrategy.VALUE_ADD: [
            "I hear you! Even if now isn't the right time, I'm happy to be a resource. Feel free to reach out with any questions!",
        ],
        ResponseStrategy.GRACEFUL_EXIT: [
            "No worries at all! Thanks for your time. Wishing you all the best!",
            "Got it! I appreciate you letting me know. Take care!",
        ],
    }


class ObjectionHandler:
    """
    Handles lead objections with context-aware responses.

    Uses the script library and contextual factors to select
    the best response strategy and script.
    """

    # Strategy selection rules based on context
    STRATEGY_RULES = {
        # First objection - be helpful and non-pushy
        "first_objection": {
            ObjectionType.OTHER_AGENT: ResponseStrategy.ACKNOWLEDGE_RESPECT,
            ObjectionType.NOT_INTERESTED: ResponseStrategy.ACKNOWLEDGE_RESPECT,
            ObjectionType.NOT_READY: ResponseStrategy.VALUE_ADD,
            ObjectionType.JUST_BROWSING: ResponseStrategy.VALUE_ADD,
            ObjectionType.PRICE_TOO_HIGH: ResponseStrategy.INFORMATION_OFFER,
            ObjectionType.CANT_AFFORD: ResponseStrategy.VALUE_ADD,
            ObjectionType.BAD_TIMING: ResponseStrategy.FUTURE_FOCUS,
            ObjectionType.NEED_SPOUSE: ResponseStrategy.SOFT_PIVOT,
            ObjectionType.NEED_TIME: ResponseStrategy.ACKNOWLEDGE_RESPECT,
            ObjectionType.HAD_BAD_EXPERIENCE: ResponseStrategy.EMPATHY_CONNECT,
            ObjectionType.NEED_FINANCING: ResponseStrategy.VALUE_ADD,
            ObjectionType.WAITING: ResponseStrategy.INFORMATION_OFFER,
        },
        # Second time same objection - be more graceful
        "repeat_objection": {
            ObjectionType.OTHER_AGENT: ResponseStrategy.GRACEFUL_EXIT,
            ObjectionType.NOT_INTERESTED: ResponseStrategy.GRACEFUL_EXIT,
            ObjectionType.NOT_READY: ResponseStrategy.FUTURE_FOCUS,
            ObjectionType.JUST_BROWSING: ResponseStrategy.FUTURE_FOCUS,
            ObjectionType.PRICE_TOO_HIGH: ResponseStrategy.ACKNOWLEDGE_RESPECT,
            ObjectionType.CANT_AFFORD: ResponseStrategy.ACKNOWLEDGE_RESPECT,
            ObjectionType.BAD_TIMING: ResponseStrategy.ACKNOWLEDGE_RESPECT,
            ObjectionType.NEED_SPOUSE: ResponseStrategy.FUTURE_FOCUS,
            ObjectionType.NEED_TIME: ResponseStrategy.FUTURE_FOCUS,
            ObjectionType.HAD_BAD_EXPERIENCE: ResponseStrategy.GRACEFUL_EXIT,
            ObjectionType.NEED_FINANCING: ResponseStrategy.FUTURE_FOCUS,
            ObjectionType.WAITING: ResponseStrategy.FUTURE_FOCUS,
        },
    }

    def __init__(self):
        """Initialize the objection handler."""
        self._objection_history: Dict[str, List[ObjectionType]] = {}

    def handle_objection(
        self,
        objection_type: ObjectionType,
        context: ObjectionContext,
        lead_id: Optional[str] = None,
    ) -> ObjectionResponse:
        """
        Handle an objection and generate appropriate response.

        Args:
            objection_type: The type of objection detected
            context: Context about the objection and lead
            lead_id: Optional lead ID for tracking history

        Returns:
            ObjectionResponse with text and metadata
        """
        # Track objection history
        if lead_id:
            if lead_id not in self._objection_history:
                self._objection_history[lead_id] = []
            self._objection_history[lead_id].append(objection_type)
            context.same_objection_count = self._objection_history[lead_id].count(objection_type)
            context.objection_count = len(self._objection_history[lead_id])

        # Select strategy
        strategy = self._select_strategy(objection_type, context)

        # Get response script
        response_text = self._get_script(objection_type, strategy)

        # Determine follow-up behavior
        follow_up_config = self._get_follow_up_config(objection_type, strategy, context)

        return ObjectionResponse(
            response_text=response_text,
            strategy=strategy,
            **follow_up_config
        )

    def _select_strategy(
        self,
        objection_type: ObjectionType,
        context: ObjectionContext,
    ) -> ResponseStrategy:
        """Select the best response strategy based on context."""

        # Negative sentiment = graceful exit
        if context.sentiment == "negative" and context.objection_count >= 2:
            return ResponseStrategy.GRACEFUL_EXIT

        # Multiple objections of same type = respect their decision
        if context.same_objection_count >= 2:
            rules = self.STRATEGY_RULES.get("repeat_objection", {})
            strategy = rules.get(objection_type)
            if strategy:
                return strategy
            return ResponseStrategy.GRACEFUL_EXIT

        # Hot lead with objection = try harder
        if context.lead_score >= 70:
            # For hot leads, be more persistent (but still friendly)
            if objection_type in [ObjectionType.NOT_READY, ObjectionType.NEED_TIME]:
                return ResponseStrategy.SOFT_PIVOT
            if objection_type == ObjectionType.BAD_TIMING:
                return ResponseStrategy.VALUE_ADD

        # First objection - use standard rules
        rules = self.STRATEGY_RULES.get("first_objection", {})
        strategy = rules.get(objection_type)

        if strategy:
            return strategy

        # Default strategies by objection severity
        exit_immediately = [
            ObjectionType.OTHER_AGENT,
            ObjectionType.NOT_INTERESTED,
            ObjectionType.LOYALTY,
        ]

        if objection_type in exit_immediately:
            return ResponseStrategy.ACKNOWLEDGE_RESPECT

        return ResponseStrategy.VALUE_ADD

    def _get_script(
        self,
        objection_type: ObjectionType,
        strategy: ResponseStrategy,
    ) -> str:
        """Get a script for the objection and strategy."""

        # Try objection-specific scripts first
        objection_scripts = ObjectionScriptLibrary.SCRIPTS.get(objection_type, {})
        strategy_scripts = objection_scripts.get(strategy, [])

        if strategy_scripts:
            return random.choice(strategy_scripts)

        # Fall back to default scripts
        default_scripts = ObjectionScriptLibrary.DEFAULT_SCRIPTS.get(strategy, [])
        if default_scripts:
            return random.choice(default_scripts)

        # Last resort
        return "I understand! Thanks for letting me know. Feel free to reach out if anything changes!"

    def _get_follow_up_config(
        self,
        objection_type: ObjectionType,
        strategy: ResponseStrategy,
        context: ObjectionContext,
    ) -> Dict[str, Any]:
        """Determine follow-up behavior based on objection."""

        config = {
            "should_follow_up": True,
            "follow_up_delay_days": 7,
            "add_to_nurture": False,
            "mark_as_closed": False,
            "tags_to_add": [],
            "notes_to_add": f"Objection: {objection_type.value}. Strategy: {strategy.value}",
        }

        # Graceful exits
        if strategy == ResponseStrategy.GRACEFUL_EXIT:
            config["should_follow_up"] = False
            config["add_to_nurture"] = True
            config["follow_up_delay_days"] = 90
            config["tags_to_add"].append("ai_objection_exit")

        # Working with another agent
        if objection_type == ObjectionType.OTHER_AGENT:
            config["should_follow_up"] = False
            config["add_to_nurture"] = True
            config["follow_up_delay_days"] = 60
            config["tags_to_add"].append("has_other_agent")

        # Not interested
        if objection_type == ObjectionType.NOT_INTERESTED:
            config["should_follow_up"] = False
            config["mark_as_closed"] = context.objection_count >= 2
            config["tags_to_add"].append("not_interested")

        # Just browsing / not ready
        if objection_type in [ObjectionType.JUST_BROWSING, ObjectionType.NOT_READY]:
            config["follow_up_delay_days"] = 14
            config["add_to_nurture"] = True
            config["tags_to_add"].append("long_term_nurture")

        # Financial objections
        if objection_type in [ObjectionType.CANT_AFFORD, ObjectionType.NEED_FINANCING]:
            config["follow_up_delay_days"] = 30
            config["tags_to_add"].append("needs_financing_help")

        # Timeline based
        if context.timeline == "long":
            config["follow_up_delay_days"] = 30
            config["add_to_nurture"] = True
        elif context.timeline == "medium":
            config["follow_up_delay_days"] = 14

        return config

    def classify_objection(self, intent: str) -> ObjectionType:
        """
        Map an intent to an objection type.

        Args:
            intent: The detected intent string

        Returns:
            Corresponding ObjectionType
        """
        intent_mapping = {
            "objection_other_agent": ObjectionType.OTHER_AGENT,
            "objection_not_ready": ObjectionType.NOT_READY,
            "objection_just_browsing": ObjectionType.JUST_BROWSING,
            "objection_price": ObjectionType.PRICE_TOO_HIGH,
            "objection_timing": ObjectionType.BAD_TIMING,
            "negative_interest": ObjectionType.NOT_INTERESTED,
        }

        return intent_mapping.get(intent, ObjectionType.UNKNOWN)

    def get_objection_history(self, lead_id: str) -> List[ObjectionType]:
        """Get objection history for a lead."""
        return self._objection_history.get(lead_id, [])

    def clear_objection_history(self, lead_id: str):
        """Clear objection history for a lead."""
        if lead_id in self._objection_history:
            del self._objection_history[lead_id]


class ObjectionAnalyzer:
    """
    Analyzes objection patterns for insights.

    Useful for:
    - Understanding common objections
    - Optimizing scripts
    - Identifying training needs
    """

    def __init__(self, handler: ObjectionHandler):
        self.handler = handler

    def get_objection_stats(self) -> Dict[str, Any]:
        """Get statistics about objection handling."""
        all_objections = []
        for history in self.handler._objection_history.values():
            all_objections.extend(history)

        if not all_objections:
            return {"total": 0, "by_type": {}}

        type_counts = {}
        for obj in all_objections:
            type_counts[obj.value] = type_counts.get(obj.value, 0) + 1

        return {
            "total": len(all_objections),
            "unique_leads": len(self.handler._objection_history),
            "by_type": type_counts,
            "most_common": max(type_counts.items(), key=lambda x: x[1])[0]
                if type_counts else None,
        }

    def get_leads_needing_attention(
        self,
        max_objections: int = 3,
    ) -> List[str]:
        """Get lead IDs that have had many objections."""
        return [
            lead_id
            for lead_id, history in self.handler._objection_history.items()
            if len(history) >= max_objections
        ]


def handle_lead_objection(
    intent: str,
    lead_score: int = 0,
    timeline: Optional[str] = None,
    sentiment: str = "neutral",
    objection_count: int = 1,
    lead_id: Optional[str] = None,
) -> ObjectionResponse:
    """
    Convenience function for handling objections.

    Args:
        intent: Detected intent string
        lead_score: Current lead score (0-100)
        timeline: Lead's timeline (immediate/short/medium/long)
        sentiment: Current sentiment (positive/negative/neutral)
        objection_count: Number of previous objections
        lead_id: Optional lead ID for tracking

    Returns:
        ObjectionResponse with response text and metadata
    """
    handler = ObjectionHandler()
    objection_type = handler.classify_objection(intent)

    context = ObjectionContext(
        objection_type=objection_type,
        objection_count=objection_count,
        lead_score=lead_score,
        timeline=timeline,
        sentiment=sentiment,
    )

    return handler.handle_objection(objection_type, context, lead_id)
