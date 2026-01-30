import base64
from datetime import datetime
import uuid

import deprecation
import requests
from flask import Flask, request, Response
import aiohttp
import asyncio
import threading
import os

from app.database.lead_cache import LeadCacheSingleton, LeadCacheService
from app.database.note_cache import NoteCacheService, NoteCacheSingleton
from app.models.lead import Lead, LeadNote
from app.service.lead_service import LeadService, LeadServiceSingleton
from app.service.note_service import NoteService
from app.service.stage_mapper_service import StageMapperService
from app.service.lead_source_settings_service import LeadSourceSettingsService
from app.database.fub_api_client import FUBApiClient
from app.database.supabase_client import SupabaseClientSingleton
from app.utils.constants import Credentials
from app.utils.dependency_container import DependencyContainer
from app.utils.webhook_cache import WebhookCache
from typing import Dict, List, Optional, Any
import os

app = Flask(__name__)

# Initialize webhook cache for idempotency
# Uses 1-hour expiry to prevent duplicate processing of the same webhook
try:
    webhook_cache = WebhookCache(
        redis_host=os.getenv('REDIS_HOST', 'localhost'),
        redis_port=int(os.getenv('REDIS_PORT', 6379)),
        redis_password=os.getenv('REDIS_PASSWORD'),
        expiration_hours=1.0,  # 1 hour expiry for idempotency
    )
except Exception as e:
    print(f"Warning: Could not initialize webhook cache (Redis may not be available): {e}")
    webhook_cache = None

# API Key for an Admin user in the Follow Up Boss Account
CREDS = Credentials()

# Get the dependency container
container = DependencyContainer.get_instance()

# Services
lead_service: LeadService = container.get_service("lead_service")
note_service: NoteService = container.get_service("note_service")
stage_mapper_service: StageMapperService = container.get_service("stage_mapper_service")
lead_source_settings_service: LeadSourceSettingsService = container.get_service("lead_source_settings_service")
lead_cache: LeadCacheService = LeadCacheSingleton.get_instance()
note_cache: NoteCacheService = NoteCacheSingleton.get_instance()

# Database
supabase = SupabaseClientSingleton.get_instance()

# API Client
api_client = FUBApiClient()


######################## Async Helper Function ########################
# Helper function to run async tasks from sync code
def run_async_task(coroutine):
    loop = asyncio.new_event_loop()

    def run_in_thread(loop, coro):
        asyncio.set_event_loop(loop)
        loop.run_until_complete(coro)
        loop.close()

    thread = threading.Thread(target=run_in_thread, args=(loop, coroutine))
    thread.daemon = True
    thread.start()


######################## Session ########################
# Create a session for async HTTP requests
async def get_aiohttp_session(system_name: str, system_key: str):
    return aiohttp.ClientSession(
        headers={
            "Content-Type": "application/json",
            'X-System': system_name,
            'X-System-Key': system_key,
            'Authorization': f'Basic {base64.b64encode(f"{CREDS.FUB_API_KEY}:".encode()).decode()}',
        }
    )

def ensure_naive_datetime(dt):
    """Convert any datetime to naive (no timezone) format for consistent comparisons"""
    if dt is None:
        return None
    if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


######################## Stage Updated Webhook ########################
@app.route('/stage-webhook', methods=['POST'])
async def webhook_stage_updated_handler():
    try:
        # Raw data
        webhook_data = request.get_json()
        print('\n\n')
        # print(webhook_data)

        event = webhook_data.get('event').lower()
        resource_uri = webhook_data.get('uri')
        print(f"Received webhook event: {event}")
        # print(f"Resource URI: {resource_uri}")

        try:
            async with await get_aiohttp_session(CREDS.STAGE_SYSTEM_NAME, CREDS.STAGE_SYSTEM_KEY) as session:
                async with session.get(resource_uri) as response:
                    response.raise_for_status()
                    person_data = await response.json()

            # print(f"Stage Data: {stage_data}")
            person = person_data.get('people', [])

            if not person or len(person) == 0:
                return Response("No people found in webhook data", status=200)

            person_id = person[0].get('id')
            print(f"Person ID: {person_id}")
            if not person_id:
                return Response("No person ID found in webhook data", status=200)

            fresh_person_data = api_client.get_person(person_id)
            new_lead = Lead.from_fub(fresh_person_data)
            print(f"New Lead Status: {new_lead.status}")

            # Get the lead from cache or database
            existing_lead = lead_cache.sync_with_db_and_cache(person_id)
            # print(f"Existing Lead Status: {existing_lead.status}")

            if not existing_lead:
                print(
                    f'Lead selected is not registered in the system, please add it by assigning "ReferralLink" on the tags of the lead')
                return Response(
                    'Lead selected is not registered in the system, please add it by assigning "ReferralLink on the tags of the lead"',
                    status=200
                )

            if stage_has_meaningful_changes(existing_lead, new_lead):
                # Process stage change for lead
                run_async_task(process_stage_updated_webhook(existing_lead))

                updated_lead = lead_service.update(new_lead)

                # Then update cache to keep them in sync
                lead_cache.store_lead(updated_lead)

                print(f"Lead {person_id} updated with meaningful changes")

                # Return success response
                return Response("OK", status=200)

            else:
                print("No meaningful changes detected, skipping stage update...")
                return Response("Canceled", status=200)

        except Exception as e:
            return Response("Error processing webhook", status=500)

    except Exception as e:
        print(f"Error Processing webhook: {e}")
        return Response("Error Processing Webhook", status=500)


