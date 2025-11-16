"""GSC schemas for API responses"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime
from uuid import UUID

class TimeFrameEnum(str, Enum):
    """Timeframe options for GSC data"""
    TODAY = "today"
    YESTERDAY = "yesterday"
    LAST_7_DAYS = "last_7_days"
    THIS_WEEK = "this_week"
    LAST_WEEK = "last_week"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    CUSTOM = "custom"

class ReportFormatEnum(str, Enum):
    """Report format options"""
    EMAIL = "email"
    PDF = "pdf"

class BreakdownTypeEnum(str, Enum):
    """Breakdown type options for GSC data"""
    COUNTRY = "country"
    DEVICE = "device"
    PAGE = "page"
    QUERY = "query"

class SortMetricEnum(str, Enum):
    """Sort metric options for GSC data"""
    CLICKS = "clicks"
    IMPRESSIONS = "impressions"
    CTR = "ctr"
    POSITION = "position"

class GSCMetricEnum(str, Enum):
    """GSC metric options"""
    CLICKS = "clicks"
    IMPRESSIONS = "impressions"
    CTR = "ctr"
    POSITION = "position"

class GSCDimensionEnum(str, Enum):
    """GSC dimension options"""
    COUNTRY = "country"
    DEVICE = "device"
    PAGE = "page"
    QUERY = "query"
    DATE = "date"

class GSCAccountBase(BaseModel):
    """Base GSC account schema"""
    project_id: UUID
    site_url: str
    credentials: Dict[str, Any]

class GSCAccountCreate(GSCAccountBase):
    """Schema for creating a GSC account"""
    pass

class GSCAccountResponse(GSCAccountBase):
    """Schema for GSC account response"""
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class GSCSite(BaseModel):
    """Schema for GSC site"""
    site_url: str
    permission_level: str
    site_type: Optional[str] = None

class GSCQueryResponse(BaseModel):
    """Schema for GSC query response"""
    rows: List[Dict[str, Any]]
    total_rows: int = Field(..., description="Total number of rows in result")
    row_limit_exceeded: bool = Field(False, description="Whether the row limit was exceeded")
