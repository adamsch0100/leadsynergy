"""
Credit Service - Handles all credit-related operations.
Ported from Leaddata's User model credit methods.
"""

import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from app.database.supabase_client import SupabaseClientSingleton
from app.models.credit_transaction import CreditTransaction

logger = logging.getLogger(__name__)


class CreditService:
    """
    Service for managing user credits.

    Credit Pool Priority:
    - Brokers: plan -> bundle -> personal
    - Agents: bundle -> allocated -> broker's shared pool (if enabled)
    """

    # Credit types
    TYPE_ENHANCEMENT = 'enhancement'
    TYPE_CRIMINAL = 'criminal'
    TYPE_DNC = 'dnc'

    def __init__(self):
        self.supabase = SupabaseClientSingleton.get_instance()

    def get_user_credits(self, user_id: str) -> Dict[str, Any]:
        """
        Get all credit information for a user.

        Returns:
            Dict with credit balances and user type info
        """
        try:
            result = self.supabase.table('users').select(
                'id, user_type, broker_id, '
                'plan_enhancement_credits, plan_criminal_credits, plan_dnc_credits, '
                'bundle_enhancement_credits, bundle_criminal_credits, bundle_dnc_credits, '
                'allocated_enhancement_credits, allocated_criminal_credits, allocated_dnc_credits, '
                'personal_enhancement_credits, personal_criminal_credits, '
                'credit_allocation_type'
            ).eq('id', user_id).single().execute()

            if not result.data:
                return None

            user = result.data
            user_type = user.get('user_type', 'agent')

            # Calculate totals based on user type
            if user_type == 'broker':
                total_enhancement = (
                    (user.get('plan_enhancement_credits') or 0) +
                    (user.get('bundle_enhancement_credits') or 0) +
                    (user.get('personal_enhancement_credits') or 0)
                )
                total_criminal = (
                    (user.get('plan_criminal_credits') or 0) +
                    (user.get('bundle_criminal_credits') or 0) +
                    (user.get('personal_criminal_credits') or 0)
                )
                total_dnc = (
                    (user.get('plan_dnc_credits') or 0) +
                    (user.get('bundle_dnc_credits') or 0)
                )
            else:
                # Agent - includes allocated credits
                total_enhancement = (
                    (user.get('bundle_enhancement_credits') or 0) +
                    (user.get('allocated_enhancement_credits') or 0)
                )
                total_criminal = (
                    (user.get('bundle_criminal_credits') or 0) +
                    (user.get('allocated_criminal_credits') or 0)
                )
                total_dnc = (
                    (user.get('bundle_dnc_credits') or 0) +
                    (user.get('allocated_dnc_credits') or 0)
                )

            return {
                'user_id': user_id,
                'user_type': user_type,
                'broker_id': user.get('broker_id'),
                'credit_allocation_type': user.get('credit_allocation_type', 'shared'),

                # Individual pools
                'plan_enhancement_credits': user.get('plan_enhancement_credits') or 0,
                'plan_criminal_credits': user.get('plan_criminal_credits') or 0,
                'plan_dnc_credits': user.get('plan_dnc_credits') or 0,
                'bundle_enhancement_credits': user.get('bundle_enhancement_credits') or 0,
                'bundle_criminal_credits': user.get('bundle_criminal_credits') or 0,
                'bundle_dnc_credits': user.get('bundle_dnc_credits') or 0,
                'allocated_enhancement_credits': user.get('allocated_enhancement_credits') or 0,
                'allocated_criminal_credits': user.get('allocated_criminal_credits') or 0,
                'allocated_dnc_credits': user.get('allocated_dnc_credits') or 0,
                'personal_enhancement_credits': user.get('personal_enhancement_credits') or 0,
                'personal_criminal_credits': user.get('personal_criminal_credits') or 0,

                # Totals
                'total_enhancement_credits': total_enhancement,
                'total_criminal_credits': total_criminal,
                'total_dnc_credits': total_dnc,
            }

        except Exception as e:
            logger.error(f"Error getting user credits: {e}")
            return None

    def can_perform_search(self, user_id: str, credit_type: str) -> Tuple[bool, str]:
        """
        Check if user can perform a search based on their credits.

        Args:
            user_id: The user's ID
            credit_type: 'enhancement', 'criminal', or 'dnc'

        Returns:
            Tuple of (can_perform: bool, reason: str)
        """
        try:
            user_credits = self.get_user_credits(user_id)
            if not user_credits:
                return False, "User not found"

            user_type = user_credits['user_type']

            if user_type == 'broker':
                # Brokers use their own credits
                if credit_type == self.TYPE_CRIMINAL:
                    has_credits = (
                        user_credits['plan_criminal_credits'] +
                        user_credits['bundle_criminal_credits'] +
                        user_credits['personal_criminal_credits']
                    ) > 0
                elif credit_type == self.TYPE_DNC:
                    has_credits = (
                        user_credits['plan_dnc_credits'] +
                        user_credits['bundle_dnc_credits']
                    ) > 0
                else:  # enhancement
                    has_credits = (
                        user_credits['plan_enhancement_credits'] +
                        user_credits['bundle_enhancement_credits'] +
                        user_credits['personal_enhancement_credits']
                    ) > 0

                if not has_credits:
                    return False, f"Insufficient {credit_type} credits"
                return True, "OK"

            else:  # Agent
                # First check agent's own credits (bundle + allocated)
                if credit_type == self.TYPE_CRIMINAL:
                    agent_credits = (
                        user_credits['bundle_criminal_credits'] +
                        user_credits['allocated_criminal_credits']
                    )
                elif credit_type == self.TYPE_DNC:
                    agent_credits = (
                        user_credits['bundle_dnc_credits'] +
                        user_credits['allocated_dnc_credits']
                    )
                else:  # enhancement
                    agent_credits = (
                        user_credits['bundle_enhancement_credits'] +
                        user_credits['allocated_enhancement_credits']
                    )

                if agent_credits > 0:
                    return True, "OK"

                # Check broker's shared pool
                broker_id = user_credits.get('broker_id')
                if broker_id:
                    broker_credits = self.get_user_credits(broker_id)
                    if broker_credits and broker_credits.get('credit_allocation_type') == 'shared':
                        if credit_type == self.TYPE_CRIMINAL:
                            has_credits = (
                                broker_credits['plan_criminal_credits'] +
                                broker_credits['bundle_criminal_credits'] +
                                broker_credits['personal_criminal_credits']
                            ) > 0
                        elif credit_type == self.TYPE_DNC:
                            has_credits = (
                                broker_credits['plan_dnc_credits'] +
                                broker_credits['bundle_dnc_credits']
                            ) > 0
                        else:  # enhancement
                            has_credits = (
                                broker_credits['plan_enhancement_credits'] +
                                broker_credits['bundle_enhancement_credits'] +
                                broker_credits['personal_enhancement_credits']
                            ) > 0

                        if has_credits:
                            return True, "OK"

                return False, f"Insufficient {credit_type} credits"

        except Exception as e:
            logger.error(f"Error checking credits: {e}")
            return False, f"Error checking credits: {str(e)}"

    def use_credits(self, user_id: str, credit_type: str, amount: int = 1,
                    description: str = None) -> Tuple[bool, str, Optional[str]]:
        """
        Deduct credits from user's account.

        Args:
            user_id: The user's ID
            credit_type: 'enhancement', 'criminal', or 'dnc'
            amount: Number of credits to deduct
            description: Optional description for the transaction

        Returns:
            Tuple of (success: bool, message: str, credit_source: str or None)
        """
        try:
            # First check if user can perform the search
            can_perform, reason = self.can_perform_search(user_id, credit_type)
            if not can_perform:
                return False, reason, None

            user_credits = self.get_user_credits(user_id)
            user_type = user_credits['user_type']
            credit_source = None
            broker_id = None

            # Determine which pool to deduct from
            if user_type == 'broker':
                credit_source = self._deduct_broker_credits(
                    user_id, credit_type, amount, user_credits
                )
            else:  # Agent
                credit_source, broker_id = self._deduct_agent_credits(
                    user_id, credit_type, amount, user_credits
                )

            if not credit_source:
                return False, "Failed to deduct credits", None

            # Record the transaction
            self._record_transaction(
                user_id=user_id,
                broker_id=broker_id,
                transaction_type=CreditTransaction.TYPE_USAGE,
                credit_type=credit_type,
                amount=amount,
                credit_source=credit_source,
                description=description or f"Used {amount} {credit_type} credit(s)"
            )

            logger.info(f"User {user_id} used {amount} {credit_type} credit(s) from {credit_source}")
            return True, "Credits deducted successfully", credit_source

        except Exception as e:
            logger.error(f"Error using credits: {e}")
            return False, f"Error using credits: {str(e)}", None

    def _deduct_broker_credits(self, user_id: str, credit_type: str,
                               amount: int, user_credits: Dict) -> Optional[str]:
        """
        Deduct credits from broker's pools in order: plan -> bundle -> personal.
        Returns the credit source that was used.
        """
        pools_order = []

        if credit_type == self.TYPE_CRIMINAL:
            pools_order = [
                ('plan_criminal_credits', CreditTransaction.SOURCE_BROKER_PLAN),
                ('bundle_criminal_credits', CreditTransaction.SOURCE_BROKER_BUNDLE),
                ('personal_criminal_credits', CreditTransaction.SOURCE_BROKER_PERSONAL),
            ]
        elif credit_type == self.TYPE_DNC:
            pools_order = [
                ('plan_dnc_credits', CreditTransaction.SOURCE_BROKER_PLAN),
                ('bundle_dnc_credits', CreditTransaction.SOURCE_BROKER_BUNDLE),
            ]
        else:  # enhancement
            pools_order = [
                ('plan_enhancement_credits', CreditTransaction.SOURCE_BROKER_PLAN),
                ('bundle_enhancement_credits', CreditTransaction.SOURCE_BROKER_BUNDLE),
                ('personal_enhancement_credits', CreditTransaction.SOURCE_BROKER_PERSONAL),
            ]

        for field, source in pools_order:
            if user_credits.get(field, 0) >= amount:
                # Deduct from this pool
                new_value = user_credits[field] - amount
                self.supabase.table('users').update({
                    field: new_value
                }).eq('id', user_id).execute()
                return source

        return None

    def _deduct_agent_credits(self, user_id: str, credit_type: str,
                              amount: int, user_credits: Dict) -> Tuple[Optional[str], Optional[str]]:
        """
        Deduct credits from agent's pools in order: bundle -> allocated -> broker's shared.
        Returns tuple of (credit_source, broker_id if shared pool used).
        """
        broker_id = user_credits.get('broker_id')

        # Agent pools
        if credit_type == self.TYPE_CRIMINAL:
            agent_pools = [
                ('bundle_criminal_credits', CreditTransaction.SOURCE_AGENT_BUNDLE),
                ('allocated_criminal_credits', CreditTransaction.SOURCE_AGENT_ALLOCATED),
            ]
        elif credit_type == self.TYPE_DNC:
            agent_pools = [
                ('bundle_dnc_credits', CreditTransaction.SOURCE_AGENT_BUNDLE),
                ('allocated_dnc_credits', CreditTransaction.SOURCE_AGENT_ALLOCATED),
            ]
        else:  # enhancement
            agent_pools = [
                ('bundle_enhancement_credits', CreditTransaction.SOURCE_AGENT_BUNDLE),
                ('allocated_enhancement_credits', CreditTransaction.SOURCE_AGENT_ALLOCATED),
            ]

        # Try agent's own pools first
        for field, source in agent_pools:
            if user_credits.get(field, 0) >= amount:
                new_value = user_credits[field] - amount
                self.supabase.table('users').update({
                    field: new_value
                }).eq('id', user_id).execute()
                return source, None

        # Try broker's shared pool
        if broker_id:
            broker_credits = self.get_user_credits(broker_id)
            if broker_credits and broker_credits.get('credit_allocation_type') == 'shared':
                if credit_type == self.TYPE_CRIMINAL:
                    broker_pools = [
                        ('plan_criminal_credits', CreditTransaction.SOURCE_BROKER_SHARED_PLAN),
                        ('bundle_criminal_credits', CreditTransaction.SOURCE_BROKER_SHARED_BUNDLE),
                        ('personal_criminal_credits', CreditTransaction.SOURCE_BROKER_SHARED_PERSONAL),
                    ]
                elif credit_type == self.TYPE_DNC:
                    broker_pools = [
                        ('plan_dnc_credits', CreditTransaction.SOURCE_BROKER_SHARED_PLAN),
                        ('bundle_dnc_credits', CreditTransaction.SOURCE_BROKER_SHARED_BUNDLE),
                    ]
                else:  # enhancement
                    broker_pools = [
                        ('plan_enhancement_credits', CreditTransaction.SOURCE_BROKER_SHARED_PLAN),
                        ('bundle_enhancement_credits', CreditTransaction.SOURCE_BROKER_SHARED_BUNDLE),
                        ('personal_enhancement_credits', CreditTransaction.SOURCE_BROKER_SHARED_PERSONAL),
                    ]

                for field, source in broker_pools:
                    if broker_credits.get(field, 0) >= amount:
                        new_value = broker_credits[field] - amount
                        self.supabase.table('users').update({
                            field: new_value
                        }).eq('id', broker_id).execute()
                        return source, broker_id

        return None, None

    def allocate_credits(self, broker_id: str, agent_id: str,
                         enhancement_credits: int = 0,
                         criminal_credits: int = 0,
                         dnc_credits: int = 0) -> Tuple[bool, str]:
        """
        Allocate credits from broker to agent.

        Args:
            broker_id: The broker's user ID
            agent_id: The agent's user ID
            enhancement_credits: Number of enhancement credits to allocate
            criminal_credits: Number of criminal credits to allocate
            dnc_credits: Number of DNC credits to allocate

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Validate broker
            broker_credits = self.get_user_credits(broker_id)
            if not broker_credits or broker_credits['user_type'] != 'broker':
                return False, "Only brokers can allocate credits"

            # Validate agent belongs to broker
            agent_result = self.supabase.table('users').select(
                'id, broker_id'
            ).eq('id', agent_id).single().execute()

            if not agent_result.data or agent_result.data.get('broker_id') != broker_id:
                return False, "Agent does not belong to this broker"

            # Check broker has enough available credits
            available = self.get_available_credits_for_allocation(broker_id)
            if enhancement_credits > available.get('enhancement_credits', 0):
                return False, f"Insufficient enhancement credits (available: {available['enhancement_credits']})"
            if criminal_credits > available.get('criminal_credits', 0):
                return False, f"Insufficient criminal credits (available: {available['criminal_credits']})"
            if dnc_credits > available.get('dnc_credits', 0):
                return False, f"Insufficient DNC credits (available: {available['dnc_credits']})"

            # Update agent's allocated credits
            self.supabase.table('users').update({
                'allocated_enhancement_credits': enhancement_credits,
                'allocated_criminal_credits': criminal_credits,
                'allocated_dnc_credits': dnc_credits,
            }).eq('id', agent_id).execute()

            # Record transaction
            self._record_transaction(
                user_id=agent_id,
                broker_id=broker_id,
                transaction_type=CreditTransaction.TYPE_ALLOCATION,
                credit_type='mixed',
                enhancement_credits=enhancement_credits,
                criminal_credits=criminal_credits,
                dnc_credits=dnc_credits,
                description=f"Credits allocated by broker"
            )

            logger.info(f"Broker {broker_id} allocated credits to agent {agent_id}")
            return True, "Credits allocated successfully"

        except Exception as e:
            logger.error(f"Error allocating credits: {e}")
            return False, f"Error allocating credits: {str(e)}"

    def get_available_credits_for_allocation(self, broker_id: str) -> Dict[str, int]:
        """
        Get broker's available credits for allocation (total minus already allocated).
        """
        try:
            broker_credits = self.get_user_credits(broker_id)
            if not broker_credits or broker_credits['user_type'] != 'broker':
                return {'enhancement_credits': 0, 'criminal_credits': 0, 'dnc_credits': 0}

            # Get total allocated to agents
            agents_result = self.supabase.table('users').select(
                'allocated_enhancement_credits, allocated_criminal_credits, allocated_dnc_credits'
            ).eq('broker_id', broker_id).execute()

            total_allocated_enhancement = sum(
                (a.get('allocated_enhancement_credits') or 0) for a in (agents_result.data or [])
            )
            total_allocated_criminal = sum(
                (a.get('allocated_criminal_credits') or 0) for a in (agents_result.data or [])
            )
            total_allocated_dnc = sum(
                (a.get('allocated_dnc_credits') or 0) for a in (agents_result.data or [])
            )

            return {
                'enhancement_credits': max(0, broker_credits['total_enhancement_credits'] - total_allocated_enhancement),
                'criminal_credits': max(0, broker_credits['total_criminal_credits'] - total_allocated_criminal),
                'dnc_credits': max(0, broker_credits['total_dnc_credits'] - total_allocated_dnc),
            }

        except Exception as e:
            logger.error(f"Error getting available credits for allocation: {e}")
            return {'enhancement_credits': 0, 'criminal_credits': 0, 'dnc_credits': 0}

    def add_credits(self, user_id: str, credit_type: str, amount: int,
                    bundle_id: int = None, stripe_charge_id: str = None,
                    description: str = None) -> Tuple[bool, str]:
        """
        Add credits to a user's bundle pool (for purchases).

        Args:
            user_id: The user's ID
            credit_type: 'enhancement', 'criminal', or 'dnc'
            amount: Number of credits to add
            bundle_id: Optional bundle ID
            stripe_charge_id: Optional Stripe charge ID
            description: Optional description

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            field_map = {
                self.TYPE_ENHANCEMENT: 'bundle_enhancement_credits',
                self.TYPE_CRIMINAL: 'bundle_criminal_credits',
                self.TYPE_DNC: 'bundle_dnc_credits',
            }

            field = field_map.get(credit_type)
            if not field:
                return False, f"Invalid credit type: {credit_type}"

            # Get current value
            result = self.supabase.table('users').select(field).eq('id', user_id).single().execute()
            if not result.data:
                return False, "User not found"

            current = result.data.get(field) or 0
            new_value = current + amount

            # Update
            self.supabase.table('users').update({
                field: new_value
            }).eq('id', user_id).execute()

            # Record transaction
            self._record_transaction(
                user_id=user_id,
                bundle_id=bundle_id,
                transaction_type=CreditTransaction.TYPE_PURCHASE,
                credit_type=credit_type,
                amount=amount,
                stripe_charge_id=stripe_charge_id,
                description=description or f"Purchased {amount} {credit_type} credits"
            )

            logger.info(f"Added {amount} {credit_type} credits to user {user_id}")
            return True, "Credits added successfully"

        except Exception as e:
            logger.error(f"Error adding credits: {e}")
            return False, f"Error adding credits: {str(e)}"

    def set_plan_credits(self, user_id: str, enhancement: int = 0,
                         criminal: int = 0, dnc: int = 0,
                         description: str = None) -> Tuple[bool, str]:
        """
        Set plan credits for a user (for subscription updates).
        """
        try:
            self.supabase.table('users').update({
                'plan_enhancement_credits': enhancement,
                'plan_criminal_credits': criminal,
                'plan_dnc_credits': dnc,
            }).eq('id', user_id).execute()

            # Record transaction
            self._record_transaction(
                user_id=user_id,
                transaction_type=CreditTransaction.TYPE_SUBSCRIPTION,
                enhancement_credits=enhancement,
                criminal_credits=criminal,
                dnc_credits=dnc,
                description=description or "Subscription credits allocated"
            )

            logger.info(f"Set plan credits for user {user_id}")
            return True, "Plan credits set successfully"

        except Exception as e:
            logger.error(f"Error setting plan credits: {e}")
            return False, f"Error setting plan credits: {str(e)}"

    def _record_transaction(self, user_id: str, transaction_type: str,
                            credit_type: str = None, amount: int = 0,
                            enhancement_credits: int = None,
                            criminal_credits: int = None,
                            dnc_credits: int = None,
                            broker_id: str = None, bundle_id: int = None,
                            credit_source: str = None, stripe_charge_id: str = None,
                            description: str = None):
        """Record a credit transaction."""
        try:
            # Calculate credit amounts if not provided
            if enhancement_credits is None and criminal_credits is None and dnc_credits is None:
                if credit_type == self.TYPE_ENHANCEMENT:
                    enhancement_credits = amount
                    criminal_credits = 0
                    dnc_credits = 0
                elif credit_type == self.TYPE_CRIMINAL:
                    enhancement_credits = 0
                    criminal_credits = amount
                    dnc_credits = 0
                elif credit_type == self.TYPE_DNC:
                    enhancement_credits = 0
                    criminal_credits = 0
                    dnc_credits = amount
                else:
                    enhancement_credits = 0
                    criminal_credits = 0
                    dnc_credits = 0

            transaction_data = {
                'user_id': user_id,
                'broker_id': broker_id,
                'bundle_id': bundle_id,
                'transaction_type': transaction_type,
                'enhancement_credits': enhancement_credits or 0,
                'criminal_credits': criminal_credits or 0,
                'dnc_credits': dnc_credits or 0,
                'credit_source': credit_source,
                'stripe_charge_id': stripe_charge_id,
                'description': description,
                'status': 'completed',
            }

            self.supabase.table('credit_transactions').insert(transaction_data).execute()

        except Exception as e:
            logger.error(f"Error recording transaction: {e}")


# Singleton instance
_credit_service_instance = None


def get_credit_service() -> CreditService:
    """Get or create the credit service singleton."""
    global _credit_service_instance
    if _credit_service_instance is None:
        _credit_service_instance = CreditService()
    return _credit_service_instance


class CreditServiceSingleton:
    """Singleton wrapper for backward compatibility."""
    _instance = None

    @classmethod
    def get_instance(cls) -> CreditService:
        if cls._instance is None:
            cls._instance = CreditService()
        return cls._instance
