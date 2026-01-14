import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any

from celery import shared_task

from app.database.fub_api_client import FUBApiClient
from app.database.lead_cache import LeadCacheSingleton
from app.database.note_cache import NoteCacheSingleton
from app.models.lead import Lead
from app.scheduler.celery_app import celery
from app.service.lead_service import LeadServiceSingleton
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
from app.service.redis_service import RedisServiceSingleton
from app.webhook.tenant_resolver import TenantResolver
from app.webhook.webhook_processors import (
    process_stage_updated_webhook,
    process_note_webhook,
    process_tag_webhook,
    process_person_created_webhook,
)

redis_service = RedisServiceSingleton.get_instance()
lead_cache = LeadCacheSingleton.get_instance()
note_cache = NoteCacheSingleton.get_instance()
api_client = FUBApiClient()
logger = logging.getLogger(__name__)


@celery.task
def process_scheduled_lead_sync() -> Dict[str, Any]:
    """Celery task that processes scheduled lead source synchronizations."""

    settings_service = LeadSourceSettingsSingleton.get_instance()
    lead_service = LeadServiceSingleton.get_instance()

    due_sources = settings_service.get_sources_due_for_sync()

    if not due_sources:
        logger.info("Scheduled sync: no lead sources due for synchronization.")
        return {"processed_sources": 0, "details": []}

    logger.info("Scheduled sync: processing %d lead sources.", len(due_sources))

    summary = []
    page_size = 100

    for source_settings in due_sources:
        source_name = source_settings.source_name
        logger.info("Scheduled sync: syncing source '%s'.", source_name)

        processed = 0
        failed = 0
        offset = 0

        while True:
            leads = lead_service.get_by_source(source_name, limit=page_size, offset=offset)

            if not leads:
                break

            for lead in leads:
                if not getattr(lead, "fub_person_id", None) or not getattr(lead, "status", None):
                    continue

                try:
                    result = _sync_lead_to_source(settings_service, lead_service, lead, source_settings)
                    if result.get("success"):
                        processed += 1
                    else:
                        failed += 1
                        logger.warning(
                            "Scheduled sync: source '%s' lead '%s' failed: %s",
                            source_name,
                            lead.fub_person_id,
                            result.get("message") or result.get("error"),
                        )
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    logger.error(
                        "Scheduled sync: error syncing lead '%s' for source '%s': %s",
                        lead.fub_person_id,
                        source_name,
                        str(exc),
                    )

            if len(leads) < page_size:
                break

            offset += page_size

        settings_service.mark_sync_completed(
            source_settings.id, source_settings.sync_interval_days
        )

        summary.append({
            "source": source_name,
            "processed": processed,
            "failed": failed,
        })

    return {"processed_sources": len(summary), "details": summary}


