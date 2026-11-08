"""make vacancy description nullable for discovered previews

Revision ID: 20261108_0001
Revises: 20260910_0005
"""

from alembic import op
import sqlalchemy as sa


revision = "20261108_0001"
down_revision = "20260910_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    sqlite = connection.dialect.name == "sqlite"
    foreign_keys_enabled = bool(connection.exec_driver_sql("PRAGMA foreign_keys").scalar()) if sqlite else False
    if sqlite and foreign_keys_enabled:
        # SQLite rebuilds the referenced table for this change. Disable FK
        # enforcement around the rebuild so ON DELETE CASCADE cannot erase
        # analyses, applications or processing events while the old table drops.
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys=OFF")
        if connection.exec_driver_sql("PRAGMA foreign_keys").scalar() != 0:
            raise RuntimeError("Cannot make vacancies.description nullable while SQLite foreign keys are enabled")
    try:
        with op.batch_alter_table("vacancies", recreate="always") as batch_op:
            batch_op.alter_column("description", existing_type=sa.Text(), nullable=True)
    finally:
        if sqlite and foreign_keys_enabled:
            with op.get_context().autocommit_block():
                op.execute("PRAGMA foreign_keys=ON")


def downgrade() -> None:
    connection = op.get_bind()
    null_count = connection.execute(sa.text("SELECT COUNT(*) FROM vacancies WHERE description IS NULL")).scalar_one()
    if null_count:
        raise RuntimeError(
            "Cannot downgrade: discovered vacancies with NULL description exist. "
            "Complete enrichment or remove them explicitly before downgrading."
        )
    sqlite = connection.dialect.name == "sqlite"
    foreign_keys_enabled = bool(connection.exec_driver_sql("PRAGMA foreign_keys").scalar()) if sqlite else False
    if sqlite and foreign_keys_enabled:
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys=OFF")
        if connection.exec_driver_sql("PRAGMA foreign_keys").scalar() != 0:
            raise RuntimeError("Cannot downgrade while SQLite foreign keys are enabled")
    try:
        with op.batch_alter_table("vacancies", recreate="always") as batch_op:
            batch_op.alter_column("description", existing_type=sa.Text(), nullable=False)
    finally:
        if sqlite and foreign_keys_enabled:
            with op.get_context().autocommit_block():
                op.execute("PRAGMA foreign_keys=ON")
