from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.core.logging_config import logger
import logging

logger = logging.getLogger(__name__)

class FeaturedImageStyleService:
    """Service for managing featured image style settings for projects"""
    
    def __init__(self, db: Session, user_id: str, project_id: str = None):
        self.db = db
        self.user_id = user_id
        self.project_id = project_id

    def store_featured_image_style(self, project_id: str, style: str) -> Dict[str, Any]:
        """
        Store featured image style for a project in the database
        
        Args:
            project_id (str): The project ID
            style (str): The featured image style to store
            
        Returns:
            Dict containing the store operation result
        """
        try:
            logger.info(f"🖼️ Storing featured image style '{style}' for project {project_id}")
            
            # Find the project
            from app.models.project import Project
            project = self.db.query(Project).filter(Project.id == project_id).first()
            
            if not project:
                logger.error(f"Project {project_id} not found")
                return {
                    "status": "error",
                    "message": f"Project {project_id} not found"
                }
            
            # Validate style input
            if not style or not style.strip():
                logger.error("Featured image style cannot be empty")
                return {
                    "status": "error",
                    "message": "Featured image style cannot be empty"
                }
            
            # Store the featured image style in the database
            project.featured_image_style = style.strip()
            self.db.commit()
            
            logger.info(f"✅ Successfully stored featured image style '{style}' for project {project_id}")
            
            return {
                "status": "success",
                "message": "Featured image style stored successfully",
                "project_id": project_id,
                "featured_image_style": style.strip()
            }
            
        except Exception as e:
            logger.error(f"❌ Error storing featured image style: {str(e)}")
            self.db.rollback()
            
            return {
                "status": "error",
                "message": f"Failed to store featured image style: {str(e)}"
            }
    
    def fetch_featured_image_style(self, project_id: str) -> Dict[str, Any]:
        """
        Fetch featured image style for a project from the database
        
        Args:
            project_id (str): The project ID
            
        Returns:
            Dict containing the fetched featured image style
        """
        try:
            logger.info(f"🖼️ Fetching featured image style for project {project_id}")
            
            # Find the project
            from app.models.project import Project
            project = self.db.query(Project).filter(Project.id == project_id).first()
            
            if not project:
                logger.error(f"Project {project_id} not found")
                return {
                    "status": "error",
                    "message": f"Project {project_id} not found"
                }
            
            # Get the featured image style
            featured_image_style = project.featured_image_style
            
            if featured_image_style is None:
                logger.info(f"No featured image style found for project {project_id}")
                return {
                    "status": "success",
                    "message": "No featured image style found for this project",
                    "project_id": project_id,
                    "featured_image_style": None
                }
            
            logger.info(f"✅ Successfully fetched featured image style '{featured_image_style}' for project {project_id}")
            
            return {
                "status": "success",
                "message": "Featured image style retrieved successfully",
                "project_id": project_id,
                "featured_image_style": featured_image_style
            }
            
        except Exception as e:
            logger.error(f"❌ Error fetching featured image style: {str(e)}")
            
            return {
                "status": "error",
                "message": f"Failed to fetch featured image style: {str(e)}"
            }
    
    def get_available_styles(self) -> Dict[str, Any]:
        """
        Get available featured image style options
        
        Returns:
            Dict containing available style options
        """
        try:
            logger.info("🖼️ Fetching available featured image style options")
            
            # Define available featured image styles
            style_options = [
                {
                    "value": "minimalist",
                    "description": "Clean, simple design with lots of white space and minimal elements",
                    "characteristics": ["Clean lines", "White space", "Simple typography", "Subtle colors"]
                },
                {
                    "value": "modern",
                    "description": "Contemporary design with bold elements and current trends",
                    "characteristics": ["Bold typography", "Vibrant colors", "Geometric shapes", "Current trends"]
                },
                {
                    "value": "vintage",
                    "description": "Retro-inspired design with classic elements and aged aesthetics",
                    "characteristics": ["Retro fonts", "Muted colors", "Classic patterns", "Nostalgic feel"]
                },
                {
                    "value": "corporate",
                    "description": "Professional business style with formal and trustworthy appearance",
                    "characteristics": ["Professional fonts", "Corporate colors", "Clean layout", "Business-focused"]
                },
                {
                    "value": "creative",
                    "description": "Artistic and innovative design with unique visual elements",
                    "characteristics": ["Unique layouts", "Creative typography", "Artistic elements", "Innovative design"]
                },
                {
                    "value": "tech",
                    "description": "Technology-focused design with futuristic and digital elements",
                    "characteristics": ["Futuristic fonts", "Tech colors", "Digital elements", "Modern interfaces"]
                },
                {
                    "value": "lifestyle",
                    "description": "Warm and approachable design that appeals to everyday life",
                    "characteristics": ["Friendly fonts", "Warm colors", "Relatable imagery", "Approachable tone"]
                },
                {
                    "value": "luxury",
                    "description": "High-end design with premium and sophisticated elements",
                    "characteristics": ["Elegant fonts", "Premium colors", "Sophisticated layout", "Luxury feel"]
                },
                {
                    "value": "playful",
                    "description": "Fun and energetic design with colorful and dynamic elements",
                    "characteristics": ["Fun fonts", "Bright colors", "Dynamic shapes", "Energetic feel"]
                },
                {
                    "value": "nature",
                    "description": "Organic and natural design inspired by the environment",
                    "characteristics": ["Natural colors", "Organic shapes", "Earthy tones", "Environmental feel"]
                }
            ]
            
            logger.info(f"✅ Successfully retrieved {len(style_options)} featured image style options")
            
            return {
                "status": "success",
                "message": "Featured image style options retrieved successfully",
                "style_options": style_options
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting featured image style options: {str(e)}")
            
            return {
                "status": "error",
                "message": f"Failed to get featured image style options: {str(e)}"
            }
