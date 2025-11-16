"""
Blog Generation V2 - Simplified 2-Step Process
New implementation with brand tonality mapping and streamlined workflow
Content processing using OpenAI GPT-4.1 for intelligent formatting
"""

import json
import logging
import redis
import requests
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any
from bson import ObjectId
from app.celery_config import celery_app as celery
from app.services.mongodb_service import MongoDBService
from app.services.unified_streaming_service import unified_streaming_service
from app.services.unified_streaming_processor import process_unified_streaming
import json
import pytz
from app.core.config import settings
from app.db.session import get_db_session
import uuid
import os
import time

# Sentry integration for Celery tasks
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration

# Import Claude prompt functions - both casual and formal variants
from app.prompts.claude.blog_generation_prompt import (
    get_blog_generation_system_prompt,
    get_blog_generation_user_prompt
)
from app.prompts.claude.blog_generation_prompt_formal import (
    get_blog_generation_system_prompt_formal,
    get_blog_generation_user_prompt_formal
)

# Initialize Sentry for Celery tasks if DSN is available
if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[CeleryIntegration()],
        send_default_pii=True,
        traces_sample_rate=0.1,  # Track 10% of performance
        profiles_sample_rate=0.1  # Profile 10% of sampled transactions
    )


import redis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis client for task metadata
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)


@celery.task(name="app.tasks.blog_generation_pro.generate_blog_pro", queue="blog_generation", bind=True)
def generate_blog_pro(self, blog_id: str, project_id: str, project: Dict[str, Any]) -> Dict[str, Any]:
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
            scope.set_tag("task_name", "generate_blog_pro")
            scope.set_tag("blog_id", blog_id)
            scope.set_tag("project_id", project_id)

        logger.info(f"Starting blog generation PRO for blog_id: {blog_id}")
        
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

        # Launch blog generation task directly (retrieves data from MongoDB)
        task_result = generate_final_blog_step.delay(
            blog_id=blog_id,
            project_id=project_id,
            project=project,
            usage_tracker=usage_tracker
        )
        
        # Update task info with direct task ID
        task_info["generation_task_id"] = task_result.id
        redis_client.set(redis_key, json.dumps(task_info), ex=86400)
        
        logger.info(f"Blog generation V2 started for blog_id: {blog_id}, task_id: {task_result.id}")
        
        return {
            "main_task_id": self.request.id,
            "task_id": task_result.id,
            "blog_id": blog_id,
            "status": "processing",
            "message": "Blog generation V2 started successfully"
        }
        
    except Exception as e:
        # Capture exception in Sentry with context
        sentry_sdk.capture_exception(e, extra={
            "blog_id": blog_id,
            "project_id": project_id,
            "task_name": "generate_blog_pro"
        })
        logger.error(f"Error in generate_blog_pro: {str(e)}", exc_info=True)
        
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
            redis_key = f"blog_generation_task:{blog_id}"
            task_info = {"status": "failed", "error": str(e)}
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

