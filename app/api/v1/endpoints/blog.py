from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request, Query, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from datetime import datetime
from uuid import UUID
from bson import ObjectId
from sqlalchemy.orm import Session
from app.db.session import get_db_session
from app.middleware.auth_middleware import verify_request_origin
from app.services.mongodb_service import MongoDBService
from app.services.cms_detector_service import CMSDetectorService
from app.services.wordpress_blog_service import WordPressBlogService
from app.services.shopify_service import ShopifyService
from app.models.shopify_credentials import ShopifyCredentials
from pymongo.database import Database
import pytz
import math
import json
from app.core.logging_config import logger
from fastapi.security import HTTPBearer
from app.models.project import Project
# Redis imports removed

security = HTTPBearer()

# Constants
COLLECTION_NAME = "blogs"

# Get IST timezone
ist_tz = pytz.timezone('Asia/Kolkata')

# Redis caching completely removed from blog endpoints

def get_current_ist_time():
    """Get current time in IST"""
    return datetime.now(ist_tz)

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

class BlogCreate(BaseModel):
    title: str
    content: str
    primary_keyword: str
    secondary_keywords: List[str]
    category: str
    tags: List[str] = []
    intent: str
    words_count: Optional[int] = None


class RayoFeaturedImage(BaseModel):
    url: str
    id: str
    filename: str

class BlogUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None
    meta_description: Optional[str] = None
    rayo_featured_image: Optional[RayoFeaturedImage] = None

class BlogResponse(BaseModel):
    id: str
    title: str
    content: str
    project_id: str
    primary_keyword: str
    secondary_keywords: List[str]
    category: str
    intent: str
    status: str
    source: str
    # meta_description: str
    words_count: int
    created_at: datetime
    updated_at: datetime
    user_id: str

    class Config:
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }

class BlogListItem(BaseModel):
    id: str
    title: str
    project_id: str
    user_id: str
    is_active: Optional[bool] = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    category: Optional[str] = None
    source: Optional[str] = None
    words_count: Optional[int] = None
    # WordPress tracking fields
    published_to_wp: Optional[bool] = False
    wordpress_id: Optional[str] = None
    wp_url: Optional[str] = None
    wp_publish_date: Optional[datetime] = None

    class Config:
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }


class BlogListMeta(BaseModel):
    total_count: int
    total_pages: int
    current_page: int
    per_page: int
    has_next: bool
    has_previous: bool
    connected_cms: Optional[str] = None
    rayo_blogs_count: int = 0
    cms_blogs_count: int = 0

class BlogListResponse(BaseModel):
    status: str
    data: List[BlogListItem]
    meta: BlogListMeta

# Pydantic model for WordPress blog update
class WordPressBlogUpdate(BaseModel):
    title: Optional[str] = Field(None, description="Blog post title")
    content: Optional[str] = Field(None, description="Full HTML content of the post")
    excerpt: Optional[str] = Field(None, description="Post excerpt/summary")
    status: Optional[str] = Field(None, description="Post status: 'publish', 'draft', 'private', 'pending', or 'future' for scheduled posts")
    categories: Optional[List[int]] = Field(None, description="Array of category IDs")
    tags: Optional[List[int]] = Field(None, description="Array of tag IDs")
    featured_media: Optional[int] = Field(None, description="Featured image media ID")
    author: Optional[int] = Field(None, description="Author/user ID")
    slug: Optional[str] = Field(None, description="URL slug for the post")
    password: Optional[str] = Field(None, description="Password for protected posts")
    comment_status: Optional[str] = Field(None, description="Comment status (open, closed)")
    ping_status: Optional[str] = Field(None, description="Ping status (open, closed)")
    date: Optional[str] = Field(None, description="Publication date (ISO format) - required for 'future' status")
    sticky: Optional[bool] = Field(None, description="Make post sticky/pinned")
    
    # Add validation for status
    @validator('status')
    def validate_status(cls, v):
        if v is not None:
            allowed_statuses = ['publish', 'draft', 'private', 'pending', 'future']
            if v not in allowed_statuses:
                raise ValueError(f'Status must be one of: {", ".join(allowed_statuses)}')
        return v
    
    # Add validation for future posts and date format
    @validator('date')
    def validate_future_date(cls, v, values):
        if values.get('status') == 'future' and not v:
            raise ValueError('Date is required when status is "future"')
        return v

    # Support for Rayo featured image format (will be converted to WordPress media)
    rayo_featured_image: Optional[RayoFeaturedImage] = Field(None, description="Rayo featured image to upload to WordPress")
    # Support for direct image URL (will be downloaded and uploaded to WordPress)
    image_url: Optional[str] = Field(None, description="Image URL to download and upload as featured image")

class PublishToWordPressRequest(BaseModel):
    status: Optional[str] = Field("draft", description="WordPress post status: publish, draft, private, future")
    author_id: Optional[int] = Field(1, description="WordPress author ID")
    categories: Optional[List[str]] = Field([], description="WordPress category names")
    category_ids: Optional[List[int]] = Field([], description="WordPress category IDs")
    tags: Optional[List[str]] = Field([], description="WordPress tag names")  
    tag_ids: Optional[List[int]] = Field([], description="WordPress tag IDs")
    content: Optional[str] = Field(None, description="Override content (optional)")
    image_url: Optional[str] = Field(None, description="Override featured image URL (optional)")
    slug: Optional[str] = Field(None, description="Override WordPress slug (optional)")
    scheduled_date: Optional[str] = Field(None, description="Schedule date for future posts (ISO format)")
    
    @validator('status')
    def validate_status(cls, v):
        allowed_statuses = ['publish', 'draft', 'private', 'pending', 'future']
        if v not in allowed_statuses:
            raise ValueError(f'Status must be one of: {", ".join(allowed_statuses)}')
        return v
    
    @validator('scheduled_date')
    def validate_scheduled_date(cls, v, values):
        if values.get('status') == 'future' and not v:
            raise ValueError('Scheduled date is required when status is "future"')
        return v

# ============ SHOPIFY MODELS ============

class ShopifyBlog(BaseModel):
    id: int
    title: str
    handle: str
    commentable: Optional[str] = None
    feedburner: Optional[str] = None
    feedburner_location: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    tags: Optional[str] = None

class ShopifyPost(BaseModel):
    id: str
    title: str
    excerpt: Optional[str] = None
    content: Optional[str] = None
    status: str
    source: str = "shopify"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    published_at: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = []
    words_count: Optional[int] = None
    shopify_url: Optional[str] = None
    metadata: Optional[dict] = None

class ShopifyAuthor(BaseModel):
    id: int
    name: str

class ShopifyTag(BaseModel):
    id: int
    name: str
    count: int = 0

class ShopifyBlogsResponse(BaseModel):
    status: str = "success"
    data: dict

class ShopifyPostsResponse(BaseModel):
    status: str = "success"
    data: dict

class ShopifyPostResponse(BaseModel):
    status: str = "success"
    data: ShopifyPost

class ShopifyAuthorsResponse(BaseModel):
    status: str = "success"
    data: dict

class ShopifyTagsResponse(BaseModel):
    status: str = "success"
    data: dict

# ============ SHOPIFY CREATE MODELS ============

class ShopifyBlogCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Blog title")
    handle: Optional[str] = Field(None, max_length=100, description="URL handle (auto-generated if not provided)")

class ShopifyArticleCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Article title")
    content: str = Field(..., description="Article HTML content")
    blog_id: int = Field(..., description="Blog ID to create article in")
    tags: Optional[str] = Field("", description="Comma-separated tags")
    author: Optional[str] = Field("", description="Author name")
    summary: Optional[str] = Field("", description="Article summary/excerpt")
    published: Optional[bool] = Field(True, description="Publish immediately")
    handle: Optional[str] = Field(None, description="URL handle (auto-generated if not provided)")

class ShopifyArticleUpdate(BaseModel):
    title: Optional[str] = Field(None, description="Article title")
    content: Optional[str] = Field(None, description="Article content (will map to body_html)")
    body_html: Optional[str] = Field(None, description="Article HTML content")
    tags: Optional[List[str]] = Field(None, description="Tags array (will be converted to comma-separated)")
    author: Optional[str] = Field(None, description="Author name")
    summary: Optional[str] = Field(None, description="Article summary/excerpt")
    published: Optional[bool] = Field(None, description="Published status")
    status: Optional[str] = Field(None, description="Article status (published/draft)")
    handle: Optional[str] = Field(None, description="Article URL handle/slug")
    image_url: Optional[str] = Field(None, description="Featured image URL")
    blog_id: Optional[int] = Field(None, description="Blog ID (for reference)")

class ShopifyTagCreate(BaseModel):
    tag_names: List[str] = Field(..., min_items=1, description="List of tag names to create")
    
class ShopifyTagCreateViaArticle(BaseModel):
    blog_id: int = Field(..., description="Blog ID to create article in")
    article_title: str = Field(..., min_length=1, description="Article title")
    article_content: str = Field(..., description="Article HTML content")  
    tag_names: List[str] = Field(..., min_items=1, description="List of tag names to create with this article")

class PublishToShopifyRequest(BaseModel):
    """Model for publishing Rayo blog to Shopify - matches frontend payload"""
    status: Optional[str] = Field("published", description="Article status: published or draft")
    author: Optional[str] = Field("Rayo User", description="Author name")
    tags: Optional[List[str]] = Field([], description="List of tag names")
    summary: Optional[str] = Field("", description="Article summary/excerpt")
    blog_id: int = Field(..., description="Shopify blog ID to publish to")
    content: Optional[str] = Field(None, description="Override content (optional)")
    image_url: Optional[str] = Field(None, description="Featured image URL")
    
    @validator('status')
    def validate_status(cls, v):
        allowed_statuses = ['published', 'draft']
        if v not in allowed_statuses:
            raise ValueError(f'Status must be one of: {", ".join(allowed_statuses)}')
        return v

def serialize_datetime(obj):
    """Convert datetime objects to ISO format strings"""
    if isinstance(obj, datetime):
        # Check if the datetime object already has timezone info
        if obj.tzinfo is None:
            # If no timezone info, assume it's UTC and convert to IST
            ist_tz = pytz.timezone('Asia/Kolkata')
            obj = pytz.utc.localize(obj).astimezone(ist_tz)
        return obj.isoformat()
    return obj

