from typing import Callable

def get_status_check_function() -> Callable:
    """
    Dynamically import and return the status check function
    to avoid circular imports
    """
    from app.api.v1.endpoints.blog_generation import get_blog_generation_status
    return get_blog_generation_status