def _sync_lead_to_source(settings_service, lead_service, lead, source_settings) -> Dict[str, Any]:
    """Sync a single lead to a specific external source."""

    platform = source_settings.source_name
    mapped_stage = source_settings.get_mapped_stage(lead.status)

    if not mapped_stage:
        return {
            "success": False,
            "message": f"No stage mapping configured for status '{lead.status}'",
        }

    try:
        from app.referral_scrapers.referral_service_factory import (  # noqa: WPS433
            ReferralServiceFactory,
        )

        normalized_platform = platform.lower()
        organization_id = getattr(lead, "organization_id", None)
        if not organization_id and getattr(lead, "metadata", None):
            organization_id = lead.metadata.get("organization_id")

        lead.metadata = getattr(lead, "metadata", {}) or {}
        lead.metadata[f"{platform.lower()}_status"] = mapped_stage
        lead_service.update(lead)

        if normalized_platform == "referralexchange":
            if isinstance(mapped_stage, str):
                if "::" in mapped_stage:
                    main, sub = [part.strip() for part in mapped_stage.split("::", 1)]
                    status_for_service = [main, sub]
                else:
                    status_for_service = [mapped_stage, ""]
            elif isinstance(mapped_stage, (list, tuple)) and len(mapped_stage) >= 2:
                status_for_service = [mapped_stage[0], mapped_stage[1]]
            else:
                status_for_service = [str(mapped_stage), ""]
            from app.referral_scrapers.referral_exchange.referral_exchange_service import (  # noqa: WPS433
                ReferralExchangeService,
            )

            service = ReferralExchangeService(
                lead=lead,
                status=status_for_service,
                organization_id=organization_id,
            )
        elif normalized_platform == "redfin":
            from app.referral_scrapers.redfin.redfin_service import (  # noqa: WPS433
                RedfinService,
            )

            service = RedfinService(
                lead=lead,
                status=mapped_stage,
                organization_id=organization_id,
            )
        elif normalized_platform == "homelight":
            from app.referral_scrapers.homelight.homelight_service import (  # noqa: WPS433
                HomelightService,
            )

            service = HomelightService(
                lead=lead,
                status=mapped_stage,
                organization_id=organization_id,
            )
        else:
            if not ReferralServiceFactory.service_exists(platform):
                return {
                    "success": False,
                    "message": f"Service implementation not available for {platform}",
                }
            service = ReferralServiceFactory.get_service(platform, lead=lead)
            if not service:
                return {
                    "success": False,
                    "message": f"Failed to initialize service for platform {platform}",
                }

        if normalized_platform == "redfin":
            success = service.redfin_run()
        elif normalized_platform == "homelight":
            success = service.homelight_run()
        elif normalized_platform == "referralexchange":
            success = service.referral_exchange_run()
        else:
            try:
                success = service.run()
            except AttributeError:
                run_method = getattr(service, f"{platform.lower().replace(' ', '_')}_run", None)
                success = run_method() if run_method else False

        if success:
            now = datetime.utcnow()
            lead.metadata[f"{platform.lower()}_last_updated"] = now.isoformat()
            lead_service.update(lead)
            return {"success": True}

        return {
            "success": False,
            "message": f"Failed to update status for platform {platform}",
        }

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Scheduled sync: unexpected error for platform '%s' lead '%s': %s",
            platform,
            lead.fub_person_id,
            str(exc),
        )
        return {"success": False, "error": str(exc)}

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_webhook_task(self, webhook_data):
    """Process webhook asynchronously using Celery"""
    try:
        tenant_resolver = TenantResolver()
        
        # Resolve tenant
        tenant_info = tenant_resolver.resolve_tenant_from_webhook(
            webhook_data['payload'],
            webhook_data['webhook_type']
        )
        
        if not tenant_info:
            raise Exception(f"Cannot resolve tenant for webhook: {webhook_data['correlation_id']}")
        
        # Create tenant-specific FUB client
        fub_client = FUBApiClient(api_key=tenant_info['api_key'])
        
        # Route to specific processor
        if webhook_data['webhook_type'] == 'stage-webhook':
            process_stage_webhook_with_tenant(webhook_data['payload'], tenant_info, fub_client)
        elif webhook_data['webhook_type'] == 'notes-created-webhook':
            process_note_webhook_with_tenant(webhook_data['payload'], tenant_info, fub_client, 'created')
        elif webhook_data['webhook_type'] == 'notes-updated-webhook':
            process_note_webhook_with_tenant(webhook_data['payload'], tenant_info, fub_client, 'updated')
        elif webhook_data['webhook_type'] == 'tag-webhook':
            process_tag_webhook_with_tenant(webhook_data['payload'], tenant_info, fub_client)
        elif webhook_data['webhook_type'] == 'person-created-webhook':
            process_person_created_webhook_with_tenant(webhook_data['payload'], tenant_info, fub_client)
        elif webhook_data['webhook_type'] == 'person-updated-webhook':
            process_person_updated_webhook_with_tenant(webhook_data['payload'], tenant_info, fub_client)

        return {'status': 'completed', 'webhook_id': webhook_data['correlation_id']}
        
    except Exception as exc:
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    
    
@shared_task
def process_scheduled_webhook_batch(tenant_id, webhook_type):
    """Process scheduled webhooks for a specific tenant"""
    # This can be called by your scheduler based on user preferences
    # For example, if a user wants webhooks processed every hour
    pass

# Helper functions that use tenant-specific clients
def process_stage_webhook_with_tenant(payload, tenant_info, fub_client):
    """Process stage webhook with tenant context"""
    from app.webhook.webhook_processors import process_stage_updated_webhook
    # Use the existing logic but with tenant-specific client
    person_id = payload.get('personId') or extract_person_id_from_uri(payload.get('uri'))
    if person_id:
        person_data = fub_client.get_person(person_id)
        # Continue with existing processing...

def process_note_webhook_with_tenant(payload, tenant_info, fub_client, event_type):
    """Process note webhook with tenant context"""
    from app.webhook.webhook_processors import process_note_webhook
    # Similar pattern for notes
    pass

def process_tag_webhook_with_tenant(payload, tenant_info, fub_client):
    """Process tag webhook with tenant context"""
    from app.webhook.webhook_processors import process_tag_webhook
    # Similar pattern for tags
    pass


