import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.db.session import engine, Base
from app.api.v1.auth import router as auth_router
from app.api.v1.maps import router as maps_router
from app.api.v1.simulator import router as simulator_router
from app.api.v1.crowdsourcing import router as crowdsourcing_router
from app.api.v1.advisor import router as advisor_router

logger = logging.getLogger(__name__)


# Automated DB initialization on startup (lifespan replaces deprecated on_event)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Best-effort schema bootstrap: don't crash the server if the configured DB (e.g. Cloud SQL)
    # is unreachable at boot. DB-backed endpoints surface errors per-request instead.
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Startup DB init skipped (database unreachable?): %s", exc)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="EquiScope: 다차원 불평등 공간 시각화 및 정책 시뮬레이터 백엔드 API",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Set CORS middleware to allow requests from any local frontend or mobile simulators.
# NOTE: allow_credentials must stay False while allow_origins is "*": browsers reject the
# wildcard Access-Control-Allow-Origin on credentialed requests. Enumerate explicit origins
# if/when cookie/JWT auth is added, and only then flip allow_credentials back on.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Standard API routers matching the equiscope-api.md spec contracts
app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth", tags=["Auth & Users"])
app.include_router(maps_router, prefix=f"{settings.API_V1_STR}/maps", tags=["Maps & News Grid"])
app.include_router(simulator_router, prefix=f"{settings.API_V1_STR}/simulator", tags=["Policy Simulator & RAG"])
app.include_router(crowdsourcing_router, prefix=f"{settings.API_V1_STR}/crowdsourcing", tags=["Crowdsourcing Report"])
app.include_router(advisor_router, prefix=f"{settings.API_V1_STR}/advisor", tags=["AI Policy Advisor"])

# Serve uploaded citizen-report media files (real storage for F-2/F-6).
_media_dir = Path(settings.MEDIA_DIR)
_media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(_media_dir)), name="media")

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }
