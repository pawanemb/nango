"""
Utility functions for tracking token consumption across different prompts.
This module provides functions to record API usage for cost tracking and optimization.
"""

import time
import hashlib
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from functools import wraps
from sqlalchemy.orm import Session
# PromptTokenConsumption model removed - using Usage table instead
from app.core.redis_client import get_redis_client
import json
import asyncio
import inspect

logger = logging.getLogger("fastapi_app")

# Model pricing information (as of March 2025)
MODEL_PRICING = {
    "gpt-4": {
        "input_per_1k": 0.03,  # $30 per 1M tokens
        "output_per_1k": 0.06  # $60 per 1M tokens
    },
    "gpt-4-turbo": {
        "input_per_1k": 0.01,  # $10 per 1M tokens
        "output_per_1k": 0.03  # $30 per 1M tokens
    },
    "gpt-3.5-turbo": {
        "input_per_1k": 0.0005,  # $0.50 per 1M tokens
        "output_per_1k": 0.0015  # $1.50 per 1M tokens
    },
    "chatgpt-4o-latest": {
        "input_per_1k": 0.005,  # $5 per 1M tokens
        "output_per_1k": 0.015  # $15 per 1M tokens
    },
    "o1": {
        "input_per_1k": 0.015,  # $15 per 1M tokens
        "output_per_1k": 0.060  # $60 per 1M tokens
    },
    "o1-mini": {
        "input_per_1k": 0.003,  # $3 per 1M tokens
        "output_per_1k": 0.012  # $12 per 1M tokens
    },
    "claude-3-5-sonnet-20241022": {
        "input_per_1k": 0.003,  # $3 per 1M tokens
        "output_per_1k": 0.015  # $15 per 1M tokens
    },
    "claude-3-opus": {
        "input_per_1k": 0.015,  # $15 per 1M tokens
        "output_per_1k": 0.075  # $75 per 1M tokens
    },
    "claude-3-sonnet": {
        "input_per_1k": 0.003,  # $3 per 1M tokens
        "output_per_1k": 0.015  # $15 per 1M tokens
    },
    "claude-3-haiku": {
        "input_per_1k": 0.00025,  # $0.25 per 1M tokens
        "output_per_1k": 0.00125  # $1.25 per 1M tokens
    }
}


def calculate_cost(model_name: str, input_tokens: int, output_tokens: int) -> Dict[str, float]:
    """
    Calculate the cost based on model and token usage.
    
    Args:
        model_name: Name of the model used
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        
    Returns:
        Dictionary with input_cost, output_cost, and total_cost in USD
    """
    # Get pricing for the model, default to GPT-4 pricing if not found
    pricing = MODEL_PRICING.get(model_name, MODEL_PRICING["gpt-4"])
    
    input_cost = (input_tokens / 1000) * pricing["input_per_1k"]
    output_cost = (output_tokens / 1000) * pricing["output_per_1k"]
    total_cost = input_cost + output_cost
    
    return {
        "input_cost_usd": input_cost,
        "output_cost_usd": output_cost,
        "total_cost_usd": total_cost
    }


def get_prompt_hash(prompt: str) -> str:
    """
    Generate a hash of the prompt for deduplication analysis.
    
    Args:
        prompt: The prompt text
        
    Returns:
        SHA256 hash of the prompt
    """
    return hashlib.sha256(prompt.encode()).hexdigest()