def process_person_created_webhook_with_tenant(payload, tenant_info, fub_client):
    """Process person created webhook with tenant context - triggers auto-enhancement"""
    from app.webhook.webhook_processors import process_person_created_webhook

    try:
        # Get user_id from tenant_info
        user_id = tenant_info.get('user_id') if tenant_info else None

        # Run the async processor
        asyncio.run(process_person_created_webhook(payload, user_id))
        logger.info(f"Processed person created webhook for tenant {tenant_info.get('tenant_id', 'unknown')}")
    except Exception as e:
        logger.error(f"Error processing person created webhook: {e}")
        raise


def process_person_updated_webhook_with_tenant(payload, tenant_info, fub_client):
    """Process person updated webhook with tenant context"""
    try:
        # Extract person ID from payload
        person_id = payload.get('personId') or extract_person_id_from_uri(payload.get('uri'))

        if person_id:
            # Fetch updated person data
            person_data = fub_client.get_person(person_id)
            if person_data:
                lead = Lead.from_fub(person_data)
                # Check if we need to sync with our database
                lead_service = LeadServiceSingleton.get_instance()
                existing_lead = lead_service.get_by_fub_person_id(str(person_id))

                if existing_lead:
                    # Update the lead in our database
                    lead.id = existing_lead.id
                    lead_service.update(lead)
                    logger.info(f"Updated lead {person_id} from person-updated webhook")
    except Exception as e:
        logger.error(f"Error processing person updated webhook: {e}")


def extract_person_id_from_uri(uri):
    """Extract person ID from FUB URI like '/v1/people/12345'"""
    if not uri:
        return None
    parts = uri.rstrip('/').split('/')
    for i, part in enumerate(parts):
        if part == 'people' and i + 1 < len(parts):
            try:
                return int(parts[i + 1])
            except ValueError:
                return parts[i + 1]
    return None


# Old functions
@celery.task
def weekly_process_stage_updates():
    raw_ids = redis_service.redis.smembers('friday_schedule:stage')
    processed = []
    if not raw_ids:
        print("No stage updates to process this Friday.")
        return

    for raw in raw_ids:
        # handle bytes vs str
        pid = raw.decode('utf-8') if isinstance(raw, bytes) else raw
        processed.append(pid)

        # your existing cache‐aside lookup
        lead = lead_cache.sync_with_db_and_cache(pid)
        if lead:
            asyncio.run(process_stage_updated_webhook(lead))
        else:
            print(f"Lead {pid} missing from cache/DB; skipped stage processing.")

    # clear the set
    redis_service.delete('friday_schedule:stage')



@celery.task
def weekly_process_notes():
    raw_ids = redis_service.redis.smembers('friday_schedule:note')
    processed = []
    if not raw_ids:
        print("No notes to process this Friday.")
        return

    for raw in raw_ids:
        note_id = raw.decode('utf-8') if isinstance(raw, bytes) else raw
        processed.append(note_id)

        # fetch fresh note data
        try:
            fresh_note_data = api_client.get_note(note_id)
        except Exception as e:
            print(f"Failed to fetch note {note_id}: {e}")
            continue

        # extract the person/lead ID
        person_id = fresh_note_data.get("personId")
        if not person_id:
            print(f"No personId for note {note_id}; skipped.")
            continue

        # lookup lead (DB fallback if cache expired)
        lead = lead_cache.sync_with_db_and_cache(person_id)
        if not lead:
            print(f"Lead {person_id} not found for note {note_id}; skipped.")
            continue

        # call the existing processor
        asyncio.run(process_note_webhook(lead, fresh_note_data, "friday_scheduled"))

    # clear the set
    redis_service.delete('friday_schedule:note')

@celery.task
def weekly_process_tags():
    raw_ids = redis_service.redis.smembers('friday_schedule:tag')
    processed = []
    if not raw_ids:
        print("No tags to process this Friday.")
        return

    for raw in raw_ids:
        # raw might be bytes or str
        if isinstance(raw, bytes):
            pid = raw.decode('utf-8')
            processed.append(pid)
        else:
            pid = raw

        # fetch fresh data and process:
        fresh = api_client.get_person(pid)
        if fresh:
            lead = Lead.from_fub(fresh)
            asyncio.run(process_tag_webhook(lead))
        else:
            print(f"Lead {pid} not found; skipped.")

    # clean up:
    redis_service.delete('friday_schedule:tag')

