"""add contribution receipt details

Revision ID: 20260711_0004
Revises: 20260710_0003
Create Date: 2026-07-11
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260711_0004"
down_revision: str | None = "20260710_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "contributions",
        sa.Column("payment_method", sa.String(length=40), nullable=False, server_default="cash"),
    )
    op.add_column("contributions", sa.Column("reference_code", sa.String(length=120), nullable=True))
    op.alter_column("contributions", "payment_method", server_default=None)


def downgrade() -> None:
    op.drop_column("contributions", "reference_code")
    op.drop_column("contributions", "payment_method")
