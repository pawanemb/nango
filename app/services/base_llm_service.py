"""
Base service class for LLM-based services with automatic token tracking.
All services that make LLM API calls should inherit from this class.
"""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.utils.token_tracking import TokenTracker
from app.core.prompt_config import get_prompt_name
import logging

logger = logging.getLogger("fastapi_app")


class BaseLLMService:
    """
    Base class for services that make LLM API calls.
    Provides automatic token tracking and common functionality.
    """
    
    def __init__(
        self,
        db: Session,
        user_id: str,
        project_id: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the base service.
        
        Args:
            db: Database session
            user_id: ID of the user making requests
            project_id: Optional project ID for tracking
            **kwargs: Additional parameters
        """
        self.db = db
        self.user_id = user_id
        self.project_id = project_id
        self.extra_params = kwargs
        
    def track_llm_call(
        self,
        prompt_type: str,
        model_provider: str = "openai",
        prompt_name: Optional[str] = None,
        **kwargs
    ) -> TokenTracker:
        """
        Create a token tracker for an LLM API call.
        
        Args:
            prompt_type: Type of prompt from PromptType enum
            model_provider: Provider of the model (openai, anthropic, etc.)
            prompt_name: Optional custom prompt name (defaults to config)
            **kwargs: Additional tracking parameters
            
        Returns:
            TokenTracker instance to use as context manager
        """
        if not prompt_name:
            prompt_name = get_prompt_name(prompt_type)
            
        # Merge kwargs with instance parameters
        tracking_params = {
            "project_id": self.project_id,
            **self.extra_params,
            **kwargs
        }
        
        return TokenTracker(
            db=self.db,
            user_id=self.user_id,
            prompt_type=prompt_type,
            prompt_name=prompt_name,
            model_provider=model_provider,
            **tracking_params
        )
    
    def update_project_id(self, project_id: str):
        """Update the project ID for tracking"""
        self.project_id = project_id
        
    def update_user_id(self, user_id: str):
        """Update the user ID for tracking"""
        self.user_id = user_id 