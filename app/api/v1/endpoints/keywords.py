from typing import Any, Dict, List, Optional, Type
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.db.session import get_db_session
from app.models.project import Project
from app.core.config import settings
from app.core.logging_config import logger
from app.middleware.auth_middleware import verify_token, verify_request_origin_sync
from app.services.balance_validator import BalanceValidator
from app.schemas.keyword import (
    KeywordBulkCreate,
    KeywordBulkDelete,
    KeywordResponse,
    KeywordSearchResponse,
    KeywordSearchRequest,
    LatestKeywordResponse,
    KeywordMetrics
)
from app.models.keywords import Keywords
from uuid import UUID, uuid4
from sqlalchemy import text
from app.services.normal_keyword_suggestions_sync import KeywordSuggestionServiceSync
from app.tasks.keyword_suggestions import fetch_semrush_data
from datetime import datetime, timezone
from app.prompts.blogGenerator.keyword_intent_prompt import gpt_keyword_intent_prompt
import json
import pytz
from bson import ObjectId
from app.services.mongodb_service import MongoDBService
from app.utils.api_utils import APIUtils

router = APIRouter()
from openai import OpenAI
openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)


def get_keyword_intent(keywordlist, service_name: str = "primary_keywords", user_id: str = None, project_id: str = None, db_session=None, usage_tracker: Optional[Dict] = None):
    """Get keyword intent with optional usage tracking or combined tracking"""
    intent_list_prompt = gpt_keyword_intent_prompt(keywordlist)
    

    openai_response = openai_client.responses.create(
        model=settings.OPENAI_MODEL,
         input=[
            {"role": "system", "content": intent_list_prompt['system']},
            {"role": "user", "content": intent_list_prompt['user']},
        ],
        max_output_tokens=settings.OPENAI_MAX_TOKENS,
        temperature=1
    )
    
    # 🔥 COMBINED/INDIVIDUAL USAGE TRACKING: Record token usage and billing
    if usage_tracker is not None:
        # Combined tracking mode - accumulate tokens
        usage_tracker["total_input_tokens"] += openai_response.usage.input_tokens
        usage_tracker["total_output_tokens"] += openai_response.usage.output_tokens
        usage_tracker["total_calls"] += 1
        usage_tracker["individual_calls"].append({
            "call_number": usage_tracker["total_calls"],
            "call_type": "intent_analysis",
            "keywords_count": len(keywordlist),
            "keywords_analyzed": keywordlist[:10],  # Store first 10 keywords for tracking
            "prompt_type": "intent_detection",
            "input_tokens": openai_response.usage.input_tokens,
            "output_tokens": openai_response.usage.output_tokens,
            "model_name": openai_response.model
        })
        
    
    elif user_id and db_session:
        # Individual tracking mode - record immediately
        try:
            from app.services.enhanced_llm_usage_service import EnhancedLLMUsageService
            
            llm_usage_service = EnhancedLLMUsageService(db_session)
            
            intent_metadata = {
                "keyword_intent_analysis": {
                    "keywords_count": len(keywordlist),
                    "keywords_analyzed": keywordlist[:10],  # Store first 10 keywords for tracking
                    "service_type": service_name,
                    "prompt_type": "intent_detection"
                }
            }
            
            billing_result = llm_usage_service.record_llm_usage(
                user_id=user_id,
                service_name=service_name,  # "primary_keywords" or "primary_related_keywords"
                model_name=openai_response.model,
                input_tokens=openai_response.usage.input_tokens,
                output_tokens=openai_response.usage.output_tokens,
                service_description=f"Keyword intent analysis - {len(keywordlist)} keywords",
                project_id=project_id,
                additional_metadata=intent_metadata
            )
            
            
        except Exception as e:
            logger.error(f"❌ Failed to record keyword intent usage: {e}")
    
    intent_list_from_gpt = openai_response.output_text.strip()
    
    
    # intent_list_from_gpt = list(json.loads(intent_list_from_gpt))
    intent_list_from_gpt = [intent.strip() for intent in intent_list_from_gpt.split(',')]
    
    

    return intent_list_from_gpt



