# Backend Startup - Fixed Instructions
## ✅ PORT CHANGE: Now using port 8000 (not blocked by Windows Firewall)

## If PowerShell Script Doesn't Work:

### Option 1: Use Batch File (Most Reliable)
Double-click `start_backend.bat` or run from command prompt:
```cmd
cd "C:\Users\adamm\Projects\ReferralLink Clone Lance\Backend"
start_backend.bat
```

### Option 1.5: Add Permanent Firewall Rule (Recommended)
For a permanent fix that prevents future port blocking:
1. Right-click `add_firewall_rule.bat`
2. Select "Run as administrator"
3. The script will add a Windows Firewall rule for port 8000
```

### Option 2: Manual Command (Always Works)
Open PowerShell or Command Prompt:
```powershell
cd "C:\Users\adamm\Projects\ReferralLink Clone Lance\Backend"
.\venv\Scripts\Activate.ps1
python main.py
```

Or without venv:
```powershell
cd "C:\Users\adamm\Projects\ReferralLink Clone Lance\Backend"
python main.py
```

### Option 3: Fix PowerShell Execution Policy
If PowerShell scripts are blocked, run this first:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
Then try running `start_backend.ps1` again.

## Troubleshooting

**If script shows "execution policy" error:**
- Use the batch file instead (Option 1)
- Or run manually (Option 2)
- Or fix execution policy (Option 3)

**If Python command not found:**
- Make sure Python is installed
- Check that Python is in your PATH
- Try using `py` instead of `python`

**If port gets blocked again:**
- Run `add_firewall_rule.bat` as administrator
- Or use Option 1.5 above for permanent firewall rule
- Port 8000 is now used instead of 5000-series ports

## ✅ What Was Fixed

**Problem**: Windows Firewall was blocking ports 5001, 5002, 5003
**Root Cause**: Windows Defender Firewall blocks uncommon ports by default
**Solution**: Changed to port 8000 (standard development port) + firewall rule

**Current Configuration**:
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`
- API calls: Working without "pending" status

