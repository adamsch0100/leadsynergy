from app.service.celery_service import CeleryServiceSingleton
from app.models.lead import Lead
from typing import Dict, Any

celery_service = CeleryServiceSingleton.get_instance()


@celery_service.create_task(name="tasks.process_stage_task", ignore_result=False)
def process_stage_task(lead_dict: Dict[str, Any]) -> str:
    from app.webhook.webhook_processors import process_stage_updated_webhook
    import asyncio

    # Convert dict back to Lead
    lead = Lead.from_fub(lead_dict)

    # Execute async function
    loop = asyncio.get_event_loop()
    loop.run_until_complete(process_stage_updated_webhook(lead))

    return f"Stage processed for lead {lead.fub_person_id}"


@celery_service.create_task(name="tasks.process_note_task")
def process_note_task(
    lead_dict: Dict[str, Any], note_data: Dict[str, Any], event_type: str
) -> str:
    from app.webhook.webhook_processors import process_note_webhook
    import asyncio

    # Convert dict back to Lead
    lead = Lead.from_fub(lead_dict)

    # Execute async back to Lead
    loop = asyncio.get_event_loop()
    loop.run_until_complete(process_note_webhook(lead, note_data, event_type))

    return f"Note {event_type} processed for lead {lead.fub_person_id}"


@celery_service.create_task(name="tasks.process_tag_task")
def process_tag_task(lead_dict: Dict[str, Any]) -> str:
    from app.webhook.webhook_processors import process_tag_webhook
    import asyncio

    print(f"Lead Dict is: {lead_dict}")
    lead = Lead.from_fub(lead_dict)

    # Execute async function
    loop = asyncio.get_event_loop()
    loop.run_until_complete(process_tag_webhook(lead))

    return f"Tag processed for lead {lead.fub_person_id}"
