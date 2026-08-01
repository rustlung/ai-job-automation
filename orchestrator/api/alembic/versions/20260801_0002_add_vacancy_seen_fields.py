"""add vacancy seen fields

Revision ID: 20260801_0002
Revises: 20260801_0001
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260801_0002"
down_revision: str | None = "20260801_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("vacancies", sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vacancies", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vacancies", sa.Column("seen_count", sa.Integer(), nullable=True))

    op.execute(
        """
        UPDATE vacancies
        SET
            first_seen_at = created_at,
            last_seen_at = COALESCE(updated_at, created_at),
            seen_count = 1
        """
    )

    _run_vacancies_batch_upgrade()

    op.create_index("ix_vacancies_first_seen_at", "vacancies", ["first_seen_at"], unique=False)
    op.create_index("ix_vacancies_last_seen_at", "vacancies", ["last_seen_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_vacancies_last_seen_at", table_name="vacancies")
    op.drop_index("ix_vacancies_first_seen_at", table_name="vacancies")

    _run_vacancies_batch_downgrade()


def _run_vacancies_batch_upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys=OFF")
    with op.batch_alter_table("vacancies") as batch_op:
        batch_op.alter_column("first_seen_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch_op.alter_column("last_seen_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch_op.alter_column("seen_count", existing_type=sa.Integer(), nullable=False)
        batch_op.create_check_constraint("ck_vacancies_seen_count_positive", "seen_count >= 1")
    if op.get_bind().dialect.name == "sqlite":
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys=ON")


def _run_vacancies_batch_downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys=OFF")
    with op.batch_alter_table("vacancies") as batch_op:
        batch_op.drop_constraint("ck_vacancies_seen_count_positive", type_="check")
        batch_op.drop_column("seen_count")
        batch_op.drop_column("last_seen_at")
        batch_op.drop_column("first_seen_at")
    if op.get_bind().dialect.name == "sqlite":
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys=ON")
