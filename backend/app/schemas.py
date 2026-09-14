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


# ---------- Jobs ----------
class JobCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str = Field(min_length=20)   # we'll feed this to the LLM later; needs substance
    status: Literal["open", "closed"] = "open"


class JobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, min_length=20)
    status: Literal["open", "closed"] | None = None


class JobResponse(BaseModel):
    id: str
    employer_id: str
    title: str
    description: str
    structured_requirements: dict
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}