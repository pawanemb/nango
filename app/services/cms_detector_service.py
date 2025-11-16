from typing import Optional
from sqlalchemy.orm import Session
from app.models.project import Project
from app.core.logging_config import logger

class CMSDetectorService:
    """
    Simple CMS detector service that identifies which CMS is configured for a project.
    """
    
    @staticmethod
    def detect_cms(project_id: str, db: Session) -> Optional[str]:
        """
        Detect which CMS is configured for a project by checking the cms_config column.
        
        Args:
            project_id: The project ID to check
            db: Database session
            
        Returns:
            str: CMS type (e.g., "wordpress", "drupal", "joomla") or None if no CMS configured
        """
        try:
            # Get project from database
            project = db.query(Project).filter(Project.id == project_id).first()
            
            if not project:
                logger.warning(f"Project {project_id} not found")
                return None
            
            # Check cms_config column
            cms_config = project.cms_config
            
            if not cms_config:
                logger.info(f"No CMS configured for project {project_id}")
                return None
            
            # Simple detection based on cms_config content
            cms_config_str = str(cms_config).lower()
            
            if "wordpress" in cms_config_str:
                logger.info(f"WordPress detected for project {project_id}")
                return "wordpress"
            elif "shopify" in cms_config_str:
                logger.info(f"Shopify detected for project {project_id}")
                return "shopify"
            elif "drupal" in cms_config_str:
                logger.info(f"Drupal detected for project {project_id}")
                return "drupal"
            elif "joomla" in cms_config_str:
                logger.info(f"Joomla detected for project {project_id}")
                return "joomla"
            else:
                logger.warning(f"Unknown CMS type in project {project_id}: {cms_config}")
                return "unknown"
                
        except Exception as e:
            logger.error(f"Error detecting CMS for project {project_id}: {str(e)}")
            return None
    
    @staticmethod
    def is_cms_configured(project_id: str, db: Session) -> bool:
        """
        Check if any CMS is configured for the project.
        
        Args:
            project_id: The project ID to check
            db: Database session
            
        Returns:
            bool: True if CMS is configured, False otherwise
        """
        cms_type = CMSDetectorService.detect_cms(project_id, db)
        return cms_type is not None and cms_type != "unknown"
    
    @staticmethod
    def get_supported_cms_types() -> list:
        """
        Get list of supported CMS types.
        
        Returns:
            list: Supported CMS types
        """
        return ["wordpress", "shopify", "drupal", "joomla"]