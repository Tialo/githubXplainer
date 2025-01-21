import os
from backend.config.settings import get_settings
from celery import Celery

# Initialize Celery app
celery_app = Celery(
    'githubxplainer',
    broker=get_settings().celery_broker_url,
    include=['backend.tasks.summary_tasks']
)

# Configure task routing
task_routes = {
    'backend.tasks.summary_tasks.*': {'queue': 'summarization'}
}

# Optional configurations
celery_app.conf.update(
    result_expires=3600,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_routes=task_routes,
    task_default_rate_limit='1/s',  # Global rate limit
    task_annotations={
        'backend.tasks.summary_tasks.*': {
            'rate_limit': '1/s'  # Specific rate limit for summarization tasks
        }
    },
    broker_connection_retry_on_startup=True  # Add this for RabbitMQ connection stability
)
