from typing import Optional, List, Dict, Any
import uuid
import os
import time
from pathlib import Path
import mimetypes
from PIL import Image
import io
import httpx
import asyncio
import boto3
import json
from botocore.exceptions import ClientError, NoCredentialsError
from app.core.config import settings
from app.core.logging_config import logger

class DigitalOceanSpacesService:
    """
    DigitalOcean Spaces Storage Service - S3-compatible storage
    Replaces Supabase storage with the same interface
    """
    
    def __init__(self, user_token: Optional[str] = None):
        """
        Initialize DigitalOcean Spaces client
        
        Args:
            user_token: Optional user token (for future user-specific operations)
        """
        try:
            # DigitalOcean Spaces configuration
            self.spaces_key = getattr(settings, 'DO_SPACES_KEY', os.getenv('DO_SPACES_KEY'))
            self.spaces_secret = getattr(settings, 'DO_SPACES_SECRET', os.getenv('DO_SPACES_SECRET'))
            self.spaces_region = getattr(settings, 'DO_SPACES_REGION', os.getenv('DO_SPACES_REGION'))
            
            # Handle endpoint configuration
            custom_endpoint = getattr(settings, 'DO_SPACES_ENDPOINT', os.getenv('DO_SPACES_ENDPOINT'))
            if custom_endpoint:
                self.spaces_endpoint = custom_endpoint
            else:
                # Auto-generate endpoint from region
                self.spaces_endpoint = f'https://{self.spaces_region}.digitaloceanspaces.com'
            
            self.bucket_name = getattr(settings, 'DO_SPACES_BUCKET', os.getenv('DO_SPACES_BUCKET', 'rayo-images'))
            
            if not all([self.spaces_key, self.spaces_secret]):
                raise ValueError("DigitalOcean Spaces credentials not configured")
            
            # Log configuration for debugging
            logger.info(f"DigitalOcean Spaces configuration:")
            logger.info(f"  Region: {self.spaces_region}")
            logger.info(f"  Endpoint: {self.spaces_endpoint}")
            logger.info(f"  Bucket: {self.bucket_name}")
            logger.info(f"  Key: {self.spaces_key[:10]}..." if self.spaces_key else "  Key: Not set")
            
            # Initialize S3 client for DigitalOcean Spaces
            self.s3_client = boto3.client(
                's3',
                endpoint_url=self.spaces_endpoint,
                aws_access_key_id=self.spaces_key,
                aws_secret_access_key=self.spaces_secret,
                region_name=self.spaces_region
            )
            
            logger.info(f"DigitalOceanSpacesService initialized successfully with bucket: {self.bucket_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize DigitalOcean Spaces client: {str(e)}")
            raise
        
        # Storage configuration (same as Supabase)
        self.max_file_size = 50 * 1024 * 1024  # 50MB
        self.allowed_mime_types = [
            'image/jpeg', 'image/jpg', 'image/png', 
            'image/webp', 'image/gif', 'image/svg+xml',
            'image/avif',  # AVIF format support
            'image/heic',  # HEIC format (iPhone photos)
            'image/heif',  # HEIF format
            'image/bmp',   # BMP format
            'image/tiff'   # TIFF format
        ]
        
    async def create_bucket_if_not_exists(self):
        """Create bucket if it doesn't exist (DigitalOcean Spaces)"""
        try:
            # Check if bucket exists
            try:
                self.s3_client.head_bucket(Bucket=self.bucket_name)
                logger.info(f"DigitalOcean Spaces bucket '{self.bucket_name}' already exists")
                return True
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == '404':
                    # Bucket doesn't exist, create it
                    logger.info(f"Creating DigitalOcean Spaces bucket: {self.bucket_name}")
                    self.s3_client.create_bucket(Bucket=self.bucket_name)
                    
                    # Set bucket to public read (for direct URL access)
                    bucket_policy = {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Sid": "PublicReadGetObject",
                                "Effect": "Allow",
                                "Principal": "*",
                                "Action": "s3:GetObject",
                                "Resource": f"arn:aws:s3:::{self.bucket_name}/*"
                            }
                        ]
                    }
                    
                    self.s3_client.put_bucket_policy(
                        Bucket=self.bucket_name,
                        Policy=json.dumps(bucket_policy)
                    )
                    
                    logger.info(f"Created public DigitalOcean Spaces bucket: {self.bucket_name}")
                    return True
                else:
                    logger.error(f"Error checking bucket: {error_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error creating/checking DigitalOcean Spaces bucket: {str(e)}")
            return False
    
    def validate_file(self, file_content: bytes, filename: str, mime_type: str) -> Dict[str, Any]:
        """Validate uploaded file (same as Supabase)"""
        errors = []
        
        # Check file size
        if len(file_content) > self.max_file_size:
            errors.append(f"File size exceeds {self.max_file_size / (1024*1024):.0f}MB limit")
        
        # Check MIME type
        if mime_type not in self.allowed_mime_types:
            errors.append(f"File type {mime_type} not allowed")
        
        # Check file extension
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg', '.avif', '.heic', '.heif', '.bmp', '.tiff']
        file_ext = Path(filename).suffix.lower()
        if file_ext not in allowed_extensions:
            errors.append(f"File extension {file_ext} not allowed")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "file_size": len(file_content),
            "mime_type": mime_type,
            "extension": file_ext
        }
    
    def get_image_metadata(self, file_content: bytes, mime_type: str) -> Dict[str, Any]:
        """Extract image metadata (same as Supabase)"""
        try:
            if mime_type.startswith('image/') and mime_type != 'image/svg+xml':
                # Create BytesIO stream and reset position
                image_stream = io.BytesIO(file_content)
                image_stream.seek(0)
                
                with Image.open(image_stream) as img:
                    return {
                        "width": img.width,
                        "height": img.height,
                        "format": img.format,
                        "mode": img.mode
                    }
        except Exception as e:
            logger.warning(f"Could not extract image metadata: {str(e)}")
            # Debug: Check if it's valid image data despite PIL issues
            if len(file_content) >= 10:
                header_hex = file_content[:10].hex()
                logger.debug(f"Image data header: {header_hex}")
                # Check for JPEG magic number (FFD8FF)
                if file_content[:3] == b'\xff\xd8\xff':
                    logger.info("✅ Valid JPEG header detected despite PIL error - continuing upload")
                elif file_content[:4] == b'\x89PNG':
                    logger.info("✅ Valid PNG header detected despite PIL error - continuing upload")
        
        return {}
    
    async def upload_project_file(self, project_id: str, user_id: str, 
                                 file_content: bytes, filename: str, 
                                 mime_type: str, category: str = None) -> Dict[str, Any]:
        """Upload file to project-specific folder in DigitalOcean Spaces"""
        try:
            # Validate file
            validation = self.validate_file(file_content, filename, mime_type)
            if not validation["valid"]:
                return {
                    "success": False,
                    "errors": validation["errors"]
                }
            
            # Generate unique filename with category prefix if provided
            file_ext = Path(filename).suffix.lower()
            timestamp = int(time.time())
            random_hash = uuid.uuid4().hex[:8]
            
            if category:
                unique_filename = f"{category}_{timestamp}_{random_hash}{file_ext}"
            else:
                unique_filename = f"{timestamp}_{random_hash}{file_ext}"
            
            # Create PROJECT-CENTRIC storage path
            storage_path = f"{project_id}/{unique_filename}"
            
            # Upload to DigitalOcean Spaces
            try:
                # Upload file to Spaces
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=storage_path,
                    Body=file_content,
                    ContentType=mime_type,
                    CacheControl='public, max-age=31536000',  # 1 year cache
                    ACL='public-read'  # Make file publicly accessible
                )
                
                logger.info(f"Successfully uploaded to DigitalOcean Spaces: {storage_path}")
                
                # Generate public URL with CDN (without bucket name)
                cdn_base_url = getattr(settings, 'CDN_BASE_URL', os.getenv('CDN_BASE_URL', 'https://cdn.rayo.work'))
                public_url = f"{cdn_base_url}/{storage_path}"
                
                # Get image metadata
                image_metadata = self.get_image_metadata(file_content, mime_type)
                logger.info(f"Extracted image metadata: {image_metadata}")
                
                result = {
                    "success": True,
                    "storage_path": storage_path,
                    "public_url": public_url,
                    "filename": unique_filename,
                    "original_filename": filename,
                    "file_size": len(file_content),
                    "mime_type": mime_type,
                    "image_metadata": image_metadata
                }
                logger.info(f"Upload result: {result}")
                return result
                
            except ClientError as e:
                error_msg = f"DigitalOcean Spaces upload failed: {str(e)}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "errors": [error_msg]
                }
                
        except Exception as e:
            logger.error(f"Error uploading project file to DigitalOcean Spaces: {str(e)}")
            return {
                "success": False,
                "errors": [f"Upload error: {str(e)}"]
            }
    
    async def delete_file(self, storage_path: str) -> bool:
        """Delete file from DigitalOcean Spaces"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=storage_path)
            logger.info(f"Successfully deleted file from DigitalOcean Spaces: {storage_path}")
            return True
        except ClientError as e:
            logger.error(f"Error deleting file from DigitalOcean Spaces: {str(e)}")
            return False
    
    async def delete_multiple_files(self, storage_paths: List[str]) -> Dict[str, Any]:
        """Delete multiple files from DigitalOcean Spaces"""
        try:
            # Delete objects in batch
            delete_objects = [{'Key': path} for path in storage_paths]
            
            response = self.s3_client.delete_objects(
                Bucket=self.bucket_name,
                Delete={'Objects': delete_objects}
            )
            
            deleted_count = len(response.get('Deleted', []))
            errors = response.get('Errors', [])
            
            if errors:
                logger.warning(f"Some files failed to delete: {errors}")
            
            return {
                "success": True,
                "deleted_count": deleted_count,
                "errors": errors
            }
            
        except ClientError as e:
            logger.error(f"Error deleting multiple files from DigitalOcean Spaces: {str(e)}")
            return {
                "success": False,
                "error": f"Bulk delete error: {str(e)}"
            }
    
    async def download_image_from_url(self, image_url: str) -> Dict[str, Any]:
        """Download image from URL and return file content and metadata (same as Supabase)"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(image_url)
                response.raise_for_status()
                
                # Get content type and validate
                content_type = response.headers.get('content-type', '')
                
                # Extract filename from URL first to check extension
                from urllib.parse import urlparse
                parsed_url = urlparse(image_url)
                url_filename = os.path.basename(parsed_url.path)
                
                # Smart content-type validation
                is_valid_image = False
                detected_mime_type = content_type.split(';')[0].strip()  # Remove charset
                
                # Check if content-type indicates an image
                if detected_mime_type.startswith('image/'):
                    is_valid_image = True
                # Check if URL has image extension (for misconfigured servers)
                elif url_filename and any(url_filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.avif', '.heic', '.heif', '.bmp', '.tiff']):
                    # Guess MIME type from extension
                    if url_filename.lower().endswith('.svg'):
                        detected_mime_type = 'image/svg+xml'
                    elif url_filename.lower().endswith(('.jpg', '.jpeg')):
                        detected_mime_type = 'image/jpeg'
                    elif url_filename.lower().endswith('.png'):
                        detected_mime_type = 'image/png'
                    elif url_filename.lower().endswith('.gif'):
                        detected_mime_type = 'image/gif'
                    elif url_filename.lower().endswith('.webp'):
                        detected_mime_type = 'image/webp'
                    elif url_filename.lower().endswith('.avif'):
                        detected_mime_type = 'image/avif'
                    elif url_filename.lower().endswith(('.heic', '.heif')):
                        detected_mime_type = 'image/heic'
                    elif url_filename.lower().endswith('.bmp'):
                        detected_mime_type = 'image/bmp'
                    elif url_filename.lower().endswith('.tiff'):
                        detected_mime_type = 'image/tiff'
                    is_valid_image = True
                    logger.info(f"Server returned {content_type} but URL has image extension, using {detected_mime_type}")
                
                if not is_valid_image:
                    return {
                        "success": False,
                        "errors": [f"URL does not point to an image. Content-Type: {content_type}, URL: {image_url}"]
                    }
                
                # Get file content
                file_content = response.content
                
                # Use the filename we already extracted
                filename = url_filename
                if not filename or '.' not in filename:
                    # Generate filename based on detected content type
                    ext_map = {
                        'image/jpeg': '.jpg',
                        'image/png': '.png',
                        'image/webp': '.webp',
                        'image/gif': '.gif',
                        'image/svg+xml': '.svg',
                        'image/avif': '.avif',
                        'image/heic': '.heic',
                        'image/bmp': '.bmp',
                        'image/tiff': '.tiff'
                    }
                    ext = ext_map.get(detected_mime_type, '.jpg')
                    filename = f"downloaded_image{ext}"
                
                return {
                    "success": True,
                    "file_content": file_content,
                    "filename": filename,
                    "mime_type": detected_mime_type,  # Use detected MIME type
                    "file_size": len(file_content)
                }
                
        except httpx.TimeoutException:
            return {
                "success": False,
                "errors": ["Request timeout while downloading image from URL"]
            }
        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "errors": [f"HTTP error {e.response.status_code} while downloading image"]
            }
        except Exception as e:
            logger.error(f"Error downloading image from URL: {str(e)}")
            return {
                "success": False,
                "errors": [f"Failed to download image: {str(e)}"]
            }
    
    async def upload_project_file_from_url(self, project_id: str, user_id: str, 
                                          image_url: str, category: str = None) -> Dict[str, Any]:
        """Upload image from URL to project-specific folder in DigitalOcean Spaces"""
        try:
            # Download image from URL
            download_result = await self.download_image_from_url(image_url)
            if not download_result["success"]:
                return download_result
            
            # Upload the downloaded content
            return await self.upload_project_file(
                project_id=project_id,
                user_id=user_id,
                file_content=download_result["file_content"],
                filename=download_result["filename"],
                mime_type=download_result["mime_type"],
                category=category
            )
            
        except Exception as e:
            logger.error(f"Error uploading project file from URL to DigitalOcean Spaces: {str(e)}")
            return {
                "success": False,
                "errors": [f"Upload from URL error: {str(e)}"]
            }
