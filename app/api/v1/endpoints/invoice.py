from fastapi import APIRouter, Depends, HTTPException, Request, Query, Path, Body
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import pytz
import logging
from pydantic import BaseModel, Field, validator
from uuid import UUID
import uuid
from fastapi.responses import FileResponse
from app.utils.invoice_pdf_generation1 import generate_invoice_pdf
from app.models.invoice import Invoice, InvoiceItem, InvoiceStatus
from app.models.account import Account
from app.models.transaction import Transaction, TransactionType
from app.db.session import get_db
from app.middleware.auth_middleware import verify_request_origin

router = APIRouter()
logger = logging.getLogger(__name__)

# Define IST timezone
IST = pytz.timezone('Asia/Kolkata')

def get_ist_now():
    """Get current time in IST timezone"""
    return datetime.now(IST)

# Helper function to generate invoice number
def generate_invoice_number(db: Session) -> str:
    """Generate a unique invoice number with prefix INV-YYYY-MM-"""
    now = get_ist_now()
    prefix = f"INV-{now.year}-{now.month:02d}-"
    
    # Get the highest invoice number with this prefix
    result = db.execute(
        select(func.max(Invoice.invoice_number)).where(Invoice.invoice_number.like(f"{prefix}%"))
    ).scalar()
    
    if result:
        # Extract the number part and increment
        try:
            last_num = int(result.split('-')[-1])
            next_num = last_num + 1
        except (ValueError, IndexError):
            next_num = 1
    else:
        next_num = 1
    
    return f"{prefix}{next_num:04d}"

# Pydantic models for request/response validation
class InvoiceItemCreate(BaseModel):
    name: str
    description: Optional[str] = None
    quantity: float = Field(1.0, gt=0)
    unit_price: float = Field(..., ge=0)
    tax_rate: Optional[float] = Field(None, ge=0)
    discount_rate: Optional[float] = Field(None, ge=0)

class InvoiceCreate(BaseModel):
    client_name: str
    client_email: Optional[str] = None
    client_phone: Optional[str] = None
    client_address: Optional[str] = None
    client_city: Optional[str] = None
    client_state: Optional[str] = None
    client_country: Optional[str] = None
    client_postal_code: Optional[str] = None
    currency: str = "INR"
    issue_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    notes: Optional[str] = None
    terms: Optional[str] = None
    payment_instructions: Optional[str] = None
    tax_rate: Optional[float] = Field(None, ge=0)
    discount_rate: Optional[float] = Field(None, ge=0)
    items: List[InvoiceItemCreate] = Field(..., min_items=1)
    invoice_metadata: Optional[Dict[str, Any]] = None
    
    @validator('due_date', pre=True, always=True)
    def set_due_date(cls, v, values):
        if v is None:
            # Default due date is 15 days from issue date
            issue_date = values.get('issue_date')
            if issue_date is None:
                issue_date = get_ist_now()
            return issue_date + timedelta(days=15)
        return v
    
    @validator('issue_date', pre=True, always=True)
    def set_issue_date(cls, v):
        if v is None:
            return get_ist_now()
        return v

class InvoiceUpdate(BaseModel):
    client_name: Optional[str] = None
    client_email: Optional[str] = None
    client_phone: Optional[str] = None
    client_address: Optional[str] = None
    client_city: Optional[str] = None
    client_state: Optional[str] = None
    client_country: Optional[str] = None
    client_postal_code: Optional[str] = None
    currency: Optional[str] = None
    issue_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    notes: Optional[str] = None
    terms: Optional[str] = None
    payment_instructions: Optional[str] = None
    tax_rate: Optional[float] = Field(None, ge=0)
    discount_rate: Optional[float] = Field(None, ge=0)
    status: Optional[str] = None
    invoice_metadata: Optional[Dict[str, Any]] = None

class InvoiceItemResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    quantity: float
    unit_price: float
    total_price: float
    tax_rate: Optional[float] = None
    tax_amount: Optional[float] = None
    discount_rate: Optional[float] = None
    discount_amount: Optional[float] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class InvoiceResponse(BaseModel):
    id: str
    invoice_number: str
    account_id: str
    user_id: str
    status: str
    issue_date: datetime
    due_date: datetime
    amount_due: float
    amount_paid: float
    currency: str
    client_name: str
    client_email: Optional[str] = None
    client_phone: Optional[str] = None
    client_address: Optional[str] = None
    client_city: Optional[str] = None
    client_state: Optional[str] = None
    client_country: Optional[str] = None
    client_postal_code: Optional[str] = None
    notes: Optional[str] = None
    terms: Optional[str] = None
    payment_instructions: Optional[str] = None
    tax_rate: Optional[float] = None
    tax_amount: Optional[float] = None
    discount_rate: Optional[float] = None
    discount_amount: Optional[float] = None
    subtotal: float
    total: float
    payment_method: Optional[str] = None
    payment_date: Optional[datetime] = None
    payment_reference: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    items: List[InvoiceItemResponse] = []
    invoice_metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True

class InvoiceListResponse(BaseModel):
    total: int
    invoices: List[InvoiceResponse]

# Helper function to convert model to dict with string UUIDs
def invoice_to_response(invoice: Invoice, include_items: bool = True) -> Dict[str, Any]:
    response = {
        "id": str(invoice.id),
        "invoice_number": invoice.invoice_number,
        "account_id": str(invoice.account_id),
        "user_id": str(invoice.user_id),
        "status": invoice.status,  # Now status is already a string, no need for .value
        "issue_date": invoice.issue_date,
        "due_date": invoice.due_date,
        "amount_due": invoice.amount_due,
        "amount_paid": invoice.amount_paid,
        "currency": invoice.currency,
        "client_name": invoice.client_name,
        "client_email": invoice.client_email,
        "client_phone": invoice.client_phone,
        "client_address": invoice.client_address,
        "client_city": invoice.client_city,
        "client_state": invoice.client_state,
        "client_country": invoice.client_country,
        "client_postal_code": invoice.client_postal_code,
        "notes": invoice.notes,
        "terms": invoice.terms,
        "payment_instructions": invoice.payment_instructions,
        "tax_rate": invoice.tax_rate,
        "tax_amount": invoice.tax_amount,
        "discount_rate": invoice.discount_rate,
        "discount_amount": invoice.discount_amount,
        "subtotal": invoice.subtotal,
        "total": invoice.total,
        "payment_method": invoice.payment_method,
        "payment_date": invoice.payment_date,
        "payment_reference": invoice.payment_reference,
        "razorpay_payment_id": str(invoice.razorpay_payment_id) if invoice.razorpay_payment_id else None,
        "created_at": invoice.created_at,
        "updated_at": invoice.updated_at,
        "invoice_metadata": invoice.invoice_metadata,
        "items": []
    }
    
    if include_items and invoice.invoice_items:
        response["items"] = [invoice_item_to_response(item) for item in invoice.invoice_items]
    
    if invoice.invoice_metadata:
        response["invoice_metadata"] = invoice.invoice_metadata
    
    return response

def invoice_item_to_response(item: InvoiceItem) -> Dict[str, Any]:
    return {
        "id": str(item.id),
        "name": item.name,
        "description": item.description,
        "quantity": item.quantity,
        "unit_price": item.unit_price,
        "total_price": item.total_price,
        "tax_rate": item.tax_rate,
        "tax_amount": item.tax_amount,
        "discount_rate": item.discount_rate,
        "discount_amount": item.discount_amount,
        "created_at": item.created_at
    }

# Calculate invoice totals
def calculate_invoice_totals(invoice_data, items_data):
    subtotal = 0
    tax_amount = 0
    discount_amount = 0
    
    # Calculate item totals and subtotal
    for item in items_data:
        item_total = item.quantity * item.unit_price
        
        # Apply item-specific tax if provided
        item_tax = 0
        if item.tax_rate is not None:
            item_tax = item_total * (item.tax_rate / 100)
        
        # Apply item-specific discount if provided
        item_discount = 0
        if item.discount_rate is not None:
            item_discount = item_total * (item.discount_rate / 100)
        
        # Add to running totals
        subtotal += item_total
        tax_amount += item_tax
        discount_amount += item_discount
    
    # Apply invoice-level tax if provided and no item-specific taxes
    if tax_amount == 0 and invoice_data.tax_rate is not None:
        tax_amount = subtotal * (invoice_data.tax_rate / 100)
    
    # Apply invoice-level discount if provided and no item-specific discounts
    if discount_amount == 0 and invoice_data.discount_rate is not None:
        discount_amount = subtotal * (invoice_data.discount_rate / 100)
    
    # Calculate final total
    total = subtotal + tax_amount - discount_amount
    
    return {
        "subtotal": subtotal,
        "tax_amount": tax_amount,
        "discount_amount": discount_amount,
        "total": total
    }

