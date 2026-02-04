-- Verify AI Agent State After World-Class Improvements
-- Run these queries to ensure everything is working correctly

-- 1. Check for any false opt-outs (like person 3310 issue)
SELECT
    fub_person_id,
    opted_out,
    opted_out_at,
    opt_out_reason,
    created_at
FROM sms_consent
WHERE opted_out = true
ORDER BY opted_out_at DESC
LIMIT 20;

-- 2. Check conversation states (verify HANDED_OFF is working)
SELECT
    fub_person_id,
    state,
    ai_enabled,
    last_message_at,
    message_count,
    created_at,
    updated_at
FROM ai_conversations
WHERE ai_enabled = true
ORDER BY last_message_at DESC
LIMIT 20;

-- 3. Count conversations by state
SELECT
    state,
    COUNT(*) as count,
    COUNT(CASE WHEN ai_enabled = true THEN 1 END) as ai_enabled_count
FROM ai_conversations
GROUP BY state
ORDER BY count DESC;

-- 4. Check recent AI messages and handoffs
SELECT
    conversation_id,
    fub_person_id,
    direction,
    channel,
    message_content,
    extracted_data,
    created_at
FROM ai_messages
WHERE created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC
LIMIT 50;

-- 5. Check for any conversations that should be HANDED_OFF but aren't
SELECT
    ac.fub_person_id,
    ac.state,
    ac.last_message_at,
    ac.message_count,
    (SELECT COUNT(*) FROM ai_messages
     WHERE conversation_id = ac.conversation_id
     AND extracted_data::text LIKE '%appointment%') as appointment_mentions
FROM ai_conversations ac
WHERE ac.ai_enabled = true
  AND ac.state != 'HANDED_OFF'
  AND ac.last_message_at > NOW() - INTERVAL '7 days'
  AND EXISTS (
      SELECT 1 FROM ai_messages am
      WHERE am.conversation_id = ac.conversation_id
      AND (
          am.extracted_data::text LIKE '%appointment%'
          OR am.extracted_data::text LIKE '%schedule%'
          OR am.extracted_data::text LIKE '%showing%'
      )
  )
LIMIT 20;

-- 6. Check lead scores for active conversations
SELECT
    fub_person_id,
    total_score,
    engagement_score,
    qualification_score,
    urgency_score,
    calculated_at
FROM lead_scores
WHERE calculated_at > NOW() - INTERVAL '24 hours'
ORDER BY total_score DESC
LIMIT 20;

-- 7. Verify person 3310 specifically (if that's your test lead)
SELECT
    'sms_consent' as table_name,
    sc.fub_person_id,
    sc.opted_out,
    sc.opted_out_at
FROM sms_consent sc
WHERE sc.fub_person_id = 3310
UNION ALL
SELECT
    'ai_conversations' as table_name,
    ac.fub_person_id,
    ac.ai_enabled::text as opted_out,
    ac.state as opted_out_at
FROM ai_conversations ac
WHERE ac.fub_person_id = 3310;

-- 8. Check for any error patterns in recent messages
SELECT
    extracted_data->>'error' as error_type,
    COUNT(*) as count,
    MAX(created_at) as last_occurrence
FROM ai_messages
WHERE created_at > NOW() - INTERVAL '24 hours'
  AND extracted_data::text LIKE '%error%'
GROUP BY extracted_data->>'error'
ORDER BY count DESC;
