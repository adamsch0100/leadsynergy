from datetime import datetime
import uuid
from typing import Dict

from flask import Flask, request, Response
from rq import Queue
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

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
from app.webhook.webhook_processors import (
    process_stage_updated_webhook,
    process_note_webhook,
    process_tag_webhook,
    process_person_created_webhook,
    normalize_value,
    normalize_tags,
    log_error,
    add_to_friday_schedule,
)
from app.webhook.tenant_resolver import TenantResolver
from app.scheduler.scheduler_main import TaskSchedulerSingleton
from app.service.celery_service import CeleryServiceSingleton
from app.scheduler.tasks import process_webhook_task

app = Flask(__name__)

# API Key for an Admin user in the Follow Up Boss Account
CREDS = Credentials()

# Get the dependency container
container = DependencyContainer.get_instance()

# Services
lead_service = LeadServiceSingleton.get_instance()
note_service = NoteServiceSingleton.get_instance()
stage_mapper_service: StageMapperService = container.get_service("stage_mapper_service")
lead_source_settings_service = LeadSourceSettingsSingleton.get_instance()
lead_cache = LeadCacheSingleton.get_instance()
note_cache = NoteCacheSingleton.get_instance()

# Database
supabase = SupabaseClientSingleton.get_instance()

# API Client
api_client = FUBApiClient()

# Scheduler Handler
celery_service = CeleryServiceSingleton.get_instance()

# Tenant Resolver
tenant_resolver = TenantResolver()


######################## Helper Functions ########################
def get_fub_client_for_webhook(webhook_data: Dict, webhook_type: str) -> FUBApiClient:
    """Get appropriate FUB API client for webhook processing"""
    # Try to resolve tenant from webhook data
    tenant_info = tenant_resolver.resolve_tenant_from_webhook(webhook_data, webhook_type)
    
    if tenant_info and tenant_info.get('api_key'):
        print(f"Using tenant-specific API key for {webhook_type} webhook")
        return FUBApiClient(tenant_info['api_key'])
    else:
        print(f"Using fallback API key for {webhook_type} webhook")
        # Fallback to environment API key
        return api_client





######################## Change Detection Functions ########################
def lead_has_meaningful_changes(existing_lead: Lead, new_lead: Lead) -> bool:
    """
    Determines whether there are meaningful changes between an existing lead and a new lead.
    A meaningful change triggers certain processes or updates, such as changes in
    status, stage, tags, phone number, name, or source.

    :param existing_lead: The existing `Lead` object to compare.
    :param new_lead: The new `Lead` object to compare against the existing lead.
    :return: A boolean indicating whether meaningful changes exist between the
        existing and new leads.
    :rtype: bool
    """
    if not existing_lead:
        return True

    new_lead.id = existing_lead.id

    # Critical changes - always process
    if existing_lead.status != new_lead.status:
        print(f"Status change detected: {existing_lead.status} -> {new_lead.status}")
        return True

    if normalize_value(existing_lead.stage_id) != normalize_value(new_lead.stage_id):
        print(
            f"Stage ID change detected: {existing_lead.stage_id} -> {new_lead.stage_id}"
        )
        return True

    # Check for tag changes (either added or removed_
    existing_tags = normalize_tags(existing_lead.tags)
    new_tags = normalize_tags(new_lead.tags)

    print(
        f"Comparing tags - Existing: {existing_tags} (type: {type(existing_lead.tags)})"
    )
    print(f"Comparing tags - New: {new_tags} (type: {type(new_lead.tags)})")

    if existing_tags != new_tags:
        added_tags = new_tags - existing_tags
        removed_tags = existing_tags - new_tags
        print(f"Tag changes detected - Added: {added_tags}. Removed: {removed_tags}")
        return True

    # Phone changes
    if existing_lead.phone != new_lead.phone:
        print(f"Phone change detected: {existing_lead.phone} -> {new_lead.phone}")
        return True

    # Name changes
    if (
        existing_lead.first_name != new_lead.first_name
        or existing_lead.last_name != new_lead.last_name
    ):
        print(
            f"Name change detected: {existing_lead.first_name} {existing_lead.last_name} -> {new_lead.first_name} {existing_lead.last_name}"
        )
        return True

    # Source change
    if existing_lead.source != new_lead.source:
        print(f"Source change detected: {existing_lead.source} -> {new_lead.source}")
        return True

    # No meaningful changes
    print(f"No meaningful changes detected for lead {existing_lead.id}")
    return False