@router.post("/", response_model=InvoiceResponse)
def create_invoice(
    invoice_data: InvoiceCreate,
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """Create a new invoice"""
    user_id = current_user.id
    
    # Get user's account
    account = db.execute(
        select(Account).where(Account.user_id == user_id)
    ).scalars().first()
    
    if not account:
        # Create account if it doesn't exist
        account = Account(
            user_id=user_id,
            currency=invoice_data.currency
        )
        db.add(account)
        db.flush()
    
    # Generate invoice number
    invoice_number = generate_invoice_number(db)
    
    # Calculate totals
    totals = calculate_invoice_totals(invoice_data, invoice_data.items)
    
    # Create invoice
    invoice = Invoice(
        invoice_number=invoice_number,
        account_id=account.id,
        user_id=user_id,
        status=InvoiceStatus.DRAFT,
        issue_date=invoice_data.issue_date,
        due_date=invoice_data.due_date,
        amount_due=totals["total"],
        amount_paid=0.0,
        currency=invoice_data.currency,
        client_name=invoice_data.client_name,
        client_email=invoice_data.client_email,
        client_phone=invoice_data.client_phone,
        client_address=invoice_data.client_address,
        client_city=invoice_data.client_city,
        client_state=invoice_data.client_state,
        client_country=invoice_data.client_country,
        client_postal_code=invoice_data.client_postal_code,
        notes=invoice_data.notes,
        terms=invoice_data.terms,
        payment_instructions=invoice_data.payment_instructions,
        tax_rate=invoice_data.tax_rate,
        tax_amount=totals["tax_amount"],
        discount_rate=invoice_data.discount_rate,
        discount_amount=totals["discount_amount"],
        subtotal=totals["subtotal"],
        total=totals["total"]
    )
    
    db.add(invoice)
    db.flush()  # Flush to get the invoice ID
    
    # Create invoice items
    for item_data in invoice_data.items:
        item_total = item_data.quantity * item_data.unit_price
        
        # Calculate item-specific tax if provided
        item_tax = None
        if item_data.tax_rate is not None:
            item_tax = item_total * (item_data.tax_rate / 100)
        
        # Calculate item-specific discount if provided
        item_discount = None
        if item_data.discount_rate is not None:
            item_discount = item_total * (item_data.discount_rate / 100)
        
        invoice_item = InvoiceItem(
            invoice_id=invoice.id,
            name=item_data.name,
            description=item_data.description,
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
            total_price=item_total,
            tax_rate=item_data.tax_rate,
            tax_amount=item_tax,
            discount_rate=item_data.discount_rate,
            discount_amount=item_discount
        )
        
        db.add(invoice_item)
    
    db.commit()
    db.refresh(invoice)
    
    return invoice_to_response(invoice)

@router.get("/", response_model=InvoiceListResponse)
def get_invoices(
    status: Optional[str] = Query(None, description="Filter by invoice status"),
    client_name: Optional[str] = Query(None, description="Filter by client name"),
    start_date: Optional[datetime] = Query(None, description="Filter by issue date (start)"),
    end_date: Optional[datetime] = Query(None, description="Filter by issue date (end)"),
    skip: int = Query(0, ge=0, description="Number of invoices to skip"),
    limit: int = Query(10, ge=1, le=100, description="Number of invoices to return"),
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """Get all invoices for the current user"""
    user_id = current_user.id
    
    # Base query
    query = select(Invoice).where(Invoice.user_id == user_id)
    
    # Apply filters
    if status:
        try:
            invoice_status = InvoiceStatus(status)
            query = query.where(Invoice.status == invoice_status.value)  # Use .value to get the string
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    if client_name:
        query = query.where(Invoice.client_name.ilike(f"%{client_name}%"))
    
    if start_date:
        query = query.where(Invoice.issue_date >= start_date)
    
    if end_date:
        query = query.where(Invoice.issue_date <= end_date)
    
    # Count total matching invoices
    total_count = db.execute(
        select(func.count()).select_from(query.subquery())
    ).scalar()
    
    # Apply pagination
    query = query.order_by(Invoice.created_at.desc()).offset(skip).limit(limit)
    
    # Execute query
    invoices = db.execute(query).scalars().all()
    
    # Convert to response format
    invoice_responses = [invoice_to_response(invoice, include_items=False) for invoice in invoices]
    
    return {
        "total": total_count,
        "invoices": invoice_responses
    }

@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: UUID = Path(..., description="The ID of the invoice to retrieve"),
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """Get a specific invoice by ID"""
    user_id = current_user.id
    
    invoice = db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == user_id)
    ).scalars().first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    return invoice_to_response(invoice)

