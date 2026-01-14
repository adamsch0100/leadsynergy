"""
FUB Embedded App Routes.
Ported from Leaddata.

Handles:
- /fub/embedded - Serve the FUB embedded app
- /fub/accept_terms - Accept terms and conditions
- /fub/manual_search - Execute searches from the embedded app
"""

from flask import request, jsonify, render_template, current_app
import logging
import json
import hmac
import hashlib
import base64
from datetime import datetime
import os

from app.fub import fub_bp
from app.enrichment.endato_client import EndatoClientSingleton
from app.billing.credit_service import CreditServiceSingleton
from app.database.supabase_client import SupabaseClientSingleton
from app.fub.note_service import FUBNoteServiceSingleton, add_enrichment_contact_data
from app.fub.referral_actions import ReferralActionsServiceSingleton

logger = logging.getLogger(__name__)


def verify_fub_signature(signed_token: str) -> dict:
    """
    Verify the FUB signed token and extract context.

    Args:
        signed_token: The signed token from FUB

    Returns:
        Decoded context data or None if invalid
    """
    try:
        if not signed_token:
            return None

        # The token format is: base64(payload).signature
        parts = signed_token.rsplit('.', 1)
        if len(parts) != 2:
            logger.warning("Invalid token format")
            return None

        payload_b64, signature = parts

        # Get the FUB secret key
        fub_secret = os.environ.get('FUB_EMBEDDED_APP_SECRET') or os.environ.get('FUB_EMBEDDED_SECRET')
        if not fub_secret:
            logger.warning("FUB_EMBEDDED_APP_SECRET not configured")
            # For development, allow unverified tokens
            if os.environ.get('FLASK_ENV') == 'development':
                try:
                    payload = base64.b64decode(payload_b64 + '==')
                    return json.loads(payload)
                except Exception:
                    return None
            return None

        # Verify signature
        expected_sig = hmac.new(
            fub_secret.encode(),
            payload_b64.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            logger.warning("Invalid token signature")
            return None

        # Decode payload
        payload = base64.b64decode(payload_b64 + '==')
        return json.loads(payload)

    except Exception as e:
        logger.error(f"Error verifying FUB token: {e}")
        return None


def get_user_from_fub_context(context: dict) -> dict:
    """
    Get or create user from FUB context.

    Args:
        context: The FUB context data

    Returns:
        User data dict or None
    """
    try:
        supabase = SupabaseClientSingleton.get_instance()

        # Get user email from context
        user_email = context.get('user', {}).get('email')
        if not user_email:
            return None

        # Find user by email
        result = supabase.table('users').select('*').eq('email', user_email).single().execute()

        if result.data:
            return result.data

        # User not found - could create one here for FUB users
        logger.warning(f"FUB user not found: {user_email}")
        return None

    except Exception as e:
        logger.error(f"Error getting user from FUB context: {e}")
        return None


def check_fub_terms_accepted(user_id: str) -> bool:
    """Check if user has accepted FUB terms."""
    try:
        supabase = SupabaseClientSingleton.get_instance()

        result = supabase.table('users').select(
            'fub_terms_accepted'
        ).eq('id', user_id).single().execute()

        return result.data.get('fub_terms_accepted', False) if result.data else False

    except Exception as e:
        logger.error(f"Error checking FUB terms: {e}")
        return False


# =============================================================================
# Embedded App Routes
# =============================================================================

@fub_bp.route('/embedded', methods=['GET'])
def embedded_app():
    """
    Serve the FUB embedded app.

    Query params:
        - token: The signed FUB token
    """
    try:
        signed_token = request.args.get('token', '')

        # Verify and decode token
        context = verify_fub_signature(signed_token)

        if not context:
            # For development/testing, allow without token
            if os.environ.get('FLASK_ENV') == 'development':
                context = {
                    'user': {'email': 'test@example.com', 'name': 'Test User'},
                    'person': {'firstName': 'John', 'lastName': 'Doe'},
                    'address': {},
                    'email': '',
                    'phone': ''
                }
            else:
                return jsonify({"error": "Invalid or missing token"}), 401

        # Get user from context
        user_data = get_user_from_fub_context(context)

        if not user_data:
            # Create a minimal user object for rendering
            user_data = {
                'id': None,
                'email': context.get('user', {}).get('email', ''),
                'name': context.get('user', {}).get('name', 'Guest')
            }

        # Check if terms accepted
        has_accepted_terms = False
        if user_data.get('id'):
            has_accepted_terms = check_fub_terms_accepted(user_data['id'])

        # Create a simple user object for the template
        class UserObj:
            def __init__(self, data):
                self.email = data.get('email', '')
                self.name = data.get('name', '')
                self.id = data.get('id')

        user = UserObj(user_data)

        # Create a simple lead object
        class LeadObj:
            def __init__(self, context):
                self.id = context.get('person', {}).get('id')

        lead = LeadObj(context)

        # Generate CSRF token (simple implementation)
        import secrets
        csrf_token = secrets.token_hex(32)

        return render_template(
            'fub_embedded_app.html',
            signed_token=signed_token,
            context=json.dumps(context),
            user=user,
            lead=lead,
            has_accepted_terms=has_accepted_terms,
            csrf_token=csrf_token
        )

    except Exception as e:
        logger.error(f"Error serving embedded app: {e}")
        return jsonify({"error": str(e)}), 500


@fub_bp.route('/accept_terms', methods=['POST'])
def accept_terms():
    """
    Accept the FUB terms and conditions.

    Body:
        - agent_email: The agent's email
        - agent_name: The agent's name
    """
    try:
        data = request.get_json()
        agent_email = data.get('agent_email')
        agent_name = data.get('agent_name')

        if not agent_email:
            return jsonify({"error": "Agent email is required"}), 400

        supabase = SupabaseClientSingleton.get_instance()

        # Find user by email
        result = supabase.table('users').select('id').eq('email', agent_email).single().execute()

        if not result.data:
            return jsonify({"error": "User not found"}), 404

        user_id = result.data['id']

        # Update user's terms acceptance
        supabase.table('users').update({
            'fub_terms_accepted': True,
            'fub_terms_accepted_at': datetime.utcnow().isoformat()
        }).eq('id', user_id).execute()

        # Also record in fub_terms_acceptance table if it exists
        try:
            supabase.table('fub_terms_acceptance').upsert({
                'user_id': user_id,
                'accepted': True,
                'accepted_at': datetime.utcnow().isoformat(),
                'ip_address': request.remote_addr,
                'user_agent': request.user_agent.string[:500] if request.user_agent else None
            }).execute()
        except Exception as e:
            logger.warning(f"Could not record in fub_terms_acceptance: {e}")

        logger.info(f"User {agent_email} accepted FUB terms")

        return jsonify({"message": "Terms accepted successfully"})

    except Exception as e:
        logger.error(f"Error accepting terms: {e}")
        return jsonify({"error": str(e)}), 500


@fub_bp.route('/manual_search', methods=['POST'])
def manual_search():
    """
    Execute a manual search from the FUB embedded app.

    Body:
        - searchType: The type of search to perform
        - formData: The search parameters
    """
    try:
        data = request.get_json()
        search_type = data.get('searchType')
        form_data = data.get('formData', {})

        # Get FUB context from header
        fub_context_str = request.headers.get('X-FUB-Context', '{}')
        try:
            fub_context = json.loads(fub_context_str)
        except json.JSONDecodeError:
            fub_context = {}

        # Get user from context
        user_email = fub_context.get('user', {}).get('email')
        if not user_email:
            return jsonify({"success": False, "message": "User email not found in context"}), 400

        supabase = SupabaseClientSingleton.get_instance()

        # Find user
        user_result = supabase.table('users').select('id').eq('email', user_email).single().execute()

        if not user_result.data:
            return jsonify({"success": False, "message": "User not found"}), 404

        user_id = user_result.data['id']

        # Check if terms accepted
        if not check_fub_terms_accepted(user_id):
            return jsonify({"success": False, "message": "Please accept the terms and conditions first"}), 403

        # Determine credit type
        credit_type_map = {
            'owner_search': 'enhancement',
            'contact_enrichment': 'enhancement',
            'reverse_phone_search': 'enhancement',
            'reverse_email_search': 'enhancement',
            'criminal_history_search': 'criminal',
            'dnc_check': 'dnc',
            'advanced_person_search': 'enhancement',
        }

        credit_type = credit_type_map.get(search_type, 'enhancement')

        # Check and deduct credits
        credit_service = CreditServiceSingleton.get_instance()
        can_perform, reason = credit_service.can_perform_search(user_id, credit_type)

        if not can_perform:
            return jsonify({
                "success": False,
                "message": f"Insufficient credits: {reason}"
            }), 402

        # Perform the search
        endato = EndatoClientSingleton.get_instance()
        result = None
        error_message = None

        if search_type == 'owner_search':
            address = form_data.get('address', '')
            result = endato.owner_search(address)

        elif search_type == 'contact_enrichment':
            result = endato.contact_enrichment(
                first_name=form_data.get('firstName', ''),
                last_name=form_data.get('lastName', ''),
                phone=form_data.get('phone', ''),
                email=form_data.get('email', ''),
                address_line1=form_data.get('addressLine1', ''),
                address_line2=form_data.get('addressLine2', '')
            )

        elif search_type == 'reverse_phone_search':
            phone = form_data.get('phone', '')
            result = endato.reverse_phone(phone)

        elif search_type == 'reverse_email_search':
            email = form_data.get('email', '')
            result = endato.reverse_email(email)

        elif search_type == 'criminal_history_search':
            result = endato.criminal_search(
                first_name=form_data.get('firstName', ''),
                last_name=form_data.get('lastName', ''),
                state=form_data.get('state')
            )

        elif search_type == 'advanced_person_search':
            result = endato.person_search(
                first_name=form_data.get('firstName'),
                last_name=form_data.get('lastName'),
                city=form_data.get('city'),
                state=form_data.get('state'),
                dob=form_data.get('dob')
            )

        else:
            return jsonify({"success": False, "message": f"Unknown search type: {search_type}"}), 400

        # Check for errors
        if result and 'error' in result:
            error_message = result['error'].get('message', 'Search failed')
            return jsonify({"success": False, "message": error_message}), 400

        # Deduct credit on successful search
        success, msg, source = credit_service.use_credits(
            user_id=user_id,
            credit_type=credit_type,
            amount=1,
            description=f"FUB {search_type}"
        )

        if not success:
            logger.warning(f"Failed to deduct credit: {msg}")

        # Log the search
        try:
            lead_id = form_data.get('lead_id')
            fub_person_id = fub_context.get('person', {}).get('id')

            lookup_data = {
                'user_id': user_id,
                'search_type': search_type,
                'criteria': form_data,
                'result': result,
                'success': True,
                'usage_type': credit_type,
                'lead_id': lead_id if lead_id else None,
                'fub_person_id': str(fub_person_id) if fub_person_id else None,
            }

            supabase.table('lookup_history').insert(lookup_data).execute()

        except Exception as e:
            logger.error(f"Error logging search: {e}")

        # Post note to FUB if enabled and person ID is available
        note_posted = False
        contact_data_added = {'phones_added': 0, 'emails_added': 0}

        try:
            # Get user settings for auto-note posting
            user_settings = supabase.table('users').select(
                'auto_add_note_on_search, auto_add_phone_to_fub_on_manual_enhance, '
                'auto_add_email_to_fub_on_manual_enhance'
            ).eq('id', user_id).single().execute()

            auto_add_note = user_settings.data.get('auto_add_note_on_search', True) if user_settings.data else True
            add_phones = user_settings.data.get('auto_add_phone_to_fub_on_manual_enhance', True) if user_settings.data else True
            add_emails = user_settings.data.get('auto_add_email_to_fub_on_manual_enhance', True) if user_settings.data else True

            fub_person_id = fub_context.get('person', {}).get('id')

            if fub_person_id:
                # Post note if enabled
                if auto_add_note:
                    note_service = FUBNoteServiceSingleton.get_instance()
                    note_result = note_service.post_enrichment_note(
                        person_id=fub_person_id,
                        search_type=search_type,
                        search_data=result,
                        search_criteria=form_data
                    )
                    if note_result and 'error' not in note_result:
                        note_posted = True
                        logger.info(f"Posted enrichment note to FUB person {fub_person_id}")

                # Add discovered contact data for contact enrichment searches
                if search_type == 'contact_enrichment' and (add_phones or add_emails):
                    contact_data_added = add_enrichment_contact_data(
                        person_id=fub_person_id,
                        enrichment_data=result,
                        add_phones=add_phones,
                        add_emails=add_emails
                    )

        except Exception as e:
            logger.warning(f"Error posting note to FUB: {e}")

        return jsonify({
            "success": True,
            "message": "Search completed successfully",
            "data": result,
            "note_posted": note_posted,
            "contact_data_added": contact_data_added
        })

    except Exception as e:
        logger.error(f"Error in manual search: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@fub_bp.route('/credits', methods=['GET'])
def get_credits():
    """
    Get credit balance for the current FUB user.
    """
    try:
        # Get FUB context from header or query
        fub_context_str = request.headers.get('X-FUB-Context', '{}')
        try:
            fub_context = json.loads(fub_context_str)
        except json.JSONDecodeError:
            fub_context = {}

        user_email = fub_context.get('user', {}).get('email')
        if not user_email:
            user_email = request.args.get('email')

        if not user_email:
            return jsonify({"error": "User email not found"}), 400

        supabase = SupabaseClientSingleton.get_instance()

        # Find user
        user_result = supabase.table('users').select('id').eq('email', user_email).single().execute()

        if not user_result.data:
            return jsonify({"error": "User not found"}), 404

        user_id = user_result.data['id']

        # Get credits
        credit_service = CreditServiceSingleton.get_instance()
        credits = credit_service.get_user_credits(user_id)

        if not credits:
            return jsonify({"error": "Could not get credits"}), 500

        return jsonify({
            "success": True,
            "credits": {
                "enhancement": credits.get('total_enhancement_credits', 0),
                "criminal": credits.get('total_criminal_credits', 0),
                "dnc": credits.get('total_dnc_credits', 0)
            }
        })

    except Exception as e:
        logger.error(f"Error getting credits: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Referral Platform Action Routes
# =============================================================================

@fub_bp.route('/referral/info', methods=['GET'])
def get_referral_info():
    """
    Get referral platform info for a lead.

    Query params:
        - fub_person_id: The FUB person ID
    """
    try:
        fub_person_id = request.args.get('fub_person_id')

        if not fub_person_id:
            # Try to get from header context
            fub_context_str = request.headers.get('X-FUB-Context', '{}')
            try:
                fub_context = json.loads(fub_context_str)
                fub_person_id = fub_context.get('person', {}).get('id')
            except json.JSONDecodeError:
                pass

        if not fub_person_id:
            return jsonify({
                "success": False,
                "message": "FUB person ID is required"
            }), 400

        referral_service = ReferralActionsServiceSingleton.get_instance()
        info = referral_service.get_lead_referral_info(str(fub_person_id))

        return jsonify({
            "success": True,
            "data": info
        })

    except Exception as e:
        logger.error(f"Error getting referral info: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@fub_bp.route('/referral/update-status', methods=['POST'])
def update_referral_status():
    """
    Update lead status on the referral platform.

    Body:
        - fub_person_id: The FUB person ID
        - new_status: The new status to set
        - note: Optional note to include
    """
    try:
        data = request.get_json()
        fub_person_id = data.get('fub_person_id')
        new_status = data.get('new_status')
        note = data.get('note')

        if not fub_person_id:
            # Try to get from header context
            fub_context_str = request.headers.get('X-FUB-Context', '{}')
            try:
                fub_context = json.loads(fub_context_str)
                fub_person_id = fub_context.get('person', {}).get('id')
            except json.JSONDecodeError:
                pass

        if not fub_person_id or not new_status:
            return jsonify({
                "success": False,
                "message": "FUB person ID and new status are required"
            }), 400

        # Get user from context
        user_id = None
        fub_context_str = request.headers.get('X-FUB-Context', '{}')
        try:
            fub_context = json.loads(fub_context_str)
            user_email = fub_context.get('user', {}).get('email')
            if user_email:
                supabase = SupabaseClientSingleton.get_instance()
                user_result = supabase.table('users').select('id').eq('email', user_email).single().execute()
                if user_result.data:
                    user_id = user_result.data['id']
        except Exception:
            pass

        referral_service = ReferralActionsServiceSingleton.get_instance()
        result = referral_service.update_platform_status(
            fub_person_id=str(fub_person_id),
            new_status=new_status,
            note=note,
            user_id=user_id
        )

        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error updating referral status: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@fub_bp.route('/referral/log-commission', methods=['POST'])
def log_referral_commission():
    """
    Log a commission for a closed deal.

    Body:
        - fub_person_id: The FUB person ID
        - sale_price: The sale price
        - commission_amount: Optional - calculated if not provided
        - fee_percent: Optional - uses platform default if not provided
        - close_date: Optional close date
        - notes: Optional notes
    """
    try:
        data = request.get_json()
        fub_person_id = data.get('fub_person_id')
        sale_price = data.get('sale_price')

        if not fub_person_id:
            # Try to get from header context
            fub_context_str = request.headers.get('X-FUB-Context', '{}')
            try:
                fub_context = json.loads(fub_context_str)
                fub_person_id = fub_context.get('person', {}).get('id')
            except json.JSONDecodeError:
                pass

        if not fub_person_id or not sale_price:
            return jsonify({
                "success": False,
                "message": "FUB person ID and sale price are required"
            }), 400

        # Get user from context
        user_id = None
        fub_context_str = request.headers.get('X-FUB-Context', '{}')
        try:
            fub_context = json.loads(fub_context_str)
            user_email = fub_context.get('user', {}).get('email')
            if user_email:
                supabase = SupabaseClientSingleton.get_instance()
                user_result = supabase.table('users').select('id').eq('email', user_email).single().execute()
                if user_result.data:
                    user_id = user_result.data['id']
        except Exception:
            pass

        referral_service = ReferralActionsServiceSingleton.get_instance()
        result = referral_service.log_commission(
            fub_person_id=str(fub_person_id),
            sale_price=float(sale_price),
            commission_amount=data.get('commission_amount'),
            fee_percent=data.get('fee_percent'),
            close_date=data.get('close_date'),
            notes=data.get('notes'),
            user_id=user_id
        )

        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error logging commission: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@fub_bp.route('/referral/action-history', methods=['GET'])
def get_referral_action_history():
    """
    Get platform action history for a lead.

    Query params:
        - fub_person_id: The FUB person ID
        - limit: Optional limit (default 50)
    """
    try:
        fub_person_id = request.args.get('fub_person_id')
        limit = int(request.args.get('limit', 50))

        if not fub_person_id:
            # Try to get from header context
            fub_context_str = request.headers.get('X-FUB-Context', '{}')
            try:
                fub_context = json.loads(fub_context_str)
                fub_person_id = fub_context.get('person', {}).get('id')
            except json.JSONDecodeError:
                pass

        if not fub_person_id:
            return jsonify({
                "success": False,
                "message": "FUB person ID is required"
            }), 400

        referral_service = ReferralActionsServiceSingleton.get_instance()
        history = referral_service.get_platform_action_history(
            fub_person_id=str(fub_person_id),
            limit=limit
        )

        return jsonify({
            "success": True,
            "data": history
        })

    except Exception as e:
        logger.error(f"Error getting action history: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# =============================================================================
# AI Agent Routes
# =============================================================================

@fub_bp.route('/ai/lead-data', methods=['GET'])
def get_ai_lead_data():
    """
    Get AI conversation state, lead score, and qualification data for a lead.

    Query params:
        - fub_person_id: The FUB person ID
    """
    try:
        fub_person_id = request.args.get('fub_person_id')

        if not fub_person_id:
            fub_context_str = request.headers.get('X-FUB-Context', '{}')
            try:
                fub_context = json.loads(fub_context_str)
                fub_person_id = fub_context.get('person', {}).get('id')
            except json.JSONDecodeError:
                pass

        if not fub_person_id:
            return jsonify({
                "success": False,
                "message": "FUB person ID is required"
            }), 400

        supabase = SupabaseClientSingleton.get_instance()

        # Get AI conversation data
        result = supabase.table('ai_conversations').select(
            'id, state, lead_score, qualification_data, conversation_history, '
            'last_ai_message_at, is_active, handoff_reason, preferred_channel'
        ).eq('fub_person_id', str(fub_person_id)).eq(
            'is_active', True
        ).order('created_at', desc=True).limit(1).execute()

        if not result.data:
            # No AI conversation exists yet
            return jsonify({
                "success": True,
                "data": {
                    "ai_enabled": False,
                    "lead_score": 0,
                    "temperature": "cold",
                    "conversation_state": "none",
                    "qualification_progress": 0,
                    "extracted_info": {},
                    "last_ai_message_at": None,
                    "has_conversation": False
                }
            })

        conv = result.data[0]
        qual_data = conv.get('qualification_data', {}) or {}

        # Calculate qualification progress
        fields_present = sum(1 for v in [
            qual_data.get('timeline'),
            qual_data.get('budget'),
            qual_data.get('location'),
            qual_data.get('pre_approved'),
            qual_data.get('motivation')
        ] if v is not None)
        qual_progress = int((fields_present / 5) * 100)

        # Determine temperature
        lead_score = conv.get('lead_score', 0)
        if lead_score >= 70:
            temperature = "hot"
        elif lead_score >= 40:
            temperature = "warm"
        else:
            temperature = "cold"

        return jsonify({
            "success": True,
            "data": {
                "ai_enabled": conv.get('is_active', False),
                "lead_score": lead_score,
                "temperature": temperature,
                "conversation_state": conv.get('state', 'initial'),
                "qualification_progress": qual_progress,
                "extracted_info": qual_data,
                "last_ai_message_at": conv.get('last_ai_message_at'),
                "has_conversation": True,
                "preferred_channel": conv.get('preferred_channel'),
                "handoff_reason": conv.get('handoff_reason')
            }
        })

    except Exception as e:
        logger.error(f"Error getting AI lead data: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500


@fub_bp.route('/ai/generate-response', methods=['POST'])
def generate_ai_response():
    """
    Generate an AI response for the lead (manual assist mode).

    Body:
        - fub_person_id: The FUB person ID
        - channel: Optional channel preference (sms, email)
        - context_message: Optional recent message to respond to
    """
    try:
        data = request.get_json()
        fub_person_id = data.get('fub_person_id')
        channel = data.get('channel', 'sms')
        context_message = data.get('context_message', '')

        if not fub_person_id:
            fub_context_str = request.headers.get('X-FUB-Context', '{}')
            try:
                fub_context = json.loads(fub_context_str)
                fub_person_id = fub_context.get('person', {}).get('id')
            except json.JSONDecodeError:
                pass

        if not fub_person_id:
            return jsonify({
                "success": False,
                "message": "FUB person ID is required"
            }), 400

        # Get user context
        user_id = None
        organization_id = None
        fub_context_str = request.headers.get('X-FUB-Context', '{}')
        try:
            fub_context = json.loads(fub_context_str)
            user_email = fub_context.get('user', {}).get('email')
            if user_email:
                supabase = SupabaseClientSingleton.get_instance()
                user_result = supabase.table('users').select('id, organization_id').eq(
                    'email', user_email
                ).single().execute()
                if user_result.data:
                    user_id = user_result.data['id']
                    organization_id = user_result.data.get('organization_id')
        except Exception:
            pass

        # Get lead info from FUB context
        lead_info = fub_context.get('person', {}) if fub_context else {}
        first_name = lead_info.get('firstName', 'there')
        phone = lead_info.get('phones', [{}])[0].get('value') if lead_info.get('phones') else None
        email = lead_info.get('emails', [{}])[0].get('value') if lead_info.get('emails') else None

        # Import AI agent components
        from app.ai_agent.response_generator import AIResponseGenerator, LeadProfile
        from app.ai_agent.template_engine import ResponseTemplateEngine

        # Create lead profile
        lead_profile = LeadProfile(
            fub_person_id=int(fub_person_id),
            first_name=first_name,
            phone=phone,
            email=email,
        )

        # Get conversation context from database
        supabase = SupabaseClientSingleton.get_instance()
        conv_result = supabase.table('ai_conversations').select('*').eq(
            'fub_person_id', str(fub_person_id)
        ).eq('is_active', True).limit(1).execute()

        conversation_history = []
        current_state = 'initial'
        qualification_data = {}

        if conv_result.data:
            conv = conv_result.data[0]
            conversation_history = conv.get('conversation_history', [])
            current_state = conv.get('state', 'initial')
            qualification_data = conv.get('qualification_data', {})

        # Generate response using template engine as fallback
        template_engine = ResponseTemplateEngine()

        # Determine what type of response to generate
        if current_state == 'initial':
            response_text = template_engine.get_welcome_message(
                lead_profile={'first_name': first_name},
                agent_name='Sarah'
            )
        elif current_state == 'qualifying':
            # Get next question based on missing qualification data
            missing = []
            if not qualification_data.get('timeline'):
                missing.append('timeline')
            elif not qualification_data.get('budget'):
                missing.append('budget')
            elif not qualification_data.get('location'):
                missing.append('location')

            if missing:
                response_text = template_engine.get_qualification_question(
                    field=missing[0],
                    first_name=first_name
                )
            else:
                response_text = f"Great {first_name}! Based on what you've shared, I think we should schedule a time to chat. What does your schedule look like this week?"
        elif current_state == 'scheduling':
            response_text = f"Hi {first_name}! I'd love to set up a time to discuss your home search in more detail. Are you available for a quick call this week?"
        else:
            response_text = f"Hi {first_name}! Just checking in - how can I help you with your home search today?"

        return jsonify({
            "success": True,
            "data": {
                "response_text": response_text,
                "channel": channel,
                "conversation_state": current_state,
                "suggested_actions": [
                    {"action": "send_sms", "label": "Send via SMS"},
                    {"action": "send_email", "label": "Send via Email"},
                    {"action": "copy", "label": "Copy to Clipboard"}
                ]
            }
        })

    except Exception as e:
        logger.error(f"Error generating AI response: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500


@fub_bp.route('/ai/toggle', methods=['POST'])
def toggle_ai_agent():
    """
    Enable/disable AI auto-nurture for a specific lead.

    Body:
        - fub_person_id: The FUB person ID
        - enabled: Boolean - whether AI should be active
    """
    try:
        data = request.get_json()
        fub_person_id = data.get('fub_person_id')
        enabled = data.get('enabled', True)

        if not fub_person_id:
            fub_context_str = request.headers.get('X-FUB-Context', '{}')
            try:
                fub_context = json.loads(fub_context_str)
                fub_person_id = fub_context.get('person', {}).get('id')
            except json.JSONDecodeError:
                pass

        if not fub_person_id:
            return jsonify({
                "success": False,
                "message": "FUB person ID is required"
            }), 400

        supabase = SupabaseClientSingleton.get_instance()

        # Check if conversation exists
        result = supabase.table('ai_conversations').select('id').eq(
            'fub_person_id', str(fub_person_id)
        ).limit(1).execute()

        if result.data:
            # Update existing conversation
            supabase.table('ai_conversations').update({
                'is_active': enabled,
                'updated_at': datetime.utcnow().isoformat()
            }).eq('fub_person_id', str(fub_person_id)).execute()
        else:
            # Get user context for new conversation
            user_id = None
            organization_id = None
            fub_context_str = request.headers.get('X-FUB-Context', '{}')
            try:
                fub_context = json.loads(fub_context_str)
                user_email = fub_context.get('user', {}).get('email')
                if user_email:
                    user_result = supabase.table('users').select('id, organization_id').eq(
                        'email', user_email
                    ).single().execute()
                    if user_result.data:
                        user_id = user_result.data['id']
                        organization_id = user_result.data.get('organization_id')
            except Exception:
                pass

            # Create new conversation record
            supabase.table('ai_conversations').insert({
                'fub_person_id': str(fub_person_id),
                'user_id': user_id,
                'organization_id': organization_id,
                'state': 'initial',
                'lead_score': 0,
                'qualification_data': {},
                'conversation_history': [],
                'is_active': enabled,
                'created_at': datetime.utcnow().isoformat()
            }).execute()

        logger.info(f"AI agent {'enabled' if enabled else 'disabled'} for FUB person {fub_person_id}")

        return jsonify({
            "success": True,
            "message": f"AI agent {'enabled' if enabled else 'disabled'}",
            "ai_enabled": enabled
        })

    except Exception as e:
        logger.error(f"Error toggling AI agent: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500


# =============================================================================
# Lead Update Routes
# =============================================================================

@fub_bp.route('/lead/enrichment-info', methods=['GET'])
def get_lead_enrichment_info():
    """
    Get enrichment info for a lead (last enhanced, count, etc.).

    Query params:
        - fub_person_id: The FUB person ID
    """
    try:
        fub_person_id = request.args.get('fub_person_id')

        if not fub_person_id:
            fub_context_str = request.headers.get('X-FUB-Context', '{}')
            try:
                fub_context = json.loads(fub_context_str)
                fub_person_id = fub_context.get('person', {}).get('id')
            except json.JSONDecodeError:
                pass

        if not fub_person_id:
            return jsonify({
                "success": False,
                "message": "FUB person ID is required"
            }), 400

        supabase = SupabaseClientSingleton.get_instance()

        # Get enrichment summary
        result = supabase.table('lookup_history').select(
            'created_at, search_type, success'
        ).eq('fub_person_id', str(fub_person_id)).eq(
            'success', True
        ).order('created_at', desc=True).execute()

        if not result.data:
            return jsonify({
                "success": True,
                "data": {
                    "last_enhanced_at": None,
                    "enrichment_count": 0,
                    "last_search_type": None
                }
            })

        last_record = result.data[0]

        return jsonify({
            "success": True,
            "data": {
                "last_enhanced_at": last_record.get('created_at'),
                "enrichment_count": len(result.data),
                "last_search_type": last_record.get('search_type')
            }
        })

    except Exception as e:
        logger.error(f"Error getting enrichment info: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500


@fub_bp.route('/lead/re-enhance', methods=['POST'])
def re_enhance_lead():
    """
    Re-run contact enrichment on the lead.

    Body:
        - fub_person_id: The FUB person ID
    """
    try:
        data = request.get_json()
        fub_person_id = data.get('fub_person_id')

        # Get FUB context
        fub_context_str = request.headers.get('X-FUB-Context', '{}')
        try:
            fub_context = json.loads(fub_context_str)
            if not fub_person_id:
                fub_person_id = fub_context.get('person', {}).get('id')
        except json.JSONDecodeError:
            fub_context = {}

        if not fub_person_id:
            return jsonify({
                "success": False,
                "message": "FUB person ID is required"
            }), 400

        # Get user context
        user_email = fub_context.get('user', {}).get('email')
        if not user_email:
            return jsonify({"success": False, "message": "User email not found in context"}), 400

        supabase = SupabaseClientSingleton.get_instance()
        user_result = supabase.table('users').select('id').eq('email', user_email).single().execute()

        if not user_result.data:
            return jsonify({"success": False, "message": "User not found"}), 404

        user_id = user_result.data['id']

        # Check credits
        credit_service = CreditServiceSingleton.get_instance()
        can_perform, reason = credit_service.can_perform_search(user_id, 'enhancement')

        if not can_perform:
            return jsonify({
                "success": False,
                "message": f"Insufficient credits: {reason}"
            }), 402

        # Get lead info from FUB context
        person = fub_context.get('person', {})
        first_name = person.get('firstName', '')
        last_name = person.get('lastName', '')
        phone = person.get('phones', [{}])[0].get('value', '') if person.get('phones') else ''
        email = person.get('emails', [{}])[0].get('value', '') if person.get('emails') else ''

        # Perform enrichment
        endato = EndatoClientSingleton.get_instance()
        result = endato.contact_enrichment(
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email
        )

        if result and 'error' not in result:
            # Deduct credit
            credit_service.use_credits(
                user_id=user_id,
                credit_type='enhancement',
                amount=1,
                description='FUB re-enhancement'
            )

            # Log the search
            lookup_data = {
                'user_id': user_id,
                'search_type': 'contact_enrichment',
                'criteria': {'firstName': first_name, 'lastName': last_name, 'phone': phone, 'email': email},
                'result': result,
                'success': True,
                'usage_type': 'enhancement',
                'fub_person_id': str(fub_person_id),
            }
            supabase.table('lookup_history').insert(lookup_data).execute()

            # Add contact data to FUB if enabled
            note_service = FUBNoteServiceSingleton.get_instance()
            contact_data_added = add_enrichment_contact_data(
                person_id=fub_person_id,
                enrichment_data=result,
                add_phones=True,
                add_emails=True
            )

            # Post note to FUB
            note_service.post_enrichment_note(
                person_id=fub_person_id,
                search_type='contact_enrichment',
                search_data=result,
                search_criteria={'firstName': first_name, 'lastName': last_name}
            )

            return jsonify({
                "success": True,
                "message": "Lead re-enhanced successfully",
                "data": result,
                "contact_data_added": contact_data_added
            })
        else:
            return jsonify({
                "success": False,
                "message": result.get('error', {}).get('message', 'Enhancement failed') if result else 'Enhancement failed'
            }), 400

    except Exception as e:
        logger.error(f"Error re-enhancing lead: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500


@fub_bp.route('/lead/enrichment-history', methods=['GET'])
def get_enrichment_history():
    """
    Get enrichment history for a lead.

    Query params:
        - fub_person_id: The FUB person ID
        - limit: Optional limit (default 20)
    """
    try:
        fub_person_id = request.args.get('fub_person_id')
        limit = int(request.args.get('limit', 20))

        if not fub_person_id:
            fub_context_str = request.headers.get('X-FUB-Context', '{}')
            try:
                fub_context = json.loads(fub_context_str)
                fub_person_id = fub_context.get('person', {}).get('id')
            except json.JSONDecodeError:
                pass

        if not fub_person_id:
            return jsonify({
                "success": False,
                "message": "FUB person ID is required"
            }), 400

        supabase = SupabaseClientSingleton.get_instance()

        result = supabase.table('lookup_history').select(
            'id, search_type, created_at, success, criteria, result'
        ).eq('fub_person_id', str(fub_person_id)).order(
            'created_at', desc=True
        ).limit(limit).execute()

        # Format results with summary
        history = []
        for record in result.data or []:
            # Create a brief summary based on result
            result_data = record.get('result', {}) or {}
            summary = ""
            if record.get('search_type') == 'contact_enrichment':
                persons = result_data.get('persons', [])
                if persons:
                    phones = len(persons[0].get('phones', []))
                    emails = len(persons[0].get('emails', []))
                    summary = f"Found {phones} phone(s), {emails} email(s)"
            elif record.get('search_type') == 'dnc_check':
                on_dnc = result_data.get('on_dnc_list', False)
                summary = "On DNC list" if on_dnc else "Not on DNC list"

            history.append({
                'id': record.get('id'),
                'search_type': record.get('search_type'),
                'created_at': record.get('created_at'),
                'success': record.get('success'),
                'result_summary': summary
            })

        return jsonify({
            "success": True,
            "data": history
        })

    except Exception as e:
        logger.error(f"Error getting enrichment history: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500


@fub_bp.route('/lead/sync', methods=['POST'])
def sync_lead():
    """
    Manual sync of lead data between FUB and LeadSynergy.

    Body:
        - fub_person_id: The FUB person ID
    """
    try:
        data = request.get_json()
        fub_person_id = data.get('fub_person_id')

        if not fub_person_id:
            fub_context_str = request.headers.get('X-FUB-Context', '{}')
            try:
                fub_context = json.loads(fub_context_str)
                fub_person_id = fub_context.get('person', {}).get('id')
            except json.JSONDecodeError:
                pass

        if not fub_person_id:
            return jsonify({
                "success": False,
                "message": "FUB person ID is required"
            }), 400

        supabase = SupabaseClientSingleton.get_instance()

        # Get user context
        user_id = None
        fub_context_str = request.headers.get('X-FUB-Context', '{}')
        try:
            fub_context = json.loads(fub_context_str)
            user_email = fub_context.get('user', {}).get('email')
            if user_email:
                user_result = supabase.table('users').select('id, fub_api_key').eq(
                    'email', user_email
                ).single().execute()
                if user_result.data:
                    user_id = user_result.data['id']
        except Exception:
            pass

        # Get FUB person data from context
        person_data = fub_context.get('person', {}) if fub_context else {}

        # Update or create lead in our database
        lead_data = {
            'fub_person_id': str(fub_person_id),
            'first_name': person_data.get('firstName', ''),
            'last_name': person_data.get('lastName', ''),
            'email': person_data.get('emails', [{}])[0].get('value') if person_data.get('emails') else None,
            'phone': person_data.get('phones', [{}])[0].get('value') if person_data.get('phones') else None,
            'source': person_data.get('source', ''),
            'status': person_data.get('stage', {}).get('name') if person_data.get('stage') else None,
            'user_id': user_id,
            'updated_at': datetime.utcnow().isoformat()
        }

        # Try to update existing lead, otherwise insert
        existing = supabase.table('leads').select('id').eq(
            'fub_person_id', str(fub_person_id)
        ).limit(1).execute()

        if existing.data:
            supabase.table('leads').update(lead_data).eq(
                'fub_person_id', str(fub_person_id)
            ).execute()
        else:
            lead_data['created_at'] = datetime.utcnow().isoformat()
            supabase.table('leads').insert(lead_data).execute()

        return jsonify({
            "success": True,
            "message": "Lead synced successfully",
            "synced_at": datetime.utcnow().isoformat()
        })

    except Exception as e:
        logger.error(f"Error syncing lead: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500
