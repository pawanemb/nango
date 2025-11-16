"""
Blog Generation Free - Single-Step Process with 90fps Streaming
Advanced implementation using Claude Sonnet 3.7 for content generation
🚀 NOW INCLUDES: 90fps word-by-word streaming like PRO version
Matches pro version functionality with comprehensive humanization rules
"""

import json
import logging
import redis
import requests
import time
from datetime import datetime, timezone
from typing import Dict, Any
from bson import ObjectId
from app.celery_config import celery_app as celery
from app.services.mongodb_service import MongoDBService
# Removed brand tonality mapping imports - using raw JSON approach like pro version
import pytz
from app.core.config import settings
from app.db.session import get_db_session
import uuid
import os

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


# OpenAI client removed - using only Claude like pro version
import redis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis client for task metadata
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

@celery.task(name="app.tasks.blog_generation_free.generate_blog_free", queue="blog_generation", bind=True)
def generate_blog_free(self, blog_id: str, project_id: str, project: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main orchestrator task for V2 blog generation
    Retrieves data from MongoDB blog document created during step workflow

    Args:
        blog_id: MongoDB blog document ID
        project_id: Project identifier
        project: Project information

    Returns:
        Dictionary containing task results and metadata
    """
    try:
        # Set Sentry context for better error tracking
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("task_name", "generate_blog_free")
            scope.set_tag("blog_id", blog_id)
            scope.set_tag("project_id", project_id)

        logger.info(f"Starting blog generation FREE for blog_id: {blog_id}")

        # Initialize combined usage tracking for all API calls
        usage_tracker = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_calls": 0,
            "service_name": "blog_generation",
            "request_id": str(uuid.uuid4())[:8],
            "individual_calls": [],
            "user_id": project.get("user_id")
        }

        # Store task metadata in Redis
        task_info = {
            "main_task_id": self.request.id,
            "project_id": project_id,
            "blog_id": blog_id,
            "status": "processing",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "usage_tracker": usage_tracker,
            "steps": {
                "blog_generation": {"status": "pending", "progress": 0}
            }
        }

        redis_key = f"blog_generation_task:{blog_id}"
        redis_client.set(redis_key, json.dumps(task_info), ex=86400)  # 24 hour expiration

        # Direct single-step task execution (retrieves data from MongoDB)
        task_result = generate_final_blog_step.apply_async(
            args=[blog_id, project_id, project, usage_tracker]
        )
        
        # Update task info with task ID
        task_info["task_id"] = task_result.id
        redis_client.set(redis_key, json.dumps(task_info), ex=86400)
        
        logger.info(f"🚀 Blog generation FREE (90fps streaming) started for blog_id: {blog_id}, task_id: {task_result.id}")
        
        return {
            "main_task_id": self.request.id,
            "task_id": task_result.id,
            "blog_id": blog_id,
            "status": "processing",
            "message": "Blog generation FREE with 90fps streaming started successfully"
        }
        
    except Exception as e:
        # Capture exception in Sentry with context
        sentry_sdk.capture_exception(e, extra={
            "blog_id": blog_id,
            "project_id": project_id,
            "task_name": "generate_blog_free"
        })
        logger.error(f"Error in generate_blog_free: {str(e)}", exc_info=True)
        
        # Update MongoDB with error status
        try:
            mongodb_service = MongoDBService()
            mongodb_service.init_sync_db()
            mongodb_service.get_sync_db()['blogs'].update_one(
                {'_id': ObjectId(blog_id)},
                {'$set': {
                    'status': 'failed',
                    'error_message': str(e),
                    'updated_at': datetime.now(timezone.utc)
                }}
            )
        except Exception as mongo_error:
            logger.error(f"Failed to update MongoDB status: {str(mongo_error)}")
        
        # Update Redis with error
        try:
            task_info["status"] = "failed"
            task_info["error"] = str(e)
            redis_client.set(redis_key, json.dumps(task_info), ex=86400)
        except Exception as redis_error:
            logger.error(f"Failed to update Redis status: {str(redis_error)}")
        
        raise




def format_outline_for_prompt(outline):
    """
    Helper function to format outline for prompt - handles both simple list and complex dict formats
    
    Args:
        outline: Either a list of strings or a complex dictionary structure
        
    Returns:
        Formatted string suitable for prompt
    """
    if isinstance(outline, list):
        # Simple list format
        return "\n".join([f"{i+1}. {section}" for i, section in enumerate(outline)])
    elif isinstance(outline, dict):
        # Complex structure with sections, subsections, conclusion, FAQs
        formatted_parts = []
        
        # Process main sections
        if "sections" in outline:
            for i, section in enumerate(outline["sections"]):
                if isinstance(section, dict):
                    heading = section.get("heading", f"Section {i+1}")
                    formatted_parts.append(f"{i+1}. {heading}")
                    
                    # Process subsections if they exist
                    if "subsections" in section:
                        for j, subsection in enumerate(section["subsections"]):
                            formatted_parts.append(f"   {chr(ord('a') + j)}. {subsection}")
                else:
                    formatted_parts.append(f"{i+1}. {section}")
        
        # Add conclusion if present
        if "conclusion" in outline:
            formatted_parts.append(f"\n**Conclusion**: {outline['conclusion']}")
        
        # Add FAQs if present
        if "faqs" in outline:
            formatted_parts.append("\n**FAQ Section**:")
            for i, faq in enumerate(outline["faqs"]):
                formatted_parts.append(f"{i+1}. {faq}")
        
        return "\n".join(formatted_parts)
    else:
        # Fallback for other types
        return str(outline)


def safe_update_progress(blog_id: str, new_progress: int, redis_key: str, phase: str, extra_data: dict = None, force_update: bool = False):
    """
    SAFE PROGRESS UPDATE: Progress can ONLY go UP, NEVER DOWN
    force_update: Allow updating streaming data even if progress doesn't change
    """
    try:
        task_data = redis_client.get(redis_key)
        if not task_data:
            return
            
        task_info = json.loads(task_data)
        current_progress = task_info.get("steps", {}).get("blog_generation", {}).get("progress", 0)
        
        # CRITICAL: Never go backwards (unless force_update for streaming data)
        if new_progress < current_progress:
            logger.debug(f"🚫 Skipping progress update: {new_progress}% < current {current_progress}% for blog_id: {blog_id}")
            return
            
        # Skip if same progress and not forced
        if new_progress == current_progress and not force_update and not extra_data:
            logger.debug(f"🔄 Same progress {current_progress}%, skipping for blog_id: {blog_id}")
            return
            
        # Update progress safely
        task_info["steps"]["blog_generation"]["progress"] = new_progress
        if "streaming_data" in task_info["steps"]["blog_generation"]:
            task_info["steps"]["blog_generation"]["streaming_data"]["phase"] = phase
            task_info["steps"]["blog_generation"]["streaming_data"]["last_updated"] = datetime.now(timezone.utc).isoformat()
            
            # Add extra data if provided
            if extra_data:
                for key, value in extra_data.items():
                    task_info["steps"]["blog_generation"]["streaming_data"][key] = value
                    
        redis_client.set(redis_key, json.dumps(task_info), ex=86400)
        
        # Log different messages for progress vs data updates
        if new_progress > current_progress:
            logger.info(f"⬆️ Progress: {current_progress}% → {new_progress}% [{phase}] for blog_id: {blog_id}")
        elif extra_data:
            logger.debug(f"📝 Data update: {new_progress}% [{phase}] for blog_id: {blog_id}")
        
    except Exception as e:
        logger.warning(f"Failed to safely update progress: {str(e)}")


def process_smooth_content_streaming(blog_id: str, content_delta: str, current_content: str, content_buffer: str, redis_key: str, last_stream_time: float) -> tuple[str, bool, str, float]:
    """
    Process content delta for REAL 90fps word-by-word streaming with throttling
    Returns: (updated_buffer, should_stream, content_to_stream, new_stream_time)
    """
    try:
        import time
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

def handle_content_stream(blog_id: str, content: str, thinking_content: str, redis_key: str):
    """
    Handle content phase streaming updates - simplified for content-only streaming like pro version
    """
    try:
        content_word_count = len(content.split())
        
        # Update content data only (no thinking)
        extra_data = {
            "live_content": content,
            "content_word_count": content_word_count,
            "content_update_timestamp": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat()
        }
        
        # Get current progress and keep it the same
        task_data = redis_client.get(redis_key)
        if task_data:
            task_info = json.loads(task_data)
            current_progress = task_info.get("steps", {}).get("blog_generation", {}).get("progress", 85)
            safe_update_progress(blog_id, current_progress, redis_key, "content", extra_data)
        
        logger.debug(f"📝 Content update: {content_word_count} words for blog_id: {blog_id}")
        
    except Exception as e:
        logger.warning(f"Failed to update content stream: {str(e)}")




def update_streaming_phase(blog_id: str, phase: str, redis_key: str):
    """
    Update the current streaming phase
    """
    try:
        task_data = redis_client.get(redis_key)
        if task_data:
            task_info = json.loads(task_data)
            if "streaming_data" in task_info["steps"]["blog_generation"]:
                task_info["steps"]["blog_generation"]["streaming_data"]["phase"] = phase
                task_info["steps"]["blog_generation"]["streaming_data"]["phase_updated_at"] = datetime.now(timezone.utc).isoformat()
                redis_client.set(redis_key, json.dumps(task_info), ex=86400)
                
        logger.info(f"🔄 Phase updated to '{phase}' for blog_id: {blog_id}")
        
    except Exception as e:
        logger.warning(f"Failed to update streaming phase: {str(e)}")

def finalize_streaming_data(blog_id: str, final_content: str, thinking_content: str, word_count: int, redis_key: str):
    """
    Finalize streaming data when generation is complete
    """
    try:
        task_data = redis_client.get(redis_key)
        if task_data:
            task_info = json.loads(task_data)
            if "streaming_data" in task_info["steps"]["blog_generation"]:
                task_info["steps"]["blog_generation"]["streaming_data"]["phase"] = "completed"
                task_info["steps"]["blog_generation"]["streaming_data"]["is_streaming"] = False
                task_info["steps"]["blog_generation"]["streaming_data"]["final_content"] = final_content[:500] + "..." if len(final_content) > 500 else final_content
                task_info["steps"]["blog_generation"]["streaming_data"]["final_word_count"] = word_count
                task_info["steps"]["blog_generation"]["streaming_data"]["completed_at"] = datetime.now(timezone.utc).isoformat()
                # Don't set progress here - handled by safe_update_progress
                redis_client.set(redis_key, json.dumps(task_info), ex=86400)
                
        logger.info(f"✅ Streaming finalized: {word_count} words for blog_id: {blog_id}")
        
    except Exception as e:
        logger.warning(f"Failed to finalize streaming data: {str(e)}")

@celery.task(name="app.tasks.blog_generation_free.generate_final_blog_step", queue="blog_generation", bind=True)
def generate_final_blog_step(self, blog_id: str, project_id: str, project: Dict[str, Any], usage_tracker: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate final blog content using Claude 3.7 Sonnet
    Retrieves all data from MongoDB blog document

    Args:
        blog_id: MongoDB blog document ID
        project_id: Project identifier
        project: Project information
        usage_tracker: Usage tracking data

    Returns:
        Dictionary containing final blog content and metadata
    """
    try:
        # Use static specialty like pro version
        specialty_info = {"expertise": "Content Expert"}

        # 🚀 PRE-INITIALIZE MongoDB connection
        mongodb_service = MongoDBService()
        mongodb_service.init_sync_db()
        logger.info(f"📊 MongoDB pre-initialized for blog_id: {blog_id}")

        # Validate critical data exists
        if not blog_id:
            raise Exception("blog_id missing from parameters")
        if not usage_tracker:
            logger.warning("usage_tracker missing - initializing new tracker")
            usage_tracker = {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_calls": 0,
                "service_name": "blog_generation",
                "request_id": str(uuid.uuid4())[:8],
                "individual_calls": [],
                "user_id": project.get("user_id")
            }

        # 📦 RETRIEVE BLOG DOCUMENT FROM MONGODB
        logger.info(f"🔍 Retrieving blog document from MongoDB for blog_id: {blog_id}")
        blog_doc = mongodb_service.get_sync_db()['blogs'].find_one({"_id": ObjectId(blog_id)})

        if not blog_doc:
            raise Exception(f"Blog document not found: {blog_id}")

        logger.info(f"✅ Retrieved blog document for blog_id: {blog_id}")

        # 📦 EXTRACT DATA FROM MONGODB DOCUMENT
        logger.info("=" * 80)
        logger.info("🔍 STARTING DATA EXTRACTION FROM MONGODB (FREE TIER)")
        logger.info("=" * 80)

        # 1. Primary Keyword (latest from array)
        logger.info("📍 [1/11] Extracting PRIMARY KEYWORD...")
        primary_keyword_array = blog_doc.get("primary_keyword", [])
        logger.info(f"   → Found {len(primary_keyword_array)} items in primary_keyword array")
        logger.info(f"   → Raw array: {primary_keyword_array}")

        if not primary_keyword_array:
            raise Exception("No primary keyword found in blog document")

        primary_keyword_data = primary_keyword_array[-1]
        logger.info(f"   → Selected latest item (index -1): {primary_keyword_data}")

        # Handle both old format (string) and new format (dict)
        if isinstance(primary_keyword_data, str):
            primary_keyword = primary_keyword_data
        else:
            primary_keyword = primary_keyword_data.get("keyword", "")
        logger.info(f"   ✅ EXTRACTED: primary_keyword = '{primary_keyword}'")
        logger.info("")

        # 2. Secondary Keywords (latest selected ones)
        logger.info("📍 [2/11] Extracting SECONDARY KEYWORDS...")
        secondary_keywords_array = blog_doc.get("secondary_keywords", [])
        logger.info(f"   → Found {len(secondary_keywords_array)} items in secondary_keywords array")

        secondary_keywords = []
        if secondary_keywords_array:
            latest_secondary = secondary_keywords_array[-1]
            logger.info(f"   → Selected latest item (index -1): {latest_secondary}")

            # Handle different formats:
            # 1. Old format: single string
            # 2. Old format: list of strings
            # 3. New format: dict with "keywords" array
            if isinstance(latest_secondary, str):
                # Old format: single string
                secondary_keywords = [latest_secondary]
                logger.info(f"   ✅ EXTRACTED (old format - single string): secondary_keywords = {secondary_keywords}")
            elif isinstance(latest_secondary, list):
                # Old format: already a list of strings
                secondary_keywords = latest_secondary
                logger.info(f"   ✅ EXTRACTED (old format - list): secondary_keywords = {secondary_keywords}")
            else:
                # New format: dict with "keywords" array
                keywords_list = latest_secondary.get("keywords", [])
                logger.info(f"   → Found {len(keywords_list)} total keywords in latest item")

                # Get only selected keywords
                secondary_keywords = [
                    kw["keyword"] if isinstance(kw, dict) else kw
                    for kw in keywords_list
                    if (isinstance(kw, dict) and kw.get("selected", False)) or isinstance(kw, str)
                ]
                logger.info(f"   → Filtered to {len(secondary_keywords)} SELECTED keywords")
                logger.info(f"   ✅ EXTRACTED: secondary_keywords = {secondary_keywords}")
        else:
            logger.info(f"   ⚠️ No secondary keywords array found")
        logger.info("")

        # 3. Category and Subcategory (root level)
        logger.info("📍 [3/11] Extracting CATEGORY & SUBCATEGORY...")
        category = blog_doc.get("category", "")
        subcategory = blog_doc.get("subcategory", "")
        logger.info(f"   → MongoDB category (root level): '{category}'")
        logger.info(f"   → MongoDB subcategory (root level): '{subcategory}'")

        if not category:
            raise Exception("No category found in blog document")
        if not subcategory:
            raise Exception("No subcategory found in blog document")

        logger.info(f"   ✅ EXTRACTED: category = '{category}'")
        logger.info(f"   ✅ EXTRACTED: subcategory = '{subcategory}'")
        logger.info("")

        # 4. Selected Title (from root array or string)
        logger.info("📍 [4/11] Extracting SELECTED TITLE...")
        title_raw = blog_doc.get("title")

        if not title_raw:
            raise Exception("No title found in blog document")

        # Handle both string and array formats
        if isinstance(title_raw, str):
            # Old format: string directly
            logger.info(f"   → Title is a string (length: {len(title_raw)})")
            blog_title = title_raw
        elif isinstance(title_raw, list):
            # New format: array
            logger.info(f"   → Title is an array with {len(title_raw)} items")
            if not title_raw:
                raise Exception("Title array is empty")
            blog_title = title_raw[-1]  # Latest selected title
            logger.info(f"   → Selected latest item (index -1): '{blog_title}'")
        else:
            raise Exception(f"Unexpected title type: {type(title_raw).__name__}")

        logger.info(f"   ✅ EXTRACTED: blog_title = '{blog_title}'")
        logger.info("")

        # 5. Outline (latest from outlines array OR root level outline field)
        logger.info("📍 [5/11] Extracting OUTLINE...")
        outlines_array = blog_doc.get("outlines", [])
        logger.info(f"   → Found {len(outlines_array)} items in outlines array")

        outline = None
        if outlines_array:
            # New format: outline in outlines array
            latest_outline = outlines_array[-1]
            logger.info(f"   → Selected latest item from outlines array (index -1)")
            outline = latest_outline.get("outline", {})
        else:
            # Old format: check for root-level outline field
            logger.info(f"   ⚠️ No outlines array found, checking for root-level 'outline' field...")
            outline = blog_doc.get("outline", {})
            if outline:
                logger.info(f"   → Found outline at root level (old format)")

        if not outline:
            logger.error(f"   ❌ No outline found in either 'outlines' array or root level!")
            raise Exception("No outline found in blog document")

        logger.info(f"   → Extracted outline with {len(outline.get('sections', []))} sections")
        logger.info(f"   ✅ EXTRACTED: outline with structure: {list(outline.keys())}")
        logger.info("")

        # 6. Word Count (root level - can be string, int, or array)
        logger.info("📍 [6/11] Extracting WORD COUNT...")
        word_count_raw = blog_doc.get("word_count")
        logger.info(f"   → Raw word_count from MongoDB: {word_count_raw} (type: {type(word_count_raw).__name__})")

        if word_count_raw is None:
            logger.error(f"   ❌ No word_count found!")
            raise Exception("No word_count found in blog document")

        # Handle different types of word_count storage
        if isinstance(word_count_raw, list):
            # Array format: get latest
            logger.info(f"   → word_count is an array with {len(word_count_raw)} items")
            word_count = word_count_raw[-1]
        elif isinstance(word_count_raw, (int, str)):
            # Simple value (int or string)
            logger.info(f"   → word_count is a simple value")
            word_count = str(word_count_raw)
        else:
            logger.error(f"   ❌ Unexpected word_count type!")
            raise Exception(f"Unexpected word_count type: {type(word_count_raw).__name__}")

        logger.info(f"   ✅ EXTRACTED: word_count = '{word_count}'")
        logger.info("")

        # 7. Country and Intent (root level - optional fields)
        logger.info("📍 [7/11] Extracting COUNTRY & INTENT...")
        country = blog_doc.get("country", "")
        keyword_intent = blog_doc.get("intent", "")

        if not country:
            logger.warning(f"   ⚠️ No country found - using empty string")
            country = ""

        if not keyword_intent:
            logger.warning(f"   ⚠️ No intent found - using empty string")
            keyword_intent = ""

        logger.info(f"   → MongoDB country (root level): '{country}'")
        logger.info(f"   → MongoDB intent (root level): '{keyword_intent}'")
        logger.info(f"   ✅ EXTRACTED: country = '{country}'")
        logger.info(f"   ✅ EXTRACTED: keyword_intent = '{keyword_intent}'")
        logger.info("")

        # 8. Sources (if available)
        logger.info("📍 [8/11] Extracting SOURCES...")
        sources_array = blog_doc.get("sources", [])
        logger.info(f"   → Found {len(sources_array)} items in sources array")

        sources = []
        if sources_array:
            latest_sources = sources_array[-1]
            logger.info(f"   → Selected latest item (index -1)")
            sources = latest_sources.get("sources", [])
            logger.info(f"   ✅ EXTRACTED: {len(sources)} sources")
        else:
            logger.info(f"   ⚠️ No sources array found (optional field)")
        logger.info("")

        # 9. Brand Tonality
        logger.info("📍 [9/11] Extracting BRAND TONALITY...")
        brand_tonality = blog_doc.get("brand_tonality")
        logger.info(f"   → MongoDB brand_tonality (root level): {brand_tonality}")

        if not brand_tonality:
            logger.error(f"   ❌ No brand_tonality found!")
            raise Exception("No brand_tonality found in blog document")

        logger.info(f"   ✅ EXTRACTED: brand_tonality = {brand_tonality}")
        logger.info("")

        # 📝 FINAL SUMMARY LOG
        logger.info("=" * 80)
        logger.info("✅ DATA EXTRACTION COMPLETE - SUMMARY (FREE TIER)")
        logger.info("=" * 80)
        logger.info(f"[1] Primary Keyword:     '{primary_keyword}'")
        logger.info(f"[2] Secondary Keywords:  {secondary_keywords}")
        logger.info(f"[3] Category:            '{category}'")
        logger.info(f"[4] Subcategory:         '{subcategory}'")
        logger.info(f"[5] Blog Title:          '{blog_title}'")
        logger.info(f"[6] Outline Sections:    {len(outline.get('sections', []))} sections")
        logger.info(f"[7] Word Count:          '{word_count}'")
        logger.info(f"[8] Country:             '{country}'")
        logger.info(f"[9] Intent:              '{keyword_intent}'")
        logger.info(f"[10] Sources:            {len(sources)} sources")
        logger.info(f"[11] Brand Tonality:     {brand_tonality}")
        logger.info("=" * 80)
        logger.info("🚀 PROCEEDING TO BLOG GENERATION (FREE)...")
        logger.info("=" * 80)
        logger.info("")

        # Set Sentry context for blog generation step
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("task_name", "generate_final_blog_step")
            scope.set_tag("step", "blog_generation")
            scope.set_tag("blog_id", blog_id)
            scope.set_tag("project_id", project_id)
            scope.set_tag("specialty", specialty_info.get("expertise", ""))
            scope.set_context("generation_request", {
                "word_count": word_count,
                "category": category,
                "language_preference": project.get('languages', [])
            })

        logger.info(f"Starting final blog generation FREE for blog_id: {blog_id}")
        
        # Update Redis status - Blog generation processing started  
        redis_key = f"blog_generation_task:{blog_id}"
        try:
            task_data = redis_client.get(redis_key)
            if task_data:
                task_info = json.loads(task_data)
                task_info["steps"]["blog_generation"]["status"] = "processing"
                task_info["steps"]["blog_generation"]["progress"] = 5
                redis_client.set(redis_key, json.dumps(task_info), ex=86400)
        except Exception as redis_error:
            logger.warning(f"Failed to update Redis status: {str(redis_error)}")

        # Pass raw brand tonality data directly as JSON string
        raw_tonality_json = json.dumps(brand_tonality, indent=2) if brand_tonality else "No specific tonality specified"

        # Extract language preference from project
        language_preference = "English (USA)"  # Default fallback
        project_languages = project.get('languages', [])
        if project_languages and len(project_languages) > 0:
            language_preference = project_languages[0]
            logger.info(f"Extracted language preference from project: '{language_preference}'")
        else:
            logger.warning(f"No language preference found in project {project_id}, using default: '{language_preference}'")

        # Extract target gender from project
        target_gender = ', '.join(project.get('gender', [])) if project.get('gender') else ''
        
        # Format complex data for logging
        # Pass outline as raw JSON instead of formatting
        raw_outline = json.dumps(outline, indent=2) if isinstance(outline, (dict, list)) else str(outline)
        # Pass sources directly as raw JSON
        raw_sources = json.dumps(sources, indent=2) if isinstance(sources, (dict, list)) else str(sources)
        
        # Build comprehensive blog generation prompt
        blog_prompt = f"""

A. Tone, voice and humanisation - high priority
1. Human voice first: write like an expert explaining something to a smart peer. Avoid corporate filler and familiar AI clichés.
2. Use natural transitions, rhetorical questions sparingly, vivid verbs, precise nouns, and one or two short illustrative examples.
3. Use sentence variation and occasional parenthetical asides to break purely declarative patterns.
4. Match the requested style axes supplied in the input:
{raw_tonality_json}
Use these to set voice choices such as contractions, rhetorical devices, and sentence complexity.
5. Adopt a "Smart Colleague" Mental Model: Imagine you are writing this for an intelligent colleague in a different department. You don't need to over-explain basic concepts, but you do need to make your specialized knowledge clear and compelling. The tone should be helpful and confident. Use parenthetical asides (like this one) to add a bit of personality or clarify a minor point.

B. Examples for tone guidance - copy these if needed
- Human example sentence:
"Most teams approach content audits with a sense of dread, picturing endless spreadsheets and weeks of work. It doesn't have to be that way. A 'mini-audit' focused on just three things can often reveal 80% of the problems. First, look for cannibalization - multiple pages fighting for the same keyword and confusing Google. Second, hunt for 'zombie pages': old, thin content with zero traffic that just drains your site's authority. Finally, check for missed internal linking opportunities, which is often the fastest win of all. Fixing just these three issues can produce a noticeable lift in performance without boiling the ocean."
- AI-ish example to avoid:
  "In today's digital landscape, organisations must navigate the realm of content transformation to remain competitive."
  Replace that kind of sentence with concrete specifics.

C.
### Input Instructions:
Below is the blog input data in tag-placeholder format.  
Each <tag>{{}}</tag> holds the value you must use.  
Read all fields carefully and use them to create a single cohesive blog post.

i. <Title>{blog_title}</Title>
ii. Don’t assign the heading and subheading number in any kind of format unless mentioned in outline or steps subheadings.
iii. Always give the introduction of the blog (without sub-heading) seperately, whether or not it is mentioned in the outline.
iv. Always include the conclusion of the blog, and take its reference from the outline mentioned in the input. Keeps its heading the same as mentioned in the outline (Conclusion). However, do not give the conclusion of the blog strictly if the same is not mentioned as 'Conclusion' in the outline. This is critical for the success of the task.
v. Always include all the FAQs for the blog and answer each of them. Take its reference from the outline mentioned in the input.  Ignore this instruction, however, if its sub-heading is not mentioned in the outline.
vi. Understand the language preference of the blog between English (UK) and English (USA) from the input
vii. Strictly stick to the word count of {word_count} mentioned for the blog post to give your response. Allow a deviation of maximum 10% only.
viii. Understand the category and sub-category of the blog to understand the approach for writing the content.
ix. Process the input scraped content as an information source for all the sub-headings mentioned in the section. Process the information for each sub-heading or sub-section as references to produce content.
x. Take the reference of the understanding information in the scraped information input for conceptual understanding about the topic. Incorporate them naturally within the content without citing the source of information unless very necessary. In doing this, maintain the tonality instructions.
xi. Take the reference of the CITATIONS or Citation Information from the input to give source links. Use them for citing statistics, research, facts, figures, and key findings. Incorporate them naturally in the content, but give all the source links strictly immediately after the cited information using ONLY this format: [source_name]. Follow this checklist for citation-specific rules in your output: 	
When referencing statistics or research, use indirect speech for reporting.
Vary your approach to presenting data and findings. Avoid using templatised phrases like ‘according to’, ‘as per; etc. unless ver necessary.
Always give the link to the original source for citing the research, statistic, or key findings.
Use the exact anchor text format for citations: [<a href="https://example.com/page">SiteName</a>]
Mention the brand name of the source as it is and then include the source in the above manner.
In doing this, maintain tonality instructions.
xii. When citing sources, use the 'url' field for links. Extract key facts from 'understanding_information' and specific citations from 'citation_information'.
xiii. Do not include commonly used terms, cliches, and phrases by AI in writing blogs strictly. Avoid phrases like ‘picture this’, ‘in the ever evolving landscape…’ etc. This is critical for the success of the job. 
xiv. Avoid commonly used words by AI in writing blogs. Eg, ‘landscape’, ‘navigate’, ‘realm’, ‘transformation’ etc. Aim for a natural and simpler variation for such words. This is critical for the success of the job. 

SEO Instructions:

i. Understand the primary keyword mentioned in the input and incorporate it naturally to maintain the keyword density of 1-1.5%.
ii. Understand the secondary keywords and incorporate them naturally throughout the content.
iii. Do not include the title of the blog in your response.

Text Formatting Instructions:
Incorporate these text formatting elements in the blog content on the basis of their applicability such that, the readers can skim through the blog easily while retaining information about key concepts easily make sure it will be in html format align with our final response formatting :
i. Lists
Bulleted lists (•): Use them when
Presenting non-sequential items like features, benefits, tips, key takeaways etc.
Breaking dense paragraphs into scannable points in any section of the outline.
Summarising information into broken-down lists
Numbered lists (1, 2, 3): Use them when
The order matters, such as steps, processes, workflows, timelines, or rankings.
Checklists (✓): Use them when
Readers need to verify the readiness or completion of actions suggested in the information.   
Nested lists: Use them when
You need to establish hierarchy between the main points with sub-points, categories with examples, steps with sub-steps, etc.
ii. Tables
Simple 2-column tables (term vs definition): Use them when
Each row pairs a short label on the left with a concise explanation or value on the right. For example, term vs definition, feature vs description, metric vs value, problem vs fix.
Multi-column tables (side-by-side comparisons): Use them when
Comparing 2 to 5 items side by side on consistent criteria.
Highlighted rows and columns for emphasis: Use them when
You need to draw attention to a recommended option, best value, or critical data.
iii. Block Formatting
Blockquotes (“ ”): Use them when
Citing an external expert, research line, policy excerpt, testimonial, or a crisp definition from an authority.
Emphasising a single striking insight or statistic that supports the surrounding text.
Code blocks (for technical content): Use them when
Showing commands, configuration, code snippets, API requests or responses, log excerpts, or error outputs.
Presenting technical steps where readers need to copy and run something exactly.
iv. Text Emphasis
Bold for keywords/numbers: Use them when
The primary keyword needs to be highlighted to help readers spot it.
A number-driven statistic needs a special attention of the reader
Italics for subtle emphasis: Use them when
Adding a nuance or a gentle aside in the sentence. Example, disclaimers, caveats, etc.
Monospace for commands/filenames: Use them when
Showing commands, flags, code identifiers, filenames, paths, or config keys inline.
Occasional ALL CAPS / small caps for emphasis: Use them when
You need to create a punchy emphasis on something, especially for blogs with a conversational tonality.
v. Dividers & Breaks
Section dividers (•••): Use them when
Breaking up long sections into digestible chunks without adding new headings.
Signalling a shift in focus, for example, from context to steps, or from analysis to examples.
Pros vs Cons lists: Use them when
The sections discuss advantages and drawbacks, considerations, or decision criteria.
Any comparison where both strengths and limitations matter for a balanced view.
Timelines (Year → Event): Use them when
You need to show important chronological developments. For example, event milestones, history, roadmap rollout, etc.







Writing Tonality Instructions:
{raw_tonality_json}
  



Input:
<Title>{blog_title}</Title>
<Primary Keyword>{primary_keyword}</Primary Keyword>
<Secondary Keywords>{', '.join(secondary_keywords)}</Secondary Keywords>
<Keyword Intent>{keyword_intent}</Keyword Intent>
<Category>{category}</Category>
<Subcategory>{subcategory}</Subcategory>
<Target Word Count>{word_count} words</Target Word Count>
<Target Gender>{target_gender}</Target Gender>
<Target Country>{country}</Target Country>
<Language Preference>{language_preference}</Language Preference>
<Outline>{raw_outline}</Outline> 
This is the scraped research data for some of the sub-headings of the blog in JSON format. Each source object contains essential fields: 'url', 'understanding_information', 'citation_information', 'section_title', and 'parent_section_title'. Use this structured input data to cite statistics, research, and facts naturally in the content: 
<Scraped Information>{raw_sources}</Scraped Information>


Output Instructions:
Give your response in the HTML format without leaving any comments or acknowledgment of the task. 
Do not include the title of the blog in your response. 
Do not change any heading or sub-heading mentioned in the outline from your end and give content for all of them. 
Do not include em dash (—) and n-dash ( – ) anywhere in your response strictly. This is critical for the success of the task. 
Give content for all the headings and sub-headings mentioned in the outline irrespective of whether or not you have its information in the scraped data input.
Give the source name with link only under [] with the format : [source_name]. This must be adhered strictly as it is critical for the success of the task. 
Do not give the response in markdown format very strictly. This is important for the success of the task. Only give the output in the HTML format. 



"""
        
        # Generate final blog content using Claude 3.7 Sonnet via streaming API
        headers = {
            "Content-Type": "application/json",
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "output-128k-2025-02-19"
        }
        
        payload = {
            "model": "claude-3-7-sonnet-20250219",
            "max_tokens": 128000,
            "temperature": 1.0,
            "stream": True,  # Enable streaming
            "system": f"""You are a senior editor and content strategist, known for a clear, direct, and engaging writing style. Your voice is that of a trusted expert who makes complex topics easy to understand without dumbing them down. You write from a strong perspective, aiming to deliver genuine insight, not just to list facts. You produce high quality, human-sounding, SEO-optimised blog posts in HTML. It is your job to minutely understand and follow the instructions that follow.

A. Core mandates
1. Use only the headings and subheadings provided in the input outline JSON. Do not invent, rename, renumber, reorder, or add any heading or subheading. Headings must appear exactly as in the outline.
2. Always write a short, engaging introduction paragraph before the first heading, even if the outline does not list an intro. Do not label it with a heading.
3. Only include a Conclusion section if the outline contains a heading exactly named "Conclusion". If the outline does not include a "Conclusion" heading, do not add one.
4. Final output must be valid HTML. No extra text outside the HTML. No JSON, no debugging, no commentary.
5. Do not include the blog title anywhere in the HTML body. The title field exists for metadata only.
6. Do not use em dash or en dash characters anywhere. Use the ASCII hyphen (-) only.
7. Do not number headings or subheadings unless numbering appears in the outline itself.
8. If any input field is missing or malformed, apply the fallback defaults below and proceed without asking clarifying questions:
   - language_preference -> "en-US"
   - word_count -> 800
   - primary_keyword -> none
   - secondary_keyword -> none
   - formality, attitude, energy, clarity -> "medium"
   - outline -> if missing, produce a short 800 word article with 3 headings: Overview, Key Points, Summary

B. Preflight validation - perform these checks internally and then proceed
1. Parse outline JSON and scraped_information input. Map scraped information to the matching section or subsection by heading text or provided key.
2. Detect language preference (en-GB or en-US) and use consistent spelling accordingly.
3. Confirm the numeric target word_count and set the acceptable range to word_count +/- 2%. Try to hit the center of that range. Do not exceed the word count +/- 2%.
4. Identify primary_keyword and secondary_keyword(s).
5. If primary_keyword is provided, aim for natural usage around 1.0% of the final word count, not exceeding 1.5%. Do not force phrases or break syntax for the keyword.
6. If scraped_information exists, treat it as source material and weave it into the relevant subsections.

C. Writing procedure - step by step
1. Write naturally first. Prioritise fluid, human phrasing. Think like an expert writing for a curious reader.
2. Vary sentence length and rhythm. Use active voice where appropriate. Contractions are allowed if the requested formality permits conversational tone.
3. Use concrete examples, specific numbers, short anecdotes, question prompts, and micro transitions such as "Here is why", "In practice", "What this means" to avoid robotic patterns.
4. Only after the prose reads natural and complete, apply structural HTML formatting (headings, paragraphs, lists, tables, blockquotes, code blocks) where they genuinely help scannability.
5. For each subsection: aim for coherent internal structure - a lead sentence, 1-3 supporting sentences, and optionally a short list or example.
6. If a subsection has no scraped info, produce a concise, accurate paragraph based on general domain knowledge but avoid unsupported factual claims.

D. SEO and citations
1. Use the primary keyword naturally in the introduction and 1-3 times through the body according to the density guideline. Use secondary keywords naturally across the content.
D. SEO and citations
1. Use the primary keyword naturally in the introduction and 1-3 times through the body according to the density guideline. Use secondary keywords naturally across the content.
2. When reporting statistics, studies or precise facts from the scraped_information, reference the original source using this exact anchor HTML format:
<a href="**[specific_source_url_here]**" class="ref">BrandName</a>
- The href attribute must be the full, direct URL to the specific article or page where the fact was found. Do not link to a generic homepage.
- The anchor text (BrandName) must be the brand or site name exactly as given in the source.
- Place citations inline where the referenced claim appears.
- Avoid templated lead-ins like always starting with "According to". Vary phrasing across the article.


3. Do not over cite. Use sources to support important claims only. Avoid a citation on every sentence.

E. Disallowed, avoidances and replacements
1. Avoid the following overused AI phrases and corporate clichés where possible:
   - landscape -> use "situation", "context", or a concrete phrase
   - navigate -> use "deal with", "handle", "use"
   - realm -> use "area" or "field"
   - transformation -> use "change" or "shift"
   - avoid "In today's digital landscape" style starters
2. Avoid repetitive sentence starts and repetitive paragraph structure.
3. Do not use excessive subhead lists or hacky stuffing of keywords into every sentence.
4. Avoid needless throat-clearing phrases and hedging language. Do not use phrases like "It is important to note that...", "It can be said that...", "In conclusion...", or "Needless to say...". Get straight to the point.
5. Avoid overly formal transition words. Instead of "Furthermore", "Moreover", "In addition", prefer simpler transitions like "Also,", "Another point is,", or just starting a new paragraph to signal a new idea.
6. Avoid starting consecutive paragraphs with the same structure (e.g., starting three paragraphs in a row with "The primary benefit of X is...").

F. Formatting rules - HTML specifics
Incorporate these text formatting elements in the blog content on the basis of their applicability such that, the readers can skim through the blog easily while retaining information about key concepts easily make sure it will be in html format align with our final response formatting :
i. Lists
Bulleted lists (•): Use them when
Presenting non-sequential items like features, benefits, tips, key takeaways etc.
Breaking dense paragraphs into scannable points in any section of the outline.
Summarising information into broken-down lists
Numbered lists (1, 2, 3): Use them when
The order matters, such as steps, processes, workflows, timelines, or rankings.
Checklists (✓): Use them when
Readers need to verify the readiness or completion of actions suggested in the information.
Nested lists: Use them when
You need to establish hierarchy between the main points with sub-points, categories with examples, steps with sub-steps, etc.
ii. Tables
Simple 2-column tables (term vs definition): Use them when
Each row pairs a short label on the left with a concise explanation or value on the right. For example, term vs definition, feature vs description, metric vs value, problem vs fix.
Multi-column tables (side-by-side comparisons): Use them when
Comparing 2 to 5 items side by side on consistent criteria.
Highlighted rows and columns for emphasis: Use them when
You need to draw attention to a recommended option, best value, or critical data.
iii. Block Formatting
Blockquotes (" "): Use them when
Citing an external expert, research line, policy excerpt, testimonial, or a crisp definition from an authority.
Emphasising a single striking insight or statistic that supports the surrounding text.
Code blocks (for technical content): Use them when
Showing commands, configuration, code snippets, API requests or responses, log excerpts, or error outputs.
Presenting technical steps where readers need to copy and run something exactly.
iv. Text Emphasis
Bold for keywords/numbers: Use them when
The primary keyword needs to be highlighted to help readers spot it.
A number-driven statistic needs a special attention of the reader
Italics for subtle emphasis: Use them when
Adding a nuance or a gentle aside in the sentence. Example, disclaimers, caveats, etc.
Monospace for commands/filenames: Use them when
Showing commands, flags, code identifiers, filenames, paths, or config keys inline.
Occasional ALL CAPS / small caps for emphasis: Use them when
You need to create a punchy emphasis on something, especially for blogs with a conversational tonality.
v. Dividers & Breaks
Section dividers (•••): Use them when
Breaking up long sections into digestible chunks without adding new headings.
Signalling a shift in focus, for example, from context to steps, or from analysis to examples.
Pros vs Cons lists: Use them when
The sections discuss advantages and drawbacks, considerations, or decision criteria.
Any comparison where both strengths and limitations matter for a balanced view.
Timelines (Year → Event): Use them when
You need to show important chronological developments. For example, event milestones, history, roadmap rollout, etc.

G. Final checklist to satisfy before returning HTML
1. All outline headings and subheadings are present verbatim and in the same order.
2. Introduction present and placed before first heading.
3. Conclusion included only if outline has "Conclusion".
4. Primary and secondary keywords present naturally and not overused.
5. Primary word count target met within +/-2%.
6. Citations use the exact anchor format required.
7. No em dash or en dash characters exist.
8. Output contains only HTML and nothing else.

H. Humanization Directives - Apply these rules to break AI patterns:
2. Inject One Analogy or Micro-Story: Within the body of the article, include one relevant analogy, metaphor, or a short, two-sentence story to illustrate a key point. For example, "Trying to do SEO without data is like driving at night with the headlights off. You might move forward, but you're probably going to hit something."
3. The Rule of Three (for Rhythm): Deliberately vary sentence structure. For every two medium-to-long sentences, write one very short sentence. For example: "This allows teams to analyze their entire content repository in just a few hours. The resulting data can then be used to inform your strategy for the next six months. It's a game-changer."
4. Ask a Direct Question: At least twice in the article, ask the reader a direct, rhetorical question to make them pause and think. For example, "But what does this actually mean for your budget?" or "Sounds simple, right?"
5. The Contrarian Hook: Defy Common Wisdom
AI models are trained on the consensus of web text, so they produce safe, agreeable introductions. An expert human often starts by challenging the status quo.
Directive: Begin the article not with a generic summary, but by identifying a common piece of advice in this topic and immediately calling it into question. Create tension from the first sentence.
AI Pattern it Breaks: The predictable, summary-based introduction.
Example (AI-ish): "Search Engine Optimization (SEO) is a crucial component of modern digital marketing. It involves various techniques to improve a website's visibility on search engines like Google."
Example (Human): "You've probably been told that SEO is all about keywords and backlinks. For years, that was true. Today, that advice is not just outdated—it's actively costing you money."
6. The Specificity Anchor: Ground a Claim in Detail
AI generalizes. It will say "improved by a significant margin" or "many customers were happy." Humans anchor their stories in oddly specific, memorable details.
Directive: When making an important claim, anchor it with a specific, almost trivial-sounding detail—a number, a time of day, a piece of feedback. This simulates a real memory.
AI Pattern it Breaks: Vague, abstract claims and lack of sensory detail.
Example (AI-ish): "After implementing the new system, the team's productivity saw a significant increase, and project turnaround times were reduced."
Example (Human): "The week after we flipped the switch, our Monday morning project stand-up went from a 45-minute slog to a 12-minute check-in. That's when I knew it was working."
7. The "Flawed Narrator": Acknowledge the Struggle
AI writes from an objective, all-knowing perspective, presenting solutions as straightforward. Humans know that progress is messy and comes from failure. Admitting this builds immense trust.
Directive: Introduce at least one concept by talking about how difficult it is, a mistake you once made with it, or a common pitfall. Frame the advice from a perspective of "I've made the mistakes so you don't have to."
AI Pattern it Breaks: The "perfect," emotionless, omniscient narrator.
Example (AI-ish): "To properly configure the software, it is important to follow all the steps in the documentation carefully."
Example (Human): "Let's be honest, the official documentation for this is a nightmare. I probably wasted a solid week trying to follow it to the letter before I realized the key was to ignore step three entirely and do this instead..."
8. The Abrupt Shift: Create Impact with Structure
AI uses perfect, logical transition words ("Furthermore," "In addition," "Therefore"). This creates a smooth but predictable rhythm. A confident human writer can pivot abruptly for dramatic effect.
Directive: At least once, end a paragraph that is building a case, and start the next paragraph with a short, sharp sentence that pivots the topic entirely. Use conjunctions like "But" or "And yet," or just a standalone question.
AI Pattern it Breaks: Over-reliance on formal transitions and uniform paragraph flow.
Example (AI-ish): "In addition to the aforementioned benefits, the system also provides enhanced security protocols to protect user data."
Example (Human): "...and that's how the feature allows you to triple your output. It sounds perfect. So why did we almost scrap it? Security."
5. The Rhythmic Run-On: Use Rhetoric, Not Just Grammar
AI constructs grammatically perfect, balanced sentences. Humans use rhythm and rhetorical devices to create emphasis and emotion. Polysyndeton (the deliberate overuse of conjunctions like "and" or "or") is a powerful tool for this.
Directive: When listing a series of related ideas or actions, connect them with "and" instead of commas to create a sense of momentum, exhaustion, or overwhelming scale.
AI Pattern it Breaks: Grammatically correct but rhythmically sterile list-making.
Example (AI-ish): "To complete the project, we had to gather requirements, design mockups, write the code, and test the final product."
Example (Human): "We had to gather the requirements and fight for budget and design the mockups and then throw them out and start over and somehow still write the code on schedule."

I. Safety and policy
1. Do not produce content that violates policy. If a request is disallowed, return a brief, safe HTML alternative explaining constraints and offering permitted options. The HTML must still be the only output.

            """,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": blog_prompt
                        }
                    ]
                }
            ]
        }
        
        streaming_data = {
            "phase": "content",
            "live_content": "",
            "content_word_count": 0,
            "is_streaming": True,
            "streaming_mode": "90fps_word_by_word",  # 🚀 NEW: Indicate advanced streaming
            "started_at": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat()
        }
        
        try:
            task_data = redis_client.get(redis_key)
            if task_data:
                task_info = json.loads(task_data)
                task_info["steps"]["blog_generation"]["streaming_data"] = streaming_data
                redis_client.set(redis_key, json.dumps(task_info), ex=86400)
        except Exception as redis_error:
            logger.warning(f"Failed to initialize streaming data in Redis: {str(redis_error)}")
        
        # Save complete request payload to file for debugging
        try:
            import os
            os.makedirs("logs/api_payloads", exist_ok=True)
            logger.info(f"Starting to save detailed Claude request for blog_id: {blog_id}")

            with open(f"logs/api_payloads/claude_request_{blog_id}.txt", "w", encoding="utf-8") as f:
                f.write("=== CLAUDE API REQUEST (FREE TIER) ===\n")
                f.write(f"Blog ID: {blog_id}\n")
                f.write(f"Timestamp: {datetime.now()}\n")
                f.write(f"Model: claude-3-7-sonnet-20250219\n")
                f.write(f"Provider: Anthropic\n\n")

                # Write detailed input variables
                f.write("=== DETAILED INPUT VARIABLES ===\n")
                f.write(f"Title: {blog_title}\n")
                f.write(f"Primary Keyword: {primary_keyword}\n")
                f.write(f"Secondary Keywords: {secondary_keywords}\n")
                f.write(f"Keyword Intent: {keyword_intent}\n")
                f.write(f"Category: {category}\n")
                f.write(f"Subcategory: {subcategory}\n")
                f.write(f"Word Count: {word_count}\n")
                f.write(f"Target Gender: {target_gender}\n")
                f.write(f"Country: {country}\n")
                f.write(f"Language Preference: {language_preference}\n")
                f.write(f"Brand Tonality (Raw): {brand_tonality}\n")
                f.write(f"Raw Tonality JSON: {raw_tonality_json}\n\n")

                # Write formatted data
                f.write("=== FORMATTED DATA ===\n")
                f.write(f"Raw Outline JSON:\n{raw_outline}\n\n")
                f.write(f"Raw Sources JSON:\n{raw_sources}\n\n")

                # Write complete system prompt
                f.write("=" * 80 + "\n")
                f.write("=== COMPLETE SYSTEM PROMPT ===\n")
                f.write("=" * 80 + "\n")
                f.write(request_payload["system"])
                f.write("\n\n")

                # Write complete user prompt
                f.write("=" * 80 + "\n")
                f.write("=== COMPLETE USER PROMPT (BLOG GENERATION) ===\n")
                f.write("=" * 80 + "\n")
                f.write(blog_prompt)
                f.write("\n\n")

                f.write("=" * 80 + "\n")
                f.write(f"System Prompt Length: {len(request_payload['system'])} characters\n")
                f.write(f"User Prompt Length: {len(blog_prompt)} characters\n")
                f.write(f"Total Prompt Length: {len(request_payload['system']) + len(blog_prompt)} characters\n")
                f.write("=" * 80 + "\n")

            logger.info(f"✅ Successfully saved complete Claude request with prompts for blog_id: {blog_id}")
            logger.info(f"📄 Payload saved to: logs/api_payloads/claude_request_{blog_id}.txt")

        except Exception as e:
            logger.error(f"Failed to save Claude request details: {str(e)}", exc_info=True)

        # No thinking content needed for free version (like pro version)
        thinking_content = ""

        # Handle streaming response from Anthropic API with 90fps word-by-word streaming
        blog_content = ""
        anthropic_usage = {}

        # 🚀 INITIALIZE 90FPS STREAMING VARIABLES
        content_buffer = ""  # Buffer for word-boundary streaming
        last_stream_time = 0  # Timestamp for throttling
        words_streamed = 0  # Word counter for progress
        
        try:
            # Track Claude API call in Sentry
            with sentry_sdk.start_transaction(op="ai_streaming", name="claude_blog_streaming") as transaction:
                transaction.set_tag("provider", "anthropic")
                transaction.set_tag("model", "claude-3-7-sonnet-20250219")
                transaction.set_tag("step", "blog_generation_streaming")
                transaction.set_data("word_count_target", word_count)
                transaction.set_data("specialty", specialty_info.get("expertise", ""))
                
                logger.info(f"🚀 Starting 90fps word-by-word streaming blog generation for blog_id: {blog_id}")
                
                response = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                    stream=True,
                    timeout=600  # 10 minute timeout
                )
                
                if response.status_code != 200:
                    raise Exception(f"Anthropic API error: {response.status_code} - {response.text}")
                
                # Process streaming response
                for line in response.iter_lines():
                    if line:
                        line_text = line.decode('utf-8')
                        if line_text.startswith('data: '):
                            try:
                                event_data = json.loads(line_text[6:])  # Remove 'data: ' prefix
                                
                                # Handle different streaming events
                                event_type = event_data.get('type')
                                
                                # Log all events for debugging
                                logger.info(f"📡 Received event type: {event_type} for blog_id: {blog_id}")
                                if 'delta' in event_data:
                                    delta_type = event_data.get('delta', {}).get('type')
                                    if delta_type:
                                        logger.info(f"📡 Delta type: {delta_type}")
                                
                                # Log full event data for thinking-related events
                                if 'thinking' in str(event_data).lower() or event_type in ['content_block_start', 'message_start']:
                                    logger.info(f"📡 FULL EVENT DATA: {json.dumps(event_data)}")
                                
                                if event_type == 'message_start':
                                    # Extract usage information if available
                                    message_data = event_data.get('message', {})
                                    anthropic_usage = message_data.get('usage', {})
                                    logger.info(f"🔄 Message started for blog_id: {blog_id}")
                                    
                                elif event_type == 'content_block_start':
                                    # Content block started
                                    logger.info(f"📝 Content generation started for blog_id: {blog_id}")
                                    update_streaming_phase(blog_id, "content", redis_key)
                                    
                                elif event_type == 'content_block_delta':
                                    # Handle content delta for streaming
                                    delta_data = event_data.get('delta', {})
                                    delta_type = delta_data.get('type')
                                    
                                    if delta_type == 'text_delta':
                                        # 🚀 90FPS WORD-BY-WORD STREAMING for FREE tier
                                        content_delta = delta_data.get('text', '')
                                        if content_delta:
                                            blog_content += content_delta
                                            
                                            # 🚀 ADVANCED STREAMING: Process delta through 90fps system
                                            content_buffer, should_stream, streamed_chunk, last_stream_time = process_smooth_content_streaming(
                                                blog_id, content_delta, blog_content, content_buffer, redis_key, last_stream_time
                                            )
                                            
                                            # Stream if conditions are met (word boundaries + timing)
                                            if should_stream and streamed_chunk:
                                                words_streamed += len(streamed_chunk.split())
                                                
                                                # 🚀 SMART PROGRESS: +1% per word chunk, gradual to 95%
                                                try:
                                                    task_data = redis_client.get(redis_key)
                                                    if task_data:
                                                        task_info = json.loads(task_data)
                                                        current_progress = task_info["steps"]["blog_generation"]["progress"]
                                                        if current_progress < 95:  # Gradual count to 95%
                                                            new_progress = min(current_progress + 1, 95)
                                                            safe_update_progress(blog_id, new_progress, redis_key, "content")
                                                except:
                                                    pass
                                                
                                                # 🚀 90FPS STREAMING: Update with current full content
                                                handle_content_stream(blog_id, blog_content, thinking_content, redis_key)
                                                
                                                logger.debug(f"🚀 Streamed {len(streamed_chunk)} chars, {words_streamed} words total for blog_id: {blog_id}")
                                    
                                # Remove duplicate code - now handled above in content_block_delta
                                
                                elif event_type == 'content_block_stop':
                                    # Content block finished - flush any remaining buffered content
                                    logger.info(f"📝 Content block finished for blog_id: {blog_id}")
                                    
                                    # 🚀 FLUSH REMAINING BUFFER: Stream any final buffered content
                                    if content_buffer.strip():
                                        logger.info(f"🚀 Flushing final buffer: {len(content_buffer)} chars for blog_id: {blog_id}")
                                        handle_content_stream(blog_id, blog_content, thinking_content, redis_key)
                                        content_buffer = ""  # Clear buffer
                                    
                                    safe_update_progress(blog_id, 100, redis_key, "content_finished")
                                    handle_content_stream(blog_id, blog_content, thinking_content, redis_key)
                                    
                                elif event_type == 'message_delta':
                                    # Handle delta updates (usage info) 
                                    delta_data = event_data.get('delta', {})
                                    
                                    # CRITICAL: Final usage with OUTPUT TOKENS comes here!
                                    if 'usage' in event_data:
                                        final_usage = event_data['usage']
                                        logger.info(f"📊 FINAL USAGE FROM message_delta: {final_usage}")
                                        anthropic_usage.update(final_usage)
                                    elif 'usage' in delta_data:
                                        usage_update = delta_data['usage'] 
                                        logger.info(f"📊 Delta usage update: {usage_update}")
                                        anthropic_usage.update(usage_update)
                                    
                                elif event_type == 'message_stop':
                                    # Final completion with 90fps streaming stats
                                    final_word_count = len(blog_content.split())
                                    logger.info(f"🚀 90fps streaming completed for blog_id: {blog_id} - {final_word_count} words, {words_streamed} words streamed")
                                    logger.info(f"📊 Final anthropic_usage at completion: {anthropic_usage}")
                                    # Final update with complete content
                                    handle_content_stream(blog_id, blog_content, thinking_content, redis_key)
                                    
                            except json.JSONDecodeError as e:
                                logger.warning(f"Failed to parse streaming event: {e}")
                                continue
                            except Exception as e:
                                logger.error(f"Error processing streaming event: {e}")
                                continue
                
                # Final usage tracking from last known usage data
                if anthropic_usage:
                    usage_tracker["total_input_tokens"] += anthropic_usage.get("input_tokens", 0)
                    usage_tracker["total_output_tokens"] += anthropic_usage.get("output_tokens", 0)
                    usage_tracker["total_calls"] += 1
                    usage_tracker["individual_calls"].append({
                        "call_number": usage_tracker["total_calls"],
                        "step": "blog_generation_streaming",
                        "model": "claude-3-7-sonnet-20250219",
                        "input_tokens": anthropic_usage.get("input_tokens", 0),
                        "output_tokens": anthropic_usage.get("output_tokens", 0),
                        "provider": "anthropic"
                    })
                    
                    logger.info(f"📊 Anthropic streaming call #{usage_tracker['total_calls']}: "
                               f"{anthropic_usage.get('input_tokens', 0)} input + {anthropic_usage.get('output_tokens', 0)} output tokens "
                               f"(Running total: {usage_tracker['total_input_tokens']} input, "
                               f"{usage_tracker['total_output_tokens']} output)")
        
        except Exception as streaming_error:
            logger.error(f"Streaming error: {str(streaming_error)}")
            # Fallback to non-streaming mode
            logger.info(f"🔄 Falling back to non-streaming mode for blog_id: {blog_id}")
            
            # Update Redis to indicate fallback mode
            try:
                task_data = redis_client.get(redis_key)
                if task_data:
                    task_info = json.loads(task_data)
                    if "streaming_data" in task_info["steps"]["blog_generation"]:
                        task_info["steps"]["blog_generation"]["streaming_data"]["phase"] = "fallback_mode"
                        task_info["steps"]["blog_generation"]["streaming_data"]["is_streaming"] = False
                        task_info["steps"]["blog_generation"]["streaming_data"]["fallback_reason"] = str(streaming_error)
                        redis_client.set(redis_key, json.dumps(task_info), ex=86400)
            except Exception as fallback_redis_error:
                logger.warning(f"Failed to update Redis for fallback mode: {str(fallback_redis_error)}")
            
            # Remove stream parameter and retry
            fallback_payload = payload.copy()
            fallback_payload.pop('stream', None)
            
            try:
                response = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=fallback_payload,
                    timeout=600
                )
                
                if response.status_code != 200:
                    raise Exception(f"Anthropic API error (fallback): {response.status_code} - {response.text}")
                
                response_data = response.json()
                anthropic_usage = response_data.get("usage", {})
                
                # Extract content from non-streaming response
                for content_item in response_data["content"]:
                    if content_item.get("type") == "text":
                        blog_content = content_item["text"]
                        break
                        
                # Update Redis with fallback completion
                try:
                    task_data = redis_client.get(redis_key)
                    if task_data:
                        task_info = json.loads(task_data)
                        if "streaming_data" in task_info["steps"]["blog_generation"]:
                            task_info["steps"]["blog_generation"]["streaming_data"]["phase"] = "completed_fallback"
                            task_info["steps"]["blog_generation"]["streaming_data"]["final_content"] = blog_content[:500] + "..." if len(blog_content) > 500 else blog_content
                            task_info["steps"]["blog_generation"]["streaming_data"]["content_word_count"] = len(blog_content.split())
                            redis_client.set(redis_key, json.dumps(task_info), ex=86400)
                except Exception as fallback_complete_redis_error:
                    logger.warning(f"Failed to update Redis for fallback completion: {str(fallback_complete_redis_error)}")
                    
                logger.info(f"✅ Fallback mode completed successfully for blog_id: {blog_id}")
                
            except Exception as fallback_error:
                logger.error(f"Fallback mode also failed: {str(fallback_error)}")
                # Update Redis with total failure
                try:
                    task_data = redis_client.get(redis_key)
                    if task_data:
                        task_info = json.loads(task_data)
                        if "streaming_data" in task_info["steps"]["blog_generation"]:
                            task_info["steps"]["blog_generation"]["streaming_data"]["phase"] = "failed"
                            task_info["steps"]["blog_generation"]["streaming_data"]["is_streaming"] = False
                            task_info["steps"]["blog_generation"]["streaming_data"]["error"] = f"Streaming failed: {streaming_error}. Fallback failed: {fallback_error}"
                            redis_client.set(redis_key, json.dumps(task_info), ex=86400)
                except:
                    pass
                raise Exception(f"Both streaming and fallback modes failed. Streaming: {streaming_error}, Fallback: {fallback_error}")
        
        # Save Anthropic response payload to file
        try:
            with open(f"logs/api_payloads/anthropic_response_{blog_id}.txt", "w", encoding="utf-8") as f:
                f.write("=== ANTHROPIC STREAMING RESPONSE ===\n")
                f.write(f"Blog ID: {blog_id}\n")
                f.write(f"Timestamp: {datetime.now()}\n")
                f.write(f"Final Content Length: {len(blog_content)} chars\n")
                f.write(f"Final Thinking Length: {len(thinking_content)} chars\n")
                f.write(f"Content: {blog_content[:1000]}...\n")  # Save first 1000 chars
        except Exception as e:
            logger.warning(f"Failed to save Anthropic response payload: {str(e)}")
        
        if not blog_content:
            raise Exception("No content generated from Anthropic streaming API")
        
        # Calculate word count (using final blog content)
        word_count = len(blog_content.split())
        
        # Mark streaming as completed in Redis
        finalize_streaming_data(blog_id, blog_content, thinking_content, word_count, redis_key)
        
        # Safely update to final completion
        safe_update_progress(blog_id, 100, redis_key, "generation_completed")
        
        # Update MongoDB with final content
        try:
            mongodb_service = MongoDBService()
            mongodb_service.init_sync_db()

            # 📦 CREATE CONTENT VERSION OBJECT (like blog.py endpoint)
            # Convert datetime to ISO string for JSON serialization
            now = datetime.now(pytz.timezone('Asia/Kolkata'))
            content_version = {
                "html": blog_content,
                "saved_at": now.isoformat(),  # Store as ISO string for JSON compatibility
                "tag": "generated",
                "version": 1,
                "words_count": word_count
            }

            update_data = {
                "content": [content_version],  # Array with version object
                "status": "draft",
                "updated_at": now.isoformat(),  # Store as ISO string for JSON compatibility
                "specialty_info": specialty_info,
                "brand_tonality_applied": brand_tonality,
                "generation_method": "free"  # FREE tier
            }

            # 📊 LOG WHAT'S BEING SAVED TO MONGODB
            logger.info("=" * 80)
            logger.info("💾 SAVING FINAL BLOG DATA TO MONGODB (FREE TIER)")
            logger.info("=" * 80)
            logger.info(f"Blog ID: {blog_id}")
            logger.info(f"Content Structure: Array with version object")
            logger.info(f"Content Length: {len(blog_content)} characters")
            logger.info(f"Word Count (in version object): {word_count} words")
            logger.info(f"Status: draft")
            logger.info(f"Specialty Info: {specialty_info}")
            logger.info(f"Brand Tonality Applied: {brand_tonality}")
            logger.info(f"Generation Method: free")
            logger.info(f"Content Version Tag: generated")
            logger.info(f"Content Version Number: 1")
            logger.info("=" * 80)

            mongodb_service.get_sync_db()['blogs'].update_one(
                {'_id': ObjectId(blog_id)},
                {'$set': update_data}
            )
            logger.info(f"✅ Blog content successfully saved to MongoDB for blog_id: {blog_id}")
            
        except Exception as mongo_error:
            logger.error(f"Failed to save to MongoDB: {str(mongo_error)}")
            raise
        
        # Final status update only
        try:
            task_data = redis_client.get(redis_key)
            if task_data:
                task_info = json.loads(task_data)
                task_info["steps"]["blog_generation"]["status"] = "completed"
                task_info["status"] = "completed"
                task_info["final_content"] = blog_content[:500] + "..." if len(blog_content) > 500 else blog_content
                task_info["word_count"] = word_count
                redis_client.set(redis_key, json.dumps(task_info), ex=86400)
        except Exception as redis_error:
            logger.warning(f"Failed to update Redis completion status: {str(redis_error)}")
        
        # Record combined usage following the EXACT same pattern as advanced outline
        if usage_tracker.get("total_calls", 0) > 0 and usage_tracker.get("user_id"):
            try:
                # Import locally to avoid SQLAlchemy relationship mapping issues (matches keywords.py pattern)
                # Force import ALL Account dependencies BEFORE Account to resolve relationship mapping in Celery workers
                from app.models.razorpay import RazorpayPayment  # noqa: F401 - Required for proper SQLAlchemy model initialization order
                from app.models.invoice import Invoice  # noqa: F401 - Required for proper SQLAlchemy model initialization order
                from app.models.transaction import Transaction  # noqa: F401 - Required for proper SQLAlchemy model initialization order
                from app.models.account import Account  # noqa: F401 - Required for proper SQLAlchemy model initialization order
                from app.services.enhanced_llm_usage_service import EnhancedLLMUsageService
                
                # Use the SAME initialization pattern as AdvancedOutlineGenerationService (Line 90)
                if hasattr(self, 'db') and self.db:
                    llm_usage_service = EnhancedLLMUsageService(self.db)
                else:
                    with get_db_session() as db:
                        llm_usage_service = EnhancedLLMUsageService(db)
                
                # Use the EXACT same metadata structure as advanced outline (Lines 877-889)
                blog_metadata = {
                    "blog_generation_stats": {
                        "total_api_calls": usage_tracker["total_calls"],
                        "request_id": usage_tracker["request_id"],
                        "blog_id": blog_id,
                        "word_count": word_count,
                        "specialty_detected": specialty_info.get("expertise", ""),
                        "generation_method": "free"
                    },
                    "individual_api_calls": usage_tracker["individual_calls"]
                }
                
                # Calculate cost manually for debugging
                from app.config.llm_pricing import LLM_MODEL_PRICING
                from app.config.service_multipliers import get_service_multiplier
                
                # Calculate total base cost from individual calls
                total_base_cost = 0.0
                for call in usage_tracker["individual_calls"]:
                    model_name = call["model"]
                    input_tokens = call["input_tokens"]
                    output_tokens = call["output_tokens"]
                    
                    if model_name in LLM_MODEL_PRICING:
                        pricing = LLM_MODEL_PRICING[model_name]
                        input_cost = (input_tokens / 1000) * pricing["input_per_1k"]
                        output_cost = (output_tokens / 1000) * pricing["output_per_1k"]
                        call_cost = input_cost + output_cost
                        total_base_cost += call_cost
                        
                        logger.info(f"📊 Cost calculation: {model_name} = {input_tokens}+{output_tokens} tokens = ${call_cost:.6f}")
                
                # Apply service multiplier
                service_multiplier = get_service_multiplier("blog_generation")["multiplier"]
                final_charge = total_base_cost * service_multiplier
                
                logger.info(f"📊 Total base cost: ${total_base_cost:.6f}, Multiplier: {service_multiplier}x, Final: ${final_charge:.6f}")
                
                # Use accurate cost calculation via underlying UsageService
                billing_result = llm_usage_service.usage_service.record_usage_and_charge(
                    user_id=usage_tracker["user_id"],
                    service_name="blog_generation",
                    base_cost=total_base_cost,  # Use the accurate calculated cost
                    multiplier=service_multiplier,
                    service_description=f"Blog generation V2 - {usage_tracker['total_calls']} API calls combined",
                    usage_data=blog_metadata,
                    project_id=project_id
                )
                
                # Log the full billing result for debugging
                logger.info(f"📋 BILLING RESULT: {billing_result}")
                
                # Check if usage was actually recorded
                if billing_result.get("success"):
                    logger.info(f"✅ BLOG GENERATION BILLING RECORDED: {usage_tracker['total_calls']} calls, "
                               f"${billing_result.get('cost', 0):.6f} charged with 20.0x multiplier")
                    
                    # Check if usage record was created in database
                    try:
                        from app.models.usage import Usage
                        with get_db_session() as db:
                            latest_usage = db.query(Usage).filter(
                                Usage.user_id == usage_tracker["user_id"],
                                Usage.service_name == "blog_generation"
                            ).order_by(Usage.created_at.desc()).first()
                            
                            if latest_usage:
                                logger.info(f"✅ USAGE TABLE UPDATED: ID={latest_usage.id}, Cost=${latest_usage.actual_charge:.6f}")
                            else:
                                logger.error("❌ NO USAGE RECORD FOUND in usage table")
                    except Exception as db_check_error:
                        logger.error(f"❌ Error checking usage table: {db_check_error}")
                else:
                    logger.error(f"❌ BILLING FAILED: {billing_result.get('message', 'Unknown error')}")
                    logger.error(f"❌ Full billing response: {billing_result}")
                
            except Exception as e:
                logger.error(f"❌ Failed to record blog generation usage: {e}")
        else:
            logger.warning("No API calls were made during blog generation or missing user_id")
        
        logger.info(f"Blog generation V2 completed for blog_id: {blog_id}, word_count: {word_count}")
        
        return {
            "blog_id": blog_id,
            "content": blog_content,
            "word_count": word_count,
            "specialty_info": specialty_info,
            "brand_tonality_applied": brand_tonality,
            "status": "completed",
            "generation_method": "free",
            "usage_summary": {
                "total_calls": usage_tracker.get("total_calls", 0),
                "total_tokens": usage_tracker.get("total_input_tokens", 0) + usage_tracker.get("total_output_tokens", 0)
            }
        }
        
    except Exception as e:
        # Capture exception in Sentry with context
        # Try to include word_count if it was extracted, otherwise skip
        extra_context = {
            "blog_id": blog_id,
            "project_id": project_id,
            "task_name": "generate_final_blog_step",
            "specialty": specialty_info.get("expertise", "")
        }
        try:
            # Try to add word_count if it was successfully extracted
            extra_context["word_count_target"] = word_count
        except NameError:
            # word_count not extracted yet (error happened early)
            pass

        sentry_sdk.capture_exception(e, extra=extra_context)
        logger.error(f"Error in generate_final_blog_step: {str(e)}", exc_info=True)
        
        # Update MongoDB with error
        try:
            mongodb_service = MongoDBService()
            mongodb_service.init_sync_db()
            mongodb_service.get_sync_db()['blogs'].update_one(
                {'_id': ObjectId(blog_id)},
                {'$set': {
                    'status': 'failed',
                    'error_message': str(e),
                    'updated_at': datetime.now(timezone.utc)
                }}
            )
        except Exception as mongo_error:
            logger.error(f"Failed to update MongoDB error status: {str(mongo_error)}")
        
        # Update Redis with error
        try:
            task_data = redis_client.get(redis_key)
            if task_data:
                task_info = json.loads(task_data)
                task_info["steps"]["blog_generation"]["status"] = "failed"
                task_info["steps"]["blog_generation"]["error"] = str(e)
                task_info["status"] = "failed"
                redis_client.set(redis_key, json.dumps(task_info), ex=86400)
        except Exception as redis_error:
            logger.warning(f"Failed to update Redis error status: {str(redis_error)}")
        
        raise


