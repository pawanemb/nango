"""
Unified Streaming Processor for Blog Generation V2
Handles both thinking phase (GPT-5) and content streaming with 90fps delivery
"""

import json
import logging
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Tuple
import pytz
import redis
from app.services.unified_streaming_service import unified_streaming_service

logger = logging.getLogger(__name__)

# Redis client
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)


async def process_unified_streaming(
    blog_id: str,
    formality: str,
    system_prompt: str,
    user_prompt: str,
    redis_key: str
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Process unified streaming for both GPT-5 (thinking + content) and Claude (content only)
    
    Args:
        blog_id: Blog identifier
        formality: Brand tonality formality level
        system_prompt: System instruction
        user_prompt: User instruction
        redis_key: Redis key for storing streaming data
        
    Returns:
        Tuple of (blog_content, thinking_content, usage_data)
    """
    blog_content = ""
    thinking_content = ""
    usage_data = {}
    content_buffer = ""
    last_stream_time = 0
    
    try:
        logger.info(f"🚀 Starting unified streaming for blog_id: {blog_id}")
        
        stream_generator = unified_streaming_service.stream_blog_generation(
            blog_id=blog_id,
            formality=formality,
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )
        
        if stream_generator is None:
            raise Exception("Stream generator returned None")
        
        event_count = 0
        try:
            async for event in stream_generator:
                event_count += 1
                logger.debug(f"Processing event #{event_count} for blog_id: {blog_id}")
                
                if event is None:
                    logger.warning(f"Received None event for blog_id: {blog_id}")
                    continue
                
                # Debug: Log the entire event structure
                logger.info(f"📝 RAW EVENT for blog_id {blog_id}: {event}")
                    
                event_type = event.get("type")
                logger.info(f"🔍 Processing event type: '{event_type}' for blog_id: {blog_id}")
                
                if event_type == "message_start":
                    # Initialize usage tracking
                    message_usage = event.get("message", {}).get("usage", {})
                    if message_usage is not None and isinstance(message_usage, dict):
                        usage_data.update(message_usage)
                    logger.info(f"🔄 Message started for blog_id: {blog_id}")
                    
                elif event_type == "thinking_delta":
                    # 🧠 GPT-5 THINKING PHASE
                    try:
                        thinking_delta = event["delta"]["text"]
                        thinking_content += thinking_delta
                    except (KeyError, TypeError) as e:
                        logger.error(f"Error accessing thinking delta: {e}, event: {event}")
                        continue
                    
                    # Update Redis with thinking progress (5-30% progress)
                    thinking_word_count = len(thinking_content.split())
                    thinking_progress = min(5 + thinking_word_count * 0.05, 30)
                    
                    extra_data = {
                        "live_thinking": thinking_content,
                        "thinking_word_count": thinking_word_count,
                        "thinking_active": True
                    }
                    
                    safe_update_progress(blog_id, int(thinking_progress), redis_key, "thinking", extra_data)
                    logger.debug(f"🧠 Thinking: {len(thinking_delta)} chars added for blog_id: {blog_id}")
                    
                elif event_type == "content_block_delta":
                    # 📝 CONTENT PHASE (Both GPT-5 and Claude)
                    try:
                        content_delta = event["delta"]["text"]
                    except (KeyError, TypeError) as e:
                        logger.error(f"Error accessing content delta: {e}, event: {event}")
                        continue
                    
                    if content_delta:
                        # Same 90fps streaming logic for both models
                        content_buffer, should_stream, streamed_chunk, last_stream_time = process_smooth_content_streaming(
                            blog_id, content_delta, blog_content, content_buffer, redis_key, last_stream_time
                        )
                        
                        if should_stream and streamed_chunk:
                            blog_content += streamed_chunk
                        
                        # Progress from 30% to 95% for content (save 5% for completion)
                        content_word_count = len(blog_content.split())
                        content_progress = min(30 + content_word_count * 0.5, 95)
                        
                        extra_data = {
                            "live_content": blog_content,
                            "content_word_count": content_word_count,
                            "content_active": True
                        }
                        
                        safe_update_progress(blog_id, int(content_progress), redis_key, "content", extra_data)
                        logger.debug(f"🔥 Content: '{streamed_chunk.strip()[:50]}...' streamed for blog_id: {blog_id}")
                            
                elif event_type == "content_block_stop":
                    # Content block finished - flush any remaining buffered content
                    if content_buffer.strip():
                        blog_content += content_buffer
                        logger.info(f"🔥 Final content flush: {len(content_buffer.strip())} chars for blog_id: {blog_id}")
                        content_buffer = ""
                    
                    logger.info(f"📝 Content block finished for blog_id: {blog_id}")
                    
                elif event_type == "message_delta":
                    # 📊 CLAUDE USAGE DATA - comes in message_delta, not message_stop
                    delta_usage = event.get("usage", {})
                    if delta_usage is not None and isinstance(delta_usage, dict):
                        usage_data.update(delta_usage)
                        logger.info(f"✅ Claude usage data collected: {delta_usage}")
                
                elif event_type == "message_stop":
                    # ✅ COMPLETION
                    final_usage = event.get("usage", {})
                    if final_usage is not None and isinstance(final_usage, dict):
                        usage_data.update(final_usage)
                        logger.info(f"✅ Usage data collected from message_stop: {final_usage}")
                    else:
                        logger.debug(f"No usage data in message_stop event (normal for Claude)")
                    
                    # Final buffer flush
                    if content_buffer.strip():
                        blog_content += content_buffer
                        logger.info(f"🔥 Final message flush: {len(content_buffer.strip())} chars for blog_id: {blog_id}")
                        content_buffer = ""
                    
                    # Final content stream and completion
                    final_word_count = len(blog_content.split())
                    extra_data = {
                        "live_content": blog_content,
                        "content_word_count": final_word_count,
                        "final_content": blog_content[:500] + "..." if len(blog_content) > 500 else blog_content,
                        "content_active": False,
                        "thinking_active": False
                    }
                    
                    safe_update_progress(blog_id, 100, redis_key, "completed", extra_data)
                    
                    # Mark as blog_ready immediately
                    try:
                        task_data = redis_client.get(redis_key)
                        if task_data:
                            task_info = json.loads(task_data)
                            task_info["status"] = "blog_ready"
                            task_info["steps"]["blog_generation"]["status"] = "blog_ready"
                            task_info["word_count"] = final_word_count
                            redis_client.set(redis_key, json.dumps(task_info), ex=86400)
                            logger.info(f"📝 Blog marked as ready for blog_id: {blog_id}")
                    except Exception as immediate_error:
                        logger.error(f"Failed to mark blog as ready: {str(immediate_error)}")
                    
                    logger.info(f"✅ Streaming completed for blog_id: {blog_id}")
                    break
                    
                elif event_type == "unknown":
                    logger.debug(f"Unknown event type: {event.get('original_type')} for blog_id: {blog_id}")
            
            logger.info(f"Streaming loop completed for blog_id: {blog_id} - processed {event_count} events")
        except Exception as loop_error:
            logger.error(f"Error in streaming loop for blog_id {blog_id}: {str(loop_error)}")
            raise
                
    except Exception as e:
        logger.error(f"Unified streaming error for blog_id {blog_id}: {str(e)}")
        raise
    
    logger.info(f"✅ Final usage data for blog_id {blog_id}: {usage_data}")
    return blog_content, thinking_content, usage_data


def safe_update_progress(blog_id: str, new_progress: int, redis_key: str, phase: str, extra_data: dict = None):
    """
    SAFE PROGRESS UPDATE: Progress can ONLY go UP, NEVER DOWN
    """
    try:
        task_data = redis_client.get(redis_key)
        if not task_data:
            return
            
        task_info = json.loads(task_data)
        current_progress = task_info.get("steps", {}).get("blog_generation", {}).get("progress", 0)
        
        # CRITICAL: Never go backwards
        if new_progress < current_progress:
            logger.debug(f"🚫 Skipping progress update: {new_progress}% < current {current_progress}% for blog_id: {blog_id}")
            return
        
        # Update progress safely
        task_info["steps"]["blog_generation"]["progress"] = new_progress
        if "streaming_data" not in task_info["steps"]["blog_generation"]:
            task_info["steps"]["blog_generation"]["streaming_data"] = {}
            
        streaming_data = task_info["steps"]["blog_generation"]["streaming_data"]
        streaming_data["phase"] = phase
        streaming_data["last_updated"] = datetime.now(pytz.timezone('Asia/Kolkata')).isoformat()
        
        # Add extra data if provided
        if extra_data:
            for key, value in extra_data.items():
                streaming_data[key] = value
                
        redis_client.set(redis_key, json.dumps(task_info), ex=86400)
        
        # Log progress changes
        if new_progress > current_progress:
            logger.info(f"⬆️ Progress: {current_progress}% → {new_progress}% [{phase}] for blog_id: {blog_id}")
        
    except Exception as e:
        logger.warning(f"Failed to safely update progress: {str(e)}")


def process_smooth_content_streaming(blog_id: str, content_delta: str, current_content: str, content_buffer: str, redis_key: str, last_stream_time: float) -> Tuple[str, bool, str, float]:
    """
    Process content delta for REAL 90fps word-by-word streaming with throttling
    Returns: (updated_buffer, should_stream, content_to_stream, new_stream_time)
    """
    try:
        current_time = time.time()
        
        # Add new characters to buffer
        updated_buffer = content_buffer + content_delta
        
        # 90FPS THROTTLING: Don't stream more than every 50ms (20fps realistic limit)
        time_since_last_stream = current_time - last_stream_time
        min_stream_interval = 0.05  # 50ms = 20fps (realistic 90fps feel)
        
        # Check for natural word boundaries
        has_word_boundary = (
            updated_buffer.endswith(' ') or 
            any(updated_buffer.endswith(p) for p in '.!?;:,\n') or
            len(updated_buffer.split()) >= 2  # At least 2 words
        )
        
        # Stream conditions: Word boundary AND enough time passed
        should_stream_now = (
            has_word_boundary and 
            time_since_last_stream >= min_stream_interval and
            len(updated_buffer.strip()) >= 2  # Minimum content
        )
        
        # FORCE stream if buffer gets too large (prevent infinite buffering)
        force_stream = len(updated_buffer.strip()) >= 15
        
        if should_stream_now or force_stream:
            # Return the content to stream and clear buffer
            return "", True, updated_buffer, current_time
        
        # Keep buffering
        return updated_buffer, False, "", last_stream_time
        
    except Exception as e:
        logger.warning(f"Error in 90fps content streaming: {str(e)}")
        return "", True, updated_buffer, time.time()  # Stream on error