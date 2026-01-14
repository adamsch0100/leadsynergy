"""
Calendar Module for LeadSynergy AI Agent.

Provides calendar integration for appointment scheduling:
- Google Calendar integration for availability checking and booking
- Agent availability management
- Appointment reminders
"""

from app.calendar.google_calendar import (
    GoogleCalendarService,
    GoogleCalendarServiceSingleton,
    TimeSlot,
)

__all__ = [
    'GoogleCalendarService',
    'GoogleCalendarServiceSingleton',
    'TimeSlot',
]
