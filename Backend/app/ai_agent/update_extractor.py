"""
Manual Update Extractor

Extracts @update notes from FUB notes to ensure manual updates
are always prioritized over auto-generated ones.

This respects the agent's/user's explicit instructions and ensures
accuracy by using their own words when they've provided them.
"""

import logging
import re
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


class UpdateExtractor:
    """
    Extracts manual @update notes from FUB notes

    Looks for:
    - @update tag in recent notes
    - Most recent @update within 30 days
    - Validates update is still relevant
    """

    UPDATE_TAG_PATTERN = r'@update\s+(.+?)(?=@|$)'
    MAX_AGE_DAYS = 30  # Only use @updates from last 30 days

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def extract_latest_update(self, lead, fub_notes: Optional[List[Dict]] = None) -> Optional[str]:
        """
        Extract the most recent @update note for a lead

        Args:
            lead: Lead object
            fub_notes: Optional pre-fetched FUB notes (list of dicts with 'body', 'created')

        Returns:
            Update text if found, None otherwise
        """

        # If notes not provided, try to get from lead
        if fub_notes is None:
            fub_notes = self._get_fub_notes(lead)

        if not fub_notes:
            return None

        # Look for @update in recent notes (newest first)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.MAX_AGE_DAYS)

        for note in fub_notes:
            # Check note age
            created = self._parse_date(note.get('created'))
            if created and created < cutoff_date:
                continue  # Too old

            # Check for @update tag
            body = note.get('body', '')
            match = re.search(self.UPDATE_TAG_PATTERN, body, re.DOTALL | re.IGNORECASE)

            if match:
                update_text = match.group(1).strip()

                # Validate it's substantial
                if len(update_text) > 10:
                    self.logger.info(
                        f"Found manual @update for {lead.first_name} {lead.last_name}: "
                        f"{update_text[:50]}..."
                    )
                    return self._clean_update_text(update_text)

        return None

    def _get_fub_notes(self, lead) -> List[Dict]:
        """Get FUB notes for lead"""
        try:
            # Try to get from lead metadata/cache first
            if hasattr(lead, 'metadata') and lead.metadata:
                cached_notes = lead.metadata.get('cached_notes')
                if cached_notes:
                    return cached_notes

            # Otherwise would call FUB API
            # from app.database.fub_api_client import FUBApiClient
            # client = FUBApiClient()
            # notes = client.get_notes(lead.fub_person_id)
            # return notes

            return []

        except Exception as e:
            self.logger.error(f"Error getting FUB notes: {e}")
            return []

    def _parse_date(self, date_str: Any) -> Optional[datetime]:
        """Parse date string to datetime"""
        if isinstance(date_str, datetime):
            return date_str

        if isinstance(date_str, str):
            try:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except:
                pass

        return None

    def _clean_update_text(self, text: str) -> str:
        """
        Clean up extracted update text

        - Remove extra whitespace
        - Remove markdown/formatting
        - Truncate if too long
        - Remove any remaining @ tags
        """

        # Remove line breaks, normalize whitespace
        text = ' '.join(text.split())

        # Remove any other @ tags that might be inline
        text = re.sub(r'@\w+', '', text)

        # Truncate if needed (platform limits usually ~500 chars)
        if len(text) > 400:
            text = text[:397] + "..."

        return text.strip()

    def extract_from_note_text(self, note_text: str) -> Optional[str]:
        """
        Extract @update from a single note text

        Useful for parsing individual notes without full lead context

        Args:
            note_text: Raw note text that may contain @update

        Returns:
            Extracted update text or None
        """

        match = re.search(self.UPDATE_TAG_PATTERN, note_text, re.DOTALL | re.IGNORECASE)
        if match:
            return self._clean_update_text(match.group(1))
        return None


# Convenience function
def get_manual_update(lead, fub_notes: Optional[List[Dict]] = None) -> Optional[str]:
    """
    Quick function to get manual update for a lead

    Usage:
        from app.ai_agent.update_extractor import get_manual_update

        manual_update = get_manual_update(lead)
        if manual_update:
            # Use manual update
        else:
            # Generate auto update
    """
    extractor = UpdateExtractor()
    return extractor.extract_latest_update(lead, fub_notes)


# Test examples
if __name__ == "__main__":
    print("Update Extractor - Test Cases")
    print("=" * 80)
    print()

    extractor = UpdateExtractor()

    # Test case 1: Simple @update
    note1 = "@update Lead is ready to view properties this weekend. Sending listings tonight."
    result1 = extractor.extract_from_note_text(note1)
    print(f"Test 1: {result1}")
    print()

    # Test case 2: @update with other tags
    note2 = "@attempt Called but no answer. @update Will try again tomorrow with text message."
    result2 = extractor.extract_from_note_text(note2)
    print(f"Test 2: {result2}")
    print()

    # Test case 3: No @update
    note3 = "Called lead, left voicemail with my contact info."
    result3 = extractor.extract_from_note_text(note3)
    print(f"Test 3: {result3 or 'None (correctly found no @update)'}")
    print()

    # Test case 4: Multi-line @update
    note4 = """
    @update Lead expressed interest in downtown condos. Budget is 400-500k.
    Planning to send MLS listings matching their criteria. Will follow up Friday.
    """
    result4 = extractor.extract_from_note_text(note4)
    print(f"Test 4: {result4}")
    print()

    print("=" * 80)
    print("All tests complete!")
