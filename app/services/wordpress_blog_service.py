from typing import List, Dict, Optional
import requests
from requests.auth import HTTPBasicAuth
from sqlalchemy.orm import Session
from app.models.wordpress_credentials import WordPressCredentials
from app.core.logging_config import logger
from datetime import datetime
import pytz
import math

class WordPressBlogService:
    """
    WordPress service for fetching blogs from connected WordPress CMS.
    """
    
    def __init__(self, base_url: str, username: str, password: str):
        """
        Initialize WordPress blog service with credentials.
        
        Args:
            base_url: WordPress site URL
            username: WordPress username
            password: WordPress application password
        """
        self.base_url = base_url.rstrip('/')
        self.api_base = f"{self.base_url}/wp-json/wp/v2"
        self.auth = HTTPBasicAuth(username, password)
        self.session = requests.Session()
        self.session.auth = self.auth
        
    @classmethod
    def from_project(cls, project_id: str, db: Session) -> Optional['WordPressBlogService']:
        """
        Create WordPress service instance from project credentials.
        
        Args:
            project_id: Project ID
            db: Database session
            
        Returns:
            WordPressBlogService instance or None if credentials not found
        """
        try:
            credentials = db.query(WordPressCredentials).filter(
                WordPressCredentials.project_id == project_id
            ).first()
            
            if not credentials:
                logger.warning(f"WordPress credentials not found for project {project_id}")
                return None
                
            return cls(
                base_url=credentials.base_url,
                username=credentials.username,
                password=credentials.password
            )
        except Exception as e:
            logger.error(f"Failed to create WordPress service for project {project_id}: {str(e)}")
            return None
    
    def get_posts(self, page: int = 1, per_page: int = 10, status: str = "any", search: str = None) -> Dict:
        """
        Fetch WordPress posts/blogs.
        
        Args:
            page: Page number (starts from 1)
            per_page: Number of posts per page
            status: Post status (any, publish, draft, private, pending, future)
            search: Search term for post titles
            
        Returns:
            Dict with posts data and pagination info
        """
        try:
            params = {
                'page': page,
                'per_page': per_page,
                'status': status,
                'orderby': 'modified',
                'order': 'desc',
                '_embed': 'wp:term'  # Include category/tag data
            }
            
            # Add search parameter if provided
            if search:
                # WordPress REST API doesn't support title-only search directly
                # We'll use regular search and filter results client-side
                params['search'] = search
                params['per_page'] = per_page * 2  # Fetch more to account for filtering
                logger.info(f"WordPress search query: '{search}' (will filter title-only client-side)")
                logger.info(f"🔍 Fetching {params['per_page']} posts to filter for title matches")
            
            logger.info(f"Fetching WordPress posts: page={page}, per_page={per_page}")
            
            # Debug: Log the full URL being called
            full_url = f"{self.api_base}/posts"
            logger.info(f"🔍 WordPress API URL: {full_url}")
            logger.info(f"🔍 WordPress API params: {params}")
            
            response = self.session.get(
                full_url,
                params=params,
                timeout=30
            )
            
            # Debug: Log the actual URL called
            logger.info(f"🔍 Actual WordPress URL called: {response.url}")
            
            if response.status_code == 200:
                posts = response.json()
                
                # Get pagination info from headers
                total_posts = int(response.headers.get('X-WP-Total', 0))
                total_pages = int(response.headers.get('X-WP-TotalPages', 0))
                
                # Debug search results
                if search:
                    logger.info(f"🔍 WordPress search for '{search}' returned {len(posts)} posts")
                    logger.info(f"🔍 WordPress search headers - Total: {total_posts}, Pages: {total_pages}")
                    if posts:
                        # Log first post title for debugging
                        first_title = posts[0].get('title', {}).get('rendered', 'No title')
                        logger.info(f"🔍 First result title: '{first_title}'")
                else:
                    logger.info(f"🔍 WordPress regular fetch returned {len(posts)} posts")
                
                # Transform WordPress posts to our format
                transformed_posts = []
                for post in posts:
                    # If searching, filter to only include posts with search term in title
                    if search:
                        post_title = post.get('title', {}).get('rendered', '').lower()
                        search_term = search.lower()
                        
                        if search_term in post_title:
                            transformed_post = self._transform_post(post)
                            transformed_posts.append(transformed_post)
                            logger.info(f"🔍 Title match: '{post_title}' contains '{search_term}'")
                        else:
                            logger.info(f"🔍 Title skip: '{post_title}' doesn't contain '{search_term}'")
                    else:
                        transformed_post = self._transform_post(post)
                        transformed_posts.append(transformed_post)
                
                # Limit results to requested per_page after filtering
                if search and len(transformed_posts) > per_page:
                    transformed_posts = transformed_posts[:per_page]
                    logger.info(f"🔍 Filtered results limited to {per_page} posts")
                
                logger.info(f"Successfully fetched {len(transformed_posts)} WordPress posts")
                
                return {
                    'posts': transformed_posts,
                    'pagination': {
                        'current_page': page,
                        'per_page': per_page,
                        'total_posts': total_posts if not search else len(transformed_posts),
                        'total_pages': total_pages if not search else math.ceil(len(transformed_posts) / per_page),
                        'has_next': page < total_pages,
                        'has_previous': page > 1
                    }
                }
            else:
                logger.error(f"WordPress API error: {response.status_code} - {response.text}")
                logger.error(f"🔍 Failed URL: {response.url}")
                if search:
                    logger.error(f"🔍 Search term was: '{search}'")
                return {'posts': [], 'pagination': None}
                
        except Exception as e:
            logger.error(f"Error fetching WordPress posts: {str(e)}")
            return {'posts': [], 'pagination': None}
    
    def get_post_by_id(self, post_id: int) -> Optional[Dict]:
        """
        Fetch a specific WordPress post by ID with full content.
        
        Args:
            post_id: WordPress post ID
            
        Returns:
            Transformed post data with full content or None
        """
        try:
            logger.info(f"Fetching WordPress post ID: {post_id}")
            
            # Include _embed for categories, featured media, and author data for individual posts
            params = {
                '_embed': 'wp:term,wp:featuredmedia,author'  # Include category/tag data, featured media, and author
            }
            
            response = self.session.get(
                f"{self.api_base}/posts/{post_id}",
                params=params,
                timeout=30
            )
            
            logger.info(f"🔍 WordPress individual post API URL: {response.url}")
            
            if response.status_code == 200:
                post = response.json()
                # Transform post with full content for individual viewing
                transformed_post = self._transform_post_full(post)
                logger.info(f"Successfully fetched WordPress post: {post['title']['rendered']}")
                return transformed_post
            else:
                logger.error(f"WordPress post not found: {post_id} - Status: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching WordPress post {post_id}: {str(e)}")
            return None
    
    def delete_post_by_id(self, post_id: int) -> bool:
        """
        Delete a specific WordPress post by ID (moves to trash).
        
        Args:
            post_id: WordPress post ID
            
        Returns:
            True if moved to trash successfully, False otherwise
        """
        try:
            logger.info(f"Moving WordPress post ID {post_id} to trash")
            
            response = self.session.delete(
                f"{self.api_base}/posts/{post_id}",
                timeout=30
            )
            
            logger.info(f"🔍 WordPress delete API URL: {response.url}")
            logger.info(f"🔍 WordPress delete response status: {response.status_code}")
            
            if response.status_code == 200:
                deleted_post = response.json()
                logger.info(f"Successfully moved WordPress post to trash: {deleted_post.get('title', {}).get('rendered', 'Unknown')}")
                logger.info(f"🔍 Post status after deletion: {deleted_post.get('status', 'trash')}")
                return True
            elif response.status_code == 404:
                logger.error(f"WordPress post not found: {post_id}")
                return False
            elif response.status_code == 401 or response.status_code == 403:
                logger.error(f"WordPress delete permission denied for post {post_id}: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
            else:
                logger.error(f"WordPress delete failed for post {post_id}: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting WordPress post {post_id}: {str(e)}")
            return False
    
    def get_categories(self) -> List[Dict]:
        """
        Fetch all WordPress categories.
        
        Returns:
            List of category objects with id, name, slug, count
        """
        try:
            logger.info("Fetching WordPress categories")
            
            # Fetch categories with high per_page to get all categories
            params = {
                'per_page': 100,  # WordPress default max
                'orderby': 'name',
                'order': 'asc'
            }
            
            response = self.session.get(
                f"{self.api_base}/categories",
                params=params,
                timeout=30
            )
            
            logger.info(f"🔍 WordPress categories API URL: {response.url}")
            logger.info(f"🔍 WordPress categories response status: {response.status_code}")
            
            if response.status_code == 200:
                categories = response.json()
                
                # Transform categories to clean format
                transformed_categories = []
                for category in categories:
                    transformed_categories.append({
                        'id': category.get('id'),
                        'name': category.get('name', ''),
                        'slug': category.get('slug', ''),
                        'description': category.get('description', ''),
                        'count': category.get('count', 0),
                        'parent': category.get('parent', 0)
                    })
                
                logger.info(f"Successfully fetched {len(transformed_categories)} WordPress categories")
                return transformed_categories
                
            else:
                logger.error(f"WordPress categories fetch failed: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching WordPress categories: {str(e)}")
            return []
    
    def get_tags(self) -> List[Dict]:
        """
        Fetch all WordPress tags.
        
        Returns:
            List of tag objects with id, name, slug, count
        """
        try:
            logger.info("Fetching WordPress tags")
            
            # Fetch tags with high per_page to get all tags
            params = {
                'per_page': 100,  # WordPress default max
                'orderby': 'name',
                'order': 'asc'
            }
            
            response = self.session.get(
                f"{self.api_base}/tags",
                params=params,
                timeout=30
            )
            
            logger.info(f"🔍 WordPress tags API URL: {response.url}")
            logger.info(f"🔍 WordPress tags response status: {response.status_code}")
            
            if response.status_code == 200:
                tags = response.json()
                
                # Transform tags to clean format
                transformed_tags = []
                for tag in tags:
                    transformed_tags.append({
                        'id': tag.get('id'),
                        'name': tag.get('name', ''),
                        'slug': tag.get('slug', ''),
                        'description': tag.get('description', ''),
                        'count': tag.get('count', 0)
                    })
                
                logger.info(f"Successfully fetched {len(transformed_tags)} WordPress tags")
                return transformed_tags
                
            else:
                logger.error(f"WordPress tags fetch failed: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching WordPress tags: {str(e)}")
            return []
    
    def upload_image(self, file_content: bytes, filename: str, content_type: str = None) -> Optional[Dict]:
        """
        Upload an image to WordPress media library.
        
        Args:
            file_content: Image file bytes
            filename: Original filename
            content_type: MIME type of the file
            
        Returns:
            WordPress media object with URL and ID, or None if failed
        """
        try:
            # Clean filename - remove query parameters and special characters
            clean_filename = filename.split('?')[0].strip()
            if not clean_filename:
                clean_filename = "uploaded-image.png"
            
            logger.info(f"Uploading image to WordPress: {clean_filename}")
            
            # Determine content type if not provided
            if not content_type:
                if clean_filename.lower().endswith('.jpg') or clean_filename.lower().endswith('.jpeg'):
                    content_type = 'image/jpeg'
                elif clean_filename.lower().endswith('.png'):
                    content_type = 'image/png'
                elif clean_filename.lower().endswith('.gif'):
                    content_type = 'image/gif'
                elif clean_filename.lower().endswith('.webp'):
                    content_type = 'image/webp'
                else:
                    # Default to PNG for unknown extensions to avoid octet-stream
                    content_type = 'image/png'
                    if '.' not in clean_filename:
                        clean_filename += '.png'
            
            # Prepare headers for media upload
            headers = {
                'Content-Type': content_type,
                'Content-Disposition': f'attachment; filename="{clean_filename}"'
            }
            
            logger.info(f"🔍 WordPress image upload - Original: {filename}, Clean: {clean_filename}, Content-Type: {content_type}")
            
            response = self.session.post(
                f"{self.api_base}/media",
                data=file_content,
                headers=headers,
                timeout=60  # Longer timeout for file upload
            )
            
            logger.info(f"🔍 WordPress upload API URL: {response.url}")
            logger.info(f"🔍 WordPress upload response status: {response.status_code}")
            
            if response.status_code == 201:  # 201 Created for successful upload
                media = response.json()
                
                # Transform media response to clean format
                uploaded_image = {
                    'id': media.get('id'),
                    'title': media.get('title', {}).get('rendered', ''),
                    'filename': media.get('source_url', '').split('/')[-1],
                    'url': media.get('source_url', ''),
                    'mime_type': media.get('mime_type', ''),
                    'file_size': media.get('media_details', {}).get('filesize', 0),
                    'width': media.get('media_details', {}).get('width', 0),
                    'height': media.get('media_details', {}).get('height', 0),
                    'alt_text': media.get('alt_text', ''),
                    'caption': media.get('caption', {}).get('rendered', ''),
                    'date': media.get('date', ''),
                    'sizes': media.get('media_details', {}).get('sizes', {})
                }
                
                logger.info(f"Successfully uploaded image to WordPress: {uploaded_image['url']}")
                logger.info(f"🔍 Image ID: {uploaded_image['id']}, Size: {uploaded_image['file_size']} bytes")
                
                return uploaded_image
                
            else:
                logger.error(f"WordPress image upload failed: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error uploading image to WordPress: {str(e)}")
            return None
    
    def get_authors(self) -> List[Dict]:
        """
        Fetch all WordPress users/authors.
        
        Returns:
            List of author objects with id, name, email, role
        """
        try:
            logger.info("Fetching WordPress authors")
            
            # Fetch users with high per_page to get all authors
            params = {
                'per_page': 100,  # WordPress default max
                'orderby': 'name',
                'order': 'asc',
                'context': 'edit'  # Get more detailed info including email
            }
            
            response = self.session.get(
                f"{self.api_base}/users",
                params=params,
                timeout=30
            )
            
            logger.info(f"🔍 WordPress authors API URL: {response.url}")
            logger.info(f"🔍 WordPress authors response status: {response.status_code}")
            
            if response.status_code == 200:
                authors = response.json()
                
                # Transform authors to clean format
                transformed_authors = []
                for author in authors:
                    transformed_authors.append({
                        'id': author.get('id'),
                        'name': author.get('name', ''),
                        'username': author.get('username', ''),
                        'email': author.get('email', ''),
                        'first_name': author.get('first_name', ''),
                        'last_name': author.get('last_name', ''),
                        'nickname': author.get('nickname', ''),
                        'slug': author.get('slug', ''),
                        'url': author.get('url', ''),
                        'description': author.get('description', ''),
                        'roles': author.get('roles', []),
                        'capabilities': author.get('capabilities', {}),
                        'avatar_urls': author.get('avatar_urls', {}),
                        'registered_date': author.get('registered_date', ''),
                        'post_count': 0  # Will be filled if needed
                    })
                
                logger.info(f"Successfully fetched {len(transformed_authors)} WordPress authors")
                return transformed_authors
                
            else:
                logger.error(f"WordPress authors fetch failed: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching WordPress authors: {str(e)}")
            return []
    
    def update_post(self, post_id: int, update_data: Dict) -> Optional[Dict]:
        """
        Update a WordPress post by ID.
        
        Args:
            post_id: WordPress post ID
            update_data: Dictionary containing fields to update
            
        Returns:
            Updated post data or None if failed
        """
        try:
            logger.info(f"Updating WordPress post ID {post_id}")
            logger.info(f"🔍 Update data: {update_data}")
            
            # Filter out None values to avoid sending empty fields
            filtered_data = {k: v for k, v in update_data.items() if v is not None}
            
            if not filtered_data:
                logger.warning("No valid data provided for update")
                return None
            
            logger.info(f"🔍 Filtered update data: {filtered_data}")
            
            # Include embedded data in update response to get full post details
            params = {
                '_embed': 'wp:term,wp:featuredmedia,author'
            }
            
            response = self.session.post(
                f"{self.api_base}/posts/{post_id}",
                json=filtered_data,
                params=params,
                timeout=30
            )
            
            logger.info(f"🔍 WordPress update API URL: {response.url}")
            logger.info(f"🔍 WordPress update response status: {response.status_code}")
            
            if response.status_code == 200:
                updated_post = response.json()
                # Transform updated post with full content for response
                transformed_post = self._transform_post_full(updated_post)
                logger.info(f"Successfully updated WordPress post: {updated_post.get('title', {}).get('rendered', 'Unknown')}")
                logger.info(f"🔍 Updated post status: {updated_post.get('status', 'unknown')}")
                return transformed_post
            elif response.status_code == 404:
                logger.error(f"WordPress post not found: {post_id}")
                return None
            elif response.status_code == 401 or response.status_code == 403:
                logger.error(f"WordPress update permission denied for post {post_id}: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
            else:
                logger.error(f"WordPress update failed for post {post_id}: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error updating WordPress post {post_id}: {str(e)}")
            return None
    
    def _transform_post_full(self, wp_post: Dict) -> Dict:
        """
        Transform WordPress post to our blog format with FULL CONTENT.
        Used for individual blog viewing.
        
        Args:
            wp_post: WordPress post data
            
        Returns:
            Transformed blog data with full content
        """
        try:
            # Parse WordPress dates
            created_at = self._parse_wp_date(wp_post.get('date', ''))
            updated_at = self._parse_wp_date(wp_post.get('modified', ''))
            
            # Extract all fields for individual viewing
            title = wp_post.get('title', {}).get('rendered', '')
            content = wp_post.get('content', {}).get('rendered', '')  # FULL CONTENT
            excerpt = wp_post.get('excerpt', {}).get('rendered', '')
            
            # Calculate word count from content
            words_count = len(content.replace('<p>', ' ').replace('</p>', ' ').split()) if content else 0
            
            # Extract category and tag names from embedded data
            category_names = []
            tag_names = []
            if '_embedded' in wp_post and 'wp:term' in wp_post['_embedded']:
                for term_array in wp_post['_embedded']['wp:term']:
                    for term in term_array:
                        if term.get('taxonomy') == 'category':
                            category_names.append(term.get('name', ''))
                        elif term.get('taxonomy') == 'post_tag':
                            tag_names.append(term.get('name', ''))
            
            # WordPress-specific fields for individual blogs
            wp_slug = wp_post.get('slug', '')
            wp_url = wp_post.get('link', '')
            
            # Extract detailed author information from embedded data
            author_details = None
            if '_embedded' in wp_post and 'author' in wp_post['_embedded']:
                author_data = wp_post['_embedded']['author']
                if author_data and len(author_data) > 0:
                    author = author_data[0]
                    author_details = {
                        'id': author.get('id'),
                        'name': author.get('name', ''),
                        'username': author.get('username', ''),
                        'email': author.get('email', ''),
                        'first_name': author.get('first_name', ''),
                        'last_name': author.get('last_name', ''),
                        'description': author.get('description', ''),
                        'url': author.get('url', ''),
                        'avatar_urls': author.get('avatar_urls', {}),
                        'roles': author.get('roles', [])
                    }
            
            # Extract detailed featured media information from embedded data
            featured_media_details = None
            if '_embedded' in wp_post and 'wp:featuredmedia' in wp_post['_embedded']:
                media_data = wp_post['_embedded']['wp:featuredmedia']
                if media_data and len(media_data) > 0:
                    media = media_data[0]
                    media_details = media.get('media_details', {})
                    featured_media_details = {
                        'id': media.get('id'),
                        'title': media.get('title', {}).get('rendered', ''),
                        'url': media.get('source_url', ''),
                        'alt_text': media.get('alt_text', ''),
                        'caption': media.get('caption', {}).get('rendered', ''),
                        'description': media.get('description', {}).get('rendered', ''),
                        'mime_type': media.get('mime_type', ''),
                        'width': media_details.get('width', 0),
                        'height': media_details.get('height', 0),
                        'file_size': media_details.get('filesize', 0)
                    }
            
            return {
                'id': str(wp_post.get('id')),
                'title': title,
                'content': content,  # FULL HTML CONTENT
                'excerpt': excerpt,  # Post excerpt
                'status': wp_post.get('status', 'publish'),
                'source': 'wordpress',
                'words_count': words_count,  # Calculated from content
                'created_at': created_at,
                'updated_at': updated_at,
                'categories': category_names,
                'tags': tag_names,  # WordPress tag names
                # WordPress-specific metadata
                'wp_url': wp_url,
                'wp_slug': wp_slug,
                'metadata': {
                    'wp_featured_media': featured_media_details,  # Detailed featured media info
                    'wp_author': author_details  # Detailed author info
                }
            }
        except Exception as e:
            logger.error(f"Error transforming WordPress post for individual view: {str(e)}")
            return {}

    def _transform_post(self, wp_post: Dict) -> Dict:
        """
        Transform WordPress post to our blog format.
        
        Args:
            wp_post: WordPress post data
            
        Returns:
            Transformed blog data
        """
        try:
            # Parse WordPress dates
            created_at = self._parse_wp_date(wp_post.get('date', ''))
            updated_at = self._parse_wp_date(wp_post.get('modified', ''))
            
            # Extract basic fields only
            title = wp_post.get('title', {}).get('rendered', '')
            
            # Set minimal word count since we're not including content
            words_count = 0
            
            # Extract category and tag names from embedded data
            category_names = []
            tag_names = []
            if '_embedded' in wp_post and 'wp:term' in wp_post['_embedded']:
                # wp:term contains arrays for different taxonomies (categories, tags, etc.)
                for term_array in wp_post['_embedded']['wp:term']:
                    for term in term_array:
                        if term.get('taxonomy') == 'category':
                            category_names.append(term.get('name', ''))
                        elif term.get('taxonomy') == 'post_tag':
                            tag_names.append(term.get('name', ''))
            
            return {
                'id': str(wp_post.get('id')),
                'title': title,
                'status': wp_post.get('status', 'publish'),
                'source': 'wordpress',
                'words_count': words_count,
                'created_at': created_at,
                'updated_at': updated_at,
                'categories': category_names,
                'tags': tag_names
            }
        except Exception as e:
            logger.error(f"Error transforming WordPress post: {str(e)}")
            return {}
    
    def _parse_wp_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse WordPress date string to datetime object.
        
        Args:
            date_str: WordPress date string
            
        Returns:
            Parsed datetime object or None
        """
        try:
            if not date_str:
                return None
                
            # WordPress returns UTC time
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            
            # Convert to IST
            ist_tz = pytz.timezone('Asia/Kolkata')
            return dt.astimezone(ist_tz)
            
        except Exception as e:
            logger.error(f"Error parsing WordPress date {date_str}: {str(e)}")
            return None
    
    def create_category(self, name: str) -> Optional[Dict]:
        """
        Create a new WordPress category.
        
        Args:
            name: Category name
            
        Returns:
            Created category data or None if failed
        """
        try:
            logger.info(f"Creating WordPress category: {name}")
            
            data = {
                "name": name,
                "slug": name.lower().replace(" ", "-").replace("_", "-")
            }
            
            response = self.session.post(
                f"{self.api_base}/categories",
                json=data,
                timeout=30
            )
            
            logger.info(f"🔍 WordPress create category API URL: {response.url}")
            logger.info(f"🔍 WordPress create category response status: {response.status_code}")
            
            if response.status_code == 201:  # 201 Created
                category = response.json()
                
                # Transform to clean format
                created_category = {
                    'id': category.get('id'),
                    'name': category.get('name', ''),
                    'slug': category.get('slug', ''),
                    'description': category.get('description', ''),
                    'count': category.get('count', 0),
                    'parent': category.get('parent', 0)
                }
                
                logger.info(f"Successfully created WordPress category: {name} (ID: {created_category['id']})")
                return created_category
                
            else:
                logger.error(f"WordPress category creation failed: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating WordPress category: {str(e)}")
            return None
    
    def create_tag(self, name: str) -> Optional[Dict]:
        """
        Create a new WordPress tag.
        
        Args:
            name: Tag name
            
        Returns:
            Created tag data or None if failed
        """
        try:
            logger.info(f"Creating WordPress tag: {name}")
            
            data = {
                "name": name,
                "slug": name.lower().replace(" ", "-").replace("_", "-")
            }
            
            response = self.session.post(
                f"{self.api_base}/tags",
                json=data,
                timeout=30
            )
            
            logger.info(f"🔍 WordPress create tag API URL: {response.url}")
            logger.info(f"🔍 WordPress create tag response status: {response.status_code}")
            
            if response.status_code == 201:  # 201 Created
                tag = response.json()
                
                # Transform to clean format
                created_tag = {
                    'id': tag.get('id'),
                    'name': tag.get('name', ''),
                    'slug': tag.get('slug', ''),
                    'description': tag.get('description', ''),
                    'count': tag.get('count', 0)
                }
                
                logger.info(f"Successfully created WordPress tag: {name} (ID: {created_tag['id']})")
                return created_tag
                
            else:
                logger.error(f"WordPress tag creation failed: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating WordPress tag: {str(e)}")
            return None

    def create_post_from_rayo(self, rayo_blog: Dict, wp_options: Dict = None) -> Optional[Dict]:
        """
        Create a new WordPress post from a Rayo blog.
        
        Args:
            rayo_blog: Rayo blog document from MongoDB
            wp_options: WordPress-specific options (status, categories, etc.)
            
        Returns:
            Created WordPress post data or None if failed
        """
        try:
            logger.info(f"Creating WordPress post from Rayo blog: {rayo_blog.get('title', 'Unknown')}")
            
            # Default WordPress options
            default_options = {
                "status": "draft",  # Safe default
                "categories": [],
                "tags": [],
                "author": 1,  # Default author
                "featured_media": None
            }
            
            if wp_options:
                default_options.update(wp_options)
            
            # Convert Rayo blog to WordPress post format
            wp_post_data = {
                "title": rayo_blog.get("title", ""),
                "content": wp_options.get("content_override", rayo_blog.get("content", "")),
                "excerpt": rayo_blog.get("meta_description", ""),  # Use meta_description as excerpt
                "status": default_options["status"],
                "slug": wp_options.get("slug_override", self._generate_slug(rayo_blog.get("title", ""))),
                "categories": default_options["categories"],
                "tags": default_options["tags"],
                "author": default_options["author"]
            }
            
            # Add scheduled date for future posts
            if default_options["status"] == "future" and wp_options and wp_options.get("date"):
                wp_post_data["date"] = wp_options["date"]
            
            # Add featured media if available
            if default_options.get("featured_media"):
                wp_post_data["featured_media"] = default_options["featured_media"]
            elif wp_options and wp_options.get("image_url_override"):
                # Upload override image URL to WordPress
                override_image = {"url": wp_options["image_url_override"], "filename": "override-image.jpg"}
                featured_media_id = self._upload_rayo_image_to_wp(override_image)
                if featured_media_id:
                    wp_post_data["featured_media"] = featured_media_id
            elif rayo_blog.get("rayo_featured_image"):
                # Upload Rayo featured image to WordPress
                featured_media_id = self._upload_rayo_image_to_wp(rayo_blog["rayo_featured_image"])
                if featured_media_id:
                    wp_post_data["featured_media"] = featured_media_id
            
            logger.info(f"🔍 WordPress post data: {wp_post_data}")
            
            # Include embedded data in response to get full post details
            params = {
                '_embed': 'wp:term,wp:featuredmedia,author'
            }
            
            # Create post in WordPress
            response = self.session.post(
                f"{self.api_base}/posts",
                json=wp_post_data,
                params=params,
                timeout=30
            )
            
            logger.info(f"🔍 WordPress create post API URL: {response.url}")
            logger.info(f"🔍 WordPress create response status: {response.status_code}")
            
            if response.status_code == 201:  # 201 Created
                wp_post = response.json()
                
                # Transform to our format
                transformed_post = self._transform_post_full(wp_post)
                
                logger.info(f"✅ Successfully created WordPress post: {wp_post.get('title', {}).get('rendered', 'Unknown')}")
                logger.info(f"🔍 WordPress post ID: {wp_post.get('id')}")
                logger.info(f"🔍 WordPress post URL: {wp_post.get('link')}")
                
                return transformed_post
                
            else:
                logger.error(f"❌ WordPress post creation failed: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error creating WordPress post from Rayo blog: {str(e)}")
            return None

    def _generate_slug(self, title: str) -> str:
        """Generate WordPress-friendly slug from title"""
        import re
        slug = title.lower()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)  # Remove special chars
        slug = re.sub(r'\s+', '-', slug)  # Replace spaces with hyphens
        slug = re.sub(r'-+', '-', slug)   # Remove multiple hyphens
        slug = slug.strip('-')            # Remove leading/trailing hyphens
        return slug[:50] if slug else "rayo-blog"  # WordPress slug length limit

    def _upload_rayo_image_to_wp(self, rayo_image: Dict) -> Optional[int]:
        """
        Upload Rayo featured image to WordPress media library
        
        Args:
            rayo_image: Rayo featured image object {url, id, filename}
            
        Returns:
            WordPress media ID or None if failed
        """
        try:
            if not rayo_image or not rayo_image.get("url"):
                return None
                
            logger.info(f"📷 Uploading Rayo image to WordPress: {rayo_image.get('filename', 'unknown')}")
            
            # Download image from Rayo URL
            import requests
            image_response = requests.get(rayo_image["url"], timeout=30)
            
            if image_response.status_code != 200:
                logger.error(f"Failed to download Rayo image: {rayo_image['url']}")
                return None
            
            # Upload to WordPress
            uploaded_image = self.upload_image(
                file_content=image_response.content,
                filename=rayo_image.get("filename", "rayo-image.jpg")
            )
            
            if uploaded_image and uploaded_image.get("id"):
                logger.info(f"✅ Rayo image uploaded to WordPress: {uploaded_image['id']}")
                return uploaded_image["id"]
            else:
                logger.error("Failed to upload Rayo image to WordPress")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error uploading Rayo image to WordPress: {str(e)}")
            return None

    def test_connection(self) -> bool:
        """
        Test WordPress API connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            response = self.session.get(
                f"{self.api_base}/users/me",
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("WordPress connection test successful")
                return True
            else:
                logger.error(f"WordPress connection test failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"WordPress connection test error: {str(e)}")
            return False