async def process_stage_updated_webhook(lead: Lead):
    event_type = "stage_update"

    try:
        person_id = lead.fub_person_id
        tags = lead.tags if hasattr(lead, 'tags') and lead.tags else []

        print(f"🔔 Processing stage for person {person_id}: {lead.first_name} {lead.last_name}")

        # First check if this lead exists in our database
        existing_lead = lead_cache.sync_with_db_and_cache(person_id)

        if not existing_lead:
            if 'ReferralLink' in tags:
                print(
                    'Lead not found in our database, but found in tags, please add it by assigning "ReferralLink" on the tags of the lead')
                return
            else:
                print('Lead not found in our database and not in tags, skipping')
                return

        else:
            # Use the existing lead from database

            # Extract stage information
            fub_stage_id = lead.stage_id
            fub_stage_name = lead.status

            if not fub_stage_id or not fub_stage_name:
                print(f"No stage information found for person ID: {person_id}")
                return

            print(f"Person {person_id} stage changed to: {fub_stage_name} (ID: {fub_stage_id})")

            # Get full stage details (options, for more metadata)
            try:
                stage_details = api_client.get_stage(fub_stage_id)
            except Exception as e:
                print(f"Error getting stage details: {e}")
                stage_details = None

            # Now handle stage mapping to external platforms
            platform_results = stage_mapper_service.handle_fub_stage_change(
                fub_person_id=person_id,
                fub_stage_id=fub_stage_id,
                fub_stage_name=fub_stage_name
            )

            app.logger.info(f"Platform update results: {platform_results}")

            # Create a log entry for this stage change
            log_entry = {
                'id': str(uuid.uuid4()),
                'lead_id': lead.id,
                'fub_person_id': person_id,
                'previous_stage': existing_lead.status,
                'new_stage': fub_stage_name,
                'timestamp': ensure_naive_datetime(datetime.now()).isoformat(),
            }

            # Insert log entry into Supabase
            supabase.table('stage_change_logs').insert(log_entry).execute()

    except Exception as e:
        print(f"Error processing stage webhook: {e}")
        # Log the error to Supabase
        try:
            error_log = {
                'id': str(uuid.uuid4()),
                'created_at': datetime.now(),
                'error_type': 'stage_webhook_processing',
                'timestamp': datetime.now().isoformat(),
                'error_message': str(e)
            }
            supabase.table('error_logs').insert(error_log).execute()
        except Exception as log_error:
            print(f"Error logging to Supabase: {log_error}")