@celery.task(name="app.tasks.blog_generation_free.get_blog_status_free", queue="blog_generation")
def get_blog_status_free(blog_id: str) -> Dict[str, Any]:
    """
    Get comprehensive status for V2 blog generation
    
    Args:
        blog_id: Blog document ID
        
    Returns:
        Dictionary containing status information in frontend-expected format
    """
    try:
        redis_key = f"blog_generation_task:{blog_id}"
        task_data = redis_client.get(redis_key)
        
        if not task_data:
            return {
                "status": "not_found",
                "progress": 0,
                "content": "",
                "message": "No task data found for this blog",
                "blog_id": blog_id
            }
        
        task_info = json.loads(task_data)
        
        # Get overall progress from single blog generation step
        overall_progress = int(task_info.get("steps", {}).get("blog_generation", {}).get("progress", 0))
        # CLEAN: Cap progress at 100% to prevent overflow
        overall_progress = min(overall_progress, 100)
        
        # Map internal status to frontend-expected status
        internal_status = task_info.get("status", "unknown")
        if internal_status in ["running", "processing"]:
            frontend_status = "in_progress"
            message = "Blog generation in progress"
        elif internal_status == "completed":
            frontend_status = "completed"
            message = "Blog generation completed successfully"
        elif internal_status == "failed":
            frontend_status = "failed"
            message = "Blog generation failed"
        else:
            frontend_status = "in_progress"
            message = "Blog generation in progress"
        
        return {
            "status": frontend_status,
            "progress": overall_progress,
            "content": task_info.get("final_content", ""),
            "message": message,
            "blog_id": blog_id
        }
        
    except Exception as e:
        logger.error(f"Error getting blog status V2: {str(e)}")
        return {
            "status": "failed",
            "progress": 0,
            "content": "",
            "message": f"Error retrieving status: {str(e)}",
            "blog_id": blog_id
        }