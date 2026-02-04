# AI Agent Task Extraction & Execution Plan

## Vision
Instead of just flagging action items for humans, the AI **executes tasks autonomously** when possible:
- "Email me lender contacts" → AI composes and sends email with lender info
- "What's my agent's availability?" → AI checks calendar and responds
- "Send me that contract" → AI finds document and emails it
- "Who should I call for inspections?" → AI responds with inspector contacts

## Core Concept: Tool-Using AI Agent

The AI agent becomes a **proactive assistant** that:
1. **Detects** action requests in conversations
2. **Determines** what tool/data is needed
3. **Executes** the action autonomously
4. **Reports** back to the lead with results

---

## Phase 1: Email Execution (Highest Impact)

### Use Case: "Can you email some lender contacts?"

**Current Behavior:**
- AI responds: "I'll have Adam send you lender contacts"
- Creates FUB task for human
- Human has to manually send email

**New Behavior:**
- AI responds: "Absolutely! I'm sending you our trusted lender contacts now - check your inbox in the next minute!"
- AI composes professional email with lender contacts
- AI sends via Playwright (already have this capability!)
- AI confirms: "Just sent that over! Did you receive it?"

### Implementation

**Step 1: Detect Email Requests**
```python
# Backend/app/ai_agent/action_detector.py
EMAIL_REQUEST_PATTERNS = {
    "lender_contacts": [
        r"email.*lender",
        r"send.*lender.*contact",
        r"who.*recommend.*mortgage",
    ],
    "inspector_contacts": [
        r"email.*inspector",
        r"send.*inspector.*contact",
        r"recommend.*inspector",
    ],
    "property_info": [
        r"email.*property.*info",
        r"send.*listing.*detail",
        r"more info.*property",
    ],
    "contract_docs": [
        r"email.*contract",
        r"send.*paperwork",
        r"email.*disclosure",
    ],
}

def detect_email_request(message: str) -> Optional[Dict[str, Any]]:
    """
    Detect if lead is requesting information via email.

    Returns:
        {
            "action": "send_email",
            "content_type": "lender_contacts" | "inspector_contacts" | ...,
            "context": {...}
        }
    """
    for content_type, patterns in EMAIL_REQUEST_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, message.lower()):
                return {
                    "action": "send_email",
                    "content_type": content_type,
                    "lead_message": message,
                }
    return None
```

**Step 2: Email Content Generator**
```python
# Backend/app/ai_agent/email_composer.py
class AIEmailComposer:
    """
    Composes professional emails based on lead requests.
    Uses templates + settings (lender contacts, inspector contacts, etc.)
    """

    def compose_lender_contacts_email(
        self,
        lead_name: str,
        agent_name: str,
        lender_contacts: List[Dict],
    ) -> Dict[str, str]:
        """
        Compose professional email with lender contacts.

        Returns:
            {
                "subject": "Trusted Lender Contacts from [Agent Name]",
                "body_html": "<html>...</html>",
                "body_text": "Plain text version"
            }
        """
        subject = f"Trusted Lender Contacts from {agent_name}"

        body_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px;">
            <p>Hi {lead_name},</p>

            <p>As promised, here are the mortgage lenders I personally recommend.
            They've helped many of my clients get great rates and smooth closings:</p>

            <div style="margin: 20px 0;">
        """

        for lender in lender_contacts:
            body_html += f"""
                <div style="border-left: 3px solid #4A90E2; padding-left: 15px; margin: 15px 0;">
                    <h3 style="margin: 0;">{lender['name']}</h3>
                    <p style="margin: 5px 0; color: #666;">{lender['company']}</p>
                    <p style="margin: 5px 0;">
                        <strong>Phone:</strong> {lender['phone']}<br>
                        <strong>Email:</strong> <a href="mailto:{lender['email']}">{lender['email']}</a>
                    </p>
                    {f"<p style='margin: 5px 0; font-style: italic;'>{lender.get('specialty', '')}</p>" if lender.get('specialty') else ""}
                    {f"<p style='margin: 5px 0; color: #444;'>{lender.get('note', '')}</p>" if lender.get('note') else ""}
                </div>
            """

        body_html += f"""
            </div>

            <p>Feel free to mention my name when you reach out - they know I only refer serious buyers!</p>

            <p>Let me know if you have any questions or want to discuss your financing options.</p>

            <p>Best regards,<br>
            <strong>{agent_name}</strong></p>
        </div>
        """

        # Plain text version
        body_text = f"Hi {lead_name},\n\nAs promised, here are the mortgage lenders I personally recommend:\n\n"
        for lender in lender_contacts:
            body_text += f"\n{lender['name']} - {lender['company']}\n"
            body_text += f"Phone: {lender['phone']}\n"
            body_text += f"Email: {lender['email']}\n"
            if lender.get('specialty'):
                body_text += f"{lender['specialty']}\n"
            body_text += "\n"

        body_text += f"\nFeel free to mention my name when you reach out!\n\nBest,\n{agent_name}"

        return {
            "subject": subject,
            "body_html": body_html,
            "body_text": body_text,
        }
```

