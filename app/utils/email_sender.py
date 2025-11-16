"""Email sending utilities"""
from typing import Optional, Dict, Any
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from jinja2 import Environment, select_autoescape, PackageLoader
from app.core.config import settings
from datetime import datetime

# Email configuration using settings
email_conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    VALIDATE_CERTS=True
)

# Initialize Jinja2 template environment
env = Environment(
    loader=PackageLoader('app', 'templates/email'),
    autoescape=select_autoescape(['html', 'xml'])
)

def format_number(num):
    """Format numbers for better readability"""
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    elif num >= 1000:
        return f"{num/1000:.1f}K"
    return str(num)

async def send_report_email(
    email: str,
    subject: str,
    report_data: Optional[Dict[str, Any]] = None,
    attachment_path: Optional[str] = None
):
    """Send GSC report via email"""
    # Get email template
    template = env.get_template('gsc_report.html')
    
    # Format data for the template
    if report_data:
        formatted_data = {
            'site_url': report_data['site_url'],
            'date_range': report_data['date_range'],
            'summary': {
                'current': {
                    'impressions': format_number(report_data['summary']['current']['impressions']),
                    'clicks': format_number(report_data['summary']['current']['clicks']),
                    'ctr': f"{report_data['summary']['current']['ctr']:.2f}%",
                    'position': f"{report_data['summary']['current']['position']:.1f}"
                },
                'changes': report_data['summary']['changes']
            },
            'top_pages': report_data['top_pages']['pages'][:5],  # Top 5 pages
            'devices': report_data['devices']['breakdown'],
            'countries': report_data['countries']['breakdown'][:5]  # Top 5 countries
        }
    else:
        formatted_data = {}

    # Create message
    html_content = template.render(**formatted_data)
    
    message = MessageSchema(
        subject=subject,
        recipients=[email],
        body=html_content,
        subtype="html"
    )

    # Add attachment if provided
    if attachment_path:
        message.attachments = [attachment_path]

    # Send email
    fm = FastMail(email_conf)
    await fm.send_message(message)

    return {"status": "success", "message": f"Email sent to {email}"}

