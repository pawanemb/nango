from fastapi import APIRouter, Depends, HTTPException, Request
from app.core.auth import get_current_user
from app.core.logging_config import logger
from app.core.config import settings
from dotenv import load_dotenv
from supabase import create_client, Client
from pydantic import BaseModel
from typing import Optional
from app.middleware.auth_middleware import verify_token
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import os
import requests
import json

router = APIRouter()

# Load environment variables
load_dotenv()

# Fetch Supabase configuration from .env with error handling
SUPABASE_URL = os.getenv("SUPABASE_URL")
if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL environment variable is not set")

SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY environment variable is not set")

REDIRECT_URL = os.getenv("FRONTEND_CALLBACK_URL")
if not REDIRECT_URL:
    logger.warning("FRONTEND_CALLBACK_URL not set, OAuth callbacks may not work properly")
    REDIRECT_URL = "https://app.rayo.work/auth/callback"  # Default fallback

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Import database dependencies for project checking
from app.db.session import get_db_session
from app.models.project import Project

# Define a Pydantic model to validate the request body
class SignupRequest(BaseModel):
    email: str
    password: str
    full_name: str

async def check_user_exists(email: str) -> bool:
    """
    Check if user already exists using Supabase REST API with pagination
    """
    try:
        # Use direct REST API to check user existence with pagination
        page = 1
        per_page = 1000  # Max per page
        
        while True:
            url = f"{SUPABASE_URL}/auth/v1/admin/users"
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"
            }
            params = {
                "page": page,
                "per_page": per_page
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                users_data = response.json()
                users = users_data.get('users', [])
                
                logger.info(f"Page {page}: Found {len(users)} users")
                
                # Check if user exists in this page
                for user in users:
                    if user.get('email') == email:
                        logger.info(f"User {email} found on page {page}")
                        return True
                
                # If we got less than per_page, we've reached the end
                if len(users) < per_page:
                    break
                    
                page += 1
                
            else:
                logger.error(f"Failed to check user existence: {response.status_code} - {response.text}")
                return False
        
        logger.info(f"User existence check for {email}: Not found")
        return False
            
    except Exception as e:
        logger.error(f"Error checking user existence: {str(e)}")
        # If we can't check, allow signup to proceed
        return False

async def get_user_verification_status(email: str) -> dict:
    """
    Get user verification status using Supabase REST API
    Returns: {"exists": bool, "verified": bool, "user_data": dict}
    """
    try:
        page = 1
        per_page = 1000
        
        while True:
            url = f"{SUPABASE_URL}/auth/v1/admin/users"
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"
            }
            params = {
                "page": page,
                "per_page": per_page
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                users_data = response.json()
                users = users_data.get('users', [])
                
                # Check if user exists in this page
                for user in users:
                    if user.get('email') == email:
                        email_confirmed_at = user.get('email_confirmed_at')
                        is_verified = email_confirmed_at is not None
                        
                        logger.info(f"User {email} found - Verified: {is_verified}")
                        return {
                            "exists": True,
                            "verified": is_verified,
                            "user_data": user
                        }
                
                # If we got less than per_page, we've reached the end
                if len(users) < per_page:
                    break
                    
                page += 1
                
            else:
                logger.error(f"Failed to get user status: {response.status_code} - {response.text}")
                return {"exists": False, "verified": False, "user_data": None}
        
        logger.info(f"User {email} not found")
        return {"exists": False, "verified": False, "user_data": None}
            
    except Exception as e:
        logger.error(f"Error getting user status: {str(e)}")
        return {"exists": False, "verified": False, "user_data": None}

@router.post("/signup")
async def signup(request: SignupRequest):
    logger.info(f"Signup attempt for email: {request.email}")
    try:        
        # Check if user already exists
        if await check_user_exists(request.email):
            logger.warning(f"Attempted signup with existing email: {request.email}")
            raise HTTPException(
                status_code=400,
                detail="User with this email already exists"
            )
        
        # Log the signup data for debugging
        logger.info(f"Attempting signup with data: email={request.email}, full_name={request.full_name}")
        
        # Attempt signup with Supabase
        response = supabase.auth.sign_up({
            "email": request.email,
            "password": request.password,
            "options": {
                "data": {
                    "full_name": request.full_name
                }
            }
        })
        
        logger.info(f"Supabase signup completed for: {request.email}")
        
        # Handle successful signup
        if response.user:
            logger.info(f"User successfully signed up: {request.email}")
            return {
                "message": "User signed up successfully! Please check your email for verification.",
                "user": {
                    "id": response.user.id,
                    "email": response.user.email,
                    "full_name": response.user.user_metadata.get("full_name") if response.user.user_metadata else None,
                    "email_confirmed": response.user.email_confirmed_at is not None
                }
            }
        else:
            logger.error("Supabase signup failed - no user in response")
            raise HTTPException(
                status_code=400,
                detail="Failed to create user account"
            )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error during signup process: {str(e)}")
        error_message = str(e)
        
        # Handle specific timeout errors
        if "timed out" in error_message.lower() or "timeout" in error_message.lower():
            raise HTTPException(
                status_code=408,
                detail="Request timed out. Please try again."
            )
        elif "already registered" in error_message.lower():
            raise HTTPException(
                status_code=400,
                detail="User with this email already exists"
            )
        elif "password" in error_message.lower() and "weak" in error_message.lower():
            raise HTTPException(
                status_code=400,
                detail="Password is too weak. Please use a stronger password."
            )
        elif "invalid" in error_message.lower() and "email" in error_message.lower():
            raise HTTPException(
                status_code=400,
                detail="Invalid email address format"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create user account: {error_message}"
            )


class UserLogin(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    user: Optional[dict] = None
    has_created_any: bool = False

@router.post("/login", response_model=LoginResponse)
async def login(user_data: UserLogin):
    logger.info(f"Login attempt for email: {user_data.email}")
    try:
        # Authenticate user with Supabase
        logger.info("Attempting Supabase authentication")
        auth_response = supabase.auth.sign_in_with_password({
            "email": user_data.email,
            "password": user_data.password
        })
        logger.info(f"Authentication successful for user: {user_data.email}")
        user_dict = {
            "id": auth_response.user.id,
            "email": auth_response.user.email,
            "app_metadata": auth_response.user.app_metadata,
            "user_metadata": auth_response.user.user_metadata,
            "created_at": auth_response.user.created_at,
            "updated_at": auth_response.user.updated_at,
            "role": auth_response.user.role
        }
        
        # Check if user has created any projects
        has_created_any = False
        try:
            with get_db_session() as db:
                project_count = db.query(Project).filter(
                    Project.user_id == auth_response.user.id
                ).count()
                has_created_any = project_count > 0
        except Exception as project_check_error:
            logger.warning(f"Failed to check user projects: {str(project_check_error)}")
            has_created_any = False
        
        logger.info(f"Login successful for user: {user_data.email}")
        return {
            "access_token": auth_response.session.access_token,
            "refresh_token": auth_response.session.refresh_token,
            "user": user_dict,
            "has_created_any": has_created_any
        }
        
    except Exception as e:
        logger.error(f"Login failed for user {user_data.email}: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )



class RefreshTokenRequest(BaseModel):
    refresh_token: str

@router.post("/refresh-token")
async def refresh_token(request: RefreshTokenRequest):
    logger.info("Attempting to refresh token")
    try:
        auth_response = supabase.auth.refresh_session(request.refresh_token)
        logger.info("Token refreshed successfully")
        return {
            "access_token": auth_response.session.access_token,
            "refresh_token": auth_response.session.refresh_token
        }
    except Exception as e:
        logger.error(f"Token refresh failed: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token"
        )


class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    access_token: str  # Token from the reset password URL
    refresh_token: str
    password: str  # New password
    # email: str  # Email associated with the token

@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    try:
        # Send password reset email using Supabase
        result = supabase.auth.reset_password_email(
            request.email,
            options={
                "redirect_to": f"{settings.FRONTEND_URL}/account/update-password"
            }
        )
        logger.info(f"Password reset email sent to: {request.email}")
        return {"message": "If an account exists with this email, you will receive a password reset link"}
    except Exception as e:
        logger.error(f"Error sending password reset email: {str(e)}")
        # Don't reveal if email exists or not for security
        return {"message": "If an account exists with this email, you will receive a password reset link"}

@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest):
    try:
        # Verify the token using verify_otp
        supabase.auth.set_session(request.access_token, request.refresh_token)
        # Update the password using the verified token
        update_result = supabase.auth.update_user(
            {"password": request.password},
            # {"Authorization": f"Bearer {request.access_token}"}
        )

        if "error" in update_result and update_result["error"]:
            raise HTTPException(status_code=400, detail=update_result["error"]["message"])

        logger.info("Password successfully reset")
        return {"message": "Password has been reset successfully"}

    except Exception as e:
        logger.error(f"Error in reset_password: {str(e)}")
        if "invalid token" in str(e).lower():
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired reset token"
            )
        raise HTTPException(
            status_code=400,
            detail="Password reset failed. Please try again."
        )

class ResendEmailRequest(BaseModel):
    email: str

class VerifyEmailRequest(BaseModel):
    token: str
    type: str  # "signup" or "email_change"

@router.post("/resend-verification")
async def resend_verification_email(request: ResendEmailRequest):
    """
    Resend email verification only if user exists and is not already verified
    """
    try:
        # First check user verification status
        user_status = await get_user_verification_status(request.email)
        
        if not user_status["exists"]:
            return {
                "message": "No account found with this email address",
                "status": "not_found"
            }
        
        if user_status["verified"]:
            return {
                "message": "Email is already verified. You can log in directly.",
                "status": "already_verified"
            }
        
        # User exists but not verified, send verification email
        url = f"{SUPABASE_URL}/auth/v1/resend"
        headers = {
            "apikey": SUPABASE_KEY,
            "Content-Type": "application/json"
        }
        data = {
            "type": "signup",
            "email": request.email
        }
        
        logger.info(f"Sending verification email to unverified user: {request.email}")
        
        # Make the HTTP request with timeout
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        logger.info(f"Supabase API response status: {response.status_code}")
        logger.info(f"Supabase API response: {response.text}")
        
        if response.status_code == 200:
            logger.info(f"Verification email sent successfully to: {request.email}")
            return {
                "message": "Verification email sent successfully",
                "email_sent": True
            }
        else:
            # Handle error response
            error_data = response.json() if response.content else {}
            error_message = error_data.get("message", "Unknown error")
            logger.error(f"Supabase API error: {error_message}")
            
            return {
                "message": error_message,
                "status": "error",
                "raw_error": True
            }
        
    except Exception as e:
        logger.error(f"Error generating verification email: {str(e)}")
        error_message = str(e)
        
        # Handle specific Supabase error cases with improved messages
        if "already been registered" in error_message.lower():
            return {
                "message": "Email is already verified. You can log in directly.",
                "status": "already_verified",
                "raw_error": error_message
            }
        elif "valid password" in error_message.lower():
            return {
                "message": "Invalid email address or user not found",
                "status": "not_found", 
                "raw_error": error_message
            }
        elif "not found" in error_message.lower() or "user not found" in error_message.lower():
            return {
                "message": "No account found with this email address",
                "status": "not_found",
                "raw_error": error_message
            }
        elif "rate limit" in error_message.lower() or "too many" in error_message.lower():
            return {
                "message": "Too many requests. Please wait before requesting another verification email",
                "status": "rate_limited",
                "raw_error": error_message
            }
        else:
            # Return the actual error message from Supabase with status
            return {
                "message": error_message,
                "status": "error",
                "raw_error": True
            }

@router.post("/verify-email")
async def verify_email(request: VerifyEmailRequest):
    """
    Verify user email with the token from email link
    """
    try:
        # Verify the email using Supabase verify_otp
        auth_response = supabase.auth.verify_otp({
            'token': request.token,
            'type': request.type
        })
        
        logger.info(f"Supabase verify response: {auth_response}")
        
        if not auth_response.user:
            logger.error("No user in verification response")
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired verification token"
            )
        
        logger.info(f"Email verified successfully for user: {auth_response.user.email}")
        return {
            "message": "Email verified successfully",
            "user": {
                "id": auth_response.user.id,
                "email": auth_response.user.email,
                "email_confirmed": auth_response.user.email_confirmed_at is not None
            }
        }
        
    except Exception as e:
        logger.error(f"Email verification failed: {str(e)}")
        error_message = str(e)
        
        # Handle specific Supabase error cases
        if "expired" in error_message.lower():
            raise HTTPException(
                status_code=400,
                detail="Verification token has expired"
            )
        elif "invalid" in error_message.lower():
            raise HTTPException(
                status_code=400,
                detail="Invalid verification token"
            )
        else:
            # Return the actual error message from Supabase
            raise HTTPException(
                status_code=400,
                detail=f"Email verification failed: {error_message}"
            )


