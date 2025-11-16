from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from datetime import datetime
from uuid import UUID
from bson import ObjectId
from sqlalchemy.orm import Session
from app.db.session import get_db_session
from app.middleware.auth_middleware import verify_request_origin
from app.services.mongodb_service import MongoDBService
from app.services.cms_detector_service import CMSDetectorService
from pymongo.database import Database
import pytz
from app.core.logging_config import logger
from fastapi.security import HTTPBearer
from app.models.project import Project
# Redis imports removed

security = HTTPBearer()

# Get IST timezone
ist_tz = pytz.timezone('Asia/Kolkata')

def verify_project_access(
    project_id: UUID,
    user_id: str,
    db: Session
) -> Project:
    """
    Verify if the current user has access to the project
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == user_id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=403,
            detail="You don't have access to this project"
        )
    return project

def serialize_datetime(obj):
    """Convert datetime objects to ISO format strings"""
    if isinstance(obj, datetime):
        # Check if the datetime object already has timezone info
        if obj.tzinfo is None:
            # If no timezone info, assume it's UTC and convert to IST
            obj = pytz.utc.localize(obj).astimezone(ist_tz)
        return obj.isoformat()
    return obj

def get_mongodb() -> Database:
    """Get MongoDB database connection"""
    mongodb_service = MongoDBService()
    return mongodb_service.get_sync_db()

router = APIRouter(
    prefix="",
    tags=["latest-blogs"],
    dependencies=[Depends(verify_request_origin), Depends(security)]
)

# Redis caching completely removed from this endpoint

@router.get("/latest")
def get_latest_blogs(
    request: Request,
    current_user = Depends(verify_request_origin),
    mongo_db = Depends(get_mongodb)
):
    """Get latest 4 blogs from MongoDB (Rayo blogs only)"""
    try:
        user_id = current_user.id
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID not provided")
            
        project_id_str = str(project_id)
        logger.info(f"Fetching latest 4 blogs from MongoDB for user {user_id} in project {project_id}")
        
        # Verify project access and detect CMS
        project = None
        connected_cms = None
        with get_db_session() as db:
            project = verify_project_access(project_id, user_id, db)
            # Detect connected CMS
            connected_cms = CMSDetectorService.detect_cms(project_id_str, db)
        
        # Direct fetch from MongoDB (Redis caching removed)
        logger.info(f"🗄️ Fetching latest blogs from MongoDB for project {project_id_str}")
        
        try:
            blogs_collection = mongo_db.blogs
            
            # Query for filtering (same logic as main blog endpoint)
            query = {
                "project_id": project_id_str,
                "is_active": True
            }
            
            # If CMS is connected, exclude published Rayo blogs from MongoDB results
            if connected_cms in ["wordpress", "shopify"]:
                query["$or"] = [
                    {"source": {"$ne": "rayo"}},  # Include non-Rayo blogs
                    {"source": "rayo", "status": {"$nin": ["publish", "published"]}}  # Include only draft/non-published Rayo blogs
                ]
                logger.info("📝 Excluding published Rayo blogs from latest blogs results (CMS connected)")
            
            logger.info(f"📋 Latest blogs MongoDB query: {query}")
            
            # Query for latest 4 active blogs for this project
            cursor = blogs_collection.find(query).sort("updated_at", -1).limit(4)
            
            blogs = list(cursor)
            logger.info(f"Found {len(blogs)} latest blogs from MongoDB")
            
            # Transform blogs to only required fields
            transformed_blogs = []
            for blog in blogs:
                # Handle title field - if array, use latest; if string, use as-is
                title_value = blog.get("title", "")
                if isinstance(title_value, list) and title_value:
                    # Use latest title from array
                    title = title_value[-1]
                elif isinstance(title_value, str):
                    # Use string title as-is
                    title = title_value
                else:
                    # Fallback for empty or invalid title
                    title = ""
                
                # Handle category field - if array, use latest; if string, use as-is
                category_value = blog.get("category", "")
                if isinstance(category_value, list) and category_value:
                    # Use latest category from array
                    category = category_value[-1]
                elif isinstance(category_value, str):
                    # Use string category as-is
                    category = category_value
                else:
                    # Fallback for empty or invalid category
                    category = ""
                
                # Extract only required fields
                blog_data = {
                    "id": str(blog["_id"]),
                    "title": title,
                    "created_at": serialize_datetime(blog.get("created_at")),
                    "updated_at": serialize_datetime(blog.get("updated_at")),
                    "words_count": blog.get("words_count", 0),
                    "status": blog.get("status", ""),
                    "category": category,
                    "step_tracking": blog.get("step_tracking", {}).get("current_step", "")
                }
                transformed_blogs.append(blog_data)
            
            # Prepare response data (no caching)
            response_data = {
                "status": "success",
                "data": transformed_blogs,
                "count": len(transformed_blogs)
            }
            
            return JSONResponse(
                content=response_data,
                status_code=200
            )
            
        except Exception as mongo_error:
            logger.error(f"MongoDB error in get_latest_blogs: {str(mongo_error)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch latest blogs: {str(mongo_error)}"
            )
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in get_latest_blogs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch latest blogs: {str(e)}"
        )