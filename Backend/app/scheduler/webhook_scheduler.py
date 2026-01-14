from celery.schedules import crontab
from app.scheduler.celery_app import celery_app
from app.scheduler.tasks import process_scheduled_webhook_batch

class WebhookScheduler:
    """Manage webhook processing schedules based on user preferences"""
    
    def __init__(self):
        self.celery_app = celery_app
        
    def update_user_webhook_schedule(self, user_id, organization_id, preferences):
        """Update webhook processing schedule for a user/organization"""
        
        # Example preferences:
        # {
        #     'process_immediately': False,
        #     'batch_interval': 'hourly',  # or 'daily', 'every_15_min'
        #     'batch_time': '09:00',
        #     'timezone': 'America/New_York'
        # }
        
        schedule_name = f'webhook_batch_{organization_id}'
        
        if preferences.get('process_immediately', True):
            # Remove any scheduled tasks
            self.remove_schedule(schedule_name)
        else:
            # Create schedule based on preferences
            schedule = self.create_schedule_from_preferences(preferences)
            
            # Add to Celery beat schedule
            celery_app.conf.beat_schedule[schedule_name] = {
                'task': 'app.scheduler.tasks.process_scheduled_webhook_batch',
                'schedule': schedule,
                'args': (organization_id, preferences.get('webhook_types', ['all'])),
                'options': {
                    'queue': 'scheduled',
                    'timezone': preferences.get('timezone', 'UTC')
                }
            }
    
    def create_schedule_from_preferences(self, preferences):
        """Convert user preferences to Celery schedule"""
        interval = preferences.get('batch_interval', 'hourly')
        
        if interval == 'every_15_min':
            return crontab(minute='*/15')
        elif interval == 'hourly':
            return crontab(minute=0)
        elif interval == 'daily':
            hour, minute = preferences.get('batch_time', '09:00').split(':')
            return crontab(hour=int(hour), minute=int(minute))
        else:
            # Default to hourly
            return crontab(minute=0)
    
    def remove_schedule(self, schedule_name):
        """Remove a schedule from Celery beat"""
        if schedule_name in celery_app.conf.beat_schedule:
            del celery_app.conf.beat_schedule[schedule_name]
