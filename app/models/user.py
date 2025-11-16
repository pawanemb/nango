from pydantic import BaseModel
from typing import Dict, Any, Optional

class UserMetadata(BaseModel):
    """User metadata model"""
    pass

class AppMetadata(BaseModel):
    """App metadata model"""
    pass

class User(BaseModel):
    """User model that matches Supabase user structure"""
    id: str
    email: str
    user_metadata: Optional[Dict[str, Any]] = None
    app_metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True  # This enables ORM mode in Pydantic v2 