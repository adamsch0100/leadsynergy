"""
Proactive Outreach Orchestrator

Orchestrates end-to-end proactive outreach when AI is enabled for a lead.

This service:
1. Validates lead data from FUB
2. Analyzes communication history → HistoricalContext
3. Generates contextual SMS + Email
4. Checks compliance & timing
5. Sends or queues messages
6. Updates conversation with metadata
7. Logs proactive outreach event

This is the main entry point for triggering proactive AI outreach.
"""

import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ProactiveOutreachOrchestrator:
    """Orchestrates complete proactive outreach workflow."""

    def __init__(
        self,
        supabase_client,
        fub_client,
        sms_service,
        compliance_checker,
        email_service=None,
    ):
        """
        Initialize orchestrator.

        Args:
            supabase_client: Supabase client for database operations
            fub_client: FUB API client for fetching lead data
            sms_service: SMS sending service (FUBSMSService)
            compliance_checker: Compliance checker service
            email_service: Optional email service (PlaywrightEmailService)
        """
        self.supabase = supabase_client
        self.fub_client = fub_client
        self.sms_service = sms_service
        self.compliance = compliance_checker
        self.email_service = email_service

    async def trigger_proactive_outreach(
        self,
        fub_person_id: int,
        organization_id: str,
        user_id: str,
        trigger_reason: str = "ai_enabled",
        enable_type: str = "auto",
    ) -> Dict[str, Any]:
        """
        Trigger complete proactive outreach workflow.

        Args:
            fub_person_id: FUB person ID
            organization_id: Organization ID
            user_id: User/agent ID
            trigger_reason: Why outreach triggered ('new_lead_ai_enabled', 'manual_enable', etc.)
            enable_type: 'auto' or 'manual'

        Returns:
            Dict with success status, actions taken, and any errors
        """
        result = {
            "success": False,
            "actions_taken": [],
            "errors": [],
            "lead_stage": None,
            "messages": {},
        }

        try:
            logger.info(f"🚀 Starting proactive outreach for lead {fub_person_id} (trigger: {trigger_reason}, type: {enable_type})")

            # Step 1: Fetch & validate lead data
            person_data = await self._fetch_and_validate_lead(fub_person_id)
            if not person_data:
                result["errors"].append("Could not fetch lead data from FUB")
                return result

            # Step 2: Get organization settings
            settings = await self._get_organization_settings(organization_id, user_id)
            if not settings:
                result["errors"].append("Could not load organization settings")
                return result

            # Step 3: Analyze lead history
            from app.ai_agent.lead_context_analyzer import LeadContextAnalyzer

            analyzer = LeadContextAnalyzer(self.fub_client, self.supabase)
            historical_context = await analyzer.analyze_lead_context(
                fub_person_id=fub_person_id,
                enable_type=enable_type,
            )

            result["lead_stage"] = historical_context.lead_stage.stage
            logger.info(f"📊 Lead classified as: {historical_context.lead_stage.stage} - {historical_context.lead_stage.reasoning}")

            # Step 4: Generate personalized messages
            from app.ai_agent.initial_outreach_generator import InitialOutreachGenerator, LeadContext

            # Build LeadContext from person_data
            lead_context = self._build_lead_context(person_data, settings)

            generator = InitialOutreachGenerator(
                agent_name=settings.get('agent_name', 'Sarah'),
                agent_email=settings.get('agent_email', ''),
                agent_phone=settings.get('agent_phone', ''),
                brokerage_name=settings.get('brokerage_name', 'our team'),
            )

            outreach = await generator.generate_outreach(
                lead_context=lead_context,
                historical_context=historical_context,
            )

            result["messages"] = {
                "sms_preview": outreach.sms_message[:100] + "..." if len(outreach.sms_message) > 100 else outreach.sms_message,
                "email_subject": outreach.email_subject,
            }

            logger.info(f"✍️  Generated messages - SMS: {len(outreach.sms_message)} chars, Email: {len(outreach.email_body)} chars")

            # Step 5: Check compliance & timing
            compliance_result = await self._check_compliance_and_timing(
                person_data=person_data,
                lead_stage=historical_context.lead_stage.stage,
                settings=settings,
            )

            if not compliance_result["can_send"]:
                result["errors"].append(f"Compliance blocked: {compliance_result['reason']}")
                return result

            # Step 6: Send or queue messages
            send_result = await self._send_or_queue_messages(
                fub_person_id=fub_person_id,
                person_data=person_data,
                outreach=outreach,
                compliance_result=compliance_result,
                settings=settings,
            )

            result["actions_taken"].extend(send_result["actions"])
            if send_result["errors"]:
                result["errors"].extend(send_result["errors"])

            # Step 7: Update conversation metadata
            await self._update_conversation_metadata(
                fub_person_id=fub_person_id,
                historical_context=historical_context,
                outreach_sent=len(send_result["actions"]) > 0,
            )

            # Step 8: Log proactive outreach event
            await self._log_proactive_outreach(
                fub_person_id=fub_person_id,
                organization_id=organization_id,
                trigger_reason=trigger_reason,
                enable_type=enable_type,
                historical_context=historical_context,
                outreach=outreach,
                send_result=send_result,
            )

            # Success if at least one message was sent/queued
            result["success"] = len(send_result["actions"]) > 0
            result["lead_timezone"] = settings.get('timezone', 'America/Denver')

            if result["success"]:
                logger.info(f"✅ Proactive outreach completed for lead {fub_person_id}: {', '.join(result['actions_taken'])}")
            else:
                logger.warning(f"⚠️  Proactive outreach completed with warnings for lead {fub_person_id}")

            return result

        except Exception as e:
            logger.error(f"❌ Proactive outreach failed for lead {fub_person_id}: {e}", exc_info=True)
            result["errors"].append(f"Unexpected error: {str(e)}")
            return result

    async def _fetch_and_validate_lead(self, fub_person_id: int) -> Optional[Dict]:
        """Fetch lead data from FUB and validate."""
        try:
            person_data = self.fub_client.get_person(str(fub_person_id), include_all_fields=True)

            # Validate phone exists
            phones = person_data.get('phones', [])
            if not phones:
                logger.warning(f"Lead {fub_person_id} has no phone number")
                return None

            # Validate email exists (nice to have, not required)
            emails = person_data.get('emails', [])
            if not emails:
                logger.info(f"Lead {fub_person_id} has no email (will send SMS only)")

            return person_data

        except Exception as e:
            logger.error(f"Failed to fetch lead {fub_person_id}: {e}")
            return None

    async def _get_organization_settings(self, organization_id: str, user_id: str) -> Optional[Dict]:
        """Get AI agent settings for organization/user."""
        try:
            # Try user-specific settings first
            result = self.supabase.table('ai_agent_settings').select('*').eq(
                'user_id', user_id
            ).limit(1).execute()

            if result.data:
                settings = result.data[0]
                settings['organization_id'] = organization_id
                settings['user_id'] = user_id
                return settings

            # Fallback to org settings
            result = self.supabase.table('ai_agent_settings').select('*').eq(
                'organization_id', organization_id
            ).limit(1).execute()

            if result.data:
                settings = result.data[0]
                settings['organization_id'] = organization_id
                settings['user_id'] = user_id
                return settings

            # Return defaults
            return {
                'agent_name': 'Sarah',
                'agent_email': '',
                'agent_phone': '',
                'brokerage_name': 'our team',
                'timezone': 'America/Denver',
                'working_hours_start': 8,
                'working_hours_end': 20,
                'organization_id': organization_id,
                'user_id': user_id,
            }

        except Exception as e:
            logger.error(f"Failed to get settings: {e}")
            return None

    def _build_lead_context(self, person_data: Dict, settings: Dict) -> 'LeadContext':
        """Build LeadContext from FUB person data."""
        from app.ai_agent.initial_outreach_generator import LeadContext

        # Extract basic info
        first_name = person_data.get('firstName', person_data.get('name', 'there'))
        last_name = person_data.get('lastName', '')
        email = person_data.get('emails', [{}])[0].get('value', '') if person_data.get('emails') else ''
        phone = person_data.get('phones', [{}])[0].get('value', '') if person_data.get('phones') else ''

        # Extract source
        source = person_data.get('source', '')

        # Extract location
        city = person_data.get('city', '')
        state = person_data.get('state', '')
        zip_code = person_data.get('zip', '')

        # Extract timeline, financing, etc. from custom fields or events
        # (Simplified - you'd parse these from FUB events/custom fields in production)

        return LeadContext(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            fub_person_id=person_data.get('id', 0),
            source=source,
            city=city,
            state=state,
            zip_code=zip_code,
            tags=person_data.get('tags', []),
        )

    async def _check_compliance_and_timing(
        self,
        person_data: Dict,
        lead_stage: str,
        settings: Dict,
    ) -> Dict[str, Any]:
        """Check compliance and determine send timing."""
        result = {
            "can_send": True,
            "reason": "",
            "send_immediately": True,
            "queue_for": None,
        }

        # Get phone for compliance check
        phones = person_data.get('phones', [])
        if not phones:
            result["can_send"] = False
            result["reason"] = "No phone number"
            return result

        phone = phones[0].get('value', '')
        person_id = person_data.get('id')

        # Check TCPA compliance
        try:
            compliance_check = await self.compliance.check_sms_compliance(
                fub_person_id=person_id,
                organization_id=settings.get('organization_id', ''),
                phone_number=phone,
                recipient_timezone=settings.get('timezone', 'America/Denver'),
            )

            if not compliance_check.can_send:
                result["can_send"] = False
                result["reason"] = compliance_check.reason or 'Compliance check failed'
                return result

        except Exception as e:
            logger.warning(f"Compliance check failed: {e}")
            # Continue with caution

        # Check TCPA hours (8am-8pm local time)
        timezone_str = settings.get('timezone', 'America/Denver')

        # Parse working hours (could be int or time string like '08:00:00')
        wh_start = settings.get('working_hours_start', 8)
        wh_end = settings.get('working_hours_end', 20)

        if isinstance(wh_start, str) and ':' in wh_start:
            # Parse time string '08:00:00' -> 8
            working_hours_start = int(wh_start.split(':')[0])
        else:
            working_hours_start = int(wh_start)

        if isinstance(wh_end, str) and ':' in wh_end:
            # Parse time string '20:00:00' -> 20
            working_hours_end = int(wh_end.split(':')[0])
        else:
            working_hours_end = int(wh_end)

        # Get current time in LEAD'S timezone (CRITICAL for TCPA compliance)
        import pytz
        try:
            lead_tz = pytz.timezone(timezone_str)
            now = datetime.now(lead_tz)
            current_hour = now.hour
        except:
            # Fallback to UTC if timezone invalid
            now = datetime.now(pytz.UTC)
            current_hour = now.hour

        if not (working_hours_start <= current_hour < working_hours_end):
            # Outside hours - queue for 8-10am tomorrow
            result["send_immediately"] = False
            tomorrow_8am = now.replace(hour=8, minute=0, second=0) + timedelta(days=1)
            result["queue_for"] = tomorrow_8am
            logger.info(f"Outside TCPA hours - queuing for {tomorrow_8am}")
            return result

        # Smart timing based on lead stage
        if lead_stage == "NEW":
            # NEW leads - send immediately (within 5 seconds)
            result["send_immediately"] = True
        elif lead_stage in ["DORMANT", "RETURNING", "COLD"]:
            # DORMANT leads - add 5-10 min delay to appear more human
            delay_minutes = 7  # Sweet spot
            result["send_immediately"] = False
            result["queue_for"] = now + timedelta(minutes=delay_minutes)
            logger.info(f"DORMANT/RETURNING lead - adding {delay_minutes}min delay to appear human")
        else:
            # WARM/other - send immediately
            result["send_immediately"] = True

        return result

    async def _send_or_queue_messages(
        self,
        fub_person_id: int,
        person_data: Dict,
        outreach: 'InitialOutreach',
        compliance_result: Dict,
        settings: Dict,
    ) -> Dict[str, Any]:
        """Send or queue SMS and email messages."""
        result = {
            "actions": [],
            "errors": [],
        }

        phone = person_data.get('phones', [{}])[0].get('value', '')

        # Send or queue SMS
        try:
            if compliance_result["send_immediately"]:
                # Send immediately via Playwright
                logger.info(f"📤 Sending SMS immediately to lead {fub_person_id}")

                from app.messaging.playwright_sms_service import send_sms_with_auto_credentials

                sms_result = await send_sms_with_auto_credentials(
                    person_id=fub_person_id,
                    message=outreach.sms_message,
                    user_id=settings.get('user_id'),
                    organization_id=settings.get('organization_id'),
                    supabase_client=self.supabase,
                )

                if sms_result.get('success'):
                    result["actions"].append("sms_sent")
                    logger.info(f"✅ SMS sent successfully via Playwright")

                    # Log message to ai_message_log for conversation tracking
                    try:
                        self.supabase.table('ai_message_log').insert({
                            'id': str(uuid4()),
                            'fub_person_id': fub_person_id,
                            'organization_id': settings.get('organization_id'),
                            'direction': 'outbound',
                            'channel': 'sms',
                            'content': outreach.sms_message,
                            'sent_at': datetime.now(timezone.utc).isoformat(),
                            'message_type': 'proactive_initial_outreach',
                        }).execute()
                        logger.info(f"✅ Message logged to ai_message_log")
                    except Exception as log_error:
                        logger.error(f"Failed to log message to ai_message_log: {log_error}")
                else:
                    result["errors"].append("SMS send failed")
                    logger.error(f"❌ SMS send failed: {sms_result.get('error', 'Unknown error')}")

            else:
                # Queue for later
                queue_time = compliance_result["queue_for"]
                logger.info(f"⏰ Queuing SMS for {queue_time}")

                # Insert into scheduled_messages table
                await self._queue_message(
                    fub_person_id=fub_person_id,
                    message_content=outreach.sms_message,
                    channel="sms",
                    scheduled_for=queue_time,
                )

                result["actions"].append("sms_queued")

        except Exception as e:
            logger.error(f"Error sending/queuing SMS: {e}")
            result["errors"].append(f"SMS error: {str(e)}")

        # Send or queue Email (if email service available)
        if self.email_service:
            email = person_data.get('emails', [{}])[0].get('value', '')
            if email:
                try:
                    if compliance_result["send_immediately"]:
                        # Add 10-minute delay after SMS
                        email_time = datetime.now() + timedelta(minutes=10)
                        logger.info(f"📧 Queuing email for 10 min after SMS")

                        await self._queue_message(
                            fub_person_id=fub_person_id,
                            message_content=outreach.email_body,
                            channel="email",
                            scheduled_for=email_time,
                            subject=outreach.email_subject,
                        )

                        result["actions"].append("email_queued")
                    else:
                        # Queue for same time as SMS + 10 min
                        email_time = compliance_result["queue_for"] + timedelta(minutes=10)

                        await self._queue_message(
                            fub_person_id=fub_person_id,
                            message_content=outreach.email_body,
                            channel="email",
                            scheduled_for=email_time,
                            subject=outreach.email_subject,
                        )

                        result["actions"].append("email_queued")

                except Exception as e:
                    logger.error(f"Error queuing email: {e}")
                    result["errors"].append(f"Email error: {str(e)}")

        return result

    async def _queue_message(
        self,
        fub_person_id: int,
        message_content: str,
        channel: str,
        scheduled_for: datetime,
        subject: str = None,
    ):
        """Queue a message for later sending."""
        try:
            data = {
                'id': str(uuid4()),
                'fub_person_id': str(fub_person_id),
                'message_content': message_content,
                'channel': channel,
                'scheduled_for': scheduled_for.isoformat(),
                'status': 'pending',
            }

            # Only include email_subject for email messages if the column exists
            # (scheduled_messages table may not have this column)
            if channel == 'email' and subject:
                data['subject'] = subject  # Use 'subject' not 'email_subject'

            self.supabase.table('scheduled_messages').insert(data).execute()

        except Exception as e:
            logger.error(f"Failed to queue message: {e}")
            raise

    async def _update_conversation_metadata(
        self,
        fub_person_id: int,
        historical_context: 'HistoricalContext',
        outreach_sent: bool,
    ):
        """Update ai_conversations with proactive outreach metadata."""
        try:
            metadata = {
                "outreach_sent": outreach_sent,
                "lead_stage_at_outreach": historical_context.lead_stage.stage,
                "days_since_last_contact": historical_context.communication_history.days_since_last_contact,
                "strategy_used": historical_context.strategy.approach,
                "prior_topics_discussed": historical_context.communication_history.topics_discussed,
                "questions_already_asked": historical_context.communication_history.questions_already_asked,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            }

            self.supabase.table('ai_conversations').update({
                'proactive_outreach_metadata': metadata
            }).eq('fub_person_id', fub_person_id).execute()

        except Exception as e:
            logger.error(f"Failed to update conversation metadata: {e}")

    async def _log_proactive_outreach(
        self,
        fub_person_id: int,
        organization_id: str,
        trigger_reason: str,
        enable_type: str,
        historical_context: 'HistoricalContext',
        outreach: 'InitialOutreach',
        send_result: Dict,
    ):
        """Log proactive outreach event to proactive_outreach_log table."""
        try:
            sms_sent = "sms_sent" in send_result["actions"]
            email_sent = "email_sent" in send_result["actions"] or "email_queued" in send_result["actions"]

            self.supabase.table('proactive_outreach_log').insert({
                'fub_person_id': str(fub_person_id),
                'organization_id': organization_id,
                'trigger_reason': trigger_reason,
                'enable_type': enable_type,
                'lead_stage': historical_context.lead_stage.stage,
                'days_since_last_contact': historical_context.communication_history.days_since_last_contact,
                'strategy_used': historical_context.strategy.approach,
                'prior_topics_discussed': historical_context.communication_history.topics_discussed,
                'questions_already_asked': historical_context.communication_history.questions_already_asked,
                'sms_sent': sms_sent,
                'email_sent': email_sent,
                'sms_preview': outreach.sms_message[:200],
                'email_subject': outreach.email_subject,
                'sent_at': datetime.now(timezone.utc).isoformat() if sms_sent else None,
            }).execute()

            logger.info(f"📝 Logged proactive outreach event for lead {fub_person_id}")

        except Exception as e:
            logger.error(f"Failed to log proactive outreach: {e}")


