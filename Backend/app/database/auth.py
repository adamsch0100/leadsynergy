"""
Supabase authentication utility module.

Provides a helper for creating authenticated Supabase clients.
All credentials must come from environment variables.
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


def get_supabase_client() -> Client:
    """Create and return a Supabase client using environment variables."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_JWT_SECRET")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SECRET_KEY must be set in environment variables")
    return create_client(supabase_url=url, supabase_key=key)
