from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import uuid

class ProjectImage(Base):
    __tablename__ = "project_images"
    __table_args__ = (
        Index('idx_project_images_project_id', 'project_id'),
        Index('idx_project_images_created_at', 'created_at'),
        Index('idx_project_images_user_id', 'user_id'),
        {"schema": "public"}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), nullable=False)  # Temporarily removed FK constraint
    user_id = Column(UUID(as_uuid=True), nullable=False)    # Temporarily removed FK constraint
    
    # File information
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String, nullable=False)
    
    # Supabase Storage information
    storage_path = Column(String, nullable=False)  # project_id/filename
    bucket_name = Column(String, nullable=False, default='images')
    public_url = Column(String, nullable=False)  # Direct access URL
    
    # Image metadata
    image_metadata = Column(JSONB, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    
    # Organization (simplified)
    category = Column(String, nullable=True)  # 'logo', 'banner', 'content', etc.
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships - temporarily removed due to FK constraint issues
    # project = relationship("Project", back_populates="images")
    # user = relationship("AuthUser")  # Who uploaded it

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'project_id': str(self.project_id),
            'user_id': str(self.user_id),
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'url': self.public_url,
            'width': self.width,
            'height': self.height,
            'category': self.category,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'image_metadata': self.image_metadata
        }

    def __repr__(self):
        return f"<ProjectImage {self.filename} for Project {self.project_id}>"
