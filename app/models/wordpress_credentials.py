from sqlalchemy import Column, String, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from app.models.project import Project
import uuid

class WordPressCredentials(Base):
    __tablename__ = "wordpress_credentials"
    __table_args__ = (
        Index('idx_wordpress_credentials_project_id', 'project_id'),  # Index for foreign key lookups
        Index('idx_wordpress_credentials_created_at', 'created_at'),  # Index for timestamp sorting
        {"schema": "public"}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True), 
        ForeignKey('public.projects.id', ondelete='CASCADE'),
        nullable=False,
        unique=True  # One WordPress credential per project
    )
    base_url = Column(String, nullable=False)
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)  # Should be encrypted in production
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())

    # Relationship with Project
    project = relationship(
        "Project",
        back_populates="wordpress_credentials",
        uselist=False
    )

    def __repr__(self):
        return f"<WordPressCredentials(project_id={self.project_id}, base_url={self.base_url})>"
