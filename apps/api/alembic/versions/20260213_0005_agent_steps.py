"""agent steps trace table

Revision ID: 20260213_0005
Revises: 20260213_0004
Create Date: 2026-02-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260213_0005"
down_revision = "20260213_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_steps",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("trace_id", sa.String(length=36), nullable=False),
        sa.Column("parent_step_id", sa.String(length=36), nullable=True),
        sa.Column("agent_name", sa.String(length=64), nullable=False),
        sa.Column("step_type", sa.String(length=32), nullable=False),
        sa.Column("parent_hash", sa.String(length=64), nullable=True),
        sa.Column("step_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_agent_steps_trace_id", "agent_steps", ["trace_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_agent_steps_trace_id", table_name="agent_steps")
    op.drop_table("agent_steps")
