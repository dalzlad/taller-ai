"""add stored preliminary AI analysis to diagnostics

Revision ID: 20260908_0002
Revises: 20260908_0001
Create Date: 2026-09-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0002"
down_revision: Union[str, None] = "20260908_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("diagnostics", sa.Column("ai_analysis", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("diagnostics", "ai_analysis")
