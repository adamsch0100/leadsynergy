"""
Qualification Flow Manager - Smart Lead Qualification Question Sequencing.

Provides intelligent lead qualification through:
1. Dynamic question selection based on what's already known
2. Adaptive sequencing based on conversation flow and lead signals
3. Progress tracking and completeness scoring
4. Natural conversation integration (not robotic Q&A)

Designed for friendly, casual real estate conversations.
"""

import logging
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


class QualificationCategory(Enum):
    """Categories of qualification information."""
    TIMELINE = "timeline"
    BUDGET = "budget"
    LOCATION = "location"
    PROPERTY_TYPE = "property_type"
    MOTIVATION = "motivation"
    PRE_APPROVAL = "pre_approval"
    CURRENT_SITUATION = "current_situation"
    DECISION_MAKERS = "decision_makers"


class QualificationPriority(Enum):
    """Priority levels for qualification questions."""
    CRITICAL = 1      # Must know to proceed
    HIGH = 2          # Very important for qualification
    MEDIUM = 3        # Useful for personalization
    LOW = 4           # Nice to have


@dataclass
class QualificationQuestion:
    """A single qualification question with variants."""
    id: str
    category: QualificationCategory
    priority: QualificationPriority
    question_variants: List[str]  # Different ways to ask
    follow_up_variants: List[str]  # If answer was partial
    data_key: str  # Key to store answer
    value_type: str  # string, number, boolean, enum
    valid_values: Optional[List[str]] = None  # For enum type
    depends_on: Optional[str] = None  # Only ask if this data_key has value
    skip_if: Optional[str] = None  # Skip if this data_key has value
    required_for_hot: bool = False  # Required to be considered "hot" lead


@dataclass
class QualificationData:
    """Current state of lead qualification."""
    timeline: Optional[str] = None
    timeline_raw: Optional[str] = None
    budget: Optional[int] = None
    budget_range_low: Optional[int] = None
    budget_range_high: Optional[int] = None
    budget_raw: Optional[str] = None
    is_pre_approved: Optional[bool] = None
    pre_approval_amount: Optional[int] = None
    location_preferences: List[str] = field(default_factory=list)
    property_types: List[str] = field(default_factory=list)
    motivation: Optional[str] = None
    motivation_raw: Optional[str] = None
    current_situation: Optional[str] = None  # renting, own, etc.
    decision_makers: Optional[str] = None  # just me, spouse, etc.
    bedrooms_min: Optional[int] = None
    bathrooms_min: Optional[int] = None
    must_haves: List[str] = field(default_factory=list)
    deal_breakers: List[str] = field(default_factory=list)
    additional_notes: str = ""
    questions_asked: List[str] = field(default_factory=list)
    last_question_category: Optional[str] = None
    qualification_score: float = 0.0
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "timeline": self.timeline,
            "timeline_raw": self.timeline_raw,
            "budget": self.budget,
            "budget_range": {"low": self.budget_range_low, "high": self.budget_range_high}
                if self.budget_range_low else None,
            "budget_raw": self.budget_raw,
            "is_pre_approved": self.is_pre_approved,
            "pre_approval_amount": self.pre_approval_amount,
            "location_preferences": self.location_preferences,
            "property_types": self.property_types,
            "motivation": self.motivation,
            "motivation_raw": self.motivation_raw,
            "current_situation": self.current_situation,
            "decision_makers": self.decision_makers,
            "bedrooms_min": self.bedrooms_min,
            "bathrooms_min": self.bathrooms_min,
            "must_haves": self.must_haves,
            "deal_breakers": self.deal_breakers,
            "additional_notes": self.additional_notes,
            "questions_asked": self.questions_asked,
            "qualification_score": self.qualification_score,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualificationData":
        """Create from dictionary."""
        budget_range = data.get("budget_range", {}) or {}
        return cls(
            timeline=data.get("timeline"),
            timeline_raw=data.get("timeline_raw"),
            budget=data.get("budget"),
            budget_range_low=budget_range.get("low"),
            budget_range_high=budget_range.get("high"),
            budget_raw=data.get("budget_raw"),
            is_pre_approved=data.get("is_pre_approved"),
            pre_approval_amount=data.get("pre_approval_amount"),
            location_preferences=data.get("location_preferences", []),
            property_types=data.get("property_types", []),
            motivation=data.get("motivation"),
            motivation_raw=data.get("motivation_raw"),
            current_situation=data.get("current_situation"),
            decision_makers=data.get("decision_makers"),
            bedrooms_min=data.get("bedrooms_min"),
            bathrooms_min=data.get("bathrooms_min"),
            must_haves=data.get("must_haves", []),
            deal_breakers=data.get("deal_breakers", []),
            additional_notes=data.get("additional_notes", ""),
            questions_asked=data.get("questions_asked", []),
            qualification_score=data.get("qualification_score", 0.0),
            updated_at=datetime.fromisoformat(data["updated_at"])
                if data.get("updated_at") else None,
        )

    def has_value(self, key: str) -> bool:
        """Check if a qualification field has a value."""
        value = getattr(self, key, None)
        if value is None:
            return False
        if isinstance(value, list):
            return len(value) > 0
        if isinstance(value, str):
            return len(value.strip()) > 0
        return True


