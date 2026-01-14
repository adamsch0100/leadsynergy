import threading
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import uuid
from supabase import create_client, Client
from dotenv import load_dotenv
import os
import json

from app.models.lead import LeadNote
from app.database.supabase_client import SupabaseClientSingleton
from app.service.lead_service import LeadService, LeadServiceSingleton

class NoteServiceSingleton:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = NoteService()

        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None


class NoteService:
    def __init__(self) -> None:
        self.supabase: Client = SupabaseClientSingleton.get_instance()
        self.table_name = "lead_notes"
        self._cache = None


    @property
    def cache(self):
        if self._cache is None:
            from app.database.lead_cache import LeadCacheSingleton
            self._cache = LeadCacheSingleton.get_instance()
        return self._cache
        
    ######################## Basic CRUD Operations ########################
    def create(self, note: LeadNote) -> LeadNote:
        if not note.id:
            note.id = str(uuid.uuid4())
        
        if not note.created_at:
            note.created_at = datetime.now()
        
        note.updated_at = datetime.now()
        
        data = vars(note)
        
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, dict):
                data[key] = json.dumps(value)
                
        data = {k: v for k, v in data.items() if v is not None}
        
        # Insert into Supabase
        result = self.supabase.table(self.table_name).insert(data).execute()
        
        # Update note with returned data if available
        if result.data and len(result.data) > 0:
            returned_data = result.data[0]
            for key, value in returned_data.items():
                if key == 'metadata' and value:
                    try:
                        setattr(note, key,json.loads(value))
                    except json.JSONDecoder:
                        setattr(note, key, {})
                else:
                    setattr(note, key, value)
                    
        print(f"Note successfully added to database for lead {note.lead_id}")
        return note
    
    
    def get_by_id(self, note_id: str) -> Optional[LeadNote]:
        result = self.supabase.table(self.table_name).select('*').eq('id', note_id).execute()
        
        if result.data and len(result.data) > 0:
            return self._parse_note_from_data(result.data[0])
        
        return None
    
    def get_by_note_id(self, note_id: str) -> Optional[LeadNote]:
        result = self.supabase.table(self.table_name).select('*').eq('note_id', note_id).execute()
        
        if result.data and len(result.data) > 0:
            note = LeadNote()
            data = result.data[0]

            for key, value in data.items():
                if hasattr(note, key):
                    setattr(note, key, value)
            return note
        
        return None
    
    
    def get_notes_for_lead(self, lead_id: str, limit: int = 100, offset: int = 0) -> List[LeadNote]:
        query = self.supabase.table(self.table_name).select('*').eq('lead', lead_id)
        
        # Add sorting by created_at in descending order
        query = query.order('created_at', desc=True)
        
        # Add pagination
        query = query.range(offset, offset + limit - 1)
        result = query.execute()
        
        notes = []
        
        if result.data:
            for item in result.data:
                note = self._parse_note_from_data(item)
                notes.append(note)
        
        return notes
    
    def update(self, note: LeadNote) -> LeadNote:
        """Update an existing note"""
        if not note.id:
            raise ValueError('Note must have an ID to be update')
        
        note.updated_at = datetime.now()
        
        data = vars(note)
        id_val = data.pop('id')
        
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, dict):
                data[key] = json.dumps(value)
                
        data = {k: v for k, v in data.items() if v is not None}
        
        result = self.supabase.table(self.table_name).update(data).eq('id', id_val).execute()
        
        if result.data and len(result.data) > 0:
            returned_data = result.data[0]
            for key, value in returned_data.items():
                if key == 'metadata' and value:
                    try:
                        setattr(note, key, json.loads(value))
                    except json.JSONDecodeError:
                        setattr(note, key, {})
                else:
                    setattr(note, key, value)
        
        return note
    
    
    def delete(self, note_id: str) -> bool:
        """Delete a note by its ID"""
        result = self.supabase.table(self.table_name).delete().eq('id', note_id).execute()
        return result.data is not None and len(result.data) > 0
    

    def delete_all_for_lead(self, lead_id: str) -> bool:
        """Delete all notes for a specific lead"""
        result = self.supabase.table(self.table_name).delete().eq('lead_id', lead_id).execute()
        return result.data is not None
    
    
    ######################## FUB Integration ########################
    def create_from_fub(self, fub_note_data: Dict[str, Any], lead_id: str) -> 'LeadNote':
        """Create a note from FUB note data"""
        """This goes into lead_note table in database"""
        print("Starting Creating Note in Database.... ")
        
        note = LeadNote()
        lead_service = LeadServiceSingleton.get_instance()
        
        # TODO: Get internal id from lead_notes using the personId
        lead = lead_service.get_by_fub_person_id(lead_id)
        
        note.lead_id = str(lead.id)
        note.note_id = str(fub_note_data.get('id'))
        note.content = fub_note_data.get('body', '')
        
        # Parse created date
        created_str = fub_note_data.get('created')
        if created_str:
            try:
                note.created_at = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                note.created_at = datetime.now()
                
        # Store original FUB data in metadata
        note.metadata = {
            'metadata': fub_note_data
        }
        
        return self.create(note)
        
    
    
    def update_from_fub(self, fub_note_data: Dict[str, Any], lead_id: str) -> Optional[LeadNote]:
        """Update a note from FUB note data or create if it doesn't exist"""
        fub_note_id = str(fub_note_data.get('id'))
        if not fub_note_id:
            return None
        
        # Find existing note
        existing_note = self.get_by_note_id(fub_note_id)
        
        if not existing_note:
            return self.create_from_fub(fub_note_data, lead_id)
        
        # Update existing note
        existing_note.content = fub_note_data.get('text', existing_note.content)
        existing_note.is_private = fub_note_data.get('isPrivate', existing_note.is_private)
        
        # Update metadata
        if not existing_note.metadata:
            existing_note.metadata = {}
            
        existing_note.metadata['fub_original'] = fub_note_data
        existing_note.metadata['last_synced'] = datetime.now().isoformat()
        
        
        self.update(existing_note)
    
    def sync_notes_from_fub(self, fub_notes: List[Dict[str, Any]], lead_id: str) -> List[LeadNote]:
        """Sync multiple notes from FUB for a lead"""
        synced_notes = []
        
        for fub_note in fub_notes:
            note = self.update_from_fub(fub_note, lead_id)
            if note:
                synced_notes.append(note)
                
        return synced_notes
    
    
    ######################## Helper Functions ########################
    def add_note_to_lead(self, lead_id:str, agent_id: str, content: str):
        pass
    
    
    def get_notes_by_agent(self, agent_id: str, limit: int = 100, offset: int = 0) -> List[LeadNote]:
        """Get all notes created by a specific agent"""
        query = self.supabase.table(self.table_name).select('*').eq('agent_id', agent_id)
        
        query = query.order('created_at', desc=True)
        
        # Add Pagination
        query = query.range(offset, offset + limit - 1)
        result = query.execute()
        
        notes = []
        
        if result.data:
            for item in result.data:
                note = self._parse_note_from_data(item)
                notes.append(note)
        
        return notes
    
    
    def _parse_note_from_data(self, data: Dict[str, Any]) -> LeadNote:
        """Parse a LeadNote object from database data"""
        note = LeadNote()
        
        for key, value in data.items():
            if key == 'metadata' and value:
                try:
                    setattr(note, key, json.loads(value))
                except (json.JSONDecodeError, TypeError):
                    setattr(note, key, {})
            elif key.endswith('_at') and value:
                try:
                    if isinstance(value, str):
                        setattr(note, key, datetime.fromisoformat(value.replace('Z', '+00:00')))
                    else:
                        setattr(note, key, value)
                except (ValueError, TypeError):
                    setattr(note, key, value)
            else:
                setattr(note, key, value)
        
        return note

from app.utils.dependency_container import DependencyContainer
DependencyContainer.get_instance().register_lazy_initializer("note_service", NoteService)