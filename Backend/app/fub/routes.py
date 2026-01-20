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

    Query params (FUB format):
        - context: Base64-encoded context data
        - signature: HMAC-SHA256 signature
    Or legacy format:
        - token: Combined token (base64.signature)
    """
    try:
        # Debug logging for FUB embedded app
        logger.info(f"FUB Embedded App Request - Args: {dict(request.args)}")
        logger.info(f"FUB Embedded App Request - Headers Origin: {request.headers.get('Origin', 'none')}")

        # FUB sends context and signature as separate params
        context_b64 = request.args.get('context', '')
        signature = request.args.get('signature', '')

        # Check for direct preview mode query param (e.g., ?example=true)
        is_preview_mode = request.args.get('example', '').lower() == 'true'

        context = None
        signed_token = ''  # Initialize for template

        # Handle direct preview mode access (no context provided)
        if is_preview_mode and not context_b64:
            logger.info("FUB Preview mode - direct URL access with ?example=true")
            context = {
                'example': True,
                'user': {'email': 'preview@example.com', 'name': 'Preview User', 'id': 0},
                'person': {
                    'id': 12345,
                    'firstName': 'Jane',
                    'lastName': 'Smith',
                    'emails': [{'value': 'jane.smith@example.com'}],
                    'phones': [{'value': '(555) 123-4567'}]
                },
                'address': {},
                'email': 'jane.smith@example.com',
                'phone': '(555) 123-4567'
            }

        # First, try to decode context to check for debug/preview mode
        if not context and context_b64:
            try:
                # Add padding if needed for base64 decode
                padded = context_b64 + '=' * (4 - len(context_b64) % 4) if len(context_b64) % 4 else context_b64
                decoded_context = json.loads(base64.b64decode(padded))
                logger.info(f"FUB Decoded context keys: {decoded_context.keys() if decoded_context else 'None'}")

                # Check for FUB preview/debug mode (example=true or debugState present)
                if decoded_context.get('example') or decoded_context.get('debugState'):
                    logger.info(f"FUB Preview mode detected - debugState: {decoded_context.get('debugState')}")
                    # In preview/debug mode, use the decoded context directly
                    context = decoded_context
            except Exception as e:
                logger.warning(f"Failed to decode context for preview check: {e}")

        # If not preview mode, verify signature
        if not context and context_b64 and signature:
            signed_token = f"{context_b64}.{signature}"
            context = verify_fub_signature(signed_token)
            if not context:
                logger.warning("FUB signature verification failed")
        elif not context:
            # Fall back to legacy combined token format
            signed_token = request.args.get('token', '')
            if signed_token:
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
                # Return HTML error page with FUB SDK so FUB recognizes the app
                error_html = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>LeadSynergy - Authentication Error</title>
    <script src="https://eia.followupboss.com/embeddedApps-v1.0.1.js"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #f9fafb; }
        .error-box { text-align: center; padding: 40px; background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .error-icon { font-size: 48px; margin-bottom: 16px; }
        h1 { color: #374151; font-size: 18px; margin: 0 0 8px; }
        p { color: #6b7280; font-size: 14px; margin: 0; }
    </style>
</head>
<body>
    <div class="error-box">
        <div class="error-icon">🔐</div>
        <h1>Authentication Required</h1>
        <p>Please access this app from within Follow Up Boss.</p>
    </div>
</body>
</html>'''
                # Return 200 so FUB iframe can detect the app (error shown in content)
                return error_html, 200, {'Content-Type': 'text/html'}

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


# =============================================================================
# AI Agent Settings Routes
# =============================================================================

def _get_user_context_from_request():
    """Helper to get user_id and organization_id from request headers."""
    user_id = None
    organization_id = None
    supabase = SupabaseClientSingleton.get_instance()

    # First try X-User-ID header (from frontend)
    direct_user_id = request.headers.get('X-User-ID')
    logger.info(f"_get_user_context_from_request: X-User-ID header = {direct_user_id}")

    if direct_user_id:
        try:
            # Query user with organization_id (column now exists after migration)
            user_result = supabase.table('users').select('id, organization_id').eq('id', direct_user_id).limit(1).execute()
            logger.info(f"User query result: {user_result.data}")
            if user_result.data and len(user_result.data) > 0:
                user_id = user_result.data[0]['id']
                organization_id = user_result.data[0].get('organization_id')
                logger.info(f"Found user_id={user_id}, organization_id={organization_id}")
        except Exception as e:
            logger.error(f"Error querying user by ID: {e}")
            # Fall back to trusting the header if query fails
            user_id = direct_user_id

    # Fall back to X-FUB-Context header (from FUB embedded app)
    if not user_id:
        fub_context_str = request.headers.get('X-FUB-Context', '{}')
        try:
            fub_context = json.loads(fub_context_str)
            user_email = fub_context.get('user', {}).get('email')
            if user_email:
                user_result = supabase.table('users').select('id, organization_id').eq('email', user_email).limit(1).execute()
                if user_result.data and len(user_result.data) > 0:
                    user_id = user_result.data[0]['id']
                    organization_id = user_result.data[0].get('organization_id')
        except Exception as e:
            logger.error(f"Error querying user by email: {e}")

    logger.info(f"_get_user_context_from_request returning: user_id={user_id}, organization_id={organization_id}")
    return user_id, organization_id


@fub_bp.route('/ai/settings/fub-login', methods=['GET'])
def get_fub_login_settings():
    """
    Get FUB browser login settings for Playwright SMS.

    Returns:
        - fub_login_email: The email/username
        - fub_login_type: Login type (email, google, microsoft)
        - has_password: Whether password is configured (never return actual password)
    """
    try:
        # Get user from context
        user_id, organization_id = _get_user_context_from_request()

        supabase = SupabaseClientSingleton.get_instance()

        # Try user-level settings first
        settings_data = None
        if user_id:
            result = supabase.table('ai_agent_settings').select(
                'fub_login_email, fub_login_password, fub_login_type'
            ).eq('user_id', user_id).execute()
            if result.data:
                settings_data = result.data[0]

        # Fall back to organization settings
        if not settings_data and organization_id:
            result = supabase.table('ai_agent_settings').select(
                'fub_login_email, fub_login_password, fub_login_type'
            ).eq('organization_id', organization_id).is_('user_id', 'null').execute()
            if result.data:
                settings_data = result.data[0]

        if settings_data:
            return jsonify({
                "success": True,
                "data": {
                    "fub_login_email": settings_data.get('fub_login_email'),
                    "fub_login_type": settings_data.get('fub_login_type') or 'email',
                    "has_password": bool(settings_data.get('fub_login_password'))
                }
            })

        # Check environment variables as fallback
        import os
        env_email = os.getenv('FUB_LOGIN_EMAIL')
        env_password = os.getenv('FUB_LOGIN_PASSWORD')
        env_type = os.getenv('FUB_LOGIN_TYPE', 'email')

        return jsonify({
            "success": True,
            "data": {
                "fub_login_email": env_email,
                "fub_login_type": env_type,
                "has_password": bool(env_password),
                "source": "environment" if env_email else None
            }
        })

    except Exception as e:
        logger.error(f"Error getting FUB login settings: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500


@fub_bp.route('/ai/settings/fub-login', methods=['POST'])
def save_fub_login_settings():
    """
    Save FUB browser login settings for Playwright SMS.

    Body:
        - fub_login_email: The email/username for FUB login
        - fub_login_password: The password (will be stored, should be encrypted)
        - fub_login_type: Login type - 'email', 'google', or 'microsoft'
    """
    try:
        data = request.get_json()
        fub_login_email = data.get('fub_login_email')
        fub_login_password = data.get('fub_login_password')
        fub_login_type = data.get('fub_login_type', 'email')

        if not fub_login_email:
            return jsonify({
                "success": False,
                "message": "FUB login email is required"
            }), 400

        if fub_login_type not in ('email', 'google', 'microsoft'):
            return jsonify({
                "success": False,
                "message": "Invalid login type. Must be 'email', 'google', or 'microsoft'"
            }), 400

        # Get user from context
        user_id, organization_id = _get_user_context_from_request()

        supabase = SupabaseClientSingleton.get_instance()

        # Build update data
        update_data = {
            'fub_login_email': fub_login_email,
            'fub_login_type': fub_login_type,
            'updated_at': datetime.utcnow().isoformat()
        }

        # Only update password if provided
        if fub_login_password:
            update_data['fub_login_password'] = fub_login_password

        # Try to update existing settings or create new
        if user_id:
            existing = supabase.table('ai_agent_settings').select('id').eq('user_id', user_id).execute()
            if existing.data:
                supabase.table('ai_agent_settings').update(update_data).eq('user_id', user_id).execute()
            else:
                update_data['user_id'] = user_id
                if organization_id:
                    update_data['organization_id'] = organization_id
                supabase.table('ai_agent_settings').insert(update_data).execute()
        elif organization_id:
            existing = supabase.table('ai_agent_settings').select('id').eq(
                'organization_id', organization_id
            ).is_('user_id', 'null').execute()
            if existing.data:
                supabase.table('ai_agent_settings').update(update_data).eq(
                    'organization_id', organization_id
                ).is_('user_id', 'null').execute()
            else:
                update_data['organization_id'] = organization_id
                supabase.table('ai_agent_settings').insert(update_data).execute()
        else:
            return jsonify({
                "success": False,
                "message": "Could not determine user or organization context"
            }), 400

        # Auto-register webhooks for AI agent after saving FUB settings
        webhook_result = None
        try:
            fub_api_key = os.getenv('FUB_API_KEY') or os.getenv('FOLLOWUPBOSS_API_KEY')
            if fub_api_key:
                from app.database.fub_api_client import FUBApiClient
                client = FUBApiClient(api_key=fub_api_key)
                base_url = os.getenv(
                    'WEBHOOK_BASE_URL',
                    'https://referral-link-backend-production.up.railway.app'
                )
                webhook_result = client.ensure_ai_webhooks(base_url)
                logger.info(f"Auto-registered AI webhooks: {webhook_result}")
        except Exception as e:
            logger.warning(f"Could not auto-register webhooks: {e}")

        return jsonify({
            "success": True,
            "message": "FUB login settings saved successfully",
            "webhooks_registered": webhook_result.get('registered', []) if webhook_result else [],
            "webhooks_existing": webhook_result.get('existing', []) if webhook_result else [],
        })

    except Exception as e:
        logger.error(f"Error saving FUB login settings: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500


@fub_bp.route('/ai/settings/fub-login/test', methods=['POST'])
def test_fub_login():
    """
    Test FUB browser login with Playwright.

    This endpoint will attempt to log in to FUB using the provided or saved credentials.

    Body (optional - if not provided, uses saved settings):
        - fub_login_email: The email/username
        - fub_login_password: The password
        - fub_login_type: Login type (email, google, microsoft)

    Returns:
        - success: Whether the login was successful
        - message: Status message
        - session_valid: Whether the session is valid after login
    """
    try:
        import asyncio
        data = request.get_json() or {}

        # Get user context first (needed for both credential lookup and test session)
        user_id, organization_id = _get_user_context_from_request()

        # Get credentials from request or fall back to saved settings
        fub_login_email = data.get('fub_login_email')
        fub_login_password = data.get('fub_login_password')
        fub_login_type = data.get('fub_login_type', 'email')

        # If no credentials provided, try to get from settings
        if not fub_login_email or not fub_login_password:
            from app.ai_agent.settings_service import get_fub_browser_credentials

            # Get credentials from settings/environment
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                credentials = loop.run_until_complete(
                    get_fub_browser_credentials(
                        supabase_client=SupabaseClientSingleton.get_instance(),
                        user_id=user_id,
                        organization_id=organization_id
                    )
                )
                loop.close()
            except Exception as e:
                logger.error(f"Error getting FUB credentials: {e}")
                credentials = None

            if not credentials:
                return jsonify({
                    "success": False,
                    "message": "No FUB login credentials configured. Please save credentials first."
                }), 400

            fub_login_email = credentials.get('email')
            fub_login_password = credentials.get('password')
            fub_login_type = credentials.get('type', 'email')

        if not fub_login_email or not fub_login_password:
            return jsonify({
                "success": False,
                "message": "FUB login email and password are required"
            }), 400

        # Store in local vars for closure
        test_email = fub_login_email
        test_password = fub_login_password
        test_type = fub_login_type
        test_user_id = user_id

        # Test login with Playwright
        async def _test_login():
            from app.messaging.playwright_sms_service import PlaywrightSMSServiceSingleton

            try:
                service = await PlaywrightSMSServiceSingleton.get_instance()

                # Create a test session
                creds = {
                    'type': test_type,
                    'email': test_email,
                    'password': test_password
                }

                # Try to get/create a session (this will attempt login)
                test_agent_id = f"test_{test_user_id or 'default'}"
                session = await service.get_or_create_session(test_agent_id, creds)

                # Verify session is valid
                is_valid = await session.is_valid()

                # Clean up test session
                await service.close_session(test_agent_id)

                return {
                    "success": True,
                    "session_valid": is_valid,
                    "message": "Login successful! FUB browser session is working."
                }
            except Exception as e:
                logger.error(f"FUB login test failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "session_valid": False,
                    "message": f"Login failed: {str(e)}"
                }

        # Run the async test
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_test_login())
            loop.close()
        except RuntimeError:
            # Event loop already running (e.g., in async context)
            result = asyncio.get_event_loop().run_until_complete(_test_login())

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error testing FUB login: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "message": f"Test failed: {str(e)}"
        }), 500


@fub_bp.route('/ai/webhooks/register', methods=['POST'])
def register_ai_webhooks():
    """
    Register all required AI agent webhooks with FUB.

    This endpoint ensures all necessary webhooks are configured for the AI agent
    to receive real-time notifications about:
    - Incoming text messages (for AI response generation)
    - New leads (for welcome sequences)

    PREREQUISITES:
    1. FUB system registration at https://apps.followupboss.com/system-registration
    2. FUB_SYSTEM_KEY environment variable set

    Body (optional):
        - base_url: Override the base URL for webhook endpoints
                    (defaults to production URL)

    Returns:
        - success: Whether registration was successful
        - registered: List of newly registered webhooks
        - existing: List of already registered webhooks
        - failed: List of webhooks that failed to register
    """
    try:
        from app.database.fub_api_client import FUBApiClient

        data = request.get_json() or {}

        # Check for system key first
        fub_system_key = os.getenv('FUB_SYSTEM_KEY')
        if not fub_system_key:
            return jsonify({
                "success": False,
                "message": "FUB System Key not configured",
                "setup_required": True,
                "instructions": {
                    "step1": "Go to https://apps.followupboss.com/system-registration",
                    "step2": "Register 'LeadSynergy' as your system name",
                    "step3": "Copy the System Key you receive",
                    "step4": "Add FUB_SYSTEM_KEY=your_key_here to your environment variables",
                    "step5": "Restart the server and try again"
                }
            }), 400

        # Determine base URL for webhooks
        # Default to Railway production URL, allow override
        default_base_url = os.getenv(
            'WEBHOOK_BASE_URL',
            'https://referral-link-backend-production.up.railway.app'
        )
        base_url = data.get('base_url', default_base_url)

        # Get FUB API key
        fub_api_key = os.getenv('FUB_API_KEY') or os.getenv('FOLLOWUPBOSS_API_KEY')
        if not fub_api_key:
            return jsonify({
                "success": False,
                "message": "FUB API key not configured"
            }), 400

        # Register webhooks
        client = FUBApiClient(api_key=fub_api_key)
        result = client.ensure_ai_webhooks(base_url)

        if result.get('error'):
            return jsonify({
                "success": False,
                "message": f"Failed to register webhooks: {result['error']}",
                "result": result
            }), 500

        return jsonify({
            "success": True,
            "message": f"Webhooks configured successfully",
            "registered": result.get('registered', []),
            "existing": result.get('existing', []),
            "failed": result.get('failed', []),
            "total_active": len(result.get('webhooks', []))
        })

    except ValueError as e:
        # System key missing error from FUBApiClient
        return jsonify({
            "success": False,
            "message": str(e),
            "setup_required": True,
            "instructions": {
                "step1": "Go to https://apps.followupboss.com/system-registration",
                "step2": "Register 'LeadSynergy' as your system name",
                "step3": "Copy the System Key you receive",
                "step4": "Add FUB_SYSTEM_KEY=your_key_here to your environment variables",
                "step5": "Restart the server and try again"
            }
        }), 400
    except Exception as e:
        logger.error(f"Error registering AI webhooks: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "message": f"Registration failed: {str(e)}"
        }), 500


@fub_bp.route('/ai/webhooks', methods=['GET'])
def get_ai_webhooks():
    """
    Get all registered webhooks for the FUB account.

    Requires FUB system registration at https://apps.followupboss.com/system-registration

    Returns:
        - success: Whether the request was successful
        - webhooks: List of registered webhooks
    """
    try:
        from app.database.fub_api_client import FUBApiClient

        # Check for system key first
        fub_system_key = os.getenv('FUB_SYSTEM_KEY')
        if not fub_system_key:
            return jsonify({
                "success": False,
                "message": "FUB System Key not configured",
                "setup_required": True,
                "instructions": {
                    "step1": "Go to https://apps.followupboss.com/system-registration",
                    "step2": "Register 'LeadSynergy' as your system name",
                    "step3": "Copy the System Key you receive",
                    "step4": "Add FUB_SYSTEM_KEY=your_key_here to your environment variables",
                    "step5": "Restart the server and try again"
                }
            }), 400

        # Get FUB API key
        fub_api_key = os.getenv('FUB_API_KEY') or os.getenv('FOLLOWUPBOSS_API_KEY')
        if not fub_api_key:
            return jsonify({
                "success": False,
                "message": "FUB API key not configured"
            }), 400

        client = FUBApiClient(api_key=fub_api_key)
        webhooks = client.get_webhooks()

        # Filter to show AI-related webhooks
        ai_webhooks = [
            w for w in webhooks
            if 'LeadSynergy' in w.get('system', '') or
               w.get('event') in ('textMessagesCreated', 'peopleCreated')
        ]

        return jsonify({
            "success": True,
            "webhooks": webhooks,
            "ai_webhooks": ai_webhooks,
            "total": len(webhooks),
            "ai_total": len(ai_webhooks)
        })

    except ValueError as e:
        # System key missing error from FUBApiClient
        return jsonify({
            "success": False,
            "message": str(e),
            "setup_required": True
        }), 400
    except Exception as e:
        logger.error(f"Error getting webhooks: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "message": f"Failed to get webhooks: {str(e)}"
        }), 500


@fub_bp.route('/ai/config/status', methods=['GET'])
def get_ai_config_status():
    """
    Get the current configuration status for AI agent features.

    Returns the status of all required configurations:
    - FUB API key
    - FUB System registration (for webhooks)
    - FUB Browser login (for SMS via Playwright)

    Returns:
        - success: Always True
        - config: Dict with configuration status for each component
        - ready: Boolean indicating if all required configs are present
    """
    try:
        fub_api_key = os.getenv('FUB_API_KEY') or os.getenv('FOLLOWUPBOSS_API_KEY')
        fub_system_key = os.getenv('FUB_SYSTEM_KEY')
        fub_system_name = os.getenv('FUB_SYSTEM_NAME', 'LeadSynergy')
        fub_login_email = os.getenv('FUB_LOGIN_EMAIL')
        fub_login_password = os.getenv('FUB_LOGIN_PASSWORD')

        config_status = {
            "fub_api": {
                "configured": bool(fub_api_key),
                "description": "FUB API Key for data access"
            },
            "fub_system": {
                "configured": bool(fub_system_key),
                "system_name": fub_system_name if fub_system_key else None,
                "description": "FUB System registration for webhook API access",
                "setup_url": "https://apps.followupboss.com/system-registration" if not fub_system_key else None
            },
            "fub_browser_login": {
                "configured": bool(fub_login_email and fub_login_password),
                "email": fub_login_email if fub_login_email else None,
                "description": "FUB browser credentials for SMS via Playwright"
            }
        }

        # Check for database-stored credentials too
        try:
            user_id, organization_id = _get_user_context_from_request()
            supabase = SupabaseClientSingleton.get_instance()

            # Try user-specific settings first
            if user_id:
                result = supabase.table('ai_agent_settings').select(
                    'fub_login_email, fub_login_password'
                ).eq('user_id', user_id).execute()
                if result.data and result.data[0].get('fub_login_email') and result.data[0].get('fub_login_password'):
                    config_status["fub_browser_login"]["configured"] = True
                    config_status["fub_browser_login"]["email"] = result.data[0].get('fub_login_email')
                    config_status["fub_browser_login"]["source"] = "database"

            # If not found yet, check any available settings (single-user setup)
            if not config_status["fub_browser_login"]["configured"]:
                result = supabase.table('ai_agent_settings').select(
                    'fub_login_email, fub_login_password'
                ).limit(1).execute()
                if result.data and result.data[0].get('fub_login_email') and result.data[0].get('fub_login_password'):
                    config_status["fub_browser_login"]["configured"] = True
                    config_status["fub_browser_login"]["email"] = result.data[0].get('fub_login_email')
                    config_status["fub_browser_login"]["source"] = "database"
        except Exception as db_err:
            logger.debug(f"Error checking database credentials: {db_err}")

        # Determine overall readiness
        ready_for_sms = config_status["fub_browser_login"]["configured"]
        ready_for_webhooks = config_status["fub_api"]["configured"] and config_status["fub_system"]["configured"]

        return jsonify({
            "success": True,
            "config": config_status,
            "ready": {
                "sms_sending": ready_for_sms,
                "webhook_registration": ready_for_webhooks,
                "full_ai_agent": ready_for_sms and ready_for_webhooks
            },
            "next_steps": _get_next_steps(config_status)
        })

    except Exception as e:
        logger.error(f"Error getting config status: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "message": f"Failed to get config status: {str(e)}"
        }), 500


def _get_next_steps(config_status: dict) -> list:
    """Generate list of next steps based on missing configuration."""
    steps = []

    if not config_status["fub_api"]["configured"]:
        steps.append({
            "priority": 1,
            "action": "Add FUB_API_KEY to environment variables",
            "description": "Get your API key from FUB Admin > API"
        })

    if not config_status["fub_system"]["configured"]:
        steps.append({
            "priority": 2,
            "action": "Register LeadSynergy as a FUB System",
            "description": "Go to https://apps.followupboss.com/system-registration",
            "url": "https://apps.followupboss.com/system-registration"
        })

    if not config_status["fub_browser_login"]["configured"]:
        steps.append({
            "priority": 3,
            "action": "Configure FUB browser login credentials",
            "description": "POST to /fub/ai/settings/fub-login with your FUB login credentials"
        })

    return steps


@fub_bp.route('/ai/nba/scan', methods=['POST'])
def run_nba_scan():
    """
    Manually trigger the Next Best Action scan.

    This scans all leads and determines the next best action for each,
    prioritizing by urgency and opportunity. Use for testing or manual intervention.

    Body (optional):
        - execute: Whether to actually execute the actions (default: False for dry run)
        - batch_size: Number of leads to process (default: 50)
        - organization_id: Specific organization to scan (default: all)

    Returns:
        - success: Whether the scan completed
        - actions: List of recommended/executed actions
        - stats: Summary statistics
    """
    import asyncio

    try:
        data = request.get_json() or {}
        execute = data.get('execute', False)  # Default to dry run
        batch_size = min(data.get('batch_size', 50), 100)  # Cap at 100
        organization_id = data.get('organization_id')

        logger.info(f"NBA scan triggered: execute={execute}, batch_size={batch_size}")

        # Import and run the NBA engine
        from app.ai_agent.next_best_action import run_nba_scan

        # Run the scan
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                run_nba_scan(
                    organization_id=organization_id,
                    execute=execute,
                    batch_size=batch_size
                )
            )
        finally:
            loop.close()

        return jsonify({
            "success": True,
            "dry_run": not execute,
            "actions": result.get('actions', []),
            "stats": result.get('stats', {}),
            "total_actions": len(result.get('actions', []))
        })

    except Exception as e:
        logger.error(f"Error running NBA scan: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "message": f"NBA scan failed: {str(e)}"
        }), 500


@fub_bp.route('/ai/nba/trigger-lead', methods=['POST'])
def trigger_lead_followup():
    """
    Manually trigger follow-up for a specific lead.

    Body:
        - fub_person_id: Required - The FUB person ID
        - action_type: Optional - Type of action (default: first_contact_sms)
        - execute: Optional - Whether to execute immediately (default: False)

    Returns:
        - success: Whether the action was triggered
        - action: The recommended/executed action
    """
    import asyncio

    try:
        data = request.get_json()
        if not data or not data.get('fub_person_id'):
            return jsonify({
                "success": False,
                "message": "fub_person_id is required"
            }), 400

        fub_person_id = data['fub_person_id']
        action_type = data.get('action_type', 'first_contact_sms')
        execute = data.get('execute', False)

        logger.info(f"Manual trigger for lead {fub_person_id}: action={action_type}, execute={execute}")

        from app.ai_agent.next_best_action import get_nba_engine, RecommendedAction, ActionType

        # Map action type string to enum
        action_type_map = {
            'first_contact_sms': ActionType.FIRST_CONTACT_SMS,
            'followup_sms': ActionType.FOLLOWUP_SMS,
            'reengagement_sms': ActionType.REENGAGEMENT_SMS,
            'first_contact_email': ActionType.FIRST_CONTACT_EMAIL,
            'followup_email': ActionType.FOLLOWUP_EMAIL,
            'channel_switch_email': ActionType.CHANNEL_SWITCH_EMAIL,
        }

        action_enum = action_type_map.get(action_type, ActionType.FIRST_CONTACT_SMS)

        # Create recommended action
        action = RecommendedAction(
            fub_person_id=fub_person_id,
            action_type=action_enum,
            priority_score=100,  # High priority for manual trigger
            reason=f"Manual trigger via API",
            days_since_contact=0,
            lead_score=0,
            source="manual_trigger"
        )

        result = {"action": action.__dict__}

        if execute:
            engine = get_nba_engine()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                exec_result = loop.run_until_complete(engine.execute_action(action))
                result['execution'] = exec_result
            finally:
                loop.close()

        return jsonify({
            "success": True,
            "executed": execute,
            "result": result
        })

    except Exception as e:
        logger.error(f"Error triggering lead follow-up: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "message": f"Trigger failed: {str(e)}"
        }), 500


# =============================================================================
# TESTING ENDPOINTS
# =============================================================================

@fub_bp.route('/ai/test/simulate-webhook', methods=['POST'])
def simulate_webhook():
    """
    Simulate a webhook for testing without actual FUB event.

    This endpoint allows testing the AI agent's response generation
    without waiting for real lead messages.

    Body:
        - fub_person_id: Required - Lead to simulate message from
        - message: Required - Simulated incoming message text
        - dry_run: Optional - If true, don't actually send response (default: True)
        - channel: Optional - sms or email (default: sms)

    Returns:
        - success: Whether simulation completed
        - ai_response: The generated AI response
        - state: Current conversation state
        - would_send: Whether response would be sent (if dry_run)
    """
    import asyncio

    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "message": "Request body required"
            }), 400

        fub_person_id = data.get('fub_person_id')
        message = data.get('message', '')
        dry_run = data.get('dry_run', True)
        channel = data.get('channel', 'sms')

        if not fub_person_id:
            return jsonify({
                "success": False,
                "message": "fub_person_id is required"
            }), 400

        logger.info(f"Simulating webhook for lead {fub_person_id}: message='{message[:50]}...', dry_run={dry_run}")

        from app.ai_agent.agent_service import AIAgentService

        # Get FUB API key
        fub_api_key = os.getenv('FUB_API_KEY') or os.getenv('FOLLOWUPBOSS_API_KEY')
        if not fub_api_key:
            return jsonify({
                "success": False,
                "message": "FUB API key not configured"
            }), 400

        # Process through AI agent
        service = AIAgentService(fub_api_key=fub_api_key, user_id=None)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(
                service.process_message(
                    fub_person_id=fub_person_id,
                    incoming_message=message,
                    channel=channel,
                )
            )
        finally:
            loop.close()

        if not response:
            return jsonify({
                "success": False,
                "message": "No response generated"
            }), 500

        result = {
            "success": True,
            "dry_run": dry_run,
            "fub_person_id": fub_person_id,
            "incoming_message": message,
            "ai_response": response.message_text,
            "state": response.conversation_state,
            "lead_score": response.lead_score,
            "should_handoff": response.should_handoff,
            "handoff_reason": response.handoff_reason,
            "extracted_info": response.extracted_info,
            "would_send": not dry_run,
        }

        # If not dry run, we would send the message here
        if not dry_run:
            logger.info(f"[LIVE] Would send message to lead {fub_person_id}: {response.message_text[:50]}...")
            # TODO: Actually send via Playwright SMS service
            result["message_sent"] = True

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error simulating webhook: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "message": f"Simulation failed: {str(e)}"
        }), 500


@fub_bp.route('/ai/test/simulate-conversation', methods=['POST'])
def simulate_conversation():
    """
    Simulate a multi-turn conversation for testing.

    Body:
        - fub_person_id: Required - Lead to simulate conversation with
        - messages: Required - List of lead messages to simulate
        - dry_run: Optional - If true, don't send responses (default: True)

    Example:
        {
            "fub_person_id": 3277,
            "messages": ["", "Yes interested!", "30 days", "$500k"],
            "dry_run": true
        }

    Returns:
        - success: Whether simulation completed
        - conversation: List of message/response pairs
        - final_state: Final conversation state
        - final_score: Final lead score
    """
    import asyncio

    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "message": "Request body required"
            }), 400

        fub_person_id = data.get('fub_person_id')
        messages = data.get('messages', [])
        dry_run = data.get('dry_run', True)

        if not fub_person_id:
            return jsonify({
                "success": False,
                "message": "fub_person_id is required"
            }), 400

        if not messages:
            return jsonify({
                "success": False,
                "message": "messages list is required"
            }), 400

        logger.info(f"Simulating {len(messages)}-turn conversation for lead {fub_person_id}")

        from app.ai_agent.agent_service import AIAgentService

        fub_api_key = os.getenv('FUB_API_KEY') or os.getenv('FOLLOWUPBOSS_API_KEY')
        service = AIAgentService(fub_api_key=fub_api_key, user_id=None)

        conversation = []
        final_state = "initial"
        final_score = 50

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            for i, msg in enumerate(messages):
                response = loop.run_until_complete(
                    service.process_message(
                        fub_person_id=fub_person_id,
                        incoming_message=msg,
                        channel="sms",
                    )
                )

                if response:
                    final_state = response.conversation_state
                    final_score = response.lead_score

                    conversation.append({
                        "turn": i + 1,
                        "lead_message": msg or "(first contact)",
                        "ai_response": response.message_text,
                        "state": response.conversation_state,
                        "score": response.lead_score,
                        "should_handoff": response.should_handoff,
                    })

                    if response.should_handoff:
                        logger.info(f"Handoff triggered at turn {i+1}")
                        break
                else:
                    conversation.append({
                        "turn": i + 1,
                        "lead_message": msg,
                        "ai_response": None,
                        "error": "No response generated",
                    })
        finally:
            loop.close()

        return jsonify({
            "success": True,
            "dry_run": dry_run,
            "fub_person_id": fub_person_id,
            "conversation": conversation,
            "total_turns": len(conversation),
            "final_state": final_state,
            "final_score": final_score,
        })

    except Exception as e:
        logger.error(f"Error simulating conversation: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "message": f"Simulation failed: {str(e)}"
        }), 500


@fub_bp.route('/ai/health', methods=['GET'])
def get_ai_health():
    """
    Get health status of the AI agent system.

    Checks all critical dependencies and returns their status.

    Returns:
        - status: Overall health status (healthy, degraded, unhealthy)
        - checks: Individual component health checks
        - metrics: System metrics (if available)
    """
    import time

    checks = {}
    overall_healthy = True

    # Check 1: Database connectivity
    try:
        start = time.time()
        supabase = SupabaseClientSingleton.get_instance()
        result = supabase.table('ai_agent_settings').select('id').limit(1).execute()
        latency = int((time.time() - start) * 1000)
        checks["database"] = {
            "status": "ok",
            "latency_ms": latency,
        }
    except Exception as e:
        checks["database"] = {
            "status": "error",
            "error": str(e),
        }
        overall_healthy = False

    # Check 2: FUB API
    fub_api_key = os.getenv('FUB_API_KEY') or os.getenv('FOLLOWUPBOSS_API_KEY')
    if fub_api_key:
        try:
            import requests
            from requests.auth import HTTPBasicAuth
            start = time.time()
            resp = requests.get(
                'https://api.followupboss.com/v1/me',
                auth=HTTPBasicAuth(fub_api_key, ''),
                timeout=10
            )
            latency = int((time.time() - start) * 1000)
            checks["fub_api"] = {
                "status": "ok" if resp.status_code == 200 else "error",
                "latency_ms": latency,
                "status_code": resp.status_code,
            }
            if resp.status_code != 200:
                overall_healthy = False
        except Exception as e:
            checks["fub_api"] = {
                "status": "error",
                "error": str(e),
            }
            overall_healthy = False
    else:
        checks["fub_api"] = {
            "status": "not_configured",
        }
        overall_healthy = False

    # Check 3: LLM API (OpenRouter or Anthropic)
    openrouter_key = os.getenv('OPENROUTER_API_KEY')
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    if openrouter_key or anthropic_key:
        checks["llm_api"] = {
            "status": "configured",
            "provider": "openrouter" if openrouter_key else "anthropic",
        }
    else:
        checks["llm_api"] = {
            "status": "not_configured",
        }
        overall_healthy = False

    # Check 4: Webhook registration
    fub_system_key = os.getenv('FUB_SYSTEM_KEY')
    checks["webhook_system"] = {
        "status": "configured" if fub_system_key else "not_configured",
    }

    # Check 5: FUB browser credentials
    try:
        if checks.get("database", {}).get("status") == "ok":
            result = supabase.table('ai_agent_settings').select(
                'fub_login_email, fub_login_password'
            ).limit(1).execute()
            has_creds = (result.data and
                        result.data[0].get('fub_login_email') and
                        result.data[0].get('fub_login_password'))
            checks["fub_browser_login"] = {
                "status": "configured" if has_creds else "not_configured",
            }
        else:
            checks["fub_browser_login"] = {"status": "unknown"}
    except Exception:
        checks["fub_browser_login"] = {"status": "unknown"}

    # Determine overall status
    if overall_healthy:
        status = "healthy"
    elif checks.get("database", {}).get("status") == "ok":
        status = "degraded"
    else:
        status = "unhealthy"

    # Get metrics if database is healthy
    metrics = {}
    if checks.get("database", {}).get("status") == "ok":
        try:
            # Count messages in last 24 hours
            from datetime import datetime, timedelta
            yesterday = (datetime.utcnow() - timedelta(hours=24)).isoformat()
            msg_result = supabase.table('ai_message_log').select(
                'id', count='exact'
            ).gte('created_at', yesterday).execute()
            metrics["messages_24h"] = msg_result.count if hasattr(msg_result, 'count') else len(msg_result.data)

            # Count active conversations
            conv_result = supabase.table('ai_conversations').select(
                'id', count='exact'
            ).eq('is_active', True).execute()
            metrics["active_conversations"] = conv_result.count if hasattr(conv_result, 'count') else len(conv_result.data)
        except Exception:
            pass

    return jsonify({
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
        "metrics": metrics,
    })
