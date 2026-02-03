# Railway Deployment Guide - Automated Setup

This guide will help you deploy all 3 services (Web, Worker, Beat) + Redis to Railway using the CLI.

## Quick Setup (Automated)

### Step 1: Install Railway CLI

**Option A: Using npm** (recommended)
```bash
npm install -g @railway/cli
```

**Option B: Using Homebrew** (Mac)
```bash
brew install railway
```

**Option C: Using Scoop** (Windows)
```bash
scoop install railway
```

**Option D: Direct download**
Download from: https://railway.app/cli

### Step 2: Login to Railway

```bash
railway login
```

This will open your browser to authenticate.

### Step 3: Run Automated Setup Script

**On Mac/Linux:**
```bash
cd Backend
chmod +x railway_setup.sh
./railway_setup.sh
```

**On Windows (Git Bash):**
```bash
cd Backend
bash railway_setup.sh
```

The script will:
1. ✅ Create a new Railway project (or link existing)
2. ✅ Add Redis database
3. ✅ Create Web service (Flask API)
4. ✅ Create Worker service (Celery Worker)
5. ✅ Create Beat service (Celery Beat)
6. ✅ Prompt you for environment variables
7. ✅ Deploy all services

**That's it!** Your AI agent will be live in ~5 minutes.

---

## Manual Setup (Alternative)

If you prefer to set up manually or the script doesn't work:

### 1. Create Project

```bash
railway init --name leadsynergy
```

### 2. Add Redis

```bash
railway add --plugin redis
```

### 3. Create Services

```bash
# Web service
railway service create web

# Worker service
railway service create worker

# Beat service
railway service create beat
```

### 4. Set Environment Variables

For each service (web, worker, beat), set these variables:

```bash
# Required variables
railway variables --service web set FUB_API_KEY="your_key"
railway variables --service web set SUPABASE_URL="your_url"
railway variables --service web set SUPABASE_KEY="your_key"
railway variables --service web set ANTHROPIC_API_KEY="your_key"

# Repeat for worker and beat
railway variables --service worker set FUB_API_KEY="your_key"
railway variables --service worker set SUPABASE_URL="your_url"
# ... etc
```

**Or use the Railway Dashboard** to set variables (easier):
1. Go to https://railway.app/project/YOUR_PROJECT
2. Click on each service
3. Go to "Variables" tab
4. Add variables there

### 5. Configure Start Commands

**Web service:**
```bash
railway variables --service web set START_COMMAND="gunicorn main:app --workers 4 --bind 0.0.0.0:\$PORT --timeout 120"
```

**Worker service:**
```bash
railway variables --service worker set START_COMMAND="celery -A app.scheduler.celery_app worker --loglevel=info --concurrency=4"
```

**Beat service:**
```bash
railway variables --service beat set START_COMMAND="celery -A app.scheduler.celery_app beat --loglevel=info"
```

### 6. Deploy

```bash
# Deploy each service
railway up --service web
railway up --service worker
railway up --service beat
```

---

## Alternative: Using Railway.toml

Create `railway.toml` in your Backend directory:

```toml
[build]
builder = "NIXPACKS"
buildCommand = "pip install -r requirements.txt"

[deploy]
startCommand = "gunicorn main:app --workers 4 --bind 0.0.0.0:$PORT --timeout 120"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
```

Then deploy:
```bash
railway up
```

---

## Verification

### Check Deployment Status

```bash
# View all services
railway status

# Check specific service logs
railway logs --service web
railway logs --service worker
railway logs --service beat
```

### What to Look For

**Web Service Logs:**
```
[INFO] Starting gunicorn
[INFO] Listening at: http://0.0.0.0:8000
[INFO] Booting worker with pid: 123
```

**Worker Service Logs:**
```
[tasks]
  . app.scheduler.ai_tasks.send_scheduled_message
  . app.scheduler.ai_tasks.trigger_instant_ai_response
  . app.scheduler.ai_tasks.process_pending_messages

celery@worker ready.
```

