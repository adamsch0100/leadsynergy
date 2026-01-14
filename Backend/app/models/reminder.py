from datetime import datetime
from typing import Optional

from app.models.base_model import BaseModel


class Reminder(BaseModel):
    def __init__(self):
        self.id: str = None
        self.lead_id: str = None
        self.user_id: str = None
        self.reminder_date: datetime = None
        self.description: Optional[str] = None
        self.status: Optional[str] = None
        self.created_at: Optional[datetime] = None
        self.updated_at: Optional[datetime] = None
