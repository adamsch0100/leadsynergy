"""
Celery application configuration for LeadSynergy.
Handles async task processing for AI agent messaging and lead sync.
"""
from celery import Celery
from celery.schedules import crontab
import os

redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
celery = Celery(
    'tasks',
    broker=redis_url,
    backend=redis_url,
    include=['app.scheduler.tasks', 'app.scheduler.ai_tasks'],
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
    # Process off-hours queued messages every 5 min during 8-10 AM Mountain Time
    'process_off_hours_queue': {
        'task': 'app.scheduler.ai_tasks.process_off_hours_queue',
        'schedule': crontab(minute='*/5', hour='15-17'),  # 8-10 AM MT = 15-17 UTC
    },
    # NBA scan: find new leads, silent leads, dormant leads, stale handoffs
    # Note: nba_hot/cold_lead_scan_interval_minutes settings exist in DB but
    # Celery beat schedules are static at module load. This runs at */15 which
    # matches the cold lead default. The per-lead 3-hour cooldown in
    # followup_manager.py prevents over-messaging regardless of scan frequency.
    'run_nba_scan': {
        'task': 'app.scheduler.ai_tasks.run_nba_scan_task',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    # Process pending scheduled messages (follow-up sequences, deferred messages)
    'process_pending_messages': {
        'task': 'app.scheduler.ai_tasks.process_pending_messages',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
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
