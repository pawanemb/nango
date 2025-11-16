from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.db.session import get_db_session
from app.schemas.project import (
    ProjectCreate, 
    ProjectResponse, 
    ProjectListResponse,
    ProjectUpdate,
    ProjectUpdateResponse,
    UpdateServicesRequest,
    UpdateTargetAudienceRequest,
    UpdateFeatureImageActiveRequest,
    TogglePinnedRequest
)
from app.models.project import Project
from app.core.auth import supabase
from app.middleware.auth_middleware import verify_token, verify_request_origin, verify_request_origin_sync
import uuid
from sqlalchemy import func
import logging
from app.services.scraping_service import ScrapingService
from app.services.fast_scraping_service import create_fast_scraping_service_compat
import json
from app.services.mongodb_service import MongoDBService
from app.core.redis_client import get_redis_client
import hashlib
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

logger = logging.getLogger("fastapi_app")

# Import Enhanced Scraping Service
try:
    from app.services.enhanced_scraping_service import create_enhanced_scraping_service_compat
    ENHANCED_SCRAPING_AVAILABLE = True
    logger.info("✅ Enhanced Scraping Service available in projects endpoint")
except ImportError as e:
    create_enhanced_scraping_service_compat = None
    ENHANCED_SCRAPING_AVAILABLE = False
    logger.warning(f"⚠️ Enhanced Scraping Service not available in projects endpoint: {e}")

router = APIRouter()

def invalidate_projects_cache(user_id: str) -> None:
    """
    Invalidate the projects list cache for a specific user.
    Called when projects are created, updated, or deleted.
    
    Args:
        user_id: The user ID whose cache should be invalidated
    """
    try:
        redis_client = get_redis_client()
        if redis_client:
            cache_key = f"projects_list:{user_id}"
            result = redis_client.delete(cache_key)
            if result:
                logger.info(f"🗑️ Cache invalidated for user {user_id}: {cache_key}")
            else:
                logger.info(f"📭 No cache found to invalidate for user {user_id}")
        else:
            logger.warning("⚠️ Redis client not available for cache invalidation")
    except Exception as e:
        logger.error(f"❌ Failed to invalidate cache for user {user_id}: {str(e)}")

def get_cache_stats() -> dict:
    """
    Get cache statistics for monitoring.
    
    Returns:
        dict: Cache statistics including hit rate, memory usage, etc.
    """
    try:
        redis_client = get_redis_client()
        if redis_client:
            info = redis_client.info()
            return {
                "redis_connected": True,
                "used_memory": info.get("used_memory_human", "N/A"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": round(
                    info.get("keyspace_hits", 0) / 
                    max(info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0), 1) * 100, 
                    2
                )
            }
        else:
            return {"redis_connected": False, "error": "Redis client not available"}
    except Exception as e:
        return {"redis_connected": False, "error": str(e)}

def check_project_creation_permission(user_id: str, db) -> dict:
    """
    Check if user can create a new project based on their plan.
    
    Free Plan: Maximum 1 active project
    Pro Plan: Unlimited projects
    
    Returns:
        dict: Permission status and details
    """
    from app.models.account import Account
    from datetime import datetime
    import pytz
    
    # Get user's account
    account = db.query(Account).filter(Account.user_id == user_id).first()
    
    if not account:
        # Create account if it doesn't exist (default to free)
        account = Account(
            user_id=user_id,
            plan_type="free",
            currency="USD",
            credits=0.0
        )
        db.add(account)
        db.flush()
    
    # Check plan type and status
    plan_type = account.plan_type or "free"
    plan_status = account.plan_status or "inactive"
    
    # Pro plan check
    if plan_type == "pro":
        # Check if plan is active and not expired
        ist = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(ist)
        
        # Check plan status
        if plan_status not in ["active"]:
            return {
                "allowed": False,
                "reason": "pro_plan_inactive",
                "message": "Your Pro plan is not active. Please renew your subscription.",
                "current_plan": plan_type,
                "plan_status": plan_status,
                "upgrade_url": "https://app.rayo.work/upgrade"
            }
        
        # Check expiration
        if account.plan_end_date and account.plan_end_date < current_time:
            return {
                "allowed": False,
                "reason": "pro_plan_expired",
                "message": "Your Pro plan has expired. Please renew to create unlimited projects.",
                "current_plan": plan_type,
                "plan_status": "expired",
                "upgrade_url": "https://app.rayo.work/upgrade"
            }
        
        # Pro plan is active - unlimited projects
        return {
            "allowed": True,
            "reason": "pro_plan_active",
            "message": "Pro plan active - unlimited projects",
            "current_plan": plan_type,
            "plan_status": plan_status,
            "project_limit": "unlimited"
        }
    
    # Free plan check
    else:
        # Count active projects for free users
        active_projects_count = db.query(Project).filter(
            Project.user_id == user_id,
            Project.is_active == True
        ).count()
        
        if active_projects_count >= 1:
            return {
                "allowed": False,
                "reason": "free_plan_limit_reached",
                "message": "Free plan allows only 1 active project. Upgrade to Pro for unlimited projects.",
                "current_plan": plan_type,
                "active_projects": active_projects_count,
                "project_limit": 1,
                "upgrade_url": "https://app.rayo.work/upgrade"
            }
        
        return {
            "allowed": True,
            "reason": "free_plan_within_limit",
            "message": "Free plan - 1 project allowed",
            "current_plan": plan_type,
            "active_projects": active_projects_count,
            "project_limit": 1
        }

