"""
Token Calculator Utility
Calculates input/output token costs by model and applies service multipliers
"""

from app.config.llm_pricing import LLM_MODEL_PRICING, DEFAULT_MODEL
from app.config.service_multipliers import get_service_multiplier
from typing import Dict, Any


class TokenCalculator:
    """
    Calculator for LLM token costs with service-specific multipliers
    """
    
    @staticmethod
    def calculate_service_cost(
        service_name: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int
    ) -> Dict[str, Any]:
        """
        Calculate total cost for a service using LLM
        
        Args:
            service_name: Name of the service (e.g., "blog_generation")
            model_name: LLM model name (e.g., "gpt-4o")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Dict with complete cost breakdown
        """
        # Get model pricing
        if model_name not in LLM_MODEL_PRICING:
            raise ValueError(f"Model '{model_name}' not found in LLM_MODEL_PRICING. Available models: {list(LLM_MODEL_PRICING.keys())}")
        
        model_pricing = LLM_MODEL_PRICING[model_name]
        
        # Calculate base API costs - handle different pricing structures
        if "credits_per_1k" in model_pricing:
            # Winston AI credit-based pricing - input_tokens represents credits used
            api_cost = (input_tokens / 1000) * model_pricing["credits_per_1k"]
            input_cost = api_cost
            output_cost = 0  # Winston AI doesn't separate input/output
        else:
            # Traditional token-based pricing (OpenAI, Anthropic)
            input_cost = (input_tokens / 1000) * model_pricing["input_per_1k"]
            output_cost = (output_tokens / 1000) * model_pricing["output_per_1k"]
            api_cost = input_cost + output_cost
        
        # Get service multiplier
        service_config = get_service_multiplier(service_name)
        service_multiplier = service_config["multiplier"]
        
        # Calculate final charge
        final_charge = api_cost * service_multiplier
        
        return {
            "service_name": service_name,
            "service_category": service_config["category"],
            "service_description": service_config["description"],
            "model_name": model_name,
            "provider": model_pricing["provider"],
            "token_usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens
            },
            "cost_breakdown": {
                "input_cost_usd": input_cost,
                "output_cost_usd": output_cost,
                "api_cost_usd": api_cost,
                "service_multiplier": service_multiplier,
                "final_charge_usd": final_charge
            },
            "pricing_details": {
                **({
                    "model_input_per_1k": model_pricing["input_per_1k"],
                    "model_output_per_1k": model_pricing["output_per_1k"]
                } if "input_per_1k" in model_pricing else {
                    "model_credits_per_1k": model_pricing["credits_per_1k"]
                }),
                "service_multiplier": service_multiplier
            }
        }
    
    @staticmethod
    def estimate_cost(
        service_name: str,
        model_name: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int
    ) -> Dict[str, Any]:
        """
        Estimate cost before making API call
        
        Args:
            service_name: Name of the service
            model_name: LLM model name
            estimated_input_tokens: Estimated input tokens
            estimated_output_tokens: Estimated output tokens
            
        Returns:
            Dict with cost estimation
        """
        return TokenCalculator.calculate_service_cost(
            service_name=service_name,
            model_name=model_name,
            input_tokens=estimated_input_tokens,
            output_tokens=estimated_output_tokens
        )
    
    @staticmethod
    def get_service_pricing_info(service_name: str) -> Dict[str, Any]:
        """
        Get pricing information for a specific service
        
        Args:
            service_name: Name of the service
            
        Returns:
            Dict with service pricing info
        """
        service_config = get_service_multiplier(service_name)
        
        # Calculate costs for different models with sample tokens
        sample_tokens = {"input": 1000, "output": 500}
        model_costs = {}
        
        for model_name in LLM_MODEL_PRICING.keys():
            cost = TokenCalculator.calculate_service_cost(
                service_name=service_name,
                model_name=model_name,
                input_tokens=sample_tokens["input"],
                output_tokens=sample_tokens["output"]
            )
            model_costs[model_name] = {
                "api_cost": cost["cost_breakdown"]["api_cost_usd"],
                "final_charge": cost["cost_breakdown"]["final_charge_usd"],
                "provider": cost["provider"]
            }
        
        return {
            "service_name": service_name,
            "service_config": service_config,
            "sample_calculation": {
                "input_tokens": sample_tokens["input"],
                "output_tokens": sample_tokens["output"],
                "model_costs": model_costs
            }
        }
    
    @staticmethod
    def compare_models_for_service(
        service_name: str,
        input_tokens: int,
        output_tokens: int
    ) -> Dict[str, Any]:
        """
        Compare costs across different models for a service
        
        Args:
            service_name: Name of the service
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Dict with model comparison
        """
        comparisons = {}
        
        for model_name in LLM_MODEL_PRICING.keys():
            cost = TokenCalculator.calculate_service_cost(
                service_name=service_name,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
            
            comparisons[model_name] = {
                "provider": cost["provider"],
                "api_cost": cost["cost_breakdown"]["api_cost_usd"],
                "final_charge": cost["cost_breakdown"]["final_charge_usd"],
                "cost_per_token": cost["cost_breakdown"]["final_charge_usd"] / cost["token_usage"]["total_tokens"]
            }
        
        # Sort by final charge
        sorted_models = sorted(
            comparisons.items(),
            key=lambda x: x[1]["final_charge"]
        )
        
        return {
            "service_name": service_name,
            "token_usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens
            },
            "model_comparison": dict(sorted_models),
            "cheapest_model": sorted_models[0][0] if sorted_models else None,
            "most_expensive_model": sorted_models[-1][0] if sorted_models else None
        }
