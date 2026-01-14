from datetime import datetime
from typing import Optional, Dict, Any, List

from app.models.base_model import BaseModel

class WebhookEvent(BaseModel):
    def __init__(self):
        self.event_id: str = None
        self.event_created: Optional[datetime] = None
        self.event_type: str = None
        self.resource_ids: List[int] = []
        self.uri: str = None
        self.data: Optional[Dict[str, Any]] = None

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'WebhookEvent':
        webhook = cls()
        webhook.event_id = data.get('eventId')
        webhook.event_type = data.get('event')
        webhook.resource_ids = data.get('resourceIds', [])
        webhook.uri = data.get('uri')
        webhook.data = data.get('data')
        
        # Parse datetime
        if event_created := data.get('eventCreated'):
            webhook.event_created = cls._parse_datetime(event_created)
            
        return webhook

    def to_dict(self) -> Dict[str, Any]:
        return {
            'eventId': self.event_id,
            'eventCreated': self.event_created.isoformat() if self.event_created else None,
            'event': self.event_type,
            'resourceIds': self.resource_ids,
            'uri': self.uri,
            'data': self.data
        }

    @staticmethod
    def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return None

    def display_data(self) -> None:
        """Display all fields and their values for debugging purposes."""
        print("\n=== Webhook Event Data ===")
        print(f"Event ID: {self.event_id}")
        print(f"Event Created: {self.event_created}")
        print(f"Event Type: {self.event_type}")
        print(f"Resource IDs: {self.resource_ids}")
        print(f"URI: {self.uri}")
        print(f"Data: {self.data}")
        print("=====================\n") 