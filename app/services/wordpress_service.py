import requests
from requests.auth import HTTPBasicAuth
from typing import Dict, List, Optional
import json
import logging
from requests_toolbelt.multipart.encoder import MultipartEncoder
import os
logger = logging.getLogger(__name__)

class WordPressService:
    def __init__(self, base_url: str, username: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize WordPress service with base URL and optional authentication credentials
        
        Args:
            base_url (str): Base URL of your WordPress site (e.g., 'https://yourblog.com')
            username (str, optional): WordPress username for authenticated requests
            password (str, optional): WordPress application password
        """
        self.base_url = base_url.rstrip('/')  # Remove trailing slash if present
        self.api_url = f"{self.base_url}/wp-json/wp/v2"
        self.auth = HTTPBasicAuth(username, password) if username and password else None

    def upload_image(self, image_data=None, image_path=None, filename=None, mime_type=None, alt_text='', caption='', description=''):
        """
        Upload an image to WordPress media library
        
        Args:
            image_data (bytes, optional): Raw image data as bytes
            image_path (str, optional): Path to the image file (alternative to image_data)
            filename (str, optional): Filename to use for the uploaded image
            mime_type (str, optional): MIME type of the image
            alt_text (str): Alternative text for the image
            caption (str): Caption for the image
            description (str): Description for the image
            
        Returns:
            tuple: (media_id, media_url) if successful, (None, None) otherwise
        """
        try:
            # Ensure we have either image_data or image_path
            if image_data is None and image_path is None:
                logger.error("Either image_data or image_path must be provided")
                return None, None
                
            # If image_data is not provided but image_path is, read the file
            if image_data is None and image_path:
                try:
                    with open(image_path, 'rb') as f:
                        image_data = f.read()
                except Exception as e:
                    logger.error(f"Failed to read image file: {str(e)}")
                    return None, None
                    
            # If filename is not provided but image_path is, extract filename from path
            if not filename and image_path:
                filename = os.path.basename(image_path)
                
            # Ensure we have a filename
            if not filename:
                logger.error("Filename must be provided when using image_data without image_path")
                return None, None
                
            # If mime_type is not provided, try to determine it from filename
            if not mime_type and filename:
                file_ext = os.path.splitext(filename)[1].lower()
                mime_types = {
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif',
                    '.webp': 'image/webp'
                }
                mime_type = mime_types.get(file_ext, 'image/jpeg')
            
            # Ensure image_data is bytes
            if not isinstance(image_data, bytes):
                logger.error("Image data must be bytes")
                return None, None
                
            # Create multipart form data
            multipart_data = MultipartEncoder(
                fields={
                    'file': (filename, image_data, mime_type),
                    'alt_text': alt_text,
                    'caption': caption,
                    'description': description
                }
            )
            
            # Set up headers
            headers = {'Content-Type': multipart_data.content_type}
            
            # Make the request to WordPress API
            response = requests.post(
                f"{self.api_url}/media",
                data=multipart_data,
                headers=headers,
                auth=self.auth
            )
            
            if response.status_code in (200, 201):
                data = response.json()
                media_id = data.get('id')
                media_url = data.get('source_url')
                logger.info(f"Successfully uploaded image: {filename}, media ID: {media_id}")
                return media_id, media_url
            else:
                logger.error(f"Error uploading image: {response.status_code} - {response.text}")
                return None, None
                
        except Exception as e:
            logger.exception(f"Exception uploading image: {str(e)}")
            return None, None
            
    def attach_image_to_post(self, post_id: int, media_id: int, set_as_featured: bool = True):
        """
        Attach an image to a WordPress blog post
        
        Args:
            post_id (int): WordPress post ID
            media_id (int): WordPress media ID
            set_as_featured (bool): Set as featured image if True
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if set_as_featured:
                # Set as featured image
                data = {
                    'featured_media': media_id
                }
                
                response = requests.post(
                    f"{self.api_url}/posts/{post_id}",
                    json=data,
                    headers={'Content-Type': 'application/json'},
                    auth=self.auth
                )
                
                if response.status_code in (200, 201):
                    logger.info(f"Successfully set media ID {media_id} as featured image for post ID {post_id}")
                    return True
                else:
                    logger.error(f"Error setting featured image: {response.status_code} - {response.text}")
                    return False
            
            return True
        except Exception as e:
            logger.exception(f"Exception attaching image to post: {str(e)}")
            return False


    def create_post(self, post_data: Dict) -> Dict:
        """
        Create a new WordPress post
        
        Args:
            post_data (Dict): Post data including title, content, status, etc.
            
        Returns:
            Dict: Response from WordPress API
        """
        endpoint = f"{self.api_url}/posts"
        logger.info(f"Creating WordPress post with data: {post_data}")
        
        try:
            response = requests.post(endpoint, json=post_data, auth=self.auth)
            response.raise_for_status()
            result = response.json()
            logger.info(f"WordPress post creation response: {result}")
            return result
        except requests.RequestException as e:
            logger.error(f"Error creating WordPress post: {str(e)}")
            raise

    def update_post(self, post_id: int, post_data: Dict) -> Dict:
        """
        Update an existing WordPress post
        
        Args:
            post_id (int): ID of the post to update
            post_data (Dict): Updated post data
            
        Returns:
            Dict: Response from WordPress API
        """
        endpoint = f"{self.api_url}/posts/{post_id}"
        logger.info(f"Updating WordPress post {post_id} with data: {post_data}")
        
        try:
            response = requests.post(endpoint, json=post_data, auth=self.auth)
            response.raise_for_status()
            result = response.json()
            logger.info(f"WordPress post update response: {result}")
            return result
        except requests.RequestException as e:
            logger.error(f"Error updating WordPress post {post_id}: {str(e)}")
            raise

    def get_categories(self) -> List[Dict]:
        """
        Get all WordPress categories
        
        Returns:
            List[Dict]: List of categories with their IDs and names
        """
        endpoint = f"{self.api_url}/categories"
        params = {
            'per_page': 100,  # Get up to 100 categories
            'orderby': 'name',
            'order': 'asc'
        }
        
        try:
            response = requests.get(endpoint, params=params, auth=self.auth)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error getting WordPress categories: {str(e)}")
            raise

    def create_category(self, name: str) -> Optional[dict]:
        """Create a new WordPress category."""
        try:
            data = {
                "name": name,
                "slug": name.lower().replace(" ", "-")
            }
            response = requests.post(
                f"{self.base_url}/wp-json/wp/v2/categories",
                headers={"Content-Type": "application/json"},
                json=data,
                auth=self.auth
            )
            if response.status_code == 201:
                return response.json()
            else:
                logger.error(f"Failed to create category: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error creating WordPress category: {str(e)}")
            return None

    def create_tag(self, name: str) -> Optional[dict]:
        """Create a new WordPress tag."""
        try:
            data = {
                "name": name,
                "slug": name.lower().replace(" ", "-")
            }
            response = requests.post(
                f"{self.base_url}/wp-json/wp/v2/tags",
                headers={"Content-Type": "application/json"},
                json=data,
                auth=self.auth
            )
            if response.status_code == 201:
                return response.json()
            else:
                logger.error(f"Failed to create tag: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error creating WordPress tag: {str(e)}")
            return None

    def get_tags(self) -> List[Dict]:
        """
        Get all WordPress tags
        
        Returns:
            List[Dict]: List of tags with their IDs and names
        """
        endpoint = f"{self.api_url}/tags"
        params = {
            'per_page': 100,  # Get up to 100 tags
            'orderby': 'name',
            'order': 'asc'
        }
        
        try:
            response = requests.get(endpoint, params=params, auth=self.auth)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error getting WordPress tags: {str(e)}")
            raise

    def upload_media(self, image_url: str) -> Optional[int]:
        """Upload media to WordPress and return the media ID."""
        try:
            # Download the image from the URL
            response = requests.get(image_url)
            if response.status_code != 200:
                logger.error(f"Failed to download image from {image_url}")
                return None
            
            image_data = response.content
            filename = image_url.split('/')[-1]
            
            # Upload to WordPress
            headers = {
                'Content-Type': 'image/jpeg',  # Adjust if needed based on image type
                'Content-Disposition': f'attachment; filename={filename}'
            }
            
            response = requests.post(
                f"{self.base_url}/wp-json/wp/v2/media",
                headers=headers,
                data=image_data,
                auth=self.auth
            )
            if response.status_code != 201:
                logger.error(f"Failed to upload media to WordPress: {response.text}")
                return None
            
            response_data = response.json()
            return response_data.get('id')
            
        except Exception as e:
            logger.error(f"Error uploading media to WordPress: {str(e)}")
            return None

    def test_connection(self) -> bool:
        """
        Test the connection to WordPress API using /users/me endpoint
        
        Returns:
            bool: True if connection is successful, False otherwise
        """
        try:
            endpoint = f"{self.api_url}/users/me"
            response = requests.get(endpoint, auth=self.auth)
            response.raise_for_status()
            return True
        except Exception:
            return False
