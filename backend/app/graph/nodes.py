"""
LangGraph node functions.

Step 7: extract_resume, extract_job, judge_match, generate_explanation
use Gemini via langchain-google-genai with structured output.

Step 7b: embed_and_index, retrieve_candidates, retrieve_evidence now use
Gemini embeddings + pgvector for real semantic retrieval. No stubs remain.

Step 7c: extract_resume and extract_job cache their results in Postgres
to avoid re-running extraction on repeat matches. judge_match and
generate_explanation retry automatically on 429 quota errors.
"""
import asyncio
import sys
from functools import wraps

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from ..config import settings
from ..db import SessionLocal
from ..models import Job, Resume
from ..services.vectorstore import (
    search_chunks,
    search_resumes,
    upsert_job_embedding,
    upsert_resume_embedding,
)
from .prompts import (
    EXTRACT_JOB_SYSTEM,
    EXTRACT_RESUME_SYSTEM,
    EXPLAIN_MATCH_SYSTEM,
    JUDGE_MATCH_SYSTEM,
)
from .schemas import (
    CandidateProfile,
    JobRequirements,
    RequirementVerdict,
    VerdictList,
)
from .state import GraphState


# ---------- LLM ----------
# Initialized once at import time. Every LLM node reuses this object.
LLM = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0,
    api_key=settings.google_api_key,
)


# ---------- Retry wrapper for 429 quota errors ----------
def _retry_on_429(max_attempts: int = 4):
    """Exponential backoff for Gemini free-tier quota (5 RPM) errors."""
    def deco(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            delay = 15
            for attempt in range(max_attempts):
                try:
                    return await fn(*args, **kwargs)
                except Exception as e:
                    msg = str(e)
                    is_429 = (
                        "429" in msg
                        or "ResourceExhausted" in msg
                        or "quota" in msg.lower()
                    )
                    if is_429 and attempt < max_attempts - 1:
                        print(
                            f"DEBUG 429 on {fn.__name__}, waiting {delay}s "
                            f"(attempt {attempt + 1}/{max_attempts})",
                            file=sys.stderr,
                        )
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, 60)
                    else:
                        raise
        return wrapper
    return deco


def _usage(raw) -> dict:
    u = getattr(raw, "usage_metadata", None) or {}
    return {
        "input": u.get("input_tokens", 0),
        "output": u.get("output_tokens", 0),
    }


# ---------- 1. extract_resume ----------
async def extract_resume(state: GraphState) -> dict:
    text_input = state.get("raw_resume_text") or ""
    if not text_input:
        return {}

    # Cache check: if we already extracted this resume, reuse it — no LLM call.
    rid = state.get("resume_id")
    if rid:
        db = SessionLocal()
        try:
            row = db.get(Resume, rid)
            if row and row.structured_profile:
                cached = CandidateProfile(**row.structured_profile)
                print(
                    f"DEBUG extract_resume -> CACHED {cached.full_name}",
                    file=sys.stderr,
                )
                return {"candidate_profile": cached}
        finally:
            db.close()

    chain = ChatPromptTemplate.from_messages([
        ("system", EXTRACT_RESUME_SYSTEM),
        ("human", "Resume text:\n\n{resume}"),
    ]) | LLM.with_structured_output(CandidateProfile, include_raw=True)

    out = await chain.ainvoke({"resume": text_input})
    profile = out["parsed"]

    # Persist for future cache hits
    if rid and profile:
        db = SessionLocal()
        try:
            row = db.get(Resume, rid)
            if row:
                row.structured_profile = profile.model_dump()
                db.commit()
        finally:
            db.close()

    print(f"DEBUG extract_resume -> FRESH {profile.full_name}", file=sys.stderr)

    return {
        "candidate_profile": profile,
        "token_usage": [{"node": "extract_resume", **_usage(out["raw"])}],
    }