def note_has_meaningful_changes(existing_note: LeadNote, new_note: LeadNote) -> bool:
    """
    Determines whether a new note has meaningful changes compared to an existing note.
    A note is considered to have meaningful changes if there is a change in the body,
    subject, or the user who updated the note. Additionally, a new note without an
    existing counterpart is always considered to have changes.

    :param existing_note: The existing LeadNote object for comparison.
    :param new_note: The new LeadNote object to compare against the existing one.
    :return: Boolean indicating whether meaningful changes are detected in the new note.
    :rtype: bool
    """
    # Always process if no existing note (new note)
    if not existing_note:
        print("New note - will create")
        return True

    # Preserve ID for comparison
    if hasattr(new_note, "id") and hasattr(existing_note, "id"):
        new_note.id = existing_note.id

    # Check body content changes
    if existing_note.body != new_note.body:
        existing_preview = (
            (existing_note.body[:30] + "...")
            if existing_note.body and len(existing_note.body) > 30
            else existing_note.body
        )
        new_preview = (
            (new_note.body[:30] + "...")
            if new_note.body and len(new_note.body) > 30
            else new_note.body
        )
        print(f"Note body changed: {existing_preview} -> {new_preview}")
        return True

    # Check subject changes
    if hasattr(existing_note, "subject") and hasattr(new_note, "subject"):
        if existing_note.subject != new_note.subject and new_note.subject:
            print(
                f"Note subject changed: {existing_note.subject} -> {new_note.subject}"
            )
            return True

    # Check user changes (who updated it)
    if hasattr(existing_note, "updated_by") and hasattr(new_note, "updated_by"):
        if existing_note.updated_by != new_note.updated_by and new_note.updated_by:
            print(
                f"Note updated by different user: {existing_note.updated_by} -> {new_note.updated_by}"
            )
            return True

    # Check if updated by ID changed
    if hasattr(existing_note, "updated_by_id") and hasattr(new_note, "updated_by_id"):
        if (
            existing_note.updated_by_id != new_note.updated_by_id
            and new_note.updated_by_id
        ):
            print(
                f"Note updated by id changed: {existing_note.updated_by_id} -> {new_note.updated_by_id}"
            )
            return True

    # No meaningful changes
    print(f"No meaningful changes detected for note {existing_note.id}")
    return False


######################## Webhook Handlers ########################
@app.route("/stage-webhook", methods=["POST"])
def webhook_stage_updated_handler():
    """Queue stage webhook for processing"""
    webhook_data = request.get_json()
    
    webhook_message = {
        'webhook_type': 'stage-webhook',
        'payload': webhook_data,
        'correlation_id': str(uuid.uuid4()),
        'received_at': datetime.utcnow().isoformat()
    }
    
    # Check if should process immediately or batch
    if should_process_immediately(webhook_data):
        process_webhook_task.delay(webhook_message)
    else:
        queue_for_batch_processing(webhook_message)
    
    return Response("Accepted", status=202)


@app.route("/notes-created-webhook", methods=["POST"])
def webhook_note_created_handler():
    """Queue note created webhook for processing"""
    webhook_data = request.get_json()
    
    webhook_message = {
        'webhook_type': 'notes-created-webhook',
        'payload': webhook_data,
        'correlation_id': str(uuid.uuid4()),
        'received_at': datetime.utcnow().isoformat()
    }
    
    # Check if should process immediately or batch
    if should_process_immediately(webhook_data):
        process_webhook_task.delay(webhook_message)
    else:
        queue_for_batch_processing(webhook_message)
    
    return Response("Accepted", status=202)


