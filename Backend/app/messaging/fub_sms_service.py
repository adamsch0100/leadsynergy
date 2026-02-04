"""
FUB SMS Service - Send text messages via Follow Up Boss Native Texting.

This service integrates with Follow Up Boss's built-in texting functionality
to send SMS messages to leads. Messages are sent through the FUB API and
appear in the lead's timeline within FUB.

Note: FUB Native Texting requires:
- Phone numbers assigned to agents in FUB
- FUB plan that includes texting feature
- textMessages webhook registered for inbound messages
"""

import logging
import base64
import aiohttp
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.utils.constants import Credentials

logger = logging.getLogger(__name__)


class FUBSMSService:
    """
    Service for sending SMS via Follow Up Boss Native Texting.

    FUB Native Texting allows sending real SMS messages that are:
    - Delivered to the lead's phone
    - Logged in the lead's FUB timeline
    - Associated with the sending agent
    """

    def __init__(self, api_key: str = None, user_id: int = None):
        """
        Initialize FUB SMS Service.

        Args:
            api_key: FUB API key (uses env default if not provided)
            user_id: FUB user ID to send messages as (optional)
        """
        self.creds = Credentials()
        self.api_key = api_key or self.creds.FUB_API_KEY
        self.base_url = "https://api.followupboss.com/v1/"
        self.auth_header = f"Basic {base64.b64encode(f'{self.api_key}:'.encode()).decode()}"
        self.headers = {
            'Content-Type': "application/json",
            'Authorization': self.auth_header,
        }
        self.user_id = user_id

    def _get_headers(self, system_name: str = None, system_key: str = None) -> Dict[str, str]:
        """Get headers with optional system identification."""
        headers = self.headers.copy()
        if system_name:
            headers['X-System'] = system_name
        if system_key:
            headers['X-System-Key'] = system_key
        return headers

    def send_text_message(
        self,
        person_id: int,
        message: str,
        from_user_id: int = None,
        phone_number: str = None,
    ) -> Dict[str, Any]:
        """
        Send a text message to a lead via FUB Native Texting.

        Args:
            person_id: FUB person ID to send message to
            message: Text message content
            from_user_id: FUB user ID to send from (optional)
            phone_number: Specific phone number to text (optional, uses primary if not specified)

        Returns:
            Dict with message details including ID

        Raises:
            Exception if message fails to send
        """
        headers = self._get_headers(
            self.creds.get('FUB_SYSTEM_NAME', 'leadsynergy-ai'),
            self.creds.get('FUB_SYSTEM_KEY'),
        )

        # Get agent's phone number for fromNumber field
        from_number = None
        if from_user_id or self.user_id:
            agent_user_id = from_user_id or self.user_id
            try:
                # Fetch agent's user profile from FUB to get their phone number
                user_response = requests.get(
                    f"{self.base_url}users/{agent_user_id}",
                    headers={"Authorization": self.auth_header},
                    timeout=10,
                )
                if user_response.status_code == 200:
                    user_data = user_response.json()
                    # FUB user profile has phone in direct field, not phones array
                    phone = user_data.get("phone")
                    if phone:
                        # Format as E.164 if not already (add +1 for US numbers)
                        if not phone.startswith('+'):
                            from_number = f"+1{phone}"
                        else:
                            from_number = phone
                        logger.info(f"Using agent phone number: {from_number}")
            except Exception as e:
                logger.warning(f"Could not fetch agent phone number: {e}")

        # Build request payload
        payload = {
            "personId": person_id,
            "message": message,
            "isIncoming": False,  # Outbound message
        }

        # Add fromNumber (agent's phone)
        if from_number:
            payload["fromNumber"] = from_number

        # Add specific phone if provided (recipient)
        if phone_number:
            payload["toNumber"] = phone_number

        try:
            response = requests.post(
                f"{self.base_url}textMessages",
                headers=headers,
                json=payload,
                timeout=30,
            )

            if response.status_code == 201:
                result = response.json()
                logger.info(f"SMS sent to person {person_id}: {message[:50]}...")
                return {
                    "success": True,
                    "message_id": result.get("id"),
                    "data": result,
                }
            else:
                error_msg = f"FUB API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                }

        except Exception as e:
            error_msg = f"Failed to send SMS: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
            }

    async def send_text_message_async(
        self,
        person_id: int,
        message: str,
        from_user_id: int = None,
        phone_number: str = None,
    ) -> Dict[str, Any]:
        """
        Send text message asynchronously.

        Args:
            person_id: FUB person ID
            message: Text message content
            from_user_id: FUB user ID to send from
            phone_number: Specific phone number to text

        Returns:
            Dict with message details
        """
        headers = self._get_headers(
            self.creds.get('FUB_SYSTEM_NAME', 'leadsynergy-ai'),
            self.creds.get('FUB_SYSTEM_KEY'),
        )

        payload = {
            "personId": person_id,
            "message": message,
            "isIncoming": False,
        }

        if from_user_id or self.user_id:
            payload["userId"] = from_user_id or self.user_id

        if phone_number:
            payload["toNumber"] = phone_number

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}textMessages",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 201:
                        result = await response.json()
                        logger.info(f"SMS sent to person {person_id}: {message[:50]}...")
                        return {
                            "success": True,
                            "message_id": result.get("id"),
                            "data": result,
                        }
                    else:
                        error_text = await response.text()
                        error_msg = f"FUB API error {response.status}: {error_text}"
                        logger.error(error_msg)
                        return {
                            "success": False,
                            "error": error_msg,
                        }

        except Exception as e:
            error_msg = f"Failed to send SMS: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
            }

    def get_text_messages(
        self,
        person_id: int,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get text message history for a person.

        Args:
            person_id: FUB person ID
            limit: Maximum messages to retrieve

        Returns:
            List of text message records
        """
        headers = self._get_headers()

        try:
            response = requests.get(
                f"{self.base_url}textMessages",
                headers=headers,
                params={
                    "personId": person_id,
                    "limit": limit,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("textmessages", [])

        except Exception as e:
            logger.error(f"Failed to get text messages: {str(e)}")
            return []

    async def get_text_messages_async(
        self,
        person_id: int,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get text message history asynchronously."""
        headers = self._get_headers()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}textMessages",
                    headers=headers,
                    params={
                        "personId": person_id,
                        "limit": limit,
                    },
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("textmessages", [])
                    return []

        except Exception as e:
            logger.error(f"Failed to get text messages: {str(e)}")
            return []

    def create_task(
        self,
        person_id: int,
        description: str,
        assigned_to: int = None,
        due_date: datetime = None,
    ) -> Dict[str, Any]:
        """
        Create a follow-up task in FUB.

        Args:
            person_id: FUB person ID
            description: Task description
            assigned_to: FUB user ID to assign task to
            due_date: When the task is due

        Returns:
            Dict with task details
        """
        headers = self._get_headers()

        payload = {
            "personId": person_id,
            "name": description,
        }

        if assigned_to:
            payload["assignedTo"] = assigned_to

        if due_date:
            payload["dueDate"] = due_date.isoformat()

        try:
            response = requests.post(
                f"{self.base_url}tasks",
                headers=headers,
                json=payload,
                timeout=30,
            )

            if response.status_code in [200, 201]:
                result = response.json()
                logger.info(f"Task created for person {person_id}: {description[:50]}...")
                return {
                    "success": True,
                    "task_id": result.get("id"),
                    "data": result,
                }
            else:
                error_msg = f"FUB API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                }

        except Exception as e:
            error_msg = f"Failed to create task: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
            }

    def add_note(
        self,
        person_id: int,
        note_content: str,
        is_private: bool = False,
    ) -> Dict[str, Any]:
        """
        Add a note to a person's record in FUB.

        Args:
            person_id: FUB person ID
            note_content: Note content (can include HTML)
            is_private: Whether note is private to the user

        Returns:
            Dict with note details
        """
        headers = self._get_headers(
            self.creds.get('FUB_SYSTEM_NAME', 'leadsynergy-ai'),
            self.creds.get('FUB_SYSTEM_KEY'),
        )

        payload = {
            "personId": person_id,
            "body": note_content,
            "isPrivate": is_private,
        }

        try:
            response = requests.post(
                f"{self.base_url}notes",
                headers=headers,
                json=payload,
                timeout=30,
            )

            if response.status_code in [200, 201]:
                result = response.json()
                logger.info(f"Note added for person {person_id}")
                return {
                    "success": True,
                    "note_id": result.get("id"),
                    "data": result,
                }
            else:
                error_msg = f"FUB API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                }

        except Exception as e:
            error_msg = f"Failed to add note: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
            }

    def create_appointment(
        self,
        person_id: int,
        title: str,
        start_time: datetime,
        end_time: datetime = None,
        description: str = None,
        location: str = None,
        assigned_to: int = None,
    ) -> Dict[str, Any]:
        """
        Create an appointment in FUB.

        Args:
            person_id: FUB person ID
            title: Appointment title
            start_time: Start datetime
            end_time: End datetime (defaults to 30 min after start)
            description: Optional description
            location: Optional location
            assigned_to: FUB user ID to assign to

        Returns:
            Dict with appointment details
        """
        headers = self._get_headers()

        # Default to 30 min appointment
        if not end_time:
            from datetime import timedelta
            end_time = start_time + timedelta(minutes=30)

        payload = {
            "personId": person_id,
            "title": title,
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
        }

        if description:
            payload["description"] = description

        if location:
            payload["location"] = location

        if assigned_to:
            payload["assignedTo"] = assigned_to

        try:
            response = requests.post(
                f"{self.base_url}appointments",
                headers=headers,
                json=payload,
                timeout=30,
            )

            if response.status_code in [200, 201]:
                result = response.json()
                logger.info(f"Appointment created for person {person_id}: {title}")
                return {
                    "success": True,
                    "appointment_id": result.get("id"),
                    "data": result,
                }
            else:
                error_msg = f"FUB API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                }

        except Exception as e:
            error_msg = f"Failed to create appointment: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
            }


class FUBSMSServiceSingleton:
    """Singleton wrapper for FUB SMS Service."""

    _instance: Optional[FUBSMSService] = None

    @classmethod
    def get_instance(cls, api_key: str = None) -> FUBSMSService:
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = FUBSMSService(api_key=api_key)
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset the singleton instance."""
        cls._instance = None


# Convenience function
async def send_sms(
    person_id: int,
    message: str,
    api_key: str = None,
    from_user_id: int = None,
) -> Dict[str, Any]:
    """Quick SMS send with default service."""
    service = FUBSMSServiceSingleton.get_instance(api_key)
    return await service.send_text_message_async(
        person_id=person_id,
        message=message,
        from_user_id=from_user_id,
    )