def track_prompt_usage(
    db: Session,
    user_id: str,
    prompt_type: str,
    prompt_name: str,
    model_name: str,
    model_provider: str,
    input_tokens: int,
    output_tokens: int,
    response_time_ms: float,
    project_id: Optional[str] = None,
    request_id: Optional[str] = None,
    blog_id: Optional[str] = None,
    keyword_id: Optional[str] = None,
    prompt_text: Optional[str] = None,
    prompt_version: Optional[str] = None,
    error_message: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Legacy function for tracking token consumption.
    
    NOTE: This function is deprecated and kept for backward compatibility.
    New code should use EnhancedLLMUsageService instead.
    
    Args:
        db: Database session
        user_id: ID of the user making the request
        prompt_type: Type of prompt
        prompt_name: Human-readable name of the prompt
        model_name: Name of the model used
        model_provider: Provider of the model (openai, anthropic, etc.)
        input_tokens: Number of input tokens consumed
        output_tokens: Number of output tokens generated
        response_time_ms: Response time in milliseconds
        project_id: Optional project ID
        request_id: Optional request ID for tracking
        blog_id: Optional blog ID if related to blog generation
        keyword_id: Optional keyword ID if related to keyword operations
        prompt_text: Optional prompt text for hash generation
        prompt_version: Optional version of the prompt
        error_message: Optional error message if request failed
        extra_metadata: Optional additional metadata
        
    Returns:
        None (deprecated function)
    """
    # This function is deprecated - EnhancedLLMUsageService should be used instead
    # Keeping as no-op for backward compatibility
    logger.warning(
        f"track_prompt_usage is deprecated. Use EnhancedLLMUsageService instead. "
        f"Called for user: {user_id}, prompt: {prompt_type}, model: {model_name}"
    )
    return None


def track_token_usage(
    prompt_type: str,
    prompt_name: str,
    model_provider: str = "openai",
    extract_project_id: bool = True,
    extract_user_id: bool = True,
    **default_kwargs
):
    """
    Decorator for automatic token tracking on functions that make LLM API calls.
    
    Args:
        prompt_type: Type of prompt (from PromptType enum)
        prompt_name: Human-readable name of the prompt
        model_provider: Provider of the model (openai, anthropic, etc.)
        extract_project_id: Whether to try to extract project_id from function args
        extract_user_id: Whether to try to extract user_id from function args
        **default_kwargs: Default values for tracking (can be overridden by function)
    
    Usage:
        @track_token_usage(
            prompt_type="keyword_suggestions",
            prompt_name="Generate Keywords"
        )
        async def generate_keywords(self, project_id: str, ...):
            response = await openai_client.responses.create(...)
            return response
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract common parameters
            tracking_params = default_kwargs.copy()
            
            # Try to extract db session
            db = None
            if args and hasattr(args[0], 'db'):
                db = args[0].db
            else:
                db = kwargs.get('db')
            
            # Try to extract user_id
            user_id = None
            if extract_user_id:
                if args and hasattr(args[0], 'user_id'):
                    user_id = args[0].user_id
                else:
                    user_id = kwargs.get('user_id')
            
            # Try to extract project_id
            project_id = None
            if extract_project_id:
                if 'project_id' in kwargs:
                    project_id = kwargs['project_id']
                elif len(args) > 1 and isinstance(args[1], str):
                    # Assume second argument might be project_id
                    project_id = args[1]
                elif args and hasattr(args[0], 'project_id'):
                    project_id = args[0].project_id
            
            # Skip tracking if we don't have required parameters
            if not db or not user_id:
                logger.warning(f"Skipping token tracking for {prompt_name}: missing db or user_id")
                return await func(*args, **kwargs)
            
            # Create tracker
            tracker = TokenTracker(
                db=db,
                user_id=user_id,
                prompt_type=prompt_type,
                prompt_name=prompt_name,
                model_provider=model_provider,
                project_id=project_id,
                **tracking_params
            )
            
            # Execute function with tracking
            async with tracker:
                result = await func(*args, **kwargs)
                
                # Try to extract response from result
                if hasattr(result, 'usage'):
                    tracker.set_response(result)
                elif isinstance(result, dict) and 'response' in result:
                    tracker.set_response(result['response'])
                elif isinstance(result, tuple) and len(result) > 0:
                    # Check if first element is the response
                    if hasattr(result[0], 'usage'):
                        tracker.set_response(result[0])
                
                return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Similar logic for sync functions
            tracking_params = default_kwargs.copy()
            
            db = None
            if args and hasattr(args[0], 'db'):
                db = args[0].db
            else:
                db = kwargs.get('db')
            
            user_id = None
            if extract_user_id:
                if args and hasattr(args[0], 'user_id'):
                    user_id = args[0].user_id
                else:
                    user_id = kwargs.get('user_id')
            
            project_id = None
            if extract_project_id:
                if 'project_id' in kwargs:
                    project_id = kwargs['project_id']
                elif len(args) > 1 and isinstance(args[1], str):
                    project_id = args[1]
                elif args and hasattr(args[0], 'project_id'):
                    project_id = args[0].project_id
            
            if not db or not user_id:
                logger.warning(f"Skipping token tracking for {prompt_name}: missing db or user_id")
                return func(*args, **kwargs)
            
            with TokenTracker(
                db=db,
                user_id=user_id,
                prompt_type=prompt_type,
                prompt_name=prompt_name,
                model_provider=model_provider,
                project_id=project_id,
                **tracking_params
            ) as tracker:
                result = func(*args, **kwargs)
                
                if hasattr(result, 'usage'):
                    tracker.set_response(result)
                elif isinstance(result, dict) and 'response' in result:
                    tracker.set_response(result['response'])
                elif isinstance(result, tuple) and len(result) > 0:
                    if hasattr(result[0], 'usage'):
                        tracker.set_response(result[0])
                
                return result
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class TokenTracker:
    """
    Context manager for tracking token usage with timing.
    Now supports both sync and async usage.
    
    Usage:
        with TokenTracker() as tracker:
            # Make your API call
            response = openai_client.responses.create(...)
            tracker.set_response(response)
    """
    
    def __init__(
        self,
        db: Session,
        user_id: str,
        prompt_type: str,
        prompt_name: str,
        model_provider: str = "openai",
        **kwargs
    ):
        self.db = db
        self.user_id = user_id
        self.prompt_type = prompt_type
        self.prompt_name = prompt_name
        self.model_provider = model_provider
        self.kwargs = kwargs
        self.start_time = None
        self.response = None
        
    def __enter__(self):
        self.start_time = time.time()
        return self
        
    async def __aenter__(self):
        self.start_time = time.time()
        return self
        
    def set_response(self, response):
        """Set the API response for token extraction"""
        self.response = response
        
    def _track_usage(self, exc_type=None, exc_val=None):
        """Common tracking logic for both sync and async"""
        end_time = time.time()
        response_time_ms = (end_time - self.start_time) * 1000
        
        # Filter out model_name from kwargs to avoid duplicate parameter error
        filtered_kwargs = {k: v for k, v in self.kwargs.items() if k != 'model_name'}
        
        try:
            if exc_type is not None:
                # An error occurred
                track_prompt_usage(
                    db=self.db,
                    user_id=self.user_id,
                    prompt_type=self.prompt_type,
                    prompt_name=self.prompt_name,
                    model_name=self.kwargs.get('model_name', 'unknown'),
                    model_provider=self.model_provider,
                    input_tokens=0,
                    output_tokens=0,
                    response_time_ms=response_time_ms,
                    error_message=str(exc_val),
                    **filtered_kwargs
                )
            elif self.response:
                # Extract token usage from response
                if hasattr(self.response, 'usage'):
                    # OpenAI response
                    track_prompt_usage(
                        db=self.db,
                        user_id=self.user_id,
                        prompt_type=self.prompt_type,
                        prompt_name=self.prompt_name,
                        model_name=getattr(self.response, 'model', self.kwargs.get('model_name', 'unknown')),
                        model_provider=self.model_provider,
                        input_tokens=self.response.usage.input_tokens,
                        output_tokens=self.response.usage.output_tokens,
                        response_time_ms=response_time_ms,
                        **filtered_kwargs
                    )
                elif hasattr(self.response, 'usage') and self.model_provider == "anthropic":
                    # Anthropic response
                    track_prompt_usage(
                        db=self.db,
                        user_id=self.user_id,
                        prompt_type=self.prompt_type,
                        prompt_name=self.prompt_name,
                        model_name=self.kwargs.get('model_name', 'claude'),
                        model_provider=self.model_provider,
                        input_tokens=self.response.usage.input_tokens,
                        output_tokens=self.response.usage.output_tokens,
                        response_time_ms=response_time_ms,
                        **filtered_kwargs
                    )
        except Exception as e:
            logger.error(f"Error tracking token usage: {str(e)}")
            # Don't raise - we don't want tracking failures to break the main flow
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._track_usage(exc_type, exc_val)
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._track_usage(exc_type, exc_val) 