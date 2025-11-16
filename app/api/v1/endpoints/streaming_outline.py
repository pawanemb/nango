"""
🚀 Streaming Outline Generation Endpoint
Real-time outline generation with SSE support
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.middleware.auth_middleware import verify_request_origin_sync
from app.services.balance_validator import BalanceValidator
from app.models.project import Project
from app.services.streaming_outline_service import StreamingOutlineService
from app.core.logging_config import logger
from app.db.session import get_db_session
from app.services.mongodb_service import MongoDBService
from app.utils.api_utils import APIUtils
from bson import ObjectId
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel
import json
import asyncio
from datetime import datetime
import pytz


router = APIRouter()


# ConnectionManager removed - not used since only SSE endpoint is active


@router.post("/streaming-outline/{blog_id}")
async def create_streaming_outline(
    request: Request,
    *,
    blog_id: str,
    current_user = Depends(verify_request_origin_sync)
):
    """
    🚀 TRUE STREAMING ENDPOINT: Real-time outline generation with immediate SSE streaming
    Gets data from MongoDB blog document instead of payload
    """
    try:
        # Get user ID and project_id
        current_user_id = current_user.user.id
        project_id = request.path_params.get("project_id")
        
        # Validate project_id and blog_id formats first
        APIUtils.validate_uuid(project_id)
        APIUtils.validate_objectid(blog_id)
        
        # Get blog data from MongoDB to extract required data
        mongodb_service = MongoDBService()
        mongodb_service.init_sync_db()
        
        # Find the blog document
        blog_doc = APIUtils.get_mongodb_blog_document(
            mongodb_service, blog_id, project_id, current_user_id
        )
        
        # Extract data from MongoDB document like other steps
        # Get primary keyword from simple array (latest)
        primary_keyword_array = blog_doc.get("primary_keyword", [])
        if not primary_keyword_array:
            raise HTTPException(
                status_code=400,
                detail="No primary keyword found. Please complete the previous steps first."
            )
        
        latest_primary = primary_keyword_array[-1]
        primary_keyword = latest_primary.get("keyword")
        
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
        
        # Extract country from root level in MongoDB
        country = blog_doc.get("country", "us")
        
        # Validate project and balance
        with get_db_session() as db:
            # Balance validation
            balance_validator = BalanceValidator(db)
            balance_check = balance_validator.validate_service_balance(
                user_id=current_user_id,
                service_key="outline_generation_streaming"
            )
            
            if not balance_check["valid"]:
                if balance_check["error"] == "insufficient_balance":
                    raise HTTPException(
                        status_code=402,
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
            
            # Validate project
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
            
            if str(project.user_id) != str(current_user_id):
                raise HTTPException(status_code=403, detail="Access denied to this project")
            
            # 🚀 TRUE STREAMING GENERATOR: Real-time updates
            async def real_time_stream_generator():
                connection_active = True
                try:
                    # Create streaming service inside generator for proper context
                    async with StreamingOutlineService(
                        db=db, 
                        user_id=current_user_id, 
                        project_id=project_id
                    ) as service:
                        
                        # Stream each update immediately as it happens using MongoDB data
                        async for update in service.stream_outline_generation(
                            primary_keyword=primary_keyword,
                            subcategory=selected_subcategory,
                            country=country,
                            blog_id=blog_id
                        ):
                            # Check if connection is still active
                            if not connection_active:
                                logger.warning("🔌 Stream connection lost - stopping generation")
                                break
                                
                            try:
                                # 🔥 IMMEDIATE STREAMING: Send each update as soon as it's generated
                                sse_data = f"data: {json.dumps(update, default=str)}\n\n"
                                logger.info(f"🔥 STREAMING: {update.get('stage', 'unknown')} - {update.get('message', '')[:50]}...")
                                yield sse_data
                                
                                # Faster streaming - no artificial delay for maximum speed
                                
                            except GeneratorExit:
                                logger.info("🔌 Client disconnected during streaming")
                                connection_active = False
                                break
                            except Exception as send_error:
                                logger.warning(f"⚠️ Send error (client disconnect): {send_error}")
                                connection_active = False
                                break
                        
                        # Send simple completion signal only if connection is active
                        if connection_active:
                            try:
                                yield f"data: [DONE]\n\n"
                            except Exception:
                                logger.info("📤 Stream completed - client already disconnected")
                        
                except asyncio.CancelledError:
                    logger.info("🛑 Stream cancelled by client")
                    connection_active = False
                except GeneratorExit:
                    logger.info("🔌 Stream generator closed by client")
                    connection_active = False
                except Exception as stream_error:
                    logger.error(f"💥 Stream generator error: {stream_error}")
                    if connection_active:
                        try:
                            error_update = {
                                "status": "stream_error",
                                "message": f"❌ Streaming failed: {str(stream_error)}"
                            }
                            yield f"data: {json.dumps(error_update)}\n\n"
                            yield f"data: [DONE]\n\n"
                        except Exception:
                            logger.error("Failed to send error message - client disconnected")
                finally:
                    logger.info("🏁 Stream generator cleanup completed")
            
            # Return streaming response with proper headers for real-time streaming
            return StreamingResponse(
                real_time_stream_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Cache-Control",
                    "X-Accel-Buffering": "no",  # Disable nginx buffering
                    "Transfer-Encoding": "chunked",  # Enable chunked encoding
                    "Keep-Alive": "timeout=300, max=1000"  # 5 minute timeout
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Streaming outline creation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket endpoint removed - not being used


# Hybrid endpoint removed - not being used


class LatestAdvancedOutlineResponse(BaseModel):
    advanced_outlines: Optional[List[Dict[str, Any]]] = None
    primary_keyword: Optional[Dict[str, Any]] = None
    secondary_keywords: Optional[List[Dict[str, Any]]] = None
    categories: Optional[List[Dict[str, Any]]] = None
    titles: Optional[List[Union[str, Dict[str, Any]]]] = None
    word_count: Optional[str] = None
    status: str
    country: Optional[str] = None
    error: Optional[str] = None
    blog_id: str
    total_websites: Optional[int] = None
    successful_outlines: Optional[int] = None
    service_type: Optional[str] = None

@router.get("/streaming-outline/{blog_id}")
def get_latest_advanced_outline_data(
    request: Request,
    *,
    blog_id: str,
    current_user = Depends(verify_request_origin_sync)
) -> LatestAdvancedOutlineResponse:
    """
    Get the latest advanced outline data from a blog's outlines.advanced array.
    This retrieves results from the streaming outline service.
    
    Args:
        blog_id: MongoDB blog document ID
        
    Returns:
        Latest advanced outline data with website analysis information
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
            "outlinesuggestion": 1,
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
        
        # Get outline suggestion data from simple array (latest)
        outlinesuggestion_array = blog_doc.get("outlinesuggestion", [])
        country = blog_doc.get("country", "us")
        
        # Get the latest outline suggestion data (simple - just latest array)
        latest_outline_data = None
        
        if outlinesuggestion_array:
            latest_outline_data = outlinesuggestion_array[-1]  # Latest entry from outlinesuggestion array
        
        # Get the latest primary keyword from simple array
        primary_keyword_array = blog_doc.get("primary_keyword", [])
        latest_primary_final = None
        if primary_keyword_array:
            latest_primary_final = primary_keyword_array[-1]
        
        # Get the latest secondary keywords from simple array
        secondary_keywords_array = blog_doc.get("secondary_keywords", [])
        latest_secondary_keywords = []
        if secondary_keywords_array:
            latest_secondary_final = secondary_keywords_array[-1]
            latest_secondary_keywords = latest_secondary_final.get("keywords", [])
        
        # Get the latest categories from simple array
        categories_array = blog_doc.get("categories", [])
        latest_categories = []
        if categories_array:
            latest_categories_final = categories_array[-1]
            latest_categories = latest_categories_final.get("categories", [])
        
        # Get the latest titles from simple array
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
        
        response = LatestAdvancedOutlineResponse(
            advanced_outlines=[latest_outline_data] if latest_outline_data else [],
            primary_keyword=latest_primary_final,
            secondary_keywords=latest_secondary_keywords,
            categories=latest_categories,
            titles=latest_titles,
            word_count=latest_word_count,
            status="success" if latest_outline_data else "no_data",
            country=country,
            error=None,
            blog_id=blog_id,
            total_websites=latest_outline_data.get("total_websites") if latest_outline_data else None,
            successful_outlines=latest_outline_data.get("successful_outlines") if latest_outline_data else None,
            service_type=latest_outline_data.get("service_type") if latest_outline_data else None
        )
        
        return response
        
    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    except Exception as e:
        logger.error(f"Error fetching latest advanced outline: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
