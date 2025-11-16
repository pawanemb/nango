"""
📝 Simple Custom Source Text Service - Direct Text Processing
Clean implementation: Validate Text → OpenAI Analysis → Return Information List
"""

from typing import Dict, Any, List
import asyncio
import time
from sqlalchemy.orm import Session
from app.core.logging_config import logger
from app.services.add_custom_source_text_prompt import AddCustomSourceTextPrompt
from app.core.config import settings
from openai import AsyncOpenAI
from app.services.enhanced_llm_usage_service import EnhancedLLMUsageService
import json
import re
from datetime import datetime

class AddCustomSourceTextService:
    """Simple service for direct text processing with OpenAI"""
    
    def __init__(self, db: Session, user_id: str, project_id: str):
        self.db = db
        self.user_id = user_id
        self.project_id = project_id
        
        # No scraper needed for text processing
        
        # Initialize OpenAI client
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Initialize enhanced LLM usage service for billing
        self.llm_usage_service = EnhancedLLMUsageService(db)
        
        logger.info(f"📝 AddCustomSourceTextService initialized for user {user_id}")
    
    async def process_text_source(self, text_content: str, blog_id: str, heading: str = None, subsection: str = None, source_name: str = None) -> Dict[str, Any]:
        """Process Text: Validate → OpenAI → Return information list"""
        
        start_time = time.time()
        
        try:
            # 🚀 STEP 1: Validate Text Content
            logger.info(f"📝 Starting text content processing")
            
            if not text_content or not text_content.strip():
                return {
                    "success": False,
                    "error": "Text content cannot be empty"
                }
            
            text_content = text_content.strip()
            content_length = len(text_content)
            
            if content_length < 50:
                return {
                    "success": False,
                    "error": "Text content too short. Please provide at least 50 characters of meaningful content."
                }
            
            if content_length > 5000:  # 5K character limit
                return {
                    "success": False,
                    "error": "Text content too long. Please limit to 5,000 characters."
                }
            
            logger.info(f"✅ Text content validated: {content_length} characters")
            
            # 🚀 STEP 2: Process with OpenAI
            logger.info("🤖 Processing text content with OpenAI")
            
            openai_result = await self._process_content_with_openai(
                content=text_content,
                source_name=source_name or "Custom Text Source",
                heading=heading,
                subsection=subsection
            )
            
            if not openai_result["success"]:
                # Pass through the original error details for "No information found"
                if openai_result.get('error') == 'No information found':
                    return {
                        "success": False,
                        "error": openai_result.get('error'),
                        "raw_response": openai_result.get('raw_response', '')
                    }
                else:
                    return {
                        "success": False,
                        "error": f"OpenAI processing failed: {openai_result.get('error', 'Unknown AI error')}"
                    }
            
            processing_time = time.time() - start_time
            
            # 🚀 STEP 3: Format Final Result
            return {
                "success": True,
                "content_length": content_length,
                "parsed_response": openai_result.get("parsed_response", {}),
                "citation": openai_result.get("citation", f"Source: {source_name or 'Custom Text Source'}"),
                "processing_time": round(processing_time, 2),
                "ai_model": "gpt-4.1-2025-04-14",
                "input_tokens": openai_result.get("input_tokens", 0),
                "output_tokens": openai_result.get("output_tokens", 0),
                "total_tokens": openai_result.get("total_tokens", 0)
            }
            
        except Exception as e:
            logger.error(f"Error processing text source: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _process_content_with_openai(self, content: str, source_name: str, heading: str = None, subsection: str = None) -> Dict[str, Any]:
        """Process text content with OpenAI using custom source text prompt"""
        
        try:
            # Get system and user prompts from text prompt file
            system_prompt = AddCustomSourceTextPrompt.get_system_prompt()
            user_prompt = AddCustomSourceTextPrompt.get_user_prompt(source_name, content, heading, subsection)

            # Make OpenAI API call
            response = await self.openai_client.chat.completions.create(
                model="gpt-4.1-2025-04-14",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=16384
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            # 🚀 RECORD USAGE IMMEDIATELY AFTER API CALL - BEFORE PARSING
            # This ensures we bill even if OpenAI returns "No information found"
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0
            
            logger.info("💰 BILLING: Recording usage regardless of response content")
            self._record_usage(
                source_name=source_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_name="gpt-4.1-2025-04-14"
            )
            
            # Extract content and clean markdown code blocks (same as streaming_sources_service.py)
            full_response = ai_response
            # Clean markdown code blocks (```json and ```) and normalize newlines
            cleaned_response = re.sub(r'```json\s*|```\s*', '', full_response).strip()
            
            # Parse JSON to return as proper object instead of string
            try:
                parsed_ai_response = json.loads(cleaned_response)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse AI response as JSON: {e}")
                logger.warning(f"Raw OpenAI response: '{cleaned_response}'")
                # Check if empty or "No information found"
                if not cleaned_response.strip() or cleaned_response.strip() == "No information found":
                    logger.info("OpenAI returned empty or 'No information found' - treating as error BUT ALREADY BILLED")
                    return {
                        "success": False,
                        "error": "No information found",
                        "raw_response": cleaned_response,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": response.usage.total_tokens if response.usage else 0
                    }
                parsed_ai_response = {"raw_response": cleaned_response, "parse_error": str(e)}
            
            logger.info(f"✅ OpenAI processed content: {len(full_response)} characters")
            
            return {
                "success": True,
                "parsed_response": parsed_ai_response,  # Parsed JSON response
                "citation": f"{source_name}",
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": response.usage.total_tokens if response.usage else 0
            }
            
        except Exception as e:
            logger.error(f"OpenAI processing error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _record_usage(self, source_name: str, input_tokens: int, output_tokens: int, model_name: str):
        """Record usage for custom text source processing"""
        try:
            logger.info("🔔 USAGE TRACKING STARTED - Custom Text Source Processing")
            logger.info(f"📊 RAW USAGE DATA:")
            logger.info(f"   📧 User ID: {self.user_id}")
            logger.info(f"   📝 Source: {source_name}")
            logger.info(f"   🤖 Model: {model_name}")
            logger.info(f"   📥 Input Tokens: {input_tokens}")
            logger.info(f"   📤 Output Tokens: {output_tokens}")
            logger.info(f"   📊 Total Tokens: {input_tokens + output_tokens}")
            logger.info(f"   🏢 Project ID: {self.project_id}")
            
            metadata = {
                "add_custom_source": {
                    "source_name": source_name,
                    "model": model_name,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "service_type": "text_processing_and_analysis"
                }
            }
            
            logger.info(f"📦 METADATA PREPARED: {metadata}")
            
            logger.info("🚀 CALLING EnhancedLLMUsageService.record_llm_usage()...")
            result = self.llm_usage_service.record_llm_usage(
                user_id=self.user_id,
                service_name="add_custom_source",  # New service name for text processing
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                service_description="Custom source text processing with AI analysis",
                project_id=self.project_id,
                additional_metadata=metadata
            )
            
            logger.info(f"✅ USAGE RECORDING SUCCESS!")
            logger.info(f"💰 BILLING RESULT: {result}")
            logger.info(f"🔔 USAGE TRACKING COMPLETED - Custom Text Source Processing")
            
        except Exception as e:
            logger.error(f"❌ USAGE TRACKING FAILED - Custom Text Source Processing")
            logger.error(f"🔥 ERROR DETAILS: {str(e)}")
            logger.error(f"📧 User ID: {self.user_id}")
            logger.error(f"📝 Source: {source_name}")
            logger.error(f"📊 Tokens: {input_tokens}/{output_tokens}")
            # Don't raise here to avoid breaking the main workflow
    
    def _create_simple_citation(self, source_name: str) -> str:
        """Create a simple citation for the text source"""
        return f"Source: {source_name} - Processed on {datetime.now().strftime('%Y-%m-%d')}"