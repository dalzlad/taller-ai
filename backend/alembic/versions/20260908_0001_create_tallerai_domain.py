"""create TallerAI domain tables

Revision ID: 20260908_0001
Revises:
Create Date: 2026-09-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260908_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

diagnostic_status = postgresql.ENUM(
    "CREATED", "ANALYZING", "REVIEW", "COMPLETED", name="diagnostic_status", create_type=False
)
media_type = postgresql.ENUM("PHOTO", "VIDEO", "AUDIO", name="media_type", create_type=False)
work_order_status = postgresql.ENUM(
    "DRAFT", "APPROVED", "IN_PROGRESS", "COMPLETED", "CANCELLED", name="work_order_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    diagnostic_status.create(bind, checkfirst=True)
    media_type.create(bind, checkfirst=True)
    work_order_status.create(bind, checkfirst=True)

    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_customers_email", "customers", ["email"])
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("plate", sa.String(length=15), nullable=False),
        sa.Column("vin", sa.String(length=17), nullable=True),
        sa.Column("brand", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("engine", sa.String(length=100), nullable=True),
        sa.Column("mileage", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("year >= 1886", name="ck_vehicles_year"),
        sa.CheckConstraint("mileage >= 0", name="ck_vehicles_mileage"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plate"),
        sa.UniqueConstraint("vin"),
    )
    op.create_index("ix_vehicles_customer_id", "vehicles", ["customer_id"])
    op.create_index("ix_vehicles_plate", "vehicles", ["plate"])
    op.create_index("ix_vehicles_vin", "vehicles", ["vin"])
    op.create_table(
        "diagnostics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), nullable=False),
        sa.Column("reported_symptoms", sa.Text(), nullable=False),
        sa.Column("mechanic_notes", sa.Text(), nullable=True),
        sa.Column("status", diagnostic_status, nullable=False, server_default="CREATED"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_diagnostics_vehicle_id", "diagnostics", ["vehicle_id"])
    op.create_table(
        "diagnostic_media",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("diagnostic_id", sa.Integer(), nullable=False),
        sa.Column("type", media_type, nullable=False),
        sa.Column("file_url", sa.String(length=2048), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["diagnostic_id"], ["diagnostics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_diagnostic_media_diagnostic_id", "diagnostic_media", ["diagnostic_id"])
    op.create_table(
        "diagnostic_findings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("diagnostic_id", sa.Integer(), nullable=False),
        sa.Column("component", sa.String(length=120), nullable=False),
        sa.Column("finding", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=30), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 100)", name="ck_findings_confidence"),
        sa.ForeignKeyConstraint(["diagnostic_id"], ["diagnostics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_diagnostic_findings_diagnostic_id", "diagnostic_findings", ["diagnostic_id"])
    op.create_table(
        "work_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("diagnostic_id", sa.Integer(), nullable=False),
        sa.Column("status", work_order_status, nullable=False, server_default="DRAFT"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("estimated_cost", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("final_cost", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.CheckConstraint("estimated_cost IS NULL OR estimated_cost >= 0", name="ck_work_orders_estimated_cost"),
        sa.CheckConstraint("final_cost IS NULL OR final_cost >= 0", name="ck_work_orders_final_cost"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["diagnostic_id"], ["diagnostics.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_work_orders_diagnostic_id", "work_orders", ["diagnostic_id"])


def downgrade() -> None:
    op.drop_index("ix_work_orders_diagnostic_id", table_name="work_orders")
    op.drop_table("work_orders")
    op.drop_index("ix_diagnostic_findings_diagnostic_id", table_name="diagnostic_findings")
    op.drop_table("diagnostic_findings")
    op.drop_index("ix_diagnostic_media_diagnostic_id", table_name="diagnostic_media")
    op.drop_table("diagnostic_media")
    op.drop_index("ix_diagnostics_vehicle_id", table_name="diagnostics")
    op.drop_table("diagnostics")
    op.drop_index("ix_vehicles_vin", table_name="vehicles")
    op.drop_index("ix_vehicles_plate", table_name="vehicles")
    op.drop_index("ix_vehicles_customer_id", table_name="vehicles")
    op.drop_table("vehicles")
    op.drop_index("ix_customers_email", table_name="customers")
    op.drop_table("customers")
    bind = op.get_bind()
    work_order_status.drop(bind, checkfirst=True)
    media_type.drop(bind, checkfirst=True)
    diagnostic_status.drop(bind, checkfirst=True)