@router.get("/creation-permissions")
def check_project_creation_permissions(
    request: Request,
    *,
    current_user = Depends(verify_request_origin_sync)
) -> Any:
    """
    Check if the current user can create a new project based on their plan.
    Useful for frontend to show/hide create project button or show upgrade prompts.
    """
    try:
        with get_db_session() as db:
            permission_check = check_project_creation_permission(str(current_user.user.id), db)
            
            return {
                "success": True,
                "can_create_project": permission_check["allowed"],
                "reason": permission_check["reason"],
                "message": permission_check["message"],
                "plan_details": {
                    "current_plan": permission_check["current_plan"],
                    "plan_status": permission_check.get("plan_status"),
                    "project_limit": permission_check.get("project_limit"),
                    "active_projects": permission_check.get("active_projects"),
                    "upgrade_url": permission_check.get("upgrade_url")
                }
            }
    
    except Exception as e:
        logger.error(f"Error checking project creation permissions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check permissions: {str(e)}"
        )

@router.post("/create", response_model=dict)
def create_project(
    request: Request,
    *,
    project_in: ProjectCreate,
    current_user = Depends(verify_request_origin_sync)
) -> Any:
    """
    Create a new project and initiate website scraping using async service.
    Requires a valid Supabase token and authorized origin.
    Handles token refresh if refresh token is provided.
    
    Plan Restrictions:
    - Free Plan: Maximum 1 active project
    - Pro Plan: Unlimited projects (active subscription required)
    """
    logger.info(f"🎯 [CREATE_PROJECT] Starting project creation process")
    logger.info(f"📝 [CREATE_PROJECT] Input data - Name: {project_in.name}, URL: {project_in.url}")
    logger.info(f"👤 [CREATE_PROJECT] User ID: {current_user.user.id}")
    
    try:
        logger.info(f"🔌 [CREATE_PROJECT] Opening database session")
        with get_db_session() as db:
            logger.info(f"✅ [CREATE_PROJECT] Database session opened successfully")
            
            # 🛡️ CHECK PROJECT CREATION PERMISSIONS
            logger.info(f"🛡️ [CREATE_PROJECT] Checking project creation permissions")
            permission_check = check_project_creation_permission(str(current_user.user.id), db)
            
            if not permission_check["allowed"]:
                logger.warning(f"❌ [CREATE_PROJECT] Permission denied: {permission_check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "Project creation not allowed",
                        "reason": permission_check["reason"],
                        "message": permission_check["message"],
                        "current_plan": permission_check["current_plan"],
                        "project_limit": permission_check.get("project_limit"),
                        "active_projects": permission_check.get("active_projects"),
                        "plan_status": permission_check.get("plan_status"),
                        "upgrade_url": permission_check.get("upgrade_url", "https://app.rayo.work/upgrade")
                    }
                )
            
            logger.info(f"✅ [CREATE_PROJECT] Permission granted: {permission_check['reason']}")
            logger.info(f"📊 [CREATE_PROJECT] Plan details: {permission_check['current_plan']} - {permission_check['message']}")
            
            project_uuid = uuid.uuid4()
            logger.info(f"🆔 [CREATE_PROJECT] Generated project UUID: {project_uuid}")
            
            logger.info(f"🏗️ [CREATE_PROJECT] Creating Project object")
            project = Project(
                id=project_uuid,
                name=project_in.name,
                url=project_in.url,
                user_id=current_user.user.id,
                services=[],
                is_active=False  # Start as inactive until scraping succeeds
            )
            logger.info(f"✅ [CREATE_PROJECT] Project object created successfully")
            
            logger.info(f"💾 [CREATE_PROJECT] Adding project to database session")
            db.add(project)
            logger.info(f"✅ [CREATE_PROJECT] Project added to session")
            
            logger.info(f"💾 [CREATE_PROJECT] Committing project to database")
            db.commit()
            logger.info(f"✅ [CREATE_PROJECT] Project committed successfully")
            
            logger.info(f"🔄 [CREATE_PROJECT] Refreshing project from database")
            db.refresh(project)
            logger.info(f"✅ [CREATE_PROJECT] Project refreshed - ID: {project.id}")

            logger.info(f"🚀 [CREATE_PROJECT] Starting scraping process")
            try:
                logger.info(f"📋 [CREATE_PROJECT] Scraping params - URL: {project_in.url}, Project ID: {project.id}, User ID: {current_user.user.id}")
                
                # Use Enhanced Scraping Service if available, otherwise fallback to Fast Scraping
                if ENHANCED_SCRAPING_AVAILABLE and create_enhanced_scraping_service_compat:
                    logger.info(f"🪄 [CREATE_PROJECT] Creating Enhanced Scraping Service instance")
                    scraping_service = create_enhanced_scraping_service_compat(user_id=current_user.user.id)
                    logger.info(f"✅ [CREATE_PROJECT] Enhanced Scraping Service created successfully")
                else:
                    logger.info(f"🔧 [CREATE_PROJECT] Creating FastScrapingService instance (fallback)")
                    scraping_service = create_fast_scraping_service_compat(user_id=current_user.user.id)
                    logger.info(f"✅ [CREATE_PROJECT] FastScrapingService created successfully")
                
                logger.info(f"🏁 [CREATE_PROJECT] Calling start_scraping_process...")
                scraping_result = scraping_service.start_scraping_process(
                    url=project_in.url, 
                    project_id=project.id
                )
                logger.info(f"🏁 [CREATE_PROJECT] start_scraping_process completed")
                logger.info(f"📊 [CREATE_PROJECT] Scraping result status: {scraping_result.get('status')}")
                logger.info(f"🔍 [CREATE_PROJECT] Full scraping result: {scraping_result}")
                
                logger.info(f"📦 [CREATE_PROJECT] Creating project response data")
                project_data = json.loads(ProjectResponse.from_orm(project).json())
                logger.info(f"✅ [CREATE_PROJECT] Project response data created")
                
                # Log performance information if available
                scraper_type = scraping_result.get("scraper_type", "Unknown")
                strategy_used = scraping_result.get("strategy_used", "unknown")
                content_format = scraping_result.get("content_format", "unknown")
                
                logger.info(f"🔧 [CREATE_PROJECT] Scraper type used: {scraper_type}")
                logger.info(f"🎯 [CREATE_PROJECT] Strategy used: {strategy_used}")
                logger.info(f"📄 [CREATE_PROJECT] Content format: {content_format}")
                
                if scraper_type == "MagicScraper":
                    logger.info(f"🪄 [CREATE_PROJECT] MagicScraper: Enhanced scraping used with {strategy_used}")
                elif scraper_type == "Enhanced":
                    logger.info(f"🚀 [CREATE_PROJECT] Enhanced Scraper: Advanced scraping used")
                elif scraper_type == "FastAsyncScraper":
                    logger.info(f"⚡ [CREATE_PROJECT] FastAsyncScraper: Fallback scraping used")
                
                logger.info(f"🔄 [CREATE_PROJECT] Processing scraping result based on status")
                
                if scraping_result["status"] == "completed":
                    logger.info(f"✅ [CREATE_PROJECT] Scraping completed successfully")
                    
                    services = scraping_result.get('services', [])
                    business_category = scraping_result.get('business_category', 'Unknown')
                    
                    logger.info(f"📊 [CREATE_PROJECT] Services found: {services}")
                    logger.info(f"🏢 [CREATE_PROJECT] Business category: {business_category}")
                    
                    logger.info(f"💾 [CREATE_PROJECT] Updating project in database with scraping results")
                    project.services = services
                    project.business_type = business_category
                    
                    logger.info(f"💾 [CREATE_PROJECT] Committing updated project to database")
                    db.commit()
                    logger.info(f"✅ [CREATE_PROJECT] Project committed successfully")
                    
                    logger.info(f"🔄 [CREATE_PROJECT] Refreshing updated project from database")
                    db.refresh(project)
                    logger.info(f"✅ [CREATE_PROJECT] Project refreshed successfully")
                    
                    logger.info(f"📦 [CREATE_PROJECT] Updating response data with scraping results")
                    # Build enhanced scraping metadata
                    enhanced_metadata = {
                        "scraper_type": scraping_result.get("scraper_type", "Unknown"),
                        "performance": scraping_result.get("performance", "standard"),
                        "scraping_status": "completed"
                    }
                    
                    # Add enhanced scraping specific metadata if available
                    if strategy_used != "unknown":
                        enhanced_metadata["strategy_used"] = strategy_used
                    if content_format != "unknown":
                        enhanced_metadata["content_format"] = content_format
                    
                    project_data.update({
                        "services": services,
                        "business_type": business_category,
                        "scraping_metadata": enhanced_metadata
                    })
                    logger.info(f"✅ [CREATE_PROJECT] Response data updated successfully")
                    
                elif scraping_result["status"] == "failed":
                    logger.error(f"❌ [CREATE_PROJECT] Scraping failed")
                    logger.error(f"❌ [CREATE_PROJECT] Error details: {scraping_result.get('error', 'Unknown error')}")
                    logger.error(f"❌ [CREATE_PROJECT] Current stage: {scraping_result.get('current_stage', 'Unknown')}")
                    
                    logger.error(f"🚨 [CREATE_PROJECT] Raising HTTPException for scraping failure")
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": scraping_result.get("error", "Project creation failed: Unable to scrape website data"),
                            "scraping_status": "failed",
                            "status": "failed"
                        }
                    )
                
                else:
                    logger.warning(f"⚠️ [CREATE_PROJECT] Unexpected scraping status: {scraping_result['status']}")
                    logger.warning(f"⚠️ [CREATE_PROJECT] Full result: {scraping_result}")
                
                logger.info(f"📤 [CREATE_PROJECT] Preparing final response")
                logger.info(f"📊 [CREATE_PROJECT] Final services: {project_data.get('services')}")
                logger.info(f"🏢 [CREATE_PROJECT] Final business_type: {project_data.get('business_type')}")
                logger.info(f"🔧 [CREATE_PROJECT] Final metadata: {project_data.get('scraping_metadata')}")
                
                logger.info(f"🗂️ [CREATE_PROJECT] Invalidating projects cache for user {current_user.user.id}")
                invalidate_projects_cache(str(current_user.user.id))
                logger.info(f"✅ [CREATE_PROJECT] Cache invalidated successfully")
                
                logger.info(f"🎉 [CREATE_PROJECT] Project creation completed successfully")
                return project_data
                
            except Exception as scraping_exception:
                logger.error(f"💥 [CREATE_PROJECT] Exception occurred in scraping process")
                logger.error(f"💥 [CREATE_PROJECT] Exception type: {type(scraping_exception).__name__}")
                logger.error(f"💥 [CREATE_PROJECT] Exception message: {str(scraping_exception)}")
                logger.error(f"💥 [CREATE_PROJECT] Exception details:", exc_info=True)
                
                logger.error(f"🚨 [CREATE_PROJECT] Raising HTTPException for scraping exception")
                raise HTTPException(
                    status_code=400,
                    detail={
                        "scraping_status": "failed",
                        "error": f"Failed to start scraping: {str(scraping_exception)}"
                    }
                )
                
    except Exception as outer_exception:
        logger.error(f"💥 [CREATE_PROJECT] Outer exception occurred")
        logger.error(f"💥 [CREATE_PROJECT] Outer exception type: {type(outer_exception).__name__}")
        logger.error(f"💥 [CREATE_PROJECT] Outer exception message: {str(outer_exception)}")
        logger.error(f"💥 [CREATE_PROJECT] Outer exception details:", exc_info=True)
        
        logger.error(f"🚨 [CREATE_PROJECT] Raising HTTPException for outer exception")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating project: Failed to scrap the website - {str(outer_exception)}"
        )
    finally:
        logger.info(f"📋 [CREATE_PROJECT] Create project endpoint execution completed")

@router.get("/list", response_model=list[ProjectListResponse])
def list_projects(
    request: Request,
    *,
    current_user = Depends(verify_request_origin_sync)
) -> Any:
    """
    Get all projects belonging to the current user.
    Requires a valid Supabase token.
    Implements Redis caching with 5-minute TTL for improved performance.
    """
    try:
        user_id = current_user.user.id
        logger.info(f"🔍 Listing projects for user: {user_id}")
        
        # Redis caching implementation
        redis_client = get_redis_client()
        cache_key = f"projects_list:{user_id}"
        cache_ttl = 300  # 5 minutes in seconds
        
        # Try to get cached data first
        if redis_client:
            try:
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    logger.info(f"📦 Cache HIT: Retrieved {user_id} projects from Redis cache")
                    cached_projects = json.loads(cached_data)
                    
                    # Add cache metadata to response headers
                    request.state.cache_status = "HIT"
                    request.state.cache_key = cache_key
                    
                    return cached_projects
                else:
                    logger.info(f"📭 Cache MISS: No cached data found for user {user_id}")
            except Exception as cache_error:
                logger.warning(f"⚠️ Redis cache read error: {str(cache_error)}")
        else:
            logger.warning("⚠️ Redis client not available, skipping cache")
        
        # Fetch from database if not cached
        logger.info(f"🗄️ Fetching projects from database for user: {user_id}")
        
        with get_db_session() as db:
            projects = db.query(Project).filter(
                Project.user_id == user_id, 
                Project.is_active == True
            ).all()
            
            project_count = len(projects)
            logger.info(f"📊 Retrieved {project_count} projects from database for user {user_id}")
            
            # Convert to response format
            project_responses = [ProjectListResponse.from_orm(project) for project in projects]
            
            # Serialize for caching (convert to JSON-serializable format)
            serialized_projects = []
            for project_response in project_responses:
                project_dict = project_response.model_dump()
                # Convert UUID and datetime objects to strings for JSON serialization
                for key, value in project_dict.items():
                    if isinstance(value, uuid.UUID):
                        project_dict[key] = str(value)
                    elif isinstance(value, datetime):
                        project_dict[key] = value.isoformat()
                serialized_projects.append(project_dict)
            
            # Cache the results in Redis
            if redis_client:
                try:
                    redis_client.setex(
                        cache_key, 
                        cache_ttl, 
                        json.dumps(serialized_projects, default=str)
                    )
                    logger.info(f"💾 Cached {project_count} projects for user {user_id} (TTL: {cache_ttl}s)")
                    
                    # Set cache metadata
                    request.state.cache_status = "MISS"
                    request.state.cache_key = cache_key
                    
                except Exception as cache_error:
                    logger.error(f"❌ Failed to cache projects data: {str(cache_error)}")
            
            return project_responses
            
    except Exception as e:
        logger.error(f"❌ Error listing projects for user {current_user.user.id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list projects: {str(e)}"
        )

