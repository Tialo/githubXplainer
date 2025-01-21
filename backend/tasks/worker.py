from celery import Celery

# Initialize Celery app
celery_app = Celery(
    'githubxplainer',
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
)
