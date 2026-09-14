from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from typing import Literal


# ---------- Auth ----------
class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Literal["employer", "candidate"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}