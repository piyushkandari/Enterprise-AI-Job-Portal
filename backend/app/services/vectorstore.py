"""
pgvector wrapper: upsert resume/job embeddings, semantic search,
and per-requirement snippet retrieval.
"""
import uuid

from sqlalchemy import text

from ..db import SessionLocal
from .embeddings import chunk_text, embed_query, embed_texts


def _to_pgvector(vec: list[float]) -> str:
    """Format a Python list as pgvector's expected string: '[1.0,2.0,...]'."""
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"


async def upsert_resume_embedding(resume_id: str, raw_text: str) -> None:
    """
    Store:
    1. Resume-level embedding (for candidate retrieval)
    2. Chunk-level embeddings (for evidence retrieval)
    """
    db = SessionLocal()
    try:
        vec = (await embed_texts([raw_text[:8000]]))[0]
        db.execute(
            text("UPDATE resumes SET embedding = CAST(:v AS vector) WHERE id = :id"),
            {"v": _to_pgvector(vec), "id": resume_id},
        )

        # Chunk-level: wipe and reinsert
        db.execute(text("DELETE FROM resume_chunks WHERE resume_id = :id"),
                   {"id": resume_id})
        chunks = chunk_text(raw_text)
        if chunks:
            chunk_vecs = await embed_texts(chunks)
            for idx, (chunk, cvec) in enumerate(zip(chunks, chunk_vecs)):
                db.execute(
                    text("""
                        INSERT INTO resume_chunks
                            (id, resume_id, chunk_index, chunk_text, embedding)
                        VALUES (:id, :rid, :idx, :txt, CAST(:v AS vector))
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "rid": resume_id,
                        "idx": idx,
                        "txt": chunk,
                        "v": _to_pgvector(cvec),
                    },
                )
        db.commit()
    finally:
        db.close()


async def upsert_job_embedding(job_id: str, raw_text: str) -> None:
    db = SessionLocal()
    try:
        vec = (await embed_texts([raw_text[:8000]]))[0]
        db.execute(
            text("UPDATE jobs SET embedding = CAST(:v AS vector) WHERE id = :id"),
            {"v": _to_pgvector(vec), "id": job_id},
        )
        db.commit()
    finally:
        db.close()


async def search_resumes(
    query_text: str,
    top_k: int = 10,
    min_years: float | None = None,
) -> list[dict]:
    qvec = await embed_query(query_text)
    db = SessionLocal()
    try:
        sql = """
            SELECT r.id, r.raw_text,
                   1 - (r.embedding <=> CAST(:v AS vector)) AS score
            FROM resumes r
            WHERE r.embedding IS NOT NULL
        """
        params: dict = {"v": _to_pgvector(qvec), "k": top_k}
        if min_years is not None:
            sql += " AND (r.structured_profile->>'years_experience')::float >= :miny"
            params["miny"] = min_years
        sql += " ORDER BY r.embedding <=> CAST(:v AS vector) LIMIT :k"

        rows = db.execute(text(sql), params).fetchall()
        return [{"id": r[0], "text": r[1], "score": float(r[2])} for r in rows]
    finally:
        db.close()


async def search_chunks(
    resume_id: str,
    requirement: str,
    top_k: int = 2,
) -> list[dict]:
    qvec = await embed_query(requirement)
    db = SessionLocal()
    try:
        rows = db.execute(
            text("""
                SELECT chunk_text,
                       1 - (embedding <=> CAST(:v AS vector)) AS score
                FROM resume_chunks
                WHERE resume_id = :rid AND embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:v AS vector)
                LIMIT :k
            """),
            {"v": _to_pgvector(qvec), "rid": resume_id, "k": top_k},
        ).fetchall()
        return [{"text": r[0], "score": float(r[1])} for r in rows]
    finally:
        db.close()