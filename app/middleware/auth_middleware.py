from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from supabase import create_client
import os
from dotenv import load_dotenv
from app.core.logging_config import logger
import jwt
import traceback
from types import SimpleNamespace
import gotrue
from starlette.responses import Response
from fastapi import Depends

load_dotenv()

security = HTTPBearer()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

async def verify_token(request: Request) -> dict:
    """
    Verify the authentication token from the request.
    Returns the authenticated user object or raises HTTPException.
    """
    auth = request.headers.get("Authorization")
    if not auth:
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": "No valid authorization token provided"}
        )
    
    try:
        # Extract token from Authorization header
        try:
            token_type, token = auth.split()
            if token_type.lower() != "bearer":
                raise ValueError("Invalid token type")
        except ValueError as e:
            return JSONResponse(
                status_code=401,
                content={"status": "error", "message": f"Invalid Authorization header format: {str(e)}"}
            )
        
        # Log token for debugging (remove in production)
        # logger.debug(f"Attempting to verify token: {token[:10]}...")
        
        # First try to decode the token to check its structure
        try:
            decoded = jwt.decode(token, options={"verify_signature": False})
            # logger.debug(f"Token decoded successfully: {decoded}")
        except jwt.InvalidTokenError as e:
            logger.error(f"Token decode failed: {str(e)}")
            return JSONResponse(
                status_code=401,
                content={"status": "error", "message": "Invalid token format"}
            )
        
        # Now verify with Supabase
        try:
            user = supabase.auth.get_user(token)
            if not user or not user.user or not user.user.id:
                raise ValueError("Invalid user data in token response")
            logger.info(f"Token verified successfully for user: {user.user.email}")
            return user
        except Exception as e:
            logger.error(f"Supabase verification failed: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return JSONResponse(
                status_code=401,
                content={"status": "error", "message": "Token verification failed"}
            )
            
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        # More specific error messages based on the exception
        if isinstance(e, jwt.ExpiredSignatureError):
            return JSONResponse(
                status_code=401,
                content={"status": "error", "message": "Token has expired"}
            )
        elif isinstance(e, jwt.InvalidTokenError):
            return JSONResponse(
                status_code=401,
                content={"status": "error", "message": "Invalid token format"}
            )
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": "Token verification failed"}
        )

async def verify_request_origin(request: Request):
    """
    Verify the request origin and token, returning the authenticated user.
    Raises HTTPException if authentication fails.
    """
    try:
        # Verify token and get user
        user = await verify_token(request)
        if isinstance(user, dict):
            user = SimpleNamespace(**user)
        logger.info(f"Authenticated user ID: {user.user.id}")
        
        # Get refresh token from headers if present
        refresh_token = request.headers.get("Refresh-Token")
        if refresh_token:
            try:
                # Attempt to refresh the token
                refresh_response = supabase.auth.refresh_session(refresh_token)
                # Add new tokens to response headers
                request.state.new_access_token = refresh_response.session.access_token
                request.state.new_refresh_token = refresh_response.session.refresh_token
            except Exception as e:
                logger.error(f"Token refresh failed: {str(e)}")
                # If refresh fails, continue with current token if it's still valid
                pass
        
        return user.user
    except Exception as e:
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": str(e)}
        )

