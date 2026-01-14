"""
Lead Scorer - Scoring system for real estate leads.

Scoring criteria (0-100 scale):
- Pre-approved: +25 points
- Timeline: +25 points max (based on urgency)
- Engagement: +20 points (replies, questions, interest)
- Budget clarity: +15 points
- Motivation: +15 points (clear reason for moving)

Lead Categories:
- Hot (70-100): Ready to transact, prioritize immediately
- Warm (40-69): Interested but not urgent, nurture weekly
- Cold (<40): Long timeline or low engagement, monthly drip
"""

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class LeadTemperature(Enum):
    """Lead temperature classification."""
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


@dataclass
class LeadScore:
    """Detailed lead score breakdown."""
    total: int
    temperature: LeadTemperature
    pre_approved_score: int = 0
    timeline_score: int = 0
    engagement_score: int = 0
    budget_score: int = 0
    motivation_score: int = 0

    # Bonus/penalty adjustments
    adjustments: List[Tuple[str, int]] = None

    def __post_init__(self):
        if self.adjustments is None:
            self.adjustments = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "temperature": self.temperature.value,
            "breakdown": {
                "pre_approved": self.pre_approved_score,
                "timeline": self.timeline_score,
                "engagement": self.engagement_score,
                "budget": self.budget_score,
                "motivation": self.motivation_score,
            },
            "adjustments": self.adjustments,
        }


