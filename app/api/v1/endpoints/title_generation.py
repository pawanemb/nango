from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.db.session import get_db_session
from app.middleware.auth_middleware import verify_request_origin_sync
from app.models.project import Project
from typing import Dict, Any, List, Optional, Union
from app.core.logging_config import logger
from pydantic import BaseModel
from app.services.normal_title_generation import TitleGenerationService
from app.services.balance_validator import BalanceValidator
from app.utils.api_utils import APIUtils
from app.services.mongodb_service import MongoDBService
from bson import ObjectId
import pytz
from datetime import datetime, timezone
router = APIRouter()

class TitleGenerationRequest(BaseModel):
    categories: List[Dict[str, Any]]

class LatestTitleResponse(BaseModel):
    titles: Optional[List[Union[str, Dict[str, Any]]]] = None
    primary_keyword: Optional[Dict[str, Any]] = None
    secondary_keywords: Optional[List[Dict[str, Any]]] = None
    categories: Optional[List[Dict[str, Any]]] = None
    status: str
    country: Optional[str] = None
    word_count: Optional[str] = None
    error: Optional[str] = None
    blog_id: str

class ManualTitleRequest(BaseModel):
    title: str


@router.put("/{blog_id}")
def update_titles_raw(
    request: Request,
    *,
    blog_id: str,
    body: Dict[str, Any],
    current_user = Depends(verify_request_origin_sync)
) -> Dict[str, Any]:
    """
    Add raw titles and word_count data to existing titles.generated array.
    Optimized for speed - minimal processing.
    """
    project_id = request.path_params.get("project_id")
    titles = body.get("titles", [])
    word_count = body.get("word_count", "")
    
    try:
        current_user_id = current_user.user.id
        
        # Fast validation
        APIUtils.validate_uuid(project_id)
        APIUtils.validate_objectid(blog_id)
        
        if not titles:
            raise HTTPException(status_code=400, detail="titles array required")
        
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
                "titles": 1,
                "title": 1,
                "word_count": 1,
                "country": 1,
                "intent": 1
            }
        )
        
        if not blog_doc:
            raise HTTPException(status_code=404, detail="Blog not found")
        
        # Quick validation - check if titles array exists
        existing_titles = blog_doc.get("titles", [])
        if not existing_titles:
            raise HTTPException(status_code=400, detail="No existing titles found")
        
        # Extract selected title from payload and save raw titles
        selected_title = None
        new_titles_to_add = []
        
        for title_item in titles:
            if isinstance(title_item, dict):
                # Extract selected title for root-level title field
                if title_item.get("selected", False):
                    selected_title = title_item.get("title")
                # Save the entire title object as-is (preserving selected: true, etc.)
                new_titles_to_add.append(title_item)
            elif isinstance(title_item, str):
                new_titles_to_add.append(title_item)
        
        # Minimal data preparation
        current_time = datetime.now(timezone.utc)
        
        # Create new titles array entry with updated tag
        titles_data = {
            "titles": new_titles_to_add,
            "tag": "updated",
            "generated_at": current_time
        }
        
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
        
        # Prepare update operations
        update_operations = {
            "$push": {
                "titles": titles_data  # Create new titles array entry
            },
            "$set": {
                "updated_at": current_time
            }
        }
        
        # Update single title field with selected title (if any)
        if selected_title:
            update_operations["$set"]["title"] = selected_title
        
        # Push word_count to array if provided (consistent with other fields)
        if word_count:
            update_operations["$push"]["word_count"] = word_count
        
        mongodb_service.get_sync_db()['blogs'].update_one(
            {"_id": ObjectId(blog_id)},
            update_operations
        )
        
        # Minimal response
        return {
            "status": "updated",
            "selected_title": selected_title,
            "word_count": word_count
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating titles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{blog_id}")
def generate_titles(
    request: Request,
    *,
    blog_id: str,
    title_generation_request: TitleGenerationRequest,
    current_user = Depends(verify_request_origin_sync)
) -> Dict[str, Any]:
    """
    Generate SEO-optimized blog titles based on MongoDB data and selected category.
    
    Args:
        blog_id: MongoDB blog document ID
        title_generation_request: Request body containing:
            category: The selected blog category
            subcategory: The selected blog subcategory
    """
    project_id = request.path_params.get("project_id")
    
    
    try:
        # Get user ID from nested user object
        try:
            current_user_id = current_user.user.id
        except Exception as user_extract_error:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid user authentication structure: {str(user_extract_error)}"
            )
        
        # Validate project_id and blog_id formats first
        APIUtils.validate_uuid(project_id)
        APIUtils.validate_objectid(blog_id)
        
        # Then verify project access
        with get_db_session() as db:
            project = APIUtils.verify_project_access(project_id, current_user_id, db)
        
        # Get blog data from MongoDB to extract all required data
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
        
        # Extract secondary keywords from array (latest)
        secondary_keywords_array = blog_doc.get("secondary_keywords", [])
        secondary_keywords_list = []
        if secondary_keywords_array:
            latest_secondary = secondary_keywords_array[-1]  # Get latest secondary keywords
            secondary_keywords_list = [kw.get("keyword") for kw in latest_secondary.get("keywords", [])]
        
        
        with get_db_session() as db:
            # 🚀 FAST BALANCE VALIDATION - Check balance BEFORE processing
            balance_validator = BalanceValidator(db)
            balance_check = balance_validator.validate_service_balance(
                user_id=current_user_id,
                service_key="title_generation"
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
            

            # Save categories selection to MongoDB
            current_time = datetime.now(timezone.utc)
            
            # Prepare category finalization data
            category_final_data = {
                "categories": title_generation_request.categories,
                "finalized_at": current_time,
                "primary_keyword": primary_keyword,
                "intent": intent,
                "country": country,
                "tag": "final"
            }
            
            # Prepare step tracking data for category completion
            category_step_tracking_data = {
                "step": "category",
                "status": "done",
                "completed_at": current_time
            }
            
            # Check if step_tracking exists, if not initialize it
            existing_step_tracking = blog_doc.get("step_tracking")
            if not existing_step_tracking:
                # Initialize step tracking structure
                step_tracking_structure = {
                    "current_step": "title",
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
            
            # Check if root-level category is an array, if not convert it
            current_category = blog_doc.get("category")
            if current_category is not None and not isinstance(current_category, list):
                # Convert string category to array format
                mongodb_service.get_sync_db()['blogs'].update_one(
                    {"_id": ObjectId(blog_id)},
                    {"$set": {"category": [current_category] if current_category else []}}
                )
            elif current_category is None:
                # Initialize category as empty array
                mongodb_service.get_sync_db()['blogs'].update_one(
                    {"_id": ObjectId(blog_id)},
                    {"$set": {"category": []}}
                )
            
            # Check if root-level subcategory is an array, if not convert it
            current_subcategory = blog_doc.get("subcategory")
            if current_subcategory is not None and not isinstance(current_subcategory, list):
                # Convert string subcategory to array format
                mongodb_service.get_sync_db()['blogs'].update_one(
                    {"_id": ObjectId(blog_id)},
                    {"$set": {"subcategory": [current_subcategory] if current_subcategory else []}}
                )
            elif current_subcategory is None:
                # Initialize subcategory as empty array
                mongodb_service.get_sync_db()['blogs'].update_one(
                    {"_id": ObjectId(blog_id)},
                    {"$set": {"subcategory": []}}
                )
            
            # Extract selected category and subcategory BEFORE saving to get values for root-level arrays
            temp_selected_category = None
            temp_selected_subcategory = None
            
            for category in title_generation_request.categories:
                if category.get("selected"):
                    temp_selected_category = category.get("category")
                    for subcategory in category.get("subcategories", []):
                        if isinstance(subcategory, dict) and subcategory.get("selected"):
                            temp_selected_subcategory = subcategory.get("name")
                            break
                    break
            
            # Update MongoDB document with category finalization and step tracking
            update_result = mongodb_service.get_sync_db()['blogs'].update_one(
                {"_id": ObjectId(blog_id)},
                {
                    "$push": {
                        "categories": category_final_data,
                        "step_tracking.category": category_step_tracking_data
                    },
                    "$set": {
                        "category": temp_selected_category,      # Update selected category at root level
                        "subcategory": temp_selected_subcategory, # Update selected subcategory at root level
                        "step_tracking.current_step": "title",
                        "updated_at": current_time
                    }
                }
            )
            
            # Use the already extracted selected category and subcategory
            selected_category = temp_selected_category
            selected_subcategory = temp_selected_subcategory
            
            # Validate that selections were found
            if not selected_category or not selected_subcategory:
                raise HTTPException(
                    status_code=400,
                    detail="No selected category or subcategory found in payload"
                )
            
            # Create service and generate titles
            service = TitleGenerationService(db=db, user_id=current_user_id, project_id=project_id)
            result = service.generate_title_workflow(
                primary_keyword=primary_keyword,
                intent=intent,
                category=selected_category,
                subcategory=selected_subcategory,
                country=country,
                project_id=project_id,
                secondary_keywords=secondary_keywords_list,
                project=project
            )
            
            # Save generated titles to MongoDB (raw data, no cleaning)
            title_generated_data = {
                "titles": result.get("titles", []),  # Save exactly as returned from AI service
                "tag": "generated",
                "generated_at": current_time
            }
            
            # Prepare step tracking data for title generation
            title_step_tracking_generated = {
                "step": "title",
                "status": "generated",
                "completed_at": current_time
            }
            
            # Update MongoDB document with generated titles - simple array push
            mongodb_service.get_sync_db()['blogs'].update_one(
                {"_id": ObjectId(blog_id)},
                {
                    "$push": {
                        "titles": title_generated_data,
                        "step_tracking.title": title_step_tracking_generated
                    },
                    "$set": {
                        "step_tracking.current_step": "title",
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
            
            return {
                "status": "success",
                "titles": result.get("titles", []),
                "blog_id": blog_id,
                "message": "Categories finalized and titles generated successfully"
            }
        
    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    
    except Exception as e:
        logger.error(f"Error in title generation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error in title generation: {str(e)}"
        )


@router.get("/{blog_id}")
def get_latest_title_data(
    request: Request,
    *,
    blog_id: str,
    current_user = Depends(verify_request_origin_sync)
) -> LatestTitleResponse:
    """
    Get the latest title data from a blog's generated array.
    
    Args:
        blog_id: MongoDB blog document ID
        
    Returns:
        Latest title data with blog information
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
            "titles": 1,
            "primary_keyword": 1,
            "secondary_keywords": 1,
            "categories": 1,
            "country": 1,
            "word_count": 1,
            "_id": 1
        }
        blog_doc = APIUtils.get_mongodb_blog_document(
            mongodb_service, blog_id, project_id, current_user_id, projection
        )
        
        # Get title data from simple array
        titles_array = blog_doc.get("titles", [])
        country = blog_doc.get("country", "us")
        
        # Get the latest titles (last item in array)
        latest_titles = []
        if titles_array and len(titles_array) > 0:
            latest_title_entry = titles_array[-1]  # Last item = latest
            latest_titles = latest_title_entry.get("titles", [])
        
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
        
        # Get the latest word count from root level array
        word_count_array = blog_doc.get("word_count", [])
        latest_word_count = None
        if word_count_array:
            latest_word_count = word_count_array[-1]  # Get latest word count
        
        response = LatestTitleResponse(
            titles=latest_titles,
            primary_keyword=latest_primary_final,
            secondary_keywords=latest_secondary_keywords,
            categories=latest_categories,
            status="success" if latest_titles else "no_data",
            country=country,
            word_count=latest_word_count,
            error=None,
            blog_id=blog_id
        )
        
        return response
        
    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    except Exception as e:
        logger.error(f"Error fetching latest titles: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.post("/{blog_id}/add-manual-title")
def add_manual_title(
    request: Request,
    *,
    blog_id: str,
    manual_title_request: ManualTitleRequest,
    current_user = Depends(verify_request_origin_sync)
) -> Dict[str, Any]:
    """
    Manually add a user-provided title to the existing title list.
    No AI generation - just adds the title to the top of the latest generated titles array.
    
    Args:
        blog_id: MongoDB blog document ID
        manual_title: User-provided title to add (as query parameter or form data)
    """
    project_id = request.path_params.get("project_id")
    
    try:
        # Get user ID from nested user object
        try:
            current_user_id = current_user.user.id
        except Exception as user_extract_error:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid user authentication structure: {str(user_extract_error)}"
            )
        
        # Extract and validate title from request
        manual_title = manual_title_request.title
        if not manual_title or not manual_title.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "message": "Manual title is required and cannot be empty"
                }
            )
        
        manual_title = manual_title.strip()
        
        if len(manual_title) > 100:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "message": "Title is too long. Maximum 100 characters allowed."
                }
            )
        
        # Validate project_id and blog_id formats first
        APIUtils.validate_uuid(project_id)
        APIUtils.validate_objectid(blog_id)
        
        # Then verify project access
        with get_db_session() as db:
            project = APIUtils.verify_project_access(project_id, current_user_id, db)
        
        # Get blog data from MongoDB to extract all required data
        mongodb_service = MongoDBService()
        mongodb_service.init_sync_db()
        
        # Find the blog document
        blog_doc = APIUtils.get_mongodb_blog_document(
            mongodb_service, blog_id, project_id, current_user_id
        )
        
        # Check if titles have been generated before
        titles_array = blog_doc.get("titles", [])
        
        if not titles_array:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "message": "No existing titles found. Please generate initial titles first using the main title generation endpoint."
                }
            )
        
        # Get the latest title generation entry (last item in array)
        latest_title_entry = titles_array[-1]
        existing_titles = latest_title_entry.get("titles", [])
        
        # Check if title already exists (case insensitive) - handle mixed format
        existing_titles_lower = []
        for title in existing_titles:
            if isinstance(title, str):
                existing_titles_lower.append(title.lower())
            elif isinstance(title, dict) and "title" in title:
                existing_titles_lower.append(title["title"].lower())
        
        if manual_title.lower() in existing_titles_lower:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "message": "This title already exists in your list"
                }
            )
        
        # Add manual title to TOP of existing titles
        updated_titles = [manual_title] + existing_titles
        
        current_time = datetime.now(timezone.utc)
        
        # Update the LATEST entry in titles array (add manual title)
        latest_index = len(titles_array) - 1  # Index of latest entry
        
        mongodb_service.get_sync_db()['blogs'].update_one(
            {"_id": ObjectId(blog_id)},
            {
                "$set": {
                    f"titles.{latest_index}.titles": updated_titles,  # Replace with updated list
                    f"titles.{latest_index}.last_manual_add_at": current_time,  # Track manual addition
                    f"titles.{latest_index}.total_manual_additions": latest_title_entry.get("total_manual_additions", 0) + 1,  # Track manual additions count
                    "updated_at": current_time
                }
            }
        )
        
        return {
            "status": "success",
            "added_title": manual_title,  # Return the manually added title
            "message": f"Successfully added manual title: '{manual_title}'",
            "total_titles_count": len(updated_titles),
            "manual_additions_count": latest_title_entry.get("total_manual_additions", 0) + 1
        }
        
    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    
    except Exception as e:
        logger.error(f"Error in add manual title: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error in add manual title: {str(e)}"
        )


@router.post("/{blog_id}/generate-more")
def generate_more_titles(
    request: Request,
    *,
    blog_id: str,
    current_user = Depends(verify_request_origin_sync)
) -> Dict[str, Any]:
    """
    Generate additional SEO-optimized blog titles and add them to existing title list.
    Uses the same data from previous steps but EXTENDS the latest generated titles array.
    
    Args:
        blog_id: MongoDB blog document ID
    """
    project_id = request.path_params.get("project_id")
    
    try:
        # 🔥 START LOGGING
        logger.info("=== GENERATE MORE TITLES ENDPOINT START ===")
        logger.info(f"Project ID: {project_id}")
        logger.info(f"Blog ID: {blog_id}")
        # Get user ID from nested user object
        try:
            current_user_id = current_user.user.id
            logger.info(f"✅ User ID extracted: {current_user_id}")
        except Exception as user_extract_error:
            logger.error(f"❌ Failed to extract user ID: {user_extract_error}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid user authentication structure: {str(user_extract_error)}"
            )
        
        # Validate project_id and blog_id formats first
        APIUtils.validate_uuid(project_id)
        APIUtils.validate_objectid(blog_id)
        
        # Then verify project access
        with get_db_session() as db:
            project = APIUtils.verify_project_access(project_id, current_user_id, db)
        
        # Get blog data from MongoDB to extract all required data
        mongodb_service = MongoDBService()
        mongodb_service.init_sync_db()
        
        # Find the blog document
        blog_doc = APIUtils.get_mongodb_blog_document(
            mongodb_service, blog_id, project_id, current_user_id
        )
        
        # Check if titles have been generated before
        logger.info("🔍 Checking for existing titles...")
        titles_array = blog_doc.get("titles", [])
        logger.info(f"📊 Found {len(titles_array)} title generation entries")
        
        if not titles_array:
            logger.error("❌ No existing titles found")
            raise HTTPException(
                status_code=400,
                detail="No existing titles found. Please generate initial titles first using the main title generation endpoint."
            )
        
        # Get the latest title generation entry (last item in array)
        latest_title_entry = titles_array[-1]
        logger.info(f"📝 Latest title entry keys: {list(latest_title_entry.keys())}")
        
        # Extract all the data from ROOT LEVEL document fields
        logger.info("📋 Extracting data from root level document...")
        
        # Get primary keyword from root level primary_keyword array (latest)
        primary_keyword_array = blog_doc.get("primary_keyword", [])
        if not primary_keyword_array:
            raise HTTPException(
                status_code=400,
                detail="No primary keyword found. Please complete the previous steps first."
            )
        latest_primary = primary_keyword_array[-1]
        primary_keyword = latest_primary.get("keyword")
        intent = latest_primary.get("intent")
        country = latest_primary.get("country")
        
        # Get category from root level category array (latest)
        category_array = blog_doc.get("category", [])
        if not category_array:
            raise HTTPException(
                status_code=400,
                detail="No category found. Please complete the category selection step first."
            )
        selected_category = category_array[-1]  # Get latest category
        
        # Get subcategory from root level subcategory array (latest)
        subcategory_array = blog_doc.get("subcategory", [])
        if not subcategory_array:
            raise HTTPException(
                status_code=400,
                detail="No subcategory found. Please complete the category selection step first."
            )
        selected_subcategory = subcategory_array[-1]  # Get latest subcategory
        
        # Get secondary keywords from root level secondary_keywords array (latest)
        secondary_keywords_array = blog_doc.get("secondary_keywords", [])
        secondary_keywords_list = []
        if secondary_keywords_array:
            latest_secondary = secondary_keywords_array[-1]
            all_secondary_keywords = latest_secondary.get("keywords", [])
            selected_secondary_keywords = [kw for kw in all_secondary_keywords if kw.get("selected", False)]
            secondary_keywords_list = [kw.get("keyword") for kw in selected_secondary_keywords]
        existing_titles = latest_title_entry.get("titles", [])
        
        logger.info(f"🔑 Primary keyword: {primary_keyword}")
        logger.info(f"💭 Intent: {intent}")
        logger.info(f"📂 Category: {selected_category}")
        logger.info(f"📁 Subcategory: {selected_subcategory}")
        logger.info(f"🌍 Country: {country}")
        logger.info(f"🏷️ Secondary keywords count: {len(secondary_keywords_list)}")
        logger.info(f"📄 Existing titles count: {len(existing_titles)}")
        logger.info(f"📄 Existing titles types: {[type(title).__name__ for title in existing_titles]}")
        
        # Log first few existing titles to see format
        for i, title in enumerate(existing_titles[:3]):
            if isinstance(title, str):
                logger.info(f"  Title {i}: (str) '{title}'")
            elif isinstance(title, dict):
                logger.info(f"  Title {i}: (dict) {title}")
            else:
                logger.info(f"  Title {i}: ({type(title).__name__}) {title}")
        
        # Validate required data exists
        if not all([primary_keyword, selected_category, selected_subcategory]):
            logger.error(f"❌ Missing required data - primary_keyword: {primary_keyword}, category: {selected_category}, subcategory: {selected_subcategory}")
            raise HTTPException(
                status_code=400,
                detail="Missing required data from previous title generation. Please regenerate titles using the main endpoint."
            )
        
        with get_db_session() as db:
            # 🚀 FAST BALANCE VALIDATION - Check balance BEFORE processing
            balance_validator = BalanceValidator(db)
            balance_check = balance_validator.validate_service_balance(
                user_id=current_user_id,
                service_key="title_generation"  # Same service key as main endpoint
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
            
            # Generate MORE titles using the same service and approach
            logger.info("🤖 Starting AI title generation...")
            logger.info(f"🤖 Using data - Keyword: {primary_keyword}, Category: {selected_category}, Subcategory: {selected_subcategory}")
            service = TitleGenerationService(db=db, user_id=current_user_id, project_id=project_id)
            result = service.generate_title_workflow(
                primary_keyword=primary_keyword,         # From existing data
                intent=intent,                          # From existing data
                category=selected_category,             # From existing data
                subcategory=selected_subcategory,       # From existing data
                country=country,                        # From existing data
                project_id=project_id,
                secondary_keywords=secondary_keywords_list,  # From existing data
                project=project
            )
            logger.info("✅ AI title generation completed")
            
            # Get newly generated titles
            new_titles = result.get("titles", [])
            logger.info(f"🆕 Generated {len(new_titles)} new titles")
            for i, title in enumerate(new_titles):
                logger.info(f"  New Title {i}: '{title}'")
            
            if not new_titles:
                logger.error("❌ No new titles generated")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to generate additional titles. Please try again."
                )
            
            # 🎯 KEY DIFFERENCE: EXTEND existing titles instead of creating new array
            # Keep existing titles as-is (preserve selected: true and other properties)
            logger.info("🔄 Processing existing titles for merging...")
            logger.info(f"📊 Existing titles to preserve: {len(existing_titles)}")
            
            # Keep existing titles exactly as they are (no normalization to preserve selected: true)
            for i, title in enumerate(existing_titles):
                if isinstance(title, str):
                    logger.info(f"  Existing {i}: (str) '{title}' → preserved")
                elif isinstance(title, dict):
                    logger.info(f"  Existing {i}: (dict) {title} → preserved with all properties")
                else:
                    logger.info(f"  Existing {i}: ({type(title).__name__}) {title} → preserved")
            
            logger.info(f"✅ Preserved {len(existing_titles)} existing titles with all properties")
            combined_titles = new_titles + existing_titles  # Merge new + existing (new titles at TOP)
            logger.info(f"🔀 Combined titles: {len(new_titles)} new + {len(existing_titles)} existing = {len(combined_titles)} total")
            
            current_time = datetime.now(timezone.utc)
            
            # Update the LATEST entry in titles array (extend the titles list)
            # Use array positional operator to update the last item
            latest_index = len(titles_array) - 1  # Index of latest entry
            logger.info(f"💾 Updating MongoDB at index {latest_index}...")
            logger.info(f"💾 Will save {len(combined_titles)} total titles to database")
            
            update_result = mongodb_service.get_sync_db()['blogs'].update_one(
                {"_id": ObjectId(blog_id)},
                {
                    "$set": {
                        f"titles.{latest_index}.titles": combined_titles,  # Replace titles with combined list
                        f"titles.{latest_index}.last_extended_at": current_time,  # Track when extended
                        f"titles.{latest_index}.total_generations": latest_title_entry.get("total_generations", 1) + 1,  # Track generation count
                        "updated_at": current_time
                    }
                }
            )
            logger.info(f"✅ MongoDB update result - Modified: {update_result.modified_count}, Matched: {update_result.matched_count}")
            
            # Get response data (same as main endpoint)
            # Extract primary keyword from array (latest)
            primary_keyword_array = blog_doc.get("primary_keyword", [])
            latest_primary = primary_keyword_array[-1] if primary_keyword_array else {}
            
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
            
            logger.info("🎉 Preparing response...")
            response_data = {
                "status": "success",
                "titles": new_titles,  # Return ONLY new titles generated
                "new_titles_count": len(new_titles),  # How many were added
                "total_titles_count": len(combined_titles),  # Total count
                "primary_keyword": latest_primary,
                "secondary_keywords": latest_secondary_keywords,
                "categories": latest_categories,
                "blog_id": blog_id,
                "country": country,
                "intent": intent,
                "selected_category": selected_category,
                "selected_subcategory": selected_subcategory,
                "message": f"Successfully generated {len(new_titles)} additional titles. Total titles: {len(combined_titles)}"
            }
            logger.info(f"✅ Generate More Titles completed successfully! New: {len(new_titles)}, Total: {len(combined_titles)}")
            logger.info("=== GENERATE MORE TITLES ENDPOINT END ===")
            return response_data
        
    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    
    except Exception as e:
        logger.error(f"Error in generate more titles: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error in generate more titles: {str(e)}"
        )
