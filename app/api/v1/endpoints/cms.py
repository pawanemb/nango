from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from app.db.session import get_db_session
from app.middleware.auth_middleware import verify_request_origin
from app.models.wordpress_credentials import WordPressCredentials
from app.models.shopify_credentials import ShopifyCredentials
from app.models.project import Project
from app.services.wordpress_service import WordPressService
from app.services.shopify_service import ShopifyService
from app.core.logging_config import logger
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from fastapi.security import HTTPBearer
from datetime import datetime
from pydantic import Field
from typing import List
from app.models.gsc import GSCAccount
from typing import Any

security = HTTPBearer()
router = APIRouter()  

class WordPressCredentialsCreate(BaseModel):
    base_url: str
    username: str
    password: str

class WordPressCredentialsResponse(BaseModel):
    base_url: str
    username: str
    created_at: str

class ShopifyCredentialsCreate(BaseModel):
    shop_domain: str
    access_token: str
    api_version: str = "2024-01"

class ShopifyCredentialsResponse(BaseModel):
    shop_domain: str
    api_version: str
    created_at: str

class ProjectConnectionsResponse(BaseModel):
    """Response schema for project connections"""
    project_id: UUID
    wordpress_connected: bool = False
    wordpress_url: Optional[str] = None
    wordpress_username: Optional[str] = None
    shopify_connected: bool = False
    shopify_domain: Optional[str] = None
    shopify_api_version: Optional[str] = None
    gsc_connected: bool = False
    gsc_sites: List[str] = Field(default=[], description="List of connected GSC site URLs")
    # created_at: datetime

    class Config:
        from_attributes = True

@router.post("/wordpress/connect", response_model=WordPressCredentialsResponse)
def connect_wordpress(
    request: Request,
    *,
    credentials: WordPressCredentialsCreate,
    current_user = Depends(verify_request_origin)
):
    """
    Connect a WordPress account to a project
    """
    try:
        # Get project_id from path parameters and convert to UUID
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID not provided")
        
        # Check if project exists and user has access
        with get_db_session() as db:
            project = db.query(Project).filter(
                Project.id == project_id,
                Project.user_id == current_user.id
            ).first()
            
            if not project:
                raise HTTPException(
                    status_code=404,
                    detail="Project not found or you don't have access to it"
                )

            # Check if WordPress credentials already exist for this project
            existing_credentials = db.query(WordPressCredentials).filter(
                WordPressCredentials.project_id == project_id
            ).first()
            
            # Check for existing CMS connections in cms_config
            if project.cms_config:
                existing_cms = []
                if 'wordpress' in project.cms_config and project.cms_config['wordpress'].get('connected'):
                    existing_cms.append('WordPress')
                if 'shopify' in project.cms_config and project.cms_config['shopify'].get('connected'):
                    existing_cms.append('Shopify')
                
                # If Shopify is connected and we're trying to connect WordPress
                if 'Shopify' in existing_cms and not existing_credentials:
                    raise HTTPException(
                        status_code=400,
                        detail="Shopify CMS is already connected to this project. Please disconnect Shopify first before connecting WordPress, or use a different project."
                    )
                elif existing_cms and 'WordPress' not in existing_cms:
                    # Other CMS connected (not WordPress)
                    cms_list = ', '.join(existing_cms)
                    raise HTTPException(
                        status_code=400,
                        detail=f"{cms_list} CMS is already connected to this project. Please disconnect existing CMS first before connecting WordPress."
                    )

        # Verify WordPress credentials by trying to connect
        try:
            wp_service = WordPressService(
                base_url=credentials.base_url,
                username=credentials.username,
                password=credentials.password
            )
            # Test WordPress connection
            if not wp_service.test_connection():
                raise HTTPException(
                    status_code=400,
                    detail="Failed to connect to WordPress: Invalid credentials"
                )
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to connect to WordPress: {str(e)}"
            )

        # Create or update WordPress credentials and project cms_config
        with get_db_session() as db:
            # Re-fetch existing credentials in the current session
            existing_creds = db.query(WordPressCredentials).filter(
                WordPressCredentials.project_id == project_id
            ).first()
            
            if existing_creds:
                # Update existing credentials
                existing_creds.base_url = credentials.base_url
                existing_creds.username = credentials.username
                existing_creds.password = credentials.password
                existing_creds.updated_at = datetime.utcnow()
                
                wp_credentials = existing_creds
                logger.info(f"Updated existing WordPress credentials for project {project_id}")
            else:
                # Create new credentials
                wp_credentials = WordPressCredentials(
                    project_id=project_id,
                    base_url=credentials.base_url,
                    username=credentials.username,
                    password=credentials.password
                )
                db.add(wp_credentials)
                logger.info(f"Created new WordPress credentials for project {project_id}")
            
            # Update project cms_config with WordPress connection info
            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                # Initialize cms_config if it doesn't exist
                if not project.cms_config:
                    project.cms_config = {}
                
                # Add/update WordPress configuration
                project.cms_config['wordpress'] = {
                    'connected': True,
                    'base_url': credentials.base_url,
                    'username': credentials.username,
                    'connected_at': datetime.utcnow().isoformat()
                }
                
                db.add(project)
            
            db.commit()
            db.refresh(wp_credentials)

            return WordPressCredentialsResponse(
                base_url=wp_credentials.base_url,
                username=wp_credentials.username,
                created_at=wp_credentials.created_at.isoformat()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error connecting WordPress account: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect WordPress account: {str(e)}"
        )

