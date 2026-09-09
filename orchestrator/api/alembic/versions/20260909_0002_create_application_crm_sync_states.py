"""create application CRM sync states

Revision ID: 20260909_0002
Revises: 20260909_0001
Create Date: 2026-09-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260909_0002"
down_revision: str | None = "20260909_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "application_crm_sync_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message_safe", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'synced', 'failed')", name="ck_application_crm_sync_states_status"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", name="uq_application_crm_sync_states_application_id"),
    )
    op.create_index("ix_application_crm_sync_states_application_id", "application_crm_sync_states", ["application_id"])
    op.create_index("ix_application_crm_sync_states_status", "application_crm_sync_states", ["status"])


def downgrade() -> None:
    op.drop_index("ix_application_crm_sync_states_status", table_name="application_crm_sync_states")
    op.drop_index("ix_application_crm_sync_states_application_id", table_name="application_crm_sync_states")
    op.drop_table("application_crm_sync_states")
