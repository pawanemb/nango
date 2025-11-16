from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
from pymongo.database import Database
from app.services.mongodb_service import MongoDBService
from sqlalchemy import func, cast, Date
from app.db.session import get_db
from app.models.gsc import GSCAccount
from app.models.project import Project
from app.models.monitoring import MonitoringProjectStats
import logging
from sqlalchemy import delete, insert
import datetime
import psycopg2
import psycopg2.extras
from app.core.config import settings
from uuid import UUID
from app.services.gsc_service import GSCService
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger("fastapi_app")

router = APIRouter(tags=["monitoring"])  # Will be mounted with /api/v1 prefix

# Create a separate router for public cron endpoint (no auth required)
cron_router = APIRouter(tags=["monitoring-cron"])

def get_mongodb() -> Database:
    """Return a synchronous MongoDB Database handle."""
    mongodb_service = MongoDBService()
    return mongodb_service.get_sync_db()


def _build_pipeline(user_id: Optional[str] = None):
    """Return aggregation pipeline; if user_id supplied restrict to that user."""
    # SIMPLIFIED MATCH for debugging - just match on user_id 
    match_stage: dict = {}
    if user_id:
        match_stage["user_id"] = user_id

        pipeline = [
        {"$match": match_stage},
            {"$group": {
            "_id": {
                "user_id": "$user_id",
                "project_id": "$project_id"
            },
            # Check word count ranges instead of exact values
                "blog_1000": {"$sum": {"$cond": [
                    {"$and": [
                    {"$gte": [{"$toInt": {"$ifNull": ["$word_count", "0"]}}, 500]},
                    {"$lte": [{"$toInt": {"$ifNull": ["$word_count", "0"]}}, 1000]}
                    ]}, 1, 0
                ]}},
                "blog_1500": {"$sum": {"$cond": [
                    {"$and": [
                    {"$gte": [{"$toInt": {"$ifNull": ["$word_count", "0"]}}, 1001]},
                    {"$lte": [{"$toInt": {"$ifNull": ["$word_count", "0"]}}, 1500]}
                    ]}, 1, 0
                ]}},
                "blog_2500": {"$sum": {"$cond": [
                    {"$and": [
                    {"$gte": [{"$toInt": {"$ifNull": ["$word_count", "0"]}}, 1501]},
                    {"$lte": [{"$toInt": {"$ifNull": ["$word_count", "0"]}}, 2500]}
                    ]}, 1, 0
                ]}},
        }},
        {"$sort": {"_id.user_id": 1, "_id.project_id": 1}}
    ]
    return pipeline


@router.get("/blog-stats", summary="Global blog stats (all users & projects)")
def get_blog_stats(mongo_db: Database = Depends(get_mongodb), db=Depends(get_db)):
    """Return accurate stats table for all users and projects with direct counting."""
    try:
        # 1. Get all projects from database
        projects = db.query(Project.id, Project.user_id, Project.name, Project.url).all()
        
        # 2. Get all blogs from MongoDB
        all_blogs = list(mongo_db["blogs"].find({}, {"project_id": 1, "user_id": 1, "word_count": 1, "words_count": 1}))
        
        # 3. Organize blogs by project
        blogs_by_project = {}
        for blog in all_blogs:
            project_id = blog.get("project_id")
            if not project_id:
                continue
                
            if project_id not in blogs_by_project:
                blogs_by_project[project_id] = []
                
            blogs_by_project[project_id].append(blog)
        
        # 4. Count blogs for each project
        project_counts = {}
        for project_id, blogs in blogs_by_project.items():
            blog_1000 = 0
            blog_1500 = 0
            blog_2500 = 0
            
            for blog in blogs:
                # Check word_count field (string or number)
                try:
                    # Try to get word_count as int or convert from string
                    wc_value = blog.get("word_count")
                    if wc_value is None:
                        # Try words_count field as fallback
                        wc_value = blog.get("words_count")
                        
                    # Convert to int if it's a string
                    if isinstance(wc_value, str):
                        wc = int(wc_value)
                    else:
                        wc = wc_value
                        
                    # Count based on ranges
                    if wc is not None:
                        if 500 <= wc <= 1000:
                            blog_1000 += 1
                        elif 1001 <= wc <= 1500:
                            blog_1500 += 1
                        elif 1501 <= wc <= 2500:
                            blog_2500 += 1
                except (ValueError, TypeError):
                    # Skip blogs with invalid word counts
                    continue
            
            project_counts[project_id] = (blog_1000, blog_1500, blog_2500)
        
        # 5. Build response with all projects (even those with zero blogs)
        data = []
        for proj_id, user_id, name, url in projects:
            str_proj_id = str(proj_id)
            b1000, b1500, b2500 = project_counts.get(str_proj_id, (0, 0, 0))
            
            data.append({
                "user_id": str(user_id),
                "project_id": str_proj_id,
                "project_name": name,
                "project_url": url,
                "blog_1000": b1000,
                "blog_1500": b1500,
                "blog_2500": b2500,
            })
            
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error aggregating global blog stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute blog stats")


@router.get("/debug-word-count/{user_id}/{project_id}", summary="Debug word count")
def debug_word_count(user_id: str, project_id: str, mongo_db: Database = Depends(get_mongodb)):
    """Direct debug of word count for a specific user and project."""
    try:
        # Get all blogs for this user/project
        blogs = list(mongo_db["blogs"].find({"user_id": user_id, "project_id": project_id}))
        
        result = []
        for blog in blogs:
            result.append({
                "title": blog.get("title"),
                "word_count": blog.get("word_count"),
                "words_count": blog.get("words_count"),
                "id": str(blog.get("_id"))
            })
            
        # Count blogs with word_count="1500"
        count_1500 = mongo_db["blogs"].count_documents({
            "user_id": user_id,
            "project_id": project_id,
            "word_count": "1500"
        })
        
        return {
            "blogs": result,
            "count_1500": count_1500
        }
    except Exception as e:
        logger.error(f"Error in debug_word_count: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/{user_id}/blog-stats", summary="Blog stats for a single user")
def get_user_blog_stats(user_id: str, mongo_db: Database = Depends(get_mongodb), db=Depends(get_db)):
    """Return per-project blog stats for the given user."""
    try:
        # Get all user's blogs from MongoDB
        user_blogs = list(mongo_db["blogs"].find({"user_id": user_id}))
        
        # Organize blogs by project
        blogs_by_project = {}
        for blog in user_blogs:
            project_id = blog.get("project_id")
            if not project_id:
                continue
                
            if project_id not in blogs_by_project:
                blogs_by_project[project_id] = []
                
            blogs_by_project[project_id].append(blog)
        
        # Count blogs by range for each project
        project_counts = {}
        for project_id, blogs in blogs_by_project.items():
            blog_1000 = 0
            blog_1500 = 0
            blog_2500 = 0
            
            for blog in blogs:
                try:
                    # Try to get word_count as int or convert from string
                    wc_value = blog.get("word_count")
                    if wc_value is None:
                        # Try words_count field as fallback
                        wc_value = blog.get("words_count")
                        
                    # Convert to int if it's a string
                    if isinstance(wc_value, str):
                        wc = int(wc_value)
                    else:
                        wc = wc_value
                        
                    # Count based on ranges
                    if wc is not None:
                        if 500 <= wc <= 1000:
                            blog_1000 += 1
                        elif 1001 <= wc <= 1500:
                            blog_1500 += 1
                        elif 1501 <= wc <= 2500:
                            blog_2500 += 1
                except (ValueError, TypeError):
                    # Skip blogs with invalid word counts
                    continue
            
            project_counts[project_id] = (blog_1000, blog_1500, blog_2500)
        
        # fetch all projects for user
        projects = db.query(Project.id).filter(Project.user_id == user_id).all()
        
        data = []
        for (proj_id,) in projects:
            str_proj_id = str(proj_id)
            b1000, b1500, b2500 = project_counts.get(str_proj_id, (0, 0, 0))
            data.append({
                "project_id": str_proj_id,
                "blog_1000": b1000,
                "blog_1500": b1500,
                "blog_2500": b2500,
            })
        
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error aggregating blog stats for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute blog stats for user")


