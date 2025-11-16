from fastapi import APIRouter, Depends, HTTPException, Query, Path, BackgroundTasks, Request, Response
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Union, Tuple
from uuid import UUID, uuid4
from datetime import datetime, timedelta
import logging
from enum import Enum
from pydantic import BaseModel
from app.core.auth import get_current_user
from app.db.session import get_db_session
from app.services.gsc_service import GSCService
from app.services.email_service import EmailService
from app.models.task import BackgroundTask, TaskType, TaskStatus
from app.models.gsc import GSCAccount
from app.models.gsc_report import GSCReport, GSCReportStatus
from app.schemas.task import TaskResponse
from app.schemas.gsc import (
    GSCAccountCreate,
    GSCAccountResponse,
    GSCMetricEnum as GSCMetric,
    GSCDimensionEnum as GSCDimension,
    GSCQueryResponse,
    GSCSite,
    TimeFrameEnum as TimeFrame,
    ReportFormatEnum as ReportFormat,
    BreakdownTypeEnum as BreakdownType,
    SortMetricEnum as SortMetric
)
from app.schemas.gsc_report import GSCReportResponse, GSCReportList
from app.utils.gsc_pdf_generator import GSCPDFGenerator
from app.utils.domain_authority import get_domain_authority
import http.client
import urllib.parse
import json
from app.core.config import settings

logger = logging.getLogger("fastapi_app")

router = APIRouter()

class SortMetric(str, Enum):
    IMPRESSIONS = "impressions"
    CLICKS = "clicks"
    CTR = "ctr"
    POSITION = "position"

class BreakdownType(str, Enum):
    COUNTRY = "country"
    DEVICE = "device"

class ReportFormat(str, Enum):
    PDF = "pdf"
    EMAIL = "email"
    JSON = "json"

class TimeFrame(str, Enum):
    TODAY = "today"
    YESTERDAY = "yesterday"
    THIS_WEEK = "this_week"
    LAST_WEEK = "last_week"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    LAST_3_MONTHS = "last_3_months"
    LAST_6_MONTHS = "last_6_months"
    THIS_YEAR = "this_year"
    CUSTOM = "custom"

class TaskResponse(BaseModel):
    """Response model for task creation"""
    task_id: str

    class Config:
        from_attributes = True

class TaskStatusResponse(BaseModel):
    """Response model for task status"""
    task_id: str
    status: str
    task_type: str
    metadata: Dict
    error_message: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


def calculate_date_range(timeframe: TimeFrame, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Tuple[str, str]:
    """Calculate start and end dates based on timeframe"""
    today = datetime.utcnow().date()
    
    if timeframe == TimeFrame.TODAY:
        return today.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
    elif timeframe == TimeFrame.YESTERDAY:
        yesterday = today - timedelta(days=1)
        return yesterday.strftime("%Y-%m-%d"), yesterday.strftime("%Y-%m-%d")
    elif timeframe == TimeFrame.THIS_WEEK:
        start = today - timedelta(days=today.weekday())  # Monday of current week
        return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
    elif timeframe == TimeFrame.LAST_WEEK:
        end = today - timedelta(days=today.weekday() + 1)  # Sunday of last week
        start = end - timedelta(days=6)  # Monday of last week
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    elif timeframe == TimeFrame.THIS_MONTH:
        start = today.replace(day=1)  # First day of current month
        return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
    elif timeframe == TimeFrame.LAST_MONTH:
        # First day of current month
        first = today.replace(day=1)
        # Last day of last month
        end = first - timedelta(days=1)
        # First day of last month
        start = end.replace(day=1)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    elif timeframe == TimeFrame.LAST_3_MONTHS:
        end = today
        start = end - timedelta(days=90)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    elif timeframe == TimeFrame.LAST_6_MONTHS:
        end = today
        start = end - timedelta(days=180)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    elif timeframe == TimeFrame.THIS_YEAR:
        start = today.replace(month=1, day=1)  # First day of current year
        return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
    elif timeframe == TimeFrame.CUSTOM:
        if not start_date or not end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date and end_date are required for custom timeframe"
            )
        return start_date, end_date
    else:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

