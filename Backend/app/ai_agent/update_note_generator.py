"""
AI-Generated Update Note Service

Generates intelligent @update notes for lead source platform syncs using AI.
When no manual @update note exists, this service can analyze the lead's context
(messages, notes, timeline) and generate an appropriate update for the platform.

Configuration Options (stored in lead_source_settings.metadata):
- ai_update_enabled: bool - Enable/disable AI-generated updates
- ai_update_mode: str - 'fallback' (only when no @update), 'always', 'supplement'
- ai_update_save_to_fub: bool - Save generated update as FUB note for audit trail
- ai_update_context: list - What context to include ['messages', 'notes', 'timeline']
- ai_update_tone: str - 'professional', 'concise', 'detailed'
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AIUpdateConfig:
    """Configuration for AI update note generation."""
    enabled: bool = False
    mode: str = 'fallback'  # 'fallback', 'always', 'supplement'
    save_to_fub: bool = True  # Save generated note to FUB for audit trail
    context_sources: List[str] = None  # ['messages', 'notes', 'timeline', 'all']
    tone: str = 'professional'  # 'professional', 'concise', 'detailed'
    max_length: int = 300

    def __post_init__(self):
        if self.context_sources is None:
            self.context_sources = ['messages', 'notes']

    @classmethod
    def from_metadata(cls, metadata: Dict[str, Any]) -> 'AIUpdateConfig':
        """Create config from lead_source_settings metadata."""
        if not metadata or not isinstance(metadata, dict):
            return cls()

        ai_settings = metadata.get('ai_update_settings', {})
        if not ai_settings:
            # Check for flat keys for backwards compatibility
            return cls(
                enabled=metadata.get('ai_update_enabled', False),
                mode=metadata.get('ai_update_mode', 'fallback'),
                save_to_fub=metadata.get('ai_update_save_to_fub', True),
                context_sources=metadata.get('ai_update_context', ['messages', 'notes']),
                tone=metadata.get('ai_update_tone', 'professional'),
                max_length=metadata.get('ai_update_max_length', 300)
            )

        return cls(
            enabled=ai_settings.get('enabled', False),
            mode=ai_settings.get('mode', 'fallback'),
            save_to_fub=ai_settings.get('save_to_fub', True),
            context_sources=ai_settings.get('context_sources', ['messages', 'notes']),
            tone=ai_settings.get('tone', 'professional'),
            max_length=ai_settings.get('max_length', 300)
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for storage in metadata."""
        return {
            'enabled': self.enabled,
            'mode': self.mode,
            'save_to_fub': self.save_to_fub,
            'context_sources': self.context_sources,
            'tone': self.tone,
            'max_length': self.max_length
        }


