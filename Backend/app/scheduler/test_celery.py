from celery import Celery

def make_celery(app):
    celery = Celery(app.import_name)
    celery.conf.update(app.config['CELERY_CONFIG'])