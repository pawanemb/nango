from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, HttpUrl, UUID4, Field, validator
from enum import Enum
from app.models.enums import GenderEnum

class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Name of the project")
    url: str = Field(..., description="URL of the project")
    industries: List[str] = Field(default=[], description="List of industries")
    services: List[str] = Field(default=[], description="List of services")
    languages: List[str] = Field(default=[], description="List of languages supported")
    age_groups: List[str] = Field(default=[], description="List of target age groups")
    locations: List[str] = Field(default=[], description="List of target locations")
    business_type: Optional[str] = Field(None, description="Business type of the project")

    @validator('url')
    def validate_url(cls, v):
        # Basic URL validation - can be enhanced
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

class ProjectCreate(ProjectBase):
    pass

class UpdateServicesRequest(BaseModel):
    """Request schema for updating project services"""
    services: List[str] = Field(..., description="List of services to update")
    business_type: Optional[str] = Field(None, description="Business type of the project")

class UpdateTargetAudienceRequest(BaseModel):
    """Request schema for updating project target audience"""
    gender: GenderEnum = Field(..., description="Target gender (Male, Female, or All)")
    languages: List[str] = Field(..., description="List of target languages")
    age_groups: List[str] = Field(..., description="List of target age groups")
    locations: List[str] = Field(..., description="List of target locations")
    industries: List[str] = Field(..., description="List of target industries")

class UpdateFeatureImageActiveRequest(BaseModel):
    """Request schema for updating feature image active status"""
    feature_image_active: bool = Field(..., description="Feature image active status (true/false)")

class TogglePinnedRequest(BaseModel):
    """Request schema for toggling pinned status"""
    pinned: bool = Field(..., description="Pinned status (true/false)")

class ProjectResponse(BaseModel):
    id: UUID
    name: str
    url: str
    industries: List[str] = []
    services: List[str] = []
    created_at: datetime
    user_id: UUID
    cms_config: Optional[Dict[str, Any]] = None
    brand_tone_settings: Optional[Dict[str, Any]] = None
    brand_name: Optional[str] = None
    visitors: int = 0
    updated_at: Optional[datetime] = None
    background_image: Optional[str] = None
    gender: GenderEnum = GenderEnum.ALL
    languages: List[str] = []
    age_groups: List[str] = []
    locations: List[str] = []
    business_type: Optional[str] = None
    featured_image_style: Optional[str] = None
    person_tone: Optional[str] = Field(default=None, description="Person tone for content generation")
    feature_image_active: bool = True
    pinned: bool = False
    internal_linking_enabled: bool = True
    is_active: bool = True
    # Response-specific fields
    task_id: Optional[str] = None
    message: Optional[str] = None
    new_access_token: Optional[str] = None
    new_refresh_token: Optional[str] = None

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    id: UUID
    name: str
    url: str
    industries: List[str] = []
    services: List[str] = []
    created_at: datetime
    user_id: UUID
    cms_config: Optional[Dict[str, Any]] = None
    brand_tone_settings: Optional[Dict[str, Any]] = None
    brand_name: Optional[str] = None
    visitors: int = 0
    updated_at: Optional[datetime] = None
    background_image: Optional[str] = None
    gender: GenderEnum = GenderEnum.ALL
    languages: List[str] = []
    age_groups: List[str] = []
    locations: List[str] = []
    business_type: Optional[str] = None
    featured_image_style: Optional[str] = None
    person_tone: Optional[str] = Field(default=None, description="Person tone for content generation")
    feature_image_active: bool = True
    pinned: bool = False
    internal_linking_enabled: bool = True
    is_active: bool = True

    class Config:
        from_attributes = True

class ProjectList(BaseModel):
    total: int
    items: List[ProjectResponse]

    class Config:
        from_attributes = True

class ProjectInDB(BaseModel):
    id: UUID4
    name: str
    url: str
    industries: List[str] = []
    services: List[str] = []
    created_at: datetime
    user_id: UUID4
    cms_config: Optional[dict] = None
    brand_tone_settings: Optional[dict] = None
    brand_name: Optional[str] = None
    visitors: int = 0
    updated_at: Optional[datetime] = None
    background_image: Optional[str] = None
    gender: GenderEnum = GenderEnum.ALL
    languages: List[str] = []
    age_groups: List[str] = []
    locations: List[str] = []
    business_type: Optional[str] = None

    class Config:
        from_attributes = True

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    # url: Optional[str] = None
    industries: Optional[List[str]] = None
    services: Optional[List[str]] = None
    brand_tone_settings: Optional[Dict[str, Any]] = None
    brand_name: Optional[str] = None
    # background_image: Optional[str] = None
    # cms_config: Optional[Dict[str, Any]] = None
    gender: Optional[GenderEnum] = None
    languages: Optional[List[str]] = None
    age_groups: Optional[List[str]] = None
    locations: Optional[List[str]] = None
    business_type: Optional[str] = None
    featured_image_style: Optional[str] = None
    person_tone: Optional[str] = None
    feature_image_active: Optional[bool] = None
    internal_linking_enabled: Optional[bool] = None

class ProjectUpdateResponse(BaseModel):
    """Response schema for project update endpoint"""
    id: UUID
    name: str
    url: str
    industries: List[str] = Field(default=[], description="List of industries")
    services: List[str] = Field(default=[], description="List of services")
    brand_tone_settings: Optional[Dict[str, Any]] = None
    brand_name: Optional[str] = None
    visitors: int = 0
    business_type: Optional[str] = None
    gender: GenderEnum = GenderEnum.ALL
    languages: List[str] = Field(default=[], description="List of languages supported")
    age_groups: List[str] = Field(default=[], description="List of target age groups")
    locations: List[str] = Field(default=[], description="List of target locations")
    featured_image_style: Optional[str] = None
    person_tone: Optional[str] = Field(default=None, description="Person tone for content generation")
    feature_image_active: bool = True
    pinned: bool = False
    internal_linking_enabled: bool = True
    is_active: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None
    user_id: UUID
    message: str = Field(default="Project updated successfully")

    class Config:
        from_attributes = True
