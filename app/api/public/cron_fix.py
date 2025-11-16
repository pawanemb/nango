from fastapi import APIRouter, Header
from pymongo.database import Database
from app.services.mongodb_service import MongoDBService
import logging
import time
import psycopg2
import psycopg2.extras
import traceback
from app.core.config import settings

logger = logging.getLogger("fastapi_app")

# Create router for public endpoints (no auth required)
router = APIRouter(tags=["monitoring-cron"])

def get_mongodb() -> Database:
    """Return a synchronous MongoDB Database handle."""
    mongodb_service = MongoDBService()
    return mongodb_service.get_sync_db()

@router.post("/refresh-monitoring", summary="Public endpoint for external cron service to refresh monitoring stats")
def cron_refresh_monitoring(api_key: str = Header(None)):
    """
    Public endpoint for external cron service to refresh monitoring stats.
    This bypasses the need for Celery/Redis by using direct SQL operations.
    
    The endpoint requires an API key in the header for security.
    Example cron command: curl -X POST "https://your-api.com/api/public/refresh-monitoring" -H "api-key: YOUR_SECRET_KEY"
    """
    # Check API key for security
    valid_api_key = settings.CRON_API_KEY
    if not api_key or api_key != valid_api_key:
        logger.warning(f"Invalid API key used in cron refresh attempt")
        return {"status": "error", "message": "Invalid API key"}
    
    # Get start time for performance tracking
    start_time = time.time()
    
    try:
        # Connect to MongoDB
        mongo_db = get_mongodb()
        
        # Get all blogs from MongoDB with word count info
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
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=settings.POSTGRES_HOST,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            port=settings.POSTGRES_PORT
        )
        
        # Important: Turn off autocommit so we can use transactions
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get project metadata
        cur.execute("SELECT id, user_id, name, url FROM public.projects")
        project_meta = {str(row["id"]): {
            "user_id": str(row["user_id"]),
            "name": row["name"],
            "url": row["url"]
        } for row in cur.fetchall()}
        
        # Get GSC account counts
        cur.execute("""
            SELECT project_id, COUNT(*) as count 
            FROM public.gsc_accounts 
            GROUP BY project_id
        """)
        gsc_counts = {str(row["project_id"]): row["count"] for row in cur.fetchall()}
        
        # Update each project individually (safer than bulk update)
        updated_count = 0
        
        try:
            # Start a transaction
            cur.execute("BEGIN")
            
            # Update each project with blog counts
            for (project_id, user_id), counts in project_counts.items():
                # Get project metadata 
                meta = project_meta.get(project_id, {"name": "Unknown", "url": ""})
                
                # Try to update existing record
                cur.execute("""
                    UPDATE public.monitoring_project_stats 
                    SET blog_1000 = %s, 
                        blog_1500 = %s, 
                        blog_2500 = %s, 
                        gsc_connected = %s,
                        project_name = %s,
                        project_url = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE project_id = %s
                """, (
                    counts["blog_1000"], 
                    counts["blog_1500"], 
                    counts["blog_2500"], 
                    gsc_counts.get(project_id, 0),
                    meta.get("name", "Unknown"),
                    meta.get("url", ""),
                    project_id
                ))
                
                # If no row was updated, insert a new one
                if cur.rowcount == 0:
                    cur.execute("""
                        INSERT INTO public.monitoring_project_stats
                        (project_id, user_id, blog_1000, blog_1500, blog_2500, gsc_connected, project_name, project_url)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        project_id,
                        user_id,
                        counts["blog_1000"],
                        counts["blog_1500"],
                        counts["blog_2500"],
                        gsc_counts.get(project_id, 0),
                        meta.get("name", "Unknown"),
                        meta.get("url", "")
                    ))
                
                updated_count += 1
            
            # Commit changes
            conn.commit()
            logger.info(f"Successfully updated {updated_count} projects in monitoring table")
            
        except Exception as e:
            # Roll back on error
            conn.rollback()
            logger.error(f"Transaction error: {e}")
            raise
        finally:
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
            "projects_updated": updated_count
        }
    except Exception as e:
        logger.error(f"Error in cron refresh monitoring: {e}")
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "message": str(e)
        } 