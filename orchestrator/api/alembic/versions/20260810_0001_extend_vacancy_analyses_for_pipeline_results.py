"""extend vacancy analyses for pipeline results

Revision ID: 20260810_0001
Revises: 20260801_0002
Create Date: 2026-08-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260810_0001"
down_revision: str | None = "20260801_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _run_batch_upgrade()
    op.create_index("ix_vacancy_analyses_run_id", "vacancy_analyses", ["run_id"], unique=False)
    op.create_index("ix_vacancy_analyses_priority", "vacancy_analyses", ["priority"], unique=False)
    op.create_index("ix_vacancy_analyses_final_score", "vacancy_analyses", ["final_score"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_vacancy_analyses_final_score", table_name="vacancy_analyses")
    op.drop_index("ix_vacancy_analyses_priority", table_name="vacancy_analyses")
    op.drop_index("ix_vacancy_analyses_run_id", table_name="vacancy_analyses")
    _run_batch_downgrade()


def _run_batch_upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys=OFF")
    with op.batch_alter_table("vacancy_analyses") as batch_op:
        batch_op.drop_constraint("uq_vacancy_analyses_identity", type_="unique")
        batch_op.add_column(sa.Column("run_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("final_score", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("priority", sa.String(length=8), nullable=True))
        batch_op.add_column(sa.Column("preliminary_snapshot", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("deterministic_features", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("semantic_snapshot", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("score_breakdown", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("hard_blockers", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("risks", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("provenance", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("vacancy_snapshot", sa.JSON(), nullable=True))
        batch_op.create_unique_constraint("uq_vacancy_analyses_vacancy_run", ["vacancy_id", "run_id"])
        batch_op.create_check_constraint(
            "ck_vacancy_analyses_final_score_range",
            "final_score IS NULL OR (final_score >= 0 AND final_score <= 100)",
        )
    if op.get_bind().dialect.name == "sqlite":
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys=ON")


def _run_batch_downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys=OFF")
    with op.batch_alter_table("vacancy_analyses") as batch_op:
        batch_op.drop_constraint("ck_vacancy_analyses_final_score_range", type_="check")
        batch_op.drop_constraint("uq_vacancy_analyses_vacancy_run", type_="unique")
        batch_op.drop_column("vacancy_snapshot")
        batch_op.drop_column("provenance")
        batch_op.drop_column("risks")
        batch_op.drop_column("hard_blockers")
        batch_op.drop_column("score_breakdown")
        batch_op.drop_column("semantic_snapshot")
        batch_op.drop_column("deterministic_features")
        batch_op.drop_column("preliminary_snapshot")
        batch_op.drop_column("priority")
        batch_op.drop_column("final_score")
        batch_op.drop_column("run_id")
        batch_op.create_unique_constraint(
            "uq_vacancy_analyses_identity",
            ["vacancy_id", "provider", "model", "prompt_version"],
        )
    if op.get_bind().dialect.name == "sqlite":
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys=ON")
