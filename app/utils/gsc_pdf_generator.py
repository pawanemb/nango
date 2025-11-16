from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, Flowable
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.lib.colors import HexColor
import plotly.graph_objects as go
import plotly.io as pio
from datetime import datetime
import io
from plotly.subplots import make_subplots

# Configure plotly for static image export
pio.kaleido.scope.default_width = 800
pio.kaleido.scope.default_height = 400

class MetricsCard(Flowable):
    """A custom flowable to create a modern metrics card"""
    def __init__(self, label, value, change, subtitle="", width=140, height=90):
        Flowable.__init__(self)
        self.label = label
        self.value = value
        self.change = change
        self.subtitle = subtitle
        self.width = width
        self.height = height

    def _get_fitting_font_size(self, text, max_width, base_font_size, font_name='Helvetica-Bold'):
        """Dynamically calculate font size to fit text within width"""
        size = base_font_size
        while size > 8:  # Don't go smaller than 8pt
            width = self.canv.stringWidth(str(text), font_name, size)
            if width <= max_width:
                break
            size -= 1
        return size

    def draw(self):
        # Draw card background with enhanced shadow effect
        self.canv.saveState()
        
        # Multiple layered shadows for depth
        shadow_colors = ['#00000008', '#00000010']
        shadow_offsets = [2, 1]  # Reduced shadow offsets
        for color, offset in zip(shadow_colors, shadow_offsets):
            self.canv.setFillColor(HexColor(color))
            self.canv.roundRect(offset, 0, self.width, self.height-offset, 6, stroke=0, fill=1)
        
        # Card background with subtle border
        self.canv.setFillColor(HexColor('#ffffff'))
        self.canv.setStrokeColor(HexColor('#f1f5f9'))
        self.canv.roundRect(0, 1, self.width, self.height, 6, stroke=1, fill=1)
        
        # Calculate available width for text
        available_width = self.width - 20  # 10px padding on each side
        
        # Draw label with improved typography
        self.canv.setFont('Helvetica-Bold', 10)
        self.canv.setFillColor(HexColor('#64748b'))
        self.canv.drawString(10, self.height - 20, self.label)
        
        # Draw value with dynamic sizing
        value_str = str(self.value)
        value_font_size = self._get_fitting_font_size(value_str, available_width, 22)
        self.canv.setFont('Helvetica-Bold', value_font_size)
        self.canv.setFillColor(HexColor('#0f172a'))
        value_width = self.canv.stringWidth(value_str, 'Helvetica-Bold', value_font_size)
        self.canv.drawString(10, self.height - 45, value_str)
        
        # Draw subtitle if present with improved spacing
        if self.subtitle:
            self.canv.setFont('Helvetica', 8)
            self.canv.setFillColor(HexColor('#94a3b8'))
            self.canv.drawString(10, self.height - 65, self.subtitle)
        
        # Draw change indicator with modern styling
        if self.change:
            change_value = float(self.change.strip('%'))
            arrow = '↑' if change_value >= 0 else '↓'
            change_color = HexColor('#10b981') if change_value >= 0 else HexColor('#ef4444')
            
            # Background pill for change indicator
            pill_text = f"{arrow} {abs(change_value)}%"
            pill_width = self.canv.stringWidth(pill_text, 'Helvetica-Bold', 9) + 10
            pill_height = 16
            pill_bg_color = HexColor('#f0fdf4') if change_value >= 0 else HexColor('#fef2f2')
            
            self.canv.setFillColor(pill_bg_color)
            self.canv.roundRect(10, 8, pill_width, pill_height, 8, stroke=0, fill=1)
            
            self.canv.setFont('Helvetica-Bold', 9)
            self.canv.setFillColor(change_color)
            self.canv.drawString(14, 13, pill_text)
        
        self.canv.restoreState()

class GSCPDFGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.custom_styles = self._create_custom_styles()
        
    def _create_custom_styles(self):
        """Create custom paragraph styles for the report"""
        custom_styles = {
            'Title': ParagraphStyle(
                'CustomTitle',
                parent=self.styles['Title'],
                fontSize=20,  
                spaceAfter=15,  
                textColor=HexColor('#111827'),
                fontName='Helvetica-Bold'
            ),
            'Subtitle': ParagraphStyle(
                'CustomSubtitle',
                parent=self.styles['Normal'],
                fontSize=12,  
                spaceAfter=10,  
                textColor=HexColor('#6b7280'),
                fontName='Helvetica'
            ),
            'SectionTitle': ParagraphStyle(
                'CustomSectionTitle',
                parent=self.styles['Heading1'],
                fontSize=16,  
                spaceAfter=8,  
                textColor=HexColor('#111827'),
                fontName='Helvetica-Bold'
            ),
            'FilterButton': ParagraphStyle(
                'FilterButton',
                parent=self.styles['Normal'],
                fontSize=10,  
                textColor=HexColor('#6b7280'),
                fontName='Helvetica',
                borderColor=HexColor('#e5e7eb'),
                borderWidth=1,
                borderPadding=6,
                borderRadius=4  
            )
        }
        return custom_styles

    def _create_metrics_section(self, metrics_data):
        """Create the metrics cards section with modern styling"""
        # Create metrics cards with real data
        cards = [
            [
                MetricsCard(
                    'Domain Authority',
                    metrics_data.get('domain_authority', '90'),
                    '',  # No change value
                    ''   # No subtitle
                ),
                MetricsCard(
                    'Impressions',
                    f"{metrics_data.get('impressions', 11024):,}",
                    metrics_data.get('impressions_change', '+15.2%'),
                    'vs. previous period'
                ),
                MetricsCard(
                    'Click Rate',
                    f"{metrics_data.get('ctr', 3.2)}%",
                    metrics_data.get('ctr_change', '-2.1%'),
                    'vs. previous period'
                ),
                MetricsCard(
                    'Avg Position',
                    metrics_data.get('avg_position', '12.4'),
                    metrics_data.get('position_change', '+8.3%'),
                    'vs. previous period'
                )
            ]
        ]
        
        # Create table with improved spacing
        table = Table(
            cards,
            colWidths=[145] * 4,  
            rowHeights=[95],  
            spaceBefore=10,
            spaceAfter=15
        )
        
        # Add modern table styling
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ]))
        
        return table

    def _create_time_series_chart(self, time_series_data):
        """Create modern time series chart with the exact style from the image"""
        fig = go.Figure()
        
        # Add main trace with gradient fill
        fig.add_trace(go.Scatter(
            x=time_series_data['dates'],
            y=time_series_data['impressions'],
            name='Impressions',
            line=dict(
                color='rgb(79, 70, 229)',  
                width=2.5,
                shape='linear'  
            ),
            mode='lines',
            fill='tonexty',
            fillcolor='rgba(79, 70, 229, 0.08)'  
        ))
        
        # Add hover template
        fig.update_traces(
            hovertemplate='<b>%{y:,.0f}</b> impressions<br>%{x}<extra></extra>',
            hoverlabel=dict(
                bgcolor='white',
                bordercolor='rgb(226, 232, 240)',  
                font=dict(size=12, color='rgb(51, 65, 85)')  
            )
        )
        
        # Improved layout with better spacing
        fig.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=50, r=50, t=30, b=50),  
            showlegend=False,
            width=700,  
            height=300,  
            xaxis=dict(
                showgrid=True,
                gridcolor='rgb(241, 245, 249)',  
                gridwidth=1,
                tickfont=dict(
                    family='Helvetica',
                    color='rgb(100, 116, 139)',  
                    size=10
                ),
                zeroline=False,
                showline=True,
                linecolor='rgb(241, 245, 249)',  
                linewidth=1,
                nticks=8,  
                tickangle=0
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgb(241, 245, 249)',  
                gridwidth=1,
                tickfont=dict(
                    family='Helvetica',
                    color='rgb(100, 116, 139)',  
                    size=10
                ),
                tickformat=',d',  
                zeroline=False,
                showline=True,
                linecolor='rgb(241, 245, 249)',  
                linewidth=1,
                rangemode='tozero'  
            )
        )
        
        # Remove filter buttons to save space
        
        # Save to PNG with high DPI for crisp rendering
        img_bytes = pio.to_image(fig, format='png', scale=2)
        
        # Create Image with specific width to fit PDF
        return Image(io.BytesIO(img_bytes), width=6.5*inch, height=3*inch)

    
    def _create_time_series_chart_click(self, time_series_data):
        """Create modern time series chart with the exact style from the image"""
        fig = go.Figure()
        
        # Add main trace with gradient fill
        fig.add_trace(go.Scatter(
            x=time_series_data['dates'],
            y=time_series_data['clicks'],
            name='Clicks',
            line=dict(
                color='rgb(79, 70, 229)',  
                width=2.5,
                shape='linear'  
            ),
            mode='lines',
            fill='tonexty',
            fillcolor='rgba(79, 70, 229, 0.08)'  
        ))
        
        # Add hover template
        fig.update_traces(
            hovertemplate='<b>%{y:,.0f}</b> clicks<br>%{x}<extra></extra>',
            hoverlabel=dict(
                bgcolor='white',
                bordercolor='rgb(226, 232, 240)',  
                font=dict(size=12, color='rgb(51, 65, 85)')  
            )
        )
        
        # Improved layout with tighter spacing
        fig.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=30, r=20, t=20, b=30),  # Reduced margins
            showlegend=False,
            width=700,  
            height=250,  # Slightly reduced height
            xaxis=dict(
                showgrid=True,
                gridcolor='rgb(241, 245, 249)',  
                gridwidth=1,
                tickfont=dict(
                    family='Helvetica',
                    color='rgb(100, 116, 139)',  
                    size=10
                ),
                zeroline=False,
                showline=True,
                linecolor='rgb(241, 245, 249)',  
                linewidth=1,
                nticks=6,  # Reduced number of ticks
                tickangle=0,
                automargin=True  # Automatically adjust margins
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgb(241, 245, 249)',  
                gridwidth=1,
                tickfont=dict(
                    family='Helvetica',
                    color='rgb(100, 116, 139)',  
                    size=10
                ),
                tickformat=',d',  
                zeroline=False,
                showline=True,
                linecolor='rgb(241, 245, 249)',  
                linewidth=1,
                rangemode='tozero',
                automargin=True  # Automatically adjust margins
            )
        )
        
        # Save to PNG with high DPI for crisp rendering
        img_bytes = pio.to_image(fig, format='png', scale=2)
        
        # Create Image with adjusted width to fit PDF
        return Image(io.BytesIO(img_bytes), width=6.5*inch, height=2.5*inch)  # Reduced height

    def _create_time_series_chart_ctr(self, time_series_data):
        """Create modern time series chart for CTR with the same style as clicks"""
        fig = go.Figure()
        
        # Calculate CTR values
        ctr_values = []
        for clicks, impressions in zip(time_series_data['clicks'], time_series_data['impressions']):
            if impressions > 0:
                ctr = (clicks / impressions) * 100
            else:
                ctr = 0
            ctr_values.append(ctr)
        
        # Add main trace with gradient fill
        fig.add_trace(go.Scatter(
            x=time_series_data['dates'],
            y=ctr_values,
            name='CTR',
            line=dict(
                color='rgb(79, 70, 229)',  
                width=2.5,
                shape='linear'  
            ),
            mode='lines',
            fill='tonexty',
            fillcolor='rgba(79, 70, 229, 0.08)'  
        ))
        
        # Add hover template
        fig.update_traces(
            hovertemplate='<b>%{y:.2f}%</b> CTR<br>%{x}<extra></extra>',
            hoverlabel=dict(
                bgcolor='white',
                bordercolor='rgb(226, 232, 240)',  
                font=dict(size=12, color='rgb(51, 65, 85)')  
            )
        )
        
        # Improved layout with tighter spacing
        fig.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=30, r=20, t=20, b=30),  # Reduced margins
            showlegend=False,
            width=700,  
            height=250,  # Slightly reduced height
            xaxis=dict(
                showgrid=True,
                gridcolor='rgb(241, 245, 249)',  
                gridwidth=1,
                tickfont=dict(
                    family='Helvetica',
                    color='rgb(100, 116, 139)',  
                    size=10
                ),
                zeroline=False,
                showline=True,
                linecolor='rgb(241, 245, 249)',  
                linewidth=1,
                nticks=6,  
                tickangle=0,
                automargin=True
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgb(241, 245, 249)',  
                gridwidth=1,
                tickfont=dict(
                    family='Helvetica',
                    color='rgb(100, 116, 139)',  
                    size=10
                ),
                tickformat='.2f',  # Format for percentage
                ticksuffix='%',    # Add % symbol
                zeroline=False,
                showline=True,
                linecolor='rgb(241, 245, 249)',  
                linewidth=1,
                rangemode='tozero',
                automargin=True
            )
        )
        
        # Save to PNG with high DPI for crisp rendering
        img_bytes = pio.to_image(fig, format='png', scale=2)
        
        # Create Image with adjusted width to fit PDF
        return Image(io.BytesIO(img_bytes), width=6.5*inch, height=2.5*inch)

    def _create_clicks_chart(self, time_series_data):
        """Create clicks chart with modern styling"""
        fig = go.Figure()
        
        # Add main trace with bar chart
        fig.add_trace(go.Bar(
            x=time_series_data['dates'],
            y=time_series_data['clicks'],
            name='Clicks',
            marker_color='rgb(249, 115, 22)',  # Orange-500
            opacity=0.9,
            width=0.6  # Make bars slightly thinner
        ))
        
        # Add filter buttons at top
        buttons = ['Geography', 'Search Appearance', 'Device', 'This week']
        button_annotations = []
        for i, button_text in enumerate(buttons):
            x_pos = 0.2 + (i * 0.2)  # Spread buttons across top
            button_annotations.append(
                dict(
                    x=x_pos,
                    y=1.15,
                    xref='paper',
                    yref='paper',
                    text=f'<span style="color: rgb(71, 85, 105); padding: 6px 12px; border: 1px solid rgb(226, 232, 240); border-radius: 6px; font-size: 12px;">☐ {button_text}</span>',
                    showarrow=False,
                    font=dict(family='Helvetica'),
                    xanchor='center',
                    yanchor='middle'
                )
            )
        
        # Add hover template
        fig.update_traces(
            hovertemplate='<b>%{y:,.0f}</b> clicks<br>%{x}<extra></extra>',
            hoverlabel=dict(
                bgcolor='white',
                bordercolor='rgb(226, 232, 240)',
                font=dict(size=12, color='rgb(51, 65, 85)')
            )
        )
        
        # Calculate y-axis range based on data
        max_clicks = max(time_series_data['clicks']) if time_series_data['clicks'] else 1200
        y_max = max(1200, max_clicks * 1.2)  # At least 1200 or 20% above max
        
        # Modern layout
        fig.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=50, r=50, t=60, b=50),  # Increased top margin for buttons
            showlegend=False,
            width=700,
            height=350,  # Increased height to accommodate buttons
            annotations=button_annotations,
            xaxis=dict(
                showgrid=True,
                gridcolor='rgb(241, 245, 249)',
                gridwidth=1,
                tickfont=dict(
                    family='Helvetica',
                    color='rgb(100, 116, 139)',
                    size=10
                ),
                zeroline=False,
                showline=True,
                linecolor='rgb(241, 245, 249)',
                linewidth=1,
                nticks=12,  # Show all months
                tickangle=0,
                tickmode='array',
                ticktext=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
                tickvals=list(range(12))
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgb(241, 245, 249)',
                gridwidth=1,
                tickfont=dict(
                    family='Helvetica',
                    color='rgb(100, 116, 139)',
                    size=10
                ),
                tickformat=',d',
                zeroline=False,
                showline=True,
                linecolor='rgb(241, 245, 249)',
                linewidth=1,
                rangemode='nonnegative',  # Only show positive values
                range=[0, y_max],  # Dynamic range based on data
                dtick=400  # Show ticks at intervals of 400
            )
        )
        
        # Save to PNG with high DPI for crisp rendering
        img_bytes = pio.to_image(fig, format='png', scale=2)
        return Image(io.BytesIO(img_bytes), width=6.5*inch, height=3.5*inch)

    def _create_pages_donut(self, pages_data):
        """Create pages donut chart with modern styling"""
        fig = go.Figure()
        
        # Add donut chart
        fig.add_trace(go.Pie(
            values=[pages_data['indexed'], pages_data['not_indexed']],
            labels=['Indexed', 'Not indexed'],
            hole=0.85,  # Larger hole for thinner donut
            marker=dict(
                colors=['rgb(34, 197, 94)', 'rgb(249, 115, 22)'],  # Green-500, Orange-500
                line=dict(color='white', width=1)
            ),
            textinfo='none',
            hovertemplate="<b>%{label}</b><br>%{value:,d} pages<extra></extra>"
        ))
        
        # Add center text
        fig.add_annotation(
            text=f"{pages_data['total']}<br><span style='font-size: 14px'>Pages</span>",
            x=0.5, y=0.5,
            font=dict(
                size=24,
                family='Helvetica-Bold',
                color='rgb(17, 24, 39)'
            ),
            showarrow=False,
            xanchor='center',
            yanchor='middle'
        )
        
        # Add "This week" button at top right
        fig.add_annotation(
            x=0.95,
            y=1.1,
            xref='paper',
            yref='paper',
            text='<span style="color: rgb(71, 85, 105); padding: 6px 12px; border: 1px solid rgb(226, 232, 240); border-radius: 6px; font-size: 12px;">☐ This week</span>',
            showarrow=False,
            font=dict(family='Helvetica'),
            xanchor='right',
            yanchor='middle'
        )
        
        # Modern layout
        fig.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=20, r=20, t=50, b=50),  # Increased top margin for button
            showlegend=True,
            width=300,
            height=350,  # Increased height to accommodate button
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=-0.2,
                xanchor='center',
                x=0.5,
                font=dict(
                    family='Helvetica',
                    size=10,
                    color='rgb(71, 85, 105)'
                )
            )
        )
        
        # Save to PNG with high DPI for crisp rendering
        img_bytes = pio.to_image(fig, format='png', scale=2)
        return Image(io.BytesIO(img_bytes), width=3*inch, height=3.5*inch)

    def _create_ranking_overview_chart(self, ranking_data):
        """Create a chart showing ranking distribution in a single row"""
        fig = go.Figure()
        
        # Get the position ranges data
        position_ranges = ranking_data.get('position_ranges', {})
        
        # Calculate total pages for percentage calculation
        total_pages = sum(position_ranges.values())
        
        # Define the ranges and their colors
        ranges = [
            {'key': '1-3', 'display': '1-3', 'color': 'rgb(99, 102, 241)'},      # Indigo/Purple
            {'key': '4-10', 'display': '4-10', 'color': 'rgb(45, 212, 191)'},    # Teal
            {'key': '11-20', 'display': '11-20', 'color': 'rgb(251, 146, 60)'},  # Orange
            {'key': '21-50', 'display': '21-50', 'color': 'rgb(34, 197, 94)'},   # Green
            {'key': '51-100', 'display': '51-100', 'color': 'rgb(251, 146, 60)'} # Orange
        ]
        
        # Calculate cumulative position for each card
        x_pos = 0
        
        # Add each range as its own card
        for range_info in ranges:
            count = position_ranges.get(range_info['key'], 0)
            value = (count / total_pages * 100) if total_pages > 0 else 0
            
            if value > 0:
                # Add colored rectangle with no gaps
                fig.add_shape(
                    type="rect",
                    x0=x_pos,
                    y0=0,
                    x1=x_pos + value,
                    y1=1,
                    fillcolor=range_info['color'],
                    line=dict(width=0),
                    layer='above'
                )
                
                # Only add text if there's enough space
                if value > 5:
                    # Add percentage and count text
                    fig.add_annotation(
                        x=x_pos + value/2,
                        y=0.5,
                        text=f"{value:.1f}%",
                        showarrow=False,
                        font=dict(
                            color='white',
                            size=12,
                            family='Helvetica-Bold'
                        )
                    )
            
            # Update position for next card
            x_pos += value
        
        # Update layout with cleaner design
        fig.update_layout(
            showlegend=False,
            plot_bgcolor='white',
            paper_bgcolor='white',
            width=800,  # Wider to match screenshot
            height=100,  # Shorter to match screenshot
            margin=dict(l=0, r=0, t=0, b=0),  # Remove margins
            xaxis=dict(
                showgrid=False,
                zeroline=False,
                showticklabels=False,
                range=[0, 100]  # Exact range for percentages
            ),
            yaxis=dict(
                showgrid=False,
                zeroline=False,
                showticklabels=False,
                range=[0, 1]  # Exact range for height
            )
        )
        
        # Save to PNG
        img_bytes = pio.to_image(fig, format='png', scale=2)
        
        # Create Image with specific width to match screenshot
        return Image(io.BytesIO(img_bytes), width=7*inch, height=1*inch)

    def generate_report(self, data):
        """Generate the GSC PDF report with modern design"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )
        
        story = []
        
        # Add title with reduced spacing
        title = Paragraph(
            f"Search Console Report - {data['site_url']}", 
            self.custom_styles['Title']
        )
        story.append(title)
        story.append(Spacer(1, 10))
        
        # Add date range with reduced spacing
        date_range = Paragraph(
            f"{data['date_range']['start']} to {data['date_range']['end']}", 
            self.custom_styles['Subtitle']
        )
        story.append(date_range)
        story.append(Spacer(1, 10))
        
        # Metrics Cards
        story.append(self._create_metrics_section(data['metrics']))
        story.append(Spacer(1, 15))
        
        # Impressions Chart
        story.append(Paragraph("Impressions", self.custom_styles['SectionTitle']))
        story.append(Spacer(1, 5))
        story.append(self._create_time_series_chart(data['time_series']))
        story.append(Spacer(1, 15))
        
        # Clicks Chart
        story.append(Paragraph("Clicks", self.custom_styles['SectionTitle']))
        story.append(Spacer(1, 5))
        story.append(self._create_time_series_chart_click(data['time_series']))
        story.append(Spacer(1, 5))  # Reduced from 15
        
        # CTR Chart
        story.append(Paragraph("Click-Through Rate (CTR)", self.custom_styles['SectionTitle']))
        story.append(Spacer(1, 5))
        story.append(self._create_time_series_chart_ctr(data['time_series']))
        story.append(Spacer(1, 10))  # Reduced from 15
        
        # Ranking Overview Chart
        story.append(Paragraph("Ranking Overview", self.custom_styles['SectionTitle']))
        story.append(Spacer(1, 5))
        
        # Map the position ranges from GSC service to our graph format
        position_ranges = data.get('ranking_overview', {}).get('position_ranges', {})
        ranking_data = {
            'position_ranges': position_ranges
        }
        
        story.append(self._create_ranking_overview_chart(ranking_data))
        story.append(Spacer(1, 15))
        
        # Pages Donut Chart 
        story.append(Paragraph("Pages Overview", self.custom_styles['SectionTitle']))
        story.append(Spacer(1, 5))
        pages_data = {
            'total': data.get('pages', {}).get('total', 120),
            'indexed': data.get('pages', {}).get('indexed', 100),
            'not_indexed': data.get('pages', {}).get('not_indexed', 20)
        }
        story.append(self._create_pages_donut(pages_data))
        
        # Build PDF
        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()
        
        return pdf_data
