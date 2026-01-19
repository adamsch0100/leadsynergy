"""Session store for browser cookie persistence per agent."""

import json
import os
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class SessionStore:
    """Persist browser sessions per agent using cookies and localStorage."""

    def __init__(self, storage_dir: str = None):
        self.storage_dir = Path(storage_dir or os.getenv(
            "SESSION_STORAGE_DIR",
            os.path.join(os.path.dirname(__file__), "..", "..", "data", "fub_sessions")
        ))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Session store initialized at: {self.storage_dir}")

    def _get_session_path(self, agent_id: str) -> Path:
        """Get path for agent's session file."""
        # Sanitize agent_id for filename
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in agent_id)
        return self.storage_dir / f"{safe_id}_session.json"

    async def save_cookies(self, agent_id: str, storage_state: dict):
        """Save browser storage state (cookies + localStorage)."""
        path = self._get_session_path(agent_id)
        try:
            with open(path, 'w') as f:
                json.dump(storage_state, f, indent=2)
            logger.info(f"Session saved for agent {agent_id}")
        except Exception as e:
            logger.error(f"Failed to save session for agent {agent_id}: {e}")
            raise

    async def get_cookies(self, agent_id: str) -> Optional[dict]:
        """Load saved storage state if exists."""
        path = self._get_session_path(agent_id)
        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                logger.info(f"Session restored for agent {agent_id}")
                return data
            except Exception as e:
                logger.error(f"Failed to load session for agent {agent_id}: {e}")
                return None
        return None

    async def clear_session(self, agent_id: str):
        """Clear saved session for agent."""
        path = self._get_session_path(agent_id)
        if path.exists():
            try:
                path.unlink()
                logger.info(f"Session cleared for agent {agent_id}")
            except Exception as e:
                logger.error(f"Failed to clear session for agent {agent_id}: {e}")

    def list_sessions(self) -> list:
        """List all saved agent sessions."""
        sessions = []
        for path in self.storage_dir.glob("*_session.json"):
            agent_id = path.stem.replace("_session", "")
            sessions.append({
                "agent_id": agent_id,
                "path": str(path),
                "modified": path.stat().st_mtime
            })
        return sessions
