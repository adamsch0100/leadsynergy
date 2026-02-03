# Test Celery Tasks Locally

## Quick Setup

### 1. Start Redis (in terminal 1)
```bash
# If you don't have Redis installed locally, use Docker:
docker run -d -p 6379:6379 redis:latest

# Or install Redis on Windows:
# Download from: https://github.com/microsoftarchive/redis/releases
```

### 2. Set Environment Variables
```bash
# In Backend directory
cp .env.example .env  # if you haven't already

# Make sure these are set in your .env:
REDIS_URL=redis://localhost:6379/0
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
OPENROUTER_API_KEY=your_openrouter_key
FUB_API_KEY=your_fub_key
```

### 3. Start Celery Worker (in terminal 2)
```bash
cd Backend
uv run celery -A app.scheduler.celery_app worker --loglevel=info --concurrency=4
```

### 4. Start Celery Beat (in terminal 3)
```bash
cd Backend
uv run celery -A app.scheduler.celery_app beat --loglevel=info
```

### 5. Monitor Tasks
You'll see logs in real-time in the Worker terminal. Any errors will show immediately.

## Test Specific Task Manually

```python
# In Backend directory
uv run python

from app.scheduler.celery_app import celery

# Manually trigger task
result = celery.send_task('app.scheduler.ai_tasks.process_pending_messages')
print(f"Task ID: {result.id}")

# Or test send_scheduled_message directly
result = celery.send_task('app.scheduler.ai_tasks.send_scheduled_message', kwargs={
    'message_id': '8bdbbceb-557b-45ad-90d4-67af643c380c',
    'fub_person_id': 3310,
    'message_content': 'Test message',
    'channel': 'sms'
})
```

## Once Working Locally
When you see success in local logs, push to Railway with confidence!
