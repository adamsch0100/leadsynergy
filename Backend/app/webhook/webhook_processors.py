import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from app.database.fub_api_client import FUBApiClient
from app.database.lead_cache import LeadCacheSingleton
from app.database.note_cache import NoteCacheSingleton
from app.database.supabase_client import SupabaseClientSingleton
from app.models.lead import Lead, LeadNote
from app.service.lead_service import LeadServiceSingleton
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
from app.service.note_service import NoteServiceSingleton
from app.service.stage_mapper_service import StageMapperService
from app.utils.constants import Credentials
from app.utils.dependency_container import DependencyContainer
from app.webhook.fub_webhook import lead_has_meaningful_changes
from app.service.redis_service import RedisServiceSingleton
from app.webhook.auto_enhancement_handler import AutoEnhancementHandlerSingleton

# API Key for an Admin user in the Follow Up Boss Account
CREDS = Credentials()

# Get the dependency container
container = DependencyContainer.get_instance()

# Services
lead_service = LeadServiceSingleton.get_instance()
note_service = NoteServiceSingleton.get_instance()
stage_mapper_service: StageMapperService = container.get_service('stage_mapper_service')
lead_source_settings_service = LeadSourceSettingsSingleton.get_instance()
lead_cache = LeadCacheSingleton.get_instance()
note_cache = NoteCacheSingleton.get_instance()

# Database
supabase = SupabaseClientSingleton.get_instance()

# API Client
api_client = FUBApiClient()

# Redis
redis_service = RedisServiceSingleton.get_instance()

# Auto Enhancement
auto_enhancement_handler = AutoEnhancementHandlerSingleton.get_instance()


######################## Utility Functions ########################
def add_to_friday_schedule(category: str, identifier: str):
    try:
        redis_service.sadd(f"friday_schedule:{category}", identifier)
        print(f'Added {identifier} to Friday schedule for category {category}')
    except Exception as e:
        print(f"Error adding to Friday schedule: {e}")

def normalize_value(value):
    if value is None:
        return ""

    return str(value).strip()


def normalize_tags(tags_value):
    print(f"normalize_tags input (type: {type(tags_value)}: {tags_value}")

    if tags_value is None:
        return set()
    if isinstance(tags_value, str):
        # Try to parse JSON if it looks like a JSON array
        if tags_value.strip().startswith('[') and tags_value.strip().endswith(']'):
            try:
                import json
                parsed_tags = json.loads(tags_value)
                print(f"Parsed JSON tags: {parsed_tags}")
                return {str(tag).strip().lower() for tag in parsed_tags if tag}
            except json.JSONDecodeError as e:
                print(f"JSON parse error: {e}")
                # Fall back to splitting by commas
                tags = set(tag.strip().lower() for tag in tags_value.strip('[]').split(',') if tag.strip())
                print(f"Split tags: {tags}")
                return tags

        # Single tag as string
        print(f"Tags Value: {tags_value}")
        return {tags_value.strip().lower()} if tags_value.strip() else set()

    # If it's a list, set, or other iterable
    try:
        # Convert all tags to lowercase strings and remove empty ones
        tags = {str(tag).strip().lower() for tag in tags_value if tag}
        print(f"Normalized tags: {tags}")
        return tags
    except (TypeError, AttributeError) as e:
        print(f"Error normalizing tags: {e}, returning empty set")
        return set()


def log_error(error_type: str, error_message: str, metadata: Optional[Dict] = None):
    try:
        error_log = {
            'id': str(uuid.uuid4()),
            'created_at': datetime.now().isoformat(),
            'error_type': error_type,
            'timestamp': datetime.now().isoformat(),
            'error_message': str(error_message),
            'metadata': metadata
        }

        # Print local
        print(f"Logging error to Supabase - Type: {error_type}, Message: {error_message}")

        if metadata and not isinstance(metadata, dict):
            metadata = {'data': str(metadata)}

        result = supabase.table('error_logs').insert(error_log).execute()
        print(f"Supabase log result: {result}")

    except Exception as e:
        print(f"Error logging to Supabase: {str(e)}")
        print(f"Exception type: {type(e).__name__}")
        import traceback
        traceback.print_exc()

