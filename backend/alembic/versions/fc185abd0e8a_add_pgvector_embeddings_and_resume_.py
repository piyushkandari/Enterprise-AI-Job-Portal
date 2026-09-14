"""add pgvector embeddings and resume_chunks

Revision ID: fc185abd0e8a
Revises: 6a398793dc4d
Create Date: 2026-09-14 23:52:37.149101

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'fc185abd0e8a'
down_revision: Union[str, None] = '6a398793dc4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Vector extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Resume-level embedding (nullable — populated by embed_and_index)
    op.execute("ALTER TABLE resumes ADD COLUMN IF NOT EXISTS embedding vector(768)")

    # Job-level embedding (nullable)
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS embedding vector(768)")

    # Chunk-level embeddings for evidence retrieval
    op.execute("""
        CREATE TABLE IF NOT EXISTS resume_chunks (
            id VARCHAR(36) PRIMARY KEY,
            resume_id VARCHAR(36) NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding vector(768) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_resume_chunks_resume_id "
        "ON resume_chunks(resume_id)"
    )

    # HNSW indexes for cosine similarity
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_resumes_embedding_hnsw
        ON resumes USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_jobs_embedding_hnsw
        ON jobs USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_resume_chunks_embedding_hnsw
        ON resume_chunks USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_resume_chunks_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_jobs_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_resumes_embedding_hnsw")
    op.execute("DROP TABLE IF EXISTS resume_chunks")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE resumes DROP COLUMN IF EXISTS embedding")