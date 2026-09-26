"""add denomination-aware staff office titles

Revision ID: 20260926_0017
Revises: 20260925_0016
Create Date: 2026-09-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260926_0017"
down_revision: str | None = "20260925_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("position_title", sa.String(length=160), nullable=True))
    op.add_column(
        "users",
        sa.Column("organization_level", sa.String(length=80), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "organization_level")
    op.drop_column("users", "position_title")
