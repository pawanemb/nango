from fastapi import APIRouter
from app.core.logging_config import logger
from app.services.mongodb_service import MongoDBService

router = APIRouter()

@router.get("/")
def health_check():
    """Check the health of the application and its dependencies."""
    logger.info("Health check endpoint accessed")
    
    # Check MongoDB connection
    mongodb_status = "healthy"
    try:
        if MongoDBService._client:
            MongoDBService._client.admin.command('ping')
        else:
            mongodb_status = "not connected"
    except Exception as e:
        logger.error(f"MongoDB health check failed: {str(e)}")
        mongodb_status = "unhealthy"

    return {
        "status": "healthy",
        "services": {
            "mongodb": mongodb_status
        }
    }
