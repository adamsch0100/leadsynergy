from datetime import datetime
from typing import Optional, Dict, Any, List

from app.models.base_model import BaseModel


class Settings(BaseModel):
    """Model for the settings table"""

    def __init__(self):
        self.id: str = None
        self.fub_api_key: Optional[str] = None
        self.fub_import_tag: Optional[str] = None
        self.created_at: Optional[datetime] = None
        self.updated_at: Optional[datetime] = None