"""
AI Email Service - Send AI-generated emails to leads with FUB integration.

This service handles:
- Sending personalized AI emails via SMTP
- Logging emails to Follow Up Boss for timeline tracking
- AI-specific email templates for lead engagement
- Integration with the AI agent for dynamic content

Email types:
- Welcome/Initial contact emails
- Follow-up sequences
- Market updates
- Property recommendations
- Appointment confirmations
- Re-engagement campaigns
"""

import os
import logging
import base64
import smtplib
import aiohttp
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from flask import render_template_string

from app.utils.constants import Credentials

logger = logging.getLogger(__name__)


class EmailCategory(Enum):
    """Categories of AI-generated emails."""
    WELCOME = "welcome"
    FOLLOW_UP = "follow_up"
    MARKET_UPDATE = "market_update"
    PROPERTY_ALERT = "property_alert"
    APPOINTMENT_CONFIRM = "appointment_confirm"
    APPOINTMENT_REMINDER = "appointment_reminder"
    RE_ENGAGEMENT = "re_engagement"
    NURTURE = "nurture"
    QUALIFICATION = "qualification"
    VALUE_CONTENT = "value_content"


@dataclass
class EmailResult:
    """Result of an email send operation."""
    success: bool
    email_id: Optional[str] = None
    fub_email_id: Optional[int] = None
    error: Optional[str] = None
    delivered_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "email_id": self.email_id,
            "fub_email_id": self.fub_email_id,
            "error": self.error,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
        }


