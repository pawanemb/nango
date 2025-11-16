from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.schemas.keyword_suggestions import (
    KeywordSuggestionsRequest,
    KeywordSuggestionsResponse
)
from app.tasks.keyword_suggestions import create_keyword_suggestions_chain
from app.core.logging_config import logger
from celery.result import AsyncResult
from datetime import datetime
from app.models.project import Project
from app.services.mongodb_service import MongoDBService
from app.middleware.auth_middleware import verify_request_origin_sync, verify_token
from uuid import UUID
from app.services.normal_keyword_suggestions_sync import KeywordSuggestionServiceSync

from app.db.session import get_db_session

router = APIRouter()

@router.post("/generate", response_model=dict)
async def generate_keyword_suggestions(
    request: Request,
    *,
    current_user = Depends(verify_request_origin_sync),
    data: KeywordSuggestionsRequest = None
) -> Any:
    """
    Generate keyword suggestions using ChatGPT and fetch their metrics.
    This is an async task that will be processed in the background.
    Requires authentication and project access.
    """
    try:
        # Get project_id from path parameters
        project_id = request.path_params.get("project_id")
        logger.info(f"Generating keyword suggestions for project_id: {project_id}")
        
        if not project_id:
            raise HTTPException(
                status_code=400,
                detail="Project ID is required"
            )
            
        # Get project data first to verify ownership
        with get_db_session() as db:
            project = db.query(Project).filter(Project.id == project_id).first()
            
            if not project:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project {project_id} not found"
                )
            
            # Verify project ownership
            if str(project.user_id) != str(current_user.user.id):
                raise HTTPException(
                    status_code=403,
                    detail="You don't have access to this project"
                )
            
            # Get scraped content from MongoDB
            mongodb_service = MongoDBService()
            scraped_content = mongodb_service.get_content_by_url(
                project_id=project.id,
                url=project.url
            )
            if not scraped_content:
                raise HTTPException(
                    status_code=404,
                    detail=f"No scraped content found for project {project_id}"
                )
                
            # Get project data
            services = project.services or []
            business_type = project.business_type or "Others"
            locations = []  # TODO: Add locations to project model if needed
            target_audience = scraped_content.demographics if scraped_content.demographics else {}
            homepage_content = scraped_content.html_content
            
            # Since industries are no longer used, provide a default value
            industry = "General"
            
            # Format target audience from demographics
            target_audience_str = ""
            if target_audience:
                audience_parts = []
                if "Age" in target_audience:
                    audience_parts.append(f"Age: {', '.join(target_audience['Age'])}")
                if "Industry" in target_audience:
                    audience_parts.append(f"Industry: {', '.join(target_audience['Industry'])}")
                if "Gender" in target_audience:
                    audience_parts.append(f"Gender: {', '.join(target_audience['Gender'])}")
                if "Language(s) Spoken" in target_audience:
                    audience_parts.append(f"Languages: {', '.join(target_audience['Language(s) Spoken'])}")
                if "Country" in target_audience:
                    audience_parts.append(f"Countries: {', '.join(target_audience['Country'])}")
                    # Also use countries as locations
                    locations = target_audience["Country"]
                    
                target_audience_str = ". ".join(audience_parts)

            # Validate required data
            if not services:
                raise HTTPException(
                    status_code=400,
                    detail="No services found for the project"
                )
                
            if not business_type:
                raise HTTPException(
                    status_code=400,
                    detail="Business type not found"
                )
                
            if not homepage_content:
                raise HTTPException(
                    status_code=400,
                    detail="No homepage content found"
                )

        # Create and execute the task chain
        try:
            # Initialize service with token tracking parameters
            service = KeywordSuggestionServiceSync(
                db=db,
                user_id=str(current_user.user.id),
                project_id=str(project_id)
            )
            result = service.generate_keyword_suggestions(
                services=services,
                business_type=business_type,
                locations=locations,
                target_audience=target_audience_str,
                homepage_content=homepage_content,
                industry=industry,
                country=data.country if data and data.country else "in"  # Use default if no data provided
            )
            
            return {
                "status": "success",
                "message": "Keywords generated successfully",
                "results": result
            }
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Error in keyword suggestion service: {str(e)}\nTraceback:\n{error_trace}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate keyword suggestions: {str(e)}"
            )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Error in keyword suggestions endpoint: {str(e)}\nTraceback:\n{error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process request: {str(e)}"
        )
    finally:
        logger.info("Completed generate keyword suggestions request")

@router.get("/status/{task_id}", response_model=dict)
async def get_task_status(
    request: Request,
    task_id: str,
    current_user = Depends(verify_request_origin_sync)
) -> dict:
    """
    Get the status of a keyword suggestions task.
    """
    try:
        # Get project_id from path parameters
        project_id = request.query_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID is required")
        
        # Get project data
        with get_db_session() as db:
            project = db.query(Project).filter(Project.id == project_id).first()
            
            if not project:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project {project_id} not found"
                )
            
            # Verify project ownership
            if str(project.user_id) != str(current_user.user.id):
                raise HTTPException(
                    status_code=403,
                    detail="You don't have access to this project"
                )
            
        # Get task result
        result = AsyncResult(task_id)
        
        if result.ready():
            if result.successful():
                return {
                    "status": "completed",
                    "result": result.get()
                }
            else:
                return {
                    "status": "failed",
                    "error": str(result.result)
                }
        else:
            return {
                "status": "pending",
                "message": "Task is still processing"
            }
            
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error checking task status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
