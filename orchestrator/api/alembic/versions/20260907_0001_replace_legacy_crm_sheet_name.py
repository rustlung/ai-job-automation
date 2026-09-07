"""replace legacy CRM sheet name

Revision ID: 20260907_0001
Revises: 20260904_0002
Create Date: 2026-09-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260907_0001"
down_revision: str | None = "20260904_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_SHEET_NAME = "Вакансии_TEST"
PRODUCTION_SHEET_NAME = "Вакансии"


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            """
            UPDATE operational_settings
            SET sheet_name = :production_sheet_name
            WHERE sheet_name = :legacy_sheet_name
            """
        ),
        {
            "legacy_sheet_name": LEGACY_SHEET_NAME,
            "production_sheet_name": PRODUCTION_SHEET_NAME,
        },
    )


def downgrade() -> None:
    # Downgrading must not restore a removed production sheet name.
    pass
