from app.celery_config import celery_app

def get_celery():
    """
    Return the Celery app instance.
    
    Returns:
        Celery app instance
    """
    return celery_app


# Import V2 blog generation tasks (now PRO tier)
from app.tasks.blog_generation import generate_blog_pro, generate_final_blog_step, get_blog_status_pro

# Import FREE tier blog generation tasks
from app.tasks.blog_generation_free import generate_blog_free, get_blog_status_free

__all__ = [
    'get_celery', 
    'generate_complete_blog', 
    # V2 blog generation tasks (PRO tier)
    'generate_blog_pro',
    'generate_final_blog_step', 
    'get_blog_status_pro',
    # FREE tier blog generation tasks
    'generate_blog_free',
    'get_blog_status_free'
]
