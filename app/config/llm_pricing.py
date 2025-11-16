"""
LLM Model Pricing Configuration
Hardcoded pricing for different AI models with business markup
"""

# LLM Model pricing per 1000 tokens (in USD)
LLM_MODEL_PRICING = {
    "gpt-4o": {
        "input_per_1k": 0.0025,   # $2.5 per 1M tokens
        "output_per_1k": 0.010,  # $10 per 1M tokens
        "provider": "openai"
    },
    "chatgpt-4o-latest": {
        "input_per_1k": 0.005,   # $5 per 1M tokens (same as gpt-4o)
        "output_per_1k": 0.015,  # $15 per 1M tokens (same as gpt-4o)
        "provider": "openai"
    },
    "gpt-4o-mini-2024-07-18": {
        "input_per_1k": 0.00015,  # $0.15 per 1M tokens
        "output_per_1k": 0.0006,  # $0.60 per 1M tokens
        "provider": "openai"
    },
    "gpt-4.1-mini": {
        "input_per_1k": 0.00015,  # $0.15 per 1M tokens
        "output_per_1k": 0.0006,  # $0.60 per 1M tokens
        "provider": "openai"
    },
    "gpt-4o-mini-2024-07-18": {
        "input_per_1k": 0.00015,  # $0.15 per 1M tokens
        "output_per_1k": 0.0006,  # $0.60 per 1M tokens
        "provider": "openai"
    },
    "gpt-4": {
        "input_per_1k": 0.03,    # $30 per 1M tokens
        "output_per_1k": 0.06,   # $60 per 1M tokens
        "provider": "openai"
    },
    "gpt-4-turbo": {
        "input_per_1k": 0.01,    # $10 per 1M tokens
        "output_per_1k": 0.03,   # $30 per 1M tokens
        "provider": "openai"
    },
    "gpt-3.5-turbo": {
        "input_per_1k": 0.0005,  # $0.50 per 1M tokens
        "output_per_1k": 0.0015, # $1.50 per 1M tokens
        "provider": "openai"
    },
    "o1": {
        "input_per_1k": 0.015,   # $15 per 1M tokens
        "output_per_1k": 0.060,  # $60 per 1M tokens
        "provider": "openai"
    },
    "o1-mini": {
        "input_per_1k": 0.003,   # $3 per 1M tokens
        "output_per_1k": 0.012,  # $12 per 1M tokens
        "provider": "openai"
    },
    "claude-3-5-sonnet-20241022": {
        "input_per_1k": 0.003,   # $3 per 1M tokens
        "output_per_1k": 0.015,  # $15 per 1M tokens
        "provider": "anthropic"
    },
    "claude-3-opus": {
        "input_per_1k": 0.015,   # $15 per 1M tokens
        "output_per_1k": 0.075,  # $75 per 1M tokens
        "provider": "anthropic"
    },
    "claude-opus-4-20250514": {
        "input_per_1k": 0.015,   # $15 per 1M tokens
        "output_per_1k": 0.075,  # $75 per 1M tokens
        "provider": "anthropic"
    },
    "claude-opus-4-1": {
        "input_per_1k": 0.015,   # $15 per 1M tokens
        "output_per_1k": 0.075,  # $75 per 1M tokens
        "provider": "anthropic"
    },
    "claude-haiku-4-5-20251001": {
        "input_per_1k": 0.015,   # $15 per 1M tokens
        "output_per_1k": 0.075,  # $75 per 1M tokens
        "provider": "anthropic"
    },
    "claude-haiku-4-5-20251001": {
        "input_per_1k": 0.00025, # $0.25 per 1M tokens
        "output_per_1k": 0.00125, # $1.25 per 1M tokens
        "provider": "anthropic"
    },
    "claude-3-sonnet": {
        "input_per_1k": 0.003,   # $3 per 1M tokens
        "output_per_1k": 0.015,  # $15 per 1M tokens
        "provider": "anthropic"
    },
    "claude-3-haiku": {
        "input_per_1k": 0.00025, # $0.25 per 1M tokens
        "output_per_1k": 0.00125, # $1.25 per 1M tokens
        "provider": "anthropic"
    },
    "gpt-4.1-2025-04-14": {
        "input_per_1k": 0.002,   # $2 per 1M tokens (same as gpt-4o)
        "output_per_1k": 0.008,  # $8 per 1M tokens (same as gpt-4o)
        "provider": "openai"
    },
    "gpt-5": {
        "input_per_1k": 0.00125,   # $1.25 per 1M tokens (premium pricing)
        "output_per_1k": 0.010,  # $10 per 1M tokens (premium pricing) 
        "reasoning_per_1k": 0.010,  # $10 per 1M reasoning tokens (same as output)
        "provider": "openai"
    },
    "claude-3-7-sonnet-20250219": {
        "input_per_1k": 0.003,   # $3 per 1M tokens (same as claude-3-5-sonnet)
        "output_per_1k": 0.015,  # $15 per 1M tokens (same as claude-3-5-sonnet)
        "provider": "anthropic"
    },
    "winston-ai-plagiarism": {
        "credits_per_1k": 0.025,    # $250 per 10M tokens ($500 per 20M tokens)
        "provider": "winston-ai"
    }
}