# ---------- Helper for PostgreSQL ----------
def _get_gsc_stats(db_session):
    """Return list of dicts with project_id, day, account_count."""
    rows = db_session.query(
        GSCAccount.project_id.label("project_id"),
        cast(GSCAccount.created_at, Date).label("day"),
        func.count(GSCAccount.id).label("accounts")
    ).group_by(GSCAccount.project_id, cast(GSCAccount.created_at, Date))\
     .order_by(cast(GSCAccount.created_at, Date).desc()).all()

    return [
        {"project_id": str(r.project_id), "day": r.day.isoformat(), "accounts": r.accounts}
        for r in rows
    ]


async def _get_gsc_performance_metrics(db: AsyncSession, project_id: str) -> Dict[str, int]:
    """Get GSC performance metrics for a project (last 30 days)"""
    try:
        from datetime import datetime, timedelta
        from app.services.gsc_service import GSCService
        from uuid import UUID
        
        # Calculate date range (last 30 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        # Get GSC account for this project
        result = await db.execute(
            text("SELECT site_url FROM public.gsc_accounts WHERE project_id = :project_id"),
            {"project_id": project_id}
        )
        gsc_account = result.fetchone()
        
        if not gsc_account:
            # No GSC account connected
            return {
                "clicks": 0,
                "impressions": 0,
                "ctr": 0.0,
                "position": 0.0
            }
        
        # Convert async session to sync for GSCService
        sync_db = db.sync_session if hasattr(db, 'sync_session') else db
        
        try:
            # Initialize GSC service
            gsc_service = GSCService(sync_db, UUID(project_id))
            
            # Get performance data for last 30 days
            analytics_data = await gsc_service.get_search_analytics_summary(
                site_url=gsc_account.site_url,
                start_date=start_date_str,
                end_date=end_date_str,
                compare=False  # Don't need comparison for monitoring stats
            )
            
            # Extract current period metrics
            current_data = analytics_data.get('current', {})
            
            return {
                "clicks": current_data.get('clicks', 0),
                "impressions": current_data.get('impressions', 0),
                "ctr": current_data.get('ctr', 0.0),  # Already as percentage
                "position": current_data.get('position', 0.0)
            }
            
        except Exception as gsc_error:
            logger.error(f"Error fetching GSC data for project {project_id}: {str(gsc_error)}")
            # Return zeros on GSC API error to avoid breaking the monitoring
            return {
                "clicks": 0,
                "impressions": 0,
                "ctr": 0.0,
                "position": 0.0
            }
            
    except Exception as e:
        logger.error(f"Error in _get_gsc_performance_metrics for project {project_id}: {str(e)}")
        return {
            "clicks": 0,
            "impressions": 0,
            "ctr": 0.0,
            "position": 0.0
        }


def _get_gsc_performance_metrics_sync(project_id: str, db_session) -> Dict[str, int]:
    """Get GSC performance metrics for a project (sync version for direct SQL operations)"""
    try:
        from datetime import datetime, timedelta
        from app.services.gsc_service import GSCService
        from app.models.gsc import GSCAccount
        from uuid import UUID
        
        # Calculate date range (last 30 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        # Get GSC account for this project
        gsc_account = db_session.query(GSCAccount).filter(
            GSCAccount.project_id == project_id
        ).first()
        
        if not gsc_account:
            # No GSC account connected
            return {
                "clicks": 0,
                "impressions": 0,
                "ctr": 0.0,
                "position": 0.0
            }
        
        try:
            # Use asyncio to run the async GSC service method in sync context
            import asyncio
            
            async def fetch_gsc_data():
                # Initialize GSC service
                gsc_service = GSCService(db_session, UUID(project_id))
                
                # Get performance data for last 30 days
                analytics_data = await gsc_service.get_search_analytics_summary(
                    site_url=gsc_account.site_url,
                    start_date=start_date_str,
                    end_date=end_date_str,
                    compare=False  # Don't need comparison for monitoring stats
                )
                
                # Extract current period metrics
                current_data = analytics_data.get('current', {})
                
                return {
                    "clicks": current_data.get('clicks', 0),
                    "impressions": current_data.get('impressions', 0),
                    "ctr": current_data.get('ctr', 0.0),  # Already as percentage
                    "position": current_data.get('position', 0.0)
                }
            
            # Run the async function in sync context
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            return loop.run_until_complete(fetch_gsc_data())
            
        except Exception as gsc_error:
            logger.error(f"Error fetching GSC data for project {project_id}: {str(gsc_error)}")
            # Return zeros on GSC API error to avoid breaking the monitoring
            return {
                "clicks": 0,
                "impressions": 0,
                "ctr": 0.0,
                "position": 0.0
            }
            
    except Exception as e:
        logger.error(f"Error in _get_gsc_performance_metrics_sync for project {project_id}: {str(e)}")
        return {
            "clicks": 0,
            "impressions": 0,
            "ctr": 0.0,
            "position": 0.0
        }


# -----------------------------------------------------------------------------
# GSC accounts stats (PostgreSQL)
# -----------------------------------------------------------------------------


@router.get("/gsc-account-stats", summary="Count of connected GSC accounts per project per day")
def gsc_account_stats(db = Depends(get_db)):
    """Return number of GSC account rows grouped by project and creation day."""
    try:
        data = _get_gsc_stats(db)
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error aggregating GSC account stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute GSC account stats")


# -----------------------------------------------------------------------------
# All projects (practice) list
# -----------------------------------------------------------------------------


@router.get("/monitoring/projects", summary="List all projects with id, name, url")
def list_all_projects(db=Depends(get_db)):
    """Return every project regardless of ownership (monitoring use)."""
    try:
        rows = db.query(Project.id, Project.name, Project.url).all()
        data = [
            {"practice_id": str(r.id), "name": r.name, "url": r.url}
            for r in rows
        ]
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error fetching all projects: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch projects list")


@router.get("/projects/{project_id}/blog-stats", summary="Blog stats for a single project")
def get_project_blog_stats(project_id: str, mongo_db: Database = Depends(get_mongodb)):
    """Return word count stats for a specific project regardless of user."""
    try:
        # Simple direct query approach
        project_blogs = list(mongo_db["blogs"].find({"project_id": project_id}))
        
        # Count blogs in each word count bucket
        blog_1000 = 0
        blog_1500 = 0
        blog_2500 = 0
        
        # Check each blog's word count (both as string and number)
        for blog in project_blogs:
            try:
                # Try to get word_count as int or convert from string
                wc_value = blog.get("word_count")
                if wc_value is None:
                    # Try words_count field as fallback
                    wc_value = blog.get("words_count")
                    
                # Convert to int if it's a string
                if isinstance(wc_value, str):
                    wc = int(wc_value)
                else:
                    wc = wc_value
                    
                # Count based on ranges
                if wc is not None:
                    if 500 <= wc <= 1000:
                        blog_1000 += 1
                    elif 1001 <= wc <= 1500:
                        blog_1500 += 1
                    elif 1501 <= wc <= 2500:
                        blog_2500 += 1
            except (ValueError, TypeError):
                # Skip blogs with invalid word counts
                continue
        
        # Return simple stats
        return {
            "status": "success", 
            "data": {
                "project_id": project_id,
                "blog_1000": blog_1000,
                "blog_1500": blog_1500,
                "blog_2500": blog_2500,
                "total_blogs": len(project_blogs)
            }
        }
    except Exception as e:
        logger.error(f"Error in get_project_blog_stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/debug-blog-counts", summary="Debug blog word counts in MongoDB")
