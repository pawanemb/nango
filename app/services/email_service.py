"""Email service for sending reports"""
import os
from typing import Dict, Optional, Any
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from jinja2 import Environment, select_autoescape, PackageLoader
from app.core.config import settings
from app.core.logging_config import logger

class EmailService:
    """Service for sending emails"""

    def __init__(self):
        """Initialize email service"""
        self.email_conf = ConnectionConfig(
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
        self.fastmail = FastMail(self.email_conf)
        self.env = Environment(
            loader=PackageLoader('app', 'templates/email'),
            autoescape=select_autoescape(['html', 'xml'])
        )

    def _format_number(self, num: float) -> str:
        """Format numbers for better readability"""
        if num >= 1000000:
            return f"{num/1000000:.1f}M"
        elif num >= 1000:
            return f"{num/1000:.1f}K"
        return str(num)

    def _format_report_data(self, report_data: Dict) -> Dict:
        """Format report data for email template"""
        try:
            # Get current and previous period data
            current_period = report_data['search_analytics']
            previous_period = report_data.get('previous_period', {})
            timeseries = report_data.get('timeseries', {'dates': [], 'impressions': []})

            # Calculate max impressions for graph scaling
            max_impressions = max(timeseries['impressions']) if timeseries['impressions'] else 0

            formatted_data = {
                'site_url': report_data['site_url'],
                'time_range': report_data['time_range'],
                'search_analytics': {
                    'total_impressions': self._format_number(current_period['total_impressions']),
                    'total_clicks': self._format_number(current_period['total_clicks']),
                    'average_ctr': f"{current_period['average_ctr']}",  # Already in percentage
                    'average_position': f"{current_period['average_position']:.1f}",
                    # Calculate changes compared to previous period
                    'impressions_change': self._calculate_change(
                        current_period['total_impressions'],
                        previous_period.get('total_impressions', 0)
                    ),
                    'clicks_change': self._calculate_change(
                        current_period['total_clicks'],
                        previous_period.get('total_clicks', 0)
                    ),
                    'ctr_change': self._calculate_change(
                        current_period['average_ctr'],
                        previous_period.get('average_ctr', 0)
                    ),
                    'position_change': self._calculate_position_change(
                        current_period['average_position'],
                        previous_period.get('average_position', 0)
                    )
                },
                'timeseries': {
                    'dates': timeseries['dates'],
                    'impressions': timeseries['impressions'],
                    'ctr': timeseries.get('ctr', [])
                },
                'max_impressions': max_impressions,
                'indexing_stats': report_data.get('indexing_stats', {
                    'total': 0,
                    'indexed': 0,
                    'not_indexed': 0
                })
            }

            return formatted_data
        except Exception as e:
            logger.error(f"Error formatting report data: {str(e)}")
            raise Exception(f"Failed to format report data: {str(e)}")

    def _calculate_change(self, current: float, previous: float) -> float:
        """Calculate percentage change between periods"""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return ((current - previous) / previous) * 100

    def _calculate_position_change(self, current: float, previous: float) -> float:
        """Calculate position change (note: lower is better)"""
        if previous == 0:
            return 0.0
        # Invert the change since lower position is better
        return ((previous - current) / previous) * 100

    async def send_report_email(
        self,
        recipient_email: str,
        subject: str,
        report_data: Dict,
        attachment_path: Optional[str] = None
    ):
        """Send GSC report via email"""
        try:
            # Format data for template
            formatted_data = self._format_report_data(report_data)

            # Get and render email template
            template = self.env.get_template('gsc_report.html')
            html_content = template.render(**formatted_data)

            # Create message
            message = MessageSchema(
                subject=subject,
                recipients=[recipient_email],
                body=html_content,
                subtype="html"
            )

            # Send email
            logger.info(f"Sending GSC report email to {recipient_email}")
            await self.fastmail.send_message(message)
            logger.info(f"Successfully sent GSC report email to {recipient_email}")

        except Exception as e:
            logger.error(f"Error sending report email: {str(e)}")
            raise Exception(f"Failed to send report email: {str(e)}")

    async def send_gsc_report_email(
        self,
        email: str,
        site_url: str,
        report_data: Dict,
        timeframe: str,
        pdf_data: Optional[bytes] = None,
        pdf_filename: Optional[str] = None
    ):
        """Send GSC report via email"""
        temp_path = None
        try:
            # Format data for template
            formatted_data = self._format_report_data(report_data)

            # Get and render email template
            # template = self.env.get_template('gsc_report_email.html')
            template = self.env.get_template('gsc_report_email_new.html')
            html_content = template.render(**formatted_data)

            # Create message
            subject = f"Google Search Console Report - {site_url} ({timeframe})"
            
            # Create message with optional PDF attachment
            if pdf_data and pdf_filename:
                # Save PDF data to temporary file
                import tempfile
                import os
                
                # Create a specific named temporary file based on site_url and timeframe
                site_name = site_url.replace('https://', '').replace('http://', '').replace('/', '_').replace('.', '_')
                temp_filename = f"gsc_report_{site_name}_{timeframe}.pdf"
                temp_dir = tempfile.gettempdir()
                temp_path = os.path.join(temp_dir, temp_filename)
                
                # Write PDF data to file
                with open(temp_path, 'wb') as f:
                    f.write(pdf_data)
                
                message = MessageSchema(
                    subject=subject,
                    recipients=[email],
                    body=html_content,
                    subtype="html",
                    attachments=[
                        {
                            "file": temp_path,
                            "filename": pdf_filename,
                            "headers": {
                                "Content-Type": "application/pdf",
                            },
                        }
                    ]
                )
            else:
                message = MessageSchema(
                    subject=subject,
                    recipients=[email],
                    body=html_content,
                    subtype="html"
                )

            # Send email
            logger.info(f"Sending GSC report email to {email}")
            await self.fastmail.send_message(message)
            logger.info(f"Successfully sent GSC report email to {email}")

        except Exception as e:
            logger.error(f"Error sending GSC report email: {str(e)}")
            raise Exception(f"Failed to send GSC report email: {str(e)}")
        finally:
            # Clean up temporary file if it exists
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                    logger.debug(f"Removed temporary PDF file: {temp_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove temporary PDF file: {str(e)}")
