from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'downloader.settings')  # Sets the default DANGO_SETTINGS_MODULE env var to the celery cmd line
app = Celery('downloader', broker='amqp:guest:guest@localhost:5672/')
app.config_from_object('django.conf:settings', namespace='CELERY')  # provides configurations source(settings.py) to celery
app.autodiscover_tasks()  # Discovers tasks.py from all apps
app.conf.update(
    broker_connection_retry_on_startup=True,
)

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
