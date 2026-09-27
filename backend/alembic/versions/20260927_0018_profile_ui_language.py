"""Add global UI language without changing church communication preferences."""

import sqlalchemy as sa

from alembic import op

revision = "20260927_0018"
down_revision = "20260926_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADD COLUMN's constant default backfills existing rows without bypassing RLS.
    op.add_column(
        "profiles", sa.Column("ui_language", sa.String(10), nullable=False, server_default="en")
    )
    op.alter_column("profiles", "ui_language", server_default=None)


def downgrade() -> None:
    op.drop_column("profiles", "ui_language")
