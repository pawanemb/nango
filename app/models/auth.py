from sqlalchemy import Table, Column, MetaData
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base_class import Base

# class AuthUser(Base):
#     __table__ = Table(
#         'users',
#         MetaData(schema='auth'),
#         Column('id', UUID(as_uuid=True), primary_key=True),
#         extend_existing=True
#     )

#     # Simple viewonly relationship
#     projects = relationship(
#         "Project",
#         primaryjoin="AuthUser.id == foreign(Project.user_id)",
#         viewonly=True
#     )

#     def __repr__(self):
#         return f"<AuthUser {self.id}>"

class AuthUser(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}  # Define schema explicitly

    id = Column(UUID(as_uuid=True), primary_key=True)

    # Relationship to Project
    projects = relationship(
        "Project",
        primaryjoin="AuthUser.id == foreign(Project.user_id)",
        viewonly=True
    )
    
    # Relationship to RazorpayPayment (using string reference to avoid import issues)
    # Temporarily commented out to fix SQLAlchemy initialization issues
    # razorpay_payments = relationship(
    #     "RazorpayPayment",
    #     primaryjoin="AuthUser.id == RazorpayPayment.user_id",
    #     viewonly=True,
    #     foreign_keys="[RazorpayPayment.user_id]"
    # )
    
    def __repr__(self):
        return f"<AuthUser {self.id}>"