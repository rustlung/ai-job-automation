"""create manual vacancy crm sync states

Revision ID: 20260910_0005
Revises: 20260910_0004
"""

from alembic import op
import sqlalchemy as sa

revision = "20260910_0005"
down_revision = "20260910_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "manual_vacancy_crm_sync_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vacancy_id", sa.Integer(), nullable=False),
        sa.Column("presentation_key", sa.String(length=320), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("synced_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(length=64)),
        sa.Column("error_message_safe", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'synced', 'failed')",
            name="ck_manual_vacancy_crm_sync_states_status",
        ),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("vacancy_id", name="uq_manual_vacancy_crm_sync_states_vacancy_id"),
        sa.UniqueConstraint("presentation_key", name="uq_manual_vacancy_crm_sync_states_presentation_key"),
    )
    op.create_index(
        "ix_manual_vacancy_crm_sync_states_vacancy_id",
        "manual_vacancy_crm_sync_states",
        ["vacancy_id"],
    )
    op.create_index(
        "ix_manual_vacancy_crm_sync_states_presentation_key",
        "manual_vacancy_crm_sync_states",
        ["presentation_key"],
    )
    op.create_index(
        "ix_manual_vacancy_crm_sync_states_status",
        "manual_vacancy_crm_sync_states",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_manual_vacancy_crm_sync_states_status", table_name="manual_vacancy_crm_sync_states")
    op.drop_index("ix_manual_vacancy_crm_sync_states_presentation_key", table_name="manual_vacancy_crm_sync_states")
    op.drop_index("ix_manual_vacancy_crm_sync_states_vacancy_id", table_name="manual_vacancy_crm_sync_states")
    op.drop_table("manual_vacancy_crm_sync_states")