@dataclass
class QualificationProgress:
    """Track qualification progress and completeness."""
    total_categories: int
    completed_categories: int
    critical_complete: bool
    high_complete: bool
    overall_percentage: float
    missing_critical: List[QualificationCategory]
    missing_high: List[QualificationCategory]
    next_recommended_category: Optional[QualificationCategory]
    is_minimally_qualified: bool
    is_fully_qualified: bool


class QualificationFlowManager:
    """
    Manages the lead qualification conversation flow.

    Intelligently sequences questions based on:
    - What information we already have
    - What the lead has naturally shared
    - Conversation flow and context
    - Lead engagement signals
    """

    # All qualification questions with friendly, casual variants
    QUESTIONS: Dict[str, QualificationQuestion] = {
        # Timeline questions
        "timeline_general": QualificationQuestion(
            id="timeline_general",
            category=QualificationCategory.TIMELINE,
            priority=QualificationPriority.CRITICAL,
            question_variants=[
                "So what's your timeline looking like? Trying to move soon or just exploring what's out there?",
                "Any idea when you're hoping to make a move? Just curious where you're at in the process!",
                "Are you looking to move pretty soon, or more just seeing what's available right now?",
            ],
            follow_up_variants=[
                "Got it! So when you say that, are we talking like next month, few months out, or more long term?",
                "That makes sense! Just to get a better idea - would you say weeks, months, or more like next year?",
            ],
            data_key="timeline",
            value_type="enum",
            valid_values=["immediate", "short", "medium", "long", "unknown"],
            required_for_hot=True,
        ),

        # Budget questions
        "budget_general": QualificationQuestion(
            id="budget_general",
            category=QualificationCategory.BUDGET,
            priority=QualificationPriority.CRITICAL,
            question_variants=[
                "Have you figured out your budget yet, or still working on that part?",
                "Do you have a price range in mind, or would it help to chat with a lender first?",
                "What are you thinking budget-wise? No pressure - just helps me know what to look for!",
            ],
            follow_up_variants=[
                "Totally get it! Even a rough ballpark helps - like are we talking under 500K, or more in the 500-800K range?",
                "No worries! What would feel comfortable monthly payment-wise? That can help narrow it down.",
            ],
            data_key="budget",
            value_type="number",
            required_for_hot=True,
        ),
        "pre_approval": QualificationQuestion(
            id="pre_approval",
            category=QualificationCategory.PRE_APPROVAL,
            priority=QualificationPriority.HIGH,
            question_variants=[
                "Have you chatted with a lender yet about getting pre-approved? I know some great ones if you need a rec!",
                "Are you pre-approved already, or is that something you still need to do?",
                "Have you talked to a mortgage person yet? Just helps sellers take offers more seriously!",
            ],
            follow_up_variants=[
                "Nice! Do you remember roughly what amount you got approved for?",
                "That's great! Knowing your pre-approval amount helps me find places that fit perfectly.",
            ],
            data_key="is_pre_approved",
            value_type="boolean",
            depends_on="budget",
        ),

        # Location questions
        "location_preference": QualificationQuestion(
            id="location_preference",
            category=QualificationCategory.LOCATION,
            priority=QualificationPriority.HIGH,
            question_variants=[
                "Any specific areas you're really into? I can keep an eye out for new listings there!",
                "Where are you hoping to end up? Got any neighborhoods or areas in mind?",
                "What areas are you looking at? Close to work, good schools, nightlife - what matters most?",
            ],
            follow_up_variants=[
                "Love that area! Any other neighborhoods you'd consider, or just focused on that one?",
                "Great choice! What draws you to that area specifically?",
            ],
            data_key="location_preferences",
            value_type="list",
            required_for_hot=True,
        ),

        # Property type
        "property_type": QualificationQuestion(
            id="property_type",
            category=QualificationCategory.PROPERTY_TYPE,
            priority=QualificationPriority.MEDIUM,
            question_variants=[
                "What kind of place are you looking for - house, condo, townhome?",
                "Are you thinking single-family home, or would you consider a condo or townhouse too?",
                "What type of property works best for you?",
            ],
            follow_up_variants=[
                "Makes sense! Any flexibility there, or pretty set on that?",
            ],
            data_key="property_types",
            value_type="list",
        ),

        # Motivation
        "motivation": QualificationQuestion(
            id="motivation",
            category=QualificationCategory.MOTIVATION,
            priority=QualificationPriority.MEDIUM,
            question_variants=[
                "What's got you looking to move? Just curious what's driving the search!",
                "So what's the story - job change, need more space, something else?",
                "Mind if I ask what's making you want to move? Helps me understand what matters most!",
            ],
            follow_up_variants=[
                "That totally makes sense! How soon does that need to happen?",
                "Oh interesting! That's definitely a good reason to move.",
            ],
            data_key="motivation",
            value_type="string",
        ),

        # Current situation
        "current_situation": QualificationQuestion(
            id="current_situation",
            category=QualificationCategory.CURRENT_SITUATION,
            priority=QualificationPriority.MEDIUM,
            question_variants=[
                "Are you renting right now, or do you have a place to sell first?",
                "What's your current living situation - renting or owning?",
                "Quick question - do you need to sell a home too, or just buying?",
            ],
            follow_up_variants=[
                "Got it! Is your lease flexible, or do you have a specific end date?",
                "Okay! Do you need to sell before you can buy, or can you do them at the same time?",
            ],
            data_key="current_situation",
            value_type="enum",
            valid_values=["renting", "owning_sell_first", "owning_can_buy", "living_with_family", "other"],
        ),

        # Decision makers
        "decision_makers": QualificationQuestion(
            id="decision_makers",
            category=QualificationCategory.DECISION_MAKERS,
            priority=QualificationPriority.LOW,
            question_variants=[
                "Will anyone else be part of the decision? Just want to make sure we include everyone!",
                "Is it just you making this decision, or do you have a partner/family involved too?",
                "Who all needs to sign off on the final choice?",
            ],
            follow_up_variants=[
                "Perfect! Should I loop them in on showings too?",
            ],
            data_key="decision_makers",
            value_type="string",
        ),

        # Must-haves
        "must_haves": QualificationQuestion(
            id="must_haves",
            category=QualificationCategory.PROPERTY_TYPE,
            priority=QualificationPriority.MEDIUM,
            question_variants=[
                "What's on your must-have list? Like, what can't you live without?",
                "Any deal-breakers or must-haves I should know about?",
                "What features are non-negotiable for you?",
            ],
            follow_up_variants=[
                "Good to know! Anything else that's super important?",
            ],
            data_key="must_haves",
            value_type="list",
            depends_on="property_type",
        ),
    }

    # Question flow rules
    CATEGORY_ORDER = [
        QualificationCategory.TIMELINE,
        QualificationCategory.BUDGET,
        QualificationCategory.LOCATION,
        QualificationCategory.PRE_APPROVAL,
        QualificationCategory.PROPERTY_TYPE,
        QualificationCategory.MOTIVATION,
        QualificationCategory.CURRENT_SITUATION,
        QualificationCategory.DECISION_MAKERS,
    ]

    def __init__(self, qualification_data: Optional[QualificationData] = None):
        """Initialize the flow manager."""
        self.data = qualification_data or QualificationData()
        self._question_count = 0
        self._last_category = None

    def get_next_question(
        self,
        conversation_context: Optional[Dict[str, Any]] = None,
        avoid_category: Optional[QualificationCategory] = None,
        max_questions_asked: int = 10,
    ) -> Optional[Tuple[QualificationQuestion, str]]:
        """
        Get the next best qualification question to ask.

        Args:
            conversation_context: Optional context about the conversation
            avoid_category: Category to skip (e.g., if just asked about it)
            max_questions_asked: Maximum questions before stopping

        Returns:
            Tuple of (QualificationQuestion, selected_question_text) or None if done
        """
        # Don't over-qualify
        if len(self.data.questions_asked) >= max_questions_asked:
            return None

        # Get progress to know what we're missing
        progress = self.get_progress()

        # If minimally qualified, we can stop asking
        if progress.is_minimally_qualified and len(self.data.questions_asked) >= 3:
            return None

        # Find next question to ask
        candidates = self._get_candidate_questions(avoid_category)

        if not candidates:
            return None

        # Sort by priority and category order
        def sort_key(q: QualificationQuestion) -> Tuple[int, int]:
            priority = q.priority.value
            try:
                category_order = self.CATEGORY_ORDER.index(q.category)
            except ValueError:
                category_order = 99
            return (priority, category_order)

        candidates.sort(key=sort_key)

        # Select the best candidate
        selected = candidates[0]

        # Choose appropriate question variant
        if selected.id in self.data.questions_asked:
            # Use follow-up variant
            variants = selected.follow_up_variants or selected.question_variants
        else:
            variants = selected.question_variants

        # Select variant (could be randomized, but using first for consistency)
        import random
        question_text = random.choice(variants)

        # Track what we've asked
        if selected.id not in self.data.questions_asked:
            self.data.questions_asked.append(selected.id)
        self.data.last_question_category = selected.category.value
        self._last_category = selected.category

        return (selected, question_text)

    def _get_candidate_questions(
        self,
        avoid_category: Optional[QualificationCategory] = None,
    ) -> List[QualificationQuestion]:
        """Get list of questions we could ask next."""
        candidates = []

        for question in self.QUESTIONS.values():
            # Skip if we have the answer
            if self.data.has_value(question.data_key):
                continue

            # Skip if avoiding this category
            if avoid_category and question.category == avoid_category:
                continue

            # Skip if dependency not met
            if question.depends_on and not self.data.has_value(question.depends_on):
                continue

            # Skip if skip condition met
            if question.skip_if and self.data.has_value(question.skip_if):
                continue

            # Don't repeat the same category twice in a row (feels robotic)
            if (self._last_category == question.category and
                len(candidates) > 0):
                continue

            candidates.append(question)

        return candidates

    def get_progress(self) -> QualificationProgress:
        """
        Calculate current qualification progress.

        Returns:
            QualificationProgress with completion metrics
        """
        # Track what's complete by category
        completed: Set[QualificationCategory] = set()
        missing_critical: List[QualificationCategory] = []
        missing_high: List[QualificationCategory] = []

        # Check each category
        category_checks = {
            QualificationCategory.TIMELINE: self.data.has_value("timeline"),
            QualificationCategory.BUDGET: (self.data.has_value("budget") or
                                          self.data.has_value("budget_range_low")),
            QualificationCategory.LOCATION: self.data.has_value("location_preferences"),
            QualificationCategory.PRE_APPROVAL: self.data.has_value("is_pre_approved"),
            QualificationCategory.PROPERTY_TYPE: self.data.has_value("property_types"),
            QualificationCategory.MOTIVATION: self.data.has_value("motivation"),
            QualificationCategory.CURRENT_SITUATION: self.data.has_value("current_situation"),
            QualificationCategory.DECISION_MAKERS: self.data.has_value("decision_makers"),
        }

        for category, is_complete in category_checks.items():
            if is_complete:
                completed.add(category)
            else:
                # Check priority
                for q in self.QUESTIONS.values():
                    if q.category == category:
                        if q.priority == QualificationPriority.CRITICAL:
                            if category not in missing_critical:
                                missing_critical.append(category)
                        elif q.priority == QualificationPriority.HIGH:
                            if category not in missing_high:
                                missing_high.append(category)
                        break

        # Calculate metrics
        total = len(QualificationCategory)
        completed_count = len(completed)
        percentage = (completed_count / total) * 100

        critical_complete = len(missing_critical) == 0
        high_complete = len(missing_high) == 0

        # Determine next category
        next_category = None
        for cat in self.CATEGORY_ORDER:
            if cat not in completed:
                next_category = cat
                break

        # Minimally qualified = have critical info (timeline, budget, location)
        is_minimally_qualified = (
            self.data.has_value("timeline") and
            (self.data.has_value("budget") or self.data.has_value("budget_range_low") or
             self.data.is_pre_approved) and
            self.data.has_value("location_preferences")
        )

        # Fully qualified = have all high+ priority info
        is_fully_qualified = critical_complete and high_complete

        return QualificationProgress(
            total_categories=total,
            completed_categories=completed_count,
            critical_complete=critical_complete,
            high_complete=high_complete,
            overall_percentage=percentage,
            missing_critical=missing_critical,
            missing_high=missing_high,
            next_recommended_category=next_category,
            is_minimally_qualified=is_minimally_qualified,
            is_fully_qualified=is_fully_qualified,
        )

    def update_from_intent(
        self,
        intent_name: str,
        extracted_entities: List[Dict[str, Any]],
        raw_message: str,
    ) -> Dict[str, Any]:
        """
        Update qualification data from detected intent and entities.

        Args:
            intent_name: The detected intent
            extracted_entities: Entities extracted from the message
            raw_message: Original message text

        Returns:
            Dict of updated fields
        """
        updates = {}
        self.data.updated_at = datetime.utcnow()

        # Update from intent
        intent_updates = self._update_from_intent_name(intent_name, raw_message)
        updates.update(intent_updates)

        # Update from entities
        for entity in extracted_entities:
            entity_updates = self._update_from_entity(entity)
            updates.update(entity_updates)

        # Recalculate qualification score
        self.data.qualification_score = self._calculate_score()

        return updates

    def _update_from_intent_name(
        self,
        intent_name: str,
        raw_message: str,
    ) -> Dict[str, Any]:
        """Update data based on intent classification."""
        updates = {}

        # Timeline intents
        if intent_name == "timeline_immediate":
            self.data.timeline = "immediate"
            self.data.timeline_raw = raw_message
            updates["timeline"] = "immediate"
        elif intent_name == "timeline_short":
            self.data.timeline = "short"
            self.data.timeline_raw = raw_message
            updates["timeline"] = "short"
        elif intent_name == "timeline_medium":
            self.data.timeline = "medium"
            self.data.timeline_raw = raw_message
            updates["timeline"] = "medium"
        elif intent_name == "timeline_long":
            self.data.timeline = "long"
            self.data.timeline_raw = raw_message
            updates["timeline"] = "long"
        elif intent_name == "timeline_unknown":
            self.data.timeline = "unknown"
            self.data.timeline_raw = raw_message
            updates["timeline"] = "unknown"

        # Pre-approval intents
        elif intent_name == "budget_preapproved":
            self.data.is_pre_approved = True
            updates["is_pre_approved"] = True

        # Motivation intents
        elif intent_name.startswith("motivation_"):
            motivation = intent_name.replace("motivation_", "")
            self.data.motivation = motivation
            self.data.motivation_raw = raw_message
            updates["motivation"] = motivation

        return updates

    def _update_from_entity(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """Update data from an extracted entity."""
        updates = {}
        entity_type = entity.get("type", entity.get("entity_type", ""))
        value = entity.get("value")
        raw_text = entity.get("raw_text", "")

        if entity_type == "budget":
            if isinstance(value, (int, float)):
                self.data.budget = int(value)
                self.data.budget_raw = raw_text
                updates["budget"] = int(value)

        elif entity_type == "budget_range":
            if isinstance(value, dict):
                self.data.budget_range_low = value.get("low")
                self.data.budget_range_high = value.get("high")
                self.data.budget_raw = raw_text
                updates["budget_range"] = value

        elif entity_type == "location":
            if value and value not in self.data.location_preferences:
                self.data.location_preferences.append(value)
                updates["location_preferences"] = self.data.location_preferences

        elif entity_type == "property_type":
            if value and value not in self.data.property_types:
                self.data.property_types.append(value)
                updates["property_types"] = self.data.property_types

        return updates

    def _calculate_score(self) -> float:
        """Calculate overall qualification score (0-100)."""
        score = 0.0

        # Timeline (25 points)
        if self.data.timeline:
            if self.data.timeline == "immediate":
                score += 25
            elif self.data.timeline == "short":
                score += 20
            elif self.data.timeline == "medium":
                score += 12
            elif self.data.timeline == "long":
                score += 5
            elif self.data.timeline == "unknown":
                score += 3

        # Budget (25 points)
        if self.data.budget or self.data.budget_range_low:
            if self.data.is_pre_approved:
                score += 25  # Best case - pre-approved
            elif self.data.budget:
                score += 20  # Specific number
            elif self.data.budget_range_low:
                score += 15  # Has a range

        # Location (20 points)
        if self.data.location_preferences:
            if len(self.data.location_preferences) == 1:
                score += 20  # Focused on specific area
            elif len(self.data.location_preferences) <= 3:
                score += 15  # Few areas
            else:
                score += 10  # Many areas (less serious)

        # Property type (10 points)
        if self.data.property_types:
            score += 10

        # Motivation (10 points)
        if self.data.motivation:
            # Some motivations indicate more urgency
            urgent_motivations = ["job", "family", "downsize"]
            if self.data.motivation in urgent_motivations:
                score += 10
            else:
                score += 7

        # Current situation (5 points)
        if self.data.current_situation:
            score += 5

        # Decision makers (5 points)
        if self.data.decision_makers:
            score += 5

        return min(score, 100.0)

    def get_summary(self) -> str:
        """Get a text summary of qualification status."""
        progress = self.get_progress()

        parts = []

        if self.data.timeline:
            timeline_labels = {
                "immediate": "Ready now",
                "short": "1-3 months",
                "medium": "3-6 months",
                "long": "6+ months",
                "unknown": "Just browsing",
            }
            parts.append(f"Timeline: {timeline_labels.get(self.data.timeline, self.data.timeline)}")

        if self.data.budget:
            parts.append(f"Budget: ${self.data.budget:,}")
        elif self.data.budget_range_low:
            parts.append(f"Budget: ${self.data.budget_range_low:,} - ${self.data.budget_range_high:,}")

        if self.data.is_pre_approved:
            parts.append("Pre-approved: Yes")

        if self.data.location_preferences:
            parts.append(f"Areas: {', '.join(self.data.location_preferences)}")

        if self.data.property_types:
            parts.append(f"Property types: {', '.join(self.data.property_types)}")

        if self.data.motivation:
            parts.append(f"Motivation: {self.data.motivation}")

        parts.append(f"Score: {self.data.qualification_score:.0f}/100")
        parts.append(f"Progress: {progress.overall_percentage:.0f}%")

        return " | ".join(parts)

    def should_continue_qualifying(self) -> bool:
        """Determine if we should continue asking qualification questions."""
        progress = self.get_progress()

        # Always try to get critical info
        if not progress.critical_complete:
            return True

        # If we've asked a lot already, stop (configurable via max_qualification_questions setting)
        max_questions = getattr(self, 'max_qualification_questions', 8)
        if len(self.data.questions_asked) >= max_questions:
            return False

        # If minimally qualified and asked at least 3, can stop
        if progress.is_minimally_qualified and len(self.data.questions_asked) >= 3:
            return False

        # Otherwise, continue until high priority is complete
        return not progress.high_complete

    def get_context_for_ai(self) -> Dict[str, Any]:
        """Get qualification context for AI response generation."""
        progress = self.get_progress()

        return {
            "qualification_data": self.data.to_dict(),
            "qualification_score": self.data.qualification_score,
            "is_minimally_qualified": progress.is_minimally_qualified,
            "is_fully_qualified": progress.is_fully_qualified,
            "missing_critical": [c.value for c in progress.missing_critical],
            "missing_high": [c.value for c in progress.missing_high],
            "next_category": progress.next_recommended_category.value
                if progress.next_recommended_category else None,
            "questions_asked_count": len(self.data.questions_asked),
            "should_continue_qualifying": self.should_continue_qualifying(),
        }


class SmartQuestionSelector:
    """
    Advanced question selection with contextual awareness.

    Selects questions based on:
    - Conversation flow
    - Lead engagement signals
    - What naturally fits the conversation
    """

    def __init__(self, flow_manager: QualificationFlowManager):
        self.flow = flow_manager

    def get_contextual_question(
        self,
        last_message: str,
        last_intent: str,
        conversation_turn: int,
    ) -> Optional[Tuple[str, str]]:
        """
        Get a question that fits naturally in the current conversation.

        Returns:
            Tuple of (question_id, question_text) or None
        """
        # Early in conversation - ask about timeline first
        if conversation_turn <= 2 and not self.flow.data.has_value("timeline"):
            q = QualificationFlowManager.QUESTIONS.get("timeline_general")
            if q:
                import random
                return (q.id, random.choice(q.question_variants))

        # If they mentioned money/budget, ask about pre-approval
        if "budget" in last_intent.lower() or "preapproved" in last_intent.lower():
            if not self.flow.data.has_value("is_pre_approved"):
                q = QualificationFlowManager.QUESTIONS.get("pre_approval")
                if q:
                    import random
                    return (q.id, random.choice(q.question_variants))

        # If they mentioned a location, ask about property type
        if "location" in last_intent.lower() and self.flow.data.location_preferences:
            if not self.flow.data.has_value("property_types"):
                q = QualificationFlowManager.QUESTIONS.get("property_type")
                if q:
                    import random
                    return (q.id, random.choice(q.question_variants))

        # Default: use flow manager's selection
        result = self.flow.get_next_question()
        if result:
            question, text = result
            return (question.id, text)

        return None

    def should_ask_question_now(
        self,
        last_intent: str,
        sentiment: str,
        conversation_turn: int,
    ) -> bool:
        """
        Determine if now is a good time to ask a qualification question.

        Don't ask if:
        - Lead is frustrated/negative
        - Just asked a question (let them respond)
        - Already very well qualified
        """
        # Don't ask if negative sentiment
        if sentiment == "negative":
            return False

        # Don't ask if lead just asked a question (answer it first)
        if last_intent == "question":
            return False

        # Don't ask if they want to schedule (move to that)
        if "appointment" in last_intent.lower() or "schedule" in last_intent.lower():
            return False

        # Early conversation - always try to qualify
        if conversation_turn <= 5:
            return True

        # Later - only if still need critical info
        progress = self.flow.get_progress()
        return not progress.critical_complete
