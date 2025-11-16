from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


class ScrapedContent(BaseModel):
    """Model for storing scraped HTML content in MongoDB"""
    project_id: UUID = Field(..., description="UUID of the associated project")
    url: str = Field(..., description="URL of the scraped page")
    html_content: str = Field(..., description="Raw HTML content of the page")
    scraped_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of when the page was scraped")
    status: str = Field(default="pending", description="Status of the scraping (pending, completed, failed, ai_processed)")
    error_message: Optional[str] = Field(None, description="Error message if scraping failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata about the scraping")
    services: Optional[List[str]] = Field(default=None, description="List of services offered")
    business_category: Optional[str] = Field(None, description="E-Commerce, SaaS, or Others")
    demographics: Optional[Dict[str, List[str]]] = Field(default=None, description="Demographic analysis results containing age, industry, gender, languages, and countries")
    ai_analysis_meta: Optional[Dict[str, Any]] = Field(None, description="For storing model, tokens_used etc.")

    class Config:
        json_schema_extra = {
            "example": {
                "project_id": "123e4567-e89b-12d3-a456-426614174000",
                "url": "https://example.com",
                "html_content": "<html>...</html>",
                "scraped_at": "2025-01-20T00:33:23+05:30",
                "status": "completed",
                "error_message": None,
                "metadata": {
                    "content_length": 1234,
                    "http_status": 200,
                    "content_type": "text/html"
                },
                "services": ["Web Development", "Digital Marketing"],
                "business_category": "SaaS",
                "demographics": {
                    "Age": ["Young Adults (18-24 years old)", "Adults (25-49 years old)"],
                    "Industry": ["Technology", "Marketing & Advertising"],
                    "Gender": ["Male", "Female"],
                    "Language(s) Spoken": ["English", "Hindi"],
                    "Country": ["United States", "India"]
                },
                "ai_analysis_meta": {
                    "model": "gpt-4-turbo-preview",
                    "tokens_used": 1234
                }
            }
        }
