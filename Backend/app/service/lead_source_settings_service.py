import asyncio
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from flask import jsonify

print("!!!! LEAD_SOURCE_SETTINGS_SERVICE MODULE LOADED V4 !!!!")

from app.database.supabase_client import SupabaseClientSingleton
from app.models.lead import Lead
from app.models.lead_source_settings import LeadSourceSettings
from app.service.lead_service import LeadServiceSingleton
from app.utils.dependency_container import DependencyContainer


class LeadSourceSettingsSingleton:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = LeadSourceSettingsService()

        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None


class LeadSourceSettingsService:
    VALID_SYNC_INTERVALS = [1, 3, 7, 14, 21, 30, 45, 60]

    def __init__(self) -> None:
        self.supabase = SupabaseClientSingleton.get_instance()
        self.table_name = "lead_source_settings"
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

        # Thread pool for running blocking operations in async context
        self._executor = ThreadPoolExecutor(max_workers=5)

    def _get_lead_type_from_tags(self, lead) -> Optional[str]:
        """Extract lead type (buyer/seller) from lead tags"""
        try:
            tags = getattr(lead, 'tags', None) or []
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except (json.JSONDecodeError, TypeError):
                    tags = []

            for tag in tags:
                tag_lower = str(tag).lower()
                if 'seller' in tag_lower:
                    return 'seller'
                elif 'buyer' in tag_lower:
                    return 'buyer'

            return None
        except Exception:
            return None

    def create(self, settings: LeadSourceSettings) -> LeadSourceSettings:
        """Create a new lead source setting"""
        settings.created_at = datetime.now()
        settings.updated_at = datetime.now()

        data_dict = settings.to_dict()

        # Ensure JSON fields are properly serialized
        for field in ["fub_stage_mapping", "options", "metadata", "assignment_rules"]:
            if field in data_dict and not isinstance(data_dict[field], str):
                data_dict[field] = json.dumps(data_dict[field])

        result = self.supabase.table(self.table_name).insert(data_dict).execute()

        if result.data and len(result.data) > 0:
            return LeadSourceSettings.from_dict(result.data[0])
        return None

    def get_by_id(self, source_id):
        result = (
            self.supabase.table("lead_source_settings")
            .select("*")
            .eq("id", source_id)
            .single()
            .execute()
        )
        if result.data:
            return LeadSourceSettings.from_dict(result.data)
        return None

    def get_by_source_name(self, source_name: str) -> Optional[LeadSourceSettings]:
        """Get a lead source setting by source name"""
        result = (
            self.supabase.table(self.table_name)
            .select("*")
            .eq("source_name", source_name)
            .execute()
        )

        if result.data and len(result.data) > 0:
            return LeadSourceSettings.from_dict(result.data[0])
        return None

    def return_stage_name(self, source_name: str, stage: str) -> Dict[str, Any]:
        lead_source = self.get_by_source_name(source_name)

        if not lead_source or not lead_source.fub_stage_mapping:
            return None

        return {stage: lead_source.fub_stage_mapping.get(stage)}

    def get_all(self, filters=None, user_id=None):
        try:
            query = self.supabase.table("lead_source_settings").select("*")

            # Always filter by user_id if provided
            if user_id:
                query = query.eq("user_id", user_id)

            # Apply additional filters if provided
            if filters and isinstance(filters, dict):
                for key, value in filters.items():
                    query = query.eq(key, value)

            result = query.execute()
            return result.data if result and result.data else []
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in get_all: {str(e)}", exc_info=True)
            return []

    def get_active_sources(self, user_id=None) -> List[LeadSourceSettings]:
        """Get all active lead sources for a user (or all if no user_id provided for backward compatibility)"""
        return self.get_all(filters={"is_active": True}, user_id=user_id)

    def create_or_get_source(self, user_id: str, source_name: str, auto_discovered: bool = False) -> LeadSourceSettings:
        """Create a new lead source for a user or get existing one. Used for auto-discovery."""
        if not user_id or not source_name:
            raise ValueError("user_id and source_name are required")

        # First try to find existing source for this user
        existing = self.get_all(filters={"source_name": source_name}, user_id=user_id)
        if existing and len(existing) > 0:
            return LeadSourceSettings.from_dict(existing[0])

        # Create new source
        new_source = LeadSourceSettings()
        new_source.id = None  # Will be set by database
        new_source.source_name = source_name
        new_source.user_id = user_id
        new_source.auto_discovered = auto_discovered
        new_source.is_active = False  # Auto-discovered sources start inactive
        new_source.assignment_strategy = "specific"
        new_source.referral_fee_percent = 0.0
        new_source.fub_stage_mapping = {}
        new_source.metadata = {}
        new_source.assignment_rules = {}
        new_source.options = {}

        # Save to database
        result = self.supabase.table(self.table_name).insert(new_source.to_dict()).execute()

        if result.data and len(result.data) > 0:
            return LeadSourceSettings.from_dict(result.data[0])

        raise Exception(f"Failed to create lead source {source_name} for user {user_id}")

    def update_sync_settings(
        self, source_id: str, sync_interval_days: Optional[int], user_id: str = None
    ) -> Optional[LeadSourceSettings]:
        """Update sync interval for a lead source and calculate next sync time"""

        # Verify ownership if user_id provided
        if user_id:
            existing = self.get_by_id(source_id)
            if not existing or existing.user_id != user_id:
                raise ValueError("Lead source not found or access denied")

        if sync_interval_days in (0, "0"):
            sync_interval_days = None

        if sync_interval_days is not None and sync_interval_days not in self.VALID_SYNC_INTERVALS:
            raise ValueError(
                f"Invalid sync interval: {sync_interval_days}. Valid options: {self.VALID_SYNC_INTERVALS}"
            )

        now = datetime.utcnow()
        update_data = {
            "sync_interval_days": sync_interval_days,
            "updated_at": now.isoformat()
        }

        if sync_interval_days is not None:
            next_sync_at = now + timedelta(days=sync_interval_days)
            update_data["next_sync_at"] = next_sync_at.isoformat()
        else:
            update_data["next_sync_at"] = None

        result = (
            self.supabase.table(self.table_name)
            .update(update_data)
            .eq("id", source_id)
            .execute()
        )

        if result.data and len(result.data) > 0:
            return LeadSourceSettings.from_dict(result.data[0])
        return None

    def get_sources_due_for_sync(self, user_id: str = None) -> List[LeadSourceSettings]:
        """Return active lead sources that are due for scheduled sync"""
        active_sources = self.get_all(filters={"is_active": True}, user_id=user_id) or []
        due_sources: List[LeadSourceSettings] = []
        now = datetime.now(timezone.utc)

        for source_data in active_sources:
            settings = LeadSourceSettings.from_dict(source_data)

            if not settings.sync_interval_days:
                continue

            next_run = settings.next_sync_at
            if next_run and next_run.tzinfo is None:
                next_run = next_run.replace(tzinfo=timezone.utc)

            if not next_run or next_run <= now:
                due_sources.append(settings)

        return due_sources

    def mark_sync_completed(self, source_id: str, sync_interval_days: Optional[int], sync_results: Dict[str, Any] = None) -> Optional[LeadSourceSettings]:
        """Update last_sync_at, next_sync_at, and last_sync_results after a sync"""
        now = datetime.now(timezone.utc)
        update_data = {
            "last_sync_at": now.isoformat(),
            "updated_at": now.isoformat()
        }

        if sync_interval_days:
            update_data["next_sync_at"] = (now + timedelta(days=sync_interval_days)).isoformat()
        else:
            update_data["next_sync_at"] = None

        # Save sync results for persistence
        if sync_results is not None:
            # Prepare the results for storage - keep essential data, limit details to avoid bloat
            persisted_results = {
                "completed_at": now.isoformat(),
                "status": sync_results.get("status", "completed"),
                "successful": sync_results.get("successful", 0),
                "failed": sync_results.get("failed", 0),
                "skipped": sync_results.get("skipped", 0),
                "total_leads": sync_results.get("total_leads", 0),
                "processed": sync_results.get("processed", 0),
                "filter_summary": sync_results.get("filter_summary"),
                "error": sync_results.get("error"),
                # Store limited details (last 50 entries to avoid bloat)
                "details": (sync_results.get("details") or [])[-50:]
            }
            update_data["last_sync_results"] = json.dumps(persisted_results)

        result = (
            self.supabase.table(self.table_name)
            .update(update_data)
            .eq("id", source_id)
            .execute()
        )

        if result.data and len(result.data) > 0:
            return LeadSourceSettings.from_dict(result.data[0])
        return None

    def update(self, settings: LeadSourceSettings, user_id: str = None) -> LeadSourceSettings:
        """Update a lead source setting"""
        if user_id:
            # Verify ownership before updating
            existing = self.get_by_id(settings.id)
            if not existing or existing.user_id != user_id:
                raise ValueError("Lead source not found or access denied")

        settings.updated_at = datetime.now()

        data_dict = settings.to_dict()

        # Ensure JSON fields are properly serialized
        for field in ["fub_stage_mapping", "options", "metadata", "assignment_rules"]:
            if field in data_dict and not isinstance(data_dict[field], str):
                data_dict[field] = json.dumps(data_dict[field])

        result = (
            self.supabase.table(self.table_name)
            .update(data_dict)
            .eq("id", settings.id)
            .execute()
        )

        if result.data and len(result.data) > 0:
            return LeadSourceSettings.from_dict(result.data[0])
        return None

    def delete(self, setting_id: str, user_id: str = None) -> bool:
        """Delete a lead source setting"""
        if user_id:
            # Verify ownership before deleting
            existing = self.get_by_id(setting_id)
            if not existing or existing.user_id != user_id:
                raise ValueError("Lead source not found or access denied")

        result = (
            self.supabase.table(self.table_name).delete().eq("id", setting_id).execute()
        )

        return bool(result.data)

    def toggle_source_active_status(
        self, setting_id: str, is_active: bool, user_id: str = None
    ) -> LeadSourceSettings:
        """Toggle a lead source's active status"""
        # Verify ownership if user_id provided
        if user_id:
            existing = self.get_by_id(setting_id)
            if not existing or existing.user_id != user_id:
                raise ValueError("Lead source not found or access denied")

        result = (
            self.supabase.table(self.table_name)
            .update({"is_active": is_active, "updated_at": datetime.now().isoformat()})
            .eq("id", setting_id)
            .execute()
        )

        if result.data and len(result.data) > 0:
            return LeadSourceSettings.from_dict(result.data[0])
        return None

    def update_stage_mappings(self, source_id, fub_stage_mapping, user_id=None):
        # Verify ownership if user_id provided
        if user_id:
            existing = self.get_by_id(source_id)
            if not existing or existing.user_id != user_id:
                raise ValueError("Lead source not found or access denied")

        # Ensure fub_stage_mapping is properly serialized
        if isinstance(fub_stage_mapping, dict):
            fub_stage_mapping = json.dumps(fub_stage_mapping)

        result = (
            self.supabase.table("lead_source_settings")
            .update({"fub_stage_mapping": fub_stage_mapping, "updated_at": "now()"})
            .eq("id", source_id)
            .execute()
        )

        if result.data and len(result.data) > 0:
            return LeadSourceSettings.from_dict(result.data[0])
        return None

    def handle_fub_stage_changef(self, lead: Lead):
        pass

    def handle_fub_stage_change(
        self, fub_person_id: str, fub_stage_id: str, fub_stage_name: str, organization_id: str = None
    ) -> Dict[str, Any]:
        """
        Handle stage changes in FUB and trigger appropriate actions in connected platforms

        Args:
            fub_person_id: The FUB person ID
            fub_stage_id: The FUB stage ID
            fub_stage_name: The FUB stage name

        Returns:
            Dict with success status and results for each platform
        """
        try:
            # Get the lead from the database
            lead_service = LeadServiceSingleton.get_instance()
            lead = lead_service.get_by_fub_person_id(fub_person_id)

            organization_id = getattr(lead, "organization_id", None)
            
            # Get organization_id from lead metadata or default to None
            # Multi-tenant: organization_id should be passed from webhook handler or user context
            if organization_id is None:
                if lead and hasattr(lead, 'metadata') and lead.metadata:
                    organization_id = lead.metadata.get('organization_id')
                # If still None, we'll use None - services can handle this

            if not lead:
                return {
                    "success": False,
                    "error": f"Lead with FUB person ID {fub_person_id} not found",
                }

            # Get all active platforms we need to sync with
            active_sources_data = self.get_active_sources() or []
            active_sources: List[LeadSourceSettings] = []

            for source_data in active_sources_data:
                if isinstance(source_data, LeadSourceSettings):
                    active_sources.append(source_data)
                else:
                    active_sources.append(LeadSourceSettings.from_dict(source_data))

            self.logger.info(f"Found {len(active_sources)} active sources")

            # Import the factory here to avoid circular imports
            from app.referral_scrapers.referral_service_factory import (
                ReferralServiceFactory,
            )

            # Track results for each platform
            platform_results = {}

            # Process each active platform
            for source in active_sources:
                platform = source.source_name
                try:
                    self.logger.info(f"Processing platform: {platform}")

                    # Get the mapped stage for this platform from the source settings
                    mapped_stage = source.get_mapped_stage(fub_stage_name)

                    if not mapped_stage:
                        self.logger.warning(
                            f"No stage mapping found for FUB stage '{fub_stage_name}' on platform {platform}"
                        )
                        platform_results[platform] = {
                            "success": False,
                            "message": f"No stage mapping found for FUB stage '{fub_stage_name}'",
                        }
                        continue

                    self.logger.info(
                        f"Mapped {fub_stage_name} to {mapped_stage} for platform {platform}"
                    )

                    # Check if we have a service implementation for this platform
                    if not ReferralServiceFactory.service_exists(platform):
                        platform_results[platform] = {
                            "success": False,
                            "message": f"No service implementation found for platform {platform}",
                        }
                        continue

                    # Store the mapped stage in the lead metadata for the service to use
                    lead.metadata = lead.metadata or {}
                    lead.metadata[f"{platform.lower()}_status"] = mapped_stage
                    lead_service.update(lead)

                    # Create service with proper status format
                    if platform.lower() == "referralexchange":
                        # ReferralExchange expects status as list/tuple [main_option, sub_option]
                        if isinstance(mapped_stage, str):
                            if "::" in mapped_stage:
                                main, sub = [part.strip() for part in mapped_stage.split("::", 1)]
                                status_for_service = [main, sub]
                            else:
                                status_for_service = [mapped_stage, ""]
                        elif isinstance(mapped_stage, (list, tuple)) and len(mapped_stage) >= 2:
                            status_for_service = [mapped_stage[0], mapped_stage[1]]
                        else:
                            status_for_service = [str(mapped_stage), ""]
                        from app.referral_scrapers.referral_exchange.referral_exchange_service import ReferralExchangeService
                        service = ReferralExchangeService(lead=lead, status=status_for_service, organization_id=organization_id)
                    elif platform.lower() == "redfin":
                        from app.referral_scrapers.redfin.redfin_service import RedfinService
                        service = RedfinService(lead=lead, status=mapped_stage, organization_id=organization_id)
                    elif platform.lower() == "homelight":
                        from app.referral_scrapers.homelight.homelight_service import HomelightService
                        service = HomelightService(lead=lead, status=mapped_stage, organization_id=organization_id, same_status_note=self.settings.same_status_note)
                    else:
                        # Use factory for other platforms
                        service = ReferralServiceFactory.get_service(platform, lead=lead)
                        if not service:
                            platform_results[platform] = {
                                "success": False,
                                "message": f"Failed to create service for platform {platform}",
                            }
                            continue

                    # Run the service's main method
                    if platform.lower() == "redfin":
                        result = service.redfin_run()
                    elif platform.lower() == "homelight":
                        result = service.homelight_run()
                    elif platform.lower() == "referralexchange":
                        result = service.referral_exchange_run()
                    else:
                        # For other platforms, call a more generic method
                        try:
                            result = service.run()
                        except AttributeError:
                            # Fall back to platform-specific run method
                            run_method = getattr(service, f"{platform.lower().replace(' ', '_')}_run", None)
                            if run_method:
                                result = run_method()
                            else:
                                result = False

                    if result:
                        next_run_time = service.calculate_next_run_time()

                        platform_results[platform] = {
                            "success": True,
                            "message": f"Successfully updated {platform} status to '{mapped_stage}'",
                            "next_scheduled_update": next_run_time.isoformat(),
                        }

                        # Update the lead with the last updated time and next update time
                        lead.metadata[f"{platform.lower()}_last_updated"] = (
                            datetime.now().isoformat()
                        )
                        lead.metadata[f"{platform.lower()}_next_update"] = (
                            next_run_time.isoformat()
                        )
                        lead_service.update(lead)
                    else:
                        platform_results[platform] = {
                            "success": False,
                            "message": f"Failed to update status in {platform}",
                        }

                except Exception as e:
                    self.logger.error(f"Error processing platform {platform}: {str(e)}")
                    platform_results[platform] = {"success": False, "error": str(e)}

            # Update the lead's FUB stage in our database
            lead.fub_stage_id = fub_stage_id
            lead.fub_stage_name = fub_stage_name
            lead.updated_at = datetime.now()
            updated_lead = lead_service.update(lead)

            # Clean up HomeLight service if it exists
            if hasattr(self, '_homelight_service') and self._homelight_service:
                try:
                    self._homelight_service.logout()
                except Exception as e:
                    self.logger.warning(f"Error cleaning up HomeLight service: {e}")
                finally:
                    self._homelight_service = None

            return {
                "success": True,
                "lead": updated_lead.to_dict() if updated_lead else None,
                "platform_results": platform_results,
            }

        except Exception as e:
            self.logger.error(f"Error in handle_fub_stage_change: {str(e)}")
            return {"success": False, "error": str(e)}

    async def handle_fub_stage_change_async(
        self, fub_person_id: str, fub_stage_id: str, fub_stage_name: str, organization_id: str = None
    ) -> Dict[str, Any]:
        """
        Async version of handle_fub_stage_change for use in webhook handlers

        Args:
            fub_person_id: The FUB person ID
            fub_stage_id: The FUB stage ID
            fub_stage_name: The FUB stage name

        Returns:
            Dict with success status and results for each platform
        """
        # Run the blocking operation in a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self.handle_fub_stage_change,
            fub_person_id,
            fub_stage_id,
            fub_stage_name,
        )

    def get_all_platforms_for_lead(self, lead: Lead) -> List[Dict[str, Any]]:
        """
        Get all platforms associated with a lead based on lead source and agent preferences

        Args:
            lead: The lead to check

        Returns:
            List of platform info dictionaries
        """
        platforms = []

        # Get lead source from lead
        lead_source = lead.source
        if not lead_source:
            return platforms

        # Get the lead source settings
        lead_source_setting = self.get_by_source_name(lead_source)
        if lead_source_setting and lead_source_setting.is_active:
            # Get the current platform status if available
            status = None
            if (
                lead.metadata
                and f"{lead_source_setting.source_name.lower()}_status" in lead.metadata
            ):
                status = lead.metadata[
                    f"{lead_source_setting.source_name.lower()}_status"
                ]

            platforms.append(
                {
                    "name": lead_source_setting.source_name,
                    "is_active": lead_source_setting.is_active,
                    "current_status": status,
                    "available_options": lead_source_setting.get_available_options(),
                    "fee_percentage": lead_source_setting.referral_fee_percent,
                }
            )

        return platforms

    def update_all_platform_statuses(
        self, lead: Lead, fub_stage_name: str
    ) -> Dict[str, Any]:
        """
        Update the status on all platforms for a lead based on FUB stage

        Args:
            lead: The lead to update
            fub_stage_name: The FUB stage name to map

        Returns:
            Dict with results for each platform
        """
        if not lead.fub_person_id:
            return {"success": False, "error": "Lead has no FUB person ID"}

        return self.handle_fub_stage_change(
            lead.fub_person_id, lead.fub_stage_id or "", fub_stage_name
        )

    def sync_single_source(self, source_name: str, fub_person_id: str, fub_stage_id: str, fub_stage_name: str, organization_id: str = None) -> Dict[str, Any]:
        print(f"DEBUG: sync_single_source called for {source_name} - person_id: {fub_person_id}")
        """
        Sync a single lead source (used by API endpoints)

        Args:
            source_name: The name of the source to sync (e.g., 'HomeLight')
            fub_person_id: The FUB person ID
            fub_stage_id: The FUB stage ID
            fub_stage_name: The FUB stage name
            organization_id: Optional organization ID

        Returns:
            Dict with success status and results for the platform
        """
        try:
            # Get the lead from the database
            lead_service = LeadServiceSingleton.get_instance()
            lead = lead_service.get_by_fub_person_id(fub_person_id)

            if not lead:
                return {
                    "success": False,
                    "error": f"Lead with FUB person ID {fub_person_id} not found",
                }

            # Get the lead source settings
            source_settings = self.get_by_source_name(source_name)
            if not source_settings or not source_settings.is_active:
                return {
                    "success": False,
                    "error": f"Lead source {source_name} not found or not active",
                }

            # Get the mapped stage for this platform
            mapped_stage = source_settings.get_mapped_stage(fub_stage_name)

            if not mapped_stage:
                return {
                    "success": False,
                    "message": f"No stage mapping found for FUB stage '{fub_stage_name}' on platform {source_name}",
                }

        except Exception as e:
            self.logger.error(f"Error in sync_single_source: {str(e)}")
            return {"success": False, "error": str(e)}

    def update_assignment_strategy(
        self, source_id: str, strategy: str, user_id: str = None
    ) -> LeadSourceSettings:
        """
        Update the assignment strategy for a lead source

        Args:
            source_id: The ID of the lead source
            strategy: The new assignment strategy value

        Returns:
            Updated LeadSourceSettings object or None if not found
        """
        # Verify ownership if user_id provided
        if user_id:
            existing = self.get_by_id(source_id)
            if not existing or existing.user_id != user_id:
                raise ValueError("Lead source not found or access denied")

        try:
            result = (
                self.supabase.table(self.table_name)
                .update({"assignment_strategy": strategy, "updated_at": "now()"})
                .eq("id", source_id)
                .execute()
            )

            if result.data and len(result.data) > 0:
                return LeadSourceSettings.from_dict(result.data[0])
            return None
        except Exception as e:
            self.logger.error(f"Error updating assignment strategy: {str(e)}")
            return None

    def update_assignment_rules(
        self, source_id: str, rules: Dict[str, Any]
    ) -> LeadSourceSettings:
        """
        Update the assignment rules configuration for a lead source

        Args:
            source_id: The ID of the lead source
            rules: The new assignment rules configuration

        Returns:
            Updated LeadSourceSettings object or None if not found
        """
        try:
            # Ensure rules is properly serialized as JSON
            if not isinstance(rules, str):
                rules_json = json.dumps(rules)
            else:
                rules_json = rules

            result = (
                self.supabase.table(self.table_name)
                .update({"assignment_rules": rules_json, "updated_at": "now()"})
                .eq("id", source_id)
                .execute()
            )

            if result.data and len(result.data) > 0:
                return LeadSourceSettings.from_dict(result.data[0])
            return None
        except Exception as e:
            self.logger.error(f"Error updating assignment rules: {str(e)}")
            return None

    def _sync_homelight_bulk(self, organization_id: str = None) -> Dict[str, Any]:
        """
        Sync multiple HomeLight leads in a single browser session

        Returns:
            Dict with bulk sync results
        """
        from app.referral_scrapers.homelight.homelight_service import HomelightService

        # Prepare lead data for bulk sync
        leads_data = []
        for bulk_item in self._bulk_sync_data:
            lead = bulk_item['lead']
            mapped_stage = bulk_item['mapped_stage']
            leads_data.append((lead, mapped_stage))

        # Get the same_status_note from the lead source settings
        same_status_note = None
        if hasattr(self, 'settings') and self.settings:
            same_status_note = self.settings.same_status_note

        # Create a service instance for bulk operations
        # Use the first lead as the template, but we'll override it for each lead
        template_lead = leads_data[0][0] if leads_data else None
        template_status = leads_data[0][1] if leads_data else None

        if not template_lead:
            return {
                "success": False,
                "message": "No leads to sync"
            }

        service = HomelightService(
            lead=template_lead,
            status=template_status,
            organization_id=organization_id,
            same_status_note=same_status_note
        )

        # Run bulk sync
        try:
            results = service.update_multiple_leads(leads_data)
            return {
                "success": True,
                "data": results
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Bulk sync failed: {str(e)}"
            }

    def sync_homelight_bulk_with_tracker(
        self,
        sync_id: str,
        source_name: str,
        leads: List,
        user_id: str,
        tracker,
        force_sync: bool = False
    ) -> None:
        """Sync HomeLight leads with progress tracking (runs in background)"""
        try:
            # Get the lead source settings
            source_settings = self.get_by_source_name(source_name)
            if not source_settings or not source_settings.is_active:
                tracker.complete_sync(sync_id, error=f"Lead source {source_name} not found or not active")
                return

            # Get minimum sync interval from settings (default 168 hours = 1 week) - THIS IS CHECKED BEFORE UPDATES
            min_sync_interval_hours = 168  # Default: 1 week (168 hours)
            if source_settings.metadata and isinstance(source_settings.metadata, dict):
                min_sync_interval_hours = source_settings.metadata.get("min_sync_interval_hours", 168)
            elif hasattr(source_settings, 'metadata') and isinstance(source_settings.metadata, str):
                try:
                    import json
                    metadata = json.loads(source_settings.metadata)
                    min_sync_interval_hours = metadata.get("min_sync_interval_hours", 168)
                except:
                    pass

            if force_sync:
                tracker.update_progress(
                    sync_id,
                    message=f"🔄 Force sync - bypassing {min_sync_interval_hours}h minimum interval"
                )
            else:
                tracker.update_progress(
                    sync_id,
                    message=f"Checking min sync interval: {min_sync_interval_hours}h"
                )

            # Filter leads to skip recently synced ones (unless force_sync is True)
            from datetime import datetime, timedelta, timezone
            now = datetime.now(timezone.utc)
            cutoff_time = now - timedelta(hours=min_sync_interval_hours)

            filtered_leads = []
            skipped_leads = []

            for lead in leads:
                # Define urgent statuses that should bypass interval check
                URGENT_STATUSES = [
                    'Hot Lead', 'Appointment Set', 'Appointment', 'Under Contract',
                    'Closing', 'Pre-Qualified', 'Active', 'Qualified Lead'
                ]

                # Check if lead has urgent status
                is_urgent = lead.status and any(
                    urgent.lower() in lead.status.lower()
                    for urgent in URGENT_STATUSES
                )

                # Check if lead was recently synced (skip this check if force_sync OR urgent)
                last_synced = None
                should_check_interval = not force_sync and not is_urgent

                if should_check_interval and lead.metadata and isinstance(lead.metadata, dict):
                    last_synced_str = lead.metadata.get("homelight_last_updated")
                    if last_synced_str:
                        try:
                            if isinstance(last_synced_str, str):
                                last_synced = datetime.fromisoformat(last_synced_str.replace('Z', '+00:00'))
                            elif isinstance(last_synced_str, datetime):
                                last_synced = last_synced_str
                            if last_synced.tzinfo is None:
                                last_synced = last_synced.replace(tzinfo=timezone.utc)
                        except Exception as e:
                            last_synced = None

                # Skip if synced recently (only if not force_sync AND not urgent)
                if should_check_interval and last_synced and last_synced > cutoff_time:
                    hours_since = (now - last_synced).total_seconds() / 3600
                    skipped_leads.append({
                        "lead_id": lead.id,
                        "fub_person_id": lead.fub_person_id,
                        "name": f"{lead.first_name} {lead.last_name}",
                        "reason": f"Synced {hours_since:.1f} hours ago (min interval: {min_sync_interval_hours}h)"
                    })
                    continue
                elif is_urgent and last_synced and last_synced > cutoff_time:
                    # Log that we're updating despite recent sync because it's urgent
                    tracker.update_progress(
                        sync_id,
                        message=f"Updating {lead.first_name} {lead.last_name} despite recent sync (urgent status: {lead.status})"
                    )

                # Extract lead type (buyer/seller) from tags for proper mapping
                lead_type = self._get_lead_type_from_tags(lead)

                # Get the mapped stage for this platform
                mapped_stage = source_settings.get_mapped_stage(lead.status, lead_type)
                if mapped_stage:
                    filtered_leads.append((lead, mapped_stage))

            tracker.update_progress(
                sync_id,
                skipped=len(skipped_leads),
                message=f"Filtered: {len(filtered_leads)} to process, {len(skipped_leads)} skipped"
            )

            if not filtered_leads:
                # Add a clear message about why no leads are being processed
                import time
                if skipped_leads and not force_sync:
                    tracker.update_progress(
                        sync_id,
                        message=f"⚠️ All {len(skipped_leads)} leads were synced within the last {min_sync_interval_hours} hours"
                    )
                    time.sleep(0.5)  # Give frontend time to receive the message
                    tracker.update_progress(
                        sync_id,
                        message=f"No updates needed - all leads are up to date. Use 'Force Sync' to override."
                    )
                elif not skipped_leads:
                    tracker.update_progress(
                        sync_id,
                        message=f"⚠️ No leads have mapped stages configured for {source_name}"
                    )
                else:
                    # Force sync was used but still no leads to process
                    tracker.update_progress(
                        sync_id,
                        message=f"⚠️ No leads have mapped stages configured for {source_name}"
                    )

                time.sleep(1)  # Give frontend time to display messages before completing

                tracker.complete_sync(
                    sync_id,
                    results={
                        "successful": 0,
                        "failed": 0,
                        "filter_summary": {
                            "total_leads": len(leads),
                            "skipped_recently_synced": len(skipped_leads) if not force_sync else 0,
                            "will_process": 0
                        },
                        "details": []
                    }
                )
                return
            
            # Get same_status_note
            same_status_note = None
            if hasattr(source_settings, 'same_status_note'):
                same_status_note = source_settings.same_status_note

            # Create service and run sync with tracker
            from app.referral_scrapers.homelight.homelight_service import HomelightService
            
            template_lead = filtered_leads[0][0]
            template_status = filtered_leads[0][1]

            service = HomelightService(
                lead=template_lead,
                status=template_status,
                organization_id=template_lead.organization_id,
                same_status_note=same_status_note,
                min_sync_interval_hours=min_sync_interval_hours
            )

            tracker.update_progress(sync_id, message="Starting HomeLight login...")
            bulk_results = service.update_multiple_leads_with_tracker(filtered_leads, sync_id, tracker)
            
            # Complete sync
            bulk_results["filter_summary"] = {
                "total_leads": len(leads),
                "skipped_recently_synced": len(skipped_leads),
                "will_process": len(filtered_leads)
            }
            if skipped_leads:
                bulk_results["skipped_leads"] = skipped_leads
            
            tracker.complete_sync(sync_id, results=bulk_results)
            
        except Exception as e:
            import traceback
            error_msg = str(e)
            self.logger.error(f"Error in HomeLight bulk sync with tracker: {error_msg}", exc_info=True)
            tracker.complete_sync(sync_id, error=error_msg)

    def sync_referralexchange_bulk_with_tracker(
        self,
        sync_id: str,
        source_name: str,
        leads: List,
        user_id: str,
        tracker,
        min_sync_interval_hours: int = 168,
        force_sync: bool = False
    ) -> None:
        """Sync ReferralExchange leads with progress tracking (bulk - login once)"""
        try:
            self.logger.info(f"[ReferralExchange Sync] Starting for source_name='{source_name}', {len(leads)} leads")
            tracker.update_progress(sync_id, message=f"Looking up source settings for '{source_name}'...")

            # Get the lead source settings
            source_settings = self.get_by_source_name(source_name)

            if source_settings:
                self.logger.info(f"[ReferralExchange Sync] Found source: is_active={source_settings.is_active}, has_mapping={bool(source_settings.fub_stage_mapping)}")
            else:
                self.logger.warning(f"[ReferralExchange Sync] No source found for name '{source_name}'")

            if not source_settings or not source_settings.is_active:
                error_msg = f"Lead source '{source_name}' not found or not active"
                self.logger.error(f"[ReferralExchange Sync] {error_msg}")
                tracker.complete_sync(sync_id, error=error_msg)
                return

            tracker.update_progress(
                sync_id,
                message=f"Preparing ReferralExchange bulk sync ({len(leads)} leads)"
            )

            # Filter leads by interval and urgency
            from datetime import datetime, timedelta, timezone
            now = datetime.now(timezone.utc)
            cutoff_time = now - timedelta(hours=min_sync_interval_hours)

            URGENT_STATUSES = [
                'Hot Lead', 'Appointment Set', 'Appointment', 'Under Contract',
                'Closing', 'Pre-Qualified', 'Active', 'Qualified Lead'
            ]

            # Build leads_data with mapped stages (filtering happens in the service)
            leads_data = []
            skipped_no_mapping = []
            skipped_recently_synced = []

            for lead in leads:
                # Check if urgent
                is_urgent = lead.status and any(
                    urgent.lower() in lead.status.lower()
                    for urgent in URGENT_STATUSES
                )

                # Check last sync time (unless force_sync or urgent)
                should_check_interval = not force_sync and not is_urgent
                if should_check_interval and lead.metadata and isinstance(lead.metadata, dict):
                    last_synced_str = lead.metadata.get("referralexchange_last_updated")
                    if last_synced_str:
                        try:
                            last_synced = datetime.fromisoformat(last_synced_str.replace('Z', '+00:00'))
                            if last_synced.tzinfo is None:
                                last_synced = last_synced.replace(tzinfo=timezone.utc)

                            if last_synced > cutoff_time:
                                hours_since = (now - last_synced).total_seconds() / 3600
                                skipped_recently_synced.append({
                                    "lead_id": lead.id,
                                    "fub_person_id": lead.fub_person_id,
                                    "name": f"{lead.first_name} {lead.last_name}",
                                    "reason": f"Synced {hours_since:.1f}h ago (min: {min_sync_interval_hours}h)"
                                })
                                continue
                        except:
                            pass

                mapped_stage = source_settings.get_mapped_stage(lead.status)
                if mapped_stage:
                    # Convert to list format for ReferralExchange
                    if isinstance(mapped_stage, str):
                        if "::" in mapped_stage:
                            main, sub = [part.strip() for part in mapped_stage.split("::", 1)]
                            status_for_service = [main, sub]
                        else:
                            status_for_service = [mapped_stage, ""]
                    elif isinstance(mapped_stage, (list, tuple)) and len(mapped_stage) >= 2:
                        status_for_service = [mapped_stage[0], mapped_stage[1]]
                    else:
                        status_for_service = [str(mapped_stage), ""]
                    leads_data.append((lead, status_for_service))
                else:
                    skipped_no_mapping.append({
                        "lead_id": lead.id,
                        "fub_person_id": lead.fub_person_id,
                        "name": f"{lead.first_name} {lead.last_name}",
                        "reason": f"No mapping for FUB status: {lead.status}"
                    })

            self.logger.info(f"[ReferralExchange Sync] Stage mapping check: {len(leads_data)} with mapping, {len(skipped_recently_synced)} recently synced, {len(skipped_no_mapping)} without mapping")
            print(f"!!!! SYNC FUNCTION EXECUTING V6 - {len(leads_data)} leads, {len(skipped_recently_synced)} skipped !!!!")
            tracker.update_progress(
                sync_id,
                skipped=len(skipped_recently_synced) + len(skipped_no_mapping),
                message=f"[SYNC_V6] {len(leads_data)} to process, {len(skipped_recently_synced)} recently synced, {len(skipped_no_mapping)} no mapping"
            )

            if not leads_data:
                self.logger.warning(f"[ReferralExchange Sync] No leads have stage mapping - completing with 0")
                if skipped_no_mapping and len(skipped_no_mapping) > 0:
                    sample = skipped_no_mapping[:3]
                    self.logger.warning(f"[ReferralExchange Sync] Sample skipped leads: {sample}")
                tracker.complete_sync(
                    sync_id,
                    results={
                        "successful": 0,
                        "failed": 0,
                        "skipped": 0,
                        "filter_summary": {
                            "total_leads": len(leads),
                            "skipped_no_mapping": len(skipped_no_mapping),
                            "will_process": 0
                        },
                        "details": []
                    }
                )
                return

            # Create service and run bulk sync
            from app.referral_scrapers.referral_exchange.referral_exchange_service import ReferralExchangeService

            template_lead = leads_data[0][0]
            template_status = leads_data[0][1]

            tracker.update_progress(sync_id, message=f"TEST_DEBUG_V3: Creating service for {template_lead.first_name} {template_lead.last_name}...")

            try:
                # Set min_sync_interval to 0 if force_sync to bypass filtering
                effective_min_interval = 0 if force_sync else min_sync_interval_hours
                service = ReferralExchangeService(
                    lead=template_lead,
                    status=template_status,
                    organization_id=template_lead.organization_id,
                    min_sync_interval_hours=effective_min_interval
                )
                driver_status = "initialized" if service.driver_service.driver else "NOT INITIALIZED"
                creds_status = "loaded" if service.email and service.password else "MISSING"
                tracker.update_progress(sync_id, message=f"Service created: driver={driver_status}, creds={creds_status}")
            except Exception as service_err:
                tracker.complete_sync(sync_id, error=f"Failed to create service: {str(service_err)}")
                return

            tracker.update_progress(sync_id, message="Starting ReferralExchange login...")

            # Run bulk update
            bulk_results = service.update_multiple_leads(leads_data)

            # Add filter summary
            bulk_results["filter_summary"] = {
                "total_leads": len(leads),
                "skipped_no_mapping": len(skipped_no_mapping),
                "will_process": len(leads_data)
            }
            if skipped_no_mapping:
                bulk_results["skipped_no_mapping"] = skipped_no_mapping

            tracker.complete_sync(sync_id, results=bulk_results)

        except Exception as e:
            import traceback
            error_msg = str(e)
            self.logger.error(f"Error in ReferralExchange bulk sync: {error_msg}", exc_info=True)
            traceback.print_exc()
            tracker.complete_sync(sync_id, error=error_msg)

    def sync_redfin_bulk_with_tracker(
        self,
        sync_id: str,
        source_name: str,
        leads: List,
        user_id: str,
        tracker,
        min_sync_interval_hours: int = 168,
        force_sync: bool = False
    ) -> None:
        """Sync Redfin leads with progress tracking (bulk - login once)"""
        try:
            # Get the lead source settings
            source_settings = self.get_by_source_name(source_name)
            if not source_settings or not source_settings.is_active:
                tracker.complete_sync(sync_id, error=f"Lead source {source_name} not found or not active")
                return

            tracker.update_progress(
                sync_id,
                message=f"Preparing Redfin bulk sync ({len(leads)} leads)"
            )

            # Filter leads by interval and urgency
            from datetime import datetime, timedelta, timezone
            now = datetime.now(timezone.utc)
            cutoff_time = now - timedelta(hours=min_sync_interval_hours)

            URGENT_STATUSES = [
                'Hot Lead', 'Appointment Set', 'Appointment', 'Under Contract',
                'Closing', 'Pre-Qualified', 'Active', 'Qualified Lead'
            ]

            # Build leads_data with mapped stages
            leads_data = []
            skipped_no_mapping = []
            skipped_recently_synced = []

            for lead in leads:
                # Check if urgent
                is_urgent = lead.status and any(
                    urgent.lower() in lead.status.lower()
                    for urgent in URGENT_STATUSES
                )

                # Check last sync time (unless force_sync or urgent)
                should_check_interval = not force_sync and not is_urgent
                if should_check_interval and lead.metadata and isinstance(lead.metadata, dict):
                    last_synced_str = lead.metadata.get("redfin_last_updated")
                    if last_synced_str:
                        try:
                            last_synced = datetime.fromisoformat(last_synced_str.replace('Z', '+00:00'))
                            if last_synced.tzinfo is None:
                                last_synced = last_synced.replace(tzinfo=timezone.utc)

                            if last_synced > cutoff_time:
                                hours_since = (now - last_synced).total_seconds() / 3600
                                skipped_recently_synced.append({
                                    "lead_id": lead.id,
                                    "fub_person_id": lead.fub_person_id,
                                    "name": f"{lead.first_name} {lead.last_name}",
                                    "reason": f"Synced {hours_since:.1f}h ago (min: {min_sync_interval_hours}h)"
                                })
                                continue
                        except:
                            pass

                mapped_stage = source_settings.get_mapped_stage(lead.status)
                if mapped_stage:
                    leads_data.append((lead, mapped_stage))
                else:
                    skipped_no_mapping.append({
                        "lead_id": lead.id,
                        "fub_person_id": lead.fub_person_id,
                        "name": f"{lead.first_name} {lead.last_name}",
                        "reason": f"No mapping for FUB status: {lead.status}"
                    })

            tracker.update_progress(
                sync_id,
                skipped=len(skipped_recently_synced) + len(skipped_no_mapping),
                message=f"Found {len(leads_data)} to process, {len(skipped_recently_synced)} recently synced, {len(skipped_no_mapping)} no mapping"
            )

            if not leads_data:
                tracker.complete_sync(
                    sync_id,
                    results={
                        "successful": 0,
                        "failed": 0,
                        "skipped": len(skipped_recently_synced) + len(skipped_no_mapping),
                        "filter_summary": {
                            "total_leads": len(leads),
                            "skipped_recently_synced": len(skipped_recently_synced),
                            "skipped_no_mapping": len(skipped_no_mapping),
                            "will_process": 0
                        },
                        "details": []
                    }
                )
                return

            # Create service and run bulk sync (login ONCE, process all leads)
            from app.referral_scrapers.redfin.redfin_service import RedfinService

            template_lead = leads_data[0][0]
            template_status = leads_data[0][1]

            service = RedfinService(
                lead=template_lead,
                status=template_status,
                organization_id=getattr(template_lead, 'organization_id', None),
                user_id=user_id,
                min_sync_interval_hours=min_sync_interval_hours
            )

            tracker.update_progress(sync_id, message="Starting Redfin login (one-time)...")

            # Run bulk update with tracker
            bulk_results = service.update_multiple_leads_with_tracker(
                leads_data, sync_id, tracker
            )

            # Add filter summary
            bulk_results["filter_summary"] = {
                "total_leads": len(leads),
                "skipped_no_mapping": len(skipped_no_mapping),
                "will_process": len(leads_data)
            }
            if skipped_no_mapping:
                bulk_results["skipped_no_mapping"] = skipped_no_mapping

            # Note: tracker.complete_sync is called inside update_multiple_leads_with_tracker

        except Exception as e:
            import traceback
            error_msg = str(e)
            self.logger.error(f"Error in Redfin bulk sync: {error_msg}", exc_info=True)
            traceback.print_exc()
            tracker.complete_sync(sync_id, error=error_msg)

    def sync_homelight_bulk(self, source_name: str, leads: List, user_id: str) -> Any:
        """
        Sync multiple HomeLight leads in a single browser session

        Args:
            source_name: The name of the source (should be 'HomeLight')
            leads: List of lead objects to sync
            user_id: The user ID for this sync

        Returns:
            Flask response with sync results
        """
        print(f"\n{'='*60}")
        print(f"STARTING HOMELIGHT BULK SYNC")
        print(f"{'='*60}")
        print(f"Total leads to sync: {len(leads)}")
        print(f"User ID: {user_id}")
        print(f"{'='*60}\n")
        
        self.logger.info(f"Bulk sync: Processing {len(leads)} HomeLight leads for user {user_id}")
        try:
            # Get the lead source settings
            source_settings = self.get_by_source_name(source_name)
            if not source_settings or not source_settings.is_active:
                return jsonify({
                    "success": False,
                    "error": f"Lead source {source_name} not found or not active"
                }), 404

            # Get minimum sync interval from settings (default 168 hours = 1 week)
            min_sync_interval_hours = 168  # Default: don't sync if updated in last 1 week
            if source_settings.metadata and isinstance(source_settings.metadata, dict):
                min_sync_interval_hours = source_settings.metadata.get("min_sync_interval_hours", 168)
            elif hasattr(source_settings, 'metadata') and isinstance(source_settings.metadata, str):
                try:
                    import json
                    metadata = json.loads(source_settings.metadata)
                    min_sync_interval_hours = metadata.get("min_sync_interval_hours", 168)
                except:
                    pass
            
            # Filter leads to skip recently synced ones
            from datetime import datetime, timedelta, timezone
            now = datetime.now(timezone.utc)
            cutoff_time = now - timedelta(hours=min_sync_interval_hours)
            
            filtered_leads = []
            skipped_leads = []
            
            for lead in leads:
                # Check if lead was recently synced
                last_synced = None
                if lead.metadata and isinstance(lead.metadata, dict):
                    last_synced_str = lead.metadata.get("homelight_last_updated")
                    if last_synced_str:
                        try:
                            if isinstance(last_synced_str, str):
                                last_synced = datetime.fromisoformat(last_synced_str.replace('Z', '+00:00'))
                            elif isinstance(last_synced_str, datetime):
                                last_synced = last_synced_str
                            if last_synced.tzinfo is None:
                                last_synced = last_synced.replace(tzinfo=timezone.utc)
                        except Exception as e:
                            print(f"[WARNING] Could not parse last_synced for lead {lead.fub_person_id}: {e}")
                            last_synced = None
                
                # Skip if synced recently
                if last_synced and last_synced > cutoff_time:
                    hours_since = (now - last_synced).total_seconds() / 3600
                    skipped_leads.append({
                        "lead_id": lead.id,
                        "fub_person_id": lead.fub_person_id,
                        "name": f"{lead.first_name} {lead.last_name}",
                        "reason": f"Synced {hours_since:.1f} hours ago (min interval: {min_sync_interval_hours}h)"
                    })
                    continue

                # Extract lead type (buyer/seller) from tags for proper mapping
                lead_type = self._get_lead_type_from_tags(lead)

                # Get the mapped stage for this platform
                mapped_stage = source_settings.get_mapped_stage(lead.status, lead_type)
                if mapped_stage:
                    filtered_leads.append((lead, mapped_stage))

            print(f"\n[FILTER] Total leads: {len(leads)}")
            print(f"[FILTER] Skipped (recently synced): {len(skipped_leads)}")
            print(f"[FILTER] Will process: {len(filtered_leads)}")
            if skipped_leads:
                print(f"[FILTER] Skipped leads (synced within last {min_sync_interval_hours}h):")
                for skipped in skipped_leads[:5]:  # Show first 5
                    print(f"  - {skipped['name']}: {skipped['reason']}")
                if len(skipped_leads) > 5:
                    print(f"  ... and {len(skipped_leads) - 5} more")
            
            # Prepare lead data for bulk sync
            leads_data = filtered_leads
            
            # Include skipped count in results
            results_summary = {
                "total_leads": len(leads),
                "skipped_recently_synced": len(skipped_leads),
                "will_process": len(leads_data)
            }

            if not leads_data:
                skip_message = f" (skipped {len(skipped_leads)} recently synced leads)" if skipped_leads else ""
                return jsonify({
                    "success": False,
                    "error": f"No leads found with valid stage mappings{skip_message}",
                    "skipped_count": len(skipped_leads),
                    "skipped_leads": skipped_leads[:10]  # Include first 10 skipped leads for reference
                }), 400

            # Get the same_status_note from the lead source settings
            same_status_note = None
            if hasattr(source_settings, 'same_status_note'):
                same_status_note = source_settings.same_status_note

            # Create HomeLight service and run bulk sync
            from app.referral_scrapers.homelight.homelight_service import HomelightService

            # Use first lead as template for service initialization
            template_lead = leads_data[0][0]
            template_status = leads_data[0][1]

            service = HomelightService(
                lead=template_lead,
                status=template_status,
                organization_id=template_lead.organization_id,
                same_status_note=same_status_note
            )

            # Run bulk sync - this will handle login once and process all leads
            print(f"Starting bulk sync with {len(leads_data)} leads...")
            self.logger.info(f"Starting bulk sync with {len(leads_data)} leads")
            bulk_results = service.update_multiple_leads(leads_data)
            
            # Add skipped leads info to results
            bulk_results["filter_summary"] = results_summary
            if skipped_leads:
                bulk_results["skipped_leads"] = skipped_leads
            
            print(f"\n{'='*60}")
            print(f"BULK SYNC COMPLETED")
            print(f"{'='*60}")
            print(f"Results: {bulk_results.get('successful', 0)} successful, {bulk_results.get('failed', 0)} failed")
            print(f"Skipped (recently synced): {len(skipped_leads)}")
            print(f"{'='*60}\n")
            self.logger.info(f"Bulk sync completed: {bulk_results.get('successful', 0)} successful, {bulk_results.get('failed', 0)} failed, {len(skipped_leads)} skipped")

            return jsonify({"success": True, "data": bulk_results}), 200

        except Exception as e:
            print(f"\n{'='*60}")
            print(f"BULK SYNC FAILED")
            print(f"{'='*60}")
            print(f"Error: {str(e)}")
            import traceback
            print(traceback.format_exc())
            print(f"{'='*60}\n")
            self.logger.error(f"Error in HomeLight bulk sync: {str(e)}", exc_info=True)
            return jsonify({"success": False, "error": str(e)}), 500

    def sync_agentpronto_bulk_with_tracker(
        self,
        sync_id: str,
        source_name: str,
        leads: List,
        user_id: str,
        tracker,
        min_sync_interval_hours: int = 168,
        force_sync: bool = False
    ) -> None:
        """Sync Agent Pronto leads with progress tracking (bulk - login once via magic link)"""
        try:
            # Get the lead source settings
            source_settings = self.get_by_source_name(source_name)
            if not source_settings or not source_settings.is_active:
                tracker.complete_sync(sync_id, error=f"Lead source {source_name} not found or not active")
                return

            tracker.update_progress(
                sync_id,
                message=f"Preparing Agent Pronto bulk sync ({len(leads)} leads)"
            )

            # Build leads_data with mapped stages
            leads_data = []
            skipped_no_mapping = []

            for lead in leads:
                mapped_stage = source_settings.get_mapped_stage(lead.status)
                if mapped_stage:
                    leads_data.append((lead, mapped_stage))
                else:
                    skipped_no_mapping.append({
                        "lead_id": lead.id,
                        "fub_person_id": lead.fub_person_id,
                        "name": f"{lead.first_name} {lead.last_name}",
                        "reason": f"No mapping for FUB status: {lead.status}"
                    })

            tracker.update_progress(
                sync_id,
                message=f"Found {len(leads_data)} leads to process, {len(skipped_no_mapping)} with no mapping"
            )

            if not leads_data:
                tracker.complete_sync(
                    sync_id,
                    results={
                        "successful": 0,
                        "failed": 0,
                        "skipped": 0,
                        "filter_summary": {
                            "total_leads": len(leads),
                            "skipped_no_mapping": len(skipped_no_mapping),
                            "will_process": 0
                        },
                        "details": []
                    }
                )
                return

            # Create service and run bulk sync
            from app.referral_scrapers.agent_pronto.agent_pronto_service import AgentProntoService

            template_lead = leads_data[0][0]
            template_status = leads_data[0][1]

            # Get same_status_note from source settings
            same_status_note = None
            if hasattr(source_settings, 'same_status_note'):
                same_status_note = source_settings.same_status_note

            service = AgentProntoService(
                lead=template_lead,
                status=template_status,
                organization_id=getattr(template_lead, 'organization_id', None),
                min_sync_interval_hours=min_sync_interval_hours,
                same_status_note=same_status_note,
                force_sync=force_sync
            )

            tracker.update_progress(sync_id, message="Starting Agent Pronto login (magic link)...")

            # Run bulk update
            bulk_results = service.update_multiple_leads(leads_data)

            # Add filter summary
            bulk_results["filter_summary"] = {
                "total_leads": len(leads),
                "skipped_no_mapping": len(skipped_no_mapping),
                "will_process": len(leads_data)
            }
            if skipped_no_mapping:
                bulk_results["skipped_no_mapping"] = skipped_no_mapping

            tracker.complete_sync(sync_id, results=bulk_results)

        except Exception as e:
            import traceback
            error_msg = str(e)
            self.logger.error(f"Error in Agent Pronto bulk sync: {error_msg}", exc_info=True)
            traceback.print_exc()
            tracker.complete_sync(sync_id, error=error_msg)

    def sync_myagentfinder_bulk_with_tracker(
        self,
        sync_id: str,
        source_name: str,
        leads: List,
        user_id: str,
        tracker,
        min_sync_interval_hours: int = 168,
        force_sync: bool = False
    ) -> None:
        """Sync My Agent Finder leads with progress tracking (bulk - login once)"""
        try:
            # Get the lead source settings
            source_settings = self.get_by_source_name(source_name)
            if not source_settings or not source_settings.is_active:
                tracker.complete_sync(sync_id, error=f"Lead source {source_name} not found or not active")
                return

            tracker.update_progress(
                sync_id,
                message=f"Preparing My Agent Finder bulk sync ({len(leads)} leads)"
            )

            # Get min_sync_interval from settings
            min_sync_interval_hours_setting = min_sync_interval_hours
            if source_settings.metadata and isinstance(source_settings.metadata, dict):
                min_sync_interval_hours_setting = source_settings.metadata.get("min_sync_interval_hours", min_sync_interval_hours)

            # PRE-FILTER: Check recently synced BEFORE opening browser (optimization)
            now = datetime.now(timezone.utc)
            cutoff_time = now - timedelta(hours=min_sync_interval_hours_setting)

            # Build leads_data with mapped stages AND filter out recently synced
            leads_data = []
            skipped_no_mapping = []
            skipped_recently_synced = []

            # Define urgent statuses
            URGENT_STATUSES = [
                'Hot Lead', 'Appointment Set', 'Appointment', 'Under Contract',
                'Closing', 'Pre-Qualified', 'Active', 'Qualified Lead'
            ]

            for lead in leads:
                lead_name = f"{lead.first_name} {lead.last_name}"

                # Check if urgent
                is_urgent = lead.status and any(
                    urgent.lower() in lead.status.lower()
                    for urgent in URGENT_STATUSES
                )

                # Check if lead was recently synced (skip if force_sync or urgent)
                should_check_interval = not force_sync and not is_urgent
                if should_check_interval and lead.metadata:
                    metadata = lead.metadata
                    if isinstance(metadata, str):
                        import json
                        try:
                            metadata = json.loads(metadata)
                        except:
                            metadata = {}

                    last_synced_str = metadata.get("myagentfinder_last_updated") if metadata else None
                    if last_synced_str:
                        try:
                            if isinstance(last_synced_str, str):
                                last_synced = datetime.fromisoformat(last_synced_str.replace('Z', '+00:00'))
                            else:
                                last_synced = last_synced_str
                            if last_synced.tzinfo is None:
                                last_synced = last_synced.replace(tzinfo=timezone.utc)

                            if last_synced > cutoff_time:
                                hours_since = (now - last_synced).total_seconds() / 3600
                                skipped_recently_synced.append({
                                    "lead_id": lead.id,
                                    "name": lead_name,
                                    "reason": f"Recently synced ({hours_since:.1f}h ago)"
                                })
                                continue  # Skip this lead - don't add to leads_data
                        except Exception as e:
                            self.logger.debug(f"Could not parse last_synced for {lead_name}: {e}")

                # Check for stage mapping
                mapped_stage = source_settings.get_mapped_stage(lead.status)
                if mapped_stage:
                    leads_data.append((lead, mapped_stage))
                else:
                    skipped_no_mapping.append({
                        "lead_id": lead.id,
                        "fub_person_id": lead.fub_person_id,
                        "name": lead_name,
                        "reason": f"No mapping for FUB status: {lead.status}"
                    })

            tracker.update_progress(
                sync_id,
                message=f"Pre-filtered: {len(leads_data)} to process, {len(skipped_recently_synced)} recently synced, {len(skipped_no_mapping)} no mapping"
            )

            # If all leads are already synced or have no mapping, complete without opening browser
            if not leads_data:
                # Build details for skipped leads
                skipped_details = []
                for skip in skipped_recently_synced:
                    skipped_details.append({
                        "name": skip["name"],
                        "status": "skipped",
                        "reason": "Recently synced"
                    })
                for skip in skipped_no_mapping:
                    skipped_details.append({
                        "name": skip["name"],
                        "status": "skipped",
                        "reason": skip["reason"]
                    })

                tracker.complete_sync(
                    sync_id,
                    results={
                        "successful": 0,
                        "failed": 0,
                        "skipped": len(skipped_recently_synced),
                        "filter_summary": {
                            "total_leads": len(leads),
                            "skipped_recently_synced": len(skipped_recently_synced),
                            "skipped_no_mapping": len(skipped_no_mapping),
                            "will_process": 0
                        },
                        "details": skipped_details
                    }
                )

                # Persist the "all skipped" result
                self.mark_sync_completed(source_settings.id, source_settings.sync_interval_days, sync_results={
                    "status": "completed",
                    "successful": 0,
                    "failed": 0,
                    "skipped": len(skipped_recently_synced),
                    "total_leads": len(leads),
                    "filter_summary": {
                        "skipped_recently_synced": len(skipped_recently_synced),
                        "skipped_no_mapping": len(skipped_no_mapping)
                    }
                })
                return

            # Create service and run bulk sync
            from app.referral_scrapers.my_agent_finder.my_agent_finder_service import MyAgentFinderService

            template_lead = leads_data[0][0]
            template_status = leads_data[0][1]

            # Get same_status_note from source settings
            same_status_note = None
            if hasattr(source_settings, 'same_status_note'):
                same_status_note = source_settings.same_status_note

            # Get nurture_days_offset from source settings metadata (default 180 = 6 months)
            nurture_days_offset = 180
            if source_settings and source_settings.metadata:
                metadata = source_settings.metadata
                if isinstance(metadata, str):
                    import json
                    metadata = json.loads(metadata)
                nurture_days_offset = metadata.get("nurture_days_offset", 180)

            service = MyAgentFinderService(
                lead=template_lead,
                status=template_status,
                organization_id=getattr(template_lead, 'organization_id', None),
                min_sync_interval_hours=min_sync_interval_hours,
                same_status_note=same_status_note,
                nurture_days_offset=nurture_days_offset
            )

            tracker.update_progress(sync_id, message="Starting My Agent Finder login...")

            # Run bulk update with tracker for cancellation support
            # Note: leads_data only contains leads that need processing (pre-filtered)
            bulk_results = service.update_multiple_leads(leads_data, tracker=tracker, sync_id=sync_id)

            # Add pre-filtered skipped leads to results
            bulk_results["skipped"] = bulk_results.get("skipped", 0) + len(skipped_recently_synced)

            # Add details for pre-filtered leads
            if "details" not in bulk_results:
                bulk_results["details"] = []
            for skip in skipped_recently_synced:
                bulk_results["details"].insert(0, {
                    "name": skip["name"],
                    "status": "skipped",
                    "reason": "Recently synced"
                })

            # Add filter summary
            bulk_results["filter_summary"] = {
                "total_leads": len(leads),
                "skipped_recently_synced": len(skipped_recently_synced),
                "skipped_no_mapping": len(skipped_no_mapping),
                "will_process": len(leads_data)
            }
            if skipped_no_mapping:
                bulk_results["skipped_no_mapping"] = skipped_no_mapping

            # Process overdue leads after bulk sync (if enabled in settings)
            process_overdue = True  # Default to enabled
            if source_settings and source_settings.metadata:
                metadata = source_settings.metadata
                if isinstance(metadata, str):
                    import json
                    metadata = json.loads(metadata)
                process_overdue = metadata.get("process_overdue_after_sync", True)

            if process_overdue:
                tracker.update_progress(sync_id, message="Processing overdue leads...")
                self.logger.info("Starting overdue leads processing after bulk sync...")
                try:
                    overdue_results = service.process_overdue_leads(max_leads=50)
                    bulk_results["overdue_processing"] = {
                        "successful": overdue_results.get("successful", 0),
                        "failed": overdue_results.get("failed", 0),
                    }
                    self.logger.info(f"Overdue processing: {overdue_results.get('successful', 0)} success, {overdue_results.get('failed', 0)} failed")
                except Exception as overdue_error:
                    self.logger.error(f"Error processing overdue leads: {overdue_error}")
                    bulk_results["overdue_processing"] = {"error": str(overdue_error)}

            tracker.complete_sync(sync_id, results=bulk_results)

            # Persist sync results to database
            bulk_results["status"] = "completed"
            self.mark_sync_completed(source_settings.id, source_settings.sync_interval_days, sync_results=bulk_results)

        except Exception as e:
            import traceback
            error_msg = str(e)
            self.logger.error(f"Error in My Agent Finder bulk sync: {error_msg}", exc_info=True)
            traceback.print_exc()
            tracker.complete_sync(sync_id, error=error_msg)

            # Persist error state to database
            if source_settings:
                self.mark_sync_completed(
                    source_settings.id,
                    source_settings.sync_interval_days,
                    sync_results={"status": "failed", "error": error_msg}
                )

    def sync_all_sources_bulk_with_tracker(
        self,
        sync_id: str,
        source_name: str,
        leads: List,
        user_id: str,
        tracker,
        force_sync: bool = False
    ) -> None:
        """Generic sync method for all lead sources with progress tracking"""
        try:
            # Initialize tracker status so update_progress/complete_sync calls work
            tracker.start_sync(
                sync_id=sync_id,
                source_id="",
                source_name=source_name,
                total_leads=len(leads),
                user_id=user_id
            )

            # Get the lead source settings
            source_settings = self.get_by_source_name(source_name)
            if not source_settings or not source_settings.is_active:
                tracker.complete_sync(sync_id, error=f"Lead source {source_name} not found or not active")
                return

            # Get minimum sync interval from settings (default 168 hours = 1 week)
            min_sync_interval_hours = 168  # Default: 1 week
            if source_settings.metadata and isinstance(source_settings.metadata, dict):
                min_sync_interval_hours = source_settings.metadata.get("min_sync_interval_hours", 168)
            elif hasattr(source_settings, 'metadata') and isinstance(source_settings.metadata, str):
                try:
                    import json
                    metadata = json.loads(source_settings.metadata)
                    min_sync_interval_hours = metadata.get("min_sync_interval_hours", 168)
                except:
                    pass

            # Skip minimum interval check if force_sync is True
            if force_sync:
                tracker.update_progress(
                    sync_id,
                    message=f"🔄 Force sync enabled - bypassing {min_sync_interval_hours}h minimum interval"
                )
            else:
                tracker.update_progress(
                    sync_id,
                    message=f"Checking min sync interval: {min_sync_interval_hours}h"
                )
            
            platform_lower = source_name.lower()

            # Handle HomeLight separately (it has its own optimized bulk sync)
            if platform_lower == "homelight":
                # Use existing HomeLight bulk sync (it does its own filtering)
                self.sync_homelight_bulk_with_tracker(
                    sync_id, source_name, leads, user_id, tracker, force_sync=force_sync
                )
                return

            # Handle ReferralExchange with bulk sync (login once, process all leads)
            if platform_lower in ["referralexchange", "referral exchange"]:
                self.sync_referralexchange_bulk_with_tracker(
                    sync_id, source_name, leads, user_id, tracker, min_sync_interval_hours, force_sync=force_sync
                )
                return

            # Handle Redfin with bulk sync (login once, process all leads)
            if platform_lower == "redfin":
                self.sync_redfin_bulk_with_tracker(
                    sync_id, source_name, leads, user_id, tracker, min_sync_interval_hours, force_sync=force_sync
                )
                return

            # Handle Agent Pronto with bulk sync (login once via magic link, process all leads)
            if platform_lower in ["agentpronto", "agent pronto"]:
                self.sync_agentpronto_bulk_with_tracker(
                    sync_id, source_name, leads, user_id, tracker, min_sync_interval_hours, force_sync=force_sync
                )
                return

            # Handle My Agent Finder with bulk sync (login once, process all leads)
            if platform_lower in ["myagentfinder", "my agent finder"]:
                self.sync_myagentfinder_bulk_with_tracker(
                    sync_id, source_name, leads, user_id, tracker, min_sync_interval_hours, force_sync=force_sync
                )
                return

            # Filter leads to skip recently synced ones (for other platforms)
            from datetime import datetime, timedelta, timezone
            now = datetime.now(timezone.utc)
            cutoff_time = now - timedelta(hours=min_sync_interval_hours)
            
            filtered_leads = []
            skipped_leads = []
            
            for lead in leads:
                # Check if lead was recently synced
                last_synced = None
                if lead.metadata and isinstance(lead.metadata, dict):
                    last_synced_str = lead.metadata.get(f"{platform_lower}_last_updated")
                    if last_synced_str:
                        try:
                            if isinstance(last_synced_str, str):
                                last_synced = datetime.fromisoformat(last_synced_str.replace('Z', '+00:00'))
                            elif isinstance(last_synced_str, datetime):
                                last_synced = last_synced_str
                            if last_synced.tzinfo is None:
                                last_synced = last_synced.replace(tzinfo=timezone.utc)
                        except Exception as e:
                            last_synced = None
                
                # Skip if synced recently
                if last_synced and last_synced > cutoff_time:
                    hours_since = (now - last_synced).total_seconds() / 3600
                    skipped_leads.append({
                        "lead_id": lead.id,
                        "fub_person_id": lead.fub_person_id,
                        "name": f"{lead.first_name} {lead.last_name}",
                        "reason": f"Synced {hours_since:.1f} hours ago (min interval: {min_sync_interval_hours}h)"
                    })
                    continue
                
                # Get the mapped stage for this platform
                mapped_stage = source_settings.get_mapped_stage(lead.status)
                if mapped_stage:
                    filtered_leads.append((lead, mapped_stage))
            
            tracker.update_progress(
                sync_id,
                skipped=len(skipped_leads),
                message=f"Filtered: {len(filtered_leads)} to process, {len(skipped_leads)} skipped"
            )
            
            if not filtered_leads:
                tracker.complete_sync(
                    sync_id,
                    results={
                        "successful": 0,
                        "failed": 0,
                        "filter_summary": {
                            "total_leads": len(leads),
                            "skipped_recently_synced": len(skipped_leads),
                            "will_process": 0
                        },
                        "details": []
                    }
                )
                return
            
            # For other platforms, process one by one
            from app.service.lead_service import LeadServiceSingleton
            lead_service = LeadServiceSingleton.get_instance()
            
            successful = 0
            failed = 0
            processed = 0
            details = []
            
            tracker.update_progress(sync_id, message=f"Starting sync for {source_name}...")
            
            # Process each lead
            for lead, mapped_stage in filtered_leads:
                if tracker.is_cancelled(sync_id):
                    tracker.update_progress(sync_id, message="Sync cancelled by user")
                    break
                
                lead_name = f"{lead.first_name} {lead.last_name}"
                tracker.update_progress(
                    sync_id,
                    current_lead=lead_name,
                    message=f"Processing {processed + 1}/{len(filtered_leads)}: {lead_name}"
                )
                
                try:
                    # Import the appropriate service based on platform
                    if platform_lower == "redfin":
                        from app.referral_scrapers.redfin.redfin_service import RedfinService
                        service = RedfinService(
                            lead=lead,
                            status=mapped_stage,
                            organization_id=getattr(lead, 'organization_id', None),
                            user_id=user_id
                        )
                        success = service.redfin_run()
                    elif platform_lower == "referralexchange":
                        from app.referral_scrapers.referral_exchange.referral_exchange_service import ReferralExchangeService
                        # ReferralExchange expects status as list
                        if isinstance(mapped_stage, str):
                            if "::" in mapped_stage:
                                main, sub = [part.strip() for part in mapped_stage.split("::", 1)]
                                status_for_service = [main, sub]
                            else:
                                status_for_service = [mapped_stage, ""]
                        elif isinstance(mapped_stage, (list, tuple)) and len(mapped_stage) >= 2:
                            status_for_service = [mapped_stage[0], mapped_stage[1]]
                        else:
                            status_for_service = [str(mapped_stage), ""]
                        
                        service = ReferralExchangeService(
                            lead=lead,
                            status=status_for_service,
                            organization_id=getattr(lead, 'organization_id', None)
                        )
                        success = service.referral_exchange_run()
                    elif platform_lower == "estately":
                        from app.referral_scrapers.estately.estately_service import EstatelyService
                        service = EstatelyService(
                            lead=lead,
                            organization_id=getattr(lead, 'organization_id', None)
                        )
                        # Estately service may not have a run method yet
                        success = False
                        tracker.update_progress(
                            sync_id,
                            message=f"Estately sync not yet implemented"
                        )
                    else:
                        tracker.update_progress(
                            sync_id,
                            message=f"Unknown platform: {source_name}"
                        )
                        success = False
                    
                    if success:
                        successful += 1
                        # Update lead metadata with last sync time
                        if not lead.metadata:
                            lead.metadata = {}
                        lead.metadata[f"{platform_lower}_last_updated"] = datetime.now(timezone.utc).isoformat()
                        lead_service.update(lead)
                        
                        details.append({
                            "lead_id": lead.id,
                            "fub_person_id": lead.fub_person_id,
                            "name": lead_name,
                            "status": "success",
                            "processing_time": None
                        })
                    else:
                        failed += 1
                        details.append({
                            "lead_id": lead.id,
                            "fub_person_id": lead.fub_person_id,
                            "name": lead_name,
                            "status": "failed",
                            "error": "Update failed"
                        })
                    
                    processed += 1
                    tracker.update_progress(
                        sync_id,
                        processed=processed,
                        successful=successful,
                        failed=failed
                    )
                    
                except Exception as e:
                    failed += 1
                    processed += 1
                    error_msg = str(e)
                    self.logger.error(f"Error syncing lead {lead_name}: {error_msg}")
                    details.append({
                        "lead_id": lead.id,
                        "fub_person_id": lead.fub_person_id,
                        "name": lead_name,
                        "status": "failed",
                        "error": error_msg
                    })
                    tracker.update_progress(
                        sync_id,
                        processed=processed,
                        failed=failed,
                        message=f"Error processing {lead_name}: {error_msg}"
                    )
            
            # Complete sync
            results = {
                "successful": successful,
                "failed": failed,
                "filter_summary": {
                    "total_leads": len(leads),
                    "skipped_recently_synced": len(skipped_leads),
                    "will_process": len(filtered_leads)
                },
                "details": details
            }
            if skipped_leads:
                results["skipped_leads"] = skipped_leads
            
            tracker.complete_sync(sync_id, results=results)

            # Persist sync results to database
            results["status"] = "completed"
            self.mark_sync_completed(source_settings.id, source_settings.sync_interval_days, sync_results=results)

        except Exception as e:
            import traceback
            error_msg = str(e)
            self.logger.error(f"Error in bulk sync for {source_name}: {error_msg}", exc_info=True)
            tracker.complete_sync(sync_id, error=error_msg)

            # Persist error state to database
            if source_settings:
                self.mark_sync_completed(
                    source_settings.id,
                    source_settings.sync_interval_days,
                    sync_results={"status": "failed", "error": error_msg}
                )


DependencyContainer.get_instance().register_lazy_initializer(
    "lead_source_settings_service", LeadSourceSettingsService
)
