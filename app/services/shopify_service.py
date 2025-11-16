import requests
from typing import Dict, Any, Optional
from datetime import datetime
from app.core.logging_config import logger

class ShopifyService:
    """Service for Shopify API integration and connection testing"""
    
    def __init__(self, shop_domain: str, access_token: str, api_version: str = "2024-01"):
        self.shop_domain = shop_domain.replace("https://", "").replace("http://", "")
        if not self.shop_domain.endswith(".myshopify.com"):
            if "." not in self.shop_domain:
                self.shop_domain = f"{self.shop_domain}.myshopify.com"
        
        self.access_token = access_token
        self.api_version = api_version
        self.base_url = f"https://{self.shop_domain}/admin/api/{self.api_version}"
        
        # Setup session with headers
        self.session = requests.Session()
        self.session.headers.update({
            'X-Shopify-Access-Token': self.access_token,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def test_connection(self) -> tuple[bool, str]:
        """
        Test Shopify connection and validate required permissions
        Returns (success: bool, error_message: str)
        """
        try:
            # Test 1: Basic connection with shop info endpoint
            response = self.session.get(f"{self.base_url}/shop.json", timeout=10)
            
            if response.status_code == 401:
                error_msg = "Invalid access token"
                logger.error(f"Shopify connection failed: {error_msg}")
                return False, error_msg
            elif response.status_code == 404:
                error_msg = "Shop domain not found"
                logger.error(f"Shopify connection failed: {error_msg}")
                return False, error_msg
            elif response.status_code != 200:
                error_msg = f"HTTP {response.status_code}"
                logger.error(f"Shopify connection failed: {error_msg}")
                return False, error_msg
            
            shop_data = response.json()
            if 'shop' not in shop_data:
                error_msg = "Invalid shop response"
                logger.error(f"Shopify connection failed: {error_msg}")
                return False, error_msg
            
            shop_name = shop_data['shop'].get('name', 'Unknown')
            logger.info(f"Successfully connected to Shopify store: {shop_name}")
            
            # Test 2: Check content read permissions (blogs)
            blogs_response = self.session.get(f"{self.base_url}/blogs.json", timeout=10)
            if blogs_response.status_code == 403:
                error_msg = "Missing 'read_content' permission. Please enable 'Content' read access in your Shopify Private App settings."
                logger.error(f"Shopify connection failed: {error_msg}")
                return False, error_msg
            elif blogs_response.status_code not in [200, 404]:  # 404 is OK if no blogs exist
                error_msg = f"Cannot read blogs (HTTP {blogs_response.status_code})"
                logger.error(f"Shopify connection failed: {error_msg}")
                return False, error_msg
            
            # Test 3: Check write permissions by attempting to create a draft article (then delete it)
            write_success, write_error = self._test_write_permissions()
            if not write_success:
                return False, write_error
            
            logger.info("Shopify connection validated with all required permissions")
            return True, "Connection successful"
                
        except requests.exceptions.Timeout:
            error_msg = "Request timeout - check your internet connection"
            logger.error(f"Shopify connection failed: {error_msg}")
            return False, error_msg
        except requests.exceptions.ConnectionError:
            error_msg = "Connection error - unable to reach Shopify servers"
            logger.error(f"Shopify connection failed: {error_msg}")
            return False, error_msg
        except requests.exceptions.RequestException as e:
            error_msg = f"Request error: {str(e)}"
            logger.error(f"Shopify connection failed: {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Shopify connection test failed: {error_msg}")
            return False, error_msg
    
    def _test_write_permissions(self) -> tuple[bool, str]:
        """
        Test write permissions by creating and deleting a test blog post
        Returns (success: bool, error_message: str)
        """
        try:
            # First, get or create a blog to test with
            blogs_response = self.session.get(f"{self.base_url}/blogs.json", timeout=10)
            
            if blogs_response.status_code != 200:
                error_msg = "Cannot retrieve blogs for write permission test"
                logger.error(error_msg)
                return False, error_msg
            
            blogs_data = blogs_response.json()
            blogs = blogs_data.get('blogs', [])
            
            # If no blogs exist, try to create one for testing
            if not blogs:
                test_blog_data = {
                    "blog": {
                        "title": "Rayo Test Blog",
                        "handle": "rayo-test-blog"
                    }
                }
                
                create_blog_response = self.session.post(
                    f"{self.base_url}/blogs.json",
                    json=test_blog_data,
                    timeout=10
                )
                
                if create_blog_response.status_code == 403:
                    error_msg = "Missing 'write_content' permission. Please enable 'Content' write access in your Shopify Private App settings."
                    logger.error(f"Shopify connection failed: {error_msg}")
                    return False, error_msg
                elif create_blog_response.status_code not in [200, 201]:
                    error_msg = f"Cannot create blog (HTTP {create_blog_response.status_code})"
                    logger.error(f"Shopify connection failed: {error_msg}")
                    return False, error_msg
                
                blog_data = create_blog_response.json()
                blog_id = blog_data['blog']['id']
                created_test_blog = True
            else:
                blog_id = blogs[0]['id']
                created_test_blog = False
            
            # Test creating a draft article
            test_article_data = {
                "article": {
                    "title": "Rayo Connection Test",
                    "body_html": "<p>This is a test article created by Rayo to validate write permissions.</p>",
                    "published": False,  # Keep as draft
                    "tags": "rayo-test"
                }
            }
            
            create_response = self.session.post(
                f"{self.base_url}/blogs/{blog_id}/articles.json",
                json=test_article_data,
                timeout=10
            )
            
            if create_response.status_code == 403:
                error_msg = "Missing 'write_content' permission. Please enable 'Content' write access in your Shopify Private App settings."
                logger.error(f"Shopify connection failed: {error_msg}")
                return False, error_msg
            elif create_response.status_code not in [200, 201]:
                error_msg = f"Cannot create article (HTTP {create_response.status_code})"
                logger.error(f"Shopify connection failed: {error_msg}")
                return False, error_msg
            
            # Clean up: Delete the test article
            article_data = create_response.json()
            article_id = article_data['article']['id']
            
            delete_response = self.session.delete(
                f"{self.base_url}/blogs/{blog_id}/articles/{article_id}.json",
                timeout=10
            )
            
            # Clean up: Delete test blog if we created it
            if created_test_blog:
                self.session.delete(f"{self.base_url}/blogs/{blog_id}.json", timeout=10)
            
            logger.info("Shopify write permissions validated successfully")
            return True, "Write permissions validated"
            
        except Exception as e:
            error_msg = f"Error testing write permissions: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_shop_info(self) -> Optional[Dict[str, Any]]:
        """
        Get shop information from Shopify
        Returns shop data if successful, None otherwise
        """
        try:
            response = self.session.get(f"{self.base_url}/shop.json", timeout=10)
            
            if response.status_code == 200:
                return response.json().get('shop')
            else:
                logger.error(f"Failed to get shop info: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting shop info: {str(e)}")
            return None
    
    
    def create_blog_post(self, blog_id: int, title: str, content: str, tags: str = "") -> Optional[Dict[str, Any]]:
        """
        Create a blog post in Shopify
        Returns article data if successful, None otherwise
        """
        try:
            article_data = {
                "article": {
                    "title": title,
                    "body_html": content,
                    "tags": tags,
                    "published": True
                }
            }
            
            response = self.session.post(
                f"{self.base_url}/blogs/{blog_id}/articles.json",
                json=article_data,
                timeout=30
            )
            
            if response.status_code == 201:
                return response.json().get('article')
            else:
                logger.error(f"Failed to create blog post: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating blog post: {str(e)}")
            return None
    
    def get_blogs(self) -> Optional[list]:
        """
        Get all blogs from the Shopify store
        Returns list of blogs if successful, None otherwise
        """
        try:
            response = self.session.get(f"{self.base_url}/blogs.json", timeout=10)
            
            if response.status_code == 200:
                return response.json().get('blogs', [])
            else:
                logger.error(f"Failed to get blogs: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting blogs: {str(e)}")
            return None

    def get_posts(self, blog_id: int = None, limit: int = 50, page: int = 1) -> Dict:
        """
        Get blog posts from Shopify. Optimized for performance.
        
        Args:
            blog_id: Specific blog ID (if None, gets from first available blog)
            limit: Posts per page (max 250)
            page: Page number (1-based)
            
        Returns:
            Dict with posts and pagination info
        """
        try:
            current_blog = None
            if not blog_id:
                blogs = self.get_blogs()
                if not blogs:
                    return {'posts': [], 'pagination': None}
                blog_id = blogs[0]['id']
                current_blog = blogs[0]
                logger.info(f"🔍 Using first blog: ID={blog_id}, Title='{blogs[0].get('title', 'Unknown')}'")
            else:
                logger.info(f"🔍 Using specified blog ID: {blog_id}")
                # Get the blog info for the specified blog_id
                blogs = self.get_blogs()
                current_blog = next((blog for blog in blogs if blog['id'] == blog_id), None)
            
            params = {
                'limit': min(limit, 250),  # Shopify max limit
                'fields': 'id,title,summary,created_at,updated_at,tags,published_at,author'
            }
            
            # Add page parameter only if page > 1 (Shopify sometimes has issues with page=1)
            if page > 1:
                params['page'] = page
            
            response = self.session.get(
                f"{self.base_url}/blogs/{blog_id}/articles.json",
                params=params,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get('articles', [])
                
                # Transform to our format
                posts = [self._transform_post(article, current_blog) for article in articles]
                
                # Simple pagination (Shopify doesn't provide total count easily)
                has_more = len(articles) == limit
                
                return {
                    'posts': posts,
                    'pagination': {
                        'current_page': page,
                        'per_page': limit,
                        'has_next': has_more,
                        'has_previous': page > 1
                    }
                }
            else:
                logger.error(f"Failed to get posts: HTTP {response.status_code}")
                logger.error(f"Request URL: {response.url}")
                logger.error(f"Response body: {response.text}")
                return {'posts': [], 'pagination': None}
                
        except Exception as e:
            logger.error(f"Error getting posts: {str(e)}")
            return {'posts': [], 'pagination': None}

    def get_post_by_id(self, blog_id: int, article_id: int) -> Optional[Dict]:
        """
        Get single blog post with full content. Optimized with field selection.
        
        Args:
            blog_id: Blog ID
            article_id: Article ID
            
        Returns:
            Transformed post data or None
        """
        try:
            # Get blog info for category
            blogs = self.get_blogs()
            current_blog = next((blog for blog in blogs if blog['id'] == blog_id), None)
            
            response = self.session.get(
                f"{self.base_url}/blogs/{blog_id}/articles/{article_id}.json",
                timeout=10
            )
            
            if response.status_code == 200:
                article = response.json().get('article')
                if article:
                    logger.info(f"🔍 DEBUG: Shopify article raw data keys: {list(article.keys())}")
                    logger.info(f"🔍 DEBUG: Shopify article image field: {article.get('image')}")
                    return self._transform_post_full(article, current_blog)
            else:
                logger.error(f"Failed to get post {article_id}: HTTP {response.status_code}")
            
            return None
                
        except Exception as e:
            logger.error(f"Error getting post {article_id}: {str(e)}")
            return None

    def get_authors(self) -> list:
        """
        Get authors from Shopify blog posts (extracted from recent posts)
        Simple implementation - gets unique authors from recent posts
        """
        try:
            blogs = self.get_blogs()
            if not blogs:
                return []
            
            authors = set()
            # Check recent posts from all blogs for unique authors
            for blog in blogs[:3]:  # Limit to first 3 blogs for performance
                params = {
                    'limit': 20,  # Small sample for author extraction
                    'fields': 'author'
                }
                
                response = self.session.get(
                    f"{self.base_url}/blogs/{blog['id']}/articles.json",
                    params=params,
                    timeout=10
                )
                
                if response.status_code == 200:
                    articles = response.json().get('articles', [])
                    for article in articles:
                        author = article.get('author')
                        if author:
                            authors.add(author)
            
            # Transform to our format
            return [{'name': author, 'id': hash(author)} for author in sorted(authors)]
            
        except Exception as e:
            logger.error(f"Error getting authors: {str(e)}")
            return []

    def get_tags(self) -> list:
        """
        Get tags from Shopify blog posts (extracted from recent posts)
        Simple implementation - gets unique tags from recent posts
        """
        try:
            blogs = self.get_blogs()
            if not blogs:
                return []
            
            all_tags = set()
            # Check recent posts from all blogs for unique tags
            for blog in blogs[:3]:  # Limit to first 3 blogs for performance
                params = {
                    'limit': 50,  # Reasonable sample for tag extraction
                    'fields': 'tags'
                }
                
                response = self.session.get(
                    f"{self.base_url}/blogs/{blog['id']}/articles.json",
                    params=params,
                    timeout=10
                )
                
                if response.status_code == 200:
                    articles = response.json().get('articles', [])
                    for article in articles:
                        tags = article.get('tags', '')
                        if tags:
                            # Shopify tags are comma-separated
                            tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
                            all_tags.update(tag_list)
            
            # Transform to our format
            return [{'name': tag, 'id': hash(tag), 'count': 0} for tag in sorted(all_tags)]
            
        except Exception as e:
            logger.error(f"Error getting tags: {str(e)}")
            return []

    def _transform_post(self, article: Dict, blog_info: Dict = None) -> Dict:
        """Transform Shopify article to our blog format (lightweight for lists)"""
        try:
            # Use blog title as category, fallback to blog handle or "Shopify"
            category = "Shopify"  # Default category
            if blog_info:
                category = blog_info.get('title', blog_info.get('handle', 'Shopify'))
            
            # Extract featured image (lightweight version)
            featured_image = None
            shopify_image = article.get('image')
            
            if shopify_image:
                if isinstance(shopify_image, dict):
                    featured_image = shopify_image.get('src') or shopify_image.get('url')
                else:
                    featured_image = str(shopify_image)
            
            transformed_data = {
                'id': str(article.get('id')),
                'title': article.get('title', ''),
                'excerpt': article.get('summary', ''),
                'status': 'publish' if article.get('published_at') else 'draft',
                'source': 'shopify',
                'category': category,  # Add category from blog title
                'created_at': article.get('created_at'),
                'updated_at': article.get('updated_at'),
                'published_at': article.get('published_at'),
                'author': article.get('author', ''),
                'tags': [tag.strip() for tag in (article.get('tags', '')).split(',') if tag.strip()],
                'words_count': 0  # Shopify doesn't provide word count in list view
            }
            
            # Add featured image if available
            if featured_image:
                transformed_data['featured_image'] = featured_image
            
            return transformed_data
        except Exception as e:
            logger.error(f"Error transforming post: {str(e)}")
            return {}

    def _transform_post_full(self, article: Dict, blog_info: Dict = None) -> Dict:
        """Transform Shopify article to our blog format (full content for individual view)"""
        try:
            content = article.get('body_html', '')
            words_count = len(content.replace('<p>', ' ').replace('</p>', ' ').split()) if content else 0
            
            # Use blog title as category, fallback to blog handle or "Shopify"
            category = "Shopify"  # Default category
            if blog_info:
                category = blog_info.get('title', blog_info.get('handle', 'Shopify'))
            
            # Extract featured image from Shopify article
            featured_image = None
            rayo_featured_image = None
            shopify_image = article.get('image')
            
            if shopify_image:
                # Shopify image can be either a dict with 'src' or direct URL string
                if isinstance(shopify_image, dict):
                    image_url = shopify_image.get('src') or shopify_image.get('url')
                    alt_text = shopify_image.get('alt', '')
                else:
                    image_url = str(shopify_image)
                    alt_text = ''
                
                if image_url:
                    logger.info(f"📷 DEBUG: Found Shopify featured image: {image_url}")
                    featured_image = image_url
                    # Convert to Rayo format for consistency
                    rayo_featured_image = {
                        'url': image_url,
                        'id': str(hash(image_url)),  # Generate consistent ID
                        'filename': image_url.split('/')[-1].split('?')[0] if '/' in image_url else 'shopify-image',
                        'alt': alt_text
                    }
            
            transformed_data = {
                'id': str(article.get('id')),
                'title': article.get('title', ''),
                'content': content,
                'excerpt': article.get('summary', ''),
                'status': 'publish' if article.get('published_at') else 'draft',
                'source': 'shopify',
                'category': category,  # Add category from blog title
                'words_count': words_count,
                'created_at': article.get('created_at'),
                'updated_at': article.get('updated_at'),
                'published_at': article.get('published_at'),
                'author': article.get('author', ''),
                'tags': [tag.strip() for tag in (article.get('tags', '')).split(',') if tag.strip()],
                'shopify_url': article.get('url', ''),
                'metadata': {
                    'shopify_blog_id': article.get('blog_id'),
                    'shopify_handle': article.get('handle'),
                    'shopify_blog_title': category  # Include blog title in metadata
                }
            }
            
            # Add featured image fields if available
            if featured_image:
                transformed_data['featured_image'] = featured_image
                transformed_data['rayo_featured_image'] = rayo_featured_image
                logger.info(f"📷 DEBUG: Added featured image to transformed data")
            else:
                logger.info(f"📷 DEBUG: No featured image found for article {article.get('id')}")
            
            return transformed_data
        except Exception as e:
            logger.error(f"Error transforming full post: {str(e)}")
            return {}

    def create_blog(self, title: str, handle: str = None) -> Optional[Dict[str, Any]]:
        """
        Create a new blog in Shopify store
        
        Args:
            title: Blog title
            handle: Blog handle (URL slug) - auto-generated if not provided
            
        Returns:
            Created blog data or None if failed
        """
        try:
            logger.info(f"Creating Shopify blog: {title}")
            
            # Auto-generate handle if not provided
            if not handle:
                import re
                handle = re.sub(r'[^a-z0-9\s-]', '', title.lower())
                handle = re.sub(r'\s+', '-', handle).strip('-')
                handle = handle[:50] if handle else "new-blog"
            
            blog_data = {
                "blog": {
                    "title": title,
                    "handle": handle
                }
            }
            
            response = self.session.post(
                f"{self.base_url}/blogs.json",
                json=blog_data,
                timeout=15
            )
            
            logger.info(f"🔍 Shopify create blog response status: {response.status_code}")
            
            if response.status_code == 201:
                blog = response.json().get('blog')
                logger.info(f"✅ Successfully created Shopify blog: {title} (ID: {blog.get('id')})")
                return blog
            elif response.status_code == 422:
                error_data = response.json()
                logger.error(f"❌ Blog creation validation error: {error_data}")
                return None
            else:
                logger.error(f"❌ Failed to create blog: HTTP {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error creating blog: {str(e)}")
            return None

    def create_article(self, blog_id: int, title: str, content: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Create a new article in Shopify blog (enhanced version of create_blog_post)
        
        Args:
            blog_id: Blog ID
            title: Article title
            content: Article HTML content
            **kwargs: Additional article options (tags, author, published, image_url, etc.)
            
        Returns:
            Created article data or None if failed
        """
        try:
            logger.info(f"Creating Shopify article: {title} in blog {blog_id}")
            
            # Build article data with defaults
            article_data = {
                "article": {
                    "title": title,
                    "body_html": content,
                    "published": kwargs.get('published', True),
                    "tags": kwargs.get('tags', ''),
                    "author": kwargs.get('author', ''),
                    "summary": kwargs.get('summary', ''),
                    "handle": kwargs.get('handle', self._generate_handle(title))
                }
            }
            
            # Add featured image if provided
            image_url = kwargs.get('image_url')
            if image_url:
                logger.info(f"📷 Adding featured image to article: {image_url}")
                article_data["article"]["image"] = {
                    "src": image_url
                }
            
            # Remove empty fields
            article_data["article"] = {k: v for k, v in article_data["article"].items() if v}
            
            response = self.session.post(
                f"{self.base_url}/blogs/{blog_id}/articles.json",
                json=article_data,
                timeout=20
            )
            
            logger.info(f"🔍 Shopify create article response status: {response.status_code}")
            
            if response.status_code == 201:
                article = response.json().get('article')
                logger.info(f"✅ Successfully created Shopify article: {title} (ID: {article.get('id')})")
                return self._transform_post_full(article)
            elif response.status_code == 422:
                error_data = response.json()
                logger.error(f"❌ Article creation validation error: {error_data}")
                return None
            else:
                logger.error(f"❌ Failed to create article: HTTP {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error creating article: {str(e)}")
            return None

    def update_article(self, blog_id: int, article_id: int, update_data: Dict, image_url: str = None) -> Optional[Dict[str, Any]]:
        """
        Update an existing Shopify article
        
        Args:
            blog_id: Blog ID
            article_id: Article ID
            update_data: Fields to update
            image_url: Optional featured image URL
            
        Returns:
            Updated article data or None if failed
        """
        try:
            logger.info(f"🔍 DEBUG: Starting Shopify article update")
            logger.info(f"🔍 DEBUG: blog_id={blog_id}, article_id={article_id}")
            logger.info(f"🔍 DEBUG: update_data={update_data}")
            logger.info(f"🔍 DEBUG: image_url={image_url}")
            
            # Add featured image if provided
            if image_url:
                logger.info(f"📷 Adding featured image to article update: {image_url}")
                update_data["image"] = {"src": image_url}
                logger.info(f"📷 DEBUG: update_data after adding image: {update_data}")
            
            # Wrap in article object for Shopify API
            wrapped_data = {"article": update_data}
            logger.info(f"🔍 DEBUG: Final wrapped_data sent to Shopify API: {wrapped_data}")
            
            # Construct URL
            url = f"{self.base_url}/blogs/{blog_id}/articles/{article_id}.json"
            logger.info(f"🔍 DEBUG: PUT request URL: {url}")
            
            response = self.session.put(
                url,
                json=wrapped_data,
                timeout=15
            )
            
            logger.info(f"🔍 DEBUG: Shopify API response status: {response.status_code}")
            logger.info(f"🔍 DEBUG: Shopify API response headers: {dict(response.headers)}")
            logger.info(f"🔍 DEBUG: Shopify API response body: {response.text}")
            
            if response.status_code == 200:
                article = response.json().get('article')
                logger.info(f"✅ DEBUG: Successfully updated Shopify article")
                logger.info(f"✅ DEBUG: Updated article title: {article.get('title')}")
                logger.info(f"✅ DEBUG: Updated article ID: {article.get('id')}")
                
                transformed_article = self._transform_post_full(article)
                logger.info(f"✅ DEBUG: Transformed article: {transformed_article is not None}")
                return transformed_article
            elif response.status_code == 404:
                logger.error(f"❌ DEBUG: Article not found: {article_id}")
                return None
            elif response.status_code == 422:
                logger.error(f"❌ DEBUG: Validation error from Shopify API")
                logger.error(f"❌ DEBUG: Error details: {response.text}")
                return None
            else:
                logger.error(f"❌ DEBUG: Failed to update article: HTTP {response.status_code}")
                logger.error(f"❌ DEBUG: Error response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ DEBUG: Exception during article update: {str(e)}")
            logger.error(f"❌ DEBUG: Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"❌ DEBUG: Full traceback: {traceback.format_exc()}")
            return None

    def delete_article(self, blog_id: int, article_id: int) -> bool:
        """
        Delete a Shopify article
        
        Args:
            blog_id: Blog ID
            article_id: Article ID
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            logger.info(f"Deleting Shopify article {article_id} from blog {blog_id}")
            
            response = self.session.delete(
                f"{self.base_url}/blogs/{blog_id}/articles/{article_id}.json",
                timeout=15
            )
            
            logger.info(f"🔍 Shopify delete article response status: {response.status_code}")
            
            if response.status_code == 200:
                logger.info(f"✅ Successfully deleted Shopify article: {article_id}")
                return True
            elif response.status_code == 404:
                logger.error(f"❌ Article not found: {article_id}")
                return False
            else:
                logger.error(f"❌ Failed to delete article: HTTP {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error deleting article: {str(e)}")
            return False

    def _generate_handle(self, title: str) -> str:
        """Generate Shopify-friendly handle from title"""
        import re
        handle = re.sub(r'[^a-z0-9\s-]', '', title.lower())
        handle = re.sub(r'\s+', '-', handle).strip('-')
        return handle[:50] if handle else "new-article"

    def create_tags(self, tag_names: list) -> Dict:
        """
        Create new tags in Shopify by creating a temporary article with those tags.
        Since Shopify doesn't have dedicated tag creation, this method creates tags
        by associating them with articles.
        
        Args:
            tag_names: List of tag names to create
            
        Returns:
            Dict with created tags info and status
        """
        try:
            logger.info(f"Creating Shopify tags: {tag_names}")
            
            # Get available blogs
            blogs = self.get_blogs()
            if not blogs:
                logger.error("No blogs available to create tags")
                return {
                    'success': False,
                    'error': 'No blogs available. Create a blog first.',
                    'created_tags': []
                }
            
            # Use first available blog
            blog_id = blogs[0]['id']
            logger.info(f"Using blog ID {blog_id} for tag creation")
            
            # Convert tag names to comma-separated string
            tags_string = ', '.join(tag_names)
            
            # Create a temporary draft article with these tags
            temp_article_data = {
                "article": {
                    "title": f"Temp Article for Tag Creation - {datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    "body_html": "<p>This is a temporary article created to establish tags in Shopify. It will be deleted automatically.</p>",
                    "tags": tags_string,
                    "published": False,  # Keep as draft
                    "author": "Rayo System"
                }
            }
            
            # Create the temporary article
            response = self.session.post(
                f"{self.base_url}/blogs/{blog_id}/articles.json",
                json=temp_article_data,
                timeout=15
            )
            
            logger.info(f"🔍 Shopify temp article creation response status: {response.status_code}")
            
            if response.status_code == 201:
                article = response.json().get('article')
                article_id = article.get('id')
                
                logger.info(f"✅ Temporary article created with ID: {article_id}")
                
                # Immediately delete the temporary article
                delete_response = self.session.delete(
                    f"{self.base_url}/blogs/{blog_id}/articles/{article_id}.json",
                    timeout=10
                )
                
                if delete_response.status_code == 200:
                    logger.info("✅ Temporary article deleted successfully")
                else:
                    logger.warning(f"⚠️ Failed to delete temporary article: {delete_response.status_code}")
                
                # Return success with created tags
                created_tags = [{'name': tag.strip(), 'id': hash(tag.strip())} for tag in tag_names]
                
                return {
                    'success': True,
                    'message': f'Successfully created {len(tag_names)} tags in Shopify',
                    'created_tags': created_tags,
                    'tags_string': tags_string
                }
            
            else:
                error_data = response.json() if response.content else {}
                logger.error(f"❌ Failed to create temporary article: {response.status_code}")
                logger.error(f"Response: {error_data}")
                
                return {
                    'success': False,
                    'error': f'Failed to create tags: HTTP {response.status_code}',
                    'created_tags': []
                }
                
        except Exception as e:
            logger.error(f"❌ Error creating tags: {str(e)}")
            return {
                'success': False,
                'error': f'Error creating tags: {str(e)}',
                'created_tags': []
            }

    def bulk_create_tags_via_article(self, blog_id: int, article_title: str, article_content: str, tag_names: list) -> Optional[Dict]:
        """
        Create tags by creating a real article with those tags (alternative approach).
        This method creates a permanent article with the specified tags.
        
        Args:
            blog_id: Blog ID to create article in
            article_title: Title for the article
            article_content: Content for the article
            tag_names: List of tag names to associate with the article
            
        Returns:
            Created article data with tags or None if failed
        """
        try:
            logger.info(f"Creating article with tags: {tag_names}")
            
            # Convert tag names to comma-separated string
            tags_string = ', '.join(tag_names)
            
            # Create article with tags
            created_article = self.create_article(
                blog_id=blog_id,
                title=article_title,
                content=article_content,
                tags=tags_string,
                published=True
            )
            
            if created_article:
                logger.info(f"✅ Article created successfully with tags: {tags_string}")
                return created_article
            else:
                logger.error("❌ Failed to create article with tags")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error creating article with tags: {str(e)}")
            return None

    def create_post_from_rayo(self, rayo_blog: Dict, shopify_options: Dict = None) -> Optional[Dict]:
        """
        Create a new Shopify article from a Rayo blog.
        
        Args:
            rayo_blog: Rayo blog document from MongoDB
            shopify_options: Shopify-specific options (blog_id, status, tags, etc.)
            
        Returns:
            Created Shopify article data or None if failed
        """
        try:
            logger.info(f"Creating Shopify article from Rayo blog: {rayo_blog.get('title', 'Unknown')}")
            
            # Default Shopify options
            default_options = {
                "blog_id": None,
                "status": "draft", 
                "tags": [],
                "author": "Rayo User",
                "summary": ""
            }
            
            if shopify_options:
                default_options.update(shopify_options)
            
            # Validate blog_id is provided
            blog_id = default_options.get("blog_id")
            if not blog_id:
                logger.error("Blog ID is required for Shopify article creation")
                return None
            
            # Convert Rayo blog to Shopify article format
            article_title = rayo_blog.get("title", "")
            article_content = shopify_options.get("content_override", rayo_blog.get("content", ""))
            
            # Convert tags list to comma-separated string (Shopify format)
            tags_list = default_options.get("tags", [])
            if isinstance(tags_list, list):
                tags_string = ', '.join(tags_list)
            else:
                tags_string = str(tags_list)
            
            # Determine published status
            status = default_options.get("status", "draft")
            published = status == "published" or status == "publish"
            
            # Create article using existing create_article method
            created_article = self.create_article(
                blog_id=blog_id,
                title=article_title,
                content=article_content,
                tags=tags_string,
                author=default_options.get("author", "Rayo User"),
                summary=default_options.get("summary", rayo_blog.get("meta_description", "")),
                published=published,
                image_url=default_options.get("image_url")  # Pass image URL for featured image
            )
            
            if created_article:
                logger.info(f"✅ Successfully created Shopify article from Rayo blog")
                logger.info(f"🔍 Shopify article ID: {created_article.get('id')}")
                return created_article
            else:
                logger.error("❌ Failed to create Shopify article from Rayo blog")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error creating Shopify article from Rayo blog: {str(e)}")
            return None

    def validate_image_url(self, image_url: str) -> bool:
        """
        Validate if image URL is accessible and valid
        
        Args:
            image_url: URL of image to validate
            
        Returns:
            True if image is accessible, False otherwise
        """
        try:
            logger.info(f"📷 Validating image URL: {image_url}")
            
            import requests
            response = requests.head(image_url, timeout=10)
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                if content_type.startswith('image/'):
                    logger.info(f"✅ Image URL is valid: {content_type}")
                    return True
                else:
                    logger.warning(f"⚠️ URL is not an image: {content_type}")
                    return False
            else:
                logger.warning(f"⚠️ Image URL returned status: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error validating image URL: {str(e)}")
            return False