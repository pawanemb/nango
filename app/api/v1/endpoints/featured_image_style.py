from fastapi import APIRouter, Depends, HTTPException, Request
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.schemas.featured_image_style import (
    StoreFeaturedImageStyleRequest, 
    StoreFeaturedImageStyleResponse, 
    FetchFeaturedImageStyleResponse,
    FeaturedImageStyleOptionsResponse
)
from app.services.featured_image_style_service import FeaturedImageStyleService
from app.db.session import get_db_session
from app.core.logging_config import logger
from sqlalchemy.orm import Session

router = APIRouter()

@router.post(
    "/projects/{project_id}/store",
    response_model=StoreFeaturedImageStyleResponse,
    summary="Store Featured Image Style",
    description="Store the selected featured image style for a project in the database"
)
def store_featured_image_style(
    project_id: str,
    style_request: StoreFeaturedImageStyleRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Store featured image style for a project.
    
    This endpoint stores the user's selected featured image style for a specific project
    in the database for future retrieval and use in content generation.
    """
    # 🔄 PERSISTENT RETRY MECHANISM - Keep trying until success
    retry_count = 0
    max_attempts = 50  # Safety limit to prevent infinite loops
    
    while retry_count < max_attempts:
        try:
            logger.info(f"🖼️ Storing featured image style '{style_request.style}' for project {project_id} by user {current_user.id} (Attempt {retry_count + 1})")
            
            with get_db_session() as db:
                # 🎯 SINGLE TRANSACTION PATTERN (like /create endpoint)
                
                # 1. Get project
                from app.models.project import Project
                project = db.query(Project).filter(Project.id == project_id).first()
                
                if not project:
                    logger.error(f"❌ Project {project_id} not found")
                    raise HTTPException(
                        status_code=404, 
                        detail="Project not found"
                    )
                
                # 2. Validate style input
                if not style_request.style or not style_request.style.strip():
                    logger.error("❌ Featured image style cannot be empty")
                    raise HTTPException(
                        status_code=400, 
                        detail="Featured image style cannot be empty"
                    )
                
                # 3. 🔥 DO BOTH UPDATES IN SINGLE TRANSACTION
                project.featured_image_style = style_request.style.strip()
                project.is_active = True  # Activate project (final step)
                
                # 4. 🎯 SINGLE COMMIT (all or nothing - like /create)
                db.commit()
                db.refresh(project)
                
                # 5. 🛡️ VERIFY UPDATES ACTUALLY APPLIED (CONFIRMATION CHECK)
                verification_project = db.query(Project).filter(Project.id == project_id).first()
                
                if not verification_project:
                    logger.error(f"❌ VERIFICATION FAILED: Project {project_id} not found after commit")
                    raise Exception("Database verification failed - project not found")
                
                if verification_project.featured_image_style != style_request.style.strip():
                    logger.error(f"❌ VERIFICATION FAILED: featured_image_style not saved. Expected: '{style_request.style.strip()}', Got: '{verification_project.featured_image_style}'")
                    raise Exception("Database verification failed - featured image style not saved")
                
                if verification_project.is_active != True:
                    logger.error(f"❌ VERIFICATION FAILED: is_active not set. Expected: True, Got: {verification_project.is_active}")
                    raise Exception("Database verification failed - project not activated")
                
                logger.info(f"✅ VERIFIED: Both featured_image_style='{verification_project.featured_image_style}' and is_active={verification_project.is_active} confirmed in database")
                
                # 🎉 SUCCESS! Return response
                return StoreFeaturedImageStyleResponse(
                    status="success",
                    message="Featured image style stored successfully and project activated",
                    project_id=project_id,
                    featured_image_style=verification_project.featured_image_style
                )
                
        except HTTPException:
            # Don't retry HTTP errors (404, 400, etc.)
            raise
        except Exception as e:
            retry_count += 1
            logger.warning(f"⚠️ Attempt {retry_count} failed: {str(e)}")
            logger.info(f"🔄 Retrying until success... (Next attempt: {retry_count + 1})")
            
            import time
            time.sleep(0.5)  # Pause before retry to avoid overwhelming database
    
    # 🚨 Safety fallback if all attempts failed
    logger.error(f"❌ CRITICAL: Failed to store featured image style after {max_attempts} attempts")
    raise HTTPException(
        status_code=500, 
        detail=f"Critical database error: Failed to store featured image style after {max_attempts} persistent attempts"
    )

@router.get(
    "/projects/{project_id}/fetch",
    response_model=FetchFeaturedImageStyleResponse,
    summary="Fetch Featured Image Style",
    description="Fetch the stored featured image style for a project from the database"
)
def fetch_featured_image_style(
    project_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Fetch featured image style for a project.
    
    This endpoint retrieves the stored featured image style for a specific project
    from the database. Returns null if no style has been stored yet.
    """
    try:
        logger.info(f"🖼️ Fetching featured image style for project {project_id} by user {current_user.id}")
        
        with get_db_session() as db:
            # Create featured image style service
            style_service = FeaturedImageStyleService(
                db=db, 
                user_id=str(current_user.id), 
                project_id=project_id
            )
            
            # Fetch featured image style
            result = style_service.fetch_featured_image_style(project_id)
            
            if result.get("status") == "success":
                logger.info(f"✅ Featured image style fetched successfully for project {project_id}")
                
                return FetchFeaturedImageStyleResponse(
                    status="success",
                    message=result.get("message", "Featured image style retrieved successfully"),
                    project_id=project_id,
                    featured_image_style=result.get("featured_image_style")
                )
            else:
                logger.error(f"❌ Failed to fetch featured image style: {result.get('message')}")
                raise HTTPException(
                    status_code=404 if "not found" in result.get("message", "").lower() else 400, 
                    detail=result.get("message", "Failed to fetch featured image style")
                )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in fetch featured image style endpoint: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to fetch featured image style: {str(e)}"
        )

@router.get(
    "/style-options",
    summary="Get Featured Image Style Options",
    description="Get all available featured image style options"
)
def get_featured_image_style_options():
    """
    Get all available featured image style options.
    
    This endpoint returns the complete list of available featured image styles
    with their descriptions and characteristics.
    """
    try:
        logger.info("🖼️ Fetching available featured image style options")
        
        # Create a temporary service instance to get options
        with get_db_session() as db:
            style_service = FeaturedImageStyleService(db=db, user_id="", project_id="")
            result = style_service.get_available_styles()
            
            if result.get("status") == "success":
                logger.info(f"✅ Successfully retrieved {len(result['style_options'])} featured image style options")
                
                return FeaturedImageStyleOptionsResponse(
                    status="success",
                    message=result.get("message", "Featured image style options retrieved successfully"),
                    style_options=result["style_options"]
                )
            else:
                logger.error(f"❌ Failed to get featured image style options: {result.get('message')}")
                raise HTTPException(
                    status_code=500, 
                    detail=result.get("message", "Failed to get featured image style options")
                )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting featured image style options: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to get featured image style options: {str(e)}"
        )
