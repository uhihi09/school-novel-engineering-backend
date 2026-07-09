import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User
from app.repositories.user_repository import user_repository

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str = Field(..., description="User email (used as the login id)")
    password: str = Field(..., min_length=6, description="Plaintext password (hashed server-side)")
    nickname: Optional[str] = Field(None, description="Display nickname")


class LoginRequest(BaseModel):
    email: str = Field(..., description="Registered email")
    password: str = Field(..., description="Account password")


class UserPublic(BaseModel):
    user_id: str
    email: str
    nickname: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


def _to_public(user: User) -> UserPublic:
    return UserPublic(user_id=user.UserId, email=user.Email, nickname=user.Nickname)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Registers a new user account and returns an access token."""
    if user_repository.get_by_email(db, req.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )
    user = User(
        UserId=f"user_{uuid.uuid4().hex[:12]}",
        Email=req.email,
        Nickname=req.nickname,
        HashedPassword=hash_password(req.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # The unique-email constraint is the source of truth: handles the race where two
        # concurrent registrations both pass the get_by_email pre-check.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )
    db.refresh(user)
    token = create_access_token(user.UserId)
    return TokenResponse(access_token=token, user=_to_public(user))


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticates an existing user and returns an access token."""
    user = user_repository.get_by_email(db, req.email)
    if user is None or not user.HashedPassword or not verify_password(req.password, user.HashedPassword):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    token = create_access_token(user.UserId)
    return TokenResponse(access_token=token, user=_to_public(user))


@router.get("/me", response_model=UserPublic)
def read_current_user(current_user: User = Depends(get_current_user)):
    """Returns the authenticated user's profile."""
    return _to_public(current_user)
