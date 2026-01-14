"""
Enrichment API Routes - All 7 search types for lead data enhancement.

Endpoints:
- /api/enrichment/contact - Contact enrichment
- /api/enrichment/phone - Reverse phone lookup
- /api/enrichment/email - Reverse email lookup
- /api/enrichment/criminal - Criminal history search
- /api/enrichment/dnc - DNC (Do Not Call) check
- /api/enrichment/owner - Property owner search
- /api/enrichment/person - Advanced person search
"""

from flask import request, jsonify
import logging
from datetime import datetime

from app.enrichment import enrichment_bp
from app.enrichment.endato_client import EndatoClientSingleton
from app.billing.credit_service import CreditServiceSingleton
from app.database.supabase_client import SupabaseClientSingleton

logger = logging.getLogger(__name__)


def get_user_id_from_request():
    """Extract user ID from request headers or body."""
    user_id = request.headers.get('X-User-ID')
    if not user_id and request.is_json:
        data = request.get_json(silent=True)
        if data:
            user_id = data.get('user_id')
    return user_id


def check_and_deduct_credits(user_id: str, credit_type: str, description: str = None):
    """
    Check if user has credits and deduct one.

    Args:
        user_id: The user's ID
        credit_type: 'enhancement', 'criminal', or 'dnc'
        description: Optional description for transaction

    Returns:
        tuple: (success: bool, error_response or None)
    """
    credit_service = CreditServiceSingleton.get_instance()

    # Check if user can perform search
    can_perform, reason = credit_service.can_perform_search(user_id, credit_type)
    if not can_perform:
        return False, jsonify({
            "success": False,
            "error": f"Insufficient credits: {reason}"
        }), 402  # 402 Payment Required

    # Deduct credit
    success, message, credit_source = credit_service.use_credits(
        user_id=user_id,
        credit_type=credit_type,
        amount=1,
        description=description
    )

    if not success:
        return False, jsonify({
            "success": False,
            "error": f"Failed to use credit: {message}"
        }), 500

    return True, None


def log_lookup_history(user_id: str, search_type: str, criteria: dict,
                       result: dict, success: bool, message: str = None,
                       lead_id: str = None, fub_person_id: str = None):
    """Log a search to the lookup history table."""
    try:
        supabase = SupabaseClientSingleton.get_instance()

        # Map search type to usage type for billing
        usage_type_map = {
            'contact_enrichment': 'enhancement',
            'reverse_phone': 'enhancement',
            'reverse_email': 'enhancement',
            'criminal_search': 'criminal',
            'dnc_check': 'dnc',
            'owner_search': 'enhancement',
            'person_search': 'enhancement',
        }

        lookup_data = {
            'user_id': user_id,
            'search_type': search_type,
            'criteria': criteria,
            'result': result if success else None,
            'success': success,
            'message': message,
            'usage_type': usage_type_map.get(search_type, 'enhancement'),
            'lead_id': lead_id,
            'fub_person_id': fub_person_id,
        }

        supabase.table('lookup_history').insert(lookup_data).execute()

    except Exception as e:
        logger.error(f"Error logging lookup history: {e}")
        # Don't fail the search if logging fails


# =============================================================================
# Contact Enrichment
# =============================================================================

