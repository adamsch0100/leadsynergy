"""
Tool Executor - Executes AI-selected tool actions.

This module bridges Claude's tool selection with actual action execution.
It handles:
- send_sms: Send text messages via FUB
- send_email: Send emails via FUB or email service
- create_task: Create follow-up tasks for human agents
- schedule_showing: Propose showing times to leads
- add_note: Document information in lead profile
- web_search: Search the web for real estate information
- no_action: Log and skip

All actions are executed through existing FUB integration services.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass

from app.messaging.fub_sms_service import FUBSMSService, FUBSMSServiceSingleton
from app.fub.note_service import FUBNoteService, get_note_service
from app.ai_agent.response_generator import ToolResponse

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of executing a tool action."""
    success: bool
    action: str
    message: str
    data: Dict[str, Any] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "action": self.action,
            "message": self.message,
            "data": self.data or {},
            "error": self.error,
        }


class ToolExecutor:
    """
    Executes tool actions selected by Claude.

    Integrates with existing FUB services to perform actions like
    sending SMS, creating tasks, adding notes, etc.
    """

    def __init__(self, api_key: str = None, user_id: int = None):
        """
        Initialize Tool Executor.

        Args:
            api_key: FUB API key
            user_id: FUB user ID for attribution
        """
        self.sms_service = FUBSMSServiceSingleton.get_instance(api_key)
        self.note_service = get_note_service()
        self.user_id = user_id

    async def execute(
        self,
        tool_response: ToolResponse,
        fub_person_id: int,
        lead_context: Dict[str, Any] = None,
    ) -> ExecutionResult:
        """
        Execute the tool action from Claude's response.

        Args:
            tool_response: The ToolResponse from Claude
            fub_person_id: FUB person ID to act on
            lead_context: Additional lead context for action execution

        Returns:
            ExecutionResult with success/failure details
        """
        action = tool_response.action
        params = tool_response.parameters

        logger.info(f"Executing tool action: {action} for person {fub_person_id}")

        try:
            if action == "send_sms":
                return await self._execute_send_sms(fub_person_id, params)

            elif action == "send_email":
                return await self._execute_send_email(fub_person_id, params, lead_context)

            elif action == "create_task":
                return await self._execute_create_task(fub_person_id, params)

            elif action == "schedule_showing":
                return await self._execute_schedule_showing(fub_person_id, params)

            elif action == "add_note":
                return await self._execute_add_note(fub_person_id, params)

            elif action == "web_search":
                return await self._execute_web_search(fub_person_id, params, lead_context)

            elif action == "no_action":
                return self._execute_no_action(fub_person_id, params)

            else:
                logger.warning(f"Unknown action: {action}")
                return ExecutionResult(
                    success=False,
                    action=action,
                    message=f"Unknown action: {action}",
                    error=f"Action '{action}' is not supported",
                )

        except Exception as e:
            logger.error(f"Error executing {action}: {e}", exc_info=True)
            return ExecutionResult(
                success=False,
                action=action,
                message=f"Failed to execute {action}",
                error=str(e),
            )

    async def _execute_send_sms(
        self,
        fub_person_id: int,
        params: Dict[str, Any],
    ) -> ExecutionResult:
        """Send SMS via FUB Native Texting."""
        message = params.get("message", "")
        urgency = params.get("urgency", "medium")

        if not message:
            return ExecutionResult(
                success=False,
                action="send_sms",
                message="No message content provided",
                error="Empty message",
            )

        # Truncate if too long
        if len(message) > 160:
            message = message[:157] + "..."
            logger.warning(f"SMS truncated to 160 chars for person {fub_person_id}")

        result = await self.sms_service.send_text_message_async(
            person_id=fub_person_id,
            message=message,
            from_user_id=self.user_id,
        )

        if result.get("success"):
            return ExecutionResult(
                success=True,
                action="send_sms",
                message=f"SMS sent: {message[:50]}...",
                data={
                    "message_id": result.get("message_id"),
                    "message": message,
                    "urgency": urgency,
                },
            )
        else:
            return ExecutionResult(
                success=False,
                action="send_sms",
                message="Failed to send SMS",
                error=result.get("error"),
            )

    async def _execute_send_email(
        self,
        fub_person_id: int,
        params: Dict[str, Any],
        lead_context: Dict[str, Any] = None,
    ) -> ExecutionResult:
        """Send email to the lead."""
        subject = params.get("subject", "")
        body = params.get("body", "")
        include_listings = params.get("include_listings", False)

        if not subject or not body:
            return ExecutionResult(
                success=False,
                action="send_email",
                message="Missing subject or body",
                error="Email requires subject and body",
            )

        # For now, create a note with email content and create task for human to send
        # This is safer than auto-sending emails
        note_content = f"""
        <h3>AI Suggested Email</h3>
        <p><strong>Subject:</strong> {subject}</p>
        <p><strong>Body:</strong></p>
        <div style="background: #f5f5f5; padding: 10px; border-radius: 4px;">
            {body}
        </div>
        <p><em>Include listings: {'Yes' if include_listings else 'No'}</em></p>
        <p><small>Generated by AI Agent - please review and send manually or approve for auto-send</small></p>
        """

        # Add note with email draft
        note_result = self.note_service.post_note_to_person(
            person_id=fub_person_id,
            subject="AI Email Draft",
            body=note_content,
            is_html=True,
        )

        # Create task to review/send
        task_result = self.sms_service.create_task(
            person_id=fub_person_id,
            description=f"Review AI email draft: {subject}",
            due_date=datetime.now() + timedelta(hours=4),
        )

        if note_result and "error" not in note_result:
            return ExecutionResult(
                success=True,
                action="send_email",
                message=f"Email draft created: {subject}",
                data={
                    "subject": subject,
                    "body_preview": body[:100],
                    "include_listings": include_listings,
                    "note_id": note_result.get("id"),
                    "task_created": bool(task_result and "error" not in task_result),
                },
            )
        else:
            return ExecutionResult(
                success=False,
                action="send_email",
                message="Failed to create email draft",
                error=note_result.get("error") if note_result else "Unknown error",
            )

    async def _execute_create_task(
        self,
        fub_person_id: int,
        params: Dict[str, Any],
    ) -> ExecutionResult:
        """Create a follow-up task for human agent."""
        title = params.get("title", "AI Follow-up Required")
        due_in_hours = params.get("due_in_hours", 24)
        priority = params.get("priority", "medium")
        notes = params.get("notes", "")

        # Build task description
        description = title
        if notes:
            description += f"\n\nAI Notes: {notes}"
        if priority == "high":
            description = f"[URGENT] {description}"

        due_date = datetime.now() + timedelta(hours=due_in_hours)

        result = self.sms_service.create_task(
            person_id=fub_person_id,
            description=description,
            due_date=due_date,
        )

        if result.get("success"):
            return ExecutionResult(
                success=True,
                action="create_task",
                message=f"Task created: {title}",
                data={
                    "task_id": result.get("task_id"),
                    "title": title,
                    "due_in_hours": due_in_hours,
                    "priority": priority,
                },
            )
        else:
            return ExecutionResult(
                success=False,
                action="create_task",
                message="Failed to create task",
                error=result.get("error"),
            )

    async def _execute_schedule_showing(
        self,
        fub_person_id: int,
        params: Dict[str, Any],
    ) -> ExecutionResult:
        """
        Schedule an appointment - works for both BUYERS (showings) and SELLERS (listing appointments).

        For Buyers: Property showings, buyer consultations
        For Sellers: Listing appointments, home valuations, CMAs
        """
        property_address = params.get("property_address", "")
        proposed_times = params.get("proposed_times", [])
        message = params.get("message", "")
        appointment_type = params.get("appointment_type", "showing")  # "showing" or "listing"
        lead_name = params.get("lead_name", "Lead")
        assigned_agent_id = params.get("assigned_agent_id")  # FUB user ID

        if not message:
            return ExecutionResult(
                success=False,
                action="schedule_showing",
                message="No message provided",
                error="schedule_showing requires a message",
            )

        # Send the scheduling message via SMS
        sms_result = await self.sms_service.send_text_message_async(
            person_id=fub_person_id,
            message=message[:160],
            from_user_id=self.user_id,
        )

        # Create appropriate FUB task based on appointment type
        if appointment_type == "listing":
            task_description = f"LISTING APPOINTMENT - {lead_name}"
            if property_address:
                task_description += f"\nProperty: {property_address}"
            task_description += f"\nAI requested listing consultation. Lead is interested in selling."
        else:
            task_description = f"SHOWING APPOINTMENT - {lead_name}"
            if property_address:
                task_description += f"\nProperty: {property_address}"
            task_description += f"\nAI is scheduling showings. Lead is qualified and ready to view."

        if proposed_times:
            task_description += f"\nProposed times: {', '.join(proposed_times[:3])}"

        # Create task assigned to the lead's agent
        task_result = self.sms_service.create_task(
            person_id=fub_person_id,
            description=task_description,
            assigned_to=assigned_agent_id,  # Assign to lead's agent
            due_date=datetime.now() + timedelta(hours=4),  # Due in 4 hours (more urgent)
        )

        # Also add a note documenting the appointment request
        note_content = f"""
        <p><strong>Appointment Request ({appointment_type.title()})</strong></p>
        <p>AI Agent proposed appointment:</p>
        <ul>
            <li>Type: {appointment_type.title()} {'Consultation' if appointment_type == 'listing' else 'Appointment'}</li>
            {'<li>Property: ' + property_address + '</li>' if property_address else ''}
            {'<li>Proposed times: ' + ', '.join(proposed_times[:3]) + '</li>' if proposed_times else ''}
        </ul>
        <p>Message sent: "{message[:100]}..."</p>
        <p><small>Awaiting lead confirmation. Task created for agent follow-up.</small></p>
        """

        self.sms_service.add_note(
            person_id=fub_person_id,
            note_content=note_content,
        )

        if sms_result.get("success"):
            return ExecutionResult(
                success=True,
                action="schedule_showing",
                message=f"{appointment_type.title()} appointment request sent",
                data={
                    "message_sent": message[:50],
                    "property": property_address,
                    "proposed_times": proposed_times,
                    "appointment_type": appointment_type,
                    "task_created": bool(task_result and task_result.get("success")),
                    "task_id": task_result.get("task_id") if task_result else None,
                },
            )
        else:
            return ExecutionResult(
                success=False,
                action="schedule_showing",
                message=f"Failed to send {appointment_type} request",
                error=sms_result.get("error"),
            )

    async def _execute_add_note(
        self,
        fub_person_id: int,
        params: Dict[str, Any],
    ) -> ExecutionResult:
        """Add internal note to lead profile."""
        note = params.get("note", "")
        category = params.get("category", "other")

        if not note:
            return ExecutionResult(
                success=False,
                action="add_note",
                message="No note content provided",
                error="Empty note",
            )

        # Format note with category
        category_labels = {
            "qualification": "Qualification Info",
            "objection": "Objection/Concern",
            "preference": "Preference",
            "timeline": "Timeline Update",
            "other": "AI Note",
        }

        note_html = f"""
        <p><strong>{category_labels.get(category, 'AI Note')}:</strong></p>
        <p>{note}</p>
        <p><small><em>Automatically documented by AI Agent</em></small></p>
        """

        result = self.sms_service.add_note(
            person_id=fub_person_id,
            note_content=note_html,
        )

        if result.get("success"):
            return ExecutionResult(
                success=True,
                action="add_note",
                message=f"Note added: {category}",
                data={
                    "note_id": result.get("note_id"),
                    "category": category,
                    "note_preview": note[:100],
                },
            )
        else:
            return ExecutionResult(
                success=False,
                action="add_note",
                message="Failed to add note",
                error=result.get("error"),
            )

    async def _execute_web_search(
        self,
        fub_person_id: int,
        params: Dict[str, Any],
        lead_context: Dict[str, Any] = None,
    ) -> ExecutionResult:
        """
        Search the web for real estate information.

        Uses Tavily or Serper API for search, optimized for real estate queries.
        Returns search results that can be used to craft informed responses.
        """
        import os
        import aiohttp

        query = params.get("query", "")
        search_type = params.get("search_type", "general")
        location = params.get("location", "")

        if not query:
            return ExecutionResult(
                success=False,
                action="web_search",
                message="No search query provided",
                error="Empty query",
            )

        # Enhance query with location if provided
        if location and location.lower() not in query.lower():
            query = f"{query} {location}"

        # Enhance query based on search type
        type_suffixes = {
            "real_estate": "real estate homes for sale",
            "schools": "school ratings reviews",
            "neighborhoods": "neighborhood guide living",
            "market_data": "real estate market statistics trends",
        }
        if search_type in type_suffixes and search_type != "general":
            query = f"{query} {type_suffixes[search_type]}"

        logger.info(f"Web search for person {fub_person_id}: {query[:100]}")

        # Try Tavily first (better for real estate research)
        tavily_key = os.getenv("TAVILY_API_KEY")
        if tavily_key:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": tavily_key,
                            "query": query,
                            "search_depth": "advanced",
                            "include_answer": True,
                            "max_results": 5,
                        },
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return ExecutionResult(
                                success=True,
                                action="web_search",
                                message=f"Found {len(data.get('results', []))} results",
                                data={
                                    "query": query,
                                    "search_type": search_type,
                                    "answer": data.get("answer", ""),
                                    "results": [
                                        {
                                            "title": r.get("title", ""),
                                            "url": r.get("url", ""),
                                            "content": r.get("content", "")[:500],
                                        }
                                        for r in data.get("results", [])[:5]
                                    ],
                                },
                            )
            except Exception as e:
                logger.warning(f"Tavily search failed: {e}")

        # Fallback to Serper
        serper_key = os.getenv("SERPER_API_KEY")
        if serper_key:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://google.serper.dev/search",
                        json={"q": query, "num": 5},
                        headers={"X-API-KEY": serper_key},
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            organic = data.get("organic", [])
                            return ExecutionResult(
                                success=True,
                                action="web_search",
                                message=f"Found {len(organic)} results",
                                data={
                                    "query": query,
                                    "search_type": search_type,
                                    "answer": data.get("answerBox", {}).get("answer", ""),
                                    "results": [
                                        {
                                            "title": r.get("title", ""),
                                            "url": r.get("link", ""),
                                            "content": r.get("snippet", ""),
                                        }
                                        for r in organic[:5]
                                    ],
                                },
                            )
            except Exception as e:
                logger.warning(f"Serper search failed: {e}")

        # No search API configured
        return ExecutionResult(
            success=False,
            action="web_search",
            message="Search unavailable - no API configured",
            error="Neither TAVILY_API_KEY nor SERPER_API_KEY is configured",
            data={"query": query, "search_type": search_type},
        )

    def _execute_no_action(
        self,
        fub_person_id: int,
        params: Dict[str, Any],
    ) -> ExecutionResult:
        """Log no-action decision."""
        reason = params.get("reason", "No action needed")

        logger.info(f"No action taken for person {fub_person_id}: {reason}")

        return ExecutionResult(
            success=True,
            action="no_action",
            message=reason,
            data={
                "reason": reason,
                "person_id": fub_person_id,
            },
        )

    async def execute_multiple(
        self,
        tool_responses: List[ToolResponse],
        fub_person_id: int,
        lead_context: Dict[str, Any] = None,
    ) -> List[ExecutionResult]:
        """
        Execute multiple tool actions (for combination actions).

        Args:
            tool_responses: List of ToolResponses to execute
            fub_person_id: FUB person ID
            lead_context: Additional lead context

        Returns:
            List of ExecutionResults
        """
        results = []
        for tool_response in tool_responses:
            result = await self.execute(tool_response, fub_person_id, lead_context)
            results.append(result)
        return results


class ToolExecutorSingleton:
    """Singleton wrapper for Tool Executor."""

    _instance: Optional[ToolExecutor] = None

    @classmethod
    def get_instance(cls, api_key: str = None, user_id: int = None) -> ToolExecutor:
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = ToolExecutor(api_key=api_key, user_id=user_id)
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset the singleton instance."""
        cls._instance = None
