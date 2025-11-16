from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.db.session import get_db_session
from app.middleware.auth_middleware import verify_request_origin_sync
from app.models.project import Project
from typing import Dict, Any, List, Optional
from app.core.logging_config import logger
from pydantic import BaseModel
from app.services.normal_category_selection import CategorySelectionService
from app.services.balance_validator import BalanceValidator
from app.services.mongodb_service import MongoDBService
from app.utils.api_utils import APIUtils
from bson import ObjectId
import pytz
from datetime import datetime, timezone
router = APIRouter()

class SecondaryKeywordsData(BaseModel):
    keywords: List[Dict[str, Any]]

class SecondaryKeywordsSelectionRequest(BaseModel):
    secondary_keywords: SecondaryKeywordsData


@router.put("/{blog_id}")
def update_categories_raw(
    request: Request,
    *,
    blog_id: str,
    body: Dict[str, Any],
    current_user = Depends(verify_request_origin_sync)
) -> Dict[str, Any]:
    """
    Add raw categories data to existing categories.generated array.
    Optimized for speed - minimal processing.
    """
    project_id = request.path_params.get("project_id")
    categories = body.get("categories", [])
    
    try:
        current_user_id = current_user.user.id
        
        # Fast validation
        APIUtils.validate_uuid(project_id)
        APIUtils.validate_objectid(blog_id)
        
        if not categories:
            raise HTTPException(status_code=400, detail="categories array required")
        
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
                "categories": 1,
                "country": 1,
                "intent": 1
            }
        )
        
        if not blog_doc:
            raise HTTPException(status_code=404, detail="Blog not found")
        
        # Quick validation - check if categories array exists
        existing_categories = blog_doc.get("categories", [])
        if not existing_categories:
            raise HTTPException(status_code=400, detail="No existing categories found")
        
        # Minimal data preparation
        current_time = datetime.now(timezone.utc)
        
        # Extract selected category and subcategory from payload
        selected_category = None
        selected_subcategory = None
        category_found = False
        
        for category in categories:
            if category.get("selected"):
                selected_category = category.get("category")
                category_found = True
                
                # Look for selected subcategory
                subcategory_found = False
                for subcategory in category.get("subcategories", []):
                    if isinstance(subcategory, dict) and subcategory.get("selected"):
                        selected_subcategory = subcategory.get("name")
                        subcategory_found = True
                        break
                
                # If category is selected but no subcategory is selected, explicitly set subcategory to null
                if not subcategory_found:
                    selected_subcategory = None
                break
        
        # Update the latest existing categories entry (not create new one)
        latest_index = len(existing_categories) - 1  # Index of latest entry
        update_operations = {
            "$set": {
                f"categories.{latest_index}.categories": categories,  # Update categories with selections
                f"categories.{latest_index}.last_updated_at": current_time,  # Track when updated
                "updated_at": current_time
            }
        }
        
        # Update root level category/subcategory
        if category_found:
            update_operations["$set"]["category"] = selected_category
            # Always update subcategory - either to the selected value or null
            update_operations["$set"]["subcategory"] = selected_subcategory
        
        mongodb_service.get_sync_db()['blogs'].update_one(
            {"_id": ObjectId(blog_id)},
            update_operations
        )
        
        # Minimal response
        return {
            "status": "updated",
            "categories": categories,
            "selected_category": selected_category,
            "selected_subcategory": selected_subcategory,
            "blog_id": blog_id
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{blog_id}")
def generate_categories(
    request: Request,
    *,
    blog_id: str,
    secondary_keywords_request: SecondaryKeywordsSelectionRequest,
    current_user = Depends(verify_request_origin_sync)
) -> Dict[str, Any]:
    """
    Generate content categories and finalize secondary keywords selection.
    
    Args:
        blog_id: MongoDB blog document ID
        secondary_keywords_request: Request containing selected secondary keywords with full data
    """
    project_id = request.path_params.get("project_id")
    
    try:
        # Get user ID and verify project access
        current_user_id = current_user.user.id
        
        # Validate project_id and blog_id formats first
        APIUtils.validate_uuid(project_id)
        APIUtils.validate_objectid(blog_id)
        
        # First verify project access
        with get_db_session() as db:
            project = APIUtils.verify_project_access(project_id, current_user_id, db)
        
        # Get blog data from MongoDB to extract keywords and intent
        mongodb_service = MongoDBService()
        mongodb_service.init_sync_db()
        
        # Find the blog document
        blog_doc = APIUtils.get_mongodb_blog_document(
            mongodb_service, blog_id, project_id, current_user_id
        )
        
        # Extract primary keyword from array (latest)
        primary_keyword_array = blog_doc.get("primary_keyword", [])
        if not primary_keyword_array:
            raise HTTPException(
                status_code=400,
                detail="No primary keyword found. Please complete previous steps first."
            )
        
        latest_primary = primary_keyword_array[-1]  # Get latest primary keyword
        primary_keyword = latest_primary.get("keyword")
        
        # Extract country and intent from root level in MongoDB
        country = blog_doc.get("country", "in")
        intent = blog_doc.get("intent", "")
        
        # Extract secondary keywords from array (latest) - just for validation
        secondary_keywords_array = blog_doc.get("secondary_keywords", [])
        if not secondary_keywords_array:
            raise HTTPException(
                status_code=400,
                detail="No secondary keywords found. Please generate secondary keywords first."
            )
        
        # Get ALL keywords from payload (for saving to MongoDB)
        all_secondary_keywords = secondary_keywords_request.secondary_keywords.keywords
        
        # Get ONLY selected keywords for AI processing
        selected_keywords_for_ai = [kw for kw in all_secondary_keywords if kw.get("selected", False)]
        secondary_keywords_list = [kw.get("keyword") for kw in selected_keywords_for_ai]
        
        # Validate that at least one keyword is selected for AI processing
        if not selected_keywords_for_ai:
            raise HTTPException(
                status_code=400,
                detail="No secondary keywords selected. Please select at least one keyword."
            )
        
        
        # Now proceed with balance validation
        with get_db_session() as db:
            # 🚀 FAST BALANCE VALIDATION - Check balance BEFORE processing
            balance_validator = BalanceValidator(db)
            balance_check = balance_validator.validate_service_balance(
                user_id=current_user_id,
                service_key="category_selection"
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
            
            
            # Create and execute the category generation service
            service = CategorySelectionService(db=db, user_id=current_user_id, project_id=project_id)
            result = service.generate_category_selection_workflow(
                primary_keyword=primary_keyword,
                secondary_keywords=secondary_keywords_list,
                intent=intent,
                project_id=project_id
            )
        
        # Update MongoDB with category results and step tracking
        current_time = datetime.now(timezone.utc)
        
        # Prepare category data for storage
        category_data = {
            "categories": result.get("categories", []),
            "generated_at": current_time,
            "primary_keyword": primary_keyword,
            "secondary_keywords": secondary_keywords_list,
            "intent": intent,
            "country": country,
            "tag": "generated"
        }
        
        # Prepare step tracking data for category generation
        category_step_tracking_generated = {
            "step": "category",
            "status": "generated",
            "completed_at": current_time
        }
        
        # Prepare secondary keywords data for finalization (save ALL keywords from payload)
        secondary_keywords_final_data = {
            "keywords": all_secondary_keywords,  # Save ALL keywords from payload
            "finalized_at": current_time,
            "primary_keyword": primary_keyword,
            "intent": intent,
            "country": country,
            "tag": "final"
        }
        
        # Prepare step tracking data for secondary keywords completion
        secondary_step_tracking_data = {
            "step": "secondary_keywords",
            "status": "done",
            "completed_at": current_time
        }
        
        # Check if step_tracking exists, if not initialize it
        existing_step_tracking = blog_doc.get("step_tracking")
        if not existing_step_tracking:
            # Initialize step tracking structure
            step_tracking_structure = {
                "current_step": "category",
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
                    "secondary_keywords": secondary_keywords_final_data,
                    "categories": category_data,
                    "step_tracking.secondary_keywords": secondary_step_tracking_data,
                    "step_tracking.category": category_step_tracking_generated
                },
                "$set": {
                    "step_tracking.current_step": "category",
                    "updated_at": current_time
                }
            }
        )
        

        # Get the latest secondary keywords from array for response
        secondary_keywords_array = blog_doc.get("secondary_keywords", [])
        latest_secondary_final = None
        if secondary_keywords_array:
            latest_secondary_final = secondary_keywords_array[-1]  # Get latest secondary keywords
        
        return {
            "status": "success",
            "categories": result.get("categories", []),
            "primary_keyword": latest_primary,
            "secondary_keywords": latest_secondary_final.get("keywords", []) if latest_secondary_final else [],
            "blog_id": blog_id,
            "country": country,
            "intent": intent,
            "message": "Categories generated successfully"
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error generating categories: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error generating categories: {str(e)}"
        )


