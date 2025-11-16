from sqlalchemy import Column, String, Integer, ARRAY, JSON, DateTime, ForeignKey, Index, Enum, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from app.models.auth import AuthUser
from app.models.enums import GenderEnum
import uuid

class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        Index('idx_projects_user_id', 'user_id'),  # Index for foreign key lookups
        Index('idx_projects_created_at', 'created_at'),  # Index for timestamp sorting
        Index('idx_projects_updated_at', 'updated_at'),  # Index for timestamp sorting
        Index('idx_projects_name', 'name'),  # Index for name searches
        Index('idx_projects_url', 'url'),  # Index for URL lookups
        {"schema": "public"}  # Schema needs to be the last item in the tuple
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    industries = Column(ARRAY(String), nullable=True, default=[])
    services = Column(ARRAY(String), nullable=True, default=[])
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    user_id = Column(
        UUID(as_uuid=True), 
        ForeignKey('auth.users.id', ondelete='CASCADE'),
        nullable=False
    )
    cms_config = Column(JSONB, nullable=True)
    brand_name = Column(String)
    visitors = Column(Integer, default=0)
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())
    background_image = Column(String)
    business_type = Column(String, nullable=True)  # Added business_type field

    # New fields for targeting
    gender = Column(Enum(GenderEnum, name='gender_enum'), nullable=False, default=GenderEnum.ALL)
    languages = Column(ARRAY(String), nullable=False, server_default='{}', default=[])
    age_groups = Column(ARRAY(String), nullable=False, server_default='{}', default=[])
    locations = Column(ARRAY(String), nullable=False, server_default='{}', default=[])
    is_active = Column(Boolean, default=True, nullable=False)
    brand_tone_settings = Column(JSONB, nullable=True, default=None)  # Brand tone configuration
    person_tone = Column(String, nullable=True, default=None)  # Person tone for content generation
    featured_image_style = Column(String, nullable=True, default=None)  # Featured image style
    feature_image_active = Column(Boolean, nullable=False, default=True)  # Feature image active status
    internal_linking_enabled = Column(Boolean, nullable=False, default=True)  # Internal linking for blogs
    pinned = Column(Boolean, nullable=False, default=False)  # Pinned status for projects
    # Relationships
    user = relationship(
        AuthUser,
        primaryjoin="Project.user_id == foreign(AuthUser.id)",
        lazy='joined'
    )

    # Relationship to Keywords - using string reference
    keywords = relationship("Keywords", back_populates="project")

    # GSC accounts relationship - using string reference
    gsc_accounts = relationship(
        "GSCAccount",
        back_populates="project",
        cascade="all, delete-orphan"
    )

    # WordPress credentials relationship - using string reference
    wordpress_credentials = relationship(
        "WordPressCredentials",
        back_populates="project",
        uselist=False,  # One-to-one relationship
        cascade="all, delete-orphan"
    )
    # Project Images relationship - temporarily removed due to FK constraint issues
    # images = relationship(
    #     "ProjectImage",
    #     back_populates="project",
    #     cascade="all, delete-orphan"
    # )
    
    # Razorpay relationship removed as payments are now global and not tied to projects

    def to_dict(self):
        """
        Convert SQLAlchemy model instance to a dictionary.
        
        Returns:
            dict: Dictionary representation of the Project
        """
        return {
            'id': str(self.id),
            'name': self.name,
            'url': self.url,
            'industries': self.industries,
            'services': self.services,
            'user_id': str(self.user_id),
            'cms_config': self.cms_config,
            'brand_name': self.brand_name,
            'visitors': self.visitors,
            'business_type': self.business_type,
            'gender': self.gender.value if self.gender else None,
            'languages': self.languages,
            'age_groups': self.age_groups,
            'locations': self.locations,
            'person_tone': self.person_tone,
            'featured_image_style': self.featured_image_style,
            'feature_image_active': self.feature_image_active,
            'internal_linking_enabled': self.internal_linking_enabled,
            'pinned': self.pinned,
            'created_at': str(self.created_at) if self.created_at else None,
            'updated_at': str(self.updated_at) if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Project {self.name}>"
