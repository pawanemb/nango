from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
from uuid import UUID


class GSCReportBase(BaseModel):
    project_id: UUID
    site_url: str
    timeframe: str
    start_date: date
    end_date: date


class GSCReportCreate(GSCReportBase):
    """Schema for creating a new GSC report record"""
    pass


class GSCReportResponse(GSCReportBase):
    """Schema for GSC report response"""
    id: UUID
    sent_by_email: bool
    sent_by_download: bool
    email_address: Optional[str] = None
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GSCReportList(BaseModel):
    """Schema for listing GSC reports"""
    reports: list[GSCReportResponse]
    total: int

    class Config:
        from_attributes = True 