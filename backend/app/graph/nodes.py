"""
LangGraph node functions.

Step 7: extract_resume, extract_job, judge_match, generate_explanation
use Gemini via langchain-google-genai with structured output.
embed_and_index / retrieve_candidates / retrieve_evidence stay stubbed
until Step 7 Part B.
"""
import hashlib
import sys

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from ..config import settings
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
    model="gemini-3.6-flash",
    temperature=0,
    api_key=settings.google_api_key,   # if TypeError, change to: google_api_key=
)


def _usage(raw) -> dict:
    u = getattr(raw, "usage_metadata", None) or {}
    return {
        "input": u.get("input_tokens", 0),
        "output": u.get("output_tokens", 0),
    }


def _stable_confidence(text: str) -> float:
    h = int(hashlib.sha1(text.encode()).hexdigest()[:8], 16)
    return 0.7 + (h % 30) / 100.0


# ---------- 1. extract_resume ----------
async def extract_resume(state: GraphState) -> dict:
    text = state.get("raw_resume_text") or ""
    if not text:
        return {}

    chain = ChatPromptTemplate.from_messages([
        ("system", EXTRACT_RESUME_SYSTEM),
        ("human", "Resume text:\n\n{resume}"),
    ]) | LLM.with_structured_output(CandidateProfile, include_raw=True)

    out = await chain.ainvoke({"resume": text})

    # DEBUG — remove after confirming extraction is clean
    print(f"DEBUG extract_resume -> {out['parsed']!r}", file=sys.stderr)

    return {
        "candidate_profile": out["parsed"],
        "token_usage": [{"node": "extract_resume", **_usage(out["raw"])}],
    }


# ---------- 2. extract_job ----------
async def extract_job(state: GraphState) -> dict:
    text = state.get("raw_job_text") or ""
    if not text:
        return {}

    chain = ChatPromptTemplate.from_messages([
        ("system", EXTRACT_JOB_SYSTEM),
        ("human", "Job description:\n\n{job}"),
    ]) | LLM.with_structured_output(JobRequirements, include_raw=True)

    out = await chain.ainvoke({"job": text})

    # DEBUG — remove after confirming extraction is clean
    print(f"DEBUG extract_job -> {out['parsed']!r}", file=sys.stderr)

    return {
        "job_requirements": out["parsed"],
        "token_usage": [{"node": "extract_job", **_usage(out["raw"])}],
    }


# ---------- 3. embed_and_index ----------
async def embed_and_index(state: GraphState) -> dict:
    # STUB — Part B replaces with real embeddings + vector store
    return {
        "token_usage": [{"node": "embed_and_index", "input": 0, "output": 0}],
    }


# ---------- 4. retrieve_candidates ----------
async def retrieve_candidates(state: GraphState) -> dict:
    # STUB — Part B replaces with semantic search
    rid = state.get("resume_id")
    if rid:
        return {
            "candidate_ids": [rid],
            "resume_texts": {rid: state.get("raw_resume_text", "")},
        }
    return {"candidate_ids": [], "resume_texts": {}}


# ---------- 5. retrieve_evidence ----------
async def retrieve_evidence(state: GraphState) -> dict:
    # STUB — Part B replaces with per-requirement snippet retrieval
    reqs = state["job_requirements"]
    resume_text = state.get("raw_resume_text") or ""
    rid = state.get("resume_id") or "unknown"

    snippets = []
    for skill in reqs.must_have_skills + reqs.nice_to_have_skills:
        present = skill.lower() in resume_text.lower()
        snippets.append({
            "requirement": skill,
            "snippet": f"Experience with {skill}." if present
                       else "(no matching evidence in stub)",
            "score": 0.9 if present else 0.2,
        })
    return {"evidence": {rid: snippets}}


# ---------- 6. judge_match ----------
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