"""Session store for browser cookie persistence per agent.

Supports two storage backends:
1. Supabase (primary) - persists across Railway deployments
2. Local files (fallback) - for local development
"""

import json
import os
from pathlib import Path
from typing import Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SessionStore:
    """Persist browser sessions per agent using cookies and localStorage.

    Uses Supabase for persistent storage across deployments, with local file fallback.
    """

    def __init__(self, storage_dir: str = None, use_database: bool = True):
        """Initialize session store.

        Args:
            storage_dir: Local directory for file-based storage (fallback)
            use_database: Whether to use Supabase for storage (default True)
        """
        self.use_database = use_database
        self._supabase = None

        # Local file storage as fallback
        self.storage_dir = Path(storage_dir or os.getenv(
            "SESSION_STORAGE_DIR",
            os.path.join(os.path.dirname(__file__), "..", "..", "data", "fub_sessions")
        ))
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Try to initialize Supabase
        if self.use_database:
            try:
                from app.database.supabase_client import SupabaseClientSingleton
                self._supabase = SupabaseClientSingleton.get_instance()
                logger.info("Session store initialized with Supabase backend")
            except Exception as e:
                logger.warning(f"Failed to initialize Supabase, using file storage: {e}")
                self.use_database = False

        if not self.use_database:
            logger.info(f"Session store initialized with file backend at: {self.storage_dir}")

    def _get_session_path(self, agent_id: str) -> Path:
        """Get path for agent's session file (fallback storage)."""
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in agent_id)
        return self.storage_dir / f"{safe_id}_session.json"

    async def save_cookies(self, agent_id: str, storage_state: dict):
        """Save browser storage state (cookies + localStorage)."""
        # Try Supabase first
        if self.use_database and self._supabase:
            try:
                await self._save_to_database(agent_id, storage_state)
                logger.info(f"Session saved to database for agent {agent_id}")
                return
            except Exception as e:
                logger.warning(f"Failed to save session to database, using file: {e}")

        # Fallback to file storage
        await self._save_to_file(agent_id, storage_state)

    async def _save_to_database(self, agent_id: str, storage_state: dict):
        """Save session to Supabase."""
        # Upsert into fub_browser_sessions table
        data = {
            "agent_id": agent_id,
            "session_data": json.dumps(storage_state),
            "updated_at": datetime.utcnow().isoformat(),
        }

        # Try to upsert
        result = self._supabase.table("fub_browser_sessions").upsert(
            data,
            on_conflict="agent_id"
        ).execute()

        if not result.data:
            raise Exception("Failed to save session to database")

    async def _save_to_file(self, agent_id: str, storage_state: dict):
        """Save session to local file."""
        path = self._get_session_path(agent_id)
        try:
            with open(path, 'w') as f:
                json.dump(storage_state, f, indent=2)
            logger.info(f"Session saved to file for agent {agent_id}")
        except Exception as e:
            logger.error(f"Failed to save session to file for agent {agent_id}: {e}")
            raise

    async def get_cookies(self, agent_id: str) -> Optional[dict]:
        """Load saved storage state if exists."""
        # Try Supabase first
        if self.use_database and self._supabase:
            try:
                data = await self._load_from_database(agent_id)
                if data:
                    logger.info(f"Session restored from database for agent {agent_id}")
                    return data
            except Exception as e:
                logger.warning(f"Failed to load session from database: {e}")

        # Fallback to file storage
        return await self._load_from_file(agent_id)

    async def _load_from_database(self, agent_id: str) -> Optional[dict]:
        """Load session from Supabase."""
        result = self._supabase.table("fub_browser_sessions").select(
            "session_data"
        ).eq("agent_id", agent_id).limit(1).execute()

        if result.data and len(result.data) > 0:
            session_json = result.data[0].get("session_data")
            if session_json:
                return json.loads(session_json)
        return None

    async def _load_from_file(self, agent_id: str) -> Optional[dict]:
        """Load session from local file."""
        path = self._get_session_path(agent_id)
        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                logger.info(f"Session restored from file for agent {agent_id}")
                return data
            except Exception as e:
                logger.error(f"Failed to load session from file for agent {agent_id}: {e}")
                return None
        return None

    async def clear_session(self, agent_id: str):
        """Clear saved session for agent."""
        # Clear from database
        if self.use_database and self._supabase:
            try:
                self._supabase.table("fub_browser_sessions").delete().eq(
                    "agent_id", agent_id
                ).execute()
                logger.info(f"Session cleared from database for agent {agent_id}")
            except Exception as e:
                logger.warning(f"Failed to clear session from database: {e}")

        # Also clear from file
        path = self._get_session_path(agent_id)
        if path.exists():
            try:
                path.unlink()
                logger.info(f"Session cleared from file for agent {agent_id}")
            except Exception as e:
                logger.error(f"Failed to clear session from file for agent {agent_id}: {e}")

    def list_sessions(self) -> list:
        """List all saved agent sessions."""
        sessions = []

        # List from database
        if self.use_database and self._supabase:
            try:
                result = self._supabase.table("fub_browser_sessions").select(
                    "agent_id, updated_at"
                ).execute()
                for row in result.data or []:
                    sessions.append({
                        "agent_id": row["agent_id"],
                        "source": "database",
                        "modified": row.get("updated_at"),
                    })
            except Exception as e:
                logger.warning(f"Failed to list sessions from database: {e}")

        # Also list from files
        for path in self.storage_dir.glob("*_session.json"):
            agent_id = path.stem.replace("_session", "")
            # Avoid duplicates
            if not any(s["agent_id"] == agent_id for s in sessions):
                sessions.append({
                    "agent_id": agent_id,
                    "source": "file",
                    "modified": path.stat().st_mtime,
                })

        return sessions