**Beat Service Logs:**
```
celery beat v5.3.4 is starting.
Scheduler: Sending due task process_pending_messages
Scheduler: Sending due task run_nba_scan
```

### Test the System

1. Get your Web service URL:
   ```bash
   railway domain --service web
   ```

2. Visit: `https://your-app.railway.app/health`

3. Create a test lead in FUB with your phone number

4. Within 60 seconds, you should receive the welcome SMS

---

## Managing Your Deployment

### View Logs (Live)

```bash
# Follow logs in real-time
railway logs --service web --follow
railway logs --service worker --follow
railway logs --service beat --follow
```

### Update Environment Variables

```bash
railway variables --service web set NEW_VAR="value"
```

Or use the dashboard (easier).

### Redeploy After Code Changes

```bash
# Redeploy all services
railway up --service web
railway up --service worker
railway up --service beat
```

Or just push to your GitHub repo - Railway auto-deploys on git push.

### Scale Services

```bash
# Scale worker to 3 replicas for higher throughput
railway scale --service worker --replicas 3

# Scale beat back to 1 (IMPORTANT: Beat must always be 1!)
railway scale --service beat --replicas 1
```

### View Service URLs

```bash
railway domain --service web
```

### Open Railway Dashboard

```bash
railway open
```

---

## Troubleshooting

### "railway: command not found"

Install Railway CLI (see Step 1 above).

### "Not authenticated"

Run: `railway login`

### Worker/Beat services crashing

Check logs:
```bash
railway logs --service worker
railway logs --service beat
```

Common issues:
- Missing environment variables (FUB_API_KEY, etc.)
- Redis not connected (check REDIS_URL is set)
- Python dependencies missing (check build logs)

### Messages not sending

1. Check Worker is running:
   ```bash
   railway logs --service worker
   ```
   Should show: `celery@worker ready.`

2. Check Beat is running:
   ```bash
   railway logs --service beat
   ```
   Should show: `Scheduler: Sending due task...`

3. Check Redis connection:
   ```bash
   railway logs --service worker | grep -i redis
   ```

### Environment variables not set

List current variables:
```bash
railway variables --service web
railway variables --service worker
railway variables --service beat
```

Set missing variables via dashboard or CLI.

---

## Cost Optimization

Railway charges based on resource usage:

1. **Start small**: 1 worker replica initially
2. **Scale up**: Add more workers if message delays occur
3. **Beat is always 1**: Never scale Beat above 1 replica
4. **Monitor usage**: Railway dashboard shows CPU/memory/cost per service

Estimated monthly cost:
- Starter tier: Free for first $5/month, then ~$10-30/month
- Hobby tier: ~$5-20/month depending on traffic
- Pro tier: ~$20-50/month for production scale

---

## CI/CD (Optional)

Set up automatic deployments on git push:

1. Go to Railway dashboard → Settings → GitHub
2. Connect your repository
3. Select branch (e.g., `main`)
4. Enable "Deploy on push"

Now every push to `main` automatically redeploys.

---

## Support

If you get stuck:

1. Check logs: `railway logs --service <name>`
2. Check Railway status: https://status.railway.app
3. Railway Discord: https://discord.gg/railway
4. Railway Docs: https://docs.railway.app

---

## Summary

**Automated setup** (5 minutes):
```bash
npm install -g @railway/cli
railway login
cd Backend
bash railway_setup.sh
```

**Manual setup** (10 minutes):
```bash
railway init
railway add --plugin redis
railway service create web
railway service create worker
railway service create beat
# Set env vars via dashboard
railway up --service web
railway up --service worker
railway up --service beat
```

**Verify**:
```bash
railway logs --service worker
# Should see: celery@worker ready.
```

**Test**:
- Create lead in FUB with your phone
- Receive SMS within 60 seconds

**Done!** 🎉
