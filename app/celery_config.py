from celery import Celery
from app.core.config import settings
from celery.schedules import crontab

# Create Celery app
celery_app = Celery('rayo_tasks')

# Configure Celery using settings from config
celery_app.config_from_object('app.celery_config', namespace='CELERY')

# Redis broker configuration
celery_app.conf.broker_url = settings.CELERY_BROKER_URL
celery_app.conf.result_backend = settings.CELERY_RESULT_BACKEND

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Kolkata',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=10800,  # 3 hours
    task_soft_time_limit=10800,  # 3 hours
    worker_send_task_events=True,
    task_send_sent_event=True,
    task_ignore_result=False,
    task_routes={
        'app.tasks.*': {'queue': 'default'},
        'app.tasks.blog_generation.*': {'queue': 'blog_generation'},
        'app.tasks.featured_image_generation.*': {'queue': 'image_generation'}
    }
)

# Autodiscover tasks in the project
celery_app.autodiscover_tasks([
    'app.tasks',
    'app.tasks.blog_generation',  # Explicitly include enhanced tasks
    'app.tasks.featured_image_generation',  # Include featured image generation tasks
], force=True)

# Ensure enhanced tasks are imported
try:
    from app.tasks import blog_generation
    print("✅ blog generation tasks imported successfully")
except ImportError as e:
    print(f"⚠️  Warning: Could not import blog generation tasks: {e}")

# Ensure featured image generation tasks are imported
try:
    from app.tasks import featured_image_generation
    print("✅ featured image generation tasks imported successfully")
except ImportError as e:
    print(f"⚠️  Warning: Could not import featured image generation tasks: {e}")

# Optional: Periodic tasks
celery_app.conf.beat_schedule = {
    # Keep other periodic tasks as needed
}

# Export the Celery app for use in other modules
__all__ = ['celery_app']
