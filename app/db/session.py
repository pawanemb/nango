from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine
from app.core.config import settings
import logging
from contextlib import contextmanager
import threading

logger = logging.getLogger(__name__)

# Initialize the engine and SessionLocal for backward compatibility
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=40,             # Increased from 10 to handle concurrent scraping and retries
    max_overflow=30,          # Increased from 5 for better resource management under load
    pool_recycle=1800,        # 30 minutes - longer recycle time for stability
    pool_timeout=30,          # Increased from 20 for better connection availability
    pool_use_lifo=True,       # Better for connection pooling
    connect_args={
        "options": "-c statement_timeout=120000 -c idle_in_transaction_session_timeout=300000",  # 2 min statement timeout
        "application_name": "dev_rayo_backend"        # Identify your app in pg_stat_activity
    },
    # Required for PgBouncer transaction pooling mode
    execution_options={
        "isolation_level": "AUTOCOMMIT"
    },
    # Add connection pooling optimizations
    pool_reset_on_return='commit',  # Reset connections properly
    echo=False  # Disable SQL logging for performance
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Context manager for handling session lifecycle
from contextlib import contextmanager

@contextmanager
def get_db_session():
    db = SessionLocal()
    try:
        yield db  # Provides session
    finally:
        db.close()  # Ensures session is closed




# Dependency for FastAPI
def get_db():
    """FastAPI dependency for database sessions"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {str(e)}")
        db.rollback()
        raise
    finally:
        logger.debug("Closing database session")
        try:
            db.close()
        except Exception as e:
            logger.error(f"Error closing database session: {str(e)}")
