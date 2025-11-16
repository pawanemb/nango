"""
🚀 Streaming Sources Collection Endpoints
Real-time sources collection with Server-Sent Events support
"""

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from app.middleware.auth_middleware import get_current_user
from app.services.balance_validator import BalanceValidator
from app.models.project import Project
from app.services.streaming_sources_service import StreamingSourcesService
from app.core.logging_config import logger
from app.db.session import get_db_session
from app.models.user import User
import json
import asyncio
from datetime import datetime, timezone
from bson import ObjectId

router = APIRouter()

from pydantic import BaseModel
from typing import Dict, Any, List, Optional, Union

class LatestSourcesResponse(BaseModel):
    sources: Optional[List[Dict[str, Any]]] = None
    total_subsections: Optional[int] = None
    total_sources: Optional[int] = None
    outline: Optional[Dict[str, Any]] = None  # ✅ Step 5
    titles: Optional[List[Union[str, Dict[str, Any]]]] = None  # ✅ Step 4
    categories: Optional[List[Dict[str, Any]]] = None  # ✅ Step 3
    secondary_keywords: Optional[List[Dict[str, Any]]] = None  # ✅ Step 2
    primary_keyword: Optional[Dict[str, Any]] = None  # ✅ Step 1 (changed from str to Dict)
    word_count: Optional[str] = None  # ✅ Word count
    country: Optional[str] = None
    blog_title: Optional[str] = None
    processing_metadata: Optional[Dict[str, Any]] = None
    generated_at: Optional[str] = None
    status: str
    error: Optional[str] = None
    blog_id: str



