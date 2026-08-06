"""add branch geofence settings

Revision ID: 20260806_0008
Revises: 20260711_0007
Create Date: 2026-08-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260806_0008"
down_revision: str | None = "20260711_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "branches",
        sa.Column("latitude", sa.Float(), nullable=True),
    )
    op.add_column(
        "branches",
        sa.Column("longitude", sa.Float(), nullable=True),
    )
    op.add_column(
        "branches",
        sa.Column(
            "attendance_radius_meters",
            sa.Integer(),
            nullable=False,
            server_default="100",
        ),
    )
    op.add_column(
        "branches",
        sa.Column(
            "geofence_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.alter_column(
        "branches",
        "attendance_radius_meters",
        server_default=None,
    )
    op.alter_column(
        "branches",
        "geofence_enabled",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("branches", "geofence_enabled")
    op.drop_column("branches", "attendance_radius_meters")
    op.drop_column("branches", "longitude")
    op.drop_column("branches", "latitude")