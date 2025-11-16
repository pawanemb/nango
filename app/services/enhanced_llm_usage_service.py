"""
Enhanced LLM Usage Service
Integrates token calculator with usage tracking and billing
"""

from sqlalchemy.orm import Session
from app.services.usage_service import UsageService
from app.utils.token_calculator import TokenCalculator
from typing import Dict, Any, Optional
import json
from datetime import datetime


class EnhancedLLMUsageService:
    """
    Enhanced service for LLM usage tracking with service-specific multipliers
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.usage_service = UsageService(db)
        self.token_calculator = TokenCalculator()
    
    def record_llm_usage(
        self,
        user_id: str,
        service_name: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        service_description: str = None,
        reference_id: str = None,
        project_id: str = None,
        additional_metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Record LLM usage with service-specific pricing
        
        Args:
            user_id: User ID
            service_name: Service name (e.g., "blog_generation", "keyword_research")
            model_name: LLM model name (e.g., "gpt-4o")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            service_description: Description of what was done
            reference_id: External reference ID
            project_id: Project ID for usage tracking
            additional_metadata: Extra metadata to store
            
        Returns:
            Dict with usage record and billing info
        """
        try:
            # Calculate cost using token calculator
            cost_data = self.token_calculator.calculate_service_cost(
                service_name=service_name,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
            
            # Prepare usage metadata - store only essential LLM info
            usage_data = {
                "model": model_name,
                "provider": cost_data["provider"],
                "input_tokens": input_tokens,
                "output_tokens": output_tokens
            }
            
            # Add additional metadata if provided
            if additional_metadata:
                usage_data.update(additional_metadata)
            
            # Record usage through existing usage service
            result = self.usage_service.record_usage_and_charge(
                user_id=user_id,
                service_name=service_name,  # Use service name from multipliers config directly
                base_cost=cost_data["cost_breakdown"]["api_cost_usd"],  # Base cost before multiplier
                multiplier=cost_data["cost_breakdown"]["service_multiplier"],  # Multiplier used
                service_description=service_description or f"{service_name} using {model_name}",
                usage_data=usage_data,  # Pass as dict, will be JSON encoded in usage service
                reference_id=reference_id,
                project_id=project_id
            )
            
            # Add LLM-specific info to response
            if result["success"]:
                result.update({
                    "service_info": {
                        "service_name": service_name,
                        "service_category": cost_data["service_category"],
                        "service_description": cost_data["service_description"]
                    },
                    "llm_info": {
                        "model": model_name,
                        "provider": cost_data["provider"],
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": cost_data["token_usage"]["total_tokens"]
                    },
                    "cost_info": {
                        "api_cost_usd": cost_data["cost_breakdown"]["api_cost_usd"],
                        "service_multiplier": cost_data["cost_breakdown"]["service_multiplier"],
                        "final_charge_usd": cost_data["cost_breakdown"]["final_charge_usd"]
                    }
                })
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": "enhanced_llm_usage_error",
                "message": f"Failed to record enhanced LLM usage: {str(e)}"
            }
    
    def estimate_service_cost(
        self,
        service_name: str,
        model_name: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int
    ) -> Dict[str, Any]:
        """
        Estimate cost for a service before making API call
        
        Args:
            service_name: Service name
            model_name: LLM model name
            estimated_input_tokens: Estimated input tokens
            estimated_output_tokens: Estimated output tokens
            
        Returns:
            Dict with cost estimation
        """
        try:
            cost_data = self.token_calculator.estimate_cost(
                service_name=service_name,
                model_name=model_name,
                estimated_input_tokens=estimated_input_tokens,
                estimated_output_tokens=estimated_output_tokens
            )
            
            return {
                "success": True,
                "estimation": cost_data
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": "estimation_error",
                "message": f"Failed to estimate cost: {str(e)}"
            }
    
    def get_service_pricing_info(self, service_name: str) -> Dict[str, Any]:
        """
        Get pricing information for a specific service
        
        Args:
            service_name: Service name
            
        Returns:
            Dict with service pricing info
        """
        try:
            pricing_info = self.token_calculator.get_service_pricing_info(service_name)
            
            return {
                "success": True,
                "pricing_info": pricing_info
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": "pricing_info_error",
                "message": f"Failed to get pricing info: {str(e)}"
            }
    
    def compare_models_for_service(
        self,
        service_name: str,
        input_tokens: int,
        output_tokens: int
    ) -> Dict[str, Any]:
        """
        Compare costs across different models for a service
        
        Args:
            service_name: Service name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Dict with model comparison
        """
        try:
            comparison = self.token_calculator.compare_models_for_service(
                service_name=service_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
            
            return {
                "success": True,
                "comparison": comparison
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": "comparison_error",
                "message": f"Failed to compare models: {str(e)}"
            }
    
    def get_service_usage_history(
        self,
        user_id: str,
        service_name: str = None,
        model_name: str = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get user's service usage history with filtering
        
        Args:
            user_id: User ID
            service_name: Filter by specific service
            model_name: Filter by specific model
            limit: Number of records to return
            offset: Offset for pagination
            
        Returns:
            Dict with usage history
        """
        try:
            # Get usage history from existing service
            filter_service = f"llm_{service_name}" if service_name else None
            
            result = self.usage_service.get_user_usage_history(
                user_id=user_id,
                service_name=filter_service,
                limit=limit,
                offset=offset
            )
            
            if not result["success"]:
                return result
            
            # Filter and enhance records
            enhanced_records = []
            for record in result["usage_records"]:
                # Only include LLM services
                if not record["service_name"].startswith("llm_"):
                    continue
                
                # Parse usage data
                usage_data = record.get("usage_data", {})
                if isinstance(usage_data, dict):
                    # Filter by model if specified
                    if model_name and usage_data.get("llm_model") != model_name:
                        continue
                    
                    # Enhance record
                    enhanced_record = record.copy()
                    enhanced_record.update({
                        "service_info": {
                            "service_name": usage_data.get("service_name"),
                            "service_category": usage_data.get("service_category")
                        },
                        "llm_info": {
                            "model": usage_data.get("llm_model"),
                            "provider": usage_data.get("provider"),
                            "token_usage": usage_data.get("token_usage", {})
                        },
                        "cost_info": usage_data.get("cost_breakdown", {})
                    })
                    
                    enhanced_records.append(enhanced_record)
            
            return {
                "success": True,
                "enhanced_usage_records": enhanced_records,
                "total_records": len(enhanced_records)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": "history_error",
                "message": f"Failed to get usage history: {str(e)}"
            }
    
    def get_service_usage_stats(
        self,
        user_id: str,
        service_name: str = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get usage statistics for services
        
        Args:
            user_id: User ID
            service_name: Optional service filter
            days: Number of days to look back
            
        Returns:
            Dict with usage statistics
        """
        try:
            # Get usage history
            result = self.get_service_usage_history(
                user_id=user_id,
                service_name=service_name,
                limit=1000
            )
            
            if not result["success"]:
                return result
            
            records = result["enhanced_usage_records"]
            
            # Calculate statistics
            total_cost = sum(record["actual_charge"] for record in records)
            total_calls = len(records)
            
            # Group by service
            service_stats = {}
            model_stats = {}
            
            for record in records:
                service_info = record.get("service_info", {})
                llm_info = record.get("llm_info", {})
                
                service = service_info.get("service_name", "unknown")
                model = llm_info.get("model", "unknown")
                
                # Service stats
                if service not in service_stats:
                    service_stats[service] = {
                        "calls": 0,
                        "total_cost": 0,
                        "total_tokens": 0,
                        "category": service_info.get("service_category", "unknown")
                    }
                
                service_stats[service]["calls"] += 1
                service_stats[service]["total_cost"] += record["actual_charge"]
                
                token_usage = llm_info.get("token_usage", {})
                service_stats[service]["total_tokens"] += token_usage.get("total_tokens", 0)
                
                # Model stats
                if model not in model_stats:
                    model_stats[model] = {
                        "calls": 0,
                        "total_cost": 0,
                        "total_tokens": 0,
                        "provider": llm_info.get("provider", "unknown")
                    }
                
                model_stats[model]["calls"] += 1
                model_stats[model]["total_cost"] += record["actual_charge"]
                model_stats[model]["total_tokens"] += token_usage.get("total_tokens", 0)
            
            return {
                "success": True,
                "period_days": days,
                "summary": {
                    "total_calls": total_calls,
                    "total_cost_usd": total_cost,
                    "average_cost_per_call": total_cost / total_calls if total_calls > 0 else 0
                },
                "service_breakdown": service_stats,
                "model_breakdown": model_stats
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": "stats_error",
                "message": f"Failed to get usage stats: {str(e)}"
            }