# Business markup multiplier (5x markup)
BUSINESS_MARKUP_MULTIPLIER = 5.0

# Default model if not specified
DEFAULT_MODEL = "gpt-4o"


def calculate_llm_cost(model_name: str, input_tokens: int, output_tokens: int, reasoning_tokens: int = 0) -> dict:
    """
    Calculate LLM cost based on model and token usage
    
    Args:
        model_name: Name of the LLM model
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        reasoning_tokens: Number of reasoning tokens (GPT-5 only)
        
    Returns:
        Dict with cost breakdown and total charge
    """
    # Get model pricing
    if model_name not in LLM_MODEL_PRICING:
        raise ValueError(f"Model '{model_name}' not found in LLM_MODEL_PRICING. Available models: {list(LLM_MODEL_PRICING.keys())}")
    
    pricing = LLM_MODEL_PRICING[model_name]
    
    # Calculate base costs (API costs)
    input_cost = (input_tokens / 1000) * pricing["input_per_1k"]
    output_cost = (output_tokens / 1000) * pricing["output_per_1k"]
    
    # Calculate reasoning cost if applicable
    reasoning_cost = 0.0
    if reasoning_tokens > 0:
        if "reasoning_per_1k" in pricing:
            reasoning_cost = (reasoning_tokens / 1000) * pricing["reasoning_per_1k"]
        else:
            # Fallback: use output token rate for reasoning tokens
            reasoning_cost = (reasoning_tokens / 1000) * pricing["output_per_1k"]
    
    base_cost = input_cost + output_cost + reasoning_cost
    
    # Apply business markup
    actual_charge = base_cost * BUSINESS_MARKUP_MULTIPLIER
    
    # Build pricing per 1k info
    pricing_per_1k = {
        "input": pricing["input_per_1k"],
        "output": pricing["output_per_1k"]
    }
    if "reasoning_per_1k" in pricing:
        pricing_per_1k["reasoning"] = pricing["reasoning_per_1k"]

    return {
        "model_name": model_name,
        "provider": pricing["provider"],
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": input_tokens + output_tokens + reasoning_tokens,
        "input_cost_usd": input_cost,
        "output_cost_usd": output_cost,
        "reasoning_cost_usd": reasoning_cost,
        "base_cost_usd": base_cost,
        "markup_multiplier": BUSINESS_MARKUP_MULTIPLIER,
        "actual_charge_usd": actual_charge,
        "pricing_per_1k": pricing_per_1k
    }


def get_model_pricing(model_name: str = None) -> dict:
    """
    Get pricing information for a specific model or all models
    
    Args:
        model_name: Optional model name to get specific pricing
        
    Returns:
        Dict with pricing information
    """
    if model_name:
        if model_name in LLM_MODEL_PRICING:
            pricing = LLM_MODEL_PRICING[model_name].copy()
            pricing["markup_multiplier"] = BUSINESS_MARKUP_MULTIPLIER
            return pricing
        else:
            return None
    
    # Return all models with markup info
    all_pricing = {}
    for model, pricing in LLM_MODEL_PRICING.items():
        all_pricing[model] = pricing.copy()
        all_pricing[model]["markup_multiplier"] = BUSINESS_MARKUP_MULTIPLIER
    
    return all_pricing


def get_supported_models() -> list:
    """Get list of all supported model names"""
    return list(LLM_MODEL_PRICING.keys())


def get_models_by_provider(provider: str) -> list:
    """
    Get models filtered by provider
    
    Args:
        provider: Provider name ('openai' or 'anthropic')
        
    Returns:
        List of model names for the provider
    """
    return [
        model for model, pricing in LLM_MODEL_PRICING.items()
        if pricing["provider"] == provider
    ]