# ---------- 2. extract_job ----------
async def extract_job(state: GraphState) -> dict:
    text_input = state.get("raw_job_text") or ""
    if not text_input:
        return {}

    # Cache check: if we already extracted this job, reuse it — no LLM call.
    jid = state.get("job_id")
    if jid:
        db = SessionLocal()
        try:
            row = db.get(Job, jid)
            if row and row.structured_requirements:
                cached = JobRequirements(**row.structured_requirements)
                print(
                    f"DEBUG extract_job -> CACHED {cached.title}",
                    file=sys.stderr,
                )
                return {"job_requirements": cached}
        finally:
            db.close()

    chain = ChatPromptTemplate.from_messages([
        ("system", EXTRACT_JOB_SYSTEM),
        ("human", "Job description:\n\n{job}"),
    ]) | LLM.with_structured_output(JobRequirements, include_raw=True)

    out = await chain.ainvoke({"job": text_input})
    reqs = out["parsed"]

    if jid and reqs:
        db = SessionLocal()
        try:
            row = db.get(Job, jid)
            if row:
                row.structured_requirements = reqs.model_dump()
                db.commit()
        finally:
            db.close()

    print(f"DEBUG extract_job -> FRESH {reqs.title}", file=sys.stderr)

    return {
        "job_requirements": reqs,
        "token_usage": [{"node": "extract_job", **_usage(out["raw"])}],
    }


# ---------- 3. embed_and_index ----------
async def embed_and_index(state: GraphState) -> dict:
    """
    Compute and persist embeddings for the resume and/or job.
    Resumes also get chunk-level embeddings for evidence retrieval.
    """
    rid = state.get("resume_id")
    jid = state.get("job_id")

    if rid and state.get("raw_resume_text"):
        await upsert_resume_embedding(rid, state["raw_resume_text"])
    if jid and state.get("raw_job_text"):
        await upsert_job_embedding(jid, state["raw_job_text"])

    return {
        "token_usage": [{"node": "embed_and_index", "input": 0, "output": 0}],
    }


# ---------- 4. retrieve_candidates ----------
async def retrieve_candidates(state: GraphState) -> dict:
    """
    Semantic search over resume embeddings, filtered by min experience.
    Uses the job description as the query.
    """
    reqs = state["job_requirements"]
    job_text = state.get("raw_job_text") or ""

    # Hard pre-filter: candidates must have at least (min_years - 1) experience.
    # The -1 gives a grace window so near-misses aren't silently dropped.
    min_years = max(reqs.min_years_experience - 1.0, 0.0)

    hits = await search_resumes(
        query_text=job_text,
        top_k=10,
        min_years=min_years if min_years > 0 else None,
    )

    # Pair mode: if we were given a specific resume_id, keep only that one.
    # Batch mode: return all semantic hits.
    target_rid = state.get("resume_id")
    if target_rid:
        filtered = [h for h in hits if h["id"] == target_rid]
        if filtered:
            hits = filtered
        else:
            # The target resume wasn't in the semantic top-k. Fall back to
            # using it directly so pair mode always produces output.
            hits = [{
                "id": target_rid,
                "text": state.get("raw_resume_text", ""),
                "score": 1.0,
            }]

    return {
        "candidate_ids": [h["id"] for h in hits],
        "resume_texts": {h["id"]: h["text"] for h in hits},
    }


# ---------- 5. retrieve_evidence ----------
async def retrieve_evidence(state: GraphState) -> dict:
    """
    For each (resume, requirement) pair, retrieve the most relevant
    resume chunks as evidence.
    """
    reqs = state["job_requirements"]
    evidence: dict[str, list[dict]] = {}

    for rid in state.get("candidate_ids", []):
        snippets: list[dict] = []
        for skill in reqs.must_have_skills + reqs.nice_to_have_skills:
            try:
                chunks = await search_chunks(rid, skill, top_k=2)
            except Exception as e:
                print(
                    f"DEBUG retrieve_evidence failed for {rid}/{skill}: {e}",
                    file=sys.stderr,
                )
                chunks = []
            for c in chunks:
                snippets.append({
                    "requirement": skill,
                    "snippet": c["text"],
                    "score": c["score"],
                })
        evidence[rid] = snippets

    return {"evidence": evidence}


