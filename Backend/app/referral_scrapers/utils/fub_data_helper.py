"""
Helper module for fetching and using FUB (Follow Up Boss) data in referral platform updates.
This provides a shared interface for all platform services to access FUB notes and determine
intelligent status updates based on lead data.
"""
import json
import re
from datetime import datetime, timezone
from typing import Optional, Tuple, List, Dict, Any

from app.database.fub_api_client import FUBApiClient
from app.models.lead import Lead
from app.models.lead_source_settings import LeadSourceSettings
from app.utils.update_note_extractor import UpdateNoteExtractor


class FUBDataHelper:
    """Helper for fetching and using FUB data in referral platform updates."""

    def __init__(self):
        self.fub_client = FUBApiClient()
        self.update_extractor = UpdateNoteExtractor()
        self._lead_service = None
        self._supabase = None

    @property
    def lead_service(self):
        """Lazy load lead service to avoid circular imports"""
        if self._lead_service is None:
            from app.service.lead_service import LeadServiceSingleton
            self._lead_service = LeadServiceSingleton.get_instance()
        return self._lead_service

    @property
    def supabase(self):
        """Lazy load supabase client"""
        if self._supabase is None:
            from app.database.supabase_client import SupabaseClientSingleton
            self._supabase = SupabaseClientSingleton.get_instance()
        return self._supabase

    def fetch_notes_summary(self, lead: Lead, limit: int = 5, max_length: int = 200) -> Optional[str]:
        """
        Fetch recent FUB notes and create a summary for update comment.

        Args:
            lead: The lead to fetch notes for
            limit: Maximum number of recent notes to consider
            max_length: Maximum length of returned summary

        Returns:
            Summary string from recent notes, or None if no notes available
        """
        try:
            # Need fub_id to fetch notes
            fub_id = getattr(lead, 'fub_id', None)
            if not fub_id:
                # Try to get from metadata
                metadata = getattr(lead, 'metadata', {}) or {}
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except (json.JSONDecodeError, TypeError):
                        metadata = {}
                fub_id = metadata.get('fub_id') or metadata.get('fub_person_id')

            if not fub_id:
                print(f"[FUB Helper] No FUB ID found for lead {lead.first_name} {lead.last_name}")
                return None

            # Fetch notes from FUB API
            notes = self.fub_client.get_notes_for_person(str(fub_id), limit=limit)

            if not notes:
                print(f"[FUB Helper] No notes found for lead {lead.first_name} {lead.last_name}")
                return None

            # Get the most recent note
            recent_note = notes[0]
            body = recent_note.get('body', '') or ''

            # Strip HTML tags
            body = self._strip_html(body)

            # Clean up whitespace
            body = ' '.join(body.split())

            if not body:
                return None

            # Truncate if needed
            if len(body) > max_length:
                body = body[:max_length - 3] + "..."

            return body

        except Exception as e:
            print(f"[FUB Helper] Error fetching notes: {e}")
            return None

    def _strip_html(self, text: str) -> str:
        """Remove HTML tags from text"""
        if not text:
            return ""
        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', ' ', text)
        # Remove extra whitespace
        clean = ' '.join(clean.split())
        return clean

    def determine_status_for_lead(
        self,
        lead: Lead,
        source_settings: LeadSourceSettings,
        platform_name: str,
        default_status: Any
    ) -> Tuple[Any, Optional[str]]:
        """
        Determine status and comment for a lead update.

        Status Priority:
        1. FUB mapped stage (if lead has FUB status that maps to platform stage)
        2. Last known status (stored in metadata from previous sync)
        3. Default status

        Comment Priority:
        1. @update: message from FUB notes (if found and newer than last sync)
        2. Recent note summary from FUB
        3. Configured same_status_note fallback

        Args:
            lead: The lead to determine status for
            source_settings: The lead source settings with mapping configuration
            platform_name: Platform identifier for metadata keys (e.g., 'referralexchange', 'homelight')
            default_status: Default status to use if no mapping found

        Returns:
            Tuple of (status, comment) where comment may be from @update notes or FUB notes
        """
        comment = None
        status = None

        try:
            # Get lead type from tags (buyer/seller)
            lead_type = self._get_lead_type_from_tags(lead)

            # Try to get FUB mapped stage
            if lead.status and source_settings:
                mapped_status = source_settings.get_mapped_stage(lead.status, lead_type)
                if mapped_status:
                    print(f"[FUB Helper] Found FUB mapping: {lead.status} -> {mapped_status}")
                    status = mapped_status

            # If no mapping, try last known status from metadata
            if not status:
                metadata = getattr(lead, 'metadata', {}) or {}
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except (json.JSONDecodeError, TypeError):
                        metadata = {}

                last_status_key = f"{platform_name}_last_status"
                last_status = metadata.get(last_status_key) if isinstance(metadata, dict) else None

                if last_status:
                    print(f"[FUB Helper] Using last known status: {last_status}")
                    status = last_status

            # If still no status, use default
            if not status:
                print(f"[FUB Helper] Using default status: {default_status}")
                status = default_status

            # Priority 1: Try to get @update message from FUB notes
            update_message = self.get_update_message_for_platform(lead, platform_name)
            if update_message:
                print(f"[FUB Helper] Found @update message for {platform_name}: {update_message[:50]}...")
                comment = update_message
            else:
                # Priority 2: Try AI-generated update (if enabled)
                ai_update = self._try_ai_generated_update(lead, platform_name, source_settings, update_message)
                if ai_update:
                    print(f"[FUB Helper] Generated AI update for {platform_name}: {ai_update[:50]}...")
                    comment = ai_update
                else:
                    # Priority 3: Try to fetch FUB notes summary for the comment
                    notes_summary = self.fetch_notes_summary(lead)
                    if notes_summary:
                        comment = notes_summary
                    elif source_settings and hasattr(source_settings, 'same_status_note'):
                        # Priority 4: Use the configured "same status" note as fallback
                        comment = source_settings.same_status_note

            return status, comment

        except Exception as e:
            print(f"[FUB Helper] Error determining status: {e}")
            return default_status, None

    def get_update_message_for_platform(
        self,
        lead: Lead,
        platform_name: str
    ) -> Optional[str]:
        """
        Get @update: message from FUB notes for a specific platform.

        Only returns messages from notes created after the last sync to this platform.

        Args:
            lead: The lead to get update message for
            platform_name: Platform identifier (e.g., 'referralexchange', 'homelight')

        Returns:
            The @update message or None if no new update found
        """
        try:
            # Get FUB ID
            fub_id = getattr(lead, 'fub_id', None)
            if not fub_id:
                metadata = getattr(lead, 'metadata', {}) or {}
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except (json.JSONDecodeError, TypeError):
                        metadata = {}
                fub_id = metadata.get('fub_id') or metadata.get('fub_person_id')

            if not fub_id:
                return None

            # Fetch notes from FUB
            notes = self.fub_client.get_notes_for_person(str(fub_id), limit=20)
            if not notes:
                return None

            # Get lead metadata for sync timestamp
            metadata = getattr(lead, 'metadata', {}) or {}
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}

            # Extract @update message
            return self.update_extractor.get_update_for_platform(
                notes,
                platform_name,
                metadata
            )

        except Exception as e:
            print(f"[FUB Helper] Error getting update message: {e}")
            return None

    def mark_update_synced(
        self,
        lead: Lead,
        platform_name: str,
        note_id: str,
        note_timestamp: str
    ) -> bool:
        """
        Mark an @update note as synced for a platform.

        Args:
            lead: The lead to update
            platform_name: Platform identifier
            note_id: FUB note ID that was synced
            note_timestamp: ISO timestamp of the note

        Returns:
            True if marked successfully
        """
        try:
            metadata = getattr(lead, 'metadata', {}) or {}
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}

            if not isinstance(metadata, dict):
                metadata = {}

            # Initialize sync tracking if needed
            if 'last_update_note_synced' not in metadata:
                metadata['last_update_note_synced'] = {}

            # Update sync info for this platform
            metadata['last_update_note_synced'][f'{platform_name.lower()}_note_id'] = note_id
            metadata['last_update_note_synced'][f'{platform_name.lower()}_timestamp'] = note_timestamp

            # Save metadata
            lead.metadata = metadata
            self.lead_service.update(lead)

            print(f"[FUB Helper] Marked @update synced for {platform_name}: note {note_id}")
            return True

        except Exception as e:
            print(f"[FUB Helper] Error marking update synced: {e}")
            return False

    def _get_lead_type_from_tags(self, lead: Lead) -> Optional[str]:
        """Extract lead type (buyer/seller) from lead tags"""
        try:
            tags = getattr(lead, 'tags', None) or []
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except (json.JSONDecodeError, TypeError):
                    tags = []

            for tag in tags:
                tag_lower = str(tag).lower()
                if 'seller' in tag_lower:
                    return 'seller'
                elif 'buyer' in tag_lower:
                    return 'buyer'

            return None
        except Exception:
            return None

    def _try_ai_generated_update(
        self,
        lead: Lead,
        platform_name: str,
        source_settings,
        existing_update: Optional[str] = None
    ) -> Optional[str]:
        """
        Try to generate an AI update note if enabled in source settings.

        Args:
            lead: The lead to generate update for
            platform_name: Target platform name
            source_settings: LeadSourceSettings with AI config in metadata
            existing_update: Existing @update note if any

        Returns:
            AI-generated update or None if disabled/failed
        """
        try:
            from app.ai_agent.update_note_generator import generate_ai_update_for_sync

            if not source_settings:
                return None

            return generate_ai_update_for_sync(
                lead=lead,
                platform_name=platform_name,
                source_settings=source_settings,
                existing_update=existing_update
            )

        except ImportError:
            print("[FUB Helper] AI update generator not available")
            return None
        except Exception as e:
            print(f"[FUB Helper] Error generating AI update: {e}")
            return None

    def lookup_lead_by_name(self, display_name: str, source: str) -> Optional[Lead]:
        """
        Match platform display name to database lead.

        Handles various name formats:
        - "FirstName LastName"
        - "FirstName L." (abbreviated)
        - "FirstName LastInitial"

        Args:
            display_name: Name as displayed on the platform
            source: Lead source (e.g., 'ReferralExchange', 'HomeLight')

        Returns:
            Lead if found, None otherwise
        """
        try:
            # Parse the display name
            parts = display_name.strip().split()
            if not parts:
                return None

            first_name = parts[0]
            last_name_part = parts[-1] if len(parts) > 1 else ""

            # Clean up last name (remove periods for initials like "C.")
            last_name_clean = last_name_part.replace(".", "").strip()

            # Search by source and first name
            result = self.supabase.table('leads').select('*').eq('source', source).ilike('first_name', f'{first_name}%').execute()

            if not result.data:
                return None

            # Try to find best match
            for lead_data in result.data:
                db_first = (lead_data.get('first_name') or '').lower()
                db_last = (lead_data.get('last_name') or '').lower()

                # Check if first names match
                if db_first.startswith(first_name.lower()) or first_name.lower().startswith(db_first):
                    # If last_name_part is just an initial (1-2 chars)
                    if len(last_name_clean) <= 2:
                        if db_last.startswith(last_name_clean.lower()):
                            return Lead.from_dict(lead_data)
                    else:
                        # Full last name comparison
                        if db_last == last_name_clean.lower() or db_last.startswith(last_name_clean.lower()):
                            return Lead.from_dict(lead_data)

            return None

        except Exception as e:
            print(f"[FUB Helper] Error looking up lead by name: {e}")
            return None

    def save_last_status_to_metadata(
        self,
        lead: Lead,
        platform_name: str,
        status: Any
    ) -> bool:
        """
        Save the successful status to lead metadata for future fallback.

        Args:
            lead: The lead to update
            platform_name: Platform identifier for metadata key
            status: The status that was successfully applied

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Get current metadata
            metadata = getattr(lead, 'metadata', {}) or {}
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}

            if not isinstance(metadata, dict):
                metadata = {}

            # Update with new status info
            status_key = f"{platform_name}_last_status"
            updated_key = f"{platform_name}_last_updated"

            # Convert status to string for storage if needed
            if isinstance(status, (list, tuple)):
                status_str = "::".join(str(s) for s in status if s)
            elif isinstance(status, dict):
                status_str = json.dumps(status)
            else:
                status_str = str(status) if status else ""

            metadata[status_key] = status_str
            metadata[updated_key] = datetime.now(timezone.utc).isoformat()

            # Update the lead
            lead.metadata = metadata
            self.lead_service.update(lead)

            print(f"[FUB Helper] Saved status to metadata: {status_key} = {status_str}")
            return True

        except Exception as e:
            print(f"[FUB Helper] Error saving status to metadata: {e}")
            return False


# Singleton instance for shared use
_fub_data_helper_instance = None

def get_fub_data_helper() -> FUBDataHelper:
    """Get singleton instance of FUBDataHelper"""
    global _fub_data_helper_instance
    if _fub_data_helper_instance is None:
        _fub_data_helper_instance = FUBDataHelper()
    return _fub_data_helper_instance
