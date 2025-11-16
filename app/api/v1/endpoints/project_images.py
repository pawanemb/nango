from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.db.session import get_db
from app.services.storage_service_factory import get_storage_service
from app.models.project_image import ProjectImage
from app.models.project import Project
from typing import Optional, List
from app.core.logging_config import logger
from app.tasks.featured_image_generation import generate_featured_image, get_featured_image_status, get_featured_image_status_by_blog_id
import json
import uuid

router = APIRouter()

@router.post("/projects/{project_id}/images/upload")
async def upload_project_image(
    request: Request,
    project_id: str,
    file: Optional[UploadFile] = File(None),
    image_url: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    custom_filename: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload an image to a specific project - supports both file upload and URL with optional custom filename"""
    try:
        # Get authenticated user
        user = request.state.user
        user_id = user.user.id
        
        # Validate input - either file or URL must be provided
        if not file and not image_url:
            raise HTTPException(status_code=400, detail="Either 'file' or 'image_url' must be provided")
        
        if file and image_url:
            raise HTTPException(status_code=400, detail="Provide either 'file' or 'image_url', not both")
        
        # Validate project ownership
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == user_id
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found or access denied")
        
        # Extract JWT token from Authorization header for Supabase authentication
        user_token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            user_token = auth_header.split(" ")[1]
            logger.info(f"Extracted user token for upload: {user_token[:10]}...")
        else:
            logger.warning("No Authorization header found for upload, falling back to service key authentication")
        
        # Initialize storage service with user authentication (auto-detects provider)
        storage_service = get_storage_service(user_token=user_token)
        await storage_service.create_bucket_if_not_exists()
        
        # Handle file upload or URL upload
        if file:
            # File upload path
            file_content = await file.read()
            
            # Build final filename with auto-detected extension
            if custom_filename:
                # Get extension from original file
                import os
                original_extension = os.path.splitext(file.filename)[1] if file.filename else ''
                # Ensure custom_filename doesn't already have extension
                custom_name_only = os.path.splitext(custom_filename)[0]
                final_filename = f"{custom_name_only}{original_extension}"
            else:
                final_filename = file.filename
                
            logger.info(f"File upload: original={file.filename}, custom_name={custom_filename}, final={final_filename}, content_type={file.content_type}, size={len(file_content)}")
            
            upload_result = await storage_service.upload_project_file(
                project_id=project_id,
                user_id=user_id,
                file_content=file_content,
                filename=final_filename,
                mime_type=file.content_type,
                category=category
            )
        else:
            # URL upload path
            logger.info(f"URL upload: image_url={image_url}, custom_filename={custom_filename}, category={category}")
            upload_result = await storage_service.upload_project_file_from_url(
                project_id=project_id,
                user_id=user_id,
                image_url=image_url,
                category=category
            )
            
            # If custom_filename provided for URL upload, update the original_filename after upload
            if custom_filename and upload_result.get("success"):
                import os
                # Get extension from the downloaded file
                downloaded_extension = os.path.splitext(upload_result.get("original_filename", ""))[1]
                # Clean custom name and add proper extension
                custom_name_only = os.path.splitext(custom_filename)[0]
                upload_result["original_filename"] = f"{custom_name_only}{downloaded_extension}"
        
        logger.info(f"Upload result: {upload_result}")
        
        if not upload_result["success"]:
            logger.error(f"Upload failed with errors: {upload_result.get('errors', [])}")
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "File upload failed",
                    "errors": upload_result["errors"]
                }
            )
        
        # Extract image dimensions
        width = height = None
        if upload_result["image_metadata"]:
            width = upload_result["image_metadata"].get("width")
            height = upload_result["image_metadata"].get("height")
        
        # Save to database
        project_image = ProjectImage(
            project_id=project_id,
            user_id=user_id,
            filename=upload_result["filename"],
            original_filename=upload_result["original_filename"],
            file_size=upload_result["file_size"],
            mime_type=upload_result["mime_type"],
            storage_path=upload_result["storage_path"],
            public_url=upload_result["public_url"],
            image_metadata=upload_result["image_metadata"],
            width=width,
            height=height,
            category=category,
            description=description
        )
        
        db.add(project_image)
        db.commit()
        db.refresh(project_image)
        
        return {
            "status": "success",
            "message": "Image uploaded successfully to project",
            "data": project_image.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading project image: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/projects/{project_id}/images")
async def get_project_images(
    request: Request,
    project_id: str,
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get all images for a specific project"""
    try:
        user = request.state.user
        user_id = user.user.id
        
        # Validate project ownership
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == user_id
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found or access denied")
        
        # Build query
        query = db.query(ProjectImage).filter(
            ProjectImage.project_id == project_id,
            ProjectImage.is_active == True
        )
        
        # Apply category filter
        if category:
            query = query.filter(ProjectImage.category == category)
        
        # Apply pagination
        offset = (page - 1) * limit
        total_count = query.count()
        images = query.order_by(ProjectImage.created_at.desc()).offset(offset).limit(limit).all()
        
        # Format response
        image_data = [image.to_dict() for image in images]
        
        return {
            "status": "success",
            "data": {
                "project": {
                    "id": str(project.id),
                    "name": project.name
                },
                "images": image_data,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total_count,
                    "pages": (total_count + limit - 1) // limit
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching project images: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/projects/{project_id}/images/search")
async def search_project_images(
    request: Request,
    project_id: str,
    q: Optional[str] = Query(None, description="Search query"),
    category: Optional[str] = Query(None),
    mime_type: Optional[str] = Query(None),
    min_size: Optional[int] = Query(None, description="Minimum file size in bytes"),
    max_size: Optional[int] = Query(None, description="Maximum file size in bytes"),
    date_from: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    sort_by: Optional[str] = Query("created_at", regex="^(created_at|file_size|filename)$"),
    sort_order: Optional[str] = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Advanced search through project images"""
    try:
        user = request.state.user
        user_id = user.user.id
        
        # Validate project ownership
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == user_id
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found or access denied")
        
        # Build base query
        query = db.query(ProjectImage).filter(
            ProjectImage.project_id == project_id,
            ProjectImage.is_active == True
        )
        
        # Apply search filters
        if q:
            search_term = f"%{q}%"
            query = query.filter(
                or_(
                    ProjectImage.filename.ilike(search_term),
                    ProjectImage.original_filename.ilike(search_term),
                    ProjectImage.description.ilike(search_term)
                )
            )
        
        if category:
            query = query.filter(ProjectImage.category == category)
        
        if mime_type:
            query = query.filter(ProjectImage.mime_type == mime_type)
        
        if min_size:
            query = query.filter(ProjectImage.file_size >= min_size)
        
        if max_size:
            query = query.filter(ProjectImage.file_size <= max_size)
        
        if date_from:
            query = query.filter(ProjectImage.created_at >= date_from)
        
        if date_to:
            query = query.filter(ProjectImage.created_at <= date_to)
        
        # Apply sorting
        sort_column = getattr(ProjectImage, sort_by)
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
        
        # Apply pagination
        offset = (page - 1) * limit
        total_count = query.count()
        images = query.offset(offset).limit(limit).all()
        
        # Format response
        image_data = [image.to_dict() for image in images]
        
        return {
            "status": "success",
            "data": {
                "project": {
                    "id": str(project.id),
                    "name": project.name
                },
                "images": image_data,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total_count,
                    "pages": (total_count + limit - 1) // limit
                },
                "search_params": {
                    "query": q,
                    "category": category,
                    "mime_type": mime_type,
                    "min_size": min_size,
                    "max_size": max_size,
                    "date_from": date_from,
                    "date_to": date_to,
                    "sort_by": sort_by,
                    "sort_order": sort_order
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching project images: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/projects/{project_id}/images/{image_id}")
async def get_project_image_details(
    request: Request,
    project_id: str,
    image_id: str,
    db: Session = Depends(get_db)
):
    """Get specific image details"""
    try:
        user = request.state.user
        user_id = user.user.id
        
        # Validate project ownership first
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == user_id
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found or access denied")
        
        # Get image from this project
        image = db.query(ProjectImage).filter(
            ProjectImage.id == image_id,
            ProjectImage.project_id == project_id,
            ProjectImage.is_active == True
        ).first()
        
        if not image:
            raise HTTPException(status_code=404, detail="Image not found or access denied")
        
        return {
            "status": "success",
            "data": image.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching image details: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/projects/{project_id}/images/bulk")
async def bulk_delete_project_images(
    request: Request,
    project_id: str,
    db: Session = Depends(get_db)
):
    """Delete multiple images from a project"""
    try:
        user = request.state.user
        user_id = user.user.id
        
        # Extract JWT token from Authorization header for Supabase authentication
        user_token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            user_token = auth_header.split(" ")[1]
            logger.info(f"Extracted user token for bulk delete: {user_token[:10]}...")
        else:
            logger.warning("No Authorization header found for bulk delete, falling back to service key authentication")
        
        # Get request body
        body = await request.json()
        image_ids = body.get("image_ids", [])
        
        if not image_ids:
            raise HTTPException(status_code=400, detail="No image IDs provided")
        
        # Validate project ownership
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == user_id
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found or access denied")
        
        # Get images to delete
        images = db.query(ProjectImage).filter(
            ProjectImage.id.in_(image_ids),
            ProjectImage.project_id == project_id
        ).all()
        
        if not images:
            raise HTTPException(status_code=404, detail="No images found to delete")
        
        # Collect storage paths for bulk deletion
        storage_paths = [image.storage_path for image in images]
        
        # Delete from storage with user authentication (auto-detects provider)
        storage_service = get_storage_service(user_token=user_token)
        storage_result = await storage_service.delete_multiple_files(storage_paths)
        
        if not storage_result["success"]:
            logger.warning(f"Failed to delete some files from storage: {storage_result.get('error')}")
        
        # Delete from database
        deleted_ids = []
        for image in images:
            deleted_ids.append(str(image.id))
            db.delete(image)
        
        db.commit()
        
        return {
            "status": "success",
            "message": f"{len(deleted_ids)} images deleted successfully",
            "data": {
                "deleted_count": len(deleted_ids),
                "deleted_ids": deleted_ids
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk deleting project images: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/projects/{project_id}/images/{image_id}")
async def update_project_image(
    request: Request,
    project_id: str,
    image_id: str,
    category: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    custom_filename: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Update image metadata - category, description, and optionally filename"""
    try:
        user = request.state.user
        user_id = user.user.id
        
        # Validate project ownership
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == user_id
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found or access denied")
        
        # Get image from this project
        image = db.query(ProjectImage).filter(
            ProjectImage.id == image_id,
            ProjectImage.project_id == project_id,
            ProjectImage.is_active == True
        ).first()
        
        if not image:
            raise HTTPException(status_code=404, detail="Image not found or access denied")
        
        # Update metadata fields
        if category is not None:
            image.category = category
        if description is not None:
            image.description = description
            
        # Handle custom filename update
        if custom_filename:
            import os
            # Get extension from current filename
            current_extension = os.path.splitext(image.original_filename or image.filename)[1]
            # Clean custom name and add extension
            custom_name_only = os.path.splitext(custom_filename)[0]
            image.original_filename = f"{custom_name_only}{current_extension}"
        
        db.commit()
        db.refresh(image)
        
        return {
            "status": "success",
            "message": "Image updated successfully",
            "data": image.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating project image: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/projects/{project_id}/images/{image_id}")
async def delete_project_image(
    request: Request,
    project_id: str,
    image_id: str,
    db: Session = Depends(get_db)
):
    """Delete a specific image from a project"""
    try:
        user = request.state.user
        user_id = user.user.id
        
        # Validate project ownership first
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == user_id
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found or access denied")
        
        # Get image from this project
        image = db.query(ProjectImage).filter(
            ProjectImage.id == image_id,
            ProjectImage.project_id == project_id
        ).first()
        
        if not image:
            raise HTTPException(status_code=404, detail="Image not found or access denied")
        
        # Extract JWT token from Authorization header for Supabase authentication
        user_token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            user_token = auth_header.split(" ")[1]
            logger.info(f"Extracted user token for single delete: {user_token[:10]}...")
        else:
            logger.warning("No Authorization header found for single delete, falling back to service key authentication")
        
        # Delete from storage with user authentication (auto-detects provider)
        storage_service = get_storage_service(user_token=user_token)
        storage_deleted = await storage_service.delete_file(image.storage_path)
        
        if not storage_deleted:
            logger.warning(f"Failed to delete file from storage: {image.storage_path}")
        
        # Delete from database
        db.delete(image)
        db.commit()
        
        return {
            "status": "success",
            "message": "Project image deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting project image: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/projects/{project_id}/images/generate-featured")
async def generate_featured_image_endpoint(
    request: Request,
    project_id: str,
    db: Session = Depends(get_db)
):
    """Generate AI-powered featured image using blog content from MongoDB"""
    try:
        user = request.state.user
        user_id = user.user.id
        
        # Get request body
        body = await request.json()
        blog_id = body.get("blog_id", "")
        
        if not blog_id:
            raise HTTPException(status_code=400, detail="blog_id is required for featured image generation")
        
        # Validate project ownership
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == user_id
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found or access denied")
        
        # Fetch blog content from MongoDB (same pattern as .py)
        try:
            from app.services.mongodb_service import MongoDBService
            from bson import ObjectId
            
            mongodb_service = MongoDBService()
            mongodb_service.init_sync_db()
            
            # Get blog document from MongoDB
            blog_doc = mongodb_service.get_sync_db()['blogs'].find_one({'_id': ObjectId(blog_id)})
            
            if not blog_doc:
                raise HTTPException(status_code=404, detail="Blog not found in database")
            
            # Extract blog content and country
            blog_content = blog_doc.get('content', '')
            country = blog_doc.get('country', 'India')  # Default to India if not specified
            
            if not blog_content:
                raise HTTPException(status_code=400, detail="Blog has no content to generate image from")
            
            logger.info(f"Fetched blog content: {len(blog_content)} characters, country: {country}")
            
        except Exception as mongo_error:
            logger.error(f"Failed to fetch blog from MongoDB: {str(mongo_error)}")
            raise HTTPException(status_code=500, detail="Failed to fetch blog content from database")
        
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Build image request payload with blog content and country
        image_request = {
            "blog_content": blog_content,  # Use blog_content instead of prompt
            "country": country,            # Add country from MongoDB
            "blog_id": blog_id            # Include blog_id for reference
        }
        
        # Convert project to dict for task
        project_dict = {
            "user_id": str(project.user_id),
            "featured_image_style": project.featured_image_style,
            "name": project.name
        }
        
        
        # Launch featured image generation task
        task_result = generate_featured_image.delay(
            image_request=image_request,
            project_id=project_id,
            project=project_dict,
            request_id=request_id
        )
        
        logger.info(f"Featured image generation started for project_id: {project_id}, request_id: {request_id}")
        
        return {
            "status": "success",
            "message": "Featured image generation started successfully",
            "data": {
                "request_id": request_id,
                "task_id": task_result.id,
                "project_id": project_id,
                "blog_id": blog_id,
                "country": country,
                "project_style": project.featured_image_style,
                "estimated_time": "30-60 seconds"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting featured image generation: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/projects/{project_id}/images/featured/status/{request_id}")
async def get_featured_image_generation_status(
    request: Request,
    project_id: str,
    request_id: str,
    db: Session = Depends(get_db)
):
    """Get status of featured image generation"""
    import time
    start_time = time.time()
    
    try:
        user = request.state.user
        user_id = user.user.id
        
        logger.info(f"🎯 [ENDPOINT] Status request for project: {project_id}, request_id: {request_id}, user: {user_id}")
        
        # Validate project ownership
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == user_id
        ).first()
        
        if not project:
            logger.warning(f"⚠️ [ENDPOINT] Project not found or access denied: {project_id} for user: {user_id}")
            raise HTTPException(status_code=404, detail="Project not found or access denied")
        
        # Get task status directly (no Celery delay for read operations)
        logger.info(f"📊 [ENDPOINT] Getting featured image status for request_id: {request_id}")
        status_start = time.time()
        
        try:
            status_data = get_featured_image_status(request_id)
            status_elapsed = time.time() - status_start
            logger.info(f"✅ [ENDPOINT] Status retrieved successfully in {status_elapsed:.3f}s")
        except Exception as status_error:
            status_elapsed = time.time() - status_start
            logger.error(f"❌ [ENDPOINT] Status retrieval failed after {status_elapsed:.3f}s: {str(status_error)}")
            raise status_error
        
        total_elapsed = time.time() - start_time
        logger.info(f"🏁 [ENDPOINT] Complete request processed in {total_elapsed:.3f}s")
        
        return {
            "status": "success",
            "data": status_data,
            "debug_info": {
                "request_id": request_id,
                "processing_time_seconds": round(total_elapsed, 3)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        total_elapsed = time.time() - start_time
        logger.error(f"❌ [ENDPOINT] Error getting featured image status after {total_elapsed:.3f}s: {str(e)}")
        logger.exception(f"❌ [ENDPOINT] Full error traceback:")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/projects/{project_id}/images/featured")
async def get_featured_images(
    request: Request,
    project_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get all AI-generated featured images for a project"""
    try:
        user = request.state.user
        user_id = user.user.id
        
        # Validate project ownership
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == user_id
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found or access denied")
        
        # Query featured images
        query = db.query(ProjectImage).filter(
            ProjectImage.project_id == project_id,
            ProjectImage.category == "featured_image",
            ProjectImage.is_active == True
        )
        
        # Apply pagination
        offset = (page - 1) * limit
        total_count = query.count()
        images = query.order_by(ProjectImage.created_at.desc()).offset(offset).limit(limit).all()
        
        # Format response
        image_data = [image.to_dict() for image in images]
        
        return {
            "status": "success",
            "data": {
                "project": {
                    "id": str(project.id),
                    "name": project.name,
                    "featured_image_style": project.featured_image_style
                },
                "images": image_data,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total_count,
                    "pages": (total_count + limit - 1) // limit
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching featured images: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
