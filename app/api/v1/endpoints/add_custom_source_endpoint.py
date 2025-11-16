"""
🔗 Simple Custom Source Endpoint - URL Processing Only
Clean implementation: Validate → Scrape → OpenAI → Return Results
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from app.services.add_custom_source_service import AddCustomSourceService
from app.core.logging_config import logger
from app.db.session import get_db_session
from app.models.project import Project
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.services.balance_validator import BalanceValidator
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class CustomSourceRequest(BaseModel):
    url: str
    heading: Optional[str] = None
    subsection: Optional[str] = None

@router.post(
    "/add-custom-sources/{blog_id}",
    summary="🔗 Add Custom URL Source - Simple Implementation", 
    description="Validate balance → Project → Blog → Scrape URL → Process with OpenAI → Return information list"
)
async def add_custom_url_source(
    request: Request,
    blog_id: str,
    source_data: CustomSourceRequest,
    current_user: User = Depends(get_current_user)
):
    """Simple URL processing: Balance check → Scrape → OpenAI → Results"""
    
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
            
            # 🚀 STEP 4: URL Validation
            if not source_data.url or not source_data.url.strip():
                raise HTTPException(status_code=400, detail="URL is required")
            
            # Clean URL
            url = source_data.url.strip()
            if not url.startswith(('http://', 'https://')):
                url = f"https://{url}"
            
            logger.info(f"🔗 Processing URL: {url}")
            
            # 🚀 STEP 5: Initialize Service
            custom_source_service = AddCustomSourceService(
                db=db,
                user_id=str(current_user.id),
                project_id=project_id
            )
            
            # 🚀 STEP 6: Process URL (Scrape + OpenAI)
            result = await custom_source_service.process_url_source(
                url=url, 
                blog_id=blog_id,
                heading=source_data.heading,
                subsection=source_data.subsection
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
                
                # Other specific error handling
                if "403" in error_message or "Forbidden" in error_message:
                    raise HTTPException(
                        status_code=400,
                        detail="Website is blocking automated access. Try a different URL or add content as text instead."
                    )
                elif "404" in error_message or "Not Found" in error_message:
                    raise HTTPException(
                        status_code=400,
                        detail="URL not found. Please check the URL and try again."
                    )
                elif "timeout" in error_message.lower() or "connection" in error_message.lower():
                    raise HTTPException(
                        status_code=400,
                        detail="Unable to connect to the URL. Please check the URL and try again."
                    )
                else:
                    raise HTTPException(status_code=500, detail=f"Processing failed: {error_message}")
            
            # 🚀 STEP 8: Return Success Response
            return {
                "status": "success",
                "message": "URL scraped and processed successfully",
                "blog_id": blog_id,
                "url": url,
                "informations": result.get("parsed_response", {})
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing custom URL source: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")