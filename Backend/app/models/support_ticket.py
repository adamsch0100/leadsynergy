from typing import Optional, Dict, Any, List
from datetime import datetime

from app.models.base_model import BaseModel


class SupportTicket(BaseModel):
    """
    Represents a customer support ticket.
    Maps to the support_tickets table.
    """

    # Status values
    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_WAITING = 'waiting'
    STATUS_CLOSED = 'closed'

    # Priority values
    PRIORITY_LOW = 'low'
    PRIORITY_NORMAL = 'normal'
    PRIORITY_HIGH = 'high'
    PRIORITY_URGENT = 'urgent'

    # Category values
    CATEGORY_BILLING = 'billing'
    CATEGORY_TECHNICAL = 'technical'
    CATEGORY_FEATURE_REQUEST = 'feature_request'
    CATEGORY_ACCOUNT = 'account'
    CATEGORY_OTHER = 'other'

    def __init__(self):
        self.id: int = None
        self.user_id: str = None
        self.subject: str = None
        self.description: str = None
        self.status: str = 'open'
        self.priority: str = 'normal'
        self.category: Optional[str] = None
        self.assigned_to: Optional[str] = None
        self.created_at: Optional[datetime] = None
        self.updated_at: Optional[datetime] = None
        self.closed_at: Optional[datetime] = None

        # Related data (populated when needed)
        self.notes: List['TicketNote'] = []
        self.user: Optional[Dict] = None
        self.assignee: Optional[Dict] = None

    @property
    def is_open(self) -> bool:
        """Check if ticket is open."""
        return self.status == self.STATUS_OPEN

    @property
    def is_closed(self) -> bool:
        """Check if ticket is closed."""
        return self.status == self.STATUS_CLOSED

    @property
    def is_urgent(self) -> bool:
        """Check if ticket is urgent priority."""
        return self.priority == self.PRIORITY_URGENT

    @property
    def is_high_priority(self) -> bool:
        """Check if ticket is high priority or above."""
        return self.priority in [self.PRIORITY_HIGH, self.PRIORITY_URGENT]

    @property
    def status_display(self) -> str:
        """Get human-readable status."""
        status_map = {
            'open': 'Open',
            'in_progress': 'In Progress',
            'waiting': 'Waiting for Customer',
            'closed': 'Closed'
        }
        return status_map.get(self.status, self.status)

    @property
    def priority_display(self) -> str:
        """Get human-readable priority."""
        return self.priority.title() if self.priority else 'Normal'

    @property
    def category_display(self) -> str:
        """Get human-readable category."""
        category_map = {
            'billing': 'Billing',
            'technical': 'Technical Support',
            'feature_request': 'Feature Request',
            'account': 'Account',
            'other': 'Other'
        }
        return category_map.get(self.category, self.category or 'General')

    def get_response_time(self) -> Optional[str]:
        """Get time since ticket was created."""
        if not self.created_at:
            return None

        now = datetime.utcnow()
        if isinstance(self.created_at, str):
            created = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        else:
            created = self.created_at

        delta = now - created.replace(tzinfo=None)

        if delta.days > 0:
            return f"{delta.days}d ago"
        elif delta.seconds >= 3600:
            return f"{delta.seconds // 3600}h ago"
        elif delta.seconds >= 60:
            return f"{delta.seconds // 60}m ago"
        else:
            return "Just now"

    def to_dict(self) -> Dict[str, Any]:
        """Convert SupportTicket object to dictionary for serialization."""
        data = {}
        for key, value in vars(self).items():
            # Skip related data that shouldn't be serialized to DB
            if key in ['notes', 'user', 'assignee']:
                continue
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            else:
                data[key] = value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SupportTicket":
        """Create SupportTicket object from dictionary."""
        ticket = cls()
        datetime_fields = ["created_at", "updated_at", "closed_at"]

        for key, value in data.items():
            if hasattr(ticket, key):
                if key in datetime_fields and value:
                    try:
                        if isinstance(value, str):
                            setattr(
                                ticket,
                                key,
                                datetime.fromisoformat(value.replace("Z", "+00:00"))
                            )
                        else:
                            setattr(ticket, key, value)
                    except (ValueError, TypeError):
                        setattr(ticket, key, value)
                else:
                    setattr(ticket, key, value)
        return ticket


class TicketNote(BaseModel):
    """
    Represents a note/comment on a support ticket.
    Maps to the ticket_notes table.
    """

    def __init__(self):
        self.id: int = None
        self.ticket_id: int = None
        self.user_id: str = None
        self.content: str = None
        self.is_internal: bool = False  # Internal notes not visible to user
        self.created_at: Optional[datetime] = None

        # Related data (populated when needed)
        self.user: Optional[Dict] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert TicketNote object to dictionary for serialization."""
        data = {}
        for key, value in vars(self).items():
            if key == 'user':
                continue
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            else:
                data[key] = value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TicketNote":
        """Create TicketNote object from dictionary."""
        note = cls()
        for key, value in data.items():
            if hasattr(note, key):
                if key == "created_at" and value:
                    try:
                        if isinstance(value, str):
                            setattr(
                                note,
                                key,
                                datetime.fromisoformat(value.replace("Z", "+00:00"))
                            )
                        else:
                            setattr(note, key, value)
                    except (ValueError, TypeError):
                        setattr(note, key, value)
                else:
                    setattr(note, key, value)
        return note
