import redis
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

def get_redis_client():
    """
    Create and return a Redis client
    
    :return: Redis client instance
    """
    try:
        redis_kwargs = {
            'host': settings.REDIS_HOST, 
            'port': settings.REDIS_PORT, 
            'db': settings.REDIS_DB,
            'decode_responses': True  # This will decode byte responses to strings
        }
        
        # Determine if password should be used
        password = getattr(settings, 'REDIS_PASSWORD', None)
        if password and str(password).lower() not in ['none', '']:
            redis_kwargs['password'] = password
        
        redis_client = redis.Redis(**redis_kwargs)
        
        # Test the connection
        redis_client.ping()
        return redis_client
    except Exception as e:
        # Log the specific error for debugging
        logger.error(f"Redis connection error: {str(e)}")
        
        # If connection fails, try without password
        try:
            redis_kwargs.pop('password', None)
            redis_client = redis.Redis(**redis_kwargs)
            redis_client.ping()
            logger.warning("Connected to Redis without password")
            return redis_client
        except Exception as fallback_error:
            logger.error(f"Failed to connect to Redis: {str(fallback_error)}")
            return None  # Return None instead of raising an exception

def set_task_status(task_id: str, status: str, additional_info: dict = None):
    """
    Set task status in Redis
    
    :param task_id: Unique task identifier
    :param status: Current status of the task
    :param additional_info: Optional additional information about the task
    """
    redis_client = get_redis_client()
    task_key = f"task_status:{task_id}"
    
    # Prepare task status data
    task_data = {
        "status": status,
        **(additional_info or {})
    }
    
    # Store task status with expiration
    redis_client.hmset(task_key, task_data)
    redis_client.expire(task_key, 86400)  # 24-hour expiration

def get_task_status(task_id: str):
    """
    Retrieve task status from Redis
    
    :param task_id: Unique task identifier
    :return: Task status dictionary
    """
    redis_client = get_redis_client()
    task_key = f"task_status:{task_id}"
    
    return redis_client.hgetall(task_key) or {}