@app.route("/notes-updated-webhook", methods=["POST"])
def webhook_note_updated_handler():
    """Queue note updated webhook for processing"""
    webhook_data = request.get_json()
    
    webhook_message = {
        'webhook_type': 'notes-updated-webhook',
        'payload': webhook_data,
        'correlation_id': str(uuid.uuid4()),
        'received_at': datetime.utcnow().isoformat()
    }
    
    # Check if should process immediately or batch
    if should_process_immediately(webhook_data):
        process_webhook_task.delay(webhook_message)
    else:
        queue_for_batch_processing(webhook_message)
    
    return Response("Accepted", status=202)


@app.route("/tag-webhook", methods=["POST"])
def webhook_tag_handler():
    """Queue tag webhook for processing"""
    webhook_data = request.get_json()
    
    webhook_message = {
        'webhook_type': 'tag-webhook',
        'payload': webhook_data,
        'correlation_id': str(uuid.uuid4()),
        'received_at': datetime.utcnow().isoformat()
    }
    
    # Check if should process immediately or batch
    if should_process_immediately(webhook_data):
        process_webhook_task.delay(webhook_message)
    else:
        queue_for_batch_processing(webhook_message)
    
    return Response("Accepted", status=202)


@app.route("/tag-updated", methods=["POST"])
def webhook_tag_updated_handler():
    """Queue tag updated webhook for processing"""
    webhook_data = request.get_json()

    webhook_message = {
        'webhook_type': 'tag-updated',
        'payload': webhook_data,
        'correlation_id': str(uuid.uuid4()),
        'received_at': datetime.utcnow().isoformat()
    }

    # Check if should process immediately or batch
    if should_process_immediately(webhook_data):
        process_webhook_task.delay(webhook_message)
    else:
        queue_for_batch_processing(webhook_message)

    return Response("Accepted", status=202)


@app.route("/person-created-webhook", methods=["POST"])
def webhook_person_created_handler():
    """Queue person created webhook for processing (triggers auto-enhancement)"""
    webhook_data = request.get_json()

    webhook_message = {
        'webhook_type': 'person-created-webhook',
        'payload': webhook_data,
        'correlation_id': str(uuid.uuid4()),
        'received_at': datetime.utcnow().isoformat()
    }

    # Always process person created immediately for auto-enhancement
    process_webhook_task.delay(webhook_message)

    return Response("Accepted", status=202)


@app.route("/person-updated-webhook", methods=["POST"])
def webhook_person_updated_handler():
    """Queue person updated webhook for processing"""
    webhook_data = request.get_json()

    webhook_message = {
        'webhook_type': 'person-updated-webhook',
        'payload': webhook_data,
        'correlation_id': str(uuid.uuid4()),
        'received_at': datetime.utcnow().isoformat()
    }

    # Check if should process immediately or batch
    if should_process_immediately(webhook_data):
        process_webhook_task.delay(webhook_message)
    else:
        queue_for_batch_processing(webhook_message)

    return Response("Accepted", status=202)


######################## Application Lifecycle ########################
@app.before_request
def setup_app():
    print("Initializing webhook server resources...")


@app.teardown_appcontext
def shutdown_app(exception=None):
    # Cleanup resources if needed
    pass


def should_process_immediately(webhook_data):
    """Check user preferences for immediate vs batch processing"""
    # Extract tenant hint and check their preferences
    # For now, default to immediate processing
    return True

def queue_for_batch_processing(webhook_message):
    """Store webhook for later batch processing"""
    from app.database.supabase_client import SupabaseClientSingleton
    supabase = SupabaseClientSingleton.get_instance()
    
    supabase.table('webhook_batch_queue').insert({
        'webhook_type': webhook_message['webhook_type'],
        'payload': webhook_message['payload'],
        'correlation_id': webhook_message['correlation_id'],
        'status': 'pending',
        'created_at': webhook_message['received_at']
    }).execute()


if __name__ == "__main__":
    app.run(debug=False, port=5000)
