"""
Endato API Client - Handles all requests to the Endato enrichment API.
Ported from Leaddata's endato_handle.py.
"""

import os
import requests
import logging
import json
import uuid
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Endato API base URL
ENDATO_BASE_URL = "https://devapi.endato.com"

# Search type to API version mapping
SEARCH_TYPE_MAPPING = {
    'contact_enrichment': 'DevAPIContactEnrich',
    'owner_search': 'DevAPIAddressID',
    'reverse_phone': 'DevAPICallerID',
    'reverse_email': 'DevAPIEmailID',
    'criminal_search': 'CriminalV2',
    'advanced_person_search': 'Person',
    'dnc_check': 'Person',  # DNC uses Person endpoint
}

# Endpoint mapping
ENDPOINT_MAPPING = {
    'Property/Enrich': 'Property/Enrich',
    'Contact/Enrich': 'Contact/Enrich',
    'Phone/Enrich': 'Phone/Enrich',
    'Email/Enrich': 'Email/Enrich',
    'CriminalSearch/V2': 'CriminalSearch/V2',
    'PersonSearch': 'PersonSearch',
    'Address/Id': 'Address/Id',
}


class EndatoClient:
    """
    Client for interacting with the Endato API.

    Handles authentication, request formatting, and response parsing
    for all enrichment search types.
    """

    def __init__(self):
        self.base_url = ENDATO_BASE_URL
        self.key_name = os.environ.get('ENDATO_KEY_NAME')
        self.key_password = os.environ.get('ENDATO_KEY_PASSWORD')

    def _validate_credentials(self) -> bool:
        """Check if API credentials are configured."""
        if not self.key_name or not self.key_password:
            logger.error("Missing Endato API credentials. Set ENDATO_KEY_NAME and ENDATO_KEY_PASSWORD environment variables.")
            return False
        return True

    def _get_headers(self, search_type: str = None) -> Dict[str, str]:
        """
        Build request headers for Endato API.

        Args:
            search_type: The type of search to determine API version

        Returns:
            Dictionary of headers
        """
        if not self._validate_credentials():
            return {}

        # Get API type based on search type
        api_type = SEARCH_TYPE_MAPPING.get(search_type, 'Person')

        # Generate unique session ID
        session_id = str(uuid.uuid4())

        return {
            'galaxy-ap-name': self.key_name,
            'galaxy-ap-password': self.key_password,
            'galaxy-search-type': api_type,
            'galaxy-client-type': 'API',
            'galaxy-client-session-id': session_id,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def _make_request(self, endpoint: str, params: Dict[str, Any],
                      search_type: str = None) -> Optional[Dict[str, Any]]:
        """
        Make a request to the Endato API.

        Args:
            endpoint: The API endpoint to call
            params: Request parameters
            search_type: Type of search for header configuration

        Returns:
            Response data as dictionary, or None on error
        """
        if not self._validate_credentials():
            return None

        try:
            headers = self._get_headers(search_type)
            mapped_endpoint = ENDPOINT_MAPPING.get(endpoint, endpoint)
            url = f"{self.base_url}/{mapped_endpoint}"

            # Log request (without sensitive data)
            logger.info(f"Making Endato request to {mapped_endpoint}")
            logger.debug(f"Request params: {json.dumps(params, indent=2)}")

            # Make the request
            response = requests.post(
                url,
                json=params,
                headers=headers,
                timeout=30
            )

            logger.info(f"Endato response status: {response.status_code}")

            try:
                response_json = response.json()
            except ValueError:
                logger.error(f"Failed to parse Endato response as JSON: {response.text}")
                return None

            # Check for API-specific errors
            if response_json.get('isError'):
                error = response_json.get('error', {})
                error_msg = error.get('message', 'Unknown error')
                tech_msg = error.get('technicalErrorMessage')
                logger.error(f"Endato API error: {error_msg}")
                if tech_msg:
                    logger.error(f"Technical details: {tech_msg}")
                return {'error': {'message': error_msg}}

            # Check HTTP status
            if response.status_code != 200:
                error_msg = response_json.get('message', 'Unknown error')
                logger.error(f"Endato request failed ({response.status_code}): {error_msg}")
                return {'error': {'message': error_msg, 'status_code': response.status_code}}

            return response_json

        except requests.exceptions.Timeout:
            logger.error("Endato request timed out after 30 seconds")
            return {'error': {'message': 'Request timed out'}}
        except requests.exceptions.RequestException as e:
            logger.error(f"Endato request failed: {str(e)}")
            return {'error': {'message': str(e)}}
        except Exception as e:
            logger.error(f"Unexpected error in Endato request: {str(e)}", exc_info=True)
            return {'error': {'message': str(e)}}

    # =========================================================================
    # Search Methods
    # =========================================================================

    def contact_enrichment(self, first_name: str = "", last_name: str = "",
                          phone: str = "", email: str = "",
                          address_line1: str = "", address_line2: str = "") -> Optional[Dict[str, Any]]:
        """
        Search for contact enrichment information.

        Requires at least 2 of: full name, phone, address, or email.

        Args:
            first_name: Person's first name
            last_name: Person's last name
            phone: Phone number
            email: Email address
            address_line1: Street address
            address_line2: City, state, zip

        Returns:
            Enriched contact data or error dict
        """
        params = {}

        if first_name:
            params['FirstName'] = first_name
        if last_name:
            params['LastName'] = last_name
        if phone:
            params['Phone'] = phone
        if email:
            params['Email'] = email

        # Add address if provided
        if address_line1 or address_line2:
            address = {}
            if address_line1:
                address['addressLine1'] = address_line1
            if address_line2:
                address['addressLine2'] = address_line2
            if address:
                params['Address'] = address

        # Verify at least two search criteria
        valid_fields = 0
        if first_name and last_name:
            valid_fields += 1
        if phone:
            valid_fields += 1
        if email:
            valid_fields += 1
        if 'Address' in params:
            valid_fields += 1

        if valid_fields < 2:
            return {'error': {'message': 'Contact enrichment requires at least 2 of: full name, phone, address, or email'}}

        params['search_type'] = 'contact_enrichment'
        return self._make_request('Contact/Enrich', params, 'contact_enrichment')

    def reverse_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """
        Perform a reverse phone lookup.

        Args:
            phone: Phone number to search (any format)

        Returns:
            Person data associated with phone or error dict
        """
        if not phone:
            return {'error': {'message': 'Phone number is required'}}

        # Format phone number - remove all non-digits first
        phone_digits = ''.join(c for c in phone if c.isdigit())

        if len(phone_digits) < 10:
            return {'error': {'message': 'Invalid phone number format'}}

        # Format to (XXX) XXX-XXXX
        if len(phone_digits) == 10:
            formatted_phone = f"({phone_digits[:3]}) {phone_digits[3:6]}-{phone_digits[6:]}"
        elif len(phone_digits) == 11 and phone_digits[0] == '1':
            # Handle +1 country code
            phone_digits = phone_digits[1:]
            formatted_phone = f"({phone_digits[:3]}) {phone_digits[3:6]}-{phone_digits[6:]}"
        else:
            formatted_phone = phone

        params = {
            'Phone': formatted_phone,
            'search_type': 'reverse_phone'
        }

        return self._make_request('Phone/Enrich', params, 'reverse_phone')

    def reverse_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Perform a reverse email lookup.

        Args:
            email: Email address to search

        Returns:
            Person data associated with email or error dict
        """
        if not email:
            return {'error': {'message': 'Email address is required'}}

        params = {
            'Email': email
        }

        return self._make_request('Email/Enrich', params, 'reverse_email')

    def criminal_search(self, first_name: str, last_name: str,
                       state: str = None) -> Optional[Dict[str, Any]]:
        """
        Perform a criminal history search.

        Args:
            first_name: Person's first name
            last_name: Person's last name
            state: Two-letter state code (optional, improves accuracy)

        Returns:
            Criminal history data or error dict
        """
        if not first_name or not last_name:
            return {'error': {'message': 'First name and last name are required'}}

        params = {
            'searchType': 'criminal_history_search',
            'firstName': first_name,
            'lastName': last_name,
            'includeDetails': True,
            'exactMatch': True,
            'matchThreshold': 80,
            'includeAKAs': True,
            'includeAddresses': True,
            'includeOffenses': True,
            'includeArrestInfo': True,
            'includeCourtInfo': True,
            'includeProbationInfo': True,
            'includeParoleInfo': True,
            'includeBondInfo': True,
            'includeSentenceInfo': True,
        }

        if state:
            params['state'] = state.upper()

        return self._make_request('CriminalSearch/V2', params, 'criminal_search')

    def owner_search(self, address: str, searched_name: str = None) -> Optional[Dict[str, Any]]:
        """
        Search for property owner information from an address.

        Args:
            address: Full address (street, city, state zip)
            searched_name: Optional name to prioritize in results

        Returns:
            Property owner data or error dict
        """
        if not address:
            return {'error': {'message': 'Address is required'}}

        try:
            # Parse address
            parts = address.split(',')
            if len(parts) < 3:
                return {'error': {'message': 'Invalid address format. Expected: street, city, state zip'}}

            street = parts[0].strip()
            city = parts[1].strip()
            state_zip = parts[2].strip()

            # Split state and zip
            state_zip_parts = state_zip.split(' ', 1)
            state = state_zip_parts[0].strip()

            params = {
                'search_type': 'DevAPIAddressID',
                'AddressLine1': street,
                'AddressLine2': f"{city}, {state}"
            }

            result = self._make_request('Address/Id', params, 'owner_search')

            if not result or 'error' in result:
                return result or {'error': {'message': 'No results found for this address'}}

            # Process results
            if 'persons' in result and result['persons']:
                persons = result['persons']
                primary_person_index = 0

                # Match searched name if provided
                if searched_name:
                    searched_name_lower = searched_name.lower()
                    for i, person in enumerate(persons):
                        name = person.get('name', {})
                        full_name = f"{name.get('firstName', '')} {name.get('lastName', '')}".lower()
                        if searched_name_lower in full_name:
                            primary_person_index = i
                            break

                # Reorder to put matched person first
                primary_person = persons.pop(primary_person_index)
                additional_persons = persons

                return {
                    'person': {
                        'name': primary_person.get('name'),
                        'age': primary_person.get('age'),
                        'phones': primary_person.get('phones', []),
                        'emails': primary_person.get('emails', []),
                        'addresses': primary_person.get('addresses', [])
                    },
                    'additionalPersons': [
                        {
                            'name': p.get('name'),
                            'age': p.get('age'),
                            'phones': p.get('phones', []),
                            'emails': p.get('emails', []),
                            'addresses': p.get('addresses', [])
                        } for p in additional_persons
                    ]
                }

            return {'error': {'message': 'No results found for this address'}}

        except Exception as e:
            logger.error(f"Error processing address: {str(e)}", exc_info=True)
            return {'error': {'message': f'Error processing address: {str(e)}'}}

    def person_search(self, first_name: str = None, last_name: str = None,
                     city: str = None, state: str = None,
                     age: int = None, dob: str = None) -> Optional[Dict[str, Any]]:
        """
        Perform an advanced person search with multiple criteria.

        Args:
            first_name: Person's first name
            last_name: Person's last name
            city: City to search
            state: Two-letter state code
            age: Approximate age
            dob: Date of birth (YYYY-MM-DD)

        Returns:
            Person search results or error dict
        """
        if not last_name:
            return {'error': {'message': 'Last name is required for person search'}}

        params = {
            'LastName': last_name
        }

        if first_name:
            params['FirstName'] = first_name
        if city:
            params['City'] = city
        if state:
            params['State'] = state.upper()
        if age:
            params['Age'] = age
        if dob:
            params['DateOfBirth'] = dob

        return self._make_request('PersonSearch', params, 'advanced_person_search')


# Singleton instance
_endato_client_instance = None


def get_endato_client() -> EndatoClient:
    """Get or create the Endato client singleton."""
    global _endato_client_instance
    if _endato_client_instance is None:
        _endato_client_instance = EndatoClient()
    return _endato_client_instance


class EndatoClientSingleton:
    """Singleton wrapper for backward compatibility."""
    _instance = None

    @classmethod
    def get_instance(cls) -> EndatoClient:
        if cls._instance is None:
            cls._instance = EndatoClient()
        return cls._instance
