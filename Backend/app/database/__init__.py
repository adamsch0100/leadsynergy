"""
Database module for LeadSynergy.

Provides database client access for all services.
"""

from app.database.supabase_client import SupabaseClientSingleton


def get_supabase_client():
    """
    Get the Supabase client instance.

    Returns:
        Supabase Client instance
    """
    return SupabaseClientSingleton.get_instance()


__all__ = [
    'SupabaseClientSingleton',
    'get_supabase_client',
]
