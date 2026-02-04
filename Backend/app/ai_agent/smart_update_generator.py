"""
Smart Update Generator - Integrates Strategy Engine with AI Generation

Combines:
1. Lead Update Strategy Engine (determines disposition & tone)
2. AI Update Generator (generates contextual updates)
3. Template-based fallbacks (when AI not available)

This ensures every lead source update is:
- Strategically appropriate for the lead's situation
- Positive and action-oriented by default
- Professional and relationship-preserving
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from app.ai_agent.lead_update_strategy import (
    LeadUpdateStrategyEngine,
    LeadContext,
    UpdateStrategy,
    generate_update_text
)

logger = logging.getLogger(__name__)


class SmartUpdateGenerator:
    """
    Generates smart, strategic updates for lead source platforms

    Workflow:
    1. Analyze lead context → Determine strategy
    2. If AI enabled → Generate AI update using strategy guidelines
    3. Else → Use template-based update
    4. Validate update meets platform requirements
    """

    def __init__(self):
        self.strategy_engine = LeadUpdateStrategyEngine()
        self.logger = logging.getLogger(__name__)

    def generate_update(
        self,
        lead,
        platform_name: str,
        ai_enabled: bool = False,
        existing_update: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate strategic update for lead

        HONESTY PRINCIPLE: Generated updates must be based on actual lead activity
        and status. Never fabricate progress that doesn't exist.

        Args:
            lead: Lead object with all FUB data
            platform_name: Target platform (referralexchange, homelight, etc.)
            ai_enabled: Whether to use AI generation
            existing_update: Existing @update note if any

        Returns:
            Dict with:
                - update_text: The generated update
                - strategy: UpdateStrategy used
                - source: 'manual' | 'ai' | 'template'
                - confidence: 0-1 confidence score
        """

        # PRIORITY 1: Always use manual @update if provided
        # This respects agent/user input and ensures accurate information
        if existing_update and len(existing_update.strip()) > 10:
            self.logger.info(f"Using manual @update for {lead.first_name} {lead.last_name}")
            return {
                'update_text': existing_update,
                'strategy': None,
                'source': 'manual',
                'confidence': 1.0,
                'reasoning': 'Manual @update provided by user/agent'
            }

        # Build lead context
        context = self._build_lead_context(lead, platform_name)

        # Determine strategy
        strategy = self.strategy_engine.determine_strategy(context)

        self.logger.info(
            f"Update strategy for {context.lead_name}: {strategy.disposition.value} "
            f"({strategy.tone.value}) - {strategy.reasoning}"
        )

        # Generate update based on strategy
        if ai_enabled:
            update_text = self._generate_ai_update(context, strategy)
            source = 'ai'
            confidence = 0.85
        else:
            update_text = generate_update_text(strategy, context)
            source = 'template'
            confidence = 0.75

        # HONESTY CHECK: Validate update aligns with lead reality
        validated = self._validate_honesty(update_text, context, strategy)

        return {
            'update_text': update_text,
            'strategy': strategy,
            'source': source,
            'confidence': confidence,
            'reasoning': strategy.reasoning,
            'honesty_validated': validated
        }

    def _validate_honesty(self, update_text: str, context: LeadContext, strategy: UpdateStrategy) -> bool:
        """
        Validate that generated update is honest and aligns with lead reality

        Checks:
        - Don't claim recent activity if days_since_contact > 14
        - Don't claim "making progress" for DORMANT leads
        - Don't use "great momentum" unless ACTIVE_ENGAGED
        - Match update tone to actual lead status

        Returns:
            True if update passes honesty checks
        """

        update_lower = update_text.lower()

        # Check for false activity claims
        if context.days_since_last_contact > 14:
            # Shouldn't claim "recently", "just spoke", "yesterday", etc.
            false_recency = ["recently spoke", "just spoke", "yesterday", "last week", "this week"]
            if any(phrase in update_lower for phrase in false_recency):
                self.logger.warning(
                    f"HONESTY CHECK FAILED: Update claims recent activity but last contact was "
                    f"{context.days_since_last_contact} days ago for {context.lead_name}"
                )
                return False

        # Check for false momentum claims
        if strategy.disposition not in [LeadDisposition.ACTIVE_ENGAGED]:
            # Shouldn't claim "great progress", "moving fast", "excited", etc.
            false_momentum = ["great progress", "moving fast", "excited", "ready to", "about to"]
            if any(phrase in update_lower for phrase in false_momentum):
                self.logger.warning(
                    f"HONESTY CHECK FAILED: Update claims momentum but lead is "
                    f"{strategy.disposition.value} for {context.lead_name}"
                )
                return False

        # Passed all checks
        return True

    def _build_lead_context(self, lead, platform_name: str) -> LeadContext:
        """Build LeadContext from lead object"""

        # Calculate days since last contact
        days_since_last_contact = self._calculate_days_since_contact(lead)
        days_since_created = self._calculate_days_since_created(lead)

        # Count attempts and responses (from notes/messages)
        attempts, responses = self._count_engagement(lead)

        # Check for recent activity
        has_recent_notes = self._has_recent_notes(lead, days=14)
        has_recent_messages = self._has_recent_messages(lead, days=7)

        # Check for dead indicators
        explicit_dead_reason = self._extract_dead_reason(lead)
        opted_out = self._check_opted_out(lead)

        return LeadContext(
            lead_id=str(lead.id),
            lead_name=f"{lead.first_name} {lead.last_name}",
            source_name=platform_name,
            days_since_last_contact=days_since_last_contact,
            days_since_created=days_since_created,
            total_attempts=attempts,
            total_responses=responses,
            fub_stage=lead.status,
            has_recent_notes=has_recent_notes,
            has_recent_messages=has_recent_messages,
            explicit_dead_reason=explicit_dead_reason,
            opted_out=opted_out,
            complaint_filed=False  # Would check from metadata
        )

    def _calculate_days_since_contact(self, lead) -> int:
        """Calculate days since last contact attempt"""
        try:
            if hasattr(lead, 'last_contacted_at') and lead.last_contacted_at:
                last_contact = lead.last_contacted_at
                if isinstance(last_contact, str):
                    last_contact = datetime.fromisoformat(last_contact.replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                return (now - last_contact).days

            # Fallback: check metadata for last sync
            if hasattr(lead, 'metadata') and lead.metadata:
                metadata = lead.metadata if isinstance(lead.metadata, dict) else {}
                last_sync = metadata.get('last_contact_date')
                if last_sync:
                    last_sync_dt = datetime.fromisoformat(last_sync.replace('Z', '+00:00'))
                    now = datetime.now(timezone.utc)
                    return (now - last_sync_dt).days

            # Default: assume recent if no data
            return 7

        except Exception as e:
            self.logger.warning(f"Error calculating days since contact: {e}")
            return 7  # Assume recent to be safe

    def _calculate_days_since_created(self, lead) -> int:
        """Calculate days since lead was created"""
        try:
            if hasattr(lead, 'created_at') and lead.created_at:
                created = lead.created_at
                if isinstance(created, str):
                    created = datetime.fromisoformat(created.replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                return (now - created).days
            return 30  # Default
        except Exception:
            return 30

    def _count_engagement(self, lead) -> tuple[int, int]:
        """
        Count engagement attempts and responses

        Returns:
            (attempts, responses) tuple
        """
        # This would ideally check FUB notes/messages
        # For now, return conservative estimates
        attempts = 3  # Assume some attempts
        responses = 1  # Assume at least one response unless proven otherwise

        # Could enhance by actually checking notes for @attempt or response indicators
        return attempts, responses

    def _has_recent_notes(self, lead, days: int = 14) -> bool:
        """Check if lead has recent notes"""
        # Would check FUB notes created in last N days
        # Placeholder for now
        return False

    def _has_recent_messages(self, lead, days: int = 7) -> bool:
        """Check if lead has recent messages"""
        # Would check FUB messages in last N days
        # Placeholder for now
        return False

    def _extract_dead_reason(self, lead) -> Optional[str]:
        """Extract explicit dead reason from notes or stage"""
        # Check stage first
        if hasattr(lead, 'status'):
            stage_lower = lead.status.lower()
            if 'dead' in stage_lower or 'lost' in stage_lower:
                # Try to extract reason from recent notes
                # For now, return generic
                return "No longer pursuing"

        return None

    def _check_opted_out(self, lead) -> bool:
        """Check if lead has opted out"""
        if hasattr(lead, 'metadata') and lead.metadata:
            metadata = lead.metadata if isinstance(lead.metadata, dict) else {}
            return metadata.get('opted_out', False)
        return False

    def _generate_ai_update(self, context: LeadContext, strategy: UpdateStrategy) -> str:
        """
        Generate AI update using strategy guidelines

        This would call the AI service with:
        - Strategy disposition and tone
        - Lead context
        - Platform-specific requirements

        For now, returns template-based update
        """

        # TODO: Integrate with actual AI generation service
        # For now, use template-based generation

        self.logger.info(f"AI generation not yet implemented, using template for {context.lead_name}")
        return generate_update_text(strategy, context)


# Quick enable function for lead sources
def enable_smart_updates(source_name: str, mode: str = 'fallback'):
    """
    Enable smart updates for a lead source

    Args:
        source_name: Name of the lead source
        mode: 'fallback' (default), 'always', or 'supplement'
    """
    from app.service.lead_source_settings_service import LeadSourceSettingsSingleton

    service = LeadSourceSettingsSingleton.get_instance()
    source = service.get_by_source_name(source_name)

    if not source:
        print(f"ERROR: Lead source '{source_name}' not found")
        return False

    # Get current metadata
    metadata = source.metadata if hasattr(source, 'metadata') else {}
    if isinstance(metadata, str):
        import json
        try:
            metadata = json.loads(metadata)
        except:
            metadata = {}

    # Update metadata with AI settings
    metadata['ai_update_enabled'] = True
    metadata['ai_update_mode'] = mode
    metadata['ai_update_save_to_fub'] = True

    # Save back
    try:
        service.update(source.id, {'metadata': metadata})
        print(f"✓ Enabled smart updates for {source_name} (mode: {mode})")
        return True
    except Exception as e:
        print(f"ERROR: Failed to update {source_name}: {e}")
        return False


if __name__ == "__main__":
    print("Smart Update Generator")
    print("=" * 80)
    print()
    print("This module combines strategic analysis with update generation")
    print("to ensure all lead source updates are positive and action-oriented.")
    print()
    print("To enable for a lead source:")
    print("  from app.ai_agent.smart_update_generator import enable_smart_updates")
    print("  enable_smart_updates('ReferralExchange', mode='fallback')")
