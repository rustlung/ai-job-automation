"""create vacancy user states

Revision ID: 20260910_0001
Revises: 20260909_0002
Create Date: 2026-09-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260910_0001"
down_revision: str | None = "20260909_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vacancy_user_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("presentation_key", sa.String(length=320), nullable=False),
        sa.Column("user_priority", sa.String(length=2), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("vacancy_status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("user_priority IN ('P1', 'P2', 'P3') OR user_priority IS NULL", name="ck_vacancy_user_states_priority"),
        sa.CheckConstraint("vacancy_status IN ('active', 'archived', 'closed')", name="ck_vacancy_user_states_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("presentation_key", name="uq_vacancy_user_states_presentation_key"),
    )
    op.create_index("ix_vacancy_user_states_presentation_key", "vacancy_user_states", ["presentation_key"])
    op.create_index("ix_vacancy_user_states_vacancy_status", "vacancy_user_states", ["vacancy_status"])
    op.create_index("ix_vacancy_user_states_user_priority", "vacancy_user_states", ["user_priority"])


def downgrade() -> None:
    op.drop_index("ix_vacancy_user_states_user_priority", table_name="vacancy_user_states")
    op.drop_index("ix_vacancy_user_states_vacancy_status", table_name="vacancy_user_states")
    op.drop_index("ix_vacancy_user_states_presentation_key", table_name="vacancy_user_states")
    op.drop_table("vacancy_user_states")
