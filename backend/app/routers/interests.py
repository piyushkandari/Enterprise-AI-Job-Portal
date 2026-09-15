from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import Job, JobInterest, Resume, User
from ..schemas import InterestResponse, InterestedCandidate

router = APIRouter(prefix="/interests", tags=["interests"])


@router.post("/{job_id}", status_code=201)
def mark_interest(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Idempotent — marking twice returns the existing record, no error."""
    if user.role != "candidate":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "candidates only")

    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")

    existing = (
        db.query(JobInterest)
        .filter(
            JobInterest.candidate_id == user.id,
            JobInterest.job_id == job_id,
        )
        .first()
    )
    if existing:
        return existing

    interest = JobInterest(candidate_id=user.id, job_id=job_id)
    db.add(interest)
    db.commit()
    db.refresh(interest)
    return interest


@router.delete("/{job_id}", status_code=204)
def remove_interest(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "candidate":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "candidates only")

    row = (
        db.query(JobInterest)
        .filter(
            JobInterest.candidate_id == user.id,
            JobInterest.job_id == job_id,
        )
        .first()
    )
    if row:
        db.delete(row)
        db.commit()


@router.get("/me", response_model=list[InterestResponse])
def my_interests(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """All jobs this candidate has marked interested in."""
    if user.role != "candidate":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "candidates only")

    rows = (
        db.query(JobInterest)
        .filter(JobInterest.candidate_id == user.id)
        .order_by(JobInterest.created_at.desc())
        .all()
    )
    return rows


@router.get("/for-job/{job_id}", response_model=list[InterestedCandidate])
def interested_for_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Employer sees who's expressed interest in their job."""
    if user.role != "employer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "employers only")

    job = db.get(Job, job_id)
    if not job or job.employer_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your job")

    rows = (
        db.query(JobInterest, User, Resume)
        .join(User, JobInterest.candidate_id == User.id)
        .outerjoin(Resume, Resume.candidate_id == User.id)
        .filter(JobInterest.job_id == job_id)
        .order_by(JobInterest.created_at.desc())
        .all()
    )

    out = []
    for interest, candidate, resume in rows:
        profile = (resume.structured_profile if resume else None) or {}
        out.append(InterestedCandidate(
            candidate_id=candidate.id,
            email=candidate.email,
            full_name=profile.get("full_name") or candidate.email.split("@")[0],
            created_at=interest.created_at,
        ))
    return out