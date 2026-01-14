# PowerShell script to start the frontend server
Write-Host "Starting Frontend Server..." -ForegroundColor Green
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

# Function to kill processes on frontend ports
function Kill-FrontendProcesses {
    try {
        # Only kill processes using our specific frontend ports
        Write-Host "Checking for processes on frontend ports (3000, 3001)..." -ForegroundColor Yellow
        Kill-ProcessOnPort 3000
        Kill-ProcessOnPort 3001
    } catch {
        Write-Host "No processes found on frontend ports" -ForegroundColor Gray
    }
}

# Kill existing processes
Write-Host "Cleaning up existing processes..." -ForegroundColor Cyan
Kill-FrontendProcesses
Write-Host "Process cleanup complete." -ForegroundColor Green
Write-Host ""

# Change to script directory (handle spaces in path)
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $scriptPath

# Check if node_modules exists
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    npm install
}

Write-Host "Starting Next.js development server..." -ForegroundColor Green
Write-Host "Note: Port may be 3000 or 3001 if 3000 is in use" -ForegroundColor Yellow
npm run dev
