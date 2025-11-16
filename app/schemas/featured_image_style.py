from pydantic import BaseModel, Field
from typing import Optional

class StoreFeaturedImageStyleRequest(BaseModel):
    """Request model for storing featured image style"""
    style: str = Field(..., description="The featured image style to store", min_length=1, max_length=100)

class StoreFeaturedImageStyleResponse(BaseModel):
    """Response model for storing featured image style"""
    status: str = Field(default="success", description="Response status")
    message: str = Field(default="Featured image style stored successfully", description="Response message")
    project_id: str = Field(..., description="Project ID")
    featured_image_style: str = Field(..., description="Stored featured image style")

class FetchFeaturedImageStyleResponse(BaseModel):
    """Response model for fetching featured image style"""
    status: str = Field(default="success", description="Response status")
    message: str = Field(default="Featured image style retrieved successfully", description="Response message")
    project_id: str = Field(..., description="Project ID")
    featured_image_style: Optional[str] = Field(None, description="Featured image style (null if not set)")

class FeaturedImageStyleOptionsResponse(BaseModel):
    """Response model for getting available featured image style options"""
    status: str = Field(default="success", description="Response status")
    message: str = Field(default="Featured image style options retrieved successfully", description="Response message")
    style_options: list = Field(..., description="Available featured image style options")
