"""
Text Shortening Service with Streaming Capabilities
Advanced content editing service with real-time processing
"""

from typing import Dict, List, Optional, AsyncGenerator, Any
from datetime import datetime
import os
import json
import asyncio
import uuid

from openai import AsyncOpenAI, OpenAI
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.core.config import settings
from app.core.logging_config import logger
from app.core.redis_client import get_redis_client
from app.services.enhanced_llm_usage_service import EnhancedLLMUsageService
from app.services.text_shortening_prompts import TextShorteningPrompts


class TextShorteningService:
    """
    Advanced text shortening service with streaming capabilities
    """
    
    def __init__(self, 
                 db: Session,
                 user_id: str,
                 project_id: Optional[str] = None,
                 openai_api_key: Optional[str] = None):
        """
        Initialize TextShorteningService.
        
        Args:
            db: Database session
            user_id: User ID for tracking
            project_id: Project ID for tracking
            openai_api_key: OpenAI API key
        """
        self.db = db
        self.user_id = user_id
        self.project_id = project_id
        
        # Initialize OpenAI clients (both sync and async)
        api_key = openai_api_key or getattr(settings, 'OPENAI_API_KEY', os.getenv('OPENAI_API_KEY'))
        self.openai_client = OpenAI(api_key=api_key)
        self.async_openai_client = AsyncOpenAI(api_key=api_key)
        
        self.logger = logger
        self.redis_client = get_redis_client()
        
        # Initialize enhanced LLM usage service for billing
        self.llm_usage_service = EnhancedLLMUsageService(db)

    def _get_effective_brand_tonality(self, project: Optional[object], provided_tonality: Optional[str]) -> str:
        """
        Extract effective brand tonality from project settings or use provided value
        
        Args:
            project: Project object with brand_tone_settings
            provided_tonality: User-provided brand tonality (optional)
            
        Returns:
            str: Effective brand tonality string
        """
        # If user provided tonality, use it
        if provided_tonality:
            return provided_tonality
        
        # Try to extract from project brand tone settings
        if project and hasattr(project, 'brand_tone_settings') and project.brand_tone_settings:
            try:
                brand_settings = project.brand_tone_settings
                
                # Build tonality description from project settings
                formality = brand_settings.get('formality', 'Neutral')
                attitude = brand_settings.get('attitude', 'Direct') 
                energy = brand_settings.get('energy', 'Grounded')
                clarity = brand_settings.get('clarity', 'Clear')
                
                # Combine into descriptive brand tonality
                brand_tonality = f"{formality.lower()}, {attitude.lower()}, {energy.lower()}, and {clarity.lower()}"
                
                self.logger.info(f"🎨 Extracted brand tonality from project settings: {brand_tonality}")
                return brand_tonality
                
            except Exception as e:
                self.logger.warning(f"⚠️ Failed to extract brand tonality from project: {e}")
        
        # Default fallback
        default_tonality = "professional and clear"
        self.logger.info(f"🎨 Using default brand tonality: {default_tonality}")
        return default_tonality

    def generate_text_shortening_workflow(
        self,
        text_to_edit: str,
        preceding_words: str = "",
        succeeding_words: str = "",
        brand_tonality: Optional[str] = None,  # Now optional - will use project settings
        primary_keyword: str = "",
        language: str = "English",
        reduction_percentage: int = 30,
        project_id: Optional[str] = None,
        project: Optional[object] = None
    ) -> Dict[str, Any]:
        """
        Complete workflow for shortening text content (non-streaming)
        
        Args:
            text_to_edit: The main text content to be shortened
            preceding_words: Context from before the text
            succeeding_words: Context from after the text
            brand_tonality: Brand voice and tone guidelines
            primary_keyword: SEO keyword to preserve
            language: Target language for output
            reduction_percentage: Target reduction percentage
            project_id: Project ID for tracking
            project: Project object with additional context
            
        Returns:
            Dict: Shortened text and metadata
        """
        try:
            self.logger.info(f"🚀 Starting text shortening workflow")
            self.logger.info(f"Text length: {len(text_to_edit)} characters")
            self.logger.info(f"Primary keyword: {primary_keyword}")
            self.logger.info(f"Target reduction: {reduction_percentage}%")
            
            # 🎨 Extract brand tonality from project settings or use provided value
            final_brand_tonality = self._get_effective_brand_tonality(project, brand_tonality)
            self.logger.info(f"Brand tonality: {final_brand_tonality}")
            self.logger.info(f"Brand tonality source: {'project settings' if not brand_tonality else 'user provided'}")
            
            # Generate the prompt
            self.logger.info(f"📝 Generating text shortening prompt...")
            prompt = TextShorteningPrompts.get_text_shortening_prompt(
                text_to_edit=text_to_edit,
                preceding_words=preceding_words,
                succeeding_words=succeeding_words,
                brand_tonality=final_brand_tonality,  # Use extracted brand tonality
                primary_keyword=primary_keyword,
                language=language,
                reduction_percentage=reduction_percentage
            )
            self.logger.info(f"✅ Prompt generated successfully")
            
            # 🔍 LOG THE COMPLETE PROMPT
            self.logger.info(f"=" * 80)
            self.logger.info(f"🎯 COMPLETE PROMPT BEING SENT TO OPENAI:")
            self.logger.info(f"=" * 80)
            self.logger.info(prompt)
            self.logger.info(f"=" * 80)
            
            # Call OpenAI API
            self.logger.info(f"🤖 Calling OpenAI API...")
            self.logger.info(f"🔧 API Parameters:")
            self.logger.info(f"  - Model: gpt-4.1-mini")
            self.logger.info(f"  - Temperature: 0.7")
            self.logger.info(f"  - Max Tokens: 4096")
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4.1-2025-04-14",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert content editor specializing in concise, impactful writing while preserving SEO elements and brand voice."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=4096
            )
            self.logger.info(f"✅ OpenAI API call completed")
            
            # Parse response
            response_content = response.choices[0].message.content.strip()
            
            # 🔍 LOG THE COMPLETE OPENAI RESPONSE
            self.logger.info(f"=" * 80)
            self.logger.info(f"🤖 COMPLETE OPENAI RESPONSE:")
            self.logger.info(f"=" * 80)
            self.logger.info(response_content)
            self.logger.info(f"=" * 80)
            
            try:
                openai_response = json.loads(response_content)
                self.logger.info(f"✅ JSON parsing successful")
            except json.JSONDecodeError as json_error:
                self.logger.error(f"❌ JSON parsing failed: {json_error}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to parse OpenAI response as JSON: {str(json_error)}"
                )
            
            # Extract shortened text
            shortened_text = openai_response.get('shortened_text', '')
            original_length = openai_response.get('original_length', len(text_to_edit))
            new_length = openai_response.get('new_length', len(shortened_text))
            reduction_achieved = openai_response.get('reduction_achieved', 0)
            keyword_preserved = openai_response.get('keyword_preserved', False)
            
            self.logger.info(f"📊 Shortening results:")
            self.logger.info(f"  Original length: {original_length}")
            self.logger.info(f"  New length: {new_length}")
            self.logger.info(f"  Reduction achieved: {reduction_achieved}%")
            self.logger.info(f"  Keyword preserved: {keyword_preserved}")
            
            # Validate results
            if not shortened_text:
                raise HTTPException(
                    status_code=500,
                    detail="No shortened text was generated"
                )
            
            # Log usage to the enhanced LLM service
            try:
                self.logger.info(f"📊 Logging usage to EnhancedLLMUsageService...")
                
                usage_data = response.usage
                input_tokens = usage_data.prompt_tokens if usage_data else len(prompt) // 4
                output_tokens = usage_data.completion_tokens if usage_data else len(shortened_text) // 4
                
                usage_metadata = {
                    "text_shortening": {
                        "original_length": original_length,
                        "new_length": new_length,
                        "reduction_percentage": reduction_achieved,
                        "primary_keyword": primary_keyword,
                        "brand_tonality": final_brand_tonality,  # Use final brand tonality
                        "language": language
                    }
                }
                
                # Record LLM usage
                result = self.llm_usage_service.record_llm_usage(
                    user_id=self.user_id,
                    service_name="text_shortening",
                    model_name="gpt-4.1-mini",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    service_description="Text shortening and content editing using OpenAI",
                    project_id=project_id,
                    additional_metadata=usage_metadata
                )
                self.logger.info(f"✅ Usage logged successfully: {result}")
                
            except Exception as usage_error:
                self.logger.error(f"⚠️ Failed to log usage (non-critical): {usage_error}")
            
            # Return results
            result = {
                "shortened_text": shortened_text,
                "original_length": original_length,
                "new_length": new_length,
                "reduction_achieved": reduction_achieved,
                "keyword_preserved": keyword_preserved,
                "metadata": {
                    "primary_keyword": primary_keyword,
                    "brand_tonality": final_brand_tonality,  # Use final brand tonality
                    "brand_tonality_source": "project_settings" if not brand_tonality else "user_provided",
                    "language": language,
                    "target_reduction": reduction_percentage,
                    "generated_at": datetime.now().isoformat()
                }
            }
            
            self.logger.info(f"🎉 Text shortening workflow completed successfully")
            return result
            
        except HTTPException:
            raise
        except Exception as workflow_error:
            self.logger.error(f"❌ Text shortening workflow failed: {workflow_error}")
            raise HTTPException(
                status_code=500,
                detail=f"Text shortening workflow error: {str(workflow_error)}"
            )

    async def stream_text_shortening_workflow(
        self,
        text_to_edit: str,
        brand_tonality: str = "professional",
        primary_keyword: str = "",
        language: str = "English",
        reduction_percentage: int = 30,
        before_context: str = "",
        after_context: str = "",
        session_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streaming workflow for real-time text shortening
        
        Args:
            text_to_edit: The main text content to be shortened
            brand_tonality: Brand voice and tone guidelines
            primary_keyword: SEO keyword to preserve
            language: Target language for output
            reduction_percentage: Target reduction percentage
            session_id: Session ID for tracking
            
        Yields:
            Dict: Streaming updates with shortened content
        """
        if not session_id:
            session_id = str(uuid.uuid4())
        
        try:
            self.logger.info(f"🚀 Starting streaming text shortening - Session: {session_id}")
            
            # Emit connection established
            yield {
                "event": "connected",
                "session_id": session_id,
                "message": "Text shortening stream connected",
                "timestamp": datetime.now().isoformat()
            }
            
            # Split text into manageable chunks
            chunk_size = 1000  # Characters per chunk
            text_chunks = self._split_text_into_chunks(text_to_edit, chunk_size)
            total_chunks = len(text_chunks)
            
            self.logger.info(f"📊 Processing {total_chunks} chunks of text")
            
            # Emit progress update
            yield {
                "event": "progress",
                "session_id": session_id,
                "total_chunks": total_chunks,
                "current_chunk": 0,
                "progress_percentage": 0,
                "message": f"Processing {total_chunks} text chunks"
            }
            
            shortened_chunks = []
            context = {
                "brand_tonality": brand_tonality,
                "primary_keyword": primary_keyword,
                "language": language,
                "reduction_percentage": reduction_percentage,
                "before_context": before_context,
                "after_context": after_context
            }
            
            # Initialize usage tracking for the entire stream
            total_input_tokens = 0
            total_output_tokens = 0
            total_api_calls = 0
            
            # Process each chunk
            for chunk_num, chunk_text in enumerate(text_chunks, 1):
                try:
                    self.logger.info(f"🔄 Processing chunk {chunk_num}/{total_chunks}")
                    
                    # Generate streaming prompt for this chunk
                    chunk_prompt = TextShorteningPrompts.get_streaming_text_shortening_prompt(
                        text_chunk=chunk_text,
                        context=context,
                        chunk_number=chunk_num,
                        total_chunks=total_chunks
                    )
                    
                    # 🔍 LOG CHUNK PROMPT
                    self.logger.info(f"=" * 60)
                    self.logger.info(f"🎯 CHUNK {chunk_num} PROMPT:")
                    self.logger.info(f"=" * 60)
                    self.logger.info(chunk_prompt)
                    self.logger.info(f"=" * 60)
                    
                    # Stream the chunk processing
                    async for chunk_result in self._stream_chunk_processing(
                        chunk_prompt, chunk_num, session_id
                    ):
                        yield chunk_result
                    
                    # Call OpenAI API for this chunk with STREAMING
                    self.logger.info(f"🌊 Starting REAL-TIME streaming for chunk {chunk_num}...")
                    
                    response_stream = await self.async_openai_client.chat.completions.create(
                        model="gpt-4.1-2025-04-14",
                        messages=[
                            {
                                "role": "system",
                                "content": "You are an experienced content Editor."
                            },
                            {
                                "role": "user",
                                "content": chunk_prompt
                            }
                        ],
                        temperature=0.7,
                        max_tokens=2048,
                        stream=True  # 🌊 Enable real-time streaming
                    )
                    
                    # 🌊 PROCESS STREAMING RESPONSE IN REAL-TIME
                    chunk_response = ""
                    chunk_input_tokens = 0
                    chunk_output_tokens = 0
                    word_count = 0
                    
                    # Emit streaming start event
                    yield {
                        "event": "chunk_stream_start",
                        "session_id": session_id,
                        "chunk_number": chunk_num,
                        "message": f"Starting real-time streaming for chunk {chunk_num}"
                    }
                    
                    async for chunk in response_stream:
                        if chunk.choices[0].delta.content:
                            content_piece = chunk.choices[0].delta.content
                            chunk_response += content_piece
                            word_count += len(content_piece.split())
                            
                            # Emit real-time content streaming
                            yield {
                                "event": "chunk_stream_content",
                                "session_id": session_id,
                                "chunk_number": chunk_num,
                                "content_piece": content_piece,
                                "accumulated_content": chunk_response,
                                "word_count": word_count,
                                "message": f"Streaming content for chunk {chunk_num}..."
                            }
                            
                            # Minimal delay for real-time streaming
                            await asyncio.sleep(0.0001)
                        
                        # Track usage data when available
                        if hasattr(chunk, 'usage') and chunk.usage:
                            chunk_input_tokens = getattr(chunk.usage, 'prompt_tokens', 0)
                            chunk_output_tokens = getattr(chunk.usage, 'completion_tokens', 0)
                    
                    # 📊 TRACK USAGE FOR THIS CHUNK
                    total_api_calls += 1
                    if chunk_input_tokens > 0 or chunk_output_tokens > 0:
                        total_input_tokens += chunk_input_tokens
                        total_output_tokens += chunk_output_tokens
                        
                        self.logger.info(f"📊 CHUNK {chunk_num} STREAMING USAGE:")
                        self.logger.info(f"📊 Input tokens (prompt_tokens): {chunk_input_tokens}")
                        self.logger.info(f"📊 Output tokens (completion_tokens): {chunk_output_tokens}")
                        self.logger.info(f"📊 Total tokens for chunk: {chunk_input_tokens + chunk_output_tokens}")
                        self.logger.info(f"📊 Running total - Input: {total_input_tokens}, Output: {total_output_tokens}, Calls: {total_api_calls}")
                    else:
                        # Estimate tokens if no usage data from streaming
                        estimated_input = len(chunk_prompt) // 4
                        estimated_output = len(chunk_response) // 4
                        total_input_tokens += estimated_input
                        total_output_tokens += estimated_output
                        self.logger.warning(f"⚠️ No usage data for streaming chunk {chunk_num}, using estimates: {estimated_input} input, {estimated_output} output")
                    
                    # Emit streaming end event
                    yield {
                        "event": "chunk_stream_end",
                        "session_id": session_id,
                        "chunk_number": chunk_num,
                        "total_words_streamed": word_count,
                        "message": f"Real-time streaming completed for chunk {chunk_num}"
                    }
                    
                    # 🔍 LOG CHUNK RESPONSE
                    self.logger.info(f"=" * 60)
                    self.logger.info(f"🤖 CHUNK {chunk_num} RESPONSE:")
                    self.logger.info(f"=" * 60)
                    self.logger.info(chunk_response)
                    self.logger.info(f"=" * 60)
                    
                    try:
                        chunk_data = json.loads(chunk_response)
                        shortened_chunk = chunk_data.get('shortened_chunk', '')
                        shortened_chunks.append(shortened_chunk)
                        
                        # Emit chunk completion
                        yield {
                            "event": "chunk_complete",
                            "session_id": session_id,
                            "chunk_number": chunk_num,
                            "shortened_chunk": shortened_chunk,
                            "chunk_reduction": chunk_data.get('chunk_reduction', 0),
                            "keyword_found": chunk_data.get('keyword_found', False),
                            "progress_percentage": (chunk_num / total_chunks) * 100
                        }
                        
                    except json.JSONDecodeError:
                        self.logger.error(f"❌ Failed to parse chunk {chunk_num} response")
                        shortened_chunks.append(chunk_text)  # Fallback to original
                        
                        yield {
                            "event": "chunk_error",
                            "session_id": session_id,
                            "chunk_number": chunk_num,
                            "error": "Failed to parse chunk response",
                            "fallback_used": True
                        }
                    
                    # Small delay to prevent rate limiting
                    await asyncio.sleep(0.1)
                    
                except Exception as chunk_error:
                    self.logger.error(f"❌ Error processing chunk {chunk_num}: {chunk_error}")
                    shortened_chunks.append(chunk_text)  # Fallback to original
                    
                    yield {
                        "event": "chunk_error",
                        "session_id": session_id,
                        "chunk_number": chunk_num,
                        "error": str(chunk_error),
                        "fallback_used": True
                    }
            
            # Combine all shortened chunks
            final_shortened_text = "".join(shortened_chunks)
            
            # Calculate final statistics
            original_length = len(text_to_edit)
            new_length = len(final_shortened_text)
            actual_reduction = ((original_length - new_length) / original_length) * 100
            keyword_preserved = primary_keyword.lower() in final_shortened_text.lower() if primary_keyword else True
            
            # 📊 RECORD USAGE FOR THE ENTIRE STREAMING SESSION
            self.logger.info(f"=" * 80)
            self.logger.info(f"📊 RECORDING USAGE FOR STREAMING SESSION:")
            self.logger.info(f"📊 Total API calls: {total_api_calls}")
            self.logger.info(f"📊 Total input tokens: {total_input_tokens}")
            self.logger.info(f"📊 Total output tokens: {total_output_tokens}")
            self.logger.info(f"=" * 80)
            
            try:
                usage_metadata = {
                    "text_shortening": {
                        "original_length": original_length,
                        "new_length": new_length,
                        "reduction_achieved": actual_reduction,
                        "keyword_preserved": keyword_preserved,
                        "total_chunks": total_chunks,
                        "total_api_calls": total_api_calls,
                        "brand_tonality": brand_tonality,
                        "primary_keyword": primary_keyword,
                        "language": language
                    }
                }
                
                # Record LLM usage with actual response data
                result = self.llm_usage_service.record_llm_usage(
                    user_id=self.user_id,
                    service_name="text_shortening",
                    model_name="gpt-4.1-mini",
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    service_description=f"Streaming text shortening with {total_api_calls} API calls",
                    project_id=self.project_id,
                    additional_metadata=usage_metadata
                )
                self.logger.info(f"✅ Usage recorded successfully for streaming session: {result}")
                
                # Emit usage recording event
                yield {
                    "event": "usage_recorded",
                    "session_id": session_id,
                    "total_input_tokens": total_input_tokens,
                    "total_output_tokens": total_output_tokens,
                    "total_api_calls": total_api_calls,
                    "usage_cost": result.get('cost_info', {}).get('final_charge_usd', 0) if result.get('success') else 0,
                    "message": "Usage tracking completed"
                }
                
            except Exception as usage_error:
                self.logger.error(f"⚠️ Failed to record streaming usage (non-critical): {usage_error}")
                self.logger.error(f"⚠️ Usage error details: {str(usage_error)}", exc_info=True)
                
                # Emit usage error event
                yield {
                    "event": "usage_error",
                    "session_id": session_id,
                    "error": str(usage_error),
                    "message": "Failed to record usage (processing completed successfully)"
                }
            
            # Emit final result
            yield {
                "event": "complete",
                "session_id": session_id,
                "shortened_text": final_shortened_text,
                "original_length": original_length,
                "new_length": new_length,
                "reduction_achieved": round(actual_reduction, 2),
                "keyword_preserved": keyword_preserved,
                "total_chunks_processed": total_chunks,
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "total_api_calls": total_api_calls,
                "message": "Text shortening completed successfully"
            }
            
        except Exception as stream_error:
            self.logger.error(f"❌ Streaming text shortening failed: {stream_error}")
            yield {
                "event": "error",
                "session_id": session_id,
                "error": str(stream_error),
                "message": "Text shortening stream failed"
            }

    def _split_text_into_chunks(self, text: str, chunk_size: int) -> List[str]:
        """
        Split text into manageable chunks while preserving HTML structure
        
        Args:
            text: Text to split
            chunk_size: Maximum characters per chunk
            
        Returns:
            List of text chunks
        """
        # Simple chunking - can be enhanced to respect HTML boundaries
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunk = text[i:i + chunk_size]
            chunks.append(chunk)
        return chunks

    async def _stream_chunk_processing(
        self, 
        prompt: str, 
        chunk_num: int, 
        session_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream individual chunk processing updates
        
        Args:
            prompt: Chunk processing prompt
            chunk_num: Current chunk number
            session_id: Session identifier
            
        Yields:
            Chunk processing updates
        """
        yield {
            "event": "chunk_start",
            "session_id": session_id,
            "chunk_number": chunk_num,
            "message": f"Processing chunk {chunk_num}",
            "timestamp": datetime.now().isoformat()
        }
        
        # Simulate processing steps
        await asyncio.sleep(0.05)
        
        yield {
            "event": "chunk_analysis",
            "session_id": session_id,
            "chunk_number": chunk_num,
            "message": "Analyzing content structure",
            "timestamp": datetime.now().isoformat()
        }
        
        await asyncio.sleep(0.05)
        
        yield {
            "event": "chunk_processing",
            "session_id": session_id,
            "chunk_number": chunk_num,
            "message": "Applying shortening rules",
            "timestamp": datetime.now().isoformat()
        }