######################## Note Created Webhook ########################
@app.route('/notes-created-webhook', methods=['POST'])
async def webhook_note_created_handler():
    try:
        webhook_data = request.get_json()
        resource_uri = webhook_data.get('uri')
        print('\n\n')
        print(f"Resource URI: {resource_uri}")
        print(f"Received note created webhook: {webhook_data}")

        try:
            async with await get_aiohttp_session(CREDS.NOTE_CREATED_SYSTEM_NAME, CREDS.NOTE_SYSTEM_KEY) as session:
                # Ensure resource_uri is a string before making the request
                if not isinstance(resource_uri, str):
                    resource_uri = str(resource_uri)
                
                async with session.get(resource_uri) as response:
                    response.raise_for_status()
                    note_data = await response.json()

            person_id = note_data.get('personId')
            print(f"Person ID: {person_id}")
            if not person_id:
                return Response("No person ID associated with this note", status=200)

            # Get fresh data from FUB API
            # fresh_person_data = api_client.get_person(person_id)
            # new_lead = Lead.from_fub(fresh_person_data)
            resource_id = webhook_data.get('resourceIds')[0]
            try:

                # Get note data
                fresh_note_data = api_client.get_note(resource_id)
                
                if 'id' in fresh_note_data:
                    print(f"Note ID type: {type(fresh_note_data['id'])}")
                
                # Create note from data
                new_note = LeadNote.from_fub(fresh_note_data)
                
            except Exception as e:
                print(f"Error creating note from FUB data: {str(e)}")
                print(f"Exception type: {type(e).__name__}")
                import traceback
                traceback.print_exc()
                new_note = None

            # Get the lead from cache or database
            existing_lead = lead_cache.sync_with_db_and_cache(person_id)
            existing_note = note_cache.sync_with_db_and_cache(resource_id)

            if not existing_lead:
                print(
                    f'Lead selected is not registered in the system, please add it by assigning "ReferralLink" on the tags of the lead')
                return Response(
                    'Lead selected is not registered in the system, please add it by assigning "ReferralLink" on the tags of the lead',
                    status=200
                )
            else:
                print("Lead is here!")

            if not existing_note:

                print(f"Note not found in system, creating a new one")
                # Process asynchronously to create a new note
                run_async_task(process_note_created_webhook(existing_lead, note_data))
                return Response("OK - Creating new note", status=200)

            if note_has_meaningful_changes2(existing_note, new_note):
                # Process asynchronously
                run_async_task(process_note_created_webhook(existing_lead, note_data))

                # Return success response
                return Response("OK", status=200)
            else:
                print("No meaningful changes detected, skipping note update")
                return Response("Cancelled", status=200)
        except Exception as e:
            print(f"Error processing webhook 1: {e}")
            return Response(f"Error processing webhook: {e}", status=500)

    except Exception as e:
        print(f"Error processing webhook 2: {e}")
        return Response("Error Processing Webhook", status=500)


async def process_note_created_webhook(lead:Lead, note_data: Dict[str, Any]):
    event_type = "notes_created"
    try:
        person_id = lead.fub_person_id
        tags = lead.tags if hasattr(lead, 'tags') and lead.tags else []

        print(f"🔔 Processing note creation for person {person_id}: {lead.first_name} {lead.last_name}")

        resource_id = note_data.get('resourceIds', [])
        if not resource_id:
            # Check if we have a direct resource_id in the note_data
            resource_id = note_data.get('id')
            if not resource_id:
                print("No resource ID found in webhook data")
                return
        else:
            resource_id = resource_id[0]

        print(f"Using resource ID: {resource_id}")

        # Get if ReferralLink tag is present
        if 'ReferralLink' not in tags:
            print(f"No ReferralLink tag present for lead {lead.id}, skipping note creation")
            return

        # Check if note already exists in our cache/database
        existing_note = note_cache.sync_with_db_and_cache(resource_id)

        if existing_note:
            print(f"Updating existing note ID: {existing_note.id}")

            # Update note with new data
            existing_note.body = note_data.get('body', existing_note.body)
            existing_note.updated_at = datetime.now()

            # Update agent information
            if note_data.get('updatedById'):
                existing_note.created_by_id = note_data.get('createdById')
                existing_note.updated_by_id = note_data.get('updatedById')
            if note_data.get('createdBy'):
                existing_note.created_by = note_data.get('createdBy')
                existing_note.updated_by = note_data.get('updatedBy')

            # Update subject
            if note_data.get('subject'):
                existing_note.subject = note_data.get('subject')

            # Update metadata
            if not existing_note.metadata:
                existing_note.metadata = {}

            existing_note.metadata = {
                'source': 'fub_webhook',
                'note_data': note_data,
                'updated_at': datetime.now().isoformat(),
                'last_update_source': 'fub_webhook_create'
            }

            # Update the note in database
            updated_note = note_service.update(existing_note)

            # Update the cache with the database
            note_cache.store_note(updated_note)

            print(f'Note updated successfully: {updated_note.id} for lead {lead.id}')

        else:
            print(f"Creating new note for lead ID: {lead.id}")

            # Create the note with proper lead association
            note = LeadNote()
            note.id = str(uuid.uuid4())
            note.lead_id = lead.id

            # Set the appropriate note_id field based on model
            if hasattr(note, 'note_id'):
                note.note_id = resource_id
            elif hasattr(note, 'note_id'):
                note.note_id = resource_id

            # Set content/body based on available field
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
                    note.created_at = ensure_naive_datetime(datetime.fromisoformat(created_str.replace('Z', '+00:00')))
                except (ValueError, TypeError):
                    note.created_at = ensure_naive_datetime(datetime.now())
            else:
                note.created_at = ensure_naive_datetime(datetime.now())

            note.updated_at = ensure_naive_datetime(datetime.now())

            # Set metadata
            note.metadata = {
                'source': 'fub_webhook',
                'note_data': note_data,
                'tags_at_creation': tags
            }

            # Save the note to the database
            saved_note = note_service.create(note)

            # Store the new note in cache
            note_cache.store_note(saved_note)

            print(f"Note created successfully with ID: {saved_note.id} for lead {lead.id}")

    except Exception as e:
        print(f"Async processing error: {e}")
        # Log the full error details
        print(f"Error details: {str(e)}")
        print(f"Webhook data: {note_data}")


