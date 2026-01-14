# PowerShell script to start the backend server
Write-Host "Starting Backend Server..." -ForegroundColor Green
Write-Host ""

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

# Function to kill processes on backend port
function Kill-BackendProcesses {
    try {
        # Only kill processes using our specific backend port
        Write-Host "Checking for processes on backend port (8000)..." -ForegroundColor Yellow
        Kill-ProcessOnPort 8000
    } catch {
        Write-Host "No processes found on backend port" -ForegroundColor Gray
    }
}

# Kill existing processes
Write-Host "Cleaning up existing processes..." -ForegroundColor Cyan
Kill-BackendProcesses
Write-Host "Process cleanup complete." -ForegroundColor Green
Write-Host ""

# Change to script directory (handle spaces in path)
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $scriptPath

# Check if virtual environment exists and activate it
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & "venv\Scripts\Activate.ps1"
} else {
    Write-Host "Virtual environment not found. Using system Python..." -ForegroundColor Yellow
}

# Load environment variables
if (Test-Path ".env") {
    Write-Host "Loading .env file..." -ForegroundColor Yellow
}

# Start the server
Write-Host "Starting Flask server on http://127.0.0.1:8000" -ForegroundColor Green
python main.py