@router.post("/connect", response_model=GSCAccountResponse)
async def connect_gsc_account(
    project_id: UUID = Path(...),
    gsc_data: GSCAccountCreate = None,
    current_user=Depends(get_current_user)
):
    """
    Connect a GSC account to a project
    """
    try:
        # Use get_db_session context manager
        with get_db_session() as db:
            # Verify the credentials
            gsc_service = GSCService(db, project_id)
            is_valid = await gsc_service.verify_credentials(gsc_data.credentials, gsc_data.site_url)
            
            if not is_valid:
                raise HTTPException(status_code=400, detail="Invalid GSC credentials or site URL")

            # Create new GSC account
            gsc_account = GSCAccount(
                project_id=project_id,
                site_url=gsc_data.site_url,
                credentials=gsc_data.credentials
            )
            
            db.add(gsc_account)
            db.commit()
            db.refresh(gsc_account)
            
            return gsc_account
    except HTTPException:
        # Re-raise HTTP exceptions directly
        raise
    except Exception as e:
        logger.error(f"Error connecting GSC account: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error connecting GSC account")

@router.get("/search-analytics", response_model=List[GSCQueryResponse])
async def get_search_analytics(
    project_id: UUID = Path(...),
    site_url: str = Query(..., description="The GSC site URL to fetch data from"),
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format"),
    dimensions: List[GSCDimension] = Query(..., description="List of dimensions to fetch"),
    current_user=Depends(get_current_user)
):
    """
    Get search analytics data from Google Search Console for a specific site
    """
    try:
        # Use get_db_session context manager
        with get_db_session() as db:
            # Verify that the site_url belongs to this project
            gsc_account = db.query(GSCAccount).filter(
                GSCAccount.project_id == project_id,
                GSCAccount.site_url == site_url
            ).first()
            
            if not gsc_account:
                raise HTTPException(
                    status_code=404,
                    detail=f"No GSC account found for project {project_id} with site URL {site_url}"
                )

            gsc_service = GSCService(db, project_id)
            data = await gsc_service.get_search_analytics(
                site_url=site_url,
                start_date=start_date,
                end_date=end_date,
                dimensions=dimensions
            )
            return data
    except HTTPException:
        # Re-raise HTTP exceptions directly
        raise
    except Exception as e:
        logger.error(f"Error fetching GSC data: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error fetching GSC data")

@router.get("/search-analytics/summary")
async def get_search_analytics_summary(
    project_id: UUID = Path(...),
    site_url: str = Query(..., description="The GSC site URL to fetch data from"),
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format"),
    compare: bool = Query(True, description="Compare with previous period"),
    current_user=Depends(get_current_user)
):
    """
    Get summary metrics from Google Search Console with optional comparison to previous period
    """
    try:
        # Use get_db_session context manager
        with get_db_session() as db:
            gsc_service = GSCService(db, project_id)
            summary = await gsc_service.get_search_analytics_summary(
                site_url=gsc_service.gsc_account.site_url,
                start_date=start_date,
                end_date=end_date,
                compare=compare
            )
            return summary
    except HTTPException:
        # Re-raise HTTP exceptions directly
        raise
    except Exception as e:
        logger.error(f"Error fetching GSC summary: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error fetching GSC summary")

@router.get("/search-analytics/timeseries")
async def get_search_analytics_timeseries(
    project_id: UUID = Path(...),
    site_url: str = Query(..., description="The GSC site URL to fetch data from"),
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format"),
    dimensions: List[GSCDimension] = Query([], description="Additional dimensions to include"),
    country: Optional[str] = Query(None, description="Filter by country"),
    device: Optional[str] = Query(None, description="Filter by device (MOBILE, DESKTOP, TABLET)"),
    search_appearance: Optional[str] = Query(None, description="Filter by search appearance"),
    current_user=Depends(get_current_user)
):
    """
    Get daily search analytics data with optional dimension filters
    """
    try:
        # Use get_db_session context manager
        with get_db_session() as db:
            # Build filters dictionary from provided query parameters
            filters = {}
            if country:
                filters['country'] = country
            if device:
                filters['device'] = device
            if search_appearance:
                filters['searchAppearance'] = search_appearance

            gsc_service = GSCService(db, project_id)
            timeseries = await gsc_service.get_search_analytics_timeseries(
                site_url=gsc_service.gsc_account.site_url,
                start_date=start_date,
                end_date=end_date,
                dimensions=[d.value for d in dimensions],
                filters=filters
            )
            return timeseries
    except HTTPException:
        # Re-raise HTTP exceptions directly
        raise
    except Exception as e:
        logger.error(f"Error fetching GSC timeseries: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error fetching GSC timeseries")

@router.get("/sites")
async def get_sites(
    request: Request,
    current_user=Depends(get_current_user)
):
    """
    Get list of sites from Google Search Console
    """
    project_id_str = request.path_params.get("project_id")
    try:
        project_id = UUID(project_id_str)
        # Use get_db_session context manager
        with get_db_session() as db:
            gsc_service = GSCService(db, project_id)
            sites = await gsc_service.get_sites()
            return sites
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    except Exception as e:
        logger.error(f"Error fetching GSC sites: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error fetching GSC sites")

@router.get("/pages/indexing")
async def get_page_indexing_stats(
    project_id: UUID = Path(...),
    site_url: str = Query(..., description="The GSC site URL to fetch data from"),
    current_user=Depends(get_current_user)
):
    """
    Get page indexing statistics from Google Search Console
    """
    try:
        # Use get_db_session context manager
        with get_db_session() as db:
            gsc_service = GSCService(db, project_id)
            stats = await gsc_service.get_page_indexing_stats(site_url=gsc_service.gsc_account.site_url)
            return stats
    except HTTPException:
        # Re-raise HTTP exceptions directly
        raise
    except Exception as e:
        logger.error(f"Error fetching page indexing stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error fetching page indexing stats")

@router.get("/pages/top-performing")
async def get_top_performing_pages(
    project_id: UUID = Path(...),
    site_url: str = Query(..., description="The GSC site URL to fetch data from"),
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format"),
    page_size: int = Query(5, description="Number of results per page", ge=1, le=1000),
    page: int = Query(1, description="Page number", ge=1),
    sort_by: SortMetric = Query(SortMetric.IMPRESSIONS, description="Metric to sort by"),
    country: Optional[str] = Query(None, description="Filter by country"),
    device: Optional[str] = Query(None, description="Filter by device (MOBILE, DESKTOP, TABLET)"),
    search_appearance: Optional[str] = Query(None, description="Filter by search appearance"),
    current_user=Depends(get_current_user)
):
    """
    Get top performing pages/blogs with metrics, sorting, and filtering options
    """
    try:
        # Use get_db_session context manager
        with get_db_session() as db:
            # Build filters dictionary from provided query parameters
            filters = {}
            if country:
                filters['country'] = country
            if device:
                filters['device'] = device
            if search_appearance:
                filters['searchAppearance'] = search_appearance

            gsc_service = GSCService(db, project_id)
            top_pages = await gsc_service.get_top_performing_pages(
                site_url=gsc_service.gsc_account.site_url,
                start_date=start_date,
                end_date=end_date,
                page_size=page_size,
                page=page,
                sort_by=sort_by,
                filters=filters
            )
            return top_pages
    except HTTPException:
        # Re-raise HTTP exceptions directly
        raise
    except Exception as e:
        logger.error(f"Error fetching top performing pages: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error fetching top performing pages")

@router.get("/ranking-overview")
async def get_ranking_overview(
    project_id: UUID = Path(...),
    site_url: str = Query(..., description="The GSC site URL to fetch data from"),
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format"),
    current_user=Depends(get_current_user)
):
    """
    Get ranking distribution overview showing how many pages rank in different position ranges
    """
    try:
        # Use get_db_session context manager
        with get_db_session() as db:
            gsc_service = GSCService(db, project_id)
            overview = await gsc_service.get_ranking_overview(
                site_url=gsc_service.gsc_account.site_url,
                start_date=start_date,
                end_date=end_date
            )
            return overview
    except HTTPException:
        # Re-raise HTTP exceptions directly
        raise
    except Exception as e:
        logger.error(f"Error fetching ranking overview: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error fetching ranking overview")

@router.get("/metrics-breakdown/{breakdown_type}")
async def get_metrics_breakdown(
    breakdown_type: BreakdownType,
    project_id: UUID = Path(...),
    site_url: str = Query(..., description="The GSC site URL to fetch data from"),
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format"),
    current_user=Depends(get_current_user)
):
    """
    Get metrics breakdown by country or device
    """
    try:
        # Use get_db_session context manager
        with get_db_session() as db:
            gsc_service = GSCService(db, project_id)
            breakdown = await gsc_service.get_metrics_breakdown(
                site_url=gsc_service.gsc_account.site_url,
                start_date=start_date,
                end_date=end_date,
                breakdown_type=breakdown_type
            )
            return breakdown
    except HTTPException:
        # Re-raise HTTP exceptions directly
        raise
    except Exception as e:
        logger.error(f"Error fetching metrics breakdown: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error fetching metrics breakdown")

async def send_report_email_background(
    email: str,
    site_url: str,
    start_date: str,
    end_date: str,
    country: Optional[str],
    task_id: UUID,
    project_id: UUID,
    timeframe: str  # Added timeframe parameter
):
    """Send GSC report email in the background"""
    try:
        # Get database session
        with get_db_session() as db:
            # Create GSC report record
            gsc_report = GSCReport(
                project_id=project_id,
                site_url=site_url,
                timeframe=timeframe,
                start_date=datetime.strptime(start_date, '%Y-%m-%d').date(),
                end_date=datetime.strptime(end_date, '%Y-%m-%d').date(),
                status=GSCReportStatus.RUNNING
            )
            db.add(gsc_report)
            db.commit()
            db.refresh(gsc_report)

            # Update task status to running
            task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()
            if task:
                task.status = TaskStatus.RUNNING
                db.commit()

            # Initialize services
            gsc_service = GSCService(db, project_id)
            email_service = EmailService()

            # Generate report data and PDF
            report_data = await gsc_service.generate_report(
                site_url=gsc_service.gsc_account.site_url,
                start_date=start_date,
                end_date=end_date,
                country=country
            )
            
            pdf_data = await gsc_service.generate_pdf_report(
                site_url=gsc_service.gsc_account.site_url,
                start_date=start_date,
                end_date=end_date,
                country=country
            )

            # Format dates for filename
            formatted_start = datetime.strptime(start_date, '%Y-%m-%d').strftime('%b_%d_%Y')
            formatted_end = datetime.strptime(end_date, '%Y-%m-%d').strftime('%b_%d_%Y')
            filename = f"gsc_report_{formatted_start}_to_{formatted_end}.pdf"

            # Send email with report data and PDF
            await email_service.send_gsc_report_email(
                email=email,
                site_url=gsc_service.gsc_account.site_url,
                report_data=report_data,
                timeframe=timeframe,
                pdf_data=pdf_data,
                pdf_filename=filename
            )

            # Update GSC report as completed and sent by email
            gsc_report.mark_email_sent(email)
            db.commit()

            # Update task status
            task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()
            if task:
                task.site_url = gsc_service.gsc_account.site_url
                task.status = TaskStatus.COMPLETED
                task.updated_at = datetime.now()
                db.commit()

    except Exception as e:
        logger.error(f"Error sending GSC report email: {str(e)}")
        # Update GSC report as failed
        with get_db_session() as db:
            gsc_report = db.query(GSCReport).filter(
                GSCReport.project_id == project_id,
                GSCReport.start_date == datetime.strptime(start_date, '%Y-%m-%d').date(),
                GSCReport.end_date == datetime.strptime(end_date, '%Y-%m-%d').date()
            ).order_by(GSCReport.created_at.desc()).first()
            
            if gsc_report:
                gsc_report.mark_failed()
                db.commit()

        # Update task status with error
        with get_db_session() as db:
            task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()
            if task:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                task.updated_at = datetime.now()
                db.commit()
        raise e

@router.post("/reports/generate")
async def generate_gsc_report(
    background_tasks: BackgroundTasks,
    project_id: UUID = Path(...),
    site_url: str = Query(..., description="Site URL to generate report for"),
    timeframe: TimeFrame = Query(..., description="Timeframe for the report"),
    report_format: ReportFormat = Query(..., description="Format of the report (email or pdf)"),
    email: Optional[str] = Query(None, description="Email to send report to (required for email format)"),
    country: Optional[str] = Query(None, description="Filter results by country"),
    start_date: Optional[str] = Query(None, description="Start date for custom timeframe (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date for custom timeframe (YYYY-MM-DD)"),
    current_user = Depends(get_current_user)
):
    """Generate a GSC report in the specified format"""
    try:
        # Validate input parameters
        if report_format == ReportFormat.EMAIL and not email:
            raise HTTPException(
                status_code=400,
                detail="Email is required for email report format"
            )
        
        # Get date range based on timeframe
        if timeframe == TimeFrame.CUSTOM:
            if not start_date or not end_date:
                raise HTTPException(
                    status_code=400,
                    detail="Start date and end date are required for custom timeframe"
                )
        else:
            start_date, end_date = calculate_date_range(timeframe)
        
        # Generate report based on format
        if report_format == ReportFormat.EMAIL:
            # Create background task for email
            task_id = None
            with get_db_session() as db:
                task = BackgroundTask(
                    id=uuid4(),
                    task_type=TaskType.EMAIL,
                    status=TaskStatus.PENDING,
                    task_metadata={
                        "site_url": site_url,
                        "start_date": start_date,
                        "end_date": end_date,
                        "report_format": report_format.value,
                        "country": country,
                        "user_id": str(current_user.id)
                    }
                )
                db.add(task)
                db.commit()
                task_id = task.id  # Capture task ID before session closes
            
            # Add email task to background
            background_tasks.add_task(
                send_report_email_background,
                email=email,
                site_url=site_url,
                start_date=start_date,
                end_date=end_date,
                country=country,
                task_id=task_id,
                project_id=project_id,
                timeframe=timeframe.value
            )
            
            return TaskResponse(task_id=str(task_id))
            
        elif report_format == ReportFormat.PDF:
            # Create GSC report record for download
            with get_db_session() as db:
                gsc_report = GSCReport(
                    project_id=project_id,
                    site_url=site_url,
                    timeframe=timeframe.value,
                    start_date=datetime.strptime(start_date, '%Y-%m-%d').date(),
                    end_date=datetime.strptime(end_date, '%Y-%m-%d').date(),
                    status=GSCReportStatus.RUNNING
                )
                db.add(gsc_report)
                db.commit()
                
                # Generate PDF immediately
                gsc_service = GSCService(db, project_id)
                pdf_data = await gsc_service.generate_pdf_report(
                    site_url=gsc_service.gsc_account.site_url,
                    start_date=start_date,
                    end_date=end_date,
                    country=country
                )
                
                # Mark report as completed via download
                gsc_report.mark_download_completed()
                db.commit()
            
            # Format dates for filename
            formatted_start = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y%m%d')
            formatted_end = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y%m%d')
            filename = f"gsc_report_{formatted_start}_to_{formatted_end}.pdf"
            
            # Return PDF as response
            return Response(
                content=pdf_data,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"'
                }
            )
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported report format: {report_format}"
            )
            
    except Exception as e:
        logger.error(f"Error generating GSC report: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating GSC report: {str(e)}"
        )

async def generate_pdf_report_background(
    site_url: str,
    start_date: str,
    end_date: str,
    country: Optional[str],
    task_id: UUID,
    project_id: UUID
):
    """Generate PDF report in the background"""
    try:
        # Get database session
        with get_db_session() as db:
            # Update task status
            task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()
            if task:
                task.status = TaskStatus.RUNNING
                task.updated_at = datetime.now()
                db.commit()
        
            # Get GSC data
            gsc_service = GSCService(db, project_id)
        
            # Get metrics data
            metrics = await gsc_service.get_search_analytics_summary(
                site_url=gsc_service.gsc_account.site_url,
                start_date=start_date,
                end_date=end_date,
                country=country
            )
        
            # Get time series data
            time_series = await gsc_service.get_search_analytics_timeseries(
                site_url=gsc_service.gsc_account.site_url,
                start_date=start_date,
                end_date=end_date,
                country=country
            )
        
            # Get top pages
            top_pages = await gsc_service.get_top_performing_pages(
                site_url=gsc_service.gsc_account.site_url,
                start_date=start_date,
                end_date=end_date,
                country=country,
                page_size=5
            )
        
            # Get indexing stats
            pages_status = await gsc_service.get_page_indexing_stats(site_url=gsc_service.gsc_account.site_url)
        
            # Prepare data for PDF generation
            report_data = {
                'site_url': gsc_service.gsc_account.site_url,
                'start_date': start_date,
                'end_date': end_date,
                'metrics': metrics,
                'time_series': time_series,
                'top_pages': top_pages['pages'],
                'pages_status': pages_status
            }
        
            # Generate PDF
            pdf_generator = GSCPDFGenerator()
            logger.info("Generating PDF")
            logger.info(report_data)
            pdf_data = pdf_generator.generate_report(report_data)
            logger.info("PDF generated")
        
            # Save PDF to file
            filename = f"gsc_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            filepath = f"/tmp/{filename}"
            with open(filepath, 'wb') as f:
                f.write(pdf_data)
        
            # Update task status
            if task:
                task.status = TaskStatus.COMPLETED
                task.task_metadata['pdf_path'] = filepath
                task.updated_at = datetime.now()
                db.commit()

    except Exception as e:
        logger.error(f"Error generating PDF report: {str(e)}")
        # Update task status with error
        with get_db_session() as db:
            task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()
            if task:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                task.updated_at = datetime.now()
                db.commit()
        raise e
    
    finally:
        pass

@router.delete("")
async def disconnect_gsc_account(
    project_id: UUID = Path(...),
    current_user=Depends(get_current_user)
):
    """
    Disconnect a GSC account from a project
    """
    try:
        # Use get_db_session context manager
        with get_db_session() as db:
            # Get GSC account
            gsc_account = db.query(GSCAccount).filter(
                GSCAccount.project_id == project_id
            ).first()

            if not gsc_account:
                raise HTTPException(
                    status_code=404,
                    detail=f"No GSC account found for project {project_id}"
                )

            # Delete GSC account
            db.delete(gsc_account)
            db.commit()

            return {"message": "GSC account disconnected successfully"}

    except HTTPException:
        # Re-raise HTTP exceptions directly
        raise
    except Exception as e:
        logger.error(f"Error disconnecting GSC account: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error disconnecting GSC account")

@router.get("/domain-authority")
async def domain_authority_endpoint(domain: str = Query(..., description="Domain URL to check")):
    """
    Get domain authority metrics using RapidAPI service
    
    Args:
        domain: Domain URL to check (without http/https)
        
    Returns:
        dict: Domain authority metrics including DA, PA, and other Moz metrics
    """
    return await get_domain_authority(domain)

@router.get("/reports/list", response_model=GSCReportList)
async def list_gsc_reports(
    project_id: UUID = Path(...),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of records to return"),
    current_user = Depends(get_current_user)
):
    """List all GSC reports for a project"""
    try:
        with get_db_session() as db:
            # Get total count
            total = db.query(GSCReport).filter(
                GSCReport.project_id == project_id
            ).count()
            
            # Get reports with pagination
            reports = db.query(GSCReport).filter(
                GSCReport.project_id == project_id
            ).order_by(
                GSCReport.created_at.desc()
            ).offset(skip).limit(limit).all()
            
            return GSCReportList(
                reports=reports,
                total=total
            )
            
    except Exception as e:
        logger.error(f"Error listing GSC reports: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error listing GSC reports: {str(e)}"
        )

@router.get("/reports/{report_id}", response_model=GSCReportResponse)
async def get_gsc_report(
    project_id: UUID = Path(...),
    report_id: UUID = Path(...),
    current_user = Depends(get_current_user)
):
    """Get a specific GSC report by ID"""
    try:
        with get_db_session() as db:
            report = db.query(GSCReport).filter(
                GSCReport.id == report_id,
                GSCReport.project_id == project_id
            ).first()
            
            if not report:
                raise HTTPException(
                    status_code=404,
                    detail="GSC report not found"
                )
                
            return report
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting GSC report: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting GSC report: {str(e)}"
        )
