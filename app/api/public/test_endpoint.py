from fastapi import APIRouter

# Create router for public test endpoints
router = APIRouter(tags=["test"])

@router.get("/healthcheck", summary="Simple health check endpoint that doesn't require auth")
def public_health_check():
    """
    Public health check endpoint that doesn't require authentication.
    Used to test if the public API routes are working correctly.
    """
    return {
        "status": "success",
        "message": "Public API endpoint is working correctly"
    } 