def ensure_naive_datetime(dt):
    """
    Ensure all datetimes are naive (no timezone) for consistent comparisons.
    Handles None values, strings, and both offset-aware and offset-naive datetimes.

    Args:
        dt: A datetime object, string, or None

    Returns:
        datetime: A naive datetime object with no timezone info
        None: If input cannot be converted to datetime
    """
    if dt is None:
        return None

    # Convert string to datetime if needed
    if isinstance(dt, str):
        try:
            # Replace 'Z' with '+00:00' for proper ISO format
            if 'Z' in dt:
                dt = dt.replace('Z', '+00:00')
            # Parse the string to datetime
            dt = datetime.fromisoformat(dt)
        except (ValueError, TypeError):
            return None

    # Ensure datetime has no timezone
    if isinstance(dt, datetime) and dt.tzinfo is not None:
        return dt.replace(tzinfo=None)

    # Return the datetime object (already naive or converted)
    return dt


######################## Webhook Processors ########################
async def process_stage_updated_webhook(lead: Lead):
    try:
        person_id = lead.fub_person_id
        tags = lead.tags if hasattr(lead, 'tags') and lead.tags else []

        print(f"🔔 Processing stage for person {person_id}: {lead.first_name} {lead.last_name}")

        # Extract stage information
        fub_stage_id = lead.stage_id
        fub_stage_name = lead.status

        if not fub_stage_id or not fub_stage_name:
            print(f"No stage information found for person ID: {person_id}")
            return

        # Get the full stage details (options, for more metadata)
        try:
            stage_details = api_client.get_stage(fub_stage_id)
        except Exception as e:
            print(f"Error getting stage details: {e}")
            stage_details = None

        # Handle stage mapping to external platforms
        platform_results = stage_mapper_service.handle_fub_stage_change(
            fub_person_id=person_id,
            fub_stage_id=fub_stage_id,
            fub_stage_name=fub_stage_name
        )

        print(f"Platform update results: {platform_results}")

        # Create a log entry for this stage change
        log_entry = {
            'id': str(uuid.uuid4()),
            'lead_id': lead.id,
            'fub_person_id': person_id,
            'previous_stage': lead.status,
            'new_stage': fub_stage_name,
            'timestamp': ensure_naive_datetime(datetime.now()).isoformat(),
        }

        # Insert log entry into Supabase
        supabase.table('stage_change_logs').insert(log_entry).execute()

    except Exception as e:
        log_error('stage_webhook_processing', str(e), {'lead_id': lead.id if lead else None})

