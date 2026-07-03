"""
smallcase_project/celery.py

Celery application bootstrap for Django.
Uses django-celery-results with Django DB as broker (no Redis required).

Start worker with:
    celery -A smallcase_project worker --loglevel=info --pool=solo
    (--pool=solo is needed on Windows to avoid multiprocessing issues)
"""

import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smallcase_project.settings')

app = Celery('smallcase_project')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
