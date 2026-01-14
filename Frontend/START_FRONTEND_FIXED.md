# Frontend Startup - Fixed Instructions

## If PowerShell Script Doesn't Work:

### Option 1: Use Batch File (Most Reliable)
Double-click `start_frontend_simple.bat` or run from command prompt:
```cmd
cd "C:\Users\adamm\Projects\ReferralLink Clone Lance\Frontend"
start_frontend_simple.bat
```

### Option 2: Manual Command (Always Works)
Open PowerShell or Command Prompt:
```powershell
cd "C:\Users\adamm\Projects\ReferralLink Clone Lance\Frontend"
npm run dev
```

### Option 3: Fix PowerShell Execution Policy
If PowerShell scripts are blocked, run this first:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
Then try running `start_frontend.ps1` again.

## Troubleshooting

**If script shows "execution policy" error:**
- Use the batch file instead (Option 1)
- Or run manually (Option 2)
- Or fix execution policy (Option 3)

**If npm command not found:**
- Make sure Node.js is installed
- Check that npm is in your PATH
- Try restarting your terminal

