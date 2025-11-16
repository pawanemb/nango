"""Task schemas for API responses"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
from app.models.task import TaskType, TaskStatus

class TaskBase(BaseModel):
    """Base task schema"""
    task_type: TaskType
    status: TaskStatus
    error_message: Optional[str] = None
    task_metadata: Optional[Dict[str, Any]] = None

class TaskCreate(TaskBase):
    """Schema for creating a task"""
    pass

class TaskResponse(BaseModel):
    """Schema for task response"""
    task_id: str

    class Config:
        from_attributes = True

class TaskStatusResponse(TaskBase):
    """Schema for task status response"""
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