@router.post(
    "/sources/{blog_id}",
    summary="🎯 MINIMAL STREAMING: Sources collection with essential events only",
    description="Clean streaming with only sources found and completion events"
)
async def collect_sources_streaming_sse(
    request: Request,
    *,
    blog_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user)
):
    """🎯 MINIMAL STREAMING: Only essential events - sources found and completion"""
    
    async def real_time_stream_generator():
        connection_active = True
        try:
            # Capture variables from outer scope to avoid reference issues
            request_payload = payload
            request_blog_id = blog_id  # Capture blog_id from outer scope
            request_user = current_user  # Capture current_user from outer scope
            project_id = request.path_params.get("project_id")
            
            logger.info(f"🚀 Starting stream generator - blog_id: {request_blog_id}, project_id: {project_id}")
            logger.debug(f"📦 Payload keys: {list(request_payload.keys()) if isinstance(request_payload, dict) else 'Not a dict'}")
            
            # 🎯 MINIMAL STREAMING: Only essential events
            if not connection_active:
                logger.warning("🔌 Stream connection lost - stopping generation")
                return
                
            try:
                # Single initialization event
                initial_update = {
                    'status': 'processing', 
                    'message': 'Starting minimal sources collection...', 
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                sse_data = f"data: {json.dumps(initial_update, default=str)}\n\n"
                logger.info(f"🎯 MINIMAL STREAMING: Started")
                yield sse_data
                
            except GeneratorExit:
                logger.info("🔌 Client disconnected during streaming")
                connection_active = False
                return
            except Exception as send_error:
                logger.warning(f"⚠️ Send error (client disconnect): {send_error}")
                connection_active = False
                return
            
            with get_db_session() as db:
                # 🚀 PARALLEL VALIDATION: Run all validations concurrently for streaming
                async def validate_balance_async():
                    """Async balance validation"""
                    balance_validator = BalanceValidator(db)
                    return balance_validator.validate_service_balance(
                        user_id=str(request_user.id),
                        service_key="sources_generation"
                    )
                
                async def validate_project_async():
                    """Async project validation"""
                    project = db.query(Project).filter(Project.id == project_id).first()
                    if not project or str(project.user_id) != str(request_user.id):
                        return {"valid": False, "error": "Project access denied"}
                    return {"valid": True, "project": project}
                
                async def validate_blog_async():
                    """Async blog validation with data extraction"""
                    try:
                        from app.services.mongodb_service import MongoDBService
                        from app.utils.api_utils import APIUtils
                        from bson import ObjectId
                        
                        mongodb_service = MongoDBService()
                        mongodb_service.init_sync_db()
                        
                        blog_doc = APIUtils.get_mongodb_blog_document(
                            mongodb_service, request_blog_id, project_id, str(request_user.id)
                        )
                        
                        # Extract data from MongoDB blog document immediately
                        primary_keyword_array = blog_doc.get("primary_keyword", [])
                        if not primary_keyword_array:
                            return {"valid": False, "error": "No primary keyword found. Please complete previous steps."}
                        
                        latest_primary = primary_keyword_array[-1]
                        primary_keyword = latest_primary.get("keyword")
                        country = blog_doc.get("country", "us")
                        title_array = blog_doc.get("title", [])
                        blog_title = title_array[-1] if title_array else "Untitled Blog"
                        
                        return {
                            "valid": True,
                            "blog_doc": blog_doc,
                            "mongodb_service": mongodb_service,
                            "primary_keyword": primary_keyword,
                            "country": country,
                            "blog_title": blog_title
                        }
                    except Exception as e:
                        return {"valid": False, "error": f"Blog not found: {str(e)}"}
                
                # 🚀 RUN ALL 3 VALIDATIONS IN PARALLEL
                try:
                    balance_result, project_result, blog_result = await asyncio.gather(
                        validate_balance_async(),
                        validate_project_async(),
                        validate_blog_async()
                    )
                    
                    # Check balance validation
                    if not balance_result["valid"]:
                        error_detail = {
                            'status': 'error',
                            'error_type': balance_result["error"],
                            'message': balance_result['message'],
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        }
                        if balance_result["error"] == "insufficient_balance":
                            error_detail.update({
                                'required_balance': balance_result["required_balance"],
                                'current_balance': balance_result["current_balance"],
                                'shortfall': balance_result["shortfall"],
                                'next_refill_time': balance_result.get("next_refill_time").isoformat() if balance_result.get("next_refill_time") else None
                            })
                        
                        if connection_active:
                            try:
                                yield f"data: {json.dumps(error_detail)}\n\n"
                            except Exception:
                                logger.error("Failed to send error message - client disconnected")
                        return
                    
                    # Check project validation
                    if not project_result["valid"]:
                        if connection_active:
                            try:
                                yield f"data: {json.dumps({'status': 'error', 'message': project_result['error'], 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
                            except Exception:
                                logger.error("Failed to send error message - client disconnected")
                        return
                    
                    # Check blog validation
                    if not blog_result["valid"]:
                        if connection_active:
                            try:
                                yield f"data: {json.dumps({'status': 'error', 'message': blog_result['error'], 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
                            except Exception:
                                logger.error("Failed to send error message - client disconnected")
                        return
                    
                    # All validations passed - extract data
                    mongodb_service = blog_result["mongodb_service"]
                    primary_keyword = blog_result["primary_keyword"]
                    country = blog_result["country"]
                    blog_title = blog_result["blog_title"]
                    
                    logger.info(f"✅ All parallel validations passed for streaming - user {request_user.id}, blog {request_blog_id}")
                    
                except Exception as parallel_error:
                    logger.error(f"Parallel validation failed: {parallel_error}")
                    if connection_active:
                        try:
                            yield f"data: {json.dumps({'status': 'error', 'message': f'Validation failed: {str(parallel_error)}', 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
                        except Exception:
                            logger.error("Failed to send error message - client disconnected")
                    return
                
                # ✅ All data already extracted in parallel validation above
                logger.debug(f"Extracted blog_title: {blog_title}")  # Data from parallel validation
                
                # Extract outline from nested payload structure
                outline_data = request_payload.get("outline", {})
                
                # Handle nested outline structure: {"outline": {"outline": {"sections": [...]}}}
                if isinstance(outline_data, dict) and "outline" in outline_data:
                    outline_data = outline_data["outline"]
                
                # Extract sections from the outline structure
                if isinstance(outline_data, dict) and "sections" in outline_data:
                    outline_json = outline_data["sections"]
                    logger.info(f"📊 Extracted {len(outline_json)} outline sections from nested structure")
                else:
                    # Fallback to direct outline array
                    outline_json = outline_data if isinstance(outline_data, list) else []
                    logger.info(f"📊 Using direct outline array with {len(outline_json)} sections")
                
                
                # Initialize streaming service with pre-extracted data
                streaming_service = StreamingSourcesService(
                    db=db, 
                    user_id=str(request_user.id), 
                    project_id=project_id,
                    blog_id=request_blog_id
                )
                
                # Pass pre-extracted MongoDB data to avoid duplicate queries
                service_config = {
                    "outline": outline_json,
                    "primary_keyword": primary_keyword,
                    "country": country,
                    "blog_title": blog_title
                }
                
                # Stream sources collection - single attempt
                sources_collected = False
                all_sources_data = []  # Collect all subsection data for sources.generated
                
                try:
                    async for update in streaming_service.collect_sources_openrouter_focused_streaming(**service_config):
                        # Check if connection is still active
                        if not connection_active:
                            logger.warning("🔌 Stream connection lost - stopping generation")
                            break
                            
                        try:
                            # 🎯 MINIMAL STREAMING: Only essential events
                            sse_data = f"data: {json.dumps(update, default=str)}\n\n"
                            
                            # Optimized logging: Only log important status changes
                            status = update.get('status', 'unknown')
                            if status in ['completed', 'failed', 'found_websites']:
                                logger.info(f"🎯 {status.upper()}")
                            else:
                                logger.debug(f"🎯 {status}")
                                
                            yield sse_data
                            
                            # 💾 COLLECT COMPLETED SUBSECTION DATA for sources.generated
                            if update.get('status') in ['subsection_completed', 'heading_completed']:
                                subsection_data = {
                                    "title": update.get('subsection_title', ''),
                                    "heading_index": update.get('heading_index', 0),
                                    "subsection_index": update.get('subsection_index', 0),
                                    "heading_title": update.get('heading_title', ''),
                                    "is_direct_heading": update.get('is_direct_heading', False),
                                    "sources": update.get('sources', []),  # Website URLs and titles
                                    "informations": update.get('informations', {}),  # AI analyzed content
                                    "processed_at": update.get('timestamp'),
                                    "sources_count": len(update.get('sources', []))
                                }
                                all_sources_data.append(subsection_data)
                                logger.info(f"📦 Collected data for subsection: {subsection_data['title']} ({subsection_data['sources_count']} sources)")
                            
                            # Check if sources collection completed successfully
                            if update.get('status') == 'processing_complete':
                                sources_collected = True
                                break
                            
                        except GeneratorExit:
                            logger.info("🔌 Client disconnected during streaming")
                            connection_active = False
                            break
                        except Exception as send_error:
                            logger.warning(f"⚠️ Send error (client disconnect): {send_error}")
                            connection_active = False
                            break
                    
                except Exception as collection_error:
                    logger.error(f"Sources collection failed: {collection_error}")
                    if connection_active:
                        try:
                            error_update = {
                                'status': 'failed',
                                'message': f'Sources collection failed: {str(collection_error)}',
                                'timestamp': datetime.now(timezone.utc).isoformat()
                            }
                            yield f"data: {json.dumps(error_update)}\n\n"
                            yield f"data: [DONE]\n\n"
                        except Exception:
                            logger.error("Failed to send error message - client disconnected")
                    return
                
                # Save results to MongoDB sources.generated + outlines.final (async operation)
                if connection_active and sources_collected:
                    try:
                        import pytz
                        current_time = datetime.now(timezone.utc)
                        
                        # Prepare outlines final data (basic completion)
                        outlines_final_data = {
                            "outline": request_payload.get("outline", {}),
                            "sources_collected": True,
                            "finalized_at": current_time,
                            "primary_keyword": primary_keyword,
                            "country": country,
                            "blog_title": blog_title,
                            "tag": "final"
                        }
                        
                        # Prepare sources generated data (complete raw data)
                        sources_generated_data = {
                            "subsections_data": all_sources_data,  # All subsections with sources + AI analysis
                            "outline": request_payload.get("outline", {}),
                            "total_subsections": len(all_sources_data),
                            "total_sources": sum(item.get('sources_count', 0) for item in all_sources_data),
                            "primary_keyword": primary_keyword,
                            "country": country,
                            "blog_title": blog_title,
                            "generated_at": current_time,
                            "processing_metadata": {
                                "queries_per_subsection": 5,
                                "results_per_query": 2,
                                "max_sources_per_subsection": 10
                            },
                            "tag": "generated"
                        }
                        
                        # Prepare step tracking data for outline completion
                        outline_step_tracking_data = {
                            "step": "outline",
                            "status": "done",
                            "completed_at": current_time
                        }
                        
                        # Prepare step tracking data for sources generation
                        sources_step_tracking_data = {
                            "step": "sources",
                            "status": "generated",
                            "completed_at": current_time
                        }
                        
                        # Non-blocking MongoDB save operation
                        def save_to_mongodb():
                            try:
                                from bson import ObjectId
                                mongodb_service.get_sync_db()['blogs'].update_one(
                                    {"_id": ObjectId(request_blog_id)},
                                    {
                                        "$push": {
                                            "outlines": outlines_final_data,
                                            "sources": sources_generated_data,
                                            "step_tracking.outline": outline_step_tracking_data,
                                            "step_tracking.sources": sources_step_tracking_data
                                        },
                                        "$set": {
                                            "step_tracking.current_step": "sources",
                                            "updated_at": current_time
                                        }
                                    }
                                )
                                return True
                            except Exception as e:
                                logger.error(f"MongoDB save failed: {e}")
                                return False
                        
                        # Execute MongoDB save in background to avoid blocking stream
                        loop = asyncio.get_event_loop()
                        save_success = await loop.run_in_executor(None, save_to_mongodb)
                        
                        if save_success:
                            final_signal = {
                                'status': 'completed', 
                                'message': 'Sources collection complete & saved to MongoDB! 🎉', 
                                'blog_id': request_blog_id,
                                'saved_to': ['outlines', 'sources'],
                                'raw_data_saved': True,
                                'total_subsections': len(all_sources_data),
                                'total_sources': sum(item.get('sources_count', 0) for item in all_sources_data),
                                'sections_processed': len(outline_json),
                                'timestamp': datetime.now(timezone.utc).isoformat()
                            }
                            yield f"data: {json.dumps(final_signal)}\n\n"
                        else:
                            error_signal = {
                                'status': 'completed_with_warning', 
                                'message': 'Sources collected but failed to save to MongoDB', 
                                'blog_id': request_blog_id,
                                'timestamp': datetime.now(timezone.utc).isoformat()
                            }
                            yield f"data: {json.dumps(error_signal)}\n\n"
                        
                        yield f"data: [DONE]\n\n"
                        
                    except Exception as save_error:
                        logger.error(f"Failed to save to MongoDB: {save_error}")
                        try:
                            error_signal = {
                                'status': 'completed_with_error', 
                                'message': 'Sources collected but save operation failed', 
                                'error': str(save_error),
                                'timestamp': datetime.now(timezone.utc).isoformat()
                            }
                            yield f"data: {json.dumps(error_signal)}\n\n"
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
                        'status': 'stream_error',
                        'message': f'❌ Streaming failed: {str(stream_error)}',
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                    yield f"data: {json.dumps(error_update)}\n\n"
                    yield f"data: [DONE]\n\n"
                except Exception:
                    logger.error("Failed to send error message - client disconnected")
        finally:
            logger.info("🏁 Stream generator cleanup completed")
    
    # Get origin for CORS
    origin = request.headers.get("origin", "*")
    
    return StreamingResponse(
        real_time_stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept, Cache-Control, X-Requested-With",
            "Access-Control-Expose-Headers": "Content-Type, Cache-Control, Connection",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Transfer-Encoding": "chunked",  # Enable chunked encoding
            "Keep-Alive": "timeout=300, max=1000"  # 5 minute timeout
        }
    )


