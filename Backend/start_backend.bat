@echo off
echo Starting Backend Server...
echo.

echo Cleaning up existing processes...
echo.

REM Kill processes on port 8000 (Backend port)
echo Killing processes on port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 "') do (
    if not "%%a"=="0" (
        echo Killing process %%a on port 8000
        taskkill /PID %%a /F >nul 2>&1
    )
)

REM Only kill processes on specific backend port

REM Wait for processes to fully terminate
timeout /t 1 /nobreak >nul

echo Process cleanup complete.
echo.

cd /d "%~dp0"

REM Prefer uv (fast, manages venv automatically)
where uv >nul 2>&1
if %ERRORLEVEL%==0 (
    echo Using uv to run backend...
    uv run python main.py
) else (
    python -m uv run python main.py 2>nul
    if %ERRORLEVEL% NEQ 0 (
        REM Fallback: activate .venv or venv manually
        if exist .venv\Scripts\Activate.bat (
            call .venv\Scripts\Activate.bat
            python main.py
        ) else if exist venv\Scripts\Activate.bat (
            call venv\Scripts\Activate.bat
            python main.py
        ) else (
            echo No virtual environment found. Using system Python...
            python main.py
        )
    )
)
pause