@enrichment_bp.route('/contact', methods=['POST'])
def contact_enrichment():
    """
    Enhance contact details with additional data.

    Body:
        - first_name: Person's first name
        - last_name: Person's last name
        - phone: Phone number (optional)
        - email: Email address (optional)
        - address_line1: Street address (optional)
        - address_line2: City, state, zip (optional)

    Requires at least 2 of: full name, phone, email, or address.
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    data = request.get_json()

    # Check and deduct credits
    success, error_response = check_and_deduct_credits(
        user_id, 'enhancement', 'Contact enrichment search'
    )
    if not success:
        return error_response

    try:
        endato = EndatoClientSingleton.get_instance()

        result = endato.contact_enrichment(
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            phone=data.get('phone', ''),
            email=data.get('email', ''),
            address_line1=data.get('address_line1', ''),
            address_line2=data.get('address_line2', '')
        )

        # Check for errors in result
        if result and 'error' in result:
            log_lookup_history(
                user_id=user_id,
                search_type='contact_enrichment',
                criteria=data,
                result=result,
                success=False,
                message=result['error'].get('message'),
                lead_id=data.get('lead_id'),
                fub_person_id=data.get('fub_person_id')
            )
            return jsonify({
                "success": False,
                "error": result['error'].get('message', 'Search failed')
            }), 400

        # Log successful search
        log_lookup_history(
            user_id=user_id,
            search_type='contact_enrichment',
            criteria=data,
            result=result,
            success=True,
            lead_id=data.get('lead_id'),
            fub_person_id=data.get('fub_person_id')
        )

        return jsonify({
            "success": True,
            "data": result
        })

    except Exception as e:
        logger.error(f"Error in contact enrichment: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Reverse Phone Lookup
# =============================================================================

@enrichment_bp.route('/phone', methods=['POST'])
def reverse_phone():
    """
    Find person information from a phone number.

    Body:
        - phone: Phone number to search (any format)
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    data = request.get_json()
    phone = data.get('phone')

    if not phone:
        return jsonify({"error": "Phone number is required"}), 400

    # Check and deduct credits
    success, error_response = check_and_deduct_credits(
        user_id, 'enhancement', f'Reverse phone lookup: {phone}'
    )
    if not success:
        return error_response

    try:
        endato = EndatoClientSingleton.get_instance()
        result = endato.reverse_phone(phone)

        if result and 'error' in result:
            log_lookup_history(
                user_id=user_id,
                search_type='reverse_phone',
                criteria={'phone': phone},
                result=result,
                success=False,
                message=result['error'].get('message'),
                lead_id=data.get('lead_id'),
                fub_person_id=data.get('fub_person_id')
            )
            return jsonify({
                "success": False,
                "error": result['error'].get('message', 'Search failed')
            }), 400

        log_lookup_history(
            user_id=user_id,
            search_type='reverse_phone',
            criteria={'phone': phone},
            result=result,
            success=True,
            lead_id=data.get('lead_id'),
            fub_person_id=data.get('fub_person_id')
        )

        return jsonify({
            "success": True,
            "data": result
        })

    except Exception as e:
        logger.error(f"Error in reverse phone search: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Reverse Email Lookup
# =============================================================================

@enrichment_bp.route('/email', methods=['POST'])
def reverse_email():
    """
    Find person information from an email address.

    Body:
        - email: Email address to search
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({"error": "Email address is required"}), 400

    # Check and deduct credits
    success, error_response = check_and_deduct_credits(
        user_id, 'enhancement', f'Reverse email lookup: {email}'
    )
    if not success:
        return error_response

    try:
        endato = EndatoClientSingleton.get_instance()
        result = endato.reverse_email(email)

        if result and 'error' in result:
            log_lookup_history(
                user_id=user_id,
                search_type='reverse_email',
                criteria={'email': email},
                result=result,
                success=False,
                message=result['error'].get('message'),
                lead_id=data.get('lead_id'),
                fub_person_id=data.get('fub_person_id')
            )
            return jsonify({
                "success": False,
                "error": result['error'].get('message', 'Search failed')
            }), 400

        log_lookup_history(
            user_id=user_id,
            search_type='reverse_email',
            criteria={'email': email},
            result=result,
            success=True,
            lead_id=data.get('lead_id'),
            fub_person_id=data.get('fub_person_id')
        )

        return jsonify({
            "success": True,
            "data": result
        })

    except Exception as e:
        logger.error(f"Error in reverse email search: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Criminal History Search
# =============================================================================

@enrichment_bp.route('/criminal', methods=['POST'])
def criminal_search():
    """
    Perform a criminal background check.

    Body:
        - first_name: Person's first name (required)
        - last_name: Person's last name (required)
        - state: Two-letter state code (optional, improves accuracy)
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    data = request.get_json()
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    state = data.get('state')

    if not first_name or not last_name:
        return jsonify({"error": "First name and last name are required"}), 400

    # Check and deduct credits (criminal type)
    success, error_response = check_and_deduct_credits(
        user_id, 'criminal', f'Criminal search: {first_name} {last_name}'
    )
    if not success:
        return error_response

    try:
        endato = EndatoClientSingleton.get_instance()
        result = endato.criminal_search(first_name, last_name, state)

        criteria = {'first_name': first_name, 'last_name': last_name}
        if state:
            criteria['state'] = state

        if result and 'error' in result:
            log_lookup_history(
                user_id=user_id,
                search_type='criminal_search',
                criteria=criteria,
                result=result,
                success=False,
                message=result['error'].get('message'),
                lead_id=data.get('lead_id'),
                fub_person_id=data.get('fub_person_id')
            )
            return jsonify({
                "success": False,
                "error": result['error'].get('message', 'Search failed')
            }), 400

        log_lookup_history(
            user_id=user_id,
            search_type='criminal_search',
            criteria=criteria,
            result=result,
            success=True,
            lead_id=data.get('lead_id'),
            fub_person_id=data.get('fub_person_id')
        )

        return jsonify({
            "success": True,
            "data": result
        })

    except Exception as e:
        logger.error(f"Error in criminal search: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# DNC (Do Not Call) Check
# =============================================================================

@enrichment_bp.route('/dnc', methods=['POST'])
def dnc_check():
    """
    Check if a phone number is on the Do Not Call registry.

    Body:
        - phone: Phone number to check (required)
        - phones: List of phone numbers to check (alternative to single phone)

    Note: This is a compliance check, not an Endato API call.
    In a production system, this would check against the National DNC Registry.
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    data = request.get_json()
    phone = data.get('phone')
    phones = data.get('phones', [])

    # Handle single phone or list
    if phone:
        phones_to_check = [phone]
    elif phones:
        phones_to_check = phones
    else:
        return jsonify({"error": "Phone number(s) required"}), 400

    # Limit batch size
    if len(phones_to_check) > 100:
        return jsonify({"error": "Maximum 100 phone numbers per request"}), 400

    # Check and deduct credits (1 credit per phone)
    credit_count = len(phones_to_check)
    credit_service = CreditServiceSingleton.get_instance()

    # Check if user has enough DNC credits
    user_credits = credit_service.get_user_credits(user_id)
    if not user_credits:
        return jsonify({"error": "User not found"}), 404

    total_dnc = user_credits.get('total_dnc_credits', 0)
    if total_dnc < credit_count:
        return jsonify({
            "success": False,
            "error": f"Insufficient DNC credits. Need {credit_count}, have {total_dnc}"
        }), 402

    try:
        # Perform DNC checks
        # Note: In production, this would call the actual DNC Registry API
        # For now, we'll implement a placeholder that returns mock data
        results = []

        for phone_number in phones_to_check:
            # Clean phone number
            cleaned = ''.join(c for c in phone_number if c.isdigit())

            # Deduct credit for each check
            success, msg, source = credit_service.use_credits(
                user_id=user_id,
                credit_type='dnc',
                amount=1,
                description=f'DNC check: {phone_number}'
            )

            if not success:
                logger.warning(f"Failed to deduct DNC credit for {phone_number}: {msg}")
                continue

            # Mock DNC check result
            # In production, this would query the National DNC Registry
            dnc_result = {
                'phone': phone_number,
                'cleaned_phone': cleaned,
                'is_on_dnc': False,  # Would be actual DNC registry result
                'registry_date': None,
                'checked_at': datetime.utcnow().isoformat()
            }

            results.append(dnc_result)

        # Log the lookup
        log_lookup_history(
            user_id=user_id,
            search_type='dnc_check',
            criteria={'phones': phones_to_check},
            result={'results': results, 'count': len(results)},
            success=True,
            lead_id=data.get('lead_id'),
            fub_person_id=data.get('fub_person_id')
        )

        return jsonify({
            "success": True,
            "data": {
                "results": results,
                "total_checked": len(results),
                "credits_used": len(results)
            }
        })

    except Exception as e:
        logger.error(f"Error in DNC check: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Property Owner Search
# =============================================================================

@enrichment_bp.route('/owner', methods=['POST'])
def owner_search():
    """
    Find property owner information from an address.

    Body:
        - address: Full address (street, city, state zip)
        - searched_name: Optional name to prioritize in results
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    data = request.get_json()
    address = data.get('address')
    searched_name = data.get('searched_name')

    if not address:
        return jsonify({"error": "Address is required"}), 400

    # Check and deduct credits
    success, error_response = check_and_deduct_credits(
        user_id, 'enhancement', f'Owner search: {address}'
    )
    if not success:
        return error_response

    try:
        endato = EndatoClientSingleton.get_instance()
        result = endato.owner_search(address, searched_name)

        criteria = {'address': address}
        if searched_name:
            criteria['searched_name'] = searched_name

        if result and 'error' in result:
            log_lookup_history(
                user_id=user_id,
                search_type='owner_search',
                criteria=criteria,
                result=result,
                success=False,
                message=result['error'].get('message'),
                lead_id=data.get('lead_id'),
                fub_person_id=data.get('fub_person_id')
            )
            return jsonify({
                "success": False,
                "error": result['error'].get('message', 'Search failed')
            }), 400

        log_lookup_history(
            user_id=user_id,
            search_type='owner_search',
            criteria=criteria,
            result=result,
            success=True,
            lead_id=data.get('lead_id'),
            fub_person_id=data.get('fub_person_id')
        )

        return jsonify({
            "success": True,
            "data": result
        })

    except Exception as e:
        logger.error(f"Error in owner search: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Advanced Person Search
# =============================================================================

@enrichment_bp.route('/person', methods=['POST'])
def person_search():
    """
    Perform an advanced person search with multiple criteria.

    Body:
        - first_name: Person's first name (optional)
        - last_name: Person's last name (required)
        - city: City to search (optional)
        - state: Two-letter state code (optional)
        - age: Approximate age (optional)
        - dob: Date of birth YYYY-MM-DD (optional)
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    data = request.get_json()
    last_name = data.get('last_name')

    if not last_name:
        return jsonify({"error": "Last name is required"}), 400

    # Check and deduct credits
    success, error_response = check_and_deduct_credits(
        user_id, 'enhancement', f'Person search: {data.get("first_name", "")} {last_name}'
    )
    if not success:
        return error_response

    try:
        endato = EndatoClientSingleton.get_instance()

        result = endato.person_search(
            first_name=data.get('first_name'),
            last_name=last_name,
            city=data.get('city'),
            state=data.get('state'),
            age=data.get('age'),
            dob=data.get('dob')
        )

        criteria = {k: v for k, v in data.items() if k in ['first_name', 'last_name', 'city', 'state', 'age', 'dob'] and v}

        if result and 'error' in result:
            log_lookup_history(
                user_id=user_id,
                search_type='person_search',
                criteria=criteria,
                result=result,
                success=False,
                message=result['error'].get('message'),
                lead_id=data.get('lead_id'),
                fub_person_id=data.get('fub_person_id')
            )
            return jsonify({
                "success": False,
                "error": result['error'].get('message', 'Search failed')
            }), 400

        log_lookup_history(
            user_id=user_id,
            search_type='person_search',
            criteria=criteria,
            result=result,
            success=True,
            lead_id=data.get('lead_id'),
            fub_person_id=data.get('fub_person_id')
        )

        return jsonify({
            "success": True,
            "data": result
        })

    except Exception as e:
        logger.error(f"Error in person search: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Lookup History
# =============================================================================

@enrichment_bp.route('/history', methods=['GET'])
def get_lookup_history():
    """
    Get the user's search history.

    Query params:
        - limit: Number of records to return (default 50, max 100)
        - offset: Offset for pagination (default 0)
        - search_type: Filter by search type
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        supabase = SupabaseClientSingleton.get_instance()

        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))
        search_type = request.args.get('search_type')

        query = supabase.table('lookup_history').select('*').eq('user_id', user_id)

        if search_type:
            query = query.eq('search_type', search_type)

        result = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()

        return jsonify({
            "success": True,
            "history": result.data or [],
            "limit": limit,
            "offset": offset
        })

    except Exception as e:
        logger.error(f"Error getting lookup history: {e}")
        return jsonify({"error": str(e)}), 500
