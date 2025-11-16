"""
Text Shortening Streaming API - Minimal Version
Only streaming endpoint with simple validation
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from app.db.session import get_db_session
from app.middleware.auth_middleware import verify_request_origin_sync
from app.models.project import Project
from typing import Dict, Any, Optional
from app.core.logging_config import logger
from pydantic import BaseModel, Field
from app.services.convert_to_list_service import ConvertToListService
from app.services.balance_validator import BalanceValidator
import asyncio
import json
from datetime import datetime

router = APIRouter()


class StreamingShorteningRequest(BaseModel):
    """Minimal request model for streaming text shortening"""
    text_to_edit: str = Field(..., description="The main text content to be shortened")
    primary_keyword: Optional[str] = Field("", description="SEO keyword to preserve in the content")
    before_context: Optional[str] = Field("", description="Context from before the text")
    after_context: Optional[str] = Field("", description="Context from after the text")


@router.post("/stream")
async def stream_convert_to_list(
    request: Request,
    *,
    streaming_request: StreamingShorteningRequest,
    current_user = Depends(verify_request_origin_sync)
):
    """
    Stream real-time text shortening with live progress updates.
    
    Args:
        streaming_request: Request body containing:
            - text_to_edit: Text content to shorten
            - primary_keyword: SEO keyword to preserve (optional)
            - language: Automatically picked from project.languages[0]
        
    Returns:
        StreamingResponse with Server-Sent Events
    """
    project_id = request.path_params.get("project_id")
    
    logger.info(f"=== STREAMING TEXT SHORTENING REQUEST ===")
    logger.info(f"Project ID: {project_id}")
    logger.info(f"Text Length: {len(streaming_request.text_to_edit)} characters")
    logger.info(f"Primary Keyword: {streaming_request.primary_keyword}")
    logger.info(f"Before Context Length: {len(streaming_request.before_context or '')} characters")
    logger.info(f"After Context Length: {len(streaming_request.after_context or '')} characters")
    logger.info(f"========================================")
    
    async def generate_streaming_response():
        """Generate Server-Sent Events for real-time text shortening"""
        try:
            # Get user ID
            current_user_id = current_user.user.id
            
            # Simple validation and processing
            with get_db_session() as db:
                # Simple balance validation
                logger.info(f"💳 BALANCE VALIDATION PROCESS:")
                logger.info(f"💳 User ID: {current_user_id}")
                logger.info(f"💳 Service key: convert_to_list")
                
                balance_validator = BalanceValidator(db)
                balance_check = balance_validator.validate_service_balance(
                    user_id=current_user_id,
                    service_key="convert_to_list"
                )
                
                logger.info(f"💳 Balance check result: {balance_check}")
                logger.info(f"💳 Is valid: {balance_check.get('valid', False)}")
                logger.info(f"💳 Current balance: ${balance_check.get('current_balance', 0)}")
                logger.info(f"💳 Required balance: ${balance_check.get('required_balance', 0)}")
                
                if not balance_check["valid"]:
                    logger.error(f"❌ Balance validation failed: {balance_check.get('message', 'Unknown error')}")
                    yield f"data: {json.dumps({'event': 'error', 'message': 'Insufficient balance'})}\n\n"
                    return
                
                logger.info(f"💳 ✅ Balance validation passed!")
                
                # Get project and extract brand tonality
                project = db.query(Project).filter(Project.id == project_id).first()
                if not project or str(project.user_id) != str(current_user_id):
                    yield f"data: {json.dumps({'event': 'error', 'message': 'Project access denied'})}\n\n"
                    return
                
                # Extract brand tonality and language from project settings
                brand_tonality = "professional and clear"  # Default
                language = "English"  # Default
                
                logger.info(f"🔍 PROJECT SETTINGS EXTRACTION:")
                logger.info(f"  - Project ID: {project.id}")
                logger.info(f"  - Project Name: {project.name}")
                logger.info(f"  - Project Brand Tone Settings: {project.brand_tone_settings}")
                logger.info(f"  - Project Languages: {project.languages}")
                
                if project.brand_tone_settings:
                    try:
                        settings = project.brand_tone_settings
                        formality = settings.get('formality', 'Professional').lower()
                        attitude = settings.get('attitude', 'Direct').lower()
                        energy = settings.get('energy', 'Grounded').lower()
                        clarity = settings.get('clarity', 'Clear').lower()
                        brand_tonality = f"{formality}, {attitude}, {energy}, and {clarity}"
                        logger.info(f"🎨 ✅ Extracted brand tonality from project: {brand_tonality}")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to extract brand tonality: {e}")
                        logger.info(f"🎨 Using default brand tonality: {brand_tonality}")
                else:
                    logger.info(f"🎨 No brand tone settings found, using default: {brand_tonality}")
                
                # Extract language from project languages
                if project.languages and len(project.languages) > 0:
                    language = project.languages[0]  # Use first language
                    logger.info(f"🌐 ✅ Extracted language from project: {language}")
                else:
                    logger.info(f"🌐 No project languages found, using default: {language}")
                
                logger.info(f"🎯 FINAL PARAMETERS FOR PROCESSING:")
                logger.info(f"  - Brand Tonality: {brand_tonality}")
                logger.info(f"  - Language: {language}")
                logger.info(f"  - Primary Keyword: {streaming_request.primary_keyword}")
                logger.info(f"  - Text Length: {len(streaming_request.text_to_edit)} characters")
                
                # Create service and start streaming
                service = ConvertToListService(db=db, user_id=current_user_id, project_id=project_id)
                
                # Stream the shortening process in REAL-TIME
                async for event_data in service.stream_convert_to_list_workflow(
                    text_to_edit=streaming_request.text_to_edit,
                    brand_tonality=brand_tonality,  # From project settings
                    primary_keyword=streaming_request.primary_keyword,
                    language=language,  # From project settings
                    reduction_percentage=30,  # Fixed reduction percentage
                    before_context=streaming_request.before_context or "",
                    after_context=streaming_request.after_context or ""
                ):
                    # Format as Server-Sent Event and stream immediately
                    event_json = json.dumps(event_data)
                    sse_data = f"data: {event_json}\n\n"
                    yield sse_data
                    
                    # NO DELAY - Stream as fast as OpenAI provides data
                    # Log real-time events for debugging
                    if event_data.get("event") == "chunk_stream_content":
                        logger.info(f"🌊 REAL-TIME: {event_data.get('content_piece', '')[:50]}...")
                
                # ✅ Usage tracking and billing is now handled by ConvertToListService
                # The streaming service will record usage with proper token tracking
                # and the EnhancedLLMUsageService will handle billing automatically
                logger.info(f"✅ Text shortening completed successfully!")
                logger.info(f"✅ Usage tracking and billing handled by service layer")
        
        except Exception as e:
            logger.error(f"❌ Streaming error: {str(e)}")
            error_event = {
                "event": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return StreamingResponse(
        generate_streaming_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/health")
def convert_to_list_health() -> Dict[str, Any]:
    """Health check endpoint for text shortening service"""
    return {
        "service": "convert_to_list_streaming",
        "status": "healthy",
        "features": ["streaming_only", "brand_tone_from_project", "simple_validation"],
        "timestamp": datetime.now().isoformat()
    }