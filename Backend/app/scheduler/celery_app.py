from celery import Celery
from celery.schedules import crontab
import os

redis_url = os.getenv('REDIS_URL', 'redis://:Lancelot@123@localhost:6379/0')
celery = Celery(
    'tasks',
    broker=redis_url,
    backend=redis_url,
    include=['app.scheduler.tasks'],
)
# crontab(hour=9, minute=0, day_of_week='fri')
# crontab(hour=9, minute=15, day_of_week='fri') -> notes
# crontab(hour=9, minute=30, day_of_week='fri') -> tags
celery.conf.beat_schedule = {
    'weekly_process_stage_updates': {
        'task': 'app.scheduler.tasks.weekly_process_stage_updates',
        'schedule': crontab(hour=9, minute=0, day_of_week='fri')
    },
    'weekly_process_notes': {
        'task': 'app.scheduler.tasks.weekly_process_notes',
        'schedule': crontab(hour=9, minute=15, day_of_week='fri'),
    },
    'weekly_process_tags': {
        'task': 'app.scheduler.tasks.weekly_process_tags',
        'schedule': crontab(hour=9, minute=30, day_of_week='fri'),
    },
    'hourly_scheduled_lead_sync': {
        'task': 'app.scheduler.tasks.process_scheduled_lead_sync',
        'schedule': crontab(minute=0),
    },
}

celery.conf.timezone = 'Asia/Manila'

# Update configuration for webhook handling
celery.conf.update(
    task_routes={
        'app.scheduler.tasks.process_webhook_task': {'queue': 'webhooks'},
        'app.scheduler.tasks.process_scheduled_webhook_batch': {'queue': 'scheduled'},
        # Your existing task routes...
    },
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Webhook-specific settings
    task_acks_late=True,  # Acknowledge tasks after completion
    worker_prefetch_multiplier=1,  # Process one task at a time for webhooks
    
    # Rate limiting per tenant
    task_annotations={
        'app.scheduler.tasks.process_webhook_task': {
            'rate_limit': '100/m',  # 100 webhooks per minute
        }
    }
)

# Define queues
celery.conf.task_queues = {
    'celery': {
        'routing_key': 'celery',
    },
    'webhooks': {
        'routing_key': 'webhook.*',
        'priority': 5,
    },
    'scheduled': {
        'routing_key': 'scheduled.*',
        'priority': 3,
    }
}
