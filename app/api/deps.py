from typing import Generator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import SessionLocal

# Default identity used when no bearer token is presented, so the map/simulator/crowdsourcing
# endpoints stay usable without auth friction during hackathon client prototyping.
DEFAULT_HACKATHON_USER_ID = "user_hackathon_equiscope_01"

# auto_error=False -> optional auth (falls back to the default user id).
_optional_bearer = HTTPBearer(auto_error=False)
# auto_error=True -> strict auth (401/403 when the token is missing).
_required_bearer = HTTPBearer()


def get_db() -> Generator:
    """Dependency provider to manage database session lifecycle."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
) -> str:
    """Resolves the caller's user id from a bearer token when present; otherwise the mock id.

    This keeps existing unauthenticated clients working while letting authenticated callers
    act as their real account.
    """
    if credentials is not None:
        payload = decode_access_token(credentials.credentials)
        if payload and payload.get("sub"):
            return payload["sub"]
    return DEFAULT_HACKATHON_USER_ID


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_required_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Strict dependency: requires a valid bearer token mapping to an existing user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(credentials.credentials)
    if not payload or not payload.get("sub"):
        raise credentials_exception
    user = db.query(User).filter(User.UserId == payload["sub"]).first()
    if user is None:
        raise credentials_exception
    return user
