"""
Embedding service: wraps Gemini embeddings and text chunking.

Model: gemini-embedding-2. Uses Matryoshka truncation to 768 dims —
Google's recommended balance of quality vs. storage. The langchain wrapper
at version 2.0.10 doesn't pass `output_dimensionality` through, so we
truncate + renormalize ourselves.
"""
import math

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from ..config import settings

EMBEDDING_MODEL = "models/gemini-embedding-2"
EMBEDDING_DIMS = 768

_embedder: GoogleGenerativeAIEmbeddings | None = None


def get_embedder() -> GoogleGenerativeAIEmbeddings:
    global _embedder
    if _embedder is None:
        _embedder = GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL,
            google_api_key=settings.google_api_key,
        )
    return _embedder


def _truncate_and_normalize(vec: list[float]) -> list[float]:
    """Matryoshka truncation: keep the first EMBEDDING_DIMS dims, then
    L2-normalize so cosine similarity is well-behaved."""
    truncated = vec[:EMBEDDING_DIMS]
    norm = math.sqrt(sum(x * x for x in truncated))
    if norm == 0:
        return truncated
    return [x / norm for x in truncated]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch-embed documents and truncate to EMBEDDING_DIMS."""
    if not texts:
        return []
    raw = await get_embedder().aembed_documents(texts)
    return [_truncate_and_normalize(v) for v in raw]


async def embed_query(text: str) -> list[float]:
    """Embed a single query string and truncate to EMBEDDING_DIMS."""
    raw = await get_embedder().aembed_query(text)
    return _truncate_and_normalize(raw)


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    """Word-based chunker with overlap — sized for resume paragraphs."""
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    step = max(chunk_size - overlap, 1)
    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + chunk_size])
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(words):
            break
    return chunks