import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List, Union

from app.models.base_model import BaseModel
from app.database.fub_api_client import FUBApiClient

class LeadSourceSettings(BaseModel):
    def __init__(self) -> None:
        self.id: str = None
        self.source_name: str = None
        self.assignment_strategy: str = None
        self.referral_fee_percent: float = None
        self.is_active: bool = True
        self.metadata: Dict[str, Any] = {}
        self.assignment_rules: Dict[str, Any] = {}
        self.created_at: datetime = None
        self.updated_at: datetime = None
        self.options: Union[List[str], Dict[str, Any]] = {}
        self.fub_stage_mapping: Dict[str, str] = {}
        self.sync_interval_days: Optional[int] = None
        self.last_sync_at: Optional[datetime] = None
        self.next_sync_at: Optional[datetime] = None
        self.last_sync_results: Dict[str, Any] = {}  # Stores the last sync results for persistence
        self.user_id: Optional[str] = None
        self.auto_discovered: bool = False
        self.same_status_note: Optional[str] = "Same as previous update. Continuing to communicate and assist the referral as best as possible."
        
    def to_dict(self) -> Dict[str, Any]:
        data = {
            'id': self.id,
            'source_name': self.source_name,
            'assignment_strategy': self.assignment_strategy,
            'referral_fee_percent': self.referral_fee_percent,
            'is_active': self.is_active,
            'metadata': self.metadata,
            'assignment_rules': self.assignment_rules,
            'options': self.options,
            'fub_stage_mapping': self.fub_stage_mapping,
            'sync_interval_days': self.sync_interval_days,
            'last_sync_at': self.last_sync_at,
            'next_sync_at': self.next_sync_at,
            'last_sync_results': self.last_sync_results,
            'user_id': self.user_id,
            'auto_discovered': self.auto_discovered,
            'same_status_note': self.same_status_note
        }
        
        if self.created_at:
            data['created_at'] = self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at
            
        if self.updated_at:
            data['updated_at'] = self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at
            
        if self.last_sync_at:
            data['last_sync_at'] = self.last_sync_at.isoformat() if isinstance(self.last_sync_at, datetime) else self.last_sync_at

        if self.next_sync_at:
            data['next_sync_at'] = self.next_sync_at.isoformat() if isinstance(self.next_sync_at, datetime) else self.next_sync_at

        return {k: v for k, v in data.items() if v is not None}
    
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LeadSourceSettings':
        instance = cls()
        
        for key, value in data.items():
            if hasattr(instance, key):
                if key in ['created_at', 'updated_at', 'last_sync_at', 'next_sync_at'] and value:
                    if isinstance(value, str):
                        try:
                            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        except ValueError:
                            pass
                if key in ['metadata', 'assignment_rules', 'options', 'fub_stage_mapping', 'last_sync_results'] and isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        pass
                        
                setattr(instance, key, value)
        
        return instance
    
    def get_mapped_stage(self, fub_stage_name: str, lead_type: Optional[str] = None) -> Optional[str]:
        """
        Get the mapped stage for a FUB stage name.

        Args:
            fub_stage_name: The FUB stage name to map
            lead_type: Optional lead type ('buyer' or 'seller') for platforms with type-specific mappings

        Returns:
            The mapped stage string, or None if no mapping exists
        """
        if not self.fub_stage_mapping or not isinstance(self.fub_stage_mapping, dict):
            return None

        mapping = self.fub_stage_mapping.get(fub_stage_name)

        if mapping is None:
            return None

        # If mapping is a dict with buyer/seller keys, extract the appropriate one
        if isinstance(mapping, dict):
            # Normalize lead_type to lowercase
            if lead_type:
                lead_type = lead_type.lower()

            # Try to get the specific type mapping
            if lead_type and lead_type in mapping:
                return mapping[lead_type]

            # Fallback: try 'seller' first (most common), then 'buyer'
            if 'seller' in mapping:
                return mapping['seller']
            if 'buyer' in mapping:
                return mapping['buyer']

            # If dict doesn't have buyer/seller keys, return None
            return None

        # Direct string mapping (backwards compatible)
        return mapping
    
    def get_available_options(self) -> List[str]:
        if isinstance(self.options, list):
            return self.options
        
        elif isinstance(self.options, dict):
            all_options = []
            for key, value in self.options.items():
                all_options.append(key)
                
                if isinstance(value, list):
                    all_options.extend(key)
                elif isinstance(value, str):
                    all_options.append(value)
            return all_options
        
        return []