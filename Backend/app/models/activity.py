import json
from typing import Optional, Dict, Any
from datetime import datetime

from app.models.base_model import BaseModel


class Activity(BaseModel):
    def __init__(self):
        self.id: str = None
        self.lead_id: str = None
        self.user_id: str = None
        self.type: str = None
        self.metadata: Optional[Dict[str, Any]] = None
        self.created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()

        if isinstance(self.metadata, dict):
            result['metadata'] = json.dumps(self.metadata)

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Activity':
        instance = super().from_dict(cls, data)

        if instance and isinstance(instance.metadata, str):
            try:
                instance.metadata = json.loads(instance.metadata)
            except json.JSONDecodeError:
                pass

        return instance

