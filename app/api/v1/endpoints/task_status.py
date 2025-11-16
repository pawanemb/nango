from fastapi import APIRouter, HTTPException, Depends
from celery.result import AsyncResult
from typing import Dict, Any, Optional, List
from app.celery_config import celery_app as celery
from app.services.mongodb_service import MongoDBService, MongoDBServiceError
from app.db.session import get_db
from sqlalchemy.orm import Session
from app.models.project import Project
import json
import re
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

def extract_json_from_markdown(text: str) -> Dict[str, Any]:
    """
    Extract and parse JSON content from markdown code blocks.
    """
    if not isinstance(text, str):
        return text  # If it's already a dict, return as is
        
    # Try to find JSON code block
    json_pattern = r"```(?:json)?\n([\s\S]*?)\n```"
    match = re.search(json_pattern, text)
    
    if match:
        json_str = match.group(1).strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {str(e)}")
            raise ValueError(f"Invalid JSON format: {str(e)}")
    else:
        # If no code block found, try parsing the text directly
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {str(e)}")
            raise ValueError(f"Invalid JSON format: {str(e)}")

class DemographicAnalysisResponse(BaseModel):
    status: str
    message: Optional[str] = None
    project_id: Optional[str] = None
    url: Optional[str] = None
    demographics: Optional[Dict[str, List[str]]] = None
    ai_meta: Dict[str, Any] = Field(default_factory=dict)

class ServiceAnalysisResponse(BaseModel):
    status: str
    message: Optional[str] = None
    project_id: Optional[str] = None
    url: Optional[str] = None
    services: Optional[str] = None
    business_category: Optional[str] = None
    ai_meta: Dict[str, Any] = Field(default_factory=dict)

