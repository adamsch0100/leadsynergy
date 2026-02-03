# Quick Start: Get Your AI Agent Sending Messages NOW

## 🚨 THE PROBLEM

**Your AI agent is 99% working but NOT sending messages because Celery workers aren't running.**

Evidence:
- ✅ Webhooks firing when leads are created
- ✅ Conversation records created in database
- ✅ Messages scheduled to `scheduled_messages` table
- ❌ **No workers to actually SEND the messages**
- ❌ **5+ messages stuck as "pending" since January 19**

## 🎯 THE FIX (3 Steps)

### Step 1: Install Redis

Redis is the message broker that Celery uses to queue tasks.

**Option A: Windows Installer** (Easiest)
1. Download: https://github.com/tporadowski/redis/releases
2. Download `Redis-x64-5.0.14.1.msi` (or latest version)
3. Run installer, use default settings
4. Redis will auto-start as a Windows service

**Option B: Using WSL** (if you have WSL installed)
```bash
wsl
sudo apt-get update
sudo apt-get install redis-server
sudo service redis-server start
```

**Verify Redis is running**:
```bash
redis-cli ping
# Should return: PONG
```

### Step 2: Install Celery (if not already installed)

```bash
cd Backend
pip install celery[redis]
```

### Step 3: Start the Workers

**You need 3 terminals open:**

#### Terminal 1: Flask API (probably already running)
```bash
cd Backend
python main.py
```

#### Terminal 2: Celery Worker (NEW - THIS IS WHAT'S MISSING!)
```bash
cd Backend
celery -A app.scheduler.celery_app worker --loglevel=info --pool=solo
```

Or on Windows, double-click: `start_celery_worker.bat`

#### Terminal 3: Celery Beat (NEW - THIS IS WHAT'S MISSING!)
```bash
cd Backend
celery -A app.scheduler.celery_app beat --loglevel=info
```

Or on Windows, double-click: `start_celery_beat.bat`

## ✅ Verification

**Within 5 minutes of starting the workers**, you should see:

1. **In Celery Worker logs**:
   ```
   [2026-02-02 12:00:00] Sending scheduled message abc123 to person 3279
   [2026-02-02 12:00:01] Message abc123 sent successfully
   ```

2. **In Celery Beat logs**:
   ```
   [2026-02-02 12:00:00] Scheduler: Sending due task process_pending_messages
   [2026-02-02 12:15:00] Scheduler: Sending due task run_nba_scan
   ```

3. **In your database** (run this to check):
   ```bash
   cd Backend
   python -c "from app.database.supabase_client import SupabaseClientSingleton; supabase = SupabaseClientSingleton.get_instance(); result = supabase.table('scheduled_messages').select('status').execute(); from collections import Counter; print(Counter([m['status'] for m in result.data]))"
   ```

   Should show messages changing from `pending` → `sent`

## 🧪 Test It

Create a test lead in FUB:
1. Add a new person with YOUR phone number
2. Within 60 seconds, you should receive a text message
3. Reply to the message
4. Within 10-30 seconds, AI should respond

## 🎬 What Happens When Workers Start

**Immediate (0-5 minutes)**:
- All pending messages from Jan 19-20 get sent (backlog cleared)
- Conversation records get first messages
- Lead scores start updating

**Every 5 minutes**:
- `process_pending_messages` task runs
- Any due scheduled messages get sent
- Follow-up sequences execute on schedule

**Every 15 minutes**:
- `run_nba_scan_task` runs
- Finds new leads that need engagement
- Finds dormant leads that need re-engagement
- Checks for high-score leads that need handoff

**When new lead is created in FUB**:
- Webhook fires → Flask receives it
- `trigger_instant_ai_response` Celery task queued
- Worker picks up task within seconds
- Welcome SMS sent within 60 seconds
- Follow-up sequence scheduled (30min, Day 1, Day 2, etc.)

## 📊 Monitoring

**Check worker is processing tasks**:
```bash
# In the Celery Worker terminal, you should see:
[tasks]
  . app.scheduler.ai_tasks.send_scheduled_message
  . app.scheduler.ai_tasks.process_pending_messages
  . app.scheduler.ai_tasks.trigger_instant_ai_response
  . app.scheduler.ai_tasks.run_nba_scan_task

[2026-02-02 12:00:00] Task app.scheduler.ai_tasks.process_pending_messages[abc-123] received
[2026-02-02 12:00:01] Task app.scheduler.ai_tasks.process_pending_messages[abc-123] succeeded
```

