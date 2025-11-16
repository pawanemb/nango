"""
Restructured Invoice PDF Generation utilities with improved layout and spacing
"""
import tempfile
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm, inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image, PageBreak
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.utils import ImageReader
import os
import sys

class InvoiceConfig:
    """Configuration class for invoice styling and layout"""
    
    # Color scheme
    COLORS = {
        'primary': colors.HexColor('#5E33FF'),
        'text': colors.HexColor('#333333'),
        'light_gray': colors.HexColor('#f8f9fa'),
        'border': colors.HexColor('#e9ecef'),
        'success': colors.HexColor('#28a745'),
        'white': colors.white,
        'black': colors.black
    }
    
    # Spacing constants
    SPACING = {
        'section': 12*mm,
        'subsection': 8*mm,
        'element': 4*mm,
        'line': 2*mm,
        'tight': 1*mm
    }
    
    # Font sizes
    FONTS = {
        'title': 20,
        'heading': 16,
        'subheading': 12,
        'body': 10,
        'small': 9,
        'tiny': 8
    }
    
    # Layout dimensions
    LAYOUT = {
        'margin': 15*mm,
        'table_padding': 6,
        'logo_width': 120,
        'logo_height': 48
    }

class InvoiceStyleManager:
    """Manages all styling for invoice elements"""
    
    def __init__(self):
        self.base_styles = getSampleStyleSheet()
        self.custom_styles = {}
        self._create_custom_styles()
    
    def _create_custom_styles(self):
        """Create custom paragraph styles"""
        
        # Company branding styles
        self.custom_styles['company_name'] = ParagraphStyle(
            name='CompanyName',
            parent=self.base_styles['Heading1'],
            fontSize=InvoiceConfig.FONTS['heading'],
            fontName='Helvetica-Bold',
            textColor=InvoiceConfig.COLORS['primary'],
            alignment=TA_LEFT,
            spaceAfter=InvoiceConfig.SPACING['tight'],
            spaceBefore=0
        )
        
        self.custom_styles['company_info'] = ParagraphStyle(
            name='CompanyInfo',
            parent=self.base_styles['Normal'],
            fontSize=InvoiceConfig.FONTS['small'],
            leading=InvoiceConfig.FONTS['small'] + 2,
            textColor=InvoiceConfig.COLORS['text'],
            alignment=TA_LEFT,
            spaceAfter=0
        )
        
        # Invoice title styles
        self.custom_styles['invoice_title'] = ParagraphStyle(
            name='InvoiceTitle',
            parent=self.base_styles['Heading1'],
            fontSize=InvoiceConfig.FONTS['heading'],
            fontName='Helvetica-Bold',
            textColor=InvoiceConfig.COLORS['text'],
            alignment=TA_RIGHT,
            spaceAfter=0
        )
        
        # Table styles
        self.custom_styles['table_header'] = ParagraphStyle(
            name='TableHeader',
            parent=self.base_styles['Normal'],
            fontSize=InvoiceConfig.FONTS['small'],
            fontName='Helvetica-Bold',
            textColor=InvoiceConfig.COLORS['text'],
            alignment=TA_LEFT
        )
        
        self.custom_styles['table_header_center'] = ParagraphStyle(
            name='TableHeaderCenter',
            parent=self.custom_styles['table_header'],
            alignment=TA_CENTER
        )
        
        self.custom_styles['table_header_right'] = ParagraphStyle(
            name='TableHeaderRight',
            parent=self.custom_styles['table_header'],
            alignment=TA_RIGHT
        )
        
        # Table cell styles
        self.custom_styles['table_cell'] = ParagraphStyle(
            name='TableCell',
            parent=self.base_styles['Normal'],
            fontSize=InvoiceConfig.FONTS['small'],
            textColor=InvoiceConfig.COLORS['text'],
            alignment=TA_LEFT,
            leading=InvoiceConfig.FONTS['small'] + 2
        )
        
        self.custom_styles['table_cell_center'] = ParagraphStyle(
            name='TableCellCenter',
            parent=self.custom_styles['table_cell'],
            alignment=TA_CENTER
        )
        
        self.custom_styles['table_cell_right'] = ParagraphStyle(
            name='TableCellRight',
            parent=self.custom_styles['table_cell'],
            alignment=TA_RIGHT
        )
        
        # Emphasis styles
        self.custom_styles['bold'] = ParagraphStyle(
            name='Bold',
            parent=self.base_styles['Normal'],
            fontSize=InvoiceConfig.FONTS['small'],
            fontName='Helvetica-Bold',
            textColor=InvoiceConfig.COLORS['text']
        )
        
        self.custom_styles['section_header'] = ParagraphStyle(
            name='SectionHeader',
            parent=self.base_styles['Normal'],
            fontSize=InvoiceConfig.FONTS['body'],
            fontName='Helvetica-Bold',
            textColor=InvoiceConfig.COLORS['text'],
            alignment=TA_LEFT,
            spaceAfter=InvoiceConfig.SPACING['line']
        )
        
        # Amount styles
        self.custom_styles['total_amount'] = ParagraphStyle(
            name='TotalAmount',
            parent=self.base_styles['Normal'],
            fontSize=InvoiceConfig.FONTS['title'],
            fontName='Helvetica-Bold',
            textColor=InvoiceConfig.COLORS['primary'],
            alignment=TA_RIGHT
        )
        
        self.custom_styles['amount_large'] = ParagraphStyle(
            name='AmountLarge',
            parent=self.base_styles['Normal'],
            fontSize=InvoiceConfig.FONTS['subheading'],
            fontName='Helvetica-Bold',
            textColor=InvoiceConfig.COLORS['text'],
            alignment=TA_RIGHT
        )
        
        # Footer styles
        self.custom_styles['footer_text'] = ParagraphStyle(
            name='FooterText',
            parent=self.base_styles['Normal'],
            fontSize=InvoiceConfig.FONTS['small'],
            textColor=InvoiceConfig.COLORS['text'],
            alignment=TA_LEFT,
            leading=InvoiceConfig.FONTS['small'] + 2
        )
    
    def get_style(self, style_name):
        """Get a custom style by name"""
        return self.custom_styles.get(style_name, self.base_styles['Normal'])

