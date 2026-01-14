"""
Appointment Scheduler - AI-powered appointment scheduling for leads.

This service orchestrates the complete appointment scheduling flow:
- Determining scheduling intent from lead messages
- Fetching available time slots from Google Calendar
- Presenting options to leads via conversational interface
- Booking appointments and syncing with FUB
- Sending confirmation and reminder notifications

Flow:
1. AI detects scheduling intent (e.g., "Can we set up a call?")
2. System fetches agent availability from Google Calendar
3. AI presents available slots in friendly format
4. Lead selects a time (e.g., "Option 2" or "Thursday at 3pm")
5. System books appointment on Google Calendar
6. System creates appointment in FUB
7. Confirmation sent via SMS/email
8. Reminder sent before appointment
"""

import logging
import re
from datetime import datetime, timedelta, time
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

from app.calendar.google_calendar import (
    GoogleCalendarService,
    GoogleCalendarServiceSingleton,
    TimeSlot,
)
from app.messaging.fub_sms_service import FUBSMSService
from app.email.ai_email_service import AIEmailService, get_ai_email_service

logger = logging.getLogger(__name__)


class AppointmentType(Enum):
    """Types of appointments."""
    PHONE_CONSULTATION = "phone_consultation"
    VIDEO_CALL = "video_call"
    IN_PERSON_MEETING = "in_person_meeting"
    PROPERTY_SHOWING = "property_showing"
    LISTING_PRESENTATION = "listing_presentation"
    BUYER_CONSULTATION = "buyer_consultation"


class SchedulingState(Enum):
    """States in the scheduling conversation flow."""
    INITIAL = "initial"
    OFFERED_SLOTS = "offered_slots"
    AWAITING_SELECTION = "awaiting_selection"
    CONFIRMING = "confirming"
    BOOKED = "booked"
    CANCELLED = "cancelled"


@dataclass
class SchedulingContext:
    """Context for an ongoing scheduling conversation."""
    state: SchedulingState = SchedulingState.INITIAL
    offered_slots: List[TimeSlot] = field(default_factory=list)
    selected_slot: Optional[TimeSlot] = None
    appointment_type: AppointmentType = AppointmentType.PHONE_CONSULTATION
    fub_person_id: Optional[int] = None
    lead_name: str = ""
    lead_email: str = ""
    lead_phone: str = ""
    agent_name: str = ""
    agent_email: str = ""
    agent_phone: str = ""
    agent_user_id: str = ""
    location: str = ""
    notes: str = ""
    google_event_id: Optional[str] = None
    fub_appointment_id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "offered_slots": [s.to_dict() for s in self.offered_slots],
            "selected_slot": self.selected_slot.to_dict() if self.selected_slot else None,
            "appointment_type": self.appointment_type.value,
            "fub_person_id": self.fub_person_id,
            "lead_name": self.lead_name,
            "agent_name": self.agent_name,
            "google_event_id": self.google_event_id,
            "fub_appointment_id": self.fub_appointment_id,
        }


@dataclass
class SchedulingResult:
    """Result of a scheduling operation."""
    success: bool
    message: str
    context: Optional[SchedulingContext] = None
    slots_offered: Optional[List[TimeSlot]] = None
    appointment_booked: bool = False
    next_action: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "context": self.context.to_dict() if self.context else None,
            "slots_offered": [s.to_dict() for s in (self.slots_offered or [])],
            "appointment_booked": self.appointment_booked,
            "next_action": self.next_action,
            "error": self.error,
        }