@router.delete("/wordpress/disconnect")
def delete_wordpress_credentials(
    request: Request,
    current_user = Depends(verify_request_origin)
):
    """
    Delete WordPress credentials for a project
    """
    try:
        # Get project_id from path parameters and convert to UUID
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID not provided")
        try:
            project_id = UUID(project_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid project ID format")

        # Check if project exists and user has access
        with get_db_session() as db:
            project = db.query(Project).filter(
                Project.id == project_id,
                Project.user_id == current_user.id
            ).first()
            
            if not project:
                raise HTTPException(
                    status_code=404,
                    detail="Project not found or you don't have access to it"
                )

            # Delete WordPress credentials
            result = db.query(WordPressCredentials).filter(
                WordPressCredentials.project_id == project_id
            ).delete()

            if result == 0:
                raise HTTPException(
                    status_code=404,
                    detail="WordPress credentials not found for this project"
                )

            # Remove WordPress data from project cms_config
            if project.cms_config and 'wordpress' in project.cms_config:
                del project.cms_config['wordpress']
                # If cms_config becomes empty, set it to None
                if not project.cms_config:
                    project.cms_config = None
                db.add(project)

            db.commit()

        return {"message": "WordPress credentials deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting WordPress credentials: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete WordPress credentials: {str(e)}"
        )

@router.post("/shopify/connect", response_model=ShopifyCredentialsResponse)
def connect_shopify(
    request: Request,
    *,
    credentials: ShopifyCredentialsCreate,
    current_user = Depends(verify_request_origin)
):
    """
    Connect a Shopify store to a project
    """
    try:
        # Get project_id from path parameters
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID not provided")
        
        # Check if project exists and user has access
        with get_db_session() as db:
            project = db.query(Project).filter(
                Project.id == project_id,
                Project.user_id == current_user.id
            ).first()
            
            if not project:
                raise HTTPException(
                    status_code=404,
                    detail="Project not found or you don't have access to it"
                )

            # Check if Shopify credentials already exist for this project
            existing_credentials = db.query(ShopifyCredentials).filter(
                ShopifyCredentials.project_id == project_id
            ).first()
            
            # Check for existing CMS connections in cms_config
            if project.cms_config:
                existing_cms = []
                if 'wordpress' in project.cms_config and project.cms_config['wordpress'].get('connected'):
                    existing_cms.append('WordPress')
                if 'shopify' in project.cms_config and project.cms_config['shopify'].get('connected'):
                    existing_cms.append('Shopify')
                
                # If WordPress is connected and we're trying to connect Shopify
                if 'WordPress' in existing_cms and not existing_credentials:
                    raise HTTPException(
                        status_code=400,
                        detail="WordPress CMS is already connected to this project. Please disconnect WordPress first before connecting Shopify, or use a different project."
                    )
                elif existing_cms and 'Shopify' not in existing_cms:
                    # Other CMS connected (not Shopify)
                    cms_list = ', '.join(existing_cms)
                    raise HTTPException(
                        status_code=400,
                        detail=f"{cms_list} CMS is already connected to this project. Please disconnect existing CMS first before connecting Shopify."
                    )

        # Verify Shopify credentials by trying to connect
        try:
            shopify_service = ShopifyService(
                shop_domain=credentials.shop_domain,
                access_token=credentials.access_token,
                api_version=credentials.api_version
            )
            # Test Shopify connection
            connection_success, error_message = shopify_service.test_connection()
            if not connection_success:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to connect to Shopify: {error_message}"
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to connect to Shopify: {str(e)}"
            )

        # Create or update Shopify credentials and project cms_config
        with get_db_session() as db:
            # Re-fetch existing credentials in the current session
            existing_creds = db.query(ShopifyCredentials).filter(
                ShopifyCredentials.project_id == project_id
            ).first()
            
            if existing_creds:
                # Update existing credentials
                existing_creds.shop_domain = credentials.shop_domain
                existing_creds.access_token = credentials.access_token
                existing_creds.api_version = credentials.api_version
                existing_creds.updated_at = datetime.utcnow()
                
                shopify_credentials = existing_creds
                logger.info(f"Updated existing Shopify credentials for project {project_id}")
            else:
                # Create new credentials
                shopify_credentials = ShopifyCredentials(
                    project_id=project_id,
                    shop_domain=credentials.shop_domain,
                    access_token=credentials.access_token,
                    api_version=credentials.api_version
                )
                db.add(shopify_credentials)
                logger.info(f"Created new Shopify credentials for project {project_id}")
            
            # Update project cms_config with Shopify connection info
            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                # Initialize cms_config if it doesn't exist
                if not project.cms_config:
                    project.cms_config = {}
                
                # Add/update Shopify configuration
                project.cms_config['shopify'] = {
                    'connected': True,
                    'shop_domain': credentials.shop_domain,
                    'api_version': credentials.api_version,
                    'connected_at': datetime.utcnow().isoformat()
                }
                
                db.add(project)
            
            db.commit()
            db.refresh(shopify_credentials)

            return ShopifyCredentialsResponse(
                shop_domain=shopify_credentials.shop_domain,
                api_version=shopify_credentials.api_version,
                created_at=shopify_credentials.created_at.isoformat()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error connecting Shopify store: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect Shopify store: {str(e)}"
        )

