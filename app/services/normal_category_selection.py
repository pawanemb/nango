from typing import Any, Dict, List, Optional
from datetime import datetime
import logging
import os
import json
from app.prompts.blogGenerator.category_prompty import generate_category_prompt
from openai import OpenAI
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.logging_config import logger
from app.models.project import Project
from app.db.session import get_db_session
from fastapi import HTTPException
from app.services.enhanced_llm_usage_service import EnhancedLLMUsageService

class CategorySelectionService:
    def __init__(self, 
                 db: Session,
                 user_id: str,
                 project_id: Optional[str] = None,
                 openai_api_key: Optional[str] = None, 
                 database_uri: Optional[str] = None):
        """
        Initialize CategorySelectionService.
        
        :param db: Database session
        :param user_id: User ID for tracking
        :param project_id: Project ID for tracking
        :param openai_api_key: OpenAI API key. If not provided, uses settings.
        :param database_uri: Optional database URI. If not provided, tries to get from settings or environment.
        """
        self.db = db
        self.user_id = user_id
        self.project_id = project_id
        self.openai_client = OpenAI(
            api_key=openai_api_key or getattr(settings, 'OPENAI_API_KEY', 
                                              os.getenv('OPENAI_API_KEY'))
        )
        self.logger = logger
        
        # Initialize enhanced LLM usage service for billing
        self.llm_usage_service = EnhancedLLMUsageService(db)
        
        # Database URI fallback mechanism
        if database_uri:
            self.database_uri = database_uri
        else:
            # Try multiple ways to get database URI
            self.database_uri = (
                getattr(settings, 'SQLALCHEMY_DATABASE_URI', None) or
                os.getenv('DATABASE_URL') or
                'postgresql://localhost/your_database'  # Fallback default
            )

    def generate_intent_prompt(self, keyword: str) -> str:
        """
        Generate prompt for determining keyword intent.
        
        :param keyword: Keyword to determine intent for
        :return: Formatted prompt string
        """
        prompt = f"""Act as an SEO expert with the proficient knowlege about keywords. Classify the given keyword into one of the following categories based on its search intent:

1. **Informational**: The keyword indicates the user is seeking information or answers to a specific question. Example: 'How to apply for a visa.'
2. **Navigational**: The keyword suggests the user is trying to find a specific website, brand, or entity. Example: 'Facebook login.'
3. **Transactional**: The keyword shows the user intends to perform a specific action, such as making a purchase or signing up for a service. Example: 'Buy iPhone 14 online.'
4. **Commercial**: The keyword reflects pre-purchase research where the user is comparing products, services, or brands. Example: 'Best laptops under $1000.'

**Classification Criteria**:
- Keywords with verbs like "how to," "guide," or "tips" → **Informational**.
- Keywords with a brand or website name directly → **Navigational**.
- Keywords with terms like "buy," "discount," or "book" → **Transactional**.
- Keywords with qualifiers like "best," "top," or "compare" → **Commercial**.

**Instruction**: Respond only with the full name of the intent -'Informational,' 'Navigational,' 'Transactional,' or 'Commercial'. Do not include anything else in your response.

**Keyword**: {keyword}"""

        return prompt


    def get_keyword_intent(self, keyword: str) -> str:
        """
        Get the intent classification for a keyword using OpenAI.
        
        :param keyword: Keyword to classify
        :return: Intent classification
        """
        try:
            prompt = self.generate_intent_prompt(keyword)
            
            # Make OpenAI API call
            response = self.openai_client.responses.create(
                model=settings.OPENAI_MODEL,
                 input=[
                    {"role": "system", "content": "You are an expert SEO specialist."},
                    {"role": "user", "content": prompt}
                ],
                temperature=settings.OPENAI_TEMPERATURE,
                max_output_tokens=settings.OPENAI_MAX_TOKENS
            )
            
            # Store usage data for combined tracking (will be recorded in workflow)
            self.keyword_intent_usage = {
                "model_name": response.model,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "metadata": {
                    "keyword": keyword,
                    "prompt_type": "keyword_intent_detection"
                }
            }
            
            intent = response.output_text.strip()
            if intent not in ["Informational", "Navigational", "Transactional", "Commercial"]:
                raise ValueError(f"Invalid intent classification: {intent}")
                
            return intent
            
        except Exception as e:
            self.logger.error(f"Error getting keyword intent: {str(e)}")
            raise

    def get_content_categories(
        self,
        intent: str,
        primary_keyword: str,
        secondary_keywords: List[str],
        project_id: str
    ) -> Dict:
        """
        Get content categories based on keyword and intent.
        
        :param intent: The search intent
        :param primary_keyword: The main keyword
        :param secondary_keywords: List of related keywords
        :param project_id: Project ID
        :return: Dictionary of content categories
        """
        try:
            # Update project_id if provided
            if project_id:
                self.project_id = project_id
                
            # Get project details
            project = None
            with get_db_session() as db:
                project = db.query(Project).filter(Project.id == project_id).first()
                if not project:
                    raise ValueError(f"Project not found with id: {project_id}")
                    
            # Use age_groups as target audience
            target_audience = ", ".join(project.age_groups) if project.age_groups else "general audience"
            # Use gender as target gender
            target_gender = project.gender if project.gender else "general audience"
                
            prompt = generate_category_prompt(
                primary_keyword=primary_keyword,
                intent=intent,
                secondary_keywords=secondary_keywords,
                target_audience=target_audience,
                target_gender=target_gender
            )
            
            # Make OpenAI API call
            response = self.openai_client.responses.create(
                model=settings.OPENAI_MODEL,
                 input=[
                    {"role": "system", "content": "You are an expert SEO content strategist."},
                    {"role": "user", "content": prompt}
                ],
                temperature=settings.OPENAI_TEMPERATURE,
                max_output_tokens=settings.OPENAI_MAX_TOKENS
            )
            
            # Store usage data for combined tracking (will be recorded in workflow)
            self.category_generation_usage = {
                "model_name": response.model,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "metadata": {
                    "primary_keyword": primary_keyword,
                    "intent": intent,
                    "target_audience": target_audience,
                    "target_gender": target_gender,
                    "prompt_type": "category_selection"
                }
            }
            
            categories_table = response.output_text.strip()
            
            return {
                "primary_keyword": primary_keyword,
                "intent": intent,
                "categories_table": categories_table
            }
        except ValueError as e:
            self.logger.error(f"Value error in get_content_categories: {str(e)}")
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            self.logger.error(f"Error in get_content_categories: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    def parse_categories_table(self, result: Dict) -> Dict:
        """
        Parse the categories table into a structured JSON format.
        
        :param result: The result dictionary containing the categories table
        :return: Structured categories dictionary
        """
        try:
            table_str = result["categories_table"]
            
            # Remove markdown code block markers and extract JSON
            json_str = table_str.replace("```json", "").replace("```", "").strip()
            
            # Parse the JSON response
            categories_data = json.loads(json_str)
            
            return {
                "primary_keyword": result["primary_keyword"],
                "intent": result["intent"],
                "categories": categories_data["categories"]
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing categories table: {str(e)}")
            raise

    def generate_category_selection_workflow(
        self,
        primary_keyword: str,
        secondary_keywords: List[str],
        intent: str,
        project_id: str
    ) -> Dict:
        """
        Complete category selection workflow.
        
        :param primary_keyword: Primary keyword
        :param secondary_keywords: List of secondary keywords
        :param intent: Search intent from payload
        :param project_id: Project identifier
        :return: Processed category selection results
        """
        try:
            # Initialize usage tracking variables
            self.category_generation_usage = None
            
            # Get content categories using provided intent
            categories_result = self.get_content_categories(
                intent=intent,
                primary_keyword=primary_keyword,
                secondary_keywords=secondary_keywords,
                project_id=project_id
            )
            
            # Record LLM usage with billing
            self._record_usage(project_id, primary_keyword, secondary_keywords, intent)
            
            # Parse categories table
            parsed_categories = self.parse_categories_table(categories_result)
            
            return parsed_categories
        
        except Exception as e:
            self.logger.error(f"Complete category selection workflow failed: {e}")
            raise
    
    def _record_usage(self, project_id: str, primary_keyword: str, secondary_keywords: List[str], intent: str):
        """
        Record usage from category generation call
        """
        try:
            if not self.category_generation_usage:
                self.logger.warning("Missing usage data for tracking")
                return
            
            # Use category generation usage data
            model_name = self.category_generation_usage["model_name"]
            input_tokens = self.category_generation_usage["input_tokens"]
            output_tokens = self.category_generation_usage["output_tokens"]
            
            # Simplified metadata
            metadata = {
                "category_selection": {
                    "call_type": "category_generation",
                    "model": model_name,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "intent": intent,
                    "primary_keyword": primary_keyword
                }
            }
            
            # Record usage
            self.llm_usage_service.record_llm_usage(
                user_id=self.user_id,
                service_name="category_selection",
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                service_description="Category selection workflow",
                project_id=project_id,
                additional_metadata=metadata
            )
            
        except Exception as e:
            self.logger.error(f"Failed to record usage: {e}")
            # Don't raise here to avoid breaking the main workflow