######################## Note Updated Webhook ########################
@app.route('/notes-updated-webhook', methods=['POST'])
async def webhook_note_updated_handler():
    try:
        webhook_data = request.get_json()
        print('\n\n')
        print(f"Received note update webhook: {webhook_data}")

        resource_uri = webhook_data.get('uri')

        try:
            async with await get_aiohttp_session(CREDS.NOTE_CREATED_SYSTEM_NAME, CREDS.NOTE_SYSTEM_KEY) as session:
                if not isinstance(resource_uri, str):
                    resource_uri = str(resource_uri)

                async with session.get(resource_uri) as response:
                    response.raise_for_status()
                    note_data = await response.json()

            person_id = note_data.get('personId')
            print(f"Note data: {note_data}")
            if not person_id:
                return Response("No person ID associated with this note", status=200)

            # Get fresh data from FUB API
            fresh_person_data = api_client.get_person(person_id)
            new_lead = Lead.from_fub(fresh_person_data)

            # Get the lead from cache or database
            existing_lead = lead_cache.sync_with_db_and_cache(person_id)

            if not existing_lead:
                print(
                    f'Lead selected is not registered in the system, please add it by assigning "ReferralLink" on the tags of lead')
                return Response(
                    'Lead selected is not registered in the system, please add it by assigning "ReferralLink" on the tags of lead',
                    status=200
                )

            # Check for meaningful changes
            if lead_has_meaningful_changes(existing_lead, new_lead):
                # Process note update for lead
                run_async_task(process_note_updated_webhook2(existing_lead, note_data))

                # Update database first
                updated_lead = lead_service.update(new_lead)

                # Then update cache to keep them in sync
                lead_cache.store_lead(updated_lead)

                print(f"Lead {person_id} updated with meaningful changes")
                return Response("OK", status=200)
            else:
                print("No meaningful changes detected, processing note update only...")
                # Still process the note update even if lead hasn't changed
                run_async_task(process_note_updated_webhook2(existing_lead, note_data))
                return Response("OK", status=200)

        except Exception as e:
            print(f"Error processing webhook: {e}")
            return Response("Error Processing Webhook", status=500)

    except Exception as e:
        print(f"Error processing webhook: {e}")
        return Response("Error Processing Webhook", status=500)


async def process_note_updated_webhook2(lead: Lead, note_data: Dict[str, Any]):
    event_type = "notes_created"
    try:
        person_id = lead.fub_person_id
        tags = lead.tags if hasattr(lead, 'tags') and lead.tags else []

        print(f"🔔 Processing note creation for person {person_id}: {lead.first_name} {lead.last_name}")

        # Get the note ID from the note data
        resource_ids = note_data.get('resourceIds', [])
        if not resource_ids:
            resource_id = note_data.get('id')
            print("No resource ID found in webhook data")
            if not resource_id:
                print("No resource ID found in webhook data")
                return
        else:
            resource_id = resource_ids[0]

        print(f"Resource ID (from webhook): {resource_id}")

        # Get note cache service
        from app.database.note_cache import NoteCacheSingleton
        note_cache = NoteCacheSingleton.get_instance()

        # Check if note already exists in our cache/database
        existing_note = note_cache.sync_with_db_and_cache(resource_id)

        if existing_note:
            print(f"Updating existing note ID: {existing_note.id}")

            # Update note with new data
            existing_note.body = note_data.get('body', existing_note.body)
            existing_note.updated_at = datetime.now().isoformat()

            # Update agent information if available
            if note_data.get('updatedById'):
                existing_note.updated_by_id = note_data.get('updatedById')
            if note_data.get('personId'):
                existing_note.lead_id = lead.id

            # Update subject if available
            if note_data.get('subject'):
                existing_note.subject = note_data.get('user')

            # Update metadata
            if not existing_note.metadata:
                existing_note.metadata = {}

            existing_note.metadata = {
                'source': 'fub_webhook',
                'note_data': note_data,
                'updated_at': datetime.now().isoformat(),
                'last_update_source': 'fub_webhook'
            }

            # Update the note in database
            updated_note = note_service.update(existing_note)

            # Update the cache with the updated note
            note_cache.store_note(updated_note)

            print(f"Note updated successfully: {updated_note.id} for lead {lead.id}")

        else:
            # Check for ReferralLink tag before creating new note
            if 'ReferralLink' not in tags:
                print(f"No ReferralLink tag present for lead {lead.id}, skipping note creation")
                return

            print(f"Creating new note for lead ID: {lead.id}")

            # Create the note with proper lead association
            note = LeadNote()
            note.id = str(uuid.uuid4())  # Ensure valid UUID
            note.lead_id = lead.id  # Associate with lead
            note.note_id = resource_id

            # Set agent information if available
            note.created_by_id = note_data.get('createdById')
            note.updated_by = note_data.get('updatedById')
            note.created_by = note_data.get('createdBy')
            note.updated_by = note_data.get('updatedBy')

            # Set subject if available
            note.subject = note_data.get('subject')

            # Parse created date if available
            created_str = note_data.get('created')
            if created_str:
                try:
                    note.created_at = ensure_naive_datetime(datetime.fromisoformat(created_str.replace('Z', '+00:00')))
                except (ValueError, TypeError):
                    note.created_at = ensure_naive_datetime(datetime.now())
            else:
                note.created_at = ensure_naive_datetime(datetime.now())

            note.updated_at = ensure_naive_datetime(datetime.now())

            # Set metadata
            note.metadata = {
                'source': 'fub_webhook',
                'note_data': note_data,
                'created_during_update': True,
                'tags_at_creation': tags
            }

            # Save the note to the database
            saved_note = note_service.create(note)

            # Store the new note in cache
            note_cache.store_note(saved_note)

            print(f"Note saved successfully with ID: {saved_note.id} for lead {lead.id}")

    except Exception as e:
        print(f"Error processing note webhook: {e}")
        # Log the error to Supabase
        try:
            error_log = {
                'id': str(uuid.uuid4()),
                'created_at': datetime.now().isoformat(),
                'error_type': 'note_webhook_processing',
                'timestamp': ensure_naive_datetime(datetime.now()).isoformat(),
                'error_message': str(e),
                'lead_id': lead.id if lead else None,
                'tags': tags
            }
            supabase.table('error_logs').insert(error_log).execute()
        except Exception as log_error:
            print(f"Error logging to Supabase: {log_error}")


