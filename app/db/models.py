from sqlalchemy import Column, String, Float, Boolean, DateTime, JSON
from datetime import datetime, timezone
from app.db.session import Base

def _utcnow() -> datetime:
    """Timezone-aware UTC now (replaces deprecated datetime.utcnow)."""
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"
    
    UserId = Column(String(36), primary_key=True, index=True)
    Email = Column(String(255), nullable=False, unique=True, index=True)
    Nickname = Column(String(100))
    HashedPassword = Column(String(255), nullable=True)  # PBKDF2 hash; nullable for legacy/mock users
    TargetLat = Column(Float, nullable=True)
    TargetLng = Column(Float, nullable=True)
    CreatedAt = Column(DateTime, default=_utcnow)

class InequalityReport(Base):
    __tablename__ = "inequality_reports"
    
    ReportId = Column(String(36), primary_key=True, index=True)
    UserId = Column(String(36), nullable=False, index=True)
    Category = Column(String(50), nullable=False)
    RawTitle = Column(String(255), nullable=False)
    SanitizedDescription = Column(String, nullable=True)
    Latitude = Column(Float, nullable=False)
    Longitude = Column(Float, nullable=False)
    IsValid = Column(Boolean, default=True)
    AiTrustScore = Column(Float, default=100.0)
    MediaUrl = Column(String(1000), nullable=True)
    CreatedAt = Column(DateTime, default=_utcnow)

class SimulationLog(Base):
    __tablename__ = "simulation_logs"
    
    SimulationId = Column(String(36), primary_key=True, index=True)
    UserId = Column(String(36), nullable=True, index=True)
    PolicyTitle = Column(String(255), nullable=False)
    PolicyVariables = Column(JSON, nullable=True)
    GiniBefore = Column(Float, nullable=False)
    GiniAfter = Column(Float, nullable=False)
    AiResultSummary = Column(String, nullable=True)
    CreatedAt = Column(DateTime, default=_utcnow)
