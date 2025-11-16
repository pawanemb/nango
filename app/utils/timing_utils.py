"""
Utility functions for tracking execution time and performance metrics.
"""

import json
import logging
from datetime import datetime
import pytz
from app.core.redis_client import get_redis_client

logger = logging.getLogger("fastapi_app")

def blogging_execution_time(blog_id, start_time, end_time, step_name):
    """
    Update the timing information for a specific stage of blog generation.
    
    Args:
        blog_id (str): The ID of the blog
        start_time (datetime): Start time of the operation
        end_time (datetime): End time of the operation
        step_name (str): Name of the generation stage (e.g., 'word_count', 'intro', 'section1')
    """
    redis_client = get_redis_client()
    if redis_client is not None:
        redis_key = f"blog_timing:{blog_id}"
        existing_data = redis_client.get(redis_key)
        if existing_data:
            existing_data = json.loads(existing_data)
            existing_data[f"start_time_{step_name}"] = start_time.isoformat()
            existing_data[f"end_time_{step_name}"] = end_time.isoformat()
            existing_data[f"execution_time_{step_name}"] = (end_time - start_time).total_seconds()
            redis_client.set(redis_key, json.dumps(existing_data, default=str))
    logger.info(f"Added the {step_name} execution time to redis")


def extract_token_usage(response):
    """
    Extract token usage information from an OpenAI API response.
    
    Args:
        response: The OpenAI API response object
        
    Returns:
        dict: A dictionary containing token usage information:
            - total_tokens: Total number of tokens used
            - prompt_tokens: Number of tokens in the prompt (input)
            - completion_tokens: Number of tokens in the completion (output)
            - estimated_cost_usd: Estimated cost in USD based on current pricing
    """
    # Extract token usage information
    total_tokens = response.usage.total_tokens
    prompt_tokens = response.usage.input_tokens
    completion_tokens = response.usage.output_tokens
    
    # Calculate approximate cost (based on o1 pricing as of March 2025)
    # Note: These rates may change, so update as needed
    input_cost_per_1k = 0.015  # $15 per 1M input tokens ($0.015 per 1K)
    output_cost_per_1k = 0.060  # $60 per 1M output tokens ($0.060 per 1K)
    
    input_cost = (prompt_tokens / 1000) * input_cost_per_1k
    output_cost = (completion_tokens / 1000) * output_cost_per_1k
    total_cost = input_cost + output_cost
    
    # Return token usage information
    return {
        "total_tokens": total_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "estimated_cost_usd": total_cost
    }


def store_token_usage(blog_id, step_name, token_usage):
    """
    Store token usage information in Redis.
    
    Args:
        blog_id (str): The ID of the blog
        step_name (str): Name of the generation step (e.g., 'step1', 'wc1')
        token_usage (dict): Token usage information from extract_token_usage
    """
    redis_client = get_redis_client()
    if redis_client is not None:
        redis_key = f"blog_timing:{blog_id}"
        existing_data = redis_client.get(redis_key)
        if existing_data:
            existing_data = json.loads(existing_data)
            existing_data[f"tokens_{step_name}_total"] = token_usage["total_tokens"]
            existing_data[f"tokens_{step_name}_input"] = token_usage["prompt_tokens"]
            existing_data[f"tokens_{step_name}_output"] = token_usage["completion_tokens"]
            existing_data[f"tokens_{step_name}_cost"] = token_usage["estimated_cost_usd"]
            redis_client.set(redis_key, json.dumps(existing_data, default=str))
    logger.info(f"Added token usage for {step_name} to Redis - Total: {token_usage['total_tokens']}, Cost: ${token_usage['estimated_cost_usd']:.6f}")
