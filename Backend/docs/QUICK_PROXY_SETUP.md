# Quick Proxy Setup Guide

## Current Status

Since you haven't paid for IPRoyal.com yet, the referral scrapers are configured to work **without proxies by default**.

## How to Control Proxy Usage

### Option 1: Use Environment Variable (Recommended)

Add this to your `.env` file:

```bash
# Disable proxy usage (current default - no IPRoyal needed)
USE_PROXY=false

# Enable proxy usage (when you have IPRoyal subscription)
USE_PROXY=true
```

### Option 2: Set Environment Variable Directly

**Windows PowerShell:**

```powershell
# Disable proxy
$env:USE_PROXY="false"

# Enable proxy
$env:USE_PROXY="true"
```

**Linux/Mac:**

```bash
# Disable proxy
export USE_PROXY=false

# Enable proxy
export USE_PROXY=true
```

## Current Setup (No IPRoyal Payment)

Your current setup should work perfectly with:

- `USE_PROXY=false` (or just leave it unset)
- No IPRoyal configuration needed
- All referral scrapers work as they did before

## When You Get IPRoyal Subscription

1. Set up IPRoyal credentials in database:

   ```bash
   python run_proxy_config_migration.py
   ```

2. Add organization proxy configs via API or database

3. Change environment variable:

   ```bash
   USE_PROXY=true
   ```

4. Run scrapers - they'll automatically use proxies

## Testing

Run this to verify the setup:

```bash
python test_proxy_flag.py
```

## Quick Summary

- **Current state**: Proxy **DISABLED** by default (no cost, works as before)
- **When ready**: Set `USE_PROXY=true` to enable IPRoyal proxies
- **Benefits**: Easy toggle, no code changes needed, cost control
