from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_role
from ..db import get_db
from ..models import Job, User
from ..schemas import JobCreate, JobResponse, JobUpdate

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/", response_model=JobResponse, status_code=201)
def create_job(
    body: JobCreate,
    db: Session = Depends(get_db),
    employer: User = Depends(require_role("employer")),
):
    job = Job(
        employer_id=employer.id,
        title=body.title,
        description=body.description,
        status=body.status,
        structured_requirements={},   # populated by the LangGraph pipeline later
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("/", response_model=list[JobResponse])
def list_jobs(
    status_filter: str | None = "open",
    db: Session = Depends(get_db),
):
    """Public endpoint — candidates browse this. Only open jobs by default."""
    q = db.query(Job)
    if status_filter:
        q = q.filter(Job.status == status_filter)
    return q.order_by(Job.created_at.desc()).all()


@router.get("/mine", response_model=list[JobResponse])
def my_jobs(
    db: Session = Depends(get_db),
    employer: User = Depends(require_role("employer")),
):
    """Employer's own jobs, including closed ones."""
    return (
        db.query(Job)
        .filter(Job.employer_id == employer.id)
        .order_by(Job.created_at.desc())
        .all()
    )


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    return job


@router.patch("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: str,
    body: JobUpdate,
    db: Session = Depends(get_db),
    employer: User = Depends(require_role("employer")),
):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    if job.employer_id != employer.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your job")

    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(job, k, v)
    db.commit()
    db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=204)
def delete_job(
    job_id: str,
    db: Session = Depends(get_db),
    employer: User = Depends(require_role("employer")),
):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    if job.employer_id != employer.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your job")
    db.delete(job)
    db.commit()