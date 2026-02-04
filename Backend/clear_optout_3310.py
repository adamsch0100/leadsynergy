#!/usr/bin/env python3
"""Clear false opt-out for person 3310."""

import asyncio
from app.database.supabase_client import SupabaseClientSingleton
from app.ai_agent.compliance_checker import ComplianceChecker

async def main():
    supabase = SupabaseClientSingleton.get_instance()

    # Clear opt-out for person 3310
    result = supabase.table("sms_consent").update({
        "opted_out": False,
        "opted_out_at": None,
        "opt_out_reason": None,
    }).eq("fub_person_id", 3310).execute()

    print(f"Cleared opt-out for person 3310: {result.data}")

    # Also ensure AI is enabled for this lead
    ai_result = supabase.table("ai_conversations").update({
        "ai_enabled": True
    }).eq("fub_person_id", 3310).execute()

    print(f"Enabled AI for person 3310: {ai_result.data}")

if __name__ == "__main__":
    asyncio.run(main())
