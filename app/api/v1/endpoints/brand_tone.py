from fastapi import APIRouter, Depends, HTTPException, Request
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.schemas.brand_tone import (
    BrandToneAnalysisRequest, 
    BrandToneAnalysisResponse, 
    StoreBrandToneRequest, 
    StoreBrandToneResponse, 
    FetchBrandToneResponse
)
from app.services.brand_tone_service import BrandToneAnalysisService
from app.db.session import get_db_session
from app.core.logging_config import logger
from sqlalchemy.orm import Session

router = APIRouter()

@router.post(
    "/analyze",
    response_model=BrandToneAnalysisResponse,
    summary="Analyze Brand Tone",
    description="Analyze brand tone from a text paragraph and return tonality values across 5 dimensions: Formality, Attitude, Energy, Clarity"
)
def analyze_brand_tone(
    request: Request,
    tone_request: BrandToneAnalysisRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Analyze brand tone from a text paragraph.
    
    This endpoint takes a paragraph of text and analyzes it to determine the most suitable
    brand tonality across five key dimensions:
    - Formality: Ceremonial, Formal, Neutral, Conversational, Colloquial
    - Attitude: Reverent, Respectful, Direct, Witty, Bold, Irreverent
    - Energy: Serene, Grounded, Upbeat, Excitable, Hype-driven
    - Clarity: Technical, Precise, Clear, Simplified, Abstract, Poetic
    """
    try:
        project_id = request.path_params.get("project_id")
        
        logger.info(f"🎨 Brand tone analysis requested by user {current_user.id}")
        logger.info(f"📝 Paragraph length: {len(tone_request.paragraph)} characters")
        
        with get_db_session() as db:
            # Create brand tone analysis service
            tone_service = BrandToneAnalysisService(
                db=db, 
                user_id=str(current_user.id), 
                project_id=project_id
            )
            
            # Perform brand tone analysis
            analysis_result = tone_service.analyze_brand_tone(tone_request.paragraph)
            
            if analysis_result.get("status") == "success":
                logger.info(f"✅ Brand tone analysis completed successfully")
                
                return BrandToneAnalysisResponse(
                    status="success",
                    message=analysis_result.get("message", "Brand tone analysis completed successfully"),
                    tone_analysis=analysis_result["tone_analysis"]
                )
            else:
                logger.error(f"❌ Brand tone analysis failed: {analysis_result.get('message')}")
                
                # Still return the analysis even if there was an error, with default values
                return BrandToneAnalysisResponse(
                    status="success",
                    message=analysis_result.get("message", "Brand tone analysis completed with fallback values"),
                    tone_analysis=analysis_result["tone_analysis"]
                )
        
    except Exception as e:
        logger.error(f"❌ Error in brand tone analysis endpoint: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Brand tone analysis failed: {str(e)}"
        )

@router.get(
    "/tone-options",
    summary="Get Brand Tone Options",
    description="Get all available brand tone options for each dimension"
)
def get_brand_tone_options():
    """
    Get all available brand tone options for each dimension.
    
    This endpoint returns the complete list of available tone options
    for each of the five brand tone dimensions.
    """
    try:
        tone_options = {
            "formality": [
                {"value": "Ceremonial", "description": "Highly structured, protocol-driven (e.g., royal communication)"},
                {"value": "Formal", "description": "Professional, precise, objective (e.g., financial reports)"},
                {"value": "Neutral", "description": "Clear, concise, balanced (e.g., Wikipedia)"},
                {"value": "Conversational", "description": "Friendly, semi-casual (e.g., Apple)"},
                {"value": "Colloquial", "description": "Relatable, uses idioms/slang (e.g., Innocent Drinks)"}
            ],
            "attitude": [
                {"value": "Reverent", "description": "Deeply respectful and deferential (e.g., military comms)"},
                {"value": "Respectful", "description": "Polite and courteous (e.g., IBM)"},
                {"value": "Direct", "description": "Honest, clear, unembellished (e.g., Basecamp)"},
                {"value": "Witty", "description": "Smart, playful, clever (e.g., Oatly)"},
                {"value": "Bold", "description": "Unapologetic, confident (e.g., Liquid Death)"},
                {"value": "Irreverent", "description": "Rebellious, sarcastic, edgy (e.g., Cards Against Humanity)"}
            ],
            "energy": [
                {"value": "Serene", "description": "Calm, composed (e.g., meditation apps)"},
                {"value": "Grounded", "description": "Thoughtful, steady (e.g., Patagonia)"},
                {"value": "Upbeat", "description": "Energetic and positive (e.g., Canva)"},
                {"value": "Excitable", "description": "High-pitched enthusiasm (e.g., youth brands)"},
                {"value": "Hype-driven", "description": "Loud, urgent, all caps (e.g., Gymshark drops)"}
            ],
            "clarity": [
                {"value": "Technical", "description": "Jargon-heavy, expert-level (e.g., engineering docs)"},
                {"value": "Precise", "description": "Detailed but easy to follow (e.g., The Verge)"},
                {"value": "Clear", "description": "No jargon, plain language (e.g., Google)"},
                {"value": "Simplified", "description": "Chunked, dumbed-down for speed (e.g., Buzzfeed)"},
                {"value": "Abstract", "description": "Conceptual, metaphor-driven (e.g., high-end fashion)"},
                {"value": "Poetic", "description": "Evocative, aesthetic-focused (e.g., Aesop skincare)"}
            ]
        }
        
        return {
            "status": "success",
            "message": "Brand tone options retrieved successfully",
            "tone_options": tone_options
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting brand tone options: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to get brand tone options: {str(e)}"
        )

@router.post(
    "/projects/{project_id}/store",
    response_model=StoreBrandToneResponse,
    summary="Store Brand Tone Settings",
    description="Store the selected brand tone settings for a project in the database"
)
def store_brand_tone_settings(
    project_id: str,
    tone_request: StoreBrandToneRequest,
    current_user: User = Depends(get_current_user)
    
):
    """
    Store brand tone settings for a project.
    
    This endpoint stores the user's selected brand tone values for a specific project
    in the database for future retrieval and use in content generation.
    """
    try:
        logger.info(f"🎨 Storing brand tone settings for project {project_id} by user {current_user.id}")
        
        with get_db_session() as db:
            # Create brand tone analysis service
            tone_service = BrandToneAnalysisService(
                db=db, 
                user_id=str(current_user.id), 
                project_id=project_id
            )
            
            # Separate brand tone settings (4-axis) from person tone
            brand_tone_settings = {
                "formality": tone_request.formality,
                "attitude": tone_request.attitude,
                "energy": tone_request.energy,
                "clarity": tone_request.clarity
            }
            
            person_tone = tone_request.person_tone
            
            # Log detailed input data
            logger.info(f"📊 INPUT DATA for project {project_id}:")
            logger.info(f"  🎨 Brand tone settings: {brand_tone_settings}")
            logger.info(f"  👤 Person tone: '{person_tone}' (type: {type(person_tone)})")
            logger.info(f"  📋 Request object person_tone: '{tone_request.person_tone}' (type: {type(tone_request.person_tone)})")

            # Store brand tone settings and person tone separately
            result = tone_service.store_brand_tone_settings(project_id, brand_tone_settings, person_tone)
            
            if result.get("status") == "success":
                logger.info(f"✅ Brand tone settings stored successfully for project {project_id}")
                
                # Combine for response (maintain API compatibility)
                combined_settings = {
                    **brand_tone_settings,
                    "person_tone": person_tone
                }
                
                return StoreBrandToneResponse(
                    status="success",
                    message=result.get("message", "Brand tone settings stored successfully"),
                    project_id=project_id,
                    brand_tone_settings=combined_settings
                )
            else:
                logger.error(f"❌ Failed to store brand tone settings: {result.get('message')}")
                raise HTTPException(
                    status_code=400, 
                    detail=result.get("message", "Failed to store brand tone settings")
                )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in store brand tone settings endpoint: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to store brand tone settings: {str(e)}"
        )

@router.get(
    "/projects/{project_id}/fetch",
    response_model=FetchBrandToneResponse,
    summary="Fetch Brand Tone Settings",
    description="Fetch the stored brand tone settings for a project from the database"
)
def fetch_brand_tone_settings(
    project_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Fetch brand tone settings for a project.
    
    This endpoint retrieves the stored brand tone values for a specific project
    from the database. Returns null if no settings have been stored yet.
    """
    try:
        logger.info(f"🎨 Fetching brand tone settings for project {project_id} by user {current_user.id}")
        
        with get_db_session() as db:
            # Create brand tone analysis service
            tone_service = BrandToneAnalysisService(
                db=db, 
                user_id=str(current_user.id), 
                project_id=project_id
            )
            
            # Fetch brand tone settings
            result = tone_service.fetch_brand_tone_settings(project_id)
            
            if result.get("status") == "success":
                logger.info(f"✅ Brand tone settings fetched successfully for project {project_id}")
                
                return FetchBrandToneResponse(
                    status="success",
                    message=result.get("message", "Brand tone settings retrieved successfully"),
                    project_id=project_id,
                    brand_tone_settings=result.get("brand_tone_settings")
                )
            else:
                logger.error(f"❌ Failed to fetch brand tone settings: {result.get('message')}")
                raise HTTPException(
                    status_code=404 if "not found" in result.get("message", "").lower() else 400, 
                    detail=result.get("message", "Failed to fetch brand tone settings")
                )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in fetch brand tone settings endpoint: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to fetch brand tone settings: {str(e)}"
        )
