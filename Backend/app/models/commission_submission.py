import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from app.models.base_model import BaseModel

class CommissionSubmission(BaseModel):
    def __init__(self) -> None:
        self.id: str = None 
        self.agent_id: Optional[str] = None
        self.closing_date: str = None
        self.commission_amount: float = None
        self.commission_percentage: float = None 
        self.contract_date: str = None 
        self.created_at: datetime = None 
        self.lead_id: Optional[str] = None 
        self.notes: Optional[str] = None
        self.proof_document_url: str = None 
        self.property_address: str = None 
        self.submitted_at: datetime = None 
        self.updated_at: datetime = None
        
    def to_dict(self) -> Dict[str, Any]:
        data = vars(self).copy()
        
        # Handle datetime objects
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CommissionSubmission":
        submission = cls()
        for key, value in data.items():
            if hasattr(submission, key):
                if key in ["created_at", "submitted_at", "updated_at"] and value:
                    try:
                        if isinstance(value, str):
                            setattr(
                                submission,
                                key,
                                datetime.fromisoformat(value.replace("Z", "+00:00")),
                            )
                        else:
                            setattr(submission, key, value)
                    except (ValueError, TypeError):
                        setattr(submission, key, value)
                else:
                    setattr(submission, key, value)
        return submission