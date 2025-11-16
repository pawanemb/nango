from pydantic import BaseModel
from typing import Optional

class UserInformationRequest(BaseModel):
    occupation: Optional[str] = None
    role: Optional[str] = None
    purpose: Optional[str] = None
    how_did_you_hear_about_us: Optional[str] = None

class UserInformationResponse(BaseModel):
    status: str
    message: str
    user_id: str