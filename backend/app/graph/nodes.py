"""
LangGraph node functions.

STEP 6: All LLM/vector-store calls are stubbed with deterministic fake data.
STEP 7 will replace the bodies with real LangChain calls — the signatures
and return shapes stay identical, so build.py never changes.
"""
import hashlib
from .schemas import CandidateProfile, JobRequirements, RequirementVerdict
from .state import GraphState


# ---------- helpers ----------
def _stable_confidence(text: str) -> float:
    """Deterministic pseudo-random confidence from text — for stubs only."""
    h = int(hashlib.sha1(text.encode()).hexdigest()[:8], 16)
    return 0.7 + (h % 30) / 100.0   # range 0.70 – 0.99


# ---------- 1. extract_resume ----------
async def extract_resume(state: GraphState) -> dict:
    text = state.get("raw_resume_text") or ""
    # STUB: pull skills from a tiny keyword list so the demo has content.
    KNOWN_SKILLS = ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS",
                    "Kubernetes", "Redis", "Celery", "LangChain", "LangGraph"]
    skills = [s for s in KNOWN_SKILLS if s.lower() in text.lower()]

    profile = CandidateProfile(
        full_name="Stub Candidate",
        skills=skills,
        years_experience=6.0,
        roles=["Senior Backend Engineer"],
        education=["B.S. Computer Science"],
        summary="Stub extraction — real LLM will replace this in Step 7.",
        extraction_confidence=_stable_confidence(text),
    )
    return {
        "candidate_profile": profile,
        "token_usage": [{"node": "extract_resume", "input": 0, "output": 0}],
    }


# ---------- 2. extract_job ----------
async def extract_job(state: GraphState) -> dict:
    text = state.get("raw_job_text") or ""
    KNOWN_SKILLS = ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS",
                    "Kubernetes", "Redis", "Celery", "LangChain", "LangGraph"]
    found = [s for s in KNOWN_SKILLS if s.lower() in text.lower()]

    reqs = JobRequirements(
        title="Stub Job",
        must_have_skills=found[:4] if found else ["Python"],
        nice_to_have_skills=found[4:],
        min_years_experience=5.0,
        responsibilities=["Stub responsibility"],
        extraction_confidence=_stable_confidence(text),
    )
    return {
        "job_requirements": reqs,
        "token_usage": [{"node": "extract_job", "input": 0, "output": 0}],
    }


# ---------- 3. embed_and_index ----------
async def embed_and_index(state: GraphState) -> dict:
    # STUB: no vector store yet. Just record that we ran.
    return {
        "token_usage": [{"node": "embed_and_index", "input": 0, "output": 0}],
    }


# ---------- 4. retrieve_candidates ----------
async def retrieve_candidates(state: GraphState) -> dict:
    # STUB: pretend we found the current resume as the only candidate.
    rid = state.get("resume_id")
    if rid:
        return {
            "candidate_ids": [rid],
            "resume_texts": {rid: state.get("raw_resume_text", "")},
        }
    return {"candidate_ids": [], "resume_texts": {}}


# ---------- 5. retrieve_evidence ----------
async def retrieve_evidence(state: GraphState) -> dict:
    # STUB: fabricate one evidence snippet per must-have skill.
    reqs = state["job_requirements"]
    resume_text = state.get("raw_resume_text") or ""
    rid = state.get("resume_id") or "unknown"

    snippets = []
    for skill in reqs.must_have_skills + reqs.nice_to_have_skills:
        # naive: use the skill name as its own "evidence" for the stub
        snippets.append({
            "requirement": skill,
            "snippet": f"Experience with {skill}." if skill.lower() in resume_text.lower()
                       else "(no matching evidence in stub)",
            "score": 0.9 if skill.lower() in resume_text.lower() else 0.2,
        })
    return {"evidence": {rid: snippets}}


# ---------- 6. judge_match ----------
async def judge_match(state: GraphState) -> dict:
    # STUB: verdict = "met" if evidence score > 0.5, else "missing".
    reqs = state["job_requirements"]
    rid = state.get("resume_id") or next(iter(state["evidence"]))
    snippets = {s["requirement"]: s for s in state["evidence"].get(rid, [])}

    verdicts: list[RequirementVerdict] = []
    for skill in reqs.must_have_skills + reqs.nice_to_have_skills:
        s = snippets.get(skill, {"score": 0.0, "snippet": ""})
        status = "met" if s["score"] > 0.5 else "missing"
        verdicts.append(RequirementVerdict(
            requirement=skill,
            status=status,
            confidence=0.9,
            evidence=s["snippet"],
            weight=1.0 if skill in reqs.must_have_skills else 0.4,
        ))
    return {
        "verdicts": verdicts,
        "token_usage": [{"node": "judge_match", "input": 0, "output": 0}],
    }


# ---------- 7. aggregate_score (DETERMINISTIC — no LLM in Step 7 either) ----------
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
    score = state.get("score", 0.0)
    met = [v.requirement for v in verdicts if v.status == "met"]
    missing = [v.requirement for v in verdicts if v.status == "missing"]
    explanation = (
        f"[STUB] Score {score}. "
        f"Matched: {', '.join(met) or 'none'}. "
        f"Missing: {', '.join(missing) or 'none'}."
    )
    return {
        "explanation": explanation,
        "token_usage": [{"node": "generate_explanation", "input": 0, "output": 0}],
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
        "explanation": "[STUB] No sufficiently relevant match found.",
    }