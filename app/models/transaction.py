from sqlalchemy import Column, Float, ForeignKey, String, Enum, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import uuid
from enum import Enum as PyEnum

class TransactionType(PyEnum):
    CREDIT = 'credit'
    DEBIT = 'debit'

class Transaction(Base):
    """
    Model to track account transactions
    """
    __tablename__ = "transactions"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey('public.accounts.id', ondelete='CASCADE'), nullable=False)
    amount = Column(Float, nullable=False)
    # currency = Column(String, nullable=True, default="INR")
    previous_balance = Column(Float, nullable=False)
    new_balance = Column(Float, nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    description = Column(String, nullable=True)
    reference_id = Column(String, nullable=True)  # For linking to external systems
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    # Commented out to fix SQLAlchemy initialization error
    # account = relationship("Account", back_populates="transactions")
    # usage_record = relationship("Usage", back_populates="transaction", lazy="select")

    def update_balance(self, account, credits):
        self.previous_balance = account.credits
        if self.type == TransactionType.CREDIT:
            account.credits += credits
        else:
            account.credits -= credits
        self.new_balance = account.credits
