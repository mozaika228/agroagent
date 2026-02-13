"""pgvector retrieval

Revision ID: 20260213_0002
Revises: 20260213_0001
Create Date: 2026-02-13
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260213_0002"
down_revision = "20260213_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        ALTER TABLE document_chunks
        ALTER COLUMN embedding TYPE vector(768)
        USING CASE
          WHEN embedding IS NULL THEN NULL
          ELSE embedding::text::vector
        END
        """
    )
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding SET NOT NULL")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS document_chunks_embedding_cos_idx
        ON document_chunks USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        """
    )
    op.execute("ANALYZE document_chunks")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS document_chunks_embedding_cos_idx")
    op.execute(
        """
        ALTER TABLE document_chunks
        ALTER COLUMN embedding TYPE jsonb
        USING embedding::text::jsonb
        """
    )