class LatestCategoriesResponse(BaseModel):
    categories: Optional[List[Dict[str, Any]]] = None
    primary_keyword: Optional[Dict[str, Any]] = None
    secondary_keywords: Optional[List[Dict[str, Any]]] = None
    status: str
    country: Optional[str] = None
    error: Optional[str] = None
    blog_id: str

@router.get("/{blog_id}")
def get_latest_categories_data(
    request: Request,
    *,
    blog_id: str,
    current_user = Depends(verify_request_origin_sync)
) -> LatestCategoriesResponse:
    """
    Get the latest categories data from a blog's final array.
    
    Args:
        blog_id: MongoDB blog document ID
        
    Returns:
        Latest categories data with blog information
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
            "categories": 1,
            "primary_keyword": 1,
            "secondary_keywords": 1,
            "country": 1,
            "_id": 1
        }
        blog_doc = APIUtils.get_mongodb_blog_document(
            mongodb_service, blog_id, project_id, current_user_id, projection
        )
        
        # Get categories data from simple array
        categories_array = blog_doc.get("categories", [])
        country = blog_doc.get("country", "in")
        
        # Get the latest categories (last item in array)
        categories_data = None
        if categories_array:
            latest_entry = categories_array[-1]  # Last item = latest
            categories_data = latest_entry.get("categories", [])
        
        # Get the latest primary keyword from array
        primary_keyword_array = blog_doc.get("primary_keyword", [])
        latest_primary_final = None
        if primary_keyword_array:
            latest_primary_final = primary_keyword_array[-1]  # Get latest primary keyword
        
        # Get the latest secondary keywords from array
        secondary_keywords_array = blog_doc.get("secondary_keywords", [])
        latest_secondary_keywords = []
        if secondary_keywords_array:
            latest_secondary_final = secondary_keywords_array[-1]  # Get latest secondary keywords
            latest_secondary_keywords = latest_secondary_final.get("keywords", [])
        
        response = LatestCategoriesResponse(
            categories=categories_data,
            primary_keyword=latest_primary_final,
            secondary_keywords=latest_secondary_keywords,
            status="success" if categories_data else "no_data",
            country=country,
            error=None,
            blog_id=blog_id
        )
        
        return response
        
    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    except Exception as e:
        logger.error(f"Error fetching latest categories: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