async def send_invoice_email(
    invoice,
    user_email: str = None,
    subject: str = None
):
    """
    Send invoice email with PDF attachment - automatically detects plan vs wallet payments
    
    Args:
        invoice: Invoice object with all details
        user_email: Email address to send to (defaults to invoice.client_email if not provided)
        subject: Email subject line (auto-generated if not provided)
        
    Returns:
        Dict with status and message
    """
    from app.utils.invoice_pdf_generation1 import generate_invoice_pdf
    from app.utils.plan_invoice_pdf_generation import generate_plan_invoice_pdf
    
    # Use client email from invoice if user_email not provided
    if not user_email and invoice.client_email:
        user_email = invoice.client_email
    
    # If still no email, return error
    if not user_email:
        return {
            "status": "error", 
            "message": "No email address provided for sending invoice"
        }
    
    # Detect payment type from invoice items
    is_plan_payment = False
    plan_name = "Pro Plan"
    plan_duration = "monthly"
    
    if invoice.invoice_items:
        item = invoice.invoice_items[0]
        # Check if this is a plan subscription
        if "subscription" in item.description.lower() or "plan" in item.name.lower():
            is_plan_payment = True
            
            # Extract plan details
            if "monthly" in item.description.lower():
                plan_duration = "monthly"
            elif "quarterly" in item.description.lower():
                plan_duration = "quarterly"
            elif "yearly" in item.description.lower():
                plan_duration = "yearly"
            
            if "pro" in item.name.lower():
                plan_name = "Pro Plan"
    
    # Convert Invoice object to dictionary for PDF generation
    invoice_data = {
        'invoice_number': invoice.invoice_number,
        'issue_date': invoice.issue_date,
        'due_date': invoice.due_date,
        'total_amount': invoice.total,
        'currency': invoice.currency,
        'payment_id': invoice.payment_reference,
        'payment_method': invoice.payment_method or "Online Payment",
        'payment_reference': invoice.payment_reference,
        'client_info': {
            'name': invoice.client_name,
            'email': invoice.client_email,
            'address': invoice.client_address or ""
        },
        'items': []
    }
    
    # Add invoice items
    if invoice.invoice_items:
        for item in invoice.invoice_items:
            invoice_data['items'].append({
                'name': item.name,
                'description': item.description,
                'quantity': item.quantity,
                'unit_price': item.unit_price,
                'total_price': item.total_price
            })
    
    # Generate appropriate PDF
    if is_plan_payment:
        print(f"DEBUG: Plan invoice data: {invoice_data}")  # Debug logging
        pdf_path = generate_plan_invoice_pdf(invoice_data)
    else:
        print(f"DEBUG: Wallet invoice data: {invoice_data}")  # Debug logging
        pdf_path = generate_invoice_pdf(invoice_data)
    
    # Format currency for display
    def format_currency_display(amount, currency):
        if currency == "INR":
            return f"Rs. {amount:,.2f}"
        elif currency == "USD":
            return f"${amount:,.2f}"
        elif currency == "EUR":
            return f"€{amount:,.2f}"
        else:
            return f"{amount:,.2f} {currency}"
    
    # Choose template and subject based on payment type
    if is_plan_payment:
        template = env.get_template('plan_invoice_email.html')
        default_subject = "Your Rayo Pro Plan is Now Active!"
        
        # Format plan-specific data
        formatted_data = {
            'client_name': invoice.client_name,
            'invoice_number': invoice.invoice_number,
            'issue_date': invoice.issue_date.strftime('%d %b, %Y') if invoice.issue_date else datetime.now().strftime('%d %b, %Y'),
            'payment_method': invoice.payment_method or "Online Payment",
            'payment_reference': invoice.payment_reference,
            'formatted_amount': format_currency_display(invoice.total, invoice.currency),
            'currency': invoice.currency,
            'plan_name': plan_name,
            'plan_duration': plan_duration,
            'plan_start_date': datetime.now().strftime('%d %b, %Y'),
            'plan_end_date': (datetime.now().replace(month=datetime.now().month+1) if plan_duration == "monthly" 
                             else datetime.now().replace(year=datetime.now().year+1)).strftime('%d %b, %Y')
        }
    else:
        template = env.get_template('invoice_email.html')
        default_subject = "Your Invoice from Rayo"
        
        # Format wallet/credit-specific data
        formatted_data = {
            'client_name': invoice.client_name,
            'invoice_number': invoice.invoice_number,
            'issue_date': invoice.issue_date.strftime('%d %b, %Y') if invoice.issue_date else datetime.now().strftime('%d %b, %Y'),
            'payment_method': invoice.payment_method or "Online Payment",
            'payment_reference': invoice.payment_reference,
            'formatted_amount': format_currency_display(invoice.total, invoice.currency),
            'currency': invoice.currency
        }
    
    # Use provided subject or default
    email_subject = subject or default_subject

    # Create message
    html_content = template.render(**formatted_data)
    
    # Prepare attachment filename
    attachment_filename = f"invoice_{invoice.invoice_number}.pdf"
    
    message = MessageSchema(
        subject=email_subject,
        recipients=[user_email],
        body=html_content,
        subtype="html",
        attachments=[{
            "file": pdf_path,
            "filename": attachment_filename,
            "content_type": "application/pdf"
        }]
    )

    # Send email
    try:
        fm = FastMail(email_conf)
        await fm.send_message(message)
        
        payment_type = "plan upgrade" if is_plan_payment else "credit recharge"
        
        return {
            "status": "success", 
            "message": f"{payment_type.title()} invoice email sent to {user_email}",
            "email_type": "plan" if is_plan_payment else "wallet"
        }
    except Exception as e:        
        import os
        # Clean up the temporary PDF file
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except:
                pass
        
        return {
            "status": "error", 
            "message": f"Failed to send invoice email: {str(e)}"
        }
    finally:
        # Clean up the temporary PDF file
        import os
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except:
                pass
