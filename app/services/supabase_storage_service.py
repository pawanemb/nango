from supabase import create_client, Client
from app.core.config import settings
from app.core.logging_config import logger
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

class SupabaseStorageService:
    def __init__(self, user_token: Optional[str] = None):
        # Create Supabase client with user token if provided, otherwise use service key
        if user_token:
            try:
                # Create client with user token for authenticated operations
                self.supabase: Client = create_client(settings.SUPABASE_URL, user_token)
                logger.info("SupabaseStorageService initialized with user token authentication")
            except Exception as e:
                logger.warning(f"Failed to create Supabase client with user token: {str(e)}")
                logger.info("Falling back to service key authentication")
                # Fallback to service key if user token fails
                self.supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        else:
            # Use service key for unauthenticated operations
            self.supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
            logger.info("SupabaseStorageService initialized with service key authentication")
        
        self.bucket_name = "images"
        self.max_file_size = 10 * 1024 * 1024  # 10MB
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
        """Create PUBLIC bucket for direct URL access"""
        try:
            # DEBUG: Log current user context
            try:
                user = self.supabase.auth.get_user()
                logger.info(f"Supabase user context: {user}")
            except Exception as auth_e:
                logger.warning(f"Could not get Supabase user context: {auth_e}")
            
            # Check if bucket exists
            buckets = self.supabase.storage.list_buckets()
            bucket_exists = any(bucket.name == self.bucket_name for bucket in buckets)
            
            if not bucket_exists:
                # Create PUBLIC bucket for direct access
                self.supabase.storage.create_bucket(
                    self.bucket_name,
                    options={
                        "public": True,  # PUBLIC BUCKET - Direct URL access
                        "file_size_limit": self.max_file_size,
                        "allowed_mime_types": self.allowed_mime_types
                    }
                )
                logger.info(f"Created PUBLIC Supabase storage bucket: {self.bucket_name}")
            
            return True
        except Exception as e:
            logger.error(f"Error creating/checking bucket: {str(e)}")
            return False
    
    def validate_file(self, file_content: bytes, filename: str, mime_type: str) -> Dict[str, Any]:
        """Validate uploaded file"""
        errors = []
        
        # Check file size
        if len(file_content) > self.max_file_size:
            errors.append(f"File size exceeds {self.max_file_size / (1024*1024)}MB limit")
        
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
        """Extract image metadata"""
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
            logger.warning(f"Could not extract image metadata (may be Google Gemini API issue): {str(e)}")
            # Debug: Check if it's valid JPEG data despite PIL issues
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
        """Upload file to project-specific folder"""
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
            
            # Upload to Supabase Storage
            try:
                response = self.supabase.storage.from_(self.bucket_name).upload(
                    path=storage_path,
                    file=file_content,
                    file_options={
                        "content-type": mime_type,
                        "cache-control": "public, max-age=31536000"  # 1 year cache
                    }
                )
                
                # DEBUG: Log the response structure
                logger.info(f"Supabase upload response type: {type(response)}")
                logger.info(f"Supabase upload response attributes: {dir(response)}")
                if hasattr(response, 'data'):
                    logger.info(f"Response data: {response.data}")
                if hasattr(response, 'error'):
                    logger.info(f"Response error: {response.error}")
                
                # Check if upload was successful - handle httpx.Response
                upload_success = False
                
                # Check if response is httpx.Response (raw HTTP response)
                if hasattr(response, 'status_code'):
                    # This is an httpx.Response object
                    if response.status_code in [200, 201]:
                        upload_success = True
                        logger.info(f"Upload successful with status code: {response.status_code}")
                    else:
                        logger.error(f"Upload failed with status code: {response.status_code}")
                        logger.error(f"Response content: {response.text}")
                # Pattern 1: Check for 'path' attribute
                elif hasattr(response, 'path') and response.path:
                    upload_success = True
                # Pattern 2: Check for 'data' with path
                elif hasattr(response, 'data') and response.data and hasattr(response.data, 'path'):
                    upload_success = True
                # Pattern 3: Check if response is a dict with path
                elif isinstance(response, dict) and response.get('path'):
                    upload_success = True
                # Pattern 4: No error means success (some Supabase versions)
                elif not hasattr(response, 'error') or not response.error:
                    upload_success = True
                
                if upload_success:
                    # Get PUBLIC URL - directly accessible
                    public_url = self.supabase.storage.from_(self.bucket_name).get_public_url(storage_path)
                    
                    # Fix: Remove trailing '?' from URL if present
                    if public_url.endswith('?'):
                        public_url = public_url.rstrip('?')
                        logger.info(f"Fixed public URL (removed trailing '?'): {public_url}")
                    else:
                        logger.info(f"Generated public URL: {public_url}")
                    
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
                else:
                    # Handle upload error
                    error_msg = "Upload failed - no data in response"
                    if hasattr(response, 'error') and response.error:
                        error_msg = f"Upload failed: {response.error}"
                    elif hasattr(response, 'message'):
                        error_msg = f"Upload failed: {response.message}"
                    
                    logger.error(f"Upload failed: {error_msg}")
                    return {
                        "success": False,
                        "errors": [error_msg]
                    }
                    
            except Exception as upload_error:
                logger.error(f"Supabase upload exception: {str(upload_error)}")
                return {
                    "success": False,
                    "errors": [f"Upload exception: {str(upload_error)}"]
                }
                
        except Exception as e:
            logger.error(f"Error uploading project file: {str(e)}")
            return {
                "success": False,
                "errors": [f"Upload error: {str(e)}"]
            }
    
    async def delete_file(self, storage_path: str) -> bool:
        """Delete file from Supabase Storage"""
        try:
            response = self.supabase.storage.from_(self.bucket_name).remove([storage_path])
            # Check if delete was successful - Supabase returns different response structure
            return hasattr(response, 'data') and response.data is not None
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            return False
    
    async def delete_multiple_files(self, storage_paths: List[str]) -> Dict[str, Any]:
        """Delete multiple files from Supabase Storage"""
        try:
            response = self.supabase.storage.from_(self.bucket_name).remove(storage_paths)
            # Check if bulk delete was successful
            if hasattr(response, 'data') and response.data is not None:
                return {
                    "success": True,
                    "deleted_count": len(storage_paths)
                }
            else:
                error_msg = "Bulk delete failed"
                if hasattr(response, 'error') and response.error:
                    error_msg = f"Bulk delete failed: {response.error}"
                return {
                    "success": False,
                    "error": error_msg
                }
        except Exception as e:
            logger.error(f"Error deleting multiple files: {str(e)}")
            return {
                "success": False,
                "error": f"Bulk delete error: {str(e)}"
            }
    
    async def download_image_from_url(self, image_url: str) -> Dict[str, Any]:
        """Download image from URL and return file content and metadata"""
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
        """Upload image from URL to project-specific folder"""
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
            logger.error(f"Error uploading project file from URL: {str(e)}")
            return {
                "success": False,
                "errors": [f"Upload from URL error: {str(e)}"]
            }
