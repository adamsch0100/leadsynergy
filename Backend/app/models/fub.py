import json
from datetime import datetime
from typing import Optional, Dict, Any, List

from app.models.base_model import BaseModel
from app.models.lead import Lead


class FUBStage(BaseModel):
    """Model for Follow Up Boss pipeline stages"""

    def __init__(self):
        self.id: str = None
        self.name: str = None
        self.pipeline_id: str = None
        self.position: Optional[int] = None
        self.created_at: Optional[datetime] = None


class FUBPipeline(BaseModel):
    """Model for Follow Up Boss pipelines"""

    def __init__(self):
        self.id: str = None
        self.name: str = None
        self.stages: Optional[List] = None
        self.created_at: Optional[datetime] = None


class FubSourceAnalytics(BaseModel):
    """Model for the fub_source_analytics table"""

    def __init__(self):
        self.id: str = None
        self.timestamp: datetime = None
        self.total_leads: Optional[str] = None
        self.unique_sources: Optional[str] = None
        self.leads_without_source: Optional[str] = None
        self.created_at: Optional[datetime] = None


class FUBResponse:
    """Helper class to parse Follow Up Boss API responses"""

    @staticmethod
    def parse_leads(response_data: Dict[str, Any]) -> List[Lead]:
        """Parse leads from a FUB API response"""
        leads = []

        if 'people' in response_data and isinstance(response_data['people'], list):
            for person_data in response_data['people']:
                lead = Lead.from_fub(person_data)
                leads.append(lead)

        return leads


# Example usage with Follow Up Boss API response
def parse_fub_response(json_string: str) -> List[Lead]:
    """Parse leads from a Follow Up Boss API response JSON string"""
    data = json.loads(json_string)
    return FUBResponse.parse_leads(data)
