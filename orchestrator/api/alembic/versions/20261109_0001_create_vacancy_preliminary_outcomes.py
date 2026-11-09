"""create vacancy preliminary outcomes

Revision ID: 20261109_0001
Revises: 20261108_0001
"""

from alembic import op
import sqlalchemy as sa


revision = "20261109_0001"
down_revision = "20261108_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vacancy_preliminary_outcomes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vacancy_id", sa.Integer(), sa.ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("outcome_source", sa.String(length=16), nullable=False),
        sa.Column("processing_state", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("vacancy_id", "run_id", name="uq_vacancy_preliminary_outcomes_vacancy_run"),
    )
    op.create_index("ix_vacancy_preliminary_outcomes_vacancy_id", "vacancy_preliminary_outcomes", ["vacancy_id"])
    op.create_index("ix_vacancy_preliminary_outcomes_run_id", "vacancy_preliminary_outcomes", ["run_id"])
    op.create_index("ix_vacancy_preliminary_outcomes_processing_state", "vacancy_preliminary_outcomes", ["processing_state"])
    op.create_index("ix_vacancy_preliminary_outcomes_outcome", "vacancy_preliminary_outcomes", ["outcome"])


def downgrade() -> None:
    op.drop_index("ix_vacancy_preliminary_outcomes_outcome", table_name="vacancy_preliminary_outcomes")
    op.drop_index("ix_vacancy_preliminary_outcomes_processing_state", table_name="vacancy_preliminary_outcomes")
    op.drop_index("ix_vacancy_preliminary_outcomes_run_id", table_name="vacancy_preliminary_outcomes")
    op.drop_index("ix_vacancy_preliminary_outcomes_vacancy_id", table_name="vacancy_preliminary_outcomes")
    op.drop_table("vacancy_preliminary_outcomes")
