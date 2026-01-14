from typing import List, Dict, Any, Optional
import threading
import uuid
from datetime import datetime

from app.models.commission_submission import CommissionSubmission
from app.database.supabase_client import SupabaseClientSingleton
from supabase import Client

class CommissionServiceSingleton:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = CommissionService()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None

class CommissionService:
    def __init__(self):
        self.supabase: Client = SupabaseClientSingleton.get_instance()
        self.table_name = "commission_submissions"

    def create(self, commission: CommissionSubmission) -> CommissionSubmission:
        if not commission.id:
            commission.id = str(uuid.uuid4())

        if not commission.created_at:
            commission.created_at = datetime.now()
            
        if not commission.submitted_at:
            commission.submitted_at = datetime.now()
            
        commission.updated_at = datetime.now()

        # Convert to dict for insertion
        data = commission.to_dict()

        # Insert into Supabase
        result = self.supabase.table(self.table_name).insert(data).execute()

        # Update commission with returned data
        if result.data and len(result.data) > 0:
            returned_data = result.data[0]
            for key, value in returned_data.items():
                setattr(commission, key, value)

        return commission

    def get_by_id(self, commission_id: str) -> Optional[CommissionSubmission]:
        result = self.supabase.table(self.table_name).select('*').eq('id', commission_id).execute()

        if result.data and len(result.data) > 0:
            return CommissionSubmission.from_dict(result.data[0])
        return None

    def get_all(self) -> List[CommissionSubmission]:
        result = self.supabase.table(self.table_name).select('*').execute()
        
        commissions = []
        if result.data:
            for item in result.data:
                commission = CommissionSubmission.from_dict(item)
                commissions.append(commission)
        
        return commissions
    
    def get_by_agent_id(self, agent_id: str) -> List[CommissionSubmission]:
        result = self.supabase.table(self.table_name).select('*').eq('agent_id', agent_id).execute()
        
        commissions = []
        if result.data:
            for item in result.data:
                commission = CommissionSubmission.from_dict(item)
                commissions.append(commission)
        
        return commissions
    
    def get_by_lead_id(self, lead_id: str) -> List[CommissionSubmission]:
        result = self.supabase.table(self.table_name).select('*').eq('lead_id', lead_id).execute()
        
        commissions = []
        if result.data:
            for item in result.data:
                commission = CommissionSubmission.from_dict(item)
                commissions.append(commission)
        
        return commissions