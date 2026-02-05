# Railway Deployment Setup for LeadSynergy

## Services Required on Railway

Your LeadSynergy backend needs **3 separate Railway services**:

### 1. **Web Service** (Main API)
- **Start Command:** `python main.py`
- Handles webhooks, API endpoints, and serves the Flask app
- Port: 8080

### 2. **Worker Service** (Celery Worker)
- **Start Command:** `celery -A app.scheduler.celery_app worker --loglevel=info --pool=solo`
- Processes async tasks (sending SMS, emails, AI responses)
- No exposed port needed
- **IMPORTANT:** Use `--pool=solo` for Railway's single-core containers

### 3. **Beat Service** (Celery Beat Scheduler)
- **Start Command:** `celery -A app.scheduler.celery_app beat --loglevel=info`
- Schedules recurring tasks:
  - Process pending messages every 5 minutes
  - NBA (Next Best Action) scan every 15 minutes
  - Off-hours queue processing
- No exposed port needed

### 4. **Redis Service** (Message Broker)
- Use Railway's Redis plugin
- Set `REDIS_URL` environment variable in all 3 services above

## Environment Variables Needed

All services need these environment variables:

```bash
# Redis (provided by Railway Redis plugin)
REDIS_URL=redis://default:password@hostname:port

# FUB Credentials (for Playwright browser automation)
FUB_LOGIN_EMAIL=your-fub-email@example.com
FUB_LOGIN_PASSWORD=your-fub-password
FUB_LOGIN_TYPE=email
FUB_API_KEY=your-fub-api-key

# AI Agent Settings
AI_AGENT_SYSTEM_NAME=leadsynergy-ai
AI_AGENT_SYSTEM_KEY=your-system-key

# Supabase
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-anon-key

# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Anthropic API (for AI responses)
ANTHROPIC_API_KEY=your-anthropic-key
```

## How the System Works Now

### When a New Lead Comes In:

#### **WITH Celery (Production on Railway):**
1. Webhook receives lead → calls `start_new_lead_sequence.delay()` (Celery task)
2. Celery worker picks up task
3. Calls `trigger_instant_ai_response` which:
   - Generates AI-powered SMS
   - Generates AI-powered email (mentions lead source)
   - Sends both via Playwright → **appears in FUB timeline**
   - Schedules follow-up sequence

#### **WITHOUT Celery (Fallback - like your current local setup):**
1. Webhook receives lead → Celery connection fails
2. Falls back to `schedule_welcome_sequence` which:
   - Sends SMS immediately via Playwright → **appears in FUB**
   - Generates AI email with lead source context
   - Sends email immediately via Playwright → **appears in FUB**
   - No follow-up sequence scheduled (requires Celery)

## Key Changes Made

### 1. Updated `schedule_welcome_sequence` (ai_webhook_handlers.py)
- **Before:** Only scheduled SMS messages (no email)
- **After:** Sends both SMS + AI-generated email via Playwright immediately
- Emails now mention lead source (e.g., "Top Agents Ranked connected us")
- Both appear in FUB timeline because sent through Playwright

### 2. Updated Procfile
- **Before:** Only `web` process
- **After:** Added `worker` and `beat` processes
- Railway needs these as separate services (see setup above)

## Testing the Setup

### Test Locally (without Celery):
```bash
cd Backend
python main.py
# Create a test lead via webhook
# Should see: "[FALLBACK] Sending immediate SMS + Email..."
```

### Test on Railway (with Celery):
1. Create test lead via webhook
2. Check Railway logs:
   - **Web service:** Should see "Celery task triggered"
   - **Worker service:** Should see "Processing instant AI response"
3. Check FUB lead profile → SMS and email should appear in timeline

## Scheduled Tasks Running

When Celery Beat is running, these tasks execute automatically:

- **Every 5 min:** Process pending scheduled messages
- **Every 5 min:** Process off-hours message queue (8-10 AM MT)
- **Every 15 min:** NBA scan (find dormant leads, trigger re-engagement)
- **Every hour:** Scheduled lead sync
- **Weekly (Fridays 9 AM):** Process stage updates, notes, tags

## Troubleshooting

### "Failed to trigger Celery task: [Errno 111] Connection refused"
- ✅ **Expected locally** (Redis not running)
- ✅ **Fallback will handle it** (sends via Playwright immediately)
- ❌ **Problem on Railway** → Check Redis service is linked and REDIS_URL is set

### Email sent but not in FUB
- If you see "[SUCCESS] Email sent" but it's not in FUB timeline
- Means it was sent via SMTP, not Playwright
- Check that Playwright credentials are set: `FUB_LOGIN_EMAIL`, `FUB_LOGIN_PASSWORD`

### SMS sent but email not sent
- Check person has email in FUB: `emails[0].value`
- Check logs for "[FALLBACK] No email address for lead X"

## Railway Service Setup Steps

1. **Create Web Service:**
   - Connect your GitHub repo
   - Set start command: `python main.py`
   - Add all environment variables

2. **Add Redis Plugin:**
   - Railway dashboard → Add Plugin → Redis
   - Copy `REDIS_URL` from Redis service
   - Add to Web, Worker, and Beat services

3. **Create Worker Service:**
   - Same repo, same branch
   - Set start command: `celery -A app.scheduler.celery_app worker --loglevel=info --pool=solo`
   - Copy all environment variables from Web service
   - Link Redis service

4. **Create Beat Service:**
   - Same repo, same branch
   - Set start command: `celery -A app.scheduler.celery_app beat --loglevel=info`
   - Copy all environment variables from Web service
   - Link Redis service

5. **Deploy All Services:**
   - All 3 should be running (green checkmarks)
   - Web service will have a public URL
   - Worker and Beat are internal (no public URLs)

## Monitoring

### Check Worker Status:
```bash
# In Railway Worker service logs
celery -A app.scheduler.celery_app inspect active
celery -A app.scheduler.celery_app inspect stats
```

### Check Scheduled Tasks:
```bash
# In Railway Beat service logs
celery -A app.scheduler.celery_app inspect scheduled
```

### Check Redis Connection:
```bash
# In any service
python -c "import redis; r = redis.from_url('$REDIS_URL'); print(r.ping())"
```
