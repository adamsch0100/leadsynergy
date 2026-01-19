# AI Follow-Up Sequences - World-Class Lead Conversion System

## Research Foundation

This follow-up system is built on research from:
- **MIT Lead Response Study**: 21x higher conversion within 5 minutes
- **LeadSimple**: 78% of sales go to the first responder
- **Robert Slack mega-team**: 45-day text campaign = 34% → 65% connections
- **Follow Up Boss, Curaytor, Ylopo**: 2024-2025 real estate ISA best practices

## Key Principles

1. **Speed to Lead** - Response within 1 minute (not 15)
2. **Multi-Touch Day 0** - 4 touches in first 2 hours
3. **Qualify Early** - Ask timeline/motivation in first messages
4. **Assumptive Close** - "I have Thursday at 3pm" not "Would you like to schedule?"
5. **Strategic Break-Up** - Day 7 "closing file" message (highest response rate!)

---

## NEW_LEAD Sequence (World-Class Aggressive)

**Total Touches**: 11 (7 with voice disabled, 11 with voice enabled)
**Duration**: 7 days
**Channels**: SMS, Email, RVM (optional), Call (optional)

### Day 0 - Speed to Lead (4 touches)

| Time | Channel | Type | Purpose |
|------|---------|------|---------|
| **0 min** | SMS | First Contact | Immediate intro + qualify timeline |
| **5 min** | RVM* | Intro VM | Ringless voicemail drop |
| **30 min** | SMS | Value + CTA | Appointment offer ("Thursday at 3pm?") |
| **2 hr** | Call* | Check-in | Live call attempt |

*RVM and Call only if `voice_enabled=True`

### Day 1 - Qualify Motivation (2 touches)

| Time | Channel | Type | Purpose |
|------|---------|------|---------|
| **AM** | SMS | Qualify | "Are you buying first or selling too?" |
| **PM** | Call* | Follow-up | Second call attempt |

### Day 2-7 - Value & Close

| Day | Channel | Type | Purpose |
|-----|---------|------|---------|
| **Day 2** | SMS | Value Add | Property alert style ("Just saw a listing...") |
| **Day 3** | Email | Market Report | Detailed value + 3 time slot options |
| **Day 4** | SMS | Social Proof | "Just helped a buyer close in {area}" |
| **Day 5** | Call* | Final Call | Third call attempt |
| **Day 7** | SMS | Break-Up | Strategic "closing your file" message |

---

## Message Templates

### First Contact (Day 0, Immediate)
```
Hey {first_name}! {agent_name} here from {brokerage}.
Saw you're looking at homes in {area} - exciting!
When are you thinking of making a move?
```

### Value + CTA (Day 0, 30 min)
```
{first_name}, btw I have a few times open this week if you want
to chat about {area}. Would {suggested_day} afternoon work for a quick call?
```

### Qualify Motivation (Day 1)
```
{first_name}, quick question - are you looking to buy first,
or do you have a place to sell too? Helps me know how to best help you!
```

### Value Add Listing (Day 2)
```
{first_name}, heads up - just saw a new listing in {area} that might
fit what you're looking for. 3BR, updated kitchen. Want details?
```

### Social Proof (Day 4)
```
{first_name}, just helped a buyer close on a great place in {area} last week.
Happy to do the same for you when you're ready!
```

### Strategic Break-Up (Day 7) - HIGHEST RESPONSE RATE
```
{first_name}, I'm closing your file for now since I haven't heard back -
but I totally get it, timing is everything!

Quick question before I do: Did something change, or is now just not the right time?

Either way, no hard feelings - I'll be here when you're ready!
```

---

## Configuration Settings

All sequence behavior is controlled via `AIAgentSettings`:

```python
# Channel toggles (in ai_agent_settings table)
sequence_sms_enabled: True       # Always on
sequence_email_enabled: True     # Always on
sequence_voice_enabled: False    # OFF by default - toggle when ready
sequence_rvm_enabled: False      # OFF by default

# Day 0 aggression level
day_0_aggression: "aggressive"   # aggressive | moderate | conservative

# Proactive features
proactive_appointment_enabled: True
qualification_questions_enabled: True

# Speed to lead
instant_response_enabled: True
instant_response_max_delay_seconds: 60

# NBA scan intervals
nba_hot_lead_scan_interval_minutes: 5    # Hot leads every 5 min
nba_cold_lead_scan_interval_minutes: 15  # Cold leads every 15 min
```

---

## Voice Channel Integration (Future)

When `voice_enabled=True`, the sequence includes:

1. **RVM (Ringless Voicemail)** - Day 0, 5 min
   - Drops voicemail without ringing
   - Non-intrusive, high delivery rate
   - Providers: SlyBroadcast, DropCowboy

2. **Call Attempts** - Day 0 (2hr), Day 1 (PM), Day 5
   - Can be AI voice or scheduled for human agent
   - Providers: Synthflow, Vapi, Twilio

See `voice_service.py` for integration stubs.

---

## Instant Response Flow

When a new lead is created via webhook:

```
1. FUB Webhook → personCreated event
2. fub_webhook.py → triggers trigger_instant_ai_response.delay()
3. Celery task executes within 60 seconds
4. First contact SMS sent immediately
5. Full sequence scheduled (Day 0 +30min, Day 1, etc.)
```

This bypasses the 15-minute NBA batch scan for maximum speed-to-lead.

