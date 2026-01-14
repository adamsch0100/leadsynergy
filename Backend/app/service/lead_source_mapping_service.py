import logging
import threading
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.database.supabase_client import SupabaseClientSingleton
from app.models.lead_source_alias import LeadSourceAlias


class LeadSourceMappingSingleton:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = LeadSourceMappingService()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None


class LeadSourceMappingService:
    """Service for managing lead source aliases/mappings."""

    def __init__(self) -> None:
        self.supabase = SupabaseClientSingleton.get_instance()
        self.table_name = "lead_source_aliases"
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def create_alias(
        self, alias_name: str, canonical_source_id: str, user_id: str
    ) -> Optional[LeadSourceAlias]:
        """Create a new alias mapping."""
        if not alias_name or not canonical_source_id or not user_id:
            raise ValueError("alias_name, canonical_source_id, and user_id are required")

        # Check if alias already exists for this user
        existing = self.get_alias_by_name(alias_name, user_id)
        if existing:
            raise ValueError(f"Alias '{alias_name}' already exists for this user")

        data = {
            "id": str(uuid.uuid4()),
            "alias_name": alias_name,
            "canonical_source_id": canonical_source_id,
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
        }

        result = self.supabase.table(self.table_name).insert(data).execute()

        if result.data and len(result.data) > 0:
            return LeadSourceAlias.from_dict(result.data[0])
        return None

    def get_alias_by_name(
        self, alias_name: str, user_id: str
    ) -> Optional[LeadSourceAlias]:
        """Get an alias by its name for a specific user."""
        result = (
            self.supabase.table(self.table_name)
            .select("*")
            .eq("alias_name", alias_name)
            .eq("user_id", user_id)
            .execute()
        )

        if result.data and len(result.data) > 0:
            return LeadSourceAlias.from_dict(result.data[0])
        return None

    def get_alias_by_id(self, alias_id: str, user_id: str) -> Optional[LeadSourceAlias]:
        """Get an alias by its ID."""
        result = (
            self.supabase.table(self.table_name)
            .select("*")
            .eq("id", alias_id)
            .eq("user_id", user_id)
            .execute()
        )

        if result.data and len(result.data) > 0:
            return LeadSourceAlias.from_dict(result.data[0])
        return None

    def get_aliases_for_source(
        self, canonical_source_id: str, user_id: str
    ) -> List[LeadSourceAlias]:
        """Get all aliases that point to a specific canonical source."""
        result = (
            self.supabase.table(self.table_name)
            .select("*")
            .eq("canonical_source_id", canonical_source_id)
            .eq("user_id", user_id)
            .execute()
        )

        if result.data:
            return [LeadSourceAlias.from_dict(item) for item in result.data]
        return []

    def get_all_aliases(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all alias mappings for a user with canonical source names joined."""
        # Get all aliases for user
        result = (
            self.supabase.table(self.table_name)
            .select("*, lead_source_settings!canonical_source_id(source_name)")
            .eq("user_id", user_id)
            .execute()
        )

        aliases = []
        if result.data:
            for item in result.data:
                alias_dict = {
                    "id": item.get("id"),
                    "alias_name": item.get("alias_name"),
                    "canonical_source_id": item.get("canonical_source_id"),
                    "user_id": item.get("user_id"),
                    "created_at": item.get("created_at"),
                }
                # Extract joined source name
                source_settings = item.get("lead_source_settings")
                if source_settings and isinstance(source_settings, dict):
                    alias_dict["canonical_source_name"] = source_settings.get(
                        "source_name"
                    )
                aliases.append(alias_dict)

        return aliases

    def resolve_source_name(
        self, source_name: str, user_id: str
    ) -> Optional[Dict[str, str]]:
        """
        Given a source name, check if it's an alias and return the canonical source info.
        Returns dict with canonical_source_id and canonical_source_name, or None if no alias exists.
        """
        alias = self.get_alias_by_name(source_name, user_id)
        if alias:
            # Get the canonical source name
            source_result = (
                self.supabase.table("lead_source_settings")
                .select("source_name")
                .eq("id", alias.canonical_source_id)
                .single()
                .execute()
            )
            canonical_name = None
            if source_result.data:
                canonical_name = source_result.data.get("source_name")

            return {
                "canonical_source_id": alias.canonical_source_id,
                "canonical_source_name": canonical_name,
            }
        return None

    def delete_alias(self, alias_id: str, user_id: str) -> bool:
        """Delete an alias mapping."""
        # Verify ownership
        existing = self.get_alias_by_id(alias_id, user_id)
        if not existing:
            raise ValueError("Alias not found or access denied")

        result = (
            self.supabase.table(self.table_name)
            .delete()
            .eq("id", alias_id)
            .eq("user_id", user_id)
            .execute()
        )

        return bool(result.data)

    def merge_sources(
        self,
        source_ids_to_merge: List[str],
        canonical_source_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Merge multiple sources into one canonical source.
        - Creates aliases for the non-canonical source names
        - Updates all leads with merged source names to use canonical name
        - Deactivates the merged (non-canonical) source settings

        Returns a summary of the merge operation.
        """
        if not source_ids_to_merge or not canonical_source_id or not user_id:
            raise ValueError(
                "source_ids_to_merge, canonical_source_id, and user_id are required"
            )

        if canonical_source_id not in source_ids_to_merge:
            raise ValueError("canonical_source_id must be in source_ids_to_merge")

        # Get canonical source details
        canonical_result = (
            self.supabase.table("lead_source_settings")
            .select("*")
            .eq("id", canonical_source_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )

        if not canonical_result.data:
            raise ValueError("Canonical source not found or access denied")

        canonical_source_name = canonical_result.data.get("source_name")

        # Get all sources to merge
        sources_to_process = []
        for source_id in source_ids_to_merge:
            if source_id == canonical_source_id:
                continue  # Skip the canonical source

            source_result = (
                self.supabase.table("lead_source_settings")
                .select("*")
                .eq("id", source_id)
                .eq("user_id", user_id)
                .single()
                .execute()
            )

            if source_result.data:
                sources_to_process.append(source_result.data)

        merge_results = {
            "canonical_source_id": canonical_source_id,
            "canonical_source_name": canonical_source_name,
            "aliases_created": [],
            "leads_updated": 0,
            "sources_deactivated": [],
            "errors": [],
        }

        for source in sources_to_process:
            source_id = source.get("id")
            source_name = source.get("source_name")

            try:
                # Create alias for this source name
                existing_alias = self.get_alias_by_name(source_name, user_id)
                if not existing_alias:
                    alias = self.create_alias(source_name, canonical_source_id, user_id)
                    if alias:
                        merge_results["aliases_created"].append(source_name)

                # Update all leads with this source name to use canonical name
                leads_result = (
                    self.supabase.table("leads")
                    .update({"source": canonical_source_name})
                    .eq("source", source_name)
                    .eq("user_id", user_id)
                    .execute()
                )

                if leads_result.data:
                    merge_results["leads_updated"] += len(leads_result.data)

                # Deactivate the merged source setting
                self.supabase.table("lead_source_settings").update(
                    {"is_active": False, "updated_at": datetime.utcnow().isoformat()}
                ).eq("id", source_id).eq("user_id", user_id).execute()

                merge_results["sources_deactivated"].append(source_name)

            except Exception as e:
                self.logger.error(f"Error merging source {source_name}: {str(e)}")
                merge_results["errors"].append(
                    {"source_name": source_name, "error": str(e)}
                )

        return merge_results
