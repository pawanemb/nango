from typing import List, Optional, ClassVar
from uuid import UUID
from pymongo import MongoClient
from pymongo.database import Database
from app.models.mongodb_models import ScrapedContent
import logging
import os
import asyncio
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class MongoDBServiceError(Exception):
    """Custom exception for MongoDB service errors"""
    pass

class MongoDBService:
    COLLECTION_NAME = "scraped_content"
    # Keep old names for backward compatibility
    _client: Optional[MongoClient] = None
    _db: Optional[Database] = None
    # New instance variables for sync operations
    _sync_client: Optional[MongoClient] = None
    _sync_db: Optional[Database] = None
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    def __init__(self):
        self._sync_client = None
        self._sync_db = None

    @classmethod
    def init_db(cls):
        """Initialize MongoDB connection synchronously"""
        try:
            if cls._client is not None:
                cls.close_connections()
            
            mongodb_url = os.getenv("MONGODB_URL")
            mongodb_username = os.getenv("MONGODB_USERNAME")
            mongodb_password = os.getenv("MONGODB_PASSWORD")
            mongodb_db_name = os.getenv("MONGODB_DB_NAME")
            mongodb_auth_source = os.getenv("MONGODB_AUTH_SOURCE")
            
            # Parse and reconstruct URL properly
            if mongodb_username and mongodb_password:
                # Extract host and port from URL
                if '@' in mongodb_url:
                    # URL already has auth info, extract the host part
                    host_part = mongodb_url.split('@')[1]
                else:
                    # Remove mongodb:// prefix if present
                    host_part = mongodb_url.replace('mongodb://', '')
                
                # Remove any trailing path or query params from host
                host_part = host_part.split('/')[0].split('?')[0]
                
                # Construct the final URL with authSource
                mongodb_url = f"mongodb://{quote_plus(mongodb_username)}:{quote_plus(mongodb_password)}@{host_part}/?authSource={mongodb_auth_source}"
            
            # Configure client with proper options
            cls._client = MongoClient(
                mongodb_url,
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=60000,
                socketTimeoutMS=60000,
                maxPoolSize=10,
                minPoolSize=1,
                waitQueueTimeoutMS=60000,
                retryWrites=True
            )
            cls._db = cls._client[mongodb_db_name]
            
            # Test connection
            cls._client.admin.command('ping')
            logger.info("MongoDB connection initialized successfully")
            
        except Exception as e:
            error_msg = f"Failed to initialize MongoDB connection: {str(e)}"
            logger.error(error_msg)
            raise MongoDBServiceError(error_msg) from e

    @classmethod
    def get_db(cls):
        """Get MongoDB database instance synchronously"""
        if cls._db is None or cls._client is None:
            cls.init_db()
                
        try:
            # Test connection is still alive
            cls._client.admin.command('ping')
            return cls._db
        except Exception as e:
            logger.error(f"MongoDB connection test failed: {str(e)}")
            raise MongoDBServiceError("MongoDB is unreachable, connection test failed.") from e

    def init_sync_db(self):
        """Initialize MongoDB connection synchronously"""
        try:
            mongodb_url = os.getenv("MONGODB_URL")
            mongodb_username = os.getenv("MONGODB_USERNAME")
            mongodb_password = os.getenv("MONGODB_PASSWORD")
            mongodb_db_name = os.getenv("MONGODB_DB_NAME")
            mongodb_auth_source = os.getenv("MONGODB_AUTH_SOURCE")
            
            # Parse and reconstruct URL properly
            if mongodb_username and mongodb_password:
                # Extract host and port from URL
                if '@' in mongodb_url:
                    # URL already has auth info, extract the host part
                    host_part = mongodb_url.split('@')[1]
                else:
                    # Remove mongodb:// prefix if present
                    host_part = mongodb_url.replace('mongodb://', '')
                
                # Remove any trailing path or query params from host
                host_part = host_part.split('/')[0].split('?')[0]
                
                # Construct the final URL with authSource
                mongodb_url = f"mongodb://{quote_plus(mongodb_username)}:{quote_plus(mongodb_password)}@{host_part}/?authSource={mongodb_auth_source}"

            # Configure client with proper options
            self._sync_client = MongoClient(
                mongodb_url,
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=60000,
                socketTimeoutMS=60000,
                maxPoolSize=10,
                minPoolSize=1,
                waitQueueTimeoutMS=60000,
                retryWrites=True
            )
            self._sync_db = self._sync_client[mongodb_db_name]
            
            # Test connection
            self._sync_client.admin.command('ping')
            logger.info("MongoDB connection initialized successfully")
        except Exception as e:
            error_msg = f"Failed to initialize MongoDB connection: {str(e)}"
            logger.error(error_msg)
            raise MongoDBServiceError(error_msg) from e

    def get_sync_db(self):
        """Get MongoDB database instance synchronously for Celery tasks"""
        if self._sync_db is None or self._sync_client is None:
            self.init_sync_db()
            
        try:
            # Test connection is still alive
            self._sync_client.admin.command('ping')
            return self._sync_db
        except Exception as e:
            logger.error(f"Failed to get sync MongoDB connection: {str(e)}")
            raise MongoDBServiceError("Failed to get sync MongoDB connection") from e

    @classmethod
    def close_connections(cls):
        """Close MongoDB connections synchronously"""
        try:
            if cls._client:
                cls._client.close()
                cls._client = None
                cls._db = None
            if cls._sync_client:
                cls._sync_client.close()
                cls._sync_client = None
                cls._sync_db = None
            logger.info("MongoDB connections closed successfully")
        except Exception as e:
            logger.error(f"Error closing MongoDB connections: {str(e)}")
            raise

    @classmethod
    def save_scraped_content(cls, content: ScrapedContent) -> str:
        """
        Save scraped content to MongoDB
        Returns the MongoDB document ID
        """
        try:
            logger.info(f"Attempting to save content for project: {content.project_id}, URL: {content.url}")
            db = cls.get_db()
            collection = db[cls.COLLECTION_NAME]
            
            # Convert model to dict and ensure project_id is string
            content_dict = content.model_dump()
            content_dict['project_id'] = str(content_dict['project_id'])
            
            # Check if document already exists
            existing = collection.find_one({
                "project_id": content_dict['project_id'],
                "url": content_dict['url']
            })
            if existing:
                logger.warning(f"Document already exists for project: {content.project_id}, URL: {content.url}")
            
            # Insert with write concern
            logger.info(f"Inserting document into MongoDB: {content_dict}")
            result = collection.insert_one(content_dict)
            
            if result.inserted_id is None:
                error_msg = "Failed to insert document - no inserted_id returned"
                logger.error(error_msg)
                raise MongoDBServiceError(error_msg)
                
            logger.info(f"Successfully saved content with ID: {result.inserted_id}")
            return str(result.inserted_id)
            
        except Exception as e:
            error_msg = f"Failed to save content to MongoDB: {str(e)}"
            logger.error(error_msg)
            logger.exception("Full traceback:")
            raise MongoDBServiceError(error_msg) from e

    @classmethod
    def save_scraped_content_sync(cls, content: ScrapedContent) -> str:
        """
        Save scraped content to MongoDB synchronously
        Returns the MongoDB document ID
        """
        try:
            logger.info(f"Attempting to save content for project: {content.project_id}, URL: {content.url}")
            db = cls.get_db()
            collection = db[cls.COLLECTION_NAME]
            
            # Convert model to dict and ensure project_id is string
            content_dict = content.model_dump()
            content_dict['project_id'] = str(content_dict['project_id'])
            
            # Check if document already exists
            existing = collection.find_one({
                "project_id": content_dict['project_id'],
                "url": content_dict['url']
            })
            if existing:
                logger.warning(f"Document already exists for project: {content.project_id}, URL: {content.url}")
            
            # Insert with write concern
            logger.info(f"Inserting document into MongoDB: {content_dict}")
            result = collection.insert_one(content_dict)
            
            if result.inserted_id is None:
                error_msg = "Failed to insert document - no inserted_id returned"
                logger.error(error_msg)
                raise MongoDBServiceError(error_msg)
                
            logger.info(f"Successfully saved content with ID: {result.inserted_id}")
            return str(result.inserted_id)
            
        except Exception as e:
            error_msg = f"Failed to save content to MongoDB: {str(e)}"
            logger.error(error_msg)
            raise MongoDBServiceError(error_msg) from e

    @classmethod
    def get_project_content(cls, project_id: UUID) -> List[ScrapedContent]:
        """
        Get all scraped content for a specific project
        """
        try:
            logger.info(f"Attempting to get content for project: {project_id}")
            db = cls.get_db()
            collection = db[cls.COLLECTION_NAME]
            
            query = {
                "project_id": str(project_id)
            }
            logger.info(f"MongoDB query: {query}")
            
            contents = list(collection.find(query))
            logger.info(f"Query result: {contents}")
            
            return [ScrapedContent(**content) for content in contents]
            
        except Exception as e:
            error_msg = f"Failed to get project content: {str(e)}"
            logger.error(error_msg)
            logger.exception("Full traceback:")
            raise MongoDBServiceError(error_msg) from e

    def get_content_by_url(self, project_id: UUID, url: str) -> Optional[ScrapedContent]:
        """
        Get scraped content for a specific URL within a project
        """
        try:
            logger.info(f"Attempting to get content for project: {project_id}, URL: {url}")
            db = self.get_sync_db()
            collection = db[self.COLLECTION_NAME]
            
            query = {
                "project_id": str(project_id),
                "url": url
            }
            logger.info(f"MongoDB query: {query}")
            
            content = collection.find_one(query)
            logger.info(f"Query result: {content}")
            
            if content is None:
                logger.warning(f"No content found for project: {project_id}, URL: {url}")
                return None
                
            try:
                return ScrapedContent(**content)
            except Exception as e:
                error_msg = f"Failed to parse content into ScrapedContent model: {str(e)}"
                logger.error(error_msg)
                logger.exception("Full traceback:")
                raise MongoDBServiceError(error_msg) from e
            
        except Exception as e:
            error_msg = f"Failed to get content by URL: {str(e)}"
            logger.error(error_msg)
            logger.exception("Full traceback:")
            raise MongoDBServiceError(error_msg) from e

    @classmethod
    def get_content_by_url_sync(cls, project_id: UUID, url: str) -> Optional[ScrapedContent]:
        """
        Get scraped content for a specific URL within a project synchronously
        """
        try:
            db = cls.get_db()
            collection = db[cls.COLLECTION_NAME]
            
            # Find document
            document = collection.find_one({
                "project_id": str(project_id),
                "url": url
            })
            
            if document:
                return ScrapedContent(**document)
            return None
            
        except Exception as e:
            error_msg = f"Failed to get content from MongoDB: {str(e)}"
            logger.error(error_msg)
            raise MongoDBServiceError(error_msg) from e

    @classmethod
    def update_content_status(cls, project_id: UUID, url: str, status: str, error_message: Optional[str] = None):
        """
        Update the status of scraped content
        """
        try:
            logger.info(f"Attempting to update status for project: {project_id}, URL: {url}")
            db = cls.get_db()
            collection = db[cls.COLLECTION_NAME]
            
            update_data = {"status": status}
            if error_message is not None:
                update_data["error_message"] = error_message
            
            query = {
                "project_id": str(project_id),
                "url": url
            }
            logger.info(f"MongoDB query: {query}")
            logger.info(f"Update data: {update_data}")
            
            result = collection.update_one(query, {"$set": update_data})
            
            if result.matched_count == 0:
                error_msg = f"No document found for project: {project_id} and URL: {url}"
                logger.error(error_msg)
                raise MongoDBServiceError(error_msg)
                
            logger.info(f"Successfully updated status for project: {project_id}, URL: {url}")
            
        except Exception as e:
            error_msg = f"Failed to update content status: {str(e)}"
            logger.error(error_msg)
            logger.exception("Full traceback:")
            raise MongoDBServiceError(error_msg) from e

    @classmethod
    def update_content(cls, content: ScrapedContent):
        """
        Update a scraped content document in MongoDB
        """
        try:
            logger.info(f"Attempting to update content for project: {content.project_id}, URL: {content.url}")
            db = cls.get_db()
            collection = db[cls.COLLECTION_NAME]
            
            # Convert model to dict and ensure project_id is string
            content_dict = content.model_dump()
            content_dict['project_id'] = str(content_dict['project_id'])
            
            query = {
                "project_id": content_dict['project_id'],
                "url": content_dict['url']
            }
            logger.info(f"MongoDB query: {query}")
            logger.info(f"Update data: {content_dict}")
            
            result = collection.update_one(query, {"$set": content_dict})
            
            if result.matched_count == 0:
                error_msg = f"No document found for project: {content.project_id} and URL: {content.url}"
                logger.error(error_msg)
                raise MongoDBServiceError(error_msg)
                
            logger.info(f"Successfully updated content for project: {content.project_id}, URL: {content.url}")
            
        except Exception as e:
            error_msg = f"Failed to update content: {str(e)}"
            logger.error(error_msg)
            logger.exception("Full traceback:")
            raise MongoDBServiceError(error_msg) from e

    @classmethod
    def update_content_sync(cls, content: ScrapedContent):
        """
        Update a scraped content document in MongoDB synchronously
        """
        try:
            db = cls.get_db()
            collection = db[cls.COLLECTION_NAME]
            
            # Convert model to dict and ensure project_id is string
            content_dict = content.model_dump()
            content_dict['project_id'] = str(content_dict['project_id'])
            
            # Update document
            result = collection.update_one(
                {
                    "project_id": content_dict['project_id'],
                    "url": content_dict['url']
                },
                {"$set": content_dict}
            )
            
            if result.matched_count == 0:
                error_msg = f"No document found to update for project: {content.project_id}, URL: {content.url}"
                logger.error(error_msg)
                raise MongoDBServiceError(error_msg)
                
            logger.info(f"Successfully updated content for project: {content.project_id}, URL: {content.url}")
            
        except Exception as e:
            error_msg = f"Failed to update content in MongoDB: {str(e)}"
            logger.error(error_msg)
            raise MongoDBServiceError(error_msg) from e

    @classmethod
    def delete_content(cls, project_id: UUID, url: str) -> bool:
        """Delete content from MongoDB"""
        try:
            logger.info(f"Attempting to delete content for project: {project_id}, URL: {url}")
            db = cls.get_db()
            collection = db[cls.COLLECTION_NAME]
            
            query = {
                "project_id": str(project_id),
                "url": url
            }
            logger.info(f"MongoDB query: {query}")
            
            result = collection.delete_one(query)
            
            if result.deleted_count == 0:
                logger.warning(f"No document was deleted for project: {project_id}, URL: {url}")
                return False
                
            logger.info(f"Successfully deleted content for project: {project_id}, URL: {url}")
            return True
            
        except Exception as e:
            error_msg = f"Failed to delete content from MongoDB: {str(e)}"
            logger.error(error_msg)
            logger.exception("Full traceback:")
            raise MongoDBServiceError(error_msg) from e

    def update_blog_status(self, blog_id: str, status: str, error_message: Optional[str] = None):
        """
        Update the status of a blog document
        """
        try:
            from bson import ObjectId
            from datetime import datetime, timezone
            import pytz

            logger.info(f"Attempting to update blog status for blog_id: {blog_id}, status: {status}")
            db = self.get_sync_db()
            collection = db['blogs']

            update_data = {
                "status": status,
                "updated_at": datetime.now(timezone.utc)
            }
            
            if error_message is not None:
                update_data["error_message"] = error_message
            
            query = {"_id": ObjectId(blog_id)}
            logger.info(f"MongoDB query: {query}")
            logger.info(f"Update data: {update_data}")
            
            result = collection.update_one(query, {"$set": update_data})
            
            if result.matched_count == 0:
                error_msg = f"No blog document found with id: {blog_id}"
                logger.error(error_msg)
                raise MongoDBServiceError(error_msg)
                
            logger.info(f"Successfully updated blog status for blog_id: {blog_id}")
            
        except Exception as e:
            error_msg = f"Failed to update blog status: {str(e)}"
            logger.error(error_msg)
            logger.exception("Full traceback:")
            raise MongoDBServiceError(error_msg) from e

    @classmethod
    def __aenter__(cls):
        """Async context manager entry"""
        cls.init_db()
        return cls

    @classmethod
    def __aexit__(cls, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        cls.close_connections()
