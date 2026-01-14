"""
Messaging Module for LeadSynergy AI Agent.

Provides communication services:
- FUB SMS Service: Send/receive texts via Follow Up Boss native texting
- Email Service: Send emails via existing email infrastructure
- Message Queue: Scheduled message handling for follow-up sequences
"""

from app.messaging.fub_sms_service import (
    FUBSMSService,
    FUBSMSServiceSingleton,
    send_sms,
)

__all__ = [
    'FUBSMSService',
    'FUBSMSServiceSingleton',
    'send_sms',
]
