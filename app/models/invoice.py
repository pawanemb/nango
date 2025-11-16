from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Integer, Enum as SQLAlchemyEnum, Text, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import uuid
from enum import Enum as PyEnum
from typing import List, Optional

class InvoiceStatus(PyEnum):
    DRAFT = 'draft'
    SENT = 'sent'
    PAID = 'paid'
    OVERDUE = 'overdue'
    CANCELLED = 'cancelled'
    PARTIALLY_PAID = 'partially_paid'

class Invoice(Base):
    """
    Model to store invoices
    """
    __tablename__ = "invoices"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_number = Column(String, nullable=False, unique=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey('public.accounts.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('auth.users.id', ondelete='CASCADE'), nullable=False)
    
    # Invoice details
    status = Column(String, nullable=False, default=InvoiceStatus.PAID.value)
    issue_date = Column(DateTime(timezone=True), nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=False)
    amount_due = Column(Float, nullable=False, default=0.0)
    amount_paid = Column(Float, nullable=False, default=0.0)
    currency = Column(String, nullable=False, default="INR")
    
    # Client information
    client_name = Column(String, nullable=False)
    client_email = Column(String, nullable=True)
    client_phone = Column(String, nullable=True)
    client_address = Column(String, nullable=True)
    client_city = Column(String, nullable=True)
    client_state = Column(String, nullable=True)
    client_country = Column(String, nullable=True)
    client_postal_code = Column(String, nullable=True)
    
    # Additional fields
    notes = Column(Text, nullable=True)
    terms = Column(Text, nullable=True)
    payment_instructions = Column(Text, nullable=True)
    tax_rate = Column(Float, nullable=True)
    tax_amount = Column(Float, nullable=True)
    discount_rate = Column(Float, nullable=True)
    discount_amount = Column(Float, nullable=True)
    subtotal = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    
    # Payment tracking
    payment_method = Column(String, nullable=True)
    payment_date = Column(DateTime(timezone=True), nullable=True)
    payment_reference = Column(String, nullable=True)
    razorpay_payment_id = Column(UUID(as_uuid=True), ForeignKey('public.razorpay_payments.id', ondelete='SET NULL'), nullable=True)
    
    # Metadata
    invoice_metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    # Commented out to fix SQLAlchemy initialization error
    # account = relationship("Account", back_populates="invoices")
    user = relationship("AuthUser", foreign_keys=[user_id])
    invoice_items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    # razorpay_payment = relationship("RazorpayPayment", foreign_keys=[razorpay_payment_id])


class InvoiceItem(Base):
    """
    Model to store invoice line items
    """
    __tablename__ = "invoice_items"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey('public.invoices.id', ondelete='CASCADE'), nullable=False)
    
    # Item details
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    quantity = Column(Float, nullable=False, default=1.0)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    
    # Optional fields
    tax_rate = Column(Float, nullable=True)
    tax_amount = Column(Float, nullable=True)
    discount_rate = Column(Float, nullable=True)
    discount_amount = Column(Float, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    invoice = relationship("Invoice", back_populates="invoice_items")
