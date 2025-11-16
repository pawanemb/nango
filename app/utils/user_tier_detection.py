"""
User Tier Detection Utility
Simple utility to detect if a user is on FREE or PRO tier
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.account import Account

logger = logging.getLogger(__name__)

def get_user_tier(db: Session, user_id: str) -> str:
    """
    Detect user tier based on their account plan_type
    
    Args:
        db: Database session
        user_id: User ID to check tier for
        
    Returns:
        str: Either "free" or "pro"
    """
    try:
        # Query user's account to get plan_type
        account = db.query(Account).filter(Account.user_id == user_id).first()
        
        if not account:
            logger.warning(f"No account found for user_id: {user_id}, defaulting to free tier")
            return "free"
        
        plan_type = account.plan_type or "free"
        
        # Normalize plan type - anything that's not "free" is considered "pro"
        if plan_type.lower() == "free":
            logger.info(f"User {user_id} is on FREE tier")
            return "free"
        else:
            logger.info(f"User {user_id} is on PRO tier (plan_type: {plan_type})")
            return "pro"
            
    except Exception as e:
        logger.error(f"Error detecting user tier for user_id {user_id}: {str(e)}")
        # Default to free tier on error for safety
        return "free"

def is_user_pro(db: Session, user_id: str) -> bool:
    """
    Check if user is on PRO tier
    
    Args:
        db: Database session
        user_id: User ID to check
        
    Returns:
        bool: True if user is PRO, False if FREE
    """
    return get_user_tier(db, user_id) == "pro"

def is_user_free(db: Session, user_id: str) -> bool:
    """
    Check if user is on FREE tier
    
    Args:
        db: Database session
        user_id: User ID to check
        
    Returns:
        bool: True if user is FREE, False if PRO
    """
    return get_user_tier(db, user_id) == "free"