@router.put("/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(
    invoice_id: UUID = Path(..., description="The ID of the invoice to update"),
    invoice_data: InvoiceUpdate = Body(...),
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """Update an existing invoice"""
    user_id = current_user.id
    
    invoice = db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == user_id)
    ).scalars().first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Only allow updates to draft invoices unless it's just a status change
    if invoice.status != InvoiceStatus.DRAFT and invoice_data.status is None:
        raise HTTPException(status_code=400, detail="Cannot update a non-draft invoice")
    
    # Update invoice fields if provided
    if invoice_data.client_name is not None:
        invoice.client_name = invoice_data.client_name
    if invoice_data.client_email is not None:
        invoice.client_email = invoice_data.client_email
    if invoice_data.client_phone is not None:
        invoice.client_phone = invoice_data.client_phone
    if invoice_data.client_address is not None:
        invoice.client_address = invoice_data.client_address
    if invoice_data.client_city is not None:
        invoice.client_city = invoice_data.client_city
    if invoice_data.client_state is not None:
        invoice.client_state = invoice_data.client_state
    if invoice_data.client_country is not None:
        invoice.client_country = invoice_data.client_country
    if invoice_data.client_postal_code is not None:
        invoice.client_postal_code = invoice_data.client_postal_code
    if invoice_data.currency is not None:
        invoice.currency = invoice_data.currency
    if invoice_data.issue_date is not None:
        invoice.issue_date = invoice_data.issue_date
    if invoice_data.due_date is not None:
        invoice.due_date = invoice_data.due_date
    if invoice_data.notes is not None:
        invoice.notes = invoice_data.notes
    if invoice_data.terms is not None:
        invoice.terms = invoice_data.terms
    if invoice_data.payment_instructions is not None:
        invoice.payment_instructions = invoice_data.payment_instructions
    if invoice_data.tax_rate is not None:
        invoice.tax_rate = invoice_data.tax_rate
        # Recalculate tax amount
        if invoice.subtotal:
            invoice.tax_amount = invoice.subtotal * (invoice_data.tax_rate / 100)
    if invoice_data.discount_rate is not None:
        invoice.discount_rate = invoice_data.discount_rate
        # Recalculate discount amount
        if invoice.subtotal:
            invoice.discount_amount = invoice.subtotal * (invoice_data.discount_rate / 100)
    
    # Update status if provided
    if invoice_data.status is not None:
        try:
            new_status = InvoiceStatus(invoice_data.status)
            invoice.status = new_status.value  # Use .value to get the string
            
            # If marked as paid, update payment details
            if new_status == InvoiceStatus.PAID and invoice.amount_paid < invoice.total:
                invoice.amount_paid = invoice.total
                invoice.payment_date = get_ist_now()
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {invoice_data.status}")
    
    # Recalculate total if tax or discount changed
    if invoice_data.tax_rate is not None or invoice_data.discount_rate is not None:
        invoice.total = invoice.subtotal + (invoice.tax_amount or 0) - (invoice.discount_amount or 0)
        invoice.amount_due = invoice.total - invoice.amount_paid
    
    invoice.updated_at = get_ist_now()
    
    db.commit()
    db.refresh(invoice)
    
    return invoice_to_response(invoice)

