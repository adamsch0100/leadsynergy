import base64
import json
import os
import requests
import aiohttp
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

from app.utils.constants import Credentials

class FUBApiClient:
    def __init__(self, api_key: str = None) -> None:
        self.creds = Credentials()
        # Use provided API key or fallback to environment key
        self.api_key = api_key or self.creds.FUB_API_KEY
        self.base_url = "https://api.followupboss.com/v1/"
        self.auth_header = f"Basic {base64.b64encode(f"{self.api_key}:".encode()).decode()}"
        self.headers = {
            'Content-Type': "application/json",
            'Authorization': self.auth_header
        }

        # System registration credentials for webhook API access
        # These are obtained by registering at https://apps.followupboss.com/system-registration
        self.system_name = os.getenv('FUB_SYSTEM_NAME', 'LeadSynergy')
        self.system_key = os.getenv('FUB_SYSTEM_KEY')


    def _add_system_headers(self, system_name: str = None, system_key: str = None) -> Dict[str, str]:
        """Add System Headers"""
        headers = self.headers.copy()

        if system_name:
            headers['X-System'] = system_name

        if system_key:
            headers['X-System-Key'] = system_key

        return headers

    def _get_webhook_headers(self) -> Dict[str, str]:
        """
        Get headers for webhook API calls.

        FUB webhook API requires X-System and X-System-Key headers.
        These are obtained by registering at https://apps.followupboss.com/system-registration

        Returns:
            Headers dict with system credentials included

        Raises:
            ValueError: If system key is not configured
        """
        if not self.system_key:
            raise ValueError(
                "FUB_SYSTEM_KEY not configured. "
                "Please register at https://apps.followupboss.com/system-registration "
                "and add FUB_SYSTEM_KEY to your environment variables."
            )

        return self._add_system_headers(
            system_name=self.system_name,
            system_key=self.system_key
        )
    
    def get_people(self, limit: int = 100, page: int = 1, updated_since: Optional[Union[str, datetime]] = None, source: Optional[str] = None, next_cursor: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve people (leads) from Follow Up Boss.

        Args:
            limit: Number of records per page (max 200 per FUB docs).
            page: 1-based page number (for initial request only).
            updated_since: Optional ISO timestamp or datetime to filter by last update time.
            source: Optional source name to filter by (e.g., "Redfin", "HomeLight").
            next_cursor: Cursor for pagination (from _metadata.next).

        Returns:
            Parsed JSON response from FUB API.
        """
        params: Dict[str, Any] = {
            "limit": limit,
        }

        # Use next cursor if provided, otherwise use page for initial request
        if next_cursor:
            params["next"] = next_cursor
        else:
            params["page"] = page

        if updated_since:
            if isinstance(updated_since, datetime):
                params["updatedSince"] = updated_since.isoformat()
            else:
                params["updatedSince"] = updated_since

        if source:
            params["source"] = source

        response = requests.get(
            f"{self.base_url}people",
            headers=self.headers,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test the FUB API connection with the current API key"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}people", headers=self.headers, params={"limit": 1}) as response:
                    if response.status != 200:
                        raise Exception(f"API test failed with status {response.status}")
                    return await response.json()
        except Exception as e:
            raise Exception(f"FUB API connection test failed: {str(e)}")
    
    ######################## Synchronous Methods ########################

    def get_users(self) -> List[Dict[str, Any]]:
        """
        Get all users (team members) from Follow Up Boss.

        Returns:
            List of user objects with id, name, email, role, etc.
        """
        try:
            url = f"{self.base_url}users"
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("users", [])
        except Exception as e:
            print(f"Error fetching FUB users: {str(e)}")
            return []

    def get_user(self, user_id: str) -> Dict[str, Any]:
        """Get a specific user by ID from Follow Up Boss."""
        try:
            url = f"{self.base_url}users/{user_id}"
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching FUB user {user_id}: {str(e)}")
            return {}

    def get_note(self, note_id: str) -> Dict[str, Any]:
        """Get a note by its ID"""
        headers = self._add_system_headers(
            self.creds.NOTE_CREATED_SYSTEM_NAME,
            self.creds.NOTE_SYSTEM_KEY
        )
        url = f"{self.base_url}notes/{note_id}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        return response.json()
    
    
    def get_person(self, person_id: str, include_all_fields: bool = True) -> Dict[str, Any]:
        """
        Get person by their ID with all available data.

        Args:
            person_id: FUB person ID
            include_all_fields: If True, includes all custom fields

        Returns:
            Complete person data including custom fields
        """
        headers = self._add_system_headers(
            self.creds.TAG_SYSTEM_NAME,
            self.creds.TAG_SYSTEM_KEY
        )

        url = f"{self.base_url}people/{person_id}"
        params = {}
        if include_all_fields:
            params["fields"] = "allFields"

        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()

        return response.json()

    def get_text_messages_for_person(self, person_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get text message history for a specific person.

        Args:
            person_id: FUB person ID
            limit: Max number of messages to retrieve

        Returns:
            List of text messages with content, direction, timestamps
        """
        url = f"{self.base_url}textMessages"
        params = {
            "personId": person_id,
            "limit": limit,
        }

        response = requests.get(url, headers=self.headers, params=params, timeout=30)
        response.raise_for_status()

        return response.json().get("textmessages", [])

    def get_emails_for_person(self, person_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get email history for a specific person.

        Args:
            person_id: FUB person ID
            limit: Max number of emails to retrieve

        Returns:
            List of emails with subject, body, direction, timestamps
        """
        url = f"{self.base_url}emails"
        params = {
            "personId": person_id,
            "limit": limit,
        }

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json().get("emails", [])
        except Exception as e:
            # Emails endpoint may not be available for all accounts
            return []

    def get_calls_for_person(self, person_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get call history for a specific person.

        Args:
            person_id: FUB person ID
            limit: Max number of calls to retrieve

        Returns:
            List of calls with duration, direction, timestamps
        """
        url = f"{self.base_url}calls"
        params = {
            "personId": person_id,
            "limit": limit,
        }

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json().get("calls", [])
        except Exception as e:
            # Calls endpoint may not be available
            return []

    def get_tasks_for_person(self, person_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get tasks assigned for a specific person.

        Args:
            person_id: FUB person ID
            limit: Max number of tasks to retrieve

        Returns:
            List of tasks with name, due date, completion status
        """
        url = f"{self.base_url}tasks"
        params = {
            "personId": person_id,
            "limit": limit,
        }

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json().get("tasks", [])
        except Exception as e:
            return []

    def get_complete_lead_context(self, person_id: int) -> Dict[str, Any]:
        """
        Get ALL available data for a lead - comprehensive context for AI.

        This pulls every piece of data FUB has about this lead:
        - Person details (contact info, stage, source, custom fields)
        - Text message history (full conversation)
        - Email history
        - Call history
        - Notes (agent notes, system notes)
        - Events (property inquiries, timeline)
        - Tasks

        Args:
            person_id: FUB person ID

        Returns:
            Complete lead context with all available data
        """
        context = {
            "person": {},
            "text_messages": [],
            "emails": [],
            "calls": [],
            "notes": [],
            "events": [],
            "tasks": [],
            "errors": [],
        }

        # Get person data with all fields
        try:
            context["person"] = self.get_person(str(person_id), include_all_fields=True)
        except Exception as e:
            context["errors"].append(f"Failed to get person: {e}")

        # Get text message history
        try:
            context["text_messages"] = self.get_text_messages_for_person(person_id, limit=50)
        except Exception as e:
            context["errors"].append(f"Failed to get text messages: {e}")

        # Get email history
        try:
            context["emails"] = self.get_emails_for_person(person_id, limit=20)
        except Exception as e:
            context["errors"].append(f"Failed to get emails: {e}")

        # Get call history
        try:
            context["calls"] = self.get_calls_for_person(person_id, limit=20)
        except Exception as e:
            context["errors"].append(f"Failed to get calls: {e}")

        # Get notes
        try:
            context["notes"] = self.get_notes_for_person(person_id, limit=30)
        except Exception as e:
            context["errors"].append(f"Failed to get notes: {e}")

        # Get events (property inquiries, timeline)
        try:
            context["events"] = self.get_events_for_person(person_id, limit=30)
        except Exception as e:
            context["errors"].append(f"Failed to get events: {e}")

        # Get tasks
        try:
            context["tasks"] = self.get_tasks_for_person(person_id, limit=20)
        except Exception as e:
            context["errors"].append(f"Failed to get tasks: {e}")

        return context
    
    def get_notes_for_person(self, person_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get notes for a specific person"""
        # Use /notes endpoint with personId filter (not /people/{id}/notes which returns 404)
        url = f"{self.base_url}notes"
        params = {
            "personId": person_id,
            "limit": limit,
        }

        response = requests.get(url, headers=self.headers, params=params, timeout=30)
        response.raise_for_status()

        return response.json().get("notes", [])

    def get_events_for_person(self, person_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get events/timeline for a specific person.

        Events include property inquiries, emails, calls, etc.
        This provides context about how the lead came in and their history.

        Args:
            person_id: FUB person ID
            limit: Max number of events to retrieve

        Returns:
            List of event dictionaries with type, description, source, etc.
        """
        url = f"{self.base_url}events"
        params = {
            "personId": person_id,
            "limit": limit,
        }

        response = requests.get(url, headers=self.headers, params=params, timeout=30)
        response.raise_for_status()

        return response.json().get("events", [])

    def get_lead_history(self, person_id: int) -> Dict[str, Any]:
        """
        Get comprehensive lead history including notes and events.

        This combines notes (planned/sent communications) and events (timeline)
        to give the AI full context about the lead's journey.

        Args:
            person_id: FUB person ID

        Returns:
            Dictionary with 'notes', 'events', and 'summary' keys
        """
        notes = self.get_notes_for_person(person_id, limit=20)
        events = self.get_events_for_person(person_id, limit=20)

        # Parse events for key info
        property_inquiry = None
        for event in events:
            if event.get("type") == "Property Inquiry":
                property_inquiry = {
                    "source": event.get("source"),
                    "description": event.get("description"),
                    "property": event.get("property", {}),
                    "date": event.get("created"),
                }
                break

        # Parse notes for communication history
        # Notes from KTS are planned messages (may not have been sent)
        planned_messages = []
        for note in notes:
            created_by = note.get("createdBy", "")
            if "KTS" in created_by or "Leadngage" in created_by:
                planned_messages.append({
                    "body": note.get("body", ""),
                    "date": note.get("created"),
                    "status": "planned_not_sent",  # KTS notes were not actually sent
                })

        return {
            "notes": notes,
            "events": events,
            "property_inquiry": property_inquiry,
            "planned_messages": planned_messages,
        }
    
    
    def update_note(self, note_id: str, content: str, is_private: bool = None) -> Dict[str, Any]:
        """Update an existing note"""
        headers = self._add_system_headers(
            self.creds.NOTE_CREATED_SYSTEM_NAME,
            self.creds.NOTE_SYSTEM_KEY
        )

        url = f"{self.base_url}notes/{note_id}"
        data = {"body": content}

        if is_private is not None:
            data["isPrivate"] = is_private

        response = requests.put(url, headers=headers, json=data)
        response.raise_for_status()

        return response.json()

    def get_custom_fields(self) -> List[Dict[str, Any]]:
        """
        Get all custom fields defined in FUB.

        Returns:
            List of custom field dicts with keys: id, label, name, type, choices, isRecurring
        """
        url = f"{self.base_url}customFields"

        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        result = response.json()
        return result.get("customFields", result.get("data", []))

    def create_custom_field(
        self,
        label: str,
        field_type: str = "text",
        choices: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a custom field in FUB.

        Note: Requires account owner access.

        Args:
            label: Display name for the field (e.g., "AI - Timeline")
            field_type: One of: text, number, date, dropdown
            choices: List of choices for dropdown fields

        Returns:
            Created custom field data from FUB
        """
        url = f"{self.base_url}customFields"

        data: Dict[str, Any] = {
            "label": label,
            "type": field_type,
        }

        if choices and field_type == "dropdown":
            data["choices"] = choices

        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()

        return response.json()

    def update_person(self, person_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a person's data in FUB.

        Args:
            person_id: FUB person ID
            data: Dict of fields to update. Can include:
                - customFields: Dict of custom field values
                - stage: Stage ID
                - assignedTo: User ID
                - tags: List of tag names
                - And other standard FUB person fields

        Returns:
            Updated person data from FUB
        """
        url = f"{self.base_url}people/{person_id}"

        response = requests.put(url, headers=self.headers, json=data)
        response.raise_for_status()

        return response.json()

    def add_note(self, person_id: int, note_content: str, is_private: bool = False) -> Dict[str, Any]:
        """
        Add a note to a person in FUB.

        Args:
            person_id: FUB person ID
            note_content: HTML or plain text note content
            is_private: If True, note is only visible to the user who created it

        Returns:
            Created note data from FUB
        """
        headers = self._add_system_headers(
            self.creds.NOTE_CREATED_SYSTEM_NAME,
            self.creds.NOTE_SYSTEM_KEY
        )

        url = f"{self.base_url}notes"
        data = {
            "personId": person_id,
            "body": note_content,
            "isPrivate": is_private,
        }

        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()

        return response.json()

    def create_task(self, person_id: int, description: str, due_date: str = None,
                    assigned_to: int = None, is_completed: bool = False) -> Dict[str, Any]:
        """
        Create a task for a person in FUB.

        Args:
            person_id: FUB person ID
            description: Task description
            due_date: Optional due date in ISO format (YYYY-MM-DD)
            assigned_to: Optional user ID to assign the task to
            is_completed: If True, task is marked as completed

        Returns:
            Created task data from FUB
        """
        url = f"{self.base_url}tasks"
        data = {
            "personId": person_id,
            "name": description,
            "isCompleted": is_completed,
        }

        if due_date:
            data["dueDate"] = due_date
        if assigned_to:
            data["assignedTo"] = assigned_to

        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()

        return response.json()

    def get_stages(self, limit: int = 100):
        """Get all stages from FUB API

        Args:
            limit: Max number of stages to retrieve (default 100)
        """
        headers = self._add_system_headers(
            self.creds.STAGE_SYSTEM_NAME,
            self.creds.STAGE_SYSTEM_KEY
        )

        url = f"{self.base_url}stages"
        params = {"limit": limit}

        response = requests.get(url, headers=headers, params=params)

        print(f"[FUB API] GET {url} with limit={limit}")
        print(f"[FUB API] Response status: {response.status_code}")

        if not response.status_code == 200:
            raise Exception(f"Failed to get stages from FUB API: {response.text}")

        data = response.json()
        stages = data.get('stages', [])

        print(f"[FUB API] Raw stages response: {data}")
        print(f"[FUB API] Total stages returned: {len(stages)}")

        return stages
    
    def get_stage(self, stage_id):
        headers = self._add_system_headers(
            self.creds.STAGE_SYSTEM_NAME,
            self.creds.STAGE_SYSTEM_KEY
        )
        
        url = f"{self.base_url}stages/{stage_id}"
        
        response = requests.get(url, headers=headers)
        
        if not response.status_code == 200:
            raise Exception(f"Failed to get stage {stage_id} from FUB API: {response.text}")
        
        return response.json()
    
    
    ######################## Asynchronous Methods ########################
    async def get_aiohttp_session(self, system_name: str = None, system_key: str = None) -> aiohttp.ClientSession:
        """Create an aiohttp session with appropriate headers"""
        headers = self.headers.copy()
        
        if system_name:
            headers["X-System"] = system_name
        
        if system_key:
            headers["X-System-Key"] = system_key
            
        return aiohttp.ClientSession(headers=headers)
    
    async def async_get_note(self, note_id: str) -> Dict[str, Any]:
        """Get a note by its ID (async)"""
        async with await self.get_aiohttp_session(
            self.creds.NOTE_CREATED_SYSTEM_NAME,
            self.creds.NOTE_SYSTEM_KEY
        ) as session:
            url = f"{self.base_url}notes/{note_id}"
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.json()
    
    async def async_get_person(self, person_id: str) -> Dict[str, Any]:
        """Get a person by their ID (async)"""
        async with await self.get_aiohttp_session(
            self.creds.TAG_SYSTEM_NAME,
            self.creds.TAG_SYSTEM_KEY
        ) as session:
            url = f"{self.base_url}people/{person_id}"
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.json()
            
    
    ######################## Webhook Management ########################

    def get_webhooks(self) -> List[Dict[str, Any]]:
        """
        Get all registered webhooks for this FUB account.

        Requires FUB system registration. See:
        https://apps.followupboss.com/system-registration

        Returns:
            List of webhook configurations
        """
        response = requests.get(
            f"{self.base_url}webhooks",
            headers=self._get_webhook_headers(),
            timeout=30
        )
        response.raise_for_status()
        return response.json().get('webhooks', [])

    def register_webhook(
        self,
        event: str,
        url: str,
        system_name: str = "LeadSynergy-AI"
    ) -> Dict[str, Any]:
        """
        Register a new webhook with FUB.

        Requires FUB system registration. See:
        https://apps.followupboss.com/system-registration

        Args:
            event: FUB event name (e.g., 'textMessagesCreated', 'peopleCreated')
            url: Full URL to receive webhook POST
            system_name: System identifier for this webhook (in payload, not headers)

        Returns:
            Webhook configuration including ID
        """
        payload = {
            'event': event,
            'url': url,
            'system': system_name
        }

        response = requests.post(
            f"{self.base_url}webhooks",
            json=payload,
            headers=self._get_webhook_headers(),
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def delete_webhook(self, webhook_id: int) -> bool:
        """
        Delete a webhook by ID.

        Requires FUB system registration. See:
        https://apps.followupboss.com/system-registration

        Args:
            webhook_id: The FUB webhook ID

        Returns:
            True if deleted successfully
        """
        response = requests.delete(
            f"{self.base_url}webhooks/{webhook_id}",
            headers=self._get_webhook_headers(),
            timeout=30
        )
        return response.status_code in (200, 204)

    def ensure_ai_webhooks(self, base_url: str, org_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Ensure all required AI agent webhooks are registered.

        This checks existing webhooks and registers any missing ones.
        Required webhooks:
        - textMessagesCreated: For incoming SMS processing
        - peopleCreated: For new lead welcome sequences

        Args:
            base_url: The base URL for the API (e.g., 'https://api.leadsynergy.ai')
            org_id: Optional organization ID to append to webhook URLs for multi-tenant routing

        Returns:
            Dict with 'registered', 'existing', and 'failed' webhook lists
        """
        # Build query string for multi-tenant routing
        query_string = f"?org_id={org_id}" if org_id else ""

        # Define required webhooks
        required_webhooks = [
            {
                'event': 'textMessagesCreated',
                'endpoint': f'/webhooks/ai/text-received{query_string}',
                'system': 'LeadSynergy-AI-SMS'
            },
            {
                'event': 'peopleCreated',
                'endpoint': f'/webhooks/ai/lead-created{query_string}',
                'system': 'LeadSynergy-AI-NewLead'
            },
        ]

        results = {
            'registered': [],
            'existing': [],
            'failed': [],
            'webhooks': []
        }

        try:
            # Get existing webhooks
            existing = self.get_webhooks()
            existing_events = {w.get('event'): w for w in existing}

            for webhook_config in required_webhooks:
                event = webhook_config['event']
                full_url = f"{base_url.rstrip('/')}{webhook_config['endpoint']}"

                # Check if already registered
                if event in existing_events:
                    existing_webhook = existing_events[event]
                    # Check if URL matches
                    if existing_webhook.get('url') == full_url:
                        results['existing'].append({
                            'event': event,
                            'id': existing_webhook.get('id'),
                            'url': full_url
                        })
                        results['webhooks'].append(existing_webhook)
                        continue
                    else:
                        # URL mismatch - delete and re-register
                        self.delete_webhook(existing_webhook.get('id'))

                # Register new webhook
                try:
                    new_webhook = self.register_webhook(
                        event=event,
                        url=full_url,
                        system_name=webhook_config['system']
                    )
                    results['registered'].append({
                        'event': event,
                        'id': new_webhook.get('id'),
                        'url': full_url
                    })
                    results['webhooks'].append(new_webhook)
                except Exception as e:
                    results['failed'].append({
                        'event': event,
                        'error': str(e)
                    })

        except Exception as e:
            results['error'] = str(e)

        return results

    ######################## Helper Methods ########################
    @staticmethod
    def parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from FUB API"""
        if not dt_str:
            return None

        try:
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return None
    def add_tag(self, person_id: str, tag: str) -> bool:
        """
        Add a tag to a person in FUB.
        
        Args:
            person_id: FUB person ID
            tag: Tag name to add
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self.base_url}/people/{person_id}"
            
            # Get current person data
            person = self.get_person(person_id)
            if not person:
                logger.error(f"Person {person_id} not found")
                return False
            
            # Get current tags
            current_tags = person.get("tags", [])
            
            # Check if tag already exists
            if tag in current_tags:
                logger.info(f"Tag '{tag}' already exists for person {person_id}")
                return True
            
            # Add new tag
            updated_tags = current_tags + [tag]
            
            # Update person with new tags
            response = requests.put(
                url,
                json={"tags": updated_tags},
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Added tag '{tag}' to person {person_id}")
                return True
            else:
                logger.error(f"Failed to add tag: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error adding tag to person {person_id}: {e}")
            return False
    
    def remove_tag(self, person_id: str, tag: str) -> bool:
        """
        Remove a tag from a person in FUB.
        
        Args:
            person_id: FUB person ID
            tag: Tag name to remove
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self.base_url}/people/{person_id}"
            
            # Get current person data
            person = self.get_person(person_id)
            if not person:
                logger.error(f"Person {person_id} not found")
                return False
            
            # Get current tags
            current_tags = person.get("tags", [])
            
            # Check if tag exists
            if tag not in current_tags:
                logger.info(f"Tag '{tag}' doesn't exist for person {person_id}")
                return True
            
            # Remove tag
            updated_tags = [t for t in current_tags if t != tag]
            
            # Update person with new tags
            response = requests.put(
                url,
                json={"tags": updated_tags},
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Removed tag '{tag}' from person {person_id}")
                return True
            else:
                logger.error(f"Failed to remove tag: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error removing tag from person {person_id}: {e}")
            return False
