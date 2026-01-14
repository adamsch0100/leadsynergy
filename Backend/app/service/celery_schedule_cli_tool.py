from operator import add
import sys
import argparse
import os
import json
from datetime import date, datetime
from httpx import get, head
from tabulate import tabulate

from redis_service import RedisServiceSingleton

# Add the project root directory to Python's path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
sys.path.insert(0, project_root)

try:
    from app.service.celery_service import CeleryServiceSingleton
    from app.service.redis_service import RedisServiceSingleton
except ImportError as e:
    print(f"Error: {e}")
    sys.exit(1)

celery_service = CeleryServiceSingleton.get_instance()
redis_service = RedisServiceSingleton.get_instance()


def check_redis_connection():
    # Simple ping to check connection
    try:
        result = redis_service.is_connected()
        if result:
            print("✓ Successfully connected to Redis server")
            print(f"  Host: {redis_service._connection_params['host']}")
            print(f"  Port: {redis_service._connection_params['port']}")
            print(f"  Database: {redis_service._connection_params['db']}")
            return True
    except Exception as e:
        print(f"✗ Failed to connect to Redis: {e}")
        return False


def list_redbeat_schedules():
    try:
        if not check_redis_connection():
            return

        # Get all RedBeat schedule keys
        redbeat_keys = redis_service.keys("redbeat:* ")

        # Filter for actual schedule entries (not lock keys or other metadata)
        schedule_keys = [k for k in redbeat_keys if ":schedule:" in k]

        if not schedule_keys:
            print("No RedBeat schedules found in Redis")
            return

        table_data = []
        for key in schedule_keys:
            try:
                # Get schedule data
                schedule_data = redis_service.get(key)
                if not schedule_data:
                    continue

                # Parse the JSON data
                schedule_entry = json.loads(schedule_data)

                # Extract name from the key
                name = key.split(":")[-1]

                # Extract task name
                task = schedule_entry.get("task", "Unknown")

                # Process schedule information
                schedule = schedule_entry.get("schedule", {})
                schedule_type = None
                schedule_details = "Unknown"

                if isinstance(schedule, dict):
                    schedule_type = schedule.get("type")

                    if schedule_type == "crontab":
                        minute = schedule.get("minute", "*")
                        hour = schedule.get("hour", "*")
                        day_of_week = schedule.get("day_of_week", "*")

                        schedule_details = f"crontab(minute={minute}, hour={hour}, day_of_week={day_of_week})"

                    elif schedule_type == "interval":
                        every = schedule.get("every", 0)
                        schedule_details = f"every {every} seconds"

                    else:
                        schedule_details = json.dumps(schedule)
                else:
                    schedule_details = str(schedule)

                # Extract last run information
                last_run_at = schedule_entry.get("last_run_at", "Never")
                if last_run_at != "Never" and isinstance(last_run_at, (int, float)):
                    try:
                        last_run_at = datetime.fromtimestamp(last_run_at).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                    except:
                        pass

                # Extract args and kwargs
                args = schedule_entry.get("args", [])
                kwargs = schedule_entry.get("kwargs", {})

                # Format for display
                args_display = str(args)
                if len(args_display) > 30:
                    args_display = args_display[:27] + "..."

                kwargs_display = str(kwargs)
                if len(kwargs_display) > 30:
                    kwargs_display = kwargs_display[:27] + "..."

                # Check if this is a Friday task
                is_friday = "No"
                if "friday" in name.lower():
                    is_friday = "Yes"
                elif schedule_type == "crontab" and isinstance(schedule, dict):
                    day_of_week = schedule.get("day_of_week", "")
                    if "friday" in str(day_of_week).lower() or "5" in str(day_of_week):
                        is_friday = "Yes"

                row = [
                    name,
                    task,
                    schedule_details,
                    is_friday,
                    last_run_at,
                    args_display,
                    kwargs_display,
                ]

                table_data.append(row)

            except Exception as e:
                print(f"Error processing key {key}: {e}")
                continue

        # Sort by modest
        table_data.sort(key=lambda x: x[0])

        print(
            tabulate(
                table_data,
                headers=[
                    "Name",
                    "Task",
                    "Schedule",
                    "Friday Task",
                    "Last Run",
                    "Args",
                    "Kwargs",
                ],
                tablefmt="grid",
            )
        )

        print(f"\nTotal scheduled tasks: {len(table_data)}")

    except Exception as e:
        print(f"Error listing RedBeat schedules: {e}")


