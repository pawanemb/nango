import os
import logging
from logging.handlers import RotatingFileHandler
from app.core.config import settings

# Create logs directory if it doesn't exist
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

# Celery worker log file
CELERY_WORKER_LOG = os.path.join(LOGS_DIR, 'celery_worker.log')
CELERY_BEAT_LOG = os.path.join(LOGS_DIR, 'celery_beat.log')

def setup_celery_logging():
    # Configure worker logger
    worker_logger = logging.getLogger('celery')
    worker_logger.setLevel(logging.INFO)
    
    # File handler for worker logs
    worker_handler = RotatingFileHandler(
        CELERY_WORKER_LOG,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    
    # Formatter
    formatter = logging.Formatter(
        '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
    )
    worker_handler.setFormatter(formatter)
    
    # Add handler to logger
    worker_logger.addHandler(worker_handler)
    
    # Configure task logger
    task_logger = logging.getLogger('celery.task')
    task_logger.setLevel(logging.INFO)
    
    # File handler for task logs (same file as worker)
    task_handler = RotatingFileHandler(
        CELERY_WORKER_LOG,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    
    # Task formatter with more details
    task_formatter = logging.Formatter(
        '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'
    )
    task_handler.setFormatter(task_formatter)
    
    # Add handler to logger
    task_logger.addHandler(task_handler)
    
    return worker_logger, task_logger
