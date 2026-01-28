"""
Trial Service - Manages 3-day trial subscriptions and trial credits.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from app.database.supabase_client import SupabaseClientSingleton

logger = logging.getLogger(__name__)

# Trial configuration
TRIAL_CREDITS = {
    'enhancement': 30,
    'criminal': 2,
    'dnc': 30
}
TRIAL_DURATION_DAYS = 3
SIGNUP_URL = 'https://app.leadsynergy.ai/signup'


class TrialService:
    """Service for managing trial subscriptions and credits."""

    def __init__(self):
        self.supabase = SupabaseClientSingleton.get_instance()

    def start_trial(self, user_id: str, organization_id: str = None) -> Dict[str, Any]:
        """
        Start a 3-day trial for a new user.

        Creates trial credits on the user record and optionally
        creates/updates a subscription record for the organization.

        Args:
            user_id: The user's ID
            organization_id: Optional organization ID for subscription tracking

        Returns:
            Dict with trial details including end date and credits granted
        """
        try:
            now = datetime.utcnow()
            trial_end = now + timedelta(days=TRIAL_DURATION_DAYS)

            # Check if user already had a trial
            existing = self.supabase.table('users').select(
                'trial_started_at'
            ).eq('id', user_id).maybe_single().execute()

            if existing.data and existing.data.get('trial_started_at'):
                logger.warning(f"User {user_id} already had a trial started")
                return {
                    'trial_started': False,
                    'message': 'Trial already used',
                    'trial_ends_at': existing.data.get('trial_ends_at')
                }

            # Update user with trial credits
            self.supabase.table('users').update({
                'trial_enhancement_credits': TRIAL_CREDITS['enhancement'],
                'trial_criminal_credits': TRIAL_CREDITS['criminal'],
                'trial_dnc_credits': TRIAL_CREDITS['dnc'],
                'trial_started_at': now.isoformat(),
                'trial_ends_at': trial_end.isoformat()
            }).eq('id', user_id).execute()

            logger.info(f"Started trial for user {user_id}, ends at {trial_end.isoformat()}")

            # Create or update subscription if organization provided
            if organization_id:
                self._create_trial_subscription(organization_id, trial_end)

            return {
                'trial_started': True,
                'trial_ends_at': trial_end.isoformat(),
                'credits_granted': TRIAL_CREDITS,
                'days': TRIAL_DURATION_DAYS
            }

        except Exception as e:
            logger.error(f"Error starting trial for user {user_id}: {e}")
            return {
                'trial_started': False,
                'error': str(e)
            }

    def _create_trial_subscription(self, organization_id: str, trial_end: datetime):
        """Create or update subscription record for trial."""
        try:
            # Check if subscription exists
            existing = self.supabase.table('subscriptions').select('id').eq(
                'organization_id', organization_id
            ).maybe_single().execute()

            subscription_data = {
                'organization_id': organization_id,
                'status': 'trialing',
                'trial_end': trial_end.isoformat(),
                'current_period_start': datetime.utcnow().isoformat(),
                'current_period_end': trial_end.isoformat(),
                'cancel_at_period_end': False
            }

            if existing.data:
                self.supabase.table('subscriptions').update(
                    subscription_data
                ).eq('id', existing.data['id']).execute()
            else:
                subscription_data['created_at'] = datetime.utcnow().isoformat()
                self.supabase.table('subscriptions').insert(
                    subscription_data
                ).execute()

            logger.info(f"Created/updated trial subscription for org {organization_id}")

        except Exception as e:
            logger.error(f"Error creating trial subscription: {e}")

    def check_trial_status(self, user_id: str) -> Dict[str, Any]:
        """
        Check the trial status for a user.

        Args:
            user_id: The user's ID

        Returns:
            Dict with status ('not_started', 'active', 'expired') and details
        """
        try:
            result = self.supabase.table('users').select(
                'trial_started_at, trial_ends_at, '
                'trial_enhancement_credits, trial_criminal_credits, trial_dnc_credits'
            ).eq('id', user_id).maybe_single().execute()

            if not result.data:
                return {'status': 'user_not_found'}

            user = result.data
            trial_ends_at = user.get('trial_ends_at')

            if not trial_ends_at:
                return {'status': 'not_started'}

            # Parse the trial end date
            if isinstance(trial_ends_at, str):
                # Handle ISO format with or without timezone
                trial_ends_at = trial_ends_at.replace('Z', '+00:00')
                if '+' not in trial_ends_at and '-' not in trial_ends_at[10:]:
                    trial_end = datetime.fromisoformat(trial_ends_at)
                else:
                    trial_end = datetime.fromisoformat(trial_ends_at).replace(tzinfo=None)
            else:
                trial_end = trial_ends_at

            now = datetime.utcnow()

            if now < trial_end:
                days_remaining = (trial_end - now).days
                hours_remaining = int((trial_end - now).total_seconds() / 3600)

                return {
                    'status': 'active',
                    'ends_at': trial_end.isoformat(),
                    'days_remaining': days_remaining,
                    'hours_remaining': hours_remaining,
                    'credits_remaining': {
                        'enhancement': user.get('trial_enhancement_credits', 0),
                        'criminal': user.get('trial_criminal_credits', 0),
                        'dnc': user.get('trial_dnc_credits', 0)
                    }
                }
            else:
                return {
                    'status': 'expired',
                    'ended_at': trial_end.isoformat(),
                    'credits_remaining': {
                        'enhancement': user.get('trial_enhancement_credits', 0),
                        'criminal': user.get('trial_criminal_credits', 0),
                        'dnc': user.get('trial_dnc_credits', 0)
                    }
                }

        except Exception as e:
            logger.error(f"Error checking trial status for user {user_id}: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def is_trial_expired(self, user_id: str) -> bool:
        """
        Quick check if a user's trial has expired.

        Args:
            user_id: The user's ID

        Returns:
            True if trial is expired, False if active or not started
        """
        status = self.check_trial_status(user_id)
        return status.get('status') == 'expired'

    def is_trial_active(self, user_id: str) -> bool:
        """
        Quick check if a user has an active trial.

        Args:
            user_id: The user's ID

        Returns:
            True if trial is active, False otherwise
        """
        status = self.check_trial_status(user_id)
        return status.get('status') == 'active'

    def get_trial_credits(self, user_id: str) -> Dict[str, int]:
        """
        Get remaining trial credits for a user.

        Args:
            user_id: The user's ID

        Returns:
            Dict with credit counts by type
        """
        try:
            result = self.supabase.table('users').select(
                'trial_enhancement_credits, trial_criminal_credits, trial_dnc_credits'
            ).eq('id', user_id).maybe_single().execute()

            if not result.data:
                return {'enhancement': 0, 'criminal': 0, 'dnc': 0}

            return {
                'enhancement': result.data.get('trial_enhancement_credits', 0) or 0,
                'criminal': result.data.get('trial_criminal_credits', 0) or 0,
                'dnc': result.data.get('trial_dnc_credits', 0) or 0
            }

        except Exception as e:
            logger.error(f"Error getting trial credits for user {user_id}: {e}")
            return {'enhancement': 0, 'criminal': 0, 'dnc': 0}

    def deduct_trial_credit(self, user_id: str, credit_type: str, amount: int = 1) -> bool:
        """
        Deduct credits from a user's trial balance.

        Args:
            user_id: The user's ID
            credit_type: 'enhancement', 'criminal', or 'dnc'
            amount: Number of credits to deduct

        Returns:
            True if successful, False if insufficient credits
        """
        try:
            column_map = {
                'enhancement': 'trial_enhancement_credits',
                'criminal': 'trial_criminal_credits',
                'dnc': 'trial_dnc_credits'
            }

            if credit_type not in column_map:
                logger.error(f"Invalid credit type: {credit_type}")
                return False

            column = column_map[credit_type]

            # Get current balance
            result = self.supabase.table('users').select(
                column
            ).eq('id', user_id).maybe_single().execute()

            if not result.data:
                return False

            current = result.data.get(column, 0) or 0

            if current < amount:
                return False

            # Deduct
            new_balance = current - amount
            self.supabase.table('users').update({
                column: new_balance
            }).eq('id', user_id).execute()

            logger.info(f"Deducted {amount} {credit_type} trial credit(s) from user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error deducting trial credit: {e}")
            return False

    def grant_trial_credits(self, user_id: str, trial_end: datetime) -> Dict[str, Any]:
        """
        Grant trial credits after Stripe checkout confirms trial subscription.

        This is called by the webhook handler after a successful checkout
        that creates a subscription with trialing status.

        Args:
            user_id: The user's ID
            trial_end: The trial end datetime from Stripe

        Returns:
            Dict with grant details
        """
        try:
            now = datetime.utcnow()

            # Update user with trial credits
            self.supabase.table('users').update({
                'trial_enhancement_credits': TRIAL_CREDITS['enhancement'],
                'trial_criminal_credits': TRIAL_CREDITS['criminal'],
                'trial_dnc_credits': TRIAL_CREDITS['dnc'],
                'trial_started_at': now.isoformat(),
                'trial_ends_at': trial_end.isoformat()
            }).eq('id', user_id).execute()

            logger.info(
                f"Granted trial credits to user {user_id}: "
                f"{TRIAL_CREDITS['enhancement']} enhancement, "
                f"{TRIAL_CREDITS['criminal']} criminal, "
                f"{TRIAL_CREDITS['dnc']} DNC. "
                f"Trial ends: {trial_end.isoformat()}"
            )

            return {
                'success': True,
                'credits_granted': TRIAL_CREDITS,
                'trial_ends_at': trial_end.isoformat()
            }

        except Exception as e:
            logger.error(f"Error granting trial credits to user {user_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def expire_trial_credits(self, user_id: str) -> Dict[str, Any]:
        """
        Zero out trial credits when trial expires without payment.

        Called when Stripe subscription status changes from 'trialing' to
        'past_due', 'canceled', or 'incomplete'.

        Args:
            user_id: The user's ID

        Returns:
            Dict with expiration details
        """
        try:
            self.supabase.table('users').update({
                'trial_enhancement_credits': 0,
                'trial_criminal_credits': 0,
                'trial_dnc_credits': 0
            }).eq('id', user_id).execute()

            logger.info(f"Expired trial credits for user {user_id}")

            return {
                'success': True,
                'message': 'Trial credits expired'
            }

        except Exception as e:
            logger.error(f"Error expiring trial credits for user {user_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }


class TrialServiceSingleton:
    """Singleton wrapper for TrialService."""

    _instance: Optional[TrialService] = None

    @classmethod
    def get_instance(cls) -> TrialService:
        if cls._instance is None:
            cls._instance = TrialService()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None
