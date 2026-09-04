"""add web backend foundation

Revision ID: 20260904_0002
Revises: 20260904_0001
Create Date: 2026-09-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260904_0002"
down_revision: str | None = "20260904_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sheet_name", sa.String(length=255), nullable=False),
        sa.Column("email_to", sa.String(length=320), nullable=False),
        sa.Column("max_pages_override", sa.Integer(), nullable=True),
        sa.Column("max_filter_items_override", sa.Integer(), nullable=True),
        sa.Column("max_enrich_items_override", sa.Integer(), nullable=True),
        sa.Column("crm_sync_priorities", sa.JSON(), nullable=False),
        sa.Column("top_vacancy_limit", sa.Integer(), nullable=False),
        sa.Column("google_crm_sync_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("trigger_source", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("profile_ids", sa.JSON(), nullable=False),
        sa.Column("config_snapshot", sa.JSON(), nullable=False),
        sa.Column("stats_snapshot", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index("ix_pipeline_runs_run_id", "pipeline_runs", ["run_id"], unique=True)
    op.create_index("ix_pipeline_runs_status", "pipeline_runs", ["status"], unique=False)
    op.create_index("ix_pipeline_runs_trigger_source", "pipeline_runs", ["trigger_source"], unique=False)
    op.create_index("ix_pipeline_runs_started_at", "pipeline_runs", ["started_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pipeline_runs_started_at", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_trigger_source", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_status", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_run_id", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")
    op.drop_table("operational_settings")
