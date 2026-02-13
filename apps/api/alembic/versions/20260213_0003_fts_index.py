"""fts index for hybrid retrieval

Revision ID: 20260213_0003
Revises: 20260213_0002
Create Date: 2026-02-13
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260213_0003"
down_revision = "20260213_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS document_chunks_fts_idx
        ON document_chunks
        USING gin (to_tsvector('simple', chunk_text))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS document_chunks_fts_idx")
