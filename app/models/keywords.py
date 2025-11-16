from sqlalchemy import Column, String, Boolean, ForeignKey, Index, Integer, Float
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import uuid

class Keywords(Base):
    __tablename__ = "keywords"
    __table_args__ = (
        Index('idx_keywords_project_id', 'project_id'),  # Index for foreign key lookups
        Index('idx_keywords_created_at', 'created_at'),  # Index for timestamp sorting
        Index('idx_keywords_name', 'name'),  # Index for name searches
        {"schema": "public"}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey('public.projects.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    last_updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    search_volume = Column(Integer, default=0, nullable=False)
    difficulty = Column(Integer, default=0, nullable=False)
    intent = Column(String, default='Unknown', nullable=False)
    cpc = Column(Float, default=0.0, nullable=False)
    competition = Column(Float, default=0.0, nullable=False)
    country = Column(String, default='in', nullable=True)

    # Relationship to Project using string reference
    project = relationship(
        "Project",
        back_populates="keywords"
    )

    def __repr__(self):
        return f"<Keywords {self.name}>"
