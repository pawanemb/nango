from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.db.session import get_db_session
from app.middleware.auth_middleware import verify_request_origin_sync
from app.models.project import Project
from typing import Dict, Any, List, Optional, Union
from app.core.logging_config import logger
from pydantic import BaseModel
from app.services.claude_outline_generation import ClaudeOutlineGenerationService
from app.services.balance_validator import BalanceValidator
from app.utils.api_utils import APIUtils
from app.services.mongodb_service import MongoDBService
from bson import ObjectId
import pytz
from datetime import datetime, timezone

router = APIRouter()

class OutlineGenerationRequest(BaseModel):
    titles: List[Union[str, Dict[str, Any]]]  # Mixed format: strings and objects with selected
    word_count: str

class OutlineResponse(BaseModel):
    status: str
    message: str
    data: dict

@router.put("/{blog_id}")
def update_outlines_raw(
    request: Request,
    *,
    blog_id: str,
    body: Dict[str, Any],
    current_user = Depends(verify_request_origin_sync)
) -> Dict[str, Any]:
    """
    Add raw outline data to existing outlines.generated array.
    Optimized for speed - minimal processing.
    """
    project_id = request.path_params.get("project_id")
    outline = body.get("outline", {})
    selected_title = body.get("selected_title", "")
    word_count = body.get("word_count", "")
    
    try:
        current_user_id = current_user.user.id
        
        # Fast validation
        APIUtils.validate_uuid(project_id)
        APIUtils.validate_objectid(blog_id)
        
        if not outline:
            raise HTTPException(status_code=400, detail="outline object required")
        
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
                "outlines": 1,
                "country": 1,
                "intent": 1
            }
        )
        
        if not blog_doc:
            raise HTTPException(status_code=404, detail="Blog not found")
        
        # Minimal data preparation
        current_time = datetime.now(timezone.utc)
        
        outline_update_data = {
            "outline": outline,
            "selected_title": selected_title,
            "word_count": word_count,
            "updated_at": current_time,
            "tag": "updated"
        }
        
        # Simple append to outlines array
        mongodb_service.get_sync_db()['blogs'].update_one(
            {"_id": ObjectId(blog_id)},
            {
                "$push": {"outlines": outline_update_data},
                "$set": {"updated_at": current_time}
            }
        )
        
        return {
            "status": "success",
            "message": "Outline updated successfully",
            "blog_id": blog_id,
            "updated_at": current_time,
            "operation": "fast_update"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating outline: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.post("/{blog_id}")
def generate_blog_outline(
    request: Request,
    *,
    blog_id: str,
    outline_request: OutlineGenerationRequest,
    current_user = Depends(verify_request_origin_sync)
) -> Dict[str, Any]:
    """
    Generate SEO-optimized blog outline based on MongoDB data and selected title.
    This is Step 5 of the blog generation workflow.
    
    Args:
        blog_id: MongoDB blog document ID
        outline_request: Request body containing:
            titles: List of titles with one marked as selected
            word_count: Target word count for the article
    """
    project_id = request.path_params.get("project_id")

    try:
        # Log incoming request details
        logger.info("=== CLAUDE OUTLINE GENERATION ENDPOINT START ===")
        logger.info(f"Project ID: {project_id}")
        logger.info(f"Blog ID: {blog_id}")
        logger.info(f"Request payload: {outline_request.dict()}")
        logger.info(f"Titles count: {len(outline_request.titles)}")
        logger.info(f"Word count: {outline_request.word_count}")
        
        # Get user ID from nested user object
        try:
            current_user_id = current_user.user.id
            logger.info(f"Current user ID: {current_user_id}")
        except Exception as user_error:
            logger.error(f"Failed to extract user ID: {user_error}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid user authentication: {str(user_error)}"
            )
        
        # Validate project_id and blog_id formats first
        logger.info(f"Validating project_id: {project_id}")
        try:
            APIUtils.validate_uuid(project_id)
            logger.info("✅ Project ID validation passed")
        except Exception as uuid_error:
            logger.error(f"❌ Project ID validation failed: {uuid_error}")
            raise
            
        logger.info(f"Validating blog_id: {blog_id}")
        try:
            APIUtils.validate_objectid(blog_id)
            logger.info("✅ Blog ID validation passed")
        except Exception as objectid_error:
            logger.error(f"❌ Blog ID validation failed: {objectid_error}")
            raise
        
        # Then verify project access
        logger.info("Verifying project access...")
        try:
            with get_db_session() as db:
                project = APIUtils.verify_project_access(project_id, current_user_id, db)
                logger.info("✅ Project access verification passed")
        except Exception as access_error:
            logger.error(f"❌ Project access verification failed: {access_error}")
            raise
        
        # Get blog data from MongoDB to extract all required data
        logger.info("Initializing MongoDB connection...")
        try:
            mongodb_service = MongoDBService()
            mongodb_service.init_sync_db()
            logger.info("✅ MongoDB connection initialized")
        except Exception as mongo_error:
            logger.error(f"❌ MongoDB initialization failed: {mongo_error}")
            raise
        
        # Find the blog document
        logger.info(f"Finding blog document for blog_id: {blog_id}")
        try:
            blog_doc = APIUtils.get_mongodb_blog_document(
                mongodb_service, blog_id, project_id, current_user_id
            )
            logger.info("✅ Blog document found")
            logger.info(f"Blog document keys: {list(blog_doc.keys())}")
        except Exception as blog_error:
            logger.error(f"❌ Blog document retrieval failed: {blog_error}")
            raise
        
        # Extract primary keyword from array (latest)
        logger.info("Extracting primary keyword from blog document...")
        primary_keyword_array = blog_doc.get("primary_keyword", [])
        logger.info(f"Primary keyword array length: {len(primary_keyword_array)}")
        
        if not primary_keyword_array:
            logger.error("❌ No primary keyword found")
            raise HTTPException(
                status_code=400,
                detail="No primary keyword found. Please complete the previous steps first."
            )
        
        latest_primary = primary_keyword_array[-1]
        primary_keyword = latest_primary.get("keyword")
        logger.info(f"✅ Primary keyword extracted: {primary_keyword}")
        
        # Extract secondary keywords from array (latest)
        secondary_keywords_array = blog_doc.get("secondary_keywords", [])
        if not secondary_keywords_array:
            raise HTTPException(
                status_code=400,
                detail="No secondary keywords found. Please complete the previous steps first."
            )
        
        latest_secondary = secondary_keywords_array[-1]
        # Get only selected secondary keywords
        all_secondary_keywords = latest_secondary.get("keywords", [])
        selected_secondary_keywords = [kw for kw in all_secondary_keywords if kw.get("selected", False)]
        secondary_keywords_list = [kw.get("keyword") for kw in selected_secondary_keywords]
        
        # Get category and subcategory from root level (simple values)
        selected_category = blog_doc.get("category")
        if not selected_category:
            raise HTTPException(
                status_code=400,
                detail="No category found. Please complete the previous steps first."
            )
        
        selected_subcategory = blog_doc.get("subcategory")
        if not selected_subcategory:
            raise HTTPException(
                status_code=400,
                detail="No subcategory found. Please complete the previous steps first."
            )
        
        logger.info(f"✅ Category from root level: {selected_category}")
        logger.info(f"✅ Subcategory from root level: {selected_subcategory}")
        
        # Extract country and intent from root level in MongoDB
        country = blog_doc.get("country", "us")
        intent = blog_doc.get("intent", "")
        
        # Extract selected title from payload
        logger.info("Extracting selected title from payload...")
        titles_array = outline_request.titles
        selected_title = None
        
        logger.info(f"Processing {len(titles_array)} titles from payload")
        
        # Find the selected title from the mixed format array in payload
        for i, title_item in enumerate(titles_array):
            logger.info(f"Title {i}: {type(title_item)} - {title_item}")
            if isinstance(title_item, dict) and title_item.get("selected", False):
                selected_title = title_item.get("title")
                logger.info(f"✅ Found selected title: {selected_title}")
                break
        
        if not selected_title:
            logger.error("❌ No selected title found in payload")
            logger.error(f"Titles array content: {titles_array}")
            raise HTTPException(
                status_code=400,
                detail="No selected title found in payload. Please select a title first."
            )
        
        with get_db_session() as db:
            # 🚀 FAST BALANCE VALIDATION - Check balance BEFORE processing
            balance_validator = BalanceValidator(db)
            balance_check = balance_validator.validate_service_balance(
                user_id=current_user_id,
                service_key="outline_generation"
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
                            "next_refill_time": balance_check.get("next_refill_time").isoformat() if balance_check.get("next_refill_time") else None
                        }
                    )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": balance_check["error"],
                            "message": balance_check["message"]
                        }
                    )
            

            # Save title selection to MongoDB first
            current_time = datetime.now(timezone.utc)
            
            # Prepare title finalization data - save ALL titles from payload
            title_final_data = {
                "titles": outline_request.titles,  # Save complete titles array from payload
                "selected_title": selected_title,  # Use extracted selected title
                "finalized_at": current_time,
                "primary_keyword": primary_keyword,
                "intent": intent,
                "country": country,
                "category": selected_category,
                "subcategory": selected_subcategory,
                "tag": "final"
            }
            
            # Prepare step tracking data for title completion
            title_step_tracking_data = {
                "step": "title",
                "status": "done",
                "completed_at": current_time
            }
            
            # Check if step_tracking exists, if not initialize it
            existing_step_tracking = blog_doc.get("step_tracking")
            if not existing_step_tracking:
                # Initialize step tracking structure
                step_tracking_structure = {
                    "current_step": "outline",
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
            
            # Check if root-level title is an array, if not convert it
            current_title = blog_doc.get("title")
            if current_title is not None and not isinstance(current_title, list):
                # Convert string title to array format
                mongodb_service.get_sync_db()['blogs'].update_one(
                    {"_id": ObjectId(blog_id)},
                    {"$set": {"title": [current_title] if current_title else []}}
                )
            elif current_title is None:
                # Initialize title as empty array
                mongodb_service.get_sync_db()['blogs'].update_one(
                    {"_id": ObjectId(blog_id)},
                    {"$set": {"title": []}}
                )
            
            # Check if root-level word_count is an array, if not convert it
            current_word_count = blog_doc.get("word_count")
            if current_word_count is not None and not isinstance(current_word_count, list):
                # Convert string/number word_count to array format
                mongodb_service.get_sync_db()['blogs'].update_one(
                    {"_id": ObjectId(blog_id)},
                    {"$set": {"word_count": [str(current_word_count)] if current_word_count else []}}
                )
            elif current_word_count is None:
                # Initialize word_count as empty array
                mongodb_service.get_sync_db()['blogs'].update_one(
                    {"_id": ObjectId(blog_id)},
                    {"$set": {"word_count": []}}
                )
            
            # Update MongoDB document with title finalization and step tracking
            mongodb_service.get_sync_db()['blogs'].update_one(
                {"_id": ObjectId(blog_id)},
                {
                    "$push": {
                        "titles": title_final_data,
                        "step_tracking.title": title_step_tracking_data,
                        "title": selected_title,  # Add selected title to root-level title array
                        "word_count": outline_request.word_count  # Add word count to root-level word_count array
                    },
                    "$set": {
                        "step_tracking.current_step": "outline",
                        "updated_at": current_time
                    }
                }
            )
            
            # Get updated document to fetch the latest title and word_count from root-level arrays
            updated_blog_doc = mongodb_service.get_sync_db()['blogs'].find_one(
                {"_id": ObjectId(blog_id)},
                {"title": 1, "word_count": 1}
            )
            latest_title_from_array = updated_blog_doc.get("title", [])[-1] if updated_blog_doc.get("title") else selected_title
            latest_word_count_from_array = updated_blog_doc.get("word_count", [])[-1] if updated_blog_doc.get("word_count") else outline_request.word_count
            
            # Now generate outline using Claude with all the extracted data
            service = ClaudeOutlineGenerationService(
                db=db,
                user_id=current_user_id,
                project_id=project_id
            )
            
            # Generate outline using Claude with MongoDB data
            result = service.generate_blog_outline_claude(
                blog_title=latest_title_from_array,  # Use latest title from root-level title array
                primary_keyword=primary_keyword,
                secondary_keywords=secondary_keywords_list,
                keyword_intent=intent,
                industry="",  # No industry from frontend, use empty string
                word_count=latest_word_count_from_array,  # Use latest word_count from root-level word_count array
                category=selected_category,
                country=country,
                subcategory=selected_subcategory,
                project_id=project_id,
                project=project.to_dict()
            )
            
            # Save generated outline to MongoDB
            outline_generated_data = {
                "outline": result.get("outline", {}),
                "generated_at": current_time,
                "selected_title": latest_title_from_array,  # Use latest title from root-level title array
                "word_count": latest_word_count_from_array,  # Use latest word_count from root-level word_count array
                "primary_keyword": primary_keyword,
                "intent": intent,
                "category": selected_category,
                "subcategory": selected_subcategory,
                "country": country,
                "secondary_keywords": secondary_keywords_list,
                "usage_stats": result.get("usage_stats", {}),
                "tag": "generated"
            }
            
            # Prepare step tracking data for outline generation
            outline_step_tracking_generated = {
                "step": "outline",
                "status": "generated",
                "completed_at": current_time
            }
            
            # Update MongoDB document with generated outline - simple array push
            mongodb_service.get_sync_db()['blogs'].update_one(
                {"_id": ObjectId(blog_id)},
                {
                    "$push": {
                        "outlines": outline_generated_data,
                        "step_tracking.outline": outline_step_tracking_generated
                    },
                    "$set": {
                        "step_tracking.current_step": "outline",
                        "updated_at": current_time
                    }
                }
            )
            
            # Get the latest secondary keywords from array for response
            secondary_keywords_array = blog_doc.get("secondary_keywords", [])
            latest_secondary_keywords = []
            if secondary_keywords_array:
                latest_secondary_final = secondary_keywords_array[-1]
                latest_secondary_keywords = latest_secondary_final.get("keywords", [])
            
            # Get the latest categories from array for response 
            categories_array = blog_doc.get("categories", [])
            latest_categories = []
            if categories_array:
                latest_categories_final = categories_array[-1]
                latest_categories = latest_categories_final.get("categories", [])
            
            # Get the latest titles from array for response
            titles_array = blog_doc.get("titles", [])
            latest_titles = []
            if titles_array:
                latest_titles_final = titles_array[-1]
                latest_titles = latest_titles_final.get("titles", [])
            
            return {
                "status": "success",
                "outline": result.get("outline", {}),
                "primary_keyword": latest_primary,
                "secondary_keywords": latest_secondary_keywords,
                "categories": latest_categories,
                "blog_id": blog_id,
                "country": country,
                "intent": intent,
                "selected_title": latest_title_from_array,
                "selected_category": selected_category,
                "selected_subcategory": selected_subcategory,
                "word_count": latest_word_count_from_array,
                "message": "Title finalized and outline generated successfully"
            }
        
    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    
    except Exception as e:
        logger.error(f"Error in outline generation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error in outline generation: {str(e)}"
        )


class LatestOutlineResponse(BaseModel):
    outline: Optional[Dict[str, Any]] = None
    primary_keyword: Optional[Dict[str, Any]] = None
    secondary_keywords: Optional[List[Dict[str, Any]]] = None
    categories: Optional[List[Dict[str, Any]]] = None
    titles: Optional[List[Union[str, Dict[str, Any]]]] = None  # ✅ Accept both strings and dicts
    word_count: Optional[str] = None
    status: str
    country: Optional[str] = None
    blog_id: str
    
@router.get("/{blog_id}")
def get_latest_outline_data(
    request: Request,
    *,
    blog_id: str,
    current_user = Depends(verify_request_origin_sync)
) -> LatestOutlineResponse:
    """
    Get the latest outline data from a blog's generated array.
    
    Args:
        blog_id: MongoDB blog document ID
        
    Returns:
        Latest outline data with blog information
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
            "outlines": 1,
            "primary_keyword": 1,
            "secondary_keywords": 1,
            "categories": 1,
            "titles": 1,
            "word_count": 1,
            "country": 1,
            "_id": 1
        }
        blog_doc = APIUtils.get_mongodb_blog_document(
            mongodb_service, blog_id, project_id, current_user_id, projection
        )
        
        # Get outline data from simple array
        outlines_array = blog_doc.get("outlines", [])
        country = blog_doc.get("country", "us")
        
        # Get the latest outline (last item in array)
        outline_data = None
        if outlines_array:
            latest_entry = outlines_array[-1]  # Last item = latest
            outline_data = latest_entry.get("outline", {})
        
        # Get the latest primary keyword from array
        primary_keyword_array = blog_doc.get("primary_keyword", [])
        latest_primary_final = None
        if primary_keyword_array:
            latest_primary_final = primary_keyword_array[-1]
        
        # Get the latest secondary keywords from array
        secondary_keywords_array = blog_doc.get("secondary_keywords", [])
        latest_secondary_keywords = []
        if secondary_keywords_array:
            latest_secondary_final = secondary_keywords_array[-1]
            latest_secondary_keywords = latest_secondary_final.get("keywords", [])
        
        # Get the latest categories from array
        categories_array = blog_doc.get("categories", [])
        latest_categories = []
        if categories_array:
            latest_categories_final = categories_array[-1]
            latest_categories = latest_categories_final.get("categories", [])
        
        # Get the latest titles from array
        titles_array = blog_doc.get("titles", [])
        latest_titles = []
        if titles_array:
            latest_titles_final = titles_array[-1]
            latest_titles = latest_titles_final.get("titles", [])
        
        # Get the latest word count from root level array
        word_count_array = blog_doc.get("word_count", [])
        latest_word_count = None
        if word_count_array:
            latest_word_count = word_count_array[-1]  # Get latest word count
        
        response = LatestOutlineResponse(
            outline=outline_data,
            primary_keyword=latest_primary_final,
            secondary_keywords=latest_secondary_keywords,
            categories=latest_categories,
            titles=latest_titles,
            word_count=latest_word_count,
            status="success" if outline_data else "no_data",
            country=country,
            blog_id=blog_id
        )
        
        return response
        
    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    except Exception as e:
        logger.error(f"Error fetching latest outline: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )