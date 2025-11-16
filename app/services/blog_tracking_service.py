from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from app.models.blog_generation_tracking import BlogGenerationTracking, BlogStepTracking
from app.db.session import get_db_session
from app.core.logging_config import logger
import json
import uuid

class BlogTrackingService:
    """Service for tracking blog generation attempts, retries, and performance."""
    
    def __init__(self):
        self.step_order_map = {
            'wc1': 1,
            'wc2': 2,
            'section': 3,
            'step1': 4,
            'step2': 5,
            'step3': 6,
            'step4': 7,
            'step5': 8,
            'step6': 9
        }
    
    def start_blog_generation_tracking(
        self,
        blog_id: str,
        project_id: str,
        user_id: str,
        blog_request: Dict[str, Any],
        main_task_id: str,
        generation_attempt: int = 1
    ) -> str:
        """
        Start tracking a new blog generation attempt.
        
        Returns:
            tracking_id: UUID of the tracking record
        """
        try:
            with get_db_session() as db:
                # Check if this is a retry (generation_attempt > 1)
                if generation_attempt > 1:
                    # Mark previous attempts as abandoned if they're still running
                    previous_attempts = db.query(BlogGenerationTracking).filter(
                        BlogGenerationTracking.blog_id == blog_id,
                        BlogGenerationTracking.overall_status.in_(['started', 'running'])
                    ).all()
                    
                    for attempt in previous_attempts:
                        attempt.overall_status = 'abandoned'
                        attempt.completed_at = datetime.now(timezone.utc)
                        if attempt.started_at:
                            attempt.total_generation_time = (
                                attempt.completed_at - attempt.started_at
                            ).total_seconds()
                
                # Create new tracking record
                tracking = BlogGenerationTracking(
                    blog_id=blog_id,
                    project_id=project_id,
                    user_id=user_id,
                    blog_title=blog_request.get('blog_title'),
                    primary_keyword=blog_request.get('primary_keyword'),
                    target_word_count=blog_request.get('word_count'),
                    generation_attempt=generation_attempt,
                    main_task_id=main_task_id,
                    overall_status='started',
                    started_at=datetime.now(timezone.utc)
                )
                
                db.add(tracking)
                db.commit()
                db.refresh(tracking)
                
                logger.info(f"Started tracking blog generation: {tracking.id} for blog {blog_id}, attempt {generation_attempt}")
                return str(tracking.id)
                
        except Exception as e:
            logger.error(f"Error starting blog generation tracking: {e}")
            raise
    
    def start_step_tracking(
        self,
        tracking_id: str,
        blog_id: str,
        step_name: str,
        task_id: Optional[str] = None
    ) -> str:
        """
        Start tracking a specific step in blog generation.
        
        Returns:
            step_tracking_id: UUID of the step tracking record
        """
        try:
            with get_db_session() as db:
                step_tracking = BlogStepTracking(
                    tracking_id=tracking_id,
                    blog_id=blog_id,
                    step_name=step_name,
                    step_order=self.step_order_map.get(step_name, 999),
                    task_id=task_id,
                    status='running',
                    started_at=datetime.now(timezone.utc),
                    api_attempts=0,
                    retry_attempts=[]
                )
                
                db.add(step_tracking)
                db.commit()
                db.refresh(step_tracking)
                
                logger.info(f"Started step tracking: {step_tracking.id} for step {step_name}")
                return str(step_tracking.id)
                
        except Exception as e:
            logger.error(f"Error starting step tracking: {e}")
            raise
    
    def record_api_attempt(
        self,
        blog_id: str,
        step_name: str,
        attempt_number: int,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        status: str = 'running',
        error_message: Optional[str] = None,
        response_data: Optional[Dict] = None
    ):
        """Record an API attempt for a specific step."""
        try:
            with get_db_session() as db:
                # Find the step tracking record
                step_tracking = db.query(BlogStepTracking).filter(
                    BlogStepTracking.blog_id == blog_id,
                    BlogStepTracking.step_name == step_name,
                    BlogStepTracking.status.in_(['running', 'pending'])
                ).order_by(BlogStepTracking.created_at.desc()).first()
                
                if not step_tracking:
                    logger.warning(f"No active step tracking found for {blog_id} step {step_name}")
                    return
                
                # Update API attempts count
                step_tracking.api_attempts = max(step_tracking.api_attempts, attempt_number)
                
                # Add to retry attempts
                if not step_tracking.retry_attempts:
                    step_tracking.retry_attempts = []
                
                attempt_data = {
                    'attempt': attempt_number,
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat() if end_time else None,
                    'status': status,
                    'error': error_message,
                    'execution_time': (end_time - start_time).total_seconds() if end_time else None
                }
                
                if response_data:
                    attempt_data['response_data'] = response_data
                
                # Update or add the attempt
                existing_attempt_idx = None
                for i, existing in enumerate(step_tracking.retry_attempts):
                    if existing.get('attempt') == attempt_number:
                        existing_attempt_idx = i
                        break
                
                if existing_attempt_idx is not None:
                    step_tracking.retry_attempts[existing_attempt_idx] = attempt_data
                else:
                    step_tracking.retry_attempts.append(attempt_data)
                
                # If this attempt succeeded, mark it
                if status == 'success':
                    step_tracking.successful_attempt = attempt_number
                
                db.commit()
                
                logger.info(f"Recorded API attempt {attempt_number} for {step_name}: {status}")
                
        except Exception as e:
            logger.error(f"Error recording API attempt: {e}")
    
    def complete_step(
        self,
        blog_id: str,
        step_name: str,
        status: str = 'completed',
        output_content: Optional[str] = None,
        error_message: Optional[str] = None,
        tokens_used: Optional[Dict] = None
    ):
        """Mark a step as completed or failed."""
        try:
            with get_db_session() as db:
                step_tracking = db.query(BlogStepTracking).filter(
                    BlogStepTracking.blog_id == blog_id,
                    BlogStepTracking.step_name == step_name,
                    BlogStepTracking.status == 'running'
                ).order_by(BlogStepTracking.created_at.desc()).first()
                
                if not step_tracking:
                    logger.warning(f"No running step tracking found for {blog_id} step {step_name}")
                    return
                
                step_tracking.status = status
                step_tracking.completed_at = datetime.now(timezone.utc)
                step_tracking.execution_time = (
                    step_tracking.completed_at - step_tracking.started_at
                ).total_seconds()
                
                if output_content:
                    step_tracking.output_content = output_content
                    # Count words in output
                    step_tracking.output_word_count = len(output_content.split())
                
                if error_message:
                    step_tracking.error_message = error_message
                
                if tokens_used:
                    step_tracking.tokens_used = tokens_used
                
                db.commit()
                
                logger.info(f"Completed step {step_name} with status {status}")
                
        except Exception as e:
            logger.error(f"Error completing step: {e}")
    
    def complete_blog_generation(
        self,
        blog_id: str,
        status: str = 'completed',
        final_content: Optional[str] = None,
        failed_step: Optional[str] = None,
        failure_reason: Optional[str] = None
    ):
        """Mark the entire blog generation as completed or failed."""
        try:
            with get_db_session() as db:
                tracking = db.query(BlogGenerationTracking).filter(
                    BlogGenerationTracking.blog_id == blog_id,
                    BlogGenerationTracking.overall_status.in_(['started', 'running'])
                ).order_by(BlogGenerationTracking.created_at.desc()).first()
                
                if not tracking:
                    logger.warning(f"No active tracking found for blog {blog_id}")
                    return
                
                tracking.overall_status = status
                tracking.completed_at = datetime.now(timezone.utc)
                tracking.total_generation_time = (
                    tracking.completed_at - tracking.started_at
                ).total_seconds()
                
                if final_content:
                    tracking.final_content = final_content
                    tracking.actual_word_count = len(final_content.split())
                
                if failed_step:
                    tracking.failed_step = failed_step
                
                if failure_reason:
                    tracking.failure_reason = failure_reason
                
                db.commit()
                
                logger.info(f"Completed blog generation {blog_id} with status {status}")
                
        except Exception as e:
            logger.error(f"Error completing blog generation: {e}")
    
    def get_blog_generation_stats(
        self,
        blog_id: Optional[str] = None,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get blog generation statistics."""
        try:
            with get_db_session() as db:
                query = db.query(BlogGenerationTracking)
                
                if blog_id:
                    query = query.filter(BlogGenerationTracking.blog_id == blog_id)
                if project_id:
                    query = query.filter(BlogGenerationTracking.project_id == project_id)
                if user_id:
                    query = query.filter(BlogGenerationTracking.user_id == user_id)
                
                results = query.order_by(BlogGenerationTracking.created_at.desc()).limit(limit).all()
                
                stats = []
                for tracking in results:
                    # Get step details
                    steps = db.query(BlogStepTracking).filter(
                        BlogStepTracking.tracking_id == tracking.id
                    ).order_by(BlogStepTracking.step_order).all()
                    
                    step_details = []
                    for step in steps:
                        step_details.append({
                            'step_name': step.step_name,
                            'status': step.status,
                            'execution_time': step.execution_time,
                            'api_attempts': step.api_attempts,
                            'successful_attempt': step.successful_attempt,
                            'retry_attempts': step.retry_attempts,
                            'error_message': step.error_message
                        })
                    
                    stats.append({
                        'tracking_id': str(tracking.id),
                        'blog_id': tracking.blog_id,
                        'generation_attempt': tracking.generation_attempt,
                        'overall_status': tracking.overall_status,
                        'total_generation_time': tracking.total_generation_time,
                        'failed_step': tracking.failed_step,
                        'failure_reason': tracking.failure_reason,
                        'actual_word_count': tracking.actual_word_count,
                        'target_word_count': tracking.target_word_count,
                        'created_at': tracking.created_at.isoformat(),
                        'completed_at': tracking.completed_at.isoformat() if tracking.completed_at else None,
                        'steps': step_details
                    })
                
                return stats
                
        except Exception as e:
            logger.error(f"Error getting blog generation stats: {e}")
            return []
    
    def get_retry_analysis(self, project_id: Optional[str] = None) -> Dict:
        """Get analysis of retry patterns and failure points."""
        try:
            with get_db_session() as db:
                query = db.query(BlogGenerationTracking)
                if project_id:
                    query = query.filter(BlogGenerationTracking.project_id == project_id)
                
                all_attempts = query.all()
                
                # Analyze retry patterns
                retry_analysis = {
                    'total_attempts': len(all_attempts),
                    'successful_attempts': len([a for a in all_attempts if a.overall_status == 'completed']),
                    'failed_attempts': len([a for a in all_attempts if a.overall_status == 'failed']),
                    'abandoned_attempts': len([a for a in all_attempts if a.overall_status == 'abandoned']),
                    'retry_distribution': {},
                    'common_failure_steps': {},
                    'average_generation_time': 0,
                    'step_failure_analysis': {}
                }
                
                # Retry distribution
                for attempt in all_attempts:
                    gen_attempt = attempt.generation_attempt
                    if gen_attempt not in retry_analysis['retry_distribution']:
                        retry_analysis['retry_distribution'][gen_attempt] = 0
                    retry_analysis['retry_distribution'][gen_attempt] += 1
                
                # Common failure steps
                failed_attempts = [a for a in all_attempts if a.failed_step]
                for attempt in failed_attempts:
                    step = attempt.failed_step
                    if step not in retry_analysis['common_failure_steps']:
                        retry_analysis['common_failure_steps'][step] = 0
                    retry_analysis['common_failure_steps'][step] += 1
                
                # Average generation time
                completed_attempts = [a for a in all_attempts if a.total_generation_time]
                if completed_attempts:
                    retry_analysis['average_generation_time'] = sum(
                        a.total_generation_time for a in completed_attempts
                    ) / len(completed_attempts)
                
                # Step failure analysis
                step_query = db.query(BlogStepTracking)
                if project_id:
                    # Join with BlogGenerationTracking to filter by project
                    step_query = step_query.join(BlogGenerationTracking).filter(
                        BlogGenerationTracking.project_id == project_id
                    )
                
                all_steps = step_query.all()
                
                for step in all_steps:
                    step_name = step.step_name
                    if step_name not in retry_analysis['step_failure_analysis']:
                        retry_analysis['step_failure_analysis'][step_name] = {
                            'total_attempts': 0,
                            'successful': 0,
                            'failed': 0,
                            'average_api_retries': 0,
                            'max_api_retries': 0
                        }
                    
                    analysis = retry_analysis['step_failure_analysis'][step_name]
                    analysis['total_attempts'] += 1
                    
                    if step.status == 'completed':
                        analysis['successful'] += 1
                    elif step.status == 'failed':
                        analysis['failed'] += 1
                    
                    if step.api_attempts:
                        analysis['max_api_retries'] = max(analysis['max_api_retries'], step.api_attempts)
                
                # Calculate averages for step analysis
                for step_name, analysis in retry_analysis['step_failure_analysis'].items():
                    if analysis['total_attempts'] > 0:
                        step_attempts = [s for s in all_steps if s.step_name == step_name and s.api_attempts]
                        if step_attempts:
                            analysis['average_api_retries'] = sum(s.api_attempts for s in step_attempts) / len(step_attempts)
                
                return retry_analysis
                
        except Exception as e:
            logger.error(f"Error getting retry analysis: {e}")
            return {}

# Global instance
blog_tracking_service = BlogTrackingService() 