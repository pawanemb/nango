from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.logging_config import logger
from app.api.v1.endpoints import monitoring

from app.api.v1.endpoints import (
    auth,
    projects,
    health,
    task_status,
    keywords,
    keyword_suggestions,
    secondary_keywords,
    category_selection,
    title_generation,
    meta_description,
    plagiarism,
    outline_generation,
    claude_outline_generation,
    blog_generation,
    blog,
    latest_blogs,
    gsc,
    oauth,
    cms,
    payment,
    account,
    invoice,
    brand_tone,
    featured_image_style,
    project_images,
    user_information,
    streaming_outline,  # 🚀 NEW: Streaming outline generation
    streaming_sources,  # 🚀 NEW: Streaming sources collection
    add_custom_source_endpoint,
    add_custom_source_text_endpoint,
    add_custom_source_pdf_endpoint,  # 🚀 NEW: Add custom source endpoint
    text_shortening,  
    convert_to_table,  # 🚀 NEW: Convert to table with streaming
    convert_to_list,  # 🚀 NEW: Convert to list with streaming
)
from app.middleware.auth_middleware import SyncAuthMiddleware
from app.services.mongodb_service import MongoDBService
import time
from dotenv import load_dotenv
import os
import sys
from fastapi.templating import Jinja2Templates
from fastapi import Depends, HTTPException
from app.middleware.auth_middleware import verify_request_origin

# Load environment variables from .env file
load_dotenv()

# Simple Pro access control function
async def require_pro(current_user = Depends(verify_request_origin)):
    """Check if user has active Pro plan"""
    from app.models.account import Account
    from app.db.session import get_db
    from datetime import datetime
    import pytz
    
    db = next(get_db())
    account = db.query(Account).filter(Account.user_id == current_user.id).first()
    
    if not account or account.plan_type != "pro":
        raise HTTPException(
            status_code=403, 
            detail={
                "error": "Pro plan required",
                "message": "This feature requires a Pro subscription",
                "current_plan": account.plan_type if account else "free",
                "upgrade_url": "https://app.rayo.work/upgrade"
            }
        )
    
    # Check if plan is expired using timezone-aware datetime
    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist)
    if account.plan_end_date and account.plan_end_date < current_time:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Pro plan expired", 
                "message": "Your Pro subscription has expired",
                "plan_expired": True,
                "upgrade_url": "https://app.rayo.work/upgrade"
            }
        )
    
    return True

# Simple Sentry setup for API tracking
import sentry_sdk
if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        send_default_pii=True,
    )

app = FastAPI(
    title="Rayo Search Project",
    description="A well-structured FastAPI project",
    version="1.0.0"
)

# Define allowed origins
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://192.168.2.8:5173",
    "http://localhost:3000", 
    "http://localhost:8000",
    "https://devapi.rayo.work",
    "https://rayo.work",
    "https://dev.rayo.work",
    "https://testing.rayo.work",
    "https://www.rayo.work",
    "https://www.dev.rayo.work",
    "https://app.rayo.work",
    "https://prodapi.rayo.work"
]

# Configure CORS with strict origin checking
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=None,  # Disable regex matching for stricter control
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "Authorization", 
        "Content-Type", 
        "Accept",
        "Accept-Language",
        "Origin",
        "Refresh-Token",
        "X-Requested-With",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
        "Cache-Control"  # ✅ ADD MISSING CACHE-CONTROL HEADER
    ],
    expose_headers=[
        "Content-Type", 
        "Authorization", 
        "Refresh-Token", 
        "New-Access-Token", 
        "New-Refresh-Token",
        "Access-Control-Allow-Origin",
        "Access-Control-Allow-Credentials"
    ],
    max_age=3600  # Increased from 600 to 3600 seconds
)

