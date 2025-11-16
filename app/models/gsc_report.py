from sqlalchemy import Column, String, DateTime, Boolean, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base_class import Base
import uuid
from enum import Enum


class GSCReportStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"


class GSCReport(Base):
    __tablename__ = "gsc_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    project_id = Column(UUID(as_uuid=True), nullable=False, index=True)  # Temporarily removed ForeignKey
    site_url = Column(String, nullable=False)
    
    # Timeframe details
    timeframe = Column(String, nullable=False)  # today, yesterday, this_week, custom, etc.
    start_date = Column(Date, nullable=False)   # Actual start date used
    end_date = Column(Date, nullable=False)     # Actual end date used
    
    # Report delivery method - tracks how report was generated/delivered
    sent_by_email = Column(Boolean, default=False, nullable=False)
    sent_by_download = Column(Boolean, default=False, nullable=False)
    email_address = Column(String, nullable=True)  # Only populated if sent by email
    
    # Status tracking
    status = Column(String, default=GSCReportStatus.PENDING, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)  # When report was completed

    def __repr__(self):
        return f"<GSCReport {self.id}: {self.site_url} ({self.timeframe}) - Email: {self.sent_by_email}, Download: {self.sent_by_download}>"
    
    def mark_email_sent(self, email: str):
        """Mark report as sent by email"""
        self.sent_by_email = True
        self.email_address = email
        self.status = GSCReportStatus.COMPLETED
        self.completed_at = func.now()
    
    def mark_download_completed(self):
        """Mark report as downloaded"""
        self.sent_by_download = True
        self.status = GSCReportStatus.COMPLETED
        self.completed_at = func.now()
    
    def mark_failed(self):
        """Mark report generation as failed"""
        self.status = GSCReportStatus.FAILED
        self.completed_at = func.now() 