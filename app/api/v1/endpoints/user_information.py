from fastapi import APIRouter, Depends, HTTPException
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.schemas.user_information import UserInformationRequest, UserInformationResponse
from app.models.user_information import UserInformation
from app.db.session import get_db_session
from app.core.logging_config import logger
from sqlalchemy.orm import Session

router = APIRouter()

@router.post(
    "/update",
    response_model=UserInformationResponse,
    summary="Update User Information",
    description="Update user information including occupation, work experience, purpose, and how they heard about us"
)
def update_user_information(
    info_request: UserInformationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Update user information in the database.
    
    This endpoint allows users to update their personal information
    including occupation, work experience, purpose, and how they heard about the service.
    """
    try:
        logger.info(f"👤 Updating user information for user {current_user.id}")
        
        with get_db_session() as db:
            # Check if user information already exists
            existing_info = db.query(UserInformation).filter(
                UserInformation.user_id == current_user.id
            ).first()
            
            if existing_info:
                # Update existing record
                if info_request.occupation is not None:
                    existing_info.occupation = info_request.occupation
                if info_request.role is not None:
                    existing_info.role = info_request.role
                if info_request.purpose is not None:
                    existing_info.purpose = info_request.purpose
                if info_request.how_did_you_hear_about_us is not None:
                    existing_info.how_did_you_hear_about_us = info_request.how_did_you_hear_about_us
                
                db.commit()
                logger.info(f"✅ User information updated successfully for user {current_user.id}")
                
            else:
                # Create new record
                new_info = UserInformation(
                    user_id=current_user.id,
                    occupation=info_request.occupation,
                    role=info_request.role,
                    purpose=info_request.purpose,
                    how_did_you_hear_about_us=info_request.how_did_you_hear_about_us
                )
                db.add(new_info)
                db.commit()
                logger.info(f"✅ User information created successfully for user {current_user.id}")
            
            return UserInformationResponse(
                status="success",
                message="User information updated successfully",
                user_id=str(current_user.id)
            )
            
    except Exception as e:
        logger.error(f"❌ Error updating user information: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update user information: {str(e)}"
        )