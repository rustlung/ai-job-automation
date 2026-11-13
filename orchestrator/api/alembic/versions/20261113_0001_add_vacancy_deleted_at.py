"""add logical vacancy deletion

Revision ID: 20261113_0001
Revises: 20261109_0002
"""

from alembic import op
import sqlalchemy as sa


revision = "20261113_0001"
down_revision = "20261109_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADD COLUMN is native in every SQLite version we support.  Avoiding a
    # batch table rebuild is essential here because vacancies are referenced
    # by historical processing rows with ON DELETE CASCADE.
    op.add_column("vacancies", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_vacancies_deleted_at", "vacancies", ["deleted_at"], unique=False)


def downgrade() -> None:
    connection = op.get_bind()
    sqlite = connection.dialect.name == "sqlite"
    foreign_keys_enabled = bool(connection.exec_driver_sql("PRAGMA foreign_keys").scalar()) if sqlite else False
    if sqlite and foreign_keys_enabled:
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys=OFF")
        if connection.exec_driver_sql("PRAGMA foreign_keys").scalar() != 0:
            raise RuntimeError("Cannot downgrade logical vacancy deletion while SQLite foreign keys are enabled")
    try:
        with op.batch_alter_table("vacancies", recreate="always") as batch_op:
            batch_op.drop_index("ix_vacancies_deleted_at")
            batch_op.drop_column("deleted_at")
    finally:
        if sqlite and foreign_keys_enabled:
            with op.get_context().autocommit_block():
                op.execute("PRAGMA foreign_keys=ON")
