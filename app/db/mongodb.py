from pymongo import MongoClient
from app.core.config import settings
import logging
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

class MongoDB:
    client: MongoClient = None
    db = None

def get_mongodb():
    """
    Get MongoDB database connection.
    Returns MongoClient instance.
    """
    if MongoDB.db is None:
        connect_to_mongo()
    return MongoDB.db

def connect_to_mongo():
    """
    Connect to MongoDB with enhanced settings.
    """
    try:
        # Build connection string
        uri = settings.MONGODB_URL
        
        # Create client with retry writes enabled
        MongoDB.client = MongoClient(
            uri,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=60000,
            socketTimeoutMS=60000,
            maxPoolSize=50,
            retryWrites=True,
            w='majority'  # Write concern
        )
        
        # Test the connection
        MongoDB.client.server_info()
        logger.info("Successfully connected to MongoDB server")
        
        # Get the database
        MongoDB.db = MongoDB.client[settings.MONGODB_DB_NAME]
        
        # Try to list collections to verify database access
        MongoDB.db.list_collection_names()
        logger.info(f"Successfully connected to database: {settings.MONGODB_DB_NAME}")
        
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        if MongoDB.client is not None:
            MongoDB.client.close()
            MongoDB.client = None
        MongoDB.db = None
        raise

def close_mongo_connection():
    """
    Close MongoDB connection.
    """
    if MongoDB.client is not None:
        MongoDB.client.close()
        MongoDB.client = None
        MongoDB.db = None
        logger.info("MongoDB connection closed")
