from datetime import datetime, timedelta, timezone
from typing import Callable

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import User

ALGO = "HS256"
TOKEN_TTL_HOURS = 24

# tokenUrl is used only by Swagger UI — points at the login endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ---------- Password hashing ----------
def hash_password(plain: str) -> str:
    # bcrypt has a 72-byte input limit; truncate cleanly (rare in practice)
    raw = plain.encode("utf-8")[:72]
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        return False


# ---------- JWT ----------
def create_access_token(user_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGO)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")


# ---------- Dependencies ----------
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(token)
    user = db.get(User, payload["sub"])
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    return user


def require_role(role: str) -> Callable[[User], User]:
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role != role:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires role: {role}")
        return user
    return _dep