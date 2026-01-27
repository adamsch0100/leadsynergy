# -*- coding: utf-8 -*-
"""
AI Agent Error Logger - Dedicated logging for AI agent errors.

Provides structured error logging with file rotation for production monitoring.
Errors are logged to logs/ai_agent_errors.log with automatic rotation.

Usage:
    from app.utils.ai_error_logger import ai_error_logger, log_ai_error

    # Simple error logging
    ai_error_logger.error("Something went wrong")

    # Structured error logging with context
    log_ai_error(
        error=e,
        context={
            "fub_person_id": 3277,
            "message": "Hello",
            "state": "qualifying",
        }
    )
"""

import logging
import os
import json
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional


# =============================================================================
# CONFIGURATION
# =============================================================================

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'ai_agent_errors.log')
MAX_BYTES = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5


# =============================================================================
# LOGGER SETUP
# =============================================================================

def setup_ai_error_logger() -> logging.Logger:
    """
    Set up the dedicated AI agent error logger with file rotation.

    Returns:
        Configured logger instance
    """
    # Ensure logs directory exists
    os.makedirs(LOG_DIR, exist_ok=True)

    # Create dedicated logger (separate from root logger)
    logger = logging.getLogger('ai_agent_errors')
    logger.setLevel(logging.DEBUG)

    # Prevent propagation to root logger (avoids duplicate logs)
    logger.propagate = False

    # Only add handler if not already added
    if not logger.handlers:
        # Rotating file handler
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding='utf-8',
        )
        file_handler.setLevel(logging.DEBUG)

        # Format: timestamp | level | message
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

        # Also add console handler for development
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)  # Only warnings and above to console
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


# Initialize the logger
ai_error_logger = setup_ai_error_logger()


# =============================================================================
# STRUCTURED LOGGING FUNCTIONS
# =============================================================================

def log_ai_error(
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    level: str = "error",
) -> None:
    """
    Log an AI agent error with structured context.

    Args:
        error: The exception that occurred
        context: Additional context (fub_person_id, state, message, etc.)
        level: Log level ("error", "warning", "critical")
    """
    context = context or {}

    log_entry = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "timestamp": datetime.utcnow().isoformat(),
        "context": context,
        "traceback": traceback.format_exc() if level in ["error", "critical"] else None,
    }

    # Format as single-line JSON for easy parsing
    log_message = json.dumps(log_entry, default=str)

    if level == "critical":
        ai_error_logger.critical(log_message)
    elif level == "warning":
        ai_error_logger.warning(log_message)
    else:
        ai_error_logger.error(log_message)


def log_webhook_error(
    error: Exception,
    webhook_type: str,
    payload: Optional[Dict[str, Any]] = None,
    fub_person_id: Optional[int] = None,
) -> None:
    """
    Log a webhook processing error.

    Args:
        error: The exception that occurred
        webhook_type: Type of webhook (text-received, lead-created, etc.)
        payload: The webhook payload that caused the error
        fub_person_id: The FUB person ID if available
    """
    log_ai_error(
        error=error,
        context={
            "component": "webhook",
            "webhook_type": webhook_type,
            "fub_person_id": fub_person_id,
            "payload_preview": str(payload)[:500] if payload else None,
        },
        level="error",
    )


def log_llm_error(
    error: Exception,
    fub_person_id: Optional[int] = None,
    prompt_preview: Optional[str] = None,
    conversation_state: Optional[str] = None,
) -> None:
    """
    Log an LLM/Claude API error.

    Args:
        error: The exception that occurred
        fub_person_id: The FUB person ID
        prompt_preview: First 500 chars of the prompt
        conversation_state: Current conversation state
    """
    log_ai_error(
        error=error,
        context={
            "component": "llm",
            "fub_person_id": fub_person_id,
            "prompt_preview": prompt_preview[:500] if prompt_preview else None,
            "conversation_state": conversation_state,
        },
        level="error",
    )


def log_fub_api_error(
    error: Exception,
    operation: str,
    fub_person_id: Optional[int] = None,
    endpoint: Optional[str] = None,
) -> None:
    """
    Log a FUB API error.

    Args:
        error: The exception that occurred
        operation: The operation being attempted (get_person, send_text, etc.)
        fub_person_id: The FUB person ID
        endpoint: The FUB API endpoint
    """
    log_ai_error(
        error=error,
        context={
            "component": "fub_api",
            "operation": operation,
            "fub_person_id": fub_person_id,
            "endpoint": endpoint,
        },
        level="error",
    )


def log_database_error(
    error: Exception,
    operation: str,
    table: Optional[str] = None,
    fub_person_id: Optional[int] = None,
) -> None:
    """
    Log a database error.

    Args:
        error: The exception that occurred
        operation: The operation being attempted (select, insert, upsert, etc.)
        table: The database table
        fub_person_id: The FUB person ID if applicable
    """
    log_ai_error(
        error=error,
        context={
            "component": "database",
            "operation": operation,
            "table": table,
            "fub_person_id": fub_person_id,
        },
        level="error",
    )


