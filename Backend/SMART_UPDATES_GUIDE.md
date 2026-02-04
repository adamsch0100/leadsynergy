# Smart Lead Source Updates - Implementation Guide

## Overview

This system ensures all updates to lead source platforms (ReferralExchange, HomeLight, Redfin, etc.) are **strategically positive and action-oriented** to maintain strong partner relationships.

## Key Philosophy

**Default to Optimism & Action** - Even when your agent dropped the ball or a lead is dormant, updates show engagement and forward momentum UNLESS there's legitimate proof the lead is dead.

---

## How It Works

### 1. **Strategy Engine** (`lead_update_strategy.py`)

Analyzes each lead and determines the right approach:

#### Lead Classifications:

| Disposition | When Applied | Update Tone | Example |
|------------|--------------|-------------|---------|
| **ACTIVE_ENGAGED** | Recent activity (< 7 days) | Optimistic | "Making great progress. Discussed their timeline and moving forward with next steps." |
| **DORMANT_RECOVERABLE** | No activity 7-30 days | Persistent | "Continuing to stay in touch with valuable market updates and resources." |
| **GHOSTING** | No activity 30-60+ days | Strategic | "Adjusting outreach strategy to provide more targeted value around their buying criteria." |
| **DEAD_CONFIRMED** | Explicit dead reason | Professional Closure | "Client confirmed they found another agent. Maintaining positive relationship for future referrals." |
| **DEAD_UNRESPONSIVE** | 10+ attempts, 0 responses, 60+ days | Respectful Closure | "After multiple attempts across different channels, unable to establish contact. Closing respectfully." |

#### Decision Tree:

```
Is lead explicitly dead?
  (opted out, complaint, "not interested", etc.)
  → YES: DEAD_CONFIRMED ❌

Is lead completely unresponsive?
  (10+ attempts, 0 responses, 60+ days)
  → YES: DEAD_UNRESPONSIVE ❌

Has lead been contacted recently?
  (< 7 days)
  → YES: ACTIVE_ENGAGED ✅

Is lead dormant but reachable?
  (30-60+ days)
  → YES: GHOSTING ✅

DEFAULT: DORMANT_RECOVERABLE ✅
```

### 2. **Smart Update Generator** (`smart_update_generator.py`)

Integrates strategy with actual update generation:

1. Builds lead context (days since contact, attempts, responses, FUB stage)
2. Determines strategy using engine
3. Generates update (AI or template-based)
4. Validates update meets requirements

### 3. **Integration with Sync Process**

Updates are generated automatically during platform syncs based on configuration.

---

## Setup & Configuration

### Quick Enable All Sources

```python
# Run this in Backend directory
python -c "
from app.ai_agent.smart_update_generator import enable_smart_updates

# Enable for all major sources
sources = ['ReferralExchange', 'Referral Exchange', 'HomeLight', 'Redfin', 'Agent Pronto']
for source in sources:
    enable_smart_updates(source, mode='fallback')
"
```

### Configuration Modes

#### `fallback` (Recommended)
- Uses manual @update if you wrote one
- Auto-generates only when no manual update exists
- **Best for:** Letting you override when needed

#### `always`
- Always AI-generates, ignores manual updates
- **Best for:** Full automation

#### `supplement`
- Enhances your manual @update with additional context
- **Best for:** Augmenting your notes

### Per-Source Configuration

```python
from app.ai_agent.smart_update_generator import enable_smart_updates

# Enable for specific source
enable_smart_updates('ReferralExchange', mode='fallback')
```

### Database Configuration (Advanced)

Updates are stored in `lead_source_settings.metadata`:

```json
{
  "ai_update_enabled": true,
  "ai_update_mode": "fallback",
  "ai_update_save_to_fub": true,
  "ai_update_settings": {
    "enabled": true,
    "mode": "fallback",
    "save_to_fub": true,
    "context_sources": ["messages", "notes"],
    "tone": "professional",
    "max_length": 300
  }
}
```

---

## Update Templates by Category

### Active Progress (ACTIVE_ENGAGED)
- "Currently in active communication. Discussed their needs and moving forward with next steps."
- "Making good progress. Last spoke recently about their timeline. Following up with property options."
- "Lead is engaged and responsive. Working through their options and will schedule a showing."

### Persistent Engagement (DORMANT_RECOVERABLE)
- "Continuing to stay in touch with valuable market updates and resources."
- "Building rapport through consistent touchpoints. Planning to reach out with fresh listings."
- "Staying top of mind with personalized content relevant to their interests."
- "Nurturing relationship with periodic check-ins and market insights."

