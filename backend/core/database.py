"""
Database setup with SQLAlchemy synchronous support.
"""

import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

from core.config import settings

logger = logging.getLogger("kms.database")

# Use synchronous SQLite
database_url: str = settings.database_url
# pylint: disable=no-member
if database_url.startswith("sqlite+aiosqlite:///"):
    database_url = database_url.replace("sqlite+aiosqlite:///", "sqlite:///")

# Create sync engine
engine = create_engine(
    database_url,
    echo=False,
    future=True,
    connect_args={"timeout": 30},
)

# Enable WAL mode and load sqlite_vec extension for SQLite
if database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    @event.listens_for(engine, "connect")
    def load_sqlite_vec(dbapi_conn, connection_record):
        """Load sqlite_vec extension on each connection."""
        try:
            import sqlite_vec
            dbapi_conn.enable_load_extension(True)
            sqlite_vec.load(dbapi_conn)
            dbapi_conn.enable_load_extension(False)
            settings.sqlite_vec_loaded = True
            logger.info("sqlite_vec extension loaded successfully")
        except Exception as e:
            settings.sqlite_vec_loaded = False
            logger.error(f"Failed to load sqlite_vec extension: {e}")


# Session factory
SessionLocal = sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
)


# Base class for models
Base = declarative_base()


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
