"""add recurring service templates

Revision ID: 60d8f54791c2
Revises: 20260806_0008
Create Date: 2026-08-07 16:12:07.439678
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '60d8f54791c2'
down_revision: str | None = '794c80156f4e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

