from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, JSON, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import uuid

class RazorpayPayment(Base):
    """
    Model to store Razorpay payment records
    """
    __tablename__ = "razorpay_payments"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey('public.accounts.id', ondelete='CASCADE'), nullable=True)  # Nullable for backward compatibility
    user_id = Column(UUID(as_uuid=True), ForeignKey('auth.users.id', ondelete='CASCADE'), nullable=False)
    razorpay_order_id = Column(String, nullable=True)
    razorpay_payment_id = Column(String, nullable=True)
    razorpay_signature = Column(String, nullable=True)
    amount = Column(Integer, nullable=False)  # Amount in smallest currency unit (paise for INR)
    currency = Column(String, nullable=False, default="INR")
    status = Column(String, nullable=False)  # created, authorized, captured, refunded, failed
    description = Column(String, nullable=True)
    payment_metadata = Column('metadata', JSONB, nullable=True)  # For storing additional data like receipt, notes, etc.
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())

    # Relationships
    # Commented out to fix SQLAlchemy initialization error
    # account = relationship("Account", foreign_keys=[account_id], back_populates="razorpay_payments")
    user = relationship("AuthUser", foreign_keys=[user_id])
