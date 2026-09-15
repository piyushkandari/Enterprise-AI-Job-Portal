"""add job_interests

Revision ID: bd17c030762a
Revises: 4a020cca5fe6
Create Date: 2026-09-15 17:08:09.601556

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bd17c030762a'
down_revision: Union[str, None] = '4a020cca5fe6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS job_interests (
            id VARCHAR(36) PRIMARY KEY,
            candidate_id VARCHAR(36) NOT NULL
                REFERENCES users(id) ON DELETE CASCADE,
            job_id VARCHAR(36) NOT NULL
                REFERENCES jobs(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (candidate_id, job_id)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_job_interests_candidate "
        "ON job_interests(candidate_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_job_interests_job "
        "ON job_interests(job_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_job_interests_job")
    op.execute("DROP INDEX IF EXISTS ix_job_interests_candidate")
    op.execute("DROP TABLE IF EXISTS job_interests")