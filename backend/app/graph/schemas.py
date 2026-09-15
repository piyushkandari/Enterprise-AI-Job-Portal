from typing import Literal
from pydantic import BaseModel, Field


class CandidateProfile(BaseModel):
    """Structured extraction of a resume."""
    full_name: str | None = None
    email: str | None = None
    skills: list[str] = Field(default_factory=list)
    years_experience: float = 0.0
    roles: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    summary: str = ""
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class JobRequirements(BaseModel):
    """Structured extraction of a job description."""
    title: str = ""
    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    min_years_experience: float = 0.0
    responsibilities: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class RequirementVerdict(BaseModel):
    """LLM judgment on ONE requirement vs. its retrieved evidence."""
    requirement: str
    status: Literal["met", "partial", "missing"]
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: str = ""
    weight: float = 1.0


class VerdictList(BaseModel):
    """Wrapper so Gemini's structured-output sees an object at the top level
    (it handles object-shaped schemas far more reliably than bare arrays)."""
    verdicts: list[RequirementVerdict]