def deep_serialize_datetime(obj):
    """Recursively convert all datetime objects to ISO strings in nested structures"""
    if isinstance(obj, datetime):
        # Serialize datetime to ISO string
        if obj.tzinfo is None:
            ist_tz = pytz.timezone('Asia/Kolkata')
            obj = pytz.utc.localize(obj).astimezone(ist_tz)
        return obj.isoformat()
    elif isinstance(obj, dict):
        # Recursively serialize all values in dict
        return {key: deep_serialize_datetime(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        # Recursively serialize all items in list
        return [deep_serialize_datetime(item) for item in obj]
    else:
        # Return as-is for other types
        return obj

def serialize_blog(blog: dict) -> dict:
    """Serialize blog object for JSON response - removed unnecessary fields"""
    # Fields to exclude from response
    excluded_fields = {
        'sources',                      # Detailed scraping data
        'generation_method',            # Internal processing info
        'content_processing_method',    # Internal processing info
        'completion_time',             # Internal timing
        'brand_tonality_applied',      # Duplicate of brand_tonality
        'specialty_info',              # Internal metadata
        'target_word_count',           # Redundant field
        'country',   
        "outline",
        "keyword_intent",
        "brand_tonality",
        'subcategory'                  # If not used by frontend
        # NOTE: meta_description and rayo_featured_image are NOT excluded - they will be included
    }
    
    # Clean the blog data
    cleaned_blog = {}
    for key, value in blog.items():
        # Skip excluded fields
        if key in excluded_fields:
            continue
            
        # Skip empty objects/arrays if not needed
        if key == 'metadata' and (not value or value == {}):
            continue
        if key == 'tags' and (not value or value == []):
            continue
        
        # Handle title field - if array, use latest; if string, use as-is
        if key == 'title':
            if isinstance(value, list) and value:
                # Use latest title from array
                cleaned_blog[key] = value[-1]
            elif isinstance(value, str):
                # Use string title as-is
                cleaned_blog[key] = value
            else:
                # Fallback for empty or invalid title
                cleaned_blog[key] = ""
            continue
        
        # Handle category field - if array, use latest; if string, use as-is
        if key == 'category':
            if isinstance(value, list) and value:
                # Use latest category from array
                cleaned_blog[key] = value[-1]
            elif isinstance(value, str):
                # Use string category as-is
                cleaned_blog[key] = value
            else:
                # Fallback for empty or invalid category
                cleaned_blog[key] = ""
            continue
        
        # Handle subcategory field - if array, use latest; if string, use as-is
        if key == 'subcategory':
            if isinstance(value, list) and value:
                # Use latest subcategory from array
                cleaned_blog[key] = value[-1]
            elif isinstance(value, str):
                # Use string subcategory as-is
                cleaned_blog[key] = value
            else:
                # Fallback for empty or invalid subcategory
                cleaned_blog[key] = ""
            continue

        # Handle content field - if array, return latest version's html; if string, use as-is
        if key == 'content':
            if isinstance(value, list) and value:
                # Get the latest version from the array
                latest_version = value[-1]
                if isinstance(latest_version, dict):
                    # Return just the html from the latest version
                    cleaned_blog[key] = latest_version.get('html', '')
                else:
                    # Fallback if not a dict
                    cleaned_blog[key] = latest_version
            elif isinstance(value, str):
                # Use string content as-is (backward compatibility)
                cleaned_blog[key] = value
            else:
                # Fallback for empty or invalid content
                cleaned_blog[key] = ""
            continue

        # Handle primary_keyword field - if array, extract keyword string; if string, use as-is
        if key == 'primary_keyword':
            if isinstance(value, list) and value:
                # Get the latest keyword from array
                latest_keyword = value[-1]
                if isinstance(latest_keyword, dict):
                    # Return just the keyword string
                    cleaned_blog[key] = latest_keyword.get('keyword', '')
                else:
                    # Fallback if not a dict
                    cleaned_blog[key] = latest_keyword
            elif isinstance(value, str):
                # Use string as-is (backward compatibility for old blogs)
                cleaned_blog[key] = value
            else:
                # Fallback for empty or invalid primary_keyword
                cleaned_blog[key] = ""
            continue

        # Handle secondary_keywords field - if array, extract SELECTED keyword strings only
        if key == 'secondary_keywords':
            if isinstance(value, list) and value:
                # Check if it's OLD format (simple array of strings) or NEW format (array of objects)
                if isinstance(value[0], str):
                    # OLD format: ["keyword1", "keyword2"] - return as-is
                    cleaned_blog[key] = value
                elif isinstance(value[0], dict):
                    # NEW format: [{keywords: [...], tag: "final"}] - get latest and filter selected
                    latest_keywords = value[-1]
                    keywords_list = latest_keywords.get('keywords', [])
                    # Extract ONLY selected keyword strings (selected: "true")
                    cleaned_blog[key] = [
                        kw.get('keyword', kw) if isinstance(kw, dict) else kw
                        for kw in keywords_list
                        if isinstance(kw, dict) and kw.get('selected') == "true"
                    ]
                else:
                    cleaned_blog[key] = []
            else:
                # Fallback for empty or invalid secondary_keywords
                cleaned_blog[key] = []
            continue

        # Handle word_count field - if array, use latest; if int/string, use as-is
        if key == 'word_count':
            if isinstance(value, list) and value:
                # Get the latest word count from array
                cleaned_blog[key] = value[-1]
            elif isinstance(value, (int, str)):
                # Use int/string as-is (backward compatibility)
                cleaned_blog[key] = value
            else:
                # Fallback for empty or invalid word_count
                cleaned_blog[key] = None
            continue

        # Handle content_history - serialize datetime objects in array (legacy field)
        if key == 'content_history' and isinstance(value, list):
            serialized_history = []
            for version in value:
                if isinstance(version, dict):
                    serialized_version = {}
                    for v_key, v_value in version.items():
                        serialized_version[v_key] = serialize_datetime(v_value) if isinstance(v_value, datetime) else v_value
                    serialized_history.append(serialized_version)
                else:
                    serialized_history.append(version)
            cleaned_blog[key] = serialized_history
            continue

        # Serialize datetime objects
        cleaned_blog[key] = serialize_datetime(value) if isinstance(value, datetime) else value

    # 🔥 DEEP SERIALIZATION: Recursively convert ALL datetime objects in nested structures
    # This handles datetime objects in arrays and nested dicts from workflow steps
    cleaned_blog = deep_serialize_datetime(cleaned_blog)

    return cleaned_blog

def get_mongodb() -> Database:
    """Get MongoDB database connection"""
    mongodb_service = MongoDBService()
    return mongodb_service.get_sync_db()

router = APIRouter(
    prefix="",
    tags=["blogs"],
    dependencies=[Depends(verify_request_origin), Depends(security)]
)

@router.post("", response_model=BlogResponse)
def create_blog(
    request: Request,
    blog: BlogCreate,
    current_user = Depends(verify_request_origin),
    mongo_db = Depends(get_mongodb)
):
    """Create a new blog"""
    try:
        user_id = current_user.id
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID not provided")
        
        logger.info(f"Creating blog for user {user_id} in project {project_id}")
        
        # Verify project access with a new, short-lived connection
        project = None
        with get_db_session() as db:
            project = verify_project_access(project_id, user_id, db)
        
        # Prepare blog data
        now = get_current_ist_time()
        blog_dict = blog.model_dump()
        blog_dict["project_id"] = str(project_id)
        blog_dict["created_at"] = now
        blog_dict["updated_at"] = now
        blog_dict["user_id"] = str(user_id)
        blog_dict["status"] = "draft"
        blog_dict["source"] = "rayo"
        blog_dict["is_active"] = True
        
        if not blog_dict.get("words_count"):
            blog_dict["words_count"] = len(blog_dict["content"].split())
        
        # MongoDB operation with timeout
        logger.info("Starting MongoDB operation")
        try:
            # Don't use async with here since we're already getting a connection from Depends
            logger.info(f"Inserting blog document")
            result = mongo_db[COLLECTION_NAME].insert_one(blog_dict)
            
            if not result or not result.inserted_id:
                logger.error("Failed to get inserted_id from MongoDB")
                raise HTTPException(status_code=500, detail="Failed to create blog - no inserted_id")
            
            logger.info(f"Blog document inserted with id: {result.inserted_id}")
            
            # Get the created blog
            created_blog = mongo_db[COLLECTION_NAME].find_one({"_id": result.inserted_id})
            if not created_blog:
                logger.error("Failed to fetch created blog from MongoDB")
                raise HTTPException(status_code=500, detail="Failed to fetch created blog")
            
            created_blog["id"] = str(created_blog.pop("_id"))
            logger.info("Blog creation successful")
            
            logger.info(f"✅ Blog created successfully for project {project_id}")
            
            return JSONResponse(content={"status": "success", "data": serialize_blog(created_blog)})
                
        except Exception as mongo_error:
            logger.error(f"MongoDB error during blog creation: {str(mongo_error)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to store blog in MongoDB: {str(mongo_error)}"
            )
                
    except HTTPException as he:
        logger.error(f"HTTP error in blog creation: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in blog creation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create blog: {str(e)}"
        )
    finally:
        logger.info("Finally ran the create_blog function")

@router.put("/{blog_id}")
async def update_blog(
    request: Request,
    blog_id: str,
    wordpress: Optional[str] = Query(None, description="Add this parameter for WordPress blogs"),
    shopify: Optional[str] = Query(None, description="Add this parameter for Shopify blogs"),
    current_user = Depends(verify_request_origin),
    mongo_db = Depends(get_mongodb)
):
    """Update a blog by ID - supports Rayo, WordPress, and Shopify blogs
    
    Examples:
    - Rayo blog: PUT /blog/64f1a2b3c4d5e6f7g8h9i0j1
    - WordPress blog: PUT /blog/56547?wordpress
    - Shopify blog: PUT /blog/610649145641?shopify
    """
    try:
        user_id = current_user.id
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID not provided")
            
        project_id_str = str(project_id)
        
        # Determine blog source based on parameters
        is_wordpress = wordpress is not None
        is_shopify = shopify is not None
        
        if is_wordpress and is_shopify:
            raise HTTPException(status_code=400, detail="Cannot specify both wordpress and shopify source")
        
        if is_shopify:
            source_type = "Shopify"
        elif is_wordpress:
            source_type = "WordPress"
        else:
            source_type = "Rayo"
            
        logger.info(f"Updating {source_type} blog {blog_id} for user {user_id} in project {project_id}")

        # Use get_db_session for database operations
        with get_db_session() as db:
            # Verify project access
            project = verify_project_access(project_id, user_id, db)
            
            # For WordPress/Shopify blogs, verify CMS connection
            if is_wordpress or is_shopify:
                connected_cms = CMSDetectorService.detect_cms(project_id_str, db)
                expected_cms = "wordpress" if is_wordpress else "shopify"
                
                if connected_cms != expected_cms:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"{expected_cms.capitalize()} CMS not connected to this project"
                    )
        
        # Parse request body based on blog source
        request_body = await request.json()
        
        # Route to appropriate update handler
        if is_wordpress:
            # Parse as WordPress update data
            try:
                wordpress_data = WordPressBlogUpdate(**request_body)
                return update_wordpress_blog_handler(blog_id, project_id_str, user_id, wordpress_data)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid WordPress blog data: {str(e)}")
        elif is_shopify:
            # Parse as Shopify update data
            try:
                shopify_data = ShopifyArticleUpdate(**request_body)
                return await update_shopify_blog_handler(blog_id, project_id_str, user_id, shopify_data)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid Shopify blog data: {str(e)}")
        else:
            # Parse as Rayo update data
            try:
                blog_data = BlogUpdate(**request_body)
                return update_rayo_blog_handler(blog_id, project_id_str, user_id, blog_data, mongo_db)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid blog update data: {str(e)}")
            
    except HTTPException as he:
        logger.error(f"HTTP error in update_blog: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in update_blog: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update blog: {str(e)}"
        )
    finally:
        logger.info("Finally ran the update_blog function")


def update_rayo_blog_handler(blog_id: str, project_id_str: str, user_id: str, blog: BlogUpdate, mongo_db) -> JSONResponse:
    """Handle Rayo blog updates (MongoDB)"""
    try:
        # Verify blog ownership
        existing_blog = mongo_db[COLLECTION_NAME].find_one({
            "_id": ObjectId(blog_id),
            "project_id": project_id_str
        })
        logger.info(f"Existing blog: {existing_blog}")
        if not existing_blog:
            logger.info(f"Blog {blog_id} not found in project {project_id_str}")
            raise HTTPException(status_code=403, detail="You don't have access to this blog")
                
        # Convert blog model to dict
        blog_dict = {}
        content_html = None

        for field, value in blog.model_dump(exclude_unset=True).items():
            if value is not None:
                # Extract content separately to handle as array
                if field == "content":
                    content_html = value
                else:
                    blog_dict[field] = value

        # Initialize metadata
        blog_dict['metadata'] = {}
        if existing_blog.get('metadata'):
            # Copy existing metadata
            blog_dict['metadata'].update(existing_blog['metadata'])

        now = get_current_ist_time()
        blog_dict["updated_at"] = now

        # Build update operations
        update_data = {"$set": blog_dict}

        # 🔥 CONTENT VERSIONING: Append to content array
        if content_html is not None:
            # Get existing content to check format
            existing_content = existing_blog.get("content")

            # 🔄 MIGRATION: If content is a string (old format), migrate it first
            if isinstance(existing_content, str):
                logger.info(f"🔄 Migrating old string content to array format for blog {blog_id}")

                # Create first version from existing string content
                old_created_at = existing_blog.get("created_at", now)
                first_version = {
                    "html": existing_content,
                    "saved_at": old_created_at,
                    "tag": "generated",
                    "version": 1,
                    "words_count": len(existing_content.split())
                }

                # Create new version from update
                new_version = {
                    "html": content_html,
                    "saved_at": now,
                    "tag": "updated",
                    "version": 2,
                    "words_count": len(content_html.split())
                }

                # Replace content with array containing both versions
                blog_dict["content"] = [first_version, new_version]
                blog_dict["words_count"] = new_version["words_count"]
                update_data = {"$set": blog_dict}

                logger.info(f"✅ Migrated content: created 2 versions (1 old + 1 new)")

            # Content is already an array or doesn't exist
            else:
                existing_content_array = existing_content if isinstance(existing_content, list) else []

                # Calculate words count
                words_count = len(content_html.split())
                blog_dict["words_count"] = words_count

                # Create new version object
                content_version = {
                    "html": content_html,
                    "saved_at": now,
                    "tag": "updated",
                    "version": len(existing_content_array) + 1,
                    "words_count": words_count
                }

                # Append to content array
                update_data["$push"] = {"content": content_version}
                logger.info(f"📝 Adding content version {content_version['version']} to content array")

        query = {
            "_id": ObjectId(blog_id),
            "project_id": project_id_str
        }
        logger.info(f"Updating Rayo blog with query: {query}")

        # Get MongoDB collection
        collection = mongo_db[COLLECTION_NAME]

        # Perform the update
        result = collection.update_one(query, update_data)
        logger.info(f"Update result - matched: {result.matched_count}, modified: {result.modified_count}")
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Blog not found")
        
        # Get the updated blog
        updated_blog = collection.find_one(query)
        if not updated_blog:
            raise HTTPException(status_code=500, detail="Failed to fetch updated blog")
        
        updated_blog["id"] = str(updated_blog.pop("_id"))
        logger.info(f"✅ Rayo blog updated successfully")
        
        return JSONResponse(
            content={
                "status": "success",
                "data": serialize_blog(updated_blog)
            },
            status_code=200
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error updating Rayo blog: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update Rayo blog: {str(e)}"
        )


def update_wordpress_blog_handler(blog_id: str, project_id_str: str, user_id: str, wordpress_data: WordPressBlogUpdate) -> JSONResponse:
    """Handle WordPress blog updates (WordPress REST API)"""
    try:
        # Create WordPress service
        with get_db_session() as db:
            wp_service = WordPressBlogService.from_project(project_id_str, db)
            if not wp_service:
                raise HTTPException(
                    status_code=500, 
                    detail="Failed to initialize WordPress service"
                )
        
        # Convert blog_id to integer for WordPress API
        try:
            wp_post_id = int(blog_id)
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail="Invalid WordPress blog ID format"
            )
        
        # Convert Pydantic model to dict and filter None values
        update_dict = {}
        for field, value in wordpress_data.model_dump(exclude_unset=True).items():
            if value is not None:
                # Skip special fields that need processing
                if field not in ['rayo_featured_image', 'image_url']:
                    update_dict[field] = value
        
        # Handle featured image upload if provided
        if wordpress_data.rayo_featured_image:
            logger.info(f"📷 Processing Rayo featured image for WordPress update: {wordpress_data.rayo_featured_image.filename}")
            # Convert RayoFeaturedImage to dict format expected by _upload_rayo_image_to_wp
            rayo_image_dict = {
                "url": wordpress_data.rayo_featured_image.url,
                "id": wordpress_data.rayo_featured_image.id,
                "filename": wordpress_data.rayo_featured_image.filename
            }
            featured_media_id = wp_service._upload_rayo_image_to_wp(rayo_image_dict)
            if featured_media_id:
                update_dict["featured_media"] = featured_media_id
                logger.info(f"✅ Rayo featured image uploaded to WordPress with media ID: {featured_media_id}")
            else:
                logger.warning("❌ Failed to upload Rayo featured image to WordPress")
        
        elif wordpress_data.image_url:
            logger.info(f"📷 Processing image URL for WordPress update: {wordpress_data.image_url}")
            # Create image dict for URL upload
            image_dict = {
                "url": wordpress_data.image_url,
                "filename": wordpress_data.image_url.split('/')[-1] or "update-image.jpg"
            }
            featured_media_id = wp_service._upload_rayo_image_to_wp(image_dict)
            if featured_media_id:
                update_dict["featured_media"] = featured_media_id
                logger.info(f"✅ Image URL uploaded to WordPress with media ID: {featured_media_id}")
            else:
                logger.warning("❌ Failed to upload image URL to WordPress")
        
        logger.info(f"Updating WordPress blog {wp_post_id} with data: {update_dict}")
        
        # Update WordPress blog
        updated_blog = wp_service.update_post(wp_post_id, update_dict)
        
        if not updated_blog:
            raise HTTPException(status_code=404, detail="WordPress blog not found or update failed")
        
        logger.info(f"✅ WordPress blog updated successfully")
        
        return JSONResponse(
            content={
                "status": "success",
                "data": serialize_blog(updated_blog)
            },
            status_code=200
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error updating WordPress blog: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update WordPress blog: {str(e)}"
        )


