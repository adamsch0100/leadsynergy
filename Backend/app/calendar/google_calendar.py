"""
Google Calendar Service - Calendar integration for appointment scheduling.

Provides:
- Availability checking based on agent's Google Calendar
- Appointment booking with calendar event creation
- Time slot generation for scheduling UI
- Appointment reminders and confirmations

Requires Google Calendar API credentials configured in environment.
"""

import logging
import os
from datetime import datetime, timedelta, time
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)

# Google Calendar imports - optional dependency
try:
    from google.oauth2.credentials import Credentials
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_CALENDAR_AVAILABLE = True
except ImportError:
    GOOGLE_CALENDAR_AVAILABLE = False
    logger.warning("Google Calendar API not installed. Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")


@dataclass
class TimeSlot:
    """Represents an available time slot."""
    start: datetime
    end: datetime
    duration_minutes: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "duration_minutes": self.duration_minutes,
            "display": self.start.strftime("%A, %B %d at %I:%M %p"),
        }

    def __str__(self) -> str:
        return self.start.strftime("%A, %B %d at %I:%M %p")


class GoogleCalendarService:
    """
    Service for Google Calendar integration.

    Handles:
    - OAuth2 or Service Account authentication
    - Checking calendar availability
    - Creating and managing calendar events
    - Generating available time slots for booking
    """

    # Default appointment duration
    DEFAULT_DURATION_MINUTES = 30

    # Working hours (for slot generation)
    DEFAULT_WORKING_START = time(9, 0)   # 9 AM
    DEFAULT_WORKING_END = time(17, 0)    # 5 PM

    def __init__(
        self,
        credentials_path: str = None,
        calendar_id: str = "primary",
        service_account: bool = False,
    ):
        """
        Initialize Google Calendar service.

        Args:
            credentials_path: Path to credentials JSON file
            calendar_id: Google Calendar ID (default: "primary")
            service_account: Whether to use service account auth
        """
        self.calendar_id = calendar_id
        self.credentials_path = credentials_path or os.getenv("GOOGLE_CALENDAR_CREDENTIALS")
        self.use_service_account = service_account
        self.service = None
        self._initialized = False

        if not GOOGLE_CALENDAR_AVAILABLE:
            logger.warning("Google Calendar API not available")

    def _initialize(self) -> bool:
        """Initialize Google Calendar API service."""
        if self._initialized:
            return True

        if not GOOGLE_CALENDAR_AVAILABLE:
            return False

        if not self.credentials_path:
            logger.error("No credentials path provided")
            return False

        try:
            if self.use_service_account:
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=['https://www.googleapis.com/auth/calendar']
                )
            else:
                # OAuth2 credentials (from saved token)
                with open(self.credentials_path, 'r') as f:
                    creds_data = json.load(f)
                credentials = Credentials.from_authorized_user_info(creds_data)

            self.service = build('calendar', 'v3', credentials=credentials)
            self._initialized = True
            logger.info("Google Calendar service initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Google Calendar: {e}")
            return False

    async def get_available_slots(
        self,
        agent_user_id: str,
        start_date: datetime = None,
        end_date: datetime = None,
        duration_minutes: int = None,
        working_hours: Tuple[time, time] = None,
        supabase_client=None,
    ) -> List[TimeSlot]:
        """
        Get available time slots for an agent.

        Args:
            agent_user_id: LeadSynergy user ID of agent
            start_date: Start of date range to check (default: tomorrow)
            end_date: End of date range (default: 7 days from start)
            duration_minutes: Appointment duration (default: 30)
            working_hours: Tuple of (start_time, end_time)
            supabase_client: Database client for agent availability

        Returns:
            List of available TimeSlot objects
        """
        duration = duration_minutes or self.DEFAULT_DURATION_MINUTES

        # Default to next 7 days starting tomorrow
        if not start_date:
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        if not end_date:
            end_date = start_date + timedelta(days=7)

        # Get agent's availability settings
        availability_settings = await self._get_agent_availability(agent_user_id, supabase_client)

        # Get busy times from Google Calendar
        busy_times = await self._get_busy_times(start_date, end_date)

        # Generate slots based on availability minus busy times
        slots = self._generate_available_slots(
            start_date=start_date,
            end_date=end_date,
            duration_minutes=duration,
            busy_times=busy_times,
            availability_settings=availability_settings,
            working_hours=working_hours,
        )

        return slots

    async def _get_agent_availability(
        self,
        user_id: str,
        supabase_client=None,
    ) -> Dict[int, List[Tuple[time, time]]]:
        """
        Get agent's availability settings from database.

        Returns:
            Dict mapping day_of_week (0-6) to list of (start, end) time tuples
        """
        if not supabase_client:
            # Return default availability (Mon-Fri 9-5)
            default_hours = [(self.DEFAULT_WORKING_START, self.DEFAULT_WORKING_END)]
            return {
                0: [],  # Sunday
                1: default_hours,  # Monday
                2: default_hours,  # Tuesday
                3: default_hours,  # Wednesday
                4: default_hours,  # Thursday
                5: default_hours,  # Friday
                6: [],  # Saturday
            }

        try:
            result = supabase_client.table("agent_availability").select("*").eq(
                "user_id", user_id
            ).eq(
                "is_available", True
            ).execute()

            availability = {i: [] for i in range(7)}

            for row in result.data:
                day = row["day_of_week"]
                start = time.fromisoformat(row["start_time"])
                end = time.fromisoformat(row["end_time"])
                availability[day].append((start, end))

            return availability

        except Exception as e:
            logger.error(f"Error fetching agent availability: {e}")
            # Return default
            default_hours = [(self.DEFAULT_WORKING_START, self.DEFAULT_WORKING_END)]
            return {i: default_hours if 1 <= i <= 5 else [] for i in range(7)}

    async def _get_busy_times(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Tuple[datetime, datetime]]:
        """Get busy times from Google Calendar."""
        if not self._initialize():
            return []

        try:
            # Query free/busy info
            body = {
                "timeMin": start_date.isoformat() + 'Z',
                "timeMax": end_date.isoformat() + 'Z',
                "items": [{"id": self.calendar_id}]
            }

            result = self.service.freebusy().query(body=body).execute()
            busy = result.get('calendars', {}).get(self.calendar_id, {}).get('busy', [])

            busy_times = []
            for period in busy:
                start = datetime.fromisoformat(period['start'].replace('Z', '+00:00'))
                end = datetime.fromisoformat(period['end'].replace('Z', '+00:00'))
                busy_times.append((start, end))

            return busy_times

        except Exception as e:
            logger.error(f"Error fetching busy times: {e}")
            return []

    def _generate_available_slots(
        self,
        start_date: datetime,
        end_date: datetime,
        duration_minutes: int,
        busy_times: List[Tuple[datetime, datetime]],
        availability_settings: Dict[int, List[Tuple[time, time]]],
        working_hours: Tuple[time, time] = None,
    ) -> List[TimeSlot]:
        """Generate available slots based on constraints."""
        slots = []
        slot_duration = timedelta(minutes=duration_minutes)

        current_date = start_date.date()
        end_date_only = end_date.date()

        while current_date <= end_date_only:
            day_of_week = current_date.weekday()
            # Convert to our format (0=Sunday)
            day_of_week = (day_of_week + 1) % 7

            # Get working hours for this day
            day_hours = availability_settings.get(day_of_week, [])
            if working_hours:
                day_hours = [working_hours]

            for work_start, work_end in day_hours:
                # Start at beginning of work hours
                slot_start = datetime.combine(current_date, work_start)

                # Generate slots until end of work hours
                while slot_start.time() < work_end:
                    slot_end = slot_start + slot_duration

                    # Check if slot end exceeds work hours
                    if slot_end.time() > work_end:
                        break

                    # Check if slot overlaps with any busy time
                    is_busy = False
                    for busy_start, busy_end in busy_times:
                        # Remove timezone info for comparison if needed
                        busy_start_naive = busy_start.replace(tzinfo=None) if busy_start.tzinfo else busy_start
                        busy_end_naive = busy_end.replace(tzinfo=None) if busy_end.tzinfo else busy_end

                        if not (slot_end <= busy_start_naive or slot_start >= busy_end_naive):
                            is_busy = True
                            break

                    if not is_busy:
                        # Only include future slots
                        if slot_start > datetime.now():
                            slots.append(TimeSlot(
                                start=slot_start,
                                end=slot_end,
                                duration_minutes=duration_minutes,
                            ))

                    # Move to next slot
                    slot_start = slot_start + slot_duration

            current_date += timedelta(days=1)

        return slots

    async def create_appointment(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime = None,
        description: str = None,
        attendees: List[str] = None,
        location: str = None,
        send_notifications: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a calendar event for an appointment.

        Args:
            title: Event title
            start_time: Appointment start time
            end_time: Appointment end time
            description: Event description
            attendees: List of attendee email addresses
            location: Event location
            send_notifications: Whether to send invite notifications

        Returns:
            Dict with event details including Google Calendar event ID
        """
        if not self._initialize():
            return {
                "success": False,
                "error": "Google Calendar not initialized",
            }

        if not end_time:
            end_time = start_time + timedelta(minutes=self.DEFAULT_DURATION_MINUTES)

        event = {
            'summary': title,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'America/New_York',  # TODO: Make configurable
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'America/New_York',
            },
        }

        if description:
            event['description'] = description

        if location:
            event['location'] = location

        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]

        try:
            result = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event,
                sendNotifications=send_notifications,
            ).execute()

            logger.info(f"Calendar event created: {result.get('id')}")

            return {
                "success": True,
                "event_id": result.get('id'),
                "html_link": result.get('htmlLink'),
                "data": result,
            }

        except HttpError as e:
            error_msg = f"Google Calendar API error: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
            }
        except Exception as e:
            error_msg = f"Failed to create calendar event: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
            }

    async def cancel_appointment(
        self,
        event_id: str,
        send_notifications: bool = True,
    ) -> Dict[str, Any]:
        """
        Cancel/delete a calendar event.

        Args:
            event_id: Google Calendar event ID
            send_notifications: Whether to send cancellation notifications

        Returns:
            Dict with success status
        """
        if not self._initialize():
            return {
                "success": False,
                "error": "Google Calendar not initialized",
            }

        try:
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id,
                sendNotifications=send_notifications,
            ).execute()

            logger.info(f"Calendar event cancelled: {event_id}")
            return {"success": True}

        except HttpError as e:
            error_msg = f"Google Calendar API error: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
            }

    async def update_appointment(
        self,
        event_id: str,
        title: str = None,
        start_time: datetime = None,
        end_time: datetime = None,
        description: str = None,
        send_notifications: bool = True,
    ) -> Dict[str, Any]:
        """
        Update an existing calendar event.

        Args:
            event_id: Google Calendar event ID
            title: New title (optional)
            start_time: New start time (optional)
            end_time: New end time (optional)
            description: New description (optional)
            send_notifications: Whether to send update notifications

        Returns:
            Dict with updated event details
        """
        if not self._initialize():
            return {
                "success": False,
                "error": "Google Calendar not initialized",
            }

        try:
            # Get existing event
            event = self.service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id,
            ).execute()

            # Update fields
            if title:
                event['summary'] = title
            if start_time:
                event['start']['dateTime'] = start_time.isoformat()
            if end_time:
                event['end']['dateTime'] = end_time.isoformat()
            if description:
                event['description'] = description

            # Save updates
            result = self.service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event,
                sendNotifications=send_notifications,
            ).execute()

            logger.info(f"Calendar event updated: {event_id}")
            return {
                "success": True,
                "event_id": result.get('id'),
                "data": result,
            }

        except Exception as e:
            error_msg = f"Failed to update calendar event: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
            }

    def format_slots_for_display(
        self,
        slots: List[TimeSlot],
        max_slots: int = 6,
    ) -> str:
        """
        Format time slots for display in SMS/text.

        Args:
            slots: List of available slots
            max_slots: Maximum slots to show

        Returns:
            Formatted string for text message
        """
        if not slots:
            return "I don't have any available slots in the next few days. Let me check with the team and get back to you!"

        display_slots = slots[:max_slots]

        lines = ["Here are some times I'm available:"]
        for i, slot in enumerate(display_slots, 1):
            lines.append(f"{i}. {slot}")

        lines.append("\nJust reply with the number that works best for you!")

        return "\n".join(lines)


class GoogleCalendarServiceSingleton:
    """Singleton wrapper for Google Calendar service."""

    _instance: Optional[GoogleCalendarService] = None

    @classmethod
    def get_instance(
        cls,
        credentials_path: str = None,
        calendar_id: str = "primary",
    ) -> GoogleCalendarService:
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = GoogleCalendarService(
                credentials_path=credentials_path,
                calendar_id=calendar_id,
            )
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset the singleton instance."""
        cls._instance = None
