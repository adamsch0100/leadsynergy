@echo off
echo Starting Backend and Frontend Servers...
echo.

echo Cleaning up existing processes...
echo.

REM Kill processes on specific ports
echo Killing processes on port 8000 (Backend)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 "') do (
    if not "%%a"=="0" (
        echo Killing process %%a on port 8000
        taskkill /PID %%a /F >nul 2>&1
    )
)

echo Killing processes on port 3000 (Frontend)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000 "') do (
    if not "%%a"=="0" (
        echo Killing process %%a on port 3000
        taskkill /PID %%a /F >nul 2>&1
    )
)

echo Killing processes on port 3001 (Alternative Frontend)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3001 "') do (
    if not "%%a"=="0" (
        echo Killing process %%a on port 3001
        taskkill /PID %%a /F >nul 2>&1
    )
)

REM Only kill processes on specific ports used by this project

REM Wait for processes to fully terminate
timeout /t 3 /nobreak >nul

echo Process cleanup complete.
echo.

REM Start Backend in a new window
start "Backend Server" cmd /k "cd /d %~dp0Backend && start_backend.bat"

REM Wait a bit for backend to start
timeout /t 3 /nobreak >nul

REM Start Frontend in a new window
start "Frontend Server" cmd /k "cd /d %~dp0Frontend && start_frontend.bat"

echo.
echo Backend and Frontend servers are starting in separate windows.
echo.
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo.
pause