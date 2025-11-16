from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.sql import func
from app.db.base_class import Base

class MonitoringProjectStats(Base):
    __tablename__ = "monitoring_project_stats"
    __table_args__ = {"schema": "public"}

    project_id    = Column(UUID(as_uuid=True), primary_key=True)
    user_id       = Column(UUID(as_uuid=True), nullable=False)
    blog_1000     = Column(Integer, default=0)
    blog_1500     = Column(Integer, default=0)
    blog_2500     = Column(Integer, default=0)
    gsc_connected = Column(Integer, default=0)
    cms_connected = Column(Integer, default=0)
    # GSC performance metrics (last 30 days)
    gsc_clicks = Column(Integer, default=0)
    gsc_impressions = Column(Integer, default=0)
    gsc_ctr = Column(Float, default=0.0)  # CTR as percentage
    gsc_position = Column(Float, default=0.0)  # Average position
    project_name  = Column(String, nullable=False)
    project_url   = Column(String, nullable=False)
    updated_at    = Column(TIMESTAMP(timezone=True),
                           server_default=func.now(),
                           onupdate=func.now())