### Strategic Re-engagement (GHOSTING)
- "Adjusting outreach strategy to provide more targeted value around their interests."
- "Trying different communication channels and times to reconnect."
- "Shifting approach to focus on new angle which may resonate better."

### Professional Closure (DEAD_CONFIRMED)
- "Lead has indicated they are working with another agent. Closing respectfully and wishing them well."
- "Client confirmed they already purchased. Maintaining positive relationship for future referrals."

### Respectful Closure (DEAD_UNRESPONSIVE)
- "After multiple attempts across different channels, unable to establish contact. Closing respectfully."
- "Reached out 10+ times via phone, email, and text without response. Moving to inactive status."

---

## Testing

### Test Strategy Engine

```bash
cd Backend
python app/ai_agent/lead_update_strategy.py
```

Output shows how different lead scenarios are handled:
- Active leads → Optimistic updates
- Dormant leads → Persistent updates
- Dead leads → Professional closure

### Test Smart Generator

```bash
cd Backend
python app/ai_agent/smart_update_generator.py
```

---

## Integration with Current Sync

The sync process will automatically use smart updates when:

1. **AI updates enabled** for the lead source
2. **No manual @update** exists (in fallback mode)
3. **Lead needs update** according to platform requirements

### Manual Override

You can always override by adding `@update` note in FUB:
```
@update Currently working on pre-approval. Will have answer by Friday.
```

System will use your manual update instead of generating one.

---

## Benefits

### For Lead Sources (Partners)
✅ Always receive positive, professional updates
✅ See consistent engagement even with dormant leads
✅ Feel confident referring more leads to you
✅ Understand when leads legitimately won't work out

### For You
✅ Protect relationships with referral partners
✅ Automate updates without losing authenticity
✅ Save time writing updates for 100+ leads
✅ Override when you need custom messaging

### For Leads
✅ Continued value and attention
✅ Professional handling even when they go silent
✅ Respectful closure when appropriate

---

## Next Steps

1. **Enable smart updates** for your lead sources (see Quick Enable above)
2. **Run a test sync** to see updates in action
3. **Review generated updates** to ensure quality
4. **Adjust templates** if needed for your voice
5. **Monitor lead source feedback** to validate approach

---

## Customization

### Add Custom Templates

Edit `UPDATE_TEMPLATES` in `lead_update_strategy.py`:

```python
UPDATE_TEMPLATES = {
    "persistent_engagement": [
        "Your custom template here with {variables}",
        "Another template variation",
    ]
}
```

### Adjust Thresholds

Edit `LeadUpdateStrategyEngine` class constants:

```python
ACTIVE_THRESHOLD_DAYS = 7          # Default: 7 days
DORMANT_THRESHOLD_DAYS = 30        # Default: 30 days
GHOSTING_THRESHOLD_DAYS = 60       # Default: 60 days
DEAD_ATTEMPTS_THRESHOLD = 10       # Default: 10 attempts
```

### Add Custom Dead Keywords

```python
DEAD_KEYWORDS = [
    "not interested",
    "your custom keyword",
]
```

---

## Monitoring & Analytics

### Check Current Settings

```python
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
service = LeadSourceSettingsSingleton.get_instance()

for source in service.get_all():
    if source.is_active:
        print(f"{source.source_name}: {source.metadata.get('ai_update_enabled', False)}")
```

### View Generated Updates

Check sync logs for:
```
Update strategy for John Doe: dormant_recoverable (persistent) - Dormant for 25 days but still viable
```

---

## Troubleshooting

### Updates Not Being Generated

1. Check if feature enabled: `ai_update_enabled = true`
2. Verify mode is correct: `fallback` requires no manual @update
3. Check logs for strategy determination
4. Ensure platform sync is running

### Updates Too Generic

1. Enable AI mode (requires OpenAI API key)
2. Add more context sources: `['messages', 'notes', 'timeline']`
3. Customize templates for your voice

### Wrong Strategy Applied

1. Review lead context data (days since contact, attempts, etc.)
2. Adjust thresholds if needed
3. Check for dead indicators in FUB stage or notes

---

## Support

For questions or issues:
1. Check logs in `Backend/logs/`
2. Run test scripts to verify behavior
3. Review generated updates in sync output

---

## Summary

This system ensures **every lead source update is strategically positive** unless there's legitimate proof a lead is dead. It protects your valuable referral partnerships while saving you time and maintaining authenticity.

**Enable it now and let the system handle the strategy!**
