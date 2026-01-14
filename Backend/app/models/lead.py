import json
from token import OP
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from app.models.base_model import BaseModel
from app.database.fub_api_client import FUBApiClient


class Lead(BaseModel):
    def __init__(self):
        self.id: str = None
        self.fub_id: str = None
        self.email: Optional[str] = None
        self.first_name: Optional[str] = None
        self.last_name: Optional[str] = None
        self.phone: Optional[str] = None
        self.source: Optional[str] = None
        self.status: Optional[str] = None
        self.tags: Optional[List[str]] = None
        self.price: float = None
        self.stage_id: Optional[str] = None
        self.fub_person_id: Optional[str] = None
        self.notes: Optional[str] = None
        self.created_at: Optional[datetime] = None
        self.updated_at: Optional[datetime] = None
        self.fub_stage_id: Optional[str] = None
        self.fub_stage_name: Optional[str] = None
        self.organization_id: Optional[str] = None
        self.user_id: Optional[str] = None
        self.metadata: Dict[str, Any] = {}

    @classmethod
    def from_fub(cls, data: Dict[str, Any]) -> "Lead":
        lead = cls()
        lead.id = str(uuid.uuid4())

        # Map basic fields
        lead.first_name = data.get("firstName", "")
        lead.last_name = data.get("lastName", "")
        lead.source = data.get("source")
        lead.status = data.get("stage")
        lead.stage_id = data.get("stageId")
        lead.tags = data.get("tags")
        lead.price = data.get("price")
        lead.fub_person_id = str(data.get("id")) if data.get("id") else None
        lead.created_at = cls._parse_datetime(data.get("created"))
        lead.updated_at = cls._parse_datetime(data.get("updated"))

        # Extract primary email
        if data.get("emails") and len(data["emails"]) > 0:
            for email in data["emails"]:
                if email.get("isPrimary") == 1:
                    lead.email = email.get("value")
                    break
            if not lead.email and data["emails"]:
                lead.email = data["emails"][0].get("value")

        # Extract primary phone
        if data.get("phones") and len(data["phones"]) > 0:
            for phone in data["phones"]:
                if phone.get("isPrimary") == 1:
                    lead.phone = phone.get("value")
                    break
            if not lead.phone and data["phones"]:
                lead.phone = data["phones"][0].get("value")

        return lead

    @classmethod
    def from_fub_to_redis(cls, data: Dict[str, Any]) -> "Lead":
        """
        Create a Lead object from Redis data that was originally from FUB
        This handles Redis-specific data format conversions
        """
        lead = cls()

        for key, value in data.items():
            if hasattr(lead, key):
                # Handle special cases for Redis data
                if key == "tags" and isinstance(value, str):
                    try:
                        lead.tags = json.loads(value)
                    except json.JSONDecodeError:
                        lead.tags = []
                elif key in ["created_at", "updated_at"] and isinstance(value, str):
                    try:
                        setattr(lead, key, datetime.fromisoformat(value))
                    except ValueError:
                        setattr(lead, key, None)
                else:
                    setattr(lead, key, value)

        return lead

    def to_fub_dict(self) -> Dict[str, Any]:
        data = {
            "firstName": self.first_name or "",
            "lastName": self.last_name or "",
            "stage": self.status or "",
            "source": self.source or "",
            "stageId": self.stage_id or "",
            "price": self.price or 0,
            "tags": self.tags or [],
            "id": self.fub_person_id,
        }

        # Add email if available
        if self.email:
            data["emails"] = [{"value": self.email, "type": "home", "isPrimary": 1}]

        # Add phone if available
        if self.phone:
            data["phones"] = [{"value": self.phone, "type": "mobile", "isPrimary": 1}]

        return data

    @property
    def full_name(self) -> str:
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)

        if parts:
            return " ".join(parts)

        return "Unknown"

    @staticmethod
    def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
        if not dt_str:
            return None

        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    def display_data(self) -> None:
        """Display all fields and their values for debugging purposes."""
        print("\n=== Lead Data ===")
        print(f"ID: {self.id}")
        print(f"FUB ID: {self.fub_id}")
        print(f"FUB Parent ID: {self.fub_person_id}")
        print(f"First Name: {self.first_name}")
        print(f"Last Name: {self.last_name}")
        print(f"Full Name: {self.full_name}")
        print(f"Email: {self.email}")
        print(f"Phone: {self.phone}")
        print(f"Source: {self.source}")
        print(f"Stage ID: {self.stage_id}")
        print(f"Status: {self.status}")
        print(f"Notes: {self.notes}")
        print(f"Price: {self.price}")
        print(f"Created At: {self.created_at}")
        print(f"Updated At: {self.updated_at}")
        print("===============\n")

    def to_dict(self) -> Dict[str, Any]:
        data = vars(self).copy()

        # Handle datetime objects
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif key == "tags" and value is None:  # Ensure tags is never None
                data[key] = []

        return data


