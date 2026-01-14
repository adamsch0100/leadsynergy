"""
Email Service.
Handles sending emails with templates via SMTP.
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from flask import render_template_string
from datetime import datetime

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails with templates."""

    def __init__(self):
        self.smtp_server = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.environ.get('MAIL_PORT', 587))
        self.smtp_username = os.environ.get('MAIL_USERNAME', '')
        self.smtp_password = os.environ.get('MAIL_PASSWORD', '')
        self.use_tls = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
        self.default_sender = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@referralbridge.com')
        self.app_name = os.environ.get('APP_NAME', 'ReferralBridge')
        self.frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:3000')

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
        from_email: Optional[str] = None
    ) -> bool:
        """
        Send an email.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML body content
            text_content: Plain text body (optional, for fallback)
            from_email: Sender email (optional, uses default)

        Returns:
            bool: True if sent successfully
        """
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = from_email or self.default_sender
            msg['To'] = to_email

            # Add plain text version
            if text_content:
                part1 = MIMEText(text_content, 'plain')
                msg.attach(part1)

            # Add HTML version
            part2 = MIMEText(html_content, 'html')
            msg.attach(part2)

            # Send
            with self._get_smtp_connection() as server:
                server.sendmail(msg['From'], [to_email], msg.as_string())

            logger.info(f"Email sent to {to_email}: {subject}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    def send_welcome_email(self, to_email: str, user_name: str) -> bool:
        """Send welcome email to new user."""
        subject = f"Welcome to {self.app_name}!"
        html_content = self._render_template('welcome', {
            'user_name': user_name,
            'app_name': self.app_name,
            'login_url': f"{self.frontend_url}/login",
            'year': datetime.now().year
        })
        return self.send_email(to_email, subject, html_content)

    def send_credit_purchase_email(
        self,
        to_email: str,
        user_name: str,
        bundle_name: str,
        credits: Dict[str, int],
        amount: float
    ) -> bool:
        """Send credit purchase confirmation."""
        subject = f"Credit Purchase Confirmation - {self.app_name}"
        html_content = self._render_template('credit_purchase', {
            'user_name': user_name,
            'bundle_name': bundle_name,
            'enhancement_credits': credits.get('enhancement', 0),
            'criminal_credits': credits.get('criminal', 0),
            'dnc_credits': credits.get('dnc', 0),
            'amount': f"${amount:.2f}",
            'app_name': self.app_name,
            'dashboard_url': f"{self.frontend_url}/admin/dashboard",
            'year': datetime.now().year
        })
        return self.send_email(to_email, subject, html_content)

    def send_low_credits_email(
        self,
        to_email: str,
        user_name: str,
        credit_type: str,
        remaining: int
    ) -> bool:
        """Send low credit warning email."""
        subject = f"Low {credit_type.title()} Credits Alert - {self.app_name}"
        html_content = self._render_template('low_credits', {
            'user_name': user_name,
            'credit_type': credit_type,
            'remaining': remaining,
            'app_name': self.app_name,
            'billing_url': f"{self.frontend_url}/admin/billing",
            'year': datetime.now().year
        })
        return self.send_email(to_email, subject, html_content)

    def send_ticket_created_email(
        self,
        to_email: str,
        user_name: str,
        ticket_id: int,
        subject: str
    ) -> bool:
        """Send ticket creation confirmation."""
        email_subject = f"Ticket #{ticket_id} Created - {self.app_name}"
        html_content = self._render_template('ticket_created', {
            'user_name': user_name,
            'ticket_id': ticket_id,
            'ticket_subject': subject,
            'app_name': self.app_name,
            'ticket_url': f"{self.frontend_url}/agent/support/tickets/{ticket_id}",
            'year': datetime.now().year
        })
        return self.send_email(to_email, email_subject, html_content)

    def send_ticket_assigned_email(
        self,
        to_email: str,
        admin_name: str,
        ticket_id: int,
        ticket_subject: str,
        user_name: str
    ) -> bool:
        """Send email to admin when ticket is assigned."""
        subject = f"Ticket #{ticket_id} Assigned to You - {self.app_name}"
        html_content = self._render_template('ticket_assigned', {
            'admin_name': admin_name,
            'ticket_id': ticket_id,
            'ticket_subject': ticket_subject,
            'user_name': user_name,
            'app_name': self.app_name,
            'ticket_url': f"{self.frontend_url}/admin/tickets/{ticket_id}",
            'year': datetime.now().year
        })
        return self.send_email(to_email, subject, html_content)

    def send_ticket_update_email(
        self,
        to_email: str,
        user_name: str,
        ticket_id: int,
        ticket_subject: str,
        new_status: str,
        note: Optional[str] = None
    ) -> bool:
        """Send ticket status update to user."""
        subject = f"Ticket #{ticket_id} Updated - {self.app_name}"
        html_content = self._render_template('ticket_update', {
            'user_name': user_name,
            'ticket_id': ticket_id,
            'ticket_subject': ticket_subject,
            'new_status': new_status,
            'note': note,
            'app_name': self.app_name,
            'ticket_url': f"{self.frontend_url}/agent/support/tickets/{ticket_id}",
            'year': datetime.now().year
        })
        return self.send_email(to_email, subject, html_content)

    def _render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render an email template with context."""
        templates = {
            'welcome': WELCOME_TEMPLATE,
            'credit_purchase': CREDIT_PURCHASE_TEMPLATE,
            'low_credits': LOW_CREDITS_TEMPLATE,
            'ticket_created': TICKET_CREATED_TEMPLATE,
            'ticket_assigned': TICKET_ASSIGNED_TEMPLATE,
            'ticket_update': TICKET_UPDATE_TEMPLATE,
        }

        template = templates.get(template_name, '')
        return render_template_string(template, **context)


class EmailServiceSingleton:
    """Singleton for EmailService."""

    _instance: Optional[EmailService] = None

    @classmethod
    def get_instance(cls) -> EmailService:
        if cls._instance is None:
            cls._instance = EmailService()
        return cls._instance


# =============================================================================
# Email Templates
# =============================================================================

WELCOME_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to {{ app_name }}</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif; background-color: #f4f4f5;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 0;">
                <table role="presentation" style="width: 600px; max-width: 100%; border-collapse: collapse; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center; background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%); border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px;">Welcome to {{ app_name }}!</h1>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #374151;">
                                Hi {{ user_name }},
                            </p>
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #374151;">
                                Thank you for signing up! We're excited to have you on board. {{ app_name }} helps you organize leads from all your referral sources and enhance them with powerful data tools.
                            </p>
                            <p style="margin: 0 0 30px; font-size: 16px; line-height: 1.6; color: #374151;">
                                Here's what you can do:
                            </p>
                            <ul style="margin: 0 0 30px; padding-left: 20px; color: #374151;">
                                <li style="margin-bottom: 10px;">Aggregate leads from multiple referral platforms</li>
                                <li style="margin-bottom: 10px;">Enrich contact data with 7 search types</li>
                                <li style="margin-bottom: 10px;">Check DNC compliance instantly</li>
                                <li style="margin-bottom: 10px;">Sync everything with Follow Up Boss</li>
                            </ul>
                            <table role="presentation" style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td align="center">
                                        <a href="{{ login_url }}" style="display: inline-block; padding: 14px 32px; background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%); color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 16px;">
                                            Go to Dashboard
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 40px; background-color: #f9fafb; border-radius: 0 0 8px 8px; text-align: center;">
                            <p style="margin: 0; font-size: 14px; color: #6b7280;">
                                &copy; {{ year }} {{ app_name }}. All rights reserved.
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

CREDIT_PURCHASE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Credit Purchase Confirmation</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif; background-color: #f4f4f5;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 0;">
                <table role="presentation" style="width: 600px; max-width: 100%; border-collapse: collapse; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center; background: linear-gradient(135deg, #10b981 0%, #059669 100%); border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px;">Purchase Confirmed!</h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #374151;">
                                Hi {{ user_name }},
                            </p>
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #374151;">
                                Thank you for your purchase! Your credits have been added to your account.
                            </p>
                            <div style="background-color: #f9fafb; border-radius: 8px; padding: 20px; margin-bottom: 30px;">
                                <h3 style="margin: 0 0 15px; font-size: 18px; color: #111827;">{{ bundle_name }}</h3>
                                <table style="width: 100%; border-collapse: collapse;">
                                    {% if enhancement_credits > 0 %}
                                    <tr>
                                        <td style="padding: 8px 0; color: #6b7280;">Enhancement Credits:</td>
                                        <td style="padding: 8px 0; text-align: right; font-weight: 600; color: #111827;">+{{ enhancement_credits }}</td>
                                    </tr>
                                    {% endif %}
                                    {% if criminal_credits > 0 %}
                                    <tr>
                                        <td style="padding: 8px 0; color: #6b7280;">Criminal Credits:</td>
                                        <td style="padding: 8px 0; text-align: right; font-weight: 600; color: #111827;">+{{ criminal_credits }}</td>
                                    </tr>
                                    {% endif %}
                                    {% if dnc_credits > 0 %}
                                    <tr>
                                        <td style="padding: 8px 0; color: #6b7280;">DNC Credits:</td>
                                        <td style="padding: 8px 0; text-align: right; font-weight: 600; color: #111827;">+{{ dnc_credits }}</td>
                                    </tr>
                                    {% endif %}
                                    <tr>
                                        <td style="padding: 12px 0 0; border-top: 1px solid #e5e7eb; color: #6b7280;">Amount Paid:</td>
                                        <td style="padding: 12px 0 0; border-top: 1px solid #e5e7eb; text-align: right; font-weight: 600; font-size: 18px; color: #10b981;">{{ amount }}</td>
                                    </tr>
                                </table>
                            </div>
                            <table role="presentation" style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td align="center">
                                        <a href="{{ dashboard_url }}" style="display: inline-block; padding: 14px 32px; background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%); color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 16px;">
                                            View Dashboard
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 20px 40px; background-color: #f9fafb; border-radius: 0 0 8px 8px; text-align: center;">
                            <p style="margin: 0; font-size: 14px; color: #6b7280;">
                                &copy; {{ year }} {{ app_name }}. All rights reserved.
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

LOW_CREDITS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Low Credits Alert</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif; background-color: #f4f4f5;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 0;">
                <table role="presentation" style="width: 600px; max-width: 100%; border-collapse: collapse; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center; background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px;">Low Credits Alert</h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #374151;">
                                Hi {{ user_name }},
                            </p>
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #374151;">
                                Your <strong>{{ credit_type }}</strong> credits are running low. You currently have:
                            </p>
                            <div style="background-color: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 20px; margin-bottom: 30px; text-align: center;">
                                <span style="font-size: 48px; font-weight: bold; color: #d97706;">{{ remaining }}</span>
                                <p style="margin: 10px 0 0; color: #92400e; font-size: 14px;">{{ credit_type }} credits remaining</p>
                            </div>
                            <p style="margin: 0 0 30px; font-size: 16px; line-height: 1.6; color: #374151;">
                                To avoid any interruption in your searches, consider purchasing more credits.
                            </p>
                            <table role="presentation" style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td align="center">
                                        <a href="{{ billing_url }}" style="display: inline-block; padding: 14px 32px; background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%); color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 16px;">
                                            Buy More Credits
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 20px 40px; background-color: #f9fafb; border-radius: 0 0 8px 8px; text-align: center;">
                            <p style="margin: 0; font-size: 14px; color: #6b7280;">
                                &copy; {{ year }} {{ app_name }}. All rights reserved.
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

TICKET_CREATED_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Support Ticket Created</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif; background-color: #f4f4f5;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 0;">
                <table role="presentation" style="width: 600px; max-width: 100%; border-collapse: collapse; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center; background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%); border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px;">Ticket #{{ ticket_id }} Created</h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #374151;">
                                Hi {{ user_name }},
                            </p>
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #374151;">
                                Your support ticket has been submitted successfully. Our team will review it and get back to you soon.
                            </p>
                            <div style="background-color: #f9fafb; border-radius: 8px; padding: 20px; margin-bottom: 30px;">
                                <p style="margin: 0 0 10px; font-size: 14px; color: #6b7280;">Ticket ID</p>
                                <p style="margin: 0 0 15px; font-size: 18px; font-weight: 600; color: #111827;">#{{ ticket_id }}</p>
                                <p style="margin: 0 0 10px; font-size: 14px; color: #6b7280;">Subject</p>
                                <p style="margin: 0; font-size: 16px; color: #111827;">{{ ticket_subject }}</p>
                            </div>
                            <table role="presentation" style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td align="center">
                                        <a href="{{ ticket_url }}" style="display: inline-block; padding: 14px 32px; background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%); color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 16px;">
                                            View Ticket
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 20px 40px; background-color: #f9fafb; border-radius: 0 0 8px 8px; text-align: center;">
                            <p style="margin: 0; font-size: 14px; color: #6b7280;">
                                &copy; {{ year }} {{ app_name }}. All rights reserved.
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

TICKET_ASSIGNED_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ticket Assigned to You</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif; background-color: #f4f4f5;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 0;">
                <table role="presentation" style="width: 600px; max-width: 100%; border-collapse: collapse; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center; background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%); border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px;">Ticket Assigned</h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #374151;">
                                Hi {{ admin_name }},
                            </p>
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #374151;">
                                A support ticket has been assigned to you.
                            </p>
                            <div style="background-color: #f9fafb; border-radius: 8px; padding: 20px; margin-bottom: 30px;">
                                <p style="margin: 0 0 10px; font-size: 14px; color: #6b7280;">Ticket ID</p>
                                <p style="margin: 0 0 15px; font-size: 18px; font-weight: 600; color: #111827;">#{{ ticket_id }}</p>
                                <p style="margin: 0 0 10px; font-size: 14px; color: #6b7280;">Subject</p>
                                <p style="margin: 0 0 15px; font-size: 16px; color: #111827;">{{ ticket_subject }}</p>
                                <p style="margin: 0 0 10px; font-size: 14px; color: #6b7280;">From</p>
                                <p style="margin: 0; font-size: 16px; color: #111827;">{{ user_name }}</p>
                            </div>
                            <table role="presentation" style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td align="center">
                                        <a href="{{ ticket_url }}" style="display: inline-block; padding: 14px 32px; background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%); color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 16px;">
                                            View Ticket
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 20px 40px; background-color: #f9fafb; border-radius: 0 0 8px 8px; text-align: center;">
                            <p style="margin: 0; font-size: 14px; color: #6b7280;">
                                &copy; {{ year }} {{ app_name }}. All rights reserved.
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

TICKET_UPDATE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ticket Updated</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif; background-color: #f4f4f5;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 0;">
                <table role="presentation" style="width: 600px; max-width: 100%; border-collapse: collapse; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center; background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%); border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px;">Ticket #{{ ticket_id }} Updated</h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #374151;">
                                Hi {{ user_name }},
                            </p>
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #374151;">
                                Your support ticket has been updated.
                            </p>
                            <div style="background-color: #f9fafb; border-radius: 8px; padding: 20px; margin-bottom: 30px;">
                                <p style="margin: 0 0 10px; font-size: 14px; color: #6b7280;">Subject</p>
                                <p style="margin: 0 0 15px; font-size: 16px; color: #111827;">{{ ticket_subject }}</p>
                                <p style="margin: 0 0 10px; font-size: 14px; color: #6b7280;">New Status</p>
                                <p style="margin: 0; font-size: 16px; font-weight: 600; color: #3b82f6;">{{ new_status }}</p>
                            </div>
                            {% if note %}
                            <div style="background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 15px 20px; margin-bottom: 30px;">
                                <p style="margin: 0 0 10px; font-size: 14px; color: #6b7280;">New Message</p>
                                <p style="margin: 0; font-size: 16px; color: #111827;">{{ note }}</p>
                            </div>
                            {% endif %}
                            <table role="presentation" style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td align="center">
                                        <a href="{{ ticket_url }}" style="display: inline-block; padding: 14px 32px; background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%); color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 16px;">
                                            View Ticket
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 20px 40px; background-color: #f9fafb; border-radius: 0 0 8px 8px; text-align: center;">
                            <p style="margin: 0; font-size: 14px; color: #6b7280;">
                                &copy; {{ year }} {{ app_name }}. All rights reserved.
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
