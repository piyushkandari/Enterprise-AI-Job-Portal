import asyncio
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..graph.build import graph
from ..models import Job, JobInterest, Match, Resume, User

router = APIRouter(prefix="/match", tags=["match"])

# Gemini free tier: 5 requests per minute. Each pair match fires ~2 LLM calls
# (judge + explain) after caching, so 12s between pairs keeps us under quota.
PAIR_DELAY_SECONDS = 12


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
    """For the logged-in candidate: run pair match against every open job,
    persist each match, and return ranked results."""
    if user.role != "candidate":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "candidates only")

    resume = db.query(Resume).filter(Resume.candidate_id == user.id).first()
    if not resume:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no resume uploaded")

    jobs = db.query(Job).filter(Job.status == "open").all()
    results = []
    for i, job in enumerate(jobs):
        # Rate-limit guard: sleep between iterations, not before the first.
        if i > 0:
            await asyncio.sleep(PAIR_DELAY_SECONDS)

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
        verdicts_json = [v.model_dump() for v in r.get("verdicts", [])]

        existing = (
            db.query(Match)
            .filter(Match.resume_id == resume.id, Match.job_id == job.id)
            .first()
        )
        if existing:
            existing.score = r.get("score", 0.0)
            existing.verdicts = verdicts_json
            existing.explanation = r.get("explanation", "")
        else:
            db.add(Match(
                resume_id=resume.id,
                job_id=job.id,
                score=r.get("score", 0.0),
                verdicts=verdicts_json,
                explanation=r.get("explanation", ""),
            ))

        results.append({
            "job_id": job.id,
            "job_title": job.title,
            "score": r.get("score", 0.0),
            "explanation": r.get("explanation", ""),
            "verdicts": verdicts_json,
        })

    db.commit()
    results.sort(key=lambda x: x["score"], reverse=True)
    return {"resume_id": resume.id, "recommendations": results}


@router.get("/me")
async def my_matches(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """All persisted matches for the current candidate, sorted by score.
    Fast — reads only from the DB, no LLM calls."""
    if user.role != "candidate":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "candidates only")

    resume = db.query(Resume).filter(Resume.candidate_id == user.id).first()
    if not resume:
        return {"resume_id": None, "recommendations": []}

    rows = (
        db.query(Match, Job)
        .join(Job, Match.job_id == Job.id)
        .filter(Match.resume_id == resume.id, Job.status == "open")
        .order_by(Match.score.desc())
        .all()
    )

    # Fetch this candidate's interests in one query.
    interested_ids = {
        i.job_id
        for i in db.query(JobInterest)
        .filter(JobInterest.candidate_id == user.id)
        .all()
    }

    return {
        "resume_id": resume.id,
        "recommendations": [
            {
                "job_id": job.id,
                "job_title": job.title,
                "score": match.score,
                "explanation": match.explanation,
                "verdicts": match.verdicts,
                "is_interested": job.id in interested_ids,
            }
            for match, job in rows
        ],
    }


@router.get("/for-job/{job_id}")
async def match_for_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Fetch the current candidate's persisted match for a specific job.
    Fast — no LLM calls."""
    if user.role != "candidate":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "candidates only")

    resume = db.query(Resume).filter(Resume.candidate_id == user.id).first()
    if not resume:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no resume uploaded")

    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")

    match = (
        db.query(Match)
        .filter(Match.resume_id == resume.id, Match.job_id == job.id)
        .first()
    )
    if not match:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no match computed yet")

    is_interested = (
        db.query(JobInterest)
        .filter(
            JobInterest.candidate_id == user.id,
            JobInterest.job_id == job.id,
        )
        .first()
    ) is not None

    return {
        "job_id": job.id,
        "job_title": job.title,
        "job_description": job.description,
        "resume_id": resume.id,
        "score": match.score,
        "explanation": match.explanation,
        "verdicts": match.verdicts,
        "computed_at": match.computed_at.isoformat(),
        "is_interested": is_interested,
    }


@router.post("/compute-for-job/{job_id}")
async def compute_for_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Employer triggers matching for one of their jobs against all candidates."""
    if user.role != "employer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "employers only")

    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    if job.employer_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your job")

    resumes = db.query(Resume).all()
    results = []
    for i, resume in enumerate(resumes):
        # Rate-limit guard: sleep between iterations, not before the first.
        if i > 0:
            await asyncio.sleep(PAIR_DELAY_SECONDS)

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
        verdicts_json = [v.model_dump() for v in r.get("verdicts", [])]

        existing = (
            db.query(Match)
            .filter(Match.resume_id == resume.id, Match.job_id == job.id)
            .first()
        )
        if existing:
            existing.score = r.get("score", 0.0)
            existing.verdicts = verdicts_json
            existing.explanation = r.get("explanation", "")
        else:
            db.add(Match(
                resume_id=resume.id,
                job_id=job.id,
                score=r.get("score", 0.0),
                verdicts=verdicts_json,
                explanation=r.get("explanation", ""),
            ))

    db.commit()
    return {"job_id": job.id, "candidates_matched": len(resumes)}


@router.get("/for-job-employer/{job_id}")
async def for_job_employer(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Ranked candidates for one job. Reads cached matches from DB.
    Also returns whether each candidate has marked interest in this job."""
    if user.role != "employer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "employers only")

    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    if job.employer_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your job")

    rows = (
        db.query(Match, Resume)
        .join(Resume, Match.resume_id == Resume.id)
        .filter(Match.job_id == job.id)
        .order_by(Match.score.desc())
        .all()
    )

    # Fetch interested candidate_ids in one query
    interested_ids = {
        i.candidate_id
        for i in db.query(JobInterest)
        .filter(JobInterest.job_id == job.id)
        .all()
    }

    candidates = []
    for match, resume in rows:
        profile = resume.structured_profile or {}
        candidates.append({
            "resume_id": resume.id,
            "candidate_id": resume.candidate_id,
            "candidate_name": profile.get("full_name") or "Anonymous candidate",
            "candidate_email": profile.get("email") or "",
            "years_experience": profile.get("years_experience", 0),
            "score": match.score,
            "explanation": match.explanation,
            "verdicts": match.verdicts,
            "is_interested": resume.candidate_id in interested_ids,
        })

    return {
        "job_id": job.id,
        "job_title": job.title,
        "candidates": candidates,
    }