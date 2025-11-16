import time
import random
from datetime import datetime, timezone
from typing import Callable, Any, Optional, Dict
from functools import wraps
from app.core.logging_config import logger
from app.services.blog_tracking_service import blog_tracking_service

def track_api_retries(
    blog_id: str,
    step_name: str,
    max_retries: int = 3,
    initial_delay: float = 5.0,
    backoff_factor: float = 2.0,
    jitter: bool = True
):
    """
    Decorator to track API retries with detailed logging.
    
    Args:
        blog_id: Blog ID for tracking
        step_name: Name of the step (e.g., 'wc1', 'step1', etc.)
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        backoff_factor: Exponential backoff factor
        jitter: Whether to add random jitter to delays
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            attempt = 0
            last_exception = None
            
            # Start step tracking
            try:
                blog_tracking_service.start_step_tracking(
                    tracking_id=kwargs.get('tracking_id', ''),
                    blog_id=blog_id,
                    step_name=step_name
                )
            except Exception as e:
                logger.warning(f"Could not start step tracking: {e}")
            
            while attempt < max_retries:
                attempt += 1
                start_time = datetime.now(timezone.utc)
                
                try:
                    logger.info(f"API attempt {attempt}/{max_retries} for {step_name}")
                    
                    # Record the attempt start
                    blog_tracking_service.record_api_attempt(
                        blog_id=blog_id,
                        step_name=step_name,
                        attempt_number=attempt,
                        start_time=start_time,
                        status='running'
                    )
                    
                    # Execute the function
                    result = func(*args, **kwargs)
                    
                    end_time = datetime.now(timezone.utc)
                    
                    # Record successful attempt
                    blog_tracking_service.record_api_attempt(
                        blog_id=blog_id,
                        step_name=step_name,
                        attempt_number=attempt,
                        start_time=start_time,
                        end_time=end_time,
                        status='success',
                        response_data={'success': True}
                    )
                    
                    # Complete step tracking
                    if hasattr(result, 'get') and isinstance(result, dict):
                        output_content = result.get('content', str(result))
                    else:
                        output_content = str(result)
                    
                    blog_tracking_service.complete_step(
                        blog_id=blog_id,
                        step_name=step_name,
                        status='completed',
                        output_content=output_content
                    )
                    
                    logger.info(f"API call successful on attempt {attempt} for {step_name}")
                    return result
                    
                except Exception as e:
                    end_time = datetime.now(timezone.utc)
                    last_exception = e
                    
                    # Record failed attempt
                    blog_tracking_service.record_api_attempt(
                        blog_id=blog_id,
                        step_name=step_name,
                        attempt_number=attempt,
                        start_time=start_time,
                        end_time=end_time,
                        status='failed',
                        error_message=str(e)
                    )
                    
                    logger.warning(f"API attempt {attempt} failed for {step_name}: {str(e)}")
                    
                    # If this was the last attempt, mark step as failed
                    if attempt >= max_retries:
                        blog_tracking_service.complete_step(
                            blog_id=blog_id,
                            step_name=step_name,
                            status='failed',
                            error_message=str(e)
                        )
                        break
                    
                    # Calculate delay with exponential backoff and optional jitter
                    delay = initial_delay * (backoff_factor ** (attempt - 1))
                    if jitter:
                        delay += random.uniform(0, 1)
                    
                    logger.info(f"Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
            
            # If we get here, all attempts failed
            logger.error(f"All {max_retries} attempts failed for {step_name}")
            if last_exception:
                raise last_exception
            else:
                raise Exception(f"All {max_retries} attempts failed for {step_name}")
        
        return wrapper
    return decorator

def enhanced_openai_call(
    blog_id: str,
    step_name: str,
    api_payload: Dict,
    max_retries: int = 3,
    timeout: int = 900
) -> Dict:
    """
    Enhanced OpenAI API call with comprehensive tracking.
    
    Args:
        blog_id: Blog ID for tracking
        step_name: Step name for tracking
        api_payload: API request payload
        max_retries: Maximum retry attempts
        timeout: Request timeout in seconds
    
    Returns:
        API response data
    """
    import requests
    
    attempt = 0
    last_exception = None
    
    while attempt < max_retries:
        attempt += 1
        start_time = datetime.now(timezone.utc)
        
        try:
            logger.info(f"OpenAI API attempt {attempt}/{max_retries} for {step_name}")
            
            # Record the attempt start
            blog_tracking_service.record_api_attempt(
                blog_id=blog_id,
                step_name=step_name,
                attempt_number=attempt,
                start_time=start_time,
                status='running'
            )
            
            # Make the API call
            response = requests.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"
                },
                json=api_payload,
                timeout=timeout
            )
            
            end_time = datetime.now(timezone.utc)
            
            # Check response status
            if response.status_code == 200:
                # Record successful attempt
                blog_tracking_service.record_api_attempt(
                    blog_id=blog_id,
                    step_name=step_name,
                    attempt_number=attempt,
                    start_time=start_time,
                    end_time=end_time,
                    status='success',
                    response_data={
                        'status_code': response.status_code,
                        'response_size': len(response.text)
                    }
                )
                
                logger.info(f"OpenAI API successful on attempt {attempt} for {step_name}")
                return response.json()
            
            # Handle retryable errors
            elif response.status_code in [429, 500, 502, 503, 504]:
                error_msg = f"OpenAI API error (retryable): {response.status_code} - {response.text}"
                
                # Record failed attempt
                blog_tracking_service.record_api_attempt(
                    blog_id=blog_id,
                    step_name=step_name,
                    attempt_number=attempt,
                    start_time=start_time,
                    end_time=end_time,
                    status='failed',
                    error_message=error_msg,
                    response_data={
                        'status_code': response.status_code,
                        'error_response': response.text[:500]  # Truncate long error messages
                    }
                )
                
                logger.warning(error_msg)
                last_exception = Exception(error_msg)
                
            else:
                # Non-retryable error
                error_msg = f"OpenAI API error (non-retryable): {response.status_code} - {response.text}"
                
                # Record failed attempt
                blog_tracking_service.record_api_attempt(
                    blog_id=blog_id,
                    step_name=step_name,
                    attempt_number=attempt,
                    start_time=start_time,
                    end_time=end_time,
                    status='failed',
                    error_message=error_msg,
                    response_data={
                        'status_code': response.status_code,
                        'error_response': response.text[:500]
                    }
                )
                
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
            end_time = datetime.now(timezone.utc)
            error_msg = f"Request failed with exception: {str(e)}"
            
            # Record failed attempt
            blog_tracking_service.record_api_attempt(
                blog_id=blog_id,
                step_name=step_name,
                attempt_number=attempt,
                start_time=start_time,
                end_time=end_time,
                status='failed',
                error_message=error_msg
            )
            
            logger.error(error_msg)
            last_exception = e
        
        # If not the last attempt, wait before retrying
        if attempt < max_retries:
            # Exponential backoff with jitter
            delay = 5 * (2 ** (attempt - 1)) + random.uniform(0, 1)
            logger.info(f"Retrying in {delay:.2f} seconds...")
            time.sleep(delay)
    
    # All attempts failed
    error_msg = f"All {max_retries} attempts failed for {step_name}"
    logger.error(error_msg)
    
    if last_exception:
        raise last_exception
    else:
        raise Exception(error_msg) 