@router.get("/google")
async def google_auth():
    """Redirect users to the Supabase Google sign-in page."""
    google_auth_url = f"{SUPABASE_URL}/auth/v1/authorize?provider=google&redirect_to={REDIRECT_URL}"
    return {"url": google_auth_url}

@router.get("/linkedin")
async def linkedin_auth():
    """
    Redirect users to the Supabase LinkedIn OAuth URL.
    """
    linkedin_auth_url = f"{SUPABASE_URL}/auth/v1/authorize?provider=linkedin_oidc&redirect_to={REDIRECT_URL}"
    return {"url": linkedin_auth_url}


@router.get("/me")
async def get_current_user_info(request: Request):
    logger.info("Fetching current user info")
    try:
        user = request.state.user
        return {
            "user": {
                "id": user.user.id,
                "email": user.user.email,
                "user_metadata": user.user.user_metadata
            }
        }
    except Exception as e:
        logger.error(f"Error fetching user info: {str(e)}")
        raise HTTPException(status_code=500, detail="Error fetching user information")

class UpdateUserRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    custom_metadata: Optional[dict] = None

class UpdateUserProfileRequest(BaseModel):
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    phone_number: Optional[str] = None
    phone_extension: Optional[str] = None

@router.patch("/me")
async def update_user_info(request: Request, update_data: UpdateUserRequest):
    """
    Update the current user's information in Supabase
    """
    logger.info("Updating user info")
    try:
        user = request.state.user
        
        # Prepare update data
        update_dict = update_data.model_dump(exclude_none=True)
        if not update_dict:
            raise HTTPException(status_code=400, detail="No data provided for update")
            
        # Update user metadata in Supabase
        supabase.auth.admin.update_user_by_id(
            user.user.id,
            {"user_metadata": update_dict}
        )
        
        return {
            "message": "User information updated successfully",
            "user": {
                "id": user.user.id,
                "email": user.user.email,
                "user_metadata": update_dict
            }
        }
        
    except Exception as e:
        logger.error(f"Error updating user info: {str(e)}")
        raise HTTPException(status_code=500, detail="Error updating user information")

