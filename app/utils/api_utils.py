from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.project import Project
from typing import Optional


class APIUtils:
    """Shared utility functions for API endpoints"""
    
    @staticmethod
    def validate_uuid(uuid_str: str) -> str:
        """
        Validate UUID format and return as string.
        
        Args:
            uuid_str: UUID string to validate
            
        Returns:
            Valid UUID string
            
        Raises:
            HTTPException: If UUID format is invalid
        """
        try:
            UUID(uuid_str)
            return uuid_str
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail=f"Project ID '{uuid_str}' not found"
            )
    
    @staticmethod
    def validate_objectid(objectid_str: str) -> str:
        """
        Validate MongoDB ObjectId format.
        
        Args:
            objectid_str: ObjectId string to validate
            
        Returns:
            Valid ObjectId string
            
        Raises:
            HTTPException: If ObjectId format is invalid
        """
        from bson import ObjectId
        from bson.errors import InvalidId
        
        try:
            # This will raise InvalidId if not valid
            ObjectId(objectid_str)
            return objectid_str
        except (InvalidId, TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail=f"Blog ID '{objectid_str}' not found"
            )
    
    @staticmethod
    def verify_project_access(project_id: str, user_id: str, db: Session) -> Optional[Project]:
        """
        Verify if user has access to the project.
        
        Args:
            project_id: Project UUID string
            user_id: User ID string
            db: Database session
            
        Returns:
            Project object if access granted
            
        Raises:
            HTTPException: If project not found or access denied
        """
        # Validate UUID format before database query as safety net
        APIUtils.validate_uuid(project_id)
        
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == user_id
        ).first()
        
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id} not found or access denied"
            )
        
        return project
    
    @staticmethod
    def get_mongodb_blog_document(mongodb_service, blog_id: str, project_id: str, user_id: str, projection: dict = None):
        """
        Get MongoDB blog document with access validation and optional projection.
        
        Args:
            mongodb_service: MongoDBService instance
            blog_id: Blog document ID
            project_id: Project ID for validation
            user_id: User ID for validation
            projection: Optional fields to include/exclude
            
        Returns:
            Blog document
            
        Raises:
            HTTPException: If blog not found or access denied
        """
        from bson import ObjectId
        
        # Validate ObjectId format before using it
        APIUtils.validate_objectid(blog_id)
        
        query = {
            "_id": ObjectId(blog_id),
            "project_id": project_id,
            "user_id": user_id
        }
        
        if projection:
            blog_doc = mongodb_service.get_sync_db()['blogs'].find_one(query, projection)
        else:
            blog_doc = mongodb_service.get_sync_db()['blogs'].find_one(query)
        
        if not blog_doc:
            raise HTTPException(
                status_code=404,
                detail=f"Blog {blog_id} not found or access denied"
            )
        
        return blog_doc
    
    @staticmethod
    def create_minimal_response(status: str, data=None, **kwargs):
        """
        Create optimized response with minimal payload.
        
        Args:
            status: Response status
            data: Main response data
            **kwargs: Additional response fields
            
        Returns:
            Minimal response dictionary
        """
        response = {"status": status}
        
        if data is not None:
            response["data"] = data
            
        # Only add non-None kwargs
        for key, value in kwargs.items():
            if value is not None:
                response[key] = value
                
        return response
    
    @staticmethod
    def bulk_mongodb_update(mongodb_service, collection_name: str, operations: list):
        """
        Perform bulk MongoDB operations for better performance.
        
        Args:
            mongodb_service: MongoDBService instance
            collection_name: Collection name
            operations: List of operations to perform
            
        Returns:
            Bulk operation result
        """
        if not operations:
            return None
            
        try:
            collection = mongodb_service.get_sync_db()[collection_name]
            return collection.bulk_write(operations, ordered=False)
        except Exception as e:
            from app.core.logging_config import logger
            logger.error(f"Bulk MongoDB operation failed: {e}")
            raise
    
    @staticmethod
    def optimize_mongodb_query(mongodb_service, collection_name: str, filter_query: dict, projection: dict = None):
        """
        Optimized MongoDB query with projection to reduce payload.
        
        Args:
            mongodb_service: MongoDBService instance
            collection_name: Collection name
            filter_query: Query filter
            projection: Fields to include/exclude
            
        Returns:
            Query result
        """
        try:
            collection = mongodb_service.get_sync_db()[collection_name]
            if projection:
                return collection.find_one(filter_query, projection)
            return collection.find_one(filter_query)
        except Exception as e:
            from app.core.logging_config import logger
            logger.error(f"Optimized MongoDB query failed: {e}")
            raise