async def update_shopify_blog_handler(blog_id: str, project_id_str: str, user_id: str, shopify_data: ShopifyArticleUpdate) -> JSONResponse:
    """Handle Shopify blog updates (Shopify REST API) - Fast & Optimized"""
    try:
        # Get Shopify credentials and create service
        with get_db_session() as db:
            shopify_creds = db.query(ShopifyCredentials).filter(
                ShopifyCredentials.project_id == project_id_str
            ).first()
            
            if not shopify_creds:
                raise HTTPException(status_code=404, detail="Shopify not connected to this project")
            
            # Create Shopify service  
            shopify_service = ShopifyService(
                shop_domain=shopify_creds.shop_domain,
                access_token=shopify_creds.access_token,
                api_version=shopify_creds.api_version
            )
        
        # Parse article ID from URL
        try:
            shopify_article_id = int(blog_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Shopify article ID format")
        
        # Get the blog ID from payload (new category/blog)
        payload_blog_id = None
        if hasattr(shopify_data, 'blog_id') and shopify_data.blog_id:
            payload_blog_id = shopify_data.blog_id
        
        # Find which blog currently contains this article
        logger.info(f"🔍 DEBUG: Finding current blog for article {shopify_article_id}")
        logger.info(f"🔍 DEBUG: Payload blog_id = {payload_blog_id}")
        
        blogs = shopify_service.get_blogs()
        logger.info(f"🔍 DEBUG: Found {len(blogs)} total blogs in Shopify store")
        
        current_blog_id = None
        current_article = None
        
        for i, blog in enumerate(blogs):
            logger.info(f"🔍 DEBUG: Checking blog {i+1}/{len(blogs)}: ID={blog['id']}, Title='{blog['title']}'")
            test_article = shopify_service.get_post_by_id(blog_id=blog['id'], article_id=shopify_article_id)
            if test_article:
                current_blog_id = blog['id']
                current_article = test_article
                logger.info(f"✅ DEBUG: Article {shopify_article_id} found in current blog {current_blog_id} ('{blog['title']}')")
                logger.info(f"✅ DEBUG: Current article data: {current_article}")
                break
            else:
                logger.info(f"❌ DEBUG: Article {shopify_article_id} NOT found in blog {blog['id']} ('{blog['title']}')")
        
        if not current_blog_id:
            logger.error(f"❌ DEBUG: Article {shopify_article_id} not found in any of the {len(blogs)} blogs")
            raise HTTPException(status_code=404, detail=f"Article {shopify_article_id} not found in any blog")
        
        # Determine target blog ID (where to update/move the article)
        logger.info(f"🔍 DEBUG: Comparing blogs - Current: {current_blog_id}, Payload: {payload_blog_id}")
        
        # Only detect blog change if payload explicitly provides a DIFFERENT blog_id
        if payload_blog_id is not None and payload_blog_id != current_blog_id:
            # User wants to move article to a different blog (category change)
            target_blog_id = payload_blog_id
            logger.info(f"📝 DEBUG: Category change detected: Moving article from blog {current_blog_id} to blog {target_blog_id}")
            is_blog_change = True
        else:
            # Same blog, just update (this is the normal case for regular updates)
            target_blog_id = current_blog_id
            if payload_blog_id is None:
                logger.info(f"📝 DEBUG: No blog_id in payload - updating existing article in current blog {current_blog_id}")
            else:
                logger.info(f"📝 DEBUG: Same blog update: Article stays in blog {current_blog_id}")
            is_blog_change = False
        
        # Convert and transform payload for Shopify API
        raw_data = shopify_data.model_dump(exclude_unset=True)
        logger.info(f"🔍 DEBUG: Raw payload received: {raw_data}")
        
        update_dict = {}
        
        for field, value in raw_data.items():
            if value is not None:
                logger.info(f"🔍 DEBUG: Processing field '{field}' = {value} (type: {type(value).__name__})")
                # Transform fields to match Shopify API expectations
                if field == "content":
                    # Map 'content' to 'body_html' for Shopify
                    update_dict["body_html"] = value
                    logger.info(f"✅ DEBUG: Mapped 'content' -> 'body_html': {len(str(value))} chars")
                elif field == "tags" and isinstance(value, list):
                    # Convert tags array to comma-separated string
                    update_dict["tags"] = ", ".join(value)
                    logger.info(f"✅ DEBUG: Converted tags array to string: '{update_dict['tags']}'")
                elif field == "status":
                    # Map status to published boolean
                    update_dict["published"] = (value == "published")
                    logger.info(f"✅ DEBUG: Mapped status '{value}' -> published: {update_dict['published']}")
                elif field in ["blog_id", "image_url"]:
                    # Skip these fields - handle separately
                    logger.info(f"⏭️ DEBUG: Skipping field '{field}' (handled separately)")
                    continue
                else:
                    # Keep other fields as-is
                    update_dict[field] = value
                    logger.info(f"✅ DEBUG: Added field '{field}': {value}")
        
        logger.info(f"🔍 DEBUG: Final update_dict for Shopify: {update_dict}")
        
        if not update_dict:
            raise HTTPException(status_code=400, detail="No valid data provided for update")
        
        # Handle featured image if provided
        image_url = None
        if hasattr(shopify_data, 'image_url') and shopify_data.image_url:
            image_url = shopify_data.image_url
            logger.info(f"📷 Adding featured image to Shopify update: {image_url}")
        
        if is_blog_change:
            # Create article in new blog (category change)
            logger.info(f"📝 Creating article in new blog {target_blog_id} with updated data")
            
            # Merge current article data with updates
            create_data = {
                "title": update_dict.get("title", current_article.get("title", "")),
                "body_html": update_dict.get("body_html", current_article.get("content", "")),
                "tags": update_dict.get("tags", ", ".join(current_article.get("tags", []))),
                "author": update_dict.get("author", current_article.get("author", "")),
                "summary": update_dict.get("summary", current_article.get("excerpt", "")),
                "published": update_dict.get("published", current_article.get("status") == "publish"),
                "handle": update_dict.get("handle", current_article.get("metadata", {}).get("shopify_handle", ""))
            }
            
            # Create new article in target blog
            updated_article = shopify_service.create_article(
                blog_id=target_blog_id,
                title=create_data["title"],
                content=create_data["body_html"],
                tags=create_data["tags"],
                author=create_data["author"],
                summary=create_data["summary"],
                published=create_data["published"],
                handle=create_data["handle"],
                image_url=image_url
            )
            
            if updated_article:
                logger.info(f"✅ Article successfully created in new blog {target_blog_id}")
            else:
                raise HTTPException(status_code=500, detail="Failed to create article in new blog")
                
        else:
            # Same blog, regular update
            logger.info(f"📝 DEBUG: Updating article {shopify_article_id} in same blog {target_blog_id}")
            logger.info(f"📝 DEBUG: Update data being sent to Shopify: {update_dict}")
            logger.info(f"📝 DEBUG: Image URL: {image_url}")
            
            updated_article = shopify_service.update_article(
                blog_id=target_blog_id,
                article_id=shopify_article_id,
                update_data=update_dict,
                image_url=image_url
            )
            
            logger.info(f"📝 DEBUG: Shopify service returned: {updated_article is not None}")
            if updated_article:
                logger.info(f"📝 DEBUG: Updated article title: {updated_article.get('title', 'No title')}")
            else:
                logger.error(f"❌ DEBUG: Shopify service returned None - update failed")
        
        if not updated_article:
            raise HTTPException(status_code=404, detail="Shopify article not found or update failed")
        
        logger.info(f"✅ Shopify article updated successfully")
        
        return JSONResponse(
            content={
                "status": "success",
                "data": serialize_blog(updated_article)
            },
            status_code=200
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error updating Shopify blog: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update Shopify blog: {str(e)}"
        )

@router.get("")
def get_blogs(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page (max 100)"),
    search: Optional[str] = Query(None, description="Search blogs by title"),
    current_user = Depends(verify_request_origin),
    mongo_db = Depends(get_mongodb)
):
    """Get all blogs for a project"""
    try:
        logger.info("Getting blogs for user")
        logger.info(datetime.now(pytz.timezone('Asia/Kolkata')))
        user_id = current_user.id
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID not provided")
        
        project_id_str = str(project_id)
        logger.info(f"Getting blogs for user {user_id} in project {project_id}")
        
        # Verify project access and detect CMS
        project = None
        connected_cms = None
        cms_details = None
        with get_db_session() as db:
            project = verify_project_access(project_id, user_id, db)
            # Detect connected CMS
            connected_cms = CMSDetectorService.detect_cms(project_id_str, db)
            
            # Get detailed CMS connection info (same as CMS API)
            cms_details = {
                "connected_cms": connected_cms,
                "wordpress_connected": False,
                "wordpress_url": None,
                "wordpress_username": None,
                "cms_config": project.cms_config if project.cms_config else {}
            }
            
            # Get WordPress connection details
            if connected_cms == "wordpress":
                from app.models.wordpress_credentials import WordPressCredentials
                wp_creds = db.query(WordPressCredentials).filter(
                    WordPressCredentials.project_id == project_id
                ).first()
                
                if wp_creds:
                    cms_details.update({
                        "wordpress_connected": True,
                        "wordpress_url": wp_creds.base_url,
                        "wordpress_username": wp_creds.username
                    })
        
        # Calculate fixed split: half from each source
        rayo_limit = per_page // 2
        wp_limit = per_page - rayo_limit  # Remaining to WordPress
        
        logger.info(f"📊 Split strategy: {rayo_limit} Rayo + {wp_limit} WordPress = {per_page} total")
        
        # Log search parameter
        if search:
            logger.info(f"🔍 Search query: '{search}'")
        
        # Direct fetch from database (Redis caching removed)
        logger.info(f"🗄️ Fetching blogs from MongoDB for project {project_id_str}")
        
        try:
            collection = mongo_db[COLLECTION_NAME]
            
            # Query for filtering (with search support)
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
                logger.info(f"📝 Excluding published Rayo blogs from MongoDB results ({connected_cms} CMS connected)")
            
            # Add search filter for MongoDB (case-insensitive title search)
            if search:
                query["title"] = {"$regex": search, "$options": "i"}
                logger.info(f"🔍 MongoDB search query: {query}")
            else:
                logger.info(f"📋 MongoDB query (no search): {query}")
            
            # Log query behavior
            if connected_cms in ["wordpress", "shopify"]:
                logger.info(f"📝 Query will exclude published Rayo blogs (status=publish/published) since {connected_cms} is connected")
            else:
                logger.info("📝 Query will include all Rayo blogs since no CMS is connected")
            
            # Projection for specific fields
            projection = {
                "_id": 1,
                "title": 1,
                "project_id": 1,
                "user_id": 1,
                "is_active": 1,
                "created_at": 1,
                "updated_at": 1,
                "category": 1,
                "step_tracking": 1,
                "source": 1,
                "words_count": 1,
                "status": 1,
                "step_tracking": {
                    "current_step": 1,
                },
            }
            
            # Get total count for pagination metadata
            total_count = collection.count_documents(query)
            
            # Calculate pagination for Rayo blogs (using fixed split)
            skip = (page - 1) * rayo_limit
            
            # Get paginated Rayo blogs (fast approach)
            cursor = collection.find(query, projection) \
                              .sort("updated_at", -1) \
                              .skip(skip) \
                              .limit(rayo_limit) \
                              .max_time_ms(120000)  # 120 second timeout
            
            logger.info(f"Cursor created for page {page} with rayo_limit {rayo_limit}")
            
            blogs = []
            for blog in cursor:
                blog["id"] = str(blog.pop("_id"))
                blogs.append(serialize_blog(blog))
            
            if search:
                logger.info(f"📊 Retrieved {len(blogs)} Rayo blogs matching '{search}' out of {total_count} total from MongoDB")
            else:
                logger.info(f"📊 Retrieved {len(blogs)} Rayo blogs out of {total_count} total from MongoDB")
            
            # Fetch CMS blogs with same pagination (fast approach)
            cms_blogs = []
            cms_total_count = 0
            if connected_cms == "wordpress":
                logger.info(f"🔗 WordPress CMS detected, fetching paginated WordPress blogs...")
                logger.info(f"🔍 DEBUG: connected_cms = {connected_cms}")
                try:
                    with get_db_session() as db:
                        logger.info(f"🔍 DEBUG: Creating WordPress service for project {project_id_str}")
                        wp_service = WordPressBlogService.from_project(project_id_str, db)
                        logger.info(f"🔍 DEBUG: WordPress service created: {wp_service is not None}")
                        
                        if wp_service:
                            if search:
                                logger.info(f"🔍 DEBUG: Calling wp_service.get_posts(page={page}, per_page={wp_limit}, search='{search}', status='any')")
                                # Fetch ALL WordPress blogs with search (any status)
                                wp_result = wp_service.get_posts(page=page, per_page=wp_limit, status="any", search=search)
                            else:
                                logger.info(f"🔍 DEBUG: Calling wp_service.get_posts(page={page}, per_page={wp_limit}, status='any')")
                                # Fetch ALL WordPress blogs (any status)
                                wp_result = wp_service.get_posts(page=page, per_page=wp_limit, status="any")
                            logger.info(f"🔍 DEBUG: WordPress API result: {wp_result}")
                            
                            if wp_result and wp_result.get('posts'):
                                wp_blogs = wp_result['posts']
                                
                                # Get total count from WordPress API pagination info
                                pagination_info = wp_result.get('pagination', {})
                                wp_total_count = pagination_info.get('total_posts', len(wp_blogs))
                                
                                if search:
                                    logger.info(f"📊 Retrieved {len(wp_blogs)} WordPress blogs matching '{search}' (page {page})")
                                    logger.info(f"📊 WordPress API reports total matching posts: {wp_total_count}")
                                else:
                                    logger.info(f"📊 Retrieved {len(wp_blogs)} WordPress blogs (page {page})")
                                    logger.info(f"📊 WordPress API reports total posts: {wp_total_count}")
                                
                                # Update cms_blogs and cms_total_count for generic use
                                cms_blogs = wp_blogs
                                cms_total_count = wp_total_count
                            else:
                                logger.warning(f"🔍 DEBUG: No WordPress posts returned. wp_result: {wp_result}")
                        else:
                            logger.warning(f"Failed to create WordPress service for project {project_id_str}")
                            logger.warning(f"🔍 DEBUG: WordPress credentials might be missing or invalid")
                except Exception as wp_error:
                    logger.error(f"Error fetching WordPress blogs: {str(wp_error)}")
                    logger.error(f"🔍 DEBUG: WordPress error details: {wp_error}", exc_info=True)
            elif connected_cms == "shopify":
                logger.info(f"🔗 Shopify CMS detected, fetching paginated Shopify blogs...")
                logger.info(f"🔍 DEBUG: connected_cms = {connected_cms}")
                try:
                    with get_db_session() as db:
                        logger.info(f"🔍 DEBUG: Creating Shopify service for project {project_id_str}")
                        
                        # Get Shopify credentials
                        shopify_creds = db.query(ShopifyCredentials).filter(
                            ShopifyCredentials.project_id == project_id_str
                        ).first()
                        
                        if shopify_creds:
                            shopify_service = ShopifyService(
                                shop_domain=shopify_creds.shop_domain,
                                access_token=shopify_creds.access_token,
                                api_version=shopify_creds.api_version
                            )
                            logger.info(f"🔍 DEBUG: Shopify service created: {shopify_service is not None}")
                            
                            # Calculate Shopify-specific limit (50% split)  
                            shopify_limit = wp_limit
                            
                            # First check if there are any blogs in the store
                            logger.info(f"🔍 DEBUG: Checking for available blogs in Shopify store...")
                            available_blogs = shopify_service.get_blogs()
                            logger.info(f"🔍 DEBUG: Available Shopify blogs: {available_blogs}")
                            
                            if not available_blogs:
                                logger.warning(f"⚠️  No blogs found in Shopify store. Cannot fetch articles.")
                                shopify_result = {'posts': [], 'pagination': None}
                            else:
                                logger.info(f"🔍 DEBUG: Found {len(available_blogs)} blog(s) in Shopify store")
                                
                                if search:
                                    logger.info(f"🔍 DEBUG: Shopify doesn't support direct search, will fetch all and filter")
                                    # Note: Shopify API doesn't support search, so we'll get all posts and filter later
                                    shopify_result = shopify_service.get_posts(limit=shopify_limit, page=page)
                                else:
                                    logger.info(f"🔍 DEBUG: Calling shopify_service.get_posts(limit={shopify_limit}, page={page})")
                                    shopify_result = shopify_service.get_posts(limit=shopify_limit, page=page)
                            
                            logger.info(f"🔍 DEBUG: Shopify API result: {shopify_result}")
                            
                            if shopify_result and shopify_result.get('posts'):
                                shopify_blogs = shopify_result['posts']
                                
                                # Apply search filter if needed (client-side since Shopify doesn't support search)
                                if search:
                                    filtered_blogs = []
                                    search_lower = search.lower()
                                    for blog in shopify_blogs:
                                        title = blog.get('title', '').lower()
                                        content = blog.get('content', '').lower() if blog.get('content') else ''
                                        excerpt = blog.get('excerpt', '').lower() if blog.get('excerpt') else ''
                                        
                                        if (search_lower in title or search_lower in content or search_lower in excerpt):
                                            filtered_blogs.append(blog)
                                    
                                    shopify_blogs = filtered_blogs
                                    logger.info(f"📊 Filtered {len(shopify_blogs)} Shopify blogs matching '{search}' from {len(shopify_result['posts'])} total")
                                
                                # Get total count from pagination info (approximate for search)
                                pagination_info = shopify_result.get('pagination', {})
                                if search:
                                    # For search, we can't get accurate total count from Shopify
                                    shopify_total_count = len(shopify_blogs)
                                else:
                                    # Use pagination info to estimate total
                                    if pagination_info.get('has_next'):
                                        shopify_total_count = page * shopify_limit + 1  # At least one more page
                                    else:
                                        shopify_total_count = (page - 1) * shopify_limit + len(shopify_blogs)
                                
                                if search:
                                    logger.info(f"📊 Retrieved {len(shopify_blogs)} Shopify blogs matching '{search}' (page {page})")
                                    logger.info(f"📊 Shopify search results count: {shopify_total_count}")
                                else:
                                    logger.info(f"📊 Retrieved {len(shopify_blogs)} Shopify blogs (page {page})")
                                    logger.info(f"📊 Shopify estimated total posts: {shopify_total_count}")
                                
                                # Update cms_blogs and cms_total_count for generic use
                                cms_blogs = shopify_blogs
                                cms_total_count = shopify_total_count
                            else:
                                logger.warning(f"🔍 DEBUG: No Shopify posts returned. shopify_result: {shopify_result}")
                        else:
                            logger.warning(f"Failed to find Shopify credentials for project {project_id_str}")
                            logger.warning(f"🔍 DEBUG: Shopify credentials might be missing or invalid")
                except Exception as shopify_error:
                    logger.error(f"Error fetching Shopify blogs: {str(shopify_error)}")
                    logger.error(f"🔍 DEBUG: Shopify error details: {shopify_error}", exc_info=True)
            else:
                logger.info(f"🔍 DEBUG: No CMS detected. connected_cms = {connected_cms}")
            
            # Merge and sort the limited blogs from both sources (fast approach)
            all_blogs = blogs + cms_blogs
            
            def safe_sort_key(blog):
                """Safe sorting key that handles both string and datetime objects"""
                updated_at = blog.get('updated_at')
                if not updated_at:
                    return datetime.min.replace(tzinfo=pytz.UTC)
                
                # If it's already a datetime object, return it
                if isinstance(updated_at, datetime):
                    return updated_at
                
                # If it's a string, try to parse it
                if isinstance(updated_at, str):
                    try:
                        # Try parsing ISO format
                        if 'T' in updated_at:
                            return datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                        else:
                            return datetime.fromisoformat(updated_at)
                    except:
                        return datetime.min.replace(tzinfo=pytz.UTC)
                
                return datetime.min.replace(tzinfo=pytz.UTC)
            
            # Sort the merged blogs (only current page from each source)
            all_blogs.sort(key=safe_sort_key, reverse=True)
            
            # Serialize all blogs to ensure JSON compatibility
            paginated_blogs = []
            for blog in all_blogs:
                serialized_blog = serialize_blog(blog)
                paginated_blogs.append(serialized_blog)
            
            if search:
                logger.info(f"📊 Search results: {len(paginated_blogs)} blogs matching '{search}' (Rayo: {len(blogs)}, {connected_cms.capitalize() if connected_cms else 'CMS'}: {len(cms_blogs)})")
            else:
                logger.info(f"📊 Fast merge: {len(paginated_blogs)} blogs (Rayo: {len(blogs)}, {connected_cms.capitalize() if connected_cms else 'CMS'}: {len(cms_blogs)})")
            
            # Calculate metadata for fixed split approach
            total_merged_count = total_count + cms_total_count  # Sum of totals from both sources
            merged_total_pages = math.ceil(total_merged_count / per_page) if total_merged_count > 0 else 0
            
            logger.info(f"📊 Total available blogs: {total_merged_count} (Rayo: {total_count}, {connected_cms.capitalize() if connected_cms else 'CMS'}: {cms_total_count})")
            
            # Get detailed CMS connection info (same as CMS API)
            cms_details = {
                "connected_cms": connected_cms,
                "wordpress_connected": False,
                "wordpress_url": None,
                "wordpress_username": None,
                "shopify_connected": False,
                "shopify_domain": None,
                "shopify_api_version": None,
                "gsc_connected": False,
                "gsc_sites": [],
                "cms_config": {}
            }
            
            # Get WordPress connection details
            if connected_cms == "wordpress":
                with get_db_session() as db:
                    from app.models.wordpress_credentials import WordPressCredentials
                    from app.models.gsc import GSCAccount
                    
                    # Get project for cms_config
                    project = db.query(Project).filter(Project.id == project_id).first()
                    if project and project.cms_config:
                        cms_details["cms_config"] = project.cms_config
                    
                    # Get WordPress credentials
                    wp_creds = db.query(WordPressCredentials).filter(
                        WordPressCredentials.project_id == project_id
                    ).first()
                    
                    if wp_creds:
                        cms_details.update({
                            "wordpress_connected": True,
                            "wordpress_url": wp_creds.base_url,
                            "wordpress_username": wp_creds.username
                        })
                    
                    # Check GSC connections for this project
                    gsc_accounts = db.query(GSCAccount).filter(
                        GSCAccount.project_id == project_id
                    ).all()
                    
                    if gsc_accounts:
                        cms_details.update({
                            "gsc_connected": True,
                            "gsc_sites": [account.site_url for account in gsc_accounts]
                        })
            elif connected_cms == "shopify":
                with get_db_session() as db:
                    from app.models.gsc import GSCAccount
                    
                    # Get project for cms_config
                    project = db.query(Project).filter(Project.id == project_id).first()
                    if project and project.cms_config:
                        cms_details["cms_config"] = project.cms_config
                    
                    # Get Shopify credentials
                    shopify_creds = db.query(ShopifyCredentials).filter(
                        ShopifyCredentials.project_id == project_id
                    ).first()
                    
                    if shopify_creds:
                        cms_details.update({
                            "shopify_connected": True,
                            "shopify_domain": shopify_creds.shop_domain,
                            "shopify_api_version": shopify_creds.api_version
                        })
                    
                    # Check GSC connections for this project
                    gsc_accounts = db.query(GSCAccount).filter(
                        GSCAccount.project_id == project_id
                    ).all()
                    
                    if gsc_accounts:
                        cms_details.update({
                            "gsc_connected": True,
                            "gsc_sites": [account.site_url for account in gsc_accounts]
                        })
            
            # Create pagination metadata with detailed CMS info
            meta = {
                "total_count": total_merged_count,  # Total across both sources
                "total_pages": merged_total_pages,
                "current_page": page,
                "per_page": per_page,
                "has_next": page < merged_total_pages,
                "has_previous": page > 1,
                "rayo_blogs_count": total_count,  # Total Rayo blogs available
                "cms_blogs_count": cms_total_count,  # Total CMS blogs available
                **cms_details  # Include detailed CMS connection information
            }
            
            logger.info(f"🔍 DEBUG: Final meta object:")
            logger.info(f"🔍 DEBUG: - total_count: {total_merged_count}")
            logger.info(f"🔍 DEBUG: - rayo_blogs_count: {total_count}")
            logger.info(f"🔍 DEBUG: - cms_blogs_count: {cms_total_count}")
            logger.info(f"🔍 DEBUG: - connected_cms: {connected_cms}")
            
            # Create response (no caching)
            response_data = {
                "status": "success",
                "data": paginated_blogs,
                "meta": meta
            }
            
            return JSONResponse(content=response_data)
                
        except Exception as mongo_error:
            logger.error(f"MongoDB error in get_blogs: {str(mongo_error)}")
            logger.exception(mongo_error)  # Log full traceback
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch blogs from MongoDB: {str(mongo_error)}"
            )
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in get_blogs: {str(e)}")
        logger.exception(e)  # Log full traceback
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error occurred: {str(e)}"
        )