class AIEmailService:
    """
    Service for sending AI-generated emails with FUB integration.

    Combines SMTP email delivery with FUB logging so emails appear
    in the lead's timeline within Follow Up Boss.
    """

    def __init__(
        self,
        smtp_server: str = None,
        smtp_port: int = None,
        smtp_username: str = None,
        smtp_password: str = None,
        fub_api_key: str = None,
    ):
        """
        Initialize AI Email Service.

        Args:
            smtp_server: SMTP server hostname
            smtp_port: SMTP server port
            smtp_username: SMTP login username
            smtp_password: SMTP login password
            fub_api_key: Follow Up Boss API key
        """
        # SMTP settings
        self.smtp_server = smtp_server or os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
        self.smtp_port = smtp_port or int(os.environ.get('MAIL_PORT', 587))
        self.smtp_username = smtp_username or os.environ.get('MAIL_USERNAME', '')
        self.smtp_password = smtp_password or os.environ.get('MAIL_PASSWORD', '')
        self.use_tls = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
        self.default_sender = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@leadsynergy.com')
        self.default_sender_name = os.environ.get('MAIL_SENDER_NAME', 'LeadSynergy')

        # FUB settings
        self.creds = Credentials()
        self.fub_api_key = fub_api_key or self.creds.FUB_API_KEY
        self.fub_base_url = "https://api.followupboss.com/v1/"
        self.fub_auth_header = f"Basic {base64.b64encode(f'{self.fub_api_key}:'.encode()).decode()}"
        self.fub_headers = {
            'Content-Type': "application/json",
            'Authorization': self.fub_auth_header,
        }

        # App settings
        self.app_name = os.environ.get('APP_NAME', 'LeadSynergy')
        self.frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:3000')

    def _get_fub_headers(self, system_name: str = None, system_key: str = None) -> Dict[str, str]:
        """Get FUB headers with optional system identification."""
        headers = self.fub_headers.copy()
        if system_name:
            headers['X-System'] = system_name
        if system_key:
            headers['X-System-Key'] = system_key
        return headers

    def _get_smtp_connection(self):
        """Create SMTP connection."""
        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            if self.use_tls:
                server.starttls()
            if self.smtp_username and self.smtp_password:
                server.login(self.smtp_username, self.smtp_password)
            return server
        except Exception as e:
            logger.error(f"Failed to connect to SMTP server: {e}")
            raise

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        fub_person_id: Optional[int] = None,
        fub_user_id: Optional[int] = None,
        category: EmailCategory = EmailCategory.FOLLOW_UP,
        template_id: Optional[str] = None,
        log_to_fub: bool = True,
    ) -> EmailResult:
        """
        Send an email with optional FUB logging.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_content: HTML body content
            text_content: Plain text fallback (generated from HTML if not provided)
            from_email: Sender email address
            from_name: Sender display name
            fub_person_id: FUB person ID to log email against
            fub_user_id: FUB user ID sending the email
            category: Email category for tracking
            template_id: Template identifier for analytics
            log_to_fub: Whether to log email to FUB timeline

        Returns:
            EmailResult with success status and IDs
        """
        email_id = None
        fub_email_id = None

        # Generate plain text if not provided
        if not text_content:
            text_content = self._html_to_text(html_content)

        # Build sender address
        sender = from_email or self.default_sender
        sender_name = from_name or self.default_sender_name
        formatted_sender = f"{sender_name} <{sender}>" if sender_name else sender

        try:
            # Create email message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = formatted_sender
            msg['To'] = to_email
            msg['X-Email-Category'] = category.value
            if template_id:
                msg['X-Template-ID'] = template_id

            # Add plain text version
            part1 = MIMEText(text_content, 'plain')
            msg.attach(part1)

            # Add HTML version
            part2 = MIMEText(html_content, 'html')
            msg.attach(part2)

            # Send via SMTP
            with self._get_smtp_connection() as server:
                server.sendmail(sender, [to_email], msg.as_string())

            email_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{to_email[:10]}"
            logger.info(f"Email sent to {to_email}: {subject}")

            # Log to FUB if enabled and person_id provided
            if log_to_fub and fub_person_id:
                fub_result = self._log_email_to_fub(
                    person_id=fub_person_id,
                    to_email=to_email,
                    subject=subject,
                    body=html_content,
                    user_id=fub_user_id,
                )
                if fub_result.get("success"):
                    fub_email_id = fub_result.get("email_id")

            return EmailResult(
                success=True,
                email_id=email_id,
                fub_email_id=fub_email_id,
                delivered_at=datetime.now(),
            )

        except Exception as e:
            error_msg = f"Failed to send email to {to_email}: {str(e)}"
            logger.error(error_msg)
            return EmailResult(
                success=False,
                error=error_msg,
            )

    async def send_email_async(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        fub_person_id: Optional[int] = None,
        fub_user_id: Optional[int] = None,
        category: EmailCategory = EmailCategory.FOLLOW_UP,
        template_id: Optional[str] = None,
        log_to_fub: bool = True,
    ) -> EmailResult:
        """Send email asynchronously."""
        # For now, use sync SMTP sending (can be enhanced with aiosmtplib later)
        # The FUB logging is done async

        email_id = None
        fub_email_id = None

        if not text_content:
            text_content = self._html_to_text(html_content)

        sender = from_email or self.default_sender
        sender_name = from_name or self.default_sender_name
        formatted_sender = f"{sender_name} <{sender}>" if sender_name else sender

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = formatted_sender
            msg['To'] = to_email

            part1 = MIMEText(text_content, 'plain')
            msg.attach(part1)

            part2 = MIMEText(html_content, 'html')
            msg.attach(part2)

            with self._get_smtp_connection() as server:
                server.sendmail(sender, [to_email], msg.as_string())

            email_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{to_email[:10]}"
            logger.info(f"Email sent to {to_email}: {subject}")

            # Log to FUB async
            if log_to_fub and fub_person_id:
                fub_result = await self._log_email_to_fub_async(
                    person_id=fub_person_id,
                    to_email=to_email,
                    subject=subject,
                    body=html_content,
                    user_id=fub_user_id,
                )
                if fub_result.get("success"):
                    fub_email_id = fub_result.get("email_id")

            return EmailResult(
                success=True,
                email_id=email_id,
                fub_email_id=fub_email_id,
                delivered_at=datetime.now(),
            )

        except Exception as e:
            error_msg = f"Failed to send email to {to_email}: {str(e)}"
            logger.error(error_msg)
            return EmailResult(
                success=False,
                error=error_msg,
            )

    def _log_email_to_fub(
        self,
        person_id: int,
        to_email: str,
        subject: str,
        body: str,
        user_id: int = None,
    ) -> Dict[str, Any]:
        """
        Log sent email to Follow Up Boss.

        Args:
            person_id: FUB person ID
            to_email: Recipient email
            subject: Email subject
            body: Email body (HTML)
            user_id: FUB user ID who sent it

        Returns:
            Dict with success status and email ID
        """
        headers = self._get_fub_headers(
            self.creds.get('AI_AGENT_SYSTEM_NAME', 'leadsynergy-ai'),
            self.creds.get('AI_AGENT_SYSTEM_KEY'),
        )

        payload = {
            "personId": person_id,
            "to": to_email,
            "subject": subject,
            "body": body,
            "isIncoming": False,
        }

        if user_id:
            payload["userId"] = user_id

        try:
            response = requests.post(
                f"{self.fub_base_url}emails",
                headers=headers,
                json=payload,
                timeout=30,
            )

            if response.status_code in [200, 201]:
                result = response.json()
                logger.info(f"Email logged to FUB for person {person_id}")
                return {
                    "success": True,
                    "email_id": result.get("id"),
                    "data": result,
                }
            else:
                error_msg = f"FUB API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                }

        except Exception as e:
            error_msg = f"Failed to log email to FUB: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
            }

    async def _log_email_to_fub_async(
        self,
        person_id: int,
        to_email: str,
        subject: str,
        body: str,
        user_id: int = None,
    ) -> Dict[str, Any]:
        """Log email to FUB asynchronously."""
        headers = self._get_fub_headers(
            self.creds.get('AI_AGENT_SYSTEM_NAME', 'leadsynergy-ai'),
            self.creds.get('AI_AGENT_SYSTEM_KEY'),
        )

        payload = {
            "personId": person_id,
            "to": to_email,
            "subject": subject,
            "body": body,
            "isIncoming": False,
        }

        if user_id:
            payload["userId"] = user_id

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.fub_base_url}emails",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status in [200, 201]:
                        result = await response.json()
                        logger.info(f"Email logged to FUB for person {person_id}")
                        return {
                            "success": True,
                            "email_id": result.get("id"),
                            "data": result,
                        }
                    else:
                        error_text = await response.text()
                        error_msg = f"FUB API error {response.status}: {error_text}"
                        logger.error(error_msg)
                        return {
                            "success": False,
                            "error": error_msg,
                        }

        except Exception as e:
            error_msg = f"Failed to log email to FUB: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
            }

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text (basic implementation)."""
        import re
        # Remove style and script tags
        text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        # Replace <br> and </p> with newlines
        text = re.sub(r'<br\s*/?>|</p>|</div>|</tr>', '\n', text, flags=re.IGNORECASE)
        # Remove remaining HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Decode common HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        # Collapse multiple whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        return text.strip()

    # ==========================================================================
    # AI Email Templates
    # ==========================================================================

    def send_ai_welcome_email(
        self,
        to_email: str,
        lead_name: str,
        agent_name: str,
        agent_email: str,
        agent_phone: str = None,
        fub_person_id: int = None,
        fub_user_id: int = None,
        location_interest: str = None,
    ) -> EmailResult:
        """
        Send AI-generated welcome email to new lead.

        Args:
            to_email: Lead email address
            lead_name: Lead's first name
            agent_name: Agent's name
            agent_email: Agent's email for reply
            agent_phone: Agent's phone (optional)
            fub_person_id: FUB person ID
            fub_user_id: FUB user ID
            location_interest: Area lead is interested in
        """
        subject = f"Hey {lead_name}! Let's find your perfect home"

        html_content = self._render_template('ai_welcome', {
            'lead_name': lead_name,
            'agent_name': agent_name,
            'agent_email': agent_email,
            'agent_phone': agent_phone,
            'location_interest': location_interest or 'your area',
            'year': datetime.now().year,
        })

        return self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            from_email=agent_email,
            from_name=agent_name,
            fub_person_id=fub_person_id,
            fub_user_id=fub_user_id,
            category=EmailCategory.WELCOME,
            template_id='ai_welcome_v1',
        )

    def send_ai_follow_up_email(
        self,
        to_email: str,
        lead_name: str,
        agent_name: str,
        agent_email: str,
        message_content: str,
        subject: str = None,
        fub_person_id: int = None,
        fub_user_id: int = None,
        category: EmailCategory = EmailCategory.FOLLOW_UP,
    ) -> EmailResult:
        """
        Send AI-generated follow-up email.

        Args:
            to_email: Lead email
            lead_name: Lead's name
            agent_name: Agent's name
            agent_email: Reply-to email
            message_content: AI-generated message body
            subject: Email subject (generated if not provided)
            fub_person_id: FUB person ID
            fub_user_id: FUB user ID
            category: Email category
        """
        if not subject:
            subject = f"Quick follow-up, {lead_name}"

        html_content = self._render_template('ai_follow_up', {
            'lead_name': lead_name,
            'agent_name': agent_name,
            'agent_email': agent_email,
            'message_content': message_content,
            'year': datetime.now().year,
        })

        return self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            from_email=agent_email,
            from_name=agent_name,
            fub_person_id=fub_person_id,
            fub_user_id=fub_user_id,
            category=category,
        )

    def send_market_update_email(
        self,
        to_email: str,
        lead_name: str,
        agent_name: str,
        agent_email: str,
        market_area: str,
        market_highlights: List[str],
        fub_person_id: int = None,
        fub_user_id: int = None,
    ) -> EmailResult:
        """
        Send market update email.

        Args:
            to_email: Lead email
            lead_name: Lead name
            agent_name: Agent name
            agent_email: Agent email
            market_area: Location for market update
            market_highlights: List of market highlights/stats
            fub_person_id: FUB person ID
            fub_user_id: FUB user ID
        """
        subject = f"What's happening in {market_area} - Market Update"

        html_content = self._render_template('market_update', {
            'lead_name': lead_name,
            'agent_name': agent_name,
            'agent_email': agent_email,
            'market_area': market_area,
            'market_highlights': market_highlights,
            'year': datetime.now().year,
        })

        return self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            from_email=agent_email,
            from_name=agent_name,
            fub_person_id=fub_person_id,
            fub_user_id=fub_user_id,
            category=EmailCategory.MARKET_UPDATE,
            template_id='market_update_v1',
        )

    def send_appointment_confirmation_email(
        self,
        to_email: str,
        lead_name: str,
        agent_name: str,
        agent_email: str,
        agent_phone: str,
        appointment_date: str,
        appointment_time: str,
        appointment_type: str,
        location: str = None,
        fub_person_id: int = None,
        fub_user_id: int = None,
    ) -> EmailResult:
        """
        Send appointment confirmation email.

        Args:
            to_email: Lead email
            lead_name: Lead name
            agent_name: Agent name
            agent_email: Agent email
            agent_phone: Agent phone
            appointment_date: Date string
            appointment_time: Time string
            appointment_type: Type of appointment (e.g., "consultation", "showing")
            location: Meeting location
            fub_person_id: FUB person ID
            fub_user_id: FUB user ID
        """
        subject = f"You're all set! {appointment_type.title()} on {appointment_date}"

        html_content = self._render_template('appointment_confirm', {
            'lead_name': lead_name,
            'agent_name': agent_name,
            'agent_email': agent_email,
            'agent_phone': agent_phone,
            'appointment_date': appointment_date,
            'appointment_time': appointment_time,
            'appointment_type': appointment_type,
            'location': location,
            'year': datetime.now().year,
        })

        return self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            from_email=agent_email,
            from_name=agent_name,
            fub_person_id=fub_person_id,
            fub_user_id=fub_user_id,
            category=EmailCategory.APPOINTMENT_CONFIRM,
            template_id='appointment_confirm_v1',
        )

    def send_appointment_reminder_email(
        self,
        to_email: str,
        lead_name: str,
        agent_name: str,
        agent_email: str,
        agent_phone: str,
        appointment_date: str,
        appointment_time: str,
        appointment_type: str,
        fub_person_id: int = None,
        fub_user_id: int = None,
    ) -> EmailResult:
        """Send appointment reminder email."""
        subject = f"Reminder: {appointment_type.title()} tomorrow at {appointment_time}"

        html_content = self._render_template('appointment_reminder', {
            'lead_name': lead_name,
            'agent_name': agent_name,
            'agent_email': agent_email,
            'agent_phone': agent_phone,
            'appointment_date': appointment_date,
            'appointment_time': appointment_time,
            'appointment_type': appointment_type,
            'year': datetime.now().year,
        })

        return self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            from_email=agent_email,
            from_name=agent_name,
            fub_person_id=fub_person_id,
            fub_user_id=fub_user_id,
            category=EmailCategory.APPOINTMENT_REMINDER,
            template_id='appointment_reminder_v1',
        )

    def send_re_engagement_email(
        self,
        to_email: str,
        lead_name: str,
        agent_name: str,
        agent_email: str,
        message_content: str,
        fub_person_id: int = None,
        fub_user_id: int = None,
    ) -> EmailResult:
        """
        Send re-engagement email to cold lead.

        Args:
            to_email: Lead email
            lead_name: Lead name
            agent_name: Agent name
            agent_email: Agent email
            message_content: AI-generated re-engagement message
            fub_person_id: FUB person ID
            fub_user_id: FUB user ID
        """
        subject = f"Hey {lead_name}, still thinking about making a move?"

        html_content = self._render_template('re_engagement', {
            'lead_name': lead_name,
            'agent_name': agent_name,
            'agent_email': agent_email,
            'message_content': message_content,
            'year': datetime.now().year,
        })

        return self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            from_email=agent_email,
            from_name=agent_name,
            fub_person_id=fub_person_id,
            fub_user_id=fub_user_id,
            category=EmailCategory.RE_ENGAGEMENT,
            template_id='re_engagement_v1',
        )

    def _render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render an email template with context."""
        templates = {
            'ai_welcome': AI_WELCOME_TEMPLATE,
            'ai_follow_up': AI_FOLLOW_UP_TEMPLATE,
            'market_update': MARKET_UPDATE_TEMPLATE,
            'appointment_confirm': APPOINTMENT_CONFIRM_TEMPLATE,
            'appointment_reminder': APPOINTMENT_REMINDER_TEMPLATE,
            're_engagement': RE_ENGAGEMENT_TEMPLATE,
        }

        template = templates.get(template_name, AI_FOLLOW_UP_TEMPLATE)
        return render_template_string(template, **context)


