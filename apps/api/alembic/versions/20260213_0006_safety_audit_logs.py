"""add safety audit logs

Revision ID: 20260213_0006
Revises: 20260213_0005
Create Date: 2026-02-13 12:10:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260213_0006"
down_revision = "20260213_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "safety_audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("trace_id", sa.String(length=36), nullable=False),
        sa.Column("policy_version", sa.String(length=50), nullable=False),
        sa.Column("original_action", sa.String(length=16), nullable=False),
        sa.Column("effective_action", sa.String(length=16), nullable=False),
        sa.Column("overridden", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("safety_level", sa.String(length=16), nullable=False),
        sa.Column("rules_triggered", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_safety_audit_logs_trace_id", "safety_audit_logs", ["trace_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_safety_audit_logs_trace_id", table_name="safety_audit_logs")
    op.drop_table("safety_audit_logs")
