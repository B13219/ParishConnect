"""track SMS delivery metadata

Revision ID: 20260921_0014
Revises: 20260921_0013
Create Date: 2026-09-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260921_0014"
down_revision: str | None = "20260921_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "message_recipients",
        sa.Column("provider_status_code", sa.Integer(), nullable=True),
    )
    op.add_column(
        "message_recipients",
        sa.Column("provider_cost", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "message_recipients",
        sa.Column("failure_reason", sa.String(length=160), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("message_recipients", "failure_reason")
    op.drop_column("message_recipients", "provider_cost")
    op.drop_column("message_recipients", "provider_status_code")
