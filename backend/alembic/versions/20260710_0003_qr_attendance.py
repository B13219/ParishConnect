"""add qr attendance windows

Revision ID: 20260710_0003
Revises: 20260710_0002
Create Date: 2026-07-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260710_0003"
down_revision: str | None = "20260710_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("events", sa.Column("qr_opens_at", sa.DateTime(), nullable=True))
    op.add_column("events", sa.Column("qr_closes_at", sa.DateTime(), nullable=True))
    op.add_column(
        "events",
        sa.Column("qr_rotation_seconds", sa.Integer(), nullable=False, server_default="60"),
    )
    op.add_column("attendance_records", sa.Column("household_person_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_attendance_records_household_person_id_household_people"),
        "attendance_records",
        "household_people",
        ["household_person_id"],
        ["id"],
    )
    op.alter_column("events", "qr_rotation_seconds", server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_attendance_records_household_person_id_household_people"),
        "attendance_records",
        type_="foreignkey",
    )
    op.drop_column("attendance_records", "household_person_id")
    op.drop_column("events", "qr_rotation_seconds")
    op.drop_column("events", "qr_closes_at")
    op.drop_column("events", "qr_opens_at")
