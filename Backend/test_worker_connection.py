"""
Test Worker and Redis connectivity.
Run this to diagnose Celery issues.
"""

import os
import sys
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def test_redis_connection():
    """Test if Redis is accessible."""
    print("=" * 80)
    print("TESTING REDIS CONNECTION")
    print("=" * 80)
    print()

    redis_url = os.getenv('REDIS_URL')

    if not redis_url:
        print("[ERROR] REDIS_URL not set in environment")
        print()
        print("Railway should auto-set this when Redis is added.")
        print("Check Railway dashboard > Worker service > Variables")
        return False

    print(f"[OK] REDIS_URL is set")
    print(f"     URL: {redis_url[:30]}...")
    print()

    # Try to connect
    try:
        import redis

        # Parse URL and connect
        r = redis.from_url(redis_url, socket_connect_timeout=5)
        r.ping()

        print("[SUCCESS] Redis connection works!")
        print(f"            Redis version: {r.info()['redis_version']}")
        return True

    except ImportError:
        print("[ERROR] redis package not installed")
        print("       Run: pip install redis")
        return False

    except Exception as e:
        print(f"[ERROR] Cannot connect to Redis: {e}")
        print()
        print("Possible causes:")
        print("  - Redis service not running on Railway")
        print("  - REDIS_URL points to wrong host")
        print("  - Network/firewall blocking connection")
        return False


def test_celery_config():
    """Test Celery configuration."""
    print()
    print("=" * 80)
    print("TESTING CELERY CONFIGURATION")
    print("=" * 80)
    print()

    try:
        from app.scheduler.celery_app import celery

        print("[OK] Celery app loaded successfully")
        print(f"     Broker: {celery.conf.broker_url}")
        print(f"     Backend: {celery.conf.result_backend}")
        print()

        # Check if tasks are registered
        registered_tasks = list(celery.tasks.keys())
        ai_tasks = [t for t in registered_tasks if 'ai_tasks' in t]

        print(f"[OK] {len(ai_tasks)} AI tasks registered:")
        for task in ai_tasks[:5]:
            print(f"     - {task}")
        if len(ai_tasks) > 5:
            print(f"     ... and {len(ai_tasks) - 5} more")

        return True

    except Exception as e:
        print(f"[ERROR] Celery configuration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_worker_running():
    """Check if Celery workers are actively running."""
    print()
    print("=" * 80)
    print("CHECKING FOR ACTIVE WORKERS")
    print("=" * 80)
    print()

    try:
        from app.scheduler.celery_app import celery

        # Inspect active workers
        inspect = celery.control.inspect(timeout=5)
        active_workers = inspect.active()

        if active_workers:
            print(f"[SUCCESS] Found {len(active_workers)} active worker(s):")
            for worker_name, tasks in active_workers.items():
                print(f"  - {worker_name}: {len(tasks)} active tasks")
        else:
            print("[WARNING] No active workers found!")
            print()
            print("This means:")
            print("  - Worker service on Railway is not running")
            print("  - Worker crashed on startup")
            print("  - Worker cannot connect to Redis")
            print()
            print("Check Railway logs:")
            print("  1. Go to Railway dashboard")
            print("  2. Click on 'Worker' service")
            print("  3. Click 'Deployments' tab")
            print("  4. View latest deployment logs")
            print()
            print("Look for errors like:")
            print("  - ModuleNotFoundError")
            print("  - Connection refused")
            print("  - Import errors")

        return bool(active_workers)

    except Exception as e:
        print(f"[ERROR] Cannot inspect workers: {e}")
        print()
        print("This usually means Redis is not accessible")
        return False


def test_send_task():
    """Try to send a test task."""
    print()
    print("=" * 80)
    print("TESTING TASK DISPATCH")
    print("=" * 80)
    print()

    try:
        from app.scheduler.celery_app import celery

        # Try to send a simple task
        result = celery.send_task('app.scheduler.ai_tasks.process_pending_messages')

        print(f"[OK] Task dispatched successfully")
        print(f"     Task ID: {result.id}")
        print(f"     State: {result.state}")

        return True

    except Exception as e:
        print(f"[ERROR] Cannot dispatch task: {e}")
        return False


if __name__ == "__main__":
    print()

    # Run all tests
    redis_ok = test_redis_connection()
    celery_ok = test_celery_config()

    if redis_ok and celery_ok:
        worker_ok = test_worker_running()

        if worker_ok:
            test_send_task()
        else:
            print()
            print("=" * 80)
            print("DIAGNOSIS: Worker service is not running properly")
            print("=" * 80)
            print()
            print("Next steps:")
            print("1. Check Worker service logs in Railway dashboard")
            print("2. Verify environment variables are set on Worker service")
            print("3. Restart Worker service")

    print()
    print("=" * 80)