@router.get("/{task_id}", response_model=Dict[str, Any])
async def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    Get the status of a task by its ID.
    Returns the current stage and results if available.
    """
    task = AsyncResult(task_id)
    
    if not task.ready():
        # Task is still running
        current_stage = task.info.get('current_stage', 'processing') if task.info else 'processing'
        return {
            "status": "in_progress",
            "current_stage": current_stage,
            "progress": task.info if task.info else None
        }
    
    if task.failed():
        return {
            "status": "error",
            "message": str(task.result),
            "current_stage": "failed"
        }
    
    result = task.get()
    
    return {
        "status": "completed",
        "current_stage": "completed",
        "result": result
    }

@router.get("/{task_id}/inspect", response_model=Dict[str, Any])
async def inspect_task(task_id: str) -> Dict[str, Any]:
    """
    Get detailed task status including state, runtime info, and any errors.
    """
    task = AsyncResult(task_id)
    
    # Get task info
    info = {
        "task_id": task_id,
        "status": task.status,
        "successful": task.successful(),
        "failed": task.failed(),
        "runtime": {
            "date_done": task.date_done.isoformat() if task.date_done else None
        }
    }
    
    # Get current state and progress
    if task.state == 'PENDING':
        info.update({
            "state": "PENDING",
            "info": "Task not yet started"
        })
    elif task.state == 'STARTED':
        info.update({
            "state": "STARTED",
            "info": "Task has been started"
        })
    elif task.state in ['SCRAPING', 'PROCESSING']:
        info.update({
            "state": task.state,
            "info": task.info
        })
    elif task.state == 'SUCCESS':
        result = task.get()
        info.update({
            "state": "SUCCESS",
            "result": result
        })
    elif task.state == 'FAILURE':
        info.update({
            "state": "FAILURE",
            "error": str(task.info.get('error')) if task.info else str(task.result),
            "stage": task.info.get('stage') if task.info else 'unknown',
            "traceback": task.traceback
        })
    elif task.state == 'RETRY':
        info.update({
            "state": "RETRY",
            "info": "Task is being retried",
            "retry_count": task.request.retries if task.request else 0
        })
    
    # Get worker info if available
    i = celery.control.inspect()
    active_tasks = i.active()
    reserved_tasks = i.reserved()
    
    if active_tasks:
        for worker, tasks in active_tasks.items():
            for t in tasks:
                if t['id'] == task_id:
                    info['worker'] = {
                        'name': worker,
                        'pid': t.get('pid'),
                        'time_start': t.get('time_start')
                    }
    
    if reserved_tasks:
        for worker, tasks in reserved_tasks.items():
            for t in tasks:
                if t['id'] == task_id:
                    info['queued_on'] = worker
    
    return info

@router.get("/{task_id}/demographics", response_model=DemographicAnalysisResponse)
async def get_demographic_analysis(
    task_id: str,
    db: Session = Depends(get_db)
) -> DemographicAnalysisResponse:
    """
    Get the demographic analysis results for a completed task.
    Returns the identified target demographics for the website.
    
    Args:
        task_id: The ID of the demographic analysis task
        
    Returns:
        DemographicAnalysisResponse containing:
        - status: success/error/in_progress
        - demographics: Dictionary with age, industry, gender, languages, and countries
        - ai_meta: Additional metadata about the analysis
    """
    task = AsyncResult(task_id)
    
    if not task.ready():
        return DemographicAnalysisResponse(
            status="in_progress",
            message="Demographic analysis is still running"
        )
    
    if task.failed():
        return DemographicAnalysisResponse(
            status="error",
            message=str(task.result)
        )
    
    try:
        result = task.get()
        
        # Get project_id and url from task result
        project_id = result.get("project_id")
        url = result.get("url")
        
        # Get the content from MongoDB to get the demographics
        content = MongoDBService.get_content_by_url(project_id=project_id, url=url)
        if not content:
            raise HTTPException(
                status_code=404,
                detail="Content not found in database"
            )
            
        # Extract demographics data
        demographics = content.demographics
        if isinstance(demographics, str):
            try:
                demographics = extract_json_from_markdown(demographics)
            except ValueError as e:
                return DemographicAnalysisResponse(
                    status="error",
                    message=f"Failed to parse demographics data: {str(e)}"
                )
            
        return DemographicAnalysisResponse(
            status="success",
            project_id=project_id,
            url=url,
            demographics=demographics,
            ai_meta=content.ai_analysis_meta.get("demographics_analysis", {}) if content.ai_analysis_meta else {},
            message="Demographic analysis completed successfully"
        )
        
    except Exception as e:
        return DemographicAnalysisResponse(
            status="error",
            message=f"Error retrieving demographic analysis: {str(e)}"
        )

@router.get("/{task_id}/services", response_model=ServiceAnalysisResponse)
async def get_service_analysis(
    task_id: str,
    db: Session = Depends(get_db)
) -> ServiceAnalysisResponse:
    """
    Get the service analysis results for a completed task.
    Returns the identified services and business category for the website.
    
    Args:
        task_id: The ID of the scraping and analysis task
        
    Returns:
        ServiceAnalysisResponse containing:
        - status: success/error/in_progress
        - services: Comma-separated list of identified services
        - business_category: E-Commerce/SaaS/Others
        - ai_meta: Additional metadata about the analysis
    """
    task = AsyncResult(task_id)
    
    if not task.ready():
        return ServiceAnalysisResponse(
            status="in_progress",
            message="Service analysis is still running"
        )
    
    if task.failed():
        return ServiceAnalysisResponse(
            status="error",
            message=str(task.result)
        )
    
    try:
        result = task.get()
        
        # Get project_id and url from task result
        project_id = result.get("project_id")
        url = result.get("url")
        
        # Get the content from MongoDB to get the services
        content = MongoDBService.get_content_by_url(project_id=project_id, url=url)
        if not content:
            raise HTTPException(
                status_code=404,
                detail="Content not found in database"
            )
            
        # Convert services list to comma-separated string
        services_str = ", ".join(content.services) if content.services else None
            
        return ServiceAnalysisResponse(
            status="success",
            project_id=project_id,
            url=url,
            services=services_str,
            business_category=content.business_category,
            ai_meta=content.ai_analysis_meta.get("service_analysis", {}) if content.ai_analysis_meta else {},
            message="Service analysis completed successfully"
        )
        
    except Exception as e:
        return ServiceAnalysisResponse(
            status="error",
            message=f"Error retrieving service analysis: {str(e)}"
        )