async def process_note_webhook(lead: Lead, note_data: Dict[str, Any], event_type: str = 'created'):
    try:
        person_id = lead.fub_person_id
        tags = lead.tags if hasattr(lead, 'tags') and lead.tags else []

        print(f"🔔 Processing note {event_type} for person {person_id}: {lead.first_name} {lead.last_name}")

        # Get the note ID from the note data
        resource_ids = note_data.get('resourceIds', [])
        if not resource_ids:
            resource_id = note_data.get('id')
            if not resource_id:
                print("No resource ID found in webhook data")
                return
        else:
            resource_id = resource_ids[0]

        print(f"Resource ID: {resource_id}")

        # Check if note already exists in our cache/database
        existing_note = note_cache.sync_with_db_and_cache(resource_id)

        if existing_note:
            print(f"Updating existing note ID: {existing_note.id}")

            # Update note with new data
            existing_note.body = note_data.get('body', existing_note.body)
            existing_note.updated_at = ensure_naive_datetime(datetime.now())

            # Update agent information if available
            if note_data.get('updatedById'):
                existing_note.updated_by_id = note_data.get('updatedById')
            if note_data.get('updatedBy'):
                existing_note.updated_by = note_data.get('updatedBy')

            # Update subject if available
            if note_data.get('subject'):
                existing_note.subject = note_data.get('subject')

            # Update metadata
            if not existing_note.metadata:
                existing_note.metadata = {}

            existing_note.metadata.update({
                'source': 'fub_webhook',
                'note_data': note_data,
                'updated_at': datetime.now().isoformat(),
                'last_update_source': f"fub_webhook_{event_type}",
            })

            # Update the note in database
            updated_note = note_service.update(existing_note)

            # Update the cache
            note_cache.store_note(updated_note)

            print(f"Note updated successfully: {updated_note.id} for lead {lead.id}")

        else:
            # Check for ReferralLink or LeadSynergy tag before creating new note
            if 'ReferralLink' not in tags and 'LeadSynergy' not in tags:
                print(f"No ReferralLink/LeadSynergy tag present for lead: {lead.id}, skipping note creation")
                return

            print(f"Creating new note for lead ID: {lead.id}")

            # Create the note with proper lead association
            note = LeadNote()
            note.id = str(uuid.uuid4())
            note.lead_id = lead.id
            note.note_id = resource_id

            # Set content/body
            note.body = note_data.get('body', '')

            # Set agent information if available
            note.created_by_id = note_data.get('createdById')
            note.updated_by_id = note_data.get('updatedById')
            note.created_by = note_data.get('createdBy')
            note.updated_by = note_data.get('updatedBy')

            # Set subject if available
            note.subject = note_data.get('subject', '')

            # Parse created date if available
            created_str = note_data.get('created')
            if created_str:
                try:
                    note.created_at = ensure_naive_datetime(created_str)
                except (ValueError, TypeError):
                    note.created_at = ensure_naive_datetime(created_str)

            else:
                note.created_at = ensure_naive_datetime(datetime.now())

            note.updated_at = ensure_naive_datetime(datetime.now())

            # Set metadata
            note.metadata = {
                'source': 'fub_webhook',
                'note_data': note_data,
                'created_during': event_type,
                'tags_at_creation': tags
            }

            # Save the note to the database
            saved_note = note_service.create(note)

            # Store the new note in cache
            note_cache.store_note(saved_note)

            print(f"Note created successfully with ID: {saved_note.id} for lead {lead.id}")

    except Exception as e:
        log_error('note_webhook_processing', str(e), {
            'lead_id': lead.id if lead else None,
            'event_type': event_type
        })


async def process_tag_webhook(lead: Lead):
    try:
        person_id = lead.fub_person_id
        tags = lead.tags if hasattr(lead, 'tags') and lead.tags else []

        print(f"🔔 Processing tags for person {person_id}: {tags}")

        # First check if this lead exists in our database
        existing_lead = lead_service.get_by_fub_person_id(person_id)

        if not existing_lead:
            if 'ReferralLink' in tags or 'LeadSynergy' in tags:
                # Create the lead in our database
                saved_lead = lead_service.create(lead)
                if saved_lead and hasattr(saved_lead, 'id') and saved_lead.id:
                    print(f"Created new lead with ID: {saved_lead.id} from ReferralLink/LeadSynergy tag")
                    mapping = stage_mapper_service.add_stage_mapping(saved_lead.fub_person_id, saved_lead.source)
                    if mapping and hasattr(mapping, 'id'):
                        print(f"Created new Mapping with ID: {mapping.id}")

                        # Trigger auto-enhancement for the new lead
                        try:
                            await trigger_auto_enhancement_for_lead(saved_lead)
                        except Exception as enhance_err:
                            print(f"Auto-enhancement error (non-blocking): {enhance_err}")
                    else:
                        lead_service.delete(saved_lead.id)
                        print("Failed to create mapping, deleting lead data from DB...")
                        return
                else:
                    print("Failed to create lead")
            else:
                print(f"No ReferralLink/LeadSynergy tag present and no existing lead - skipping lead creation")
                return
        else:
            # Use the existing lead from database
            # If we need to update the lead with latest data from FUB
            data = api_client.get_person(person_id)
            new_lead = Lead.from_fub(data)

            # Preserve important fields from existing lead
            new_lead.id = existing_lead.id
            new_lead.created_at = existing_lead.created_at

            # Update the lead if needed
            if lead_has_meaningful_changes(existing_lead, new_lead):
                lead = lead_service.update(new_lead)
                print(f"Lead updated with new data")

        # Get the external status mapping
        external_status = lead_service.get_fub_stage_mapping(lead)
        print(f"FUB Status: {lead.status}")
        print(f"External Status: {external_status}")

    except Exception as e:
        log_error('tag_webhook_processing', str(e), {
            'lead_id': lead.id if lead else None
        })


