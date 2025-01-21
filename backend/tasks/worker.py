import os
from celery import Celery

# Initialize Celery app
celery_app = Celery(
    'githubxplainer',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    include=['backend.tasks.summary_tasks']
)

# Optional configurations
celery_app.conf.update(
    result_expires=3600,
    worker_prefetch_multiplier=1,
    task_acks_late=True
)
