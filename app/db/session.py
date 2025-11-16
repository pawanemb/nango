from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# GLOBAL engine (reused across all workers)
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=20,            # GOOD for Cloud Run
    max_overflow=10,         # Avoid Supabase overload
    pool_recycle=1800,       
    pool_timeout=20,         
    pool_use_lifo=True,
    connect_args={
        "application_name": "rayo_backend",
        "options": "-c statement_timeout=60000"
    },
    execution_options={"isolation_level": "AUTOCOMMIT"},
    pool_reset_on_return='commit',
)

# GLOBAL session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Context manager
@contextmanager
def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# FastAPI dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()