@router.get("/{blog_id}")
def get_blog(
    request: Request,
    blog_id: str,
    wordpress: Optional[str] = Query(None, description="Add this parameter for WordPress blogs"),
    shopify: Optional[str] = Query(None, description="Add this parameter for Shopify blogs"),
    source: Optional[str] = Query(None, description="Blog source: 'shopify' for Shopify blogs"),
    current_user = Depends(verify_request_origin),
    mongo_db = Depends(get_mongodb)
):
    """Get a specific blog by ID - supports Rayo, WordPress, and Shopify blogs
    
    Examples:
    - Rayo blog: GET /blog/64f1a2b3c4d5e6f7g8h9i0j1
    - WordPress blog: GET /blog/56547?wordpress
    - Shopify blog: GET /blog/610649145641?shopify
    - Shopify blog: GET /blog/610649145641?source=shopify
    """
    try:
        user_id = current_user.id
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID not provided")
            
        project_id_str = str(project_id)
        
        # Determine blog source based on parameters
        is_wordpress = wordpress is not None
        is_shopify = (shopify is not None) or (source == "shopify")
        
        logger.info(f"🔍 DEBUG: shopify parameter = '{shopify}', source parameter = '{source}', is_shopify = {is_shopify}")
        logger.info(f"🔍 DEBUG: wordpress parameter = '{wordpress}', is_wordpress = {is_wordpress}")
        
        if is_wordpress and is_shopify:
            raise HTTPException(status_code=400, detail="Cannot specify both wordpress and shopify source")
        
        if is_shopify:
            source_type = "Shopify"
        elif is_wordpress:
            source_type = "WordPress"
        else:
            source_type = "Rayo"
            
        logger.info(f"Getting {source_type} blog {blog_id} for user {user_id} in project {project_id}")
        
        # Verify project access first
        project = None
        connected_cms = None
        with get_db_session() as db:
            project = verify_project_access(project_id, user_id, db)
            
            # Check CMS connection for WordPress/Shopify blogs
            if is_wordpress or is_shopify:
                connected_cms = CMSDetectorService.detect_cms(project_id_str, db)
                expected_cms = "wordpress" if is_wordpress else "shopify"
                
                if connected_cms != expected_cms:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"{expected_cms.capitalize()} CMS not connected to this project"
                    )
        
        logger.info(f"🔍 DEBUG: Routing decision - is_wordpress: {is_wordpress}, is_shopify: {is_shopify}")
        
        if is_wordpress:
            # Handle WordPress blog fetching
            logger.info("✅ Starting WordPress blog fetch operation")
            return get_wordpress_blog_individual(blog_id, project_id_str, user_id)
        elif is_shopify:
            # Handle Shopify blog fetching
            logger.info("✅ Starting Shopify blog fetch operation")
            return get_shopify_blog_individual(blog_id, project_id_str, user_id)
        else:
            # Handle Rayo blog fetching (existing logic)
            logger.info("✅ Starting MongoDB fetch operation")
            return get_rayo_blog_individual(blog_id, project_id_str, user_id, mongo_db)
            
    except HTTPException as he:
        logger.error(f"HTTP error in get_blog: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in get_blog: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch blog: {str(e)}"
        )
    finally:
        logger.info("Finally ran the get_blog function")


