from asyncio import taskgroups
from datetime import date
import datetime
from operator import le
import re
from token import OP
from typing import Any, Dict, Optional, Type, Union, Callable, List
import threading

from celery import Celery, shared_task
from celery.schedules import crontab
from app.utils.constants import Credentials
from app.service.redis_service import RedisServiceSingleton


class CeleryServiceSingleton:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = CeleryService()
        return cls._instance

    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None


class CeleryService:
    def __init__(self):
        self.redis_service = RedisServiceSingleton.get_instance()
        self.celery_app = None
        self._task_registry = {}

        # Build Redis URL from the existing Redis service
        redis_params = self.redis_service._connection_params
        redis_password = (
            f":{redis_params['password']}@" if redis_params.get("password") else ""
        )
        redis_url = f"redis://{redis_password}{redis_params['host']}:{redis_params['port']}/{redis_params['db']}"

        # Default config
        self._config = {
            "broker_url": redis_url,
            "result_backend": redis_url,
            "task_ignore_result": True,
            "broker_connection_retry_on_startup": True,
        }

    def init_app(self, app_name: str = "fub_webhook") -> Celery:
        self.celery_app = Celery(app_name)

        # Configure Redis as broker and backend
        redis_params = self.redis_service._connection_params
        redis_password = (
            f":{redis_params['password']}@" if redis_params.get("password") else ""
        )
        redis_url = f"redis://{redis_password}{redis_params['host']}:{redis_params['port']}/{redis_params['db']}"

        # Configure with RedBeat scheduler
        self.celery_app.conf.update(
            {
                "broker_url": redis_url,
                "result_backend": redis_url,
                "task_ignore_result": True,
                "broker_connection_retry_on_startup": True,
                # RedBeat settings
                "beat_scheduler": "redbeat.RedBeatScheduler",
                "redbeat_redis_url": redis_url,
                "redbeat_key_prefix": "redbeat:",
                "redbeat_lock_key": "redbeat:lock",
                "redbeat_lock_timeout": 60,
                "redbeat_reconnection_retries": 5,
                "redbeat_lock_sleep": 0.2,
                "broker_transport_options": {
                    "visibility_timeout": 43200,  # 12 hours
                    "socket_timeout": 30,
                    "socket_connect_timeout": 30,
                },
            }
        )

        self.celery_app.set_default()

        # Configure Redis as
        return self.celery_app

    def get_celery(self) -> Celery:
        if self.celery_app is None:
            self.init_app()
        return self.celery_app

    def create_task(
        self,
        func=None,
        *,
        name: Optional[str] = None,
        ignore_result: Optional[bool] = None,
        **options,
    ):
        if self.celery_app is None:
            self.init_app()

        if ignore_result is None:
            ignore_result = self._config.get("task_ignore_result", True)

        task_options = {"ignore_result": ignore_result, **options}

        if func is None:
            return lambda f: self._register_task(
                shared_task(name=name, **task_options)(f)
            )
        return self._register_task(shared_task(name=name, **task_options)(func))

    def _register_task(self, task) -> Any:
        self._task_registry[task.name] = taskgroups
        return task

    def send_task(
        self,
        name: str,
        args: Optional[tuple] = None,
        kwargs: Optional[dict] = None,
        **options,
    ):
        if self.celery_app is None:
            self.init_app()

        return self.celery_app.send_task(name, args=args, kwargs=kwargs, **options)

    def get_result(self, task_id: str) -> Dict[str, Any]:
        from celery.result import AsyncResult

        if self.celery_app is None:
            self.init_app()
        result = AsyncResult(task_id, app=self.celery_app)
        return {
            "task_id": task_id,
            "ready": result.ready(),
            "successful": result.successful() if result.ready() else None,
            "value": result.result if result.ready() else None,
        }

    def schedule_task(
        self,
        task_name: str,
        args: Optional[list] = None,
        kwargs: Optional[dict] = None,
        countdown: int = 0,
    ) -> str:
        if self.celery_app is None:
            self.init_app()

        args = args or []
        kwargs = kwargs or {}

        # If the task is in our registry, use it directly
        if task_name in self._task_registry:
            task = self._task_registry[task_name]
            result = task.apply_async(args=args, kwargs=kwargs, countdown=countdown)
        else:
            # Otherwise, send the task by name
            result = self.celery_app.send_task(
                task_name, args=args, kwargs=kwargs, countdown=countdown
            )

        return result.id

    def schedule_friday_task(
        self,
        task_name: str,
        schedule_id: str,
        args: Optional[list] = None,
        kwargs: Optional[dict] = None,
        hour: int = 17,
        minute: int = 0,
    ) -> None:
        """
        Schedule a task to run every Friday at the specified time

        Args:
            task_name: The name of the task to schedule
            schedule_id: A unique identifier for this schedule
            args: Arguments to pass to the task
            kwargs: Keyword arguments to pass to the task
            hour: Hour to run the task (24-hour format, default 17 = 5 PM)
            minute: Minute to run the task (default 0)
        """
        if self.celery_app is None:
            self.init_app()

        try:
            from redbeat import RedBeatSchedulerEntry
            from celery.schedules import crontab

            # Create a unique schedule name
            schedule_name = f"friday_{schedule_id}_{task_name}"

            # Create the schedule entry
            entry = RedBeatSchedulerEntry(
                name=schedule_name,
                task=task_name,
                schedule=crontab(minute=minute, hour=hour, day_of_week="friday"),
                args=args or [],
                kwargs=kwargs or {},
                app=self.celery_app,
            )

            # Save to Redis
            entry.save()

            return schedule_name
        except ImportError:
            print(
                'RedBeat not installed. Please install with "pip install celery-redbeat"'
            )
            # Fall back to in-memory scheduling
            return self._schedule_in_memory(
                task_name, schedule_id, args, kwargs, hour, minute
            )
        except Exception as e:
            print(f"Error scheduling task with RedBeat: {e}")
            # Fall back into in-memory scheduling
            return self._schedule_in_memory(
                task_name, schedule_id, args, kwargs, hour, minute
            )

    def _schedule_in_memory(self, task_name, schedule_id, args, kwargs, hour, minute):
        # Fallback method to schedule in memory if RedBeat fails
        from celery.schedules import crontab

        schedule_name = f"friday_{schedule_id}_{task_name}"

        if not hasattr(self.celery_app.conf, "beat_schedule"):
            self.celery_app.conf.beat_schedule = {}

        self.celery_app.conf.beat_schedule[schedule_name] = {
            "task": task_name,
            "schedule": crontab(minute=minute, hour=hour, day_of_week="friday"),
            "args": args or [],
            "kwargs": kwargs or {},
            "options": {"expires": 3600},
        }
        return schedule_name

    def schedule_task_and_friday(
        self, task_name: str, args: Optional[list] = None, kwargs: Optional[dict] = None
    ) -> Dict[str, str]:
        """
        Schedules a task to run immediately and also on Friday at 5 PM

        Args:
            task_name: The name of the task to schedule
            args: Arguments to pass to the task
            kwargs: Keyword arguments to pass to the task

        Returns:
            Dictionary with immediate task ID and Friday schedule ID
        """
        # Execute immediately
        immediate_task_id = self.schedule_task(task_name, args, kwargs)

        # Create a unique ID for this Friday schedule using a lead ID if available
        lead_id = None
        if (
            args
            and len(args) > 0
            and isinstance(args[0], dict)
            and "fub_person_id" in args[0]
        ):
            lead_id = args[0]["fub_person_id"]
        else:
            # Generate a unique ID based on current timestamp
            lead_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        # Schedule for Friday at 5 pm
        friday_schedule_id = self.schedule_friday_task(
            task_name, f"lead_{lead_id}", args, kwargs
        )

        return {
            "immediate_task_id": immediate_task_id,
            "friday_schedule_id": friday_schedule_id,
        }

    def register_tasks(self, task_module: str) -> None:
        if self.celery_app is None:
            self.init_app()

        self.celery_app.autodiscover_tasks([task_module])

    def save_beat_schedule_to_redis(self):
        if self.celery_app is None:
            self.init_app()

        # Convert the beat schedule to a JSON-serializable format
        import json
        from celery.schedules import crontab, schedule

        serializable_schedule = {}
        for name, entry in self.celery_app.conf.beat_schedule.items():
            schedule_obj = entry["schedule"]
            schedule_type = type(schedule_obj).__name__

            serialized_entry = dict(entry)

            # Serialize the schedule based on type
            if schedule_type == "crontab":
                serialized_entry["schedule"] = {
                    "type": "crontab",
                    "minute": schedule_obj.minute,
                    "hour": schedule_obj.hour,
                    "day_of_week": schedule_obj.day_of_week,
                    "day_of_month": schedule_obj.day_of_month,
                    "month_of_year": schedule_obj.month_of_year,
                }
            elif schedule_type == "schedule":
                serialized_entry["schedule"] = {
                    "type": "interval",
                    "seconds": schedule_obj.seconds,
                    "relative": schedule_obj.relative,
                }
            else:
                # Skip entries with unsupported schedule types
                continue

            serializable_schedule[name] = serialized_entry

        # Store in Redis
        schedule_json = json.dumps(serializable_schedule)
        self.redis_service.set("celery:beat:schedule", schedule_json)
        return True