class LeadScorer:
    """
    Scores leads based on qualification criteria.

    Score Components (max 100):
    - Pre-approval status: 0-25 points
    - Timeline urgency: 0-25 points
    - Engagement level: 0-20 points
    - Budget clarity: 0-15 points
    - Motivation clarity: 0-15 points
    """

    # Score weights
    MAX_PREAPPROVAL = 25
    MAX_TIMELINE = 25
    MAX_ENGAGEMENT = 20
    MAX_BUDGET = 15
    MAX_MOTIVATION = 15

    # Temperature thresholds
    HOT_THRESHOLD = 70
    WARM_THRESHOLD = 40

    # Timeline scoring
    TIMELINE_SCORES = {
        "immediately": 25,
        "asap": 25,
        "30_days": 25,
        "1_month": 25,
        "60_days": 20,
        "2_months": 20,
        "60_90_days": 15,
        "90_days": 15,
        "3_months": 15,
        "3_6_months": 10,
        "6_months": 10,
        "6_months_plus": 5,
        "1_year": 5,
        "just_browsing": 0,
        "not_sure": 5,
        "unknown": 0,
    }

    # Motivation scoring
    MOTIVATION_SCORES = {
        "job_relocation": 15,
        "job_transfer": 15,
        "growing_family": 12,
        "downsizing": 12,
        "divorce": 15,  # High urgency
        "estate_sale": 15,  # High urgency
        "investment": 10,
        "first_time_buyer": 10,
        "upgrading": 10,
        "retiring": 8,
        "relocating": 12,
        "military_transfer": 15,  # High urgency
        "just_looking": 3,
        "unknown": 0,
    }

    def __init__(self):
        """Initialize the lead scorer."""
        pass

    def calculate_score(
        self,
        pre_approved: Optional[bool] = None,
        timeline: Optional[str] = None,
        budget: Optional[str] = None,
        motivation: Optional[str] = None,
        engagement_signals: Optional[Dict[str, Any]] = None,
        existing_score: int = 0,
    ) -> LeadScore:
        """
        Calculate comprehensive lead score.

        Args:
            pre_approved: Whether lead is pre-approved for financing
            timeline: Timeline string (e.g., "30_days", "6_months_plus")
            budget: Budget string (e.g., "$300k-$400k")
            motivation: Motivation for moving
            engagement_signals: Dict with engagement indicators
            existing_score: Starting score to adjust from

        Returns:
            LeadScore with detailed breakdown
        """
        adjustments = []

        # Pre-approval score
        pre_approved_score = 0
        if pre_approved is True:
            pre_approved_score = self.MAX_PREAPPROVAL
        elif pre_approved is False:
            pre_approved_score = 5  # At least they answered
        # None = unknown = 0

        # Timeline score
        timeline_score = 0
        if timeline:
            timeline_normalized = self._normalize_timeline(timeline)
            timeline_score = self.TIMELINE_SCORES.get(timeline_normalized, 5)

        # Budget score
        budget_score = 0
        if budget:
            budget_score = self._calculate_budget_score(budget)

        # Motivation score
        motivation_score = 0
        if motivation:
            motivation_normalized = self._normalize_motivation(motivation)
            motivation_score = self.MOTIVATION_SCORES.get(motivation_normalized, 5)

        # Engagement score
        engagement_score = 0
        if engagement_signals:
            engagement_score = self._calculate_engagement_score(engagement_signals)

        # Calculate base total
        total = (
            pre_approved_score +
            timeline_score +
            engagement_score +
            budget_score +
            motivation_score
        )

        # Apply adjustments
        for reason, points in adjustments:
            total += points

        # Clamp to 0-100
        total = max(0, min(100, total))

        # Determine temperature
        if total >= self.HOT_THRESHOLD:
            temperature = LeadTemperature.HOT
        elif total >= self.WARM_THRESHOLD:
            temperature = LeadTemperature.WARM
        else:
            temperature = LeadTemperature.COLD

        return LeadScore(
            total=total,
            temperature=temperature,
            pre_approved_score=pre_approved_score,
            timeline_score=timeline_score,
            engagement_score=engagement_score,
            budget_score=budget_score,
            motivation_score=motivation_score,
            adjustments=adjustments,
        )

    def update_score(
        self,
        current_score: int,
        delta: int,
        reason: str = None,
    ) -> Tuple[int, LeadTemperature]:
        """
        Update an existing score with a delta.

        Args:
            current_score: Current lead score
            delta: Points to add (positive) or subtract (negative)
            reason: Optional reason for the adjustment

        Returns:
            Tuple of (new_score, new_temperature)
        """
        new_score = max(0, min(100, current_score + delta))

        if new_score >= self.HOT_THRESHOLD:
            temperature = LeadTemperature.HOT
        elif new_score >= self.WARM_THRESHOLD:
            temperature = LeadTemperature.WARM
        else:
            temperature = LeadTemperature.COLD

        if reason:
            logger.info(f"Score updated: {current_score} -> {new_score} ({delta:+d}) - {reason}")

        return new_score, temperature

    def _normalize_timeline(self, timeline: str) -> str:
        """Normalize timeline string to standard format."""
        timeline = timeline.lower().strip()

        # Direct mappings
        if "immediate" in timeline or "asap" in timeline or "right away" in timeline:
            return "immediately"
        if "30 day" in timeline or "1 month" in timeline or "month" in timeline and "1" in timeline:
            return "30_days"
        if "60 day" in timeline or "2 month" in timeline:
            return "60_days"
        if "90 day" in timeline or "3 month" in timeline or "60-90" in timeline or "60 to 90" in timeline:
            return "60_90_days"
        if "6 month" in timeline or "half year" in timeline:
            return "6_months"
        if "year" in timeline or "12 month" in timeline:
            return "1_year"
        if "brows" in timeline or "looking" in timeline or "just" in timeline:
            return "just_browsing"
        if "not sure" in timeline or "don't know" in timeline or "unsure" in timeline:
            return "not_sure"

        # Check for any month mention
        import re
        month_match = re.search(r'(\d+)\s*month', timeline)
        if month_match:
            months = int(month_match.group(1))
            if months <= 1:
                return "30_days"
            elif months <= 2:
                return "60_days"
            elif months <= 3:
                return "90_days"
            elif months <= 6:
                return "3_6_months"
            else:
                return "6_months_plus"

        return "unknown"

    def _normalize_motivation(self, motivation: str) -> str:
        """Normalize motivation string to standard format."""
        motivation = motivation.lower().strip()

        if "job" in motivation or "work" in motivation or "career" in motivation:
            if "transfer" in motivation:
                return "job_transfer"
            return "job_relocation"
        if "family" in motivation or "baby" in motivation or "kids" in motivation or "room" in motivation:
            return "growing_family"
        if "downsize" in motivation or "smaller" in motivation or "retire" in motivation:
            if "retire" in motivation:
                return "retiring"
            return "downsizing"
        if "divorce" in motivation or "separat" in motivation:
            return "divorce"
        if "estate" in motivation or "inherit" in motivation or "passed" in motivation:
            return "estate_sale"
        if "invest" in motivation or "rental" in motivation or "property" in motivation:
            return "investment"
        if "first" in motivation or "never" in motivation:
            return "first_time_buyer"
        if "upgrade" in motivation or "bigger" in motivation or "more space" in motivation:
            return "upgrading"
        if "military" in motivation or "pcs" in motivation:
            return "military_transfer"
        if "relocat" in motivation or "moving" in motivation:
            return "relocating"
        if "just looking" in motivation or "browsing" in motivation:
            return "just_looking"

        return "unknown"

    def _calculate_budget_score(self, budget: str) -> int:
        """Calculate score based on budget clarity."""
        budget = budget.lower().strip()

        # Clear specific range = full points
        if "$" in budget or "k" in budget or any(c.isdigit() for c in budget):
            # Has specific numbers
            if "-" in budget or "to" in budget:
                return self.MAX_BUDGET  # Clear range
            return 12  # Single number

        # Vague but present
        if budget and budget not in ["unknown", "not sure", "don't know"]:
            return 8

        return 0

    def _calculate_engagement_score(self, signals: Dict[str, Any]) -> int:
        """
        Calculate engagement score from various signals.

        Signals can include:
        - reply_count: Number of replies from lead
        - questions_asked: Number of questions lead asked
        - positive_sentiment: Boolean or count
        - link_clicks: Number of links clicked
        - email_opens: Number of emails opened
        - response_speed: How fast they reply (seconds)
        """
        score = 0

        # Replies indicate engagement
        reply_count = signals.get("reply_count", 0)
        if reply_count >= 3:
            score += 10
        elif reply_count >= 1:
            score += 5

        # Questions show interest
        questions = signals.get("questions_asked", 0)
        if questions >= 2:
            score += 5
        elif questions >= 1:
            score += 3

        # Positive sentiment
        if signals.get("positive_sentiment"):
            score += 3

        # Fast response time (under 5 minutes)
        response_speed = signals.get("response_speed")
        if response_speed and response_speed < 300:
            score += 2

        return min(score, self.MAX_ENGAGEMENT)

    def get_score_explanation(self, score: LeadScore) -> str:
        """Generate human-readable explanation of score."""
        explanations = []

        if score.pre_approved_score > 0:
            if score.pre_approved_score == self.MAX_PREAPPROVAL:
                explanations.append("Pre-approved for financing (+25)")
            else:
                explanations.append(f"Financing status discussed (+{score.pre_approved_score})")

        if score.timeline_score > 0:
            urgency = "urgent" if score.timeline_score >= 20 else "moderate" if score.timeline_score >= 10 else "relaxed"
            explanations.append(f"Timeline urgency: {urgency} (+{score.timeline_score})")

        if score.budget_score > 0:
            clarity = "clear" if score.budget_score >= 12 else "somewhat clear"
            explanations.append(f"Budget {clarity} (+{score.budget_score})")

        if score.motivation_score > 0:
            explanations.append(f"Clear motivation (+{score.motivation_score})")

        if score.engagement_score > 0:
            explanations.append(f"Engaged in conversation (+{score.engagement_score})")

        for reason, points in score.adjustments:
            explanations.append(f"{reason} ({points:+d})")

        return f"{score.temperature.value.upper()} lead ({score.total}/100): " + "; ".join(explanations)


# Convenience functions
def calculate_lead_score(**kwargs) -> LeadScore:
    """Calculate lead score with default scorer."""
    scorer = LeadScorer()
    return scorer.calculate_score(**kwargs)


def get_lead_temperature(score: int) -> LeadTemperature:
    """Get lead temperature from score."""
    if score >= LeadScorer.HOT_THRESHOLD:
        return LeadTemperature.HOT
    elif score >= LeadScorer.WARM_THRESHOLD:
        return LeadTemperature.WARM
    return LeadTemperature.COLD
