import operator
from typing import TypedDict, Literal, Annotated

from .schemas import CandidateProfile, JobRequirements, RequirementVerdict


class GraphState(TypedDict, total=False):
    # --- inputs ---
    mode: Literal["pair", "resume_to_jobs", "job_to_candidates"]
    job_id: str | None
    resume_id: str | None
    raw_job_text: str | None
    raw_resume_text: str | None

    # --- extraction ---
    candidate_profile: CandidateProfile | None
    job_requirements: JobRequirements | None

    # --- retrieval ---
    candidate_ids: list[str]
    resume_texts: dict[str, str]
    evidence: dict[str, list[dict]]

    # --- judgment ---
    verdicts: list[RequirementVerdict]
    score: float
    explanation: str

    # --- control / observability ---
    trace_id: str
    retry_count: int
    errors: Annotated[list[str], operator.add]
    token_usage: Annotated[list[dict], operator.add]