def debug_blog_counts(mongo_db: Database = Depends(get_mongodb)):
    """Examine blog documents directly to debug word count issues."""
    try:
        # Get sample of blogs
        sample_blogs = list(mongo_db["blogs"].find(
            {"$and": [
                {"$or": [
                    {"is_active": True},
                    {"is_active": {"$exists": False}}
                ]},
                {"user_id": {"$exists": True}},
                {"project_id": {"$exists": True}}
            ]}
        ).limit(50))
        
        # Extract word count info
        blog_info = []
        word_count_types = {}
        range_counts = {"500-1000": 0, "1001-1500": 0, "1501-2500": 0, "other": 0, "invalid": 0}
        
        for blog in sample_blogs:
            # Get word count values
            wc = blog.get("word_count")
            wcs = blog.get("words_count")
            
            # Record the data types
            wc_type = type(wc).__name__ if wc is not None else "None"
            wcs_type = type(wcs).__name__ if wcs is not None else "None"
            
            word_count_types[wc_type] = word_count_types.get(wc_type, 0) + 1
            word_count_types[f"words_count_{wcs_type}"] = word_count_types.get(f"words_count_{wcs_type}", 0) + 1
            
            # Try to convert to integer
            try:
                numeric_wc = None
                if isinstance(wc, (int, float)):
                    numeric_wc = int(wc)
                elif isinstance(wc, str) and wc.isdigit():
                    numeric_wc = int(wc)
                elif wcs is not None:
                    if isinstance(wcs, (int, float)):
                        numeric_wc = int(wcs)
                    elif isinstance(wcs, str) and wcs.isdigit():
                        numeric_wc = int(wcs)
                
                # Categorize by range
                if numeric_wc is not None:
                    if 500 <= numeric_wc <= 1000:
                        range_counts["500-1000"] += 1
                    elif 1001 <= numeric_wc <= 1500:
                        range_counts["1001-1500"] += 1
                    elif 1501 <= numeric_wc <= 2500:
                        range_counts["1501-2500"] += 1
                    else:
                        range_counts["other"] += 1
                else:
                    range_counts["invalid"] += 1
            except (ValueError, TypeError):
                range_counts["invalid"] += 1
            
            # Add to blog info
            blog_info.append({
                "blog_id": str(blog.get("_id")),
                "project_id": blog.get("project_id"),
                "user_id": blog.get("user_id"),
                "word_count": wc,
                "word_count_type": wc_type,
                "words_count": wcs,
                "words_count_type": wcs_type
            })
        
        return {
            "status": "success",
            "total_blogs": len(sample_blogs),
            "word_count_types": word_count_types,
            "range_counts": range_counts,
            "blog_sample": blog_info[:10]  # First 10 blogs
        }
    except Exception as e:
        logger.error(f"Error in debug_blog_counts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/celery-status", summary="Check Celery worker status")
def check_celery_status():
    """Check if Celery workers are running and test connection to Redis."""
    from app.celery_config import celery_app
    try:
        # Check if Celery workers are available
        i = celery_app.control.inspect()
        availability = i.ping() or {}
        
        # Check registered tasks
        registered_tasks = i.registered() or {}
        
        # Check active tasks
        active_tasks = i.active() or {}
        
        # Check Redis connection
        redis_ok = False
        try:
            redis_info = celery_app.backend.client.info()
            redis_ok = True
        except Exception as e:
            redis_info = str(e)
        
        return {
            "status": "success",
            "workers_available": bool(availability),
            "workers": list(availability.keys()) if availability else [],
            "registered_tasks": {k: len(v) for k, v in registered_tasks.items()} if registered_tasks else {},
            "active_tasks": {k: len(v) for k, v in active_tasks.items()} if active_tasks else {},
            "redis_connected": redis_ok,
            "redis_info": redis_info if redis_ok else None
        }
    except Exception as e:
        logger.error(f"Error checking Celery status: {e}")
        return {
            "status": "error",
            "message": str(e),
            "celery_running": False
        }


@router.post("/test-monitoring-update/{project_id}", summary="Test monitoring table update for a specific project")
def test_monitoring_update(project_id: str, mongo_db: Database = Depends(get_mongodb), db=Depends(get_db)):
    """
    Test updating the monitoring_project_stats table for a specific project.
    This bypasses Celery and directly updates the database.
    """
    try:
        # 1. Get the project from PostgreSQL
        from app.models.project import Project
        from app.models.monitoring import MonitoringProjectStats
        from sqlalchemy import delete, insert
        
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # 2. Count blogs for this project
        project_blogs = list(mongo_db["blogs"].find({"project_id": project_id}))
        
        # Log what we found for debugging
        logger.info(f"Found {len(project_blogs)} blogs for project {project_id}")
        
        # 3. Get word counts directly
        blog_1000 = 0
        blog_1500 = 0
        blog_2500 = 0
        
        # Sample a few blogs to examine
        sample_blogs = []
        
        for blog in project_blogs:
            try:
                # Add to sample for debugging
                if len(sample_blogs) < 5:
                    sample_blogs.append({
                        "id": str(blog.get("_id")),
                        "word_count": blog.get("word_count"),
                        "words_count": blog.get("words_count")
                    })
                
                # First try words_count
                wc_value = blog.get("words_count")
                
                # If words_count is None, try word_count
                if wc_value is None:
                    wc_value = blog.get("word_count")
                
                # Convert to int if needed
                if isinstance(wc_value, (int, float)):
                    numeric_wc = int(wc_value)
                elif isinstance(wc_value, str) and wc_value.isdigit():
                    numeric_wc = int(wc_value)
                # Handle case where word_count is exactly "1500" 
                elif wc_value == "1500":
                    numeric_wc = 1500
                elif wc_value == "1000":
                    numeric_wc = 1000
                elif wc_value == "2500":
                    numeric_wc = 2500
                else:
                    numeric_wc = None
                
                # Count based on ranges
                if numeric_wc is not None:
                    if 500 <= numeric_wc <= 1000:
                        blog_1000 += 1
                    elif 1001 <= numeric_wc <= 1500:
                        blog_1500 += 1
                    elif 1501 <= numeric_wc <= 2500:
                        blog_2500 += 1
            except (ValueError, TypeError):
                continue
        
        # 4. Update the monitoring table directly
        # First delete any existing entry
        db.execute(delete(MonitoringProjectStats).where(MonitoringProjectStats.project_id == project_id))
        
        # Insert new row
        row = {
            "project_id": project.id,
            "user_id": project.user_id,
            "blog_1000": blog_1000,
            "blog_1500": blog_1500,
            "blog_2500": blog_2500,
            "gsc_connected": db.query(GSCAccount).filter(GSCAccount.project_id == project_id).count(),
            "project_name": project.name,
            "project_url": project.url,
        }
        
        db.execute(insert(MonitoringProjectStats).values([row]))
        db.commit()
        
        # 5. Return success with details
        return {
            "status": "success",
            "message": f"Monitoring stats updated for project {project_id}",
            "counts": {
                "blog_1000": blog_1000,
                "blog_1500": blog_1500,
                "blog_2500": blog_2500
            },
            "sample_blogs": sample_blogs,
            "row_inserted": row
        }
    except Exception as e:
        logger.error(f"Error updating monitoring stats for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start-celery", summary="Start the Celery worker")