# Add Auth middleware
app.middleware("http")(SyncAuthMiddleware())

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(health.router, prefix="/api/v1/health", tags=["health"])
app.include_router(task_status.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(keywords.router, prefix="/api/v1/projects/{project_id}/keywords", tags=["keywords"])
app.include_router(keyword_suggestions.router, prefix="/api/v1/projects/{project_id}/keyword-suggestions", tags=["keyword-suggestions"])
app.include_router(secondary_keywords.router, prefix="/api/v1/projects/{project_id}/secondary-keywords", tags=["secondary-keywords"])
app.include_router(category_selection.router, prefix="/api/v1/projects/{project_id}/category-selection", tags=["category-selection"])
app.include_router(title_generation.router, prefix="/api/v1/projects/{project_id}/title-generation", tags=["title-generation"])
app.include_router(meta_description.router, prefix="/api/v1/projects/{project_id}/meta-description", tags=["meta-description"])
app.include_router(plagiarism.router, prefix="/api/v1/projects/{project_id}/plagiarism", tags=["plagiarism"])
app.include_router(outline_generation.router, prefix="/api/v1/projects/{project_id}/outline-generation", tags=["outline-generation"])
app.include_router(claude_outline_generation.router, prefix="/api/v1/projects/{project_id}/outline-generation", tags=["claude-outline-generation"])
app.include_router(blog_generation.router, prefix="/api/v1/projects/{project_id}/blog-generation", tags=["blog-generation"])
app.include_router(latest_blogs.router, prefix="/api/v1/projects/{project_id}/blog", tags=["latest-blogs"])
app.include_router(blog.router, prefix="/api/v1/projects/{project_id}/blog", tags=["blog"])
app.include_router(gsc.router, prefix="/api/v1/projects/{project_id}/gsc", tags=["gsc"])
app.include_router(oauth.router, prefix="/api/v1/projects/{project_id}/oauth/google", tags=["oauth"])
app.include_router(cms.router, prefix="/api/v1/projects/{project_id}/cms", tags=["cms"])
app.include_router(payment.router, prefix="/api/v1/payment", tags=["payment"])
app.include_router(account.router, prefix="/api/v1/account", tags=["account"])
app.include_router(invoice.router, prefix="/api/v1/invoice", tags=["invoice"])
app.include_router(monitoring.router, prefix="/api/v1", tags=["monitoring"])
app.include_router(brand_tone.router, prefix="/api/v1/brand-tone", tags=["brand-tone"])
app.include_router(featured_image_style.router, prefix="/api/v1/featured-image-style", tags=["featured-image-style"])
app.include_router(project_images.router, prefix="/api/v1", tags=["project-images"])
app.include_router(user_information.router, prefix="/api/v1/user-information", tags=["user-information"])

# 🚀 NEW: Add streaming outline router
app.include_router(streaming_outline.router, prefix="/api/v1/projects/{project_id}", tags=["streaming-outline"])

# 🚀 NEW: Add streaming sources router
app.include_router(streaming_sources.router, prefix="/api/v1/projects/{project_id}", tags=["streaming-sources"])

# 🚀 NEW: Add custom source endpoint router
app.include_router(add_custom_source_endpoint.router, prefix="/api/v1/projects/{project_id}", tags=["add-custom-source"])

# 🚀 NEW: Add custom source text endpoint router
app.include_router(add_custom_source_text_endpoint.router, prefix="/api/v1/projects/{project_id}", tags=["add-custom-source-text"])

# 🚀 NEW: Add custom source pdf endpoint router
app.include_router(add_custom_source_pdf_endpoint.router, prefix="/api/v1/projects/{project_id}", tags=["add-custom-source-pdf"])

# 🚀 NEW: Add text shortening router  
app.include_router(text_shortening.router, prefix="/api/v1/projects/{project_id}/text-shortening", tags=["text-shortening"], dependencies=[Depends(require_pro)])

# 🚀 NEW: Add convert to table router
app.include_router(convert_to_table.router, prefix="/api/v1/projects/{project_id}/convert-to-table", tags=["convert-to-table"], dependencies=[Depends(require_pro)])

# 🚀 NEW: Add convert to list router
app.include_router(convert_to_list.router, prefix="/api/v1/projects/{project_id}/convert-to-list", tags=["convert-to-list"], dependencies=[Depends(require_pro)]    )

# Add public cron router that bypasses auth middleware
from app.api.public.cron import router as cron_router
app.include_router(cron_router, prefix="/api/public", tags=["monitoring-cron"])

# Add public cron router that bypasses auth middleware
from app.api.public.cron_fix import router as cron_fix_router
app.include_router(cron_fix_router, prefix="/api/public/v2", tags=["monitoring-cron-v2"])

# Add a test public endpoint
from app.api.public.test_endpoint import router as test_router
app.include_router(test_router, prefix="/api/public/test", tags=["test"])

templates = Jinja2Templates(directory="app/templates")

@app.on_event("startup")
def startup_event():
    """Initialize connections on startup"""
    try:
        # Fix Windows console encoding for Unicode support
        if sys.platform == "win32":
            try:
                os.system("chcp 65001 > nul")
                os.environ["PYTHONIOENCODING"] = "utf-8"
                os.environ["PYTHONLEGACYWINDOWSSTDIO"] = "utf-8"
                if hasattr(sys.stdout, 'reconfigure'):
                    sys.stdout.reconfigure(encoding='utf-8')
                    sys.stderr.reconfigure(encoding='utf-8')
                logger.info("✅ Windows console encoding configured for Unicode support")
            except Exception as e:
                logger.warning(f"⚠️  Could not configure console encoding: {e}")
        
        # Close any existing MongoDB connections first
        if MongoDBService._client is not None:
            logger.info("Cleaning up existing MongoDB connections...")
            MongoDBService.close_connections()
        
        logger.info("Initializing MongoDB connection...")
        MongoDBService.init_db()
        
        # Verify connections are working
        db = MongoDBService.get_db()
        db.command('ping')
        logger.info("MongoDB connection initialized and verified")
        
    except Exception as e:
        logger.error(f"Failed to initialize MongoDB connection: {str(e)}")
        logger.exception("Full traceback:")
        # Fail fast - don't let the app start with a broken MongoDB connection
        raise RuntimeError(f"Application startup failed: MongoDB connection error - {str(e)}")

@app.on_event("shutdown")
def shutdown_event():
    """Close connections on shutdown"""
    shutdown_successful = True
    try:
        logger.info("Starting graceful shutdown...")        
        # Close MongoDB connections
        logger.info("Closing MongoDB connections...")
        try:
            MongoDBService.close_connections()
            logger.info("MongoDB connections closed successfully")
        except Exception as e:
            shutdown_successful = False
            logger.error(f"Error closing MongoDB connections: {str(e)}")
            logger.exception("Full traceback:")
            
        # Add any other cleanup tasks here
        # Each should be in its own try-except block
        # to ensure all cleanup attempts run even if some fail
        
        if shutdown_successful:
            logger.info("All connections closed successfully")
        else:
            logger.warning("Some connections may not have been closed properly")
            
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")
        logger.exception("Full traceback:")
    finally:
        logger.info("Shutdown process completed")

# Add a liveliness probe endpoint
@app.get("/api/v1/health/live")
def liveliness():
    """Check if the application is alive and database connections are working"""
    try:
        # Test MongoDB connection
        db = MongoDBService.get_db()
        db.command('ping')
        return {"status": "healthy"}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )

