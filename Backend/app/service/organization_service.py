from typing import List, Dict, Any, Optional
import threading 
import uuid
from datetime import datetime

from app.models.organization import Organization
from app.database.supabase_client import SupabaseClientSingleton
from supabase import Client

class OrganizationServiceSingleton:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = OrganizationService()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None

class OrganizationService:
    def __init__(self):
        self.supabase: Client = SupabaseClientSingleton.get_instance()
        self.table_name = "organizations"

    def create(self, org: Organization) -> Organization:
        if not org.id:
            org.id = str(uuid.uuid4())

        if not org.created_at:
            org.created_at = datetime.now()
            
        org.updated_at = datetime.now()

        # Convert to dict for insertion
        data = org.to_dict()

        # Insert into Supabase
        result = self.supabase.table(self.table_name).insert(data).execute()

        # Update org with returned data
        if result.data and len(result.data) > 0:
            returned_data = result.data[0]
            for key, value in returned_data.items():
                setattr(org, key, value)

        return org

    def get_by_id(self, org_id: str) -> Optional[Organization]:
        result = self.supabase.table(self.table_name).select('*').eq('id', org_id).execute()

        if result.data and len(result.data) > 0:
            return Organization.from_dict(result.data[0])
        return None
        
    def get_by_slug(self, slug: str) -> Optional[Organization]:
        result = self.supabase.table(self.table_name).select('*').eq('slug', slug).execute()

        if result.data and len(result.data) > 0:
            return Organization.from_dict(result.data[0])
        return None

    def get_all(self) -> List[Organization]:
        result = self.supabase.table(self.table_name).select('*').execute()
        
        orgs = []
        if result.data:
            for item in result.data:
                org = Organization.from_dict(item)
                orgs.append(org)
        
        return orgs
        
    def update(self, org: Organization) -> Organization:
        if not org.id:
            raise ValueError("Organization must have an ID to be updated")

        org.updated_at = datetime.now()

        # Convert to dict for update
        data = org.to_dict()
        id_val = data.pop('id')  # Remove ID from the data to be updated

        # Update in Supabase
        result = self.supabase.table(self.table_name).update(data).eq('id', id_val).execute()

        # Update org with returned data
        if result.data and len(result.data) > 0:
            returned_data = result.data[0]
            for key, value in returned_data.items():
                setattr(org, key, value)

        return org
        
    def delete(self, org_id: str) -> bool:
        result = self.supabase.table(self.table_name).delete().eq('id', org_id).execute()
        return result.data is not None and len(result.data) > 0