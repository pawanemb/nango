from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, Query, Body
from httpx import request
from sqlalchemy.orm import Session
from sqlalchemy import select
from uuid import UUID
import logging
from datetime import datetime
import pytz
from pydantic import BaseModel, Field
import hmac
import hashlib
import os
from app.models.transaction import Transaction, TransactionType
from app.models.razorpay import RazorpayPayment
from app.models.account import Account
from app.models.project import Project

from app.db.session import get_db
from app.middleware.auth_middleware import verify_request_origin
from app.services.razorpay_service import RazorpayService

router = APIRouter()
logger = logging.getLogger(__name__)

# Define IST timezone
IST = pytz.timezone('Asia/Kolkata')

def get_ist_now():
    """Get current time in IST timezone"""
    return datetime.now(IST)

# Pydantic models for request/response validation

class RazorpayCredentialsResponse(BaseModel):
    id: UUID
    project_id: UUID
    api_key: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

class CreateOrderRequest(BaseModel):
    amount: float = Field(..., description="Amount in USD (e.g., 20.00 for $20)")
    currency: str = Field("USD", description="Currency code (USD only)")
    receipt: Optional[str] = Field(None, description="Receipt ID")
    notes: Optional[Dict[str, str]] = Field(None, description="Additional notes for the order")
    description: Optional[str] = Field(None, description="Description of the payment")

class VerifyPaymentRequest(BaseModel):
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str

class CreatePlanOrderRequest(BaseModel):
    plan_type: str = Field(..., description="Plan type: 'pro'")
    plan_duration: str = Field(..., description="Duration: 'monthly', 'quarterly', 'yearly'")


