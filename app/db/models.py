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

class RegionStat(Base):
    """Real per-region inequality statistics (F-1), seeded from public data + grounded search."""
    __tablename__ = "region_stats"

    RegionId = Column(String(64), primary_key=True, index=True)   # e.g. "seoul-gangnam"
    RegionName = Column(String(100), nullable=False)              # "강남구"
    CenterLat = Column(Float, nullable=False)
    CenterLng = Column(Float, nullable=False)
    AvgIncomeManwon = Column(Float, nullable=True)   # income: 월 평균 소득(만원)
    DoctorsPer1k = Column(Float, nullable=True)      # healthcare: 인구 1천명당 의사 수
    Pm25 = Column(Float, nullable=True)              # climate: 연평균 PM2.5 (㎍/㎥)
    EducationIndex = Column(Float, nullable=True)    # education: 교육 접근/자원 지수 (0~100)
    Source = Column(String(255), nullable=True)      # data provenance
    UpdatedAt = Column(DateTime, default=_utcnow)

class RegionBoundary(Base):
    """Real administrative boundary polygons (F-1 choropleth), keyed to region_stats by RegionId."""
    __tablename__ = "region_boundaries"

    RegionId = Column(String(64), primary_key=True, index=True)  # matches RegionStat.RegionId
    Boundary = Column(JSON, nullable=False)   # GeoJSON geometry (MultiPolygon/Polygon), simplified
    MinLat = Column(Float, nullable=True)
    MaxLat = Column(Float, nullable=True)
    MinLng = Column(Float, nullable=True)
    MaxLng = Column(Float, nullable=True)

class NewsPin(Base):
    """Inequality news collected continuously by the background collector (F-2).

    Rows accumulate over time (no deletion) — a time-series asset. DedupeKey blocks
    re-inserting the same headline across collection cycles.
    """
    __tablename__ = "news_pins"

    PinId = Column(String(36), primary_key=True, index=True)
    RegionName = Column(String(50), nullable=False, index=True)   # 시도 (or "viewport" for live-path saves)
    Headline = Column(String(500), nullable=False)
    Category = Column(String(50), default="income")
    SentimentScore = Column(Float, default=-0.5)
    Severity = Column(String(20), default="Medium")
    Summary = Column(String, nullable=True)
    Latitude = Column(Float, nullable=False, index=True)
    Longitude = Column(Float, nullable=False, index=True)
    DedupeKey = Column(String(64), unique=True, index=True)       # sha256(normalized headline)
    CollectedAt = Column(DateTime, default=_utcnow, index=True)

class PolicyDoc(Base):
    """Policy/legislation corpus for real vector-search RAG (F-5/F-7)."""
    __tablename__ = "policy_docs"

    DocId = Column(String(64), primary_key=True, index=True)
    Title = Column(String(255), nullable=False)
    Category = Column(String(50), nullable=True)
    Content = Column(String, nullable=False)
    Embedding = Column(JSON, nullable=True)          # list[float] embedding vector
    Source = Column(String(255), nullable=True)
    UpdatedAt = Column(DateTime, default=_utcnow)
