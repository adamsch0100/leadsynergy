from datetime import datetime
from typing import Optional, Dict, Any, List
import json

from app.models.base_model import BaseModel


class StageMapping(BaseModel):
    """Model for the stage_mappings table"""

    def __init__(self):
        self.id: str = None
        self.user_id: str = None
        self.source_id: str = None
        self.lead_id: str = None
        self.fub_stage_id: str = None
        self.fub_stage_name: str = None
        self.platform: str = None
        self.platform_stage_name: Dict[str, Any] = None
        self.created_at: Optional[datetime] = None
        self.updated_at: Optional[datetime] = None
        self.metadata: Optional[Dict[str, Any]] = None
        
    def to_dict(self) -> Dict[str, Any]:
        data = vars(self).copy()
        
        # Handle datetime objects
        for key, value in data.items():
            if isinstance(value, datetime):
               data[key] = value.isoformat()
               
        
        # Convert metadata to JSON string if it exists
        if self.metadata and isinstance(self.metadata, dict):
            data['metadata'] = json.dumps(self.metadata)
            
        return {k: v for k, v in data.items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StageMapping':
        mapping = cls()
        
        for key, value in data.items():
            if hasattr(mapping, key):
                setattr(mapping, key, value)
        
        # Parse metadata JSON if it exists
        if mapping.metadata and isinstance(mapping.metadata, str):
            try:
                mapping.metadata = json.loads(mapping.metadata)
            except json.JSONDecodeError:
                mapping.metadata = {}
                
        return mapping
    
    
    def get_external_stage(self) -> str:
        return self.platform_stage_name or "Unknown"
    
    
    @staticmethod
    def get_default_mapping(fub_stage_name: str, platform: str) -> str:
        default_mappings = {
            "generic": {
                'New Lead': "New Referral",
                "Contacted": 'In Progress',
                "Qualified": "Qualified",
                "Under Contract": "In Contract",
                "Closed": "Closed/Complete",
                "Lost": "Cancelled"
            }
        }
        
        platform_mappings = default_mappings.get(platform.lower(), default_mappings["generic"])
        
        return platform_mappings.get(fub_stage_name, fub_stage_name)