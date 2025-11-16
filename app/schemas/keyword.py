from typing import List, Optional
from pydantic import BaseModel, UUID4, Field, validator
from uuid import UUID
from datetime import datetime

class KeywordSearchRequest(BaseModel):
    keyword: str
    country: str = "us"
    blog_id: Optional[str] = None

class KeywordMetrics(BaseModel):
    keyword: str
    intent: str
    search_volume: int
    keyword_difficulty: float

class KeywordSearchResponse(BaseModel):
    primary_keyword: Optional[KeywordMetrics] = None
    status: str
    country: str  # Changed from 'database' to 'country'
    error: Optional[str] = None
    blog_id: Optional[str] = None  # ✅ MongoDB blog document ID

class LatestKeywordResponse(BaseModel):
    primary_keyword: Optional[KeywordMetrics] = None
    status: str
    country: str
    error: Optional[str] = None
    blog_id: str

class KeywordCreate(BaseModel):
    name: str
    search_volume: int
    difficulty: int
    intent: str
    cpc: float
    competition: float
    country: str

class KeywordBulkCreate(BaseModel):
    keywords: List[KeywordCreate]

class KeywordBulkDelete(BaseModel):
    keyword_ids: List[UUID4]

class KeywordResponse(BaseModel):
    id: UUID4
    name: str
    search_volume: int
    difficulty: int
    intent: str
    cpc: float
    competition: float
    country: str
    project_id: UUID4
    created_at: datetime
    active: bool

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }
