# PowerShell script to start both backend and frontend servers
Write-Host "Starting Backend and Frontend Servers..." -ForegroundColor Green
Write-Host ""

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path

# Function to kill processes on specific port
function Kill-ProcessOnPort {
    param([int]$port)
    try {
        $processInfo = netstat -ano | findstr ":$port " | Select-Object -First 1
        if ($processInfo) {
            $pid = ($processInfo -split '\s+')[-1]
            if ($pid -and $pid -ne "0") {
                Write-Host "Killing process on port $port (PID: $pid)..." -ForegroundColor Yellow
                taskkill /PID $pid /F | Out-Null
                Start-Sleep -Seconds 1
            }
        }
    } catch {
        Write-Host "No process found on port $port" -ForegroundColor Gray
    }
}

# Function to kill Python processes on specific ports
function Kill-PythonProcesses {
    try {
        # Only kill processes using our specific backend port
        Write-Host "Checking for processes on backend port (8000)..." -ForegroundColor Yellow
        Kill-ProcessOnPort 8000
    } catch {
        Write-Host "No processes found on backend port" -ForegroundColor Gray
    }
}

# Function to kill Node.js processes on specific ports
function Kill-NodeProcesses {
    try {
        # Only kill processes using our specific frontend ports
        Write-Host "Checking for processes on frontend ports (3000, 3001)..." -ForegroundColor Yellow
        Kill-ProcessOnPort 3000
        Kill-ProcessOnPort 3001

        # Kill orphaned node processes from LeadSynergy Frontend
        Write-Host "Cleaning up orphaned node processes..." -ForegroundColor Yellow
        $nodeProcesses = Get-WmiObject Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue
        foreach ($proc in $nodeProcesses) {
            if ($proc.CommandLine -like "*LeadSynergy*Frontend*" -or $proc.CommandLine -like "*next*dev*") {
                Write-Host "  Killing orphaned node process (PID: $($proc.ProcessId))..." -ForegroundColor Yellow
                Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {
        Write-Host "No processes found on frontend ports" -ForegroundColor Gray
    }
}

# Kill existing processes
Write-Host "Cleaning up existing processes..." -ForegroundColor Cyan
Kill-ProcessOnPort 8000  # Backend port
Kill-ProcessOnPort 3000  # Frontend port
Kill-ProcessOnPort 3001  # Alternative Frontend port
Kill-PythonProcesses
Kill-NodeProcesses

Write-Host "Process cleanup complete." -ForegroundColor Green
Write-Host ""

# Start Backend in a new window
Write-Host "Starting Backend Server..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-File", "$scriptPath\Backend\start_backend.ps1" -WindowStyle Normal

# Wait a bit for backend to start
Start-Sleep -Seconds 3

# Start Frontend in a new window
Write-Host "Starting Frontend Server..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-File", "$scriptPath\Frontend\start_frontend.ps1" -WindowStyle Normal

Write-Host ""
Write-Host "Backend and Frontend servers are starting in separate windows." -ForegroundColor Green
Write-Host ""
Write-Host "Backend: http://localhost:8000" -ForegroundColor Yellow
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press any key to exit this window (servers will continue running)..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

