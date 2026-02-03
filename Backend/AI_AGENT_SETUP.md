# AI Agent Setup Guide

## 🚨 CRITICAL: Why Your AI Agent Isn't Sending Messages

**Problem Discovered**: The AI agent creates conversation records and schedules messages, but **Celery workers are not running** to actually send them.

**Evidence**:
- 5+ pending messages in database from January 19-20 never sent
- All ai_conversations have score 0 because no messages were sent
- Messages scheduled but status stuck at "pending"

## Architecture

The LeadSynergy AI agent requires **3 services** to function:

1. **Flask API** (`main.py`) - Receives webhooks, handles requests ✅
2. **Celery Worker** - Processes background tasks (message sending) ❌
3. **Celery Beat** - Runs periodic tasks (NBA scan, pending messages) ❌

**Without #2 and #3, the AI agent cannot send messages or process leads.**

## Required Services

### 1. Redis (Message Broker)

Celery requires Redis to queue tasks. Install and start Redis:

**Windows**:
```bash
# Download Redis for Windows from: https://github.com/tporadowski/redis/releases
# Or use WSL:
wsl
sudo apt-get install redis-server
redis-server
```

**Mac**:
```bash
brew install redis
brew services start redis
```

**Linux**:
```bash
sudo apt-get install redis-server
sudo systemctl start redis
```

**Verify Redis is running**:
```bash
redis-cli ping
# Should return: PONG
```

### 2. Flask API (Already Running)

Your main Flask application should already be running on port 8000.

### 3. Celery Worker (MISSING - START THIS!)

Processes background tasks including message sending.

**Start on Windows**:
```bash
cd Backend
start_celery_worker.bat
```

**Start on Mac/Linux**:
```bash
cd Backend
celery -A app.scheduler.celery_app worker --loglevel=info
```

### 4. Celery Beat Scheduler (MISSING - START THIS!)

Runs periodic tasks every 5-15 minutes.

**Start on Windows**:
```bash
cd Backend
start_celery_beat.bat
```

**Start on Mac/Linux**:
```bash
cd Backend
celery -A app.scheduler.celery_app beat --loglevel=info
```

## Verification Steps

### 1. Check Pending Messages

```bash
cd Backend
python -c "from app.database.supabase_client import SupabaseClientSingleton; supabase = SupabaseClientSingleton.get_instance(); result = supabase.table('scheduled_messages').select('id, fub_person_id, scheduled_for, status').eq('status', 'pending').limit(10).execute(); print(f'Pending messages: {len(result.data)}'); import json; print(json.dumps(result.data, indent=2))"
```

### 2. Check Conversations

```bash
python -c "from app.database.supabase_client import SupabaseClientSingleton; supabase = SupabaseClientSingleton.get_instance(); result = supabase.table('ai_conversations').select('fub_person_id, state, lead_score, last_ai_message_at').limit(10).execute(); import json; print(json.dumps(result.data, indent=2))"
```

### 3. Monitor Celery Worker Logs

After starting the worker, you should see:
```
[tasks]
  . app.scheduler.ai_tasks.send_scheduled_message
  . app.scheduler.ai_tasks.start_new_lead_sequence
  . app.scheduler.ai_tasks.trigger_instant_ai_response
  . app.scheduler.ai_tasks.process_pending_messages
  . app.scheduler.ai_tasks.run_nba_scan_task
```

### 4. Monitor Celery Beat Logs

After starting beat, you should see:
```
Scheduler: Sending due task process_pending_messages
Scheduler: Sending due task run_nba_scan
```

## What Happens When You Start the Workers

