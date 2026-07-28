"""create vacancy analyses table

Revision ID: 20260728_0001
Revises: 20260727_0001
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260728_0001"
down_revision: str | None = "20260727_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vacancy_analyses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vacancy_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("relevance", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("relevance >= 0 AND relevance <= 10", name="ck_vacancy_analyses_relevance_range"),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], name="fk_vacancy_analyses_vacancy_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "vacancy_id",
            "provider",
            "model",
            "prompt_version",
            name="uq_vacancy_analyses_identity",
        ),
    )
    op.create_index("ix_vacancy_analyses_vacancy_id", "vacancy_analyses", ["vacancy_id"], unique=False)
    op.create_index("ix_vacancy_analyses_created_at", "vacancy_analyses", ["created_at"], unique=False)
    op.create_index("ix_vacancy_analyses_provider_model", "vacancy_analyses", ["provider", "model"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_vacancy_analyses_provider_model", table_name="vacancy_analyses")
    op.drop_index("ix_vacancy_analyses_created_at", table_name="vacancy_analyses")
    op.drop_index("ix_vacancy_analyses_vacancy_id", table_name="vacancy_analyses")
    op.drop_table("vacancy_analyses")
