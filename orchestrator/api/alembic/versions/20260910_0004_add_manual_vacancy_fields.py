"""add manual vacancy fields

Revision ID: 20260910_0004
Revises: 20260910_0003
"""
from alembic import op
import sqlalchemy as sa

revision = "20260910_0004"
down_revision = "20260910_0003"
branch_labels = None
depends_on = None

def upgrade() -> None:
    with op.batch_alter_table("vacancies") as batch:
        batch.alter_column("url", existing_type=sa.String(length=2048), nullable=True)
        batch.add_column(sa.Column("origin", sa.String(length=32), nullable=True))

def downgrade() -> None:
    with op.batch_alter_table("vacancies") as batch:
        batch.drop_column("origin")
        batch.alter_column("url", existing_type=sa.String(length=2048), nullable=False)
