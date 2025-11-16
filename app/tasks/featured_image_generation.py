"""
Featured Image Generation - AI-Powered Featured Image Creation - FIXED VERSION
New implementation with dynamic style system and proper flow
"""

import json
import logging
import redis
import requests
import base64
import os
import time
from datetime import datetime, timezone
from typing import Dict, Any
from bson import ObjectId
import random
from app.celery_config import celery_app as celery
from app.services.mongodb_service import MongoDBService
from app.services.storage_service_factory import get_storage_service
import json
import pytz
from app.core.config import settings
from app.db.session import get_db_session
from app.models.project import Project
from app.models.project_image import ProjectImage
import uuid

# Sentry integration for Celery tasks
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration

# Initialize Sentry for Celery tasks if DSN is available
if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[CeleryIntegration()],
        send_default_pii=True,
        traces_sample_rate=0.1,  # Track 10% of performance
        profiles_sample_rate=0.1  # Profile 10% of sampled transactions
    )

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis client for task metadata
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Google GenAI Client
from google import genai

# OpenAI Client for prompt enhancement
import openai

@celery.task(name="app.tasks.featured_image_generation.generate_featured_image", queue="image_generation", bind=True)
def generate_featured_image(self, image_request: Dict[str, Any], project_id: str, project: Dict[str, Any], request_id: str) -> Dict[str, Any]:
    """
    Main orchestrator task for featured image generation
    AI-powered image creation with project-based styling
    
    Args:
        image_request: Image generation request payload (contains blog content)
        project_id: Project identifier
        project: Project information (contains featured_image_style)
        request_id: Unique request identifier
        
    Returns:
        Dictionary containing task results and metadata
    """
    try:
        # Set Sentry context for better error tracking
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("task_name", "generate_featured_image")
            scope.set_tag("request_id", request_id)
            scope.set_tag("project_id", project_id)
        
        logger.info(f"Starting featured image generation for request_id: {request_id}")
        
        # Initialize combined usage tracking for all API calls
        usage_tracker = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_calls": 0,
            "service_name": "featured_image_generation",
            "request_id": str(uuid.uuid4())[:8],
            "individual_calls": [],
            "user_id": project.get("user_id")
        }
        
        # Extract blog_id for tracking
        blog_id = image_request.get("blog_id", request_id)  # Fallback to request_id if no blog_id
        
        # Store task metadata in Redis using blog_id as primary key
        task_info = {
            "main_task_id": self.request.id,
            "project_id": project_id,
            "request_id": request_id,
            "blog_id": blog_id,
            "status": "processing",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "original_image_request": image_request,
            "usage_tracker": usage_tracker,
            "steps": {
                "prompt_enhancement": {"status": "pending", "progress": 0},
                "image_generation": {"status": "pending", "progress": 0}
            }
        }
        
        # Use blog_id as primary Redis key, with request_id as secondary
        redis_key_blog = f"featured_image_task:{blog_id}"
        redis_key_request = f"featured_image_task:{request_id}"
        
        # Store under both keys for flexibility
        redis_client.set(redis_key_blog, json.dumps(task_info), ex=86400)  # Primary: blog_id
        redis_client.set(redis_key_request, json.dumps(task_info), ex=86400)  # Secondary: request_id
        
        # Launch image generation task
        task_result = generate_image_with_gemini.delay(
            image_request=image_request,
            project_id=project_id,
            project=project,
            request_id=request_id,
            usage_tracker=usage_tracker
        )
        
        # Update task info with generation task ID
        task_info["generation_task_id"] = task_result.id
        redis_client.set(redis_key_blog, json.dumps(task_info), ex=86400)
        redis_client.set(redis_key_request, json.dumps(task_info), ex=86400)
        
        logger.info(f"Featured image generation started for request_id: {request_id}, task_id: {task_result.id}")
        
        return {
            "main_task_id": self.request.id,
            "task_id": task_result.id,
            "request_id": request_id,
            "status": "processing",
            "message": "Featured image generation started successfully"
        }
        
    except Exception as e:
        # Capture exception in Sentry with context
        sentry_sdk.capture_exception(e, extra={
            "request_id": request_id,
            "project_id": project_id,
            "task_name": "generate_featured_image"
        })
        logger.error(f"Error in generate_featured_image: {str(e)}", exc_info=True)
        
        # Update Redis with error
        try:
            redis_key = f"featured_image_task:{request_id}"
            task_info = {"status": "failed", "error": str(e)}
            redis_client.set(redis_key, json.dumps(task_info), ex=86400)
        except Exception as redis_error:
            logger.error(f"Failed to update Redis status: {str(redis_error)}")
        
        raise


def call_openai_for_prompt_enhancement(blog_content: str, project_style: str, country: str, request_id: str, usage_tracker: Dict[str, Any]) -> str:
    """
    Direct OpenAI call for prompt enhancement (non-Celery version)
    
    Args:
        blog_content: The blog content to analyze
        project_style: Project's featured_image_style from database
        country: Country from blog data
        request_id: Unique request identifier
        usage_tracker: Token usage tracking dictionary
        
    Returns:
        Enhanced prompt string for Gemini
    """
    logger.info(f"🤖 Direct OpenAI enhancement for style: {project_style}, request_id: {request_id}")
    
    # Initialize OpenAI client
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        raise Exception("No OpenAI API key found")
    
    # Load style-specific prompts from files
    def load_style_prompts(project_style: str):
        """Load system and user prompts for the given style"""
        try:
            # Map project style to file names
            style_mapping = {
                "Studio Ghibli style anime": "studio_ghibli_anime",
                "Knitted yarn textile art": "knitted_yarn_textile", 
                "Claymation 3D": "claymation_3d",
                "Hand-drawn Geometric Illustration": "hand_drawn_geometric",
                "Pixar Style": "pixar_style",
                "Papercut layered art": "papercut_layered",
                "Flat minimal vector icon": "flat_minimal_vector",
                "8-bit pixel art": "pixel_art_8bit",
                "Gradient mesh vector art": "gradient_mesh_vector",
                "Realistic photography": "realistic_photography",
                "Retro vintage film grain": "retro_vintage_film",
                "Cyberpunk futuristic neon": "cyberpunk_neon",
                "Halftone comic book": "halftone_comic",
                "Graffiti street art": "graffiti_street_art",
                "Origami folded paper": "origami_folded_paper",
                "Andy Warhol pop art": "andy_warhol_pop_art"
            }
            
            style_file = style_mapping.get(project_style)
            if not style_file:
                return None, None
                
            # Import the style module dynamically
            import importlib
            module_path = f"app.prompts.featured_image_generation.styles.{style_file}"
            style_module = importlib.import_module(module_path)
            
            return style_module.SYSTEM_PROMPT, style_module.USER_PROMPT
            
        except Exception as e:
            logger.warning(f"Failed to load style prompts for {project_style}: {e}")
            return None, None
    
    # Create enhanced prompt for Gemini
    try:
        import openai
        client = openai.OpenAI(api_key=openai_api_key)
        
        # Load style-specific prompts
        system_prompt, user_prompt_template = load_style_prompts(project_style)
        
        if system_prompt and user_prompt_template:
            # Use style-specific prompts - replace placeholders manually to avoid format errors
            system_message = system_prompt.replace("{Studio Ghibli style anime}", project_style)
            system_message = system_message.replace("{realistic photography}", project_style)
            system_message = system_message.replace("{cyberpunk futuristic neon}", project_style)
            # Generic replacement for any style in curly braces
            import re
            system_message = re.sub(r'\{[^}]+\}', project_style, system_message)
            
            user_message = user_prompt_template.replace("{blog_content}", blog_content)
            user_message = user_message.replace("{country}", country)
            user_message = user_message.replace("{Country}", country)
            
            logger.info(f"✅ Using style-specific prompts for: {project_style}")
        else:
            # No fallback - raise error if style prompts not found
            raise Exception(f"Style prompts not found for: {project_style}. Please ensure style is configured properly.")
        
        # Use new OpenAI responses API with web search (like secondary_keywords.py)
        client = openai.OpenAI(api_key=openai_api_key)
        
        logger.info(f"🔍 Calling OpenAI responses API with web search for enhanced prompts")
        
        # Make the API call using the OpenAI client (same approach as secondary_keywords.py)
        try:
            logger.info(f"🔍 Making OpenAI call with system_message length: {len(system_message)}")
            logger.info(f"🔍 Making OpenAI call with user_message length: {len(user_message)}")
            
            # Save request payload to file for debugging
            request_payload = {
                "model": "gpt-4.1-2025-04-14",
                "input": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                "temperature": 1,
                "max_output_tokens": 2048,
                "tools": [
                    {
                        "type": "web_search",
                        "user_location": {
                            "type": "approximate"
                        },
                        "search_context_size": "medium"
                    }
                ],
                "store": True,
                "include": ["web_search_call.action.sources"]
            }
            
            # Save request to text file
            import json
            request_file = f"/tmp/openai_request_{request_id}.txt"
            with open(request_file, 'w') as f:
                f.write("=== OPENAI REQUEST PAYLOAD ===\n")
                f.write(json.dumps(request_payload, indent=2))
                f.write("\n\n=== SYSTEM MESSAGE ===\n")
                f.write(system_message)
                f.write("\n\n=== USER MESSAGE ===\n")
                f.write(user_message)
            logger.info(f"📝 Saved OpenAI request to: {request_file}")
            
            response = client.responses.create(**request_payload)
            
            # Save full response to text file
            response_file = f"/tmp/openai_response_{request_id}.txt"
            with open(response_file, 'w') as f:
                f.write("=== OPENAI RESPONSE OBJECT ===\n")
                f.write(f"Type: {type(response)}\n")
                f.write(f"Attributes: {dir(response)}\n")
                f.write("\n=== RAW RESPONSE ===\n")
                f.write(str(response))
                f.write("\n\n=== RESPONSE DICT ===\n")
                try:
                    f.write(json.dumps(response.__dict__, indent=2, default=str))
                except:
                    f.write("Could not serialize response.__dict__")
                f.write("\n\n=== OUTPUT_TEXT ===\n")
                try:
                    f.write(f"output_text: {response.output_text}")
                except AttributeError as e:
                    f.write(f"No output_text attribute: {e}")
                f.write("\n\n=== ALL ATTRIBUTES ===\n")
                for attr in dir(response):
                    if not attr.startswith('_'):
                        try:
                            value = getattr(response, attr)
                            f.write(f"{attr}: {value}\n")
                        except:
                            f.write(f"{attr}: <could not access>\n")
            logger.info(f"📝 Saved OpenAI response to: {response_file}")
            
            logger.info(f"🔍 OpenAI response object: {type(response)}")
            logger.info(f"🔍 OpenAI response attributes: {dir(response)}")
            
            # Extract the response text using the same method as secondary_keywords.py
            response_content = response.output_text.strip()
            
            logger.info(f"🔍 Raw response_content: '{response_content}'")
            logger.info(f"🔍 Response content length: {len(response_content)}")
            
            if not response_content:
                raise Exception("Empty response from OpenAI responses API")
                
        except Exception as api_error:
            logger.error(f"❌ OpenAI responses API call failed: {str(api_error)}")
            raise Exception(f"OpenAI responses API call failed: {str(api_error)}")
        
        logger.info(f"🔍 Web search response received: {len(response_content)} characters")
        
        # Extract the image prompt from the response (format: "Blog Summary: ... Image Prompt: ...")
        if "Image Prompt:" in response_content:
            # Split by "Image Prompt:" and take everything after it
            prompt_parts = response_content.split("Image Prompt:")
            if len(prompt_parts) > 1:
                enhanced_prompt = prompt_parts[1].strip()
            else:
                enhanced_prompt = response_content.strip()
        else:
            enhanced_prompt = response_content.strip()
        
        # Additional debugging
        logger.info(f"🔍 Final enhanced_prompt after extraction: '{enhanced_prompt}'")
        logger.info(f"🔍 Final enhanced_prompt length: {len(enhanced_prompt)}")
        
        # Track usage for the new API format
        if hasattr(response, 'usage'):
            usage_data = response.usage
            usage_tracker["total_input_tokens"] += getattr(usage_data, 'prompt_tokens', 0)
            usage_tracker["total_output_tokens"] += getattr(usage_data, 'completion_tokens', 0)
            usage_tracker["total_calls"] += 1
        
        # Log web search sources if available
        if hasattr(response, 'web_search_call'):
            sources = getattr(response.web_search_call, 'action', {}).get('sources', [])
            if sources:
                logger.info(f"🔍 Web search found {len(sources)} sources for enhanced prompt generation")
                for i, source in enumerate(sources[:3]):  # Log first 3 sources
                    logger.info(f"  Source {i+1}: {source.get('title', 'Unknown')} - {source.get('url', 'No URL')}")
            else:
                logger.info("🔍 No web search sources found in response")
        else:
            logger.info("🔍 No web search data in response")
        
        logger.info(f"✅ OpenAI enhancement successful: {enhanced_prompt[:100]}...")
        return enhanced_prompt
        
    except Exception as e:
        logger.error(f"❌ OpenAI API call failed: {str(e)}")
        # No fallback - re-raise the exception
        raise Exception(f"Failed to enhance prompt with OpenAI: {str(e)}")


