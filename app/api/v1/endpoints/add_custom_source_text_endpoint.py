"""
📝 Simple Custom Source Text Endpoint - Direct Text Processing
Clean implementation: Validate → Process Text → OpenAI → Return Results
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from app.services.add_custom_source_text_service import AddCustomSourceTextService
from app.core.logging_config import logger
from app.db.session import get_db_session
from app.models.project import Project
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.services.balance_validator import BalanceValidator
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class CustomSourceTextRequest(BaseModel):
    text_content: str
    source_name: Optional[str] = None
    heading: Optional[str] = None
    subsection: Optional[str] = None

@router.post(
    "/add-custom-sources-text/{blog_id}",
    summary="📝 Add Custom Text Source - Simple Implementation", 
    description="Validate balance → Project → Blog → Process Text → Process with OpenAI → Return information list"
)
async def add_custom_text_source(
    request: Request,
    blog_id: str,
    source_data: CustomSourceTextRequest,
    current_user: User = Depends(get_current_user)
):
    """Simple text processing: Balance check → Process Text → OpenAI → Results"""
    
    try:
        project_id = request.path_params.get("project_id")
        
        with get_db_session() as db:
            # 🚀 PARALLEL VALIDATION: Run all validations concurrently
            async def validate_balance_async():
                """Async balance validation"""
                balance_validator = BalanceValidator(db)
                return balance_validator.validate_service_balance(
                    user_id=str(current_user.id),
                    service_key="add_custom_source"
                )
            
            async def validate_project_async():
                """Async project validation"""
                project = db.query(Project).filter(Project.id == project_id).first()
                if not project or str(project.user_id) != str(current_user.id):
                    return {"valid": False, "error": "Project access denied or not found"}
                return {"valid": True, "project": project}
            
            async def validate_blog_async():
                """Async blog validation"""
                try:
                    from app.services.mongodb_service import MongoDBService
                    from app.utils.api_utils import APIUtils
                    
                    mongodb_service = MongoDBService()
                    mongodb_service.init_sync_db()
                    
                    blog_doc = APIUtils.get_mongodb_blog_document(
                        mongodb_service, blog_id, project_id, str(current_user.id)
                    )
                    return {"valid": True, "blog_doc": blog_doc}
                except Exception as e:
                    return {"valid": False, "error": f"Blog not found: {str(e)}"}
            
            # 🚀 RUN ALL 3 VALIDATIONS IN PARALLEL
            import asyncio
            try:
                balance_result, project_result, blog_result = await asyncio.gather(
                    validate_balance_async(),
                    validate_project_async(), 
                    validate_blog_async()
                )
                
                # Check balance validation
                if not balance_result["valid"]:
                    if balance_result["error"] == "insufficient_balance":
                        raise HTTPException(
                            status_code=402,
                            detail={
                                "error": "insufficient_balance",
                                "message": balance_result["message"],
                                "required_balance": balance_result["required_balance"],
                                "current_balance": balance_result["current_balance"],
                                "shortfall": balance_result["shortfall"],
                                "next_refill_time": balance_result.get("next_refill_time").isoformat() if balance_result.get("next_refill_time") else None
                            }
                        )
                    else:
                        raise HTTPException(
                            status_code=400,
                            detail={
                                "error": balance_result["error"],
                                "message": balance_result["message"]
                            }
                        )
                
                # Check project validation
                if not project_result["valid"]:
                    raise HTTPException(status_code=403, detail=project_result["error"])
                
                # Check blog validation  
                if not blog_result["valid"]:
                    raise HTTPException(status_code=404, detail=blog_result["error"])
                
                logger.info(f"✅ All parallel validations passed for user {current_user.id}, blog {blog_id}")
                
            except HTTPException:
                raise
            except Exception as parallel_error:
                logger.error(f"Parallel validation failed: {parallel_error}")
                raise HTTPException(status_code=500, detail=f"Validation failed: {str(parallel_error)}")
            
            # 🚀 STEP 4: Text Content Validation
            if not source_data.text_content or not source_data.text_content.strip():
                raise HTTPException(status_code=400, detail="Text content is required")
            
            # Validate text content
            text_content = source_data.text_content.strip()
            content_length = len(text_content)
            
            if content_length < 50:
                raise HTTPException(status_code=400, detail="Text content too short. Please provide at least 50 characters.")
            
            if content_length > 500000:  # 500K character limit
                raise HTTPException(status_code=400, detail="Text content too long. Please limit to 500,000 characters.")
            
            source_name = source_data.source_name or "Custom Text Source"
            logger.info(f"📝 Processing text content: {content_length} characters, source: {source_name}")
            
            # 🚀 STEP 5: Initialize Text Service
            custom_source_text_service = AddCustomSourceTextService(
                db=db,
                user_id=str(current_user.id),
                project_id=project_id
            )
            
            # 🚀 STEP 6: Process Text Content (Direct + OpenAI)
            result = await custom_source_text_service.process_text_source(
                text_content=text_content, 
                blog_id=blog_id,
                heading=source_data.heading,
                subsection=source_data.subsection,
                source_name=source_name
            )
            
            # 🚀 STEP 7: Handle Results
            if not result["success"]:
                error_message = result.get("error", "Unknown error")
                
                # Check for "No information found" specifically
                if error_message == "No information found":
                    return {
                        "status": "error",
                        "message": "No information found"
                    }
                
                # Other specific error handling for text processing
                if "too short" in error_message.lower():
                    raise HTTPException(
                        status_code=400,
                        detail="Text content is too short. Please provide more meaningful content."
                    )
                elif "too long" in error_message.lower():
                    raise HTTPException(
                        status_code=400,
                        detail="Text content is too long. Please reduce the content size."
                    )
                elif "empty" in error_message.lower():
                    raise HTTPException(
                        status_code=400,
                        detail="Text content cannot be empty. Please provide valid text content."
                    )
                else:
                    raise HTTPException(status_code=500, detail=f"Processing failed: {error_message}")
            
            # 🚀 STEP 8: Return Success Response
            return {
                "status": "success",
                "message": "Text content processed successfully",
                "blog_id": blog_id,
                "source_name": source_name,
                "content_length": content_length,
                "informations": result.get("parsed_response", {})
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing custom text source: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")