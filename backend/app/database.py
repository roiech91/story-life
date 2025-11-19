"""Database setup and session management for the Life Story application."""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator

from app.config import get_settings
from app.models import Base

settings = get_settings()

# Get DATABASE_URL from environment or settings
# Railway automatically provides DATABASE_URL when Postgres service is linked
database_url = os.getenv("DATABASE_URL") or settings.DATABASE_URL

if not database_url:
    raise ValueError(
        "DATABASE_URL is not set. "
        "Please set it as an environment variable or in your .env file. "
        "Railway automatically provides DATABASE_URL when a Postgres service is linked."
    )

# Railway sometimes provides postgres:// instead of postgresql://
# SQLAlchemy requires postgresql://, so we convert it
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

# Log the database URL (without password for security)
safe_url = database_url.split("@")[-1] if "@" in database_url else "***"
print(f"Connecting to database at: ***@{safe_url}")

# Create database engine
engine = create_engine(
    database_url,
    echo=settings.DATABASE_ECHO,
    pool_pre_ping=True,  # Verify connections before using them
    connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function for FastAPI to get a database session.
    
    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions (for use outside FastAPI dependencies).
    
    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