# =========================================================================
# CONVENIENCE FUNCTION - call from any enable path
# =========================================================================

async def trigger_proactive_outreach(
    fub_person_id: int,
    organization_id: str,
    user_id: str,
    trigger_reason: str = "ai_enabled",
    enable_type: str = "manual",
    supabase_client=None,
):
    """
    Convenience function to trigger proactive outreach from ANY enable path.

    This handles all the setup (FUB client, compliance, orchestrator) so callers
    only need to pass the basic identifiers.

    Args:
        fub_person_id: FUB person ID
        organization_id: Organization ID
        user_id: User ID who enabled AI
        trigger_reason: Why outreach is being triggered
        enable_type: 'auto' or 'manual'
        supabase_client: Optional - will create one if not provided
    """
    try:
        from app.database.supabase_client import SupabaseClientSingleton
        from app.database.fub_api_client import FUBApiClient
        from app.ai_agent.compliance_checker import ComplianceChecker

        supabase = supabase_client or SupabaseClientSingleton.get_instance()
        fub_client = FUBApiClient()

        orchestrator = ProactiveOutreachOrchestrator(
            supabase_client=supabase,
            fub_client=fub_client,
            sms_service=None,  # Not used - we use Playwright directly now
            compliance_checker=ComplianceChecker(supabase_client=supabase),
        )

        result = await orchestrator.trigger_proactive_outreach(
            fub_person_id=fub_person_id,
            organization_id=organization_id,
            user_id=user_id,
            trigger_reason=trigger_reason,
            enable_type=enable_type,
        )

        if result["success"]:
            logger.info(f"Proactive outreach triggered for lead {fub_person_id}: {', '.join(result['actions_taken'])}")

            # ================================================================
            # SCHEDULE FOLLOW-UP SEQUENCE (Day 0-7 intensive + 12-month nurture)
            # The initial SMS/email was already sent above. Now schedule the
            # remaining follow-up steps so the AI continues to engage the lead.
            # ================================================================
            try:
                from app.ai_agent.followup_manager import get_followup_manager, FollowUpTrigger

                followup_manager = get_followup_manager(supabase)

                # Use timezone from the orchestrator result (already fetched from settings)
                lead_timezone = result.get("lead_timezone", "America/Denver")

                sequence_result = await followup_manager.schedule_followup_sequence(
                    fub_person_id=fub_person_id,
                    organization_id=organization_id,
                    trigger=FollowUpTrigger.NEW_LEAD,
                    start_delay_hours=0,
                    preferred_channel="sms",
                    lead_timezone=lead_timezone,
                )

                total_scheduled = sequence_result.get("total_scheduled", 0)
                nurture_scheduled = sequence_result.get("nurture_scheduled", 0)

                # Mark initial outreach steps as already sent (steps 0 and 1)
                # since the orchestrator already handled first contact SMS + email
                steps_marked = 0
                for fu in sequence_result.get("followups", []):
                    msg_type = fu.get("message_type", "")
                    if msg_type in ("first_contact", "email_welcome"):
                        try:
                            supabase.table("ai_scheduled_followups").update({
                                "status": "sent",
                            }).eq("id", fu["id"]).execute()
                            steps_marked += 1
                        except Exception:
                            pass

                logger.info(
                    f"📅 Follow-up sequence scheduled for lead {fub_person_id}: "
                    f"{total_scheduled} follow-ups + {nurture_scheduled} nurture "
                    f"({steps_marked} initial steps marked as sent)"
                )
                result["followup_sequence_id"] = sequence_result.get("sequence_id")
                result["followups_scheduled"] = total_scheduled

            except Exception as followup_err:
                logger.error(f"Failed to schedule follow-up sequence for lead {fub_person_id}: {followup_err}", exc_info=True)
                # Don't fail the whole outreach just because follow-up scheduling failed
        else:
            logger.warning(f"Proactive outreach issues for lead {fub_person_id}: {', '.join(result.get('errors', []))}")

        return result

    except Exception as e:
        logger.error(f"Failed to trigger proactive outreach for lead {fub_person_id}: {e}", exc_info=True)
        return {"success": False, "errors": [str(e)]}
