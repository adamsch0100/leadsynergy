"""
FUB Team Provisioning Service - Auto-provisions team members when broker sets up FUB API key.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.database.supabase_client import SupabaseClientSingleton
from app.database.fub_api_client import FUBApiClient
from app.models.user import User, UserProfile
from app.models.organization import Organization

logger = logging.getLogger(__name__)


class FUBTeamProvisioningService:
    """
    Service to auto-provision FUB team members when a broker sets up their API key.

    This creates user records for all team members in the FUB account and links
    them to the broker's organization.
    """

    def __init__(self):
        self.supabase = SupabaseClientSingleton.get_instance()

    def provision_team_from_fub(
        self,
        broker_user_id: str,
        organization_id: str,
        fub_api_key: str
    ) -> Dict[str, Any]:
        """
        Fetch all team members from FUB and create user records.

        Args:
            broker_user_id: The broker's user ID (who provided the API key)
            organization_id: The organization to add team members to
            fub_api_key: The FUB API key to use for fetching users

        Returns:
            Dict with provisioning results:
            {
                "success": bool,
                "provisioned_count": int,
                "skipped_count": int,
                "failed_count": int,
                "details": List[Dict]  # Details for each user processed
            }
        """
        try:
            # Create FUB API client
            fub_client = FUBApiClient(api_key=fub_api_key)

            # Fetch all users from FUB
            fub_users = fub_client.get_users()

            if not fub_users:
                logger.info(f"No FUB users found for broker {broker_user_id}")
                return {
                    "success": True,
                    "provisioned_count": 0,
                    "skipped_count": 0,
                    "failed_count": 0,
                    "details": [],
                    "message": "No team members found in Follow Up Boss"
                }

            results = {
                "success": True,
                "provisioned_count": 0,
                "skipped_count": 0,
                "failed_count": 0,
                "details": []
            }

            for fub_user in fub_users:
                result = self._provision_single_user(
                    fub_user=fub_user,
                    broker_user_id=broker_user_id,
                    organization_id=organization_id
                )

                results["details"].append(result)

                if result["status"] == "provisioned":
                    results["provisioned_count"] += 1
                elif result["status"] == "skipped":
                    results["skipped_count"] += 1
                else:
                    results["failed_count"] += 1

            logger.info(
                f"Team provisioning complete for org {organization_id}: "
                f"{results['provisioned_count']} provisioned, "
                f"{results['skipped_count']} skipped, "
                f"{results['failed_count']} failed"
            )

            return results

        except Exception as e:
            logger.error(f"Error provisioning team from FUB: {e}")
            return {
                "success": False,
                "error": str(e),
                "provisioned_count": 0,
                "skipped_count": 0,
                "failed_count": 0,
                "details": []
            }

    def _provision_single_user(
        self,
        fub_user: Dict[str, Any],
        broker_user_id: str,
        organization_id: str
    ) -> Dict[str, Any]:
        """
        Provision a single FUB user.

        Args:
            fub_user: FUB user data (id, name, email, role, etc.)
            broker_user_id: The broker's user ID
            organization_id: The organization ID

        Returns:
            Dict with provisioning result for this user
        """
        fub_user_id = fub_user.get("id")
        email = fub_user.get("email", "").lower().strip()
        name = fub_user.get("name", "")
        fub_role = fub_user.get("role", "agent")

        if not email:
            return {
                "fub_user_id": fub_user_id,
                "email": None,
                "status": "failed",
                "reason": "No email address"
            }

        try:
            # Check if user with this email already exists
            existing = self.supabase.table('users').select('id, fub_user_id').eq(
                'email', email
            ).maybe_single().execute()

            if existing.data:
                # User exists - just update the fub_user_id if not set
                existing_user_id = existing.data['id']
                existing_fub_id = existing.data.get('fub_user_id')

                if not existing_fub_id:
                    self.supabase.table('users').update({
                        'fub_user_id': fub_user_id
                    }).eq('id', existing_user_id).execute()

                # Make sure they're in the organization
                self._ensure_organization_membership(existing_user_id, organization_id, fub_role)

                return {
                    "fub_user_id": fub_user_id,
                    "email": email,
                    "name": name,
                    "status": "skipped",
                    "reason": "User already exists",
                    "user_id": existing_user_id
                }

            # Create new user
            user_id = str(uuid.uuid4())

            # Parse name into first/last
            first_name, last_name = self._parse_name(name)

            # Map FUB role to our role
            role = self._map_fub_role(fub_role)

            # Create user record
            now = datetime.utcnow().isoformat()
            user_data = {
                'id': user_id,
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'full_name': name,
                'role': role,
                'fub_user_id': fub_user_id,
                'provisioned_by_user_id': broker_user_id,
                'created_at': now,
                'updated_at': now,
                'email_notifications': True,
                'sms_notifications': False
            }

            self.supabase.table('users').insert(user_data).execute()

            # Create user profile
            profile_data = {
                'id': user_id,
                'email': email,
                'full_name': name,
                'role': role,
                'onboarding_completed': True,  # Provisioned users skip onboarding
                'onboarding_step': 'complete',
                'created_at': now,
                'updated_at': now
            }

            try:
                self.supabase.table('user_profiles').insert(profile_data).execute()
            except Exception as profile_err:
                logger.warning(f"Could not create profile for {email}: {profile_err}")

            # Add to organization
            self._ensure_organization_membership(user_id, organization_id, fub_role)

            logger.info(f"Provisioned user {email} (FUB ID: {fub_user_id})")

            return {
                "fub_user_id": fub_user_id,
                "email": email,
                "name": name,
                "status": "provisioned",
                "user_id": user_id,
                "role": role
            }

        except Exception as e:
            logger.error(f"Error provisioning user {email}: {e}")
            return {
                "fub_user_id": fub_user_id,
                "email": email,
                "name": name,
                "status": "failed",
                "reason": str(e)
            }

    def _ensure_organization_membership(
        self,
        user_id: str,
        organization_id: str,
        fub_role: str
    ):
        """Ensure user is a member of the organization."""
        try:
            # Check if already a member
            existing = self.supabase.table('organization_users').select('id').eq(
                'user_id', user_id
            ).eq(
                'organization_id', organization_id
            ).maybe_single().execute()

            if existing.data:
                return  # Already a member

            # Add to organization
            role = self._map_fub_role(fub_role)
            now = datetime.utcnow().isoformat()

            self.supabase.table('organization_users').insert({
                'user_id': user_id,
                'organization_id': organization_id,
                'role': role,
                'created_at': now,
                'updated_at': now
            }).execute()

        except Exception as e:
            logger.error(f"Error ensuring org membership for user {user_id}: {e}")

    def _parse_name(self, full_name: str) -> tuple:
        """Parse a full name into first and last name."""
        if not full_name:
            return ("", "")

        parts = full_name.strip().split(" ", 1)
        first_name = parts[0] if parts else ""
        last_name = parts[1] if len(parts) > 1 else ""

        return (first_name, last_name)

    def _map_fub_role(self, fub_role: str) -> str:
        """Map FUB role to our system role."""
        role_mapping = {
            "admin": "broker",
            "owner": "broker",
            "manager": "manager",
            "agent": "agent",
            "assistant": "agent",
            "lender": "agent"
        }
        return role_mapping.get(fub_role.lower(), "agent")

    def get_or_create_organization(self, user_id: str, fub_account_info: Dict = None) -> str:
        """
        Get or create an organization for a user.

        If the user is already in an organization, return that org ID.
        Otherwise, create a new organization.

        Args:
            user_id: The user's ID
            fub_account_info: Optional FUB account info for naming

        Returns:
            Organization ID
        """
        try:
            # Check if user is already in an organization
            existing = self.supabase.table('organization_users').select(
                'organization_id'
            ).eq('user_id', user_id).limit(1).execute()

            if existing.data:
                return existing.data[0]['organization_id']

            # Create new organization
            org_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()

            # Get org name from FUB account or user
            org_name = "My Organization"
            if fub_account_info:
                org_name = fub_account_info.get('domain', 'My Organization')

            org_data = {
                'id': org_id,
                'name': org_name,
                'created_at': now,
                'updated_at': now
            }

            self.supabase.table('organizations').insert(org_data).execute()

            # Add user to organization as owner
            self.supabase.table('organization_users').insert({
                'user_id': user_id,
                'organization_id': org_id,
                'role': 'broker',
                'created_at': now,
                'updated_at': now
            }).execute()

            logger.info(f"Created organization {org_id} for user {user_id}")

            return org_id

        except Exception as e:
            logger.error(f"Error getting/creating organization for user {user_id}: {e}")
            raise


class FUBTeamProvisioningServiceSingleton:
    """Singleton wrapper for FUBTeamProvisioningService."""

    _instance: Optional[FUBTeamProvisioningService] = None

    @classmethod
    def get_instance(cls) -> FUBTeamProvisioningService:
        if cls._instance is None:
            cls._instance = FUBTeamProvisioningService()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None
