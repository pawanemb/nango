from fastapi import APIRouter, Depends, HTTPException, Request
from app.db.session import get_db_session
from app.middleware.auth_middleware import verify_request_origin_sync
from app.models.project import Project
from typing import Dict, Any, Optional
from app.core.logging_config import logger
from pydantic import BaseModel
from app.services.plagiarism_service import PlagiarismService
from app.services.balance_validator import BalanceValidator

router = APIRouter()

class PlagiarismRequest(BaseModel):
    text: str
    language: Optional[str] = "en"
    country: Optional[str] = "us"

@router.post("/")
def check_plagiarism(
    request: Request,
    *,
    plagiarism_request: PlagiarismRequest,
    current_user = Depends(verify_request_origin_sync)
) -> Dict[str, Any]:
    """
    Check text for plagiarism using Winston AI.
    
    Args:
        plagiarism_request: Request body containing:
            text: The text content to check for plagiarism
            language: Language code (default: "en")
            country: Country code (default: "us")
    """
    project_id = request.path_params.get("project_id")
    
    # Log the complete API request payload
    logger.info(f"=== PLAGIARISM DETECTION API REQUEST ===")
    logger.info(f"Project ID: {project_id}")
    logger.info(f"Request Payload: {plagiarism_request.model_dump()}")
    logger.info(f"Text length: {len(plagiarism_request.text)} characters")
    logger.info(f"Language: {plagiarism_request.language}")
    logger.info(f"Country: {plagiarism_request.country}")
    logger.info(f"=========================================")
    
    try:
        # Get user ID from nested user object
        try:
            current_user_id = current_user.user.id
            logger.info(f"✅ Successfully extracted user_id: {current_user_id}")
        except Exception as user_extract_error:
            logger.error(f"❌ Failed to extract user_id: {user_extract_error}")
            logger.error(f"❌ current_user structure: {current_user}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid user authentication structure: {str(user_extract_error)}"
            )
        
        project = None
        # Get project data
        logger.info(f"🔍 DEBUG: Opening database session...")
        with get_db_session() as db:
            logger.info(f"✅ Database session opened successfully")
            
            # Balance validation - Check balance BEFORE processing
            logger.info(f"🔍 DEBUG: Starting balance validation for user {current_user_id}")
            try:
                balance_validator = BalanceValidator(db)
                logger.info(f"✅ BalanceValidator created successfully")
                
                balance_check = balance_validator.validate_service_balance(
                    user_id=current_user_id,
                    service_key="plagiarism_detection"
                )
                logger.info(f"✅ Balance validation completed: {balance_check}")
            except Exception as balance_error:
                logger.error(f"❌ Balance validation failed: {balance_error}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Balance validation error: {str(balance_error)}"
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
            
            logger.info(f"✅ Balance validation passed for user {current_user_id}: ${balance_check['current_balance']:.2f} >= ${balance_check['required_balance']:.2f}")
            
            # Project lookup
            logger.info(f"🔍 DEBUG: Looking up project with ID: {project_id}")
            try:
                project = db.query(Project).filter(Project.id == project_id).first()
                logger.info(f"✅ Project query completed. Found: {project is not None}")
                if project:
                    logger.info(f"✅ Project details: ID={project.id}, Name={project.name}, User ID={project.user_id}")
            except Exception as project_error:
                logger.error(f"❌ Project lookup failed: {project_error}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Project lookup error: {str(project_error)}"
                )
            
            if not project:
                logger.error(f"❌ Project {project_id} not found in database")
                raise HTTPException(
                    status_code=404,
                    detail=f"Project {project_id} not found"
                )
            
            # Verify project ownership
            logger.info(f"🔍 DEBUG: Verifying project ownership. Project user_id: {project.user_id}, Current user_id: {current_user_id}")
            if str(project.user_id) != str(current_user_id):
                logger.error(f"❌ Project ownership mismatch: {project.user_id} != {current_user_id}")
                raise HTTPException(
                    status_code=403,
                    detail="You don't have access to this project"
                )
            logger.info(f"✅ Project ownership verified")

            # Start the plagiarism detection
            logger.info(f"=== CALLING PLAGIARISM SERVICE ===")
            logger.info(f"Service Parameters:")
            logger.info(f"  - Text length: {len(plagiarism_request.text)} characters")
            logger.info(f"  - Language: {plagiarism_request.language}")
            logger.info(f"  - Country: {plagiarism_request.country}")
            logger.info(f"  - Project ID: {project_id}")
            logger.info(f"  - User ID: {current_user_id}")
            
            # Create PlagiarismService
            logger.info(f"🔍 DEBUG: Creating PlagiarismService...")
            try:
                service = PlagiarismService(db=db, user_id=current_user_id, project_id=project_id)
                logger.info(f"✅ PlagiarismService created successfully")
            except Exception as service_error:
                logger.error(f"❌ Failed to create PlagiarismService: {service_error}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Service creation error: {str(service_error)}"
                )
            
            # Call check_plagiarism_workflow
            logger.info(f"🔍 DEBUG: Calling check_plagiarism_workflow...")
            try:
                result = service.check_plagiarism_workflow(
                    text=plagiarism_request.text,
                    language=plagiarism_request.language,
                    country=plagiarism_request.country,
                    project_id=project_id,
                    project=project
                )
                logger.info(f"✅ check_plagiarism_workflow completed successfully")
            except Exception as workflow_error:
                logger.error(f"❌ check_plagiarism_workflow failed: {workflow_error}")
                logger.error(f"❌ Full traceback:", exc_info=True)
                raise HTTPException(
                    status_code=400,
                    detail=f"Plagiarism detection workflow error: {str(workflow_error)}"
                )
            
            logger.info(f"=== PLAGIARISM DETECTION COMPLETED ===")
            logger.info(f"Plagiarism score: {result.get('plagiarism_score', 0)}%")
            logger.info(f"Sources found: {result.get('sources_found', 0)}")
            logger.info(f"Credits used: {result.get('credits_used', 0)}")
            return {
                "status": "success",
                "data": result,
                "message": "Plagiarism detection completed successfully"
            }
        
    except HTTPException as http_err:
        # Log HTTPExceptions for debugging
        logger.error(f"❌ HTTP Exception in plagiarism detection: {http_err.status_code} - {http_err.detail}")
        logger.error(f"❌ Full HTTP exception: {http_err}")
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    
    except Exception as e:
        logger.error(f"❌ Unexpected error in plagiarism detection: {str(e)}", exc_info=True)
        logger.error(f"❌ Exception type: {type(e)}")
        logger.error(f"❌ Exception args: {e.args}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error in plagiarism detection: {str(e)}"
        )
    finally:
        logger.info("Executed the plagiarism detection endpoint")