def get_rayo_blog_individual(blog_id: str, project_id_str: str, user_id: str, mongo_db) -> JSONResponse:
    """Fetch individual Rayo blog from MongoDB"""
    try:
        # MongoDB query for Rayo blogs
        blog = mongo_db[COLLECTION_NAME].find_one(
            {
                "_id": ObjectId(blog_id),
                "project_id": project_id_str,
                "$or": [
                    {"is_active": True},
                    {"is_active": {"$exists": False}}
                ]
            },
            max_time_ms=60000  # 60 second timeout
        )
        
        if not blog:
            logger.info(f"Rayo blog {blog_id} not found")
            raise HTTPException(status_code=404, detail="Blog not found")
        
        logger.info(f"Rayo blog {blog_id} found, preparing response")
        blog["id"] = str(blog.pop("_id"))
        serialized_blog = serialize_blog(blog)

        return JSONResponse(
            content={
                "status": "success",
                "data": serialized_blog
            },
            status_code=200
        )
        
    except Exception as mongo_error:
        logger.error(f"MongoDB error during Rayo blog fetch: {str(mongo_error)}")
        if "timed out" in str(mongo_error).lower():
            raise HTTPException(
                status_code=504,
                detail="Database operation timed out"
            )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch blog from MongoDB: {str(mongo_error)}"
        )


def get_wordpress_blog_individual(blog_id: str, project_id_str: str, user_id: str) -> JSONResponse:
    """Fetch individual WordPress blog via WordPress API"""
    try:
        # Create WordPress service
        with get_db_session() as db:
            wp_service = WordPressBlogService.from_project(project_id_str, db)
            if not wp_service:
                raise HTTPException(
                    status_code=500, 
                    detail="Failed to initialize WordPress service"
                )
        
        # Convert blog_id to integer for WordPress API
        try:
            wp_post_id = int(blog_id)
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail="Invalid WordPress blog ID format"
            )
        
        # Fetch WordPress blog by ID
        logger.info(f"Fetching WordPress blog {wp_post_id}")
        wp_blog = wp_service.get_post_by_id(wp_post_id)
        
        if not wp_blog:
            logger.info(f"WordPress blog {wp_post_id} not found")
            raise HTTPException(status_code=404, detail="WordPress blog not found")
        
        logger.info(f"WordPress blog {wp_post_id} found, preparing response")
        
        # Serialize WordPress blog (handle datetime objects)
        serialized_blog = serialize_blog(wp_blog)
        
        return JSONResponse(
            content={
                "status": "success",
                "data": serialized_blog
            },
            status_code=200
        )
        
    except HTTPException as he:
        raise he
    except Exception as wp_error:
        logger.error(f"WordPress error during blog fetch: {str(wp_error)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch WordPress blog: {str(wp_error)}"
        )


def get_shopify_blog_individual(blog_id: str, project_id_str: str, user_id: str) -> JSONResponse:
    """Fetch individual Shopify blog via Shopify API - Fast & Optimized"""
    try:
        # Get Shopify credentials and create service
        with get_db_session() as db:
            shopify_creds = db.query(ShopifyCredentials).filter(
                ShopifyCredentials.project_id == project_id_str
            ).first()
            
            if not shopify_creds:
                raise HTTPException(status_code=404, detail="Shopify not connected to this project")
            
            # Create Shopify service  
            shopify_service = ShopifyService(
                shop_domain=shopify_creds.shop_domain,
                access_token=shopify_creds.access_token,
                api_version=shopify_creds.api_version
            )
        
        # Parse blog_id format: Could be "article_id" or "blog_id_article_id" 
        # For performance, we need to handle both cases efficiently
        if '_' in blog_id:
            # Format: blog_id_article_id (e.g., "116827586857_123456")
            try:
                blog_id_part, article_id_part = blog_id.split('_', 1)
                shopify_blog_id = int(blog_id_part) 
                shopify_article_id = int(article_id_part)
            except (ValueError, IndexError):
                raise HTTPException(status_code=400, detail="Invalid Shopify blog ID format")
        else:
            # Format: just article_id - need to find which blog it belongs to
            try:
                shopify_article_id = int(blog_id)
                # Get first blog as fallback (performance optimization)
                blogs = shopify_service.get_blogs()
                if not blogs:
                    raise HTTPException(status_code=404, detail="No Shopify blogs found")
                shopify_blog_id = blogs[0]['id']  # Use first blog for performance
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid Shopify article ID format")
        
        # Fetch Shopify article by ID
        logger.info(f"Fetching Shopify article {shopify_article_id} from blog {shopify_blog_id}")
        shopify_blog = shopify_service.get_post_by_id(
            blog_id=shopify_blog_id, 
            article_id=shopify_article_id
        )
        
        if not shopify_blog:
            logger.info(f"Shopify article {shopify_article_id} not found")
            raise HTTPException(status_code=404, detail="Shopify blog not found")
        
        logger.info(f"Shopify article {shopify_article_id} found, preparing response")
        
        # Serialize Shopify blog (already handled in transform method)
        serialized_blog = serialize_blog(shopify_blog)
        
        return JSONResponse(
            content={
                "status": "success",
                "data": serialized_blog
            },
            status_code=200
        )

    except HTTPException as he:
        raise he
    except Exception as shopify_error:
        logger.error(f"Shopify error during blog fetch: {str(shopify_error)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch Shopify blog: {str(shopify_error)}"
        )

@router.get("/{blog_id}/versions")
def get_blog_content_versions(
    request: Request,
    blog_id: str,
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    limit: int = Query(3, ge=1, le=6, description="Items per page (max 6)"),
    current_user = Depends(verify_request_origin),
    mongo_db = Depends(get_mongodb)
):
    """
    Get all content versions for a Rayo blog with pagination.
    Returns the version history of blog content from latest to oldest.

    Query Parameters:
    - page: Page number (default: 1, min: 1)
    - limit: Items per page (default: 3, max: 6)

    Example: GET /projects/{project_id}/blog/64f1a2b3c4d5e6f7g8h9i0j1/versions?page=1&limit=3

    Response:
    {
        "status": "success",
        "data": {
            "blog_id": "64f1a2b3...",
            "title": "Blog Title",
            "total_versions": 5,
            "page": 1,
            "limit": 3,
            "total_pages": 2,
            "versions": [
                {
                    "version": 5,
                    "html": "<p>Latest version...</p>",
                    "words_count": 120,
                    "tag": "updated",
                    "saved_at": "2024-01-15T10:00:00+05:30"
                },
                ...
            ]
        }
    }
    """
    try:
        user_id = current_user.id
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID not provided")

        project_id_str = str(project_id)

        logger.info(f"Getting content versions for Rayo blog {blog_id} in project {project_id}")

        # Verify project access
        with get_db_session() as db:
            project = verify_project_access(project_id, user_id, db)

        # Fetch blog from MongoDB
        blog = mongo_db[COLLECTION_NAME].find_one(
            {
                "_id": ObjectId(blog_id),
                "project_id": project_id_str,
                "$or": [
                    {"is_active": True},
                    {"is_active": {"$exists": False}}
                ]
            },
            max_time_ms=60000
        )

        if not blog:
            logger.info(f"Blog {blog_id} not found")
            raise HTTPException(status_code=404, detail="Blog not found")

        # Extract content array (all versions)
        content_array = blog.get("content", [])

        # Handle backward compatibility - if content is a string, return empty array
        if isinstance(content_array, str):
            logger.warning(f"Blog {blog_id} has old content format (string). No versions available.")
            content_array = []

        # Serialize datetime objects in version array
        all_versions = []
        for version in content_array:
            if isinstance(version, dict):
                serialized_version = {
                    "version": version.get("version"),
                    "html": version.get("html"),
                    "words_count": version.get("words_count"),
                    "tag": version.get("tag"),
                    "saved_at": serialize_datetime(version.get("saved_at"))
                }
                all_versions.append(serialized_version)

        # Reverse to show latest first (newest to oldest)
        all_versions.reverse()

        # Calculate pagination
        total_versions = len(all_versions)
        total_pages = (total_versions + limit - 1) // limit  # Ceiling division
        start_index = (page - 1) * limit
        end_index = start_index + limit

        # Get paginated versions
        paginated_versions = all_versions[start_index:end_index]

        logger.info(f"✅ Found {total_versions} content versions for blog {blog_id}, returning page {page}/{total_pages}")

        # Get title - handle both array and string formats
        title = blog.get("title", "")
        if isinstance(title, list) and title:
            title = title[-1]

        response_data = {
            "blog_id": str(blog["_id"]),
            "title": title,
            "total_versions": total_versions,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "versions": paginated_versions
        }

        return JSONResponse(
            content={
                "status": "success",
                "data": response_data
            },
            status_code=200
        )

    except HTTPException as he:
        logger.error(f"HTTP error in get_blog_content_versions: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in get_blog_content_versions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch content versions: {str(e)}"
        )

@router.delete("/{blog_id}")
async def delete_blog(
    request: Request,
    blog_id: str,
    wordpress: Optional[str] = Query(None, description="Add this parameter for WordPress blogs"),
    current_user = Depends(verify_request_origin),
    mongo_db = Depends(get_mongodb)
):
    """
    Delete a blog - supports both Rayo and WordPress blogs
    
    Examples:
    - Rayo blog: DELETE /blog/64f1a2b3c4d5e6f7g8h9i0j1
    - WordPress blog: DELETE /blog/56547?wordpress
    """
    try:
        user_id = current_user.id
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID is required")
        
        project_id_str = str(project_id)
        
        # Determine blog source - just check if 'wordpress' parameter exists
        is_wordpress = wordpress is not None
        source_type = "WordPress" if is_wordpress else "Rayo"
        logger.info(f"Deleting {source_type} blog {blog_id} for user {user_id} in project {project_id}")
        
        # Verify project access first
        project = None
        connected_cms = None
        with get_db_session() as db:
            project = verify_project_access(project_id, user_id, db)
            if is_wordpress:
                # Also detect connected CMS for WordPress blogs
                connected_cms = CMSDetectorService.detect_cms(project_id_str, db)
                if connected_cms != "wordpress":
                    raise HTTPException(
                        status_code=400, 
                        detail="WordPress CMS not connected to this project"
                    )
        
        if is_wordpress:
            # Handle WordPress blog deletion
            logger.info("Starting WordPress blog delete operation")
            return await delete_wordpress_blog(blog_id, project_id_str, user_id)
        else:
            # Handle Rayo blog deletion (existing logic)
            logger.info("Starting MongoDB blog delete operation")
            return delete_rayo_blog(blog_id, project_id_str, user_id, mongo_db)

    except HTTPException as he:
        logger.error(f"HTTP error in delete_blog: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in delete_blog: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete blog: {str(e)}"
        )


def delete_rayo_blog(blog_id: str, project_id_str: str, user_id: str, mongo_db) -> JSONResponse:
    """Delete/soft delete Rayo blog from MongoDB"""
    try:
        # Get the blog collection
        blogs_collection = mongo_db.blogs

        # Check if blog exists and belongs to the project
        blog = blogs_collection.find_one({
            "_id": ObjectId(blog_id),
            "project_id": project_id_str,
            # "is_active": True
        })
        
        if not blog:
            logger.info(f"Rayo blog {blog_id} not found")
            raise HTTPException(status_code=404, detail="Blog not found")

        # Update the blog to set is_active=False (soft delete)
        result = blogs_collection.update_one(
            {"_id": ObjectId(blog_id)},
            {
                "$set": {
                    "is_active": False,
                    "updated_at": get_current_ist_time()
                }
            }
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to delete blog")

        logger.info(f"✅ Rayo blog {blog_id} soft deleted successfully")

        return JSONResponse(
            status_code=200,
            content={"message": "Rayo blog deleted successfully"}
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error deleting Rayo blog: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete Rayo blog: {str(e)}"
        )


async def delete_wordpress_blog(blog_id: str, project_id_str: str, user_id: str) -> JSONResponse:
    """Delete WordPress blog via WordPress API"""
    try:
        # Create WordPress service
        with get_db_session() as db:
            wp_service = WordPressBlogService.from_project(project_id_str, db)
            if not wp_service:
                raise HTTPException(
                    status_code=500, 
                    detail="Failed to initialize WordPress service"
                )
        
        # Convert blog_id to integer for WordPress API
        try:
            wp_post_id = int(blog_id)
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail="Invalid WordPress blog ID format"
            )
        
        # Delete WordPress blog
        logger.info(f"Deleting WordPress blog {wp_post_id}")
        success = wp_service.delete_post_by_id(wp_post_id)
        
        if not success:
            logger.info(f"WordPress blog {wp_post_id} not found or couldn't be deleted")
            raise HTTPException(status_code=404, detail="WordPress blog not found or couldn't be deleted")
        
        logger.info(f"WordPress blog {wp_post_id} deleted successfully")
        
        logger.info(f"✅ WordPress blog {wp_post_id} deleted successfully")
        
        return JSONResponse(
            status_code=200,
            content={"message": "WordPress blog deleted successfully"}
        )
        
    except HTTPException as he:
        raise he
    except Exception as wp_error:
        logger.error(f"WordPress error during blog deletion: {str(wp_error)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete WordPress blog: {str(wp_error)}"
        )