**Step 3: Email Executor**
```python
# Backend/app/ai_agent/task_executor.py
class AITaskExecutor:
    """
    Executes tasks autonomously on behalf of the lead.
    Uses Playwright, FUB API, and other tools.
    """

    async def execute_email_lender_contacts(
        self,
        lead_email: str,
        lead_name: str,
        agent_name: str,
        lender_contacts: List[Dict],
        fub_credentials: Dict,
    ) -> Dict[str, Any]:
        """
        Execute: Send lender contacts via email.

        Returns:
            {
                "success": True/False,
                "confirmation_message": "Just sent that over! Check your inbox.",
                "error": None or error message
            }
        """
        try:
            # Compose email
            composer = AIEmailComposer()
            email_content = composer.compose_lender_contacts_email(
                lead_name=lead_name,
                agent_name=agent_name,
                lender_contacts=lender_contacts,
            )

            # Send via Playwright (already have this!)
            from app.messaging.playwright_sms_service import PlaywrightSMSService
            email_service = PlaywrightSMSService()

            result = await email_service.send_email(
                agent_id=fub_credentials['agent_id'],
                person_id=fub_credentials['person_id'],
                subject=email_content['subject'],
                body=email_content['body_html'],
                credentials=fub_credentials,
            )

            if result.get('success'):
                return {
                    "success": True,
                    "confirmation_message": "Just sent that over! Check your inbox in the next minute - I included contact info for 3 excellent lenders I personally recommend.",
                    "error": None,
                }
            else:
                return {
                    "success": False,
                    "confirmation_message": None,
                    "error": result.get('error'),
                }

        except Exception as e:
            logger.error(f"Failed to execute email lender contacts: {e}")
            return {
                "success": False,
                "confirmation_message": None,
                "error": str(e),
            }
```

**Step 4: Integration into Agent Service**
```python
# Backend/app/ai_agent/agent_service.py
# Add after intent detection, before response generation

# Detect executable actions
from app.ai_agent.action_detector import detect_email_request
from app.ai_agent.task_executor import AITaskExecutor

action_request = detect_email_request(message)
if action_request and action_request['action'] == 'send_email':
    logger.info(f"Detected executable action: {action_request['content_type']}")

    # Check if we have the data to fulfill this request
    if action_request['content_type'] == 'lender_contacts':
        lender_contacts = self.settings.vendor_contacts.get('lenders', [])

        if lender_contacts and lead_profile.email:
            # EXECUTE THE TASK
            executor = AITaskExecutor()
            exec_result = await executor.execute_email_lender_contacts(
                lead_email=lead_profile.email,
                lead_name=lead_profile.first_name,
                agent_name=self.settings.agent_name or lead_profile.assigned_agent,
                lender_contacts=lender_contacts,
                fub_credentials={
                    'agent_id': user_id,
                    'person_id': fub_person_id,
                    'email': Credentials().FUB_LOGIN_EMAIL,
                    'password': Credentials().FUB_LOGIN_PASSWORD,
                    'type': Credentials().FUB_LOGIN_TYPE,
                },
            )

            if exec_result['success']:
                # Task executed! Return confirmation
                response.response_text = exec_result['confirmation_message']
                response.result = ProcessingResult.SUCCESS
                response.template_used = "task_executed_lender_contacts"

                # Log the action
                await log_ai_message(
                    conversation_id=context.conversation_id,
                    fub_person_id=fub_person_id,
                    direction="action_executed",
                    channel="email",
                    message_content=f"Sent lender contacts to {lead_profile.email}",
                    extracted_data={"action": "email_lender_contacts", "success": True},
                )

                return response
            else:
                # Task failed - fallback to human handoff
                logger.warning(f"Failed to execute lender email: {exec_result['error']}")
                # Continue to normal response generation (will create task for human)
        else:
            # Missing data - can't execute
            logger.info(f"Cannot execute lender email - missing contacts or lead email")
            # Continue to normal response generation
```

---

## Phase 2: Information Lookup Execution

### Use Case: "What's your availability this week?"

