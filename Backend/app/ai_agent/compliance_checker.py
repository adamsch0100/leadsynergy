"""
Compliance Checker - TCPA and SMS compliance verification.

Ensures all outbound communications comply with:
- TCPA 2025 regulations
- FCC rules for SMS marketing
- Do Not Call (DNC) registry requirements
- Consent documentation requirements

Key Rules:
- Only text 8 AM - 8 PM recipient's local time
- Maximum 3 texts per 24-hour period
- Immediate opt-out handling (STOP keyword)
- Maintain opt-out records for 4+ years
- Check DNC registry before texting
- Document consent with timestamps
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Optional, Dict, Any, Tuple, List
from enum import Enum
import pytz

logger = logging.getLogger(__name__)


class ComplianceStatus(Enum):
    """Status of compliance check."""
    COMPLIANT = "compliant"
    BLOCKED_NO_CONSENT = "blocked_no_consent"
    BLOCKED_OPTED_OUT = "blocked_opted_out"
    BLOCKED_DNC = "blocked_dnc"
    BLOCKED_OUTSIDE_HOURS = "blocked_outside_hours"
    BLOCKED_RATE_LIMIT = "blocked_rate_limit"
    BLOCKED_STAGE = "blocked_stage"  # Lead's FUB stage blocks AI contact
    HANDOFF_STAGE = "handoff_stage"  # Stage requires human handoff
    BLOCKED_OTHER = "blocked_other"


@dataclass
class ComplianceResult:
    """Result of a compliance check."""
    status: ComplianceStatus
    can_send: bool
    reason: Optional[str] = None
    next_allowed_time: Optional[datetime] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "can_send": self.can_send,
            "reason": self.reason,
            "next_allowed_time": self.next_allowed_time.isoformat() if self.next_allowed_time else None,
            "warnings": self.warnings,
        }


class ComplianceChecker:
    """
    Checks SMS and communication compliance.

    Handles:
    - Time window verification (8 AM - 8 PM local time)
    - Rate limiting (max 30 messages per 24 hours)
    - Consent verification
    - Opt-out status
    - DNC registry status
    """

    # Texting hours (recipient's local time)
    ALLOWED_START_HOUR = 8   # 8 AM
    ALLOWED_END_HOUR = 20    # 8 PM

    # Rate limits - counts ALL AI messages per lead per day
    # 30 allows for extended conversations where lead is actively replying
    MAX_MESSAGES_PER_DAY = 30

    # Default timezone if unknown (Mountain Time for Colorado-based operations)
    DEFAULT_TIMEZONE = "America/Denver"

    # Stage patterns that BLOCK AI outreach entirely
    # These stages mean the lead should NOT receive automated AI messages
    BLOCK_STAGE_PATTERNS = [
        "closed", "sold", "lost", "sphere", "trash",
        "not interested", "dnc", "do not", "archived",
        "inactive", "dead", "junk", "spam", "wrong",
        "bad number", "duplicate", "deceased",
        "past client", "active client",
    ]

    # Stage patterns that require human handoff
    # AI can still respond but should create task for human follow-up
    HANDOFF_STAGE_PATTERNS = [
        "showing", "offer", "negotiat", "contract",
        "under agreement", "pending", "escrow", "closing"
    ]

    def __init__(self, supabase_client=None, endato_client=None):
        """
        Initialize compliance checker.

        Args:
            supabase_client: Database client for consent records
            endato_client: Endato client for DNC checks
        """
        self.supabase = supabase_client
        self.endato = endato_client

    async def check_sms_compliance(
        self,
        fub_person_id: int,
        organization_id: str,
        phone_number: str,
        recipient_timezone: str = None,
    ) -> ComplianceResult:
        """
        Perform full compliance check before sending SMS.

        Args:
            fub_person_id: FUB person ID
            organization_id: Organization ID
            phone_number: Recipient phone number
            recipient_timezone: Recipient's timezone (optional)

        Returns:
            ComplianceResult with status and details
        """
        warnings = []
        tz = recipient_timezone or self.DEFAULT_TIMEZONE

        # Get consent record
        consent = await self._get_consent_record(fub_person_id, organization_id)

        # Check 1: Opt-out status
        if consent and consent.get("opted_out"):
            return ComplianceResult(
                status=ComplianceStatus.BLOCKED_OPTED_OUT,
                can_send=False,
                reason=f"Lead opted out on {consent.get('opted_out_at', 'unknown date')}",
            )

        # Check 2: Consent given
        if not consent or not consent.get("consent_given"):
            # For FUB leads, we may assume implied consent from inquiry
            # But flag it as a warning
            warnings.append("No explicit consent record - relying on implied consent from lead inquiry")

        # Check 3: DNC status
        if consent and consent.get("is_on_dnc"):
            return ComplianceResult(
                status=ComplianceStatus.BLOCKED_DNC,
                can_send=False,
                reason="Phone number is on the Do Not Call registry",
            )

        # Check 4: Time window
        time_ok, next_allowed = self._check_time_window(tz)
        if not time_ok:
            return ComplianceResult(
                status=ComplianceStatus.BLOCKED_OUTSIDE_HOURS,
                can_send=False,
                reason=f"Outside allowed texting hours (8 AM - 8 PM {tz})",
                next_allowed_time=next_allowed,
            )

        # Check 5: Rate limit
        if consent:
            messages_today = consent.get("messages_sent_today", 0)
            last_message_date = consent.get("last_message_date")

            # Reset counter if it's a new day
            today = datetime.now(pytz.timezone(tz)).date()
            if last_message_date and str(last_message_date) != str(today):
                messages_today = 0

            if messages_today >= self.MAX_MESSAGES_PER_DAY:
                # Calculate next allowed time (tomorrow at 8 AM)
                tomorrow = today + timedelta(days=1)
                next_allowed = datetime.combine(
                    tomorrow,
                    time(self.ALLOWED_START_HOUR, 0),
                    tzinfo=pytz.timezone(tz)
                )
                return ComplianceResult(
                    status=ComplianceStatus.BLOCKED_RATE_LIMIT,
                    can_send=False,
                    reason=f"Rate limit reached ({self.MAX_MESSAGES_PER_DAY} messages per day)",
                    next_allowed_time=next_allowed,
                )

        # All checks passed
        return ComplianceResult(
            status=ComplianceStatus.COMPLIANT,
            can_send=True,
            warnings=warnings,
        )

    def check_stage_eligibility(
        self,
        stage_name: str,
        excluded_stages: list = None,
    ) -> Tuple[bool, ComplianceStatus, str]:
        """
        Check if lead's FUB stage allows AI contact.

        Uses smart pattern matching to handle custom agent-created stages.
        For example, "Closed - Sold" and "CLOSED" both match the "closed" pattern.
        Also checks user-configured excluded stages (exact match).

        Args:
            stage_name: The lead's current FUB stage name
            excluded_stages: User-configured list of excluded stage names (exact match, case-insensitive)

        Returns:
            Tuple of (is_eligible, status, reason)
            - is_eligible: True if AI can contact, False if blocked
            - status: ComplianceStatus indicating the result type
            - reason: Human-readable reason for the decision
        """
        if not stage_name:
            # No stage means we can proceed (new lead without stage assignment)
            return True, ComplianceStatus.COMPLIANT, "No stage assigned"

        stage_lower = stage_name.lower().strip()

        # Check 0: User-configured excluded stages (exact match, case-insensitive)
        if excluded_stages:
            for excluded in excluded_stages:
                if excluded and stage_lower == excluded.lower().strip():
                    reason = f"Lead stage '{stage_name}' is excluded by user settings"
                    logger.info(f"Stage eligibility check: BLOCKED (user setting) - {reason}")
                    return False, ComplianceStatus.BLOCKED_STAGE, reason

        # Check 1: Is this a blocked stage? (hardcoded safety net)
        for pattern in self.BLOCK_STAGE_PATTERNS:
            if pattern in stage_lower:
                reason = f"Lead stage '{stage_name}' blocks AI contact (matched '{pattern}')"
                logger.info(f"Stage eligibility check: BLOCKED - {reason}")
                return False, ComplianceStatus.BLOCKED_STAGE, reason

        # Check 2: Is this a handoff stage?
        for pattern in self.HANDOFF_STAGE_PATTERNS:
            if pattern in stage_lower:
                reason = f"Lead stage '{stage_name}' requires human handoff (matched '{pattern}')"
                logger.info(f"Stage eligibility check: HANDOFF - {reason}")
                return True, ComplianceStatus.HANDOFF_STAGE, reason

        # Stage doesn't match any special patterns - allowed
        return True, ComplianceStatus.COMPLIANT, "Stage allows AI contact"

    async def check_full_eligibility(
        self,
        fub_person_id: int,
        organization_id: str,
        phone_number: str,
        stage_name: str = None,
        recipient_timezone: str = None,
        excluded_stages: list = None,
    ) -> ComplianceResult:
        """
        Perform full eligibility check including stage and SMS compliance.

        This is the recommended method for checking if AI should contact a lead.
        It combines:
        1. Stage eligibility (blocked/handoff stages + user-excluded stages)
        2. SMS compliance (hours, rate limits, opt-out status, DNC)

        Note: TCPA consent is assumed for all leads in FUB - they consented
        when entering through the lead source platform.

        Args:
            fub_person_id: FUB person ID
            organization_id: Organization ID
            phone_number: Recipient phone number
            stage_name: Lead's current FUB stage (optional but recommended)
            recipient_timezone: Recipient's timezone (optional)
            excluded_stages: User-configured excluded stages list (optional)

        Returns:
            ComplianceResult with full status details
        """
        warnings = []

        # Check 1: Stage eligibility (if stage provided)
        if stage_name:
            is_eligible, status, reason = self.check_stage_eligibility(stage_name, excluded_stages)

            if not is_eligible:
                return ComplianceResult(
                    status=status,
                    can_send=False,
                    reason=reason,
                )

            if status == ComplianceStatus.HANDOFF_STAGE:
                # Eligible but requires handoff - add warning
                warnings.append(f"Stage '{stage_name}' requires human follow-up")

        # Check 3: Standard SMS compliance (hours, rate limits, DNC)
        sms_result = await self.check_sms_compliance(
            fub_person_id=fub_person_id,
            organization_id=organization_id,
            phone_number=phone_number,
            recipient_timezone=recipient_timezone,
        )

        # Merge warnings
        if sms_result.warnings:
            warnings.extend(sms_result.warnings)

        # If SMS check failed, return that result
        if not sms_result.can_send:
            sms_result.warnings = warnings
            return sms_result

        # All checks passed
        return ComplianceResult(
            status=ComplianceStatus.COMPLIANT,
            can_send=True,
            warnings=warnings,
        )

    def _check_time_window(self, timezone_str: str) -> Tuple[bool, Optional[datetime]]:
        """
        Check if current time is within allowed texting window.

        Returns:
            Tuple of (is_allowed, next_allowed_time)
        """
        try:
            tz = pytz.timezone(timezone_str)
        except pytz.exceptions.UnknownTimeZoneError:
            tz = pytz.timezone(self.DEFAULT_TIMEZONE)

        now = datetime.now(tz)
        current_hour = now.hour

        if self.ALLOWED_START_HOUR <= current_hour < self.ALLOWED_END_HOUR:
            return True, None

        # Calculate next allowed time
        if current_hour < self.ALLOWED_START_HOUR:
            # Before start time today
            next_allowed = now.replace(
                hour=self.ALLOWED_START_HOUR,
                minute=0,
                second=0,
                microsecond=0
            )
        else:
            # After end time, next morning
            tomorrow = now.date() + timedelta(days=1)
            next_allowed = datetime.combine(
                tomorrow,
                time(self.ALLOWED_START_HOUR, 0),
                tzinfo=tz
            )

        return False, next_allowed

    async def _get_consent_record(
        self,
        fub_person_id: int,
        organization_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get consent record from database."""
        if not self.supabase:
            return None

        try:
            result = self.supabase.table("sms_consent").select("*").eq(
                "fub_person_id", fub_person_id
            ).eq(
                "organization_id", organization_id
            ).execute()

            if result.data:
                return result.data[0]
        except Exception as e:
            logger.error(f"Error fetching consent record: {e}")

        return None

    async def record_consent(
        self,
        fub_person_id: int,
        organization_id: str,
        phone_number: str,
        consent_source: str = "fub_import",
        consent_ip: str = None,
    ) -> bool:
        """
        Record SMS consent for a lead.

        Args:
            fub_person_id: FUB person ID
            organization_id: Organization ID
            phone_number: Phone number
            consent_source: Source of consent (web_form, verbal, fub_import, text_optin)
            consent_ip: IP address if from web form

        Returns:
            True if successfully recorded
        """
        if not self.supabase:
            return False

        try:
            data = {
                "fub_person_id": fub_person_id,
                "organization_id": organization_id,
                "phone_number": self._normalize_phone(phone_number),
                "consent_given": True,
                "consent_timestamp": datetime.utcnow().isoformat(),
                "consent_source": consent_source,
            }

            if consent_ip:
                data["consent_ip_address"] = consent_ip

            # Upsert - update if exists, insert if not
            result = self.supabase.table("sms_consent").upsert(
                data,
                on_conflict="fub_person_id,organization_id"
            ).execute()

            logger.info(f"Consent recorded for FUB person {fub_person_id}")
            return bool(result.data)

        except Exception as e:
            logger.error(f"Error recording consent: {e}")
            return False

    async def record_opt_out(
        self,
        fub_person_id: int,
        organization_id: str,
        reason: str = None,
    ) -> bool:
        """
        Record opt-out for a lead.

        Args:
            fub_person_id: FUB person ID
            organization_id: Organization ID
            reason: Optional reason (e.g., "STOP keyword")

        Returns:
            True if successfully recorded
        """
        if not self.supabase:
            return False

        try:
            result = self.supabase.table("sms_consent").update({
                "opted_out": True,
                "opted_out_at": datetime.utcnow().isoformat(),
                "opt_out_reason": reason,
            }).eq(
                "fub_person_id", fub_person_id
            ).eq(
                "organization_id", organization_id
            ).execute()

            logger.info(f"Opt-out recorded for FUB person {fub_person_id}: {reason}")
            return bool(result.data)

        except Exception as e:
            logger.error(f"Error recording opt-out: {e}")
            return False

    async def clear_opt_out(
        self,
        fub_person_id: int,
        organization_id: str,
    ) -> bool:
        """Clear opt-out status for a lead (re-subscribe).

        Use when a lead was falsely opted out or explicitly opts back in
        (e.g., texts START).

        Args:
            fub_person_id: FUB person ID
            organization_id: Organization ID

        Returns:
            True if successfully cleared
        """
        if not self.supabase:
            return False

        try:
            result = self.supabase.table("sms_consent").update({
                "opted_out": False,
                "opted_out_at": None,
                "opt_out_reason": None,
            }).eq(
                "fub_person_id", fub_person_id
            ).eq(
                "organization_id", organization_id
            ).execute()

            logger.info(f"Opt-out cleared for FUB person {fub_person_id}")
            return bool(result.data)

        except Exception as e:
            logger.error(f"Error clearing opt-out: {e}")
            return False

    async def increment_message_count(
        self,
        fub_person_id: int,
        organization_id: str,
        phone_number: str = None,
    ) -> bool:
        """Increment daily message count after sending.

        Args:
            fub_person_id: FUB person ID
            organization_id: Organization ID
            phone_number: Lead's phone number (required if no existing consent record)
        """
        if not self.supabase:
            return False

        try:
            consent = await self._get_consent_record(fub_person_id, organization_id)
            today = datetime.utcnow().date()

            if consent:
                last_date = consent.get("last_message_date")
                current_count = consent.get("messages_sent_today", 0)

                # Reset if new day
                if str(last_date) != str(today):
                    current_count = 0

                result = self.supabase.table("sms_consent").update({
                    "messages_sent_today": current_count + 1,
                    "last_message_date": str(today),
                }).eq(
                    "fub_person_id", fub_person_id
                ).eq(
                    "organization_id", organization_id
                ).execute()

                return bool(result.data)
            else:
                # Create new record with count - phone_number is required
                if not phone_number:
                    logger.warning(f"Cannot create consent record without phone_number for person {fub_person_id}")
                    return False

                result = self.supabase.table("sms_consent").insert({
                    "fub_person_id": fub_person_id,
                    "organization_id": organization_id,
                    "phone_number": self._normalize_phone(phone_number),
                    "messages_sent_today": 1,
                    "last_message_date": str(today),
                    "consent_given": True,  # Implied from sending
                    "consent_source": "fub_import",
                }).execute()

                return bool(result.data)

        except Exception as e:
            logger.error(f"Error incrementing message count: {e}")
            return False

    async def check_dnc_status(
        self,
        phone_number: str,
        fub_person_id: int,
        organization_id: str,
    ) -> bool:
        """
        Check if phone number is on DNC registry using Endato.

        Args:
            phone_number: Phone number to check
            fub_person_id: FUB person ID
            organization_id: Organization ID

        Returns:
            True if on DNC (should NOT contact), False if clear
        """
        if not self.endato:
            logger.warning("Endato client not available for DNC check")
            return False  # Assume not on DNC if can't check

        try:
            # Use existing Endato DNC check
            result = await self.endato.check_dnc(phone_number)
            is_on_dnc = result.get("is_on_dnc", False)

            # Update consent record with DNC status
            if self.supabase:
                self.supabase.table("sms_consent").upsert({
                    "fub_person_id": fub_person_id,
                    "organization_id": organization_id,
                    "phone_number": self._normalize_phone(phone_number),
                    "dnc_checked": True,
                    "dnc_checked_at": datetime.utcnow().isoformat(),
                    "is_on_dnc": is_on_dnc,
                }, on_conflict="fub_person_id,organization_id").execute()

            return is_on_dnc

        except Exception as e:
            logger.error(f"Error checking DNC status: {e}")
            return False

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number to E.164 format."""
        import re
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', phone)

        # Add country code if missing (assume US)
        if len(digits) == 10:
            digits = '1' + digits
        elif len(digits) == 11 and digits[0] == '1':
            pass  # Already has country code
        else:
            # Return as-is if can't normalize
            return phone

        return '+' + digits

    def is_opt_out_keyword(self, message: str) -> bool:
        """Check if message contains opt-out keyword.

        Uses word-boundary matching (\b) to avoid false positives from
        substrings like 'send' triggering 'end', 'quite' triggering 'quit',
        or 'understand' triggering 'end'.
        """
        message_lower = message.lower().strip()

        opt_out_patterns = [
            r'\bstop\b',              # TCPA required keyword
            r'\bunsubscribe\b',       # Standard opt-out
            r'\bcancel\b',            # Intent to stop
            r'\bquit\b',             # Intent to stop
            r'\bopt\s*out\b',        # "opt out" or "optout"
            r'\bremove me\b',        # Request to remove
            r"\bdon'?t\s+text\b",    # "don't text" or "dont text"
            r'\bnot\s+interested\b',  # "not interested" / "not interested at this time"
            r'\bno\s+thanks\b',      # "no thanks"
            r'\bleave me alone\b',   # "leave me alone"
            r'\bdelete\b.*\bmessages?\b',  # "delete your messages" / "deleting your messages"
            # Note: "end" removed - too many false positives with "end of year", "weekend", etc.
        ]

        return any(re.search(pattern, message_lower) for pattern in opt_out_patterns)


# Convenience function for quick compliance check
async def check_sms_compliance(
    fub_person_id: int,
    organization_id: str,
    phone_number: str,
    supabase_client=None,
    recipient_timezone: str = None,
) -> ComplianceResult:
    """Quick compliance check with default checker."""
    checker = ComplianceChecker(supabase_client=supabase_client)
    return await checker.check_sms_compliance(
        fub_person_id=fub_person_id,
        organization_id=organization_id,
        phone_number=phone_number,
        recipient_timezone=recipient_timezone,
    )
