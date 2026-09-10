"""create vacancy user state reconciliation conflicts

Revision ID: 20260910_0002
Revises: 20260910_0001
Create Date: 2026-09-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260910_0002"
down_revision: str | None = "20260910_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vacancy_user_state_reconciliation_conflicts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conflict_key", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("old_presentation_keys", sa.JSON(), nullable=False),
        sa.Column("new_presentation_keys", sa.JSON(), nullable=False),
        sa.Column("canonical_vacancy_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('merge', 'split')", name="ck_vacancy_user_state_reconciliation_conflicts_kind"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conflict_key", name="uq_vacancy_user_state_reconciliation_conflicts_key"),
    )
    op.create_index("ix_vacancy_user_state_reconciliation_conflicts_kind", "vacancy_user_state_reconciliation_conflicts", ["kind"])
    op.create_index("ix_vacancy_user_state_reconciliation_conflicts_created_at", "vacancy_user_state_reconciliation_conflicts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_vacancy_user_state_reconciliation_conflicts_created_at", table_name="vacancy_user_state_reconciliation_conflicts")
    op.drop_index("ix_vacancy_user_state_reconciliation_conflicts_kind", table_name="vacancy_user_state_reconciliation_conflicts")
    op.drop_table("vacancy_user_state_reconciliation_conflicts")