@router.post("/search", response_model=KeywordSearchResponse)
def search_keywords(
    request: Request,
    *,
    search_request: KeywordSearchRequest,
    current_user = Depends(verify_request_origin_sync)
):
    """
    Search for keyword metrics using SEMrush API.
    Requires authentication and project access.
    """
    try:
        # Extract values from request body
        keyword = search_request.keyword
        country = search_request.country
        blog_id = search_request.blog_id
        
        # Get project_id from path parameters
        project_id = request.path_params.get("project_id")
        request_type = "phrase_this"  # Default value
        
        
        # Validate UUID format
        APIUtils.validate_uuid(project_id)
        
        # Get user ID
        current_user_id = current_user.user.id
        
        # Verify project exists and access
        with get_db_session() as db:
            # 🚀 FAST BALANCE VALIDATION - Check balance BEFORE processing
            balance_validator = BalanceValidator(db)
            balance_check = balance_validator.validate_service_balance(
                user_id=current_user_id,
                service_key="primary_keywords"
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
            
            
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            APIUtils.verify_project_access(project_id, current_user_id, db)
        
        # Fetch metrics from SEMrush
        try:
            metrics = fetch_semrush_data(keyword, country, request_type)
            # if not metrics:
            #     return KeywordSearchResponse(
            #         data=None,
            #         related=[],
            #         status="error",
            #         type=request_type,
            #         database=country,
            #         error="No data found for the given keyword"
            #     )
                
            # Format response
            current_timestamp = int(datetime.now().timestamp())
            
            
            if metrics:
                metric = metrics[0]
                
                intent_list = []
                if metric.get("intent").lower()=="unknown" or metric.get("intent")=="-":
                    intent_list = get_keyword_intent(
                        keywordlist=[metric.get("keyword")],
                        service_name="primary_keywords",
                        user_id=current_user_id,
                        project_id=project_id,
                        db_session=db
                    )
                
                final_intent = intent_list[0].capitalize() if intent_list else metric.get("intent").lower()
                
                # ✅ SAVE TO MONGODB
                mongodb_service = MongoDBService()
                mongodb_service.init_sync_db()
                
                # ✅ SIMPLE LOGIC: blog_id in URL = UPDATE, no blog_id = CREATE
                existing_blog = None
                if blog_id:
                    existing_blog = APIUtils.get_mongodb_blog_document(
                        mongodb_service, blog_id, project_id, current_user_id
                    )
                else:
                    pass
                
                current_time = datetime.now(timezone.utc)
                
                # Determine tag based on whether blog_id exists
                tag = "updated" if blog_id else "generated"
                
                keyword_data = {
                    "keyword": metric["keyword"],
                    "search_volume": metric.get("search_volume", 0),
                    "difficulty": metric.get("difficulty", 0),
                    "intent": final_intent,
                    "country": country,
                    "tag": tag,
                    "generated_at": current_time
                }
                
                # Prepare step tracking data for primary keyword generation
                step_tracking_status = "updated" if blog_id else "generated"
                
                step_tracking_data = {
                    "step": "primary_keyword",
                    "status": step_tracking_status,
                    "completed_at": current_time
                }
                
                if existing_blog:
                    # Update existing document - PUSH to array
                    blog_id = str(existing_blog["_id"])
                    
                    # Initialize step_tracking if missing
                    existing_step_tracking = existing_blog.get("step_tracking")
                    if not existing_step_tracking:
                        step_tracking_structure = {
                            "current_step": "primary_keyword",
                            "primary_keyword": [],
                            "secondary_keywords": [],
                            "category": [],
                            "title": [],
                            "outline": [],
                            "sources": []
                        }
                        mongodb_service.get_sync_db()['blogs'].update_one(
                            {"_id": ObjectId(blog_id)},
                            {"$set": {"step_tracking": step_tracking_structure}}
                        )
                    
                    # Simple push operation
                    update_result = mongodb_service.get_sync_db()['blogs'].update_one(
                        {"_id": ObjectId(blog_id)},
                        {
                            "$push": {
                                "primary_keyword": keyword_data,
                                "step_tracking.primary_keyword": step_tracking_data
                            },
                            "$set": {
                                "step_tracking.current_step": "primary_keyword",
                                "country": country,
                                "intent": final_intent,
                                "updated_at": datetime.now(timezone.utc)
                            }
                        }
                    )
                        
                    
                else:
                    # Create new document with array
                    
                    blog_doc = {
                        "project_id": project_id,
                        "user_id": current_user_id,
                        "status": "incomplete",
                        "title": "Untitled Blog",
                        "country": country,
                        "intent": final_intent,
                        "primary_keyword": [keyword_data],
                        "step_tracking": {
                            "current_step": "primary_keyword",
                            "primary_keyword": [step_tracking_data],
                            "secondary_keywords": [],
                            "category": [],
                            "title": [],
                            "outline": [],
                            "sources": []
                        },
                        "source": "rayo",
                        "is_active": False,
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    }
                    
                    
                    result = mongodb_service.get_sync_db()['blogs'].insert_one(blog_doc)
                    blog_id = str(result.inserted_id)
                    
                
                data = KeywordMetrics(
                    keyword=metric["keyword"],
                    search_volume=metric.get("search_volume", 0),
                    keyword_difficulty=float(metric.get("difficulty", 0)),
                    intent=final_intent
                )
            else:
                
                intent_list = get_keyword_intent(
                    keywordlist=[keyword],
                    service_name="primary_keywords",
                    user_id=current_user_id,
                    project_id=project_id,
                    db_session=db
                )
                
                final_intent = intent_list[0].capitalize() if intent_list else "-"
                
                # Save to MongoDB (even without metrics)
                mongodb_service = MongoDBService()
                mongodb_service.init_sync_db()
                
                # ✅ SIMPLE LOGIC: blog_id in URL = UPDATE, no blog_id = CREATE
                existing_blog = None
                if blog_id:
                    existing_blog = APIUtils.get_mongodb_blog_document(
                        mongodb_service, blog_id, project_id, current_user_id
                    )
                else:
                    pass
                
                current_time = datetime.now(timezone.utc)
                
                # Determine tag based on whether blog_id exists  
                tag = "updated" if blog_id else "generated"
                
                keyword_data = {
                    "keyword": keyword,
                    "search_volume": 0,
                    "difficulty": 0,
                    "intent": final_intent,
                    "country": country,
                    "tag": tag,
                    "generated_at": current_time
                }
                
                # Prepare step tracking data for primary keyword generation (no metrics case)
                step_tracking_status = "updated" if blog_id else "generated"
                
                step_tracking_data = {
                    "step": "primary_keyword",
                    "status": step_tracking_status,
                    "completed_at": current_time
                }
                
                if existing_blog:
                    blog_id = str(existing_blog["_id"])
                    
                    # Initialize step_tracking if missing
                    existing_step_tracking = existing_blog.get("step_tracking")
                    if not existing_step_tracking:
                        step_tracking_structure = {
                            "current_step": "primary_keyword",
                            "primary_keyword": [],
                            "secondary_keywords": [],
                            "category": [],
                            "title": [],
                            "outline": [],
                            "sources": []
                        }
                        mongodb_service.get_sync_db()['blogs'].update_one(
                            {"_id": ObjectId(blog_id)},
                            {"$set": {"step_tracking": step_tracking_structure}}
                        )
                    
                    # Simple push operation
                    update_result = mongodb_service.get_sync_db()['blogs'].update_one(
                        {"_id": ObjectId(blog_id)},
                        {
                            "$push": {
                                "primary_keyword": keyword_data,
                                "step_tracking.primary_keyword": step_tracking_data
                            },
                            "$set": {
                                "step_tracking.current_step": "primary_keyword",
                                "country": country,
                                "intent": final_intent,
                                "updated_at": datetime.now(timezone.utc)
                            }
                        }
                    )
                        
                    
                else:
                    
                    blog_doc = {
                        "project_id": project_id,
                        "user_id": current_user_id,
                        "status": "incomplete",
                        "title": "Untitled Blog",
                        "country": country,
                        "intent": final_intent,
                        "primary_keyword": [keyword_data],
                        "step_tracking": {
                            "current_step": "primary_keyword",
                            "primary_keyword": [step_tracking_data],
                            "secondary_keywords": [],
                            "category": [],
                            "title": [],
                            "outline": [],
                            "sources": []
                        },
                        "source": "rayo",
                        "is_active": False,
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    }
                    
                    
                    result = mongodb_service.get_sync_db()['blogs'].insert_one(blog_doc)
                    blog_id = str(result.inserted_id)
                    

                data = KeywordMetrics(
                    keyword=keyword,
                    search_volume=0,
                    keyword_difficulty=0.0,
                    intent=final_intent
                )
                
            # Include blog_id in response
            response = KeywordSearchResponse(
                primary_keyword=data,
                status="success",
                country=country,
                error=None,
                blog_id=blog_id
            )
            
            
            return response
            
        except Exception as e:
            logger.error(f"Error fetching SEMrush data: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching keyword metrics: {str(e)}"
            )
            
    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    except Exception as e:
        logger.error(f"Error searching keywords: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.get("/search/{blog_id}", response_model=LatestKeywordResponse)
def get_latest_keyword_data(
    request: Request,
    *,
    blog_id: str,
    current_user = Depends(verify_request_origin_sync)
):
    """
    Get the latest primary keyword data from a blog.
    
    Args:
        blog_id: MongoDB blog document ID
        
    Returns:
        Latest keyword data with blog information
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
            
            APIUtils.verify_project_access(project_id, current_user_id, db)
        
        # Get blog data from MongoDB
        mongodb_service = MongoDBService()
        mongodb_service.init_sync_db()
        
        # Find the blog document with projection for performance
        projection = {
            "primary_keyword": 1,
            "country": 1,
            "_id": 1
        }
        blog_doc = APIUtils.get_mongodb_blog_document(
            mongodb_service, blog_id, project_id, current_user_id, projection
        )
        
        
        # Get primary keyword data
        primary_keywords = blog_doc.get("primary_keyword", [])
        country = blog_doc.get("country", "us")
        
        # Get the latest keyword (last item in array, tag doesn't matter)
        primary_keyword_data = None
        if primary_keywords:
            latest_keyword_raw = primary_keywords[-1]  # Last item = latest
            
            primary_keyword_data = KeywordMetrics(
                keyword=latest_keyword_raw.get("keyword", ""),
                search_volume=latest_keyword_raw.get("search_volume", 0),
                keyword_difficulty=float(latest_keyword_raw.get("difficulty", 0.0)),
                intent=latest_keyword_raw.get("intent", "Unknown")
            )
        
        response = LatestKeywordResponse(
            primary_keyword=primary_keyword_data,
            status="success" if primary_keyword_data else "no_data",
            country=country,
            error=None,
            blog_id=blog_id
        )
        
        return response
        
    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    except Exception as e:
        logger.error(f"Error fetching latest keyword data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.post("/add", response_model=List[KeywordResponse])
def create_bulk_keywords(
    request: Request,
    *,
    keywords: KeywordBulkCreate,
    current_user = Depends(verify_request_origin_sync)
):
    """
    Create multiple keywords for a project.
    
    Args:
        request: FastAPI request object
        keywords: List of keywords to create
        
    Returns:
        List of created keywords
    """
    try:
        # Get project_id from path parameters
        project_id = request.path_params.get("project_id")
        
        # Get user ID
        current_user_id = current_user.user.id
        
        # Verify project exists and access
        with get_db_session() as db:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            APIUtils.verify_project_access(project_id, current_user_id, db)
            
            # Create keywords
            created_keywords = []
            for keyword_data in keywords.keywords:
                keyword = Keywords(
                    id=uuid4(),
                    name=keyword_data.name,
                    search_volume=keyword_data.search_volume,
                    difficulty=keyword_data.difficulty,
                    intent=keyword_data.intent,
                    cpc=keyword_data.cpc,
                    competition=keyword_data.competition,
                    country=keyword_data.country,
                    project_id=project_id,
                    active=True
                )
                db.add(keyword)
                created_keywords.append(keyword)
            
            db.commit()
            
            # Convert to response models
            response_keywords = [KeywordResponse.from_orm(kw) for kw in created_keywords]
            return response_keywords
            
    except Exception as e:
        logger.error(f"Error creating keywords: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.delete("/delete", response_model=dict)
def delete_bulk_keywords(
    request: Request,
    *,
    keywords: KeywordBulkDelete,
    current_user = Depends(verify_request_origin_sync)
):
    """
    Delete multiple keywords by their IDs for a project.
    
    Args:
        request: FastAPI request object
        keywords: List of keyword IDs to delete
        
    Returns:
        Dictionary with deletion results
    """
    try:
        # Get project_id from path parameters
        project_id = request.path_params.get("project_id")
        
        # Get user ID
        current_user_id = current_user.user.id
        
        # Verify project exists and access
        with get_db_session() as db:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            APIUtils.verify_project_access(project_id, current_user_id, db)
            
            # Find keywords that belong to this project and user
            keywords_to_delete = db.query(Keywords).filter(
                Keywords.id.in_([str(kid) for kid in keywords.keyword_ids]),
                Keywords.project_id == project_id,
                Keywords.active == True
            ).all()
            
            # Check if all requested keywords were found
            found_ids = {kw.id for kw in keywords_to_delete}
            requested_ids = {str(kid) for kid in keywords.keyword_ids}
            not_found_ids = requested_ids - found_ids
            
            # Soft delete (set active=False) instead of hard delete
            deleted_count = 0
            deleted_keywords = []
            
            for keyword in keywords_to_delete:
                keyword.active = False
                deleted_keywords.append({
                    "id": keyword.id,
                    "name": keyword.name
                })
                deleted_count += 1
            
            db.commit()
            
            
            return APIUtils.create_minimal_response(
                status="success",
                data={
                    "deleted_count": deleted_count,
                    "deleted_keywords": deleted_keywords
                },
                not_found_ids=list(not_found_ids) if not_found_ids else None,
                message=f"Successfully deleted {deleted_count} keywords"
            )
            
    except Exception as e:
        logger.error(f"Error deleting keywords: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.get("/list", response_model=List[KeywordResponse])
def list_project_keywords(
    request: Request,
    *,
    current_user = Depends(verify_request_origin_sync)
):
    """
    List all keywords for a project.
    
    Args:
        request: FastAPI request object
        
    Returns:
        List of keywords
    """
    try:
        # Get project_id from path parameters
        project_id = request.path_params.get("project_id")
        
        # Get user ID
        current_user_id = current_user.user.id
        
        # Verify project exists and access
        with get_db_session() as db:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            APIUtils.verify_project_access(project_id, current_user_id, db)
            
            # Get all keywords for the project
            keywords = db.query(Keywords).filter(
                Keywords.project_id == project_id,
                Keywords.active == True
            ).all()
            
            # Convert to response models
            response_keywords = [KeywordResponse.from_orm(kw) for kw in keywords]
            return response_keywords
            
    except Exception as e:
        logger.error(f"Error listing keywords: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.get("/related")
def get_related_keywords(
    request: Request,
    *,
    keyword: str,
    country: str = "us",
    project_id: UUID = None,
    current_user = Depends(verify_request_origin_sync)
):
    """
    Get related keywords for a given keyword using SEMrush API.
    
    Args:
        keyword: The keyword to get related keywords for
        country: Country code for SEMrush database (default: us)
        
    Returns:
        List of related keywords with their metrics
    """
    try:
        # Get project_id from path parameters
        project_id = request.path_params.get("project_id")
        
        # Verify project exists
        project = None
        with get_db_session() as db:
            # 🚀 FAST BALANCE VALIDATION - Check balance BEFORE processing
            balance_validator = BalanceValidator(db)
            balance_check = balance_validator.validate_service_balance(
                user_id=current_user.user.id,
                service_key="primary_related_keywords"
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
            
            
            project = APIUtils.verify_project_access(project_id, current_user.user.id, db)
        
        # 🔥 COMBINED USAGE TRACKING: Initialize tracker for all LLM calls
        import uuid
        usage_tracker = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_calls": 0,
            "service_name": "primary_related_keywords",
            "request_id": str(uuid.uuid4())[:8],
            "individual_calls": []  # Track each individual call details
        }
        
        # Initialize KeywordSuggestionService and get related keywords with usage tracking
        keyword_service = KeywordSuggestionServiceSync()
        related_keywords = keyword_service.get_related_keywords(
            keyword=keyword,
            country=country,
            project=project,
            usage_tracker=usage_tracker  # Pass usage tracker
        )
        keywords_list_semrush = [kw["keyword"] for kw in related_keywords]
        
        # Fetch metrics for all keywords in one go
        try:
            metrics_results = fetch_semrush_data(keywords_list_semrush, country)
            
            # Modified get_keyword_intent to NOT record individual billing (part of combined tracking)
            intent_list_from_gpt = get_keyword_intent(
                keywordlist=keywords_list_semrush,
                service_name="primary_related_keywords",
                user_id=current_user.user.id,
                project_id=project_id,
                db_session=None,  # Don't record individual billing
                usage_tracker=usage_tracker  # Pass usage tracker for accumulation
            )
            # Create a metrics dictionary for faster lookup
            metrics_dict = {metric['keyword']: metric for metric in metrics_results} if metrics_results else {}
            
            # Process metrics for each keyword
            keywords_with_metrics = []
            for index, kw in enumerate(related_keywords):
                keyword = kw["keyword"]
                metric = metrics_dict.get(keyword, {})
                keywords_with_metrics.append({
                    "name": keyword,
                    "search_volume": metric.get("search_volume", 0),
                    "keyword_difficulty": float(metric.get("difficulty", 0.0)),
                    "difficulty": float(metric.get("difficulty", 0.0)),  # Same as keyword_difficulty
                    "cpc": metric.get("cpc", 0.0),
                    "competition": metric.get("competition", 0.0),
                    # "intent": metric.get("intent", intent_list_from_gpt[index].capitalize()),
                    "intent": intent_list_from_gpt[index].capitalize(),
                    "country": country,
                    "index": index
                })
        
        except Exception as e:
            logger.error(f"Error fetching metrics for keywords: {str(e)}")
            keywords_with_metrics = []

        # 🔥 COMBINED BILLING: Record single usage entry for all LLM calls
        if usage_tracker["total_calls"] > 0:
            try:
                from app.services.enhanced_llm_usage_service import EnhancedLLMUsageService
                
                llm_usage_service = EnhancedLLMUsageService(db)
                
                related_keywords_metadata = {
                    "related_keywords_stats": {
                        "total_llm_calls": usage_tracker["total_calls"],
                        "primary_keyword": keyword,
                        "related_keywords_found": len(related_keywords),
                        "keywords_with_metrics": len(keywords_with_metrics),
                        "request_id": usage_tracker["request_id"],
                        "country": country,
                        "project_id": project_id
                    },
                    "individual_llm_calls": usage_tracker["individual_calls"]  # ALL individual call details
                }
                
                # Record combined usage with related keywords service multiplier (8.0x)
                billing_result = llm_usage_service.record_llm_usage(
                    user_id=current_user.user.id,
                    service_name=usage_tracker["service_name"],  # "primary_related_keywords"
                    model_name=settings.OPENAI_MODEL,  # Use model name from settings
                    input_tokens=usage_tracker["total_input_tokens"],
                    output_tokens=usage_tracker["total_output_tokens"],
                    service_description=f"Related keywords research - {usage_tracker['total_calls']} LLM calls combined",
                    project_id=project_id,
                    additional_metadata=related_keywords_metadata
                )
                
                
            except Exception as e:
                logger.error(f"❌ Failed to record related keywords usage: {e}")
        
        return keywords_with_metrics

    except HTTPException:
        # Re-raise HTTPExceptions to preserve their original status and detail
        raise
    except Exception as e:
        logger.error(f"Error in get_related_keywords: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