@router.delete("/shopify/disconnect")
def delete_shopify_credentials(
    request: Request,
    current_user = Depends(verify_request_origin)
):
    """
    Delete Shopify credentials for a project
    """
    try:
        # Get project_id from path parameters
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID not provided")
        try:
            project_id = UUID(project_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid project ID format")

        # Check if project exists and user has access
        with get_db_session() as db:
            project = db.query(Project).filter(
                Project.id == project_id,
                Project.user_id == current_user.id
            ).first()
            
            if not project:
                raise HTTPException(
                    status_code=404,
                    detail="Project not found or you don't have access to it"
                )

            # Delete Shopify credentials
            result = db.query(ShopifyCredentials).filter(
                ShopifyCredentials.project_id == project_id
            ).delete()

            if result == 0:
                raise HTTPException(
                    status_code=404,
                    detail="Shopify credentials not found for this project"
                )

            # Remove Shopify data from project cms_config
            if project.cms_config and 'shopify' in project.cms_config:
                del project.cms_config['shopify']
                # If cms_config becomes empty, set it to None
                if not project.cms_config:
                    project.cms_config = None
                db.add(project)

            db.commit()

        return {"message": "Shopify credentials deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting Shopify credentials: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete Shopify credentials: {str(e)}"
        )

@router.get("/connections", response_model=ProjectConnectionsResponse)
def get_project_connections(
    request: Request,
    current_user = Depends(verify_request_origin)
) -> Any:
    """
    Get all available connections (WordPress and GSC) for a project
    """
    try:
        project_id = request.path_params.get("project_id")
        logger.info(f"Checking connections for project_id: {project_id}")
        logger.info(f"Current user ID: {current_user.id}")
        
        # Check if project exists and user has access
        with get_db_session() as db:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                logger.error(f"Project not found: {project_id}")
                raise HTTPException(
                    status_code=404,
                    detail="Project not found"
                )
            
            logger.info(f"Project user_id: {project.user_id}")
            if str(project.user_id) != str(current_user.id):
                logger.error(f"Permission denied - user_id types: project={type(project.user_id)}, current={type(current_user.id)}")
                logger.error(f"Values do not match: project={str(project.user_id)}, current={str(current_user.id)}")
                raise HTTPException(
                    status_code=403,
                    detail="Not enough permissions to access this project"
                )

            # Check WordPress connection
            wp_creds = db.query(WordPressCredentials).filter(
                WordPressCredentials.project_id == project_id
            ).first()

            # Check Shopify connection
            shopify_creds = db.query(ShopifyCredentials).filter(
                ShopifyCredentials.project_id == project_id
            ).first()

            # Check GSC connections
            gsc_accounts = db.query(GSCAccount).filter(
                GSCAccount.project_id == project_id
            ).all()

            logger.info(f"WordPress credentials found: {bool(wp_creds)}")
            logger.info(f"Shopify credentials found: {bool(shopify_creds)}")
            logger.info(f"Number of GSC accounts found: {len(gsc_accounts) if gsc_accounts else 0}")

            return ProjectConnectionsResponse(
                project_id=project_id,
                wordpress_connected=bool(wp_creds),
                wordpress_url=wp_creds.base_url if wp_creds else None,
                wordpress_username=wp_creds.username if wp_creds else None,
                shopify_connected=bool(shopify_creds),
                shopify_domain=shopify_creds.shop_domain if shopify_creds else None,
                shopify_api_version=shopify_creds.api_version if shopify_creds else None,
                gsc_connected=bool(gsc_accounts),
                gsc_sites=[account.site_url for account in gsc_accounts] if gsc_accounts else []
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking project connections: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error checking project connections: {str(e)}"
        )

@router.get("/check-cms")
def check_cms_config(
    request: Request,
    current_user = Depends(verify_request_origin)
) -> Any:
    """
    Check CMS configuration from project's cms_config column
    Returns CMS connection data directly from the stored configuration
    """
    try:
        project_id = request.path_params.get("project_id")
        logger.info(f"Checking CMS config for project_id: {project_id}")
        logger.info(f"Current user ID: {current_user.id}")
        
        # Check if project exists and user has access
        with get_db_session() as db:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                logger.error(f"Project not found: {project_id}")
                raise HTTPException(
                    status_code=404,
                    detail="Project not found"
                )
            
            logger.info(f"Project user_id: {project.user_id}")
            if str(project.user_id) != str(current_user.id):
                logger.error(f"Permission denied - user_id types: project={type(project.user_id)}, current={type(current_user.id)}")
                logger.error(f"Values do not match: project={str(project.user_id)}, current={str(current_user.id)}")
                raise HTTPException(
                    status_code=403,
                    detail="Not enough permissions to access this project"
                )

            # Get cms_config from project
            cms_config = project.cms_config if hasattr(project, 'cms_config') and project.cms_config else {}
            
            logger.info(f"CMS config found: {bool(cms_config)}")
            logger.info(f"CMS config content: {cms_config}")

            # Return the cms_config as-is if it exists, otherwise return empty dict
            if cms_config:
                return cms_config
            else:
                return {}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking CMS config: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error checking CMS config: {str(e)}"
        )

'''
@router.get("/wordpress/{project_id}", response_model=WordPressCredentialsResponse)
def get_wordpress_credentials(
    request: Request,
    project_id: UUID,
    current_user = Depends(verify_request_origin)
):
    """
    Get WordPress credentials for a project
    """
    try:
        # Check if project exists and user has access
        with get_db_session() as db:
            project = db.query(Project).filter(
                Project.id == project_id,
                Project.user_id == current_user.id
            ).first()
            
            if not project:
                raise HTTPException(
                    status_code=404,
                    detail="Project not found or you don't have access to it"
                )

            # Get WordPress credentials
            credentials = db.query(WordPressCredentials).filter(
                WordPressCredentials.project_id == project_id
            ).first()

            if not credentials:
                raise HTTPException(
                    status_code=404,
                    detail="WordPress credentials not found for this project"
                )

            return WordPressCredentialsResponse(
                project_id=credentials.project_id,
                base_url=credentials.base_url,
                username=credentials.username,
                created_at=credentials.created_at.isoformat()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching WordPress credentials: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch WordPress credentials: {str(e)}"
        )
'''