@router.patch("/profile")
async def update_user_profile(request: Request, profile_data: UpdateUserProfileRequest):
    """
    Update specific profile fields for the current user in Supabase
    
    This endpoint allows updating:
    - full_name: User's full name
    - company_name: User's company name
    - phone_number: User's phone number
    - phone_extension: User's phone extension
    """
    logger.info("Updating user profile fields")
    try:
        user = request.state.user
        
        # Prepare update data
        update_dict = profile_data.model_dump(exclude_none=True)
        if not update_dict:
            raise HTTPException(status_code=400, detail="No data provided for update")
        
        # Get current user metadata
        try:
            current_user = supabase.auth.admin.get_user_by_id(user.user.id)
            current_metadata = current_user.user.user_metadata or {}
        except Exception as e:
            logger.error(f"Error fetching current user metadata: {str(e)}")
            current_metadata = {}
        
        # Update metadata with new values
        updated_metadata = {**current_metadata, **update_dict}
        
        # Update user metadata in Supabase
        supabase.auth.admin.update_user_by_id(
            user.user.id,
            {"user_metadata": updated_metadata}
        )
        
        return {
            "message": "User profile updated successfully",
            "user": {
                "id": user.user.id,
                "email": user.user.email,
                "user_metadata": updated_metadata
            }
        }
        
    except Exception as e:
        logger.error(f"Error updating user profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Error updating user profile information")
