@echo off
echo Starting Frontend Server...
echo.

echo Cleaning up existing processes...
echo.

REM Kill processes on ports 3000-3001 (Frontend ports)
echo Killing processes on port 3000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000 "') do (
    if not "%%a"=="0" (
        echo Killing process %%a on port 3000
        taskkill /PID %%a /F >nul 2>&1
    )
)

echo Killing processes on port 3001...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3001 "') do (
    if not "%%a"=="0" (
        echo Killing process %%a on port 3001
        taskkill /PID %%a /F >nul 2>&1
    )
)

REM Only kill processes on specific frontend ports

REM Wait for processes to fully terminate
timeout /t 1 /nobreak >nul

echo Process cleanup complete.
echo.

cd /d "%~dp0"

if not exist node_modules (
    echo Installing dependencies...
    call npm install
)

echo Starting Next.js development server...
echo Note: Port may be 3000 or 3001 if 3000 is in use
call npm run dev