---

## Proactive Appointment Offering

The AI uses "assumptive close" technique:

**Bad (passive)**: "Would you like to schedule a call?"
**Good (assumptive)**: "I have Thursday at 3pm open - does that work?"

Functions available:
- `generate_assumptive_close()` - Gets real calendar availability
- `generate_proactive_cta()` - Generic CTAs for follow-ups
- `get_suggested_day_and_time()` - Optimal days (Tue-Thu) and times (2-3pm)

---

## Qualification Flow

Early messages qualify leads on:

| Question | Field | Options |
|----------|-------|---------|
| "When are you thinking of making a move?" | timeline | 1-3 months, 3-6 months, 6+ months |
| "Are you buying first or selling too?" | has_home_to_sell | True/False |
| "What's driving your search?" | motivation | job change, family, investment |
| "Is it just you or with family?" | decision_makers | just me, with partner, with family |

Qualified leads convert at **5-7x the rate** of unqualified leads.

---

## Sequence Skip Logic

Steps can be skipped based on settings:

```python
FollowUpStep(
    delay_days=0,
    delay_minutes=5,
    channel="rvm",
    message_type=MessageType.RVM_INTRO,
    skip_if_disabled="voice_enabled",  # Skip if voice OFF
)
```

With `voice_enabled=False`:
- 11 total steps → 7 active steps
- RVM and Call steps are skipped automatically

---

## Other Sequences

### REVIVAL SEQUENCE (Cold/Dormant Leads 30+ days)
**Goal**: Offer VALUE first, not sales pitch. Reference their original criteria.

| Day | Channel | Message Type | Purpose |
|-----|---------|--------------|---------|
| 0 | SMS | Value Add | Market update or new listing |
| 7 | SMS | Gentle Follow-up | Check if situation changed |
| 21 | Email | Channel Switch | More detailed email |
| 45 | Email | Final Attempt | Gentle close |

### STANDARD RE-ENGAGEMENT
**Goal**: Re-spark interest without being pushy

| Day | Channel | Message Type | Purpose |
|-----|---------|--------------|---------|
| 1 | Primary | Gentle Follow-up | Check in |
| 3 | Primary | Value Add | Provide value |
| 7 | Secondary | Channel Switch | Try other channel |
| 14 | Secondary | Final Attempt | Soft close |

### NURTURE SEQUENCE (6+ Month Timeline)
**Goal**: Stay top of mind without pressure

| Day | Channel | Message Type | Purpose |
|-----|---------|--------------|---------|
| 30 | Email | Monthly Touchpoint | Market update |

---

## TCPA Compliance

All automated messages respect:
- **Working hours**: 8 AM - 8 PM in lead's timezone
- **Rate limits**: Max 3 messages per 24 hours
- **Opt-outs**: Immediate stop on "stop" or "unsubscribe"

---

## Performance Metrics to Track

1. **Response Rate** - % of leads that respond to first message
2. **Time to First Response** - How quickly we contact new leads
3. **Appointment Conversion** - % of conversations that book appointments
4. **Template Performance** - Which message variants get best responses
5. **Channel Performance** - SMS vs Email vs Voice conversion rates

---

## Files Reference

| File | Purpose |
|------|---------|
| `followup_manager.py` | Sequence definitions, templates, scheduling |
| `settings_service.py` | Channel toggles, aggression settings |
| `voice_service.py` | RVM/Voice AI integration stubs |
| `appointment_scheduler.py` | Assumptive close, proactive scheduling |
| `ai_tasks.py` | Celery tasks including instant response |
| `fub_webhook.py` | Webhook trigger for instant AI response |
| `next_best_action.py` | NBA engine for batch processing |

---

## FUB System Registration (One-Time Setup)

FUB requires system registration to use the webhook API. This is a **one-time setup** for LeadSynergy.

### Step 1: Register with FUB

1. Go to: https://apps.followupboss.com/system-registration
2. Fill in:
   - **System Name**: LeadSynergy
   - **Description**: AI-powered lead follow-up automation
   - **Website**: https://leadsynergy.ai
3. Submit and copy the **System Key** you receive

### Step 2: Add Environment Variable

Add to your `.env` file or Railway environment:
```bash
FUB_SYSTEM_KEY=your_key_here
FUB_SYSTEM_NAME=LeadSynergy  # Optional, defaults to LeadSynergy
```

### Step 3: Register Webhooks

Once the system key is configured, register webhooks via API:
```bash
# Using curl
curl -X POST https://your-api.com/fub/ai/webhooks/register

# Or via the admin UI
# Navigate to AI Agent Settings > Webhooks > Register
```

---

## Research Sources

- [MIT Lead Response Study](https://hbr.org/2011/03/the-short-life-of-online-sales-leads)
- [Follow Up Boss Texting Guide](https://www.followupboss.com/blog/texting-real-estate-leads)
- [The Close Lead Conversion Guide](https://theclose.com/real-estate-lead-conversion/)
- [Curaytor 2025 Conversion Guide](https://www.curaytor.com/blog/the-ultimate-lead-conversion-guide-for-2025)
- [RISMedia AI Lead Revival](https://www.rismedia.com/2025/05/21/reviving-cold-leads-power-ai-real-estate-engagement/)
- [JustCall Multi-Channel Guide](https://justcall.io/blog/how-to-follow-up-with-real-estate-leads.html)
