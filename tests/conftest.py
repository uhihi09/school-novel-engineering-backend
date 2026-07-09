import os
from pathlib import Path

TEST_DB_FILE = str(Path(__file__).resolve().parent.parent / "test_equiscope.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"

# Keep the suite HERMETIC regardless of the developer's .env. Set BEFORE importing the app so
# settings/singletons bind to these values:
#   • DATABASE_URL -> throwaway in-memory SQLite (the app engine only runs startup create_all;
#     all real queries go through the overridden get_db, so this avoids file-lock contention).
#   • Gemini creds blanked -> gemini_service.client stays None -> mock fallbacks, no network calls.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["GEMINI_API_KEY"] = ""
os.environ["USE_VERTEX_AI"] = "false"
os.environ["GCP_PROJECT_ID"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db.session import Base
from app.api.deps import get_db

# CRITICAL: Import all models so they are registered on the Base.metadata
from app.db.models import User, InequalityReport, SimulationLog

# Use StaticPool for SQLite file connections in tests
from sqlalchemy.pool import StaticPool
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Initializes and tears down the test database tables once for the entire session."""
    # Ensure any residual test database is cleaned up first
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except OSError:
            pass
            
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except OSError:
            pass

@pytest.fixture(scope="function")
def db():
    """Yields a database session nested inside a transaction, rolling back after the test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db):
    """FastAPI TestClient fixture with overridden DB dependency."""
    def override_get_db():
        try:
            yield db
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
