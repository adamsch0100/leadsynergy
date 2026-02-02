import os
import signal

from tasks_old import update_referral_sources

# Monkey-patch missing signal attributes on Windows
if not hasattr(signal, 'SIGRTMIN'):
    signal.SIGRTMIN = 34
if not hasattr(signal, 'SIGUSR1'):
    signal.SIGUSR1 = 10

from flask import Flask, request, jsonify
from redis import Redis
from rq import Queue
import time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

app = Flask(__name__)

# Configure Redis connection (adjust host/port as needed)
redis_conn = Redis(password=os.getenv('REDIS_PASSWORD', ''), host='localhost', port=6379)
# Create an RQ named 'updates'
q = Queue('updates', connection=redis_conn)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON payload'}), 400

    lead_id = data.get('lead_id')
    new_stage = data.get('new_stage')
    referral_mapping = data.get('sources', {})

    if not lead_id or not new_stage:
        return jsonify({'error': "Missing 'lead_id' or 'new_stage'"}), 400

    # Enqueue an immediate update job
    job = q.enqueue(update_referral_sources, lead_id, new_stage, referral_mapping)
    app.logger.info(f'Webhook: enqueued job {job.get_id()} for lead {lead_id}')

    return jsonify({'status': 'job enqueued', 'job_id': job.get_id()}), 200

def schedule_update_job():
    # Dummy data for the scheduled update job
    dummy_lead_id = "123"
    dummy_new_stage = "Nurturing"
    dummy_sources = {'SourceA': 'MappingInfoA', 'SourceB': 'MappingInfoB'}
    job = q.enqueue(update_referral_sources, dummy_lead_id, dummy_new_stage, dummy_sources)
    app.logger.info(f"Schedule job enqueued: {job.get_id()} for lead {dummy_lead_id}")


if __name__ == '__main__':
    # Set up APScheduler to run the scheduled_update_job on specific days/times
    scheduler = BackgroundScheduler()
    # Schedule the job every Friday at 17:00 (5PM)
    trigger_friday = CronTrigger(day_of_week='fri', hour=17, minute=0)
    scheduler.add_job(schedule_update_job, trigger=trigger_friday, id='friday_update')

    # Also schedule it every Saturday at 17:00 (5PM)
    trigger_saturday = CronTrigger(day_of_week='sat', hour=17, minute=0)
    scheduler.add_job(schedule_update_job, trigger=trigger_saturday, id='saturday_update')

    scheduler.start()
    print("Scheduler started with Friday and Saturday triggers")

    app.run(debug=True, port=5000)