@router.delete("/{invoice_id}")
def delete_invoice(
    invoice_id: UUID = Path(..., description="The ID of the invoice to delete"),
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """Delete an invoice"""
    user_id = current_user.id
    
    invoice = db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == user_id)
    ).scalars().first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Only allow deletion of draft invoices
    if invoice.status != InvoiceStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft invoices can be deleted")
    
    db.delete(invoice)
    db.commit()
    
    return {"message": "Invoice deleted successfully"}

@router.post("/{invoice_id}/send", response_model=InvoiceResponse)
def send_invoice(
    invoice_id: UUID = Path(..., description="The ID of the invoice to send"),
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """Mark an invoice as sent"""
    user_id = current_user.id
    
    invoice = db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == user_id)
    ).scalars().first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Only allow sending draft invoices
    if invoice.status != InvoiceStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft invoices can be sent")
    
    # Update status to sent
    invoice.status = InvoiceStatus.SENT.value  # Use .value to get the string
    invoice.updated_at = get_ist_now()
    
    db.commit()
    db.refresh(invoice)
    
    return invoice_to_response(invoice)

@router.post("/{invoice_id}/mark-paid", response_model=InvoiceResponse)
def mark_invoice_paid(
    invoice_id: UUID = Path(..., description="The ID of the invoice to mark as paid"),
    payment_method: str = Query(..., description="Payment method used"),
    payment_reference: Optional[str] = Query(None, description="Payment reference number"),
    payment_date: Optional[datetime] = Query(None, description="Date of payment"),
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """Mark an invoice as paid"""
    user_id = current_user.id
    
    invoice = db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == user_id)
    ).scalars().first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Only allow marking sent or partially paid invoices as paid
    if invoice.status not in [InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID]:
        raise HTTPException(status_code=400, detail="Only sent or partially paid invoices can be marked as paid")
    
    # Update payment details
    invoice.status = InvoiceStatus.PAID.value  # Use .value to get the string
    invoice.payment_method = payment_method
    invoice.payment_reference = payment_reference
    invoice.payment_date = payment_date or get_ist_now()
    invoice.amount_paid = invoice.total
    invoice.amount_due = 0
    invoice.updated_at = get_ist_now()
    
    db.commit()
    db.refresh(invoice)
    
    return invoice_to_response(invoice)

@router.post("/{invoice_id}/record-payment")
def record_payment(
    invoice_id: UUID = Path(..., description="The ID of the invoice"),
    amount: float = Query(..., gt=0, description="Payment amount"),
    payment_method: str = Query(..., description="Payment method used"),
    payment_reference: Optional[str] = Query(None, description="Payment reference number"),
    payment_date: Optional[datetime] = Query(None, description="Date of payment"),
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """Record a payment for an invoice"""
    user_id = current_user.id
    
    invoice = db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == user_id)
    ).scalars().first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Only allow payments for sent or partially paid invoices
    if invoice.status not in [InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID]:
        raise HTTPException(status_code=400, detail="Cannot record payment for this invoice")
    
    # Validate payment amount
    if amount > invoice.amount_due:
        raise HTTPException(status_code=400, detail="Payment amount exceeds amount due")
    
    # Update payment details
    invoice.amount_paid += amount
    invoice.amount_due -= amount
    invoice.payment_method = payment_method
    invoice.payment_reference = payment_reference
    invoice.payment_date = payment_date or get_ist_now()
    
    # Update status based on payment
    if invoice.amount_due <= 0:
        invoice.status = InvoiceStatus.PAID.value  # Use .value to get the string
    else:
        invoice.status = InvoiceStatus.PARTIALLY_PAID.value  # Use .value to get the string
    
    invoice.updated_at = get_ist_now()
    
    db.commit()
    db.refresh(invoice)
    
    return invoice_to_response(invoice)

