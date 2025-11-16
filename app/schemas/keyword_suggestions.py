from typing import List, Optional
from pydantic import BaseModel, Field
from uuid import UUID

class KeywordMetrics(BaseModel):
    search_volume: int = Field(..., alias="searchVolume")
    difficulty: float
    intent: str
    cpc: float
    competition: float

class KeywordSuggestion(BaseModel):
    keyword: str
    metrics: Optional[KeywordMetrics] = None

class KeywordSuggestionsRequest(BaseModel):
    country: str = Field(default="in", description="Country code for keyword metrics (e.g., 'us', 'uk', 'in')")

class KeywordSuggestionsResponse(BaseModel):
    suggestions: List[KeywordSuggestion]
    status: str = "success"

class BatchKeywordMetricsRequest(BaseModel):
    keywords: List[str]
    country: str = "us"

class BatchKeywordMetricsResponse(BaseModel):
    keywords: List[KeywordSuggestion]
    status: str = "success"
