"""create vacancy user state crm sync states

Revision ID: 20260910_0003
Revises: 20260910_0002
"""

from alembic import op
import sqlalchemy as sa

revision = "20260910_0003"
down_revision = "20260910_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vacancy_user_state_crm_sync_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("presentation_key", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("synced_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(length=64)),
        sa.Column("error_message_safe", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'synced', 'failed')", name="ck_vacancy_user_state_crm_sync_states_status"),
        sa.UniqueConstraint("presentation_key", name="uq_vacancy_user_state_crm_sync_states_presentation_key"),
    )
    op.create_index("ix_vacancy_user_state_crm_sync_states_presentation_key", "vacancy_user_state_crm_sync_states", ["presentation_key"])
    op.create_index("ix_vacancy_user_state_crm_sync_states_status", "vacancy_user_state_crm_sync_states", ["status"])


def downgrade() -> None:
    op.drop_index("ix_vacancy_user_state_crm_sync_states_status", table_name="vacancy_user_state_crm_sync_states")
    op.drop_index("ix_vacancy_user_state_crm_sync_states_presentation_key", table_name="vacancy_user_state_crm_sync_states")
    op.drop_table("vacancy_user_state_crm_sync_states")