@router.post("/{invoice_id}/link-payment/{payment_id}")
def link_razorpay_payment(
    invoice_id: UUID = Path(..., description="The ID of the invoice"),
    payment_id: UUID = Path(..., description="The ID of the Razorpay payment"),
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """Link a Razorpay payment to an invoice"""
    from app.models.razorpay import RazorpayPayment
    
    user_id = current_user.id
    
    invoice = db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == user_id)
    ).scalars().first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    payment = db.execute(
        select(RazorpayPayment).where(RazorpayPayment.id == payment_id, RazorpayPayment.user_id == user_id)
    ).scalars().first()
    
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    # Verify payment status
    if payment.status != "captured":
        raise HTTPException(status_code=400, detail="Payment must be captured to link to an invoice")
    
    # Link payment to invoice
    invoice.razorpay_payment_id = payment.id
    
    # Calculate payment amount in base currency (not smallest unit)
    payment_amount = payment.amount / 100
    
    # Update invoice payment details
    previous_amount_paid = invoice.amount_paid
    invoice.amount_paid += payment_amount
    if invoice.amount_paid > invoice.total:
        invoice.amount_paid = invoice.total
    
    invoice.amount_due = max(0, invoice.total - invoice.amount_paid)
    invoice.payment_method = "Razorpay"
    invoice.payment_reference = payment.razorpay_payment_id
    invoice.payment_date = payment.updated_at or get_ist_now()
    
    # Update status based on payment
    if invoice.amount_due <= 0:
        invoice.status = InvoiceStatus.PAID.value  # Use .value to get the string
    else:
        invoice.status = InvoiceStatus.PARTIALLY_PAID.value  # Use .value to get the string
    
    invoice.updated_at = get_ist_now()
    
    db.commit()
    db.refresh(invoice)
    
    return invoice_to_response(invoice)

@router.post("/{invoice_id}/cancel")
def cancel_invoice(
    invoice_id: UUID = Path(..., description="The ID of the invoice to cancel"),
    current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """Cancel an invoice"""
    user_id = current_user.id
    
    invoice = db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == user_id)
    ).scalars().first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Only allow cancelling non-paid invoices
    if invoice.status == InvoiceStatus.PAID:
        raise HTTPException(status_code=400, detail="Cannot cancel a paid invoice")
    
    # Update status to cancelled
    invoice.status = InvoiceStatus.CANCELLED.value  # Use .value to get the string
    invoice.updated_at = get_ist_now()
    
    db.commit()
    db.refresh(invoice)
    
    return invoice_to_response(invoice)