1. **Celery Worker starts** - Begins listening for tasks
2. **Celery Beat starts** - Begins scheduling periodic tasks
3. **Every 5 minutes**: `process_pending_messages` runs - sends all due messages
4. **Every 15 minutes**: `run_nba_scan_task` runs - finds new leads needing engagement
5. **Pending messages from January 19-20 get sent immediately** (they're past due)
6. **New leads trigger instant responses** via `trigger_instant_ai_response`

## Periodic Tasks Configured

From `celery_app.py`:

| Task | Schedule | Purpose |
|------|----------|---------|
| `process_pending_messages` | Every 5 min | Send due scheduled messages |
| `run_nba_scan_task` | Every 15 min | Find new/dormant leads to engage |
| `process_off_hours_queue` | Every 5 min (8-10 AM MT) | Send queued off-hours messages |
| `process_scheduled_lead_sync` | Every hour | Sync lead status with platforms |

## Environment Variables Required

Ensure these are set in your `.env` file:

```bash
# Redis
REDIS_URL=redis://localhost:6379/0

# FUB API
FUB_API_KEY=your_fub_api_key

# AI Models
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key
OPENROUTER_API_KEY=your_openrouter_key

# Database
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

## Production Deployment

For production (Railway/Heroku/AWS):

### Railway Configuration

Add these services to your Railway project:

1. **Web Service** (Flask API)
   - Start command: `gunicorn main:app --workers 4 --bind 0.0.0.0:$PORT`

2. **Worker Service** (Celery Worker)
   - Start command: `celery -A app.scheduler.celery_app worker --loglevel=info`
   - Scale: 2-4 workers depending on load

3. **Beat Service** (Celery Beat)
   - Start command: `celery -A app.scheduler.celery_app beat --loglevel=info`
   - Scale: 1 instance only (multiple beat schedulers cause duplicate tasks)

4. **Redis Add-on**
   - Add from Railway marketplace
   - Auto-sets REDIS_URL environment variable

### Important Notes

- **Celery Beat** should only run 1 instance (multiple = duplicate scheduled tasks)
- **Celery Worker** can scale horizontally (2-10+ workers)
- All services share the same codebase and environment variables
- Redis URL must be accessible from all services

## Troubleshooting

### Messages Not Sending

**Check Redis**:
```bash
redis-cli ping
# Should return PONG
```

**Check Celery Worker is Running**:
```bash
# Look for "celery worker" process
ps aux | grep celery
# Windows: tasklist | findstr celery
```

**Check Logs**:
- Worker logs: Check the Celery worker terminal
- Beat logs: Check the Celery beat terminal
- Flask logs: Check main Flask terminal

**Manually Process Pending Messages**:
```bash
cd Backend
python -c "from app.scheduler.ai_tasks import process_pending_messages; process_pending_messages()"
```

### Worker Dies Immediately

**Common causes**:
1. Redis not running - start Redis first
2. Missing dependencies - run `pip install -r requirements.txt`
3. Import errors - check Python path includes Backend directory
4. Environment variables missing - check `.env` file

### Messages Send But No Response from Leads

This is normal! Real leads may not respond. Test with:
1. Create a test lead in FUB with YOUR phone number
2. Wait for welcome message (should arrive within 60 seconds if worker is running)
3. Reply to the message
4. AI should respond within 10-30 seconds

### High Score Leads Not Getting Handed Off

**Check handoff threshold**:
```sql
SELECT auto_handoff_score FROM ai_agent_settings;
```

Default is 70. Lower it if needed:
```sql
UPDATE ai_agent_settings SET auto_handoff_score = 50;
```

## Quick Start (Development)

```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start Flask API
cd Backend
python main.py

# Terminal 3: Start Celery Worker
cd Backend
celery -A app.scheduler.celery_app worker --loglevel=info --pool=solo

# Terminal 4: Start Celery Beat
cd Backend
celery -A app.scheduler.celery_app beat --loglevel=info
```

## What Gets Fixed When You Start Workers

1. ✅ **Pending messages from January 19-20 get sent** (backlog cleared)
2. ✅ **New leads get instant welcome messages** (<60 seconds)
3. ✅ **Follow-up sequences execute** (Day 1, Day 2, Day 3, etc.)
4. ✅ **Lead scores update** (as conversations progress)
5. ✅ **Handoffs trigger** (when score > 70)
6. ✅ **NBA scan finds dormant leads** (re-engagement)
7. ✅ **Compliance checks before each send** (DNC, opt-out, working hours)

## Monitoring

**Check task execution stats**:
```bash
# Flower (Celery monitoring UI)
pip install flower
celery -A app.scheduler.celery_app flower --port=5555
# Visit http://localhost:5555
```

**Check message send rate**:
```sql
SELECT
  DATE_TRUNC('hour', sent_at) as hour,
  COUNT(*) as messages_sent
FROM scheduled_messages
WHERE status = 'sent'
GROUP BY hour
ORDER BY hour DESC
LIMIT 24;
```

**Check conversation progress**:
```sql
SELECT
  state,
  COUNT(*) as count,
  AVG(lead_score) as avg_score
FROM ai_conversations
GROUP BY state;
```

## Next Steps

1. **Start Redis** (if not running)
2. **Start Celery Worker** (`start_celery_worker.bat`)
3. **Start Celery Beat** (`start_celery_beat.bat`)
4. **Watch the logs** - pending messages should send immediately
5. **Test with a new lead** - create in FUB, should get message within 60s
6. **Monitor conversations** - scores should increase as leads engage

---

**Need Help?**
- Check logs in all 4 terminals (Flask, Redis, Worker, Beat)
- Verify Redis is reachable: `redis-cli ping`
- Verify environment variables are set
- Check Python import paths if you get import errors