class AIUpdateNoteGenerator:
    """
    Generates AI-powered update notes for lead source platform syncs.

    Uses the lead's full context from FUB (messages, notes, timeline) to generate
    intelligent status updates that can be sent to referral platforms like
    HomeLight, ReferralExchange, Agent Pronto, etc.
    """

    def __init__(self):
        self._fub_client = None
        self._llm_client = None
        self._lead_service = None
        self._supabase = None

    @property
    def fub_client(self):
        if self._fub_client is None:
            from app.database.fub_api_client import FUBApiClient
            self._fub_client = FUBApiClient()
        return self._fub_client

    @property
    def lead_service(self):
        if self._lead_service is None:
            from app.service.lead_service import LeadServiceSingleton
            self._lead_service = LeadServiceSingleton.get_instance()
        return self._lead_service

    @property
    def supabase(self):
        if self._supabase is None:
            from app.database.supabase_client import SupabaseClientSingleton
            self._supabase = SupabaseClientSingleton.get_instance()
        return self._supabase

    async def generate_update_note(
        self,
        lead,
        platform_name: str,
        config: AIUpdateConfig,
        existing_update: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate an AI update note for a lead.

        Args:
            lead: The lead object with fub_person_id
            platform_name: Target platform (homelight, referralexchange, etc.)
            config: AI update configuration
            existing_update: Existing @update note if any (for supplement mode)

        Returns:
            Generated update note string, or None if generation failed
        """
        if not config.enabled:
            return None

        # In supplement mode, enhance existing update
        if config.mode == 'supplement' and existing_update:
            return await self._supplement_update(lead, existing_update, config)

        # In fallback mode, only generate if no existing update
        if config.mode == 'fallback' and existing_update:
            return existing_update

        # Generate new update
        try:
            # Gather context based on config
            context = await self._gather_context(lead, config)

            if not context.get('has_activity'):
                logger.info(f"No recent activity for lead {lead.first_name} {lead.last_name}, skipping AI update")
                return None

            # Generate the update using LLM
            update_text = await self._generate_with_llm(lead, platform_name, context, config)

            if not update_text:
                return None

            # Optionally save to FUB for audit trail
            if config.save_to_fub and update_text:
                await self._save_to_fub(lead, update_text, platform_name)

            return update_text

        except Exception as e:
            logger.error(f"Error generating AI update for {lead.first_name} {lead.last_name}: {e}")
            return None

    def generate_update_note_sync(
        self,
        lead,
        platform_name: str,
        config: AIUpdateConfig,
        existing_update: Optional[str] = None
    ) -> Optional[str]:
        """
        Synchronous version of generate_update_note for use in non-async contexts.
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're already in an async context, run in thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.generate_update_note(lead, platform_name, config, existing_update)
                    )
                    return future.result(timeout=30)
            else:
                return loop.run_until_complete(
                    self.generate_update_note(lead, platform_name, config, existing_update)
                )
        except Exception as e:
            logger.error(f"Error in sync generate_update_note: {e}")
            # Fall back to simple generation without async
            return self._generate_simple_update(lead, platform_name, config)

    def _generate_simple_update(
        self,
        lead,
        platform_name: str,
        config: AIUpdateConfig
    ) -> Optional[str]:
        """
        Simple synchronous update generation without full async context gathering.
        Uses basic lead info and recent notes.
        """
        try:
            # Get FUB person ID
            fub_id = getattr(lead, 'fub_person_id', None) or getattr(lead, 'fub_id', None)
            if not fub_id:
                metadata = getattr(lead, 'metadata', {}) or {}
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except:
                        metadata = {}
                fub_id = metadata.get('fub_person_id') or metadata.get('fub_id')

            if not fub_id:
                return None

            # Fetch recent notes
            notes = self.fub_client.get_notes_for_person(str(fub_id), limit=5)

            # Fetch recent messages
            messages = []
            try:
                messages = self.fub_client.get_text_messages_for_person(str(fub_id), limit=10)
            except:
                pass

            # Build context summary
            context_parts = []

            # Add recent message summary
            if messages:
                recent_msgs = [m for m in messages[:5] if m.get('message')]
                if recent_msgs:
                    last_msg = recent_msgs[0]
                    msg_text = last_msg.get('message', '')[:100]
                    is_incoming = last_msg.get('isIncoming', False)
                    direction = "from lead" if is_incoming else "to lead"
                    context_parts.append(f"Recent message {direction}: {msg_text}")

            # Add recent note summary
            if notes:
                for note in notes[:2]:
                    body = note.get('body', '')
                    if body and '@update' not in body.lower():
                        # Strip HTML
                        import re
                        clean = re.sub(r'<[^>]+>', ' ', body)
                        clean = ' '.join(clean.split())[:150]
                        if clean:
                            context_parts.append(f"Note: {clean}")

            if not context_parts:
                return None

            # Generate update using LLM
            return self._call_llm_sync(lead, platform_name, context_parts, config)

        except Exception as e:
            logger.error(f"Error in simple update generation: {e}")
            return None

    def _call_llm_sync(
        self,
        lead,
        platform_name: str,
        context_parts: List[str],
        config: AIUpdateConfig
    ) -> Optional[str]:
        """Call LLM synchronously to generate update."""
        try:
            import os
            import requests

            # Get LLM settings
            api_key = os.getenv('OPENROUTER_API_KEY') or os.getenv('OPENAI_API_KEY')
            if not api_key:
                logger.warning("No LLM API key configured for AI update generation")
                return None

            # Determine tone instructions
            tone_instructions = {
                'professional': 'Use a professional, business-appropriate tone.',
                'concise': 'Be very brief and to the point, just the essential facts.',
                'detailed': 'Provide comprehensive details about the current status and next steps.'
            }

            tone = tone_instructions.get(config.tone, tone_instructions['professional'])

            # Build prompt
            lead_name = f"{lead.first_name} {lead.last_name}".strip()
            lead_status = getattr(lead, 'status', 'Unknown')

            prompt = f"""Generate a brief status update for a real estate referral lead to send to the {platform_name} platform.

Lead: {lead_name}
Current Stage: {lead_status}

Recent Activity:
{chr(10).join('- ' + part for part in context_parts)}

Instructions:
- {tone}
- Maximum {config.max_length} characters
- Focus on current engagement status and any progress
- Do NOT include greetings or signatures
- Write as if you are the agent providing an update to the referral company
- Be factual based on the context provided

Generate the update:"""

            # Call OpenRouter API
            base_url = os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
            model = os.getenv('AI_UPDATE_MODEL', 'anthropic/claude-3-haiku')

            response = requests.post(
                f"{base_url}/chat/completions",
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'https://leadsynergy.ai',
                    'X-Title': 'LeadSynergy AI Update'
                },
                json={
                    'model': model,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': 200,
                    'temperature': 0.7
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                update_text = result.get('choices', [{}])[0].get('message', {}).get('content', '')

                # Clean up and truncate
                update_text = update_text.strip()
                if len(update_text) > config.max_length:
                    update_text = update_text[:config.max_length - 3] + '...'

                logger.info(f"Generated AI update for {lead_name}: {update_text[:50]}...")
                return update_text
            else:
                logger.error(f"LLM API error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return None

    async def _gather_context(self, lead, config: AIUpdateConfig) -> Dict[str, Any]:
        """Gather context for update generation based on config."""
        context = {
            'has_activity': False,
            'messages': [],
            'notes': [],
            'timeline': [],
            'lead_info': {}
        }

        fub_id = getattr(lead, 'fub_person_id', None) or getattr(lead, 'fub_id', None)
        if not fub_id:
            return context

        sources = config.context_sources or ['messages', 'notes']
        if 'all' in sources:
            sources = ['messages', 'notes', 'timeline']

        try:
            # Gather messages
            if 'messages' in sources:
                messages = self.fub_client.get_text_messages_for_person(str(fub_id), limit=20)
                if messages:
                    context['messages'] = messages
                    context['has_activity'] = True

            # Gather notes
            if 'notes' in sources:
                notes = self.fub_client.get_notes_for_person(str(fub_id), limit=10)
                if notes:
                    context['notes'] = notes
                    context['has_activity'] = True

            # Gather full timeline
            if 'timeline' in sources:
                # Timeline includes calls, emails, events
                try:
                    calls = self.fub_client.get_calls_for_person(str(fub_id), limit=5)
                    emails = self.fub_client.get_emails_for_person(str(fub_id), limit=5)
                    context['timeline'] = {
                        'calls': calls or [],
                        'emails': emails or []
                    }
                    if calls or emails:
                        context['has_activity'] = True
                except:
                    pass

            # Add lead info
            context['lead_info'] = {
                'name': f"{lead.first_name} {lead.last_name}".strip(),
                'status': getattr(lead, 'status', None),
                'source': getattr(lead, 'source', None),
                'tags': getattr(lead, 'tags', None)
            }

        except Exception as e:
            logger.error(f"Error gathering context: {e}")

        return context

    async def _generate_with_llm(
        self,
        lead,
        platform_name: str,
        context: Dict[str, Any],
        config: AIUpdateConfig
    ) -> Optional[str]:
        """Generate update using LLM with full context."""
        # Build context parts for the prompt
        context_parts = []

        # Process messages
        for msg in context.get('messages', [])[:5]:
            text = msg.get('message', '')[:100]
            direction = "from lead" if msg.get('isIncoming') else "to lead"
            if text:
                context_parts.append(f"Message {direction}: {text}")

        # Process notes
        import re
        for note in context.get('notes', [])[:3]:
            body = note.get('body', '')
            if body and '@update' not in body.lower():
                clean = re.sub(r'<[^>]+>', ' ', body)
                clean = ' '.join(clean.split())[:150]
                if clean:
                    context_parts.append(f"Note: {clean}")

        if not context_parts:
            return None

        return self._call_llm_sync(lead, platform_name, context_parts, config)

    async def _supplement_update(
        self,
        lead,
        existing_update: str,
        config: AIUpdateConfig
    ) -> str:
        """Supplement an existing @update with additional AI context."""
        # For now, just return the existing update
        # Future: Could enhance with additional context
        return existing_update

    async def _save_to_fub(self, lead, update_text: str, platform_name: str) -> bool:
        """Save the generated update as a note in FUB for audit trail."""
        try:
            fub_id = getattr(lead, 'fub_person_id', None) or getattr(lead, 'fub_id', None)
            if not fub_id:
                return False

            note_body = f"@update: {update_text}\n\n[AI-generated for {platform_name} sync - {datetime.now().strftime('%Y-%m-%d %H:%M')}]"

            result = self.fub_client.create_note(
                person_id=str(fub_id),
                body=note_body
            )

            if result:
                logger.info(f"Saved AI-generated update to FUB for lead {fub_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"Error saving update to FUB: {e}")
            return False


# Singleton instance
_generator_instance = None

def get_ai_update_generator() -> AIUpdateNoteGenerator:
    """Get singleton instance of AI update generator."""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = AIUpdateNoteGenerator()
    return _generator_instance


def generate_ai_update_for_sync(
    lead,
    platform_name: str,
    source_settings,
    existing_update: Optional[str] = None
) -> Optional[str]:
    """
    Convenience function to generate AI update for platform sync.

    Args:
        lead: Lead object
        platform_name: Target platform name
        source_settings: LeadSourceSettings object
        existing_update: Existing @update note if any

    Returns:
        Generated or existing update text, or None
    """
    # Get config from source settings metadata
    metadata = getattr(source_settings, 'metadata', {}) or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except:
            metadata = {}

    config = AIUpdateConfig.from_metadata(metadata)

    if not config.enabled:
        return existing_update

    generator = get_ai_update_generator()

    # Use sync version for compatibility
    result = generator.generate_update_note_sync(
        lead=lead,
        platform_name=platform_name,
        config=config,
        existing_update=existing_update
    )

    return result or existing_update
