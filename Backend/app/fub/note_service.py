"""
FUB Note Service - Posts enrichment notes to Follow Up Boss.

Handles:
- Posting rich HTML notes to FUB contacts
- Adding new contact information (phones/emails) discovered during enrichment
- Managing FUB API authentication
"""

import os
import requests
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.fub.note_generators import generate_note_for_search

logger = logging.getLogger(__name__)

# FUB API base URL
FUB_API_BASE_URL = "https://api.followupboss.com/v1"


class FUBNoteService:
    """
    Service for posting notes and updates to Follow Up Boss.
    """

    def __init__(self, api_key: str = None):
        """
        Initialize the FUB Note Service.

        Args:
            api_key: FUB API key. If not provided, uses FUB_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get('FUB_API_KEY')
        self.base_url = FUB_API_BASE_URL

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for FUB API requests."""
        if not self.api_key:
            logger.error("FUB API key not configured")
            return {}

        # FUB uses Basic auth with API key as username, no password
        import base64
        auth_string = base64.b64encode(f"{self.api_key}:".encode()).decode()

        return {
            'Authorization': f'Basic {auth_string}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def _make_request(self, method: str, endpoint: str,
                      data: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Make a request to the FUB API.

        Args:
            method: HTTP method (GET, POST, PUT, etc.)
            endpoint: API endpoint (e.g., '/people/123/notes')
            data: Request body for POST/PUT

        Returns:
            Response data as dict, or None on error
        """
        if not self.api_key:
            logger.error("Cannot make FUB request: API key not configured")
            return None

        try:
            url = f"{self.base_url}{endpoint}"
            headers = self._get_headers()

            logger.info(f"Making FUB API request: {method} {endpoint}")

            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                timeout=30
            )

            logger.info(f"FUB API response status: {response.status_code}")

            if response.status_code in [200, 201]:
                return response.json()
            elif response.status_code == 204:
                return {'success': True}
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', response.text)
                except Exception:
                    error_msg = response.text

                logger.error(f"FUB API error ({response.status_code}): {error_msg}")
                return {'error': error_msg, 'status_code': response.status_code}

        except requests.exceptions.Timeout:
            logger.error("FUB API request timed out")
            return {'error': 'Request timed out'}
        except requests.exceptions.RequestException as e:
            logger.error(f"FUB API request failed: {e}")
            return {'error': str(e)}
        except Exception as e:
            logger.error(f"Unexpected error in FUB API request: {e}", exc_info=True)
            return {'error': str(e)}

    def post_note_to_person(self, person_id: int, subject: str, body: str,
                            is_html: bool = True) -> Optional[Dict[str, Any]]:
        """
        Post a note to a FUB person/contact.

        Args:
            person_id: The FUB person ID
            subject: Note subject/title
            body: Note body (can be HTML)
            is_html: Whether the body contains HTML

        Returns:
            Response data or None on error
        """
        if not person_id:
            logger.error("Cannot post note: No person ID provided")
            return None

        data = {
            'subject': subject,
            'body': body,
            'isHtml': is_html
        }

        return self._make_request('POST', f'/people/{person_id}/notes', data)

    def post_enrichment_note(self, person_id: int, search_type: str,
                             search_data: Dict[str, Any],
                             search_criteria: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Post an enrichment result note to FUB.

        Args:
            person_id: The FUB person ID
            search_type: Type of search performed
            search_data: The search result data
            search_criteria: The original search parameters

        Returns:
            Response data or None on error
        """
        # Generate the note HTML
        note_html = generate_note_for_search(search_type, search_data, search_criteria)

        # Create subject based on search type
        subject_map = {
            'contact_enrichment': 'Contact Enrichment Results',
            'criminal_history_search': 'Criminal History Check',
            'dnc_check': 'DNC Compliance Check',
            'reverse_phone_search': 'Reverse Phone Lookup',
            'reverse_email_search': 'Reverse Email Lookup',
            'owner_search': 'Property Owner Search',
            'advanced_person_search': 'Person Search Results'
        }

        subject = subject_map.get(search_type, f'LeadSynergy: {search_type}')

        logger.info(f"Posting {search_type} note to FUB person {person_id}")

        result = self.post_note_to_person(
            person_id=person_id,
            subject=subject,
            body=note_html,
            is_html=True
        )

        if result and 'error' not in result:
            logger.info(f"Successfully posted {search_type} note to FUB")
        else:
            logger.warning(f"Failed to post note to FUB: {result}")

        return result

    def add_phone_to_person(self, person_id: int, phone: str,
                            phone_type: str = 'mobile') -> Optional[Dict[str, Any]]:
        """
        Add a phone number to a FUB person.

        Args:
            person_id: The FUB person ID
            phone: Phone number to add
            phone_type: Type of phone (mobile, home, work, etc.)

        Returns:
            Response data or None on error
        """
        if not person_id or not phone:
            return None

        # First get the current person data
        person_data = self._make_request('GET', f'/people/{person_id}')
        if not person_data or 'error' in person_data:
            return person_data

        # Get existing phones
        existing_phones = person_data.get('phones', [])

        # Check if phone already exists
        phone_digits = ''.join(c for c in phone if c.isdigit())
        for existing in existing_phones:
            existing_digits = ''.join(c for c in existing.get('value', '') if c.isdigit())
            if phone_digits == existing_digits:
                logger.info(f"Phone {phone} already exists for person {person_id}")
                return {'message': 'Phone already exists', 'existing': True}

        # Add new phone
        new_phones = existing_phones + [{'value': phone, 'type': phone_type}]

        return self._make_request('PUT', f'/people/{person_id}', {
            'phones': new_phones
        })

    def add_email_to_person(self, person_id: int, email: str,
                            email_type: str = 'personal') -> Optional[Dict[str, Any]]:
        """
        Add an email address to a FUB person.

        Args:
            person_id: The FUB person ID
            email: Email address to add
            email_type: Type of email (personal, work, etc.)

        Returns:
            Response data or None on error
        """
        if not person_id or not email:
            return None

        # First get the current person data
        person_data = self._make_request('GET', f'/people/{person_id}')
        if not person_data or 'error' in person_data:
            return person_data

        # Get existing emails
        existing_emails = person_data.get('emails', [])

        # Check if email already exists
        email_lower = email.lower()
        for existing in existing_emails:
            if existing.get('value', '').lower() == email_lower:
                logger.info(f"Email {email} already exists for person {person_id}")
                return {'message': 'Email already exists', 'existing': True}

        # Add new email
        new_emails = existing_emails + [{'value': email, 'type': email_type}]

        return self._make_request('PUT', f'/people/{person_id}', {
            'emails': new_emails
        })

    def add_enrichment_data_to_person(self, person_id: int,
                                      enrichment_data: Dict[str, Any],
                                      add_phones: bool = True,
                                      add_emails: bool = True) -> Dict[str, Any]:
        """
        Add discovered phones and emails from enrichment to a FUB person.

        Args:
            person_id: The FUB person ID
            enrichment_data: The enrichment result data
            add_phones: Whether to add discovered phones
            add_emails: Whether to add discovered emails

        Returns:
            Summary of what was added
        """
        results = {
            'phones_added': 0,
            'emails_added': 0,
            'errors': []
        }

        if not person_id:
            results['errors'].append('No person ID provided')
            return results

        # Extract contact data
        person_data = enrichment_data.get('person', enrichment_data)
        phones = person_data.get('phones', [])
        emails = person_data.get('emails', [])

        # Add phones
        if add_phones and phones:
            for phone_data in phones[:5]:  # Limit to 5
                phone = phone_data.get('number', phone_data.get('phone'))
                if phone:
                    phone_type = 'mobile' if phone_data.get('isMobile') else phone_data.get('type', 'other')
                    result = self.add_phone_to_person(person_id, phone, phone_type)
                    if result and 'error' not in result and not result.get('existing'):
                        results['phones_added'] += 1
                    elif result and 'error' in result:
                        results['errors'].append(f"Failed to add phone: {result['error']}")

        # Add emails
        if add_emails and emails:
            for email_data in emails[:5]:  # Limit to 5
                email = email_data.get('email', email_data) if isinstance(email_data, dict) else email_data
                if email:
                    email_type = email_data.get('type', 'personal') if isinstance(email_data, dict) else 'personal'
                    result = self.add_email_to_person(person_id, email, email_type)
                    if result and 'error' not in result and not result.get('existing'):
                        results['emails_added'] += 1
                    elif result and 'error' in result:
                        results['errors'].append(f"Failed to add email: {result['error']}")

        logger.info(f"Added {results['phones_added']} phones, {results['emails_added']} emails to person {person_id}")

        return results

    def get_person(self, person_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a FUB person by ID.

        Args:
            person_id: The FUB person ID

        Returns:
            Person data or None on error
        """
        return self._make_request('GET', f'/people/{person_id}')

    def search_people(self, query: str = None, email: str = None,
                      phone: str = None, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
        """
        Search for people in FUB.

        Args:
            query: General search query
            email: Search by email
            phone: Search by phone
            limit: Max results to return

        Returns:
            List of matching people or None on error
        """
        params = []
        if query:
            params.append(f"q={query}")
        if email:
            params.append(f"email={email}")
        if phone:
            params.append(f"phone={phone}")
        params.append(f"limit={limit}")

        endpoint = f"/people?{'&'.join(params)}"
        result = self._make_request('GET', endpoint)

        if result and 'people' in result:
            return result['people']
        return result


# =============================================================================
# Singleton Pattern
# =============================================================================

_note_service_instance = None


def get_note_service() -> FUBNoteService:
    """Get or create the FUB Note Service singleton."""
    global _note_service_instance
    if _note_service_instance is None:
        _note_service_instance = FUBNoteService()
    return _note_service_instance


class FUBNoteServiceSingleton:
    """Singleton wrapper for backward compatibility."""
    _instance = None

    @classmethod
    def get_instance(cls) -> FUBNoteService:
        if cls._instance is None:
            cls._instance = FUBNoteService()
        return cls._instance


# =============================================================================
# Convenience Functions
# =============================================================================

def post_enrichment_note_to_fub(person_id: int, search_type: str,
                                 search_data: Dict[str, Any],
                                 search_criteria: Dict[str, Any] = None,
                                 api_key: str = None) -> Optional[Dict[str, Any]]:
    """
    Convenience function to post an enrichment note to FUB.

    Args:
        person_id: The FUB person ID
        search_type: Type of search performed
        search_data: The search result data
        search_criteria: The original search parameters
        api_key: Optional FUB API key (uses env var if not provided)

    Returns:
        Response data or None on error
    """
    service = FUBNoteService(api_key) if api_key else get_note_service()
    return service.post_enrichment_note(person_id, search_type, search_data, search_criteria)


def add_enrichment_contact_data(person_id: int, enrichment_data: Dict[str, Any],
                                 add_phones: bool = True, add_emails: bool = True,
                                 api_key: str = None) -> Dict[str, Any]:
    """
    Convenience function to add enrichment contact data to FUB.

    Args:
        person_id: The FUB person ID
        enrichment_data: The enrichment result data
        add_phones: Whether to add discovered phones
        add_emails: Whether to add discovered emails
        api_key: Optional FUB API key (uses env var if not provided)

    Returns:
        Summary of what was added
    """
    service = FUBNoteService(api_key) if api_key else get_note_service()
    return service.add_enrichment_data_to_person(
        person_id, enrichment_data, add_phones, add_emails
    )
