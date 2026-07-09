from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
    # Validate pooled connections before use so Cloud SQL idle-timeout drops are transparently
    # recycled instead of surfacing as "server closed the connection unexpectedly". Harmless on SQLite.
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# NOTE: the FastAPI request-scoped DB dependency lives in app.api.deps.get_db (single source
# of truth). This module only exposes the engine, session factory, and declarative Base.
