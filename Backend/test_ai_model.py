"""
Test AI model configuration and connectivity.
This verifies OpenRouter/Grok is working correctly.
"""

import os
import sys
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def test_openrouter_connection():
    """Test OpenRouter API connection with Grok model."""
    print("=" * 80)
    print("TESTING OPENROUTER / GROK CONNECTION")
    print("=" * 80)
    print()

    # Check if API key is set
    api_key = os.getenv('OPENROUTER_API_KEY')

    if not api_key:
        print("[ERROR] OPENROUTER_API_KEY not set in environment")
        print()
        print("This needs to be set in Railway:")
        print("  1. Go to Railway dashboard")
        print("  2. Click on Worker service")
        print("  3. Go to Variables tab")
        print("  4. Add: OPENROUTER_API_KEY=your_key")
        print()
        print("Get your key from: https://openrouter.ai/keys")
        return False

    print(f"[OK] OPENROUTER_API_KEY is set: {api_key[:8]}...{api_key[-4:]}")
    print()

    # Test API call
    print("Testing Grok 4.1 Fast model...")
    print("-" * 80)

    try:
        import requests

        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "x-ai/grok-4.1-fast",
                "messages": [
                    {
                        "role": "user",
                        "content": "Say 'Hello! I am Grok from x.ai working via OpenRouter!' in exactly those words."
                    }
                ],
                "max_tokens": 50,
            },
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()
            message = data.get('choices', [{}])[0].get('message', {}).get('content', '')

            print("[SUCCESS] Grok responded:")
            print(f'"{message}"')
            print()
            print("[OK] Your AI model is working correctly!")
            return True

        elif response.status_code == 401:
            print("[ERROR] Authentication failed - Invalid API key")
            print()
            print("Your OPENROUTER_API_KEY may be:")
            print("  - Incorrect")
            print("  - Expired")
            print("  - Not activated")
            print()
            print("Get a new key from: https://openrouter.ai/keys")
            return False

        elif response.status_code == 402:
            print("[ERROR] Insufficient credits")
            print()
            print("Your OpenRouter account needs credits:")
            print("  1. Go to: https://openrouter.ai/credits")
            print("  2. Add credits to your account")
            print("  3. Retry")
            return False

        else:
            print(f"[ERROR] API request failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except requests.exceptions.Timeout:
        print("[ERROR] Request timed out")
        print("OpenRouter may be temporarily unavailable")
        return False

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Network error: {e}")
        return False

    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_database_model_config():
    """Check what model is configured in the database."""
    from app.database.supabase_client import SupabaseClientSingleton

    print()
    print("=" * 80)
    print("CHECKING DATABASE CONFIGURATION")
    print("=" * 80)
    print()

    supabase = SupabaseClientSingleton.get_instance()
    settings = supabase.table('ai_agent_settings').select('llm_model, agent_name, is_enabled').limit(1).execute()

    if settings.data:
        s = settings.data[0]
        model = s.get('llm_model', 'Not configured')
        agent = s.get('agent_name', 'Not set')
        enabled = s.get('is_enabled', False)

        print(f"Current configuration:")
        print(f"  Model: {model}")
        print(f"  Agent name: {agent}")
        print(f"  Status: {'ENABLED' if enabled else 'DISABLED'}")
        print()

        if model == 'x-ai/grok-4.1-fast':
            print("[OK] Using Grok 4.1 Fast via OpenRouter")
            print("     You need: OPENROUTER_API_KEY")
            print("     You don't need: ANTHROPIC_API_KEY or OPENAI_API_KEY")
        elif 'claude' in model.lower():
            print("[INFO] Using Anthropic Claude")
            print("      You need: ANTHROPIC_API_KEY")
        elif 'gpt' in model.lower():
            print("[INFO] Using OpenAI GPT")
            print("      You need: OPENAI_API_KEY")
        else:
            print(f"[WARNING] Unknown model: {model}")

    else:
        print("[WARNING] No AI agent settings found in database")

    print()
    print("=" * 80)


if __name__ == "__main__":
    # Check database config first
    check_database_model_config()

    # Test OpenRouter connection
    success = test_openrouter_connection()

    print()
    if success:
        print("[SUMMARY] Everything looks good!")
        print()
        print("Your AI agent will use:")
        print("  - Model: Grok 4.1 Fast (x-ai/grok-4.1-fast)")
        print("  - Provider: OpenRouter")
        print("  - Agent: Nadia")
        print()
    else:
        print("[SUMMARY] OpenRouter/Grok is not working correctly")
        print()
        print("Fix by setting OPENROUTER_API_KEY in Railway:")
        print("  1. Get key: https://openrouter.ai/keys")
        print("  2. Add credits: https://openrouter.ai/credits")
        print("  3. Set in Railway → Worker → Variables")
        print("  4. Redeploy: railway up --service worker")
        print()

    print("=" * 80)
