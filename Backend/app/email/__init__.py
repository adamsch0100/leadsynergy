"""
Email Module.
Provides email sending functionality with templates.

Functions:
- send_welcome_email - New user welcome
- send_credit_purchase_email - Bundle purchase confirmation
- send_low_credits_email - Low credit warning
- send_ticket_notification - Ticket status updates

AI Email Functions:
- send_ai_welcome_email - AI welcome for new leads
- send_ai_follow_up_email - AI follow-up messages
- send_market_update_email - Market update campaigns
- send_appointment_confirmation_email - Appointment confirmations
- send_appointment_reminder_email - Appointment reminders
- send_re_engagement_email - Cold lead re-engagement
"""

from flask import Blueprint

email_bp = Blueprint('email', __name__)

from app.email.email_service import EmailService, EmailServiceSingleton
from app.email.ai_email_service import (
    AIEmailService,
    AIEmailServiceSingleton,
    EmailCategory,
    EmailResult,
    get_ai_email_service,
)

__all__ = [
    # Standard email service
    'EmailService',
    'EmailServiceSingleton',
    # AI email service
    'AIEmailService',
    'AIEmailServiceSingleton',
    'EmailCategory',
    'EmailResult',
    'get_ai_email_service',
]