@router.put("/sources/{blog_id}")
def update_sources_raw(
    request: Request,
    *,
    blog_id: str,
    body: Dict[str, Any],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Add raw sources data to existing sources.generated array.
    Optimized for speed - minimal processing, direct data dump.
    """
    project_id = request.path_params.get("project_id")
    sources_data = body.get("sources", {})
    
    try:
        current_user_id = str(current_user.id)
        
        # Fast validation
        from app.utils.api_utils import APIUtils
        APIUtils.validate_uuid(project_id)
        APIUtils.validate_objectid(blog_id)
        
        if not sources_data:
            raise HTTPException(status_code=400, detail="sources object required")
        
        # Single MongoDB connection
        from app.services.mongodb_service import MongoDBService
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
                "sources": 1,
                "country": 1
            }
        )
        
        if not blog_doc:
            raise HTTPException(status_code=404, detail="Blog not found")
        
        # Minimal data preparation
        import pytz
        current_time = datetime.now(timezone.utc)
        
        # Create new sources entry matching POST structure
        sources_entry = {
            "subsections_data": sources_data,  # Match POST structure
            "generated_at": current_time,
            "tag": "updated"
        }
        
        # Fast append to sources array
        mongodb_service.get_sync_db()['blogs'].update_one(
            {"_id": ObjectId(blog_id)},
            {
                "$push": {"sources": sources_entry},
                "$set": {"updated_at": current_time}
            }
        )
        
        # Minimal response
        return {
            "status": "updated",
            "sources": sources_data,
            "blog_id": blog_id,
            "message": "Raw sources data added to sources"
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating sources: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources/{blog_id}")
def get_latest_sources_data(
    request: Request,
    *,
    blog_id: str,
    current_user: User = Depends(get_current_user)
) -> LatestSourcesResponse:
    """
    Get the latest sources data from a blog's sources.generated array.
    This retrieves complete raw sources data from the streaming sources service.
    
    Args:
        blog_id: MongoDB blog document ID
        
    Returns:
        Latest sources data with all subsection sources and AI analysis
    """
    try:
        # Get project_id from path parameters
        project_id = request.path_params.get("project_id")
        
        # Validate UUID and ObjectId formats
        from app.utils.api_utils import APIUtils
        APIUtils.validate_uuid(project_id)
        APIUtils.validate_objectid(blog_id)
        
        # Get user ID
        current_user_id = str(current_user.id)
        
        # Verify project exists and access
        with get_db_session() as db:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            project = APIUtils.verify_project_access(project_id, current_user_id, db)
        
        # Get blog data from MongoDB
        from app.services.mongodb_service import MongoDBService
        mongodb_service = MongoDBService()
        mongodb_service.init_sync_db()
        
        # Find the blog document with projection for performance
        # ✅ INCLUDE ALL PREVIOUS STEPS (matching outline endpoint pattern)
        projection = {
            "sources": 1,
            "outlines": 1,  # ✅ Step 5
            "titles": 1,  # ✅ Step 4
            "categories": 1,  # ✅ Step 3
            "secondary_keywords": 1,  # ✅ Step 2
            "primary_keyword": 1,  # ✅ Step 1
            "word_count": 1,  # ✅ Word count
            "country": 1,
            "title": 1,  # For blog_title fallback
            "_id": 1
        }
        blog_doc = APIUtils.get_mongodb_blog_document(
            mongodb_service, blog_id, project_id, current_user_id, projection
        )
        
        # Get sources data from simple array
        sources_array = blog_doc.get("sources", [])
        country = blog_doc.get("country", "us")

        # Get the latest sources data (last item in array) - CURRENT STEP
        sources_data = None
        total_subsections = None
        total_sources = None
        processing_metadata = None
        generated_at = None

        if sources_array:
            latest_entry = sources_array[-1]  # Last item = latest
            sources_data = latest_entry.get("subsections_data", [])  # Array of subsection data
            total_subsections = latest_entry.get("total_subsections", 0)
            total_sources = latest_entry.get("total_sources", 0)
            processing_metadata = latest_entry.get("processing_metadata", {})
            generated_at_raw = latest_entry.get("generated_at")
            # Convert datetime object to string if needed
            if generated_at_raw:
                from datetime import datetime
                generated_at = generated_at_raw.isoformat() if isinstance(generated_at_raw, datetime) else generated_at_raw
            else:
                generated_at = None

        # ✅ GET ALL PREVIOUS STEPS DATA (following outline endpoint pattern)

        # Step 5: Outline
        outlines_array = blog_doc.get("outlines", [])
        outline_data = None
        if outlines_array:
            latest_outline = outlines_array[-1]
            outline_data = latest_outline.get("outline", {})

        # Step 4: Titles
        titles_array = blog_doc.get("titles", [])
        latest_titles = []
        if titles_array:
            latest_titles_final = titles_array[-1]
            latest_titles = latest_titles_final.get("titles", [])

        # Step 3: Categories
        categories_array = blog_doc.get("categories", [])
        latest_categories = []
        if categories_array:
            latest_categories_final = categories_array[-1]
            latest_categories = latest_categories_final.get("categories", [])

        # Step 2: Secondary Keywords
        secondary_keywords_array = blog_doc.get("secondary_keywords", [])
        latest_secondary_keywords = []
        if secondary_keywords_array:
            latest_secondary_final = secondary_keywords_array[-1]
            latest_secondary_keywords = latest_secondary_final.get("keywords", [])

        # Step 1: Primary Keyword
        primary_keyword_array = blog_doc.get("primary_keyword", [])
        latest_primary_final = None
        if primary_keyword_array:
            latest_primary_final = primary_keyword_array[-1]

        # Word Count
        word_count_array = blog_doc.get("word_count", [])
        latest_word_count = None
        if word_count_array:
            latest_word_count = word_count_array[-1]

        # Blog Title (from title array or fallback to sources data)
        title_array = blog_doc.get("title", [])
        blog_title = title_array[-1] if title_array else "Untitled Blog"
        
        response = LatestSourcesResponse(
            sources=sources_data,
            total_subsections=total_subsections,
            total_sources=total_sources,
            outline=outline_data,  # ✅ Step 5
            titles=latest_titles,  # ✅ Step 4
            categories=latest_categories,  # ✅ Step 3
            secondary_keywords=latest_secondary_keywords,  # ✅ Step 2
            primary_keyword=latest_primary_final,  # ✅ Step 1 (now returns full Dict)
            word_count=latest_word_count,  # ✅ Word count
            country=country,
            blog_title=blog_title,
            processing_metadata=processing_metadata,
            generated_at=generated_at if generated_at else None,
            status="success" if sources_data else "no_data",
            error=None,
            blog_id=blog_id
        )
        
        return response
        
    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    except Exception as e:
        logger.error(f"Error fetching latest sources data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