def start_celery():
    """
    Start the Celery worker process. This is primarily for development use.
    In production, Celery should be managed by the deployment system.
    """
    import subprocess
    import os
    import sys
    
    try:
        # Get the current directory
        current_dir = os.getcwd()
        
        # Start Redis if it's not running (for development)
        try:
            redis_status = subprocess.run(
                ["redis-cli", "ping"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            redis_running = redis_status.returncode == 0 and "PONG" in redis_status.stdout
        except:
            redis_running = False
            
        if not redis_running:
            # Try to start Redis in background
            try:
                subprocess.Popen(
                    ["redis-server"], 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL
                )
                redis_started = True
            except:
                redis_started = False
        else:
            redis_started = False  # Already running
            
        # Start Celery worker
        celery_cmd = [
            sys.executable, "-m", "celery",
            "-A", "app.celery_config", 
            "worker", 
            "--loglevel=info",
            "--concurrency=1"
        ]
        
        celery_process = subprocess.Popen(
            celery_cmd,
            cwd=current_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        return {
            "status": "success",
            "message": "Celery worker started",
            "redis_status": "Started" if redis_started else "Already running" if redis_running else "Failed to start",
            "celery_pid": celery_process.pid
        }
    except Exception as e:
        logger.error(f"Error starting Celery worker: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/force-update-monitoring/{project_id}", summary="Force update monitoring table for a specific project")
def force_update_monitoring(project_id: str, mongo_db: Database = Depends(get_mongodb)):
    """
    Force update the monitoring_project_stats table for a specific project.
    This uses a direct database connection to ensure updates reach the database.
    """
    try:
        import psycopg2
        import psycopg2.extras
        from app.core.config import settings
        import uuid
        
        # Get connection string from settings
        db_url = settings.get_database_url
        
        # Create direct engine connection
        engine = create_engine(db_url)
        
        # 1. Get project blogs from MongoDB
        project_blogs = list(mongo_db["blogs"].find({"project_id": project_id}))
        
        # Log what we found
        logger.info(f"Found {len(project_blogs)} blogs for project {project_id}")
        
        # 2. Count blogs in each category
        blog_1000 = 0
        blog_1500 = 0
        blog_2500 = 0
        
        # Sample blogs for debugging
        sample_blogs = []
        
        for blog in project_blogs:
            # Add to sample for debugging
            if len(sample_blogs) < 5:
                sample_blogs.append({
                    "id": str(blog.get("_id")),
                    "word_count": blog.get("word_count"),
                    "words_count": blog.get("words_count")
                })
            
            # Count blogs
            try:
                # First try words_count
                wc_value = blog.get("words_count")
                
                # If words_count is None, try word_count
                if wc_value is None:
                    wc_value = blog.get("word_count")
                
                # Handle string literals directly
                if wc_value == "1500":
                    blog_1500 += 1
                    continue
                elif wc_value == "1000":
                    blog_1000 += 1
                    continue
                elif wc_value == "2500":
                    blog_2500 += 1
                    continue
                
                # Convert to int if needed
                numeric_wc = None
                if isinstance(wc_value, (int, float)):
                    numeric_wc = int(wc_value)
                elif isinstance(wc_value, str) and wc_value.isdigit():
                    numeric_wc = int(wc_value)
                
                # Count based on ranges
                if numeric_wc is not None:
                    if 500 <= numeric_wc <= 1000:
                        blog_1000 += 1
                    elif 1001 <= numeric_wc <= 1500:
                        blog_1500 += 1
                    elif 1501 <= numeric_wc <= 2500:
                        blog_2500 += 1
            except (ValueError, TypeError) as e:
                logger.error(f"Error processing blog {blog.get('_id')}: {e}")
                continue
        
        # 3. Get project metadata
        with engine.connect() as conn:
            # Get project details
            result = conn.execute(
                text("SELECT id, user_id, name, url FROM public.projects WHERE id = :project_id"),
                {"project_id": project_id}
            )
            project = result.fetchone()
            
            if not project:
                return {"status": "error", "message": "Project not found"}
                
            # Count GSC accounts
            result = conn.execute(
                text("SELECT COUNT(*) FROM public.gsc_accounts WHERE project_id = :project_id"),
                {"project_id": project_id}
            )
            gsc_count = result.scalar()
            
            # 4. Update monitoring_project_stats
            # First delete existing record
            conn.execute(
                text("DELETE FROM public.monitoring_project_stats WHERE project_id = :project_id"),
                {"project_id": project_id}
            )
            
            # Then insert new record
            conn.execute(
                text("""
                INSERT INTO public.monitoring_project_stats 
                (project_id, user_id, blog_1000, blog_1500, blog_2500, gsc_connected, gsc_clicks, gsc_impressions, gsc_ctr, gsc_position, project_name, project_url)
                VALUES (:project_id, :user_id, :blog_1000, :blog_1500, :blog_2500, :gsc_connected, :gsc_clicks, :gsc_impressions, :gsc_ctr, :gsc_position, :project_name, :project_url)
                """),
                {
                    "project_id": project_id,
                    "user_id": str(project.user_id),
                    "blog_1000": blog_1000,
                    "blog_1500": blog_1500,
                    "blog_2500": blog_2500,
                    "gsc_connected": gsc_count or 0,
                    "gsc_clicks": 0,  # Placeholder for force update
                    "gsc_impressions": 0,  # Placeholder for force update
                    "gsc_ctr": 0.0,  # Placeholder for force update
                    "gsc_position": 0.0,  # Placeholder for force update
                    "project_name": project.name,
                    "project_url": project.url
                }
            )
            
            # Commit the transaction
            conn.commit()
        
        return {
            "status": "success",
            "message": f"Monitoring stats forcefully updated for project {project_id}",
            "counts": {
                "blog_1000": blog_1000,
                "blog_1500": blog_1500,
                "blog_2500": blog_2500
            },
            "sample_blogs": sample_blogs
        }
    except Exception as e:
        logger.error(f"Error force updating monitoring stats for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.post("/direct-sql-update", summary="Update monitoring stats using direct SQL")
def direct_sql_update():
    """
    Update the monitoring_project_stats table using direct SQL with psycopg2.
    This is a completely independent implementation that bypasses SQLAlchemy entirely.
    """
    try:
        import psycopg2
        import psycopg2.extras
        from app.core.config import settings
        
        # 1. Connect to the MongoDB database
        from app.services.mongodb_service import MongoDBService
        mongo_db = MongoDBService().get_sync_db()
        logger.info("Connected to MongoDB")
        
        # 2. Get all blogs with project_id, user_id and word counts
        all_blogs = list(mongo_db["blogs"].find(
            {"$and": [
                {"$or": [
                    {"is_active": True},
                    {"is_active": {"$exists": False}}
                ]},
                {"user_id": {"$exists": True}},
                {"project_id": {"$exists": True}}
            ]}
        ))
        logger.info(f"Found {len(all_blogs)} total blogs in MongoDB")
        
        # 3. Categorize blogs by project and count word counts
        project_counts = {}
        for blog in all_blogs:
            project_id = blog.get("project_id")
            user_id = blog.get("user_id")
            
            if not project_id or not user_id:
                continue
            
            # Get word count
            wc_value = blog.get("word_count")
            if wc_value is None:
                wc_value = blog.get("words_count")
            
            # Initialize project counters if needed
            if (project_id, user_id) not in project_counts:
                project_counts[(project_id, user_id)] = {
                    "blog_1000": 0,
                    "blog_1500": 0,
                    "blog_2500": 0,
                    "total": 0
                }
            
            # Count total blogs per project
            project_counts[(project_id, user_id)]["total"] += 1
            
            # Handle string literals directly
            if wc_value == "1500":
                project_counts[(project_id, user_id)]["blog_1500"] += 1
                continue
            elif wc_value == "1000":
                project_counts[(project_id, user_id)]["blog_1000"] += 1
                continue
            elif wc_value == "2500":
                project_counts[(project_id, user_id)]["blog_2500"] += 1
                continue
            
            # Convert to numeric and count by range
            try:
                numeric_wc = None
                if isinstance(wc_value, (int, float)):
                    numeric_wc = int(wc_value)
                elif isinstance(wc_value, str) and wc_value.isdigit():
                    numeric_wc = int(wc_value)
                
                if numeric_wc is not None:
                    if 500 <= numeric_wc <= 1000:
                        project_counts[(project_id, user_id)]["blog_1000"] += 1
                    elif 1001 <= numeric_wc <= 1500:
                        project_counts[(project_id, user_id)]["blog_1500"] += 1
                    elif 1501 <= numeric_wc <= 2500:
                        project_counts[(project_id, user_id)]["blog_2500"] += 1
            except (ValueError, TypeError):
                continue
        
        logger.info(f"Processed word counts for {len(project_counts)} project-user pairs")
        
        # 4. Connect to PostgreSQL directly with psycopg2
        # Use psycopg2.connect for a completely fresh connection
        conn = psycopg2.connect(
            host=settings.POSTGRES_HOST,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            port=settings.POSTGRES_PORT
        )
        
        # Set autocommit mode to ensure changes are visible immediately
        conn.autocommit = True
        logger.info("Connected to PostgreSQL with psycopg2")
        
        # Create a cursor for executing SQL
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # 5. Get all projects for metadata
        cur.execute("SELECT id, user_id, name, url FROM public.projects")
        projects = cur.fetchall()
        logger.info(f"Found {len(projects)} projects in PostgreSQL")
        
        # Create a map of project IDs to metadata
        project_meta = {}
        for p in projects:
            project_meta[str(p["id"])] = {
                "user_id": str(p["user_id"]),
                "name": p["name"],
                "url": p["url"]
            }
        
        # 6. Get GSC account counts
        cur.execute("""
            SELECT project_id, COUNT(*) as count 
            FROM public.gsc_accounts 
            GROUP BY project_id
        """)
        gsc_counts = {str(row["project_id"]): row["count"] for row in cur.fetchall()}
        logger.info(f"Found GSC accounts for {len(gsc_counts)} projects")
        
        # 7. Get existing entries in monitoring table
        cur.execute("SELECT project_id, user_id, project_name, project_url, gsc_connected FROM public.monitoring_project_stats")
        existing_entries = {str(row["project_id"]): {
            "user_id": str(row["user_id"]),
            "name": row["project_name"],
            "url": row["project_url"],
            "gsc_connected": row["gsc_connected"]
        } for row in cur.fetchall()}
        logger.info(f"Found {len(existing_entries)} existing entries in monitoring table")
        
        # 8. Prepare values for bulk insert
        insert_values = []
        updated_projects = set()
        
        for (project_id, user_id), counts in project_counts.items():
            # Get project metadata
            meta = project_meta.get(project_id)
            if not meta:
                logger.warning(f"Missing metadata for project {project_id}, skipping")
                continue
                
            # Mark this project as updated
            updated_projects.add(project_id)
            
            # Add to insert values
            insert_values.append((
                project_id,
                user_id,
                counts["blog_1000"],
                counts["blog_1500"],
                counts["blog_2500"],
                gsc_counts.get(project_id, 0),
                0,  # gsc_clicks (placeholder for direct SQL)
                0,  # gsc_impressions (placeholder for direct SQL)
                0.0,  # gsc_ctr (placeholder for direct SQL)
                0.0,  # gsc_position (placeholder for direct SQL)
                meta["name"],
                meta["url"]
            ))
            
        # Add projects with no blogs but exist in the database
        for project_id, metadata in project_meta.items():
            if project_id not in updated_projects:
                # Get existing entry or default to zeros
                existing = existing_entries.get(project_id, {"user_id": metadata["user_id"], "gsc_connected": 0})
                
                insert_values.append((
                    project_id,
                    metadata["user_id"],
                    0,  # blog_1000
                    0,  # blog_1500
                    0,  # blog_2500
                    gsc_counts.get(project_id, 0),
                    0,  # gsc_clicks (placeholder for direct SQL)
                    0,  # gsc_impressions (placeholder for direct SQL)
                    0.0,  # gsc_ctr (placeholder for direct SQL)
                    0.0,  # gsc_position (placeholder for direct SQL)
                    metadata["name"],
                    metadata["url"]
                ))
                logger.info(f"Preserving project {project_id} with no blogs")
        
        # Now delete and insert in a transaction
        cur.execute("BEGIN")
        cur.execute("DELETE FROM public.monitoring_project_stats")
        logger.info("Cleared existing monitoring_project_stats table")
        
        # 9. Insert new values (bulk insert for efficiency)
        if insert_values:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO public.monitoring_project_stats
                (project_id, user_id, blog_1000, blog_1500, blog_2500, gsc_connected, gsc_clicks, gsc_impressions, gsc_ctr, gsc_position, project_name, project_url)
                VALUES %s
                """,
                insert_values
            )
            logger.info(f"Inserted {len(insert_values)} rows into monitoring_project_stats")
        
        # Commit the transaction
        cur.execute("COMMIT")
        
        # 10. Verify updates were made
        cur.execute("SELECT COUNT(*) FROM public.monitoring_project_stats")
        count = cur.fetchone()[0]
        logger.info(f"Final monitoring_project_stats table contains {count} rows")
        
        # 11. Verify specific records
        if insert_values:
            # Check a few random projects
            sample_size = min(5, len(insert_values))
            sample_projects = [insert_values[i][0] for i in range(sample_size)]
            
            placeholders = ','.join(['%s'] * sample_size)
            cur.execute(
                f"SELECT project_id, blog_1000, blog_1500, blog_2500 FROM public.monitoring_project_stats WHERE project_id IN ({placeholders})",
                sample_projects
            )
            verification_rows = cur.fetchall()
            logger.info(f"Verification found {len(verification_rows)} of {sample_size} sample rows")
            
            # Check first row for details
            if verification_rows:
                sample = verification_rows[0]
                logger.info(f"Sample row: project_id={sample['project_id']}, "
                          f"blog_1000={sample['blog_1000']}, "
                          f"blog_1500={sample['blog_1500']}, "
                          f"blog_2500={sample['blog_2500']}")
        
        # Close cursor and connection
        cur.close()
        conn.close()
        
        return {
            "status": "success",
            "message": f"Monitoring stats updated using direct SQL with {len(insert_values)} rows",
            "total_blogs": len(all_blogs),
            "total_projects": len(project_counts),
            "rows_inserted": len(insert_values),
            "verification_count": count
        }
    except Exception as e:
        logger.error(f"Error in direct SQL update: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/debug-monitoring-table/{project_id}", summary="Debug what's in the monitoring table for a project")
def debug_monitoring_table(project_id: str):
    """
    Directly query the monitoring_project_stats table in Supabase to check what's there.
    This uses the raw psycopg2 connection to avoid any caching or ORM issues.
    """
    try:
        import psycopg2
        import psycopg2.extras
        from app.core.config import settings
        
        # Connect directly to PostgreSQL
        conn = psycopg2.connect(
            host=settings.POSTGRES_HOST,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            port=settings.POSTGRES_PORT
        )
        
        # Create a cursor with dictionary factory
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Query the monitoring table for this project
        cur.execute(
            "SELECT * FROM public.monitoring_project_stats WHERE project_id = %s",
            (project_id,)
        )
        
        # Fetch the result
        result = cur.fetchone()
        
        # Close connection
        cur.close()
        conn.close()
        
        if result:
            # Convert to dict for JSON serialization
            row_dict = dict(result)
            # Convert UUID objects to strings
            for key, value in row_dict.items():
                if hasattr(value, 'hex'):  # UUID objects have a hex attribute
                    row_dict[key] = str(value)
                elif isinstance(value, (datetime.datetime, datetime.date)):
                    row_dict[key] = value.isoformat()
            
            return {
                "status": "success",
                "project_found": True,
                "row_data": row_dict,
                "database_info": {
                    "host": settings.POSTGRES_HOST,
                    "database": settings.POSTGRES_DB,
                    "port": settings.POSTGRES_PORT
                }
            }
        else:
            # Check if the project exists at all
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM public.projects WHERE id = %s", (project_id,))
            project_exists = cur.fetchone()[0] > 0
            cur.close()
            
            return {
                "status": "warning",
                "project_found": False,
                "project_exists_in_projects_table": project_exists,
                "message": f"No entry found for project {project_id} in monitoring_project_stats table",
                "database_info": {
                    "host": settings.POSTGRES_HOST,
                    "database": settings.POSTGRES_DB,
                    "port": settings.POSTGRES_PORT
                }
            }
    except Exception as e:
        logger.error(f"Error debugging monitoring table: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/trigger-aggressive-update/{project_id}", summary="Trigger an extremely aggressive update of the specific project with maximum debug logging")
def trigger_aggressive_update(project_id: str, mongo_db: Database = Depends(get_mongodb)):
    """
    Trigger an extremely aggressive update of the specific project with maximum debug logging.
    This is a completely independent implementation that bypasses SQLAlchemy entirely.
    """
    try:
        import psycopg2
        import psycopg2.extras
        from app.core.config import settings
        
        # Step 1: Get project from PostgreSQL since projects are stored there
        logger.info(f"Aggressive update: Getting project {project_id} from PostgreSQL")
        conn_pg = psycopg2.connect(
            host=settings.POSTGRES_HOST,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            port=settings.POSTGRES_PORT
        )
        cur_pg = conn_pg.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur_pg.execute(
            "SELECT * FROM public.projects WHERE id = %s",
            (project_id,)
        )
        project = cur_pg.fetchone()
        cur_pg.close()
        
        if not project:
            if conn_pg:
                conn_pg.close()
            return {
                "status": "error",
                "message": f"Project {project_id} not found in PostgreSQL"
            }
        
        # Get key project details
        user_id = str(project['user_id']) if 'user_id' in project else None
        project_name = project['name'] if 'name' in project else ""
        project_url = project['url'] if 'url' in project else ""
        gsc_connected = 1 if project.get('gsc_connected', False) else 0
        
        # Step 2: Get blogs from MongoDB for this project
        logger.info(f"Aggressive update: Getting blogs for project {project_id}")
        blogs = list(mongo_db["blogs"].find({"project_id": project_id}))
        logger.info(f"Aggressive update: Found {len(blogs)} blogs for project {project_id}")
        
        # Step 3: Count blogs by word count range
        blog_1000_count = 0
        blog_1500_count = 0
        blog_2500_count = 0
        blog_details = []
        
        for blog in blogs:
            # Collect details for debugging
            blog_detail = {
                "id": str(blog.get("_id")),
                "word_count": blog.get("word_count", None),
                "words_count": blog.get("words_count", None)
            }
            blog_details.append(blog_detail)
            
            # Get word count (handle both word_count and words_count fields, and both string and numeric formats)
            word_count = None
            if "word_count" in blog and blog["word_count"] is not None:
                try:
                    if isinstance(blog["word_count"], str):
                        word_count = int(blog["word_count"])
                    else:
                        word_count = blog["word_count"]
                except (ValueError, TypeError):
                    word_count = None
            
            if word_count is None and "words_count" in blog and blog["words_count"] is not None:
                try:
                    if isinstance(blog["words_count"], str):
                        word_count = int(blog["words_count"])
                    else:
                        word_count = blog["words_count"]
                except (ValueError, TypeError):
                    word_count = None
            
            # Count based on word count ranges
            if word_count is not None:
                if 500 <= word_count <= 1000:
                    blog_1000_count += 1
                elif 1001 <= word_count <= 1500 or word_count == 1500:  # Explicit check for 1500
                    blog_1500_count += 1
                elif 1501 <= word_count <= 2500:
                    blog_2500_count += 1
        
        # Step 4: Connect directly to PostgreSQL and update with raw SQL
        logger.info(f"Aggressive update: Connecting to PostgreSQL to update monitoring stats")
        conn = psycopg2.connect(
            host=settings.POSTGRES_HOST,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            port=settings.POSTGRES_PORT
        )
        
        # Use a transaction for atomicity
        conn.autocommit = False
        
        try:
            cursor = conn.cursor()
            
            # First, check if the row exists
            cursor.execute(
                "SELECT COUNT(*) FROM public.monitoring_project_stats WHERE project_id = %s",
                (project_id,)
            )
            row_exists = cursor.fetchone()[0] > 0
            
            if row_exists:
                # Update existing row with VERY explicit SQL
                logger.info(f"Aggressive update: Row exists, updating monitoring stats with UPDATE statement")
                update_sql = """
                UPDATE public.monitoring_project_stats
                SET blog_1000 = %s,
                    blog_1500 = %s,
                    blog_2500 = %s,
                    gsc_connected = %s,
                    gsc_clicks = %s,
                    gsc_impressions = %s,
                    gsc_ctr = %s,
                    gsc_position = %s,
                    project_name = %s,
                    project_url = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE project_id = %s
                """
                cursor.execute(
                    update_sql,
                    (
                        blog_1000_count, 
                        blog_1500_count, 
                        blog_2500_count, 
                        gsc_connected,
                        0,  # gsc_clicks (placeholder for aggressive update)
                        0,  # gsc_impressions (placeholder for aggressive update)
                        0.0,  # gsc_ctr (placeholder for aggressive update)
                        0.0,  # gsc_position (placeholder for aggressive update)
                        project_name,
                        project_url,
                        project_id
                    )
                )
                # Check affected rows
                affected_rows = cursor.rowcount
                logger.info(f"Aggressive update: Update affected {affected_rows} rows")
            else:
                # Insert new row
                logger.info(f"Aggressive update: Row doesn't exist, inserting new monitoring stats with INSERT statement")
                insert_sql = """
                INSERT INTO public.monitoring_project_stats
                (user_id, project_id, blog_1000, blog_1500, blog_2500, gsc_connected, gsc_clicks, gsc_impressions, gsc_ctr, gsc_position, project_name, project_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(
                    insert_sql,
                    (
                        user_id,
                        project_id,
                        blog_1000_count,
                        blog_1500_count,
                        blog_2500_count,
                        gsc_connected,
                        0,  # gsc_clicks (placeholder for aggressive update)
                        0,  # gsc_impressions (placeholder for aggressive update)
                        0.0,  # gsc_ctr (placeholder for aggressive update)
                        0.0,  # gsc_position (placeholder for aggressive update)
                        project_name,
                        project_url
                    )
                )
                # Check affected rows
                affected_rows = cursor.rowcount
                logger.info(f"Aggressive update: Insert affected {affected_rows} rows")
            
            # Commit the transaction
            logger.info("Aggressive update: Committing transaction")
            conn.commit()
            
            # Verify the update worked
            cursor.execute(
                "SELECT * FROM public.monitoring_project_stats WHERE project_id = %s",
                (project_id,)
            )
            updated_row = cursor.fetchone()
            
            # Close cursor and connection
            cursor.close()
            conn.close()
            
            if updated_row:
                # Convert to dict for JSON serialization
                row_dict = dict(zip([desc[0] for desc in cursor.description], updated_row))
                # Convert UUID objects to strings
                for key, value in row_dict.items():
                    if hasattr(value, 'hex'):  # UUID objects have a hex attribute
                        row_dict[key] = str(value)
                    elif isinstance(value, (datetime.datetime, datetime.date)):
                        row_dict[key] = value.isoformat()
                
                return {
                    "status": "success",
                    "message": f"Monitoring stats aggressively updated for project {project_id}",
                    "counts": {
                        "blog_1000": blog_1000_count,
                        "blog_1500": blog_1500_count,
                        "blog_2500": blog_2500_count
                    },
                    "sample_blogs": blog_details[:5],  # Show first 5 blogs for debugging
                    "affected_rows": affected_rows,
                    "verified_db_row": row_dict
                }
            else:
                return {
                    "status": "warning",
                    "message": f"Update operation succeeded but verification failed for project {project_id}",
                    "counts": {
                        "blog_1000": blog_1000_count,
                        "blog_1500": blog_1500_count,
                        "blog_2500": blog_2500_count
                    },
                    "sample_blogs": blog_details[:5]  # Show first 5 blogs for debugging
                }
                
        except Exception as e:
            # Rollback in case of error
            conn.rollback()
            logger.error(f"Aggressive update: Error in PostgreSQL operation: {e}")
            raise
        finally:
            # Make sure to close the connection
            if conn and not conn.closed:
                conn.close()
                
    except Exception as e:
        logger.error(f"Aggressive update: Error updating monitoring stats: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/admin-refresh-all-monitoring", summary="Admin-only endpoint to force refresh all monitoring stats in the database")
def admin_refresh_all_monitoring():
    """
    Admin-only endpoint to force refresh all monitoring stats in the database.
    This is a completely independent implementation that bypasses SQLAlchemy entirely.
    """
    try:
        import psycopg2
        import psycopg2.extras
        from app.core.config import settings
        
        # Connect directly to PostgreSQL
        conn = psycopg2.connect(
            host=settings.POSTGRES_HOST,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            port=settings.POSTGRES_PORT
        )
        
        # Create a cursor with dictionary factory
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Query the monitoring table for all projects
        cur.execute("SELECT project_id FROM public.monitoring_project_stats")
        project_ids = [str(row["project_id"]) for row in cur.fetchall()]
        
        # Get all blogs from MongoDB
        from app.services.mongodb_service import MongoDBService
        mongo_db = MongoDBService().get_sync_db()
        all_blogs = list(mongo_db["blogs"].find(
            {"$and": [
                {"$or": [
                    {"is_active": True},
                    {"is_active": {"$exists": False}}
                ]},
                {"user_id": {"$exists": True}},
                {"project_id": {"$exists": True}}
            ]}
        ))
        
        # Count blogs by word count range
        project_counts = {}
        for blog in all_blogs:
            project_id = blog.get("project_id")
            user_id = blog.get("user_id")
            
            if not project_id or not user_id:
                continue
            
            # Get word count
            wc_value = blog.get("word_count")
            if wc_value is None:
                wc_value = blog.get("words_count")
            
            # Initialize project counters if needed
            if (project_id, user_id) not in project_counts:
                project_counts[(project_id, user_id)] = {
                    "blog_1000": 0,
                    "blog_1500": 0,
                    "blog_2500": 0,
                    "total": 0
                }
            
            # Count total blogs per project
            project_counts[(project_id, user_id)]["total"] += 1
            
            # Handle string literals directly
            if wc_value == "1500":
                project_counts[(project_id, user_id)]["blog_1500"] += 1
                continue
            elif wc_value == "1000":
                project_counts[(project_id, user_id)]["blog_1000"] += 1
                continue
            elif wc_value == "2500":
                project_counts[(project_id, user_id)]["blog_2500"] += 1
                continue
            
            # Convert to numeric and count by range
            try:
                numeric_wc = None
                if isinstance(wc_value, (int, float)):
                    numeric_wc = int(wc_value)
                elif isinstance(wc_value, str) and wc_value.isdigit():
                    numeric_wc = int(wc_value)
                
                if numeric_wc is not None:
                    if 500 <= numeric_wc <= 1000:
                        project_counts[(project_id, user_id)]["blog_1000"] += 1
                    elif 1001 <= numeric_wc <= 1500:
                        project_counts[(project_id, user_id)]["blog_1500"] += 1
                    elif 1501 <= numeric_wc <= 2500:
                        project_counts[(project_id, user_id)]["blog_2500"] += 1
            except (ValueError, TypeError):
                continue
        
        logger.info(f"Processed word counts for {len(project_counts)} project-user pairs")
        
        # Get GSC account counts
        cur.execute("""
            SELECT project_id, COUNT(*) as count 
            FROM public.gsc_accounts 
            GROUP BY project_id
        """)
        gsc_counts = {str(row["project_id"]): row["count"] for row in cur.fetchall()}
        logger.info(f"Found GSC accounts for {len(gsc_counts)} projects")
        
        # Get existing entries in monitoring table
        cur.execute("SELECT project_id, user_id, project_name, project_url, gsc_connected FROM public.monitoring_project_stats")
        existing_entries = {str(row["project_id"]): {
            "user_id": str(row["user_id"]),
            "name": row["project_name"],
            "url": row["project_url"],
            "gsc_connected": row["gsc_connected"]
        } for row in cur.fetchall()}
        logger.info(f"Found {len(existing_entries)} existing entries in monitoring table")
        
        # Prepare values for bulk insert
        insert_values = []
        updated_projects = set()
        
        for (project_id, user_id), counts in project_counts.items():
            # Get project metadata
            meta = existing_entries.get(project_id)
            if not meta:
                logger.warning(f"Missing metadata for project {project_id}, skipping")
                continue
                
            # Mark this project as updated
            updated_projects.add(project_id)
            
            # Add to insert values
            insert_values.append((
                project_id,
                user_id,
                counts["blog_1000"],
                counts["blog_1500"],
                counts["blog_2500"],
                gsc_counts.get(project_id, 0),
                meta["name"],
                meta["url"]
            ))
        
        # Add projects with no blogs but exist in the database
        for project_id, meta in project_counts.items():
            if project_id not in updated_projects:
                # Get existing entry or default to zeros
                existing = existing_entries.get(project_id, {"user_id": meta["user_id"], "gsc_connected": 0})
                
                insert_values.append((
                    project_id,
                    meta["user_id"],
                    0,  # blog_1000
                    0,  # blog_1500
                    0,  # blog_2500
                    gsc_counts.get(project_id, 0),
                    0,  # gsc_clicks (placeholder for direct SQL)
                    0,  # gsc_impressions (placeholder for direct SQL)
                    0.0,  # gsc_ctr (placeholder for direct SQL)
                    0.0,  # gsc_position (placeholder for direct SQL)
                    meta["name"],
                    meta["url"]
                ))
                logger.info(f"Preserving project {project_id} with no blogs")
        
        # Now delete and insert in a transaction
        cur.execute("BEGIN")
        cur.execute("DELETE FROM public.monitoring_project_stats")
        logger.info("Cleared existing monitoring_project_stats table")
        
        # Insert new values (bulk insert for efficiency)
        if insert_values:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO public.monitoring_project_stats
                (project_id, user_id, blog_1000, blog_1500, blog_2500, gsc_connected, gsc_clicks, gsc_impressions, gsc_ctr, gsc_position, project_name, project_url)
                VALUES %s
                """,
                insert_values
            )
            logger.info(f"Inserted {len(insert_values)} rows into monitoring_project_stats")
        
        # Commit the transaction
        cur.execute("COMMIT")
        
        # Verify updates were made
        cur.execute("SELECT COUNT(*) FROM public.monitoring_project_stats")
        count = cur.fetchone()[0]
        logger.info(f"Final monitoring_project_stats table contains {count} rows")
        
        # Verify specific records
        if insert_values:
            # Check a few random projects
            sample_size = min(5, len(insert_values))
            sample_projects = [insert_values[i][0] for i in range(sample_size)]
            
            placeholders = ','.join(['%s'] * sample_size)
            cur.execute(
                f"SELECT project_id, blog_1000, blog_1500, blog_2500 FROM public.monitoring_project_stats WHERE project_id IN ({placeholders})",
                sample_projects
            )
            verification_rows = cur.fetchall()
            logger.info(f"Verification found {len(verification_rows)} of {sample_size} sample rows")
            
            # Check first row for details
            if verification_rows:
                sample = verification_rows[0]
                logger.info(f"Sample row: project_id={sample['project_id']}, "
                          f"blog_1000={sample['blog_1000']}, "
                          f"blog_1500={sample['blog_1500']}, "
                          f"blog_2500={sample['blog_2500']}")
        
        # Close cursor and connection
        cur.close()
        conn.close()
        
        return {
            "status": "success",
            "message": f"Monitoring stats updated using direct SQL with {len(insert_values)} rows",
            "total_blogs": len(all_blogs),
            "total_projects": len(project_counts),
            "rows_inserted": len(insert_values),
            "verification_count": count
        }
    except Exception as e:
        logger.error(f"Error in admin_refresh_all_monitoring: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@cron_router.post("/cron-refresh-monitoring", summary="Endpoint for external cron service to refresh monitoring stats")
def cron_refresh_monitoring(api_key: str = Header(None)):
    """
    Endpoint for external cron service (like EasyCron or GitHub Actions) to refresh monitoring stats.
    This bypasses the need for Celery/Redis by using direct SQL operations.
    
    The endpoint requires an API key in the header for security.
    Example cron command: curl -X POST "https://your-api.com/api/v1/cron-refresh-monitoring" -H "api-key: YOUR_SECRET_KEY"
    """
    # Check API key for security
    from app.core.config import settings
    
    valid_api_key = settings.CRON_API_KEY
    if not api_key or api_key != valid_api_key:
        logger.warning(f"Invalid API key used in cron refresh attempt")
        return {"status": "error", "message": "Invalid API key"}
    
    # Get start time for performance tracking
    import time
    start_time = time.time()
    
    try:
        import psycopg2
        import psycopg2.extras
        
        # Connect directly to PostgreSQL
        conn = psycopg2.connect(
            host=settings.POSTGRES_HOST,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            port=settings.POSTGRES_PORT
        )
        conn.autocommit = False  # Use explicit transaction control
        
        # Create a cursor with dictionary factory
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get all projects from PostgreSQL
        cur.execute("SELECT id, user_id, name, url FROM public.projects")
        projects = cur.fetchall()
        project_meta = {str(p["id"]): {
            "user_id": str(p["user_id"]),
            "name": p["name"],
            "url": p["url"]
        } for p in projects}
        
        # Get existing monitoring entries
        cur.execute("SELECT project_id, user_id, project_name, project_url, gsc_connected FROM public.monitoring_project_stats")
        existing_entries = {str(row["project_id"]): {
            "user_id": str(row["user_id"]),
            "name": row["project_name"],
            "url": row["project_url"],
            "gsc_connected": row["gsc_connected"]
        } for row in cur.fetchall()}
        
        # Get GSC account counts
        cur.execute("""
            SELECT project_id, COUNT(*) as count 
            FROM public.gsc_accounts 
            GROUP BY project_id
        """)
        gsc_counts = {str(row["project_id"]): row["count"] for row in cur.fetchall()}
        
        # Get all blogs from MongoDB
        from app.services.mongodb_service import MongoDBService
        mongo_db = MongoDBService().get_sync_db()
        all_blogs = list(mongo_db["blogs"].find(
            {"$and": [
                {"$or": [
                    {"is_active": True},
                    {"is_active": {"$exists": False}}
                ]},
                {"user_id": {"$exists": True}},
                {"project_id": {"$exists": True}}
            ]}
        ))
        
        # Process blogs by project
        project_counts = {}
        word_count_issues = 0
        
        for blog in all_blogs:
            project_id = blog.get("project_id")
            user_id = blog.get("user_id")
            
            if not project_id or not user_id:
                continue
            
            # Initialize project counters if needed
            if (project_id, user_id) not in project_counts:
                project_counts[(project_id, user_id)] = {
                    "blog_1000": 0,
                    "blog_1500": 0,
                    "blog_2500": 0,
                    "total": 0
                }
            
            # Count total blogs per project
            project_counts[(project_id, user_id)]["total"] += 1
            
            # Get word count (handle both fields and formats)
            wc_value = blog.get("word_count")
            if wc_value is None:
                wc_value = blog.get("words_count")
            
            # Handle string literals directly
            if wc_value == "1500":
                project_counts[(project_id, user_id)]["blog_1500"] += 1
                continue
            elif wc_value == "1000":
                project_counts[(project_id, user_id)]["blog_1000"] += 1
                continue
            elif wc_value == "2500":
                project_counts[(project_id, user_id)]["blog_2500"] += 1
                continue
            
            # Convert to numeric and count by range
            try:
                numeric_wc = None
                if isinstance(wc_value, (int, float)):
                    numeric_wc = int(wc_value)
                elif isinstance(wc_value, str) and wc_value.isdigit():
                    numeric_wc = int(wc_value)
                
                if numeric_wc is not None:
                    if 500 <= numeric_wc <= 1000:
                        project_counts[(project_id, user_id)]["blog_1000"] += 1
                    elif 1001 <= numeric_wc <= 1500:
                        project_counts[(project_id, user_id)]["blog_1500"] += 1
                    elif 1501 <= numeric_wc <= 2500:
                        project_counts[(project_id, user_id)]["blog_2500"] += 1
            except (ValueError, TypeError):
                word_count_issues += 1
                continue
        
        # Prepare values for bulk insert
        insert_values = []
        updated_projects = set()
        
        # First add projects with blogs
        for (project_id, user_id), counts in project_counts.items():
            # Get project metadata - try project_meta first, then existing_entries as fallback
            meta = project_meta.get(project_id)
            if not meta:
                meta = existing_entries.get(project_id)
                if not meta:
                    logger.warning(f"Missing metadata for project {project_id}, using basic info")
                    meta = {
                        "user_id": user_id,
                        "name": "Unknown Project",
                        "url": ""
                    }
            
            # Mark this project as updated
            updated_projects.add(project_id)
            
            # Add to insert values
            insert_values.append((
                project_id,
                user_id,
                counts["blog_1000"],
                counts["blog_1500"],
                counts["blog_2500"],
                gsc_counts.get(project_id, 0),
                meta.get("name", "Unknown Project"),
                meta.get("url", "")
            ))
        
        # Then add projects with no blogs (preserve all projects)
        for project_id, meta in project_counts.items():
            if project_id not in updated_projects:
                insert_values.append((
                    project_id,
                    meta["user_id"],
                    0,  # blog_1000
                    0,  # blog_1500
                    0,  # blog_2500
                    gsc_counts.get(project_id, 0),
                    meta["name"],
                    meta["url"]
                ))
        
        # Also include any projects in the existing monitoring table that might not be in projects table
        for project_id, meta in existing_entries.items():
            if project_id not in updated_projects:
                insert_values.append((
                    project_id,
                    meta["user_id"],
                    0,  # blog_1000
                    0,  # blog_1500
                    0,  # blog_2500
                    meta["gsc_connected"],
                    meta["name"],
                    meta["url"]
                ))
        
        # Execute the transaction
        try:
            # Begin transaction
            cur.execute("BEGIN")
            
            # Delete existing entries
            cur.execute("DELETE FROM public.monitoring_project_stats")
            
            # Insert new values (bulk insert for efficiency)
            if insert_values:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO public.monitoring_project_stats
                    (project_id, user_id, blog_1000, blog_1500, blog_2500, gsc_connected, project_name, project_url)
                    VALUES %s
                    """,
                    insert_values
                )
            
            # Commit the transaction
            cur.execute("COMMIT")
            
        except Exception as e:
            # Roll back on error
            cur.execute("ROLLBACK")
            logger.error(f"Transaction error in cron refresh: {e}")
            raise
        
        # Get final count
        cur.execute("SELECT COUNT(*) FROM public.monitoring_project_stats")
        final_count = cur.fetchone()[0]
        
        # Close database connections
        cur.close()
        conn.close()
        
        # Calculate execution time
        execution_time = time.time() - start_time
        
        return {
            "status": "success",
            "message": f"Monitoring stats refreshed successfully in {execution_time:.2f} seconds",
            "projects_with_blogs": len(project_counts),
            "total_blogs_processed": len(all_blogs),
            "word_count_issues": word_count_issues,
            "total_rows_inserted": len(insert_values),
            "final_table_size": final_count
        }
    except Exception as e:
        logger.error(f"Error in cron refresh monitoring: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "message": str(e)
        }
