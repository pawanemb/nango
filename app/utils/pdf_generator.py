"""PDF Generation utilities"""
import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.linecharts import HorizontalLineChart

def format_number(num):
    """Format numbers for better readability"""
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    elif num >= 1000:
        return f"{num/1000:.1f}K"
    return str(num)

def create_pie_chart(data, title):
    """Create a pie chart for device or country distribution"""
    drawing = Drawing(400, 200)
    pie = Pie()
    pie.x = 150
    pie.y = 50
    pie.width = 100
    pie.height = 100
    
    # Data for pie chart
    pie.data = [item['impressions'] for item in data['breakdown']]
    pie.labels = [item['key'] for item in data['breakdown']]
    
    # Add pie chart to the drawing
    drawing.add(pie)
    return drawing

def generate_gsc_pdf(report_data):
    """Generate a PDF report from GSC data"""
    # Create reports directory if it doesn't exist
    reports_dir = os.path.join(os.getcwd(), 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    
    # Generate unique filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = os.path.join(reports_dir, f'gsc_report_{timestamp}.pdf')
    
    # Create the PDF document
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30
    )
    story.append(Paragraph(f"GSC Report - {report_data['site_url']}", title))
    
    # Date Range
    date_range = ParagraphStyle(
        'DateRange',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=20
    )
    story.append(Paragraph(
        f"Period: {report_data['date_range']['start_date']} to {report_data['date_range']['end_date']}",
        date_range
    ))
    story.append(Spacer(1, 20))
    
    # Summary Section
    story.append(Paragraph("Performance Summary", styles['Heading2']))
    summary_data = [
        ['Metric', 'Current', 'Previous', 'Change'],
        ['Impressions', 
         format_number(report_data['summary']['current']['impressions']),
         format_number(report_data['summary']['previous']['impressions']),
         f"{report_data['summary']['changes']['impressions_change']}%"],
        ['Clicks',
         format_number(report_data['summary']['current']['clicks']),
         format_number(report_data['summary']['previous']['clicks']),
         f"{report_data['summary']['changes']['clicks_change']}%"],
        ['CTR',
         f"{report_data['summary']['current']['ctr']:.2f}%",
         f"{report_data['summary']['previous']['ctr']:.2f}%",
         f"{report_data['summary']['changes']['ctr_change']}%"],
        ['Position',
         f"{report_data['summary']['current']['position']:.1f}",
         f"{report_data['summary']['previous']['position']:.1f}",
         f"{report_data['summary']['changes']['position_change']}%"]
    ]
    
    t = Table(summary_data, colWidths=[2*inch, 1.5*inch, 1.5*inch, 1.5*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(t)
    story.append(Spacer(1, 20))
    
    # Ranking Distribution
    story.append(Paragraph("Ranking Distribution", styles['Heading2']))
    ranking_data = [['Position Range', 'Number of Pages']]
    for item in report_data['ranking']['ranking_distribution']:
        ranking_data.append([item['range'], format_number(item['count'])])
    
    t = Table(ranking_data, colWidths=[3*inch, 3*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(t)
    story.append(Spacer(1, 20))
    
    # Device Distribution
    story.append(Paragraph("Device Distribution", styles['Heading2']))
    story.append(create_pie_chart(report_data['devices'], "Device Distribution"))
    story.append(Spacer(1, 20))
    
    # Top Pages
    story.append(Paragraph("Top Performing Pages", styles['Heading2']))
    pages_data = [['Page', 'Impressions', 'Clicks', 'CTR', 'Position']]
    for page in report_data['top_pages']['pages'][:10]:  # Top 10 pages
        pages_data.append([
            page['page'],
            format_number(page['impressions']),
            format_number(page['clicks']),
            f"{page['ctr']:.2f}%",
            f"{page['position']:.1f}"
        ])
    
    t = Table(pages_data, colWidths=[3*inch, 1*inch, 1*inch, 1*inch, 1*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('WORDWRAP', (0, 0), (-1, -1), True)
    ]))
    story.append(t)
    
    # Build PDF
    doc.build(story)
    return filename