class InvoiceFormatter:
    """Handles formatting of invoice data"""
    
    @staticmethod
    def format_currency(amount, currency="INR"):
        """Format currency with appropriate symbol and thousand separators"""
        if amount is None:
            amount = 0
        
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            amount = 0
        
        if currency == "INR":
            return f"Rs. {amount:,.2f}"
        elif currency == "USD":
            return f"${amount:,.2f}"
        elif currency == "EUR":
            return f"€{amount:,.2f}"
        else:
            return f"{amount:,.2f} {currency}"
    
    @staticmethod
    def format_date(date_obj):
        """Format date object to string"""
        if date_obj is None:
            return datetime.now().strftime('%d %b, %Y')
        
        if isinstance(date_obj, str):
            try:
                date_obj = datetime.strptime(date_obj, '%Y-%m-%d')
            except ValueError:
                return date_obj
        
        return date_obj.strftime('%d %b, %Y')
    
    @staticmethod
    def safe_get_attr(obj, attr_name, default=""):
        """Safely get attribute from object with default value"""
        return getattr(obj, attr_name, default) or default
    
    @staticmethod
    def format_phone(phone):
        """Format phone number"""
        if not phone:
            return ""
        return str(phone).strip()

class InvoicePDFGenerator:
    """Main class for generating invoice PDFs"""
    
    def __init__(self):
        self.config = InvoiceConfig()
        self.style_manager = InvoiceStyleManager()
        self.formatter = InvoiceFormatter()
        self.doc = None
        self.elements = []
    
    def generate_invoice_pdf(self, invoice, output_path=None):
        """
        Generate a professional tax invoice PDF
        
        Args:
            invoice: Invoice object with all details
            output_path: Path to save the PDF (if None, a temporary file is created)
            
        Returns:
            Path to the generated PDF file
        """
        # Create output path if not provided
        if output_path is None:
            temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
            output_path = temp_file.name
            temp_file.close()
        
        # Initialize document
        self.doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=self.config.LAYOUT['margin'],
            leftMargin=self.config.LAYOUT['margin'],
            topMargin=self.config.LAYOUT['margin'],
            bottomMargin=self.config.LAYOUT['margin']
        )
        
        # Clear elements list
        self.elements = []
        
        # Build invoice sections
        self._build_header()
        self._build_spacer(self.config.SPACING['section'])
        self._build_invoice_info(invoice)
        self._build_spacer(self.config.SPACING['section'])
        self._build_items_table(invoice)
        self._build_spacer(self.config.SPACING['subsection'])
        self._build_totals_section(invoice)
        self._build_spacer(self.config.SPACING['section'])
        self._build_footer()
        
        # Generate PDF
        self.doc.build(self.elements)
        
        return output_path
    
    def _build_header(self):
        """Build the header section with logo and company info"""
        # Try to load logo
        logo_path = self._get_logo_path()
        logo_element = self._create_logo_element(logo_path)
        
        # Company address
        company_address = [
            "Plot No-17, Incuspaze, Sector-18",
            "Gurugram, Haryana - 122001, India",
            "TAX ID: 06AAACM0568Q1ZS",
            "",
            "www.mantarav.com",
            "finance@exmyb.com",
            "+91 8887102246"
        ]
        
        company_info_text = "<br/>".join(company_address)
        company_info = Paragraph(company_info_text, self.style_manager.get_style('company_info'))
        
        # Create header table
        header_data = [
            [logo_element, '', company_info]
        ]
        
        header_table = Table(
            header_data, 
            colWidths=[self.doc.width * 0.3, self.doc.width * 0.3, self.doc.width * 0.4]
        )
        
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        self.elements.append(header_table)
    
    def _build_invoice_info(self, invoice):
        """Build the invoice information section"""
        # Handle both dictionary and object formats
        if isinstance(invoice, dict):
            # Dictionary format (from email_sender)
            invoice_date = self.formatter.format_date(invoice.get('issue_date'))
            total_amount = self.formatter.format_currency(
                invoice.get('total_amount', 0), 
                invoice.get('currency', 'USD')
            )
            
            # Client information
            client_info = invoice.get('client_info', {})
            client_name = client_info.get('name', 'Client Name')
            client_address = client_info.get('address', '')
            client_email = client_info.get('email', '')
            client_phone = ''
            client_location = ''
            
            # Invoice details
            invoice_number = invoice.get('invoice_number', '001')
            
        else:
            # Object format (backward compatibility)
            invoice_date = self.formatter.format_date(getattr(invoice, 'issue_date', None))
            total_amount = self.formatter.format_currency(
                getattr(invoice, 'total', 0), 
                getattr(invoice, 'currency', 'INR')
            )
            
            # Client information
            client_name = self.formatter.safe_get_attr(invoice, 'client_name', 'Client Name')
            client_address = self.formatter.safe_get_attr(invoice, 'client_address', '')
            client_city = self.formatter.safe_get_attr(invoice, 'client_city', '')
            client_country = self.formatter.safe_get_attr(invoice, 'client_country', '')
            client_postal = self.formatter.safe_get_attr(invoice, 'client_postal_code', '')
            client_phone = self.formatter.format_phone(getattr(invoice, 'client_phone', ''))
            client_email = getattr(invoice, 'client_email', '')
            
            # Build client address
            client_location = f"{client_city}, {client_country} - {client_postal}".strip(' ,-')
            
            # Invoice details
            invoice_number = self.formatter.safe_get_attr(invoice, 'invoice_number', '001')
        
        # Create invoice info table
        invoice_info_data = [
            [
                Paragraph("<b>Billed to</b>", self.style_manager.get_style('section_header')),
                Paragraph("<b>Invoice number</b>", self.style_manager.get_style('section_header')),
                Paragraph("<b>Total Amount</b>", self.style_manager.get_style('section_header'))
            ],
            [
                Paragraph(f"<b>{client_name}</b>", self.style_manager.get_style('bold')),
                Paragraph(f"#{invoice_number}", self.style_manager.get_style('table_cell')),
                Paragraph(f'<font color="{self.config.COLORS["primary"]}" size="16"><b>{total_amount}</b></font>', 
                         self.style_manager.get_style('table_cell_right'))
            ],
            [
                Paragraph(client_email if client_email else client_address, self.style_manager.get_style('table_cell')),
                Paragraph("<b>Reference</b>", self.style_manager.get_style('section_header')),
                ''
            ],
            [
                Paragraph(client_location if client_location else client_address, self.style_manager.get_style('table_cell')),
                Paragraph(f"INV-{invoice_number}", self.style_manager.get_style('table_cell')),
                ''
            ],
            [
                Paragraph(client_phone, self.style_manager.get_style('table_cell')),
                Paragraph("<b>Invoice date</b>", self.style_manager.get_style('section_header')),
                ''
            ],
            [
                Paragraph("<b>Subject</b>", self.style_manager.get_style('section_header')),
                Paragraph(invoice_date, self.style_manager.get_style('table_cell')),
                ''
            ],
            [
                Paragraph("Plan Subscription Services" if isinstance(invoice, dict) else "Professional Services", self.style_manager.get_style('table_cell')),
                '',
                ''
            ]
        ]
        
        invoice_info_table = Table(
            invoice_info_data,
            colWidths=[self.doc.width * 0.4, self.doc.width * 0.3, self.doc.width * 0.3]
        )
        
        invoice_info_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), self.config.LAYOUT['table_padding']),
            ('BOTTOMPADDING', (0, 0), (-1, -1), self.config.LAYOUT['table_padding']),
            ('LEFTPADDING', (0, 0), (-1, -1), self.config.LAYOUT['table_padding']),
            ('RIGHTPADDING', (0, 0), (-1, -1), self.config.LAYOUT['table_padding']),
            ('BOX', (0, 0), (-1, -1), 0.5, self.config.COLORS['border']),
        ]))
        
        self.elements.append(invoice_info_table)
    
    def _build_items_table(self, invoice):
        """Build the items table"""
        # Table headers
        headers = [
            Paragraph("<b>ITEM DETAIL</b>", self.style_manager.get_style('table_header')),
            Paragraph("<b>QTY</b>", self.style_manager.get_style('table_header_center')),
            Paragraph("<b>RATE</b>", self.style_manager.get_style('table_header_right')),
            Paragraph("<b>AMOUNT</b>", self.style_manager.get_style('table_header_right'))
        ]
        
        # Table data
        table_data = [headers]
        
        # Handle both dictionary and object formats
        if isinstance(invoice, dict):
            # Dictionary format
            items = invoice.get('items', [])
            if items:
                for item in items:
                    item_name = item.get('name', 'Service')
                    item_description = item.get('description', '')
                    item_quantity = item.get('quantity', 1)
                    item_rate = item.get('unit_price', 0)
                    item_amount = item.get('total_price', item_quantity * item_rate)
                    
                    # Format item detail
                    item_detail = f"<b>{item_name}</b>"
                    if item_description:
                        item_detail += f"<br/>{item_description}"
                    
                    table_data.append([
                        Paragraph(item_detail, self.style_manager.get_style('table_cell')),
                        Paragraph(str(item_quantity), self.style_manager.get_style('table_cell_center')),
                        Paragraph(f"{item_rate:,.2f}", self.style_manager.get_style('table_cell_right')),
                        Paragraph(f"{item_amount:,.2f}", self.style_manager.get_style('table_cell_right'))
                    ])
            else:
                # Default item for dictionary format
                subtotal = invoice.get('total_amount', 0)
                table_data.append([
                    Paragraph("<b>Plan Subscription</b><br/>Pro Plan subscription service", 
                             self.style_manager.get_style('table_cell')),
                    Paragraph("1", self.style_manager.get_style('table_cell_center')),
                    Paragraph(f"{subtotal:,.2f}", self.style_manager.get_style('table_cell_right')),
                    Paragraph(f"{subtotal:,.2f}", self.style_manager.get_style('table_cell_right'))
                ])
        else:
            # Object format (backward compatibility)
            if hasattr(invoice, 'invoice_items') and invoice.invoice_items:
                for item in invoice.invoice_items:
                    item_name = self.formatter.safe_get_attr(item, 'name', 'Service')
                    item_description = self.formatter.safe_get_attr(item, 'description', '')
                    item_quantity = getattr(item, 'quantity', 1)
                    item_rate = getattr(item, 'unit_price', 0)
                    item_amount = item_quantity * item_rate
                    
                    # Format item detail
                    item_detail = f"<b>{item_name}</b>"
                    if item_description:
                        item_detail += f"<br/>{item_description}"
                    
                    table_data.append([
                        Paragraph(item_detail, self.style_manager.get_style('table_cell')),
                        Paragraph(str(item_quantity), self.style_manager.get_style('table_cell_center')),
                        Paragraph(f"{item_rate:,.2f}", self.style_manager.get_style('table_cell_right')),
                        Paragraph(f"{item_amount:,.2f}", self.style_manager.get_style('table_cell_right'))
                    ])
            else:
                # Default item for object format
                subtotal = getattr(invoice, 'subtotal', 0)
                table_data.append([
                    Paragraph("<b>Professional Services</b><br/>Consultation and service delivery", 
                             self.style_manager.get_style('table_cell')),
                    Paragraph("1", self.style_manager.get_style('table_cell_center')),
                    Paragraph(f"{subtotal:,.2f}", self.style_manager.get_style('table_cell_right')),
                    Paragraph(f"{subtotal:,.2f}", self.style_manager.get_style('table_cell_right'))
                ])
        
        # Create table
        col_widths = [self.doc.width * 0.5, self.doc.width * 0.15, self.doc.width * 0.175, self.doc.width * 0.175]
        items_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.config.COLORS['light_gray']),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('ALIGN', (2, 0), (3, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), self.config.FONTS['small']),
            ('TOPPADDING', (0, 0), (-1, -1), self.config.LAYOUT['table_padding'] + 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), self.config.LAYOUT['table_padding'] + 2),
            ('LEFTPADDING', (0, 0), (-1, -1), self.config.LAYOUT['table_padding']),
            ('RIGHTPADDING', (0, 0), (-1, -1), self.config.LAYOUT['table_padding']),
            ('GRID', (0, 0), (-1, -1), 0.5, self.config.COLORS['border']),
        ]))
        
        self.elements.append(items_table)
    
    def _build_totals_section(self, invoice):
        """Build the totals calculation section"""
        # Handle both dictionary and object formats
        if isinstance(invoice, dict):
            # Dictionary format
            total = invoice.get('total_amount', 0)
            subtotal = total  # For plans, usually no separate subtotal
            tax_rate = invoice.get('tax_rate', 0)  # Plans usually don't have tax
            tax_amount = invoice.get('tax_amount', 0)
            currency = invoice.get('currency', 'USD')
        else:
            # Object format (backward compatibility)
            subtotal = getattr(invoice, 'subtotal', 0) or 0
            tax_rate = getattr(invoice, 'tax_rate', 18) or 18
            tax_amount = getattr(invoice, 'tax_amount', None) or (subtotal * tax_rate / 100)
            total = getattr(invoice, 'total', None) or (subtotal + tax_amount)
            currency = getattr(invoice, 'currency', 'INR')
        
        # Build totals data
        totals_data = [
            ['', Paragraph("<b>Subtotal</b>", self.style_manager.get_style('table_cell_right')),
             Paragraph(self.formatter.format_currency(subtotal, currency), self.style_manager.get_style('table_cell_right'))],
            ['', Paragraph(f"<b>Tax ({tax_rate}%)</b>", self.style_manager.get_style('table_cell_right')),
             Paragraph(self.formatter.format_currency(tax_amount, currency), self.style_manager.get_style('table_cell_right'))],
            ['', Paragraph("<b>Total</b>", self.style_manager.get_style('amount_large')),
             Paragraph(f"<b>{self.formatter.format_currency(total, currency)}</b>", self.style_manager.get_style('amount_large'))]
        ]
        
        # Add payment information if available
        if hasattr(invoice, 'amount_paid') and getattr(invoice, 'amount_paid') is not None:
            amount_paid = getattr(invoice, 'amount_paid', 0)
            totals_data.append([
                '', Paragraph("<b>Payment Made</b>", self.style_manager.get_style('table_cell_right')),
                Paragraph(f"<b>(-) {self.formatter.format_currency(amount_paid, currency)}</b>", 
                         self.style_manager.get_style('table_cell_right'))
            ])
            
            # Withholding tax if applicable
            withholding_tax = getattr(invoice, 'withholding_tax_amount', 0) or 0
            if withholding_tax > 0:
                totals_data.append([
                    '', Paragraph("<b>Amount Withheld</b>", self.style_manager.get_style('table_cell_right')),
                    Paragraph(f"<b>(-) {self.formatter.format_currency(withholding_tax, currency)}</b>", 
                             self.style_manager.get_style('table_cell_right'))
                ])
            
            # Balance due
            amount_due = getattr(invoice, 'amount_due', None) or (total - amount_paid - withholding_tax)
            totals_data.append([
                '', Paragraph("<b>Balance Due</b>", self.style_manager.get_style('amount_large')),
                Paragraph(f"<b>{self.formatter.format_currency(amount_due, currency)}</b>", 
                         self.style_manager.get_style('amount_large'))
            ])
        
        # Create totals table
        totals_table = Table(
            totals_data,
            colWidths=[self.doc.width * 0.65, self.doc.width * 0.175, self.doc.width * 0.175]
        )
        
        totals_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (2, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), self.config.LAYOUT['table_padding']),
            ('BOTTOMPADDING', (0, 0), (-1, -1), self.config.LAYOUT['table_padding']),
            ('LINEBELOW', (1, -2), (2, -2), 1, self.config.COLORS['border']),
        ]))
        
        self.elements.append(totals_table)
    
    def _build_footer(self):
        """Build the footer section"""
        # Thank you note
        thank_you = Paragraph("Thank you for your business!", self.style_manager.get_style('footer_text'))
        self.elements.append(thank_you)
        self._build_spacer(self.config.SPACING['section'])
        
        # Terms and conditions
        terms_title = Paragraph("<b>Terms & Conditions</b>", self.style_manager.get_style('section_header'))
        self.elements.append(terms_title)
        
        # Bank details
        bank_details = [
            "Payment should be made within 30 days of invoice date.",
            "",
            "<b>Bank Details:</b>",
            "Account Name: Mantarav Private Limited",
            "Account Number: 184305001267",
            "IFSC Code: ICIC0001843",
            "Bank Branch: Nirvana Country"
        ]
        
        bank_info = Paragraph("<br/>".join(bank_details), self.style_manager.get_style('footer_text'))
        self.elements.append(bank_info)
    
    def _build_spacer(self, height):
        """Add a spacer element"""
        self.elements.append(Spacer(1, height))
    
    def _get_logo_path(self):
        """Get the path to the logo file"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(current_dir, "Rayo_Logo.png")
        return logo_path if os.path.exists(logo_path) else None
    
    def _create_logo_element(self, logo_path):
        """Create logo element with fallback"""
        if logo_path and os.path.exists(logo_path):
            try:
                return Image(logo_path, 
                           width=self.config.LAYOUT['logo_width'], 
                           height=self.config.LAYOUT['logo_height'])
            except Exception:
                pass
        
        # Fallback to text logo
        logo_text = f'<font color="{self.config.COLORS["primary"]}" size="24"><b>RAYO</b></font>'
        return Paragraph(logo_text, self.style_manager.get_style('company_name'))

# Plan-specific functions
def generate_plan_invoice_pdf(invoice, output_path=None):
    """
    Generate a professional plan invoice PDF
    
    Args:
        invoice: Invoice object with all details
        output_path: Path to save the PDF (if None, a temporary file is created)
        
    Returns:
        Path to the generated PDF file
    """
    generator = InvoicePDFGenerator()
    return generator.generate_invoice_pdf(invoice, output_path)

# Alias for backward compatibility
def generate_invoice_pdf(invoice, output_path=None):
    """Alias for generate_plan_invoice_pdf"""
    return generate_plan_invoice_pdf(invoice, output_path)

# Number to words converter for Indian currency
def num_to_words(num):
    """Convert number to words for Indian currency format"""
    if num == 0:
        return "Zero"
    
    units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
    teens = ["", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", 
             "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "Ten", "Twenty", "Thirty", "Forty", "Fifty", 
            "Sixty", "Seventy", "Eighty", "Ninety"]
    
    def convert_less_than_thousand(n):
        if n == 0:
            return ""
        elif n < 10:
            return units[n]
        elif n == 10:
            return "Ten"
        elif 10 < n < 20:
            return teens[n - 10]
        elif n < 100:
            return tens[n // 10] + ("" if n % 10 == 0 else " " + units[n % 10])
        else:
            return units[n // 100] + " Hundred" + ("" if n % 100 == 0 else " " + convert_less_than_thousand(n % 100))
    
    # Handle decimals
    num_str = f"{num:.2f}"
    whole, decimal = num_str.split('.')
    whole = int(whole)
    
    result = ""
    
    # Convert crores (10 million)
    if whole >= 10000000:
        crores = whole // 10000000
        result += convert_less_than_thousand(crores) + " Crore "
        whole %= 10000000
    
    # Convert lakhs (100 thousand)
    if whole >= 100000:
        lakhs = whole // 100000
        result += convert_less_than_thousand(lakhs) + " Lakh "
        whole %= 100000
    
    # Convert thousands
    if whole >= 1000:
        thousands = whole // 1000
        result += convert_less_than_thousand(thousands) + " Thousand "
        whole %= 1000
    
    # Convert remaining
    if whole > 0:
        result += convert_less_than_thousand(whole)
    
    return result.strip() + " Only" if result.strip() else "Zero Only"

# Example usage and testing
if __name__ == "__main__":
    # Example invoice data structure
    class MockInvoice:
        def __init__(self):
            self.invoice_number = "INV-2024-001"
            self.issue_date = datetime.now()
            self.due_date = datetime.now()
            self.client_name = "Test Client Ltd."
            self.client_address = "123 Business Street"
            self.client_city = "Mumbai"
            self.client_country = "India"
            self.client_postal_code = "400001"
            self.client_phone = "+91 9876543210"
            self.subtotal = 10000.00
            self.tax_rate = 18.0
            self.tax_amount = 1800.00
            self.total = 11800.00
            self.currency = "INR"
            self.invoice_items = []
    
    # Test the generator
    mock_invoice = MockInvoice()
    pdf_path = generate_invoice_pdf(mock_invoice)
    print(f"Test PDF generated at: {pdf_path}")
