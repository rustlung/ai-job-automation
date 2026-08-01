"""create vacancy processing events table

Revision ID: 20260801_0001
Revises: 20260728_0001
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260801_0001"
down_revision: str | None = "20260728_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vacancy_processing_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vacancy_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["vacancy_id"],
            ["vacancies.id"],
            name="fk_vacancy_processing_events_vacancy_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vacancy_processing_events_vacancy_id", "vacancy_processing_events", ["vacancy_id"], unique=False)
    op.create_index("ix_vacancy_processing_events_run_id", "vacancy_processing_events", ["run_id"], unique=False)
    op.create_index("ix_vacancy_processing_events_stage", "vacancy_processing_events", ["stage"], unique=False)
    op.create_index("ix_vacancy_processing_events_status", "vacancy_processing_events", ["status"], unique=False)
    op.create_index("ix_vacancy_processing_events_created_at", "vacancy_processing_events", ["created_at"], unique=False)
    op.create_index(
        "ix_vacancy_processing_events_vacancy_id_created_at",
        "vacancy_processing_events",
        ["vacancy_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_vacancy_processing_events_vacancy_id_created_at", table_name="vacancy_processing_events")
    op.drop_index("ix_vacancy_processing_events_created_at", table_name="vacancy_processing_events")
    op.drop_index("ix_vacancy_processing_events_status", table_name="vacancy_processing_events")
    op.drop_index("ix_vacancy_processing_events_stage", table_name="vacancy_processing_events")
    op.drop_index("ix_vacancy_processing_events_run_id", table_name="vacancy_processing_events")
    op.drop_index("ix_vacancy_processing_events_vacancy_id", table_name="vacancy_processing_events")
    op.drop_table("vacancy_processing_events")
