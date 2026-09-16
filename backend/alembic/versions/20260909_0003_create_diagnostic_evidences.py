"""create diagnostic evidences

Revision ID: 20260909_0003
Revises: 20260908_0002
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260909_0003"
down_revision: str | None = "20260908_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

diagnostic_evidence_type = postgresql.ENUM(
    "IMAGE", "AUDIO", "VIDEO", name="diagnostic_evidence_type", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    diagnostic_evidence_type.create(bind, checkfirst=True)
    op.create_table(
        "diagnostic_evidences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("diagnostic_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", diagnostic_evidence_type, nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["diagnostic_id"], ["diagnostics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_diagnostic_evidences_diagnostic_id", "diagnostic_evidences", ["diagnostic_id"])


def downgrade() -> None:
    op.drop_index("ix_diagnostic_evidences_diagnostic_id", table_name="diagnostic_evidences")
    op.drop_table("diagnostic_evidences")
    diagnostic_evidence_type.drop(op.get_bind(), checkfirst=True)
