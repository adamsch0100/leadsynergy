"""
Email 2FA Code Retriever

Retrieves 2FA verification codes from email (Gmail/Google Workspace) via IMAP.
Designed to work with per-user credentials stored in lead_source_settings metadata.

Usage:
    # With explicit credentials
    helper = Email2FAHelper(email="user@domain.com", app_password="xxxx xxxx xxxx xxxx")
    code = helper.get_verification_code(sender_contains="redfin", max_age_seconds=120)

    # From lead source settings (for multi-tenant)
    helper = Email2FAHelper.from_lead_source_settings(source_name="Redfin", user_id="...")
    code = helper.get_verification_code(sender_contains="redfin")
"""

import imaplib
import email
from email.header import decode_header
import re
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class Email2FAHelper:
    """Helper class to retrieve 2FA codes from email via IMAP"""

    # Gmail IMAP settings
    IMAP_SERVER = "imap.gmail.com"
    IMAP_PORT = 993

    # Common 2FA code patterns
    CODE_PATTERNS = [
        r'\b(\d{6})\b',  # 6-digit code
        r'\b(\d{4})\b',  # 4-digit code
        r'code[:\s]+(\d{4,6})',  # "code: 123456" or "code 123456"
        r'verification[:\s]+(\d{4,6})',  # "verification: 123456"
        r'pin[:\s]+(\d{4,6})',  # "pin: 1234"
    ]

    def __init__(
        self,
        email_address: str = None,
        app_password: str = None,
        imap_server: str = None,
        imap_port: int = None
    ):
        """
        Initialize the email 2FA helper.

        Args:
            email_address: Gmail/Google Workspace email address
            app_password: Google App Password (NOT your regular password)
            imap_server: IMAP server (default: imap.gmail.com)
            imap_port: IMAP port (default: 993)
        """
        self.email_address = email_address
        self.app_password = app_password
        self.imap_server = imap_server or self.IMAP_SERVER
        self.imap_port = imap_port or self.IMAP_PORT
        self._connection = None

    @classmethod
    def from_env(cls) -> 'Email2FAHelper':
        """Create helper from environment variables"""
        from app.utils.constants import Credentials
        creds = Credentials()
        return cls(
            email_address=creds.GMAIL_EMAIL,
            app_password=creds.GMAIL_APP_PASSWORD
        )

    @classmethod
    async def from_settings(
        cls,
        supabase_client=None,
        user_id: str = None,
        organization_id: str = None
    ) -> 'Email2FAHelper':
        """
        Create helper from centralized ai_agent_settings (preferred method).

        This loads Gmail credentials from the program-wide settings in the database,
        falling back to environment variables if not configured in the database.

        Args:
            supabase_client: Supabase client for database access
            user_id: Optional user ID for user-specific settings
            organization_id: Optional organization ID for org-level settings

        Returns:
            Email2FAHelper instance (may have None credentials if not configured)
        """
        try:
            from app.ai_agent.settings_service import get_gmail_credentials

            # Try to get credentials from database settings first
            credentials = await get_gmail_credentials(
                supabase_client=supabase_client,
                user_id=user_id,
                organization_id=organization_id
            )

            if credentials:
                return cls(
                    email_address=credentials.get('email'),
                    app_password=credentials.get('app_password')
                )

            # Fall back to environment variables
            logger.info("No Gmail credentials in database settings, falling back to env vars")
            return cls.from_env()

        except Exception as e:
            logger.error(f"Error loading Gmail credentials from settings: {e}")
            # Fall back to environment variables
            return cls.from_env()

    @classmethod
    def from_lead_source_settings(
        cls,
        source_name: str,
        user_id: str = None
    ) -> Optional['Email2FAHelper']:
        """
        Create helper from lead source settings metadata.

        The metadata should contain:
        {
            "two_factor_auth": {
                "email": "user@domain.com",
                "app_password": "xxxx xxxx xxxx xxxx",
                "enabled": true
            }
        }

        Args:
            source_name: Name of the lead source (e.g., "Redfin")
            user_id: Optional user ID for multi-tenant lookup

        Returns:
            Email2FAHelper instance or None if not configured
        """
        try:
            from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
            settings_service = LeadSourceSettingsSingleton.get_instance()

            if user_id:
                # Get user-specific settings
                sources = settings_service.get_all(
                    filters={"source_name": source_name},
                    user_id=user_id
                )
                if sources and len(sources) > 0:
                    source_data = sources[0]
                else:
                    source_data = None
            else:
                # Get global settings
                source_settings = settings_service.get_by_source_name(source_name)
                source_data = source_settings

            if not source_data:
                logger.warning(f"No lead source settings found for {source_name}")
                return None

            # Get metadata
            metadata = None
            if hasattr(source_data, 'metadata'):
                metadata = source_data.metadata
            elif isinstance(source_data, dict):
                metadata = source_data.get('metadata')

            if not metadata:
                logger.warning(f"No metadata found for {source_name}")
                return None

            # Parse metadata if it's a string
            if isinstance(metadata, str):
                import json
                try:
                    metadata = json.loads(metadata)
                except:
                    logger.error(f"Failed to parse metadata for {source_name}")
                    return None

            # Get 2FA config
            two_fa_config = metadata.get('two_factor_auth', {})
            if not two_fa_config.get('enabled', False):
                logger.info(f"2FA not enabled for {source_name}")
                return None

            email_addr = two_fa_config.get('email')
            app_pwd = two_fa_config.get('app_password')

            if not email_addr or not app_pwd:
                logger.warning(f"2FA email/password not configured for {source_name}")
                return None

            return cls(email_address=email_addr, app_password=app_pwd)

        except Exception as e:
            logger.error(f"Error loading 2FA settings from database: {e}")
            return None

    def connect(self) -> bool:
        """Connect to IMAP server"""
        try:
            if self._connection:
                return True

            if not self.email_address or not self.app_password:
                logger.error("Email credentials not configured")
                return False

            logger.info(f"Connecting to {self.imap_server}...")
            self._connection = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self._connection.login(self.email_address, self.app_password.replace(" ", ""))
            logger.info("IMAP connection successful")
            return True

        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP login failed: {e}")
            self._connection = None
            return False
        except Exception as e:
            logger.error(f"IMAP connection error: {e}")
            self._connection = None
            return False

    def disconnect(self):
        """Disconnect from IMAP server"""
        if self._connection:
            try:
                self._connection.logout()
            except:
                pass
            self._connection = None

    def get_verification_code(
        self,
        sender_contains: str = None,
        subject_contains: str = None,
        max_age_seconds: int = 180,
        max_retries: int = 10,
        retry_delay: float = 3.0,
        code_length: int = 6
    ) -> Optional[str]:
        """
        Get the verification code from recent emails.

        Args:
            sender_contains: Filter by sender email/name (e.g., "redfin", "noreply@redfin.com")
            subject_contains: Filter by subject line
            max_age_seconds: Only check emails from the last N seconds (default: 180 = 3 minutes)
            max_retries: Number of times to retry if code not found (default: 10)
            retry_delay: Seconds to wait between retries (default: 3.0)
            code_length: Expected length of the code (default: 6)

        Returns:
            The verification code as a string, or None if not found
        """
        for attempt in range(max_retries):
            try:
                code = self._fetch_code(
                    sender_contains=sender_contains,
                    subject_contains=subject_contains,
                    max_age_seconds=max_age_seconds,
                    code_length=code_length
                )

                if code:
                    logger.info(f"Found verification code: {code}")
                    return code

                if attempt < max_retries - 1:
                    logger.info(f"Code not found yet, retrying in {retry_delay}s... ({attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)

            except Exception as e:
                logger.error(f"Error fetching code (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)

        logger.warning("Verification code not found after all retries")
        return None

    def _fetch_code(
        self,
        sender_contains: str = None,
        subject_contains: str = None,
        max_age_seconds: int = 180,
        code_length: int = 6
    ) -> Optional[str]:
        """Internal method to fetch the code from emails"""
        if not self.connect():
            return None

        try:
            # Select inbox
            self._connection.select("INBOX")

            # Build search criteria
            # Search for recent emails
            since_date = (datetime.now() - timedelta(seconds=max_age_seconds)).strftime("%d-%b-%Y")
            search_criteria = f'(SINCE "{since_date}")'

            # Search for emails
            status, message_ids = self._connection.search(None, search_criteria)

            if status != "OK" or not message_ids[0]:
                logger.debug("No recent emails found")
                return None

            # Get message IDs (most recent first)
            ids = message_ids[0].split()
            ids.reverse()

            logger.debug(f"Found {len(ids)} recent emails to check")

            # Check each email
            for msg_id in ids[:20]:  # Only check last 20 emails
                try:
                    status, msg_data = self._connection.fetch(msg_id, "(RFC822)")

                    if status != "OK":
                        continue

                    # Parse email
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    # Check sender
                    from_header = msg.get("From", "")
                    if sender_contains and sender_contains.lower() not in from_header.lower():
                        continue

                    # Check subject
                    subject = self._decode_header(msg.get("Subject", ""))
                    if subject_contains and subject_contains.lower() not in subject.lower():
                        continue

                    # Check date
                    date_str = msg.get("Date", "")
                    msg_date = email.utils.parsedate_to_datetime(date_str)
                    if msg_date:
                        # Make timezone-aware comparison
                        now = datetime.now(msg_date.tzinfo) if msg_date.tzinfo else datetime.now()
                        age = (now - msg_date).total_seconds()
                        if age > max_age_seconds:
                            logger.debug(f"Email too old: {age}s")
                            continue

                    logger.info(f"Checking email from: {from_header}, subject: {subject[:50]}")

                    # Extract body
                    body = self._get_email_body(msg)

                    # Find code in body
                    code = self._extract_code(body, code_length)
                    if code:
                        return code

                    # Also check subject for code
                    code = self._extract_code(subject, code_length)
                    if code:
                        return code

                except Exception as e:
                    logger.debug(f"Error parsing email {msg_id}: {e}")
                    continue

            return None

        except Exception as e:
            logger.error(f"Error searching emails: {e}")
            return None

    def _decode_header(self, header: str) -> str:
        """Decode email header"""
        try:
            decoded_parts = decode_header(header)
            result = ""
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    result += part.decode(encoding or "utf-8", errors="ignore")
                else:
                    result += part
            return result
        except:
            return header

    def _get_email_body(self, msg) -> str:
        """Extract text body from email message"""
        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or "utf-8"
                        body += payload.decode(charset, errors="ignore")
                    except:
                        pass
                elif content_type == "text/html" and not body:
                    # Fallback to HTML if no plain text
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or "utf-8"
                        html = payload.decode(charset, errors="ignore")
                        # Simple HTML to text
                        body = re.sub(r'<[^>]+>', ' ', html)
                    except:
                        pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or "utf-8"
                body = payload.decode(charset, errors="ignore")
            except:
                pass

        return body

    def _extract_code(self, text: str, expected_length: int = 6) -> Optional[str]:
        """Extract verification code from text"""
        if not text:
            return None

        # Try specific patterns first
        for pattern in self.CODE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match) == expected_length:
                    return match

        # Fallback: find any N-digit number
        pattern = rf'\b(\d{{{expected_length}}})\b'
        matches = re.findall(pattern, text)
        if matches:
            # Return the first match that looks like a code (not a year, etc.)
            for match in matches:
                # Skip years (19xx, 20xx)
                if not (match.startswith("19") or match.startswith("20")):
                    return match
            # If all look like years, return first anyway
            return matches[0]

        return None

    def get_verification_link(
        self,
        sender_contains: str = None,
        subject_contains: str = None,
        link_contains: str = None,
        max_age_seconds: int = 180,
        max_retries: int = 10,
        retry_delay: float = 3.0,
        mark_as_read: bool = True
    ) -> Optional[str]:
        """
        Get a verification link from recent emails (for magic link 2FA).

        Args:
            sender_contains: Filter by sender email/name (e.g., "google", "noreply")
            subject_contains: Filter by subject line
            link_contains: Filter links by URL pattern (e.g., "accounts.google.com")
            max_age_seconds: Only check emails from the last N seconds (default: 180 = 3 minutes)
            max_retries: Number of times to retry if link not found (default: 10)
            retry_delay: Seconds to wait between retries (default: 3.0)
            mark_as_read: If True, mark the email as read after extracting the link (default: True)

        Returns:
            The verification link URL as a string, or None if not found
        """
        for attempt in range(max_retries):
            try:
                result = self._fetch_link(
                    sender_contains=sender_contains,
                    subject_contains=subject_contains,
                    link_contains=link_contains,
                    max_age_seconds=max_age_seconds
                )

                if result:
                    link, msg_id = result
                    logger.info(f"Found verification link: {link[:80]}...")

                    # Mark the email as read to prevent processing it again
                    if mark_as_read and msg_id:
                        self._mark_email_as_read(msg_id)

                    return link

                if attempt < max_retries - 1:
                    logger.info(f"Link not found yet, retrying in {retry_delay}s... ({attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)

            except Exception as e:
                logger.error(f"Error fetching link (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)

        logger.warning("Verification link not found after all retries")
        return None

    def _mark_email_as_read(self, msg_id: bytes):
        """Mark an email as read (add \\Seen flag)."""
        try:
            if self._connection:
                self._connection.store(msg_id, '+FLAGS', '\\Seen')
                logger.info(f"Marked email {msg_id} as read")
        except Exception as e:
            logger.warning(f"Failed to mark email as read: {e}")

    def _fetch_link(
        self,
        sender_contains: str = None,
        subject_contains: str = None,
        link_contains: str = None,
        max_age_seconds: int = 180
    ) -> Optional[Tuple[str, bytes]]:
        """Internal method to fetch a verification link from emails.

        Returns:
            Tuple of (link, msg_id) if found, None otherwise
        """
        if not self.connect():
            return None

        try:
            # Select inbox
            self._connection.select("INBOX")

            # Search for recent UNREAD emails first, then fall back to all recent
            since_date = (datetime.now() - timedelta(seconds=max_age_seconds)).strftime("%d-%b-%Y")

            # Try unread emails first
            search_criteria = f'(SINCE "{since_date}" UNSEEN)'
            status, message_ids = self._connection.search(None, search_criteria)

            if status != "OK" or not message_ids[0]:
                # Fall back to all recent emails
                search_criteria = f'(SINCE "{since_date}")'
                status, message_ids = self._connection.search(None, search_criteria)

            if status != "OK" or not message_ids[0]:
                logger.debug("No recent emails found")
                return None

            # Get message IDs (most recent first)
            ids = message_ids[0].split()
            ids.reverse()

            logger.debug(f"Found {len(ids)} recent emails to check for links")

            # Check each email
            for msg_id in ids[:20]:
                try:
                    status, msg_data = self._connection.fetch(msg_id, "(RFC822)")

                    if status != "OK":
                        continue

                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    # Check sender
                    from_header = msg.get("From", "")
                    if sender_contains and sender_contains.lower() not in from_header.lower():
                        continue

                    # Check subject
                    subject = self._decode_header(msg.get("Subject", ""))
                    if subject_contains and subject_contains.lower() not in subject.lower():
                        continue

                    # Check date
                    date_str = msg.get("Date", "")
                    msg_date = email.utils.parsedate_to_datetime(date_str)
                    if msg_date:
                        now = datetime.now(msg_date.tzinfo) if msg_date.tzinfo else datetime.now()
                        age = (now - msg_date).total_seconds()
                        if age > max_age_seconds:
                            continue

                    logger.info(f"Checking email for links from: {from_header}, subject: {subject[:50]}")

                    # Extract body (prefer HTML for links)
                    body = self._get_email_body_html(msg)

                    # Find verification links
                    link = self._extract_verification_link(body, link_contains)
                    if link:
                        return (link, msg_id)

                except Exception as e:
                    logger.debug(f"Error parsing email {msg_id}: {e}")
                    continue

            return None

        except Exception as e:
            logger.error(f"Error searching emails for links: {e}")
            return None

    def _get_email_body_html(self, msg) -> str:
        """Extract HTML body from email (for link extraction)"""
        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/html":
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or "utf-8"
                        body = payload.decode(charset, errors="ignore")
                        break
                    except:
                        pass
                elif content_type == "text/plain" and not body:
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or "utf-8"
                        body = payload.decode(charset, errors="ignore")
                    except:
                        pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or "utf-8"
                body = payload.decode(charset, errors="ignore")
            except:
                pass

        return body

    def _extract_verification_link(self, text: str, link_contains: str = None) -> Optional[str]:
        """Extract verification link from email body"""
        if not text:
            return None

        # Common patterns for verification links
        link_patterns = [
            r'href=["\']([^"\']+)["\']',  # HTML href
            r'(https?://[^\s<>"\']+)',  # Plain URLs
        ]

        # Keywords that indicate a verification link
        verification_keywords = [
            'verify', 'confirm', 'approve', 'signin', 'sign-in', 'login',
            'auth', 'authenticate', 'validation', 'activate', 'account'
        ]

        all_links = []
        for pattern in link_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            all_links.extend(matches)

        # Filter and prioritize links
        for link in all_links:
            link_lower = link.lower()

            # Skip obviously non-verification links
            if any(skip in link_lower for skip in ['unsubscribe', 'privacy', 'terms', 'help', 'support', '.css', '.js', '.png', '.jpg']):
                continue

            # If link_contains is specified, filter by it
            if link_contains and link_contains.lower() not in link_lower:
                continue

            # Check for verification keywords
            if any(keyword in link_lower for keyword in verification_keywords):
                logger.debug(f"Found verification link: {link[:100]}")
                return link

        # If no verification keyword found but we have link_contains filter, return first match
        if link_contains:
            for link in all_links:
                if link_contains.lower() in link.lower():
                    return link

        return None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


def get_redfin_2fa_code(
    email_address: str = None,
    app_password: str = None,
    user_id: str = None,
    max_retries: int = 15,
    retry_delay: float = 2.0
) -> Optional[str]:
    """
    Convenience function to get Redfin 2FA code.

    Args:
        email_address: Gmail address (optional if using database config)
        app_password: Gmail app password (optional if using database config)
        user_id: User ID for database lookup
        max_retries: Number of retries
        retry_delay: Delay between retries

    Returns:
        6-digit verification code or None
    """
    # Try to create helper from provided credentials or database
    helper = None

    if email_address and app_password:
        helper = Email2FAHelper(email_address=email_address, app_password=app_password)
    elif user_id:
        helper = Email2FAHelper.from_lead_source_settings("Redfin", user_id=user_id)

    if not helper:
        # Fallback to environment variables
        helper = Email2FAHelper.from_env()

    if not helper or not helper.email_address:
        logger.error("No email credentials available for 2FA")
        return None

    with helper:
        return helper.get_verification_code(
            sender_contains="redfin",
            max_age_seconds=180,
            max_retries=max_retries,
            retry_delay=retry_delay,
            code_length=6
        )