def handle_content_stream(blog_id: str, content: str, redis_key: str):
    """
    Handle content phase streaming updates - SAFE VERSION (no progress change)
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
            current_progress = task_info.get("steps", {}).get("blog_generation", {}).get("progress", 0)
            safe_update_progress(blog_id, current_progress, redis_key, "content", extra_data)
        
        logger.debug(f"📝 Content update: {content_word_count} words for blog_id: {blog_id}")
        
    except Exception as e:
        logger.warning(f"Failed to update content stream: {str(e)}")



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

def finalize_streaming_data(blog_id: str, final_content: str, word_count: int, redis_key: str):
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

@celery.task(name="app.tasks.blog_generation_pro.generate_final_blog_step", queue="blog_generation", bind=True)
def generate_final_blog_step(self, blog_id: str, project_id: str, project: Dict[str, Any], usage_tracker: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate final blog content using UNIFIED STREAMING (GPT-5 for formal, Claude for casual)
    Retrieves all data from MongoDB blog document

    Args:
        blog_id: MongoDB blog document ID
        project_id: Project identifier
        project: Project information
        usage_tracker: Token usage tracking dictionary

    Returns:
        Dictionary containing final blog content and metadata
    """
    try:
        # Initialize error tracking variables
        streaming_error = None

        # 🚀 PRE-INITIALIZE MongoDB connection to avoid delay later
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
                "total_reasoning_tokens": 0,  # New: GPT-5 reasoning tokens
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
        logger.info("🔍 STARTING DATA EXTRACTION FROM MONGODB")
        logger.info("=" * 80)

        # 1. Primary Keyword (latest from array)
        logger.info("📍 [1/11] Extracting PRIMARY KEYWORD...")
        primary_keyword_array = blog_doc.get("primary_keyword", [])
        logger.info(f"   → Found {len(primary_keyword_array)} items in primary_keyword array")
        logger.info(f"   → Raw array: {primary_keyword_array}")

        if not primary_keyword_array:
            raise Exception("No primary keyword found in blog document")

        primary_keyword_data = primary_keyword_array[-1]  # Latest
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

        # 3. Category and Subcategory (root level - simple values)
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
        logger.info("✅ DATA EXTRACTION COMPLETE - SUMMARY")
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
        logger.info("🚀 PROCEEDING TO BLOG GENERATION...")
        logger.info("=" * 80)
        logger.info("")

        # Set Sentry context for blog generation step
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("task_name", "generate_final_blog_step")
            scope.set_tag("step", "blog_generation")
            scope.set_tag("blog_id", blog_id)
            scope.set_tag("project_id", project_id)
            scope.set_context("generation_request", {
                "word_count": word_count,
                "category": category,
                "language_preference": project.get('languages', [])
            })

        logger.info(f"Starting final blog generation for blog_id: {blog_id}")
        
        # Update Redis status - Step 2 processing started (45% total: 25% + 20%)
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

        # Extract individual brand tonality parameters for cleaner prompt injection
        formality = brand_tonality.get("formality", "Neutral")
        attitude = brand_tonality.get("attitude", "Balanced")
        energy = brand_tonality.get("energy", "Moderate")
        clarity = brand_tonality.get("clarity", "Clear")

        logger.info(f"Brand tonality parameters - Formality: {formality}, Attitude: {attitude}, Energy: {energy}, Clarity: {clarity}")

        # SIMPLE LOGIC: Decide which prompt to use based on formality
        # If formality is Ceremonial or Formal → Use FORMAL prompt (GPT-5)
        # If formality is Neutral, Conversational or Colloquial → Use CASUAL prompt (Claude)
        use_formal_prompt = formality in ["Ceremonial", "Formal"]
        logger.info(f"🎯 Prompt Selection: {'FORMAL' if use_formal_prompt else 'CASUAL'} (Formality: {formality})")

        # Keep raw JSON for logging purposes
        raw_tonality_json = json.dumps(brand_tonality, indent=2) if brand_tonality else "No specific tonality specified"

        # Extract person tone from project
        person_tone = project.get("person_tone", "second person")  # Default to "second person" to maintain current behavior
        logger.info(f"Person tone extracted from project: '{person_tone}'")

        # Extract language preference from project
        language_preference = "English (USA)"  # Default fallback
        project_languages = project.get('languages', [])
        if project_languages and len(project_languages) > 0:
            # Project stores: ["English (USA)"] or ["English (UK)"]
            language_preference = project_languages[0]  # Take first language
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

        # Build blog generation prompt - choose formal or casual based on formality parameter
        if use_formal_prompt:
            # Use FORMAL prompt for: Ceremonial, Formal, Neutral
            blog_prompt = get_blog_generation_user_prompt_formal(
                blog_title=blog_title,
                primary_keyword=primary_keyword,
                secondary_keywords=secondary_keywords,
                keyword_intent=keyword_intent,
                category=category,
                subcategory=subcategory,
                word_count=word_count,
                country=country,
                language_preference=language_preference,
                target_gender=target_gender,
                person_tone=person_tone,
                formality=formality,
                attitude=attitude,
                energy=energy,
                clarity=clarity,
                raw_outline=raw_outline,
                raw_sources=raw_sources
            )
        else:
            # Use CASUAL prompt for: Conversational, Colloquial
            blog_prompt = get_blog_generation_user_prompt(
                blog_title=blog_title,
                primary_keyword=primary_keyword,
                secondary_keywords=secondary_keywords,
                keyword_intent=keyword_intent,
                category=category,
                subcategory=subcategory,
                word_count=word_count,
                country=country,
                language_preference=language_preference,
                target_gender=target_gender,
                person_tone=person_tone,
                formality=formality,
                attitude=attitude,
                energy=energy,
                clarity=clarity,
                raw_outline=raw_outline,
                raw_sources=raw_sources
            )

        # 🎯 UNIFIED STREAMING: Generate content using GPT-5 for formal or Claude for casual
        
        # Choose system prompt based on formality
        if use_formal_prompt:
            system_prompt = get_blog_generation_system_prompt_formal()
        else:
            system_prompt = get_blog_generation_system_prompt()

        # Model selection happens inside unified_streaming_service based on formality
        logger.info(f"🎯 Model Selection: {formality} formality level will auto-select GPT-5 (formal) or Claude (casual)")
        
        # Save request details to file
        try:
            import os
            os.makedirs("logs/api_payloads", exist_ok=True)
            logger.info(f"Starting to save detailed request for blog_id: {blog_id}")
            
            with open(f"logs/api_payloads/unified_request_{blog_id}.txt", "w", encoding="utf-8") as f:
                f.write("=== UNIFIED STREAMING REQUEST ===\n")
                f.write(f"Blog ID: {blog_id}\n")
                f.write(f"Timestamp: {datetime.now()}\n")
                f.write(f"Selected Model: Auto-selected based on formality ({formality})\n")
                
                # Write detailed input variables section
                f.write("\n=== DETAILED INPUT VARIABLES ===\n")
                f.write(f"Title: {blog_title}\n")
                f.write(f"Primary Keyword: {primary_keyword}\n")
                f.write(f"Secondary Keywords: {secondary_keywords}\n")
                f.write(f"Keyword Intent: {keyword_intent}\n")
                f.write(f"Category: {category}\n")
                f.write(f"Subcategory: {subcategory}\n")
                f.write(f"Word Count: {word_count}\n")
                f.write(f"Target Gender: {target_gender}\n")
                f.write(f"Target Country: {country}\n")
                f.write(f"Language Preference: {language_preference}\n")
                f.write(f"Person Tone: {person_tone}\n")
                f.write(f"Formality: {formality}\n")
                f.write(f"Attitude: {attitude}\n")
                f.write(f"Energy: {energy}\n")
                f.write(f"Clarity: {clarity}\n")
                f.write(f"Brand Tonality (Raw): {brand_tonality}\n")
                f.write(f"Raw Tonality JSON: {raw_tonality_json}\n")
                f.write(f"Project Data: {project}\n")
                
                # Write formatted data section
                f.write("\n=== FORMATTED DATA ===\n")
                f.write(f"Raw Outline JSON:\n{raw_outline}\n\n")
                f.write(f"Raw Sources JSON:\n{raw_sources}\n\n")

                # Write complete prompts
                f.write("\n" + "=" * 80 + "\n")
                f.write("=== COMPLETE SYSTEM PROMPT ===\n")
                f.write("=" * 80 + "\n")
                f.write(system_prompt)
                f.write("\n\n")

                f.write("=" * 80 + "\n")
                f.write("=== COMPLETE USER PROMPT (BLOG GENERATION) ===\n")
                f.write("=" * 80 + "\n")
                f.write(blog_prompt)
                f.write("\n\n")

                f.write("=" * 80 + "\n")
                f.write(f"System Prompt Length: {len(system_prompt)} characters\n")
                f.write(f"User Prompt Length: {len(blog_prompt)} characters\n")
                f.write(f"Total Prompt Length: {len(system_prompt) + len(blog_prompt)} characters\n")
                f.write("=" * 80 + "\n")

            logger.info(f"✅ Successfully saved complete request with prompts for blog_id: {blog_id}")
            logger.info(f"📄 Payload saved to: logs/api_payloads/unified_request_{blog_id}.txt")
            
        except Exception as e:
            logger.error(f"Failed to save request details: {str(e)}", exc_info=True)
        
        # Initialize streaming data in Redis (enhanced for thinking + content)
        streaming_data = {
            "phase": "starting",
            "live_content": "",
            "live_thinking": "",  # New: GPT-5 thinking content
            "content_word_count": 0,
            "thinking_word_count": 0,  # New: GPT-5 thinking word count
            "is_streaming": True,
            "started_at": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat(),
            "content_active": True,
            "thinking_active": True  # New: Track if thinking phase is active
        }
        
        try:
            task_data = redis_client.get(redis_key)
            if task_data:
                task_info = json.loads(task_data)
                task_info["steps"]["blog_generation"]["streaming_data"] = streaming_data
                redis_client.set(redis_key, json.dumps(task_info), ex=86400)
        except Exception as redis_error:
            logger.warning(f"Failed to initialize streaming data in Redis: {str(redis_error)}")
        
        # 🚀 UNIFIED STREAMING: Handle both GPT-5 thinking + Claude content streaming
        blog_content = ""
        thinking_content = ""  # New: GPT-5 thinking content
        unified_usage = {}  # Unified usage data
        streaming_success = False
        
        try:
            # Track unified streaming call in Sentry
            model, provider = unified_streaming_service.select_model_and_provider(formality)
            
            with sentry_sdk.start_transaction(op="unified_streaming", name="unified_blog_streaming") as transaction:
                transaction.set_tag("provider", provider)
                transaction.set_tag("model", model)
                transaction.set_tag("step", "blog_generation")
                transaction.set_tag("formality", formality)
                transaction.set_data("word_count_target", word_count)
                
                logger.info(f"🚀 Starting unified streaming for blog_id: {blog_id} with {provider}/{model}")
                
                # 🎯 UNIFIED STREAMING CALL - Handles both GPT-5 thinking and Claude content
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    blog_content, thinking_content, unified_usage = loop.run_until_complete(
                        process_unified_streaming(
                            blog_id=blog_id,
                            formality=formality,
                            system_prompt=system_prompt,
                            user_prompt=blog_prompt,
                            redis_key=redis_key
                        )
                    )
                    
                    # Streaming completed successfully
                    streaming_success = True
                    logger.info(f"✅ Unified streaming completed successfully for blog_id: {blog_id}")
                    logger.info(f"📊 Content: {len(blog_content)} chars, Thinking: {len(thinking_content)} chars")
                    
                finally:
                    loop.close()
                
                # Old streaming code removed - now handled by unified_streaming_processor
                
        except Exception as streaming_err:
            streaming_error = streaming_err  # Store for later reference
            logger.error(f"Streaming error: {str(streaming_error)}")
            
        # If streaming failed, raise error immediately - no fallback
        if not streaming_success and streaming_error:
            logger.error(f"❌ Streaming failed for blog_id: {blog_id} - {str(streaming_error)}")
            raise Exception(f"Streaming failed: {str(streaming_error)}")
        else:
            # Streaming completed successfully
            logger.info(f"🧹 Streaming completed successfully, continuing with post-processing for blog_id: {blog_id}")
                
        # 📊 POST-STREAMING UNIFIED USAGE TRACKING (supports both GPT-5 and Claude)
        try:
            logger.info(f"📊 Processing usage data: {unified_usage}")
            if unified_usage and (streaming_success or not streaming_error):
                # Get model and provider info
                model, provider = unified_streaming_service.select_model_and_provider(formality)
                
                # Update usage tracker with unified data
                usage_tracker["total_input_tokens"] += unified_usage.get("input_tokens", 0)
                usage_tracker["total_output_tokens"] += unified_usage.get("output_tokens", 0)
                # Add total_reasoning_tokens field if it doesn't exist
                if "total_reasoning_tokens" not in usage_tracker:
                    usage_tracker["total_reasoning_tokens"] = 0
                usage_tracker["total_reasoning_tokens"] += unified_usage.get("reasoning_tokens", 0)  # GPT-5 only
                usage_tracker["total_calls"] += 1
                
                # Add individual call record
                call_record = {
                    "call_number": usage_tracker["total_calls"],
                    "step": "blog_generation",
                    "model": model,
                    "provider": provider,
                    "input_tokens": unified_usage.get("input_tokens", 0),
                    "output_tokens": unified_usage.get("output_tokens", 0)
                }
                
                # Add reasoning tokens if GPT-5
                if provider == "openai" and unified_usage.get("reasoning_tokens", 0) > 0:
                    call_record["reasoning_tokens"] = unified_usage.get("reasoning_tokens", 0)
                
                usage_tracker["individual_calls"].append(call_record)
                
                # Enhanced logging
                tokens_summary = f"{unified_usage.get('input_tokens', 0)} input + {unified_usage.get('output_tokens', 0)} output"
                if unified_usage.get("reasoning_tokens", 0) > 0:
                    tokens_summary += f" + {unified_usage.get('reasoning_tokens', 0)} reasoning"
                
                logger.info(f"📊 {provider.upper()} {model} call #{usage_tracker['total_calls']}: {tokens_summary} tokens")
                logger.info(f"📊 Running totals: {usage_tracker['total_input_tokens']} input, {usage_tracker['total_output_tokens']} output, {usage_tracker['total_reasoning_tokens']} reasoning")
            else:
                logger.warning(f"❌ Skipping usage tracking - unified_usage empty or streaming failed")
        except Exception as usage_error:
            logger.warning(f"Unified usage tracking failed (non-critical): {str(usage_error)}")
            
        # Calculate word count (using final blog content)
        word_count = len(blog_content.split())

        # Update MongoDB with final content (using pre-initialized connection)
        # MongoDB connection already established at task start - no delay here
        try:
            now = datetime.now(pytz.timezone('Asia/Kolkata'))

            # 📦 CREATE CONTENT VERSION OBJECT (like blog.py endpoint)
            # Convert datetime to ISO string for JSON serialization
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
                "brand_tonality_applied": brand_tonality,
                "person_tone_applied": person_tone,
                "generation_method": "pro"  # PRO tier
            }

            # 📊 LOG WHAT'S BEING SAVED TO MONGODB
            logger.info("=" * 80)
            logger.info("💾 SAVING FINAL BLOG DATA TO MONGODB (PRO)")
            logger.info("=" * 80)
            logger.info(f"Blog ID: {blog_id}")
            logger.info(f"Content saved as ARRAY with version object")
            logger.info(f"Content Version: 1")
            logger.info(f"Content Tag: generated")
            logger.info(f"Content Length: {len(blog_content)} characters")
            logger.info(f"Word Count (in version): {word_count} words")
            logger.info(f"Status: draft")
            logger.info(f"Brand Tonality Applied: {brand_tonality}")
            logger.info(f"Person Tone Applied: {person_tone}")
            logger.info(f"Generation Method: pro")
            logger.info("=" * 80)

            mongodb_service.get_sync_db()['blogs'].update_one(
                {'_id': ObjectId(blog_id)},
                {'$set': update_data}
            )
            logger.info(f"✅ Blog content successfully saved to MongoDB for blog_id: {blog_id}")
            
            # ✨ AUTO-TRIGGER FEATURED IMAGE GENERATION (ALWAYS ENABLED)
            try:
                logger.info(f"🎨 Auto-starting featured image generation for blog_id: {blog_id}")
                
                # Prepare image request from blog data (using extracted MongoDB variables)
                image_request = {
                    "blog_content": blog_content,  # Full generated blog content
                    "blog_id": blog_id,
                    "country": country,
                    "category": category,
                    "primary_keyword": primary_keyword
                }
                
                # Launch featured image generation asynchronously
                from app.tasks.featured_image_generation import generate_featured_image
                
                image_task = generate_featured_image.delay(
                    image_request=image_request,
                    project_id=project_id,
                    project=project,
                    request_id=f"blog_v2_{blog_id}_{uuid.uuid4().hex[:8]}"
                )
                
                # Update Redis with image generation status
                task_data = redis_client.get(redis_key)
                if task_data:
                    task_info = json.loads(task_data)
                    task_info["featured_image"] = {
                        "status": "generating",
                        "task_id": image_task.id,
                        "started_at": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat(),
                        "request_id": f"blog_v2_{blog_id}_{uuid.uuid4().hex[:8]}"
                    }
                    
                    # 🚀 ADD STREAMING NOTIFICATION: Notify SSE clients that image generation started
                    if "streaming_data" in task_info["steps"]["blog_generation"]:
                        task_info["steps"]["blog_generation"]["streaming_data"]["image_generation_started"] = True
                        task_info["steps"]["blog_generation"]["streaming_data"]["image_task_id"] = image_task.id
                        task_info["steps"]["blog_generation"]["streaming_data"]["image_started_at"] = datetime.now(pytz.timezone('Asia/Kolkata')).isoformat()
                    
                    # 🎯 NOW MARK AS COMPLETED: Image generation triggered, now mark blog as fully completed
                    task_info["status"] = "completed"
                    task_info["steps"]["blog_generation"]["status"] = "completed"
                    
                    redis_client.set(redis_key, json.dumps(task_info), ex=86400)
                
                logger.info(f"🎨 Featured image generation started: {image_task.id} for blog_id: {blog_id}")
                logger.info(f"📡 Streaming notification added for image generation start")
                logger.info(f"✅ FINAL COMPLETION: Blog marked as completed AFTER image trigger for blog_id: {blog_id}")
                
            except Exception as image_error:
                logger.error(f"⚠️ Failed to start featured image generation for blog_id {blog_id}: {str(image_error)}")
                # Update blog Redis to show image generation failed
                try:
                    task_data = redis_client.get(redis_key)
                    if task_data:
                        task_info = json.loads(task_data)
                        task_info["featured_image"] = {
                            "status": "failed",
                            "error": str(image_error),
                            "failed_at": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat()
                        }
                        # 🎯 STILL MARK AS COMPLETED: Blog is done even if image failed
                        task_info["status"] = "completed"
                        task_info["steps"]["blog_generation"]["status"] = "completed"
                        redis_client.set(redis_key, json.dumps(task_info), ex=86400)
                        logger.info(f"✅ BLOG COMPLETED: Marked as completed despite image failure for blog_id: {blog_id}")
                except Exception as redis_update_error:
                    logger.warning(f"Failed to update Redis with image error: {str(redis_update_error)}")
                # Don't raise - image generation failure shouldn't fail blog generation
            
        except Exception as mongo_error:
            logger.error(f"Failed to save to MongoDB: {str(mongo_error)}")
            raise
        
        # ONLY AFTER MongoDB save - mark streaming as completed in Redis
        finalize_streaming_data(blog_id, blog_content, word_count, redis_key)
        
        # DO NOT update progress again - already set to 100% in message_stop
        # Progress was already updated in message_stop event to prevent "stuck at 100%" issue
        
        # Post-processing status update (completion already marked immediately after streaming)
        try:
            task_data = redis_client.get(redis_key)
            if task_data:
                task_info = json.loads(task_data)
                # Don't override status (already set to "completed" immediately after streaming)
                # Just update any additional metadata from post-processing
                task_info["post_processing_completed"] = True
                task_info["post_processing_completed_at"] = datetime.now(pytz.timezone('Asia/Kolkata')).isoformat()
                redis_client.set(redis_key, json.dumps(task_info), ex=86400)
                logger.info(f"📋 Post-processing completed for blog_id: {blog_id}")
        except Exception as redis_error:
            logger.warning(f"Failed to update Redis post-processing status: {str(redis_error)}")
        
        # Record combined usage following the EXACT same pattern as advanced outline
        logger.info(f"🔍 BILLING DEBUG: Starting billing process for blog_id: {blog_id}")
        logger.info(f"🔍 BILLING DEBUG: usage_tracker = {usage_tracker}")
        logger.info(f"🔍 BILLING DEBUG: total_calls = {usage_tracker.get('total_calls', 0)}")
        logger.info(f"🔍 BILLING DEBUG: user_id = {usage_tracker.get('user_id')}")
        
        if usage_tracker.get("total_calls", 0) > 0 and usage_tracker.get("user_id"):
            logger.info(f"🔍 BILLING DEBUG: Billing conditions met - proceeding with billing")
            try:
                # Import locally to avoid SQLAlchemy relationship mapping issues (matches keywords.py pattern)
                logger.info(f"🔍 BILLING DEBUG: Starting model imports")
                # Force import ALL Account dependencies BEFORE Account to resolve relationship mapping in Celery workers
                from app.models.razorpay import RazorpayPayment  # noqa: F401 - Required for proper SQLAlchemy model initialization order
                from app.models.invoice import Invoice  # noqa: F401 - Required for proper SQLAlchemy model initialization order
                from app.models.transaction import Transaction  # noqa: F401 - Required for proper SQLAlchemy model initialization order
                from app.models.account import Account  # noqa: F401 - Required for proper SQLAlchemy model initialization order
                from app.services.enhanced_llm_usage_service import EnhancedLLMUsageService
                logger.info(f"🔍 BILLING DEBUG: Model imports completed successfully")
                
                # Use the SAME initialization pattern as AdvancedOutlineGenerationService (Line 90)
                logger.info(f"🔍 BILLING DEBUG: Checking for existing db session")
                logger.info(f"🔍 BILLING DEBUG: hasattr(self, 'db') = {hasattr(self, 'db')}")
                if hasattr(self, 'db'):
                    logger.info(f"🔍 BILLING DEBUG: self.db = {getattr(self, 'db', None)}")
                
                if hasattr(self, 'db') and self.db:
                    logger.info(f"🔍 BILLING DEBUG: Using existing db session")
                    llm_usage_service = EnhancedLLMUsageService(self.db)
                else:
                    logger.info(f"🔍 BILLING DEBUG: Creating new db session")
                    with get_db_session() as db:
                        logger.info(f"🔍 BILLING DEBUG: New db session created: {db}")
                        llm_usage_service = EnhancedLLMUsageService(db)
                        logger.info(f"🔍 BILLING DEBUG: EnhancedLLMUsageService initialized: {llm_usage_service}")
                
                # Use the EXACT same metadata structure as advanced outline (Lines 877-889)
                logger.info(f"🔍 BILLING DEBUG: Building blog metadata")
                blog_metadata = {
                    "blog_generation_stats": {
                        "total_api_calls": usage_tracker["total_calls"],
                        "request_id": usage_tracker["request_id"],
                        "blog_id": blog_id,
                        "word_count": word_count,
                        "generation_method": "pro"
                    },
                    "individual_api_calls": usage_tracker["individual_calls"]
                }
                logger.info(f"🔍 BILLING DEBUG: Blog metadata created: {blog_metadata}")
                
                # Calculate cost manually for debugging
                logger.info(f"🔍 BILLING DEBUG: Starting cost calculation")
                from app.config.llm_pricing import LLM_MODEL_PRICING
                from app.config.service_multipliers import get_service_multiplier
                logger.info(f"🔍 BILLING DEBUG: Imported pricing configs")
                
                # Calculate total base cost from individual calls (including reasoning tokens)
                total_base_cost = 0.0
                logger.info(f"🔍 BILLING DEBUG: Processing {len(usage_tracker['individual_calls'])} individual calls")
                for i, call in enumerate(usage_tracker["individual_calls"]):
                    model_name = call["model"]
                    input_tokens = call["input_tokens"]
                    output_tokens = call["output_tokens"]
                    reasoning_tokens = call.get("reasoning_tokens", 0)  # GPT-5 only
                    
                    log_msg = f"🔍 BILLING DEBUG: Call {i+1}: {model_name}, {input_tokens} input, {output_tokens} output"
                    if reasoning_tokens > 0:
                        log_msg += f", {reasoning_tokens} reasoning"
                    logger.info(log_msg)
                    
                    if model_name in LLM_MODEL_PRICING:
                        pricing = LLM_MODEL_PRICING[model_name]
                        logger.info(f"🔍 BILLING DEBUG: Pricing for {model_name}: {pricing}")
                        
                        input_cost = (input_tokens / 1000) * pricing["input_per_1k"]
                        output_cost = (output_tokens / 1000) * pricing["output_per_1k"]
                        
                        # Add reasoning token cost for GPT-5 (same rate as output tokens typically)
                        reasoning_cost = 0.0
                        if reasoning_tokens > 0 and "reasoning_per_1k" in pricing:
                            reasoning_cost = (reasoning_tokens / 1000) * pricing["reasoning_per_1k"]
                        elif reasoning_tokens > 0:
                            # Fallback: use output token rate for reasoning tokens
                            reasoning_cost = (reasoning_tokens / 1000) * pricing["output_per_1k"]
                            
                        call_cost = input_cost + output_cost + reasoning_cost
                        total_base_cost += call_cost
                        
                        cost_breakdown = f"{input_tokens}+{output_tokens}"
                        if reasoning_tokens > 0:
                            cost_breakdown += f"+{reasoning_tokens} reasoning"
                        cost_breakdown += f" tokens = ${call_cost:.6f}"
                        
                        logger.info(f"📊 Cost calculation: {model_name} = {cost_breakdown}")
                        logger.info(f"🔍 BILLING DEBUG: Input: ${input_cost:.6f}, Output: ${output_cost:.6f}, Reasoning: ${reasoning_cost:.6f}")
                    else:
                        logger.error(f"🔍 BILLING DEBUG: Model {model_name} not found in pricing config!")
                        logger.info(f"🔍 BILLING DEBUG: Available models: {list(LLM_MODEL_PRICING.keys())}")
                
                logger.info(f"🔍 BILLING DEBUG: Total base cost calculated: ${total_base_cost:.6f}")
                
                # Apply service multiplier
                logger.info(f"🔍 BILLING DEBUG: Getting service multiplier for 'blog_generation'")
                try:
                    service_multiplier_data = get_service_multiplier("blog_generation")
                    logger.info(f"🔍 BILLING DEBUG: Service multiplier data: {service_multiplier_data}")
                    service_multiplier = service_multiplier_data["multiplier"]
                    logger.info(f"🔍 BILLING DEBUG: Service multiplier extracted: {service_multiplier}")
                except Exception as multiplier_error:
                    logger.error(f"🔍 BILLING DEBUG: Error getting service multiplier: {str(multiplier_error)}")
                    service_multiplier = 5.0  # Default fallback
                
                final_charge = total_base_cost * service_multiplier
                
                logger.info(f"📊 Total base cost: ${total_base_cost:.6f}, Multiplier: {service_multiplier}x, Final: ${final_charge:.6f}")
                
                # Use accurate cost calculation via underlying UsageService
                logger.info(f"🔍 BILLING DEBUG: Starting record_usage_and_charge call")
                logger.info(f"🔍 BILLING DEBUG: Parameters:")
                logger.info(f"🔍 BILLING DEBUG:   user_id = {usage_tracker['user_id']}")
                logger.info(f"🔍 BILLING DEBUG:   service_name = 'blog_generation'")
                logger.info(f"🔍 BILLING DEBUG:   base_cost = ${total_base_cost:.6f}")
                logger.info(f"🔍 BILLING DEBUG:   multiplier = {service_multiplier}")
                logger.info(f"🔍 BILLING DEBUG:   project_id = {project_id}")
                logger.info(f"🔍 BILLING DEBUG:   usage_data = {blog_metadata}")
                
                try:
                    billing_result = llm_usage_service.usage_service.record_usage_and_charge(
                        user_id=usage_tracker["user_id"],
                        service_name="blog_generation",
                        base_cost=total_base_cost,  # Use the accurate calculated cost
                        multiplier=service_multiplier,
                        service_description=f"Blog generation V2 - {usage_tracker['total_calls']} API calls combined",
                        usage_data=blog_metadata,
                        project_id=project_id
                    )
                    logger.info(f"🔍 BILLING DEBUG: record_usage_and_charge call completed successfully")
                except Exception as billing_call_error:
                    logger.error(f"🔍 BILLING DEBUG: record_usage_and_charge call failed: {str(billing_call_error)}")
                    logger.error(f"🔍 BILLING DEBUG: Full billing error traceback:", exc_info=True)
                    raise
                
                # Log the full billing result for debugging
                logger.info(f"📋 BILLING RESULT: {billing_result}")
                logger.info(f"🔍 BILLING DEBUG: Billing result type: {type(billing_result)}")
                logger.info(f"🔍 BILLING DEBUG: Billing result keys: {list(billing_result.keys()) if isinstance(billing_result, dict) else 'Not a dict'}")
                
                # Check if usage was actually recorded
                logger.info(f"🔍 BILLING DEBUG: Checking billing result success")
                if billing_result.get("success"):
                    logger.info(f"🔍 BILLING DEBUG: Billing result indicates success")
                    logger.info(f"✅ BLOG GENERATION BILLING RECORDED: {usage_tracker['total_calls']} calls, "
                               f"${billing_result.get('actual_charge', 0):.6f} charged with {billing_result.get('multiplier', 'unknown')}x multiplier")
                    logger.info(f"💰 BILLING SUMMARY: Usage ID={billing_result.get('usage_id')}, "
                               f"Transaction ID={billing_result.get('transaction_id')}, "
                               f"Balance: ${billing_result.get('previous_balance', 0):.2f} → ${billing_result.get('new_balance', 0):.2f}")
                else:
                    logger.info(f"🔍 BILLING DEBUG: Billing result indicates failure or no success key")
                    logger.info(f"🔍 BILLING DEBUG: billing_result.get('success') = {billing_result.get('success')}")
                    
                    # Check if usage record was created in database
                    logger.info(f"🔍 BILLING DEBUG: Checking usage table for verification")
                    try:
                        from app.models.usage import Usage
                        logger.info(f"🔍 BILLING DEBUG: Usage model imported successfully")
                        with get_db_session() as db:
                            logger.info(f"🔍 BILLING DEBUG: New db session for verification: {db}")
                            logger.info(f"🔍 BILLING DEBUG: Querying for user_id={usage_tracker['user_id']}, service_name='blog_generation'")
                            latest_usage = db.query(Usage).filter(
                                Usage.user_id == usage_tracker["user_id"],
                                Usage.service_name == "blog_generation"
                            ).order_by(Usage.created_at.desc()).first()
                            logger.info(f"🔍 BILLING DEBUG: Query executed, result: {latest_usage}")
                            
                            if latest_usage:
                                logger.info(f"🔍 BILLING DEBUG: Found usage record: ID={latest_usage.id}")
                                logger.info(f"🔍 BILLING DEBUG: Usage details: cost=${latest_usage.actual_charge:.6f}, created_at={latest_usage.created_at}")
                                logger.info(f"✅ USAGE TABLE UPDATED: ID={latest_usage.id}, Cost=${latest_usage.actual_charge:.6f}")
                            else:
                                logger.error("❌ NO USAGE RECORD FOUND in usage table")
                                logger.info(f"🔍 BILLING DEBUG: Let's check if any usage records exist at all")
                                all_usage = db.query(Usage).filter(Usage.user_id == usage_tracker["user_id"]).count()
                                logger.info(f"🔍 BILLING DEBUG: Total usage records for user: {all_usage}")
                    except Exception as db_check_error:
                        logger.error(f"❌ Error checking usage table: {db_check_error}")
                        logger.error(f"🔍 BILLING DEBUG: Database check error traceback:", exc_info=True)
                
            except Exception as e:
                logger.error(f"❌ Failed to record blog generation usage: {e}")
                logger.error(f"🔍 BILLING DEBUG: Full billing exception traceback:", exc_info=True)
        else:
            logger.warning("No API calls were made during blog generation or missing user_id")
            logger.info(f"🔍 BILLING DEBUG: Billing skipped because:")
            logger.info(f"🔍 BILLING DEBUG:   total_calls = {usage_tracker.get('total_calls', 0)} (needs > 0)")
            logger.info(f"🔍 BILLING DEBUG:   user_id = {usage_tracker.get('user_id')} (needs to exist)")
            logger.info(f"🔍 BILLING DEBUG:   Condition met: {usage_tracker.get('total_calls', 0) > 0 and usage_tracker.get('user_id')}")
        
        logger.info(f"Blog generation V2 completed for blog_id: {blog_id}, word_count: {word_count}")
        
        return {
            "blog_id": blog_id,
            "content": blog_content,
            "word_count": word_count,
            "specialty_info": {"expertise": "Content Expert", "static": True},
            "brand_tonality_applied": brand_tonality,
            "person_tone_applied": person_tone,
            "status": "completed",
            "generation_method": "pro",
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
            "task_name": "generate_final_blog_step"
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


@celery.task(name="app.tasks.blog_generation_pro.get_blog_status_pro", queue="blog_generation")
def get_blog_status_pro(blog_id: str) -> Dict[str, Any]:
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
        
        # Check for featured image status
        featured_image_status = None
        if "featured_image" in task_info:
            img_data = task_info["featured_image"]
            if img_data.get("status") == "generating":
                # Check if image generation is complete
                try:
                    from app.tasks.featured_image_generation import get_featured_image_status_by_blog_id
                    img_status_result = get_featured_image_status_by_blog_id(blog_id)
                    if img_status_result.get("status") == "completed":
                        featured_image_status = {
                            "status": "completed",
                            "image_url": img_status_result.get("result", {}).get("public_url"),
                            "image_id": img_status_result.get("result", {}).get("image_id")
                        }
                    else:
                        featured_image_status = {
                            "status": img_status_result.get("status", "generating"),
                            "progress": img_status_result.get("progress", 0)
                        }
                except Exception as img_check_error:
                    logger.warning(f"Failed to check featured image status: {str(img_check_error)}")
                    featured_image_status = {"status": "unknown"}
            else:
                featured_image_status = {"status": img_data.get("status", "unknown")}
        
        result = {
            "status": frontend_status,
            "progress": overall_progress,
            "content": task_info.get("final_content", ""),
            "message": message,
            "blog_id": blog_id
        }
        
        # Add featured image data if available
        if featured_image_status:
            result["featured_image"] = featured_image_status
        
        # Add MongoDB featured image data
        try:
            mongodb_service = MongoDBService()
            mongodb_service.init_sync_db()
            blog_doc = mongodb_service.get_sync_db()['blogs'].find_one({"_id": ObjectId(blog_id)})
            if blog_doc:
                result["featured_image"] = blog_doc.get("rayo_featured_image")
        except Exception as mongo_error:
            logger.warning(f"Failed to get MongoDB featured image data: {str(mongo_error)}")
            
        return result
        
    except Exception as e:
        logger.error(f"Error getting blog status V2: {str(e)}")
        return {
            "status": "failed",
            "progress": 0,
            "content": "",
            "message": f"Error retrieving status: {str(e)}",
            "blog_id": blog_id
        }