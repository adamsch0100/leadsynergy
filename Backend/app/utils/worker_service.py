import sys
import os
import redis
from rq import SimpleWorker, Queue
from rq.timeouts import BaseDeathPenalty

# Add the project path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Custom worker class for Windows that disables death penalty timeouts
class WindowsWorker(SimpleWorker):
    death_penalty_class = BaseDeathPenalty

# Redis connection
redis_conn = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', '6379')),
    password=os.getenv('REDIS_PASSWORD', '')
)

if __name__ == '__main__':
    queue_name = 'updates'
    q = Queue(queue_name, connection=redis_conn)

    # Use the custom Windows-compatible worker
    worker = WindowsWorker([q], connection=redis_conn)
    print(f"Starting Windows-compatible worker to listen on queue: {queue_name}")

    worker.work()