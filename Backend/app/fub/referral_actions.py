"""
Referral Actions Service - Platform actions from FUB embedded app.

Handles:
- Getting referral platform info for a lead
- Updating lead status on referral platforms
- Logging commissions for closed deals
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

from app.database.supabase_client import SupabaseClientSingleton
from app.models.lead import Lead
from app.referral_scrapers.referral_service_factory import ReferralServiceFactory

logger = logging.getLogger(__name__)


# Platform status options mapping
PLATFORM_STATUS_OPTIONS = {
    'homelight': {
        'display_name': 'HomeLight',
        'fee_percent': 25,
        'statuses': [
            {'value': 'Actively Working', 'label': 'Actively Working'},
            {'value': 'Under Agreement', 'label': 'Under Agreement'},
            {'value': 'Under Contract', 'label': 'Under Contract'},
            {'value': 'Closed', 'label': 'Closed'},
            {'value': 'Lost', 'label': 'Lost'},
            {'value': 'Not Interested', 'label': 'Not Interested'},
        ]
    },
    'redfin': {
        'display_name': 'Redfin',
        'fee_percent': 30,
        'statuses': [
            {'value': 'In Contact', 'label': 'In Contact'},
            {'value': 'Showing Homes', 'label': 'Showing Homes'},
            {'value': 'Under Contract', 'label': 'Under Contract'},
            {'value': 'Closed', 'label': 'Closed'},
            {'value': 'Did Not Close', 'label': 'Did Not Close'},
        ]
    },
    'referral_exchange': {
        'display_name': 'Referral Exchange',
        'fee_percent': 25,
        'statuses': [
            {'value': 'Contacted', 'label': 'Contacted'},
            {'value': 'Met', 'label': 'Met'},
            {'value': 'Working', 'label': 'Working'},
            {'value': 'Submitted', 'label': 'Submitted'},
            {'value': 'Under Contract', 'label': 'Under Contract'},
            {'value': 'Closed', 'label': 'Closed'},
            {'value': 'Not Working', 'label': 'Not Working'},
        ]
    },
    'agent_pronto': {
        'display_name': 'Agent Pronto',
        'fee_percent': 25,
        'statuses': [
            {'value': 'In Progress', 'label': 'In Progress'},
            {'value': 'Under Contract', 'label': 'Under Contract'},
            {'value': 'Closed', 'label': 'Closed'},
            {'value': 'Lost', 'label': 'Lost'},
        ]
    },
    'my_agent_finder': {
        'display_name': 'MyAgentFinder',
        'fee_percent': 25,
        'statuses': [
            {'value': 'New', 'label': 'New'},
            {'value': 'Contacted', 'label': 'Contacted'},
            {'value': 'Qualified', 'label': 'Qualified'},
            {'value': 'Under Contract', 'label': 'Under Contract'},
            {'value': 'Closed', 'label': 'Closed'},
            {'value': 'Dead', 'label': 'Dead'},
        ]
    }
}


class ReferralActionsService:
    """
    Service for managing referral platform actions from the FUB embedded app.
    """

    def __init__(self):
        self.supabase = SupabaseClientSingleton.get_instance()

    def get_lead_by_fub_person_id(self, fub_person_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a lead by FUB person ID.

        Args:
            fub_person_id: The FUB person ID

        Returns:
            Lead data dict or None
        """
        try:
            result = self.supabase.table('leads').select(
                '*'
            ).eq('fub_person_id', str(fub_person_id)).single().execute()

            return result.data if result.data else None
        except Exception as e:
            logger.error(f"Error getting lead by FUB person ID: {e}")
            return None

    def get_lead_referral_info(self, fub_person_id: str) -> Dict[str, Any]:
        """
        Get referral platform info for a lead.

        Args:
            fub_person_id: The FUB person ID

        Returns:
            Dict with platform info, status, fee %, available statuses
        """
        try:
            # Get the lead
            lead_data = self.get_lead_by_fub_person_id(fub_person_id)

            if not lead_data:
                return {
                    'has_referral_source': False,
                    'message': 'Lead not found in system'
                }

            source = lead_data.get('source', '').lower().replace(' ', '_')
            platform_info = PLATFORM_STATUS_OPTIONS.get(source)

            if not platform_info:
                return {
                    'has_referral_source': False,
                    'message': f'Unknown or non-referral source: {lead_data.get("source", "Unknown")}',
                    'lead_id': lead_data.get('id'),
                    'lead_source': lead_data.get('source')
                }

            # Get current status from lead metadata or status field
            current_status = lead_data.get('status', 'Unknown')
            metadata = lead_data.get('metadata', {}) or {}
            platform_status = metadata.get('platform_status', current_status)

            return {
                'has_referral_source': True,
                'lead_id': lead_data.get('id'),
                'lead_name': f"{lead_data.get('first_name', '')} {lead_data.get('last_name', '')}".strip(),
                'platform': {
                    'key': source,
                    'display_name': platform_info['display_name'],
                    'fee_percent': platform_info['fee_percent'],
                },
                'current_status': platform_status,
                'available_statuses': platform_info['statuses'],
                'last_sync': lead_data.get('updated_at'),
                'fub_stage': lead_data.get('fub_stage_name', 'Unknown')
            }

        except Exception as e:
            logger.error(f"Error getting referral info: {e}", exc_info=True)
            return {
                'has_referral_source': False,
                'error': str(e)
            }

    def update_platform_status(self, fub_person_id: str, new_status: str,
                                note: str = None, user_id: str = None) -> Dict[str, Any]:
        """
        Update lead status on the referral platform.

        Args:
            fub_person_id: The FUB person ID
            new_status: The new status to set
            note: Optional note to include with the update
            user_id: The user making the update

        Returns:
            Dict with success status and details
        """
        try:
            # Get the lead
            lead_data = self.get_lead_by_fub_person_id(fub_person_id)

            if not lead_data:
                return {
                    'success': False,
                    'message': 'Lead not found'
                }

            source = lead_data.get('source', '').lower().replace(' ', '_')
            old_status = lead_data.get('status', 'Unknown')

            # Create Lead object for the scraper
            lead = Lead()
            for key, value in lead_data.items():
                if hasattr(lead, key):
                    setattr(lead, key, value)

            # Get the scraper service
            service = ReferralServiceFactory.get_service(source, lead)

            if not service:
                # Log the action attempt even if we can't perform it
                self._log_platform_action(
                    lead_id=lead_data.get('id'),
                    user_id=user_id,
                    platform=source,
                    action='status_update_failed',
                    old_status=old_status,
                    new_status=new_status,
                    note=f"Service not available for platform: {source}"
                )
                return {
                    'success': False,
                    'message': f'No service available for platform: {source}'
                }

            # Attempt to update on the platform
            try:
                # Login to the platform
                logged_in = service.login()
                if not logged_in:
                    self._log_platform_action(
                        lead_id=lead_data.get('id'),
                        user_id=user_id,
                        platform=source,
                        action='status_update_failed',
                        old_status=old_status,
                        new_status=new_status,
                        note="Login failed"
                    )
                    return {
                        'success': False,
                        'message': 'Failed to login to platform'
                    }

                # Update status
                update_success = service.update_customers(new_status)

                if update_success:
                    # Update local lead record
                    metadata = lead_data.get('metadata', {}) or {}
                    metadata['platform_status'] = new_status
                    metadata['last_platform_update'] = datetime.utcnow().isoformat()

                    self.supabase.table('leads').update({
                        'status': new_status,
                        'metadata': metadata,
                        'updated_at': datetime.utcnow().isoformat()
                    }).eq('id', lead_data.get('id')).execute()

                    # Log successful action
                    self._log_platform_action(
                        lead_id=lead_data.get('id'),
                        user_id=user_id,
                        platform=source,
                        action='status_update',
                        old_status=old_status,
                        new_status=new_status,
                        note=note
                    )

                    return {
                        'success': True,
                        'message': f'Status updated to "{new_status}" on {source}',
                        'old_status': old_status,
                        'new_status': new_status
                    }
                else:
                    self._log_platform_action(
                        lead_id=lead_data.get('id'),
                        user_id=user_id,
                        platform=source,
                        action='status_update_failed',
                        old_status=old_status,
                        new_status=new_status,
                        note="Update method returned false"
                    )
                    return {
                        'success': False,
                        'message': 'Platform update failed'
                    }

            except Exception as update_error:
                logger.error(f"Error updating platform: {update_error}")
                self._log_platform_action(
                    lead_id=lead_data.get('id'),
                    user_id=user_id,
                    platform=source,
                    action='status_update_failed',
                    old_status=old_status,
                    new_status=new_status,
                    note=str(update_error)
                )
                return {
                    'success': False,
                    'message': f'Error updating platform: {str(update_error)}'
                }

        except Exception as e:
            logger.error(f"Error in update_platform_status: {e}", exc_info=True)
            return {
                'success': False,
                'message': str(e)
            }

    def log_commission(self, fub_person_id: str, sale_price: float,
                       commission_amount: float = None, fee_percent: float = None,
                       close_date: str = None, notes: str = None,
                       user_id: str = None) -> Dict[str, Any]:
        """
        Log a commission for a closed deal.

        Args:
            fub_person_id: The FUB person ID
            sale_price: The sale price
            commission_amount: The commission amount (calculated if not provided)
            fee_percent: The referral fee percentage
            close_date: The close date
            notes: Optional notes
            user_id: The user logging the commission

        Returns:
            Dict with success status and commission details
        """
        try:
            # Get the lead
            lead_data = self.get_lead_by_fub_person_id(fub_person_id)

            if not lead_data:
                return {
                    'success': False,
                    'message': 'Lead not found'
                }

            source = lead_data.get('source', '').lower().replace(' ', '_')
            platform_info = PLATFORM_STATUS_OPTIONS.get(source, {})

            # Calculate fee if not provided
            if not fee_percent:
                fee_percent = platform_info.get('fee_percent', 25)

            if not commission_amount:
                # Assuming standard 3% agent commission
                agent_commission = sale_price * 0.03
                commission_amount = agent_commission * (fee_percent / 100)

            # Create commission record
            commission_id = str(uuid.uuid4())
            commission_data = {
                'id': commission_id,
                'lead_id': lead_data.get('id'),
                'user_id': user_id,
                'fub_person_id': fub_person_id,
                'platform': source,
                'sale_price': sale_price,
                'commission_amount': commission_amount,
                'fee_percent': fee_percent,
                'close_date': close_date or datetime.utcnow().date().isoformat(),
                'notes': notes,
                'status': 'pending',
                'created_at': datetime.utcnow().isoformat()
            }

            # Insert into database
            try:
                self.supabase.table('commission_submissions').insert(
                    commission_data
                ).execute()
            except Exception as db_error:
                logger.warning(f"Could not save to commission_submissions: {db_error}")
                # Try alternate table name
                try:
                    self.supabase.table('commissions').insert(
                        commission_data
                    ).execute()
                except Exception as alt_error:
                    logger.error(f"Could not save commission: {alt_error}")

            # Update lead status to Closed
            metadata = lead_data.get('metadata', {}) or {}
            metadata['commission_logged'] = True
            metadata['commission_id'] = commission_id
            metadata['commission_amount'] = commission_amount

            self.supabase.table('leads').update({
                'status': 'Closed',
                'metadata': metadata,
                'updated_at': datetime.utcnow().isoformat()
            }).eq('id', lead_data.get('id')).execute()

            # Log the action
            self._log_platform_action(
                lead_id=lead_data.get('id'),
                user_id=user_id,
                platform=source,
                action='commission_logged',
                new_status='Closed',
                note=f"Commission: ${commission_amount:.2f} ({fee_percent}% of sale)"
            )

            return {
                'success': True,
                'message': 'Commission logged successfully',
                'commission': {
                    'id': commission_id,
                    'sale_price': sale_price,
                    'commission_amount': commission_amount,
                    'fee_percent': fee_percent,
                    'platform': platform_info.get('display_name', source)
                }
            }

        except Exception as e:
            logger.error(f"Error logging commission: {e}", exc_info=True)
            return {
                'success': False,
                'message': str(e)
            }

    def _log_platform_action(self, lead_id: str, user_id: str, platform: str,
                              action: str, old_status: str = None,
                              new_status: str = None, note: str = None):
        """
        Log a platform action to the database.

        Args:
            lead_id: The lead ID
            user_id: The user ID
            platform: The platform name
            action: The action type
            old_status: Previous status
            new_status: New status
            note: Optional note
        """
        try:
            log_data = {
                'id': str(uuid.uuid4()),
                'lead_id': lead_id,
                'user_id': user_id,
                'platform': platform,
                'action': action,
                'old_status': old_status,
                'new_status': new_status,
                'note': note,
                'created_at': datetime.utcnow().isoformat()
            }

            self.supabase.table('platform_action_log').insert(log_data).execute()
            logger.info(f"Logged platform action: {action} for lead {lead_id}")

        except Exception as e:
            logger.warning(f"Could not log platform action: {e}")

    def get_platform_action_history(self, fub_person_id: str = None,
                                     lead_id: str = None,
                                     limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get platform action history for a lead.

        Args:
            fub_person_id: Optional FUB person ID
            lead_id: Optional lead ID
            limit: Max results to return

        Returns:
            List of action records
        """
        try:
            query = self.supabase.table('platform_action_log').select('*')

            if lead_id:
                query = query.eq('lead_id', lead_id)
            elif fub_person_id:
                lead_data = self.get_lead_by_fub_person_id(fub_person_id)
                if lead_data:
                    query = query.eq('lead_id', lead_data.get('id'))
                else:
                    return []

            result = query.order('created_at', desc=True).limit(limit).execute()
            return result.data if result.data else []

        except Exception as e:
            logger.error(f"Error getting action history: {e}")
            return []


# =============================================================================
# Singleton Pattern
# =============================================================================

_referral_actions_instance = None


def get_referral_actions_service() -> ReferralActionsService:
    """Get or create the Referral Actions Service singleton."""
    global _referral_actions_instance
    if _referral_actions_instance is None:
        _referral_actions_instance = ReferralActionsService()
    return _referral_actions_instance


class ReferralActionsServiceSingleton:
    """Singleton wrapper for backward compatibility."""
    _instance = None

    @classmethod
    def get_instance(cls) -> ReferralActionsService:
        if cls._instance is None:
            cls._instance = ReferralActionsService()
        return cls._instance
