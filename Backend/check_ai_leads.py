"""
Script to check AI-enabled leads and their conversion status.
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'ignore')

# Add the Backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.supabase_client import SupabaseClientSingleton

def format_datetime(dt_string):
    """Format ISO datetime to readable string."""
    if not dt_string:
        return "Never"
    try:
        dt = datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        return dt_string

def get_ai_enabled_leads():
    """Get all leads with AI enabled and their conversion status."""
    load_dotenv()
    supabase = SupabaseClientSingleton.get_instance()

    print("\n" + "="*80)
    print("AI-ENABLED LEADS CONVERSION STATUS")
    print("="*80 + "\n")

    # Get leads with AI enabled
    settings_result = supabase.table('lead_ai_settings').select('*').eq(
        'ai_enabled', True
    ).execute()

    ai_leads = settings_result.data or []

    if not ai_leads:
        print("❌ No leads found with AI enabled.")
        return

    print(f"✅ Found {len(ai_leads)} leads with AI enabled\n")

    # Get person IDs
    person_ids = [int(l.get('fub_person_id')) for l in ai_leads if l.get('fub_person_id')]

    # Get conversation states for these leads
    conv_result = supabase.table('ai_conversations').select(
        'fub_person_id, state, lead_score, qualification_data, '
        'last_ai_message_at, last_lead_response_at, updated_at, handoff_reason'
    ).in_('fub_person_id', person_ids).execute()

    conv_by_person = {c['fub_person_id']: c for c in (conv_result.data or [])}

    # Get message counts
    msg_result = supabase.table('ai_message_log').select(
        'fub_person_id, direction, created_at'
    ).in_('fub_person_id', person_ids).order('created_at', desc=True).limit(1000).execute()

    msg_counts = {}
    for msg in (msg_result.data or []):
        pid = msg['fub_person_id']
        if pid not in msg_counts:
            msg_counts[pid] = {'sent': 0, 'received': 0, 'last_activity': None}
        if msg['direction'] == 'outbound':
            msg_counts[pid]['sent'] += 1
        else:
            msg_counts[pid]['received'] += 1
        if not msg_counts[pid]['last_activity']:
            msg_counts[pid]['last_activity'] = msg['created_at']

    # Try to get lead names from FUB data
    try:
        # Convert person_ids to strings for query (they're stored as strings in DB)
        person_ids_str = [str(pid) for pid in person_ids]

        leads_result = supabase.table('leads').select(
            'fub_person_id, first_name, last_name, email, phone'
        ).in_('fub_person_id', person_ids_str).execute()

        # Create lookup dict with int keys for easier matching
        lead_info = {int(l['fub_person_id']): l for l in (leads_result.data or [])}
    except Exception as e:
        print(f"⚠️  Could not fetch lead names: {e}")
        lead_info = {}

    # Display each lead
    for idx, lead in enumerate(ai_leads, 1):
        person_id = int(lead.get('fub_person_id', 0))
        conv = conv_by_person.get(person_id, {})
        msgs = msg_counts.get(person_id, {'sent': 0, 'received': 0, 'last_activity': None})
        info = lead_info.get(person_id, {})

        state = conv.get('state', 'no_conversation')
        score = conv.get('lead_score', 0)

        # Get name
        first_name = info.get('first_name', 'Unknown')
        last_name = info.get('last_name', '')
        full_name = f"{first_name} {last_name}".strip()

        print(f"\n{'─'*80}")
        print(f"Lead #{idx}: {full_name} (Person ID: {person_id})")
        print(f"{'─'*80}")

        # Contact info
        email = info.get('email', 'N/A')
        phone = info.get('phone', 'N/A')
        print(f"📧 Email: {email}")
        print(f"📱 Phone: {phone}")

        # AI Status
        print(f"\n🤖 AI Status:")
        print(f"   Enabled: ✅ Yes")
        print(f"   Enabled At: {format_datetime(lead.get('enabled_at'))}")
        print(f"   Enabled By: {lead.get('enabled_by', 'System')}")
        print(f"   Reason: {lead.get('reason', 'N/A')}")

        # Conversation State
        print(f"\n💬 Conversation:")

        # State emoji mapping
        state_emoji = {
            'initial': '🆕',
            'qualifying': '❓',
            'objection_handling': '🛡️',
            'scheduling': '📅',
            'nurture': '🌱',
            'handed_off': '🤝',
            'completed': '✅',
            'engaged': '👥',
            'no_conversation': '❌'
        }

        emoji = state_emoji.get(state, '❔')
        print(f"   State: {emoji} {state.upper().replace('_', ' ')}")

        # Score with color coding
        if score:
            if score >= 80:
                score_indicator = "🔥 HOT"
            elif score >= 60:
                score_indicator = "🌡️  WARM"
            elif score >= 40:
                score_indicator = "❄️  COOL"
            else:
                score_indicator = "🧊 COLD"
            print(f"   Score: {score}/100 {score_indicator}")
        else:
            print(f"   Score: Not scored yet")

        # Handoff reason if applicable
        if state == 'handed_off':
            handoff_reason = conv.get('handoff_reason', 'N/A')
            print(f"   Handoff Reason: {handoff_reason}")

        # Messages
        print(f"\n📨 Messages:")
        print(f"   Sent by AI: {msgs['sent']}")
        print(f"   Received from Lead: {msgs['received']}")

        # Response rate
        if msgs['sent'] > 0:
            response_rate = (msgs['received'] / msgs['sent']) * 100
            print(f"   Response Rate: {response_rate:.1f}%")

        # Last activity
        last_activity = msgs.get('last_activity') or conv.get('updated_at')
        print(f"   Last Activity: {format_datetime(last_activity)}")
        print(f"   Last AI Message: {format_datetime(conv.get('last_ai_message_at'))}")
        print(f"   Last Lead Response: {format_datetime(conv.get('last_lead_response_at'))}")

        # Qualification data
        qual_data = conv.get('qualification_data', {}) or {}
        if qual_data:
            print(f"\n📋 Qualification Data:")

            if qual_data.get('timeline'):
                print(f"   Timeline: {qual_data['timeline']}")
            if qual_data.get('budget'):
                print(f"   Budget: {qual_data['budget']}")
            if qual_data.get('location'):
                print(f"   Location: {qual_data['location']}")
            if qual_data.get('property_type'):
                print(f"   Property Type: {qual_data['property_type']}")
            if qual_data.get('motivation'):
                print(f"   Motivation: {qual_data['motivation']}")
            if 'pre_approved' in qual_data:
                pre_app = "✅ Yes" if qual_data['pre_approved'] else "❌ No"
                print(f"   Pre-Approved: {pre_app}")

    # Summary stats
    print(f"\n\n{'='*80}")
    print("SUMMARY STATISTICS")
    print(f"{'='*80}")

    # Count by state
    states = {}
    for person_id in person_ids:
        conv = conv_by_person.get(person_id, {})
        state = conv.get('state', 'no_conversation')
        states[state] = states.get(state, 0) + 1

    print(f"\n📊 Leads by State:")
    for state, count in sorted(states.items(), key=lambda x: x[1], reverse=True):
        print(f"   {state.upper().replace('_', ' ')}: {count}")

    # Score distribution
    scores = [conv_by_person.get(pid, {}).get('lead_score', 0) for pid in person_ids]
    valid_scores = [s for s in scores if s and s > 0]

    if valid_scores:
        print(f"\n🎯 Score Distribution:")
        hot = len([s for s in valid_scores if s >= 80])
        warm = len([s for s in valid_scores if 60 <= s < 80])
        cool = len([s for s in valid_scores if 40 <= s < 60])
        cold = len([s for s in valid_scores if s < 40])

        print(f"   🔥 HOT (80+): {hot}")
        print(f"   🌡️  WARM (60-79): {warm}")
        print(f"   ❄️  COOL (40-59): {cool}")
        print(f"   🧊 COLD (<40): {cold}")
        print(f"   Average Score: {sum(valid_scores)/len(valid_scores):.1f}")

    # Message stats
    total_sent = sum(msgs['sent'] for msgs in msg_counts.values())
    total_received = sum(msgs['received'] for msgs in msg_counts.values())

    print(f"\n📬 Message Stats:")
    print(f"   Total Sent: {total_sent}")
    print(f"   Total Received: {total_received}")
    if total_sent > 0:
        print(f"   Overall Response Rate: {(total_received/total_sent)*100:.1f}%")

    print(f"\n{'='*80}\n")

if __name__ == '__main__':
    try:
        get_ai_enabled_leads()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