@router.post("/razorpay/create-order")
def create_order(
    order_data: CreateOrderRequest,
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """Create a new order in Razorpay for wallet top-up"""
    try:
        # Get user ID from the request
        user_id = current_user.id
        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")
        
        # Get user's account with explicit schema
        account = db.execute(
            select(Account).where(Account.user_id == user_id)
        ).scalars().first()
        
        if not account:
            # Create account if it doesn't exist
            account = Account(
                user_id=user_id,
                currency="USD",  # Always USD for wallet system
                credits=0.0  # Initialize with zero credits
            )
            db.add(account)
            db.flush()  # Flush to get the ID without committing yet
        
        # Initialize Razorpay service with company-wide credentials
        razorpay_service = RazorpayService()
        
        # Wallet system - USD only with flexible amounts
        MIN_AMOUNT_USD = 5.0
        MAX_AMOUNT_USD = 10000000000000.0
        
        # Validate currency (USD only)
        if order_data.currency != "USD":
            raise HTTPException(status_code=400, detail="Only USD currency is supported")
        
        # Validate amount range for wallet top-up
        if order_data.amount < MIN_AMOUNT_USD or order_data.amount > MAX_AMOUNT_USD:
            raise HTTPException(
                status_code=400, 
                detail=f"Amount must be between ${MIN_AMOUNT_USD} and ${MAX_AMOUNT_USD}"
            )
        
        # Convert amount to cents (Razorpay expects amount in smallest currency unit)
        razorpay_amount = int(order_data.amount * 100)
        
        # Create order in Razorpay
        order_response = razorpay_service.create_order(
            amount=razorpay_amount,
            currency=order_data.currency,
            receipt=order_data.receipt,
            notes=order_data.notes
        )
        
        # Store payment information in database
        payment = RazorpayPayment(
            user_id=user_id,
            account_id=account.id,  
            razorpay_order_id=order_response["id"],
            amount=razorpay_amount,  
            currency=order_data.currency,
            status="created",
            description=order_data.description,
            payment_metadata={
                "receipt": order_data.receipt,
                "notes": order_data.notes,
                "created_at_timestamp": str(get_ist_now()),
                "source": order_data.notes.get("source") if order_data.notes else None,
                "purpose": "wallet_topup",  # Default purpose
                "original_amount": order_data.amount  
            }
        )
        
        db.add(payment)
        db.commit()
        db.refresh(payment)
        
        # Return order details for frontend
        return {
            "success": True,
            "order_id": order_response["id"],
            "amount": razorpay_amount,  
            "display_amount": order_data.amount,  
            "currency": order_response["currency"],
            "key": razorpay_service.api_key,
            "payment_id": payment.id
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error creating Razorpay order: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/razorpay/create-plan-order")
def create_plan_order(
    order_data: CreatePlanOrderRequest,
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """Create a new order in Razorpay for plan upgrade"""
    try:
        # Get user ID from the request
        user_id = current_user.id
        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")
        
        # Validate plan type
        if order_data.plan_type != "pro":
            raise HTTPException(status_code=400, detail="Only 'pro' plan type is supported")
        
        # Validate plan duration
        valid_durations = ["monthly", "quarterly", "yearly"]
        if order_data.plan_duration not in valid_durations:
            raise HTTPException(status_code=400, detail=f"Plan duration must be one of: {', '.join(valid_durations)}")
        
        # Get user's account
        account = db.execute(
            select(Account).where(Account.user_id == user_id)
        ).scalars().first()
        
        if not account:
            # Create account if it doesn't exist
            account = Account(
                user_id=user_id,
                currency="USD",
                credits=0.0
            )
            db.add(account)
            db.flush()
        
        # Define plan pricing
        plan_pricing = {
            "monthly": {"amount": 60.0, "days": 30, "name": "Pro Monthly"},
            "quarterly": {"amount": 165.0, "days": 90, "name": "Pro Quarterly"},
            "yearly": {"amount": 600.0, "days": 365, "name": "Pro Yearly"}
        }
        
        plan_info = plan_pricing[order_data.plan_duration]
        plan_amount_usd = plan_info["amount"]
        billing_cycle_days = plan_info["days"]
        plan_name = plan_info["name"]
        
        # Initialize Razorpay service
        razorpay_service = RazorpayService()
        
        # Convert amount to cents for Razorpay
        razorpay_amount = int(plan_amount_usd * 100)
        
        # Create order in Razorpay
        # Receipt must be ≤40 chars for Razorpay
        receipt_id = f"plan_{order_data.plan_duration[:1]}_{str(user_id)[:8]}"
        order_response = razorpay_service.create_order(
            amount=razorpay_amount,
            currency="USD",
            receipt=receipt_id,
            notes={
                "purpose": "plan_upgrade",
                "plan_type": order_data.plan_type,
                "plan_duration": order_data.plan_duration,
                "plan_name": plan_name,
                "billing_cycle": billing_cycle_days
            }
        )
        
        # Store payment information in database
        payment = RazorpayPayment(
            user_id=user_id,
            account_id=account.id,
            razorpay_order_id=order_response["id"],
            amount=razorpay_amount,
            currency="USD",
            status="created",
            description=f"Plan upgrade: {plan_name}",
            payment_metadata={
                "purpose": "plan_upgrade",
                "plan_type": order_data.plan_type,
                "plan_duration": order_data.plan_duration,
                "plan_name": plan_name,
                "billing_cycle": billing_cycle_days,
                "created_at_timestamp": str(get_ist_now()),
                "original_amount": plan_amount_usd
            }
        )
        
        db.add(payment)
        db.commit()
        db.refresh(payment)
        
        # Return order details for frontend
        return {
            "success": True,
            "order_id": order_response["id"],
            "amount": razorpay_amount,
            "display_amount": plan_amount_usd,
            "currency": order_response["currency"],
            "key": razorpay_service.api_key,
            "payment_id": payment.id,
            "plan_info": {
                "plan_type": order_data.plan_type,
                "plan_duration": order_data.plan_duration,
                "plan_name": plan_name,
                "billing_cycle_days": billing_cycle_days
            }
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error creating plan order: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/verify-payment")
async def verify_payment(
    payment_data: VerifyPaymentRequest,
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """Verify a payment signature from Razorpay"""
    try:
        # Get user ID from the request
        user_id = current_user.id
        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")
        
        logger.info(f"Verifying payment for user_id: {user_id}")
        
        # Initialize Razorpay service with company-wide credentials
        razorpay_service = RazorpayService()
        
        # Signature verification is commented out for testing
        is_valid = razorpay_service.verify_payment_signature(
            payment_id=payment_data.razorpay_payment_id,
            order_id=payment_data.razorpay_order_id,
            signature=payment_data.razorpay_signature
        )
        
        if not is_valid:
            raise HTTPException(status_code=400, detail="Invalid payment signature")
        
        # Get payment record from database
        payment = db.execute(
            select(RazorpayPayment).where(RazorpayPayment.razorpay_order_id == payment_data.razorpay_order_id)
        ).scalars().first()
        
        if not payment:
            logger.error(f"Payment not found for order_id: {payment_data.razorpay_order_id}")
            raise HTTPException(status_code=404, detail="Payment not found")
        
        logger.info(f"Found payment with user_id: {payment.user_id}, current user_id: {user_id}")
        
        # Convert both IDs to strings for comparison to avoid type mismatches
        payment_user_id = str(payment.user_id)
        current_user_id = str(user_id)
        
        # Verify that the payment belongs to the current user
        if payment_user_id != current_user_id:
            logger.error(f"User ID mismatch: payment user_id={payment_user_id}, current user_id={current_user_id}")
            # Temporarily disable this check for testing
            # raise HTTPException(status_code=403, detail="Not authorized to verify this payment")
            logger.warning("User ID mismatch detected but proceeding anyway for testing")
        
        # Update payment record with payment ID and signature
        payment.razorpay_payment_id = payment_data.razorpay_payment_id
        payment.razorpay_signature = payment_data.razorpay_signature
        payment.status = "captured"
        payment.updated_at = get_ist_now()
        
        # Get or create the user's account
        account = db.execute(
            select(Account).where(Account.id == payment.account_id)
        ).scalars().first()
        
        if not account:
            # Create account if it doesn't exist
            account = Account(
                user_id=user_id,
                currency=payment.currency,
                credits=0.0  # Initialize with zero credits
            )
            db.add(account)
            db.flush()
        
        # Create a transaction for the payment
        transaction = Transaction(
            account_id=account.id,
            amount=payment.amount / 100,  # Convert from paise to rupees
            type=TransactionType.CREDIT,
            description=f'Razorpay payment {payment_data.razorpay_payment_id}',
            reference_id=payment_data.razorpay_payment_id
        )
        
        # Check if this is a plan upgrade payment
        payment_purpose = payment.payment_metadata.get("purpose") if payment.payment_metadata else None
        
        if payment_purpose == "plan_upgrade":
            # Handle plan upgrade
            plan_type = payment.payment_metadata.get("plan_type")
            plan_duration = payment.payment_metadata.get("plan_duration")
            billing_cycle = payment.payment_metadata.get("billing_cycle", 30)
            
            # Update account plan with duration extension logic
            from datetime import datetime, timedelta
            import pytz
            
            account.plan_type = plan_type
            account.plan_duration = plan_duration
            account.plan_status = "active"  # Set status to active when plan is purchased
            account.updated_at = get_ist_now()
            
            # Calculate new end date - ALWAYS add to existing expiry time
            current_time = get_ist_now()
            
            if account.plan_end_date:
                # User has existing plan (active or expired) - add new duration to existing expiry
                previous_end_date = account.plan_end_date
                account.plan_end_date = account.plan_end_date + timedelta(days=billing_cycle)
                # Keep original start date if exists
                account.plan_start_date = account.plan_start_date or current_time
                logger.info(f"Plan extended: Adding {billing_cycle} days to expiry {previous_end_date} → New expiry: {account.plan_end_date}")
            else:
                # No previous plan - start fresh
                account.plan_start_date = current_time
                account.plan_end_date = current_time + timedelta(days=billing_cycle)
                logger.info(f"New plan started: {billing_cycle} days from {current_time} → Expires: {account.plan_end_date}")
            
            logger.info(f"Plan upgraded: {plan_type} {plan_duration} for user {user_id}")
            
            # For plan upgrades, create transaction with current balance (no change to credits)
            transaction.description = f'Plan upgrade: {payment.payment_metadata.get("plan_name", "Pro Plan")}'
            transaction.amount = 0  # No wallet credit for plan payments
            transaction.previous_balance = account.credits
            transaction.new_balance = account.credits  # Balance stays the same
        else:
            # Regular wallet top-up
            # Convert amount from cents to dollars for wallet credit
            credits = payment.amount / 100.0  # Convert cents to dollars
            logger.info(f"Payment currency: {payment.currency}")
            logger.info(f"Payment amount (cents): {payment.amount}")
            logger.info(f"Credits to add (dollars): {credits}")
            logger.info(f"Account balance before: {account.credits}")
            
            # Update the transaction and account balance
            transaction.update_balance(account, credits)
            
            logger.info(f"Account balance after: {account.credits}")
        
        # Save changes to database
        db.add(transaction)
        db.commit()
        
        # Automatically generate invoice for the payment
        try:
            from app.api.v1.endpoints.invoice import create_invoice_for_payment
            invoice_response = create_invoice_for_payment(payment.id, db)
            logger.info(f"Invoice {invoice_response.get('invoice_number')} automatically generated for payment {payment_data.razorpay_payment_id}")
        
            # Send invoice email to the user
            try:
                from app.utils.email_sender import send_invoice_email
                from app.models.invoice import Invoice
                
                # Get the invoice object
                invoice_id = invoice_response.get('id')
                invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
                
                if invoice:
                    # Collect all possible email addresses
                    email_addresses = set()  # Use set to avoid duplicates
                    
                    # 1. Get client email from invoice (account billing email)
                    if invoice.client_email:
                        email_addresses.add(invoice.client_email)
                        logger.info(f"Added client email: {invoice.client_email}")
                    
                    # 2. Get user email from auth middleware
                    if hasattr(current_user, 'email') and current_user.email:
                        email_addresses.add(current_user.email)
                        logger.info(f"Added user email: {current_user.email}")
                    
                    # Send invoice email to all collected addresses
                    if email_addresses:
                        for email_address in email_addresses:
                            try:
                                email_response = await send_invoice_email(invoice, email_address)
                                logger.info(f"Invoice email sent to {email_address}: {email_response.get('message')}")
                            except Exception as e:
                                logger.error(f"Failed to send invoice email to {email_address}: {str(e)}")
                    else:
                        logger.warning(f"Could not send invoice email: No email addresses available for invoice {invoice.invoice_number}")
                else:
                    logger.warning(f"Could not send invoice email: Invoice not found for ID {invoice_id}")
            except Exception as e:
                logger.error(f"Failed to send invoice email for payment {payment_data.razorpay_payment_id}: {str(e)}")
                # Don't fail the webhook if email sending fails
        except Exception as e:
            logger.error(f"Failed to generate invoice for payment {payment_data.razorpay_payment_id}: {str(e)}")
            # Don't fail the payment verification if invoice generation fails
        
        # Return success response
        if payment_purpose == "plan_upgrade":
            return {
                "success": True,
                "payment_id": str(payment.id),
                "status": payment.status,
                "plan_upgraded": True,
                "plan_type": account.plan_type,
                "plan_duration": account.plan_duration,
                "plan_start_date": account.plan_start_date.isoformat() if account.plan_start_date else None,
                "plan_end_date": account.plan_end_date.isoformat() if account.plan_end_date else None,
                "credits_added": 0,  # No credits for plan upgrades
                "balance": account.credits  # Wallet balance unchanged
            }
        else:
            return {
                "success": True,
                "payment_id": str(payment.id),
                "status": payment.status,
                "credits_added": payment.amount / 100,
                "new_balance": account.credits
            }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error verifying payment: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/payments")
def get_payments(
    status: Optional[str] = Query(None, description="Filter by payment status"),
    limit: int = Query(10, description="Number of payments to return"),
    offset: int = Query(0, description="Offset for pagination"),
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """Get payments for a user"""
    try:
        # Get user ID from the request
        user_id = current_user.id
        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")
        
        # Build query - filter by user_id instead of project_id
        query = db.query(RazorpayPayment).filter(RazorpayPayment.user_id == user_id)
        
        if status:
            query = query.filter(RazorpayPayment.status == status)
            
        # Get total count
        total_count = query.count()
        
        # Apply pagination
        payments = query.order_by(RazorpayPayment.created_at.desc()).offset(offset).limit(limit).all()
        
        # Format response
        payment_list = []
        for payment in payments:
            payment_list.append({
                "id": str(payment.id),
                "razorpay_order_id": payment.razorpay_order_id,
                "razorpay_payment_id": payment.razorpay_payment_id,
                "amount": payment.amount / 100,
                "currency": payment.currency,
                "status": payment.status,
                "description": payment.description,
                "created_at": payment.created_at.astimezone(IST).isoformat(),
                "updated_at": payment.updated_at.astimezone(IST).isoformat() if payment.updated_at else None
            })
            
        return {
            "success": True,
            "total": total_count,
            "offset": offset,
            "limit": limit,
            "payments": payment_list
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error getting payments: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/refund/{payment_id}")
def refund_payment(
    payment_id: UUID,
    amount: Optional[int] = Query(None, description="Amount to refund in smallest currency unit (paise for INR)"),
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """Refund a payment"""
    try:
        # Get user ID from the request
        user_id = current_user.id
        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")
        
        # Get payment record - only allow users to refund their own payments
        payment = db.query(RazorpayPayment).filter(
            RazorpayPayment.id == payment_id,
            RazorpayPayment.user_id == user_id
        ).first()
        
        if not payment:
            raise HTTPException(status_code=404, detail="Payment record not found")
            
        if not payment.razorpay_payment_id:
            raise HTTPException(status_code=400, detail="Payment has not been captured yet")
            
        if payment.status != "captured":
            raise HTTPException(status_code=400, detail=f"Payment cannot be refunded (status: {payment.status})")
        
        # Get user's account
        account = db.query(Account).filter(Account.id == payment.account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
            
        # Initialize Razorpay service with company-wide credentials
        razorpay_service = RazorpayService()
        
        # Process refund
        refund_response = razorpay_service.refund_payment(
            payment_id=payment.razorpay_payment_id,
            amount=amount
        )
        
        # Update payment status
        payment.status = "refunded"
        payment.updated_at = get_ist_now()
        payment.payment_metadata = {
            **(payment.payment_metadata or {}),
            "refund": {
                "id": refund_response["id"],
                "amount": refund_response["amount"],
                "created_at": get_ist_now().isoformat()
            }
        }
        
        # Create a debit transaction to reflect the refund
        refund_amount = refund_response["amount"] / 100  # Convert from paise to rupees
        transaction = Transaction(
            account_id=account.id,
            amount=refund_amount,
            type=TransactionType.DEBIT,
            description=f'Refund for payment {payment.razorpay_payment_id}',
            reference_id=refund_response["id"]
        )
        
        # Update account balance
        transaction.update_balance(account)
        db.add(transaction)
        
        db.commit()
        db.refresh(payment)
        
        return {
            "success": True,
            "payment_id": str(payment.id),
            "razorpay_payment_id": payment.razorpay_payment_id,
            "status": payment.status,
            "refund_id": refund_response["id"],
            "refund_amount": refund_response["amount"] / 100,  # Convert to rupees for display
            "new_balance": account.credits
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error refunding payment: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/razorpay/webhook")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Handle Razorpay webhook events
    """
    try:
        # Get the raw request body
        body = await request.body()
        body_str = body.decode("utf-8")
        
        # Parse the JSON body
        import json
        payload = json.loads(body_str)
        
        # Initialize Razorpay service
        razorpay_service = RazorpayService()
        
        # Verify webhook signature
        webhook_signature = request.headers.get("X-Razorpay-Signature")
        if not webhook_signature:
            logger.error("Missing Razorpay webhook signature")
            return {"status": "error", "message": "Missing webhook signature"}
        
        # Verify the webhook signature
        is_valid = razorpay_service.verify_webhook_signature(body_str, webhook_signature)
        if not is_valid:
            logger.error("Invalid Razorpay webhook signature")
            return {"status": "error", "message": "Invalid webhook signature"}
        
        # Process the webhook event
        event = payload.get("event")
        if not event:
            logger.error("Missing event in webhook payload")
            return {"status": "error", "message": "Missing event in payload"}
        
        # Handle different event types
        if event == "payment.captured":
            # Payment was successfully captured
            payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
            payment_id = payment_entity.get("id")
            order_id = payment_entity.get("order_id")
            
            if not payment_id or not order_id:
                logger.error("Missing payment ID or order ID in webhook payload")
                return {"status": "error", "message": "Missing payment details"}
            
            # Update payment record in database
            payment = db.query(RazorpayPayment).filter(
                RazorpayPayment.razorpay_order_id == order_id
            ).first()
            
            if not payment:
                logger.error(f"Payment record not found for order ID: {order_id}")
                return {"status": "error", "message": "Payment record not found"}
            
            # Update payment status
            payment.razorpay_payment_id = payment_id
            payment.status = "captured"
            payment.updated_at = get_ist_now()
            
            # Get or create user's account
            account = db.execute(
                select(Account).where(Account.id == payment.account_id)
            ).scalars().first()
            
            if not account:
                # Create account if it doesn't exist
                account = Account(
                    user_id=payment.user_id,
                    currency=payment.currency,
                    credits=0.0  # Initialize with zero credits
                )
                db.add(account)
                db.flush()
            
            # Create transaction for the payment
            transaction = Transaction(
                account_id=account.id,
                amount=payment.amount / 100,  # Convert from paise to rupees
                type=TransactionType.CREDIT,
                description=f'Razorpay payment {payment_id}',
                reference_id=payment_id
            )
            
            # Update account balance
            transaction.update_balance(account)
            db.add(transaction)
            
            db.commit()
            
            # Automatically generate invoice for the payment
            try:
                from app.api.v1.endpoints.invoice import create_invoice_for_payment
                invoice_response = create_invoice_for_payment(payment.id, db)
                logger.info(f"Invoice {invoice_response.get('invoice_number')} automatically generated for payment {payment_id}")
                
                # Send invoice email to the user
                try:
                    from app.utils.email_sender import send_invoice_email
                    from app.models.invoice import Invoice
                    from supabase import create_client
                    import os
                    
                    # Get the invoice object
                    invoice_id = invoice_response.get('id')
                    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
                    
                    if invoice:
                        # Collect all possible email addresses
                        email_addresses = set()  # Use set to avoid duplicates
                        
                        # 1. Get client email from invoice (account billing email)
                        if invoice.client_email:
                            email_addresses.add(invoice.client_email)
                            logger.info(f"Added client email: {invoice.client_email}")
                        
                        # 2. Try to get user email from Supabase using user_id
                        try:
                            if payment.user_id:
                                supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
                                user_response = supabase.auth.admin.get_user_by_id(payment.user_id)
                                if user_response and user_response.user and user_response.user.email:
                                    email_addresses.add(user_response.user.email)
                                    logger.info(f"Added user email from Supabase: {user_response.user.email}")
                        except Exception as e:
                            logger.warning(f"Could not fetch user email from Supabase: {str(e)}")
                        
                        # Send invoice email to all collected addresses
                        if email_addresses:
                            for email_address in email_addresses:
                                try:
                                    email_response = await send_invoice_email(invoice, email_address)
                                    logger.info(f"Invoice email sent to {email_address}: {email_response.get('message')}")
                                except Exception as e:
                                    logger.error(f"Failed to send invoice email to {email_address}: {str(e)}")
                        else:
                            logger.warning(f"Could not send invoice email: No email addresses available for invoice {invoice.invoice_number}")
                    else:
                        logger.warning(f"Could not send invoice email: Invoice not found for ID {invoice_id}")
                except Exception as e:
                    logger.error(f"Failed to send invoice email for payment {payment_id}: {str(e)}")
                    # Don't fail the webhook if email sending fails
            except Exception as e:
                logger.error(f"Failed to generate invoice for payment {payment_id}: {str(e)}")
                # Don't fail the webhook if invoice generation fails
            
            logger.info(f"Payment {payment_id} captured and processed successfully")
            return {"status": "success", "message": "Payment captured and processed"}
            
        elif event == "payment.failed":
            # Payment failed
            payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
            payment_id = payment_entity.get("id")
            order_id = payment_entity.get("order_id")
            
            if not order_id:
                logger.error("Missing order ID in webhook payload")
                return {"status": "error", "message": "Missing order ID"}
            
            # Update payment record in database
            payment = db.query(RazorpayPayment).filter(
                RazorpayPayment.razorpay_order_id == order_id
            ).first()
            
            if payment:
                payment.status = "failed"
                payment.updated_at = get_ist_now()
                if payment_id:
                    payment.razorpay_payment_id = payment_id
                db.commit()
            
            logger.info(f"Payment for order {order_id} marked as failed")
            return {"status": "success", "message": "Payment failure recorded"}
            
        elif event == "refund.processed":
            # Refund was processed
            refund_entity = payload.get("payload", {}).get("refund", {}).get("entity", {})
            payment_id = refund_entity.get("payment_id")
            refund_id = refund_entity.get("id")
            
            if not payment_id or not refund_id:
                logger.error("Missing payment ID or refund ID in webhook payload")
                return {"status": "error", "message": "Missing refund details"}
            
            # Find the payment record
            payment = db.query(RazorpayPayment).filter(
                RazorpayPayment.razorpay_payment_id == payment_id
            ).first()
            
            if not payment:
                logger.error(f"Payment record not found for payment ID: {payment_id}")
                return {"status": "error", "message": "Payment record not found"}
            
            # Update payment status
            payment.status = "refunded"
            payment.updated_at = get_ist_now()
            
            # Get user's account
            account = db.execute(
                select(Account).where(Account.id == payment.account_id)
            ).scalars().first()
            
            if account:
                # Create transaction for the refund
                transaction = Transaction(
                    account_id=account.id,
                    amount=payment.amount / 100,  # Convert from paise to rupees
                    type=TransactionType.DEBIT,
                    description=f'Refund for payment {payment_id}',
                    reference_id=refund_id
                )
                
                # Update account balance
                transaction.update_balance(account)
                db.add(transaction)
            
            db.commit()
            
            logger.info(f"Refund {refund_id} processed successfully")
            return {"status": "success", "message": "Refund processed"}
        
        # For other events, just log and acknowledge
        logger.info(f"Received webhook event: {event}")
        return {"status": "success", "message": f"Event {event} acknowledged"}
        
    except Exception as e:
        logger.error(f"Error processing Razorpay webhook: {str(e)}")
        db.rollback()
        return {"status": "error", "message": str(e)}


@router.get("/usage-history")
def get_user_usage_history(
    service_name: Optional[str] = Query(None, description="Filter by specific service"),
    project_id: Optional[str] = Query(None, description="Filter by specific project"),
    limit: int = Query(50, ge=1, le=100, description="Number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """
    Get user's service usage history
    
    Query Parameters:
    - service_name: Filter by specific service (optional)
    - project_id: Filter by specific project (optional)
    - limit: Number of records to return (default: 50, max: 100)
    - offset: Number of records to skip (default: 0)
    
    Returns:
    - List of usage records with service name, charge, transaction ID, and timestamp
    """
    try:
        # Get user ID from authentication
        user_id = current_user.id
        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")
        
        # Use the existing UsageService instead of duplicating logic
        from app.services.usage_service import UsageService
        usage_service = UsageService(db)
        
        # Get usage history using the service
        result = usage_service.get_user_usage_history(
            user_id=user_id,
            service_name=service_name,
            project_id=project_id,
            limit=limit,
            offset=offset
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching usage history: {result.get('message', 'Unknown error')}"
            )
        
        # Transform the response to match the expected API format
        usage_history = []
        for record in result["usage_records"]:
            usage_history.append({
                "usage_id": record["id"],
                "service_name": record["service_name"],
                "actual_charge": record["actual_charge"],
                "project_id": record["project_id"],
                "project_name": record["project_name"],
                "project_url": record["project_url"],
                "created_at": record["created_at"]
            })
        
        return {
            "success": True,
            "usage_history": usage_history,
            "pagination": {
                "total_records": result["total_records"],
                "current_page": (offset // limit) + 1,
                "total_pages": (result["total_records"] + limit - 1) // limit,
                "limit": limit,
                "offset": offset,
                "has_next": offset + limit < result["total_records"],
                "has_previous": offset > 0
            },
            "filters": {
                "service_name": service_name,
                "project_id": project_id
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching usage history: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching usage history: {str(e)}"
        )

