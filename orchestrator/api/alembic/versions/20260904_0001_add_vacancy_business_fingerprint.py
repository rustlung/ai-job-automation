"""add vacancy business fingerprint

Revision ID: 20260904_0001
Revises: 20260810_0001
Create Date: 2026-09-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260904_0001"
down_revision: str | None = "20260810_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("vacancies", sa.Column("business_fingerprint", sa.String(length=64), nullable=True))
    op.create_index("ix_vacancies_business_fingerprint", "vacancies", ["business_fingerprint"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_vacancies_business_fingerprint", table_name="vacancies")
    op.drop_column("vacancies", "business_fingerprint")
