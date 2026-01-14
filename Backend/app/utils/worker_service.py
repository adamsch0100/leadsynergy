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
    host='localhost',
    port=6379,
    password='Lancelot@123'
)

if __name__ == '__main__':
    queue_name = 'updates'
    q = Queue(queue_name, connection=redis_conn)

    # Use the custom Windows-compatible worker
    worker = WindowsWorker([q], connection=redis_conn)
    print(f"Starting Windows-compatible worker to listen on queue: {queue_name}")

    worker.work()