class AIEmailServiceSingleton:
    """Singleton wrapper for AI Email Service."""

    _instance: Optional[AIEmailService] = None

    @classmethod
    def get_instance(cls) -> AIEmailService:
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = AIEmailService()
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset the singleton instance."""
        cls._instance = None


# Convenience function
def get_ai_email_service() -> AIEmailService:
    """Get AI email service instance."""
    return AIEmailServiceSingleton.get_instance()


# =============================================================================
# AI Email Templates - Friendly & Casual Tone
# =============================================================================

AI_WELCOME_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Let's find your perfect home!</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif; background-color: #f8fafc;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" style="width: 600px; max-width: 100%; border-collapse: collapse; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.07);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 30px;">
                            <p style="margin: 0; font-size: 24px; color: #1e293b; font-weight: 600;">
                                Hey {{ lead_name }}! 👋
                            </p>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding: 0 40px 30px;">
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.7; color: #475569;">
                                I saw you were looking at homes in {{ location_interest }} - great choice!
                                I'd love to help you find the perfect place.
                            </p>
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.7; color: #475569;">
                                A little about me: I'm {{ agent_name }}, and I've been helping people find
                                their dream homes for years. I know the area really well and I'm here to
                                make your search as smooth as possible.
                            </p>
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.7; color: #475569;">
                                What's your timeline looking like? Are you just starting to explore,
                                or are you getting closer to making a move?
                            </p>
                            <p style="margin: 0; font-size: 16px; line-height: 1.7; color: #475569;">
                                Just hit reply and let me know - I'd love to hear what you're looking for!
                            </p>
                        </td>
                    </tr>
                    <!-- Signature -->
                    <tr>
                        <td style="padding: 30px 40px; border-top: 1px solid #e2e8f0;">
                            <p style="margin: 0 0 5px; font-size: 16px; font-weight: 600; color: #1e293b;">
                                {{ agent_name }}
                            </p>
                            <p style="margin: 0 0 5px; font-size: 14px; color: #64748b;">
                                {{ agent_email }}
                            </p>
                            {% if agent_phone %}
                            <p style="margin: 0; font-size: 14px; color: #64748b;">
                                {{ agent_phone }}
                            </p>
                            {% endif %}
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 40px; background-color: #f8fafc; border-radius: 0 0 12px 12px; text-align: center;">
                            <p style="margin: 0; font-size: 12px; color: #94a3b8;">
                                &copy; {{ year }} All rights reserved
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

AI_FOLLOW_UP_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Following up</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif; background-color: #f8fafc;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" style="width: 600px; max-width: 100%; border-collapse: collapse; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.07);">
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.7; color: #475569;">
                                Hey {{ lead_name }},
                            </p>
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.7; color: #475569;">
                                {{ message_content }}
                            </p>
                            <p style="margin: 0; font-size: 16px; line-height: 1.7; color: #475569;">
                                Talk soon!
                            </p>
                        </td>
                    </tr>
                    <!-- Signature -->
                    <tr>
                        <td style="padding: 0 40px 40px;">
                            <p style="margin: 0 0 5px; font-size: 16px; font-weight: 600; color: #1e293b;">
                                {{ agent_name }}
                            </p>
                            <p style="margin: 0; font-size: 14px; color: #64748b;">
                                {{ agent_email }}
                            </p>
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 40px; background-color: #f8fafc; border-radius: 0 0 12px 12px; text-align: center;">
                            <p style="margin: 0; font-size: 12px; color: #94a3b8;">
                                &copy; {{ year }} All rights reserved
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

MARKET_UPDATE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Market Update</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif; background-color: #f8fafc;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" style="width: 600px; max-width: 100%; border-collapse: collapse; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.07);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px;">
                            <p style="margin: 0; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; color: #3b82f6;">
                                Market Update
                            </p>
                            <p style="margin: 10px 0 0; font-size: 24px; font-weight: 600; color: #1e293b;">
                                What's happening in {{ market_area }}
                            </p>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding: 20px 40px 30px;">
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.7; color: #475569;">
                                Hey {{ lead_name }}!
                            </p>
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.7; color: #475569;">
                                Thought you might like a quick update on what's happening in {{ market_area }}:
                            </p>
                            <!-- Highlights -->
                            <div style="background-color: #f1f5f9; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                                {% for highlight in market_highlights %}
                                <p style="margin: {% if loop.first %}0{% else %}15px 0 0{% endif %}; font-size: 15px; line-height: 1.6; color: #334155;">
                                    • {{ highlight }}
                                </p>
                                {% endfor %}
                            </div>
                            <p style="margin: 0; font-size: 16px; line-height: 1.7; color: #475569;">
                                Want me to send you listings that match what you're looking for?
                                Just reply and let me know!
                            </p>
                        </td>
                    </tr>
                    <!-- Signature -->
                    <tr>
                        <td style="padding: 0 40px 40px;">
                            <p style="margin: 0 0 5px; font-size: 16px; font-weight: 600; color: #1e293b;">
                                {{ agent_name }}
                            </p>
                            <p style="margin: 0; font-size: 14px; color: #64748b;">
                                {{ agent_email }}
                            </p>
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 40px; background-color: #f8fafc; border-radius: 0 0 12px 12px; text-align: center;">
                            <p style="margin: 0; font-size: 12px; color: #94a3b8;">
                                &copy; {{ year }} All rights reserved
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

APPOINTMENT_CONFIRM_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>You're all set!</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif; background-color: #f8fafc;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" style="width: 600px; max-width: 100%; border-collapse: collapse; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.07);">
                    <!-- Header with checkmark -->
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center;">
                            <div style="width: 60px; height: 60px; background-color: #10b981; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 20px;">
                                <span style="font-size: 30px; color: white;">✓</span>
                            </div>
                            <p style="margin: 0; font-size: 24px; font-weight: 600; color: #1e293b;">
                                You're all set!
                            </p>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding: 20px 40px 30px;">
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.7; color: #475569;">
                                Hey {{ lead_name }}, your {{ appointment_type }} is confirmed!
                            </p>
                            <!-- Appointment details box -->
                            <div style="background-color: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                                <table style="width: 100%; border-collapse: collapse;">
                                    <tr>
                                        <td style="padding: 8px 0; font-size: 14px; color: #64748b;">Date</td>
                                        <td style="padding: 8px 0; font-size: 16px; font-weight: 600; color: #1e293b; text-align: right;">{{ appointment_date }}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 8px 0; font-size: 14px; color: #64748b;">Time</td>
                                        <td style="padding: 8px 0; font-size: 16px; font-weight: 600; color: #1e293b; text-align: right;">{{ appointment_time }}</td>
                                    </tr>
                                    {% if location %}
                                    <tr>
                                        <td style="padding: 8px 0; font-size: 14px; color: #64748b;">Location</td>
                                        <td style="padding: 8px 0; font-size: 16px; font-weight: 600; color: #1e293b; text-align: right;">{{ location }}</td>
                                    </tr>
                                    {% endif %}
                                </table>
                            </div>
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.7; color: #475569;">
                                I'll send you a reminder before we meet. If anything comes up or you need
                                to reschedule, just let me know - no worries at all!
                            </p>
                            <p style="margin: 0; font-size: 16px; line-height: 1.7; color: #475569;">
                                Looking forward to chatting with you!
                            </p>
                        </td>
                    </tr>
                    <!-- Contact Info -->
                    <tr>
                        <td style="padding: 20px 40px; background-color: #f8fafc;">
                            <p style="margin: 0 0 10px; font-size: 14px; font-weight: 600; color: #64748b;">
                                Need to reach me?
                            </p>
                            <p style="margin: 0 0 5px; font-size: 16px; font-weight: 600; color: #1e293b;">
                                {{ agent_name }}
                            </p>
                            <p style="margin: 0 0 5px; font-size: 14px; color: #64748b;">
                                📧 {{ agent_email }}
                            </p>
                            <p style="margin: 0; font-size: 14px; color: #64748b;">
                                📱 {{ agent_phone }}
                            </p>
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 40px; background-color: #f8fafc; border-radius: 0 0 12px 12px; text-align: center;">
                            <p style="margin: 0; font-size: 12px; color: #94a3b8;">
                                &copy; {{ year }} All rights reserved
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

APPOINTMENT_REMINDER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reminder: Tomorrow!</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif; background-color: #f8fafc;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" style="width: 600px; max-width: 100%; border-collapse: collapse; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.07);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px;">
                            <p style="margin: 0; font-size: 14px; font-weight: 600; color: #f59e0b;">
                                ⏰ REMINDER
                            </p>
                            <p style="margin: 10px 0 0; font-size: 24px; font-weight: 600; color: #1e293b;">
                                See you tomorrow!
                            </p>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding: 20px 40px 30px;">
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.7; color: #475569;">
                                Hey {{ lead_name }}! Just a friendly reminder about our {{ appointment_type }} tomorrow.
                            </p>
                            <!-- Appointment details -->
                            <div style="background-color: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                                <p style="margin: 0 0 10px; font-size: 18px; font-weight: 600; color: #1e293b;">
                                    {{ appointment_date }} at {{ appointment_time }}
                                </p>
                                <p style="margin: 0; font-size: 14px; color: #92400e;">
                                    {{ appointment_type | capitalize }}
                                </p>
                            </div>
                            <p style="margin: 0; font-size: 16px; line-height: 1.7; color: #475569;">
                                If you need to reschedule or have any questions before we meet,
                                just give me a call or shoot me a text!
                            </p>
                        </td>
                    </tr>
                    <!-- Contact Info -->
                    <tr>
                        <td style="padding: 20px 40px; background-color: #f8fafc;">
                            <p style="margin: 0 0 5px; font-size: 16px; font-weight: 600; color: #1e293b;">
                                {{ agent_name }}
                            </p>
                            <p style="margin: 0 0 5px; font-size: 14px; color: #64748b;">
                                {{ agent_email }}
                            </p>
                            <p style="margin: 0; font-size: 14px; color: #64748b;">
                                {{ agent_phone }}
                            </p>
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 40px; background-color: #f8fafc; border-radius: 0 0 12px 12px; text-align: center;">
                            <p style="margin: 0; font-size: 12px; color: #94a3b8;">
                                &copy; {{ year }} All rights reserved
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

RE_ENGAGEMENT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Checking in</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif; background-color: #f8fafc;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" style="width: 600px; max-width: 100%; border-collapse: collapse; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.07);">
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.7; color: #475569;">
                                Hey {{ lead_name }}!
                            </p>
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.7; color: #475569;">
                                {{ message_content }}
                            </p>
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.7; color: #475569;">
                                No pressure at all - just wanted to check in and see how things are going!
                            </p>
                            <p style="margin: 0; font-size: 16px; line-height: 1.7; color: #475569;">
                                Hope to hear from you!
                            </p>
                        </td>
                    </tr>
                    <!-- Signature -->
                    <tr>
                        <td style="padding: 0 40px 40px;">
                            <p style="margin: 0 0 5px; font-size: 16px; font-weight: 600; color: #1e293b;">
                                {{ agent_name }}
                            </p>
                            <p style="margin: 0; font-size: 14px; color: #64748b;">
                                {{ agent_email }}
                            </p>
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 40px; background-color: #f8fafc; border-radius: 0 0 12px 12px; text-align: center;">
                            <p style="margin: 0; font-size: 12px; color: #94a3b8;">
                                &copy; {{ year }} All rights reserved
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