######################## Tag Webhook ########################
@app.route('/tag-webhook', methods=['POST'])
async def webhook_tag_handler():
    global person
    event_type = "tag_updated"
    try:
        # Get the raw webhook data
        webhook_data = request.get_json()

        print('\n\n')

        # Extract event and URI
        event = webhook_data.get('event')
        resource_uri = webhook_data.get('uri')

        # Generate a unique webhook ID for idempotency
        # Use event + URI hash as unique identifier
        webhook_id = f"{event}:{resource_uri}" if event and resource_uri else None

        event = event.lower()
        person_id = None
        if event and (event == "peopletagscreated" or event == 'peopletagsupdated'):
            try:
                async with await get_aiohttp_session(CREDS.TAG_SYSTEM_NAME, CREDS.TAG_SYSTEM_KEY) as session:
                    async with session.get(resource_uri) as response:
                        response.raise_for_status()
                        person_data = await response.json()

                person = person_data.get('people', [])
                print(f"Person: {person}")

                if not person or len(person) == 0:
                    # print("No people found in webhook data")
                    return Response("No people found in webhook data", status=200)

                person_id = person[0].get('id')
                print(f"Person ID: {person_id}")
                if not person_id:
                    return Response("No person ID found in webhook data", status=200)

                # ===== IDEMPOTENCY CHECK =====
                # Prevent duplicate processing if webhook fires multiple times
                if webhook_cache and person_id:
                    is_new = webhook_cache.check_and_mark(
                        lead_id=str(person_id),
                        event_type=f"tag_{event}"
                    )
                    if not is_new:
                        print(f"⚠️ Duplicate webhook detected for person {person_id}, skipping...")
                        return Response("Duplicate webhook - already processed", status=200)
                # ===========================

                # Get fresh data from FUB API
                fresh_person_data = api_client.get_person(person_id)
                new_lead = Lead.from_fub(fresh_person_data)

                # new_lead.display_data()
                # Get the lead from cache or database
                existing_lead = lead_cache.sync_with_db_and_cache(person_id)

                if not existing_lead:
                    print(f"New lead detected with Person ID: {person_id}")

                    lead = Lead.from_fub(person[0])

                    # Early validation of lead source
                    if not lead_service.check_source(lead):
                        print("Lead is not associated with any lead source from DB")
                        return Response(
                            'Lead source not configured in system',
                            status=200  # Using 200 to acknowledge receipt but indicate filtered
                        )

                    # Log incoming webhook
                    print(f"Received webhook event: {event} at {datetime.now()}")

                    # Process asynchronously
                    run_async_task(process_tag_webhook2(lead, lead_service))

                    # Return success response
                    return Response("OK", status=200)

                print(f"There are changes for existing lead: {existing_lead.fub_person_id}")
                # Only process if there are meaningful changes
                if lead_has_meaningful_changes(existing_lead, new_lead):
                    # Update database first
                    updated_lead = lead_service.update(new_lead)

                    # Then update cache to keep them in sync
                    lead_cache.store_lead(updated_lead)

                    print(f"Lead {person_id} updated with meaningful changes")
                    # Return success response
                    return Response("OK", status=200)
                else:
                    print(f"No meaningful changes for lead {person_id}")
                    # Return success response
                    return Response("OK", status=200)
            except Exception as e:
                return Response("Error processing webhook", status=500)

    except Exception as e:
        print(f"Error processing webhook: {e}")
        return Response("Error processing webhook", status=500)


