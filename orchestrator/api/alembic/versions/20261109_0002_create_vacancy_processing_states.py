"""create vacancy processing states

Revision ID: 20261109_0002
Revises: 20261109_0001
"""

from alembic import op
import sqlalchemy as sa


revision = "20261109_0002"
down_revision = "20261109_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vacancy_processing_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vacancy_id", sa.Integer(), sa.ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("preview_snapshot", sa.JSON(), nullable=False),
        sa.Column("preliminary_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enrichment_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column("last_error_summary", sa.Text(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("vacancy_id", "run_id", name="uq_vacancy_processing_states_vacancy_run"),
    )
    op.create_index("ix_vacancy_processing_states_run_state", "vacancy_processing_states", ["run_id", "state"])
    op.create_index("ix_vacancy_processing_states_state_claim_expires_at", "vacancy_processing_states", ["state", "claim_expires_at"])
    op.create_index("ix_vacancy_processing_states_vacancy_id", "vacancy_processing_states", ["vacancy_id"])


def downgrade() -> None:
    op.drop_index("ix_vacancy_processing_states_vacancy_id", table_name="vacancy_processing_states")
    op.drop_index("ix_vacancy_processing_states_state_claim_expires_at", table_name="vacancy_processing_states")
    op.drop_index("ix_vacancy_processing_states_run_state", table_name="vacancy_processing_states")
    op.drop_table("vacancy_processing_states")