class LeadAssignment(BaseModel):
    def __init__(self):
        self.id: str = None
        self.lead_id: str = None
        self.user_id: str = None
        self.assignment_type: str = None
        self.assigned_at: Optional[datetime] = None

    @classmethod
    def from_fub(cls, data: Dict[str, Any]) -> "LeadAssignment":
        assignment = cls()
        assignment.id = str(uuid.uuid4())
        assignment.lead_id = data.get("lead_id", "")
        assignment.user_id = data.get("id", "")


class LeadUpdate(BaseModel):
    def __init__(self):
        self.id: str = None
        self.lead_id: str = None
        self.user_id: str = None
        self.notes: Optional[str] = None
        self.created_at: Optional[datetime] = None


class LeadNote(BaseModel):
    def __init__(self):
        self.id: str = None
        self.lead_id: str = None
        self.note_id: str = None
        self.created_by_id: str = None
        self.updated_by_id: str = None
        self.created_by: str = None  # Actual Name of Agent who made the note
        self.updated_by: str = None  # Actual Name of Agent who updated the note
        self.subject: str = None
        self.body: str = None
        self.replies: Optional[Dict[str, Any]] = None
        self.metadata: Dict[str, Any] = None
        self.created_at: Optional[datetime] = None
        self.updated_at: Optional[datetime] = None

    def to_json(self) -> Dict[str, Any]:
        data = vars(self).copy()

        # Handle datetime objects
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, dict):
                data[key] = json.dumps(value)

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LeadNote":
        note = cls()
        for key, value in data.items():
            if hasattr(note, key):
                if key.endswith("_at") and value:
                    try:
                        if isinstance(value, str):
                            setattr(
                                note,
                                key,
                                datetime.fromisoformat(value.replace("Z", "+00:00")),
                            )
                        else:
                            setattr(note, key, value)
                    except (ValueError, TypeError):
                        setattr(note, key, value)

                elif key == "metadata" and isinstance(value, str):
                    try:
                        setattr(note, key, json.loads(value))
                    except json.JSONDecodeError:
                        setattr(note, key, {})

                else:
                    setattr(note, key, value)

        return note

    @staticmethod
    def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
        if not dt_str:
            return None

        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    @classmethod
    def from_fub(cls, data: Dict[str, Any]) -> "LeadNote":
        note = cls()
        note.id = str(uuid.uuid4())

        # Map basic fields - ensure all IDs are strings
        note.note_id = str(data.get("id")) if data.get("id") is not None else None
        note.body = data.get("body", "")
        note.subject = data.get("subject", "")

        # Convert IDs to strings
        note.created_by_id = (
            str(data.get("createdById"))
            if data.get("createdById") is not None
            else None
        )
        note.updated_by_id = (
            str(data.get("updatedById"))
            if data.get("updatedById") is not None
            else None
        )
        note.created_by = data.get("createdBy", "")
        note.updated_by = data.get("updatedBy", "")
        note.lead_id = (
            str(data.get("personId")) if data.get("personId") is not None else None
        )

        # Parse dates
        note.created_at = cls._parse_datetime(data.get("created"))
        note.updated_at = cls._parse_datetime(data.get("updated"))

        # Initialize metadata
        note.metadata = {"source": "fub_api", "raw_data": data}

        return note


class LeadSourceSettings(BaseModel):
    def __init__(self):
        self.id: str = None
        self.source_name: str = None
        self.assignment_strategy: str = None
        self.referral_fee_percent: Optional[float] = None
        self.active = Optional[bool] = None
        self.metadata: Optional[Dict[str, Any]] = None
        self.assignment_rules: Optional[Dict[str, Any]] = None
        self.created_at: Optional[datetime] = None
        self.updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()

        for field in ["metadata", "assignment_rules"]:
            value = getattr(self, field, None)
            if isinstance(value, dict):
                result[field] = json.dumps(value)

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LeadSourceSettings":
        instance = super().from_dict(cls, data)

        # Parse JSON fields
        if instance:
            for field in ["metadata", "assignment_rules"]:
                value = getattr(instance, field, None)
                if isinstance(value, str):
                    try:
                        setattr(instance, field, json.loads(value))
                    except json.JSONDecodeError:
                        pass

        return instance
