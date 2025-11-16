from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.sql import func
from app.db.base_class import Base

class ShopifyCredentials(Base):
    """Shopify credentials for project integration"""
    
    __tablename__ = "shopify_credentials"
    
    project_id = Column(String, primary_key=True, index=True)
    shop_domain = Column(String, nullable=False)  # e.g., "mystore.myshopify.com"
    access_token = Column(Text, nullable=False)   # Private app access token
    api_version = Column(String, default="2024-01", nullable=False)  # Shopify API version
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