def verify_token_sync(request: Request) -> dict:
    """
    Synchronous version of verify_token.
    Verify the authentication token from the request.
    Returns the authenticated user object or raises HTTPException.
    """
    # Log token for debugging (remove in production)
    logger.debug(f"Attempting to verify token: {request.headers.get('Authorization')[:10]}...")
    logger.debug(f"Attempting to verify token: {request.headers.get('Authorization')[:10]}...")
    try:
        # Get token from Authorization header
        auth = request.headers.get("Authorization")
        if not auth:
            return JSONResponse(
                    status_code=401,
                    content={"status": "error", "message": "No valid authorization token provided"}
                )

        # Extract token
        try:
            token_type, token = auth.split()
            if token_type.lower() != "bearer":
                raise ValueError("Invalid token type")
        except ValueError as e:
            return JSONResponse(
                status_code=401,
                content={"status": "error", "message": f"Invalid Authorization header format: {str(e)}"}
            )

        # First try to decode the token to check its structure
        try:
            decoded = jwt.decode(token, options={"verify_signature": False})
        except jwt.InvalidTokenError as e:
            logger.error(f"Token decode failed: {str(e)}")
            return JSONResponse(
                status_code=401,
                content={"status": "error", "message": "Invalid token format"}
            )
        
        # Now verify with Supabase
        try:
            user = supabase.auth.get_user(token)
            if not user or not user.user or not user.user.id:
                raise ValueError("Invalid user data in token response")
            logger.info(f"Token verified successfully for user: {user.user.email}")
            return user
        except Exception as e:
            logger.error(f"Supabase verification failed: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return JSONResponse(
                status_code=401,
                content={"status": "error", "message": "Token verification failed"}
            )

    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        if isinstance(e, jwt.ExpiredSignatureError):
            return JSONResponse(
                status_code=401,
                content={"status": "error", "message": "Token has expired"}
            )
        elif isinstance(e, jwt.InvalidTokenError):
            return JSONResponse(
                status_code=401,
                content={"status": "error", "message": "Invalid token format"}
            )
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": "Token verification failed"}
        )

def verify_request_origin_sync(request: Request):
    """
    Synchronous version of verify_request_origin.
    Verify the request origin and token, returning the authenticated user.
    Raises HTTPException if authentication fails.
    """
    try:
        # Verify token and get user
        user = verify_token_sync(request)
        if isinstance(user, dict):
            user = SimpleNamespace(**user)
        logger.info(f"Authenticated user ID: {user.user.id}")
        
        # Get refresh token from headers if present
        refresh_token = request.headers.get("Refresh-Token")
        if refresh_token:
            user.refresh_token = refresh_token
            
        return user
        
    except Exception as e:
        logger.error(f"Request origin verification failed: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=401,
            detail="Authentication failed"
        )

class AuthMiddleware:
    async def __call__(self, request: Request, call_next):
        """
        Middleware that verifies JWT tokens and handles token refresh.
        Skips verification for public endpoints and OPTIONS requests.
        """
        # Skip auth for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Skip auth for public endpoints
        if request.url.path in [
            "/api/v1/auth/login", 
            "/api/v1/auth/signup", 
            "/api/v1/health",
            "/api/v1/auth/google",  
            "/api/v1/auth/google/callback",
            "/api/v1/auth/linkedin",  
            "/api/v1/auth/linkedin/callback",
            "/api/v1/auth/refresh-token",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/reset-password",
            "/api/v1/auth/resend-verification",
            "/api/v1/auth/verify-email",
            "/",
            "/openapi.json",
            "/docs",
            "/api/v1/admin-refresh-all-monitoring",
            "/api/v1/health/live",
            "/test-gsc-report",
            "/test-gsc-report-email"
        ] or request.url.path.startswith("/api/public/"):
            return await call_next(request)

        try:
            auth = request.headers.get("Authorization")
            if not auth:
                return JSONResponse(
                    status_code=401,
                    content={"status": "error", "message": "No valid authorization token provided"}
                )
            
            # Extract token from Authorization header
            try:
                token_type, token = auth.split()
                if token_type.lower() != "bearer":
                    raise ValueError("Invalid token type")
            except ValueError as e:
                return JSONResponse(
                    status_code=401,
                    content={"status": "error", "message": f"Invalid Authorization header format: {str(e)}"}
                )
            
            # Log the raw token for debugging (remove in production)
            # logger.debug(f"Raw token received: {token[:10]}...")
            
            try:
                user = await verify_token(request)
                if isinstance(user, dict):
                    user = SimpleNamespace(**user)
                if not user or not user.user or not user.user.id:
                    return JSONResponse(
                        status_code=401,
                        content={"status": "error", "message": "Token verification failed"}
                    )
                # Convert user to object with attributes
                request.state.user = SimpleNamespace(**{
                    "user": SimpleNamespace(**{
                        "id": user.user.id,
                        "email": user.user.email,
                        "app_metadata": user.user.app_metadata,
                        "user_metadata": user.user.user_metadata
                    })
                })
                # logger.debug(f"User data set in state: {request.state.user}")
            except Exception as e:
                logger.error(f"Token verification failed: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                return JSONResponse(
                    status_code=401,
                    content={"status": "error", "message": "Token verification failed"}
                )
            
            response = await call_next(request)
            
            # Get refresh token from headers if present
            refresh_token = request.headers.get("Refresh-Token")
            if refresh_token:
                try:
                    # Attempt to refresh the token
                    refresh_response = supabase.auth.refresh_session(refresh_token)
                    # Add new tokens to response headers
                    response.headers["New-Access-Token"] = refresh_response.session.access_token
                    response.headers["New-Refresh-Token"] = refresh_response.session.refresh_token
                except Exception as e:
                    logger.error(f"Token refresh failed: {str(e)}")
                    # If refresh fails, continue with current token if it's still valid
                    pass
            
            return response
        except Exception as e:
            logger.error(f"Middleware error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": "Internal server error in auth middleware"}
            )