**Check pending message count**:
```bash
cd Backend
python -c "from app.database.supabase_client import SupabaseClientSingleton; supabase = SupabaseClientSingleton.get_instance(); result = supabase.table('scheduled_messages').select('id').eq('status', 'pending').execute(); print(f'Pending messages: {len(result.data)}')"
```

This number should decrease over time as messages get sent.

**Check conversation states**:
```bash
python -c "from app.database.supabase_client import SupabaseClientSingleton; supabase = SupabaseClientSingleton.get_instance(); result = supabase.table('ai_conversations').select('fub_person_id, state, lead_score, last_ai_message_at').limit(10).execute(); import json; print(json.dumps(result.data, indent=2))"
```

Look for:
- `last_ai_message_at` changing from `null` to timestamps
- `lead_score` increasing from 0 as conversations progress
- `state` changing from `initial` to `active` or other states

## 🐛 Troubleshooting

### "redis-cli: command not found"
Redis is not installed. See Step 1 above.

### Worker starts then immediately exits
Check if Redis is running:
```bash
redis-cli ping
```
Should return `PONG`. If not, start Redis.

### "No module named 'celery'"
Install Celery:
```bash
pip install celery[redis]
```

### Messages still not sending after 10 minutes
1. Check Redis is running: `redis-cli ping`
2. Check Worker logs for errors
3. Check Beat logs for errors
4. Verify environment variables are set (FUB_API_KEY, etc.)
5. Manually trigger pending message processing:
   ```bash
   cd Backend
   python -c "from app.scheduler.ai_tasks import process_pending_messages; print(process_pending_messages())"
   ```

### "ModuleNotFoundError" when starting worker
Make sure you're in the Backend directory:
```bash
cd Backend
celery -A app.scheduler.celery_app worker --loglevel=info --pool=solo
```

## 🚀 Production Deployment

For Railway/Heroku/AWS, you need to deploy 3 separate services:

1. **Web** (Flask API)
   - Start: `gunicorn main:app --workers 4`
   - Scale: 1-2 instances

2. **Worker** (Celery Worker)
   - Start: `celery -A app.scheduler.celery_app worker --loglevel=info`
   - Scale: 2-4 instances (can scale up for more throughput)

3. **Beat** (Celery Beat)
   - Start: `celery -A app.scheduler.celery_app beat --loglevel=info`
   - Scale: **EXACTLY 1 instance** (multiple = duplicate tasks!)

4. **Redis** (Message Broker)
   - Add from platform marketplace (Railway, Heroku, etc.)
   - Sets REDIS_URL automatically

## ❓ FAQ

**Q: Why were messages not sending before?**
A: The Flask API was queuing tasks to Celery, but no Celery workers were running to process them. It's like having a restaurant that takes orders but has no kitchen staff.

**Q: Do I need all 3 terminals open?**
A: Yes, in development. In production, these run as separate services/processes.

**Q: What if I close the Celery Worker terminal?**
A: Messages stop sending immediately. The worker must stay running.

**Q: Can I run the worker in the background?**
A: Yes:
- Windows: Use `pythonw` or create a Windows service
- Linux/Mac: Use `nohup` or `screen` or systemd service
- Production: Platform handles this (Railway, Heroku, etc.)

**Q: Why do I need Celery Beat?**
A: Beat schedules periodic tasks (every 5/15 minutes). Without it:
- Pending messages won't be checked/sent automatically
- NBA scan won't run (new leads won't be found)
- No automatic re-engagement for dormant leads

**Q: How do I know it's working?**
A: Check the Worker terminal for task execution logs, or check database for messages changing from `pending` to `sent`.

## 📋 Checklist

- [ ] Redis installed and running (`redis-cli ping` returns `PONG`)
- [ ] Celery installed (`pip install celery[redis]`)
- [ ] Terminal 1: Flask API running
- [ ] Terminal 2: Celery Worker running
- [ ] Terminal 3: Celery Beat running
- [ ] Pending message count decreasing over 5-10 minutes
- [ ] Test lead receives message within 60 seconds
- [ ] AI responds to test lead reply within 30 seconds

## 🎉 Success Metrics

After starting the workers, within 1 hour you should see:

1. **All 5+ pending messages from January sent** ✅
2. **Lead scores increasing** from 0 → 5+ as messages are sent ✅
3. **Conversation states changing** from `initial` → `active` ✅
4. **New leads getting instant welcome messages** (<60s) ✅
5. **Follow-up sequences executing** on Day 1, Day 2, etc. ✅

---

**Still stuck?** Check:
1. Redis running: `redis-cli ping`
2. Environment variables set: `echo $FUB_API_KEY`
3. Worker logs for errors: Look in Terminal 2
4. Beat logs for errors: Look in Terminal 3
5. Database message status: Run the SQL query above
