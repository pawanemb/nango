from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=1,             # <= ONLY 1 connection per instance
    max_overflow=0,          # <= do not create extra connections
    pool_timeout=5,
    pool_recycle=300,
    pool_pre_ping=True,
    connect_args={
        "options": "-c statement_timeout=120000 -c idle_in_transaction_session_timeout=300000"
    },
    execution_options={
        "isolation_level": "AUTOCOMMIT"
    },
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
