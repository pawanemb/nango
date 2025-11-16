from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import create_client
from app.core.config import settings
from app.core.logging_config import logger

security = HTTPBearer()

# Initialize Supabase client
try:
    supabase = create_client(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_KEY.strip('"')  # Remove any quotes
    )
    logger.info("Supabase client initialized")
except Exception as e:
    logger.error(f"Failed to initialize Supabase client: {str(e)}")
    raise

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    try:
        token = credentials.credentials
        user = supabase.auth.get_user(token)
        return user.user
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials"
        )
