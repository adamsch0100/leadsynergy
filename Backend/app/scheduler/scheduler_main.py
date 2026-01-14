from app.service.redis_service import RedisServiceSingleton
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Union, Callable
from threading import Lock
import asyncio

from rq import Queue
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.models.lead import Lead
from app.webhook.webhook_processors import *

logger = logging.getLogger(__name__)


class TaskSchedulerSingleton:
    _instance = None
    _lock = Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = TaskScheduler()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            if cls._instance is not None:
                if hasattr(cls._instance, 'scheduler') and cls._instance.scheduler.running:
                    cls._instance.scheduler.shutdown()
                cls._instance = None


class TaskScheduler:
    """
    A scheduler for processing webhook tasks immediately and scheduling them for Friday runs.
    """

    def __init__(self, queue_name='updates'):
        self.redis_service = RedisServiceSingleton.get_instance()
        self._redis_conn = self.redis_service.redis

        # Initialize RQ queue
        self.queue = self.redis_service.get_queue(queue_name)

        # Initialize scheduler with Friday trigger (5 PM)
        self.scheduler = BackgroundScheduler()
        self.friday_trigger = CronTrigger(day_of_week='fri', hour=17, minute=0)
        self.scheduler.start()

        logger.info(f"TaskScheduler initialized with queue '{queue_name}'")

    # ===== Stage Update Tasks =====
    async def process_stage_task(self, lead:Lead):
        logger.info(f"Processing stage update for lead {lead.fub_person_id}")
        try:
            await process_tag_webhook(lead)
            logger.info(f"Stage processing completed for lead {lead.fub_person_id}")
            return f"Stage processed stage for lead {lead.fub_person_id}"
        except Exception as e:
            logger.error(f"Error processing stage for lead {lead.fub_person_id}: {str(e)}")
            raise

    # ===== Note Tasks =====
    async def process_note_task(self, lead:Lead, note_data:Dict[str, Any], event_type:str):
        logger.info(f"Processing note {event_type} for lead {lead.fub_person_id}")
        try:
            await process_note_webhook(lead, note_data, event_type)
            logger.info(f"Note processing completed for lead {lead.fub_person_id}")
            return f"Note {event_type} processed for lead {lead.fub_person_id}"
        except Exception as e:
            logger.error(f"Error processing note for lead {lead.fub_person_id}: {str(e)}")
            raise

    # ===== Tag Tasks =====
    async def process_tag_task(self, lead:Lead):
        logger.info(f"Processing tag for lead {lead.fub_person_id}")
        try:
            await process_tag_webhook(lead)
            logger.info(f"Tag processing completed for lead {lead.fub_person_id}")
            return f"Tag processed for lead {lead.fub_person_id}"
        except Exception as e:
            logger.error(f"Error processing tag for lead {lead.fub_person_id}: {str(e)}")
            raise

    # ===== Generic Task Scheduling Methods =====
    def enqueue_task(self, task_type: str, *args, **kwargs) -> str:
        # Select the appropriate task function
        task_function = self._get_task_function(task_type)
        task_name = f"{task_type}_task"

        # Enqueue the job
        job = self.queue.enqueue(
            f"app.scheduler.scheduler_main.TaskSchedulerSingleton.get_instance().process_{task_name}",
            args=args,
            kwargs=kwargs,
            timeout='10m'
        )

        job_id = job.get_id()

        # Extract lead ID for logging if available
        lead_id = args[0].fub_person_id if args and hasattr(args[0], 'fub_person_id') else "unknown"
        logger.info(f"Enqueued {task_type} job {job_id} for immediate processing of lead {lead_id}")

        return job_id

    def schedule_task(self, task_type: str, *args, **kwargs) -> str:
        lead_id = args[0].fub_person_id if args and hasattr(args[0], 'fub_person_id') else datetime.now().strftime('%Y%m%d%H%M%S')

        # Create unique ID for this scheduled job
        job_id = f"friday_{task_type}_{lead_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Define the function that will enqueue the job on Friday
        def _enqueue_friday_job():
            task_name = f"{task_type}_task"
            friday_job = self.queue.enqueue(
                f'app.scheduler.scheduler_main.TaskSchedulerSingleton.get_instance().process_{task_name}',
                args=args,
                kwargs=kwargs,
                timeout='10m'
            )
            logger.info(f'Friday scheduled {task_type} job executed: {friday_job.get_id()} for lead {lead_id}')
            return friday_job.get_id()

        # Add the job to the scheduler
        self.scheduler.add_job(
            _enqueue_friday_job,
            trigger=self.friday_trigger,
            id=job_id,
            replace_existing=True
        )

        logger.info(f"Scheduled {task_type} job {job_id} to run on next Friday at 5 PM")

    def process_now_and_friday(self, task_type: str, *args, **kwargs) -> Dict[str, str]:
        immediate_job_id = self.enqueue_task(task_type, *args, **kwargs)
        friday_job_id = self.schedule_task(task_type, *args, **kwargs)

        return {
            'immediate_job_id': immediate_job_id,
            'friday_job_id': friday_job_id
        }


    # ===== Specialized Convenience Methods =====
    def process_stage(self, lead: Lead, schedule_friday: bool = True) -> Union[str, Dict[str, str]]:
        if schedule_friday:
            return self.process_now_and_friday('stage', lead)
        else:
            return self.enqueue_task('stage', lead)

    def process_note(self, lead: Lead, note_data: Dict[str, Any], event_type: str, schedule_friday: bool = True) -> Union[str, Dict[str, str]]:
        if schedule_friday:
            return self.process_now_and_friday('note', lead, note_data, event_type)
        else:
            return self.enqueue_task('note', lead, note_data, event_type)

    def process_tag(self, lead: Lead, schedule_friday: bool = True) -> Union[str, Dict[str, str]]:
        if schedule_friday:
            return self.process_now_and_friday('tag', lead)
        else:
            return self.enqueue_task('tag', lead)

    # ===== Helper Methods =====
    def _get_task_function(self, task_type: str) -> Callable:
        if task_type == 'stage':
            return self.process_stage_task
        elif task_type == 'note':
            return self.process_note_task
        elif task_type == 'tag':
            return self.process_tag_task
        else:
            raise ValueError(f"Unknown task type: {task_type}")


    def shutdown(self):
        if hasattr(self, 'scheduler') and self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("TaskScheduler shutdown complete")
