"""
Sync Status Tracker - Manages real-time sync status for frontend updates
"""
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from collections import defaultdict

class SyncStatusTracker:
    """Thread-safe tracker for sync progress"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SyncStatusTracker, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._lock = threading.Lock()
        self._statuses: Dict[str, Dict[str, Any]] = {}  # {sync_id: status}
        self._listeners: Dict[str, List] = defaultdict(list)  # {sync_id: [callbacks]}
        self._cancelled: Dict[str, bool] = {}  # {sync_id: cancelled}
        self._initialized = True
    
    def start_sync(self, sync_id: str, source_id: str, source_name: str, total_leads: int, user_id: str) -> None:
        """Initialize a new sync status"""
        with self._lock:
            self._statuses[sync_id] = {
                "sync_id": sync_id,
                "source_id": source_id,
                "source_name": source_name,
                "user_id": user_id,
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "total_leads": total_leads,
                "processed": 0,
                "successful": 0,
                "failed": 0,
                "skipped": 0,
                "current_lead": None,
                "messages": [],
                "details": [],
                "filter_summary": None,
                "completed_at": None,
                "error": None,
                "cancelled": False
            }
            self._cancelled[sync_id] = False
    
    def update_progress(
        self, 
        sync_id: str, 
        processed: int = None,
        successful: int = None,
        failed: int = None,
        skipped: int = None,
        current_lead: str = None,
        message: str = None,
        detail: Dict[str, Any] = None
    ) -> None:
        """Update sync progress"""
        with self._lock:
            if sync_id not in self._statuses:
                return
            
            status = self._statuses[sync_id]
            
            if processed is not None:
                status["processed"] = processed
            if successful is not None:
                status["successful"] = successful
            if failed is not None:
                status["failed"] = failed
            if skipped is not None:
                status["skipped"] = skipped
            if current_lead:
                status["current_lead"] = current_lead
            if message:
                status["messages"].append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": message
                })
                # Keep only last 100 messages
                if len(status["messages"]) > 100:
                    status["messages"] = status["messages"][-100:]
            if detail:
                status["details"].append(detail)
            
            # Notify listeners
            self._notify_listeners(sync_id, status.copy())
    
    def cancel_sync(self, sync_id: str) -> bool:
        """Cancel a running sync"""
        with self._lock:
            if sync_id not in self._statuses:
                return False
            
            status = self._statuses[sync_id]
            if status.get("status") not in ["running", "in_progress", "cancelling"]:
                return False  # Can't cancel completed/failed syncs
            
            self._cancelled[sync_id] = True
            status["cancelled"] = True
            status["status"] = "cancelling"
            status["messages"].append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "Sync cancellation requested..."
            })
            
            self._notify_listeners(sync_id, status.copy())
            return True
    
    def is_cancelled(self, sync_id: str) -> bool:
        """Check if a sync has been cancelled"""
        with self._lock:
            return self._cancelled.get(sync_id, False)
    
    def complete_sync(
        self, 
        sync_id: str, 
        results: Dict[str, Any] = None,
        error: str = None
    ) -> None:
        """Mark sync as completed"""
        with self._lock:
            if sync_id not in self._statuses:
                return
            
            status = self._statuses[sync_id]
            
            # If cancelled, mark as cancelled instead of completed
            if self._cancelled.get(sync_id, False):
                status["status"] = "cancelled"
                status["messages"].append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": "Sync cancelled by user"
                })
            else:
                status["status"] = "completed" if not error else "failed"
            
            status["completed_at"] = datetime.now(timezone.utc).isoformat()
            
            if error:
                status["error"] = error
            
            if results:
                status["successful"] = results.get("successful", 0)
                status["failed"] = results.get("failed", 0)
                status["skipped"] = results.get("filter_summary", {}).get("skipped_recently_synced", 0)
                status["details"] = results.get("details", [])
                status["filter_summary"] = results.get("filter_summary")
            
            # Final notification
            self._notify_listeners(sync_id, status.copy())
    
    def get_status(self, sync_id: str) -> Optional[Dict[str, Any]]:
        """Get current status for a sync"""
        with self._lock:
            return self._statuses.get(sync_id, {}).copy()

    def get_active_syncs(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all active (running/cancelling) syncs for a user"""
        with self._lock:
            active = []
            for sync_id, status in self._statuses.items():
                if status.get("user_id") == user_id and status.get("status") in ["running", "in_progress", "cancelling"]:
                    active.append(status.copy())
            return active
    
    def subscribe(self, sync_id: str, callback) -> None:
        """Subscribe to updates for a sync"""
        with self._lock:
            self._listeners[sync_id].append(callback)
    
    def unsubscribe(self, sync_id: str, callback) -> None:
        """Unsubscribe from updates"""
        with self._lock:
            if sync_id in self._listeners:
                try:
                    self._listeners[sync_id].remove(callback)
                except ValueError:
                    pass
    
    def _notify_listeners(self, sync_id: str, status: Dict[str, Any]) -> None:
        """Notify all listeners of a status update"""
        listeners = self._listeners.get(sync_id, [])[:]  # Copy list
        for callback in listeners:
            try:
                callback(status)
            except Exception as e:
                print(f"Error notifying listener: {e}")
    
    def cleanup_old_syncs(self, max_age_hours: int = 24) -> None:
        """Remove old completed syncs to prevent memory leaks"""
        with self._lock:
            now = datetime.now(timezone.utc)
            cutoff = now.timestamp() - (max_age_hours * 3600)
            
            to_remove = []
            for sync_id, status in self._statuses.items():
                if status.get("status") in ["completed", "failed"]:
                    completed_at = status.get("completed_at")
                    if completed_at:
                        try:
                            completed = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                            if completed.timestamp() < cutoff:
                                to_remove.append(sync_id)
                        except:
                            pass
            
            for sync_id in to_remove:
                del self._statuses[sync_id]
                if sync_id in self._listeners:
                    del self._listeners[sync_id]

# Singleton instance
_tracker = SyncStatusTracker()

def get_tracker() -> SyncStatusTracker:
    """Get the singleton tracker instance"""
    return _tracker