@router.get("/wordpress/categories")
def get_wordpress_categories(
    request: Request,
    current_user = Depends(verify_request_origin)
):
    """Get all WordPress categories from connected CMS"""
    try:
        user_id = current_user.id
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID not provided")
        
        project_id_str = str(project_id)
        logger.info(f"Getting WordPress categories for user {user_id} in project {project_id}")
        
        # Verify project access and CMS connection
        with get_db_session() as db:
            project = verify_project_access(project_id, user_id, db)
            connected_cms = CMSDetectorService.detect_cms(project_id_str, db)
            
            if connected_cms != "wordpress":
                raise HTTPException(
                    status_code=400, 
                    detail="WordPress CMS not connected to this project"
                )
        
        # Create WordPress service
        with get_db_session() as db:
            wp_service = WordPressBlogService.from_project(project_id_str, db)
            if not wp_service:
                raise HTTPException(
                    status_code=500, 
                    detail="Failed to initialize WordPress service"
                )
        
        # Fetch categories
        logger.info("Fetching WordPress categories")
        categories = wp_service.get_categories()
        
        logger.info(f"Retrieved {len(categories)} WordPress categories")
        
        return JSONResponse(
            content={
                "status": "success",
                "data": categories
            },
            status_code=200
        )
        
    except HTTPException as he:
        logger.error(f"HTTP error in get_wordpress_categories: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in get_wordpress_categories: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch WordPress categories: {str(e)}"
        )


@router.get("/wordpress/tags")  
def get_wordpress_tags(
    request: Request,
    current_user = Depends(verify_request_origin)
):
    """Get all WordPress tags from connected CMS"""
    try:
        user_id = current_user.id
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID not provided")
        
        project_id_str = str(project_id)
        logger.info(f"Getting WordPress tags for user {user_id} in project {project_id}")
        
        # Verify project access and CMS connection
        with get_db_session() as db:
            project = verify_project_access(project_id, user_id, db)
            connected_cms = CMSDetectorService.detect_cms(project_id_str, db)
            
            if connected_cms != "wordpress":
                raise HTTPException(
                    status_code=400, 
                    detail="WordPress CMS not connected to this project"
                )
        
        # Create WordPress service
        with get_db_session() as db:
            wp_service = WordPressBlogService.from_project(project_id_str, db)
            if not wp_service:
                raise HTTPException(
                    status_code=500, 
                    detail="Failed to initialize WordPress service"
                )
        
        # Fetch tags
        logger.info("Fetching WordPress tags")
        tags = wp_service.get_tags()
        
        logger.info(f"Retrieved {len(tags)} WordPress tags")
        
        return JSONResponse(
            content={
                "status": "success",
                "data": tags
            },
            status_code=200
        )
        
    except HTTPException as he:
        logger.error(f"HTTP error in get_wordpress_tags: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in get_wordpress_tags: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch WordPress tags: {str(e)}"
        )


@router.post("/wordpress/upload-image")
async def upload_wordpress_image(
    request: Request,
    file: UploadFile = File(...),
    current_user = Depends(verify_request_origin)
):
    """Upload an image to WordPress media library"""
    try:
        user_id = current_user.id
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID not provided")
        
        project_id_str = str(project_id)
        logger.info(f"Uploading image to WordPress for user {user_id} in project {project_id}")
        logger.info(f"🔍 File details - Name: {file.filename}, Content-Type: {file.content_type}, Size: {file.size}")
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}"
            )
        
        # Validate file size (10MB max)
        max_size = 10 * 1024 * 1024  # 10MB
        if file.size and file.size > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {max_size // (1024*1024)}MB"
            )
        
        # Verify project access and CMS connection
        with get_db_session() as db:
            project = verify_project_access(project_id, user_id, db)
            connected_cms = CMSDetectorService.detect_cms(project_id_str, db)
            
            if connected_cms != "wordpress":
                raise HTTPException(
                    status_code=400, 
                    detail="WordPress CMS not connected to this project"
                )
        
        # Create WordPress service
        with get_db_session() as db:
            wp_service = WordPressBlogService.from_project(project_id_str, db)
            if not wp_service:
                raise HTTPException(
                    status_code=500, 
                    detail="Failed to initialize WordPress service"
                )
        
        # Read file content
        file_content = await file.read()
        logger.info(f"Read {len(file_content)} bytes from uploaded file")
        
        # Upload to WordPress
        logger.info("Uploading image to WordPress media library")
        uploaded_image = wp_service.upload_image(
            file_content=file_content,
            filename=file.filename,
            content_type=file.content_type
        )
        
        if not uploaded_image:
            raise HTTPException(
                status_code=500,
                detail="Failed to upload image to WordPress"
            )
        
        logger.info(f"Successfully uploaded image: {uploaded_image['url']}")
        
        return JSONResponse(
            content={
                "status": "success",
                "data": uploaded_image,
                "message": "Image uploaded successfully to WordPress media library"
            },
            status_code=201
        )
        
    except HTTPException as he:
        logger.error(f"HTTP error in upload_wordpress_image: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in upload_wordpress_image: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload image: {str(e)}"
        )


@router.get("/wordpress/authors")  
def get_wordpress_authors(
    request: Request,
    current_user = Depends(verify_request_origin)
):
    """Get all WordPress authors from connected CMS"""
    try:
        user_id = current_user.id
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID not provided")
        
        project_id_str = str(project_id)
        logger.info(f"Getting WordPress authors for user {user_id} in project {project_id}")
        
        # Verify project access and CMS connection
        with get_db_session() as db:
            project = verify_project_access(project_id, user_id, db)
            connected_cms = CMSDetectorService.detect_cms(project_id_str, db)
            
            if connected_cms != "wordpress":
                raise HTTPException(
                    status_code=400, 
                    detail="WordPress CMS not connected to this project"
                )
        
        # Create WordPress service
        with get_db_session() as db:
            wp_service = WordPressBlogService.from_project(project_id_str, db)
            if not wp_service:
                raise HTTPException(
                    status_code=500, 
                    detail="Failed to initialize WordPress service"
                )
        
        # Fetch authors
        logger.info("Fetching WordPress authors")
        authors = wp_service.get_authors()
        
        logger.info(f"Retrieved {len(authors)} WordPress authors")
        
        return JSONResponse(
            content={
                "status": "success",
                "data": authors
            },
            status_code=200
        )
        
    except HTTPException as he:
        logger.error(f"HTTP error in get_wordpress_authors: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in get_wordpress_authors: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch WordPress authors: {str(e)}"
        )


@router.post("/wordpress/categories")
async def create_wordpress_category(
    request: Request,
    current_user = Depends(verify_request_origin)
):
    """Create a new WordPress category"""
    try:
        user_id = current_user.id
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID not provided")
        
        project_id_str = str(project_id)
        logger.info(f"Creating WordPress category for user {user_id} in project {project_id}")
        
        # Verify project access and CMS connection
        with get_db_session() as db:
            project = verify_project_access(project_id, user_id, db)
            connected_cms = CMSDetectorService.detect_cms(project_id_str, db)
            
            if connected_cms != "wordpress":
                raise HTTPException(
                    status_code=400, 
                    detail="WordPress CMS not connected to this project"
                )
        
        # Parse request body
        request_body = await request.json()
        category_name = request_body.get("name")
        
        if not category_name:
            raise HTTPException(status_code=400, detail="Category name is required")
        
        # Create WordPress service and category
        with get_db_session() as db:
            wp_service = WordPressBlogService.from_project(project_id_str, db)
            if not wp_service:
                raise HTTPException(
                    status_code=500, 
                    detail="Failed to initialize WordPress service"
                )
        
        # Use the create_category method (need to add this to WordPressBlogService)
        created_category = wp_service.create_category(category_name)
        
        if not created_category:
            raise HTTPException(status_code=500, detail="Failed to create WordPress category")
        
        logger.info(f"Successfully created WordPress category: {category_name}")
        
        return JSONResponse(
            content={
                "status": "success",
                "data": created_category,
                "message": f"Category '{category_name}' created successfully"
            },
            status_code=201
        )
        
    except HTTPException as he:
        logger.error(f"HTTP error in create_wordpress_category: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in create_wordpress_category: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create WordPress category: {str(e)}"
        )


@router.post("/wordpress/tags")
async def create_wordpress_tag(
    request: Request,
    current_user = Depends(verify_request_origin)
):
    """Create a new WordPress tag"""
    try:
        user_id = current_user.id
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID not provided")
        
        project_id_str = str(project_id)
        logger.info(f"Creating WordPress tag for user {user_id} in project {project_id}")
        
        # Verify project access and CMS connection
        with get_db_session() as db:
            project = verify_project_access(project_id, user_id, db)
            connected_cms = CMSDetectorService.detect_cms(project_id_str, db)
            
            if connected_cms != "wordpress":
                raise HTTPException(
                    status_code=400, 
                    detail="WordPress CMS not connected to this project"
                )
        
        # Parse request body
        request_body = await request.json()
        tag_name = request_body.get("name")
        
        if not tag_name:
            raise HTTPException(status_code=400, detail="Tag name is required")
        
        # Create WordPress service and tag
        with get_db_session() as db:
            wp_service = WordPressBlogService.from_project(project_id_str, db)
            if not wp_service:
                raise HTTPException(
                    status_code=500, 
                    detail="Failed to initialize WordPress service"
                )
        
        # Use the create_tag method (need to add this to WordPressBlogService)
        created_tag = wp_service.create_tag(tag_name)
        
        if not created_tag:
            raise HTTPException(status_code=500, detail="Failed to create WordPress tag")
        
        logger.info(f"Successfully created WordPress tag: {tag_name}")
        
        return JSONResponse(
            content={
                "status": "success",
                "data": created_tag,
                "message": f"Tag '{tag_name}' created successfully"
            },
            status_code=201
        )
        
    except HTTPException as he:
        logger.error(f"HTTP error in create_wordpress_tag: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in create_wordpress_tag: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create WordPress tag: {str(e)}"
        )


@router.get("/wordpress/status-options")
def get_wordpress_status_options(
    request: Request,
    current_user = Depends(verify_request_origin)
):
    """Get available WordPress post status options"""
    try:
        user_id = current_user.id
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID not provided")
        
        project_id_str = str(project_id)
        logger.info(f"Getting WordPress status options for user {user_id} in project {project_id}")
        
        # Verify project access and CMS connection
        with get_db_session() as db:
            project = verify_project_access(project_id, user_id, db)
            connected_cms = CMSDetectorService.detect_cms(project_id_str, db)
            
            if connected_cms != "wordpress":
                raise HTTPException(
                    status_code=400, 
                    detail="WordPress CMS not connected to this project"
                )
        
        # Define available status options with descriptions
        status_options = [
            {
                "value": "publish",
                "label": "Published",
                "description": "Published and visible to public",
                "requires_date": False
            },
            {
                "value": "draft", 
                "label": "Draft",
                "description": "Save as draft (not visible to public)",
                "requires_date": False
            },
            {
                "value": "private",
                "label": "Private", 
                "description": "Private (only visible to admins)",
                "requires_date": False
            },
            {
                "value": "pending",
                "label": "Pending Review",
                "description": "Pending review by editor/admin",
                "requires_date": False
            },
            {
                "value": "future",
                "label": "Schedule for Later",
                "description": "Schedule for future publication",
                "requires_date": True
            }
        ]
        
        return JSONResponse(
            content={
                "status": "success",
                "data": status_options
            },
            status_code=200
        )
        
    except HTTPException as he:
        logger.error(f"HTTP error in get_wordpress_status_options: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in get_wordpress_status_options: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get WordPress status options: {str(e)}"
        )


