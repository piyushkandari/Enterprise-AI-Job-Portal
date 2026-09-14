from langgraph.graph import StateGraph, START, END

from .state import GraphState
from . import nodes


def _route_after_extraction(state: GraphState) -> str:
    confs = []
    if state.get("candidate_profile"):
        confs.append(state["candidate_profile"].extraction_confidence)
    if state.get("job_requirements"):
        confs.append(state["job_requirements"].extraction_confidence)
    conf = min(confs) if confs else 1.0
    if conf < 0.6:
        return "clarify_or_retry" if state.get("retry_count", 0) < 2 else "no_match_fallback"
    return "embed_and_index"


def _route_after_retrieval(state: GraphState) -> str:
    return "retrieve_evidence" if state.get("candidate_ids") else "no_match_fallback"


def build_graph():
    g = StateGraph(GraphState)
    g.add_node("extract_resume", nodes.extract_resume)
    g.add_node("extract_job", nodes.extract_job)
    g.add_node("embed_and_index", nodes.embed_and_index)
    g.add_node("retrieve_candidates", nodes.retrieve_candidates)
    g.add_node("retrieve_evidence", nodes.retrieve_evidence)
    g.add_node("judge_match", nodes.judge_match)
    g.add_node("aggregate_score", nodes.aggregate_score)
    g.add_node("generate_explanation", nodes.generate_explanation)
    g.add_node("clarify_or_retry", nodes.clarify_or_retry)
    g.add_node("no_match_fallback", nodes.no_match_fallback)

    g.add_edge(START, "extract_resume")
    g.add_edge("extract_resume", "extract_job")
    g.add_conditional_edges(
        "extract_job",
        _route_after_extraction,
        {
            "clarify_or_retry": "clarify_or_retry",
            "embed_and_index": "embed_and_index",
            "no_match_fallback": "no_match_fallback",
        },
    )
    g.add_edge("clarify_or_retry", "extract_resume")
    g.add_edge("embed_and_index", "retrieve_candidates")
    g.add_conditional_edges(
        "retrieve_candidates",
        _route_after_retrieval,
        {
            "retrieve_evidence": "retrieve_evidence",
            "no_match_fallback": "no_match_fallback",
        },
    )
    g.add_edge("retrieve_evidence", "judge_match")
    g.add_edge("judge_match", "aggregate_score")
    g.add_edge("aggregate_score", "generate_explanation")
    g.add_edge("generate_explanation", END)
    g.add_edge("no_match_fallback", END)
    return g.compile()


graph = build_graph()