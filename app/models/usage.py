from sqlalchemy import Column, Float, ForeignKey, String, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import uuid

class Usage(Base):
    """
    Model to track service usage and billing
    Records what services users consume and how much they're charged
    """
    __tablename__ = "usage"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('auth.users.id', ondelete='CASCADE'), nullable=False)
    account_id = Column(UUID(as_uuid=True), nullable=False)  # Account ID without foreign key constraint
    
    # Service details
    service_name = Column(String, nullable=False)  # e.g., "blog_generation", "keyword_research"
    service_description = Column(String, nullable=True)  # e.g., "Generated blog: How to SEO"
    
    # Pricing details
    base_cost = Column(Float, nullable=False)  # Base service cost (e.g., 0.65)
    multiplier = Column(Float, nullable=False, default=1.0)  # Pricing multiplier (e.g., 5.0 for 5x)
    actual_charge = Column(Float, nullable=False)  # Amount actually charged (base_cost * multiplier)
    
    # Usage metadata
    usage_data = Column(String, nullable=True)  # JSON string for additional data
    status = Column(String, nullable=False, default="completed")  # completed, failed, refunded
    
    # Linking
    transaction_id = Column(UUID(as_uuid=True), ForeignKey('public.transactions.id'), nullable=True)
    reference_id = Column(String, nullable=True)  # External reference (e.g., blog_id, task_id)
    project_id = Column(UUID(as_uuid=True), nullable=True)  # Project ID for usage tracking
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    # account = relationship("Account", back_populates="usage_records")
    # transaction = relationship("Transaction", back_populates="usage_record")
    
    def calculate_charge(self):
        """Calculate the actual charge based on base cost and multiplier"""
        self.actual_charge = self.base_cost * self.multiplier
        return self.actual_charge
    
    def __repr__(self):
        return f"<Usage(service='{self.service_name}', charge=${self.actual_charge:.2f}, user='{self.user_id}')>"