@router.get("/blog-stats", tags=["monitoring"])
def get_blog_stats(mongo_db = Depends(get_mongodb)):
    """
    Returns a table of User ID, Project ID, Blog_1000, Blog_1500, Blog_2500.
    Blog_1000: Number of blogs with 900-1100 words
    Blog_1500: Number of blogs with 1400-1600 words
    Blog_2500: Number of blogs with 2400-2600 words
    """
    try:
        pipeline = [
            {"$match": {"is_active": True}},
            {"$group": {
                "_id": {"user_id": "$user_id", "project_id": "$project_id"},
                "blog_1000": {"$sum": {"$cond": [
                    {"$and": [
                        {"$gte": ["$words_count", 900]},
                        {"$lte": ["$words_count", 1100]}
                    ]}, 1, 0
                ]}},
                "blog_1500": {"$sum": {"$cond": [
                    {"$and": [
                        {"$gte": ["$words_count", 1400]},
                        {"$lte": ["$words_count", 1600]}
                    ]}, 1, 0
                ]}},
                "blog_2500": {"$sum": {"$cond": [
                    {"$and": [
                        {"$gte": ["$words_count", 2400]},
                        {"$lte": ["$words_count", 2600]}
                    ]}, 1, 0
                ]}},
            }}
        ]
        collection = mongo_db[COLLECTION_NAME]
        results = list(collection.aggregate(pipeline))
        # Format for table
        table = []
        for row in results:
            table.append({
                "user_id": row["_id"]["user_id"],
                "project_id": row["_id"]["project_id"],
                "blog_1000": row["blog_1000"],
                "blog_1500": row["blog_1500"],
                "blog_2500": row["blog_2500"]
            })
        return JSONResponse(content={"status": "success", "data": table})
    except Exception as e:
        logger.error(f"Error in get_blog_stats: {str(e)}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


# Cache clear endpoint removed - no more Redis caching

@router.post("/{blog_id}/publish-to-wordpress")
async def publish_rayo_blog_to_wordpress(
    blog_id: str,
    publish_request: PublishToWordPressRequest,
    request: Request,
    current_user = Depends(verify_request_origin),
    mongo_db = Depends(get_mongodb)
):
    """
    🚀 NEW FUNCTIONALITY: Publish a Rayo blog to WordPress
    """
    try:
        user_id = current_user.id
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID not provided")
        
        # Verify project access with a new, short-lived connection
        project = None
        with get_db_session() as db:
            project = verify_project_access(project_id, user_id, db)
        
        logger.info(f"🚀 Publishing Rayo blog {blog_id} to WordPress")
        
        # Get Rayo blog from MongoDB
        rayo_blog = mongo_db[COLLECTION_NAME].find_one({"_id": ObjectId(blog_id)})
        
        if not rayo_blog:
            raise HTTPException(status_code=404, detail="Rayo blog not found")
        
        if rayo_blog.get("source") != "rayo":
            raise HTTPException(status_code=400, detail="Can only publish Rayo-generated blogs")
        
        # Check if already published to WordPress
        if rayo_blog.get("wordpress_id"):
            raise HTTPException(
                status_code=400, 
                detail=f"Blog already published to WordPress (Post ID: {rayo_blog['wordpress_id']})"
            )
        
        # Get WordPress service
        wp_service = None
        with get_db_session() as db:
            wp_service = WordPressBlogService.from_project(str(project_id), db)
        
        if not wp_service:
            raise HTTPException(status_code=400, detail="WordPress not connected to this project")
        
        # Handle category and tag creation/mapping
        final_category_ids = []
        final_tag_ids = []
        
        # Process categories
        if publish_request.category_ids:
            final_category_ids = publish_request.category_ids
        elif publish_request.categories:
            # Create categories by name if they don't exist
            for category_name in publish_request.categories:
                if category_name.strip():
                    category = wp_service.create_category(category_name.strip())
                    if category and category.get('id'):
                        final_category_ids.append(category['id'])
        
        # Process tags  
        if publish_request.tag_ids:
            final_tag_ids = publish_request.tag_ids
        elif publish_request.tags:
            # Create tags by name if they don't exist
            for tag_name in publish_request.tags:
                if tag_name.strip():
                    tag = wp_service.create_tag(tag_name.strip())
                    if tag and tag.get('id'):
                        final_tag_ids.append(tag['id'])
        
        # Prepare WordPress options
        wp_options = {
            "status": publish_request.status,
            "categories": final_category_ids,
            "tags": final_tag_ids,
            "author": publish_request.author_id
        }
        
        # Override content if provided
        if publish_request.content:
            wp_options["content_override"] = publish_request.content
            
        # Override slug if provided
        if publish_request.slug:
            wp_options["slug_override"] = publish_request.slug
            
        # Override image if provided
        if publish_request.image_url:
            wp_options["image_url_override"] = publish_request.image_url
        
        # Handle scheduled posts
        if publish_request.status == "future" and publish_request.scheduled_date:
            wp_options["date"] = publish_request.scheduled_date
        
        # Create WordPress post from Rayo blog
        wp_post = wp_service.create_post_from_rayo(rayo_blog, wp_options)
        
        if not wp_post:
            raise HTTPException(status_code=500, detail="Failed to create WordPress post")
        
        # Update Rayo blog with WordPress tracking info
        update_data = {
            "wordpress_id": str(wp_post["id"]),
            "published_to_wp": True,
            "wp_url": wp_post.get("wp_url", ""),
            "wp_publish_date": get_current_ist_time(),
            "updated_at": get_current_ist_time(),
            "status": wp_post.get("status", "draft")  # Update Rayo blog status to match WordPress
        }
        
        mongo_db[COLLECTION_NAME].update_one(
            {"_id": ObjectId(blog_id)},
            {"$set": update_data}
        )
        
        logger.info(f"✅ Successfully published Rayo blog to WordPress: {wp_post['id']}")
        logger.info(f"📝 Updated Rayo blog status from '{rayo_blog.get('status', 'unknown')}' to '{wp_post.get('status', 'draft')}'")
        
        return JSONResponse(
            status_code=201,
            content={
                "status": "success",
                "message": "Blog published to WordPress successfully",
                "data": {
                    "wordpress_post_id": wp_post["id"],
                    "wordpress_url": wp_post.get("wp_url", ""),
                    "wordpress_status": wp_post.get("status", ""),
                    "rayo_blog_id": blog_id,
                    "rayo_blog_status_updated": wp_post.get("status", "draft")  # Show the updated Rayo status
                }
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error publishing to WordPress: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to publish to WordPress")

@router.get("/{blog_id}/wordpress-status")
async def get_blog_wordpress_status(
    blog_id: str,
    request: Request,
    current_user = Depends(verify_request_origin),
    mongo_db = Depends(get_mongodb)
):
    """
    Check if a Rayo blog is published to WordPress and its status
    """
    try:
        user_id = current_user.id
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID not provided")
        
        # Verify project access with a new, short-lived connection
        project = None
        with get_db_session() as db:
            project = verify_project_access(project_id, user_id, db)
        
        # Get blog from MongoDB
        blog = mongo_db[COLLECTION_NAME].find_one({"_id": ObjectId(blog_id)})
        
        if not blog:
            raise HTTPException(status_code=404, detail="Blog not found")
        
        wordpress_status = {
            "published_to_wordpress": bool(blog.get("wordpress_id")),
            "wordpress_post_id": blog.get("wordpress_id"),
            "wordpress_url": blog.get("wp_url", ""),
            "publish_date": serialize_datetime(blog.get("wp_publish_date")) if blog.get("wp_publish_date") else None
        }
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "data": wordpress_status
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting WordPress status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get WordPress status")

@router.get("/unpublished-to-wordpress")
async def get_unpublished_rayo_blogs(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    current_user = Depends(verify_request_origin),
    mongo_db = Depends(get_mongodb)
):
    """
    Get Rayo blogs that haven't been published to WordPress yet
    """
    try:
        user_id = current_user.id
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID not provided")
        
        # Verify project access with a new, short-lived connection
        project = None
        with get_db_session() as db:
            project = verify_project_access(project_id, user_id, db)
        
        # Query for unpublished Rayo blogs
        query = {
            "project_id": str(project_id),
            "source": "rayo",
            "$or": [
                {"published_to_wp": {"$ne": True}},
                {"wordpress_id": {"$exists": False}}
            ]
        }
        
        # Get MongoDB collection
        collection = mongo_db[COLLECTION_NAME]
        
        # Get total count
        total_count = collection.count_documents(query)
        
        # Get paginated results
        blogs = collection.find(query) \
                         .sort("created_at", -1) \
                         .skip((page - 1) * per_page) \
                         .limit(per_page)
        
        # Convert to list and serialize
        blog_list = []
        for blog in blogs:
            blog["id"] = str(blog.pop("_id"))
            blog_list.append(serialize_blog(blog))
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "data": blog_list,
                "meta": {
                    "total_count": total_count,
                    "total_pages": math.ceil(total_count / per_page) if total_count > 0 else 0,
                    "current_page": page,
                    "per_page": per_page,
                    "has_next": page < math.ceil(total_count / per_page) if total_count > 0 else False,
                    "has_previous": page > 1
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting unpublished blogs: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get unpublished blogs")


# ============ SHOPIFY BLOG ENDPOINTS ============

@router.get("/shopify/blogs")
def get_shopify_blogs(
    request: Request,
    current_user = Depends(verify_request_origin)
):
    """Get all blogs from connected Shopify store"""
    try:
        project_id = request.path_params.get("project_id")
        user_id = current_user.id

        with get_db_session() as db:
            verify_project_access(UUID(project_id), user_id, db)
            
            # Get Shopify credentials
            shopify_creds = db.query(ShopifyCredentials).filter(
                ShopifyCredentials.project_id == project_id
            ).first()
            
            if not shopify_creds:
                raise HTTPException(status_code=404, detail="Shopify not connected to this project")
            
            # Create Shopify service and get blogs
            shopify_service = ShopifyService(
                shop_domain=shopify_creds.shop_domain,
                access_token=shopify_creds.access_token,
                api_version=shopify_creds.api_version
            )
            
            blogs = shopify_service.get_blogs()
            if blogs is None:
                raise HTTPException(status_code=500, detail="Failed to fetch Shopify blogs")
            
            return JSONResponse(
                status_code=200,
                content={"status": "success", "data": {"blogs": blogs}}
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Shopify blogs: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get Shopify blogs")


@router.get("/shopify/posts")
def get_shopify_posts(
    request: Request,
    blog_id: Optional[int] = Query(None, description="Shopify blog ID"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=250, description="Posts per page"),
    current_user = Depends(verify_request_origin)
):
    """Get posts from Shopify blog with pagination"""
    try:
        project_id = request.path_params.get("project_id")
        user_id = current_user.id

        with get_db_session() as db:
            verify_project_access(UUID(project_id), user_id, db)
            
            # Get Shopify credentials
            shopify_creds = db.query(ShopifyCredentials).filter(
                ShopifyCredentials.project_id == project_id
            ).first()
            
            if not shopify_creds:
                raise HTTPException(status_code=404, detail="Shopify not connected to this project")
            
            # Create Shopify service and get posts
            shopify_service = ShopifyService(
                shop_domain=shopify_creds.shop_domain,
                access_token=shopify_creds.access_token,
                api_version=shopify_creds.api_version
            )
            
            result = shopify_service.get_posts(blog_id=blog_id, limit=per_page, page=page)
            
            return JSONResponse(
                status_code=200,
                content={"status": "success", "data": result}
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Shopify posts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get Shopify posts")


@router.get("/shopify/posts/{article_id}")
def get_shopify_post_by_id(
    request: Request,
    article_id: int,
    blog_id: int = Query(..., description="Shopify blog ID"),
    current_user = Depends(verify_request_origin)
):
    """Get single Shopify post by ID with full content"""
    try:
        project_id = request.path_params.get("project_id")
        user_id = current_user.id

        with get_db_session() as db:
            verify_project_access(UUID(project_id), user_id, db)
            
            # Get Shopify credentials
            shopify_creds = db.query(ShopifyCredentials).filter(
                ShopifyCredentials.project_id == project_id
            ).first()
            
            if not shopify_creds:
                raise HTTPException(status_code=404, detail="Shopify not connected to this project")
            
            # Create Shopify service and get post
            shopify_service = ShopifyService(
                shop_domain=shopify_creds.shop_domain,
                access_token=shopify_creds.access_token,
                api_version=shopify_creds.api_version
            )
            
            post = shopify_service.get_post_by_id(blog_id=blog_id, article_id=article_id)
            if not post:
                raise HTTPException(status_code=404, detail="Shopify post not found")
            
            return JSONResponse(
                status_code=200,
                content={"status": "success", "data": post}
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Shopify post {article_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get Shopify post")


@router.get("/shopify/authors")
def get_shopify_authors(
    request: Request,
    current_user = Depends(verify_request_origin)
):
    """Get all authors from Shopify blog posts"""
    try:
        project_id = request.path_params.get("project_id")
        user_id = current_user.id

        with get_db_session() as db:
            verify_project_access(UUID(project_id), user_id, db)
            
            # Get Shopify credentials
            shopify_creds = db.query(ShopifyCredentials).filter(
                ShopifyCredentials.project_id == project_id
            ).first()
            
            if not shopify_creds:
                raise HTTPException(status_code=404, detail="Shopify not connected to this project")
            
            # Create Shopify service and get authors
            shopify_service = ShopifyService(
                shop_domain=shopify_creds.shop_domain,
                access_token=shopify_creds.access_token,
                api_version=shopify_creds.api_version
            )
            
            authors = shopify_service.get_authors()
            
            return JSONResponse(
                status_code=200,
                content={"status": "success", "data": {"authors": authors}}
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Shopify authors: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get Shopify authors")


@router.get("/shopify/tags")
def get_shopify_tags(
    request: Request,
    current_user = Depends(verify_request_origin)
):
    """Get all tags from Shopify blog posts"""
    try:
        project_id = request.path_params.get("project_id")
        user_id = current_user.id

        with get_db_session() as db:
            verify_project_access(UUID(project_id), user_id, db)
            
            # Get Shopify credentials
            shopify_creds = db.query(ShopifyCredentials).filter(
                ShopifyCredentials.project_id == project_id
            ).first()
            
            if not shopify_creds:
                raise HTTPException(status_code=404, detail="Shopify not connected to this project")
            
            # Create Shopify service and get tags
            shopify_service = ShopifyService(
                shop_domain=shopify_creds.shop_domain,
                access_token=shopify_creds.access_token,
                api_version=shopify_creds.api_version
            )
            
            tags = shopify_service.get_tags()
            
            return JSONResponse(
                status_code=200,
                content={"status": "success", "data": {"tags": tags}}
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Shopify tags: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get Shopify tags")


# ============ SHOPIFY CREATE ENDPOINTS ============

@router.post("/shopify/blogs")
def create_shopify_blog(
    request: Request,
    blog_data: ShopifyBlogCreate,
    current_user = Depends(verify_request_origin)
):
    """Create a new blog in Shopify store"""
    try:
        project_id = request.path_params.get("project_id")
        user_id = current_user.id

        with get_db_session() as db:
            verify_project_access(UUID(project_id), user_id, db)
            
            # Get Shopify credentials
            shopify_creds = db.query(ShopifyCredentials).filter(
                ShopifyCredentials.project_id == project_id
            ).first()
            
            if not shopify_creds:
                raise HTTPException(status_code=404, detail="Shopify not connected to this project")
            
            # Create Shopify service and create blog
            shopify_service = ShopifyService(
                shop_domain=shopify_creds.shop_domain,
                access_token=shopify_creds.access_token,
                api_version=shopify_creds.api_version
            )
            
            created_blog = shopify_service.create_blog(
                title=blog_data.title,
                handle=blog_data.handle
            )
            
            if not created_blog:
                raise HTTPException(status_code=400, detail="Failed to create blog in Shopify")
            
            return JSONResponse(
                status_code=201,
                content={"status": "success", "data": {"blog": created_blog}}
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating Shopify blog: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create Shopify blog")


@router.post("/shopify/articles")
def create_shopify_article(
    request: Request,
    article_data: ShopifyArticleCreate,
    current_user = Depends(verify_request_origin)
):
    """Create a new article in Shopify blog"""
    try:
        project_id = request.path_params.get("project_id")
        user_id = current_user.id

        with get_db_session() as db:
            verify_project_access(UUID(project_id), user_id, db)
            
            # Get Shopify credentials
            shopify_creds = db.query(ShopifyCredentials).filter(
                ShopifyCredentials.project_id == project_id
            ).first()
            
            if not shopify_creds:
                raise HTTPException(status_code=404, detail="Shopify not connected to this project")
            
            # Create Shopify service and create article
            shopify_service = ShopifyService(
                shop_domain=shopify_creds.shop_domain,
                access_token=shopify_creds.access_token,
                api_version=shopify_creds.api_version
            )
            
            created_article = shopify_service.create_article(
                blog_id=article_data.blog_id,
                title=article_data.title,
                content=article_data.content,
                tags=article_data.tags,
                author=article_data.author,
                summary=article_data.summary,
                published=article_data.published,
                handle=article_data.handle
            )
            
            if not created_article:
                raise HTTPException(status_code=400, detail="Failed to create article in Shopify")
            
            return JSONResponse(
                status_code=201,
                content={"status": "success", "data": created_article}
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating Shopify article: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create Shopify article")


@router.put("/shopify/posts/{article_id}")
def update_shopify_article(
    request: Request,
    article_id: int,
    article_data: ShopifyArticleUpdate,
    blog_id: int = Query(..., description="Shopify blog ID"),
    current_user = Depends(verify_request_origin)
):
    """Update an existing Shopify article"""
    try:
        project_id = request.path_params.get("project_id")
        user_id = current_user.id

        with get_db_session() as db:
            verify_project_access(UUID(project_id), user_id, db)
            
            # Get Shopify credentials
            shopify_creds = db.query(ShopifyCredentials).filter(
                ShopifyCredentials.project_id == project_id
            ).first()
            
            if not shopify_creds:
                raise HTTPException(status_code=404, detail="Shopify not connected to this project")
            
            # Create Shopify service and update article
            shopify_service = ShopifyService(
                shop_domain=shopify_creds.shop_domain,
                access_token=shopify_creds.access_token,
                api_version=shopify_creds.api_version
            )
            
            # Convert to dict and remove None values
            update_data = {k: v for k, v in article_data.dict(exclude_unset=True).items() if v is not None}
            
            if not update_data:
                raise HTTPException(status_code=400, detail="No valid data provided for update")
            
            updated_article = shopify_service.update_article(
                blog_id=blog_id,
                article_id=article_id,
                update_data=update_data
            )
            
            if not updated_article:
                raise HTTPException(status_code=404, detail="Failed to update article - article may not exist")
            
            return JSONResponse(
                status_code=200,
                content={"status": "success", "data": updated_article}
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating Shopify article {article_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update Shopify article")


@router.delete("/shopify/posts/{article_id}")
def delete_shopify_article(
    request: Request,
    article_id: int,
    blog_id: int = Query(..., description="Shopify blog ID"),
    current_user = Depends(verify_request_origin)
):
    """Delete a Shopify article"""
    try:
        project_id = request.path_params.get("project_id")
        user_id = current_user.id

        with get_db_session() as db:
            verify_project_access(UUID(project_id), user_id, db)
            
            # Get Shopify credentials
            shopify_creds = db.query(ShopifyCredentials).filter(
                ShopifyCredentials.project_id == project_id
            ).first()
            
            if not shopify_creds:
                raise HTTPException(status_code=404, detail="Shopify not connected to this project")
            
            # Create Shopify service and delete article
            shopify_service = ShopifyService(
                shop_domain=shopify_creds.shop_domain,
                access_token=shopify_creds.access_token,
                api_version=shopify_creds.api_version
            )
            
            deleted = shopify_service.delete_article(blog_id=blog_id, article_id=article_id)
            
            if not deleted:
                raise HTTPException(status_code=404, detail="Article not found or failed to delete")
            
            return JSONResponse(
                status_code=200,
                content={"status": "success", "message": "Article deleted successfully"}
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting Shopify article {article_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete Shopify article")


# ============ SHOPIFY TAG CREATION ENDPOINTS ============

@router.post("/shopify/tags")
def create_shopify_tags(
    request: Request,
    tag_data: ShopifyTagCreate,
    current_user = Depends(verify_request_origin)
):
    """
    Create new tags in Shopify by creating a temporary article.
    Since Shopify doesn't have dedicated tag creation, this creates tags
    by temporarily associating them with an article, then deleting the article.
    """
    try:
        project_id = request.path_params.get("project_id")
        user_id = current_user.id

        with get_db_session() as db:
            verify_project_access(UUID(project_id), user_id, db)
            
            # Get Shopify credentials
            shopify_creds = db.query(ShopifyCredentials).filter(
                ShopifyCredentials.project_id == project_id
            ).first()
            
            if not shopify_creds:
                raise HTTPException(status_code=404, detail="Shopify not connected to this project")
            
            # Create Shopify service and create tags
            shopify_service = ShopifyService(
                shop_domain=shopify_creds.shop_domain,
                access_token=shopify_creds.access_token,
                api_version=shopify_creds.api_version
            )
            
            # Create tags using temporary article method
            result = shopify_service.create_tags(tag_data.tag_names)
            
            if not result['success']:
                raise HTTPException(
                    status_code=400, 
                    detail=result.get('error', 'Failed to create tags')
                )
            
            return JSONResponse(
                status_code=201,
                content={
                    "status": "success",
                    "message": result['message'],
                    "data": {
                        "tags": result['created_tags'],
                        "total_created": len(result['created_tags'])
                    }
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating Shopify tags: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create Shopify tags")


@router.post("/shopify/tags/via-article")
def create_shopify_tags_via_article(
    request: Request,
    tag_article_data: ShopifyTagCreateViaArticle,
    current_user = Depends(verify_request_origin)
):
    """
    Create new tags in Shopify by creating a real article with those tags.
    This method creates a permanent article and associates the tags with it.
    """
    try:
        project_id = request.path_params.get("project_id")
        user_id = current_user.id

        with get_db_session() as db:
            verify_project_access(UUID(project_id), user_id, db)
            
            # Get Shopify credentials
            shopify_creds = db.query(ShopifyCredentials).filter(
                ShopifyCredentials.project_id == project_id
            ).first()
            
            if not shopify_creds:
                raise HTTPException(status_code=404, detail="Shopify not connected to this project")
            
            # Create Shopify service and create article with tags
            shopify_service = ShopifyService(
                shop_domain=shopify_creds.shop_domain,
                access_token=shopify_creds.access_token,
                api_version=shopify_creds.api_version
            )
            
            # Create article with tags
            created_article = shopify_service.bulk_create_tags_via_article(
                blog_id=tag_article_data.blog_id,
                article_title=tag_article_data.article_title,
                article_content=tag_article_data.article_content,
                tag_names=tag_article_data.tag_names
            )
            
            if not created_article:
                raise HTTPException(status_code=400, detail="Failed to create article with tags")
            
            return JSONResponse(
                status_code=201,
                content={
                    "status": "success",
                    "message": f"Successfully created article with {len(tag_article_data.tag_names)} tags",
                    "data": {
                        "article": created_article,
                        "created_tags": tag_article_data.tag_names,
                        "total_tags": len(tag_article_data.tag_names)
                    }
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating Shopify tags via article: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create tags via article")


# ============ SHOPIFY PUBLISH ENDPOINT ============

@router.post("/{blog_id}/publish-to-shopify")
async def publish_rayo_blog_to_shopify(
    blog_id: str,
    publish_request: PublishToShopifyRequest,
    request: Request,
    current_user = Depends(verify_request_origin),
    mongo_db = Depends(get_mongodb)
):
    """
    🚀 Publish a Rayo blog to Shopify - matches frontend payload structure
    """
    try:
        user_id = current_user.id
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID not provided")
        
        # Verify project access
        project = None
        with get_db_session() as db:
            project = verify_project_access(project_id, user_id, db)
        
        logger.info(f"🚀 Publishing Rayo blog {blog_id} to Shopify")
        logger.info(f"📊 Publish request payload: {publish_request.dict()}")
        
        # Get Rayo blog from MongoDB
        rayo_blog = mongo_db[COLLECTION_NAME].find_one({"_id": ObjectId(blog_id)})
        
        if not rayo_blog:
            logger.error(f"❌ Rayo blog not found: {blog_id}")
            raise HTTPException(status_code=404, detail="Rayo blog not found")
        
        logger.info(f"📝 Found Rayo blog: '{rayo_blog.get('title', 'Unknown')}' (Source: {rayo_blog.get('source', 'unknown')})")
        
        if rayo_blog.get("source") != "rayo":
            logger.error(f"❌ Invalid source: {rayo_blog.get('source')} - can only publish Rayo blogs")
            raise HTTPException(status_code=400, detail="Can only publish Rayo-generated blogs")
        
        # Check if already published to Shopify
        if rayo_blog.get("shopify_id"):
            logger.warning(f"⚠️ Blog already published to Shopify: Article ID {rayo_blog['shopify_id']}")
            raise HTTPException(
                status_code=400, 
                detail=f"Blog already published to Shopify (Article ID: {rayo_blog['shopify_id']})"
            )
        
        # Get Shopify service
        shopify_service = None
        with get_db_session() as db:
            shopify_creds = db.query(ShopifyCredentials).filter(
                ShopifyCredentials.project_id == project_id
            ).first()
            
            if not shopify_creds:
                logger.error(f"❌ Shopify credentials not found for project {project_id}")
                raise HTTPException(status_code=400, detail="Shopify not connected to this project")
            
            logger.info(f"🏪 Shopify connection found: {shopify_creds.shop_domain} (API: {shopify_creds.api_version})")
            
            shopify_service = ShopifyService(
                shop_domain=shopify_creds.shop_domain,
                access_token=shopify_creds.access_token,
                api_version=shopify_creds.api_version
            )
        
        # Prepare Shopify options from frontend payload
        shopify_options = {
            "blog_id": publish_request.blog_id,
            "status": publish_request.status,
            "tags": publish_request.tags or [],
            "author": publish_request.author or "Rayo User",
            "summary": publish_request.summary or ""
        }
        
        logger.info(f"⚙️ Shopify options prepared:")
        logger.info(f"   📝 Target blog ID: {publish_request.blog_id}")
        logger.info(f"   📊 Status: {publish_request.status}")
        logger.info(f"   🏷️ Tags: {publish_request.tags}")
        logger.info(f"   👤 Author: {publish_request.author}")
        logger.info(f"   📄 Summary length: {len(publish_request.summary or '')}")
        
        # Override content if provided
        if publish_request.content:
            shopify_options["content_override"] = publish_request.content
            logger.info(f"   📝 Content override: {len(publish_request.content)} characters")
        else:
            logger.info(f"   📝 Using original Rayo content: {len(rayo_blog.get('content', ''))} characters")
        
        # Handle featured image URL
        if publish_request.image_url:
            logger.info(f"📷 Featured image URL provided: {publish_request.image_url}")
            
            # Validate image URL
            if shopify_service.validate_image_url(publish_request.image_url):
                shopify_options["image_url"] = publish_request.image_url
                logger.info(f"✅ Image URL validated and will be set as featured image")
            else:
                logger.warning(f"⚠️ Invalid image URL, proceeding without featured image")
                shopify_options["image_url"] = None
        else:
            logger.info(f"📷 No featured image URL provided in request")
        
        # Create Shopify article from Rayo blog
        shopify_article = shopify_service.create_post_from_rayo(rayo_blog, shopify_options)
        
        if not shopify_article:
            raise HTTPException(status_code=500, detail="Failed to create Shopify article")
        
        # Update Rayo blog with Shopify tracking info
        shopify_status = "published" if shopify_article.get("status") == "publish" else "draft"
        
        update_data = {
            "shopify_id": str(shopify_article["id"]),
            "published_to_shopify": True,
            "shopify_url": shopify_article.get("shopify_url", ""),
            "shopify_blog_id": publish_request.blog_id,
            "shopify_publish_date": get_current_ist_time(),
            "updated_at": get_current_ist_time(),
            "status": shopify_status  # Update Rayo blog status to match Shopify
        }
        
        mongo_db[COLLECTION_NAME].update_one(
            {"_id": ObjectId(blog_id)},
            {"$set": update_data}
        )
        
        logger.info(f"✅ Successfully published Rayo blog to Shopify: {shopify_article['id']}")
        logger.info(f"📝 Updated Rayo blog status to '{shopify_status}'")
        
        return JSONResponse(
            status_code=201,
            content={
                "status": "success",
                "message": "Blog published to Shopify successfully",
                "data": {
                    "shopify_article_id": shopify_article["id"],
                    "shopify_url": shopify_article.get("shopify_url", ""),
                    "shopify_status": shopify_article.get("status", ""),
                    "shopify_blog_id": publish_request.blog_id,
                    "rayo_blog_id": blog_id,
                    "rayo_blog_status_updated": shopify_status,
                    "tags_created": publish_request.tags,
                    "author": publish_request.author,
                    "featured_image_set": bool(publish_request.image_url and shopify_options.get("image_url")),
                    "featured_image_url": publish_request.image_url if shopify_options.get("image_url") else None
                }
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error publishing to Shopify: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to publish to Shopify")


@router.get("/{blog_id}/shopify-status")
async def get_blog_shopify_status(
    blog_id: str,
    request: Request,
    current_user = Depends(verify_request_origin),
    mongo_db = Depends(get_mongodb)
):
    """
    Get the Shopify publishing status of a Rayo blog
    """
    try:
        user_id = current_user.id
        project_id = request.path_params.get("project_id")
        
        # Verify project access
        with get_db_session() as db:
            verify_project_access(project_id, user_id, db)
        
        # Get blog from MongoDB
        rayo_blog = mongo_db[COLLECTION_NAME].find_one({"_id": ObjectId(blog_id)})
        
        if not rayo_blog:
            raise HTTPException(status_code=404, detail="Blog not found")
        
        shopify_status = {
            "published_to_shopify": rayo_blog.get("published_to_shopify", False),
            "shopify_id": rayo_blog.get("shopify_id"),
            "shopify_url": rayo_blog.get("shopify_url", ""),
            "shopify_blog_id": rayo_blog.get("shopify_blog_id"),
            "shopify_publish_date": rayo_blog.get("shopify_publish_date"),
            "last_updated": rayo_blog.get("updated_at")
        }
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "data": shopify_status
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Shopify status for blog {blog_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get Shopify status")


