"""
Database engine and schema management.

On server startup, call `ensure_schema()` to auto-create any
tables defined in models.py that don't yet exist in the database.
"""

import os
import logging
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("cloudinha-db")


def get_database_url() -> str:
    """Get the PostgreSQL connection URL from environment variables."""
    db_url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DB_CONNECTION_STRING")
    if not db_url:
        logger.warning("No SUPABASE_DB_URL or DB_CONNECTION_STRING found. Schema sync disabled.")
        return None
    # SQLAlchemy requires 'postgresql://' not 'postgres://'
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return db_url


def ensure_schema():
    """
    Create any missing tables in the database.
    
    Uses SQLAlchemy's create_all with checkfirst=True,
    which is idempotent — it only creates tables that don't exist.
    Existing tables are NOT modified (no ALTER TABLE).
    """
    from src.db.models import Base

    db_url = get_database_url()
    if not db_url:
        return

    try:
        engine = create_engine(db_url, echo=False, pool_pre_ping=True)
        
        # Inspect current state
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names(schema="public"))
        model_tables = set(Base.metadata.tables.keys())
        
        missing = model_tables - existing_tables
        
        if missing:
            logger.info(f"[DB] Creating {len(missing)} missing table(s): {', '.join(sorted(missing))}")
            Base.metadata.create_all(engine, checkfirst=True)
            logger.info("[DB] Schema sync complete.")
        else:
            logger.info(f"[DB] All {len(model_tables)} tables already exist. No changes needed.")
        
        engine.dispose()
        
    except Exception as e:
        logger.error(f"[DB] Schema sync failed (non-fatal): {e}")
        # Don't crash the server if DB sync fails — it's a best-effort operation
