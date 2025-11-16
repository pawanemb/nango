from sqlalchemy.orm import Session
from sqlalchemy import select
from app.config.service_validation import get_service_requirement, get_min_balance
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class BalanceValidator:
    """
    Fast service balance validation
    Checks if user has sufficient balance before hitting main endpoints
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def validate_service_balance(self, user_id: str, service_key: str) -> Dict[str, Any]:
        """
        Fast balance validation for a service
        
        Args:
            user_id: User ID
            service_key: Service key from SERVICE_REQUIREMENTS
            
        Returns:
            Dict with validation result
        """
        try:
            # Import models locally to avoid SQLAlchemy relationship mapping issues (matches keywords.py pattern)
            from app.models.account import Account
            
            # Get service requirements
            service_req = get_service_requirement(service_key)
            if not service_req:
                return {
                    "valid": False,
                    "error": "invalid_service",
                    "message": f"Service '{service_key}' not found"
                }
            
            # Get user account
            account = self.db.execute(
                select(Account).where(Account.user_id == user_id)
            ).scalars().first()
            
            if not account:
                return {
                    "valid": False,
                    "error": "account_not_found",
                    "message": "User account not found"
                }
            
            # Check balance
            min_balance = service_req["min_balance"]
            current_balance = account.credits
            next_refill_time = account.next_refill_time
            
            if current_balance < min_balance:
                return {
                    "valid": False,
                    "error": "insufficient_balance",
                    "message": f"Insufficient balance for {service_req['description']}",
                    "required_balance": min_balance,
                    "current_balance": current_balance,
                    "shortfall": min_balance - current_balance,
                    "next_refill_time": next_refill_time
                }
            
            # Validation passed
            return {
                "valid": True,
                "service_name": service_req["service_name"],
                "description": service_req["description"],
                "current_balance": current_balance,
                "required_balance": min_balance
            }
            
        except Exception as e:
            logger.error(f"Balance validation error: {str(e)}")
            return {
                "valid": False,
                "error": "validation_error",
                "message": f"Validation failed: {str(e)}"
            }
    
    def check_permissions(self, user_id: str) -> Dict[str, Any]:
        """
        Check if user has permission based on credit balance
        Permission granted if credits >= 5, denied if < 5
        
        Args:
            user_id: User ID
            
        Returns:
            Dict with permission status and next_refill_time
        """
        try:
            # Import models locally to avoid SQLAlchemy relationship mapping issues
            from app.models.account import Account
            
            # Get user account
            account = self.db.execute(
                select(Account).where(Account.user_id == user_id)
            ).scalars().first()
            
            if not account:
                return {
                    "permission": False,
                    "message": "User account not found",
                    "next_refill_time": None
                }
            
            current_balance = account.credits
            has_permission = current_balance >= 5.0
            
            return {
                "permission": has_permission,
                "current_balance": current_balance,
                "next_refill_time": account.next_refill_time
            }
            
        except Exception as e:
            logger.error(f"Permission check error: {str(e)}")
            return {
                "permission": False,
                "message": f"Permission check failed: {str(e)}",
                "next_refill_time": None
            }

    def get_user_balance(self, user_id: str) -> float:
        """Get user's current balance quickly"""
        try:
            # Import models locally to avoid SQLAlchemy relationship mapping issues (matches keywords.py pattern)
            from app.models.account import Account
            
            account = self.db.execute(
                select(Account).where(Account.user_id == user_id)
            ).scalars().first()
            return account.credits if account else 0.0
        except Exception:
            return 0.0
