"""
Helper utility for working with FUB API using user-specific API keys.

This demonstrates how to use the updated FUBApiClient with multi-tenant support.
"""

from typing import Dict, Any, Optional, List
from app.database.fub_api_client import FUBApiClient
from app.service.fub_api_key_service import FUBAPIKeyServiceSingleton
from app.middleware.fub_api_key_middleware import get_user_fub_api_key, get_current_user_id

def get_fub_client_for_user(user_id: str) -> Optional[FUBApiClient]:
    """
    Get a FUB API client instance for a specific user.
    
    Args:
        user_id: The user's ID
        
    Returns:
        FUBApiClient instance with the user's API key, or None if no API key found
    """
    fub_service = FUBAPIKeyServiceSingleton.get_instance()
    api_key = fub_service.get_api_key_for_user(user_id)
    
    if not api_key:
        return None
        
    return FUBApiClient(api_key)

def get_fub_client_from_request() -> Optional[FUBApiClient]:
    """
    Get a FUB API client instance using the current request context.
    This should be used within routes that have the @fub_api_key_required decorator.
    
    Returns:
        FUBApiClient instance with the current user's API key, or None if not available
    """
    api_key = get_user_fub_api_key()
    
    if not api_key:
        return None
        
    return FUBApiClient(api_key)

def get_fub_leads_for_user(user_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Example function showing how to get FUB leads for a specific user.
    
    Args:
        user_id: The user's ID
        limit: Number of leads to fetch
        offset: Offset for pagination
        
    Returns:
        List of lead dictionaries from FUB API
    """
    client = get_fub_client_for_user(user_id)
    if not client:
        raise ValueError(f"No FUB API key found for user {user_id}")
    
    # Use the client to make FUB API calls
    # Note: You'll need to implement these methods in the FUBApiClient
    # This is just an example of the pattern
    try:
        # This would be implemented in the FUB API client
        # response = client.get_people(limit=limit, offset=offset)
        # return response.get('people', [])
        return []
    except Exception as e:
        print(f"Error fetching leads for user {user_id}: {str(e)}")
        return []

def create_fub_note_for_user(user_id: str, person_id: str, note_content: str) -> Optional[Dict[str, Any]]:
    """
    Example function showing how to create a FUB note for a specific user.
    
    Args:
        user_id: The user's ID
        person_id: The FUB person ID
        note_content: Content of the note
        
    Returns:
        Created note data from FUB API, or None if failed
    """
    client = get_fub_client_for_user(user_id)
    if not client:
        raise ValueError(f"No FUB API key found for user {user_id}")
    
    try:
        # This would be implemented in the FUB API client
        # response = client.create_note(person_id, note_content)
        # return response
        return None
    except Exception as e:
        print(f"Error creating note for user {user_id}: {str(e)}")
        return None

# Example of how to update existing services to use user-specific API keys:

class UserSpecificLeadService:
    """
    Example service showing how to modify existing services to use user-specific FUB API keys.
    """
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.fub_client = get_fub_client_for_user(user_id)
        
        if not self.fub_client:
            raise ValueError(f"No FUB API key configured for user {user_id}")
    
    def sync_leads_from_fub(self) -> List[Dict[str, Any]]:
        """
        Sync leads from FUB using the user's API key.
        """
        try:
            # Use the user's FUB client to fetch leads
            # leads = self.fub_client.get_people()
            # Process and store leads...
            return []
        except Exception as e:
            print(f"Error syncing leads for user {self.user_id}: {str(e)}")
            return []
    
    def create_lead_in_fub(self, lead_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create a lead in FUB using the user's API key.
        """
        try:
            # Use the user's FUB client to create lead
            # result = self.fub_client.create_person(lead_data)
            # return result
            return None
        except Exception as e:
            print(f"Error creating lead in FUB for user {self.user_id}: {str(e)}")
            return None 