def list_schedules(verbose=False):
    if celery_service.celery_app is None:
        celery_service.init_app()

    beat_schedule = celery_service.celery_app.conf.beat_schedule

    if not beat_schedule:
        print("No scheduled tasks found")
        return

    table_data = []

    for schedule_name, schedule_data in beat_schedule.items():
        schedule_type = type(schedule_data["schedule"]).__name__

        # Format schedule details
        if schedule_type == "crontab":
            schedule_details = f"crontab(minute='{schedule_data['schedule'].minute}', hour='{schedule_data['schedule'].hour}')"
            schedule_details += (
                f"day_of_week='{schedule_data['schedule'].day_of_week}',"
            )
            schedule_details += (
                f"day_of_month='{schedule_data['schedule'].day_of_month}'"
            )
            schedule_details += (
                f"month_of_year='{schedule_data['schedule'].month_of_year}'"
            )
        elif schedule_type == "interval":
            schedule_details = f"every {schedule_data['schedule'].seconds} seconds"
        else:
            schedule_details = str(schedule_data["schedule"])

        # Format args and kwargs
        args = schedule_data.get("args", [])
        kwargs = schedule_data.get("kwargs", {})

        # Format args for display (truncate if too long)
        args_display = str(args)
        if len(args_display) > 30 and not verbose:
            args_display = args_display[:27] + "..."

        # Format kwargs for display (truncate if too long)
        kwargs_display = str(kwargs)
        if len(kwargs_display) > 30 and not verbose:
            kwargs_display = kwargs_display[:27] + "..."

        # Check if task is Friday schedule
        is_friday = (
            "Yes"
            if "friday" in schedule_name.lower()
            or (
                schedule_type == "crontab"
                and "friday" in schedule_data["schedule"].day_of_week.lower()
            )
            else "No"
        )

        row = [
            schedule_name,
            schedule_data["task"],
            schedule_details,
            is_friday,
            args_display,
            kwargs_display,
        ]

        table_data.append(row)

    # Sort by schedule name
    table_data.sort(key=lambda x: x[0])

    print(
        tabulate(
            table_data,
            headers=[
                "Schedule Name",
                "Task",
                "Schedule",
                "Friday Task",
                "Args",
                "Kwargs",
            ],
            tablefmt="grid",
        )
    )

    print(f"\nTotal scheduled tasks: {len(beat_schedule)}")


def show_schedule(schedule_name):
    if celery_service.celery_app is None:
        celery_service.init_app()

    beat_schedule = celery_service.celery_app.conf.beat_schedule

    if not schedule_name in beat_schedule:
        print(f"No schedule found with name: {schedule_name}")
        return

    schedule_data = beat_schedule[schedule_name]

    print("\n=== Schedule Details ===")
    print(f"Name: {schedule_name}")
    print(f"Task: {schedule_data['task']}")

    # Schedule details
    schedule_type = type(schedule_data["schedule"]).__name__
    print(f"Schedule Type: {schedule_type}")

    if schedule_type == "crontab":
        crontab = schedule_data["schedule"]
        print(f"Minute: {crontab.minute}")
        print(f"Hour: {crontab.hour}")
        print(f"Day of Week: {crontab.day_of_week}")
        print(f"Day of Month: {crontab.day_of_month}")
        print(f"Month of Year: {crontab.month_of_year}")
    elif schedule_type == "interval":
        interval = schedule_data["schedule"]
        print(f"Every: {interval.seconds} seconds")
    else:
        print(f"Schedule: {schedule_data['schedule']}")

    # Arguments
    print("\nArguments:")
    if "args" in schedule_data and schedule_data["args"]:
        for i, arg in enumerate(schedule_data["args"]):
            print(f" [{i}]: {json.dumps(arg, indent=2)}")
    else:
        print("  None")

    # Keyword arguments
    print("\nKeyword Arguments:")
    if "kwargs" in schedule_data and schedule_data["kwargs"]:
        for key, value in schedule_data["kwargs"].items():
            print(f"  {key}: {json.dumps(value, indent=2)}")
    else:
        print("  None")

    # Options
    print("\nOptions:")
    if "options" in schedule_data and schedule_data["options"]:
        for key, value in schedule_data["options"].items():
            print(f"  {key}: {value}")
    else:
        print("  None")


def add_friday_schedule(task_name, lead_id, args=None, kwargs=None, hour=17, minute=0):
    if not task_name:
        print("Task name is required")
        return

    try:
        # Initialize Celery app if not already initialized
        if celery_service.celery_app is None:
            celery_service.init_app()

        # Parse args if provided as JSON string
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except:
                print("Error parsing args JSON. Using empty list")
                args = []

        # Parse kwargs if provided as JSON string
        if isinstance(kwargs, str):
            try:
                args = json.loads(args)
            except:
                print("Error parsing args JSON. Using empty list")
                kwargs = {}

        # Generate a unique ID if lead_id not provided
        if not lead_id:
            lead_id = datetime.now().strftime("%Y%m%d%H%M%S")

        # Schedule the task
        schedule_id = celery_service.schedule_friday_task(
            task_name,
            f"lead_{lead_id}",
            args=args or [],
            kwargs=kwargs or {},
            hour=hour,
            minute=minute,
        )

        print(
            f"✓ Successfully scheduled tasl '{task_name}' for Friday at {hour:02d}:{minute:02d}"
        )
        print(f"  Schedule ID: {schedule_id}")

    except Exception as e:
        print(f"✗ Failed to add schedule: {e}")


