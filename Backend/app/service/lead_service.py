from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import threading
from supabase import Client

from app.models.lead import Lead
from app.database.supabase_client import SupabaseClientSingleton

from app.utils.constants import Credentials


class LeadServiceSingleton:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = LeadService()

        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None


CREDS = Credentials()


class LeadService:
    def __init__(self):
        self.api_key = CREDS.SUPABASE_SECRET_KEY
        self.supabase_url = CREDS.SUPABASE_URL
        self.supabase: Client = SupabaseClientSingleton.get_instance()
        self.table_name = "leads"
        self._cache = None

    @property
    def cache(self):
        if self._cache is None:
            from app.database.lead_cache import LeadCacheSingleton

            self._cache = LeadCacheSingleton.get_instance()
        return self._cache

    # Basic CRUD Operations
    def create(self, lead: Lead) -> "Lead":
        if not lead.id:
            lead.id = str(uuid.uuid4())

        if not lead.created_at:
            lead.created_at = datetime.now()
        lead.updated_at = datetime.now()

        # Convert lead to dict for insertion
        data = vars(lead)

        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()

        data = {k: v for k, v in data.items() if v is not None}

        # Insert into Supabase
        result = self.supabase.table(self.table_name).insert(data).execute()

        # Update lead with returned data if available
        if result.data and len(result.data) > 0:
            returned_data = result.data[0]
            for key, value in returned_data.items():
                setattr(lead, key, value)

        print("Lead is successfully added to database")

        try:
            # Also cache the lead in Redis
            if lead.fub_person_id:
                self.cache.store_lead(lead)
                print(f"Lead {lead.fub_person_id} cached in Redis")
        except Exception as e:
            print(f"Error caching lead in Redis: {str(e)}")

        return lead

    def exists_by_fub_id(self, fub_person_id: str) -> bool:
        try:
            result = (
                self.supabase.table(self.table_name)
                .select("id")
                .eq("fub_person_id", str(fub_person_id))
                .execute()
            )
        except:
            return False

        return bool(result.data and len(result.data) > 0)

    # Get by ID
    def get_by_id(self, lead_id: str) -> Optional["Lead"]:
        result = (
            self.supabase.table(self.table_name).select("*").eq("id", lead_id).execute()
        )

        if result.data and len(result.data) > 0:
            import json
            lead = Lead()
            data = result.data[0]

            for key, value in data.items():
                if hasattr(lead, key):
                    # Parse metadata if it's a JSON string
                    if key == "metadata" and isinstance(value, str):
                        try:
                            value = json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            value = {}
                    setattr(lead, key, value)

            return lead
        return None

    def get_by_fub_person_id(self, fub_person_id: str) -> Optional["Lead"]:
        """Get a lead by its FUB person ID"""
        try:
            result = (
                self.supabase.table(self.table_name)
                .select("*")
                .eq("fub_person_id", fub_person_id)
                .execute()
            )

            if result.data and len(result.data) > 0:
                import json
                lead = Lead()
                data = result.data[0]

                for key, value in data.items():
                    if hasattr(lead, key):
                        # Parse metadata if it's a JSON string
                        if key == "metadata" and isinstance(value, str):
                            try:
                                value = json.loads(value)
                            except (json.JSONDecodeError, TypeError):
                                value = {}
                        setattr(lead, key, value)

                return lead

            return None
        except Exception as e:
            print(f"Error retrieving lead with FUB person ID {fub_person_id}: {str(e)}")
            return None

    # Get leads by agent ID
    def get_by_agent_id(
        self, agent_id: str, limit: int = 100, offset: int = 0
    ) -> List["Lead"]:
        """Get all leads assigned to a specific agent"""
        try:
            query = (
                self.supabase.table(self.table_name)
                .select("*")
                .eq("assigned_agent_id", agent_id)
            )

            # Apply pagination
            query = query.range(offset, offset + limit - 1)
            result = query.execute()

            leads = []
            if result.data:
                import json
                for item in result.data:
                    lead = Lead()

                    for key, value in item.items():
                        if hasattr(lead, key):
                            # Parse metadata if it's a JSON string
                            if key == "metadata" and isinstance(value, str):
                                try:
                                    value = json.loads(value)
                                except (json.JSONDecodeError, TypeError):
                                    value = {}
                            setattr(lead, key, value)

                    leads.append(lead)

            return leads
        except Exception as e:
            print(f"Error retrieving leads for agent {agent_id}: {str(e)}")
            return []

    # Get lead with notes
    def get_with_notes(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Get a lead with its notes"""
        try:
            # First get the lead
            lead_result = (
                self.supabase.table(self.table_name)
                .select("*")
                .eq("id", lead_id)
                .single()
                .execute()
            )

            if not lead_result.data:
                return None

            # Then get the notes for this lead
            notes_result = (
                self.supabase.table("lead_notes")
                .select("*")
                .eq("lead_id", lead_id)
                .execute()
            )

            # Combine lead with its notes
            lead_data = lead_result.data
            lead_data["notes"] = notes_result.data if notes_result.data else []

            return lead_data
        except Exception as e:
            print(f"Error retrieving lead with notes for ID {lead_id}: {str(e)}")
            return None

    # Get all leads
    def get_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List["Lead"]:
        """Get all leads with optional filters and pagination"""
        try:
            leads = []
            page_size = min(limit, 1000)  # Supabase max is 1000 per request
            current_offset = offset
            remaining = limit

            while remaining > 0:
                fetch_count = min(page_size, remaining)
                query = self.supabase.table(self.table_name).select("*")

                if filters:
                    for field, value in filters.items():
                        query = query.eq(field, value)

                # Pagination - fetch in chunks of up to 1000
                query = query.range(current_offset, current_offset + fetch_count - 1)
                result = query.execute()

                if not result.data:
                    break  # No more data

                import json
                for item in result.data:
                    lead = Lead()

                    for key, value in item.items():
                        if hasattr(lead, key):
                            # Parse metadata if it's a JSON string
                            if key == "metadata" and isinstance(value, str):
                                try:
                                    value = json.loads(value)
                                except (json.JSONDecodeError, TypeError):
                                    value = {}
                            setattr(lead, key, value)

                    leads.append(lead)

                fetched = len(result.data)
                if fetched < fetch_count:
                    break  # Got all available data

                remaining -= fetched
                current_offset += fetched

            return leads
        except Exception as e:
            print(f"Error retrieving all leads: {str(e)}")
            return []

    # Get leads by source
    def get_by_source(
        self, source: str, limit: int = 100, offset: int = 0
    ) -> List["Lead"]:
        """Get all leads from a specific source"""
        try:
            query = (
                self.supabase.table(self.table_name).select("*").eq("source", source)
            )

            # Apply pagination
            query = query.range(offset, offset + limit - 1)
            result = query.execute()

            leads = []
            if result.data:
                import json
                for item in result.data:
                    lead = Lead()

                    for key, value in item.items():
                        if hasattr(lead, key):
                            # Parse metadata if it's a JSON string
                            if key == "metadata" and isinstance(value, str):
                                try:
                                    value = json.loads(value)
                                except (json.JSONDecodeError, TypeError):
                                    value = {}
                            setattr(lead, key, value)

                    leads.append(lead)

            return leads
        except Exception as e:
            print(f"Error retrieving leads for source {source}: {str(e)}")
            return []

    # Get leads by source and user
    def get_by_source_and_user(
        self, source: str, user_id: str, limit: int = 100, offset: int = 0
    ) -> List["Lead"]:
        """Get all leads from a specific source belonging to a specific user"""
        try:
            query = (
                self.supabase.table(self.table_name)
                .select("*")
                .eq("source", source)
                .eq("user_id", user_id)
            )

            # Apply pagination
            query = query.range(offset, offset + limit - 1)
            result = query.execute()

            leads = []
            if result.data:
                import json
                for item in result.data:
                    lead = Lead()

                    for key, value in item.items():
                        if hasattr(lead, key):
                            # Parse metadata if it's a JSON string
                            if key == "metadata" and isinstance(value, str):
                                try:
                                    value = json.loads(value)
                                except (json.JSONDecodeError, TypeError):
                                    value = {}
                            setattr(lead, key, value)

                    leads.append(lead)

            return leads
        except Exception as e:
            print(f"Error retrieving leads for source {source} and user {user_id}: {str(e)}")
            return []

    # Get leads by status
    def get_by_status(
        self, status: str, limit: int = 100, offset: int = 0
    ) -> List["Lead"]:
        """Get all leads with a specific status"""
        try:
            query = (
                self.supabase.table(self.table_name).select("*").eq("status", status)
            )

            # Apply pagination
            query = query.range(offset, offset + limit - 1)
            result = query.execute()

            leads = []
            if result.data:
                import json
                for item in result.data:
                    lead = Lead()

                    for key, value in item.items():
                        if hasattr(lead, key):
                            # Parse metadata if it's a JSON string
                            if key == "metadata" and isinstance(value, str):
                                try:
                                    value = json.loads(value)
                                except (json.JSONDecodeError, TypeError):
                                    value = {}
                            setattr(lead, key, value)

                    leads.append(lead)

            return leads
        except Exception as e:
            print(f"Error retrieving leads with status {status}: {str(e)}")
            return []

    # Updating Lead
    def update(self, lead: Lead) -> Lead:
        if not lead.id:
            raise ValueError("Lead must have an ID to be updated")

        lead.updated_at = datetime.now()

        data = vars(lead)
        id_val = data.pop("id")

        # Convert all datetime fields to isoformat
        import json
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif key == "metadata" and isinstance(value, dict):
                # Convert metadata dict to JSON string for Supabase
                data[key] = json.dumps(value)

        data = {k: v for k, v in data.items() if v is not None}

        result = (
            self.supabase.table(self.table_name).update(data).eq("id", id_val).execute()
        )

        if result.data and len(result.data) > 0:
            import json
            returned_data = result.data[0]
            for key, value in returned_data.items():
                # Parse metadata if it's a JSON string
                if key == "metadata" and isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        value = {}
                setattr(lead, key, value)

        return lead

    # Update lead stage
    def update_stage(self, lead_id: str, stage_id: str) -> Optional["Lead"]:
        """Update just the stage of a lead"""
        try:
            # First get the current lead
            lead = self.get_by_id(lead_id)
            if not lead:
                return None

            # Update the stage
            lead.stage_id = stage_id

            # Save the updated lead
            return self.update(lead)
        except Exception as e:
            print(f"Error updating stage for lead {lead_id}: {str(e)}")
            return None

    # Update lead status
    def update_status(self, lead_id: str, status: str) -> Optional["Lead"]:
        """Update just the status of a lead"""
        try:
            # First get the current lead
            lead = self.get_by_id(lead_id)
            if not lead:
                return None

            # Update the status
            lead.status = status

            # Save the updated lead
            return self.update(lead)
        except Exception as e:
            print(f"Error updating status for lead {lead_id}: {str(e)}")
            return None

    # Delete a lead
    def delete(self, id: str) -> bool:
        result = self.supabase.table(self.table_name).delete().eq("id", id).execute()

        return result.data is not None and len(result.data) > 0

    # Assign lead to agent
    def assign_to_agent(self, lead_id: str, agent_id: str) -> Optional["Lead"]:
        """Assign a lead to a specific agent"""
        try:
            # First get the current lead
            lead = self.get_by_id(lead_id)
            if not lead:
                return None

            # Update the assigned agent
            lead.assigned_agent_id = agent_id

            # Save the updated lead
            return self.update(lead)
        except Exception as e:
            print(f"Error assigning lead {lead_id} to agent {agent_id}: {str(e)}")
            return None

    ### FUB Integration

    # Create
    def create_from_fub(self, fub_data: Dict[str, Any]) -> "Lead":
        fub_id = str(fub_data.get("id"))
        if self.exists_by_fub_id(fub_id):
            print("User already exists...")
            return Lead()

        lead = Lead.from_fub(fub_data)
        return self.create(lead)

    # Update
    def update_from_fub(self, fub_data: Dict[str, Any]) -> Optional["Lead"]:
        fub_id = str(fub_data.get("id"))
        if not fub_id:
            return None

        # Find FUB Parent ID
        result = (
            self.supabase.table(self.table_name)
            .select("*")
            .eq("fub_person_id", fub_id)
            .execute()
        )

        if not result.data or len(result.data) == 0:
            return self.create_from_fub(fub_data)

        # Update
        lead = Lead()
        for key, value in result.data[0].items():
            if hasattr(lead, key):
                setattr(lead, key, value)

        # Update with new FUB data
        updated_lead = Lead.from_fub(fub_data)

        updated_lead.id = lead.id

        updated_lead.created_at = lead.created_at

        return self.update(updated_lead)

    # Check if the source of the Lead is in DB
    def check_source(self, lead: Lead) -> bool:
        print(f"Lead Source is: {lead.source}")
        result = (
            self.supabase.table("lead_source_settings")
            .select("*")
            .eq("source_name", lead.source)
            .execute()
        )

        if result.data and len(result.data) > 0:
            return True
        return False

    # Get the FUB Mapping of the lead
    def get_fub_stage_mapping(self, lead: Lead) -> Dict[str, Any]:
        mapping = (
            self.supabase.table("lead_source_settings")
            .select("*")
            .eq("source_name", lead.source)
            .execute()
        )

        result_map = find_mapping_by_exact_key(mapping.data, lead.status)
        return result_map


def find_mapping_by_exact_key(dict_list: list, key_name) -> Dict[str, Any]:
    if not dict_list or len(dict_list) == 0:
        return {}

    # Get the first dictionary from the list since we're looking for a specific source
    source_dict = dict_list[0]

    # Check if fub_stage_mapping exists in the dictionary
    if "fub_stage_mapping" not in source_dict:
        return {}

    mapping = source_dict["fub_stage_mapping"]

    # Parse the mapping if it's a string (JSON)
    if isinstance(mapping, str):
        try:
            import json

            mapping = json.loads(mapping)
        except json.JSONDecodeError:
            return {}

    # Return the mapping for the specific key if it exists
    return mapping.get(key_name, {})


# Register with container during module initialization
from app.utils.dependency_container import DependencyContainer

DependencyContainer.get_instance().register_lazy_initializer(
    "lead_service", LeadService
)
