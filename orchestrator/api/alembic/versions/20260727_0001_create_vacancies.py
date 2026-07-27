"""create vacancies table

Revision ID: 20260727_0001
Revises:
Create Date: 2026-07-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260727_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vacancies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("salary_text", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "external_id", name="uq_vacancies_source_external_id"),
    )
    op.create_index("ix_vacancies_source", "vacancies", ["source"], unique=False)
    op.create_index("ix_vacancies_external_id", "vacancies", ["external_id"], unique=False)
    op.create_index("ix_vacancies_created_at", "vacancies", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_vacancies_created_at", table_name="vacancies")
    op.drop_index("ix_vacancies_external_id", table_name="vacancies")
    op.drop_index("ix_vacancies_source", table_name="vacancies")
    op.drop_table("vacancies")
