"""
Blog Generation V2 API Endpoints
Simplified 2-step blog generation with brand tonality mapping
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Union
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List
from bson import ObjectId
from app.middleware.auth_middleware import verify_token_sync
from app.services.mongodb_service import MongoDBService
from app.services.blog_tracking_service import blog_tracking_service
from app.tasks.blog_generation import generate_blog_pro, get_blog_status_pro
from app.tasks.blog_generation_free import generate_blog_free, get_blog_status_free
from app.utils.user_tier_detection import get_user_tier
import pytz
from app.models.project import Project
from app.db.session import get_db_session
from sqlalchemy.orm import Session
from app.services.balance_validator import BalanceValidator
import json
import redis
import asyncio
import time

# Import Pro access control
async def require_pro(request: Request):
    """Check if user has active Pro plan"""
    from app.models.account import Account
    from app.db.session import get_db
    from datetime import datetime
    import pytz
    
    db = next(get_db())
    
    # Get user from request state (set by auth middleware)
    if not hasattr(request.state, 'user') or not request.state.user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    user_id = request.state.user.user.id
    account = db.query(Account).filter(Account.user_id == user_id).first()
    
    if not account or account.plan_type != "pro":
        raise HTTPException(
            status_code=403, 
            detail={
                "error": "Pro plan required",
                "message": "This feature requires a Pro subscription",
                "current_plan": account.plan_type if account else "free",
                "upgrade_url": "https://app.rayo.work/upgrade"
            }
        )
    
    # Check if plan is expired using timezone-aware datetime
    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist)
    if account.plan_end_date and account.plan_end_date < current_time:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Pro plan expired", 
                "message": "Your Pro subscription has expired",
                "plan_expired": True,
                "upgrade_url": "https://app.rayo.work/upgrade"
            }
        )
    
    return True

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis client for streaming data
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

router = APIRouter()

class BrandTonality(BaseModel):
    formality: Optional[str] = Field(None, description="Formality level: formal, semi_formal, casual")
    attitude: Optional[str] = Field(None, description="Attitude: bold, friendly, neutral, authoritative")
    energy: Optional[str] = Field(None, description="Energy level: high, medium, low")
    clarity: Optional[str] = Field(None, description="Clarity level: simple, detailed, balanced")

class BlogGenerationV2Request(BaseModel):
    brand_tonality: BrandTonality = Field(..., description="Brand tonality settings")

class BlogGenerationV2Response(BaseModel):
    success: bool
    message: str
    blog_id: str
    task_id: str
    status: str
    estimated_completion_time: str

class BlogStatusV2Response(BaseModel):
    status: str
    progress: int
    content: str
    message: str
    blog_id: str
    featured_image: Optional[Dict[str, Any]] = None

@router.post("/{blog_id}", response_model=BlogGenerationV2Response)
async def generate_blog_v2_endpoint(
    request: Request,
    blog_id: str,
    blog_request: BlogGenerationV2Request,
    background_tasks: BackgroundTasks
):
    """
    Generate blog using V2 simplified process - retrieves data from MongoDB

    Args:
        request: FastAPI Request object
        blog_id: MongoDB blog document ID from URL path
        blog_request: Contains brand_tonality
        background_tasks: FastAPI background tasks

    Returns:
        Blog generation response with task information
    """
    try:
        # Verify authentication
        auth_result = verify_token_sync(request)
        if not auth_result:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token"
            )

        # Get project_id from path params
        project_id = request.path_params.get("project_id")

        logger.info(f"Starting blog generation V2 for blog_id: {blog_id}, project_id: {project_id}")

        # Get blog document from MongoDB (created by step workflow)
        mongodb_service = MongoDBService()
        mongodb_service.init_sync_db()

        blog_doc = mongodb_service.get_sync_db()['blogs'].find_one({
            "_id": ObjectId(blog_id),
            "project_id": project_id
        })

        if not blog_doc:
            raise HTTPException(
                status_code=404,
                detail="Blog document not found. Please complete the previous steps first."
            )

        # Verify blog has completed all required steps
        step_tracking = blog_doc.get("step_tracking", {})
        current_step = step_tracking.get("current_step", "")
        if current_step not in ["outline", "sources"]:
            raise HTTPException(
                status_code=400,
                detail=f"Blog is not ready for generation. Current step: {current_step}. Please complete all steps first."
            )

        logger.info(f"✅ Blog document validated - current_step: {current_step}")

        # Get user_id from blog document
        user_id = str(blog_doc.get("user_id"))

        # Use context manager for database session
        with get_db_session() as db:
            # Validate project exists
            project = db.query(Project).filter(Project.id == project_id).first()

            if not project:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project not found with id: {project_id}"
                )

            # Verify project belongs to user
            if str(project.user_id) != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied to this project"
                )

            # 🚀 FAST BALANCE VALIDATION - Check balance BEFORE processing
            balance_validator = BalanceValidator(db)
            balance_check = balance_validator.validate_service_balance(
                user_id=user_id,
                service_key="blog_generation"
            )

            if not balance_check["valid"]:
                if balance_check["error"] == "insufficient_balance":
                    raise HTTPException(
                        status_code=402,  # Payment Required
                        detail={
                            "error": "insufficient_balance",
                            "message": balance_check["message"],
                            "required_balance": balance_check["required_balance"],
                            "current_balance": balance_check["current_balance"],
                          "shortfall": balance_check["shortfall"],
                              "next_refill_time": balance_check.get("next_refill_time").isoformat() if balance_check.get("next_refill_time") else None                       }
                    )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": balance_check["error"],
                            "message": balance_check["message"]
                        }
                    )

            logger.info(f"✅ Balance validation passed for user {user_id}: ${balance_check['current_balance']:.2f} >= ${balance_check['required_balance']:.2f}")

            # Convert project to dictionary for task processing
            project_dict = {
                "id": str(project.id),
                "name": project.name,
                "user_id": str(project.user_id),
                "brand_tone": getattr(project, 'brand_tone', None),
                "languages": project.languages or [],
                "featured_image_style": getattr(project, 'featured_image_style', None)  # Add this for PRO image generation
            }

        # Update MongoDB status to "creating" and store brand_tonality from payload
        mongodb_service.get_sync_db()['blogs'].update_one(
            {'_id': ObjectId(blog_id)},
            {'$set': {
                'status': 'creating',
                'brand_tonality': blog_request.brand_tonality.dict(),  # Store brand tonality from payload
                'updated_at': datetime.now(timezone.utc)
            }}
        )

        logger.info(f"✅ Updated blog document with brand_tonality: {blog_request.brand_tonality.dict()}")

        # Start blog generation tracking
        try:
            # Extract title and primary keyword for tracking
            title_array = blog_doc.get("title", [])
            selected_title = title_array[-1] if title_array else "Untitled"

            primary_keyword_array = blog_doc.get("primary_keyword", [])
            primary_keyword = ""
            if primary_keyword_array:
                primary_keyword_data = primary_keyword_array[-1]
                # Handle both old format (string) and new format (dict)
                if isinstance(primary_keyword_data, str):
                    primary_keyword = primary_keyword_data
                else:
                    primary_keyword = primary_keyword_data.get("keyword", "")

            blog_tracking_service.start_blog_generation_tracking(
                blog_id=blog_id,
                project_id=project_id,
                user_id=user_id,
                blog_title=selected_title,
                primary_keyword=primary_keyword
            )
        except Exception as tracking_error:
            logger.warning(f"Failed to start tracking: {str(tracking_error)}")

        # 🎯 USER TIER DETECTION - Route to appropriate task based on user tier
        user_tier = get_user_tier(db, user_id)

        if user_tier == "pro":
            # Launch PRO blog generation task - only pass blog_id
            task_result = generate_blog_pro.delay(
                blog_id=blog_id,
                project_id=project_id,
                project=project_dict
            )
            logger.info(f"🚀 Launched PRO blog generation task for user {user_id}: {task_result.id}")
        else:
            # Launch FREE blog generation task - only pass blog_id
            task_result = generate_blog_free.delay(
                blog_id=blog_id,
                project_id=project_id,
                project=project_dict
            )
            logger.info(f"🆓 Launched FREE blog generation task for user {user_id}: {task_result.id}")

        logger.info(f"Successfully routed blog generation request for user tier: {user_tier}")

        return BlogGenerationV2Response(
            success=True,
            message="Blog generation V2 started successfully",
            blog_id=blog_id,
            task_id=task_result.id,
            status="processing",
            estimated_completion_time="5-10 minutes"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in generate_blog_v2_endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start blog generation: {str(e)}"
        )

@router.get("/status/{blog_id}", response_model=BlogStatusV2Response)
async def get_blog_generation_status_v2(
    request: Request,
    blog_id: str
):
    """
    Get detailed status of V2 blog generation
    
    Args:
        project_id: Project identifier
        blog_id: Blog document ID
        current_user: Authenticated user information
        
    Returns:
        Detailed status information for the blog generation
    """
    try:
        logger.info(f"Getting blog generation status for blog_id: {blog_id}")
        
        # 🔍 SMART STATUS DETECTION - Try both status functions since we need to determine tier
        # First try PRO status function
        try:
            status_result = get_blog_status_pro(blog_id)
            if status_result and status_result.get("status") != "unknown":
                logger.info(f"Found PRO task status for blog_id: {blog_id}")
            else:
                # Try FREE status function as fallback
                status_result = get_blog_status_free(blog_id)
                logger.info(f"Found FREE task status for blog_id: {blog_id}")
        except Exception:
            # Fallback to FREE status function
            status_result = get_blog_status_free(blog_id)
            logger.info(f"Using FREE task status (fallback) for blog_id: {blog_id}")
        
        return BlogStatusV2Response(
            status=status_result.get("status", "unknown"),
            progress=status_result.get("progress", 0),
            content=status_result.get("content", ""),
            message=status_result.get("message", ""),
            blog_id=status_result.get("blog_id", blog_id),
            featured_image=status_result.get("featured_image"),
            featured_image_generation=status_result.get("featured_image_generation")
        )
        
    except Exception as e:
        logger.error(f"Error getting blog status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get blog status: {str(e)}"
        )

@router.get("/content/{blog_id}")
async def get_blog_content_v2(
    request: Request,
    blog_id: str
):
    """
    Get the final blog content from MongoDB
    
    Args:
        project_id: Project identifier
        blog_id: Blog document ID
        current_user: Authenticated user information
        
    Returns:
        Complete blog content and metadata
    """
    try:
        # Verify authentication
        auth_result = verify_token_sync(request)
        if not auth_result:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token"
            )
        
        # Get project_id from request path params
        project_id = request.path_params.get("project_id")
        
        logger.info(f"Getting blog content V2 for blog_id: {blog_id}")
        
        # Get blog from MongoDB
        mongodb_service = MongoDBService()
        mongodb_service.init_sync_db()
        blog_doc = mongodb_service.get_sync_db()['blogs'].find_one({"_id": ObjectId(blog_id)})
        
        if not blog_doc:
            raise HTTPException(
                status_code=404,
                detail="Blog not found"
            )
        
        # Verify user has access to this blog
        if blog_doc.get("project_id") != project_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied to this blog"
            )
        
        return {
            "blog_id": blog_id,
            "title": blog_doc.get("title", ""),
            "content": blog_doc.get("content", ""),
            "word_count": blog_doc.get("word_count", 0),
            "status": blog_doc.get("status", "unknown"),
            "primary_keyword": blog_doc.get("primary_keyword", ""),
            "secondary_keywords": blog_doc.get("secondary_keywords", []),
            "category": blog_doc.get("category", ""),
            "subcategory": blog_doc.get("subcategory", ""),
            "country": blog_doc.get("country", ""),
            "brand_tonality": blog_doc.get("brand_tonality", {}),
            "created_at": blog_doc.get("created_at"),
            "updated_at": blog_doc.get("updated_at"),
            "generation_method": blog_doc.get("generation_method", "v2_simplified"),
            "featured_image": blog_doc.get("rayo_featured_image"),
            "featured_image_generation": blog_doc.get("featured_image_generation")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting blog content V2: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get blog content: {str(e)}"
        )

@router.post("/retry/{blog_id}")
async def retry_blog_generation(
    request: Request,
    blog_id: str,
    background_tasks: BackgroundTasks
):
    """
    Retry failed blog generation using V2 process
    
    Args:
        project_id: Project identifier
        blog_id: Blog document ID to retry
        background_tasks: FastAPI background tasks
        db: Database session
        current_user: Authenticated user information
        
    Returns:
        Retry response with new task information
    """
    try:
        # Verify authentication
        auth_result = verify_token_sync(request)
        if not auth_result:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token"
            )
        
        # Get project_id from request path params
        project_id = request.path_params.get("project_id")
        user_id = None
        
        logger.info(f"Retrying blog generation V2 for blog_id: {blog_id}")
        
        # Use context manager for database session
        with get_db_session() as db:
            # Validate project exists
            project = db.query(Project).filter(Project.id == project_id).first()
            
            if not project:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project not found with id: {project_id}"
                )
            
            # Get user_id from project or auth
            user_id = request.state.user.user.id if hasattr(request.state, 'user') and request.state.user and hasattr(request.state.user, 'user') else str(project.user_id)
            
            # 🚀 FAST BALANCE VALIDATION - Check balance BEFORE processing
            balance_validator = BalanceValidator(db)
            balance_check = balance_validator.validate_service_balance(
                user_id=user_id,
                service_key="blog_generation"
            )
            
            if not balance_check["valid"]:
                if balance_check["error"] == "insufficient_balance":
                    raise HTTPException(
                        status_code=402,  # Payment Required
                        detail={
                            "error": "insufficient_balance",
                            "message": balance_check["message"],
                            "required_balance": balance_check["required_balance"],
                            "current_balance": balance_check["current_balance"],
                          "shortfall": balance_check["shortfall"],
                              "next_refill_time": balance_check.get("next_refill_time").isoformat() if balance_check.get("next_refill_time") else None                       }
                    )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": balance_check["error"],
                            "message": balance_check["message"]
                        }
                    )
            
            logger.info(f"✅ Balance validation passed for user {user_id}: ${balance_check['current_balance']:.2f} >= ${balance_check['required_balance']:.2f}")
            
            # Convert project to dictionary
            project_dict = {
                "id": str(project.id),
                "name": project.name,
                "user_id": str(project.user_id),
                "brand_tone": getattr(project, 'brand_tone', None),
                "languages": project.languages or [],
                "featured_image_style": getattr(project, 'featured_image_style', None)  # Add this for PRO image generation
            }
        
        # Get existing blog from MongoDB
        mongodb_service = MongoDBService()
        mongodb_service.init_sync_db()
        blog_doc = mongodb_service.get_sync_db()['blogs'].find_one({"_id": ObjectId(blog_id)})
        
        if not blog_doc:
            raise HTTPException(
                status_code=404,
                detail="Blog not found"
            )
        
        # Verify blog belongs to this project
        if blog_doc.get("project_id") != project_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied to this blog"
            )
        
        # Reset blog status to creating
        mongodb_service.update_blog_status(blog_id, "creating")
        
        # 🎯 USER TIER DETECTION FOR RETRY - Route to appropriate task
        # No need to reconstruct blog_request - data comes from MongoDB
        user_tier = get_user_tier(db, user_id)

        if user_tier == "pro":
            # Launch PRO retry task - only pass blog_id
            task_result = generate_blog_pro.delay(
                blog_id=blog_id,
                project_id=project_id,
                project=project_dict
            )
            logger.info(f"🚀 Launched PRO retry task for user {user_id}: {task_result.id}")
        else:
            # Launch FREE retry task - only pass blog_id
            task_result = generate_blog_free.delay(
                blog_id=blog_id,
                project_id=project_id,
                project=project_dict
            )
            logger.info(f"🆓 Launched FREE retry task for user {user_id}: {task_result.id}")
        
        logger.info(f"Successfully routed retry request for blog_id: {blog_id}, user_tier: {user_tier}, task_id: {task_result.id}")
        
        return {
            "success": True,
            "message": "Blog generation retry started successfully",
            "blog_id": blog_id,
            "new_task_id": task_result.id,
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in retry_blog_generation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retry blog generation: {str(e)}"
        )

@router.post("/regenerate/{blog_id}")
async def regenerate_blog_v2(
    request: Request,
    blog_id: str,
    background_tasks: BackgroundTasks,
    _: bool = Depends(require_pro)
):
    """
    Regenerate blog: Duplicate existing blog + retry on the copy
    """
    try:
        project_id = request.path_params.get("project_id")
        logger.info(f"Regenerating blog: {blog_id}")
        
        # Get original blog
        mongodb_service = MongoDBService()
        mongodb_service.init_sync_db()
        original_blog = mongodb_service.get_sync_db()['blogs'].find_one({"_id": ObjectId(blog_id)})
        
        if not original_blog:
            raise HTTPException(status_code=404, detail="Blog not found")
        
        if original_blog.get("project_id") != project_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Duplicate document
        duplicate_blog = original_blog.copy()
        del duplicate_blog["_id"]  # Remove ID for new document

        # Reset for generation
        original_title_raw = duplicate_blog.get("title", "")

        # Handle title format (can be string or array)
        if isinstance(original_title_raw, list):
            original_title = original_title_raw[-1] if original_title_raw else ""
        else:
            original_title = original_title_raw

        # Don't prepend "Regenerated: " if it's already there
        if not original_title.startswith("Regenerated: "):
            new_title = f"Regenerated: {original_title}"
        else:
            # Already has "Regenerated: " prefix, just use it as is
            new_title = original_title

        duplicate_blog.update({
            "title": new_title,
            "status": "creating",
            "content": "",
            "regenerated_from": blog_id,
            "updated_at": datetime.now(timezone.utc)
        })
        # Note: Keep original word_count, country, intent, brand_tonality, etc. from duplicated blog
        
        # Create new blog
        result = mongodb_service.get_sync_db()['blogs'].insert_one(duplicate_blog)
        new_blog_id = str(result.inserted_id)
        
        logger.info(f"Duplicated: {blog_id} → {new_blog_id}")
        
        # Verify authentication (same as retry)
        auth_result = verify_token_sync(request)
        if not auth_result:
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        
        # Get user_id and validate (same as retry)
        user_id = None
        with get_db_session() as db:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise HTTPException(status_code=404, detail=f"Project not found with id: {project_id}")
            
            user_id = request.state.user.user.id if hasattr(request.state, 'user') and request.state.user and hasattr(request.state.user, 'user') else str(project.user_id)
            
            # Balance validation (same as retry)
            balance_validator = BalanceValidator(db)
            balance_check = balance_validator.validate_service_balance(user_id=user_id, service_key="blog_generation")
            
            if not balance_check["valid"]:
                if balance_check["error"] == "insufficient_balance":
                    raise HTTPException(status_code=402, detail={
                        "error": "insufficient_balance",
                        "message": balance_check["message"],
                        "required_balance": balance_check["required_balance"],
                        "current_balance": balance_check["current_balance"],
                        "shortfall": balance_check["shortfall"],
                        "next_refill_time": balance_check.get("next_refill_time").isoformat() if balance_check.get("next_refill_time") else None
                    })
                else:
                    raise HTTPException(status_code=400, detail={
                        "error": balance_check["error"],
                        "message": balance_check["message"]
                    })
            
            logger.info(f"✅ Balance validation passed for user {user_id}: ${balance_check['current_balance']:.2f} >= ${balance_check['required_balance']:.2f}")
            
            project_dict = {
                "id": str(project.id),
                "name": project.name,
                "user_id": str(project.user_id),
                "brand_tone": getattr(project, 'brand_tone', None),
                "languages": project.languages or [],
                "featured_image_style": getattr(project, 'featured_image_style', None)
            }
        
        # User tier detection and task launch
        # No need to reconstruct blog_request - data comes from MongoDB (duplicated document)
        user_tier = get_user_tier(db, user_id)

        if user_tier == "pro":
            task_result = generate_blog_pro.delay(
                blog_id=new_blog_id,
                project_id=project_id,
                project=project_dict
            )
            logger.info(f"🚀 Launched PRO regeneration task for user {user_id}: {task_result.id}")
        else:
            task_result = generate_blog_free.delay(
                blog_id=new_blog_id,
                project_id=project_id,
                project=project_dict
            )
            logger.info(f"🆓 Launched FREE regeneration task for user {user_id}: {task_result.id}")
        
        return {
            "success": True,
            "message": "Blog regeneration started",
            "original_blog_id": blog_id,
            "new_blog_id": new_blog_id,
            "new_task_id": task_result.id,
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Regenerate error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Regeneration failed: {str(e)}")

@router.get("/logs/{blog_id}")
async def get_blog_generation_logs_v2(
    request: Request,
    blog_id: str
):
    """
    Get detailed logs and progress information for V2 blog generation
    
    Args:
        project_id: Project identifier
        blog_id: Blog document ID
        current_user: Authenticated user information
        
    Returns:
        Detailed logs and progress information
    """
    try:
        # 🔍 SMART STATUS DETECTION FOR LOGS - Try both status functions
        try:
            status_result = get_blog_status_pro(blog_id)
            if not status_result or status_result.get("status") == "unknown":
                status_result = get_blog_status_free(blog_id)
        except Exception:
            status_result = get_blog_status_free(blog_id)
        
        # Get MongoDB document for additional details
        mongodb_service = MongoDBService()
        mongodb_service.init_sync_db()
        
        blog_doc = mongodb_service.get_sync_db()['blogs'].find_one(
            {'_id': ObjectId(blog_id)}
        )
        
        if not blog_doc:
            raise HTTPException(
                status_code=404,
                detail="Blog not found"
            )
        
        # Compile comprehensive logs
        logs = {
            "blog_id": blog_id,
            "status": status_result.get("status", "unknown"),
            "overall_progress": status_result.get("overall_progress", 0),
            "created_at": blog_doc.get("created_at"),
            "updated_at": blog_doc.get("updated_at"),
            "generation_method": "v2_simplified",
            "steps_detail": status_result.get("steps", {}),
            "error_message": blog_doc.get("error_message"),
            "task_info": {
                "task_id": status_result.get("task_id"),
                "redis_key": f"blog_generation:{blog_id}",
                "mongodb_status": blog_doc.get("status")
            },
            "content_info": {
                "word_count": blog_doc.get("word_count", 0),
                "brand_tonality_applied": blog_doc.get("brand_tonality_applied"),
                "has_content": bool(blog_doc.get("content"))
            },
            "original_request": blog_doc.get("original_blog_request", {})
        }
        
        return {
            "success": True,
            "logs": logs,
            "timestamp": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting blog logs V2: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get blog logs: {str(e)}"
        )

async def generate_sse_events(blog_id: str):
    """
    Generate Server-Sent Events for real-time blog generation streaming
    """
    # 🔍 SMART REDIS KEY DETECTION - Check for both PRO and FREE task keys
    redis_key_pro = f"blog_generation_task:{blog_id}"  # PRO task key
    redis_key_free = f"blog_generation_task:{blog_id}"  # FREE task key (same pattern for now)
    redis_key = redis_key_pro  # Start with PRO key, will switch if needed
    last_content_length = 0
    last_phase = None
    last_content_timestamp = None
    image_generation_notified = False  # Track if we've notified about image generation start
    stream_start_time = time.time()
    
    # Send initial connection event
    yield f"event: connected\ndata: {{\"message\": \"Connected to blog generation stream\", \"blog_id\": \"{blog_id}\"}}\n\n"
    
    try:
        timeout_seconds = 600  # 10 minutes timeout  
        check_interval = 0.05  # Check every 50ms for faster update detection
        
        while time.time() - stream_start_time < timeout_seconds:
            try:
                task_data = redis_client.get(redis_key)
                if not task_data:
                    # Task not found, might not have started yet
                    yield f"event: status\ndata: {{\"status\": \"waiting\", \"progress\": 0, \"message\": \"Waiting for task to start...\"}}\n\n"
                    await asyncio.sleep(check_interval)
                    continue
                
                task_info = json.loads(task_data)
                overall_status = task_info.get("status", "unknown")
                
                # Get overall progress from single step
                overall_progress = int(task_info.get("steps", {}).get("blog_generation", {}).get("progress", 0))
                # CLEAN: Cap progress at 100% to prevent overflow
                overall_progress = min(overall_progress, 100)
                
                # Get streaming data if available
                streaming_data = task_info.get("steps", {}).get("blog_generation", {}).get("streaming_data", {})
                
                if streaming_data:
                    current_phase = streaming_data.get("phase", "starting")
                    is_streaming = streaming_data.get("is_streaming", False)
                    content = streaming_data.get("live_content", "")
                    content_word_count = streaming_data.get("content_word_count", 0)
                    content_timestamp = streaming_data.get("content_update_timestamp")
                    
                    # 🧠 NEW: GPT-5 thinking phase data
                    thinking_content = streaming_data.get("live_thinking", "")
                    thinking_word_count = streaming_data.get("thinking_word_count", 0)
                    thinking_active = streaming_data.get("thinking_active", False)
                    content_active = streaming_data.get("content_active", True)
                    
                    # Send progress update
                    progress_data = {
                        "status": "in_progress" if overall_status in ["running", "processing", "blog_ready"] else overall_status,
                        "progress": overall_progress,
                        "phase": current_phase,
                        "content_words": content_word_count,
                        "thinking_words": thinking_word_count,  # NEW: thinking word count
                        "thinking_active": thinking_active,     # NEW: thinking phase active
                        "content_active": content_active,       # NEW: content phase active
                        "is_streaming": is_streaming,
                        "blog_id": blog_id
                    }
                    
                    yield f"event: progress\ndata: {json.dumps(progress_data)}\n\n"
                    
                    # 🧠 NEW: Send thinking updates for GPT-5 formal content
                    if current_phase == "thinking" and thinking_content and thinking_active:
                        thinking_data = {
                            "thinking": thinking_content,
                            "thinking_words": thinking_word_count,
                            "phase": current_phase,
                            "progress": overall_progress,
                            "is_streaming": is_streaming,
                            "status": "in_progress",
                            "blog_id": blog_id
                        }
                        yield f"event: thinking\ndata: {json.dumps(thinking_data)}\n\n"
                    
                    # Send content updates if content changed (check both timestamp AND content length)
                    content_changed = (
                        current_phase == "content" and content and 
                        (content_timestamp != last_content_timestamp or len(content) > last_content_length)
                    )
                    if content_changed:
                        content_data = {
                            "content": content,
                            "content_words": content_word_count,
                            "phase": current_phase,
                            "progress": overall_progress,
                            "is_streaming": is_streaming,
                            "status": "in_progress",
                            "blog_id": blog_id
                        }
                        yield f"event: content\ndata: {json.dumps(content_data)}\n\n"
                        last_content_timestamp = content_timestamp
                        last_content_length = len(content)
                    
                    # Send phase change notifications (including thinking phase)
                    if current_phase != last_phase and current_phase in ["thinking", "content", "completed"]:
                        logger.info(f"🔄 [SSE_STREAM] Phase change detected: {last_phase} → {current_phase} for blog_id: {blog_id}")
                        
                        phase_data = {
                            "phase": current_phase,
                            "status": "in_progress" if current_phase != "completed" and overall_status in ["running", "processing", "blog_ready"] else overall_status,
                            "progress": overall_progress,
                            "content_words": content_word_count,
                            "thinking_words": thinking_word_count,  # NEW: include thinking words in phase changes
                            "thinking_active": thinking_active,     # NEW: include thinking status
                            "content_active": content_active,       # NEW: include content status
                            "is_streaming": is_streaming,
                            "blog_id": blog_id
                        }
                        
                            
                        logger.info(f"🔄 [SSE_STREAM] Sending phase change event: {json.dumps(phase_data)}")
                        yield f"event: status\ndata: {json.dumps(phase_data)}\n\n"
                        last_phase = current_phase
                    
                    # 🎨 NEW: Detect and notify about image generation start
                    image_started = streaming_data.get("image_generation_started", False)
                    if image_started and not image_generation_notified:
                        image_task_id = streaming_data.get("image_task_id")
                        image_started_at = streaming_data.get("image_started_at")
                        
                        image_start_data = {
                            "image_generation": {
                                "status": "started",
                                "task_id": image_task_id,
                                "started_at": image_started_at,
                                "blog_id": blog_id,
                                "message": "Featured image generation started"
                            }
                        }
                        
                        logger.info(f"🎨 [SSE_STREAM] Image generation started notification: {image_task_id} for blog_id: {blog_id}")
                        yield f"event: image_started\ndata: {json.dumps(image_start_data)}\n\n"
                        image_generation_notified = True
                
                else:
                    # No streaming data yet, send basic status
                    status_data = {
                        "status": "in_progress" if overall_status in ["running", "processing"] else overall_status,
                        "progress": overall_progress,
                        "phase": "starting",
                        "content_words": 0,
                        "is_streaming": False,
                        "blog_id": blog_id
                    }
                    yield f"event: status\ndata: {json.dumps(status_data)}\n\n"
                
                # Check if generation is completed
                if overall_status == "completed":
                    final_word_count = streaming_data.get("final_word_count", 0) or task_info.get("word_count", 0)
                    final_data = {
                        "status": "completed",
                        "success": True,
                        "final_word_count": final_word_count,
                        "progress": 100,
                        "blog_id": blog_id,
                        "message": "Blog generation completed successfully"
                    }
                    
                    # 🎨 ADD IMAGE GENERATION STATUS to final completion if available
                    if "featured_image" in task_info:
                        img_data = task_info["featured_image"]
                        final_data["featured_image"] = {
                            "status": img_data.get("status", "unknown"),
                            "task_id": img_data.get("task_id"),
                            "started_at": img_data.get("started_at"),
                            "message": "Image generation may still be in progress" if img_data.get("status") == "generating" else f"Image generation {img_data.get('status', 'unknown')}"
                        }
                        
                        # Try to get current image status
                        try:
                            from app.tasks.featured_image_generation import get_featured_image_status_by_blog_id
                            img_status = get_featured_image_status_by_blog_id(blog_id)
                            if img_status and img_status.get("status") != "not_found":
                                final_data["featured_image"]["current_status"] = img_status.get("status")
                                final_data["featured_image"]["current_progress"] = img_status.get("progress", 0)
                                if img_status.get("status") == "completed" and img_status.get("result"):
                                    final_data["featured_image"]["image_url"] = img_status.get("result", {}).get("public_url")
                                    final_data["featured_image"]["image_id"] = img_status.get("result", {}).get("image_id")
                        except Exception as img_final_error:
                            logger.warning(f"Failed to get final image status: {str(img_final_error)}")
                    
                    yield f"event: final\ndata: {json.dumps(final_data)}\n\n"
                    break
                
                # Check if generation failed
                if overall_status == "failed":
                    error_message = task_info.get("error", "Unknown error occurred")
                    error_data = {
                        "status": "failed",
                        "success": False,
                        "message": error_message,
                        "blog_id": blog_id
                    }
                    yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
                    break
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error in streaming: {e}")
                continue
            except Exception as e:
                logger.error(f"Error in streaming loop: {e}")
                error_data = {
                    "message": f"Streaming error: {str(e)}",
                    "blog_id": blog_id
                }
                yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
                break
            
            await asyncio.sleep(check_interval)
        
        # Timeout reached
        if time.time() - stream_start_time >= timeout_seconds:
            timeout_data = {
                "message": "Stream timeout reached",
                "blog_id": blog_id,
                "timeout_seconds": timeout_seconds
            }
            yield f"event: timeout\ndata: {json.dumps(timeout_data)}\n\n"
    
    except Exception as e:
        logger.error(f"Critical error in SSE generator: {e}")
        error_data = {
            "message": f"Critical streaming error: {str(e)}",
            "blog_id": blog_id
        }
        yield f"event: error\ndata: {json.dumps(error_data)}\n\n"

# Removed custom OPTIONS handler - FastAPI CORS middleware handles this automatically

@router.get("/stream/{blog_id}")
async def stream_blog_generation(
    request: Request,
    blog_id: str
):
    """
    Server-Sent Events endpoint for real-time blog generation streaming
    
    Args:
        request: FastAPI Request object
        blog_id: Blog document ID
        
    Returns:
        StreamingResponse with Server-Sent Events
    """
    try:
        # Verify authentication using the same pattern as other endpoints
        auth_result = verify_token_sync(request)
        if not auth_result:
            # Return error as SSE event
            async def auth_error():
                error_data = {
                    "error": "authentication_failed",
                    "message": "Invalid or missing authentication token"
                }
                yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
            
            return StreamingResponse(
                auth_error(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Cache-Control",
                    "X-Accel-Buffering": "no",
                    "Transfer-Encoding": "chunked",
                    "Keep-Alive": "timeout=300, max=1000"
                }
            )
        
        logger.info(f"Starting SSE stream for blog_id: {blog_id}")
        
        return StreamingResponse(
            generate_sse_events(blog_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
                "Transfer-Encoding": "chunked",  # Enable chunked encoding
                "Keep-Alive": "timeout=300, max=1000"  # 5 minute timeout
            }
        )
        
    except Exception as e:
        logger.error(f"Error starting SSE stream: {str(e)}", exc_info=True)
        
        # Return error as SSE stream
        async def error_stream():
            error_data = {
                "error": "stream_start_failed",
                "message": f"Failed to start stream: {str(e)}"
            }
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
        
        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache", 
                "Expires": "0",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
                "X-Accel-Buffering": "no",
                "Transfer-Encoding": "chunked", 
                "Keep-Alive": "timeout=300, max=1000"
            }
        )

@router.get("/debug/{blog_id}")
async def debug_blog_streaming_data(
    request: Request,
    blog_id: str
):
    """
    Debug endpoint to inspect current streaming data
    """
    try:
        # Verify authentication
        auth_result = verify_token_sync(request)
        if not auth_result:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token"
            )
        
        # 🔍 SMART REDIS KEY DETECTION FOR DEBUG - Try both key patterns
        redis_key_pro = f"blog_generation_task:{blog_id}"
        redis_key_free = f"blog_generation_task:{blog_id}"  # Same pattern for now
        
        task_data = redis_client.get(redis_key_pro)
        redis_key = redis_key_pro
        
        if not task_data:
            # Try FREE key as fallback
            task_data = redis_client.get(redis_key_free)
            redis_key = redis_key_free
        
        if not task_data:
            return {
                "error": "No streaming data found for this blog_id",
                "blog_id": blog_id,
                "redis_key": redis_key
            }
        
        task_info = json.loads(task_data)
        streaming_data = task_info.get("steps", {}).get("blog_generation", {}).get("streaming_data", {})
        
        # Calculate metrics for debugging
        content_words = len(streaming_data.get("live_content", "").split()) if streaming_data.get("live_content") else 0
        thinking_words = len(streaming_data.get("live_thinking", "").split()) if streaming_data.get("live_thinking") else 0
        
        debug_info = {
            "blog_id": blog_id,
            "status": task_info.get("status", "unknown"),
            "overall_progress": task_info.get("steps", {}).get("blog_generation", {}).get("progress", 0),
            "is_streaming": streaming_data.get("is_streaming", False),
            "current_phase": streaming_data.get("phase", "unknown"),
            "live_word_count": content_words,
            "thinking_word_count": thinking_words,  # NEW: thinking word count for debug
            "thinking_active": streaming_data.get("thinking_active", False),  # NEW: thinking status
            "content_active": streaming_data.get("content_active", True),     # NEW: content status
            "last_updated": streaming_data.get("last_updated"),
            "raw_data": task_info
        }
        
        return debug_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in debug endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Debug error: {str(e)}"
        )