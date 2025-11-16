from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import Optional, Dict, Any
import json
from datetime import datetime

class UsageService:
    """
    Service to handle usage tracking and billing
    Integrates with existing account/transaction system
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def record_usage_and_charge(
        self,
        user_id: str,
        service_name: str,
        base_cost: float,
        multiplier: float = 1.0,
        service_description: str = None,
        usage_data: Dict[Any, Any] = None,
        reference_id: str = None,
        project_id: str = None
    ) -> Dict[str, Any]:
        """
        Record service usage and charge the user's account
        
        Args:
            user_id: User ID
            service_name: Name of the service (e.g., "blog_generation")
            base_cost: Base cost of the service (e.g., 0.65)
            multiplier: Pricing multiplier (e.g., 5.0 for 5x charge)
            service_description: Description of what was done
            usage_data: Additional metadata as dict
            reference_id: External reference ID
            project_id: Project ID for usage tracking
            
        Returns:
            Dict with usage record, transaction, and account balance info
        """
        try:
            # Import models locally to avoid SQLAlchemy relationship mapping issues (matches keywords.py pattern)
            from app.models.account import Account
            from app.models.transaction import Transaction, TransactionType
            from app.models.usage import Usage
            from app.models.project import Project
            
            # Get or create account
            account = self.db.execute(
                select(Account).where(Account.user_id == user_id)
            ).scalars().first()
            
            if not account:
                account = Account(
                    user_id=user_id,
                    currency="USD",
                    credits=0.0
                )
                self.db.add(account)
                self.db.flush()
            
            # Calculate actual charge
            actual_charge = base_cost * multiplier
            
            # Check sufficient balance
            if account.credits < actual_charge:
                return {
                    "success": False,
                    "error": "insufficient_balance",
                    "message": f"Insufficient balance. Need: ${actual_charge:.2f}, Available: ${account.credits:.2f}",
                    "required_amount": actual_charge,
                    "current_balance": account.credits
                }
            
            # Create usage record
            usage = Usage(
                user_id=user_id,
                account_id=account.id,
                service_name=service_name,
                service_description=service_description,
                base_cost=base_cost,
                multiplier=multiplier,
                actual_charge=actual_charge,
                usage_data=json.dumps(usage_data) if usage_data else None,
                reference_id=reference_id,
                project_id=project_id,
                status="completed"
            )
            
            # Create debit transaction
            transaction = Transaction(
                account_id=account.id,
                amount=actual_charge,
                type=TransactionType.DEBIT,
                description=f"{service_name}: {service_description or 'Service usage'}",
                reference_id=f"usage_{usage.id}"
            )
            
            # Update account balance
            transaction.update_balance(account, actual_charge)
            
            # Link usage to transaction
            self.db.add(usage)
            self.db.add(transaction)
            self.db.flush()
            
            usage.transaction_id = transaction.id
            
            # Commit all changes
            self.db.commit()
            
            return {
                "success": True,
                "usage_id": str(usage.id),
                "transaction_id": str(transaction.id),
                "service_name": service_name,
                "base_cost": base_cost,
                "multiplier": multiplier,
                "actual_charge": actual_charge,
                "previous_balance": transaction.previous_balance,
                "new_balance": transaction.new_balance,
                "timestamp": usage.created_at.isoformat()
            }
            
        except Exception as e:
            self.db.rollback()
            return {
                "success": False,
                "error": "processing_error",
                "message": str(e)
            }
    
    def get_user_usage_history(
        self,
        user_id: str,
        service_name: str = None,
        project_id: str = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get user's usage history"""
        try:
            # Import models locally to avoid SQLAlchemy relationship mapping issues (matches keywords.py pattern)
            from app.models.usage import Usage
            from app.models.project import Project
            
            # Build base query with project join for filtering
            base_query = select(Usage, Project.name.label('project_name'), Project.url.label('project_url')).outerjoin(
                Project, Usage.project_id == Project.id
            ).where(Usage.user_id == user_id)
            
            if service_name:
                base_query = base_query.where(Usage.service_name == service_name)
            
            if project_id:
                base_query = base_query.where(Usage.project_id == project_id)
            
            # Get total count with same filters
            count_query = select(func.count(Usage.id)).where(Usage.user_id == user_id)
            
            if service_name:
                count_query = count_query.where(Usage.service_name == service_name)
            
            if project_id:
                count_query = count_query.where(Usage.project_id == project_id)
            
            total_count = self.db.execute(count_query).scalar()
            
            # Get paginated records with project info
            query = base_query.order_by(Usage.created_at.desc()).limit(limit).offset(offset)
            results = self.db.execute(query).all()
            
            return {
                "success": True,
                "usage_records": [
                    {
                        "id": str(result.Usage.id),
                        "service_name": result.Usage.service_name,
                        "service_description": result.Usage.service_description,
                        "base_cost": result.Usage.base_cost,
                        "multiplier": result.Usage.multiplier,
                        "actual_charge": result.Usage.actual_charge,
                        "status": result.Usage.status,
                        "reference_id": result.Usage.reference_id,
                        "project_id": str(result.Usage.project_id) if result.Usage.project_id else None,
                        "project_name": result.project_name,
                        "project_url": result.project_url,
                        "created_at": result.Usage.created_at.isoformat(),
                        "usage_data": json.loads(result.Usage.usage_data) if result.Usage.usage_data else None
                    }
                    for result in results
                ],
                "total_records": total_count
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": "query_error",
                "message": str(e)
            }
    
    def get_service_pricing(self) -> Dict[str, Dict[str, float]]:
        """Get current service pricing configuration"""
        return {
            "blog_generation": {
                "base_cost": 0.65,
                "multiplier": 5.0,
                "actual_cost": 3.25
            },
            "keyword_research": {
                "base_cost": 0.20,
                "multiplier": 3.0,
                "actual_cost": 0.60
            },
            "content_analysis": {
                "base_cost": 0.15,
                "multiplier": 2.0,
                "actual_cost": 0.30
            },
            "seo_audit": {
                "base_cost": 0.50,
                "multiplier": 4.0,
                "actual_cost": 2.00
            }
        }
    
    def calculate_service_cost(self, service_name: str, base_cost: float = None) -> Dict[str, float]:
        """Calculate cost for a specific service"""
        pricing = self.get_service_pricing()
        
        if service_name in pricing:
            return pricing[service_name]
        
        # Default pricing if service not found
        multiplier = 5.0  # Default 5x multiplier
        base = base_cost or 0.65  # Default base cost
        
        return {
            "base_cost": base,
            "multiplier": multiplier,
            "actual_cost": base * multiplier
        }
