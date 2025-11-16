from typing import Callable

def get_status_check_function() -> Callable:
    """
    Dynamically import and return the status check function
    to avoid circular imports
    """
    from app.api.v1.endpoints.blog_generation import get_blog_generation_status
    return get_blog_generation_status

def get_monitor_blog_generation_status() -> Callable:
    """
    Dynamically import monitor_blog_generation_status to avoid circular imports
    
    :return: Function to monitor blog generation status
    """
    try:
        from app.api.v1.endpoints.blog_generation import monitor_blog_generation_status
        return monitor_blog_generation_status
    except ImportError:
        logger.error("Could not import monitor_blog_generation_status")
        return None