@router.get("/has-created-any")
def check_user_has_created_any_project(
    request: Request,
    *,
    current_user = Depends(verify_request_origin_sync)
) -> Any:
    """
    Check if the user has created any project previously (active or inactive).
    
    This endpoint simply checks if there is any project entry in the database
    for the current user, regardless of the project's active status.
    Returns a boolean indicating whether the user has any project history.
    """
    try:
        user_id = current_user.user.id
        logger.info(f"🔍 Checking if user {user_id} has created any project previously")
        
        with get_db_session() as db:
            # Count all projects for this user (active and inactive)
            project_count = db.query(Project).filter(
                Project.user_id == user_id
            ).count()
            
            has_projects = project_count > 0
            
            logger.info(f"📊 User {user_id} has {project_count} total projects (active + inactive)")
            logger.info(f"✅ Result: has_created_any = {has_projects}")
            
            return {
                "has_created_any": has_projects,
                "total_projects_count": project_count,
                "user_id": user_id,
                "message": f"User has {'created projects previously' if has_projects else 'not created any projects yet'}"
            }
        
    except Exception as e:
        logger.error(f"❌ Error checking user project history: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check user project history: {str(e)}"
        )

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: uuid.UUID,
    request: Request,
    *,
    current_user = Depends(verify_request_origin_sync)
) -> Any:
    """
    Get details of a specific project by ID.
    Only the project owner can access the project detaels.
    
    Args:
        project_id: UUID of the project to retrieve
        request: FastAPI request object
        current_user: Authenticated user from verify_request_origin
        
    Returns:
        ProjectResponse: Project details including name, URL, services, etc.
        
    Raises:
        HTTPException: 404 if project not found or 403 if user doesn't have access
    """
    try:
        logger.info(f"Attempting to retrieve project {project_id} for user {current_user.user.id}")
        
        with get_db_session() as db:
            # Get the project from database
            project = db.query(Project).filter(Project.id == project_id, Project.is_active == True).first()
            
            if not project:
                logger.warning(f"Project {project_id} not found for user {current_user.user.id}")
                raise HTTPException(
                    status_code=404,
                    detail="Project not found"
                )
            
            # Verify project ownership
            if str(project.user_id) != str(current_user.user.id):
                logger.warning(f"Unauthorized access attempt to project {project_id} by user {current_user.user.id}")
                raise HTTPException(
                    status_code=403,
                    detail="You don't have permission to access this project"
                )
            
            logger.info(f"Successfully retrieved project {project_id} for user {current_user.user.id}")
            return ProjectResponse.from_orm(project)
    
    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    
    except Exception as e:
        logger.error(f"Unexpected error retrieving project {project_id} for user {current_user.user.id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.put("/{project_id}/services")
def update_project_services(
    project_id: uuid.UUID,
    request: Request,
    services_update: UpdateServicesRequest,
    current_user = Depends(verify_request_origin_sync)
) -> Any:
    """
    Update the services and business type of an existing project and analyze demographics.
    Only the project owner can update the services.
    """

    try:

        project = None
        with get_db_session() as db:
            project = db.query(Project).filter(Project.id == project_id).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")    
        
        # Log IDs for debugging
        logger.info(f"Project user_id::update_project_services: {project.user_id}")
        
        # Check if the current user owns the project
        if str(project.user_id) != str(current_user.user.id):
            raise HTTPException(
                status_code=403, 
                detail=f"Not authorized to update this project. Project owner: {project.user_id}, Current user: {current_user.user.id}"
            )
    
        # Get the website content from MongoDB
        mongodb_service = MongoDBService()
        content = mongodb_service.get_content_by_url(
            project_id=str(project_id),
            url=project.url
        )
        
        if not content:
            logger.error(f"No content found for project_id: {project_id}, url: {project.url}")
            raise HTTPException(
                status_code=404,
                detail="Website content not found. Please ensure website has been scraped."
            )
            
        # Reopen database connection for update
        with get_db_session() as db:
            # Fetch the project again to ensure we have a fresh instance
            project = db.query(Project).filter(Project.id == project_id).first()
            
            # Update project services and business type
            project.services = services_update.services
            if services_update.business_type:
                project.business_type = services_update.business_type
            project.updated_at = func.now()  # Update the timestamp
            db.commit()
            db.refresh(project)
        
        # Start demographic analysis using async function
        from app.services.normal_demographics import analyze_demographics
        
        logger.info(f"[DEMOGRAPHICS] Starting demographic analysis for project {project_id}")
        analysis_result = analyze_demographics(
            project_id=str(project_id),
            url=project.url,
            services=services_update.services,
            business_type=project.business_type or "Others",
            html_content=content.html_content,
            user_id=str(current_user.user.id)
        )
        
        logger.info(f"[DEMOGRAPHICS] Demographic analysis result: {analysis_result.get('status')}")
        
        # Update project with demographics results if analysis was successful
        if analysis_result.get("status") == "success" and analysis_result.get("demographics"):
            demographics = analysis_result["demographics"]
            logger.info(f"[SUCCESS] Demographics data: {list(demographics.keys()) if demographics else 'None'}")
            
            try:
                with get_db_session() as db:
                    project_to_update = db.query(Project).filter(Project.id == project_id).first()
                    if project_to_update:
                        # Extract demographic data with proper handling
                        age_groups = demographics.get("Age", []) or []
                        languages = demographics.get("Language(s) Spoken", []) or []
                        countries = demographics.get("Country", []) or []
                        gender_list = demographics.get("Gender", []) or []
                        
                        # Ensure arrays
                        if isinstance(age_groups, str):
                            age_groups = [age_groups]
                        if isinstance(languages, str):
                            languages = [languages]
                        if isinstance(countries, str):
                            countries = [countries]
                        
                        # Update project fields
                        project_to_update.age_groups = age_groups
                        project_to_update.languages = languages
                        project_to_update.locations = countries
                        
                        # Update gender
                        gender_mapping = {
                            "Male": "MALE", "Female": "FEMALE", 
                            "Non-binary": "OTHERS", "All": "OTHERS"
                        }
                        if gender_list and len(gender_list) > 0:
                            mapped_gender = gender_mapping.get(gender_list[0], "OTHERS")
                            project_to_update.gender = mapped_gender
                        
                        db.commit()
                        db.refresh(project_to_update)
                        
                        logger.info(f"[SUCCESS] Updated: ages={age_groups}, langs={languages}, locs={countries}")
                        
                        # Update the project variable for response
                        project = project_to_update
                    else:
                        logger.error(f"[DEMOGRAPHICS] Project not found: {project_id}")
            except Exception as e:
                logger.error(f"[DEMOGRAPHICS] Update error: {str(e)}")
        else:
            logger.warning(f"[DEMOGRAPHICS] Analysis failed: {analysis_result.get('error')}")
        
        # Create response data
        response_data = {
            "id": project.id,
            "name": project.name,
            "url": project.url,
            "industries": project.industries or [],
            "services": project.services,
            "created_at": project.created_at,
            "user_id": project.user_id,
            "brand_tone_settings": project.brand_tone_settings,
            "brand_name": project.brand_name,
            "visitors": project.visitors,
            "updated_at": project.updated_at,
            "gender": project.gender,
            "languages": project.languages,
            "age_groups": project.age_groups,
            "locations": project.locations,
            "business_type": project.business_type,
            "demographics": analysis_result.get("demographics"),
            "message": "Services updated successfully"
        }
        
        # Invalidate cache
        invalidate_projects_cache(str(current_user.user.id))
        
        return response_data
        
    except Exception as e:
        logger.error(f"Error updating services: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error updating services: {str(e)}"
        )
    finally:
        logger.info("Executed the update project services endpoint")

@router.put("/{project_id}/target-audience", response_model=dict)
def update_project_target_audience(
    project_id: uuid.UUID,
    request: Request,
    *,
    target_audience: UpdateTargetAudienceRequest,
    current_user = Depends(verify_request_origin_sync)
) -> Any:
    """
    Update the target audience of an existing project.
    Only the project owner can update the target audience.
    """
    try:
        # Get the project
        with get_db_session() as db:
            project = db.query(Project).filter(Project.id == project_id).first()
            
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            # Verify ownership
            if str(project.user_id) != str(current_user.user.id):
                raise HTTPException(status_code=403, detail="Not enough permissions")
            
            # Update target audience fields
            project.gender = target_audience.gender
            project.languages = target_audience.languages
            project.age_groups = target_audience.age_groups
            project.locations = target_audience.locations
            project.industries = target_audience.industries

            # Save changes
            db.commit()
            db.refresh(project)
            
            # Enhanced brand tone analysis using both services
            brand_tone_analysis = None
            try:
                # Get MongoDB content
                mongodb_service = MongoDBService()
                content = mongodb_service.get_content_by_url(
                    project_id=str(project_id),
                    url=project.url
                )
                
                if content and content.html_content:
                    # Initialize both services
                    from app.services.openai_service import OpenAIService
                    from app.services.brand_tone_service import BrandToneAnalysisService
                    
                    openai_service = OpenAIService(
                        db=db,
                        user_id=str(current_user.user.id),
                        project_id=str(project_id)
                    )
                    
                    brand_tone_service = BrandToneAnalysisService(
                        db=db,
                        user_id=str(current_user.user.id),
                        project_id=str(project_id)
                    )
                    
                    # Get original OpenAI analysis
                    openai_brand_tone = openai_service.get_brand_tone_lines(
                        html_content=content.html_content
                    )
                    logger.info(f"OpenAI brand tone analysis result: {openai_brand_tone}")
                    
                    # Get detailed brand tone analysis using BrandToneAnalysisService
                    # Extract text content from HTML for better analysis
                    import re
                    from bs4 import BeautifulSoup
                    
                    # Clean HTML and extract text
                    soup = BeautifulSoup(content.html_content, 'html.parser')
                    text_content = soup.get_text(separator=' ', strip=True)
                    # Limit to first 3000 characters for analysis
                    text_for_analysis = text_content[:3000] if len(text_content) > 3000 else text_content
                    
                    detailed_tone_analysis = brand_tone_service.analyze_brand_tone(text_for_analysis)
                    logger.info(f"Detailed brand tone analysis result: {detailed_tone_analysis}")
                    
                    # Combine both analyses
                    brand_tone_analysis = {
                        "status": "success",
                        "openai_analysis": openai_brand_tone,
                        "detailed_tone_analysis": detailed_tone_analysis,
                        "combined_result": {
                            "openai_brand_tone": openai_brand_tone,
                            "tone_dimensions": detailed_tone_analysis.get("tone_analysis", {}),
                            "analysis_status": detailed_tone_analysis.get("status", "unknown")
                        }
                    }
                    
                    # Store the detailed tone settings in the project if analysis was successful
                    if (detailed_tone_analysis.get("status") == "success" and 
                        detailed_tone_analysis.get("tone_analysis")):
                        
                        tone_analysis = detailed_tone_analysis["tone_analysis"]
                        
                        # Separate 4-axis tonality from person_tone if present
                        brand_tone_settings = {
                            key: value for key, value in tone_analysis.items() 
                            if key in ["formality", "attitude", "energy", "clarity"]
                        }
                        person_tone = tone_analysis.get("person_tone", None)
                        
                        store_result = brand_tone_service.store_brand_tone_settings(
                            project_id=str(project_id),
                            brand_tone_settings=brand_tone_settings,
                            person_tone=person_tone
                        )
                        logger.info(f"Brand tone storage result: {store_result}")
                        brand_tone_analysis["storage_result"] = store_result
                    
            except Exception as ai_error:
                logger.error(f"Brand tone analysis failed: {str(ai_error)}")
                brand_tone_analysis = {"status": "error", "error": "Brand tone analysis failed"}
            
            # Invalidate cache
            invalidate_projects_cache(str(current_user.user.id))
            
            # Return response with brand tone analysis
            response_data = ProjectResponse.from_orm(project)
            
            # Add brand tone analysis to response as dict
            response_dict = response_data.model_dump()
            if brand_tone_analysis:
                response_dict["brand_tone_analysis"] = brand_tone_analysis
            
            return response_dict
        
    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    
    except Exception as e:
        logger.error(f"Error updating project target audience: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{project_id}/update", response_model=ProjectUpdateResponse)
def update_project_details(
    project_id: uuid.UUID,
    request: Request,
    *,
    project_update: ProjectUpdate,
    current_user = Depends(verify_request_origin_sync)
) -> Any:
    """
    Update project details excluding id, name, url, and timestamps.
    Only the project owner can update the project details.
    """
    try:
        # Get the project
        with get_db_session() as db:
            project = db.query(Project).filter(Project.id == project_id, Project.is_active == True).first()
            
            if not project:
                raise HTTPException(
                    status_code=404,
                    detail="Project not found"
                )
            
            logger.info(f"Project user_id::update_project_details: {project.user_id} (type: {type(project.user_id)})")
            logger.info(f"Project current_user.id::update_project_details: {current_user.user.id} (type: {type(current_user.user.id)})")
            logger.info(f"Project user_id as string: {str(project.user_id)}")
            logger.info(f"Current user id as string: {str(current_user.user.id)}")
            
            # Verify ownership
            if str(project.user_id).lower() != str(current_user.user.id).lower():
                logger.error(f"Permission denied - user_id types: project={type(project.user_id)}, current={type(current_user.user.id)}")
                logger.error(f"Values do not match: project={str(project.user_id)}, current={str(current_user.user.id)}")
                raise HTTPException(
                    status_code=403,
                    detail="Not enough permissions to update this project"
                )

            try:
                # Update allowed fields
                update_data = project_update.model_dump(exclude_unset=True)
                
                # Handle brand_tone_settings specially if it contains person_tone
                if 'brand_tone_settings' in update_data and update_data['brand_tone_settings']:
                    brand_tone_data = update_data['brand_tone_settings']
                    
                    # Check if person_tone is included in brand_tone_settings
                    if 'person_tone' in brand_tone_data:
                        # Extract person_tone and store separately
                        person_tone = brand_tone_data.pop('person_tone')
                        project.person_tone = person_tone
                        logger.info(f"✅ Updated person_tone separately: {person_tone}")
                    
                    # Store the 4-axis brand tone settings in JSONB column
                    project.brand_tone_settings = brand_tone_data
                    logger.info(f"✅ Updated brand_tone_settings: {brand_tone_data}")
                    
                    # Remove from update_data to avoid double processing
                    update_data.pop('brand_tone_settings')
                
                # Update other allowed fields
                for field, value in update_data.items():
                    if field not in ['id', 'url', 'created_at', 'updated_at'] and value is not None:
                        setattr(project, field, value)
                        logger.info(f"✅ Updated {field}: {value}")

                db.add(project)
                db.commit()
                db.refresh(project)

                # Invalidate cache
                invalidate_projects_cache(str(current_user.user.id))
                
                return ProjectUpdateResponse(
                    id=project.id,
                    name=project.name,
                    url=project.url,
                    industries=project.industries,
                    services=project.services,
                    brand_tone_settings=project.brand_tone_settings,
                    brand_name=project.brand_name,
                    visitors=project.visitors,
                    business_type=project.business_type,
                    gender=project.gender,
                    languages=project.languages,
                    age_groups=project.age_groups,
                    locations=project.locations,
                    featured_image_style=project.featured_image_style,
                    person_tone=project.person_tone,  # ✅ Added missing field
                    feature_image_active=project.feature_image_active,
                    pinned=project.pinned,  # ✅ Added missing field
                    internal_linking_enabled=project.internal_linking_enabled,  # ✅ Added missing field
                    created_at=project.created_at,
                    updated_at=project.updated_at,
                    user_id=project.user_id,
                    message="Project updated successfully"
                )
            except Exception as db_error:
                db.rollback()
                logger.error(f"Database error while updating project: {str(db_error)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Database error while updating project: {str(db_error)}"
                )
        
    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    
    except Exception as e:
        logger.error(f"Error updating project details: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{project_id}/feature-image-active", response_model=dict)
def update_project_feature_image_active(
    project_id: uuid.UUID,
    request: Request,
    *,
    feature_image_request: UpdateFeatureImageActiveRequest,
    current_user = Depends(verify_request_origin_sync)
) -> Any:
    """
    Update the feature image active status of an existing project.
    Only the project owner can update the feature image active status.
    """
    try:
        logger.info(f"Updating feature image active status for project {project_id} by user {current_user.user.id}")
        
        # Get the project
        with get_db_session() as db:
            project = db.query(Project).filter(Project.id == project_id, Project.is_active == True).first()
            
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            # Verify ownership
            if str(project.user_id) != str(current_user.user.id):
                raise HTTPException(status_code=403, detail="Not enough permissions")
            
            # Update feature image active status
            project.feature_image_active = feature_image_request.feature_image_active
            project.updated_at = func.now()  # Update the timestamp
            
            # Save changes
            db.commit()
            db.refresh(project)
            
            logger.info(f"Feature image active status updated to {feature_image_request.feature_image_active} for project {project_id}")
            
            # Invalidate cache
            invalidate_projects_cache(str(current_user.user.id))
            
            # Return updated project response
            response_data = ProjectResponse.from_orm(project)
            response_dict = response_data.model_dump()
            response_dict["message"] = "Feature image active status updated successfully"
            
            return response_dict
        
    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    
    except Exception as e:
        logger.error(f"Error updating feature image active status: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_id}", response_model=dict)
async def delete_project(
    project_id: uuid.UUID,
    request: Request,
    *,
    current_user = Depends(verify_request_origin_sync),
) -> dict:
    """
    Soft delete a project by setting is_active=False.
    Only the project owner can delete the project.
    
    Args:
        project_id: UUID of the project to delete
        request: FastAPI request object
        current_user: Authenticated user from verify_request_origin
        db: Database session
        
    Returns:
        dict: Success message
        
    Raises:
        HTTPException: 404 if project not found or 403 if user doesn't have access
    """
    try:
        # Get user_id from current_user
        user_id = current_user.user.id
        project = None
        logger.info(f"Project user_id::delete_project: {user_id} (type: {type(user_id)})")
        
        # Get the project and update within the same session
        with get_db_session() as db:
            project = db.query(Project).filter(
                Project.id == project_id,
                Project.user_id == user_id,
                Project.is_active == True
            ).first()
            
            if not project:
                raise HTTPException(status_code=404, detail="Project not found or already deleted")
            
            # logger.info(f"Project before update: {project} {project.is_active}")
            
            # Soft delete the project
            project.is_active = False
            db.commit()
            
            #logger.info(f"Project after update: {project} {project.is_active}")
            
            # Invalidate cache
            invalidate_projects_cache(str(current_user.user.id))
            
            return {
                "message": "Project deleted successfully",
                "project_id": str(project_id)
            }

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error deleting project: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cache/stats")
def get_projects_cache_stats(
    request: Request,
    *,
    current_user = Depends(verify_request_origin_sync)
) -> Any:
    """
    Get cache statistics for projects list endpoint.
    Useful for monitoring cache performance and hit rates.
    """
    try:
        user_id = current_user.user.id
        cache_stats = get_cache_stats()
        
        # Add user-specific cache info
        redis_client = get_redis_client()
        user_cache_info = {"user_cache_exists": False, "user_cache_ttl": None}
        
        if redis_client:
            try:
                cache_key = f"projects_list:{user_id}"
                exists = redis_client.exists(cache_key)
                ttl = redis_client.ttl(cache_key) if exists else None
                
                user_cache_info = {
                    "user_cache_exists": bool(exists),
                    "user_cache_ttl": ttl,
                    "user_cache_key": cache_key
                }
            except Exception as e:
                logger.error(f"Error getting user cache info: {str(e)}")
        
        return {
            "cache_stats": cache_stats,
            "user_cache_info": user_cache_info,
            "user_id": user_id
        }
        
    except Exception as e:
        logger.error(f"Error getting cache stats: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get cache stats: {str(e)}"
        )

@router.delete("/cache/clear")
def clear_projects_cache(
    request: Request,
    *,
    current_user = Depends(verify_request_origin_sync)
) -> Any:
    """
    Clear the projects list cache for the current user.
    Useful for debugging or forcing cache refresh.
    """
    try:
        user_id = current_user.user.id
        invalidate_projects_cache(str(user_id))
        
        return {
            "message": "Projects cache cleared successfully",
            "user_id": user_id,
            "cache_key": f"projects_list:{user_id}"
        }
        
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear cache: {str(e)}"
        )

