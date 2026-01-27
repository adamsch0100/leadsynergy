"""
Agent Notification Service - Immediate alerts for hot leads.

When a hot lead is detected and handoff is triggered, this service sends
immediate notifications to the agent via:
1. SMS via FUB (using a "notification lead" in FUB with the agent's phone)
2. Email (backup notification with more details)

HOW IT WORKS:
To receive SMS notifications, the agent creates a "lead" in FUB with their
own phone number. When a hot lead is detected, we send an SMS to that
"notification lead" - which means the agent gets a text.

Example setup:
1. Create a lead in FUB named "LeadSynergy Bot" or "Agent Notifications"
2. Set the phone number to the agent's cell phone
3. Copy that lead's FUB Person ID
4. Paste it in AI Settings -> notification_fub_person_id

This approach:
- Uses existing FUB infrastructure (no Twilio needed)
- Texts appear in FUB like any other conversation
- Simple to configure
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AgentNotifier:
    """Send immediate notifications to agents for hot leads."""

    def __init__(self, notification_fub_person_id: Optional[int] = None):
        """
        Initialize notification services.

        Args:
            notification_fub_person_id: FUB person ID of the "notification lead"
                                        (a lead with the agent's phone number)
        """
        self.notification_fub_person_id = notification_fub_person_id

        # Email service (lazy import to avoid circular imports)
        self._email_service = None
        self._fub_sms_service = None

    @property
    def email_service(self):
        """Lazy load email service."""
        if self._email_service is None:
            try:
                from app.email.email_service import EmailService
                self._email_service = EmailService()
            except Exception as e:
                logger.error(f"Failed to initialize email service: {e}")
        return self._email_service

    @property
    def fub_sms_service(self):
        """Lazy load FUB SMS service."""
        if self._fub_sms_service is None:
            try:
                from app.messaging.fub_sms_service import FUBSMSService
                self._fub_sms_service = FUBSMSService()
            except Exception as e:
                logger.error(f"Failed to initialize FUB SMS service: {e}")
        return self._fub_sms_service

    def notify_agent_sms(
        self,
        lead_name: str,
        trigger_type: str,
        lead_message: str,
        lead_phone: Optional[str] = None,
    ) -> bool:
        """
        Send SMS alert to agent about hot lead via FUB.

        The SMS is sent to the "notification lead" in FUB, which has the
        agent's phone number. This way the agent receives the alert as a
        text message.

        Args:
            lead_name: Lead's full name
            trigger_type: Type of handoff trigger (e.g., "Schedule Showing")
            lead_message: The lead's message that triggered handoff
            lead_phone: Lead's phone number (for quick callback)

        Returns:
            True if SMS was sent successfully, False otherwise
        """
        if not self.notification_fub_person_id:
            logger.info("[AGENT-NOTIFY] No notification_fub_person_id configured, skipping SMS")
            return False

        if not self.fub_sms_service:
            logger.warning("[AGENT-NOTIFY] FUB SMS service not available")
            return False

        # Build notification message
        truncated_message = lead_message[:100] + "..." if len(lead_message) > 100 else lead_message
        phone_info = f"\nCall: {lead_phone}" if lead_phone else ""

        message = (
            f"HOT LEAD: {lead_name}\n"
            f"{trigger_type}\n"
            f"\"{truncated_message}\""
            f"{phone_info}\n"
            f"Respond ASAP!"
        )

        try:
            result = self.fub_sms_service.send_text_message(
                person_id=self.notification_fub_person_id,
                message=message,
            )

            if result.get("success") or result.get("id"):
                logger.info(f"[AGENT-NOTIFY] SMS alert sent via FUB to notification lead {self.notification_fub_person_id}")
                return True
            else:
                logger.warning(f"[AGENT-NOTIFY] FUB SMS may have failed: {result}")
                return False

        except Exception as e:
            logger.error(f"[AGENT-NOTIFY] Failed to send SMS alert via FUB: {e}")
            return False

    def notify_agent_email(
        self,
        agent_email: str,
        agent_name: str,
        lead_name: str,
        trigger_type: str,
        lead_message: str,
        lead_phone: Optional[str] = None,
        lead_score: Optional[int] = None,
        lead_source: Optional[str] = None,
        fub_person_id: Optional[int] = None,
    ) -> bool:
        """
        Send email alert to agent with full context.

        Args:
            agent_email: Agent's email address
            agent_name: Agent's name for personalization
            lead_name: Lead's full name
            trigger_type: Type of handoff trigger
            lead_message: The lead's message that triggered handoff
            lead_phone: Lead's phone number (optional)
            lead_score: Lead's AI score 0-100 (optional)
            lead_source: Lead source (optional)
            fub_person_id: FUB person ID for direct link (optional)

        Returns:
            True if email was sent successfully, False otherwise
        """
        if not agent_email:
            logger.warning("[AGENT-NOTIFY] Cannot send email: No agent email address")
            return False

        if not self.email_service:
            logger.warning("[AGENT-NOTIFY] Cannot send email: Email service not available")
            return False

        subject = f"HOT LEAD: {lead_name} - {trigger_type}"

        # Build FUB link if person ID available
        fub_link = ""
        if fub_person_id:
            fub_link = f'<p><a href="https://app.followupboss.com/app/people/{fub_person_id}" style="background:#4CAF50;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;display:inline-block;">View in Follow Up Boss</a></p>'

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #ff6b6b; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
        .content {{ background: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
        .quote {{ background: #fff; padding: 15px; border-left: 4px solid #ff6b6b; margin: 15px 0; }}
        .info-table {{ width: 100%; border-collapse: collapse; }}
        .info-table td {{ padding: 8px; border-bottom: 1px solid #eee; }}
        .info-table td:first-child {{ font-weight: bold; width: 120px; }}
        .action {{ background: #fff3cd; padding: 15px; border: 1px solid #ffc107; margin: 15px 0; border-radius: 5px; }}
        .footer {{ text-align: center; padding: 15px; color: #888; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin:0;">Hot Lead Alert!</h1>
        </div>
        <div class="content">
            <p>Hi {agent_name or 'Agent'},</p>
            <p><strong>{lead_name}</strong> needs your attention immediately.</p>

            <h3>What happened:</h3>
            <p>The AI detected: <strong>{trigger_type}</strong></p>

            <h3>Lead's message:</h3>
            <div class="quote">
                "{lead_message}"
            </div>

            <h3>Lead Info:</h3>
            <table class="info-table">
                <tr><td>Name:</td><td>{lead_name}</td></tr>
                <tr><td>Phone:</td><td>{lead_phone or 'See FUB'}</td></tr>
                <tr><td>Score:</td><td>{lead_score if lead_score is not None else 'N/A'}/100</td></tr>
                <tr><td>Source:</td><td>{lead_source or 'N/A'}</td></tr>
            </table>

            <div class="action">
                <strong>ACTION:</strong> Contact this lead within the next 5 minutes!
            </div>

            {fub_link}
        </div>
        <div class="footer">
            <p>This alert was sent by LeadSynergy AI Agent.</p>
            <p>You received this because a hot lead was detected in your account.</p>
        </div>
    </div>
</body>
</html>
"""

        try:
            result = self.email_service.send_email(
                to_email=agent_email,
                subject=subject,
                html_content=html,
            )
            if result:
                logger.info(f"[AGENT-NOTIFY] Email alert sent to {agent_email}")
            return result
        except Exception as e:
            logger.error(f"[AGENT-NOTIFY] Failed to send email alert: {e}")
            return False

    def notify_agent(
        self,
        agent_email: Optional[str],
        agent_name: str,
        lead_name: str,
        trigger_type: str,
        lead_message: str,
        lead_phone: Optional[str] = None,
        lead_score: Optional[int] = None,
        lead_source: Optional[str] = None,
        fub_person_id: Optional[int] = None,
    ) -> dict:
        """
        Send all configured notifications to agent.

        This is the main entry point - it attempts to send both SMS and email,
        and returns a summary of what was sent.

        Returns:
            Dict with 'sms_sent' and 'email_sent' booleans
        """
        results = {
            "sms_sent": False,
            "email_sent": False,
        }

        # Try SMS first (fastest) - via FUB to notification lead
        results["sms_sent"] = self.notify_agent_sms(
            lead_name=lead_name,
            trigger_type=trigger_type,
            lead_message=lead_message,
            lead_phone=lead_phone,
        )

        # Then email (more context)
        if agent_email:
            results["email_sent"] = self.notify_agent_email(
                agent_email=agent_email,
                agent_name=agent_name,
                lead_name=lead_name,
                trigger_type=trigger_type,
                lead_message=lead_message,
                lead_phone=lead_phone,
                lead_score=lead_score,
                lead_source=lead_source,
                fub_person_id=fub_person_id,
            )

        # Log summary
        if results["sms_sent"] or results["email_sent"]:
            channels = []
            if results["sms_sent"]:
                channels.append("SMS (FUB)")
            if results["email_sent"]:
                channels.append("Email")
            logger.info(f"[AGENT-NOTIFY] Agent notified via {', '.join(channels)} for lead: {lead_name}")
        else:
            logger.warning(f"[AGENT-NOTIFY] Could not notify agent for lead: {lead_name} (no notification_fub_person_id or email configured)")

        return results