def log_compliance_block(
    fub_person_id: int,
    reason: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log when a message is blocked for compliance reasons.

    Args:
        fub_person_id: The FUB person ID
        reason: Why the message was blocked
        details: Additional details (time, timezone, etc.)
    """
    log_entry = {
        "event": "compliance_block",
        "fub_person_id": fub_person_id,
        "reason": reason,
        "details": details,
        "timestamp": datetime.utcnow().isoformat(),
    }

    ai_error_logger.warning(json.dumps(log_entry, default=str))


def log_handoff(
    fub_person_id: int,
    reason: str,
    conversation_state: Optional[str] = None,
    lead_score: Optional[int] = None,
) -> None:
    """
    Log when a lead is handed off to a human agent.

    Args:
        fub_person_id: The FUB person ID
        reason: Why the handoff occurred
        conversation_state: Current conversation state
        lead_score: Current lead score
    """
    log_entry = {
        "event": "handoff",
        "fub_person_id": fub_person_id,
        "reason": reason,
        "conversation_state": conversation_state,
        "lead_score": lead_score,
        "timestamp": datetime.utcnow().isoformat(),
    }

    ai_error_logger.info(json.dumps(log_entry, default=str))


def log_opt_out(
    fub_person_id: int,
    keyword: str,
    phone: Optional[str] = None,
) -> None:
    """
    Log when a lead opts out.

    Args:
        fub_person_id: The FUB person ID
        keyword: The opt-out keyword used
        phone: The phone number (partially masked)
    """
    # Mask phone number for privacy
    masked_phone = None
    if phone and len(phone) > 4:
        masked_phone = "***" + phone[-4:]

    log_entry = {
        "event": "opt_out",
        "fub_person_id": fub_person_id,
        "keyword": keyword,
        "phone_masked": masked_phone,
        "timestamp": datetime.utcnow().isoformat(),
    }

    ai_error_logger.warning(json.dumps(log_entry, default=str))


# =============================================================================
# METRICS LOGGING
# =============================================================================

def log_response_metrics(
    fub_person_id: int,
    response_time_ms: int,
    tokens_used: Optional[int] = None,
    conversation_state: Optional[str] = None,
    success: bool = True,
) -> None:
    """
    Log response generation metrics for monitoring.

    Args:
        fub_person_id: The FUB person ID
        response_time_ms: Time to generate response in milliseconds
        tokens_used: Number of tokens used (if available)
        conversation_state: Current conversation state
        success: Whether the response was successful
    """
    log_entry = {
        "event": "response_metrics",
        "fub_person_id": fub_person_id,
        "response_time_ms": response_time_ms,
        "tokens_used": tokens_used,
        "conversation_state": conversation_state,
        "success": success,
        "timestamp": datetime.utcnow().isoformat(),
    }

    ai_error_logger.info(json.dumps(log_entry, default=str))


# =============================================================================
# LOG FILE ACCESS
# =============================================================================

def get_recent_errors(limit: int = 50) -> list:
    """
    Get recent errors from the log file.

    Args:
        limit: Maximum number of entries to return

    Returns:
        List of recent log entries (newest first)
    """
    if not os.path.exists(LOG_FILE):
        return []

    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Get last N lines, reverse for newest first
        recent = lines[-limit:] if len(lines) > limit else lines
        recent.reverse()

        return [line.strip() for line in recent if line.strip()]
    except Exception as e:
        ai_error_logger.error(f"Failed to read log file: {e}")
        return []


def get_error_summary(hours: int = 24) -> Dict[str, Any]:
    """
    Get a summary of errors from the last N hours.

    Args:
        hours: Number of hours to look back

    Returns:
        Summary dict with error counts by type
    """
    cutoff = datetime.utcnow().timestamp() - (hours * 3600)
    errors = get_recent_errors(limit=1000)

    summary = {
        "total_errors": 0,
        "by_component": {},
        "by_type": {},
        "recent_critical": [],
    }

    for line in errors:
        try:
            # Parse timestamp from log line
            if " | " not in line:
                continue

            parts = line.split(" | ", 2)
            if len(parts) < 3:
                continue

            timestamp_str, level, message = parts

            # Try to parse message as JSON
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                continue

            # Check if within time window
            if "timestamp" in data:
                try:
                    entry_time = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
                    if entry_time.timestamp() < cutoff:
                        continue
                except (ValueError, AttributeError):
                    pass

            # Count errors
            if level in ["ERROR", "CRITICAL"]:
                summary["total_errors"] += 1

                # By component
                component = data.get("context", {}).get("component", "unknown")
                summary["by_component"][component] = summary["by_component"].get(component, 0) + 1

                # By error type
                error_type = data.get("error_type", "unknown")
                summary["by_type"][error_type] = summary["by_type"].get(error_type, 0) + 1

                # Track critical errors
                if level == "CRITICAL":
                    summary["recent_critical"].append({
                        "timestamp": data.get("timestamp"),
                        "error": data.get("error_message"),
                        "component": component,
                    })

        except Exception:
            continue

    return summary