class AppointmentScheduler:
    """
    AI-powered appointment scheduling service.

    Handles the complete scheduling flow from detecting intent
    to booking and confirming appointments.
    """

    # Default appointment duration in minutes
    DEFAULT_DURATION = 30

    # Maximum slots to offer at once
    MAX_SLOTS_TO_OFFER = 6

    # Patterns for detecting slot selection
    SLOT_SELECTION_PATTERNS = [
        r'^(\d)$',                           # Just a number: "2"
        r'^option\s*(\d)$',                  # "option 2"
        r'^#?(\d)$',                         # "#2"
        r'^number\s*(\d)$',                  # "number 2"
        r'^the\s+(\d)(?:st|nd|rd|th)?\s*(?:one)?$',  # "the 2nd one"
    ]

    # Patterns for detecting time preferences
    TIME_PATTERNS = [
        r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)',  # "3pm" or "3:30 pm"
        r'(morning|afternoon|evening)',       # General time of day
    ]

    # Day patterns
    DAY_PATTERNS = [
        r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
        r'(tomorrow|today)',
        r'(next\s+\w+day)',
    ]

    def __init__(
        self,
        calendar_service: GoogleCalendarService = None,
        fub_service: FUBSMSService = None,
        email_service: AIEmailService = None,
        fub_api_key: str = None,
    ):
        """
        Initialize appointment scheduler.

        Args:
            calendar_service: Google Calendar service instance
            fub_service: FUB SMS/API service instance
            email_service: AI email service instance
            fub_api_key: FUB API key for creating services
        """
        self.calendar = calendar_service or GoogleCalendarServiceSingleton.get_instance()
        self.fub = fub_service or FUBSMSService(api_key=fub_api_key)
        self.email = email_service or get_ai_email_service()

        # Cache for ongoing scheduling conversations
        self._scheduling_contexts: Dict[int, SchedulingContext] = {}

    async def start_scheduling(
        self,
        fub_person_id: int,
        lead_name: str,
        lead_email: str = "",
        lead_phone: str = "",
        agent_user_id: str = "",
        agent_name: str = "",
        agent_email: str = "",
        agent_phone: str = "",
        appointment_type: AppointmentType = AppointmentType.PHONE_CONSULTATION,
        duration_minutes: int = None,
        supabase_client=None,
    ) -> SchedulingResult:
        """
        Start the scheduling flow by offering available time slots.

        Args:
            fub_person_id: FUB person ID
            lead_name: Lead's name
            lead_email: Lead's email
            lead_phone: Lead's phone
            agent_user_id: Agent's user ID (for availability lookup)
            agent_name: Agent's name
            agent_email: Agent's email
            agent_phone: Agent's phone
            appointment_type: Type of appointment
            duration_minutes: Appointment duration
            supabase_client: Database client

        Returns:
            SchedulingResult with available slots and response message
        """
        duration = duration_minutes or self.DEFAULT_DURATION

        # Get available slots from calendar
        try:
            slots = await self.calendar.get_available_slots(
                agent_user_id=agent_user_id,
                duration_minutes=duration,
                supabase_client=supabase_client,
            )
        except Exception as e:
            logger.error(f"Failed to get available slots: {e}")
            return SchedulingResult(
                success=False,
                message="I'm having trouble checking the calendar right now. Can I get back to you with some times?",
                error=str(e),
            )

        if not slots:
            return SchedulingResult(
                success=True,
                message=f"I don't have any open slots in the next week, {lead_name}. Let me check with {agent_name} and get back to you with some options!",
                next_action="manual_scheduling",
            )

        # Take top slots
        offered_slots = slots[:self.MAX_SLOTS_TO_OFFER]

        # Create scheduling context
        context = SchedulingContext(
            state=SchedulingState.OFFERED_SLOTS,
            offered_slots=offered_slots,
            appointment_type=appointment_type,
            fub_person_id=fub_person_id,
            lead_name=lead_name,
            lead_email=lead_email,
            lead_phone=lead_phone,
            agent_name=agent_name,
            agent_email=agent_email,
            agent_phone=agent_phone,
            agent_user_id=agent_user_id,
        )

        # Cache the context
        self._scheduling_contexts[fub_person_id] = context

        # Format slots for display
        message = self._format_slot_options(lead_name, offered_slots, appointment_type)

        return SchedulingResult(
            success=True,
            message=message,
            context=context,
            slots_offered=offered_slots,
            next_action="await_selection",
        )

    async def process_scheduling_response(
        self,
        fub_person_id: int,
        message: str,
        context: SchedulingContext = None,
    ) -> SchedulingResult:
        """
        Process a lead's response during scheduling flow.

        Args:
            fub_person_id: FUB person ID
            message: Lead's message
            context: Existing scheduling context (or fetched from cache)

        Returns:
            SchedulingResult with next step
        """
        # Get or create context
        if not context:
            context = self._scheduling_contexts.get(fub_person_id)

        if not context:
            return SchedulingResult(
                success=False,
                message="I don't have an active scheduling session. Would you like me to show you some available times?",
                next_action="restart_scheduling",
            )

        message_lower = message.lower().strip()

        # Check if they want to cancel/reschedule
        if self._is_cancel_intent(message_lower):
            self._scheduling_contexts.pop(fub_person_id, None)
            return SchedulingResult(
                success=True,
                message="No problem at all! Just let me know whenever you're ready to schedule.",
                next_action="cancelled",
            )

        # Try to parse slot selection
        selected_index = self._parse_slot_selection(message_lower)

        if selected_index is not None:
            if 1 <= selected_index <= len(context.offered_slots):
                selected_slot = context.offered_slots[selected_index - 1]
                context.selected_slot = selected_slot
                context.state = SchedulingState.CONFIRMING

                # Book the appointment
                return await self._book_appointment(context)
            else:
                return SchedulingResult(
                    success=True,
                    message=f"I only have options 1 through {len(context.offered_slots)}. Which one works for you?",
                    context=context,
                    next_action="await_selection",
                )

        # Try to parse a specific time/day preference
        preferred_slot = self._parse_time_preference(message_lower, context.offered_slots)

        if preferred_slot:
            context.selected_slot = preferred_slot
            context.state = SchedulingState.CONFIRMING
            return await self._book_appointment(context)

        # Didn't understand the response
        return SchedulingResult(
            success=True,
            message=f"I didn't quite catch that, {context.lead_name}. Just reply with the number of the time that works best for you (like '2' for option 2), or let me know if you need different times!",
            context=context,
            next_action="await_selection",
        )

    async def _book_appointment(
        self,
        context: SchedulingContext,
    ) -> SchedulingResult:
        """Book the appointment on Google Calendar and FUB."""
        if not context.selected_slot:
            return SchedulingResult(
                success=False,
                message="Something went wrong - no time slot selected.",
                context=context,
                error="No slot selected",
            )

        slot = context.selected_slot
        appointment_title = self._get_appointment_title(context)

        # Create Google Calendar event
        try:
            calendar_result = await self.calendar.create_appointment(
                title=appointment_title,
                start_time=slot.start,
                end_time=slot.end,
                description=f"Appointment with {context.lead_name}\n\nPhone: {context.lead_phone}\nEmail: {context.lead_email}\n\nBooked via LeadSynergy AI",
                attendees=[context.lead_email] if context.lead_email else None,
                send_notifications=True,
            )

            if calendar_result.get("success"):
                context.google_event_id = calendar_result.get("event_id")
                logger.info(f"Google Calendar event created: {context.google_event_id}")
            else:
                logger.warning(f"Failed to create Google Calendar event: {calendar_result.get('error')}")

        except Exception as e:
            logger.error(f"Google Calendar error: {e}")

        # Create FUB appointment
        try:
            fub_result = self.fub.create_appointment(
                person_id=context.fub_person_id,
                title=appointment_title,
                start_time=slot.start,
                end_time=slot.end,
                description=f"Booked via LeadSynergy AI Agent",
            )

            if fub_result.get("success"):
                context.fub_appointment_id = fub_result.get("appointment_id")
                logger.info(f"FUB appointment created: {context.fub_appointment_id}")

        except Exception as e:
            logger.error(f"FUB appointment error: {e}")

        # Update context state
        context.state = SchedulingState.BOOKED

        # Send confirmation email if we have email address
        if context.lead_email:
            try:
                self.email.send_appointment_confirmation_email(
                    to_email=context.lead_email,
                    lead_name=context.lead_name,
                    agent_name=context.agent_name,
                    agent_email=context.agent_email,
                    agent_phone=context.agent_phone,
                    appointment_date=slot.start.strftime("%A, %B %d"),
                    appointment_time=slot.start.strftime("%I:%M %p"),
                    appointment_type=context.appointment_type.value.replace("_", " "),
                    fub_person_id=context.fub_person_id,
                )
            except Exception as e:
                logger.error(f"Failed to send confirmation email: {e}")

        # Clear from cache
        self._scheduling_contexts.pop(context.fub_person_id, None)

        # Format confirmation message
        message = self._format_confirmation(context)

        return SchedulingResult(
            success=True,
            message=message,
            context=context,
            appointment_booked=True,
            next_action="appointment_confirmed",
        )

    async def cancel_appointment(
        self,
        fub_person_id: int,
        context: SchedulingContext = None,
        reason: str = None,
    ) -> SchedulingResult:
        """
        Cancel an existing appointment.

        Args:
            fub_person_id: FUB person ID
            context: Scheduling context with appointment details
            reason: Cancellation reason

        Returns:
            SchedulingResult
        """
        if not context:
            context = self._scheduling_contexts.get(fub_person_id)

        if not context or not context.google_event_id:
            return SchedulingResult(
                success=False,
                message="I couldn't find an appointment to cancel.",
                error="No appointment found",
            )

        # Cancel Google Calendar event
        if context.google_event_id:
            try:
                await self.calendar.cancel_appointment(context.google_event_id)
                logger.info(f"Cancelled Google Calendar event: {context.google_event_id}")
            except Exception as e:
                logger.error(f"Failed to cancel Google Calendar event: {e}")

        # Note: FUB doesn't have a delete appointment API, so we'd need to
        # update it or add a note about cancellation

        context.state = SchedulingState.CANCELLED
        self._scheduling_contexts.pop(fub_person_id, None)

        return SchedulingResult(
            success=True,
            message=f"No worries, {context.lead_name}! I've cancelled the appointment. Just let me know whenever you want to reschedule!",
            context=context,
            next_action="cancelled",
        )

    async def reschedule_appointment(
        self,
        fub_person_id: int,
        context: SchedulingContext = None,
    ) -> SchedulingResult:
        """
        Reschedule an existing appointment.

        Args:
            fub_person_id: FUB person ID
            context: Existing context

        Returns:
            SchedulingResult with new slots
        """
        # Cancel existing and start fresh
        if context and context.google_event_id:
            await self.cancel_appointment(fub_person_id, context)

        # Start new scheduling flow
        if context:
            return await self.start_scheduling(
                fub_person_id=fub_person_id,
                lead_name=context.lead_name,
                lead_email=context.lead_email,
                lead_phone=context.lead_phone,
                agent_user_id=context.agent_user_id,
                agent_name=context.agent_name,
                agent_email=context.agent_email,
                agent_phone=context.agent_phone,
                appointment_type=context.appointment_type,
            )

        return SchedulingResult(
            success=False,
            message="I don't have your previous appointment details. Let me know and I can set up a new time for you!",
            error="No context available",
        )

    def _format_slot_options(
        self,
        lead_name: str,
        slots: List[TimeSlot],
        appointment_type: AppointmentType,
    ) -> str:
        """Format slots as a friendly message."""
        type_desc = appointment_type.value.replace("_", " ")

        lines = [f"Awesome, {lead_name}! I'd love to set up a quick {type_desc} with you."]
        lines.append("")
        lines.append("Here are some times that work:")

        for i, slot in enumerate(slots, 1):
            lines.append(f"{i}. {slot}")

        lines.append("")
        lines.append("Just reply with the number that works best!")

        return "\n".join(lines)

    def _format_confirmation(self, context: SchedulingContext) -> str:
        """Format appointment confirmation message."""
        slot = context.selected_slot
        if not slot:
            return "Your appointment has been booked!"

        date_str = slot.start.strftime("%A, %B %d")
        time_str = slot.start.strftime("%I:%M %p")

        lines = [
            f"You're all set, {context.lead_name}!",
            "",
            f"Your appointment is booked for {date_str} at {time_str}.",
            "",
            f"Looking forward to chatting with you! If anything comes up, just let me know.",
        ]

        return "\n".join(lines)

    def _parse_slot_selection(self, message: str) -> Optional[int]:
        """Parse slot selection from message."""
        message = message.strip().lower()

        for pattern in self.SLOT_SELECTION_PATTERNS:
            match = re.match(pattern, message, re.IGNORECASE)
            if match:
                return int(match.group(1))

        return None

    def _parse_time_preference(
        self,
        message: str,
        available_slots: List[TimeSlot],
    ) -> Optional[TimeSlot]:
        """Try to match a time preference to available slots."""
        message_lower = message.lower()

        # Check for day mention
        target_day = None
        for pattern in self.DAY_PATTERNS:
            match = re.search(pattern, message_lower)
            if match:
                day_text = match.group(1)
                target_day = self._parse_day_reference(day_text)
                break

        # Check for time mention
        target_time = None
        for pattern in self.TIME_PATTERNS:
            match = re.search(pattern, message_lower)
            if match:
                if match.group(1) in ['morning', 'afternoon', 'evening']:
                    target_time = match.group(1)
                else:
                    hour = int(match.group(1))
                    minute = int(match.group(2) or 0)
                    period = match.group(3) if len(match.groups()) >= 3 else 'am'

                    if period == 'pm' and hour != 12:
                        hour += 12
                    elif period == 'am' and hour == 12:
                        hour = 0

                    target_time = time(hour, minute)
                break

        if not target_day and not target_time:
            return None

        # Find best matching slot
        for slot in available_slots:
            matches_day = (
                target_day is None or
                slot.start.date() == target_day
            )
            matches_time = (
                target_time is None or
                self._time_matches(slot.start.time(), target_time)
            )

            if matches_day and matches_time:
                return slot

        return None

    def _parse_day_reference(self, day_text: str) -> Optional[datetime]:
        """Parse day reference to actual date."""
        today = datetime.now().date()

        if day_text == 'today':
            return today
        elif day_text == 'tomorrow':
            return today + timedelta(days=1)
        elif day_text.startswith('next'):
            # "next thursday"
            day_name = day_text.replace('next', '').strip()
            return self._next_weekday(day_name)
        else:
            # Day name like "thursday"
            return self._next_weekday(day_text)

    def _next_weekday(self, day_name: str) -> Optional[datetime]:
        """Get next occurrence of a weekday."""
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

        try:
            target_weekday = days.index(day_name.lower())
        except ValueError:
            return None

        today = datetime.now().date()
        current_weekday = today.weekday()

        days_ahead = target_weekday - current_weekday
        if days_ahead <= 0:
            days_ahead += 7

        return today + timedelta(days=days_ahead)

    def _time_matches(
        self,
        slot_time: time,
        target: Any,
    ) -> bool:
        """Check if slot time matches target preference."""
        if isinstance(target, time):
            # Within 30 minutes
            slot_minutes = slot_time.hour * 60 + slot_time.minute
            target_minutes = target.hour * 60 + target.minute
            return abs(slot_minutes - target_minutes) <= 30

        elif isinstance(target, str):
            # Morning: 6-12, Afternoon: 12-17, Evening: 17-21
            hour = slot_time.hour
            if target == 'morning':
                return 6 <= hour < 12
            elif target == 'afternoon':
                return 12 <= hour < 17
            elif target == 'evening':
                return 17 <= hour < 21

        return False

    def _is_cancel_intent(self, message: str) -> bool:
        """Check if message indicates cancellation intent."""
        cancel_phrases = [
            'cancel', 'nevermind', 'never mind', 'forget it',
            'not anymore', 'changed my mind', 'no thanks',
            'maybe later', 'not right now',
        ]
        return any(phrase in message.lower() for phrase in cancel_phrases)

    def _get_appointment_title(self, context: SchedulingContext) -> str:
        """Generate appointment title."""
        type_map = {
            AppointmentType.PHONE_CONSULTATION: "Phone Consultation",
            AppointmentType.VIDEO_CALL: "Video Call",
            AppointmentType.IN_PERSON_MEETING: "Meeting",
            AppointmentType.PROPERTY_SHOWING: "Property Showing",
            AppointmentType.LISTING_PRESENTATION: "Listing Presentation",
            AppointmentType.BUYER_CONSULTATION: "Buyer Consultation",
        }

        type_str = type_map.get(context.appointment_type, "Appointment")
        return f"{type_str} with {context.lead_name}"

    def get_scheduling_context(self, fub_person_id: int) -> Optional[SchedulingContext]:
        """Get cached scheduling context for a lead."""
        return self._scheduling_contexts.get(fub_person_id)

    def has_active_scheduling(self, fub_person_id: int) -> bool:
        """Check if lead has active scheduling session."""
        return fub_person_id in self._scheduling_contexts


class AppointmentSchedulerSingleton:
    """Singleton wrapper for appointment scheduler."""

    _instance: Optional[AppointmentScheduler] = None

    @classmethod
    def get_instance(cls, fub_api_key: str = None) -> AppointmentScheduler:
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = AppointmentScheduler(fub_api_key=fub_api_key)
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset the singleton instance."""
        cls._instance = None


# Convenience function
def get_appointment_scheduler(fub_api_key: str = None) -> AppointmentScheduler:
    """Get appointment scheduler instance."""
    return AppointmentSchedulerSingleton.get_instance(fub_api_key)
