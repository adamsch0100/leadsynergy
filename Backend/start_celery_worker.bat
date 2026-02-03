@echo off
REM Start Celery Worker for AI Agent
REM This processes background tasks: message sending, follow-up sequences, etc.

echo Starting Celery Worker...
echo.
echo This window must stay open for the AI agent to send messages.
echo Close this window to stop the worker.
echo.

cd /d "%~dp0"

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Start Celery worker
celery -A app.scheduler.celery_app worker --loglevel=info --pool=solo

pause
