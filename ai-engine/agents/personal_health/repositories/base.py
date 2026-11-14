"""SQLAlchemy base configuration and database session management."""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from ..config.settings import get_settings

Base = declarative_base()

def get_engine():
    """Create and return SQLAlchemy engine with appropriate dialect."""
    return get_engine_for_url(None)


def get_engine_for_url(db_url: str | None):
    """Create an engine for an explicit URL, or the configured settings URL when None."""
    cfg = get_settings()
    db_url = db_url or cfg.database_url
    if db_url.startswith("sqlite"):
        if ":memory:" in db_url:
            from sqlalchemy.pool import StaticPool
            return create_engine(
                db_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool
            )
        db_path = db_url.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        return create_engine(db_url, connect_args={"check_same_thread": False})
    return create_engine(db_url, pool_pre_ping=True)

engine = get_engine()
SessionFactory = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

def reconfigure_engine(db_url: str) -> None:
    """Point the existing engine and session factory at a new database URL.

    Integration seam for the backend API gateway and tests: the scoped session
    factory is reconfigured in place (identity preserved) so repositories keep
    working without reimport. The previous engine is disposed first.
    """
    global engine
    try:
        engine.dispose()
    except Exception:
        pass
    engine = get_engine_for_url(db_url)
    SessionFactory.configure(bind=engine)

def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)

def get_db_session():
    """Yield a database session context."""
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()