async def process_tag_webhook2(lead: Lead, lead_service: LeadService):
    global external_status

    try:
        person_id = lead.fub_person_id
        tags = lead.tags if hasattr(lead, 'tags') and lead.tags else []

        print(f"🔔 Processing tags for person {person_id}: {tags}")

        # First check if this lead exists in our database
        existing_lead = lead_service.get_by_fub_person_id(person_id)

        if not existing_lead:
            if 'ReferralLink' in tags:
                # Create the lead in our database
                saved_lead = lead_service.create(lead)
                if saved_lead and hasattr(saved_lead, 'id') and saved_lead.id:
                    print(f"Created new lead with ID: {saved_lead.id} from ReferralLink tag")
                    mapping = stage_mapper_service.add_stage_mapping(saved_lead.fub_person_id, saved_lead.source)
                    if mapping and hasattr(mapping, 'id'):
                        print(f"Created new Mapping with ID: {mapping.id}")
                        lead = saved_lead

                        # ==========================================================
                        # NEW: INSTANT AI RESPONSE - Speed-to-Lead (< 1 minute)
                        # Research: MIT study - 21x higher conversion within 5 min
                        # ==========================================================
                        try:
                            from app.scheduler.ai_tasks import trigger_instant_ai_response
                            print(f"🚀 Triggering INSTANT AI response for new lead {person_id}")

                            # Queue the instant response task (runs immediately)
                            trigger_instant_ai_response.delay(
                                fub_person_id=person_id,
                                source=lead.source,
                                organization_id=None,  # Will be determined from settings
                                user_id=None,
                            )
                            print(f"✅ Instant AI response queued for person {person_id}")

                        except Exception as ai_error:
                            # Don't fail the webhook if AI trigger fails
                            print(f"⚠️ AI trigger error (non-fatal): {ai_error}")
                        # ==========================================================

                    else:
                        lead_service.delete(saved_lead.id)
                        print("Failed to create mapping, deleting lead data from DB...")
                        return
                else:
                    print("Failed to create lead")
            else:
                print(f"No ReferralLink tag present and no existing lead - skipping lead creation")
                return
        else:
            # Use the existing lead from database
            lead = existing_lead

            # If we need to update the lead with latest data from FUB
            data = api_client.get_person(person_id)
            new_lead = Lead.from_fub(data)

            # Preserve important fields from existing lead
            new_lead.id = lead.id
            new_lead.created_at = lead.created_at

            # Store tags in the database separately
            try:
                # Update the lead if needed
                if (new_lead.source != lead.source or
                        new_lead.status != lead.status or
                        new_lead.email != lead.email or
                        new_lead.phone != lead.phone or
                        new_lead.tags != lead.tags):
                    lead = lead_service.update(new_lead)
                    print(f"Lead updated with new data")

                # Now update tags for this lead using a separate service/table
                if hasattr(lead_service, 'update_tags'):
                    lead_service.update_tags(lead.id, tags)
                    print(f"Tags updated for lead ID: {lead.id}, tags: {tags}")
                else:
                    # Fallback - log that we need a way to store tags
                    print(f"WARNING: No method to store tags. Lead ID: {lead.id}")
            except Exception as update_error:
                print(f"Error updating lead or tags: {update_error}")

        # Get the external status mapping
        external_status = lead_service.get_fub_stage_mapping(lead)

        print(f"FUB Status: {lead.status}")
        print(f"External Status: {external_status}")

    except Exception as e:
        print(f"Async processing error: {e}")

        # Log error to database
        try:
            supabase = SupabaseClientSingleton.get_instance()
            error_log = {
                'id': str(uuid.uuid4()),
                'created_at': datetime.now().isoformat(),
                'error_type': 'tag_webhook_processing',
                'webhook_data': {'lead_id': lead.id if lead else None},
                'timestamp': datetime.now().isoformat(),
                'error_message': str(e)
            }

            supabase.table('error_logs').insert(error_log).execute()
        except Exception as log_error:
            print(f"Error logging to Supabase: {log_error}")


