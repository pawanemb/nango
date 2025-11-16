"""
🔗 Simple Custom Source Endpoint - URL Processing Only
Clean implementation: Validate → Scrape → OpenAI → Return Results
"""

from fastapi import APIRouter, Depends, HTTPException, Request, File, UploadFile, Form
from app.services.add_custom_source_pdf_service import AddCustomSourceService
from app.core.logging_config import logger
from app.db.session import get_db_session
from app.models.project import Project
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.services.balance_validator import BalanceValidator
from pydantic import BaseModel
from typing import Optional, Union

router = APIRouter()

class CustomSourceRequest(BaseModel):
    url: str
    heading: Optional[str] = None
    subsection: Optional[str] = None

@router.post(
    "/add-custom-sources-pdf/{blog_id}",
    summary="📄 Add Custom PDF File Source - Upload & Process", 
    description="Upload PDF file → Store in DigitalOcean Spaces → Generate CDN URL → Process with RayoScraper → OpenAI Analysis"
)
async def add_custom_pdf_source(
    request: Request,
    blog_id: str,
    current_user: User = Depends(get_current_user),
    pdf_file: UploadFile = File(..., description="PDF file to upload and process"),
    source_name: Optional[str] = Form(None, description="Optional custom source name (defaults to filename)"),
    heading: Optional[str] = Form(None, description="Optional heading for content context"),
    subsection: Optional[str] = Form(None, description="Optional subsection for content context")
):
    """PDF File Processing: Upload → Store → Generate CDN URL → RayoScraper → OpenAI → Results"""
    
    try:
        project_id = request.path_params.get("project_id")
        
        with get_db_session() as db:
            # 🚀 STEP 1: Validate File
            if not pdf_file:
                raise HTTPException(status_code=400, detail="PDF file is required")
            
            # Check file type - be more lenient with content type detection
            valid_pdf_types = ['application/pdf', 'application/x-pdf', 'application/vnd.pdf']
            if pdf_file.content_type and not any(pdf_file.content_type.startswith(pdf_type) for pdf_type in valid_pdf_types):
                # Also check file extension as fallback
                if not pdf_file.filename or not pdf_file.filename.lower().endswith('.pdf'):
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Invalid file type. Expected PDF file, got: {pdf_file.content_type}"
                    )
            
            # Check file size (50MB limit)
            if pdf_file.size and pdf_file.size > 50 * 1024 * 1024:
                raise HTTPException(
                    status_code=400,
                    detail="File size exceeds 50MB limit"
                )
            
            logger.info(f"📄 Processing PDF file: {pdf_file.filename} ({pdf_file.size} bytes)")
            
            # 🚀 STEP 2: Read file content
            try:
                pdf_content = await pdf_file.read()
                if len(pdf_content) == 0:
                    raise HTTPException(status_code=400, detail="PDF file is empty")
                
                # Validate PDF file header (PDF magic number)
                if not pdf_content.startswith(b'%PDF-'):
                    raise HTTPException(
                        status_code=400, 
                        detail="Invalid PDF file. File does not have a valid PDF header."
                    )
                
                logger.info(f"📄 PDF file validated: {len(pdf_content)} bytes, header: {pdf_content[:8]}")
                
            except HTTPException:
                raise
            except UnicodeDecodeError as e:
                # This shouldn't happen with raw bytes, but just in case
                logger.error(f"Unicode decode error reading PDF: {str(e)}")
                raise HTTPException(
                    status_code=400, 
                    detail="PDF file contains invalid characters. Please ensure it's a valid PDF file."
                )
            except Exception as e:
                logger.error(f"Error reading PDF file: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Failed to read PDF file: {str(e)}")
            
            # 🚀 STEP 3: Run parallel validations (same as URL endpoint)
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
                
                logger.info(f"✅ All parallel validations passed for PDF upload by user {current_user.id}, blog {blog_id}")
                
            except HTTPException:
                raise
            except Exception as parallel_error:
                logger.error(f"Parallel validation failed: {parallel_error}")
                raise HTTPException(status_code=500, detail=f"Validation failed: {str(parallel_error)}")
            
            # 🚀 STEP 4: Initialize Service and Process PDF
            custom_source_service = AddCustomSourceService(
                db=db,
                user_id=str(current_user.id),
                project_id=project_id
            )
            
            # 🚀 STEP 5: Process PDF File (Upload + Process)
            result = await custom_source_service.process_pdf_file(
                pdf_content=pdf_content,
                original_filename=pdf_file.filename,
                blog_id=blog_id,
                heading=heading,
                subsection=subsection,
                source_name=source_name
            )
            
            # 🚀 STEP 6: Handle Results
            if not result["success"]:
                error_message = result.get("error", "Unknown error")
                
                # Check for "No information found" specifically
                if error_message == "No information found":
                    return {
                        "status": "error",
                        "message": "No information found in the uploaded PDF"
                    }
                
                # Handle specific errors
                if "upload" in error_message.lower():
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to upload PDF to storage. Please try again."
                    )
                elif "timeout" in error_message.lower() or "connection" in error_message.lower():
                    raise HTTPException(
                        status_code=400,
                        detail="Unable to process the uploaded PDF. Please try again."
                    )
                else:
                    raise HTTPException(status_code=500, detail=f"Processing failed: {error_message}")
            
            # 🚀 STEP 7: Return Success Response
            return {
                "status": "success",
                "message": "PDF file uploaded and processed successfully",
                "blog_id": blog_id,
                "original_filename": pdf_file.filename,
                "pdf_url": result.get("pdf_upload_info", {}).get("pdf_url", ""),
                "informations": result.get("parsed_response", {})
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing custom PDF source: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")