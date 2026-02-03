@echo off
REM Start Celery Beat Scheduler for AI Agent
REM This runs periodic tasks: NBA scan (every 15 min), process pending messages (every 5 min)

echo Starting Celery Beat Scheduler...
echo.
echo This window must stay open for periodic AI tasks to run.
echo Close this window to stop the scheduler.
echo.

cd /d "%~dp0"

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Start Celery beat scheduler
celery -A app.scheduler.celery_app beat --loglevel=info

pause
