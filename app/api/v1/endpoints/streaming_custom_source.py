"""
🚀 Streaming Custom Source Generation Endpoints
Real-time custom source processing with WebSocket and SSE support
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from app.middleware.auth_middleware import verify_request_origin_sync
from app.services.balance_validator import BalanceValidator
from app.models.project import Project
from app.services.streaming_custom_source_service import StreamingCustomSourceService
from app.core.logging_config import logger
from app.db.session import get_db_session
from pydantic import BaseModel
from typing import Optional, Literal
import json
import asyncio
from datetime import datetime


router = APIRouter()


class StreamingCustomSourceRequest(BaseModel):
    outline_json: list  # Raw outline structure from frontend (array of sections)
    subsection_data: dict  # Raw subsection data from frontend
    source_type: Literal["text", "url"]  # text or url
    content: str  # Direct text OR URL to scrape


@router.post("/custom-source/streaming")
async def create_streaming_custom_source(
    request: Request,
    *,
    streaming_request: StreamingCustomSourceRequest,
    current_user = Depends(verify_request_origin_sync)
):
    """
    🚀 TRUE STREAMING ENDPOINT: Real-time custom source processing with immediate SSE streaming
    Supports both text and URL processing with the same prompt structure
    """
    try:
        # Get user ID
        current_user_id = current_user.user.id
        project_id = request.path_params.get("project_id")
        
        # Validate project and balance
        with get_db_session() as db:
            # Balance validation - use existing service keys
            balance_validator = BalanceValidator(db)
            service_key = "add_custom_source"  # Use existing service key for both text and URL
            balance_check = balance_validator.validate_service_balance(
                user_id=current_user_id,
                service_key=service_key
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
                    async with StreamingCustomSourceService(
                        db=db, 
                        user_id=current_user_id, 
                        project_id=project_id
                    ) as service:
                        
                        # Stream each update immediately as it happens
                        async for update in service.stream_custom_source_processing(
                            outline_json=streaming_request.outline_json,
                            subsection_data=streaming_request.subsection_data,
                            source_type=streaming_request.source_type,
                            content=streaming_request.content
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
                                
                            except GeneratorExit:
                                logger.info("🔌 Client disconnected during streaming")
                                connection_active = False
                                break
                            except Exception as send_error:
                                logger.warning(f"⚠️ Send error (client disconnect): {send_error}")
                                connection_active = False
                                break
                        
                        # Send final completion signal only if connection is active
                        if connection_active:
                            try:
                                final_signal = {
                                    "stage": "stream_complete",
                                    "status": "finished",
                                    "message": "🎉 Custom source processing completed successfully",
                                    "timestamp": datetime.utcnow().isoformat()
                                }
                                yield f"data: {json.dumps(final_signal)}\n\n"
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
                                "stage": "stream_error",
                                "status": "failed",
                                "message": f"❌ Custom source processing failed: {str(stream_error)}",
                                "timestamp": datetime.utcnow().isoformat()
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
        logger.error(f"Streaming custom source creation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))