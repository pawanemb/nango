"""
Minimal schemas for outline customization endpoints
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class CustomSourceRequest(BaseModel):
    """Schema for adding custom sources to subsections"""
    type: str = Field(..., description="Source type: text, url, or pdf")
    content: str = Field(..., description="Source content or text")
    title: Optional[str] = Field(None, description="Custom title for the source")
    url: Optional[str] = Field(None, description="URL if type is url")

class SearchResult(BaseModel):
    """Schema for search result"""
    id: Optional[str] = Field(None, description="Search result ID")
    title: str = Field(..., description="Result title")
    url: str = Field(..., description="Result URL")
    snippet: Optional[str] = Field(None, description="Result snippet")
    knowledge: Optional[Dict[str, Any]] = Field(None, description="Extracted knowledge")
    citation: Optional[str] = Field(None, description="Citation information")
    traffic_data: Optional[Dict[str, Any]] = Field(None, description="URL traffic analysis data")
    is_selected: bool = Field(default=False, description="Whether result is selected")
    ranking: int = Field(default=0, description="Search ranking")
    processed_at: Optional[datetime] = Field(None, description="When the result was processed")

class SubsectionDataPoint(BaseModel):
    """Schema for subsection data point"""
    id: Optional[str] = Field(None, description="Data point ID")
    title: str = Field(..., description="Subsection title")
    search_results: List[SearchResult] = Field(default=[], description="Associated search results")
    data_type: str = Field(default="generated", description="Type of data")
    is_processed: bool = Field(default=False, description="Whether processed")

class CustomSubsection(BaseModel):
    """Schema for custom subsection"""
    id: Optional[str] = Field(None, description="Subsection ID")
    title: str = Field(..., description="Subsection title")
    data_point: SubsectionDataPoint = Field(..., description="Associated data point")
    order: int = Field(default=1, description="Subsection order")

class CustomHeading(BaseModel):
    """Schema for custom heading"""
    id: Optional[str] = Field(None, description="Heading ID")
    title: str = Field(..., description="Heading title")
    subsections: List[CustomSubsection] = Field(default=[], description="List of subsections")
    order: int = Field(default=1, description="Heading order")

class CustomizableOutline(BaseModel):
    """Schema for customizable outline"""
    blog_id: str = Field(..., description="Blog ID")
    headings: List[CustomHeading] = Field(default=[], description="List of heading objects")
    conclusion: Optional[str] = Field(None, description="Conclusion")
    faqs: List[str] = Field(default=[], description="FAQ questions")
    status: Optional[str] = Field("draft", description="Outline status")
    created_at: Optional[datetime] = Field(None)
    updated_at: Optional[datetime] = Field(None)

class DataCollectionResponse(BaseModel):
    """Schema for data collection response"""
    blog_id: str = Field(..., description="Blog/outline ID")
    status: str = Field(..., description="Response status")
    message: str = Field(..., description="Response message")
    outline: CustomizableOutline = Field(..., description="Updated outline")
    total_search_results: int = Field(..., description="Total search results collected")
    processed_results: int = Field(..., description="Number of processed results")
    next_step: str = Field(..., description="Next step instructions")
    is_user_first_time: Optional[bool] = Field(None, description="First time user flag")

# REMOVED: SearchResultsCollectionRequest - no longer needed for streaming sources
# The streaming endpoint now uses simple dict payload instead

# Update forward references for circular dependencies
CustomHeading.model_rebuild()
CustomSubsection.model_rebuild()
CustomizableOutline.model_rebuild()