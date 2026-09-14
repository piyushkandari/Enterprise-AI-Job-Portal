from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from ..db import get_db
from ..models import User
from ..schemas import LoginRequest, SignupRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserResponse, status_code=201)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        # Same message for both cases — never reveal whether the email exists
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")

    token = create_access_token(user.id, user.role)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user