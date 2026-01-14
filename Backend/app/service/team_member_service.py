import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from supabase import Client

from app.database.supabase_client import SupabaseClientSingleton
from app.models.team_member import TeamMember
from app.service.user_service import UserServiceSingleton


class TeamMemberService:
    def __init__(self) -> None:
        self.supabase: Client = SupabaseClientSingleton.get_instance()
        self.user_service = UserServiceSingleton.get_instance()

    def get_by_organization(self, organization_id: str) -> List[TeamMember]:
        """
        Get all team members for an organization

        Args:
            organization_id: The ID of the organization

        Returns:
            List of TeamMember objects
        """
        try:
            # Get users belonging to this organization with their user details
            result = (
                self.supabase.table("organization_users")
                .select("*, users(*)")
                .eq("organization_id", organization_id)
                .execute()
            )

            # Transform the data to TeamMember objects
            team_members = []
            for item in result.data:
                if "users" in item and item["users"]:
                    team_member = TeamMember.from_user_and_org_data(item["users"], item)
                    team_members.append(team_member)

            return team_members
        except Exception as e:
            print(f"Error fetching team members: {str(e)}")
            return []

    def get_by_id(self, member_id: str) -> Optional[TeamMember]:
        """
        Get a team member by user ID

        Args:
            member_id: The ID of the user

        Returns:
            TeamMember object or None if not found
        """
        try:
            # Get the user
            user = self.user_service.get_by_id(member_id)
            if not user:
                return None

            # Convert to TeamMember
            team_member = TeamMember()
            team_member.id = user.id
            team_member.user_id = user.id
            team_member.first_name = user.first_name
            team_member.last_name = user.last_name
            team_member.full_name = user.full_name
            team_member.email = user.email
            team_member.phone_number = user.phone_number
            team_member.email_notifications = user.email_notifications
            team_member.sms_notifications = user.sms_notifications
            team_member.created_at = user.created_at
            team_member.updated_at = user.updated_at

            return team_member
        except Exception as e:
            print(f"Error fetching team member: {str(e)}")
            return None

    def create(
        self, organization_id: str, data: Dict[str, Any]
    ) -> Optional[TeamMember]:
        """
        Create a new team member and add to organization

        Args:
            organization_id: The ID of the organization
            data: Dictionary with user data

        Returns:
            TeamMember object or None if creation failed
        """
        try:
            # Create the user
            new_user = self.user_service.create(data)
            if not new_user:
                return None

            # Add user to organization
            role = data.get("role", "agent")
            result = (
                self.supabase.table("organization_users")
                .insert(
                    {
                        "organization_id": organization_id,
                        "user_id": new_user.id,
                        "role": role,
                    }
                )
                .execute()
            )

            # Create TeamMember object
            team_member = TeamMember()
            team_member.id = new_user.id
            team_member.user_id = new_user.id
            team_member.organization_id = organization_id
            team_member.first_name = new_user.first_name
            team_member.last_name = new_user.last_name
            team_member.full_name = new_user.full_name
            team_member.email = new_user.email
            team_member.phone_number = new_user.phone_number
            team_member.role = role
            team_member.email_notifications = new_user.email_notifications
            team_member.sms_notifications = new_user.sms_notifications
            team_member.created_at = new_user.created_at
            team_member.updated_at = new_user.updated_at

            return team_member
        except Exception as e:
            print(f"Error creating team member: {str(e)}")
            return None

    def update(self, member_id: str, data: Dict[str, Any]) -> Optional[TeamMember]:
        """
        Update a team member

        Args:
            member_id: The ID of the user
            data: Dictionary with data to update

        Returns:
            Updated TeamMember object or None if update failed
        """
        try:
            # Update the user
            updated_user = self.user_service.update(member_id, data)
            if not updated_user:
                return None

            # Convert to TeamMember
            team_member = TeamMember()
            team_member.id = updated_user.id
            team_member.user_id = updated_user.id
            team_member.first_name = updated_user.first_name
            team_member.last_name = updated_user.last_name
            team_member.full_name = updated_user.full_name
            team_member.email = updated_user.email
            team_member.phone_number = updated_user.phone_number
            team_member.email_notifications = updated_user.email_notifications
            team_member.sms_notifications = updated_user.sms_notifications
            team_member.created_at = updated_user.created_at
            team_member.updated_at = updated_user.updated_at

            return team_member
        except Exception as e:
            print(f"Error updating team member: {str(e)}")
            return None

    def delete(self, organization_id: str, member_id: str) -> bool:
        """
        Delete a team member from organization and the system

        Args:
            organization_id: The ID of the organization
            member_id: The ID of the user

        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            # First remove the user from the organization
            self.supabase.table("organization_users").delete().eq(
                "user_id", member_id
            ).eq("organization_id", organization_id).execute()

            # Then delete the user
            return self.user_service.delete(member_id)
        except Exception as e:
            print(f"Error deleting team member: {str(e)}")
            return False

    def update_role(
        self, organization_id: str, member_id: str, role: str
    ) -> Optional[TeamMember]:
        """
        Update a team member's role in an organization

        Args:
            organization_id: The ID of the organization
            member_id: The ID of the user
            role: The new role

        Returns:
            Updated TeamMember object or None if update failed
        """
        try:
            # Update the user's role in the organization
            result = (
                self.supabase.table("organization_users")
                .update({"role": role})
                .eq("user_id", member_id)
                .eq("organization_id", organization_id)
                .execute()
            )

            if not result.data:
                return None

            # Get the updated user
            return self.get_by_id(member_id)
        except Exception as e:
            print(f"Error updating team member role: {str(e)}")
            return None

    def invite(
        self, organization_id: str, email: str, role: str = "agent"
    ) -> Optional[Dict[str, Any]]:
        """
        Invite a user to join an organization

        Args:
            organization_id: The ID of the organization
            email: The email of the user to invite
            role: The role to assign to the user

        Returns:
            Dictionary with user ID and email, or None if invitation failed
        """
        try:
            # Check if user already exists
            existing_user = self.user_service.get_by_email(email)

            if existing_user:
                # Add user to organization if not already a member
                check = (
                    self.supabase.table("organization_users")
                    .select("*")
                    .eq("user_id", existing_user.id)
                    .eq("organization_id", organization_id)
                    .execute()
                )

                if not check.data:
                    self.supabase.table("organization_users").insert(
                        {
                            "organization_id": organization_id,
                            "user_id": existing_user.id,
                            "role": role,
                        }
                    ).execute()

                return {"id": existing_user.id, "email": email}

            # Create a new user
            new_user = self.user_service.create(
                {
                    "email": email,
                    "first_name": "Invited",
                    "last_name": "User",
                    "full_name": "Invited User",
                    "role": role,
                }
            )

            if not new_user:
                return None

            # Add user to organization
            self.supabase.table("organization_users").insert(
                {
                    "organization_id": organization_id,
                    "user_id": new_user.id,
                    "role": role,
                }
            ).execute()

            return {"id": new_user.id, "email": email}
        except Exception as e:
            print(f"Error inviting team member: {str(e)}")
            return None

    def resend_invite(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Resend invitation to a user

        Args:
            email: The email of the user

        Returns:
            Dictionary with email, or None if user not found
        """
        try:
            # Check if user exists
            existing_user = self.user_service.get_by_email(email)

            if not existing_user:
                return None

            # In a real implementation, this would send an email invitation
            return {"email": email}
        except Exception as e:
            print(f"Error resending invitation: {str(e)}")
            return None

    def create_magic_link_invitation(
        self, organization_id: str, email: str, role: str, inviter_name: str, organization_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Create a pending invitation record for magic link flow

        Args:
            organization_id: The ID of the organization
            email: The email of the user to invite
            role: The role to assign to the user
            inviter_name: Name of the person sending the invitation
            organization_name: Name of the organization

        Returns:
            Dictionary with invitation details, or None if creation failed
        """
        try:
            # Check if user already exists
            existing_user = self.user_service.get_by_email(email)
            
            if existing_user:
                # Check if already a member of this organization
                check = (
                    self.supabase.table("organization_users")
                    .select("*")
                    .eq("user_id", existing_user.id)
                    .eq("organization_id", organization_id)
                    .execute()
                )
                
                if check.data:
                    return {
                        "status": "already_member",
                        "message": "User is already a member of this organization",
                        "email": email
                    }

            # Create or update pending invitation record
            invitation_data = {
                "email": email,
                "organization_id": organization_id,
                "role": role,
                "inviter_name": inviter_name,
                "organization_name": organization_name,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(days=7)).isoformat()  # 7 days expiry
            }

            # Check if invitation already exists
            existing_invitation = (
                self.supabase.table("pending_invitations")
                .select("*")
                .eq("email", email)
                .eq("organization_id", organization_id)
                .execute()
            )

            if existing_invitation.data:
                # Update existing invitation
                result = (
                    self.supabase.table("pending_invitations")
                    .update(invitation_data)
                    .eq("email", email)
                    .eq("organization_id", organization_id)
                    .execute()
                )
            else:
                # Create new invitation
                result = (
                    self.supabase.table("pending_invitations")
                    .insert(invitation_data)
                    .execute()
                )

            if result.data:
                return {
                    "email": email,
                    "organization_id": organization_id,
                    "role": role,
                    "status": "pending",
                    "invitation_id": result.data[0].get("id") if result.data else None
                }

            return None
        except Exception as e:
            print(f"Error creating magic link invitation: {str(e)}")
            return None

    def complete_magic_link_invitation(
        self, user_id: str, email: str, organization_id: str, role: str, 
        full_name: str = None, first_name: str = None, last_name: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Complete the magic link invitation process by creating user records

        Args:
            user_id: The Supabase user ID from magic link authentication
            email: The user's email
            organization_id: The organization ID
            role: The role to assign
            full_name: Full name of the user
            first_name: First name of the user
            last_name: Last name of the user

        Returns:
            Dictionary with completion result, or None if failed
        """
        try:
            from app.models.user import User, UserProfile
            from datetime import timedelta

            # Prepare name fields
            if not full_name and first_name and last_name:
                full_name = f"{first_name} {last_name}".strip()
            elif not first_name and not last_name and full_name:
                name_parts = full_name.split(" ", 1)
                first_name = name_parts[0] if len(name_parts) > 0 else full_name
                last_name = name_parts[1] if len(name_parts) > 1 else ""

            # Check if user already exists in our system
            existing_user = self.user_service.get_by_id(user_id)
            
            if not existing_user:
                # Create user record in users table
                user = User()
                user.id = user_id
                user.email = email
                user.first_name = first_name or "Invited"
                user.last_name = last_name or "User"
                user.full_name = full_name or f"{first_name or 'Invited'} {last_name or 'User'}".strip()
                user.role = role
                user.email_notifications = True
                user.sms_notifications = False
                user.created_at = datetime.now()
                user.updated_at = datetime.now()

                # Insert user using raw Supabase call (bypassing user service ID generation)
                user_data = user.to_dict()
                user_result = self.supabase.table("users").insert(user_data).execute()
                
                if not user_result.data:
                    raise Exception("Failed to create user record")

            # Check if user profile exists
            existing_profile = self.user_service.get_profile(user_id)
            
            if not existing_profile:
                # Create user profile
                profile = UserProfile()
                profile.id = user_id
                profile.email = email
                profile.full_name = full_name or f"{first_name or 'Invited'} {last_name or 'User'}".strip()
                profile.role = role
                profile.email_notifications = True
                profile.sms_notifications = False
                profile.onboarding_completed = False  # Important: user still needs FUB API key setup
                profile.fub_api_key = None
                profile.created_at = datetime.now()
                profile.updated_at = datetime.now()

                # Create profile using raw Supabase call
                profile_data = profile.to_dict()
                profile_result = self.supabase.table("user_profiles").insert(profile_data).execute()
                
                if not profile_result.data:
                    raise Exception("Failed to create user profile")

            # Check if already a member of this organization
            existing_membership = (
                self.supabase.table("organization_users")
                .select("*")
                .eq("user_id", user_id)
                .eq("organization_id", organization_id)
                .execute()
            )

            if not existing_membership.data:
                # Add user to organization
                org_user_data = {
                    "user_id": user_id,
                    "organization_id": organization_id,
                    "role": role,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
                
                org_result = self.supabase.table("organization_users").insert(org_user_data).execute()
                
                if not org_result.data:
                    raise Exception("Failed to add user to organization")

            # Mark invitation as completed
            try:
                self.supabase.table("pending_invitations").update({
                    "status": "completed",
                    "completed_at": datetime.now().isoformat()
                }).eq("email", email).eq("organization_id", organization_id).execute()
            except Exception as inv_error:
                # Don't fail the whole process if invitation update fails
                print(f"Warning: Could not update invitation status: {str(inv_error)}")

            return {
                "user_id": user_id,
                "email": email,
                "organization_id": organization_id,
                "role": role,
                "full_name": full_name,
                "onboarding_completed": False,
                "requires_fub_api_key": True,
                "message": "Invitation completed successfully"
            }

        except Exception as e:
            print(f"Error completing magic link invitation: {str(e)}")
            return None


class TeamMemberServiceSingleton:
    _instance = None

    @classmethod
    def get_instance(cls) -> TeamMemberService:
        if cls._instance is None:
            cls._instance = TeamMemberService()
        return cls._instance
