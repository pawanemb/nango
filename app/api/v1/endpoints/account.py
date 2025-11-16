from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from datetime import datetime
import pytz
import logging
from pydantic import BaseModel, Field
from uuid import UUID

from app.models.account import Account
from app.models.transaction import Transaction, TransactionType
from app.db.session import get_db
from app.middleware.auth_middleware import verify_request_origin
from app.services.balance_validator import BalanceValidator

router = APIRouter()
logger = logging.getLogger(__name__)

# Define IST timezone
IST = pytz.timezone('Asia/Kolkata')

def get_ist_now():
    """Get current time in IST timezone"""
    return datetime.now(IST)

# Pydantic models for request/response validation
class AccountCreate(BaseModel):
    currency: str = "INR"
    billing_name: Optional[str] = None
    billing_email: Optional[str] = None
    billing_phone: Optional[str] = None
    billing_address: Optional[str] = None
    billing_city: Optional[str] = None
    billing_state: Optional[str] = None
    billing_country: Optional[str] = None
    billing_postal_code: Optional[str] = None

class AccountUpdate(BaseModel):
    currency: Optional[str] = None
    billing_name: Optional[str] = None
    billing_email: Optional[str] = None
    billing_phone: Optional[str] = None
    billing_address: Optional[str] = None
    billing_city: Optional[str] = None
    billing_state: Optional[str] = None
    billing_country: Optional[str] = None
    billing_postal_code: Optional[str] = None

class AccountResponse(BaseModel):
    id: str
    user_id: str
    credits: float
    currency: str
    billing_name: Optional[str] = None
    billing_email: Optional[str] = None
    billing_phone: Optional[str] = None
    billing_address: Optional[str] = None
    billing_city: Optional[str] = None
    billing_state: Optional[str] = None
    billing_country: Optional[str] = None
    billing_postal_code: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TransactionResponse(BaseModel):
    id: str
    account_id: str
    amount: float
    currency: str
    transaction_type: str
    description: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Helper function to convert model to dict with string UUIDs
def account_to_response(account: Account, db: Session = None) -> Dict[str, Any]:
    response_data = {
        "id": str(account.id),
        "user_id": str(account.user_id),
        "credits": account.credits,
        "currency": account.currency,
        "billing_name": account.billing_name,
        "billing_email": account.billing_email,
        "billing_phone": account.billing_phone,
        "billing_address": account.billing_address,
        "billing_city": account.billing_city,
        "billing_state": account.billing_state,
        "billing_country": account.billing_country,
        "billing_postal_code": account.billing_postal_code,
        "plan_status": account.plan_status,
        "created_at": account.created_at,
        "updated_at": account.updated_at
    }
    
    # Add total_paid if db session is provided
    if db:
        response_data["total_paid"] = calculate_total_paid(db, str(account.id))
    
    return response_data

def transaction_to_response(transaction: Transaction) -> Dict[str, Any]:
    return {
        "id": str(transaction.id),
        "account_id": str(transaction.account_id),
        "amount": transaction.amount,
        "currency": transaction.currency,
        "transaction_type": transaction.transaction_type,
        "description": transaction.description,
        "created_at": transaction.created_at
    }

def calculate_total_paid(db: Session, account_id: str) -> float:
    """Calculate total amount paid by user from payment transactions"""
    try:
        # Import models locally to avoid SQLAlchemy relationship mapping issues
        from app.models.transaction import Transaction, TransactionType
        
        # Get all CREDIT transactions that are actual payments (not manual credits)
        # This includes Razorpay payments, plan upgrades, and wallet top-ups
        payment_transactions = db.execute(
            select(Transaction)
            .where(
                Transaction.account_id == account_id,
                Transaction.type == TransactionType.CREDIT,
                Transaction.description.like('%payment%')
            )
        ).scalars().all()
        
        # Also include transactions with reference_id (payment references)
        reference_transactions = db.execute(
            select(Transaction)
            .where(
                Transaction.account_id == account_id,
                Transaction.type == TransactionType.CREDIT,
                Transaction.reference_id.isnot(None),
                ~Transaction.description.like('%manual%')
            )
        ).scalars().all()
        
        # Combine and deduplicate transactions
        all_payment_transactions = list(payment_transactions) + list(reference_transactions)
        unique_transactions = {t.id: t for t in all_payment_transactions}
        
        total_paid = sum(transaction.amount for transaction in unique_transactions.values())
        return round(total_paid, 2)  # Round to 2 decimal places
        
    except Exception as e:
        logger.error(f"Error calculating total paid: {str(e)}")
        return 0.0