@router.patch("/{project_id}/toggle-pinned", response_model=ProjectResponse)
def toggle_project_pinned(
    project_id: uuid.UUID,
    request: Request,
    pinned_data: TogglePinnedRequest,
    current_user = Depends(verify_request_origin_sync)
) -> Any:
    """
    Toggle the pinned status of a project.
    Only the project owner can toggle the pinned status.
    
    Args:
        project_id: UUID of the project to toggle pinned status
        request: FastAPI request object
        pinned_data: TogglePinnedRequest containing the new pinned status
        current_user: Authenticated user from verify_request_origin
        
    Returns:
        ProjectResponse: Updated project details including the new pinned status
        
    Raises:
        HTTPException: 404 if project not found or 403 if user doesn't have access
    """
    try:
        logger.info(f"Toggling pinned status for project {project_id} to {pinned_data.pinned} for user {current_user.user.id}")
        
        with get_db_session() as db:
            # Get the project from database
            project = db.query(Project).filter(Project.id == project_id, Project.is_active == True).first()
            
            if not project:
                logger.warning(f"Project {project_id} not found for user {current_user.user.id}")
                raise HTTPException(
                    status_code=404,
                    detail="Project not found"
                )
            
            # Verify project ownership
            if str(project.user_id) != str(current_user.user.id):
                logger.warning(f"Unauthorized access attempt to project {project_id} by user {current_user.user.id}")
                raise HTTPException(
                    status_code=403,
                    detail="You don't have permission to access this project"
                )
            
            # Update the pinned status
            project.pinned = pinned_data.pinned
            db.commit()
            db.refresh(project)
            
            # Clear the user's projects cache to reflect the change
            try:
                invalidate_projects_cache(str(current_user.user.id))
                logger.info(f"Cache invalidated for user {current_user.user.id} after pinned status update")
            except Exception as cache_error:
                logger.warning(f"Failed to invalidate cache after pinned status update: {str(cache_error)}")
            
            logger.info(f"Successfully updated pinned status for project {project_id} to {pinned_data.pinned} for user {current_user.user.id}")
            return ProjectResponse.from_orm(project)
    
    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    
    except Exception as e:
        logger.error(f"Unexpected error toggling pinned status for project {project_id} for user {current_user.user.id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

