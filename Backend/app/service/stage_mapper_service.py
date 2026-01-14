import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from supabase import Client

from app.database.fub_api_client import FUBApiClient
from app.database.supabase_client import SupabaseClientSingleton
from app.models.stage_mapping import StageMapping
from app.service.lead_source_settings_service import LeadSourceSettingsService
from app.utils.dependency_container import DependencyContainer

container = DependencyContainer.get_instance()


class StageMapperService:
    def __init__(self, user_api_key: str = None) -> None:
        self.supabase: Client = SupabaseClientSingleton.get_instance()
        self.table_name = "stage_mappings"
        self.fub_api_client = FUBApiClient(user_api_key)
        self.lead_source_settings_service = LeadSourceSettingsService()
        self.lead_service = container.get_service("lead_service")
        self._cached_fub_stages = None
        self._cache_timestamp = None

    ######################## Basic CRUD Operations ########################

    def create(self, stage_mapping: StageMapping) -> StageMapping:
        if not stage_mapping.id:
            stage_mapping.id = str(uuid.uuid4())

        if not stage_mapping.created_at:
            stage_mapping.created_at = datetime.now()

        stage_mapping.updated_at = datetime.now()

        # Add this check to convert dict to StageMapping if needed
        if isinstance(stage_mapping, dict):
            stage_mapping_obj = StageMapping()
            for key, value in stage_mapping.items():
                if hasattr(stage_mapping_obj, key):
                    setattr(stage_mapping_obj, key, value)
            stage_mapping = stage_mapping_obj

        # Convert to dict for insertion
        data = stage_mapping.to_dict()

        # Insert into Supabase
        result = self.supabase.table(self.table_name).insert(data).execute()

        # Update mapping with returned data if available
        if result.data and len(result.data) > 0:
            returned_data = result.data[0]
            for key, value in returned_data.items():
                if hasattr(stage_mapping, key):
                    setattr(stage_mapping, key, value)

        return stage_mapping

    def get_by_id(self, mapping_id: str) -> Optional[StageMapping]:
        result = (
            self.supabase.table(self.table_name)
            .select("*")
            .eq("id", mapping_id)
            .execute()
        )

        if result.data and len(result.data) > 0:
            return StageMapping.from_dict(result.data[0])

        return None

    def get_all(
        self, filters: Optional[Dict[str, Any]] = None, limit: int = 10, offset: int = 0
    ) -> List[StageMapping]:
        query = self.supabase.table(self.table_name).select("*")

        if filters:
            for field, value in filters.items():
                query = query.eq(field, value)

        # Pagination
        query = query.range(offset, offset + limit - 1)
        result = query.execute()

        mappings = []
        if result.data:
            for item in result.data:
                mapping = StageMapping.from_dict(item)
                mappings.append(mapping)

        return mappings

    def update(self, stage_mapping: StageMapping) -> StageMapping:
        if not stage_mapping.id:
            raise ValueError("Stage mapping must have an ID to be updated")

        # Add this check to convert dict to StageMapping if needed
        if isinstance(stage_mapping, dict):
            stage_mapping_obj = StageMapping()
            for key, value in stage_mapping.items():
                if hasattr(stage_mapping_obj, key):
                    setattr(stage_mapping_obj, key, value)
            stage_mapping = stage_mapping_obj

        stage_mapping.updated_at = datetime.now()

        data = stage_mapping.to_dict()
        id_val = data.pop("id")

        result = (
            self.supabase.table(self.table_name).update(data).eq("id", id_val).execute()
        )

        if result.data and len(result.data) > 0:
            returned_data = result.data[0]
            for key, value in returned_data.items():
                if hasattr(stage_mapping, key):
                    setattr(stage_mapping, key, value)

        return stage_mapping

    def delete(self, mapping_id: str) -> bool:
        result = (
            self.supabase.table(self.table_name).delete().eq("id", mapping_id).execute()
        )

        return result.data is not None and len(result.data) > 0

    ####################### FUB API Integration #######################

    def get_fub_stages(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        # Check if we need to refresh the cache
        cache_expiry = 3600
        current_time = datetime.now()

        if (
            self._cached_fub_stages is None
            or self._cache_timestamp is None
            or force_refresh
            or (current_time - self._cache_timestamp).total_seconds() > cache_expiry
        ):

            try:
                # Fetch stages from FUB API
                stages = self.fub_api_client.get_stages()

                # Update cache
                self._cached_fub_stages = stages
                self._cache_timestamp = current_time

                return stages
            except Exception as e:
                print(f"Error fetching stages from FUB API: {e}")
                return self._cached_fub_stages or []

        # Return cached stages
        return self._cached_fub_stages

    def get_fub_stage_by_id(self, stage_id: str) -> Optional[Dict[str, Any]]:
        stages = self.get_fub_stages()

        for stage in stages:
            if str(stage.get("id")) == stage_id:
                return stage

        return None

    def get_fub_stage_by_name(self, stage_name: str) -> Optional[Dict[str, Any]]:
        stages = self.get_fub_stages()

        for stage in stages:
            if stage.get("name", "").lower() == stage_name.lower():
                return stage

        return None

    ####################### Specialized Operations #######################

    def get_by_fub_stage_and_platform(
        self, fub_stage_id: str, platform: str
    ) -> Optional[StageMapping]:
        result = (
            self.supabase.table(self.table_name)
            .select("*")
            .eq("fub_stage_id", fub_stage_id)
            .eq("platform", platform)
            .execute()
        )

        if result.data and len(result.data) > 0:
            return StageMapping.from_dict(result.data[0])

        return None

    def get_mappings_by_user(self, user_id: str) -> List[StageMapping]:
        return self.get_all(filters={"user_id": user_id})

    def get_mapping_by_fub_person_id(
        self, fub_person_id: str
    ) -> Optional[StageMapping]:
        """
        Retrieves the stage mapping associated with a specific Follow Up Boss person ID.
        Since a lead can only have one source and stage in FUB, this returns a single mapping

        Args:
            fub_person_id (str): The Follow Up Boss person ID to search for

        Returns:
            Optional[StageMapping]: The stage mapping for the FUB person, or None if not found
        """
        try:
            # Get the lead from the databse using FUB person ID
            lead = self.lead_service.get_by_fub_person_id(fub_person_id)

            if not lead:
                print(f"Lead with FUB person ID {fub_person_id} not found")
                return None

            # Query the most relevant stage mapping (most recently updated)
            result = (
                self.supabase.table(self.table_name)
                .select("*")
                .eq("lead_id", lead.id)
                .order("updated_at", desc=True)
                .limit(1)
                .execute()
            )

            if result.data and len(result.data) > 0:
                return StageMapping.from_dict(result.data[0])

            return None

        except Exception as e:
            print(f"Error fetching mapping for FUB person ID {fub_person_id}: {str(e)}")
            return None

    def get_mappings_by_source(self, source_id: str) -> List[StageMapping]:
        return self.get_all(filters={"source_id": source_id})

    def get_mappings_by_platform(self, platform: str) -> List[StageMapping]:
        return self.get_all(filters={"platform": platform})

    def map_fub_stage_to_external(
        self, fub_stage_name: str, platform: str, source_id: Optional[str] = None
    ) -> str:
        filters = {
            "fub_stage_name": fub_stage_name,
            "platform": platform,
            "is_active": True,
        }

        if source_id:
            filters["source_id"] = source_id

        result = (
            self.supabase.table(self.table_name)
            .select("*")
            .eq("fub_stage_name", fub_stage_name)
            .eq("platform", platform)
        )

        if source_id:
            result = result.eq("source_id", source_id)

        result = result.eq("is_active", True).execute()

        if result.data and len(result.data) > 0:
            mapping = StageMapping.from_dict(result.data[0])
            return mapping.platform_stage_name

        # Return default mapping if no specific mapping found
        return "None"

    def add_stage_mapping(self, fub_person_id: str, source_name: str) -> StageMapping:
        try:
            # Get the lead from the database
            from app.service.lead_source_settings_service import (
                LeadSourceSettingsService,
            )

            lead_source_settings_service = LeadSourceSettingsService()

            ### Supabase Ops
            lead = self.lead_service.get_by_fub_person_id(fub_person_id)
            lead_source_settings = lead_source_settings_service.get_by_source_name(
                source_name
            )

            if not lead:
                raise ValueError(f"Lead with FUB person ID {fub_person_id} not found")

            if not lead_source_settings:
                print("Source Settings not found in DB")
                return StageMapping()

            # Get all platforms we need to sync with
            platforms_query = (
                self.supabase.table("lead_source_settings")
                .select("source_name")
                .eq("is_active", True)
                .execute()
            )
            platforms = (
                [item["source_name"] for item in platforms_query.data]
                if platforms_query.data
                else []
            )
            print(f"Platforms: {platforms}")

            # Compare if the source of lead matches in one of the platforms in database
            if lead.source in platforms:
                print(f"Matched! Lead Source {lead.source} matches {platforms}")
            else:
                raise ValueError(f"No Lead Source match for {lead.source} in database")

            # Insert into db
            mapping = StageMapping()
            mapping.source_id = lead_source_settings.id
            mapping.lead_id = lead.id
            mapping.fub_stage_id = lead.stage_id
            mapping.fub_stage_name = lead.status
            mapping.platform = lead_source_settings.source_name
            mapping.platform_stage_name = (
                lead_source_settings_service.return_stage_name(source_name, lead.status)
            )
            mapping.created_at = datetime.now()
            mapping.metadata = {}

            result = self.create(mapping)
            return result
        except Exception as e:
            print(f"{e}")
            raise ValueError(f"There is an error adding mapping: {e}")

    def handle_fub_stage_change(
        self, fub_person_id: str, fub_stage_id: str, fub_stage_name: str
    ) -> Dict[str, Any]:
        try:
            # Get the lead from the database
            lead = self.lead_service.get_by_fub_person_id(fub_person_id)

            if not lead:
                return {
                    "success": False,
                    "error": f"Lead with FUB person ID {fub_person_id} not found",
                }

            # Get all platforms we need to sync with
            platforms_query = (
                self.supabase.table("lead_source_settings")
                .select("source_name")
                .eq("is_active", True)
                .execute()
            )
            platforms = (
                [item["source_name"] for item in platforms_query.data]
                if platforms_query.data
                else []
            )
            print(f"Platforms: {platforms}")

            # Compare if the source of lead matches in one of the platforms in database
            if lead.source in platforms:
                print(f"Matched! Lead Source {lead.source} matches {platforms}")

                # Update lead status
                lead.status = fub_stage_name
                self.lead_service.update(lead)

                # Get or create a mapping
                mapping = self.get_mapping_by_fub_person_id(fub_person_id)
                if not mapping:
                    # Create new mapping if none exists
                    from app.service.lead_source_settings_service import (
                        LeadSourceSettingsService,
                    )

                    lead_source_settings_service = LeadSourceSettingsService()
                    lead_source_settings = (
                        lead_source_settings_service.get_by_source_name(lead.source)
                    )

                    mapping = StageMapping()
                    mapping.source_id = lead_source_settings.id
                    mapping.lead_id = lead.id
                    mapping.fub_stage_id = fub_stage_id
                    mapping.fub_stage_name = fub_stage_name
                    mapping.platform = lead.source
                    mapping.platform_stage_name = (
                        lead_source_settings_service.return_stage_name(
                            lead.source, fub_stage_name
                        )
                    )
                    mapping = self.create(mapping)
                else:
                    # Update existing mapping
                    mapping.fub_stage_id = fub_stage_id
                    mapping.fub_stage_name = fub_stage_name
                    mapping.platform_stage_name = (
                        self.lead_source_settings_service.return_stage_name(
                            lead.source, fub_stage_name
                        )
                    )
                    mapping = self.update(mapping)

                from app.referral_scrapers.referral_executor import ReferralExecutor

                executor = ReferralExecutor(lead, mapping)
                print(f"Initializing ReferralExecutor for {lead.source}")

                try:
                    if executor.execute():
                        print(f"Successfully updated the external platform for lead")
                        return {
                            "success": True,
                            "lead_id": lead.id,
                            "fub_stage": fub_stage_name,
                            "mapping": mapping.to_dict() if mapping else None,
                        }
                    else:
                        print(
                            f"Failed to update external platform - executor returned False"
                        )
                        return {
                            "success": False,
                            "error": "Failed to update external platform",
                        }
                except Exception as e:
                    print(f"Exception during executor execution: {str(e)}")
                    return {
                        "success": False,
                        "error": f"Error during executor execution: {str(e)}",
                    }
            else:
                print(
                    f"There is not Lead Source match for {lead.source} in database. Available platforms: {platforms}"
                )
                return {
                    "success": False,
                    "error": f"No Lead Source match for {lead.source} in database.",
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_completion(self, mapping_id: str) -> Dict[str, Any]:
        if not mapping_id:
            raise ValueError("Stage mapping must have an ID to be updated")

        stage_mapping = self.get_by_id(mapping_id)
        if not stage_mapping:
            raise ValueError("Stage is not found in database")

        result = (
            self.supabase.table(self.table_name)
            .update({"is_completed": True, "updated_at": datetime.now()})
            .eq("id", stage_mapping.id)
            .execute()
        )
        return result

    def create_default_mappings(
        self, user_id: str, source_id: str, platform: str
    ) -> List[StageMapping]:
        # Get all available stages from FUB
        fub_stages = self.get_fub_stages()

        # Default external platform mappings
        default_external_stages = {
            "New Lead": "New Referral",
            "Contacted": "In Progress",
            "Qualified": "Qualified",
            "Under Contract": "In Contract",
            "Closed": "Closed/Complete",
            "Lost": "Cancelled",
        }

        created_mappings = []

        # Create a mapping for each FUB stage
        for stage in fub_stages:
            stage_name = stage.get("name", "")
            stage_id = str(stage.get("id", ""))

            if not stage_name or not stage_id:
                continue

            mapping = StageMapping()
            mapping.user_id = user_id
            mapping.source_id = source_id
            mapping.platform = platform
            mapping.fub_stage_id = stage_id
            mapping.fub_stage_name = stage_name

            # Use default mapping if available, otherwise use the same name
            mapping.platform_stage_name = default_external_stages.get(
                stage_name, stage_name
            )
            mapping.metadata = {"fub_stage_data": stage, "created_from": "auto_mapping"}

            created = self.create(mapping)
            created_mappings.append(created)

        return created_mappings


DependencyContainer.get_instance().register_lazy_initializer(
    "stage_mapper_service", StageMapperService
)
