"""
SQLAlchemy models for blog-related database operations
Matches existing database table structure
"""

from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import uuid

class BlogHeading(Base):
    """SQLAlchemy model for blog headings - matches existing table structure"""
    __tablename__ = "blog_headings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    blog_id = Column(String, nullable=False, index=True)  # Reference to blog/outline
    title = Column(String, nullable=False)  # Changed from 'text' to 'title' to match existing table
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship to search results
    search_results = relationship("BlogSearchResult", back_populates="heading", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BlogHeading(id={self.id}, title='{self.title[:30]}...')>"

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": str(self.id),
            "blog_id": self.blog_id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class BlogSearchResult(Base):
    """SQLAlchemy model for blog search results - matches existing table structure"""
    __tablename__ = "blog_search_results"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    heading_id = Column(UUID(as_uuid=True), ForeignKey("blog_headings.id", ondelete="CASCADE"), nullable=False)
    
    # Subsection and categorization (NOT NULL in existing table)
    subsection_title = Column(String, nullable=False, index=True)
    
    # Search result data
    url = Column(String, nullable=False)
    title = Column(String, nullable=False)
    snippet = Column(Text)
    knowledge = Column(Text)  # Full content/knowledge extracted
    citation = Column(Text)
    
    # Search metadata
    traffic_data = Column(JSONB)
    is_selected = Column(Boolean)
    search_rank = Column(Integer, nullable=False, default=0)
    
    # Processing status
    processed_at = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship back to heading
    heading = relationship("BlogHeading", back_populates="search_results")

    def __repr__(self):
        return f"<BlogSearchResult(id={self.id}, title='{self.title[:30]}...')>"

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": str(self.id),
            "heading_id": str(self.heading_id),
            "subsection_title": self.subsection_title,
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "knowledge": self.knowledge,
            "citation": self.citation,
            "traffic_data": self.traffic_data,
            "is_selected": self.is_selected,
            "search_rank": self.search_rank,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
