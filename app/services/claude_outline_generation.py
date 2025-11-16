from typing import Dict, List, Optional
import anthropic
import logging
import json
from sqlalchemy.orm import Session
from app.core.config import settings
from app.services.country_service import CountryService
from app.services.enhanced_llm_usage_service import EnhancedLLMUsageService
from app.prompts.blogGenerator.claude_outline_prompt import get_claude_system_prompt, get_claude_user_prompt

class ClaudeOutlineGenerationService:
    def __init__(self, db: Session, user_id: str, project_id: Optional[str] = None):
        self.db = db
        self.user_id = user_id
        self.project_id = project_id
        self.logger = logging.getLogger(__name__)
        
        # Initialize Anthropic SDK client
        self.client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )
        
        # Initialize enhanced LLM usage service for billing
        self.llm_usage_service = EnhancedLLMUsageService(db)

    def _get_search_region(self, converted_country: str) -> str:
        """Get web search region from converted country name"""
        # Return the full country name for Claude API region parameter
        # Claude API expects country names, not country codes
        self.logger.info(f"Using region '{converted_country}' for country '{converted_country}'")
        return converted_country

    def parse_outline_to_json(self, outline_text: str) -> Dict:
        """Parse Claude response text to JSON structure"""
        try:
            # If input is already a dictionary, return it directly
            if isinstance(outline_text, dict):
                return outline_text

            # Remove escape characters and clean the text
            cleaned_text = outline_text.replace('\\n', '').replace('\\"', '"').strip()
            
            # Parse the cleaned text as JSON
            try:
                outline_json = json.loads(cleaned_text)
            except json.JSONDecodeError:
                # If direct parsing fails, try to parse with extra cleaning
                try:
                    outline_json = json.loads(cleaned_text.replace('\n', '').replace('  ', ' '))
                except json.JSONDecodeError:
                    # Last resort: return a minimal valid structure
                    outline_json = {
                        "sections": [],
                        "conclusion": "",
                        "faqs": []
                    }

            # Ensure the structure has the required keys
            if not isinstance(outline_json, dict):
                outline_json = {
                    "sections": [],
                    "conclusion": "",
                    "faqs": []
                }

            # Validate and clean the structure
            if "sections" not in outline_json:
                outline_json["sections"] = []
            if "conclusion" not in outline_json:
                outline_json["conclusion"] = ""
            if "faqs" not in outline_json:
                outline_json["faqs"] = []

            return outline_json

        except Exception as e:
            self.logger.error(f"Unexpected error parsing outline JSON: {str(e)}")
            return {
                "sections": [],
                "conclusion": "",
                "faqs": []
            }

    def generate_blog_outline_claude(
        self,
        blog_title: str,
        primary_keyword: str,
        secondary_keywords: List[str],
        keyword_intent: str,
        industry: str,
        word_count: str,
        country: str,
        category: str,
        subcategory: str,
        project_id: str,
        project: Dict
    ) -> Dict:
        """Generate SEO-optimized blog outline using Claude Opus."""
        try:
            # Update project_id if provided
            if project_id:
                self.project_id = project_id

            # Convert country code to full country name
            converted_country = CountryService.get_country_name(country)

            # Get system and user prompts
            system_prompt = get_claude_system_prompt()
            user_prompt = get_claude_user_prompt(
                blog_title=blog_title,
                primary_keyword=primary_keyword,
                secondary_keywords=secondary_keywords,
                keyword_intent=keyword_intent,
                industry=industry,
                word_count=word_count,
                country=converted_country,
                category=category,
                subcategory=subcategory,
                project=project
            )

            # Map country to region for web search  
            search_region = self._get_search_region(converted_country)

            # Call Claude Opus API using Anthropic SDK with streaming
            
            with self.client.beta.messages.stream(
                model="claude-haiku-4-5-20251001",  # Updated model name
                max_tokens=20000,
                temperature=1,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_prompt
                            }
                        ]
                    }
                ],
                tools=[
                    {
                        "name": "web_search",
                        "type": "web_search_20250305",
                        "user_location": {
                            "type": "approximate",
                            "region": search_region
                        }
                    }
                ],
                thinking={
                    "type": "enabled",
                    "budget_tokens": 16000
                },
                betas=["web-search-2025-03-05"]  # SDK way to enable beta features
            ) as stream:
                # Collect the complete message from stream
                message = stream.get_final_message()
            
            # Convert SDK response to dict format for existing code compatibility
            response_data = {
                "content": [block.model_dump() for block in message.content],
                "usage": {
                    "input_tokens": message.usage.input_tokens,
                    "output_tokens": message.usage.output_tokens
                },
                "model": message.model,
                "id": message.id,
                "role": message.role,
                "type": message.type
            }
            
            # Extract exact token counts for usage recording
            claude_input_tokens = response_data.get("usage", {}).get("input_tokens", 0)
            claude_output_tokens = response_data.get("usage", {}).get("output_tokens", 0)
            
            # Record LLM usage with billing
            outline_metadata = {
                "outline_generation": {
                    "blog_title": blog_title,
                    "primary_keyword": primary_keyword,
                    "category": category,
                    "subcategory": subcategory,
                    "word_count": word_count,
                    "country": converted_country,
                    "model": "claude-haiku-4-5-20251001",
                    "claude_raw_usage": response_data.get("usage", {})
                }
            }
            
            result = self.llm_usage_service.record_llm_usage(
                user_id=self.user_id,
                service_name="outline_generation",
                model_name="claude-haiku-4-5-20251001",
                input_tokens=claude_input_tokens,
                output_tokens=claude_output_tokens,
                service_description="Blog outline generation using Claude Opus",
                project_id=self.project_id,
                additional_metadata=outline_metadata
            )
            
            # Extract ONLY the final response text (skip thinking blocks)
            outline_text = ""
            content_blocks = response_data.get("content", [])
            
            for content_block in content_blocks:
                block_type = content_block.get("type", "unknown")
                
                # Only process text blocks, skip thinking blocks
                if block_type == "text":
                    text_content = content_block.get("text", "")
                    outline_text += text_content
            
            if not outline_text:
                raise ValueError("No text content found in Claude response")
            
            # Parse outline to JSON
            try:
                # First try direct JSON parsing
                outline_json = json.loads(outline_text)
            except json.JSONDecodeError:
                # If direct JSON parsing fails, try to extract JSON from text
                import re
                
                # Remove ```json and ``` wrappers if present
                cleaned_text = outline_text.strip()
                if cleaned_text.startswith('```json'):
                    cleaned_text = cleaned_text[7:]  # Remove ```json
                if cleaned_text.endswith('```'):
                    cleaned_text = cleaned_text[:-3]  # Remove ```
                cleaned_text = cleaned_text.strip()
                
                try:
                    outline_json = json.loads(cleaned_text)
                except json.JSONDecodeError:
                    # Look for JSON-like content between {{ }}
                    json_match = re.search(r'\{(.*)\}', cleaned_text, re.DOTALL)
                    if json_match:
                        try:
                            extracted_json = '{' + json_match.group(1) + '}'
                            outline_json = json.loads(extracted_json)
                        except json.JSONDecodeError:
                            # If still no luck, fall back to text parsing
                            outline_json = self.parse_outline_to_json(outline_text)
                    else:
                        # If still no luck, fall back to text parsing
                        outline_json = self.parse_outline_to_json(outline_text)
            
            return {
                "status": "success",
                "outline": outline_json,
                "project_id": project_id,
                "raw_response": outline_text  # Raw Claude response text
            }

        except Exception as e:
            self.logger.error(f"Error generating Claude outline: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }