from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base_class import Base
import uuid

class BlogGenerationTracking(Base):
    __tablename__ = "blog_generation_tracking"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    blog_id = Column(String, nullable=False, index=True)  # MongoDB blog ID
    project_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Blog metadata
    blog_title = Column(String, nullable=True)
    primary_keyword = Column(String, nullable=True)
    target_word_count = Column(Integer, nullable=True)
    actual_word_count = Column(Integer, nullable=True)
    
    # Generation attempt tracking
    generation_attempt = Column(Integer, default=1)  # 1, 2, 3... for user retries
    main_task_id = Column(String, nullable=True)  # Celery main task ID
    
    # Overall status
    overall_status = Column(String, default='started')  # started, completed, failed, abandoned
    
    # Timing information
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    total_generation_time = Column(Float, nullable=True)  # in seconds
    
    # Step-by-step tracking (JSON format)
    step_tracking = Column(JSON, default=dict)  # Detailed step tracking
    
    # Failure information
    failed_step = Column(String, nullable=True)  # Which step failed
    failure_reason = Column(Text, nullable=True)
    
    # API retry tracking for each step
    api_retry_details = Column(JSON, default=dict)  # Detailed API retry info
    
    # Final content metrics
    final_content = Column(Text, nullable=True)
    content_quality_score = Column(Float, nullable=True)
    
    # Additional metadata - temporarily removed to work with existing schema
    # extra_metadata = Column(JSON, default=dict)  # Any additional tracking data
    
    updated_at = Column(DateTime(timezone=True), 
                       server_default=func.now(), 
                       onupdate=func.now())

class BlogStepTracking(Base):
    __tablename__ = "blog_step_tracking"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tracking_id = Column(UUID(as_uuid=True), nullable=False, index=True)  # FK to BlogGenerationTracking
    blog_id = Column(String, nullable=False, index=True)
    
    # Step information
    step_name = Column(String, nullable=False)  # wc1, wc2, section, step1, step2, etc.
    step_order = Column(Integer, nullable=False)
    task_id = Column(String, nullable=True)  # Celery task ID for this step
    
    # Step status
    status = Column(String, default='pending')  # pending, running, completed, failed
    
    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    execution_time = Column(Float, nullable=True)  # in seconds
    
    # API retry tracking for this specific step
    api_attempts = Column(Integer, default=0)
    successful_attempt = Column(Integer, nullable=True)  # Which attempt succeeded
    
    # Retry details (JSON array of attempts)
    retry_attempts = Column(JSON, default=list)  # [{"attempt": 1, "start_time": "", "end_time": "", "status": "", "error": ""}]
    
    # Content and results
    output_content = Column(Text, nullable=True)
    output_word_count = Column(Integer, nullable=True)
    
    # Error information
    error_message = Column(Text, nullable=True)
    error_type = Column(String, nullable=True)
    
    # Token usage (if applicable)
    tokens_used = Column(JSON, default=dict)  # {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), 
                       server_default=func.now(), 
                       onupdate=func.now()) 