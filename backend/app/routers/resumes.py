from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_role
from ..db import get_db
from ..models import Resume, User
from ..schemas import ResumeMeta, ResumeResponse
from ..services.parsing import MAX_BYTES, extract_text

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("/", response_model=ResumeResponse, status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    candidate: User = Depends(require_role("candidate")),
):
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"file too large (max {MAX_BYTES // (1024*1024)} MB)",
        )
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty file")

    text = extract_text(file.filename or "", data)

    # One resume per candidate — upload replaces the previous.
    existing = (
        db.query(Resume).filter(Resume.candidate_id == candidate.id).first()
    )
    if existing:
        existing.raw_text = text
        existing.structured_profile = {}   # invalidate — will be re-extracted by graph
        existing.embedding_id = None
        db.commit()
        db.refresh(existing)
        return existing

    resume = Resume(
        candidate_id=candidate.id,
        raw_text=text,
        structured_profile={},
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


@router.get("/me", response_model=ResumeResponse)
def my_resume(
    db: Session = Depends(get_db),
    candidate: User = Depends(require_role("candidate")),
):
    resume = (
        db.query(Resume).filter(Resume.candidate_id == candidate.id).first()
    )
    if not resume:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no resume uploaded")
    return resume


@router.get("/me/meta", response_model=ResumeMeta | None)
def my_resume_meta(
    db: Session = Depends(get_db),
    candidate: User = Depends(require_role("candidate")),
):
    """Lightweight — used by dashboard to check 'has resume?' without pulling text."""
    resume = (
        db.query(Resume).filter(Resume.candidate_id == candidate.id).first()
    )
    return resume


@router.delete("/me", status_code=204)
def delete_my_resume(
    db: Session = Depends(get_db),
    candidate: User = Depends(require_role("candidate")),
):
    resume = (
        db.query(Resume).filter(Resume.candidate_id == candidate.id).first()
    )
    if not resume:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no resume uploaded")
    db.delete(resume)
    db.commit()