async def handle_referral_tag(person: dict):
    """
    Handle what happens when a ReferralLink tag is detected.
    Customize this function based on your needs.
    """
    # Example: Log the detection with more details
    # people = person_data.get('people', [])

    # Return empty list if no people found
    if not person:
        return []

    first_person = person[0]
    ### Try converting the JSON response into model
    try:
        person_model = lead_service.create_from_fub(first_person)
        # person_model.display_data()

    except Exception as e:
        print("There is an error in converting into Lead Model: ", e)

    # Add your custom logic here
    # For example:
    # - Send an email notification
    # - Update a database
    # - Trigger an automation
    # - Send a Slack notification
    # - etc.


def extract_tags(response):
    # Access the first person in the people list
    people = response.get('people', [])

    # Return empty list if no people found
    if not people:
        return []

    # Get the tags from the first person
    first_person = people[0]
    tags = first_person.get('tags', [])

    return tags


######################## Tag Updated Webhook ########################

@app.route('/tag-updated', methods=['POST'])
async def webhook_tag_updated_handler():
    try:
        # Get the raw webhook data
        webhook_data = request.get_json()
        print("\n\n")

        # Extract event and URI
        event = webhook_data.get('event')
        resource_uri = webhook_data.get('uri')

        # Log incoming webhook
        print(f"Received webhook event: {event} at {datetime.now()}")

        # Process asynchronously
        run_async_task(process_tag_update_webhook(event, resource_uri))

        # Return success response
        return Response("OK", status=200)

    except Exception as e:
        print(f"Error processing webhook: {e}")
        return Response("Error processing webhook", status=500)


async def process_tag_update_webhook(event, resource_uri):
    try:
        event = event.lower()
        # Handle tag update event
        if event and (event == 'peopleupdated'):
            try:
                async with await get_aiohttp_session(CREDS.TAG_SYSTEM_NAME, CREDS.TAG_SYSTEM_KEY) as session:
                    async with session.get(resource_uri) as response:
                        response.raise_for_status()
                        person_data = await response.json()

                person = person_data.get('people', [])
                if not person or len(person) == 0:
                    print("No people found in webhook data")
                    return

                person_id = person[0].get('id')
                if not person_id:
                    print("No person ID found in webhook data")
                    return

                old_lead = lead_service.get_by_fub_person_id(person_id)
                new_lead = Lead.from_fub(person)

                # Compare the old and new lead
                if old_lead.tags != new_lead.tags:
                    print(f"New tags found for lead: {old_lead.first_name} {old_lead.last_name}")
                    old_lead.tags = new_lead.tags
                    lead_service.update(old_lead)

            except Exception as e:
                pass

    except Exception as e:
        pass


######################## Helper Functions ########################
# Convert both to strings and strip whitespace before comparing
def normalize_value(value):
    if value is None:
        return ""
    return str(value).strip()


# Check for tag changes (either added or removed)
def normalize_tags(tags_value):
    if tags_value is None:
        return set()
    if isinstance(tags_value, str):
        # Try to parse as JSON if it looks like a JSON array
        if tags_value.strip().startswith('[') and tags_value.strip().endswith(']'):
            try:
                import json
                return set(json.loads(tags_value))
            except json.JSONDecodeError:
                # If JSON parsing fails, split by commas as fallback
                return set(tag.strip() for tag in tags_value.strip('[]').split(','))
        # Single tag as string
        return {tags_value}
    # Already a list or other iterable
    return set(tags_value)


def lead_has_meaningful_changes(existing_lead: Lead, new_lead: Lead) -> bool:
    """
    Determining if there are meaningful changes between existing lead and new lead
    :param existing_lead: The lead from your database
    :param new_lead: The new lead from FUB webhook/API
    :return: True if meaningful changes exist, False otherwise
    """
    # Always process if no existing lead (new lead)
    if not existing_lead:
        return True

    new_lead.id = existing_lead.id

    # Critical changes - always process
    if existing_lead.status != new_lead.status:
        print(f"Status change detected: {existing_lead.status} -> {new_lead.status}")
        return True

    if normalize_value(existing_lead.stage_id) != normalize_value(new_lead.stage_id):
        print(f"Stage ID change detected: '{existing_lead.stage_id}' -> '{new_lead.stage_id}'")
        print(f"Types: {type(existing_lead.stage_id)} -> {type(new_lead.stage_id)}")
        return True

    # Check for tag changes (either added or removed)
    existing_tags = normalize_tags(existing_lead.tags)
    new_tags = normalize_tags(new_lead.tags)

    if existing_tags != new_tags:
        added_tags = new_tags - existing_tags
        removed_tags = existing_tags - new_tags
        print(f"Tag changes detected - Added: {added_tags}. Removed: {removed_tags}")
        return True

    # Phone changes (any change, including setting to None)
    if existing_lead.phone != new_lead.phone:
        print(f"Phone change detected: {existing_lead.phone} -> {new_lead.phone}")
        return True

    # Name changes (any change, including setting to None)
    if existing_lead.first_name != new_lead.first_name or existing_lead.last_name != new_lead.last_name:
        print(
            f"Name change detected: {existing_lead.first_name} {existing_lead.last_name} -> {new_lead.first_name} {new_lead.last_name}")
        return True

    # Source change
    if existing_lead.source != new_lead.source:
        print(f"Source change detected: {existing_lead.source} -> {new_lead.source}")
        return True

    # If we got here, there are no meaningful changes to process
    print(f"No meaningful changes detected for lead {existing_lead.id}")
    return False


