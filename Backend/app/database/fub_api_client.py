import base64
import json
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
        
    
    def _add_system_headers(self, system_name: str = None, system_key: str = None) -> Dict[str, str]:
        """Add System Headers"""
        headers = self.headers.copy()
        
        if system_name:
            headers['X-System'] = system_name
            
        if system_key:
            headers['X-System-Key'] = system_key
            
        return headers
    
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
    
    
    def get_person(self, person_id: str) -> Dict[str, Any]:
        """Get person by their ID"""
        headers = self._add_system_headers(
            self.creds.TAG_SYSTEM_NAME,
            self.creds.TAG_SYSTEM_KEY
        )
        
        url = f"{self.base_url}people/{person_id}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        return response.json()
    
    def get_notes_for_person(self, person_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get notes for a specific person"""
        headers = self._add_system_headers(
            self.creds.NOTE_CREATED_SYSTEM_NAME,
            self.creds.NOTE_SYSTEM_KEY
        )
        
        url = f"{self.base_url}people/{person_id}/notes"
        params = {
            "limit": limit,
            "offset": offset
        }
        
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        return response.json().get("notes", [])
    
    
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