"""Task models for background job tracking"""
from sqlalchemy import Column, String, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import enum
from app.db.base_class import Base
import uuid

class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskType(str, enum.Enum):
    EMAIL = "email"
    PDF = "pdf"
    REPORT = "report"

class BackgroundTask(Base):
    """Model for tracking background tasks"""
    __tablename__ = "background_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type = Column(SQLEnum(TaskType), nullable=False)
    status = Column(SQLEnum(TaskStatus), nullable=False, default=TaskStatus.PENDING)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    error_message = Column(String, nullable=True)
    task_metadata = Column(JSON, nullable=True)  # Store any task-specific data

    def to_dict(self):
        """Convert task to dictionary"""
        return {
            "id": str(self.id),
            "task_type": self.task_type,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error_message": self.error_message,
            "metadata": self.task_metadata  # Keep metadata in response for backward compatibility
        }
