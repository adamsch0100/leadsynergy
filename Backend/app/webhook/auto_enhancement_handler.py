"""
Auto-Enhancement Handler - Automatically enhance new leads from FUB.

Handles:
- Checking if auto-enhancement is enabled for a user
- Performing contact enrichment on new leads
- Adding discovered phones/emails to FUB
- Posting enrichment notes to FUB
- Respecting credit limits
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.database.supabase_client import SupabaseClientSingleton
from app.enrichment.endato_client import EndatoClientSingleton
from app.billing.credit_service import CreditServiceSingleton
from app.fub.note_service import FUBNoteServiceSingleton, add_enrichment_contact_data

logger = logging.getLogger(__name__)


class AutoEnhancementHandler:
    """
    Handler for automatically enhancing new leads when they arrive in FUB.
    """

    def __init__(self):
        self.supabase = SupabaseClientSingleton.get_instance()
        self.endato = EndatoClientSingleton.get_instance()
        self.credit_service = CreditServiceSingleton.get_instance()
        self.note_service = FUBNoteServiceSingleton.get_instance()

    def get_user_auto_enhance_settings(self, user_id: str) -> Dict[str, Any]:
        """
        Get auto-enhancement settings for a user.

        Args:
            user_id: The user ID

        Returns:
            Dict with auto-enhancement settings
        """
        try:
            result = self.supabase.table('users').select(
                'auto_enhance_enabled, auto_enhance_phone, auto_enhance_email, '
                'auto_enhance_credit_limit, auto_add_phone_to_fub_on_manual_enhance, '
                'auto_add_email_to_fub_on_manual_enhance, auto_add_note_on_search'
            ).eq('id', user_id).single().execute()

            if result.data:
                return {
                    'enabled': result.data.get('auto_enhance_enabled', False),
                    'enhance_phone': result.data.get('auto_enhance_phone', True),
                    'enhance_email': result.data.get('auto_enhance_email', True),
                    'credit_limit': result.data.get('auto_enhance_credit_limit', 10),
                    'add_phones_to_fub': result.data.get('auto_add_phone_to_fub_on_manual_enhance', True),
                    'add_emails_to_fub': result.data.get('auto_add_email_to_fub_on_manual_enhance', True),
                    'add_note_to_fub': result.data.get('auto_add_note_on_search', True)
                }

            return {'enabled': False}

        except Exception as e:
            logger.error(f"Error getting auto-enhance settings: {e}")
            return {'enabled': False}

    def should_auto_enhance(self, user_id: str) -> tuple:
        """
        Check if auto-enhancement should be performed for a user.

        Args:
            user_id: The user ID

        Returns:
            Tuple of (should_enhance: bool, reason: str)
        """
        try:
            # Get user settings
            settings = self.get_user_auto_enhance_settings(user_id)

            if not settings.get('enabled'):
                return False, "Auto-enhancement is disabled"

            # Check credit balance
            credits = self.credit_service.get_user_credits(user_id)
            if not credits:
                return False, "Could not retrieve credit balance"

            enhancement_credits = credits.get('total_enhancement_credits', 0)
            if enhancement_credits < 1:
                return False, "Insufficient enhancement credits"

            # Check daily limit
            today_usage = self._get_today_auto_enhance_count(user_id)
            credit_limit = settings.get('credit_limit', 10)

            if today_usage >= credit_limit:
                return False, f"Daily auto-enhance limit reached ({credit_limit})"

            return True, "Ready to auto-enhance"

        except Exception as e:
            logger.error(f"Error checking auto-enhance eligibility: {e}")
            return False, str(e)

    def _get_today_auto_enhance_count(self, user_id: str) -> int:
        """Get the number of auto-enhancements performed today."""
        try:
            today = datetime.utcnow().date().isoformat()

            result = self.supabase.table('lookup_history').select(
                'id', count='exact'
            ).eq('user_id', user_id).eq(
                'usage_type', 'auto_enhancement'
            ).gte('created_at', today).execute()

            return result.count if result.count else 0

        except Exception as e:
            logger.error(f"Error getting auto-enhance count: {e}")
            return 0

    def enhance_new_lead(self, user_id: str, fub_person_id: int,
                         first_name: str = None, last_name: str = None,
                         phone: str = None, email: str = None,
                         address: str = None) -> Dict[str, Any]:
        """
        Perform auto-enhancement on a new lead.

        Args:
            user_id: The user ID
            fub_person_id: The FUB person ID
            first_name: Lead's first name
            last_name: Lead's last name
            phone: Lead's phone number
            email: Lead's email address
            address: Lead's address

        Returns:
            Dict with enhancement results
        """
        results = {
            'success': False,
            'enhanced': False,
            'note_posted': False,
            'phones_added': 0,
            'emails_added': 0,
            'message': ''
        }

        try:
            # Check if should auto-enhance
            should_enhance, reason = self.should_auto_enhance(user_id)
            if not should_enhance:
                results['message'] = reason
                return results

            # Get user settings
            settings = self.get_user_auto_enhance_settings(user_id)

            # Perform contact enrichment
            enrichment_result = self.endato.contact_enrichment(
                first_name=first_name or '',
                last_name=last_name or '',
                phone=phone or '',
                email=email or '',
                address_line1=address or ''
            )

            if not enrichment_result or 'error' in enrichment_result:
                error_msg = enrichment_result.get('error', {}).get('message', 'Enrichment failed') if enrichment_result else 'No response'
                results['message'] = f"Enrichment failed: {error_msg}"
                return results

            results['enhanced'] = True

            # Deduct credit
            success, msg, source = self.credit_service.use_credits(
                user_id=user_id,
                credit_type='enhancement',
                amount=1,
                description='Auto-enhancement on new lead'
            )

            if not success:
                logger.warning(f"Failed to deduct credit for auto-enhancement: {msg}")

            # Log the lookup
            try:
                self.supabase.table('lookup_history').insert({
                    'user_id': user_id,
                    'search_type': 'contact_enrichment',
                    'criteria': {
                        'firstName': first_name,
                        'lastName': last_name,
                        'phone': phone,
                        'email': email
                    },
                    'result': enrichment_result,
                    'success': True,
                    'usage_type': 'auto_enhancement',
                    'fub_person_id': str(fub_person_id)
                }).execute()
            except Exception as log_error:
                logger.warning(f"Failed to log auto-enhancement: {log_error}")

            # Add phones and emails to FUB if enabled
            if fub_person_id and (settings.get('add_phones_to_fub') or settings.get('add_emails_to_fub')):
                contact_result = add_enrichment_contact_data(
                    person_id=fub_person_id,
                    enrichment_data=enrichment_result,
                    add_phones=settings.get('add_phones_to_fub', True),
                    add_emails=settings.get('add_emails_to_fub', True)
                )
                results['phones_added'] = contact_result.get('phones_added', 0)
                results['emails_added'] = contact_result.get('emails_added', 0)

            # Post note to FUB if enabled
            if fub_person_id and settings.get('add_note_to_fub'):
                note_result = self.note_service.post_enrichment_note(
                    person_id=fub_person_id,
                    search_type='contact_enrichment',
                    search_data=enrichment_result,
                    search_criteria={
                        'firstName': first_name,
                        'lastName': last_name,
                        'phone': phone,
                        'email': email
                    }
                )
                if note_result and 'error' not in note_result:
                    results['note_posted'] = True

            results['success'] = True
            results['message'] = 'Lead enhanced successfully'

            logger.info(f"Auto-enhanced lead {fub_person_id} for user {user_id}")

            return results

        except Exception as e:
            logger.error(f"Error in auto-enhancement: {e}", exc_info=True)
            results['message'] = str(e)
            return results

    def process_new_person_webhook(self, webhook_data: Dict[str, Any],
                                    user_id: str = None) -> Dict[str, Any]:
        """
        Process a new person webhook and optionally auto-enhance.

        Args:
            webhook_data: The webhook payload from FUB
            user_id: Optional user ID (will try to resolve if not provided)

        Returns:
            Dict with processing results
        """
        results = {
            'processed': False,
            'auto_enhanced': False,
            'message': ''
        }

        try:
            # Extract person data from webhook
            person_data = webhook_data.get('person', webhook_data.get('data', {}))
            fub_person_id = person_data.get('id')

            if not fub_person_id:
                results['message'] = 'No person ID in webhook data'
                return results

            # Get user ID if not provided
            if not user_id:
                # Try to resolve from webhook data or use default
                user_id = self._resolve_user_from_webhook(webhook_data)
                if not user_id:
                    results['message'] = 'Could not resolve user ID'
                    return results

            results['processed'] = True

            # Check if should auto-enhance
            should_enhance, reason = self.should_auto_enhance(user_id)

            if should_enhance:
                # Extract person details
                first_name = person_data.get('firstName', '')
                last_name = person_data.get('lastName', '')

                # Get primary phone
                phones = person_data.get('phones', [])
                phone = None
                for p in phones:
                    if p.get('isPrimary'):
                        phone = p.get('value')
                        break
                if not phone and phones:
                    phone = phones[0].get('value')

                # Get primary email
                emails = person_data.get('emails', [])
                email = None
                for e in emails:
                    if e.get('isPrimary'):
                        email = e.get('value')
                        break
                if not email and emails:
                    email = emails[0].get('value')

                # Get address
                addresses = person_data.get('addresses', [])
                address = None
                if addresses:
                    addr = addresses[0]
                    parts = []
                    if addr.get('street'):
                        parts.append(addr['street'])
                    if addr.get('city'):
                        parts.append(addr['city'])
                    if addr.get('state'):
                        parts.append(addr['state'])
                    if addr.get('code'):
                        parts.append(addr['code'])
                    address = ', '.join(parts) if parts else None

                # Perform auto-enhancement
                enhance_result = self.enhance_new_lead(
                    user_id=user_id,
                    fub_person_id=fub_person_id,
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    email=email,
                    address=address
                )

                results['auto_enhanced'] = enhance_result.get('success', False)
                results['enhancement_details'] = enhance_result
            else:
                results['message'] = reason

            return results

        except Exception as e:
            logger.error(f"Error processing new person webhook: {e}", exc_info=True)
            results['message'] = str(e)
            return results

    def _resolve_user_from_webhook(self, webhook_data: Dict[str, Any]) -> Optional[str]:
        """
        Try to resolve the user ID from webhook data.

        Args:
            webhook_data: The webhook payload

        Returns:
            User ID if found, None otherwise
        """
        try:
            # Try to get from webhook metadata
            if 'userId' in webhook_data:
                return webhook_data['userId']

            # Try to get from assignedTo in person data
            person_data = webhook_data.get('person', webhook_data.get('data', {}))
            if 'assignedTo' in person_data:
                assigned_email = person_data['assignedTo']
                if assigned_email:
                    result = self.supabase.table('users').select('id').eq(
                        'email', assigned_email
                    ).single().execute()
                    if result.data:
                        return result.data['id']

            # Try to get from system event source
            if 'systemEvent' in webhook_data:
                event = webhook_data['systemEvent']
                if 'user' in event and 'email' in event['user']:
                    result = self.supabase.table('users').select('id').eq(
                        'email', event['user']['email']
                    ).single().execute()
                    if result.data:
                        return result.data['id']

            return None

        except Exception as e:
            logger.error(f"Error resolving user from webhook: {e}")
            return None


# =============================================================================
# Singleton Pattern
# =============================================================================

_auto_enhancement_instance = None


def get_auto_enhancement_handler() -> AutoEnhancementHandler:
    """Get or create the Auto Enhancement Handler singleton."""
    global _auto_enhancement_instance
    if _auto_enhancement_instance is None:
        _auto_enhancement_instance = AutoEnhancementHandler()
    return _auto_enhancement_instance


class AutoEnhancementHandlerSingleton:
    """Singleton wrapper for backward compatibility."""
    _instance = None

    @classmethod
    def get_instance(cls) -> AutoEnhancementHandler:
        if cls._instance is None:
            cls._instance = AutoEnhancementHandler()
        return cls._instance