@router.get("/me", response_model=AccountResponse)
def get_account(
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """Get the current user's account"""
    user_id = current_user.id
    
    account = db.execute(
        select(Account).where(Account.user_id == user_id)
    ).scalars().first()
    
    if not account:
        # Create account if it doesn't exist (wallet system)
        logger.info(f"Creating new account for user_id: {user_id}")
        account = Account(
            user_id=user_id,
            currency="USD",  # Default to USD for wallet system
            credits=0.0  # Initialize with zero credits
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        logger.info(f"Created account {account.id} for user {user_id}")
    
    return account_to_response(account, db)

@router.get("/balance")
def get_balance(
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """Get the current user's wallet balance with plan details"""
    user_id = current_user.id
    
    account = db.execute(
        select(Account).where(Account.user_id == user_id)
    ).scalars().first()
    
    if not account:
        # Create account if it doesn't exist (wallet system)
        logger.info(f"Creating new account for user_id: {user_id}")
        account = Account(
            user_id=user_id,
            currency="USD",  # Default to USD for wallet system
            credits=0.0  # Initialize with zero credits
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        logger.info(f"Created account {account.id} for user {user_id}")
    
    # Use database plan_status if available, otherwise calculate dynamically
    plan_status = account.plan_status if account.plan_status else "inactive"
    days_left = None
    expiring_within_7_days = False
    
    if account.plan_end_date:
        # Calculate days left regardless of plan_status
        current_time = get_ist_now()
        
        if account.plan_end_date > current_time:
            time_diff = account.plan_end_date - current_time
            days_left = time_diff.days
            # Check if expiring within 7 days
            expiring_within_7_days = days_left <= 7
            # If no database status, use calculated status
            if not account.plan_status:
                plan_status = "active"
        else:
            time_diff = current_time - account.plan_end_date
            days_left = -time_diff.days  # Negative number indicates expired days
            expiring_within_7_days = False  # Already expired
            # If no database status, use calculated status
            if not account.plan_status:
                plan_status = "expired"
    
    # Calculate total amount paid by user
    total_paid = calculate_total_paid(db, str(account.id))
    
    return {
        "success": True,
        "balance": account.credits,
        "currency": account.currency,
        "total_paid": total_paid,
        "plan_type": account.plan_type,
        "plan_duration": account.plan_duration,
        "plan_start_date": account.plan_start_date,
        "plan_end_date": account.plan_end_date,
        "plan_status": plan_status,
        "days_left": days_left,
        "expiring_within_7_days": expiring_within_7_days
    }

@router.post("/", response_model=AccountResponse)
def create_account(
    account_data: AccountCreate,
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """Create a new account for the current user"""
    user_id = current_user.id
    
    # Check if account already exists
    existing_account = db.execute(
        select(Account).where(Account.user_id == user_id)
    ).scalars().first()
    
    if existing_account:
        raise HTTPException(status_code=400, detail="Account already exists for this user")
    
    # Create new account
    account = Account(
        user_id=user_id,
        currency=account_data.currency,
        billing_name=account_data.billing_name,
        billing_email=account_data.billing_email,
        billing_phone=account_data.billing_phone,
        billing_address=account_data.billing_address,
        billing_city=account_data.billing_city,
        billing_state=account_data.billing_state,
        billing_country=account_data.billing_country,
        billing_postal_code=account_data.billing_postal_code,
        credits=0.0  # Initialize with zero credits
    )
    
    db.add(account)
    db.commit()
    db.refresh(account)
    
    return account_to_response(account, db)

@router.put("/", response_model=AccountResponse)
def update_account(
    account_data: AccountUpdate,
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """Update the current user's account"""
    user_id = current_user.id
    
    account = db.execute(
        select(Account).where(Account.user_id == user_id)
    ).scalars().first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Update account fields if provided
    if account_data.currency is not None:
        account.currency = account_data.currency
    if account_data.billing_name is not None:
        account.billing_name = account_data.billing_name
    if account_data.billing_email is not None:
        account.billing_email = account_data.billing_email
    if account_data.billing_phone is not None:
        account.billing_phone = account_data.billing_phone
    if account_data.billing_address is not None:
        account.billing_address = account_data.billing_address
    if account_data.billing_city is not None:
        account.billing_city = account_data.billing_city
    if account_data.billing_state is not None:
        account.billing_state = account_data.billing_state
    if account_data.billing_country is not None:
        account.billing_country = account_data.billing_country
    if account_data.billing_postal_code is not None:
        account.billing_postal_code = account_data.billing_postal_code
    
    account.updated_at = get_ist_now()
    
    db.commit()
    db.refresh(account)
    
    return account_to_response(account, db)

@router.get("/transactions", response_model=List[TransactionResponse])
def get_transactions(
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    """Get the current user's transactions"""
    user_id = current_user.id
    
    # Get user's account
    account = db.execute(
        select(Account).where(Account.user_id == user_id)
    ).scalars().first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Get transactions for this account
    transactions = db.execute(
        select(Transaction)
        .where(Transaction.account_id == account.id)
        .order_by(Transaction.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).scalars().all()
    
    return [transaction_to_response(t) for t in transactions]

@router.post("/add-credits", response_model=AccountResponse)
def add_credits(
    amount: float = Query(..., gt=0),
    description: str = Query(...),
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """Add credits to the current user's account (admin only)"""
    user_id = current_user.id
    
    # Check if user is admin (implement your admin check logic here)
    # For now, we'll assume only admins can call this endpoint
    # You should implement proper authorization checks
    
    # Get user's account
    account = db.execute(
        select(Account).where(Account.user_id == user_id)
    ).scalars().first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Add credits to account
    account.credits += amount
    account.updated_at = get_ist_now()
    
    # Create transaction record
    transaction = Transaction(
        account_id=account.id,
        amount=amount,
        currency=account.currency,
        transaction_type=TransactionType.CREDIT,
        description=description,
        metadata={
            "added_by": str(user_id),
            "added_at": get_ist_now().isoformat(),
            "method": "manual"
        }
    )
    
    db.add(transaction)
    db.commit()
    db.refresh(account)
    
    return account_to_response(account, db)

@router.get("/check-permissions")
def check_permissions(
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """Check if user has permission based on credit balance (>= 5 credits)"""
    user_id = str(current_user.id)
    
    # Initialize balance validator
    validator = BalanceValidator(db)
    
    # Check permissions
    result = validator.check_permissions(user_id)
    
    return result
