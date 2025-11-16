from app.celery_config import celery_app as celery
from app.db.session import get_db_session
from app.services.mongodb_service import MongoDBService
from app.models.wordpress_credentials import WordPressCredentials
from app.core.logging_config import logger
from datetime import datetime, timedelta
import pytz
from app.core.celery_logging import setup_celery_logging
import asyncio
import json
from app.services.mongodb_service import MongoDBService
from app.models.monitoring import MonitoringProjectStats
from app.models.project import Project
from app.models.gsc import GSCAccount
from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert

# Import blog generation tasks to ensure they are discovered
from app.tasks import blog_generation

# Setup Celery logging
worker_logger, task_logger = setup_celery_logging()

def run_async_in_new_loop(async_func, *args, **kwargs):
    """
    Run an async function inside a new event loop.
    This ensures the event loop is created and destroyed properly
    within the Celery worker.
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Use asyncio.run to properly handle async function
        result = loop.run_until_complete(async_func(*args, **kwargs))
        
        # Close the loop
        loop.close()
        
        return result
    except Exception as e:
        logger.error(f"Error running async function: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


def setup_periodic_tasks(sender, **kwargs):
    """Setup periodic tasks"""
    from celery.schedules import crontab
    