async def process_person_created_webhook(webhook_data: Dict[str, Any], user_id: str = None):
    """
    Process a new person created webhook and optionally trigger auto-enhancement.

    Args:
        webhook_data: The webhook payload from FUB
        user_id: Optional user ID (will try to resolve if not provided)
    """
    try:
        print(f"🔔 Processing person created webhook")

        # Extract person data
        person_data = webhook_data.get('person', webhook_data.get('data', {}))
        fub_person_id = person_data.get('id')

        if not fub_person_id:
            print("No person ID found in webhook data")
            return

        person_name = f"{person_data.get('firstName', '')} {person_data.get('lastName', '')}".strip()
        print(f"New person: {person_name} (ID: {fub_person_id})")

        # Check for ReferralLink or LeadSynergy tag
        tags = person_data.get('tags', [])
        should_process = any(tag in ['ReferralLink', 'LeadSynergy'] for tag in tags)

        if not should_process:
            print(f"No ReferralLink/LeadSynergy tag found, skipping auto-enhancement")
            return

        # Try to auto-enhance the new lead
        try:
            enhancement_result = auto_enhancement_handler.process_new_person_webhook(
                webhook_data=webhook_data,
                user_id=user_id
            )

            if enhancement_result.get('auto_enhanced'):
                print(f"✅ Auto-enhanced new lead {fub_person_id}")
                details = enhancement_result.get('enhancement_details', {})
                print(f"   - Phones added: {details.get('phones_added', 0)}")
                print(f"   - Emails added: {details.get('emails_added', 0)}")
                print(f"   - Note posted: {details.get('note_posted', False)}")
            else:
                print(f"Auto-enhancement not performed: {enhancement_result.get('message', 'Unknown reason')}")

        except Exception as enhance_error:
            print(f"Error during auto-enhancement: {enhance_error}")
            log_error('auto_enhancement', str(enhance_error), {
                'fub_person_id': fub_person_id
            })

    except Exception as e:
        log_error('person_created_webhook_processing', str(e), {
            'webhook_data': webhook_data
        })


async def trigger_auto_enhancement_for_lead(lead: Lead, user_id: str = None):
    """
    Trigger auto-enhancement for an existing lead.
    Called when a new lead is created via tag webhook.

    Args:
        lead: The Lead object
        user_id: Optional user ID
    """
    try:
        if not lead or not lead.fub_person_id:
            return

        print(f"🔍 Checking auto-enhancement for lead {lead.fub_person_id}")

        # Build webhook data from lead
        webhook_data = {
            'person': {
                'id': lead.fub_person_id,
                'firstName': lead.first_name,
                'lastName': lead.last_name,
                'emails': [{'value': lead.email, 'isPrimary': True}] if lead.email else [],
                'phones': [{'value': lead.phone, 'isPrimary': True}] if lead.phone else [],
                'tags': lead.tags or []
            }
        }

        # Try to auto-enhance
        enhancement_result = auto_enhancement_handler.process_new_person_webhook(
            webhook_data=webhook_data,
            user_id=user_id or lead.user_id
        )

        if enhancement_result.get('auto_enhanced'):
            print(f"✅ Auto-enhanced lead {lead.fub_person_id}")
        else:
            print(f"Auto-enhancement skipped: {enhancement_result.get('message', 'Unknown')}")

    except Exception as e:
        print(f"Error in trigger_auto_enhancement_for_lead: {e}")
        log_error('trigger_auto_enhancement', str(e), {
            'lead_id': lead.id if lead else None
        })