"""
Utility functions for working with the Anthropic API.
"""

import tiktoken
import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger("fastapi_app")

# Claude models use cl100k_base tokenizer (same as GPT-4)
CLAUDE_TOKENIZER = tiktoken.get_encoding("cl100k_base")

# Current Claude pricing (as of April 2025)
CLAUDE_PRICING = {
    "claude-3-7-sonnet-20250219": {
        "input_per_1k": 0.003,  # $3 per 1M input tokens ($0.003 per 1K)
        "output_per_1k": 0.015,  # $15 per 1M output tokens ($0.015 per 1K)
    },
    "claude-3-5-sonnet-20240620": {
        "input_per_1k": 0.003,  # $0.003 per 1K input tokens
        "output_per_1k": 0.015,  # $0.015 per 1K output tokens
    },
    "claude-3-opus-20240229": {
        "input_per_1k": 0.015,  # $15 per 1M input tokens ($0.015 per 1K)
        "output_per_1k": 0.075,  # $75 per 1M output tokens ($0.075 per 1K)
    },
    "claude-3-haiku-20240307": {
        "input_per_1k": 0.0008,  # $0.80 per 1M input tokens ($0.0008 per 1K)
        "output_per_1k": 0.004,  # $4 per 1M output tokens ($0.004 per 1K)
    },
}

def count_tokens(text: str) -> int:
    """
    Count the number of tokens in a text string using Claude's tokenizer.
    
    Args:
        text (str): The text to count tokens for
        
    Returns:
        int: The number of tokens
    """
    return len(CLAUDE_TOKENIZER.encode(text))

def calculate_anthropic_token_usage(
    model: str, 
    system_prompt: str, 
    user_prompt: str, 
    output_text: str
) -> Dict[str, Any]:
    """
    Calculate token usage and cost for an Anthropic API call.
    
    Args:
        model (str): The Anthropic model used
        system_prompt (str): The system prompt
        user_prompt (str): The user prompt
        output_text (str): The generated output text
        
    Returns:
        dict: A dictionary containing token usage information:
            - total_tokens: Total number of tokens used
            - prompt_tokens: Number of tokens in the prompt (input)
            - completion_tokens: Number of tokens in the completion (output)
            - estimated_cost_usd: Estimated cost in USD based on current pricing
    """
    # Count tokens
    system_tokens = count_tokens(system_prompt) if system_prompt else 0
    user_tokens = count_tokens(user_prompt)
    output_tokens = count_tokens(output_text)
    
    # Calculate total tokens
    prompt_tokens = system_tokens + user_tokens
    total_tokens = prompt_tokens + output_tokens
    
    # Get pricing for the model
    model_pricing = CLAUDE_PRICING.get(model, CLAUDE_PRICING["claude-3-7-sonnet-20250219"])
    
    # Calculate cost
    input_cost = (prompt_tokens / 1000) * model_pricing["input_per_1k"]
    output_cost = (output_tokens / 1000) * model_pricing["output_per_1k"]
    total_cost = input_cost + output_cost
    
    logger.info(f"Anthropic token usage - Model: {model}, Input: {prompt_tokens}, Output: {output_tokens}, Cost: ${total_cost:.6f}")
    
    return {
        "total_tokens": total_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": output_tokens,
        "estimated_cost_usd": total_cost
    }