@router.post("/create-for-payment", response_model=InvoiceResponse)
def create_invoice_for_payment(
    payment_id: UUID = Query(..., description="The ID of the Razorpay payment"),
    # current_user = Depends(verify_request_origin),
    db: Session = Depends(get_db)
):
    """Create an invoice for a credits recharge payment"""
    from app.models.razorpay import RazorpayPayment
    from app.models.account import Account
    
    # Get the payment details using direct SQL query which we know works
    payment_row = db.execute(
        text("""
            SELECT * FROM public.razorpay_payments 
            WHERE id = :payment_id
        """),
        {"payment_id": str(payment_id)}
    ).fetchone()
    
    if not payment_row:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    # Use the user_id from the payment record instead of the authenticated user
    user_id = payment_row.user_id
    
    # Verify payment status
    if payment_row.status != "captured":
        raise HTTPException(status_code=400, detail="Payment must be captured to create an invoice")
    
    # Get the account associated with the payment
    account = db.execute(
        text("""
            SELECT * FROM public.accounts 
            WHERE id = :account_id
        """),
        {"account_id": str(payment_row.account_id)}
    ).fetchone()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Generate invoice number
    invoice_number = generate_invoice_number(db)
    
    # Calculate amount in base currency (not smallest unit)
    amount = payment_row.amount / 100
    
    # Apply GST for Indian payments in INR
    tax_rate = None
    tax_amount = None
    if payment_row.currency == "INR":
        tax_rate = 18.0  # 18% GST for Indian payments
        tax_amount = amount * (tax_rate / 100)
        subtotal = amount - tax_amount  # The amount before tax
    else:
        subtotal = amount  # No tax for non-INR payments
    
    # Create invoice - use InvoiceStatus.PAID.value to get the lowercase string 'paid'
    invoice = Invoice(
        invoice_number=invoice_number,
        account_id=account.id,
        user_id=user_id,
        status=InvoiceStatus.PAID.value,  # Use .value to get the lowercase string 'paid'
        issue_date=payment_row.created_at or get_ist_now(),
        due_date=payment_row.created_at or get_ist_now(),  # Same as issue date since it's already paid
        amount_due=0.0,  # Zero since it's already paid
        amount_paid=amount,
        currency=payment_row.currency or "INR",
        client_name=account.billing_name or "Account Owner",
        client_email=account.billing_email,
        client_phone=account.billing_phone,
        client_address=account.billing_address,
        client_city=account.billing_city,
        client_state=account.billing_state,
        client_country=account.billing_country,
        client_postal_code=account.billing_postal_code,
        notes="This invoice was automatically generated for a credits recharge payment.",
        tax_rate=tax_rate,
        tax_amount=tax_amount,
        subtotal=subtotal,
        total=amount,  # Total is the full amount including tax
        payment_method="Razorpay",
        payment_date=payment_row.updated_at or get_ist_now(),
        payment_reference=payment_row.razorpay_payment_id,
        razorpay_payment_id=payment_row.id,
        invoice_metadata={"razorpay_payment_details": {
            "payment_id": payment_row.razorpay_payment_id,
            "order_id": payment_row.razorpay_order_id,
            "amount_in_smallest_unit": payment_row.amount
        }}
    )
    
    db.add(invoice)
    db.flush()  # Flush to get the invoice ID
    
    # Create invoice item based on payment purpose
    payment_metadata = payment_row.metadata or {}
    payment_purpose = payment_metadata.get("purpose")
    
    if payment_purpose == "plan_upgrade":
        # Plan upgrade invoice item
        plan_name = payment_metadata.get("plan_name", "Pro Plan")
        plan_duration = payment_metadata.get("plan_duration", "monthly")
        
        invoice_item = InvoiceItem(
            invoice_id=invoice.id,
            name=f"{plan_name} Subscription",
            description=f"{plan_name} ({plan_duration}) - Plan upgrade subscription",
            quantity=1.0,
            unit_price=amount,
            total_price=amount
        )
    else:
        # Wallet top-up invoice item
        invoice_item = InvoiceItem(
            invoice_id=invoice.id,
            name="Credits Recharge",
            description=f"Recharge of {amount} credits to your account",
            quantity=1.0,
            unit_price=amount,
            total_price=amount
        )
    
    db.add(invoice_item)
    db.commit()
    db.refresh(invoice)
    
    return invoice_to_response(invoice)

@router.get("/download-pdf/{invoice_id}", response_class=FileResponse)
async def download_invoice_pdf(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(verify_request_origin)
):
    """
    Download an invoice as a PDF file
    """
    # Convert string ID to UUID
    try:
        invoice_uuid = uuid.UUID(invoice_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invoice ID format")
    
    # Get the invoice
    invoice = db.query(Invoice).filter(Invoice.id == invoice_uuid).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Check if user has access to this invoice
    # if not current_user.is_superuser and invoice.user_id != current_user.id:
    #     # For non-superusers, check if the invoice belongs to their account
    #     account = db.query(Account).filter(Account.user_id == current_user.id).first()
    #     if not account or invoice.account_id != account.id:
    #         raise HTTPException(status_code=403, detail="You don't have access to this invoice")
    
    # Generate the PDF
    pdf_path = generate_invoice_pdf(invoice)
    
    # Return the file
    filename = f"invoice_{invoice.invoice_number}.pdf"
    headers = {
        'Content-Disposition': f'attachment; filename="{filename}"'
    }
    
    return FileResponse(
        path=pdf_path,
        filename=filename,
        media_type="application/pdf",
        headers=headers
    )

@router.post("/create-for-payment-and-download", response_class=FileResponse)
async def create_invoice_for_payment_and_download(
    payment_id: str,
    db: Session = Depends(get_db)
):
    """
    Create an invoice for a payment and download it as a PDF
    """
    # First create the invoice using the existing endpoint logic
    invoice = create_invoice_for_payment(payment_id, db)
    
    # Generate the PDF
    pdf_path = generate_invoice_pdf(invoice)
    
    # Return the file
    filename = f"invoice_{invoice.invoice_number}.pdf"
    headers = {
        'Content-Disposition': f'attachment; filename="{filename}"'
    }
    
    return FileResponse(
        path=pdf_path,
        filename=filename,
        media_type="application/pdf",
        headers=headers
    )
