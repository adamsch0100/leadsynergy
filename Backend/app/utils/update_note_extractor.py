"""
Utility for extracting @update: messages from FUB notes for platform sync.

When agents add notes with @update: prefix, this content is extracted
and sent to external lead source platforms during sync operations.

Example note:
    @update: Client prefers south side properties near downtown. Budget increased to $450k.

This message would be sent as the comment field to ReferralExchange, AgentPronto, HomeLight.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from html import unescape


class UpdateNoteExtractor:
    """Extracts @update: messages from FUB notes for platform sync."""

    # Pattern to match @update: followed by content (case-insensitive)
    # Captures everything after @update: until the next @update: or end of string
    MARKER_PATTERN = re.compile(
        r'@update:\s*(.+?)(?=@update:|$)',
        re.IGNORECASE | re.DOTALL
    )

    # HTML tag pattern for stripping
    HTML_TAG_PATTERN = re.compile(r'<[^>]+>')

    # Maximum length for update messages
    MAX_MESSAGE_LENGTH = 500

    def __init__(self, fub_client=None):
        """
        Initialize the extractor.

        Args:
            fub_client: Optional FUBApiClient instance for fetching notes
        """
        self.fub_client = fub_client

    def extract_update_messages(self, notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract all @update messages from a list of notes.

        Args:
            notes: List of note dicts from FUB API with keys like 'id', 'body', 'created'

        Returns:
            List of dicts with keys: note_id, message, created_at
            Sorted by created_at descending (most recent first)
        """
        updates = []

        for note in notes:
            note_id = note.get('id')
            body = note.get('body', '')
            created_at = note.get('created')

            if not body:
                continue

            message = self.parse_update_from_body(body)
            if message:
                updates.append({
                    'note_id': note_id,
                    'message': message,
                    'created_at': created_at
                })

        # Sort by created_at descending (most recent first)
        updates.sort(
            key=lambda x: x.get('created_at') or '',
            reverse=True
        )

        return updates

    def get_most_recent_update(
        self,
        notes: List[Dict[str, Any]],
        since_timestamp: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get the most recent @update message from notes.

        Args:
            notes: List of note dicts from FUB API
            since_timestamp: Only consider notes created after this ISO timestamp

        Returns:
            Dict with note_id, message, created_at or None if no @update found
        """
        updates = self.extract_update_messages(notes)

        if not updates:
            return None

        # Filter by timestamp if provided
        if since_timestamp:
            updates = [
                u for u in updates
                if u.get('created_at') and u['created_at'] > since_timestamp
            ]

        return updates[0] if updates else None

    def get_update_for_platform(
        self,
        notes: List[Dict[str, Any]],
        platform_name: str,
        lead_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Get @update message for a specific platform, respecting last sync timestamp.

        Args:
            notes: List of note dicts from FUB API
            platform_name: Platform identifier (e.g., 'referralexchange', 'homelight')
            lead_metadata: Lead's metadata dict containing sync timestamps

        Returns:
            The @update message string or None if no new update found
        """
        # Get last sync timestamp for this platform
        since_timestamp = None
        if lead_metadata:
            sync_info = lead_metadata.get('last_update_note_synced', {})
            since_timestamp = sync_info.get(f'{platform_name}_timestamp')

        update = self.get_most_recent_update(notes, since_timestamp)

        if update:
            return update['message']
        return None

    def parse_update_from_body(self, body: str) -> Optional[str]:
        """
        Parse @update: content from a note body.

        Handles:
        - HTML content (strips tags)
        - Multiple @update markers (returns the last one)
        - HTML entities (unescapes them)
        - Truncates long messages

        Args:
            body: Note body text (may contain HTML)

        Returns:
            Extracted message string or None if no @update found
        """
        if not body:
            return None

        # Strip HTML tags
        clean_body = self.HTML_TAG_PATTERN.sub(' ', body)

        # Unescape HTML entities
        clean_body = unescape(clean_body)

        # Normalize whitespace
        clean_body = ' '.join(clean_body.split())

        # Find all @update matches
        matches = self.MARKER_PATTERN.findall(clean_body)

        if not matches:
            return None

        # Use the last match (most recent intent if multiple in same note)
        message = matches[-1].strip()

        if not message:
            return None

        # Truncate if too long
        if len(message) > self.MAX_MESSAGE_LENGTH:
            message = message[:self.MAX_MESSAGE_LENGTH - 3] + '...'

        return message

    @staticmethod
    def get_sync_timestamp_key(platform_name: str) -> str:
        """Get the metadata key for storing sync timestamp for a platform."""
        return f'{platform_name.lower()}_timestamp'

    @staticmethod
    def build_sync_metadata_update(
        platform_name: str,
        note_id: str,
        timestamp: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build metadata update dict for tracking synced notes.

        Args:
            platform_name: Platform identifier
            note_id: FUB note ID that was synced
            timestamp: ISO timestamp of the note (defaults to now)

        Returns:
            Dict to merge into lead.metadata
        """
        if timestamp is None:
            timestamp = datetime.utcnow().isoformat()

        return {
            'last_update_note_synced': {
                f'{platform_name.lower()}_note_id': note_id,
                f'{platform_name.lower()}_timestamp': timestamp
            }
        }


def extract_update_message_for_sync(
    notes: List[Dict[str, Any]],
    platform_name: str,
    lead_metadata: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Convenience function to extract @update message for platform sync.

    Args:
        notes: List of note dicts from FUB API
        platform_name: Platform identifier (e.g., 'referralexchange', 'homelight')
        lead_metadata: Lead's metadata dict containing sync timestamps

    Returns:
        The @update message string or None if no new update found
    """
    extractor = UpdateNoteExtractor()
    return extractor.get_update_for_platform(notes, platform_name, lead_metadata)
