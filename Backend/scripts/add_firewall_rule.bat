@echo off
echo Adding Windows Firewall rule for Flask development server...
echo This script requires administrator privileges.
echo.

netsh advfirewall firewall add rule name="Flask Backend Server (Port 8000)" dir=in action=allow protocol=TCP localport=8000

if %errorlevel% equ 0 (
    echo.
    echo SUCCESS: Firewall rule added for port 8000
    echo Your Flask backend server should now work without port blocking issues.
) else (
    echo.
    echo ERROR: Could not add firewall rule.
    echo Please run this batch file as Administrator (Right-click -> Run as administrator)
)

echo.
pause




