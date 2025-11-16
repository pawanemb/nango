from pydantic import BaseModel, Field
from typing import Optional

class BrandToneAnalysisRequest(BaseModel):
    """Request model for brand tone analysis"""
    paragraph: str = Field(..., description="The paragraph text to analyze for brand tone", min_length=10, max_length=5000)

class BrandToneResponse(BaseModel):
    """Response model for brand tone analysis"""
    formality: str = Field(..., description="Formality spectrum result")
    attitude: str = Field(..., description="Attitude spectrum result")
    energy: str = Field(..., description="Energy spectrum result")
    clarity: str = Field(..., description="Clarity spectrum result")
    person_tone: Optional[str] = Field(None, description="Person tone for content generation")

class BrandToneAnalysisResponse(BaseModel):
    """Complete response for brand tone analysis"""
    status: str = Field(default="success", description="Response status")
    message: str = Field(default="Brand tone analysis completed successfully", description="Response message")
    tone_analysis: BrandToneResponse = Field(..., description="Brand tone analysis results")

class StoreBrandToneRequest(BaseModel):
    """Request model for storing brand tone settings"""
    formality: str = Field(..., description="Selected formality tone")
    attitude: str = Field(..., description="Selected attitude tone")
    energy: str = Field(..., description="Selected energy tone")
    clarity: str = Field(..., description="Selected clarity tone")
    person_tone: Optional[str] = Field(default="First person", description="The person tone for content generation")

class StoreBrandToneResponse(BaseModel):
    """Response model for storing brand tone settings"""
    status: str = Field(default="success", description="Response status")
    message: str = Field(default="Brand tone settings stored successfully", description="Response message")
    project_id: str = Field(..., description="Project ID")
    brand_tone_settings: BrandToneResponse = Field(..., description="Stored brand tone settings")

class FetchBrandToneResponse(BaseModel):
    """Response model for fetching brand tone settings"""
    status: str = Field(default="success", description="Response status")
    message: str = Field(default="Brand tone settings retrieved successfully", description="Response message")
    project_id: str = Field(..., description="Project ID")
    brand_tone_settings: Optional[BrandToneResponse] = Field(None, description="Brand tone settings (null if not set)")
