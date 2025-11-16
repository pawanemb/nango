from enum import Enum
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
from sqlalchemy import Column, String, JSON, ForeignKey, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import uuid

class GSCMetric(str, Enum):
    """Google Search Console metrics"""
    CLICKS = "clicks"
    IMPRESSIONS = "impressions"
    CTR = "ctr"
    POSITION = "position"

class GSCDimension(str, Enum):
    COUNTRY = "country"
    DEVICE = "device"
    PAGE = "page"
    QUERY = "query"
    SEARCH_APPEARANCE = "searchAppearance"
    DATE = "date"

class GSCQueryResponse(BaseModel):
    clicks: int
    impressions: int
    ctr: float
    position: float

class GSCSite(BaseModel):
    siteUrl: str
    permissionLevel: str

# SQLAlchemy Model
class GSCAccount(Base):
    __tablename__ = "gsc_accounts"
    __table_args__ = (
        Index('idx_gsc_accounts_project_id', 'project_id'),  # Index for foreign key lookups
        Index('idx_gsc_accounts_created_at', 'created_at'),  # Index for timestamp sorting
        Index('idx_gsc_accounts_site_url', 'site_url'),  # Index for site URL lookups
        {"schema": "public"}  # Schema needs to be the last item in the tuple
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True), 
        ForeignKey('public.projects.id', ondelete='CASCADE'),
        nullable=False
    )
    site_url = Column(String, nullable=False)
    credentials = Column(JSON, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())

    # Remove circular import by using string reference
    project = relationship(
        "Project",
        back_populates="gsc_accounts"
    )

    def __repr__(self):
        return f"<GSCAccount {self.site_url}>"

# Pydantic Models for API
class GSCAccountCreate(BaseModel):
    site_url: str
    credentials: Dict

class GSCAccountResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    site_url: str
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