@celery.task(name="app.tasks.featured_image_generation.retry_featured_image", queue="image_generation", bind=True)
def retry_featured_image(self, blog_id: str, project_id: str, project: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retry failed featured image generation
    Similar to blog generation V2 retry mechanism
    
    Args:
        blog_id: Blog document ID to retry image generation for
        project_id: Project identifier
        project: Project information
        
    Returns:
        Dictionary containing retry task results and metadata
    """
    try:
        # Set Sentry context for retry tracking
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("task_name", "retry_featured_image")
            scope.set_tag("blog_id", blog_id)
            scope.set_tag("project_id", project_id)
        
        logger.info(f"🔄 Retrying featured image generation for blog_id: {blog_id}")
        
        # Get blog content from MongoDB for retry
        mongodb_service = MongoDBService()
        mongodb_service.init_sync_db()
        
        blog_doc = mongodb_service.get_sync_db()['blogs'].find_one({'_id': ObjectId(blog_id)})
        if not blog_doc:
            raise Exception(f"Blog document not found for blog_id: {blog_id}")
        
        blog_content = blog_doc.get('content', '')
        if not blog_content:
            raise Exception(f"No blog content found for blog_id: {blog_id}")
        
        # Prepare image request from existing blog data
        image_request = {
            "blog_content": blog_content,
            "blog_id": blog_id,
            "country": blog_doc.get("country", "us"),
            "category": blog_doc.get("category", ""),
            "primary_keyword": blog_doc.get("primary_keyword", "")
        }
        
        # Generate new request_id for retry
        request_id = f"retry_{blog_id}_{uuid.uuid4().hex[:8]}"
        
        logger.info(f"🎨 Starting retry image generation with request_id: {request_id}")
        
        # Launch featured image generation retry
        image_task = generate_featured_image.delay(
            image_request=image_request,
            project_id=project_id,
            project=project,
            request_id=request_id
        )
        
        # Update Redis with retry status
        redis_key = f"featured_image_task:{blog_id}"
        retry_info = {
            "main_task_id": self.request.id,
            "retry_task_id": image_task.id,
            "request_id": request_id,
            "status": "retrying",
            "retry_started_at": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat(),
            "original_failure_retry": True
        }
        redis_client.set(redis_key, json.dumps(retry_info), ex=86400)
        
        logger.info(f"✅ Featured image retry started: {image_task.id} for blog_id: {blog_id}")
        
        return {
            "main_task_id": self.request.id,
            "task_id": image_task.id,
            "request_id": request_id,
            "blog_id": blog_id,
            "status": "retrying",
            "message": "Featured image generation retry started successfully"
        }
        
    except Exception as e:
        # Capture exception in Sentry with context
        sentry_sdk.capture_exception(e, extra={
            "blog_id": blog_id,
            "project_id": project_id,
            "task_name": "retry_featured_image"
        })
        logger.error(f"Error in retry_featured_image: {str(e)}", exc_info=True)
        
        # Update Redis with retry failure
        try:
            redis_key = f"featured_image_task:{blog_id}"
            retry_error_info = {
                "status": "retry_failed", 
                "error": str(e),
                "retry_failed_at": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat()
            }
            redis_client.set(redis_key, json.dumps(retry_error_info), ex=86400)
        except Exception as redis_error:
            logger.error(f"Failed to update Redis retry status: {str(redis_error)}")
        
        raise


def safe_update_image_progress(identifier: str, new_progress: int, redis_key: str, phase: str, extra_data: dict = None, force_update: bool = False):
    """
    SAFE PROGRESS UPDATE for featured image generation: Progress can ONLY go UP, NEVER DOWN
    Similar to blog generation V2 progress system
    """
    try:
        task_data = redis_client.get(redis_key)
        if not task_data:
            return
            
        task_info = json.loads(task_data)
        current_progress = task_info.get("steps", {}).get("image_generation", {}).get("progress", 0)
        
        # CRITICAL: Never go backwards (unless force_update)
        if new_progress < current_progress:
            logger.debug(f"🚫 Skipping image progress update: {new_progress}% < current {current_progress}% for {identifier}")
            return
            
        # Skip if same progress and not forced
        if new_progress == current_progress and not force_update and not extra_data:
            logger.debug(f"🔄 Same image progress {current_progress}%, skipping for {identifier}")
            return
            
        # Update progress safely
        if "steps" not in task_info:
            task_info["steps"] = {}
        if "image_generation" not in task_info["steps"]:
            task_info["steps"]["image_generation"] = {}
            
        task_info["steps"]["image_generation"]["progress"] = new_progress
        
        if "generation_data" in task_info["steps"]["image_generation"]:
            task_info["steps"]["image_generation"]["generation_data"]["phase"] = phase
            task_info["steps"]["image_generation"]["generation_data"]["last_updated"] = datetime.now(timezone.utc).isoformat()
            
            # Add extra data if provided
            if extra_data:
                for key, value in extra_data.items():
                    task_info["steps"]["image_generation"]["generation_data"][key] = value
                    
        redis_client.set(redis_key, json.dumps(task_info), ex=86400)
        
        # Log progress updates
        if new_progress > current_progress:
            logger.info(f"⬆️ Image Progress: {current_progress}% → {new_progress}% [{phase}] for {identifier}")
        elif extra_data:
            logger.debug(f"📝 Image Data update: {new_progress}% [{phase}] for {identifier}")
        
    except Exception as e:
        logger.warning(f"Failed to safely update image progress: {str(e)}")


def handle_image_stream(identifier: str, phase: str, progress: int, redis_key: str, extra_data: dict = None):
    """
    Handle image generation phase streaming updates - similar to blog content streaming
    """
    try:
        # Update image generation data with streaming info
        stream_data = {
            "current_phase": phase,
            "progress": progress,
            "stream_update_timestamp": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat()
        }
        
        if extra_data:
            stream_data.update(extra_data)
        
        # Get current progress and update with stream data
        task_data = redis_client.get(redis_key)
        if task_data:
            task_info = json.loads(task_data)
            current_progress = task_info.get("steps", {}).get("image_generation", {}).get("progress", 0)
            safe_update_image_progress(identifier, max(current_progress, progress), redis_key, phase, stream_data)
        
        logger.debug(f"📝 Image stream update: {phase} ({progress}%) for {identifier}")
        
    except Exception as e:
        logger.warning(f"Failed to update image stream: {str(e)}")


@celery.task(name="app.tasks.featured_image_generation.get_featured_image_streaming_status", queue="image_generation")
def get_featured_image_streaming_status(identifier: str) -> Dict[str, Any]:
    """
    Get comprehensive streaming status for featured image generation
    Similar to blog generation V2 status endpoint
    
    Args:
        identifier: Either blog_id or request_id to check status for
        
    Returns:
        Dictionary containing status information in frontend-expected format
    """
    start_time = time.time()
    logger.info(f"🔍 [STATUS_API] Starting status check for identifier: {identifier}")
    
    try:
        # Log Redis connection attempt
        logger.debug(f"🔍 [STATUS_API] Attempting Redis connection for identifier: {identifier}")
        
        # Try both Redis key patterns
        redis_keys = [
            f"featured_image_task:{identifier}",
            f"featured_image_task:{identifier}"
        ]
        
        task_data = None
        used_key = None
        
        logger.debug(f"🔍 [STATUS_API] Checking Redis keys: {redis_keys}")
        
        for redis_key in redis_keys:
            try:
                logger.debug(f"🔍 [STATUS_API] Checking Redis key: {redis_key}")
                task_data = redis_client.get(redis_key)
                if task_data:
                    used_key = redis_key
                    logger.info(f"✅ [STATUS_API] Found data in Redis key: {used_key}")
                    break
                else:
                    logger.debug(f"❌ [STATUS_API] No data in Redis key: {redis_key}")
            except Exception as redis_error:
                logger.error(f"❌ [STATUS_API] Redis error for key {redis_key}: {str(redis_error)}")
                continue
        
        if not task_data:
            elapsed_time = time.time() - start_time
            logger.warning(f"⚠️ [STATUS_API] No task data found for identifier: {identifier} (took {elapsed_time:.3f}s)")
            return {
                "status": "not_found",
                "progress": 0,
                "phase": "unknown",
                "message": "No image generation task data found",
                "identifier": identifier,
                "debug_info": f"Checked keys: {redis_keys}, took {elapsed_time:.3f}s"
            }
        
        # Log data parsing attempt
        logger.debug(f"🔍 [STATUS_API] Parsing task data from Redis (length: {len(task_data)} chars)")
        
        try:
            task_info = json.loads(task_data)
            logger.debug(f"✅ [STATUS_API] Successfully parsed JSON data")
        except Exception as json_error:
            logger.error(f"❌ [STATUS_API] JSON parsing error: {str(json_error)}")
            logger.error(f"❌ [STATUS_API] Raw data preview: {task_data[:200]}...")
            raise json_error
        
        # Log data structure analysis
        logger.debug(f"🔍 [STATUS_API] Task info keys: {list(task_info.keys())}")
        logger.debug(f"🔍 [STATUS_API] Steps available: {list(task_info.get('steps', {}).keys())}")
        
        # Get progress from image generation step
        steps = task_info.get("steps", {})
        image_step = steps.get("image_generation", {})
        raw_progress = image_step.get("progress", 0)
        
        logger.debug(f"🔍 [STATUS_API] Raw progress from Redis: {raw_progress}")
        
        try:
            image_progress = int(raw_progress)
            # Cap progress at 100%
            image_progress = min(image_progress, 100)
            logger.debug(f"🔍 [STATUS_API] Processed progress: {image_progress}%")
        except (ValueError, TypeError) as progress_error:
            logger.error(f"❌ [STATUS_API] Progress conversion error: {str(progress_error)}, raw value: {raw_progress}")
            image_progress = 0
        
        # Get current phase
        generation_data = image_step.get("generation_data", {})
        current_phase = generation_data.get("phase", "unknown")
        
        logger.debug(f"🔍 [STATUS_API] Current phase: {current_phase}")
        logger.debug(f"🔍 [STATUS_API] Generation data keys: {list(generation_data.keys())}")
        
        # Map internal status to frontend-expected status
        internal_status = task_info.get("status", "unknown")
        logger.debug(f"🔍 [STATUS_API] Internal status: {internal_status}")
        
        if internal_status in ["running", "processing"]:
            frontend_status = "in_progress"
            message = "Featured image generation in progress"
        elif internal_status == "completed":
            frontend_status = "completed"
            message = "Featured image generation completed successfully"
        elif internal_status == "failed":
            frontend_status = "failed"
            message = "Featured image generation failed"
        elif internal_status == "retrying":
            frontend_status = "retrying"
            message = "Retrying featured image generation"
        else:
            frontend_status = "in_progress"
            message = "Featured image generation in progress"
        
        logger.info(f"📊 [STATUS_API] Status mapping: {internal_status} → {frontend_status} ({image_progress}% - {current_phase})")
        
        result = {
            "status": frontend_status,
            "progress": image_progress,
            "phase": current_phase,
            "message": message,
            "identifier": identifier
        }
        
        # Add additional data if available
        if "public_url" in task_info:
            result["image_url"] = task_info["public_url"]
            logger.debug(f"🔍 [STATUS_API] Added image_url to result")
        if "image_id" in task_info:
            result["image_id"] = task_info["image_id"]
            logger.debug(f"🔍 [STATUS_API] Added image_id to result")
        if "enhanced_prompt" in generation_data:
            prompt = generation_data["enhanced_prompt"]
            result["enhanced_prompt"] = prompt[:100] + "..." if len(prompt) > 100 else prompt
            logger.debug(f"🔍 [STATUS_API] Added enhanced_prompt to result (length: {len(prompt)})")
        
        # Add final result data if available
        if "final_result" in task_info:
            final_result = task_info["final_result"]
            result.update({
                "image_url": final_result.get("public_url"),
                "image_id": final_result.get("image_id"),
                "filename": final_result.get("filename")
            })
            logger.debug(f"🔍 [STATUS_API] Added final_result data to response")
        
        elapsed_time = time.time() - start_time
        logger.info(f"✅ [STATUS_API] Successfully retrieved status for {identifier}: {frontend_status} ({image_progress}%) in {elapsed_time:.3f}s")
        
        return result
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"❌ [STATUS_API] Error getting image streaming status for {identifier}: {str(e)} (took {elapsed_time:.3f}s)")
        logger.exception(f"❌ [STATUS_API] Full error traceback for {identifier}:")
        
        return {
            "status": "failed",
            "progress": 0,
            "phase": "error",
            "message": f"Error retrieving status: {str(e)}",
            "identifier": identifier,
            "debug_info": f"Error after {elapsed_time:.3f}s: {str(e)}"
        }


@celery.task(name="app.tasks.featured_image_generation.enhance_prompt_with_openai", queue="image_generation", bind=True)
def enhance_prompt_with_openai(self, blog_content: str, project_style: str, country: str, request_id: str, usage_tracker: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhance image generation prompt using OpenAI GPT with dynamic style system
    
    Args:
        blog_content: The blog content to analyze  
        project_style: Project's featured_image_style from database
        country: Country from MongoDB blog document
        request_id: Unique request identifier
        usage_tracker: Token usage tracking dictionary
        
    Returns:
        Dictionary containing enhanced prompt and metadata
    """
    try:
        logger.info(f"🤖 Enhancing prompt with OpenAI using style: {project_style} for request_id: {request_id}")
        
        # Initialize OpenAI client
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            logger.warning("⚠️ No OpenAI API key found - using fallback prompt")
            return {
                "enhanced_prompt": f"Create a professional blog header image representing: {blog_content[:100]}...",
                "enhancement_method": "none",
                "original_prompt": blog_content
            }
        
        # Load appropriate style prompts based on project's featured_image_style
        system_prompt = None
        user_prompt_template = None
        
        try:
            # Map project style to our style files
            style_mapping = {
                "Studio Ghibli style anime": "studio_ghibli_anime",
                "Knitted yarn textile art": "knitted_yarn_textile", 
                "Claymation 3D": "claymation_3d",
                "Papercut layered art": "papercut_layered",
                "Flat minimal vector icon": "flat_minimal_vector",
                "8-bit pixel art": "pixel_art_8bit",
                "Gradient mesh vector art": "gradient_mesh_vector",
                "Realistic photography": "realistic_photography",
                "Retro vintage film grain": "retro_vintage_film",
                "Cyberpunk futuristic neon": "cyberpunk_neon",
                "Halftone comic book": "halftone_comic",
                "Graffiti street art": "graffiti_street_art",
                "Origami folded paper": "origami_folded_paper",
                "Andy Warhol pop art": "andy_warhol_pop_art"
            }
            
            # Get the module name for the project's style
            style_module_name = style_mapping.get(project_style)
            if style_module_name:
                # Dynamically import the style module
                module_path = f"app.prompts.featured_image_generation.styles.{style_module_name}"
                style_module = __import__(module_path, fromlist=['SYSTEM_PROMPT', 'USER_PROMPT'])
                
                system_prompt = style_module.SYSTEM_PROMPT
                user_prompt_template = style_module.USER_PROMPT
                
                logger.info(f"✅ Loaded style prompts for: {project_style}")
            else:
                logger.warning(f"⚠️ Unknown project style: {project_style}, using default")
                
        except Exception as style_error:
            logger.error(f"❌ Failed to load style prompts: {style_error}")
        
        # Fallback to default prompts if style loading failed
        if not system_prompt or not user_prompt_template:
            system_prompt = "You are an expert at writing detailed, creative prompts for AI image generation."
            user_prompt_template = """Create a detailed, vivid prompt for AI image generation based on this blog content:

{blog_content}

Return ONLY the enhanced prompt, nothing else. Keep it under 200 words but make it rich and detailed."""
        
        # Format the user prompt with blog content and country from MongoDB
        # Truncate blog content to prevent token limit issues (keep first 2000 chars)
        truncated_content = blog_content[:2000] + "..." if len(blog_content) > 2000 else blog_content
        
        # Handle template safely by replacing placeholders manually
        user_prompt = user_prompt_template.replace("{blog_content}", truncated_content)
        user_prompt = user_prompt.replace("{country}", country)

        # Initialize retry variables
        openai_success = False
        openai_error = None
        enhanced_prompt = None
        response = None
        
        try:
            # Prepare OpenAI API payload
            openai_payload = {
                "model": "gpt-4o-mini-2024-07-18",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 16384,
                "temperature": 1.0
            }
            
            # Save OpenAI payload to txt file for debugging/analysis
            try:
                logs_dir = "logs/openai_payloads"
                os.makedirs(logs_dir, exist_ok=True)
                
                payload_filename = f"openai_payload_{request_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                payload_filepath = os.path.join(logs_dir, payload_filename)
                
                with open(payload_filepath, 'w', encoding='utf-8') as f:
                    f.write(f"OpenAI API Payload - Request ID: {request_id}\n")
                    f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                    f.write(f"Project Style: {project_style}\n")
                    f.write(f"Country: {country}\n")
                    f.write("=" * 80 + "\n\n")
                    
                    f.write("SYSTEM PROMPT:\n")
                    f.write("-" * 40 + "\n")
                    f.write(system_prompt + "\n\n")
                    
                    f.write("USER PROMPT:\n")
                    f.write("-" * 40 + "\n")
                    f.write(user_prompt + "\n\n")
                    
                    f.write("FULL PAYLOAD JSON:\n")
                    f.write("-" * 40 + "\n")
                    f.write(json.dumps(openai_payload, indent=2, ensure_ascii=False))
                
                logger.info(f"📄 OpenAI payload saved to: {payload_filepath}")
                
            except Exception as save_error:
                logger.warning(f"⚠️ Failed to save OpenAI payload to file: {save_error}")
            
            # PRIMARY ATTEMPT: Call OpenAI API with retry logic
            client = openai.OpenAI(api_key=openai_api_key)
            max_retries = 3
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"🔄 OpenAI attempt {attempt + 1}/{max_retries} for request_id: {request_id}")
                    
                    response = client.chat.completions.create(
                        **openai_payload,
                        timeout=60  # 60 second timeout for OpenAI
                    )
                    
                    raw_content = response.choices[0].message.content
                    enhanced_prompt = raw_content.strip() if raw_content else ""
                    
                    logger.info(f"🔍 OpenAI raw response: '{raw_content}'")
                    logger.info(f"🔍 OpenAI stripped response: '{enhanced_prompt}'")
                    logger.info(f"🔍 Response length: {len(enhanced_prompt) if enhanced_prompt else 0}")
                    
                    if not enhanced_prompt:
                        logger.error(f"❌ OpenAI returned empty content!")
                        raise Exception("OpenAI returned empty content")
                    
                    openai_success = True
                    logger.info(f"✅ OpenAI attempt {attempt + 1} succeeded for request_id: {request_id}")
                    break  # Success - exit retry loop
                    
                except Exception as attempt_error:
                    openai_error = attempt_error
                    logger.warning(f"⚠️ OpenAI attempt {attempt + 1} failed: {str(attempt_error)}")
                    
                    if attempt == max_retries - 1:
                        # Final attempt failed
                        logger.error(f"❌ All {max_retries} OpenAI attempts failed for request_id: {request_id}")
                        break
                    else:
                        # Wait before retry with exponential backoff
                        wait_time = 2 ** attempt  # 1s, 2s, 4s
                        logger.info(f"🕐 Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
            
            # Check if OpenAI succeeded
            if not openai_success:
                logger.error(f"❌ OpenAI enhancement completely failed after {max_retries} attempts")
                raise openai_error
            
            # Save OpenAI response to the same file
            try:
                with open(payload_filepath, 'a', encoding='utf-8') as f:
                    f.write("\n\n" + "=" * 80 + "\n")
                    f.write("OPENAI RESPONSE:\n")
                    f.write("-" * 40 + "\n")
                    f.write(f"Model: {response.model}\n")
                    f.write(f"Usage: {response.usage}\n")
                    f.write(f"Enhanced Prompt: {enhanced_prompt}\n")
                logger.info(f"📄 OpenAI response saved to: {payload_filepath}")
            except Exception as save_error:
                logger.warning(f"⚠️ Failed to save OpenAI response to file: {save_error}")
            
            # Update usage tracking
            usage_tracker["total_calls"] += 1
            usage_tracker["total_input_tokens"] += response.usage.prompt_tokens
            usage_tracker["total_output_tokens"] += response.usage.completion_tokens
            usage_tracker["individual_calls"].append({
                "call_number": usage_tracker["total_calls"],
                "step": "prompt_enhancement",
                "model": "gpt-4o-mini-2024-07-18",
                "provider": "openai",
                "request_type": "chat_completion",
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "prompt_enhanced": True,
                "style_used": project_style
            })
            
            logger.info(f"✨ Enhanced prompt created: {enhanced_prompt[:100]}...")
            logger.info(f"📊 OpenAI usage: {response.usage.prompt_tokens} input + {response.usage.completion_tokens} output tokens")
            
            return enhanced_prompt
            
        except Exception as openai_error:
            logger.error(f"❌ OpenAI prompt enhancement failed: {openai_error}")
            raise openai_error
            
    except Exception as e:
        logger.error(f"Error in enhance_prompt_with_openai: {str(e)}", exc_info=True)
        raise e


def safe_update_progress(identifier: str, new_progress: int, redis_key: str, phase: str, extra_data: dict = None, force_update: bool = False):
    """
    SAFE PROGRESS UPDATE: Progress can ONLY go UP, NEVER DOWN
    force_update: Allow updating data even if progress doesn't change
    identifier: Can be request_id or blog_id
    """
    try:
        task_data = redis_client.get(redis_key)
        if not task_data:
            return
            
        task_info = json.loads(task_data)
        current_progress = task_info.get("steps", {}).get("image_generation", {}).get("progress", 0)
        
        # CRITICAL: Never go backwards (unless force_update for data)
        if new_progress < current_progress:
            logger.debug(f"🚫 Skipping progress update: {new_progress}% < current {current_progress}% for identifier: {identifier}")
            return
            
        # Skip if same progress and not forced
        if new_progress == current_progress and not force_update and not extra_data:
            logger.debug(f"🔄 Same progress {current_progress}%, skipping for identifier: {identifier}")
            return
            
        # Update progress safely
        task_info["steps"]["image_generation"]["progress"] = new_progress
        if "generation_data" not in task_info["steps"]["image_generation"]:
            task_info["steps"]["image_generation"]["generation_data"] = {}
            
        task_info["steps"]["image_generation"]["generation_data"]["phase"] = phase
        task_info["steps"]["image_generation"]["generation_data"]["last_updated"] = datetime.now(timezone.utc).isoformat()
        
        # Add extra data if provided
        if extra_data:
            for key, value in extra_data.items():
                task_info["steps"]["image_generation"]["generation_data"][key] = value
                
        redis_client.set(redis_key, json.dumps(task_info), ex=86400)
        
        # Log different messages for progress vs data updates
        if new_progress > current_progress:
            logger.info(f"⬆️ Progress: {current_progress}% → {new_progress}% [{phase}] for identifier: {identifier}")
        elif extra_data:
            logger.debug(f"📝 Data update: {new_progress}% [{phase}] for identifier: {identifier}")
        
    except Exception as e:
        logger.warning(f"Failed to safely update progress: {str(e)}")


@celery.task(name="app.tasks.featured_image_generation.generate_image_with_gemini", queue="image_generation", bind=True)
def generate_image_with_gemini(self, image_request: Dict[str, Any], project_id: str, project: Dict[str, Any], request_id: str, usage_tracker: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate featured image using Google Gemini Imagen with FIXED flow
    
    Args:
        image_request: Image generation request payload (contains blog content as "prompt")
        project_id: Project identifier
        project: Project information (contains featured_image_style)
        request_id: Unique request identifier
        usage_tracker: Token usage tracking dictionary
        
    Returns:
        Dictionary containing generated image data and metadata
    """
    try:
        # Set Sentry context for image generation step
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("task_name", "generate_image_with_gemini")
            scope.set_tag("step", "image_generation")
            scope.set_tag("request_id", request_id)
            scope.set_tag("project_id", project_id)
        
        logger.info(f"Starting AI-powered image generation pipeline for request_id: {request_id}")
        
        # Extract blog content and metadata
        blog_content = image_request.get("blog_content", "")  # Blog content from MongoDB
        country = image_request.get("country", "India")       # Country from MongoDB
        blog_id = image_request.get("blog_id", "")           # Blog ID for reference
        project_style = project.get("featured_image_style", "Realistic photography")  # From DB
        
        # Use blog_id as primary Redis key if available, fallback to request_id
        primary_key = blog_id if blog_id else request_id
        redis_key = f"featured_image_task:{primary_key}"
        redis_key_secondary = f"featured_image_task:{request_id}" if blog_id else None
        
        def update_dual_progress(progress: int, phase: str, extra_data: dict = None):
            """Update progress on both blog_id and request_id Redis keys"""
            safe_update_progress(primary_key, progress, redis_key, phase, extra_data)
            if redis_key_secondary:
                safe_update_progress(request_id, progress, redis_key_secondary, phase, extra_data)
        
        logger.info(f"Blog content: {len(blog_content)} characters, Country: {country}, Style: {project_style}")
        logger.info(f"Blog content preview: {blog_content[:200]}...")
        logger.info(f"Tracking with primary_key: {primary_key} (blog_id: {blog_id})")
        
        # Validate blog content is not empty
        if not blog_content or blog_content.strip() == "":
            logger.error(f"❌ Blog content is empty! Cannot enhance prompt.")
            raise Exception(f"Blog content is empty - cannot generate image without content. Blog ID: {blog_id}")
        
        # 📝 UPDATE MONGODB: Mark image generation as started in rayo_featured_image
        if blog_id:
            try:
                mongodb_service = MongoDBService()
                mongodb_service.init_sync_db()
                db = mongodb_service.get_sync_db()
                blogs_collection = db['blogs']
                
                start_data = {
                    "status": "generating",
                    "started_at": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat(),
                    "style": project_style,
                    "request_id": request_id
                }
                
                blogs_collection.update_one(
                    {"_id": ObjectId(blog_id)},
                    {"$set": {"rayo_featured_image": start_data}}
                )
                
                logger.info(f"📝 MongoDB: Started tracking image generation for blog {blog_id}")
            except Exception as mongo_error:
                logger.warning(f"⚠️ Failed to update MongoDB start status: {str(mongo_error)}")
        
        # STEP 1: Enhance prompt with OpenAI using our style system (5% → 20%)
        update_dual_progress(10, "enhancing_prompt")
        
        # Initialize enhanced_prompt variable
        enhanced_prompt = None
        
        # Call OpenAI to enhance the prompt
        try:
            logger.info(f"🤖 Calling OpenAI to enhance prompt for style: {project_style}")
            
            # Call the enhancement function directly (not as Celery task to avoid .get() issue)
            enhanced_prompt = call_openai_for_prompt_enhancement(
                blog_content=blog_content,
                project_style=project_style,
                country=country,
                request_id=request_id,
                usage_tracker=usage_tracker
            )
            
            logger.info(f"✨ OpenAI prompt enhancement completed")
            logger.info(f"🔍 Enhanced prompt type: {type(enhanced_prompt)}")
            logger.info(f"🔍 Enhanced prompt length: {len(enhanced_prompt) if enhanced_prompt else 'None'}")
            logger.info(f"🔍 Enhanced prompt repr: {repr(enhanced_prompt)}")
            logger.info(f"Enhanced prompt: {enhanced_prompt}")
            
            # Update progress - prompt enhanced (20%)
            update_dual_progress(20, "prompt_enhanced", {
                "enhanced_prompt": enhanced_prompt[:100] + "..." if len(enhanced_prompt) > 100 else enhanced_prompt,
                "enhancement_method": "openai_enhancement",
                "original_prompt": blog_content[:100] + "...",
                "style_used": project_style
            })
            
        except Exception as openai_error:
            logger.error(f"❌ OpenAI enhancement failed: {openai_error}")
            # No fallback - re-raise the exception to fail the task
            raise Exception(f"Prompt enhancement failed: {str(openai_error)}")
        
        # STEP 2: Generate image with Gemini (20% → 100%)
        logger.info(f"🎨 Starting Gemini image generation with enhanced prompt")
        
        # Initialize Google GenAI client
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise Exception("GEMINI_API_KEY or GOOGLE_API_KEY environment variable not found")
        
        logger.info(f"🔑 Gemini API key configured successfully")
        client = genai.Client(api_key=api_key)
        
        # Update progress - API client initialized (30%)
        update_dual_progress(30, "gemini_api_initialized")
        
        # Validate enhanced prompt before sending to Gemini
        if not enhanced_prompt or enhanced_prompt.strip() == "":
            logger.error(f"❌ Enhanced prompt is empty! Cannot generate image.")
            raise Exception(f"Enhanced prompt is empty - OpenAI enhancement may have failed. Blog content length: {len(blog_content)}")
        
        # Generate image with Gemini using enhanced prompt
        logger.info(f"🎨 Calling Gemini Imagen API with enhanced prompt for request_id: {request_id}")
        logger.info(f"🎨 Enhanced prompt being sent to Gemini: {enhanced_prompt}")
        
        # Save enhanced prompt to txt file for debugging/analysis
        try:
            logs_dir = "logs/gemini_prompts"
            os.makedirs(logs_dir, exist_ok=True)
            
            prompt_filename = f"gemini_prompt_{request_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            prompt_filepath = os.path.join(logs_dir, prompt_filename)
            
            with open(prompt_filepath, 'w', encoding='utf-8') as f:
                f.write(f"Gemini Imagen API Prompt - Request ID: {request_id}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"Project Style: {project_style}\n")
                f.write(f"Country: {country}\n")
                f.write("=" * 80 + "\n\n")
                
                f.write("ENHANCED PROMPT FOR GEMINI:\n")
                f.write("-" * 40 + "\n")
                f.write(str(enhanced_prompt) + "\n\n")
                
                f.write("GEMINI CONFIG:\n")
                f.write("-" * 40 + "\n")
                f.write(f"Model: models/imagen-4.0-generate-001\n")
                f.write(f"Number of images: 1\n")
                f.write(f"Output format: image/jpeg\n")
                f.write(f"Aspect ratio: 16:9 (HARDCODED)\n")
                f.write(f"Image size: 2K\n")
            
            logger.info(f"📄 Gemini prompt saved to: {prompt_filepath}")
            
        except Exception as save_error:
            logger.warning(f"⚠️ Failed to save Gemini prompt to file: {save_error}")
        
        # Save Gemini API payload before call
        try:
            gemini_payload = {
                "model": "models/imagen-4.0-generate-001",
                "prompt": enhanced_prompt,
                "config": {
                    "number_of_images": 1,
                    "output_mime_type": "image/jpeg",
                    "aspect_ratio": "16:9",
                    "image_size": "2K"
                }
            }
            
            with open(prompt_filepath, 'a', encoding='utf-8') as f:
                f.write("\nGEMINI API PAYLOAD:\n")
                f.write("-" * 40 + "\n")
                f.write(json.dumps(gemini_payload, indent=2, ensure_ascii=False))
                f.write("\n")
            
            logger.info(f"📄 Gemini payload saved to: {prompt_filepath}")
        except Exception as save_error:
            logger.warning(f"⚠️ Failed to save Gemini payload to file: {save_error}")
        
        # PRIMARY ATTEMPT: Generate image with Gemini with retry logic
        gemini_success = False
        gemini_error = None
        result = None
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🔄 Gemini attempt {attempt + 1}/{max_retries} for request_id: {request_id}")
                
                # FIXED: Use correct Google Gemini API parameters (from official example)
                result = client.models.generate_images(
                    model="models/imagen-4.0-generate-001",
                    prompt=enhanced_prompt,
                    config=dict(
                        number_of_images=1,
                        output_mime_type="image/jpeg",
                        aspect_ratio="16:9",
                        image_size="2K"
                    ),
                )
                
                # Validate result
                if not result.generated_images:
                    raise Exception("No images generated by Gemini API")
                
                gemini_success = True
                logger.info(f"✅ Gemini attempt {attempt + 1} succeeded for request_id: {request_id}")
                break  # Success - exit retry loop
                
            except Exception as attempt_error:
                gemini_error = attempt_error
                logger.warning(f"⚠️ Gemini attempt {attempt + 1} failed: {str(attempt_error)}")
                
                if attempt == max_retries - 1:
                    # Final attempt failed
                    logger.error(f"❌ All {max_retries} Gemini attempts failed for request_id: {request_id}")
                    break
                else:
                    # Wait before retry with exponential backoff
                    wait_time = 2 ** attempt  # 1s, 2s, 4s
                    logger.info(f"🕐 Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
        
        # Check if Gemini succeeded
        if not gemini_success:
            logger.error(f"❌ Gemini image generation completely failed after {max_retries} attempts")
            raise gemini_error
        
        # Update progress - image generated (60%)
        update_dual_progress(60, "image_generated")

        if len(result.generated_images) != 1:
            logger.warning("Number of images generated does not match the requested number.")
        
        # Get the generated image
        generated_image = result.generated_images[0]
        
        # Extract image bytes from Google GenAI Image object
        logger.info(f"🖼️ Image object type: {type(generated_image.image)}")
        
        # Google GenAI Image object has direct access to image_bytes!
        if hasattr(generated_image.image, 'image_bytes'):
            raw_image_data = generated_image.image.image_bytes
            logger.info(f"✅ Successfully extracted {len(raw_image_data)} bytes from .image_bytes")
            logger.info(f"🖼️ Image mime_type: {getattr(generated_image.image, 'mime_type', 'unknown')}")
            
            # Check if data is base64 encoded (common with Google APIs)
            try:
                # Check if it starts with base64 JPEG header (/9j/)
                if isinstance(raw_image_data, bytes) and raw_image_data.startswith(b'/9j/'):
                    logger.info("🔧 Detected base64-encoded image data - decoding...")
                    import base64
                    image_content = base64.b64decode(raw_image_data)
                    logger.info(f"✅ Decoded to {len(image_content)} raw bytes")
                else:
                    image_content = raw_image_data
                    logger.info("📦 Using raw bytes directly")
                
                # Verify JPEG header after potential decoding
                if image_content[:3] == b'\xff\xd8\xff':
                    logger.info("✅ Valid JPEG magic bytes detected")
                else:
                    logger.warning(f"⚠️ Unexpected image header: {image_content[:10].hex()}")
                
            except Exception as decode_error:
                logger.warning(f"⚠️ Base64 decode failed, using raw data: {decode_error}")
                image_content = raw_image_data
            
            # DEBUG: Test image data with PIL
            try:
                import io
                from PIL import Image as PILImage
                image_stream = io.BytesIO(image_content)
                with PILImage.open(image_stream) as test_img:
                    logger.info(f"🔍 DEBUG: Image validation successful - {test_img.size}, format: {test_img.format}")
            except Exception as validation_error:
                logger.warning(f"⚠️ PIL validation still failed - {validation_error}")
                logger.info(f"🔍 Continuing with upload anyway - {len(image_content)} bytes")
                # Continue anyway - storage upload may still work
            
        else:
            raise Exception("Google GenAI Image object missing expected 'image_bytes' attribute")
        
        # Update progress - image processed (75%)
        update_dual_progress(75, "image_processed", {
            "image_size_bytes": len(image_content)
        })
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"featured_image_{timestamp}_{request_id[:8]}.jpg"
        
        # Upload to Supabase Storage
        logger.info(f"☁️ Uploading enhanced image to storage for request_id: {request_id}")
        import asyncio
        
        async def upload_image():
            storage_service = get_storage_service()  # Auto-detects provider
            await storage_service.create_bucket_if_not_exists()
            
            return await storage_service.upload_project_file(
                project_id=project_id,
                user_id=project.get("user_id"),
                file_content=image_content,
                filename=filename,
                mime_type="image/jpeg",
                category="featured_image"
            )
        
        # Run the async upload in a sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            upload_result = loop.run_until_complete(upload_image())
        finally:
            loop.close()
        
        if not upload_result["success"]:
            raise Exception(f"Failed to upload image to storage: {upload_result.get('errors', [])}")
        
        # Update progress - image uploaded (90%)
        update_dual_progress(90, "image_uploaded", {
            "storage_url": upload_result["public_url"]
        })
        
        # Save to database with graceful error handling
        try:
            with get_db_session() as db:
                # Extract image dimensions
                width = height = None
                if upload_result["image_metadata"]:
                    width = upload_result["image_metadata"].get("width")
                    height = upload_result["image_metadata"].get("height")
                
                project_image = ProjectImage(
                    project_id=project_id,
                    user_id=project.get("user_id"),
                    filename=upload_result["filename"],
                    original_filename=upload_result["original_filename"],
                    file_size=upload_result["file_size"],
                    mime_type=upload_result["mime_type"],
                    storage_path=upload_result["storage_path"],
                    bucket_name="images",  # Add the bucket name field
                    public_url=upload_result["public_url"],
                    image_metadata=upload_result["image_metadata"],
                    width=width,
                    height=height,
                    category="featured_image",
                    description=f"AI-generated featured image ({project_style}): {enhanced_prompt[:100]}"
                )
                
                db.add(project_image)
                db.commit()
                db.refresh(project_image)
                
                image_id = str(project_image.id)
                logger.info(f"✅ Image saved to database with ID: {image_id}")
                
        except Exception as db_error:
            logger.error(f"❌ Database save failed: {str(db_error)}")
            logger.warning("⚠️ Continuing execution - image already uploaded to storage successfully")
            # Generate a fallback ID for the response
            image_id = f"img_{request_id[:8]}_{int(time.time())}"
            logger.info(f"⚠️ Using fallback image_id: {image_id} due to DB error")
        
        # Update usage tracker for Gemini call
        usage_tracker["total_calls"] += 1
        usage_tracker["individual_calls"].append({
            "call_number": usage_tracker["total_calls"],
            "step": "image_generation",
            "model": "imagen-4.0-generate-001",
            "provider": "google",
            "request_type": "image_generation",
            "prompt_length": len(enhanced_prompt),
            "image_generated": True,
            "style_used": project_style
        })
        
        # Final completion (100%)
        update_dual_progress(100, "completed", {
            "image_id": image_id,
            "public_url": upload_result["public_url"],
            "filename": filename,
            "style_used": project_style
        })
        
        # Mark task as completed in Redis (both keys)
        try:
            # Update primary key (blog_id)
            task_data = redis_client.get(redis_key)
            if task_data:
                task_info = json.loads(task_data)
                task_info["status"] = "completed"
                task_info["steps"]["image_generation"]["status"] = "completed"
                task_info["steps"]["image_generation"]["progress"] = 100
                task_info["final_result"] = {
                    "image_id": image_id,
                    "public_url": upload_result["public_url"],
                    "filename": filename,
                    "enhanced_prompt": enhanced_prompt,
                    "style_used": project_style
                }
                redis_client.set(redis_key, json.dumps(task_info), ex=86400)
            
            # Update secondary key (request_id) if different
            if redis_key_secondary and redis_key_secondary != redis_key:
                redis_client.set(redis_key_secondary, json.dumps(task_info), ex=86400)
                
            logger.info(f"🎯 Task completed for request_id: {request_id}")
        except Exception as completion_error:
            logger.error(f"Failed to mark task completion: {str(completion_error)}")
        
        # NEW: Update MongoDB blog document with featured image details
        try:
            blog_id = image_request.get("blog_id")  # Get blog_id from request
            if blog_id:
                logger.info(f"📝 Updating MongoDB blog {blog_id} with featured image details")
                
                # Prepare featured image data for MongoDB
                rayo_featured_image = {
                    "status": "completed",
                    "completed_at": datetime.now(timezone.utc),
                    "url": upload_result["public_url"],
                    "id": image_id,
                    "filename": upload_result["original_filename"] or filename,
                    "storage_path": upload_result["storage_path"],
                    "created_at": datetime.now(timezone.utc),
                    "style_used": project_style,
                    "generation_method": "gemini_imagen",
                    "image_metadata": upload_result.get("image_metadata", {}),
                    "file_size": upload_result.get("file_size", 0),
                    "request_id": request_id
                }
                
                logger.info(f"📝 Featured image data to save: {rayo_featured_image}")
                
                # Update the blog document in MongoDB
                mongodb_service = MongoDBService()
                mongodb_service.init_sync_db()
                
                update_result = mongodb_service.get_sync_db()['blogs'].update_one(
                    {'_id': ObjectId(blog_id)},
                    {
                        '$set': {
                            'rayo_featured_image': rayo_featured_image,
                            'updated_at': datetime.now(timezone.utc)
                        }
                    }
                )
                
                if update_result.modified_count > 0:
                    logger.info(f"✅ Successfully updated MongoDB blog {blog_id} with featured image: {image_id}")
                else:
                    logger.warning(f"⚠️ MongoDB blog {blog_id} not found for featured image update (matched: {update_result.matched_count})")
            else:
                logger.warning("⚠️ No blog_id provided in image_request - skipping MongoDB update")
                
        except Exception as mongo_error:
            logger.error(f"❌ Failed to update MongoDB blog with featured image: {str(mongo_error)}")
            logger.exception("Full MongoDB update error traceback:")
            # Don't fail the whole process - image was still created successfully

        # Record usage for billing (similar to blog generation)
        if usage_tracker.get("total_calls", 0) > 0 and usage_tracker.get("user_id"):
            try:
                from app.services.enhanced_llm_usage_service import EnhancedLLMUsageService
                from app.config.service_multipliers import get_service_multiplier
                
                with get_db_session() as db:
                    llm_usage_service = EnhancedLLMUsageService(db)
                    
                    # Calculate base cost for image generation
                    base_cost = 0.05  # Example cost for image generation
                    
                    # Get service multiplier
                    service_multiplier_data = get_service_multiplier("featured_image_generation")
                    service_multiplier = service_multiplier_data["multiplier"]
                    
                    image_metadata = {
                        "image_generation_stats": {
                            "total_api_calls": usage_tracker["total_calls"],
                            "request_id": usage_tracker["request_id"],
                            "image_id": image_id,
                            "generation_method": "gemini_imagen",
                            "style_used": project_style
                        },
                        "individual_api_calls": usage_tracker["individual_calls"]
                    }
                    
                    billing_result = llm_usage_service.usage_service.record_usage_and_charge(
                        user_id=usage_tracker["user_id"],
                        service_name="featured_image_generation",
                        base_cost=base_cost,
                        multiplier=service_multiplier,
                        service_description=f"Featured image generation ({project_style}) - {usage_tracker['total_calls']} API calls",
                        usage_data=image_metadata,
                        project_id=project_id
                    )
                    
                    logger.info(f"✅ IMAGE GENERATION BILLING RECORDED: {usage_tracker['total_calls']} calls, "
                               f"${billing_result.get('actual_charge', 0):.6f} charged")
                    
            except Exception as e:
                logger.error(f"❌ Failed to record image generation usage: {e}")
        
        logger.info(f"Featured image generation completed for request_id: {request_id}")
        
        return {
            "request_id": request_id,
            "image_id": image_id,
            "public_url": upload_result["public_url"],
            "filename": filename,
            "enhanced_prompt": enhanced_prompt,
            "style_used": project_style,
            "status": "completed",
            "usage_summary": {
                "total_calls": usage_tracker.get("total_calls", 0),
                "generation_method": "gemini_imagen"
            }
        }
        
    except Exception as e:
        # Capture exception in Sentry with context
        sentry_sdk.capture_exception(e, extra={
            "request_id": request_id,
            "project_id": project_id,
            "task_name": "generate_image_with_gemini"
        })
        logger.error(f"Error in generate_image_with_gemini: {str(e)}", exc_info=True)
        
        # Update MongoDB with failure status
        try:
            blog_id = image_request.get("blog_id")
            if blog_id:
                logger.info(f"📝 Updating MongoDB blog {blog_id} with failure status")
                
                failure_data = {
                    "status": "failed",
                    "failed_at": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat(),
                    "error": str(e),
                    "request_id": request_id,
                    "style_attempted": project.get("featured_image_style", "unknown")
                }
                
                mongodb_service = MongoDBService()
                mongodb_service.init_sync_db()
                
                mongodb_service.get_sync_db()['blogs'].update_one(
                    {'_id': ObjectId(blog_id)},
                    {
                        '$set': {
                            'rayo_featured_image': failure_data,
                            'updated_at': datetime.now(timezone.utc)
                        }
                    }
                )
                
                logger.info(f"✅ Successfully updated MongoDB blog {blog_id} with failure status")
        except Exception as mongo_error:
            logger.error(f"❌ Failed to update MongoDB failure status: {str(mongo_error)}")
        
        # Update Redis with error (both keys)
        try:
            task_data = redis_client.get(redis_key)
            if task_data:
                task_info = json.loads(task_data)
                task_info["steps"]["image_generation"]["status"] = "failed"
                task_info["steps"]["image_generation"]["error"] = str(e)
                task_info["status"] = "failed"
                redis_client.set(redis_key, json.dumps(task_info), ex=86400)
                
                # Update secondary key too
                if redis_key_secondary and redis_key_secondary != redis_key:
                    redis_client.set(redis_key_secondary, json.dumps(task_info), ex=86400)
        except Exception as redis_error:
            logger.warning(f"Failed to update Redis error status: {str(redis_error)}")
        
        raise


@celery.task(name="app.tasks.featured_image_generation.get_featured_image_status", queue="image_generation")
def get_featured_image_status(request_id: str) -> Dict[str, Any]:
    """
    Get comprehensive status for featured image generation
    
    Args:
        request_id: Image generation request ID
        
    Returns:
        Dictionary containing status information in frontend-expected format
    """
    start_time = time.time()
    logger.info(f"🔍 [STATUS_BY_REQUEST] Starting status check for request_id: {request_id}")
    
    try:
        redis_key = f"featured_image_task:{request_id}"
        logger.debug(f"🔍 [STATUS_BY_REQUEST] Using Redis key: {redis_key}")
        
        try:
            task_data = redis_client.get(redis_key)
            logger.debug(f"🔍 [STATUS_BY_REQUEST] Redis get operation completed (data length: {len(task_data) if task_data else 0})")
        except Exception as redis_error:
            logger.error(f"❌ [STATUS_BY_REQUEST] Redis connection error: {str(redis_error)}")
            raise redis_error
        
        if not task_data:
            elapsed_time = time.time() - start_time
            logger.warning(f"⚠️ [STATUS_BY_REQUEST] No task data found for request_id: {request_id} (took {elapsed_time:.3f}s)")
            return {
                "status": "not_found",
                "progress": 0,
                "message": "No task data found for this request",
                "request_id": request_id,
                "debug_info": f"No data in Redis key: {redis_key}, took {elapsed_time:.3f}s"
            }
        
        try:
            task_info = json.loads(task_data)
            logger.debug(f"✅ [STATUS_BY_REQUEST] Successfully parsed JSON data")
        except Exception as json_error:
            logger.error(f"❌ [STATUS_BY_REQUEST] JSON parsing error: {str(json_error)}")
            logger.error(f"❌ [STATUS_BY_REQUEST] Raw data preview: {task_data[:200]}...")
            raise json_error
        
        # Get overall progress from both steps
        steps = task_info.get("steps", {})
        logger.debug(f"🔍 [STATUS_BY_REQUEST] Available steps: {list(steps.keys())}")
        
        try:
            prompt_progress = int(steps.get("prompt_enhancement", {}).get("progress", 0))
            image_progress = int(steps.get("image_generation", {}).get("progress", 0))
            logger.debug(f"🔍 [STATUS_BY_REQUEST] Progress - Prompt: {prompt_progress}%, Image: {image_progress}%")
        except (ValueError, TypeError) as progress_error:
            logger.error(f"❌ [STATUS_BY_REQUEST] Progress conversion error: {str(progress_error)}")
            prompt_progress = image_progress = 0
        
        # Overall progress is the maximum of both steps since they run sequentially
        overall_progress = max(prompt_progress, image_progress)
        # Cap progress at 100% to prevent overflow
        overall_progress = min(overall_progress, 100)
        
        logger.debug(f"🔍 [STATUS_BY_REQUEST] Calculated overall progress: {overall_progress}%")
        
        # Map internal status to frontend-expected status
        internal_status = task_info.get("status", "unknown")
        logger.debug(f"🔍 [STATUS_BY_REQUEST] Internal status: {internal_status}")
        
        if internal_status in ["running", "processing"]:
            frontend_status = "in_progress"
            message = "Featured image generation in progress"
        elif internal_status == "completed":
            frontend_status = "completed"
            message = "Featured image generation completed successfully"
        elif internal_status == "failed":
            frontend_status = "failed"
            message = "Featured image generation failed"
        else:
            frontend_status = "in_progress"
            message = "Featured image generation in progress"
        
        logger.info(f"📊 [STATUS_BY_REQUEST] Status mapping: {internal_status} → {frontend_status} ({overall_progress}%)")
        
        # Extract final result if available
        final_result = task_info.get("final_result", {})
        if final_result:
            logger.debug(f"🔍 [STATUS_BY_REQUEST] Final result available with keys: {list(final_result.keys())}")
        
        elapsed_time = time.time() - start_time
        logger.info(f"✅ [STATUS_BY_REQUEST] Successfully retrieved status for {request_id}: {frontend_status} ({overall_progress}%) in {elapsed_time:.3f}s")
        
        return {
            "status": frontend_status,
            "progress": overall_progress,
            "message": message,
            "request_id": request_id,
            "result": final_result if final_result else None
        }
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"❌ [STATUS_BY_REQUEST] Error getting featured image status for {request_id}: {str(e)} (took {elapsed_time:.3f}s)")
        logger.exception(f"❌ [STATUS_BY_REQUEST] Full error traceback for {request_id}:")
        
        return {
            "status": "failed",
            "progress": 0,
            "message": f"Error retrieving status: {str(e)}",
            "request_id": request_id,
            "debug_info": f"Error after {elapsed_time:.3f}s: {str(e)}"
        }


@celery.task(name="app.tasks.featured_image_generation.get_featured_image_status_by_blog_id", queue="image_generation")
def get_featured_image_status_by_blog_id(blog_id: str) -> Dict[str, Any]:
    """
    Get featured image generation status by blog_id (primary tracking method)
    
    Args:
        blog_id: Blog document ID
        
    Returns:
        Dictionary containing status information in frontend-expected format
    """
    start_time = time.time()
    logger.info(f"🔍 [STATUS_BY_BLOG] Starting status check for blog_id: {blog_id}")
    
    try:
        redis_key = f"featured_image_task:{blog_id}"
        logger.debug(f"🔍 [STATUS_BY_BLOG] Using Redis key: {redis_key}")
        
        try:
            task_data = redis_client.get(redis_key)
            logger.debug(f"🔍 [STATUS_BY_BLOG] Redis get operation completed (data length: {len(task_data) if task_data else 0})")
        except Exception as redis_error:
            logger.error(f"❌ [STATUS_BY_BLOG] Redis connection error: {str(redis_error)}")
            raise redis_error
        
        if not task_data:
            elapsed_time = time.time() - start_time
            logger.warning(f"⚠️ [STATUS_BY_BLOG] No task data found for blog_id: {blog_id} (took {elapsed_time:.3f}s)")
            return {
                "status": "not_found",
                "progress": 0,
                "message": "No featured image generation task found for this blog",
                "blog_id": blog_id,
                "result": None,
                "debug_info": f"No data in Redis key: {redis_key}, took {elapsed_time:.3f}s"
            }
        
        try:
            task_info = json.loads(task_data)
            logger.debug(f"✅ [STATUS_BY_BLOG] Successfully parsed JSON data with keys: {list(task_info.keys())}")
        except Exception as json_error:
            logger.error(f"❌ [STATUS_BY_BLOG] JSON parsing error: {str(json_error)}")
            logger.error(f"❌ [STATUS_BY_BLOG] Raw data preview: {task_data[:200]}...")
            raise json_error
        
        # Get overall progress from image generation step  
        steps = task_info.get("steps", {})
        image_step = steps.get("image_generation", {})
        
        logger.debug(f"🔍 [STATUS_BY_BLOG] Available steps: {list(steps.keys())}")
        logger.debug(f"🔍 [STATUS_BY_BLOG] Image step keys: {list(image_step.keys())}")
        
        try:
            raw_progress = image_step.get("progress", 0)
            overall_progress = int(raw_progress)
            overall_progress = min(overall_progress, 100)  # Cap at 100%
            logger.debug(f"🔍 [STATUS_BY_BLOG] Progress: {raw_progress} → {overall_progress}%")
        except (ValueError, TypeError) as progress_error:
            logger.error(f"❌ [STATUS_BY_BLOG] Progress conversion error: {str(progress_error)}, raw value: {image_step.get('progress', 'N/A')}")
            overall_progress = 0
        
        
        # Map internal status to frontend-expected status
        internal_status = task_info.get("status", "unknown")
        logger.debug(f"🔍 [STATUS_BY_BLOG] Internal status: {internal_status}")
        
        if internal_status in ["running", "processing"]:
            frontend_status = "in_progress"
            message = "Featured image generation in progress"
        elif internal_status == "completed":
            frontend_status = "completed"
            message = "Featured image generation completed successfully"
        elif internal_status == "failed":
            frontend_status = "failed"
            message = "Featured image generation failed"
            # Log error details if available
            error_info = image_step.get("error", "Unknown error")
            logger.error(f"❌ [STATUS_BY_BLOG] Task failed for blog_id {blog_id}: {error_info}")
        else:
            frontend_status = "in_progress"
            message = "Featured image generation in progress"
        
        logger.info(f"📊 [STATUS_BY_BLOG] Status mapping: {internal_status} → {frontend_status} ({overall_progress}%)")
        
        # Extract final result if available
        final_result = task_info.get("final_result", {})
        if final_result:
            logger.debug(f"🔍 [STATUS_BY_BLOG] Final result available with keys: {list(final_result.keys())}")
        
        # Get request_id for debugging
        request_id = task_info.get("request_id")
        logger.debug(f"🔍 [STATUS_BY_BLOG] Associated request_id: {request_id}")
        
        elapsed_time = time.time() - start_time
        logger.info(f"✅ [STATUS_BY_BLOG] Successfully retrieved status for {blog_id}: {frontend_status} ({overall_progress}%) in {elapsed_time:.3f}s")
        
        return {
            "status": frontend_status,
            "progress": overall_progress,
            "message": message,
            "blog_id": blog_id,
            "request_id": request_id,  # Include request_id for debugging
            "result": final_result if final_result else None
        }
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"❌ [STATUS_BY_BLOG] Error getting featured image status for blog_id {blog_id}: {str(e)} (took {elapsed_time:.3f}s)")
        logger.exception(f"❌ [STATUS_BY_BLOG] Full error traceback for {blog_id}:")
        
        return {
            "status": "failed",
            "progress": 0,
            "message": f"Error retrieving status: {str(e)}",
            "blog_id": blog_id,
            "result": None,
            "debug_info": f"Error after {elapsed_time:.3f}s: {str(e)}"
        }


@celery.task(name="app.tasks.featured_image_generation.retry_featured_image", queue="image_generation", bind=True)
def retry_featured_image(self, blog_id: str, project_id: str, project: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retry featured image generation for a blog
    Simply calls the main generate_featured_image task again
    
    Args:
        blog_id: Blog document ID to retry image generation for
        project_id: Project identifier
        project: Project information dictionary
        
    Returns:
        Dictionary containing retry task results
    """
    try:
        logger.info(f"Retrying featured image generation for blog_id: {blog_id}")
        
        # Generate a new request_id for the retry
        retry_request_id = f"retry_{blog_id}_{str(uuid.uuid4())[:8]}"
        
        # Create image request from blog data
        mongo_service = MongoDBService()
        blog_doc = mongo_service.get_blog_by_id(blog_id)
        
        if not blog_doc:
            return {
                "success": False,
                "message": f"Blog document not found for blog_id: {blog_id}",
                "blog_id": blog_id
            }
        
        # Extract blog content for image generation
        blog_content = ""
        if blog_doc.get("generated_blog", {}).get("full_blog"):
            blog_content = blog_doc["generated_blog"]["full_blog"]
        elif blog_doc.get("final_blog"):
            blog_content = blog_doc["final_blog"]
        elif blog_doc.get("content"):
            blog_content = blog_doc["content"]
        else:
            return {
                "success": False,
                "message": "No blog content found to generate image from",
                "blog_id": blog_id
            }
        
        # Create image request payload
        image_request = {
            "blog_id": blog_id,
            "blog_content": blog_content,
            "country": blog_doc.get("country", "us"),
            "style": project.get("featured_image_style", "modern_minimalist")
        }
        
        # Launch retry task
        retry_task_result = generate_featured_image.delay(
            image_request=image_request,
            project_id=project_id,
            project=project,
            request_id=retry_request_id
        )
        
        logger.info(f"🔄 Launched featured image retry task for blog_id: {blog_id}, task_id: {retry_task_result.id}")
        
        return {
            "success": True,
            "message": "Featured image generation retry started successfully",
            "blog_id": blog_id,
            "new_task_id": retry_task_result.id,
            "request_id": retry_request_id,
            "status": "processing"
        }
        
    except Exception as e:
        logger.error(f"Error retrying featured image generation for blog_id {blog_id}: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to retry featured image generation: {str(e)}",
            "blog_id": blog_id
        }


def safe_update_image_progress(blog_id: str, request_id: str, progress: int, phase: str, additional_data: Dict[str, Any] = None):
    """
    Safely update image generation progress in Redis with dual key support
    Similar to blog generation v2 progress tracking
    
    Args:
        blog_id: Blog document ID (primary tracking key)
        request_id: Request ID (secondary tracking key) 
        progress: Progress percentage (0-100)
        phase: Current processing phase
        additional_data: Optional additional data to store
    """
    try:
        # Get current task data
        redis_key_blog = f"featured_image_task:{blog_id}"
        redis_key_request = f"featured_image_task:{request_id}"
        
        current_data = redis_client.get(redis_key_blog)
        if current_data:
            task_data = json.loads(current_data)
        else:
            # Create new task data if not exists
            task_data = {
                "blog_id": blog_id,
                "request_id": request_id,
                "status": "processing",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "steps": {
                    "image_generation": {"status": "running", "progress": 0}
                }
            }
        
        # Update progress and phase
        if "steps" not in task_data:
            task_data["steps"] = {}
        if "image_generation" not in task_data["steps"]:
            task_data["steps"]["image_generation"] = {}
            
        task_data["steps"]["image_generation"]["progress"] = progress
        task_data["steps"]["image_generation"]["phase"] = phase
        task_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        # Add additional data if provided
        if additional_data:
            if "generation_data" not in task_data["steps"]["image_generation"]:
                task_data["steps"]["image_generation"]["generation_data"] = {}
            task_data["steps"]["image_generation"]["generation_data"].update(additional_data)
        
        # Store in both Redis keys
        task_data_json = json.dumps(task_data)
        redis_client.set(redis_key_blog, task_data_json, ex=86400)  # 24 hours expiry
        redis_client.set(redis_key_request, task_data_json, ex=86400)
        
        logger.info(f"⬆️ Progress: {progress}% [{phase}] for blog_id: {blog_id}")
        
    except Exception as e:
        logger.error(f"Error updating image progress: {str(e)}")


def handle_image_stream(blog_id: str, request_id: str, phase: str, progress: int, content: str = None):
    """
    Handle image generation streaming updates
    Similar to blog generation v2 streaming but for image generation phases
    
    Args:
        blog_id: Blog document ID
        request_id: Request identifier
        phase: Current phase (e.g., 'enhancing_prompt', 'generating_image', 'uploading')
        progress: Progress percentage (0-100)
        content: Optional content/message for the phase
    """
    try:
        additional_data = {
            "phase": phase,
            "last_update": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat()
        }
        
        if content:
            additional_data["message"] = content
            
        safe_update_image_progress(blog_id, request_id, progress, phase, additional_data)
        
    except Exception as e:
        logger.error(f"Error handling image stream: {str(e)}")


@celery.task(name="app.tasks.featured_image_generation.get_featured_image_streaming_status_v2", queue="image_generation")
def get_featured_image_streaming_status_v2(identifier: str) -> Dict[str, Any]:
    """
    Get real-time streaming status for featured image generation (V2 with enhanced logging)
    Compatible with both blog_id and request_id identifiers
    Similar to blog generation v2 streaming status endpoint
    
    Args:
        identifier: Either blog_id or request_id
        
    Returns:
        Dictionary containing streaming status information
    """
    try:
        logger.info(f"Getting streaming status for identifier: {identifier}")
        
        # Try both Redis key patterns
        redis_keys = [
            f"featured_image_task:{identifier}",
            f"featured_image_task:{identifier}"
        ]
        
        task_data = None
        used_key = None
        
        for redis_key in redis_keys:
            task_data = redis_client.get(redis_key)
            if task_data:
                used_key = redis_key
                break
        
        if not task_data:
            return {
                "status": "not_found",
                "progress": 0,
                "phase": "unknown",
                "message": "No image generation task found",
                "identifier": identifier,
                "streaming": False
            }
        
        task_info = json.loads(task_data)
        
        # Get image generation progress
        image_step = task_info.get("steps", {}).get("image_generation", {})
        progress = min(int(image_step.get("progress", 0)), 100)
        
        # Get current phase and generation data
        generation_data = image_step.get("generation_data", {})
        current_phase = generation_data.get("phase", "unknown")
        
        # Map internal status to streaming status
        internal_status = task_info.get("status", "unknown")
        if internal_status in ["running", "processing"]:
            status = "streaming"
            streaming = True
            message = f"Image generation in progress - {current_phase}"
        elif internal_status == "completed":
            status = "completed"
            streaming = False
            message = "Featured image generated successfully"
        elif internal_status == "failed":
            status = "failed"
            streaming = False
            message = "Featured image generation failed"
        elif internal_status == "retrying":
            status = "retrying"
            streaming = True
            message = "Retrying image generation"
        else:
            status = "processing"
            streaming = True
            message = "Image generation starting"
        
        result = {
            "status": status,
            "progress": progress,
            "phase": current_phase,
            "message": message,
            "identifier": identifier,
            "streaming": streaming,
            "last_update": generation_data.get("last_update"),
            "request_id": task_info.get("request_id"),
            "blog_id": task_info.get("blog_id")
        }
        
        # Add result data if completed
        if internal_status == "completed" and "final_result" in task_info:
            final_result = task_info["final_result"]
            result.update({
                "image_url": final_result.get("public_url"),
                "image_id": final_result.get("image_id"),
                "enhanced_prompt": final_result.get("enhanced_prompt", "")[:100] + "..." if len(final_result.get("enhanced_prompt", "")) > 100 else final_result.get("enhanced_prompt", "")
            })
        
        return result
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"❌ [STREAMING_STATUS_V2] Error getting streaming status for {identifier}: {str(e)} (took {elapsed_time:.3f}s)")
        logger.exception(f"❌ [STREAMING_STATUS_V2] Full error traceback for {identifier}:")
        
        return {
            "status": "failed",
            "progress": 0,
            "phase": "error",
            "message": f"Error retrieving streaming status: {str(e)}",
            "identifier": identifier,
            "streaming": False,
            "debug_info": f"Error after {elapsed_time:.3f}s: {str(e)}"
        }