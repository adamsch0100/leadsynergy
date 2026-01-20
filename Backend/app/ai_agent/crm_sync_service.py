"""
CRM Custom Field Sync Service.

Syncs AI-extracted qualification data to Follow Up Boss custom fields.

This enables:
- Automatic population of CRM fields based on AI conversations
- Two-way sync (read FUB fields to inform AI, write AI data to FUB)
- Customizable field mappings per organization
- Lead score sync to FUB custom fields

Default AI fields to sync:
- timeline: When the lead plans to buy/sell
- budget: Budget/price range
- location_preference: Preferred areas/neighborhoods
- motivation: Reason for moving
- pre_approved: Pre-approval status
- property_type: Type of property interested in
- lead_score: AI-calculated lead score
- last_ai_contact: Timestamp of last AI interaction
- ai_conversation_state: Current state (qualifying, scheduling, etc.)
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class FieldMapping:
    """Mapping between AI field and FUB custom field."""
    ai_field: str
    fub_field_id: str
    fub_field_name: str = ""
    field_type: str = "text"  # text, number, date, dropdown
    is_enabled: bool = True
    transform_func: Optional[str] = None  # Optional transform function name


# Default field mappings (can be customized per org)
DEFAULT_FIELD_MAPPINGS = {
    "timeline": FieldMapping(
        ai_field="timeline",
        fub_field_id="ai_timeline",
        fub_field_name="AI - Timeline",
        field_type="dropdown",
    ),
    "budget": FieldMapping(
        ai_field="budget",
        fub_field_id="ai_budget",
        fub_field_name="AI - Budget",
        field_type="text",
    ),
    "location_preference": FieldMapping(
        ai_field="location_preference",
        fub_field_id="ai_location",
        fub_field_name="AI - Preferred Location",
        field_type="text",
    ),
    "motivation": FieldMapping(
        ai_field="motivation",
        fub_field_id="ai_motivation",
        fub_field_name="AI - Motivation",
        field_type="dropdown",
    ),
    "pre_approved": FieldMapping(
        ai_field="pre_approved",
        fub_field_id="ai_preapproval",
        fub_field_name="AI - Pre-Approval Status",
        field_type="dropdown",
    ),
    "property_type": FieldMapping(
        ai_field="property_type",
        fub_field_id="ai_property_type",
        fub_field_name="AI - Property Type",
        field_type="dropdown",
    ),
    "lead_score": FieldMapping(
        ai_field="lead_score",
        fub_field_id="ai_lead_score",
        fub_field_name="AI - Lead Score",
        field_type="number",
    ),
    "last_ai_contact": FieldMapping(
        ai_field="last_ai_contact",
        fub_field_id="ai_last_contact",
        fub_field_name="AI - Last Contact",
        field_type="date",
    ),
    "conversation_state": FieldMapping(
        ai_field="conversation_state",
        fub_field_id="ai_conv_state",
        fub_field_name="AI - Conversation State",
        field_type="dropdown",
    ),
}


class CRMSyncService:
    """
    Service for syncing AI data with Follow Up Boss custom fields.

    Usage:
        service = CRMSyncService(supabase_client, fub_client)

        # Sync qualification data to FUB
        await service.sync_to_fub(
            fub_person_id=12345,
            qualification_data={"timeline": "30_days", "budget": "$500k"},
            lead_score=75,
        )

        # Get field mappings for an org
        mappings = await service.get_field_mappings(organization_id)
    """

    def __init__(self, supabase_client=None, fub_client=None):
        self.supabase = supabase_client
        self.fub = fub_client
        self._mapping_cache: Dict[str, List[FieldMapping]] = {}

    async def get_field_mappings(
        self,
        organization_id: Optional[str] = None,
    ) -> Dict[str, FieldMapping]:
        """
        Get field mappings for an organization.

        Args:
            organization_id: Organization ID (uses defaults if None)

        Returns:
            Dict of ai_field -> FieldMapping
        """
        # Check cache
        cache_key = organization_id or "default"
        if cache_key in self._mapping_cache:
            return self._mapping_cache[cache_key]

        mappings = dict(DEFAULT_FIELD_MAPPINGS)

        # Try to load custom mappings from database
        if self.supabase and organization_id:
            try:
                result = self.supabase.table("ai_custom_field_mappings").select(
                    "*"
                ).eq("organization_id", organization_id).eq(
                    "is_enabled", True
                ).execute()

                if result.data:
                    for row in result.data:
                        ai_field = row.get("ai_field")
                        if ai_field:
                            mappings[ai_field] = FieldMapping(
                                ai_field=ai_field,
                                fub_field_id=row.get("fub_field_id", ""),
                                fub_field_name=row.get("fub_field_name", ""),
                                field_type=row.get("field_type", "text"),
                                is_enabled=row.get("is_enabled", True),
                            )

            except Exception as e:
                logger.error(f"Error loading custom field mappings: {e}")

        self._mapping_cache[cache_key] = mappings
        return mappings

    async def sync_to_fub(
        self,
        fub_person_id: int,
        qualification_data: Dict[str, Any],
        lead_score: Optional[int] = None,
        conversation_state: Optional[str] = None,
        organization_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Sync AI qualification data to FUB custom fields.

        Args:
            fub_person_id: FUB person ID
            qualification_data: Dict of qualification data from AI
            lead_score: Optional lead score to sync
            conversation_state: Optional conversation state
            organization_id: Organization ID for custom mappings
            api_key: Optional FUB API key override

        Returns:
            Dict with sync results
        """
        if not self.fub:
            logger.warning("No FUB client - cannot sync to CRM")
            return {"success": False, "error": "No FUB client configured"}

        try:
            # Get field mappings
            mappings = await self.get_field_mappings(organization_id)

            # Build custom fields update
            custom_fields = {}

            # Sync qualification data
            for ai_field, value in qualification_data.items():
                if ai_field in mappings and mappings[ai_field].is_enabled:
                    mapping = mappings[ai_field]
                    transformed_value = self._transform_value(
                        value,
                        mapping.field_type,
                    )
                    custom_fields[mapping.fub_field_id] = transformed_value

            # Sync lead score
            if lead_score is not None and "lead_score" in mappings:
                mapping = mappings["lead_score"]
                if mapping.is_enabled:
                    custom_fields[mapping.fub_field_id] = lead_score

            # Sync conversation state
            if conversation_state and "conversation_state" in mappings:
                mapping = mappings["conversation_state"]
                if mapping.is_enabled:
                    custom_fields[mapping.fub_field_id] = conversation_state

            # Sync last AI contact timestamp
            if "last_ai_contact" in mappings:
                mapping = mappings["last_ai_contact"]
                if mapping.is_enabled:
                    custom_fields[mapping.fub_field_id] = datetime.utcnow().isoformat()

            if not custom_fields:
                logger.info(f"No fields to sync for person {fub_person_id}")
                return {"success": True, "synced_fields": 0}

            # Update FUB person with custom fields
            try:
                update_result = self.fub.update_person(
                    person_id=fub_person_id,
                    data={"customFields": custom_fields},
                )

                if update_result:
                    logger.info(
                        f"Synced {len(custom_fields)} fields to FUB person {fub_person_id}"
                    )
                    return {
                        "success": True,
                        "synced_fields": len(custom_fields),
                        "fields": list(custom_fields.keys()),
                    }
                else:
                    logger.warning(f"FUB update returned empty for person {fub_person_id}")
                    return {"success": False, "error": "FUB update returned empty"}

            except Exception as fub_error:
                error_msg = str(fub_error)
                # 400 errors typically mean custom fields don't exist in FUB
                if "400" in error_msg:
                    logger.warning(
                        f"FUB custom fields not configured for person {fub_person_id}. "
                        f"Tried to sync fields: {list(custom_fields.keys())}. "
                        f"Data is still saved in ai_conversations table."
                    )
                    return {
                        "success": False,
                        "error": "FUB custom fields not configured - create them in FUB first",
                        "fields_attempted": list(custom_fields.keys()),
                    }
                raise  # Re-raise other errors

        except Exception as e:
            logger.error(f"Error syncing to FUB: {e}")
            return {"success": False, "error": str(e)}

    async def sync_from_fub(
        self,
        fub_person_id: int,
        organization_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Read FUB custom fields to inform AI context.

        Args:
            fub_person_id: FUB person ID
            organization_id: Organization ID for custom mappings

        Returns:
            Dict of AI field -> value from FUB
        """
        if not self.fub:
            return {}

        try:
            # Get person data from FUB
            person = self.fub.get_person(fub_person_id)
            if not person:
                return {}

            # Get field mappings
            mappings = await self.get_field_mappings(organization_id)

            # Extract custom fields
            custom_fields = person.get("customFields", {})
            ai_data = {}

            for ai_field, mapping in mappings.items():
                if mapping.fub_field_id in custom_fields:
                    value = custom_fields[mapping.fub_field_id]
                    if value:
                        ai_data[ai_field] = value

            return ai_data

        except Exception as e:
            logger.error(f"Error reading from FUB: {e}", exc_info=True)
            return {}

    def _transform_value(
        self,
        value: Any,
        field_type: str,
    ) -> Any:
        """Transform value for FUB field type."""
        if value is None:
            return None

        if field_type == "number":
            try:
                # Handle budget strings like "$500k" or "500000"
                if isinstance(value, str):
                    cleaned = value.replace("$", "").replace(",", "").lower()
                    if "k" in cleaned:
                        cleaned = cleaned.replace("k", "")
                        return int(float(cleaned) * 1000)
                    elif "m" in cleaned:
                        cleaned = cleaned.replace("m", "")
                        return int(float(cleaned) * 1000000)
                    return int(float(cleaned))
                return int(value)
            except (ValueError, TypeError):
                return None

        if field_type == "date":
            if isinstance(value, datetime):
                return value.isoformat()
            return str(value)

        # Default: convert to string
        return str(value)

    async def ensure_custom_fields_exist(
        self,
        organization_id: str,
    ) -> Dict[str, Any]:
        """
        Ensure all required custom fields exist in FUB.

        Note: FUB custom fields are typically created via the UI or API.
        This method checks which fields exist and which need to be created.

        Args:
            organization_id: Organization ID

        Returns:
            Dict with existing and missing fields
        """
        if not self.fub:
            return {"error": "No FUB client"}

        try:
            # Get existing custom fields from FUB
            existing_fields = self.fub.get_custom_fields()
            existing_ids = set(f.get("id") for f in existing_fields)

            # Get our required mappings
            mappings = await self.get_field_mappings(organization_id)

            existing = []
            missing = []

            for ai_field, mapping in mappings.items():
                if mapping.fub_field_id in existing_ids:
                    existing.append(ai_field)
                else:
                    missing.append({
                        "ai_field": ai_field,
                        "fub_field_id": mapping.fub_field_id,
                        "fub_field_name": mapping.fub_field_name,
                        "field_type": mapping.field_type,
                    })

            return {
                "existing": existing,
                "missing": missing,
                "total_required": len(mappings),
            }

        except Exception as e:
            logger.error(f"Error checking custom fields: {e}", exc_info=True)
            return {"error": str(e)}

    async def save_field_mapping(
        self,
        organization_id: str,
        ai_field: str,
        fub_field_id: str,
        fub_field_name: str = "",
        field_type: str = "text",
    ) -> bool:
        """
        Save a custom field mapping for an organization.

        Args:
            organization_id: Organization ID
            ai_field: AI field name
            fub_field_id: FUB custom field ID
            fub_field_name: Display name
            field_type: Field type

        Returns:
            True if saved successfully
        """
        if not self.supabase:
            return False

        try:
            data = {
                "organization_id": organization_id,
                "ai_field": ai_field,
                "fub_field_id": fub_field_id,
                "fub_field_name": fub_field_name,
                "field_type": field_type,
                "is_enabled": True,
                "updated_at": datetime.utcnow().isoformat(),
            }

            result = self.supabase.table("ai_custom_field_mappings").upsert(
                data,
                on_conflict="organization_id,ai_field"
            ).execute()

            # Invalidate cache
            cache_key = organization_id
            if cache_key in self._mapping_cache:
                del self._mapping_cache[cache_key]

            return bool(result.data)

        except Exception as e:
            logger.error(f"Error saving field mapping: {e}", exc_info=True)
            return False


# Singleton instance
_crm_sync_service: Optional[CRMSyncService] = None


def get_crm_sync_service(
    supabase_client=None,
    fub_client=None,
) -> CRMSyncService:
    """Get the global CRM sync service instance."""
    global _crm_sync_service

    if _crm_sync_service is None:
        _crm_sync_service = CRMSyncService(supabase_client, fub_client)
    else:
        if supabase_client and not _crm_sync_service.supabase:
            _crm_sync_service.supabase = supabase_client
        if fub_client and not _crm_sync_service.fub:
            _crm_sync_service.fub = fub_client

    return _crm_sync_service
