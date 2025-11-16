from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.db.session import get_db_session
from app.middleware.auth_middleware import verify_request_origin_sync
from app.models.project import Project
from typing import Dict, Any, List, Optional
from app.core.logging_config import logger
from app.services.normal_secondary_keywords import SecondaryKeywordsService
from app.services.balance_validator import BalanceValidator
from pydantic import BaseModel
from app.services.mongodb_service import MongoDBService
from app.utils.api_utils import APIUtils
from bson import ObjectId
import pytz
from datetime import datetime, timezone

router = APIRouter()


class PrimaryKeywordData(BaseModel):
    keyword: str
    intent: str
    search_volume: int
    keyword_difficulty: float

class SecondaryKeywordsRequest(BaseModel):
    primary_keyword: PrimaryKeywordData

class ManualKeywordsRequest(BaseModel):
    keywords: List[str]


@router.put("/{blog_id}")
def update_secondary_keywords_raw(
    request: Request,
    *,
    blog_id: str,
    body: Dict[str, Any],
    current_user = Depends(verify_request_origin_sync)
) -> Dict[str, Any]:
    """
    Add raw secondary keywords data to existing secondary_keywords.generated array.
    Optimized for speed - minimal processing.
    """
    project_id = request.path_params.get("project_id")
    secondary_keywords = body.get("secondary_keywords", [])
    
    try:
        current_user_id = current_user.user.id
        
        # Fast validation
        APIUtils.validate_uuid(project_id)
        APIUtils.validate_objectid(blog_id)
        
        if not secondary_keywords:
            raise HTTPException(status_code=400, detail="secondary_keywords array required")
        
        # Single MongoDB connection
        mongodb_service = MongoDBService()
        mongodb_service.init_sync_db()
        
        # Fast document check with minimal projection
        blog_doc = mongodb_service.get_sync_db()['blogs'].find_one(
            {
                "_id": ObjectId(blog_id),
                "project_id": project_id,
                "user_id": current_user_id
            },
            {
                "secondary_keywords": 1,
                "country": 1,
                "intent": 1
            }
        )
        
        if not blog_doc:
            raise HTTPException(status_code=404, detail="Blog not found")
        
        # Quick validation - check if secondary keywords array exists
        if not blog_doc.get("secondary_keywords"):
            raise HTTPException(status_code=400, detail="No existing secondary keywords found")
        
        # Minimal data preparation
        current_time = datetime.now(timezone.utc)
        
        secondary_keywords_data = {
            "keywords": secondary_keywords,
            "tag": "updated",
            "generated_at": current_time
        }
        
        # Fast append - direct array push
        mongodb_service.get_sync_db()['blogs'].update_one(
            {"_id": ObjectId(blog_id)},
            {
                "$push": {"secondary_keywords": secondary_keywords_data},
                "$set": {"updated_at": current_time}
            }
        )
        
        # Minimal response
        return {
            "status": "updated",
            "secondary_keywords": secondary_keywords,
            "blog_id": blog_id
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating secondary keywords: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{blog_id}")
def generate_secondary_keywords(
    request: Request,
    *,
    blog_id: str,
    keywords_request: SecondaryKeywordsRequest,
    current_user = Depends(verify_request_origin_sync)
) -> Dict[str, Any]:
    """
    Generate secondary keywords for a given primary keyword.
    
    Args:
        blog_id: MongoDB blog document ID
        keywords_request: Request body containing complete primary_keyword object
    """
    # Extract primary keyword data from request body
    primary_keyword_data = keywords_request.primary_keyword
    primary_keyword = primary_keyword_data.keyword
    primary_intent = primary_keyword_data.intent
    primary_search_volume = primary_keyword_data.search_volume
    primary_difficulty = primary_keyword_data.keyword_difficulty
    
    project_id = request.path_params.get("project_id")
    
    try:
        # Get user ID and verify project access
        current_user_id = current_user.user.id
        
        # Validate project_id and blog_id formats first
        APIUtils.validate_uuid(project_id)
        APIUtils.validate_objectid(blog_id)
        
        # Then verify project access
        with get_db_session() as db:
            project = APIUtils.verify_project_access(project_id, current_user_id, db)
            
            if not project:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project {project_id} not found"
                )
        
        # Get blog data from MongoDB to extract country and intent
        mongodb_service = MongoDBService()
        mongodb_service.init_sync_db()
        
        # Find the blog document
        blog_doc = mongodb_service.get_sync_db()['blogs'].find_one({
            "_id": ObjectId(blog_id),
            "project_id": project_id,
            "user_id": current_user_id
        })
        
        if not blog_doc:
            raise HTTPException(
                status_code=404, 
                detail=f"Blog {blog_id} not found or access denied"
            )
        
        # Extract country from blog document, use intent from payload
        country = blog_doc.get("country", "in")
        intent = primary_intent  # Use intent from primary keyword payload
        
        # Note: This endpoint serves dual purpose - finalizes primary keyword AND generates secondary keywords
        # No validation needed here as this endpoint handles the primary keyword finalization
        
        # Now proceed with balance validation
        with get_db_session() as db:
            # 🚀 FAST BALANCE VALIDATION - Check balance BEFORE processing
            balance_validator = BalanceValidator(db)
            balance_check = balance_validator.validate_service_balance(
                user_id=current_user_id,
                service_key="secondary_keywords"
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
            
            
            # Now run the service with proper parameters
            service = SecondaryKeywordsService(db=db, user_id=current_user_id, project_id=project_id)
            result = service.generate_secondary_keywords_workflow(
                primary_keyword=primary_keyword,
                project_id=project_id,
                country=country,
                intent=intent
            )
        
        # Update MongoDB with secondary keywords results
        current_time = datetime.now(timezone.utc)
        
        secondary_keywords_data = {
            "keywords": result["keywords"],
            "tag": "generated",
            "generated_at": current_time
        }
        
        # Prepare step tracking data for secondary keywords generation
        secondary_step_tracking_generated = {
            "step": "secondary_keywords",
            "status": "generated",
            "completed_at": current_time
        }
        
        # Prepare primary keyword data for finalization
        primary_keyword_final_data = {
            "keyword": primary_keyword,
            "intent": primary_intent,
            "search_volume": primary_search_volume,
            "difficulty": primary_difficulty,
            "country": country,
            "tag": "final",
            "finalized_at": current_time
        }
        
        # Prepare step tracking data
        primary_step_tracking_data = {
            "step": "primary_keyword",
            "status": "done",
            "completed_at": current_time
        }
        
        # Initialize step_tracking if missing
        existing_step_tracking = blog_doc.get("step_tracking")
        if not existing_step_tracking:
            step_tracking_structure = {
                "current_step": "secondary_keywords",
                "primary_keyword": [],
                "secondary_keywords": [],
                "category": [],
                "title": [],
                "outline": [],
                "sources": []
            }
            mongodb_service.get_sync_db()['blogs'].update_one(
                {"_id": ObjectId(blog_id)},
                {"$set": {"step_tracking": step_tracking_structure}}
            )
        
        # Simple update - push to direct arrays
        update_result = mongodb_service.get_sync_db()['blogs'].update_one(
            {"_id": ObjectId(blog_id)},
            {
                "$push": {
                    "secondary_keywords": secondary_keywords_data,
                    "primary_keyword": primary_keyword_final_data,
                    "step_tracking.primary_keyword": primary_step_tracking_data,
                    "step_tracking.secondary_keywords": secondary_step_tracking_generated
                },
                "$set": {
                    "step_tracking.current_step": "secondary_keywords",
                    "is_active": True,
                    "updated_at": current_time
                }
            }
        )
        
        
        # Return the finalized primary keyword data we just created
        return {
            "status": "success",
            "secondary_keywords": result.get("keywords", []),
            "primary_keyword": primary_keyword_final_data,
            "blog_id": blog_id,
            "country": country,
            "intent": intent,
            "message": "Secondary keywords generated successfully"
        }
            
    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    
    except Exception as e:
        logger.error(f"Error generating secondary keywords: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.post("/manual/{blog_id}")
def analyze_manual_keywords(
    request: Request,
    *,
    blog_id: str,
    body: ManualKeywordsRequest,
    current_user = Depends(verify_request_origin_sync)
) -> Dict[str, Any]:
    """
    Analyze provided keywords manually without AI generation.
    Fetches metrics and intent analysis for the given keywords.
    
    Args:
        blog_id: MongoDB blog document ID  
        body: Request body containing keywords list
    """
    project_id = request.path_params.get("project_id")
    keywords = body.keywords
    
    try:
        # Get user ID and verify project access
        current_user_id = current_user.user.id
        
        # Validate project_id and blog_id formats first
        APIUtils.validate_uuid(project_id)
        APIUtils.validate_objectid(blog_id)
        
        # Verify project access
        with get_db_session() as db:
            project = APIUtils.verify_project_access(project_id, current_user_id, db)
            
            if not project:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project {project_id} not found"
                )
        
        # Verify blog exists
        mongodb_service = MongoDBService()
        mongodb_service.init_sync_db()
        
        blog_doc = APIUtils.get_mongodb_blog_document(
            mongodb_service, blog_id, project_id, current_user_id
        )
        
        # Extract country from blog document
        country = blog_doc.get("country", "in")
        
        # Get project data first to verify ownership
        with get_db_session() as db:
            # 🚀 FAST BALANCE VALIDATION - Check balance BEFORE processing
            balance_validator = BalanceValidator(db)
            balance_check = balance_validator.validate_service_balance(
                user_id=current_user_id,
                service_key="secondary_keywords_manual"
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
            
            
            # Validate keywords input
            if not keywords or len(keywords) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Keywords list cannot be empty"
                )
            
            # Filter and clean keywords
            clean_keywords = [kw.strip() for kw in keywords if kw.strip()]
            if len(clean_keywords) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="No valid keywords provided after cleaning"
                )
            
            # Limit to maximum 20 keywords
            if len(clean_keywords) > 20:
                clean_keywords = clean_keywords[:20]
            
            # Initialize service and run manual analysis workflow with billing
            service = SecondaryKeywordsService(db=db, user_id=current_user_id, project_id=project_id)
            
            # Run complete manual analysis workflow with billing
            processed_results = service.manual_keywords_analysis_workflow(
                keywords=clean_keywords,
                project_id=project_id,
                country=country
            )
            
            # Update MongoDB with manual analysis results
            current_time = datetime.now(timezone.utc)
            
            # Check if secondary_keywords array exists
            existing_secondary = blog_doc.get("secondary_keywords", [])
            
            if not existing_secondary:
                raise HTTPException(
                    status_code=400,
                    detail="No existing secondary keywords found. Please generate secondary keywords first."
                )
            
            # Prepare manual keywords with tag for adding to existing array
            manual_keywords = []
            for keyword in processed_results["keywords"]:
                manual_keyword = {
                    **keyword,
                    "tag": "manual"
                }
                manual_keywords.append(manual_keyword)
            
            # Add manual keywords to the latest existing secondary keywords entry
            latest_index = len(existing_secondary) - 1  # Index of latest entry
            update_result = mongodb_service.get_sync_db()['blogs'].update_one(
                {"_id": ObjectId(blog_id)},
                {
                    "$push": {
                        f"secondary_keywords.{latest_index}.keywords": {"$each": manual_keywords}
                    },
                    "$set": {"updated_at": current_time}
                }
            )
            
            
            return APIUtils.create_minimal_response(
                status="success",
                data={
                    "keywords": processed_results["keywords"],
                    "total_keywords": len(processed_results["keywords"]),
                    "analyzed_at": processed_results["generated_at"],
                    "country": country,
                    "analysis_type": "manual",
                    "blog_id": blog_id
                },
                message="Manual keyword analysis completed successfully"
            )
            
    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    
    except Exception as e:
        logger.error(f"Error in manual keyword analysis: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


class LatestSecondaryKeywordsResponse(BaseModel):
    secondary_keywords: Optional[List[Dict[str, Any]]] = None
    primary_keyword: Optional[Dict[str, Any]] = None
    status: str
    country: Optional[str] = None
    error: Optional[str] = None
    blog_id: str

@router.get("/{blog_id}")
def get_latest_secondary_keywords_data(
    request: Request,
    *,
    blog_id: str,
    current_user = Depends(verify_request_origin_sync)
) -> LatestSecondaryKeywordsResponse:
    """
    Get the latest secondary keywords data from a blog's final array.
    
    Args:
        blog_id: MongoDB blog document ID
        
    Returns:
        Latest secondary keywords data with blog information
    """
    try:
        # Get project_id from path parameters
        project_id = request.path_params.get("project_id")
        
        # Validate UUID and ObjectId formats
        APIUtils.validate_uuid(project_id)
        APIUtils.validate_objectid(blog_id)
        
        # Get user ID
        current_user_id = current_user.user.id
        
        # Verify project exists and access
        with get_db_session() as db:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            project = APIUtils.verify_project_access(project_id, current_user_id, db)
        
        # Get blog data from MongoDB
        mongodb_service = MongoDBService()
        mongodb_service.init_sync_db()
        
        # Find the blog document with projection for performance
        projection = {
            "secondary_keywords": 1,
            "primary_keyword": 1,
            "country": 1,
            "_id": 1
        }
        blog_doc = APIUtils.get_mongodb_blog_document(
            mongodb_service, blog_id, project_id, current_user_id, projection
        )
        
        
        # Get secondary keyword data from simple array
        secondary_keywords_array = blog_doc.get("secondary_keywords", [])
        country = blog_doc.get("country", "in")
        
        # Get the latest secondary keywords (last item in array)
        secondary_keywords_data = None
        if secondary_keywords_array:
            latest_secondary = secondary_keywords_array[-1]  # Last item = latest
            secondary_keywords_data = latest_secondary.get("keywords", [])
        
        # Get the latest primary keyword from simple array
        primary_keywords_array = blog_doc.get("primary_keyword", [])
        latest_primary_final = None
        if primary_keywords_array:
            latest_primary_final = primary_keywords_array[-1]  # Get latest primary keyword
        
        response = LatestSecondaryKeywordsResponse(
            secondary_keywords=secondary_keywords_data,
            primary_keyword=latest_primary_final,
            status="success" if secondary_keywords_data else "no_data",
            country=country,
            error=None,
            blog_id=blog_id
        )
        
        return response
        
    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    except Exception as e:
        logger.error(f"Error fetching latest secondary keywords: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