class SyncAuthMiddleware:
    async def __call__(self, request: Request, call_next):
        """
        Middleware that verifies JWT tokens and handles token refresh.
        Skips verification for public endpoints and OPTIONS requests.
        """
        # Skip auth for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Skip auth for public endpoints
        if request.url.path in [
            "/api/v1/auth/login", 
            "/api/v1/auth/signup", 
            "/api/v1/health",
            "/api/v1/auth/google",  
            "/api/v1/auth/google/callback",
            "/api/v1/auth/linkedin",  
            "/api/v1/auth/linkedin/callback",
            "/api/v1/auth/refresh-token",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/reset-password",
            "/api/v1/auth/resend-verification",
            "/api/v1/auth/verify-email",
            "/",
            "/openapi.json",
            "/docs",
            "/api/v1/health/live",
            "/api/v1/admin-refresh-all-monitoring",
            "/test-gsc-report",
            "/test-gsc-report-email"
        ] or request.url.path.startswith("/api/public/"):
            return await call_next(request)

        try:
            auth = request.headers.get("Authorization")
            if not auth:
                return JSONResponse(
                    status_code=401,
                    content={"status": "error", "message": "No valid authorization token provided"}
                )
            
            # Extract token from Authorization header
            try:
                token_type, token = auth.split()
                if token_type.lower() != "bearer":
                    raise ValueError("Invalid token type")
            except ValueError as e:
                return JSONResponse(
                    status_code=401,
                    content={"status": "error", "message": f"Invalid Authorization header format: {str(e)}"}
                )

            # Verify token synchronously
            user = verify_token_sync(request)
            if isinstance(user, JSONResponse):
                return user

            # Store user in request state
            request.state.user = user
            
            # Log activity to database
            try:
                from app.services.simple_activity_logger import log_activity
                
                # Get user's full name from user_metadata if available
                user_name = None
                if hasattr(user.user, 'user_metadata') and user.user.user_metadata:
                    user_name = user.user.user_metadata.get('full_name')
                
                # Get provider from app_metadata
                provider = None
                if hasattr(user.user, 'app_metadata') and user.user.app_metadata:
                    provider = user.user.app_metadata.get('provider')
                
                log_activity(
                    user_id=str(user.user.id),
                    user_email=user.user.email,
                    endpoint=str(request.url.path),
                    name=user_name,
                    provider=provider
                )
            except Exception as log_error:
                logger.error(f"Activity logging error: {log_error}")
            
            try:
                # Call next middleware/route handler
                response = await call_next(request)
                return response
            except Exception as e:
                logger.error(f"Error in route handler: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                return JSONResponse(
                    status_code=500,
                    content={"status": "error", "message": "Internal server error"}
                )

        except Exception as e:
            logger.error(f"Authentication middleware error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return JSONResponse(
                status_code=401,
                content={"status": "error", "message": "Authentication failed"}
            )

async def get_current_user(request: Request):
    """
    FastAPI dependency to get the current authenticated user.
    This function is used as a dependency in route handlers.
    """
    user = await verify_request_origin(request)
    if isinstance(user, JSONResponse):
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    return user