def stage_has_meaningful_changes(existing_lead: Lead, new_lead: Lead) -> bool:
    # Always process if no existing lead(new Lead)
    if not existing_lead:
        return False

    # Only check for stage name changes (status in the model)
    if existing_lead.status != new_lead.status:
        print(f"Stage name change detected: {existing_lead.status} -> {new_lead.status}")
        return True

    # No meaningful changes
    print(f"No meaningful stage changes detected for lead: {existing_lead.id}")
    return False


def note_has_meaningful_changes(existing_note: LeadNote, note_data: Dict[str, Any]) -> bool:
    # Always process if no existing note (new note)
    if not existing_note:
        print("New note - will create")
        return True

    # Check body content changes
    new_body = note_data.get('body', '')
    if existing_note.body != new_body:
        existing_preview = (existing_note.body[:30] + '...') if existing_note.body and len(
            existing_note.body) > 30 else existing_note.body
        new_preview = (new_body[:30] + '...') if new_body and len(new_body) > 30 else new_body
        print(f"Note body changed: {existing_preview} -> {new_preview}")
        return True

    # Check subject changes
    new_subject = note_data.get('subject', '')
    if existing_note.subject != new_subject and new_subject:
        print(f"Note subject changed: {existing_note.subject} -> {new_subject}")
        return True

    # Check user changes (who updated it)
    new_user = note_data.get('updatedBy', '')
    if existing_note.updated_by != new_user and new_user:
        print(f"Note updated by different user: {existing_note.updated_by} -> {new_user}")

    # Check if updated by ID changed
    new_updated_by_id = note_data.get('updatedById', '')
    if existing_note.updated_by_id != new_updated_by_id and new_updated_by_id:
        print(f"Note updated by id changed: {existing_note.updated_by_id} -> {new_updated_by_id}")
        return True

    # No meaningful changes
    print(f"No meaningful changes detected for note {existing_note.id}")
    return False


def note_has_meaningful_changes2(existing_note: LeadNote, new_note: LeadNote) -> bool:
    # Always process if no existing note (new note)
    if not existing_note:
        print("New note - will create")
        return True

    # Preserve ID for comparison
    if hasattr(new_note, 'id') and hasattr(existing_note, 'id'):
        new_note.id = existing_note.id

    # Check body content changes
    if existing_note.body != new_note.body:
        existing_preview = (existing_note.body[:30] + '...') if existing_note.body and len(
            existing_note.body) > 30 else existing_note.body
        new_preview = (new_note.body[:30] + '...') if new_note.body and len(new_note.body) > 30 else new_note.body
        print(f"Note body changed: {existing_preview} -> {new_preview}")
        return True

    # Check subject changes
    if hasattr(existing_note, 'subject') and hasattr(new_note, 'subject'):
        if existing_note.subject != new_note.subject and new_note.subject:
            print(f"Note subject changed: {existing_note.subject} -> {new_note.subject}")
            return True

    # Check user changes (who updated it)
    if hasattr(existing_note, 'updated_by') and hasattr(new_note, 'updated_by'):
        if existing_note.updated_by != new_note.updated_by and new_note.updated_by:
            print(f"Note updated by different user: {existing_note.updated_by} -> {new_note.updated_by}")
            return True

    # Check if updated by ID changed
    if hasattr(existing_note, 'updated_by_id') and hasattr(new_note, 'updated_by_id'):
        if existing_note.updated_by_id != new_note.updated_by_id and new_note.updated_by_id:
            print(f"Note updated by id changed: {existing_note.updated_by_id} -> {new_note.updated_by_id}")
            return True

    # No meaningful changes
    print(f"No meaningful changes detected for note {existing_note.id}")
    return False
