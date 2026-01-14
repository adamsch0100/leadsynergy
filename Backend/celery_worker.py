from app.service.celery_service import CeleryServiceSingleton
import os
import sys

# Add the project directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Initialize Celery
celery_service = CeleryServiceSingleton.get_instance()
celery_app = celery_service.init_app()

# Import tasks to register them
from app.scheduler import tasks_old


# Helper function to clear the lock if needed
def clear_redbeat_lock():
    try:
        redis_client = celery_service.redis_service.redis
        lock_key = celery_app.conf.get("redbeat_lock_key", "redbeat:lock")

        if redis_client.exists(lock_key):
            redis_client.delete(lock_key)
            print(f"Cleared stale RedBeat lock")
            return True
    except Exception as e:
        print(f"Error clearing RedBeat lock: {e}")

    return False


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "clear_lock":
        clear_redbeat_lock()
