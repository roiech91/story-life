"""Database setup and session management for the Life Story application."""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError
from contextlib import contextmanager
from typing import Generator

from app.config import get_settings
from app.models import Base

settings = get_settings()

# Get DATABASE_URL from environment or settings
# Railway automatically provides DATABASE_URL when Postgres service is linked
database_url = os.getenv("DATABASE_URL") or settings.DATABASE_URL

# PostgreSQL is required - fail if DATABASE_URL is not set
if not database_url:
    raise ValueError(
        "DATABASE_URL is required but not set.\n"
        "Please set DATABASE_URL in your .env file or environment variables.\n"
        "Example: DATABASE_URL=postgresql://user:password@localhost:5432/lifestory\n"
        "For local PostgreSQL setup, see backend/README.md"
    )

# Railway sometimes provides postgres:// instead of postgresql://
# SQLAlchemy requires postgresql://, so we convert it
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

# Ensure we're using PostgreSQL (not SQLite)
if not database_url.startswith("postgresql://"):
    raise ValueError(
        f"PostgreSQL is required, but DATABASE_URL uses unsupported protocol: {database_url.split('://')[0]}\n"
        "Please set DATABASE_URL to use PostgreSQL.\n"
        "Example: DATABASE_URL=postgresql://user:password@localhost:5432/lifestory"
    )

# Log the database URL (without password for security)
if "@" in database_url:
    # Extract the part after @ for logging
    safe_url = database_url.split("@")[-1]
    print(f"Connecting to PostgreSQL: postgresql://***@{safe_url}")
else:
    print(f"Connecting to PostgreSQL: {database_url}")

# Create PostgreSQL engine and test connection
# PostgreSQL is required - fail fast if connection fails
try:
    engine = create_engine(
        database_url,
        echo=settings.DATABASE_ECHO,
        pool_pre_ping=True,  # Verify connections before using them
    )
    
    # Test the connection
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("✅ PostgreSQL connection successful")
except OperationalError as e:
    error_msg = str(e)
    
    # Provide detailed error messages based on the type of failure
    if "password authentication failed" in error_msg.lower():
        print("❌ PostgreSQL connection failed: Password authentication failed")
        print("\n💡 Troubleshooting steps:")
        print("   1. Check your DATABASE_URL in .env file or environment variables")
        print("   2. Verify PostgreSQL credentials (username and password)")
        print("   3. Ensure PostgreSQL is running:")
        print("      - macOS: brew services start postgresql")
        print("      - Linux: sudo systemctl start postgresql")
        print("      - Docker: docker start <postgres-container>")
        if "@" in database_url:
            print(f"   4. Current DATABASE_URL format: {database_url.split('@')[0]}@***")
        print("\n   Example DATABASE_URL: postgresql://postgres:password@localhost:5432/lifestory")
    elif "could not connect" in error_msg.lower() or "connection refused" in error_msg.lower():
        print("❌ PostgreSQL connection failed: Could not connect to database server")
        print("\n💡 Troubleshooting steps:")
        print("   1. Ensure PostgreSQL is running:")
        print("      - macOS: brew services start postgresql")
        print("      - Linux: sudo systemctl start postgresql")
        print("      - Docker: docker start <postgres-container>")
        print("   2. Check if PostgreSQL is listening on the correct port (default: 5432)")
        print("   3. Verify the host and port in your DATABASE_URL")
        print("   4. Test connection manually: psql -h localhost -p 5432 -U postgres")
    elif "database" in error_msg.lower() and "does not exist" in error_msg.lower():
        print("❌ PostgreSQL connection failed: Database does not exist")
        print("\n💡 Troubleshooting steps:")
        print("   1. Create the database:")
        print("      psql -U postgres -c 'CREATE DATABASE lifestory;'")
        print("   2. Or update DATABASE_URL to use an existing database")
    else:
        print(f"❌ PostgreSQL connection failed: {error_msg}")
        print("\n💡 Troubleshooting steps:")
        print("   1. Verify your DATABASE_URL is correct")
        print("   2. Ensure PostgreSQL is installed and running")
        print("   3. Check PostgreSQL server logs for more details")
        print("   4. Test connection manually: psql <your-database-url>")
    
    raise
except Exception as e:
    print(f"❌ PostgreSQL connection failed: {e}")
    raise

# Create session factory for PostgreSQL
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

