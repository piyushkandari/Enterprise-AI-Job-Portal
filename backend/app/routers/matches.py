import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..graph.build import graph
from ..models import Job, Match, Resume, User

router = APIRouter(prefix="/match", tags=["match"])


@router.post("/pair")
async def match_pair(
    job_id: str,
    resume_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run the graph for one resume × one job."""
    job = db.get(Job, job_id)
    resume = db.get(Resume, resume_id)
    if not job or not resume:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job or resume not found")

    # Authorization: employer must own the job OR candidate must own the resume
    if user.role == "employer" and job.employer_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your job")
    if user.role == "candidate" and resume.candidate_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your resume")

    state = {
        "mode": "pair",
        "job_id": job.id,
        "resume_id": resume.id,
        "raw_job_text": job.description,
        "raw_resume_text": resume.raw_text,
        "retry_count": 0,
        "trace_id": str(uuid.uuid4()),
    }
    result = await graph.ainvoke(state)

    # Persist the match (upsert: one row per resume×job pair)
    existing = (
        db.query(Match)
        .filter(Match.resume_id == resume.id, Match.job_id == job.id)
        .first()
    )
    verdicts_json = [v.model_dump() for v in result.get("verdicts", [])]
    if existing:
        existing.score = result.get("score", 0.0)
        existing.verdicts = verdicts_json
        existing.explanation = result.get("explanation", "")
    else:
        db.add(Match(
            resume_id=resume.id,
            job_id=job.id,
            score=result.get("score", 0.0),
            verdicts=verdicts_json,
            explanation=result.get("explanation", ""),
        ))
    db.commit()

    return {
        "job_id": job.id,
        "resume_id": resume.id,
        "score": result.get("score", 0.0),
        "explanation": result.get("explanation", ""),
        "verdicts": verdicts_json,
        "trace_id": result.get("trace_id"),
        "token_usage": result.get("token_usage", []),
        "errors": result.get("errors", []),
    }


@router.post("/recommend-jobs")
async def recommend_jobs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """For the logged-in candidate: run pair match against every open job."""
    if user.role != "candidate":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "candidates only")

    resume = db.query(Resume).filter(Resume.candidate_id == user.id).first()
    if not resume:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no resume uploaded")

    jobs = db.query(Job).filter(Job.status == "open").all()
    results = []
    for job in jobs:
        state = {
            "mode": "pair",
            "job_id": job.id,
            "resume_id": resume.id,
            "raw_job_text": job.description,
            "raw_resume_text": resume.raw_text,
            "retry_count": 0,
            "trace_id": str(uuid.uuid4()),
        }
        r = await graph.ainvoke(state)
        results.append({
            "job_id": job.id,
            "job_title": job.title,
            "score": r.get("score", 0.0),
            "explanation": r.get("explanation", ""),
            "verdicts": [v.model_dump() for v in r.get("verdicts", [])],
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return {"resume_id": resume.id, "recommendations": results}