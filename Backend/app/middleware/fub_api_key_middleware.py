from functools import wraps
from flask import request, jsonify, g
from app.service.fub_api_key_service import FUBAPIKeyServiceSingleton

def fub_api_key_required(f):
    """Decorator that ensures the user has a valid FUB API key and injects it into the request context"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip middleware for auth routes and API key setup
        skip_paths = [
            "/auth", 
            "/api/setup", 
            "/api/supabase/auth",
            "/api/supabase/users",
            "/api/supabase/organizations",
            "/api/supabase/team-members",
            "/api/supabase/system-settings",
            "/api/supabase/settings",
            "/api/supabase/subscription",
            "/api/supabase/payment-methods",
            "/api/supabase/billing-history",
            "/api/supabase/commissions"
        ]
        
        if any(request.path.startswith(path) for path in skip_paths):
            return f(*args, **kwargs)

        # Get the current user ID - this would normally come from your auth system
        # For now, we'll look for it in the request headers or session
        user_id = request.headers.get('X-User-ID') or getattr(g, 'user_id', None)
        
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401

        # Get the current user's API key
        fub_service = FUBAPIKeyServiceSingleton.get_instance()
        api_key = fub_service.get_api_key_for_user(user_id)

        if not api_key:
            return jsonify({
                "error": "FUB API key not configured. Please configure your API key first.",
                "redirect": "/setup/api-key"
            }), 403

        # Add the API key to the request context
        g.fub_api_key = api_key
        g.user_id = user_id
        
        return f(*args, **kwargs)
    return decorated_function

def get_user_fub_api_key() -> str:
    """Helper function to get the current user's FUB API key from the request context"""
    return getattr(g, 'fub_api_key', None)

def get_current_user_id() -> str:
    """Helper function to get the current user ID from the request context"""
    return getattr(g, 'user_id', None) 