**Implementation:**
```python
# Backend/app/ai_agent/action_detector.py
LOOKUP_REQUEST_PATTERNS = {
    "agent_availability": [
        r"when.*available",
        r"what.*availability",
        r"free.*this week",
        r"schedule.*showing",
    ],
    "property_details": [
        r"tell me about.*property",
        r"what.*bedrooms",
        r"how much.*square feet",
    ],
}

# Backend/app/ai_agent/task_executor.py
async def execute_availability_lookup(
    self,
    agent_id: str,
    timeframe: str = "this week",
) -> Dict[str, Any]:
    """
    Look up agent's availability via Google Calendar API.

    Returns available time slots for showing appointments.
    """
    try:
        from app.calendar.google_calendar import get_available_slots

        slots = await get_available_slots(
            agent_id=agent_id,
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=7),
            duration_minutes=60,  # 1 hour for showings
        )

        if slots:
            # Format friendly response
            slot_text = "\n".join([
                f"- {slot['day']} at {slot['time']}"
                for slot in slots[:5]  # Limit to 5 options
            ])

            return {
                "success": True,
                "confirmation_message": f"Great question! I have availability:\n\n{slot_text}\n\nWhich time works best for you?",
                "available_slots": slots,
            }
        else:
            return {
                "success": False,
                "confirmation_message": "Let me check the calendar and get back to you shortly with some times!",
                "available_slots": [],
            }

    except Exception as e:
        logger.error(f"Failed to execute availability lookup: {e}")
        return {
            "success": False,
            "confirmation_message": None,
            "error": str(e),
        }
```

---

## Phase 3: Document Sending Execution

### Use Case: "Can you send me the purchase agreement?"

**Implementation:**
```python
# Backend/app/ai_agent/document_manager.py
class DocumentManager:
    """
    Manages documents, templates, and contracts.
    Can retrieve and send via email.
    """

    DOCUMENT_LIBRARY = {
        "purchase_agreement": {
            "filename": "Purchase_Agreement_Template.pdf",
            "path": "/documents/templates/",
            "description": "Standard purchase agreement for Washington state",
        },
        "seller_disclosure": {
            "filename": "Seller_Disclosure_Form.pdf",
            "path": "/documents/templates/",
            "description": "Seller disclosure statement",
        },
        # ... more documents
    }

    async def send_document_via_email(
        self,
        document_type: str,
        lead_email: str,
        lead_name: str,
        agent_name: str,
    ) -> Dict[str, Any]:
        """
        Find document and send via email with professional cover message.
        """
        if document_type not in self.DOCUMENT_LIBRARY:
            return {"success": False, "error": "Document not found"}

        doc_info = self.DOCUMENT_LIBRARY[document_type]

        # Compose email with attachment
        subject = f"{doc_info['description']} from {agent_name}"
        body = f"""
        Hi {lead_name},

        Attached is the {doc_info['description']} you requested.

        Please review and let me know if you have any questions!

        Best regards,
        {agent_name}
        """

        # Send via email service with attachment
        # ... implementation
```

---

## Implementation Priority

### Week 1: Email Execution (Lender Contacts)
1. Build `action_detector.py` - detect email requests
2. Build `email_composer.py` - compose professional emails
3. Build `task_executor.py` - execute email sending
4. Integrate into `agent_service.py`
5. **Test with lender contacts scenario**

### Week 2: More Email Types
1. Inspector contacts
2. Property information
3. Documents/contracts

### Week 3: Information Lookup
1. Agent availability (Google Calendar integration)
2. Property details (MLS lookup)

### Week 4: Testing & Deployment
1. Comprehensive testing (20+ scenarios)
2. Error handling and fallbacks
3. Deploy on real leads!

---

## Success Metrics

**Before:**
- "Email me lender contacts" → FUB task created → human sends email manually (5-60 min delay)

**After:**
- "Email me lender contacts" → AI sends email instantly (< 1 minute)
- Lead receives professional, branded email with all lender contacts
- Lead responds: "Got it, thanks!" (instant gratification = higher engagement)

**Expected Impact:**
- 90% reduction in response time for information requests
- 50% increase in lead engagement (instant responses are impressive)
- Human agents freed up to focus on appointments and closings
- Leads feel VIP treatment (instant, professional service)

---

## Fallback Strategy

When AI cannot execute a task (missing data, error, etc.):
1. **Gracefully acknowledge**: "Great question! Let me get that information for you."
2. **Create FUB task** for human agent
3. **Set expectations**: "I'll have [Agent Name] send that over within the hour."
4. **Log the failure** for improvement

This ensures no requests fall through the cracks, even when autonomous execution fails.

---

## Next Steps

Ready to implement? Let's start with **Email Execution for Lender Contacts** - highest impact, leverages existing Playwright capability, and directly addresses your use case.

**Quick Win Timeline:**
- Day 1: Build action detector + email composer
- Day 2: Build task executor + integrate
- Day 3: Test with 10 scenarios
- Day 4: Deploy on test lead
- Day 5: Deploy on real leads!

Let me know when you're ready to start building! 🚀
