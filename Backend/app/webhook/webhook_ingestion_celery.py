from flask import Flask, request, Response
import uuid
from datetime import datetime
from app.scheduler.tasks import process_webhook_task
from app.scheduler.celery_app import celery_app

app = Flask(__name__)

@app.route('/webhook/<webhook_type>', methods=['POST'])
def universal_webhook_handler(webhook_type):
    """Lightweight webhook ingestion that queues to Celery"""
    try:
        webhook_data = request.get_json()
        
        # Extract tenant hint for routing
        tenant_hint = extract_tenant_hint(webhook_data, webhook_type)
        
        # Create webhook message
        webhook_message = {
            'webhook_type': webhook_type,
            'payload': webhook_data,
            'tenant_hint': tenant_hint,
            'received_at': datetime.utcnow().isoformat(),
            'correlation_id': str(uuid.uuid4()),
            'source_ip': request.remote_addr
        }
        
        # Queue to Celery with routing based on webhook type
        task = process_webhook_task.apply_async(
            args=[webhook_message],
            queue='webhooks',  # Dedicated queue for webhooks
            routing_key=f'webhook.{webhook_type}',
            priority=5  # Medium priority
        )
        
        # Store task ID for tracking if needed
        store_webhook_task_mapping(webhook_message['correlation_id'], task.id)
        
        return Response("Accepted", status=202)
        
    except Exception as e:
        print(f"Webhook ingestion error: {e}")
        return Response("Accepted", status=202)

def extract_tenant_hint(webhook_data, webhook_type):
    """Extract tenant hint for routing"""
    if 'personId' in webhook_data:
        return str(webhook_data['personId'])
    elif 'resourceIds' in webhook_data and webhook_data['resourceIds']:
        return str(webhook_data['resourceIds'][0])
    elif 'uri' in webhook_data and '/people/' in webhook_data['uri']:
        parts = webhook_data['uri'].split('/people/')
        if len(parts) > 1:
            return parts[1].split('/')[0]
    return None

def store_webhook_task_mapping(correlation_id, task_id):
    """Store mapping between webhook and Celery task for tracking"""
    # Store in Redis or database
    from app.database.supabase_client import SupabaseClientSingleton
    supabase = SupabaseClientSingleton.get_instance()
    
    supabase.table('webhook_tasks').insert({
        'correlation_id': correlation_id,
        'celery_task_id': task_id,
        'created_at': datetime.utcnow().isoformat()
    }).execute()
