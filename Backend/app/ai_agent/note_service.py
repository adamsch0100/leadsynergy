"""
AI Update Note Service.

Manages @update notes that the AI generates from extracted lead data.
These notes sync to lead sources via the existing lead source integration.

Key functionality:
- Queue notes for review (pending status)
- Approve/dismiss notes
- Create FUB notes with @update prefix
- Log activity for monitoring dashboard
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID

from app.database import get_supabase_client
from app.database.fub_api_client import FUBApiClient

logger = logging.getLogger(__name__)


# Note types that can be extracted
NOTE_TYPES = {
    'timeline': 'Timeline',
    'budget': 'Budget',
    'pre_approval': 'Pre-approved',
    'areas': 'Areas',
    'motivation': 'Motivation',
    'property_type': 'Looking for',
    'current_situation': 'Currently',
    'financing': 'Financing',
    'agent_status': 'Agent Status',
}


class AIUpdateNoteService:
    """Service for managing AI-generated @update notes."""

    def __init__(self, supabase_client=None):
        """
        Initialize the note service.

        Args:
            supabase_client: Optional Supabase client. If not provided, uses singleton.
        """
        self.supabase = supabase_client or get_supabase_client()
        self.fub_client = FUBApiClient()

    async def queue_update_note(
        self,
        person_id: int,
        note_type: str,
        raw_value: str,
        confidence: float = 0.8,
        message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Queue an @update note for review.

        Args:
            person_id: FUB person ID
            note_type: Type of data (timeline, budget, pre_approval, etc.)
            raw_value: The extracted value (e.g., "0-3 months", "$525,000")
            confidence: AI confidence score (0.0-1.0)
            message_id: Optional ID of the message this was extracted from

        Returns:
            Created note record or error dict
        """
        try:
            # Format the note content with @update prefix
            type_label = NOTE_TYPES.get(note_type, note_type.replace('_', ' ').title())
            note_content = f"@update {type_label}: {raw_value}"

            # Check for duplicate pending notes
            existing = self.supabase.table('ai_pending_notes').select('id').eq(
                'person_id', person_id
            ).eq('note_type', note_type).eq('status', 'pending').execute()

            if existing.data:
                # Update existing pending note instead of creating duplicate
                update_result = self.supabase.table('ai_pending_notes').update({
                    'note_content': note_content,
                    'raw_value': raw_value,
                    'confidence': confidence,
                    'extracted_from_message_id': message_id,
                }).eq('id', existing.data[0]['id']).execute()

                logger.info(f"Updated existing pending note for person {person_id}, type {note_type}")
                return {'success': True, 'note': update_result.data[0] if update_result.data else None, 'updated': True}

            # Create new pending note
            note_data = {
                'person_id': person_id,
                'note_type': note_type,
                'note_content': note_content,
                'raw_value': raw_value,
                'confidence': confidence,
                'status': 'pending',
                'extracted_from_message_id': message_id,
            }

            result = self.supabase.table('ai_pending_notes').insert(note_data).execute()

            if result.data:
                logger.info(f"Queued @update note for person {person_id}: {note_type}={raw_value}")

                # Log activity
                await self.log_activity(
                    person_id=person_id,
                    activity_type='note_created',
                    description=f"AI extracted {type_label}: {raw_value}",
                    activity_data={'note_id': result.data[0]['id'], 'note_type': note_type}
                )

                return {'success': True, 'note': result.data[0]}

            return {'success': False, 'error': 'Failed to create note'}

        except Exception as e:
            logger.error(f"Error queueing update note: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    async def approve_note(self, note_id: str, reviewed_by: str) -> Dict[str, Any]:
        """
        Approve a pending note and create it in FUB.

        Args:
            note_id: UUID of the pending note
            reviewed_by: Email of the user who approved

        Returns:
            Result dict with success status
        """
        try:
            # Get the pending note
            result = self.supabase.table('ai_pending_notes').select('*').eq('id', note_id).single().execute()

            if not result.data:
                return {'success': False, 'error': 'Note not found'}

            note = result.data

            if note['status'] != 'pending':
                return {'success': False, 'error': f"Note is not pending, status: {note['status']}"}

            # Create the note in FUB
            fub_result = self.fub_client.add_note(
                person_id=note['person_id'],
                note_content=note['note_content'],
                is_private=False
            )

            fub_note_id = fub_result.get('id') if fub_result else None

            # Update the pending note status
            update_data = {
                'status': 'sent' if fub_note_id else 'approved',
                'reviewed_at': datetime.utcnow().isoformat(),
                'reviewed_by': reviewed_by,
                'fub_note_id': fub_note_id,
            }

            self.supabase.table('ai_pending_notes').update(update_data).eq('id', note_id).execute()

            logger.info(f"Approved note {note_id}, FUB note ID: {fub_note_id}")

            # Log activity
            await self.log_activity(
                person_id=note['person_id'],
                activity_type='note_approved',
                description=f"@update note approved: {note['note_content']}",
                activity_data={'note_id': note_id, 'fub_note_id': fub_note_id}
            )

            return {
                'success': True,
                'fub_note_id': fub_note_id,
                'note_content': note['note_content']
            }

        except Exception as e:
            logger.error(f"Error approving note {note_id}: {e}", exc_info=True)

            # Mark as error
            self.supabase.table('ai_pending_notes').update({
                'error_message': str(e),
            }).eq('id', note_id).execute()

            return {'success': False, 'error': str(e)}

    async def dismiss_note(self, note_id: str, reviewed_by: str) -> Dict[str, Any]:
        """
        Dismiss a pending note (don't create in FUB).

        Args:
            note_id: UUID of the pending note
            reviewed_by: Email of the user who dismissed

        Returns:
            Result dict with success status
        """
        try:
            # Update the note status
            result = self.supabase.table('ai_pending_notes').update({
                'status': 'dismissed',
                'reviewed_at': datetime.utcnow().isoformat(),
                'reviewed_by': reviewed_by,
            }).eq('id', note_id).execute()

            if result.data:
                logger.info(f"Dismissed note {note_id}")
                return {'success': True}

            return {'success': False, 'error': 'Note not found'}

        except Exception as e:
            logger.error(f"Error dismissing note {note_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    async def bulk_approve_notes(self, note_ids: List[str], reviewed_by: str) -> Dict[str, Any]:
        """
        Approve multiple notes at once.

        Args:
            note_ids: List of note UUIDs to approve
            reviewed_by: Email of the user who approved

        Returns:
            Result dict with success/failure counts
        """
        results = {'approved': 0, 'failed': 0, 'errors': []}

        for note_id in note_ids:
            result = await self.approve_note(note_id, reviewed_by)
            if result.get('success'):
                results['approved'] += 1
            else:
                results['failed'] += 1
                results['errors'].append({'note_id': note_id, 'error': result.get('error')})

        return results

    async def get_pending_notes(self, person_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get pending notes awaiting review.

        Args:
            person_id: Optional filter by person
            limit: Max number of notes to return

        Returns:
            List of pending note records
        """
        try:
            query = self.supabase.table('ai_pending_notes').select('*').eq('status', 'pending').order('created_at', desc=True).limit(limit)

            if person_id:
                query = query.eq('person_id', person_id)

            result = query.execute()
            return result.data or []

        except Exception as e:
            logger.error(f"Error getting pending notes: {e}", exc_info=True)
            return []

    async def get_notes_for_person(self, person_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get all AI notes for a specific person.

        Args:
            person_id: FUB person ID
            limit: Max number of notes to return

        Returns:
            List of note records
        """
        try:
            result = self.supabase.table('ai_pending_notes').select('*').eq(
                'person_id', person_id
            ).order('created_at', desc=True).limit(limit).execute()

            return result.data or []

        except Exception as e:
            logger.error(f"Error getting notes for person {person_id}: {e}", exc_info=True)
            return []

    # ==================== Activity Logging ====================

    async def log_activity(
        self,
        person_id: int,
        activity_type: str,
        description: str,
        activity_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Log an AI activity event for the monitoring dashboard.

        Args:
            person_id: FUB person ID
            activity_type: Type of activity (message_sent, state_changed, escalated, etc.)
            description: Human-readable description
            activity_data: Additional data specific to the activity

        Returns:
            Created activity record or error dict
        """
        try:
            record = {
                'person_id': person_id,
                'activity_type': activity_type,
                'description': description,
                'activity_data': activity_data or {},
            }

            result = self.supabase.table('ai_activity_log').insert(record).execute()

            if result.data:
                return {'success': True, 'activity': result.data[0]}

            return {'success': False, 'error': 'Failed to log activity'}

        except Exception as e:
            # Don't fail if activity logging fails - it's non-critical
            logger.warning(f"Failed to log activity: {e}")
            return {'success': False, 'error': str(e)}

    async def get_activity_feed(self, limit: int = 50, person_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get recent AI activity for the monitoring feed.

        Args:
            limit: Max number of activities to return
            person_id: Optional filter by person

        Returns:
            List of activity records
        """
        try:
            query = self.supabase.table('ai_activity_log').select('*').order('created_at', desc=True).limit(limit)

            if person_id:
                query = query.eq('person_id', person_id)

            result = query.execute()
            return result.data or []

        except Exception as e:
            logger.error(f"Error getting activity feed: {e}", exc_info=True)
            return []


# ==================== Helper Functions ====================

def extract_update_notes_from_data(extracted_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Parse extracted data from AI and identify fields that should become @update notes.

    Args:
        extracted_data: Dict of extracted lead data from AI response

    Returns:
        List of dicts with {note_type, raw_value} for each @update note to create
    """
    notes = []

    # Map extracted data keys to note types
    mappings = {
        'timeline': ['timeline', 'timeframe', 'time_frame', 'move_date', 'when_buying'],
        'budget': ['budget', 'price_range', 'max_price', 'min_price'],
        'pre_approval': ['pre_approval', 'pre_approved', 'preapproval', 'pre_approval_amount'],
        'areas': ['areas', 'neighborhoods', 'cities', 'locations', 'zip_codes'],
        'motivation': ['motivation', 'reason_for_moving', 'why_moving'],
        'property_type': ['property_type', 'home_type', 'looking_for'],
        'current_situation': ['current_situation', 'currently', 'living_situation'],
        'financing': ['financing', 'loan_type', 'down_payment'],
        'agent_status': ['has_agent', 'working_with_agent', 'agent_status'],
    }

    for note_type, keys in mappings.items():
        for key in keys:
            if key in extracted_data and extracted_data[key]:
                value = extracted_data[key]

                # Format value appropriately
                if isinstance(value, bool):
                    value = 'Yes' if value else 'No'
                elif isinstance(value, list):
                    value = ', '.join(str(v) for v in value)
                elif isinstance(value, (int, float)):
                    # Format currency
                    if 'amount' in key or 'price' in key or 'budget' in key:
                        value = f"${value:,.0f}"
                    else:
                        value = str(value)

                if value and str(value).strip():
                    notes.append({
                        'note_type': note_type,
                        'raw_value': str(value).strip()
                    })
                    break  # Only one note per type

    return notes


# Singleton instance for service
_note_service_instance: Optional[AIUpdateNoteService] = None


def get_note_service(supabase_client=None) -> AIUpdateNoteService:
    """
    Get the AIUpdateNoteService instance.

    Args:
        supabase_client: Optional Supabase client

    Returns:
        AIUpdateNoteService instance
    """
    global _note_service_instance

    if _note_service_instance is None:
        _note_service_instance = AIUpdateNoteService(supabase_client)

    return _note_service_instance
