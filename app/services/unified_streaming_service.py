"""
Unified Streaming Service for GPT-5 and Claude Opus 4-1
Handles both thinking phase (GPT-5) and content streaming for blog generation
"""

import json
import logging
import aiohttp
import asyncio
import time
from typing import Dict, Any, AsyncGenerator, Optional, Tuple
from datetime import datetime
import pytz
from app.core.config import settings

logger = logging.getLogger(__name__)


class UnifiedStreamingService:
    """Unified streaming service supporting both GPT-5 Responses API and Claude Messages API"""
    
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            logger.error("OPENAI_API_KEY is not set!")
        else:
            logger.debug(f"OpenAI API key set: {settings.OPENAI_API_KEY[:10]}...")
            
        self.openai_headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        self.anthropic_headers = {
            "Content-Type": "application/json",
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"
        }
    
    def select_model_and_provider(self, formality: str) -> Tuple[str, str]:
        """
        Select model and API provider based on formality level
        
        Args:
            formality: Brand tonality formality level
            
        Returns:
            Tuple of (model, provider)
        """
        formal_levels = ["Ceremonial", "Formal"]
        
        if formality in formal_levels:
            return "gpt-5", "openai"  # Formal → GPT-5 with thinking
        else:
            return "claude-haiku-4-5-20251001", "anthropic"  # Casual → Claude
    
    async def stream_blog_generation(
        self,
        blog_id: str,
        formality: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 32000,
        temperature: float = 1.0
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Unified streaming interface for both GPT-5 and Claude
        
        Args:
            blog_id: Blog identifier
            formality: Brand tonality formality level
            system_prompt: System instruction
            user_prompt: User instruction
            max_tokens: Maximum tokens to generate
            temperature: Generation temperature
            
        Yields:
            Normalized streaming events
        """
        model, provider = self.select_model_and_provider(formality)
        
        logger.info(f"🎯 Selected {model} via {provider} for formality: {formality}")
        
        if provider == "openai":
            try:
                async for event in self._stream_gpt5_responses(
                    blog_id, system_prompt, user_prompt, max_tokens, temperature
                ):
                    if event is not None:  # Ensure event is not None
                        yield self._normalize_gpt5_event(event, blog_id)
            except Exception as e:
                logger.error(f"GPT-5 streaming error: {str(e)}")
                raise
        elif provider == "anthropic":
            try:
                async for event in self._stream_anthropic_messages(
                    blog_id, system_prompt, user_prompt, max_tokens, temperature
                ):
                    if event is not None:  # Ensure event is not None
                        yield self._normalize_anthropic_event(event, blog_id)
            except Exception as e:
                logger.error(f"Claude streaming error: {str(e)}")
                raise
    
    async def _stream_gpt5_responses(
        self,
        blog_id: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream GPT-5 Responses API with thinking + content phases
        """
        # GPT-5 Responses API format (exact format from working curl)
        payload = {
            "model": "gpt-5",
            "input": [
                {
                    "role": "developer",
                    "content": [{"type": "input_text", "text": system_prompt}]
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}]
                }
            ],
            "text": {
                "format": {"type": "text"},
                "verbosity": "high"
            },
            "reasoning": {
                "effort": "low", 
                "summary": "auto"
            },
            "tools": [],
            "store": True,
            "include": ["reasoning.encrypted_content", "web_search_call.action.sources"],
            "stream": True
        }
        
        logger.info(f"🚀 Starting GPT-5 streaming for blog_id: {blog_id}")
        logger.info(f"GPT-5 request URL: https://api.openai.com/v1/responses")
        logger.info(f"GPT-5 headers: {dict(self.openai_headers)}")
        logger.info(f"GPT-5 payload size: {len(json.dumps(payload))} chars")
        logger.debug(f"GPT-5 payload: {json.dumps(payload, indent=2)}")
        
        timeout = aiohttp.ClientTimeout(total=600)  # 10 minute timeout
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    "https://api.openai.com/v1/responses",
                    headers=self.openai_headers,
                    json=payload
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"GPT-5 API HTTP {response.status} error: {error_text}")
                        logger.error(f"Request headers: {self.openai_headers}")
                        raise Exception(f"GPT-5 API error: {response.status} - {error_text}")
                    
                    logger.info(f"GPT-5 response status: {response.status}, content-type: {response.headers.get('content-type', 'unknown')}")
                    
                    buffer = ""
                    event_count = 0
                    
                    try:
                        async for chunk in response.content:
                            if chunk:
                                chunk_text = chunk.decode('utf-8')
                                buffer += chunk_text
                                logger.debug(f"Received chunk: {repr(chunk_text[:100])}...")
                                
                                lines = buffer.split('\n')
                                buffer = lines[-1]  # Keep the incomplete line in buffer
                                
                                for line in lines[:-1]:  # Process complete lines
                                    line = line.strip()
                                    if line.startswith('data: '):
                                        data_part = line[6:]  # Remove 'data: '
                                        if data_part == '[DONE]':
                                            logger.info(f"GPT-5 stream completed for blog_id: {blog_id} ({event_count} events processed)")
                                            return
                                        try:
                                            event_data = json.loads(data_part)
                                            event_count += 1
                                            logger.debug(f"GPT-5 event #{event_count}: {event_data.get('type', 'unknown')}")
                                            yield event_data
                                        except json.JSONDecodeError as e:
                                            logger.warning(f"Failed to parse GPT-5 event '{data_part[:100]}...': {e}")
                                            continue
                                        except Exception as e:
                                            logger.error(f"Error processing GPT-5 event: {e}")
                                            continue
                                    elif line.startswith('event: ') or line == '' or line.startswith(':'):
                                        # Skip event type lines, empty lines, and comments
                                        logger.debug(f"Skipping SSE metadata: {line}")
                                        continue
                                    elif line:
                                        logger.debug(f"Unknown SSE line: {line}")
                    except Exception as stream_error:
                        logger.error(f"Error during GPT-5 streaming: {str(stream_error)}")
                        raise
                    
                    logger.warning(f"GPT-5 stream ended without [DONE] signal for blog_id: {blog_id} ({event_count} events processed)")
                                    
        except Exception as e:
            logger.error(f"GPT-5 streaming error for blog_id {blog_id}: {str(e)}")
            raise
    
    async def _stream_anthropic_messages(
        self,
        blog_id: str,
        system_prompt: str, 
        user_prompt: str,
        max_tokens: int,
        temperature: float
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream Claude Messages API (existing implementation)
        """
        payload = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_prompt
                        }
                    ]
                }
            ]
        }
        
        logger.info(f"🚀 Starting Claude streaming for blog_id: {blog_id}")
        
        timeout = aiohttp.ClientTimeout(total=600)  # 10 minute timeout
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=self.anthropic_headers,
                    json=payload
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Claude API error: {response.status} - {error_text}")
                    
                    async for line in response.content:
                        if line:
                            line_text = line.decode('utf-8').strip()
                            if line_text.startswith('data: '):
                                try:
                                    event_data = json.loads(line_text[6:])  # Remove 'data: '
                                    yield event_data
                                except json.JSONDecodeError as e:
                                    logger.warning(f"Failed to parse Claude event: {e}")
                                    continue
                                except Exception as e:
                                    logger.error(f"Error processing Claude event: {e}")
                                    continue
                                    
        except Exception as e:
            logger.error(f"Claude streaming error for blog_id {blog_id}: {str(e)}")
            raise
    
    def _normalize_gpt5_event(self, gpt5_event: Dict[str, Any], blog_id: str) -> Dict[str, Any]:
        """
        Convert GPT-5 events to unified format compatible with existing Claude processing
        """
        if not gpt5_event or not isinstance(gpt5_event, dict):
            logger.warning(f"Invalid GPT-5 event received: {gpt5_event}")
            return {"type": "unknown", "data": gpt5_event, "blog_id": blog_id}
            
        event_type = gpt5_event.get("type")
        sequence_number = gpt5_event.get("sequence_number", 0)
        
        logger.debug(f"Normalizing GPT-5 event type: '{event_type}' for blog_id: {blog_id}")
        
        if event_type == "response.created":
            usage = gpt5_event.get("response", {}).get("usage", {})
            if usage is None:
                usage = {}
            return {
                "type": "message_start",
                "message": {
                    "usage": usage
                },
                "blog_id": blog_id,
                "sequence_number": sequence_number
            }
        
        elif event_type == "response.reasoning_summary_text.delta":
            # 🧠 THINKING PHASE - Map to custom thinking event
            delta_text = gpt5_event.get("delta", "")
            if delta_text is None:
                delta_text = ""
            
            return {
                "type": "thinking_delta",
                "delta": {
                    "type": "text_delta",
                    "text": str(delta_text)
                },
                "phase": "thinking",
                "sequence_number": sequence_number,
                "blog_id": blog_id,
                "item_id": gpt5_event.get("item_id"),
                "summary_index": gpt5_event.get("summary_index", 0)
            }
        
        elif event_type == "response.output_text.delta":
            # 📝 CONTENT PHASE - Map to Claude-compatible content delta
            delta_text = gpt5_event.get("delta", "")
            if delta_text is None:
                delta_text = ""
                
            return {
                "type": "content_block_delta",
                "delta": {
                    "type": "text_delta",
                    "text": str(delta_text)
                },
                "phase": "content",
                "sequence_number": sequence_number,
                "blog_id": blog_id,
                "item_id": gpt5_event.get("item_id")
            }
        
        elif event_type == "response.output_text.done":
            return {
                "type": "content_block_stop",
                "blog_id": blog_id,
                "sequence_number": sequence_number
            }
        
        elif event_type == "response.completed":
            # ✅ COMPLETION - Extract comprehensive usage data
            response_data = gpt5_event.get("response", {})
            usage = response_data.get("usage", {})
            
            # Ensure usage is a dict
            if not isinstance(usage, dict):
                logger.warning(f"Usage data is not dict, type = {type(usage)}, converting to empty dict")
                usage = {}
            
            # Extract reasoning tokens from nested structure
            reasoning_tokens = 0
            output_tokens_details = usage.get("output_tokens_details", {})
            if isinstance(output_tokens_details, dict):
                reasoning_tokens = output_tokens_details.get("reasoning_tokens", 0)
            
            # Also try top-level fallback
            if reasoning_tokens == 0:
                reasoning_tokens = usage.get("reasoning_tokens", 0)
                
            normalized_usage = {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "reasoning_tokens": reasoning_tokens,  # GPT-5 specific - fixed extraction
                "total_tokens": usage.get("total_tokens", 0)
            }
            
            logger.info(f"✅ GPT-5 usage normalized: {normalized_usage['input_tokens']} input + {normalized_usage['output_tokens']} output + {normalized_usage['reasoning_tokens']} reasoning = {normalized_usage['total_tokens']} total tokens")
            
            return {
                "type": "message_stop",
                "usage": normalized_usage,
                "phase": "completed",
                "blog_id": blog_id,
                "sequence_number": sequence_number,
                "model": response_data.get("model", "gpt-5")
            }
        
        # Pass through unknown events
        return {
            "type": "unknown",
            "original_type": event_type,
            "data": gpt5_event,
            "blog_id": blog_id,
            "sequence_number": sequence_number
        }
    
    def _normalize_anthropic_event(self, claude_event: Dict[str, Any], blog_id: str) -> Dict[str, Any]:
        """
        Pass-through for Claude events (already in correct format) with blog_id injection
        """
        # Add blog_id to all Claude events for consistency
        claude_event["blog_id"] = blog_id
        return claude_event


# Global instance
unified_streaming_service = UnifiedStreamingService()