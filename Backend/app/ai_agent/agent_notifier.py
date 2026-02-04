"""Agent Notifier - Send immediate notifications to human agents on handoff.

When AI hands off to a human agent, this sends immediate alerts via:
1. SMS to agent's notification number (via FUB)
2. Email from the lead to the assigned agent (via FUB)

This ensures the agent knows IMMEDIATELY that a lead needs attention.
"""

import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


async def notify_agent_of_handoff(
    fub_person_id: int,
    lead_name: str,
    lead_phone: str,
    lead_email: str,
    handoff_reason: str,
    last_message: str,
    assigned_agent_email: Optional[str],
    settings,
    fub_client=None,
):
    """
    Send immediate notifications to the agent when a handoff occurs.

    Sends:
    1. SMS to notification_fub_person_id (agent's notification number)
    2. Email from lead to assigned agent

    Args:
        fub_person_id: FUB person ID of the lead
        lead_name: Lead's name
        lead_phone: Lead's phone number
        lead_email: Lead's email
        handoff_reason: Why the handoff occurred
        last_message: Last message from the lead
        assigned_agent_email: Email of the assigned agent
        settings: AIAgentSettings object
        fub_client: Optional FUB client (will create if not provided)
    """
    notifications_sent = []
    errors = []

    # Build FUB link
    fub_link = f"https://app.followupboss.com/2/people/view/{fub_person_id}"

    try:
        # 1. Send SMS to agent's notification number
        if settings.notify_agent_on_handoff_sms and settings.notification_fub_person_id:
            try:
                sms_result = await send_sms_to_agent(
                    notification_person_id=settings.notification_fub_person_id,
                    lead_name=lead_name,
                    lead_phone=lead_phone,
                    handoff_reason=handoff_reason,
                    last_message=last_message,
                    fub_link=fub_link,
                    template=settings.handoff_notification_template,
                    user_id=settings.user_id,
                    organization_id=settings.organization_id,
                )

                if sms_result:
                    notifications_sent.append("SMS")
                    logger.info(f"Sent SMS handoff notification to agent for lead {fub_person_id}")
                else:
                    errors.append("SMS notification failed")

            except Exception as e:
                logger.error(f"Error sending SMS notification to agent: {e}")
                errors.append(f"SMS error: {str(e)[:100]}")

        # 2. Send email from lead to assigned agent
        if settings.notify_agent_on_handoff_email and assigned_agent_email:
            try:
                email_result = await send_email_to_agent(
                    fub_person_id=fub_person_id,
                    lead_name=lead_name,
                    handoff_reason=handoff_reason,
                    last_message=last_message,
                    assigned_agent_email=assigned_agent_email,
                    user_id=settings.user_id,
                    organization_id=settings.organization_id,
                    fub_client=fub_client,
                )

                if email_result:
                    notifications_sent.append("Email")
                    logger.info(f"Sent email handoff notification to agent for lead {fub_person_id}")
                else:
                    errors.append("Email notification failed")

            except Exception as e:
                logger.error(f"Error sending email notification to agent: {e}")
                errors.append(f"Email error: {str(e)[:100]}")

        # Log summary
        if notifications_sent:
            logger.info(f"Handoff notifications sent for lead {fub_person_id}: {', '.join(notifications_sent)}")
        else:
            logger.warning(f"No handoff notifications sent for lead {fub_person_id}: {', '.join(errors)}")

        return {
            "success": len(notifications_sent) > 0,
            "notifications_sent": notifications_sent,
            "errors": errors,
        }

    except Exception as e:
        logger.error(f"Error in notify_agent_of_handoff for lead {fub_person_id}: {e}")
        return {
            "success": False,
            "notifications_sent": [],
            "errors": [str(e)],
        }


async def send_sms_to_agent(
    notification_person_id: int,
    lead_name: str,
    lead_phone: str,
    handoff_reason: str,
    last_message: str,
    fub_link: str,
    template: str,
    user_id: str = None,
    organization_id: str = None,
):
    """
    Send SMS to agent's notification number via FUB.

    Uses the notification_fub_person_id (a "lead" in FUB that's actually the agent's phone).

    Args:
        notification_person_id: FUB person ID for agent notifications
        lead_name: Name of the lead
        lead_phone: Phone number of the lead
        handoff_reason: Why handoff occurred
        last_message: Last message from lead
        fub_link: Link to lead in FUB
        template: Message template
        user_id: User ID for credential lookup
        organization_id: Organization ID for credential lookup
    """
    from app.messaging.playwright_sms_service import send_sms_with_auto_credentials

    try:
        # Format the notification message
        message = template.format(
            lead_name=lead_name,
            lead_phone=lead_phone,
            reason=handoff_reason,
            last_message=last_message[:100] + ("..." if len(last_message) > 100 else ""),
            fub_link=fub_link,
        )

        # Send via Playwright (to the notification person ID)
        result = await send_sms_with_auto_credentials(
            person_id=notification_person_id,
            message=message,
            user_id=user_id,
            organization_id=organization_id,
        )

        if result.get('success'):
            logger.info(f"SMS notification sent to agent for {lead_name}")
            return True
        else:
            logger.error(f"Failed to send SMS notification: {result.get('error')}")
            return False

    except Exception as e:
        logger.error(f"Error sending SMS to agent: {e}")
        return False


async def send_email_to_agent(
    fub_person_id: int,
    lead_name: str,
    handoff_reason: str,
    last_message: str,
    assigned_agent_email: str,
    user_id: str = None,
    organization_id: str = None,
    fub_client=None,
):
    """
    Send email from the lead to the assigned agent via Playwright.

    This sends an email through the FUB interface to the assigned agent.
    The agent receives it in their inbox.

    Args:
        fub_person_id: FUB person ID of the lead
        lead_name: Name of the lead
        handoff_reason: Why handoff occurred
        last_message: Last message from lead
        assigned_agent_email: Email of the assigned agent
        user_id: User ID for credential lookup
        organization_id: Organization ID for credential lookup
        fub_client: Optional FUB client (unused, kept for API compatibility)
    """
    from app.messaging.playwright_sms_service import send_email_with_auto_credentials

    try:
        # Build email subject and body
        subject = f"🔔 AI Handoff Alert: {lead_name} needs your attention"

        body = f"""AI has handed off this lead to you - respond ASAP

Lead Information:
- Name: {lead_name}
- Handoff Reason: {handoff_reason}

Last Message from Lead:
"{last_message}"

Action Required:
The AI has determined this lead needs human attention. Please respond to them as soon as possible.

View Lead in Follow Up Boss:
https://app.followupboss.com/2/people/view/{fub_person_id}

---
This is an automated handoff notification from your AI agent.
Powered by LeadSynergy AI"""

        # Send email via Playwright
        result = await send_email_with_auto_credentials(
            person_id=fub_person_id,
            subject=subject,
            body=body,
            user_id=user_id,
            organization_id=organization_id,
        )

        if result.get('success'):
            logger.info(f"Email notification sent to agent {assigned_agent_email} for lead {fub_person_id}")
            return True
        else:
            logger.error(f"Failed to send email notification: {result.get('error')}")
            return False

    except Exception as e:
        logger.error(f"Error sending email to agent: {e}")
        return False