def remove_schedule(schedule_name):
    if celery_service.celery_app is None:
        celery_service.init_app()

    beat_schedule = celery_service.celery_app.conf.beat_schedule

    if not schedule_name in beat_schedule:
        print(f"None schedule found with name: {schedule_name}")
        return

    confirm = input(
        f"Are you sure you want to remove schedule '{schedule_name}'? (y/n)"
    )
    if confirm.lower() != "y":
        print("Operation cancelled")
        return

    try:
        # Remove the schedule
        del beat_schedule[schedule_name]

        # Update Celery configuration
        celery_service.celery_app.conf.beat_schedule = beat_schedule

        print(f"✓ Successfully removed schedule '{schedule_name}'")
    except Exception as e:
        print(f"✗ Failed to remove schedule: {e}")


def clear_schedules():
    if celery_service.celery_app is None:
        celery_service.init_app()

    beat_schedule = celery_service.celery_app.conf.beat_schedule

    if not beat_schedule:
        print("No scheduled tasks found")
        return

    confirm = input(
        f"Are you sure you want to clear all {len(beat_schedule)} schedules? (y/n)"
    )
    if confirm.lower() != "y":
        print("Operation cancelled")
        return

    try:
        # Clear the schedule
        celery_service.celery_app.conf.beat_schedule = {}

        print(f"✓ Successfully cleared all schedules")
    except Exception as e:
        print("✗ Failed to clear schedules: {e}")


def list_tasks():
    if celery_service.celery_app is None:
        celery_service.init_app()

    # Get the task registry
    task_registry = celery_service._task_registry

    if not task_registry:
        print("No tasks registered. Make sure tasks are imported")
        return

    table_data = []
    for task_name, task in task_registry.items():
        ignore_result = getattr(task, "ignore_result", True)

        row = [
            task_name,
            "No" if ignore_result else "Yes",
            task.__doc__.strip() if task.__doc__ else "No documentation",
        ]

        table_data.append(row)

    # Sort by task name
    table_data.sort(key=lambda x: x[0])

    print(
        tabulate(
            table_data,
            headers=["Task Name", "Returns Result", "Description"],
            tablefmt="grid",
        )
    )

    print(f"\nTotal registered tasks: {len(task_registry)}")


def clear_redbeat_lock():
    try:
        # Connect to Redis
        if not check_redis_connection():
            return

        # Delete the lock key
        lock_key = "redbeat:lock"
        if redis_service.exists(lock_key):
            redis_service.delete(lock_key)
            print(f"✓ Successfully cleared RedBeat lock")
        else:
            print("No RedBeat lock found")

    except Exception as e:
        print(f"✗ Error clearing RedBeat lock: {e}")


def main():
    parser = argparse.ArgumentParser(description="Celery Schedule Management Utility")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # List command
    list_parser = subparsers.add_parser("list", help="List all scheduled tasks")
    list_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show full details"
    )

    # Show command
    show_parser = subparsers.add_parser(
        "show", help="Show details for a specific schedule"
    )
    show_parser.add_argument("schedule_name", help="Schedule name to show")

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a Friday schedule for a task")
    add_parser.add_argument("task_name", help="Task name to schedule")
    add_parser.add_argument("--lead-id", help="Lead ID for the schedule name")
    add_parser.add_argument("--args", help="JSON array of arguments")
    add_parser.add_argument("--kwargs", help="JSON object of keyword arguments")
    add_parser.add_argument(
        "--hour", type=int, default=17, help="Hour to run (24-hour format, default 17)"
    )
    add_parser.add_argument(
        "--minute", type=int, default=0, help="Minute to run (default 0)"
    )

    # Remove command
    remove_parser = subparsers.add_parser("remove", help="Remove a specific schedule")
    remove_parser.add_argument("schedule_name", help="Schedule name to remove")

    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear all schedules")

    # Tasks command
    tasks_parser = subparsers.add_parser("tasks", help="List all available tasks")

    # Ping command
    ping_parser = subparsers.add_parser("ping", help="Check Redis connection")

    # RedBeat command
    redbeat_parser = subparsers.add_parser(
        "redbeat", help="List RedBeat schedules from Redis"
    )

    # Clear lock
    clear_lock_parser = subparsers.add_parser(
        "clear-lock", help="Clear the RedBeat scheduler lock"
    )

    args = parser.parse_args()

    # First, check Redis connection for all commands except help
    if args.command and args.command != "help":
        if not check_redis_connection():
            return 1

    # Handle commands
    if args.command == "list":
        list_schedules(args.verbose)
    elif args.command == "show":
        show_schedule(args.schedule_name)
    elif args.command == "add":
        add_friday_schedule(
            args.task_name, args.lead_id, args.args, args.kwargs, args.hour, args.minute
        )
    elif args.command == "remove":
        remove_schedule(args.schedule_name)
    elif args.command == "tasks":
        list_tasks()
    elif args.command == "redbeat":
        list_redbeat_schedules()
    elif args.command == "clear-lock":
        clear_redbeat_lock()
    elif args.command == "ping":
        # Already checked above
        pass
    else:
        parser.print_help()


if __name__ == "__main__":
    sys.exit(main() or 0)