@app.middleware("http")
async def verify_origin(request: Request, call_next):
    origin = request.headers.get("Origin")
    
    # 🔍 DEBUG LOGGING FOR CORS ISSUES
    if request.method == "OPTIONS":
        logger.info(f"🔧 MIDDLEWARE: OPTIONS request received:")
        logger.info(f"   📍 URL: {request.url}")
        logger.info(f"   🌐 Origin: {origin}")
        logger.info(f"   📋 Headers: {dict(request.headers)}")
        logger.info(f"   ✅ Allowed Origins: {ALLOWED_ORIGINS}")
    
    # Skip origin check for non-browser requests (no Origin header)
    if not origin:
        if request.method == "OPTIONS":
            logger.info("   ⏭️ No Origin header - proceeding to handler")
        return await call_next(request)
    
    # Check if origin is allowed
    if origin not in ALLOWED_ORIGINS:
        logger.error(f"   ❌ Origin {origin} NOT in allowed list!")
        logger.error(f"   📝 Allowed: {ALLOWED_ORIGINS}")
        return JSONResponse(
            status_code=403,
            content={
                "status": "error",
                "message": "Origin not allowed",
                "detail": f"Origin {origin} is not in the allowed origins list"
            }
        )
    
    if request.method == "OPTIONS":
        logger.info(f"   ✅ Origin {origin} is allowed - proceeding to handler")
    
    response = await call_next(request)
    return response

@app.get("/")
def root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to Rayo Search Project"}