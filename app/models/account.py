from sqlalchemy import Column, String, Float, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import uuid

class Account(Base):
    """
    Model to store user accounts
    """
    __tablename__ = "accounts"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('auth.users.id', ondelete='CASCADE'), nullable=False)
    credits = Column(Float, default=0.0)
    currency = Column(String, default="INR")
    billing_name = Column(String, nullable=True)
    billing_email = Column(String, nullable=True)
    billing_phone = Column(String, nullable=True)
    billing_address = Column(String, nullable=True)
    billing_city = Column(String, nullable=True)
    billing_state = Column(String, nullable=True)
    billing_country = Column(String, nullable=True)
    billing_postal_code = Column(String, nullable=True)
    billing_tax_number = Column(String, nullable=True)
    next_refill_time = Column(DateTime(timezone=True), nullable=True)
    plan_type = Column(String(20), default="free", nullable=True)
    plan_duration = Column(String(20), nullable=True)
    plan_start_date = Column(DateTime(timezone=True), nullable=True)
    plan_end_date = Column(DateTime(timezone=True), nullable=True)
    plan_status = Column(String(20), default="active", nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("AuthUser", foreign_keys=[user_id])
    # Commented out to fix SQLAlchemy initialization error
    # razorpay_payments = relationship("RazorpayPayment", back_populates="account")
    # transactions = relationship("Transaction", back_populates="account")
    # invoices = relationship("Invoice", back_populates="account")
    # usage_records = relationship("Usage", back_populates="account")
