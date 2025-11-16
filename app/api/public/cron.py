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

def get_gsc_performance_metrics_sync(project_id: str, cur):
    """Get GSC performance metrics for a project using direct database queries and GSC API."""
    try:
        from datetime import datetime, timedelta
        from app.services.gsc_service import GSCService
        from uuid import UUID
        import json
        import asyncio
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        
        # Calculate date range (last 30 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        # Check if project has GSC account
        cur.execute(
            "SELECT site_url, credentials FROM public.gsc_accounts WHERE project_id = %s LIMIT 1",
            (project_id,)
        )
        gsc_account = cur.fetchone()
        
        if not gsc_account:
            return {
                "clicks": 0,
                "impressions": 0,
                "ctr": 0.0,
                "position": 0.0
            }
        
        site_url = gsc_account['site_url']
        credentials_json = gsc_account['credentials']
        
        try:
            # Parse credentials from JSON
            if isinstance(credentials_json, str):
                credentials = json.loads(credentials_json)
            else:
                credentials = credentials_json
            
            # Create credentials object
            creds = Credentials(
                token=credentials.get('token'),
                refresh_token=credentials.get('refresh_token'),
                token_uri=credentials.get('token_uri'),
                client_id=credentials.get('client_id'),
                client_secret=credentials.get('client_secret'),
                scopes=credentials.get('scopes', ['https://www.googleapis.com/auth/webmasters.readonly'])
            )
            
            # Build the service
            service = build('searchconsole', 'v1', credentials=creds)
            
            # Query GSC API for performance data
            request = {
                'startDate': start_date_str,
                'endDate': end_date_str,
                'dimensions': [],  # No dimensions for summary
                'searchType': 'web'
            }
            
            response = service.searchanalytics().query(
                siteUrl=site_url,
                body=request
            ).execute()
            
            # Extract metrics from response
            rows = response.get('rows', [])
            if rows:
                # Sum up all the metrics (should be one row since no dimensions)
                total_clicks = sum(row.get('clicks', 0) for row in rows)
                total_impressions = sum(row.get('impressions', 0) for row in rows)
                
                # Calculate weighted averages for CTR and position
                if total_impressions > 0:
                    weighted_ctr = sum(row.get('ctr', 0) * row.get('impressions', 0) for row in rows)
                    weighted_position = sum(row.get('position', 0) * row.get('impressions', 0) for row in rows)
                    
                    avg_ctr = (weighted_ctr / total_impressions) * 100  # Convert to percentage
                    avg_position = weighted_position / total_impressions
                else:
                    avg_ctr = 0.0
                    avg_position = 0.0
                
                return {
                    "clicks": total_clicks,
                    "impressions": total_impressions,
                    "ctr": round(avg_ctr, 2),
                    "position": round(avg_position, 2)
                }
            else:
                # No data for the period
                return {
                    "clicks": 0,
                    "impressions": 0,
                    "ctr": 0.0,
                    "position": 0.0
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
        logger.error(f"Error in get_gsc_performance_metrics_sync for project {project_id}: {e}")
        return {
            "clicks": 0,
            "impressions": 0,
            "ctr": 0.0,
            "position": 0.0
        }

@router.post("/refresh-monitoring", summary="Public endpoint for external cron service to refresh monitoring stats")
def cron_refresh_monitoring(api_key: str = Header(None)):
    """
    Public endpoint for external cron service (like EasyCron or GitHub Actions) to refresh monitoring stats.
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
        mongo_db = get_mongodb()
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
            
            # Get GSC performance metrics for this project
            gsc_metrics = get_gsc_performance_metrics_sync(project_id, cur)
            
            # Add to insert values
            insert_values.append((
                project_id,
                user_id,
                counts["blog_1000"],
                counts["blog_1500"],
                counts["blog_2500"],
                gsc_counts.get(project_id, 0),
                gsc_metrics["clicks"],
                gsc_metrics["impressions"],
                gsc_metrics["ctr"],
                gsc_metrics["position"],
                meta.get("name", "Unknown Project"),
                meta.get("url", "")
            ))
        
        # Then add projects with no blogs (preserve all projects)
        for project_id, meta in project_meta.items():
            if project_id not in updated_projects:
                # Get GSC performance metrics for this project
                gsc_metrics = get_gsc_performance_metrics_sync(project_id, cur)
                
                insert_values.append((
                    project_id,
                    meta["user_id"],
                    0,  # blog_1000
                    0,  # blog_1500
                    0,  # blog_2500
                    gsc_counts.get(project_id, 0),
                    gsc_metrics["clicks"],
                    gsc_metrics["impressions"],
                    gsc_metrics["ctr"],
                    gsc_metrics["position"],
                    meta["name"],
                    meta["url"]
                ))
        
        # Also include any projects in the existing monitoring table that might not be in projects table
        for project_id, meta in existing_entries.items():
            if project_id not in updated_projects:
                # Get GSC performance metrics for this project
                gsc_metrics = get_gsc_performance_metrics_sync(project_id, cur)
                
                insert_values.append((
                    project_id,
                    meta["user_id"],
                    0,  # blog_1000
                    0,  # blog_1500
                    0,  # blog_2500
                    meta["gsc_connected"],
                    gsc_metrics["clicks"],
                    gsc_metrics["impressions"],
                    gsc_metrics["ctr"],
                    gsc_metrics["position"],
                    meta["name"],
                    meta["url"]
                ))
        
        # Execute the transaction
        try:
            # Delete existing entries
            cur.execute("DELETE FROM public.monitoring_project_stats")
            
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
            
            # Commit the transaction
            cur.execute("COMMIT")
            
        except Exception as e:
            # Roll back on error
            cur.execute("ROLLBACK")
            logger.error(f"Transaction error in cron refresh: {e}")
            raise

        # Execute the transaction with UPSERT approach
        try:
            # Start transaction
            cur.execute("BEGIN")
            
            # Use UPSERT approach with ON CONFLICT
            if insert_values:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO public.monitoring_project_stats
                    (project_id, user_id, blog_1000, blog_1500, blog_2500, gsc_connected, gsc_clicks, gsc_impressions, gsc_ctr, gsc_position, project_name, project_url)
                    VALUES %s
                    ON CONFLICT (project_id) 
                    DO UPDATE SET
                        user_id = EXCLUDED.user_id,
                        blog_1000 = EXCLUDED.blog_1000,
                        blog_1500 = EXCLUDED.blog_1500,
                        blog_2500 = EXCLUDED.blog_2500,
                        gsc_connected = EXCLUDED.gsc_connected,
                        gsc_clicks = EXCLUDED.gsc_clicks,
                        gsc_impressions = EXCLUDED.gsc_impressions,
                        gsc_ctr = EXCLUDED.gsc_ctr,
                        gsc_position = EXCLUDED.gsc_position,
                        project_name = EXCLUDED.project_name,
                        project_url = EXCLUDED.project_url,
                        updated_at = CURRENT_TIMESTAMP
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
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "message": str(e)
        } 