# ---------- 6. judge_match ----------
@_retry_on_429()
async def judge_match(state: GraphState) -> dict:
    reqs = state["job_requirements"]
    rid = state.get("resume_id") or next(iter(state["evidence"]))
    snippets = state["evidence"].get(rid, [])

    req_list = [*reqs.must_have_skills, *reqs.nice_to_have_skills]
    if not req_list:
        print("DEBUG judge_match -> no requirements to judge", file=sys.stderr)
        return {"verdicts": []}

    evidence_block = "\n".join(
        f"- [{s['requirement']}] {s['snippet']}" for s in snippets
    ) or "(no evidence found)"

    chain = ChatPromptTemplate.from_messages([
        ("system", JUDGE_MATCH_SYSTEM),
        ("human",
         "Requirements (evaluate each, in order):\n{reqs}\n\n"
         "Evidence snippets from the resume:\n{ev}\n\n"
         "Return one verdict per requirement."),
    ]) | LLM.with_structured_output(VerdictList, include_raw=True)

    out = await chain.ainvoke({
        "reqs": "\n".join(f"- {r}" for r in req_list),
        "ev": evidence_block,
    })

    # DEBUG — remove after confirming verdicts are being produced
    print(f"DEBUG judge_match -> {out['parsed']!r}", file=sys.stderr)

    verdicts: list[RequirementVerdict] = out["parsed"].verdicts

    # Apply weights in code — the LLM doesn't decide policy.
    for v in verdicts:
        v.weight = 1.0 if v.requirement in reqs.must_have_skills else 0.4

    return {
        "verdicts": verdicts,
        "token_usage": [{"node": "judge_match", **_usage(out["raw"])}],
    }


# ---------- 7. aggregate_score (DETERMINISTIC — no LLM ever) ----------
async def aggregate_score(state: GraphState) -> dict:
    verdicts = state.get("verdicts") or []
    if not verdicts:
        return {"score": 0.0}

    value = {"met": 1.0, "partial": 0.5, "missing": 0.0}
    num = sum(v.weight * value[v.status] for v in verdicts)
    den = sum(v.weight for v in verdicts) or 1.0
    return {"score": round(100.0 * num / den, 1)}


# ---------- 8. generate_explanation ----------
@_retry_on_429()
async def generate_explanation(state: GraphState) -> dict:
    verdicts = state.get("verdicts") or []
    met = [v.requirement for v in verdicts if v.status == "met"]
    partial = [v.requirement for v in verdicts if v.status == "partial"]
    missing = [v.requirement for v in verdicts if v.status == "missing"]

    chain = ChatPromptTemplate.from_messages([
        ("system", EXPLAIN_MATCH_SYSTEM),
        ("human",
         "Score: {score}\n"
         "Matched: {met}\n"
         "Partial: {partial}\n"
         "Missing: {missing}"),
    ]) | LLM

    msg = await chain.ainvoke({
        "score": state.get("score", 0.0),
        "met": ", ".join(met) or "none",
        "partial": ", ".join(partial) or "none",
        "missing": ", ".join(missing) or "none",
    })

    return {
        "explanation": msg.content,
        "token_usage": [{"node": "generate_explanation", **_usage(msg)}],
    }


# ---------- 9. clarify_or_retry ----------
async def clarify_or_retry(state: GraphState) -> dict:
    return {
        "retry_count": state.get("retry_count", 0) + 1,
        "errors": ["low extraction confidence — retrying"],
    }


# ---------- 10. no_match_fallback ----------
async def no_match_fallback(state: GraphState) -> dict:
    return {
        "score": 0.0,
        "verdicts": [],
        "explanation": "No sufficiently relevant match found.",
    }